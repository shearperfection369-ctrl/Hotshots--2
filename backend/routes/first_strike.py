"""routes.first_strike — the Load Hunter's competitive edge layer.

Seven weapons: continuous auto-scan loop, dynamic bid calculator with an
aggressiveness dial, per-lane win/loss learning, carrier-proximity boost,
poster-pattern predictions, after-hours aggression, relationship scoring.
Simulated outcomes until real board APIs are keyed.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import random
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

logger = logging.getLogger("tennant_tms.first_strike")

DEFAULT_FS_CONFIG: Dict[str, Any] = {
    "enabled": True,
    "interval_sec": 45,
    "aggressiveness": 55,        # 0 conservative … 100 cutthroat
    "after_hours_boost": True,   # push harder when competitors are offline
    "learning_enabled": True,    # per-lane win/loss auto-adjustment
    "max_bids_per_cycle": 4,
    "min_margin_pct": 10.0,
}

STATE_RE = re.compile(r"\b([A-Z]{2})\b")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _central_now() -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=6)


def _is_after_hours() -> bool:
    ct = _central_now()
    return ct.weekday() >= 5 or ct.hour < 8 or ct.hour >= 17


def _lane_key(load: Dict[str, Any]) -> str:
    o = (load.get("origin") or "")[-2:].upper()
    d = (load.get("destination") or "")[-2:].upper()
    return f"{o}-{d}"


def _states_of(text: str) -> set:
    return set(STATE_RE.findall(text or ""))


class FsConfigIn(BaseModel):
    enabled: Optional[bool] = None
    interval_sec: Optional[int] = Field(None, ge=15, le=600)
    aggressiveness: Optional[int] = Field(None, ge=0, le=100)
    after_hours_boost: Optional[bool] = None
    learning_enabled: Optional[bool] = None
    max_bids_per_cycle: Optional[int] = Field(None, ge=1, le=20)
    min_margin_pct: Optional[float] = Field(None, ge=0, le=50)


class BidIn(BaseModel):
    load_id: str


def build_first_strike_router(*, api_router: APIRouter, db,
                              get_current_user: Callable) -> Callable:
    router = APIRouter(prefix="/load-hunter/first-strike", tags=["first-strike"])

    async def _config() -> Dict[str, Any]:
        row = await db.first_strike_config.find_one({"_id": "default"}, {"_id": 0})
        return {**DEFAULT_FS_CONFIG, **(row or {})}

    async def _all_loads() -> List[Dict[str, Any]]:
        from routes.brokerage import LOAD_BOARDS, _gen_loads_for_board  # type: ignore
        out: List[Dict[str, Any]] = []
        for b in LOAD_BOARDS:
            rows = await db.brokerage_loads.find({"board_id": b["id"]}, {"_id": 0}).to_list(50)
            if not rows:
                rows = _gen_loads_for_board(b["id"], count=14)
            for r in rows:
                r = dict(r)
                r["board_id"] = b["id"]
                rate = float(r.get("rate_usd") or 0)
                cpay = float(r.get("carrier_pay_usd") or 0)
                if not r.get("margin_pct") and rate and cpay:
                    r["margin_pct"] = round((rate - cpay) / rate * 100, 1)
                out.append(r)
        return out

    async def _lane_stats() -> Dict[str, Dict[str, Any]]:
        rows = await db.hunter_bid_outcomes.find({}, {"_id": 0, "lane": 1, "won": 1}).to_list(4000)
        agg: Dict[str, Dict[str, int]] = {}
        for r in rows:
            s = agg.setdefault(r["lane"], {"bids": 0, "wins": 0})
            s["bids"] += 1
            s["wins"] += 1 if r.get("won") else 0
        return {k: {**v, "win_rate": round(v["wins"] / v["bids"], 3) if v["bids"] else 0.0}
                for k, v in agg.items()}

    async def _known_posters() -> set:
        rows = await db.brokerage_bookings.distinct("customer_name")
        return {r for r in rows if r}

    async def _bench_states() -> set:
        carriers = await db.dispatch_carriers.find({"is_active": True}, {"_id": 0}).to_list(300)
        states: set = set()
        for c in carriers:
            for key in ("home_base", "domicile", "city_state", "location", "base_city"):
                states |= _states_of(str(c.get(key) or ""))
            sa = c.get("service_area") or c.get("service_states") or []
            if isinstance(sa, list):
                states |= {str(s).upper()[:2] for s in sa if s}
            else:
                states |= _states_of(str(sa))
        return states

    def _price_bid(load: Dict[str, Any], cfg: Dict[str, Any], lane_stat: Optional[Dict[str, Any]],
                   after_hours: bool, known: bool, proximate: bool) -> Dict[str, Any]:
        posted = float(load.get("rate_usd") or 0)
        aggr = int(cfg.get("aggressiveness", 55))
        discount = aggr / 100 * 0.06
        adjustment = "—"
        if cfg.get("learning_enabled") and lane_stat and lane_stat["bids"] >= 3:
            if lane_stat["win_rate"] < 0.30:
                discount += 0.02
                adjustment = "tightened −2% (losing lane)"
            elif lane_stat["win_rate"] > 0.70:
                discount -= 0.015
                adjustment = "harvesting +1.5% (winning lane)"
        if after_hours and cfg.get("after_hours_boost"):
            discount = max(0.0, discount - 0.01)
        discount = max(0.0, min(discount, 0.10))
        bid = round(posted * (1 - discount))
        prob = 0.32 + aggr / 100 * 0.38
        prob += 0.12 if after_hours else 0.0
        prob += 0.10 if known else 0.0
        prob += 0.08 if proximate else 0.0
        prob += (discount - 0.033) * 1.5
        prob = max(0.05, min(prob, 0.95))
        badges = []
        if known:
            badges.append("known-shipper")
        if proximate:
            badges.append("truck-nearby")
        if after_hours:
            badges.append("after-hours")
        return {"suggested_bid_usd": bid, "discount_pct": round(discount * 100, 2),
                "win_probability": round(prob, 3), "badges": badges,
                "lane_adjustment": adjustment, "posted_rate_usd": posted}

    async def _fire_bid(load: Dict[str, Any], cfg: Dict[str, Any], lane_stats: Dict[str, Any],
                        known_posters: set, bench: set, auto: bool,
                        response_sec: float) -> Dict[str, Any]:
        lane = _lane_key(load)
        after_hours = _is_after_hours()
        known = (load.get("shipper") or "") in known_posters
        proximate = bool(_states_of(load.get("origin") or "") & bench)
        pricing = _price_bid(load, cfg, lane_stats.get(lane), after_hours, known, proximate)
        won = random.random() < pricing["win_probability"]
        outcome = {
            "id": str(uuid.uuid4()), "at": _now_iso(), "auto": auto,
            "load_id": load.get("load_id"), "board_id": load.get("board_id"),
            "lane": lane, "poster": load.get("shipper"),
            "origin": load.get("origin"), "destination": load.get("destination"),
            "equipment": load.get("equipment"), "won": won,
            "response_sec": round(response_sec, 1), "after_hours": after_hours,
            **pricing,
        }
        await db.hunter_bid_outcomes.insert_one(dict(outcome))
        return outcome

    async def strike_cycle() -> Dict[str, Any]:
        cfg = await _config()
        if not cfg.get("enabled"):
            return {"skipped": True, "reason": "disabled"}
        t0 = datetime.now(timezone.utc)
        loads = await _all_loads()
        lane_stats = await _lane_stats()
        known = await _known_posters()
        bench = await _bench_states()

        seen_row = await db.first_strike_seen.find_one({"_id": "seen"}) or {}
        first_seen: Dict[str, str] = seen_row.get("map") or {}
        already_bid = set(await db.hunter_bid_outcomes.distinct("load_id"))

        now = datetime.now(timezone.utc)
        candidates = []
        for l in loads:
            lid = l.get("load_id")
            if lid not in first_seen:
                first_seen[lid] = now.isoformat()
            if lid in already_bid:
                continue
            if float(l.get("margin_pct") or 0) < float(cfg.get("min_margin_pct", 10)):
                continue
            candidates.append(l)
        candidates.sort(key=lambda l: float(l.get("margin_pct") or 0), reverse=True)

        fired = []
        for l in candidates[: int(cfg.get("max_bids_per_cycle", 4))]:
            seen_at = datetime.fromisoformat(first_seen[l["load_id"]])
            response_sec = max(0.8, (now - seen_at).total_seconds())
            fired.append(await _fire_bid(l, cfg, lane_stats, known, bench, auto=True,
                                         response_sec=min(response_sec, 300)))

        if len(first_seen) > 3000:
            first_seen = dict(list(first_seen.items())[-3000:])
        await db.first_strike_seen.update_one(
            {"_id": "seen"}, {"$set": {"map": first_seen, "at": _now_iso()}}, upsert=True)

        cycle = {"at": _now_iso(), "scanned": len(loads), "candidates": len(candidates),
                 "bids": len(fired), "wins": sum(1 for f in fired if f["won"]),
                 "avg_response_sec": round(sum(f["response_sec"] for f in fired) / len(fired), 1) if fired else None,
                 "after_hours": _is_after_hours(),
                 "elapsed_ms": round((datetime.now(timezone.utc) - t0).total_seconds() * 1000, 1)}
        await db.fs_cycles.insert_one(dict(cycle))
        await db.sentinel_heartbeats.update_one(
            {"_id": "first_strike_loop"}, {"$set": {"at": _now_iso()}}, upsert=True)
        return cycle

    def _predictions_for(posters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        preds = []
        ct = _central_now()
        for p in posters:
            name = p["poster"]
            h = int(hashlib.md5(name.encode()).hexdigest()[:4], 16)
            hour, minute = 6 + h % 10, h % 60
            nxt = ct.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if nxt <= ct:
                nxt += timedelta(days=1)
            while nxt.weekday() >= 5:
                nxt += timedelta(days=1)
            preds.append({"poster": name, "sample_size": p["count"],
                          "pattern": f"posts ~{hour:02d}:{minute:02d} CT weekdays",
                          "next_predicted_ct": nxt.strftime("%a %H:%M CT"),
                          "alert": f"Call {name} 15 min before {hour:02d}:{minute:02d} CT — beat the post"})
        return preds

    @router.get("/status")
    async def status(_=Depends(get_current_user)) -> Dict[str, Any]:
        cfg = await _config()
        outcomes = await db.hunter_bid_outcomes.find({}, {"_id": 0}).sort("at", -1).to_list(2000)
        bids = len(outcomes)
        wins = sum(1 for o in outcomes if o.get("won"))
        avg_resp = round(sum(o.get("response_sec") or 0 for o in outcomes) / bids, 1) if bids else None
        lane_stats = await _lane_stats()
        lanes = sorted(({"lane": k, **v} for k, v in lane_stats.items()),
                       key=lambda x: x["bids"], reverse=True)[:10]
        for ln in lanes:
            if ln["bids"] >= 3 and ln["win_rate"] < 0.30:
                ln["adjustment"] = "tightened −2%"
            elif ln["bids"] >= 3 and ln["win_rate"] > 0.70:
                ln["adjustment"] = "harvesting +1.5%"
            else:
                ln["adjustment"] = "—"
        agg: Dict[str, int] = {}
        for o in outcomes:
            if o.get("poster"):
                agg[o["poster"]] = agg.get(o["poster"], 0) + 1
        top_posters = [{"poster": k, "count": v} for k, v in
                       sorted(agg.items(), key=lambda x: x[1], reverse=True)[:6]]
        hb = await db.sentinel_heartbeats.find_one({"_id": "first_strike_loop"}) or {}
        cycles = await db.fs_cycles.find({}, {"_id": 0}).sort("at", -1).to_list(5)
        return {"config": cfg, "after_hours_now": _is_after_hours(),
                "loop_heartbeat": hb.get("at"),
                "totals": {"bids": bids, "wins": wins,
                           "win_rate": round(wins / bids, 3) if bids else None,
                           "avg_response_sec": avg_resp,
                           "revenue_won_usd": round(sum(o.get("suggested_bid_usd") or 0
                                                        for o in outcomes if o.get("won")), 0)},
                "lane_learning": lanes, "predictions": _predictions_for(top_posters),
                "recent_cycles": cycles, "recent_outcomes": outcomes[:8],
                "simulated": True}

    @router.post("/config")
    async def set_config(payload: FsConfigIn, _=Depends(get_current_user)) -> Dict[str, Any]:
        updates = {k: v for k, v in payload.model_dump().items() if v is not None}
        if updates:
            await db.first_strike_config.update_one(
                {"_id": "default"}, {"$set": updates}, upsert=True)
        return {"ok": True, "config": await _config()}

    @router.get("/candidates")
    async def candidates(_=Depends(get_current_user)) -> Dict[str, Any]:
        cfg = await _config()
        loads = await _all_loads()
        lane_stats = await _lane_stats()
        known = await _known_posters()
        bench = await _bench_states()
        already = set(await db.hunter_bid_outcomes.distinct("load_id"))
        after_hours = _is_after_hours()
        items = []
        for l in loads:
            if l.get("load_id") in already or float(l.get("margin_pct") or 0) < float(cfg.get("min_margin_pct", 10)):
                continue
            lane = _lane_key(l)
            pricing = _price_bid(l, cfg, lane_stats.get(lane), after_hours,
                                 (l.get("shipper") or "") in known,
                                 bool(_states_of(l.get("origin") or "") & bench))
            items.append({"load_id": l.get("load_id"), "board_id": l.get("board_id"),
                          "poster": l.get("shipper"), "lane": lane,
                          "origin": l.get("origin"), "destination": l.get("destination"),
                          "equipment": l.get("equipment"), "miles": l.get("miles"),
                          "margin_pct": l.get("margin_pct"), **pricing})
        items.sort(key=lambda x: x["win_probability"], reverse=True)
        return {"items": items[:8], "after_hours_now": after_hours}

    @router.post("/bid")
    async def manual_bid(payload: BidIn, _=Depends(get_current_user)) -> Dict[str, Any]:
        cfg = await _config()
        loads = await _all_loads()
        load = next((l for l in loads if l.get("load_id") == payload.load_id), None)
        if not load:
            return {"ok": False, "error": "Load no longer on the boards"}
        outcome = await _fire_bid(load, cfg, await _lane_stats(), await _known_posters(),
                                  await _bench_states(), auto=False, response_sec=1.2)
        return {"ok": True, "outcome": outcome}

    api_router.include_router(router)
    return strike_cycle


async def first_strike_loop(strike_cycle: Callable, db) -> None:
    logger.info("First Strike loop started")
    await asyncio.sleep(20)
    while True:
        try:
            row = await db.first_strike_config.find_one({"_id": "default"}) or {}
            interval = int(row.get("interval_sec") or DEFAULT_FS_CONFIG["interval_sec"])
            await strike_cycle()
        except Exception as e:                                      # noqa: BLE001
            logger.warning("First Strike cycle failed: %s", e)
            interval = 60
        await asyncio.sleep(max(15, interval))
