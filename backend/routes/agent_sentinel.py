"""routes.agent_sentinel — AGENT SENTINEL: platform health watchdog.

Every 30 minutes: checks all registered deployments (HTTP reachability +
latency), pings the LLM agent stack (responsiveness + key-budget errors),
and computes the rolling API error rate. Degradations raise alerts in the
sentinel feed and light the red banner in the OS.

Endpoints — /api/sentinel/*
"""
import asyncio
import logging
import os
import time
import uuid
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger("orisei.agent_sentinel")

SWEEP_INTERVAL_S = 1800  # 30 minutes
LATENCY_DEGRADED_MS = 3000
LLM_SLOW_MS = 20000
ERR_RATE_WARN = 0.02
ERR_RATE_CRIT = 0.05
ERR_MIN_SAMPLE = 20

# Rolling in-process request log fed by server.py middleware: (epoch, status)
_REQ_WINDOW: deque = deque(maxlen=8000)
_BUDGET_WORDS = ("budget", "credit", "insufficient", "exceeded", "quota", "402")


def record_request(status_code: int) -> None:
    _REQ_WINDOW.append((time.time(), status_code))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


class DeploymentIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    url: str = Field(..., min_length=4, max_length=400)
    health_path: Optional[str] = Field(default=None, max_length=200)


def _default_deployments() -> List[Dict[str, Any]]:
    self_url = os.environ.get("PUBLIC_FRONTEND_URL", "").rstrip("/")
    out = []
    if self_url:
        out.append({"name": "Orisei TMS (this deployment)", "url": self_url,
                    "health_path": "/api/health", "builtin": True})
    out.append({"name": "JadeOS Automation Hub", "url": "https://mpls-automation-hub.emergent.host",
                "health_path": "/", "builtin": True})
    return out


def _error_rate_snapshot() -> Dict[str, Any]:
    cutoff = time.time() - 3600
    recent = [s for ts, s in _REQ_WINDOW if ts >= cutoff]
    total = len(recent)
    errors = sum(1 for s in recent if s >= 500 and s not in (502, 504))
    upstream = sum(1 for s in recent if s in (502, 504))
    rate = (errors / total) if total else 0.0
    status = "ok"
    if total >= ERR_MIN_SAMPLE and rate >= ERR_RATE_CRIT:
        status = "critical"
    elif total >= ERR_MIN_SAMPLE and rate >= ERR_RATE_WARN:
        status = "degraded"
    return {"window_min": 60, "total_requests": total, "errors_5xx": errors,
            "upstream_502_504": upstream,
            "rate_pct": round(rate * 100, 2), "status": status}


async def _check_deployment(dep: Dict[str, Any]) -> Dict[str, Any]:
    url = dep["url"].rstrip("/") + (dep.get("health_path") or "/")
    started = time.perf_counter()
    status, http_code, error = "up", None, None
    try:
        async with httpx.AsyncClient(timeout=12, follow_redirects=True) as client:
            r = await client.get(url)
        http_code = r.status_code
        latency = int((time.perf_counter() - started) * 1000)
        if r.status_code >= 500:
            status = "down"
        elif r.status_code >= 400 or latency > LATENCY_DEGRADED_MS:
            status = "degraded"
    except Exception as e:  # noqa: BLE001
        latency = int((time.perf_counter() - started) * 1000)
        status, error = "down", str(e)[:200]
    return {"deployment_id": dep["deployment_id"], "name": dep["name"], "url": dep["url"],
            "status": status, "http_code": http_code, "latency_ms": latency,
            "error": error, "checked_at": _iso(_now())}


async def _check_llm() -> Dict[str, Any]:
    key = os.environ.get("EMERGENT_LLM_KEY")
    if not key:
        return {"status": "error", "detail": "EMERGENT_LLM_KEY not configured",
                "latency_ms": None, "checked_at": _iso(_now())}
    started = time.perf_counter()
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(api_key=key, session_id=f"sentinel-{uuid.uuid4().hex[:8]}",
                       system_message="Reply with exactly one word: pong").with_model("openai", "gpt-4o-mini")
        reply = await asyncio.wait_for(chat.send_message(UserMessage(text="ping")), timeout=45)
        latency = int((time.perf_counter() - started) * 1000)
        status = "slow" if latency > LLM_SLOW_MS else "ok"
        return {"status": status, "detail": f"Agent replied in {latency} ms ({str(reply)[:30]!r})",
                "latency_ms": latency, "checked_at": _iso(_now())}
    except Exception as e:  # noqa: BLE001
        latency = int((time.perf_counter() - started) * 1000)
        msg = str(e)
        low = msg.lower()
        if any(w in low for w in _BUDGET_WORDS):
            return {"status": "budget_exhausted", "detail": f"LLM key budget issue: {msg[:200]}",
                    "latency_ms": latency, "checked_at": _iso(_now())}
        return {"status": "error", "detail": msg[:200], "latency_ms": latency,
                "checked_at": _iso(_now())}


