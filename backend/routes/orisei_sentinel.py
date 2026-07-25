"""routes.orisei_sentinel — self-repair monitoring agent.

Continuously health-checks the load-routing logic and AUTO-PATCHES anomalies:
stalled loads, driverless bookings, dead backhaul hunts, config drift, and a
crashed autopilot loop. Every anomaly + patch lands in the repair log.
"""
import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import Depends

logger = logging.getLogger(__name__)

STALL_MINUTES = 25          # longest legit stage (in_transit ~11 min) x2 + slack
HUNT_DEAD_MINUTES = 6       # hunts must scan every cycle (120s)
HEARTBEAT_MINUTES = 5       # autopilot loop writes a heartbeat each cycle
SAFE_CONFIG = {"daily_limit": 10, "min_margin": 150.0}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _age_min(iso: Optional[str]) -> float:
    if not iso:
        return 1e9
    try:
        return (datetime.now(timezone.utc) - datetime.fromisoformat(iso)).total_seconds() / 60
    except Exception:  # noqa: BLE001
        return 1e9


def build_sentinel_router(*, api_router, db, get_current_user, require_role, run_cycle):

    async def _log(check: str, severity: str, target: str, issue: str, patch: str) -> Dict[str, Any]:
        doc = {"repair_id": f"FIX-{uuid.uuid4().hex[:6].upper()}", "at": _now(), "check": check,
               "severity": severity, "target": target, "issue": issue, "patch": patch}
        await db.sentinel_repairs.insert_one(dict(doc))
        return doc

    async def _assign_driver(load: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        mc = (load.get("carrier") or {}).get("mc_number", "")
        d = await db.dispatch_drivers.find_one({"is_active": True, "mc_number": mc}, {"_id": 0},
                                               sort=[("last_assigned_at", 1)])
        if not d:
            d = await db.dispatch_drivers.find_one({"is_active": True}, {"_id": 0},
                                                   sort=[("last_assigned_at", 1)])
        if d:
            await db.dispatch_drivers.update_one({"driver_id": d["driver_id"]},
                                                 {"$set": {"last_assigned_at": _now()}})
        return d

    async def run_sweep() -> Dict[str, Any]:
        checks: List[Dict[str, Any]] = []
        repairs: List[Dict[str, Any]] = []

        # 1) stalled loads — stuck in a stage far past the sim timers
        found = patched = 0
        active = await db.autopilot_loads.find({"stage": {"$nin": ["completed"]}}, {"_id": 0}).to_list(300)
        for ld in active:
            if _age_min(ld.get("stage_at") or ld.get("created_at")) >= STALL_MINUTES:
                found += 1
                await db.autopilot_loads.update_one(
                    {"load_id": ld["load_id"]},
                    {"$set": {"stage_at": "2020-01-01T00:00:00+00:00"},
                     "$push": {"timeline": {"at": _now(), "stage": ld["stage"],
                                            "note": "Sentinel: stage stalled — timer re-armed, load re-kicked"}}})
                repairs.append(await _log("stalled_loads", "medium", ld["load_id"],
                                          f"stuck at '{ld['stage']}' for {int(_age_min(ld.get('stage_at')))} min",
                                          "stage timer re-armed — lifecycle advances next cycle"))
                patched += 1
        checks.append({"check": "stalled_loads", "label": "Stalled load-routing stages",
                       "found": found, "patched": patched})

        # 2) driverless bookings — every booked load must carry a driver
        found = patched = 0
        for ld in active:
            if not ld.get("driver"):
                found += 1
                d = await _assign_driver(ld)
                if d:
                    brief = {k: d.get(k, "") for k in ("driver_id", "name", "phone", "cdl_number", "home_base")}
                    await db.autopilot_loads.update_one(
                        {"load_id": ld["load_id"]},
                        {"$set": {"driver": brief},
                         "$push": {"timeline": {"at": _now(), "stage": ld["stage"],
                                                "note": f"Sentinel: missing driver — {d['name']} assigned, docs updated"}}})
                    repairs.append(await _log("driverless_loads", "high", ld["load_id"],
                                              "booked load had no driver on file",
                                              f"driver {d['name']} (CDL {d['cdl_number']}) auto-assigned"))
                    patched += 1
        checks.append({"check": "driverless_loads", "label": "Bookings missing a driver",
                       "found": found, "patched": patched})

        # 3) dead backhaul hunts — hunting but no scan inside the window
        found = patched = 0
        hunts = await db.backhaul_hunts.find({"status": "hunting"}).to_list(100)
        for h in hunts:
            if _age_min(h.get("last_scan_at") or h.get("opened_at")) >= HUNT_DEAD_MINUTES:
                found += 1
                await db.backhaul_hunts.update_one({"hunt_id": h["hunt_id"]},
                                                   {"$set": {"opened_at": _now(), "last_scan_at": _now()}})
                repairs.append(await _log("dead_hunts", "medium", h["hunt_id"],
                                          f"hunt {h['stranded_at']} → {h['home_base']} stopped scanning",
                                          "hunt window re-armed — scanning resumes next cycle"))
                patched += 1
        checks.append({"check": "dead_hunts", "label": "Backhaul hunts gone quiet",
                       "found": found, "patched": patched})

        # 4) config drift — reset out-of-range routing config to safe defaults
        found = patched = 0
        cfg = await db.broker_autopilot_config.find_one({"_id": "cfg"}) or {}
        fixes = {}
        dl = cfg.get("daily_limit", 10)
        if not isinstance(dl, int) or not 1 <= dl <= 25:
            fixes["daily_limit"] = SAFE_CONFIG["daily_limit"]
        mm = cfg.get("min_margin", 150.0)
        if not isinstance(mm, (int, float)) or not 0 <= mm <= 2000:
            fixes["min_margin"] = SAFE_CONFIG["min_margin"]
        if fixes:
            found = patched = len(fixes)
            await db.broker_autopilot_config.update_one({"_id": "cfg"}, {"$set": fixes}, upsert=True)
            repairs.append(await _log("config_drift", "high", "broker_autopilot_config",
                                      f"invalid config values: {list(fixes)}",
                                      f"reset to safe defaults {fixes}"))
        checks.append({"check": "config_drift", "label": "Routing config sanity",
                       "found": found, "patched": patched})

        # 5) autopilot loop heartbeat — if the loop died, run the cycle directly
        found = patched = 0
        hb = await db.sentinel_heartbeats.find_one({"_id": "autopilot_loop"})
        hb_age = _age_min(hb.get("at") if hb else None)
        if hb_age >= HEARTBEAT_MINUTES:
            found = 1
            try:
                await run_cycle()
                repairs.append(await _log("loop_heartbeat", "critical", "autopilot_loop",
                                          f"no heartbeat for {int(min(hb_age, 9999))} min — loop presumed down",
                                          "Sentinel executed the routing cycle directly; loads kept moving"))
                patched = 1
            except Exception as e:  # noqa: BLE001
                logger.exception("sentinel direct cycle failed")
                repairs.append(await _log("loop_heartbeat", "critical", "autopilot_loop",
                                          f"loop down and direct cycle failed: {type(e).__name__}",
                                          "escalate — see backend logs"))
        checks.append({"check": "loop_heartbeat", "label": "Autopilot loop heartbeat",
                       "found": found, "patched": patched, "heartbeat_age_min": round(min(hb_age, 9999), 1)})

        # 6) orphan hunts — booked hunts pointing at loads that no longer exist
        found = patched = 0
        booked = await db.backhaul_hunts.find({"status": "booked"}).to_list(100)
        for h in booked:
            if h.get("booked_load_id") and not await db.autopilot_loads.find_one({"load_id": h["booked_load_id"]}):
                found += 1
                await db.backhaul_hunts.update_one({"hunt_id": h["hunt_id"]},
                                                   {"$set": {"status": "expired", "closed_at": _now()}})
                repairs.append(await _log("orphan_hunts", "low", h["hunt_id"],
                                          f"booked load {h['booked_load_id']} missing from the system",
                                          "hunt closed as expired"))
                patched += 1
        checks.append({"check": "orphan_hunts", "label": "Orphaned backhaul bookings",
                       "found": found, "patched": patched})

        healthy = all(c["found"] == c["patched"] for c in checks)
        state = {"last_sweep_at": _now(), "checks": checks, "healthy": healthy,
                 "anomalies_found": sum(c["found"] for c in checks),
                 "patched": sum(c["patched"] for c in checks)}
        await db.sentinel_state.update_one({"_id": "state"}, {"$set": state, "$inc": {"sweeps": 1}}, upsert=True)
        return {"ok": True, **state, "repairs": repairs}

    # ---------------- endpoints ----------------
    @api_router.get("/self-repair/status")
    async def sentinel_status(_=Depends(get_current_user)) -> Dict[str, Any]:
        state = await db.sentinel_state.find_one({"_id": "state"}, {"_id": 0}) or {}
        log = await db.sentinel_repairs.find({}, {"_id": 0}).sort("at", -1).to_list(50)
        totals = {"repairs_total": await db.sentinel_repairs.count_documents({})}
        return {"state": state, "repair_log": log, **totals,
                "thresholds": {"stall_minutes": STALL_MINUTES, "hunt_dead_minutes": HUNT_DEAD_MINUTES,
                               "heartbeat_minutes": HEARTBEAT_MINUTES}}

    @api_router.post("/self-repair/sweep")
    async def sentinel_sweep(_=Depends(require_role("admin", "dispatcher"))) -> Dict[str, Any]:
        return await run_sweep()

    return run_sweep


async def sentinel_loop(run_sweep):
    await asyncio.sleep(30)
    while True:
        try:
            await run_sweep()
        except Exception:  # noqa: BLE001
            logger.exception("sentinel sweep failed")
        await asyncio.sleep(120)