def build_agent_sentinel_router(*, api_router: APIRouter, db,
                                get_current_user: Callable, require_role: Callable) -> None:
    router = APIRouter(prefix="/sentinel", tags=["agent-sentinel"])
    state = {"loop_started": False, "sweeping": False, "next_check_at": None}

    async def _ensure_seed():
        if await db.sentinel_deployments.count_documents({}) == 0:
            for d in _default_deployments():
                d.update({"deployment_id": f"DEP-{uuid.uuid4().hex[:8].upper()}",
                          "enabled": True, "created_at": _iso(_now())})
                await db.sentinel_deployments.insert_one(d)

    async def _raise_or_resolve_alerts(snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Fingerprint-deduped alerts; auto-resolve recovered ones."""
        failing: Dict[str, Dict[str, Any]] = {}
        for d in snapshot["deployments"]:
            if d["status"] in ("down", "degraded"):
                sev = "critical" if d["status"] == "down" else "warning"
                failing[f"deploy:{d['deployment_id']}"] = {
                    "severity": sev, "source": "deployment",
                    "title": f"{d['name']} is {d['status'].upper()}",
                    "detail": d.get("error") or f"HTTP {d.get('http_code')} · {d.get('latency_ms')} ms",
                }
        llm = snapshot["llm"]
        if llm["status"] == "budget_exhausted":
            failing["llm:budget"] = {"severity": "critical", "source": "llm",
                                     "title": "LLM key budget exhausted",
                                     "detail": llm["detail"] + " — top up the Emergent Universal Key."}
        elif llm["status"] in ("error", "slow"):
            failing["llm:health"] = {"severity": "warning", "source": "llm",
                                     "title": "AI agent degraded" if llm["status"] == "slow" else "AI agent unresponsive",
                                     "detail": llm["detail"]}
        er = snapshot["error_rate"]
        if er["status"] in ("degraded", "critical"):
            failing["errors:rate"] = {"severity": "critical" if er["status"] == "critical" else "warning",
                                      "source": "errors",
                                      "title": f"API error rate elevated — {er['rate_pct']}%",
                                      "detail": f"{er['errors_5xx']} of {er['total_requests']} requests failed (5xx) in the last hour."}

        active = await db.sentinel_alerts.find(
            {"status": {"$in": ["active", "acked"]}}, {"_id": 0}).to_list(200)
        active_fp = {a["fingerprint"]: a for a in active}
        new_alerts = []
        for fp, meta in failing.items():
            if fp in active_fp:
                continue
            alert = {"alert_id": f"SEN-{uuid.uuid4().hex[:6].upper()}", "fingerprint": fp,
                     "status": "active", "detected_at": _iso(_now()), "resolved_at": None, **meta}
            await db.sentinel_alerts.insert_one(dict(alert))
            new_alerts.append(alert)
        for fp, a in active_fp.items():
            if fp not in failing:
                await db.sentinel_alerts.update_one(
                    {"alert_id": a["alert_id"]},
                    {"$set": {"status": "resolved", "resolved_at": _iso(_now())}})
        if new_alerts:
            logger.warning("Agent Sentinel raised %d alert(s): %s",
                           len(new_alerts), ", ".join(a["title"] for a in new_alerts))
        return new_alerts

    async def _sweep(include_llm: bool = True) -> Dict[str, Any]:
        if state["sweeping"]:
            latest = await db.sentinel_checks.find_one({}, {"_id": 0}, sort=[("at", -1)])
            return latest or {}
        state["sweeping"] = True
        try:
            await _ensure_seed()
            deps = await db.sentinel_deployments.find({"enabled": True}, {"_id": 0}).to_list(50)
            dep_results = list(await asyncio.gather(*[_check_deployment(d) for d in deps]))
            llm = await _check_llm() if include_llm else \
                ((await db.sentinel_checks.find_one({}, {"_id": 0, "llm": 1}, sort=[("at", -1)]) or {}).get("llm")
                 or {"status": "unknown", "detail": "not yet probed", "latency_ms": None, "checked_at": None})
            er = _error_rate_snapshot()
            statuses = [d["status"] for d in dep_results] + [llm["status"], er["status"]]
            overall = "critical" if any(s in ("down", "budget_exhausted", "critical") for s in statuses) else \
                "degraded" if any(s in ("degraded", "error", "slow") for s in statuses) else "ok"
            snapshot = {"snapshot_id": f"SNAP-{uuid.uuid4().hex[:8].upper()}", "at": _iso(_now()),
                        "deployments": dep_results, "llm": llm, "error_rate": er, "overall": overall}
            await db.sentinel_checks.insert_one(dict(snapshot))
            snapshot.pop("_id", None)
            await _raise_or_resolve_alerts(snapshot)
            return snapshot
        finally:
            state["sweeping"] = False

    async def _bg_loop():
        await asyncio.sleep(25)  # let the app finish booting
        while True:
            try:
                state["next_check_at"] = _iso(_now() + timedelta(seconds=SWEEP_INTERVAL_S))
                await _sweep(include_llm=True)
            except Exception as e:  # noqa: BLE001
                logger.warning("Sentinel sweep failed: %s", e)
            await asyncio.sleep(SWEEP_INTERVAL_S)

    def _ensure_loop():
        if not state["loop_started"]:
            state["loop_started"] = True
            asyncio.get_running_loop().create_task(_bg_loop())
            logger.info("Agent Sentinel loop started (every %ds)", SWEEP_INTERVAL_S)

    router.start_loop = _ensure_loop  # exposed for server startup

    @router.get("/status")
    async def status(_=Depends(get_current_user)) -> Dict[str, Any]:
        _ensure_loop()
        latest = await db.sentinel_checks.find_one({}, {"_id": 0}, sort=[("at", -1)])
        active = await db.sentinel_alerts.find(
            {"status": {"$in": ["active", "acked"]}}, {"_id": 0}).sort("detected_at", -1).to_list(50)
        unacked = [a for a in active if a["status"] == "active"]
        banner = None
        if unacked:
            worst = "critical" if any(a["severity"] == "critical" for a in unacked) else "warning"
            banner = {"severity": worst,
                      "message": unacked[0]["title"] + (f" (+{len(unacked) - 1} more)" if len(unacked) > 1 else ""),
                      "alert_ids": [a["alert_id"] for a in unacked]}
        return {"snapshot": latest, "active_alerts": active, "banner": banner,
                "next_check_at": state["next_check_at"], "interval_min": SWEEP_INTERVAL_S // 60}

    @router.post("/scan")
    async def scan_now(_=Depends(get_current_user)) -> Dict[str, Any]:
        _ensure_loop()
        snapshot = await _sweep(include_llm=True)
        active = await db.sentinel_alerts.find(
            {"status": {"$in": ["active", "acked"]}}, {"_id": 0}).sort("detected_at", -1).to_list(50)
        return {"snapshot": snapshot, "active_alerts": active}

    @router.get("/alerts")
    async def alerts_feed(limit: int = 100, _=Depends(get_current_user)) -> Dict[str, Any]:
        feed = await db.sentinel_alerts.find({}, {"_id": 0}).sort("detected_at", -1).to_list(min(limit, 300))
        return {"alerts": feed}

    @router.post("/alerts/{alert_id}/ack")
    async def ack_alert(alert_id: str, user=Depends(get_current_user)) -> Dict[str, Any]:
        r = await db.sentinel_alerts.update_one(
            {"alert_id": alert_id, "status": "active"},
            {"$set": {"status": "acked", "acked_by": user.email, "acked_at": _iso(_now())}})
        if r.matched_count == 0:
            raise HTTPException(status_code=404, detail="Alert not found or not active")
        return {"ok": True}

    @router.get("/deployments")
    async def list_deployments(_=Depends(get_current_user)) -> Dict[str, Any]:
        await _ensure_seed()
        deps = await db.sentinel_deployments.find({}, {"_id": 0}).sort("created_at", 1).to_list(50)
        return {"deployments": deps}

    @router.post("/deployments")
    async def add_deployment(payload: DeploymentIn, _=Depends(require_role("owner"))) -> Dict[str, Any]:
        url = payload.url.strip().rstrip("/")
        if not url.startswith("http"):
            url = "https://" + url
        dep = {"deployment_id": f"DEP-{uuid.uuid4().hex[:8].upper()}", "name": payload.name.strip(),
               "url": url, "health_path": (payload.health_path or "/").strip(), "builtin": False,
               "enabled": True, "created_at": _iso(_now())}
        await db.sentinel_deployments.insert_one(dict(dep))
        dep.pop("_id", None)
        return dep

    @router.delete("/deployments/{deployment_id}")
    async def remove_deployment(deployment_id: str, _=Depends(require_role("owner"))) -> Dict[str, Any]:
        r = await db.sentinel_deployments.delete_one({"deployment_id": deployment_id, "builtin": False})
        if r.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Deployment not found (built-ins cannot be removed)")
        await db.sentinel_alerts.update_many(
            {"fingerprint": f"deploy:{deployment_id}", "status": {"$in": ["active", "acked"]}},
            {"$set": {"status": "resolved", "resolved_at": _iso(_now())}})
        return {"ok": True}

    api_router.include_router(router)
    logger.info("Agent Sentinel registered (/api/sentinel)")
    build_agent_sentinel_router.start_loop = _ensure_loop
