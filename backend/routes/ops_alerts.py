"""routes.ops_alerts — AI LOAD SENTINEL: real-time issue detection on REAL loads.

Detects: delayed shipments, ETA breaches, stale GPS, overdue invoices, pending
carrier vetting, Hunter risk rejections. Each new alert gets an AI action brief
(Claude) and fires email (Resend or queued) + SMS (Twilio or queued) notifications.
Frontend polls /api/alerts/scan; a background loop also sweeps every 3 minutes.

Endpoints — /api/alerts/*
"""

import asyncio
import json
import logging
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException

logger = logging.getLogger("orisei.ops_alerts")
NOT_SAMPLE = {"is_sample": {"$ne": True}}
SEV_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _json_from_llm(text: str) -> Any:
    t = re.sub(r"^```(json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    start = t.find("[")
    end = t.rfind("]")
    return json.loads(t[start:end + 1])


async def _send_sms(db, *, to: str, body: str) -> Dict[str, Any]:
    """Twilio if connected, else queue for the moment the key arrives."""
    from routes.connections import get_connection_credentials
    creds = await get_connection_credentials(db, "twilio")
    status, error = "queued_awaiting_key", None
    if creds and creds.get("account_sid") and creds.get("auth_token") and creds.get("from_number"):
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.post(
                    f"https://api.twilio.com/2010-04-01/Accounts/{creds['account_sid']}/Messages.json",
                    auth=(creds["account_sid"], creds["auth_token"]),
                    data={"To": to, "From": creds["from_number"], "Body": body[:1500]})
            status = "sent" if r.status_code < 300 else \
                "queued_awaiting_key" if r.status_code in (401, 403) else "failed"
            error = None if r.status_code < 300 else r.text[:200]
        except Exception as e:                                        # noqa: BLE001
            status, error = "failed", str(e)[:200]
    await db.sms_queue.insert_one({
        "sms_id": f"SMS-{uuid.uuid4().hex[:8].upper()}", "to": to, "body": body,
        "status": status, "error": error, "created_at": _iso(_now()),
        "sent_at": _iso(_now()) if status == "sent" else None})
    return {"status": status}


def build_ops_alerts_router(*, api_router: APIRouter, db,
                            get_current_user: Callable, require_role: Callable) -> None:
    router = APIRouter(prefix="/alerts", tags=["ops-alerts"])
    state = {"loop_started": False, "scanning": False}

    async def _settings() -> Dict[str, Any]:
        s = await db.alert_settings.find_one({"_id": "settings"}) or {}
        return {"email": s.get("email", ""), "phone": s.get("phone", ""),
                "email_enabled": s.get("email_enabled", True),
                "sms_enabled": s.get("sms_enabled", True),
                "min_severity": s.get("min_severity", "high")}

    # -------------------------------------------------------------- detection
    async def _detect() -> List[Dict[str, Any]]:
        now = _now()
        now_iso = now.isoformat()
        found: List[Dict[str, Any]] = []

        async for s in db.shipments.find({**NOT_SAMPLE, "status": "delayed"},
                                         {"_id": 0, "shipment_id": 1, "reference": 1, "carrier": 1,
                                          "origin": 1, "destination": 1, "eta": 1}).limit(25):
            found.append({"type": "delayed", "severity": "high", "ref": s.get("shipment_id"),
                          "title": f"Load {s.get('reference') or s.get('shipment_id')} flagged DELAYED",
                          "detail": f"{(s.get('origin') or {}).get('city', '?')} → {(s.get('destination') or {}).get('city', '?')} · carrier {s.get('carrier') or '?'} · ETA {s.get('eta') or 'unknown'}"})

        async for s in db.shipments.find({**NOT_SAMPLE, "status": "in_transit",
                                          "eta": {"$lt": now_iso, "$gt": "2000"}},
                                         {"_id": 0, "shipment_id": 1, "reference": 1, "carrier": 1,
                                          "origin": 1, "destination": 1, "eta": 1}).limit(25):
            found.append({"type": "eta_breach", "severity": "high", "ref": s.get("shipment_id"),
                          "title": f"ETA breached — {s.get('reference') or s.get('shipment_id')} still in transit",
                          "detail": f"ETA was {str(s.get('eta'))[:16]} · carrier {s.get('carrier') or '?'} · {(s.get('origin') or {}).get('city', '?')} → {(s.get('destination') or {}).get('city', '?')}"})

        stale_cut = _iso(now - timedelta(hours=4))
        async for s in db.shipments.find({**NOT_SAMPLE, "status": "in_transit",
                                          "updated_at": {"$lt": stale_cut}},
                                         {"_id": 0, "shipment_id": 1, "reference": 1,
                                          "carrier": 1, "updated_at": 1}).limit(25):
            found.append({"type": "gps_stale", "severity": "medium", "ref": s.get("shipment_id"),
                          "title": f"GPS silent 4+ hrs — {s.get('reference') or s.get('shipment_id')}",
                          "detail": f"Last ping {str(s.get('updated_at'))[:16]} · carrier {s.get('carrier') or '?'} — request check call / Macropoint refresh"})

        async for i in db.brokerage_invoices.find({**NOT_SAMPLE,
                                                   "status": {"$in": ["issued", "sent", "partial"]},
                                                   "due_at": {"$lt": now_iso, "$gt": "2000"}},
                                                  {"_id": 0, "invoice_id": 1, "customer_name": 1,
                                                   "total_usd": 1, "due_at": 1}).limit(25):
            amt = float(i.get("total_usd") or 0)
            days = max(0, (now - datetime.fromisoformat(i["due_at"])).days) if i.get("due_at") else 0
            sev = "high" if amt > 5000 or days > 15 else "medium"
            found.append({"type": "invoice_overdue", "severity": sev, "ref": i.get("invoice_id"),
                          "title": f"Invoice {i['invoice_id']} past due — ${amt:,.0f}",
                          "detail": f"{i.get('customer_name')} · {days} days late · escalate via AR Engine"})

        async for m in db.marketplace_bookings.find({"vetting": "pending_fmcsa_key", "status": "booked"},
                                                    {"_id": 0, "mb_id": 1, "carrier": 1}).limit(10):
            c = m.get("carrier") or {}
            found.append({"type": "vetting_pending", "severity": "medium", "ref": m.get("mb_id"),
                          "title": f"Carrier vetting pending — {c.get('company')} (MC-{c.get('mc_number')})",
                          "detail": f"Booked via marketplace {m['mb_id']} — verify authority/insurance before dispatch (auto once FMCSA key added)"})

        hunt_cut = _iso(now - timedelta(hours=24))
        n_rej = await db.hunter_audit.count_documents({"action": "risk_reject", "at": {"$gte": hunt_cut}})
        if n_rej:
            found.append({"type": "hunter_risk", "severity": "low", "ref": "24h-window",
                          "title": f"Hunter risk-rejected {n_rej} load(s) in the last 24h",
                          "detail": "Loads blocked by the risk registry (credit flags / low payment scores). Review in Load Hunter → Audit Trail."})

        decs = await db.hunter_decisions.find({}, {"_id": 0, "divergence": 1}).sort("at", -1).to_list(20)
        if len(decs) >= 5:
            div = sum(1 for d in decs if d.get("divergence") != "aligned")
            rate = div / len(decs) * 100
            if rate >= 35:
                found.append({"type": "misalignment", "severity": "high", "ref": "hunter-window",
                              "title": f"AI misalignment — {rate:.0f}% of your last {len(decs)} Hunter decisions overrode the AI",
                              "detail": f"{div}/{len(decs)} decisions diverged from the AI's recommendation. Open Load Hunter → Misalignment Monitor and retrain the weights from your revealed preferences."})
        return found

    async def _ai_briefs(alerts: List[Dict[str, Any]]) -> None:
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            chat = LlmChat(api_key=os.environ.get("EMERGENT_LLM_KEY"),
                           session_id=f"sentinel-{uuid.uuid4().hex[:8]}",
                           system_message=(
                               "You are the AI Load Sentinel for Orisei Freight Solutions. For each alert, "
                               "write a 2-sentence action brief: sentence 1 = operational impact, sentence 2 "
                               "= the exact next move the broker should make. Return STRICT JSON array of "
                               "strings, same order as input, no prose.")).with_model(
                               "anthropic", "claude-sonnet-4-5-20250929")
            payload = json.dumps([{"type": a["type"], "title": a["title"], "detail": a["detail"]}
                                  for a in alerts])
            briefs = _json_from_llm(await chat.send_message(UserMessage(text=payload)))
            for a, b in zip(alerts, briefs):
                a["ai_brief"] = str(b)
        except Exception as e:                                        # noqa: BLE001
            logger.warning("Sentinel AI brief failed: %s", e)
            for a in alerts:
                a.setdefault("ai_brief", f"{a['detail']} — review and act now.")

    async def _notify(alerts: List[Dict[str, Any]]) -> None:
        s = await _settings()
        min_rank = SEV_RANK.get(s["min_severity"], 2)
        to_send = [a for a in alerts if SEV_RANK[a["severity"]] >= min_rank]
        if not to_send:
            return
        if s["email_enabled"] and s["email"]:
            from routes.orisei_auto_digest import _resend_creds, _send_via_resend
            creds = await _resend_creds(db)
            rows = "".join(
                f"<tr><td style='padding:6px 10px;border-bottom:1px solid #eee'><b style='color:#b91c1c'>{a['severity'].upper()}</b></td>"
                f"<td style='padding:6px 10px;border-bottom:1px solid #eee'><b>{a['title']}</b><br/><span style='color:#555'>{a.get('ai_brief') or a['detail']}</span></td></tr>"
                for a in to_send)
            html = ("<div style='font-family:Arial,sans-serif'><h2 style='color:#0E3A6B'>◆ Orisei AI Load Sentinel</h2>"
                    f"<p>{len(to_send)} issue(s) detected on your live loads:</p>"
                    f"<table style='border-collapse:collapse;font-size:13px'>{rows}</table>"
                    "<p style='color:#888;font-size:11px'>Open Live Ops Command to act.</p></div>")
            subject = f"🚨 Sentinel: {len(to_send)} load issue(s) — {to_send[0]['title'][:60]}"
            if creds and creds.get("api_key"):
                res = await _send_via_resend(creds, to=s["email"], subject=subject, html=html)
                status = "sent" if res.get("sent") else "failed"
            else:
                status = "queued_awaiting_key"
            await db.outreach_queue.insert_one({
                "queue_id": f"OQ-{uuid.uuid4().hex[:8].upper()}", "type": "alert",
                "ref": ",".join(a["alert_id"] for a in to_send), "to_email": s["email"],
                "subject": subject, "html": html, "has_pdf": False, "status": status,
                "created_at": _iso(_now()), "sent_at": _iso(_now()) if status == "sent" else None})
            for a in to_send:
                a["notified_email"] = status
        if s["sms_enabled"] and s["phone"]:
            body = f"ORISEI SENTINEL: {len(to_send)} load issue(s). " + \
                " | ".join(a["title"] for a in to_send[:3])
            res = await _send_sms(db, to=s["phone"], body=body)
            for a in to_send:
                a["notified_sms"] = res["status"]
        for a in to_send:
            await db.ops_alerts.update_one({"alert_id": a["alert_id"]},
                                           {"$set": {"notified_email": a.get("notified_email"),
                                                     "notified_sms": a.get("notified_sms")}})

    async def _run_scan() -> Dict[str, Any]:
        if state["scanning"]:
            open_alerts = await db.ops_alerts.find({"status": "open"}, {"_id": 0}).sort("detected_at", -1).to_list(100)
            return {"new_alerts": [], "open_alerts": open_alerts, "busy": True}
        state["scanning"] = True
        try:
            detected = await _detect()
            open_fps = {a["fingerprint"] async for a in
                        db.ops_alerts.find({"status": {"$in": ["open", "acknowledged"]}},
                                           {"_id": 0, "fingerprint": 1})}
            new = []
            for d in detected:
                fp = f"{d['type']}:{d['ref']}"
                if fp in open_fps:
                    continue
                d.update({"alert_id": f"AL-{uuid.uuid4().hex[:6].upper()}", "fingerprint": fp,
                          "status": "open", "detected_at": _iso(_now())})
                new.append(d)
            if new:
                for a in new:
                    a["ai_brief"] = a["detail"]
                brief_targets = [a for a in new if SEV_RANK[a["severity"]] >= 1][:5]
                if brief_targets:
                    await _ai_briefs(brief_targets)
                for a in new:
                    await db.ops_alerts.insert_one(dict(a))
                await _notify(new)
                logger.info("Sentinel: %d new alert(s) raised", len(new))
            open_alerts = await db.ops_alerts.find({"status": {"$in": ["open", "acknowledged"]}},
                                                   {"_id": 0}).sort("detected_at", -1).to_list(100)
            return {"new_alerts": [{k: v for k, v in a.items()} for a in new],
                    "open_alerts": open_alerts}
        finally:
            state["scanning"] = False

    async def _bg_loop():
        while True:
            try:
                await _run_scan()
            except Exception as e:                                    # noqa: BLE001
                logger.warning("Sentinel background scan failed: %s", e)
            await asyncio.sleep(180)

    def _ensure_loop():
        if not state["loop_started"]:
            state["loop_started"] = True
            asyncio.get_event_loop().create_task(_bg_loop())
            logger.info("Sentinel background loop started (180s sweep)")

    # -------------------------------------------------------------- endpoints
    @router.post("/scan")
    async def scan(_=Depends(get_current_user)) -> Dict[str, Any]:
        _ensure_loop()
        return await _run_scan()

    @router.get("")
    async def list_alerts(_=Depends(get_current_user)) -> Dict[str, Any]:
        items = await db.ops_alerts.find({}, {"_id": 0}).sort("detected_at", -1).to_list(200)
        return {"items": items,
                "open": sum(1 for i in items if i["status"] in ("open", "acknowledged"))}

    @router.post("/{alert_id}/ack")
    async def ack(alert_id: str, user=Depends(get_current_user)) -> Dict[str, Any]:
        r = await db.ops_alerts.update_one({"alert_id": alert_id, "status": "open"},
                                           {"$set": {"status": "acknowledged",
                                                     "acked_at": _iso(_now()),
                                                     "acked_by": getattr(user, "user_id", None)}})
        if not r.matched_count:
            raise HTTPException(404, "Open alert not found")
        return {"ok": True}

    @router.post("/{alert_id}/resolve")
    async def resolve(alert_id: str, user=Depends(get_current_user)) -> Dict[str, Any]:
        r = await db.ops_alerts.update_one({"alert_id": alert_id},
                                           {"$set": {"status": "resolved",
                                                     "resolved_at": _iso(_now()),
                                                     "resolved_by": getattr(user, "user_id", None)}})
        if not r.matched_count:
            raise HTTPException(404, "Alert not found")
        return {"ok": True}

    @router.get("/settings")
    async def get_settings(_=Depends(get_current_user)) -> Dict[str, Any]:
        return await _settings()

    @router.post("/settings")
    async def set_settings(payload: Dict[str, Any],
                           _=Depends(require_role("admin", "dispatcher"))) -> Dict[str, Any]:
        upd = {k: payload[k] for k in ("email", "phone", "email_enabled", "sms_enabled", "min_severity")
               if k in payload}
        if upd.get("min_severity") and upd["min_severity"] not in SEV_RANK:
            raise HTTPException(400, "min_severity must be low|medium|high|critical")
        await db.alert_settings.update_one({"_id": "settings"}, {"$set": upd}, upsert=True)
        return {"ok": True, **await _settings()}

    @router.post("/test")
    async def fire_test(user=Depends(get_current_user)) -> Dict[str, Any]:
        """Fire a demo alert through the full pipeline (AI brief + notify + popup)."""
        a = {"alert_id": f"AL-{uuid.uuid4().hex[:6].upper()}",
             "fingerprint": f"test:{uuid.uuid4().hex[:6]}", "type": "test",
             "severity": "critical", "ref": "TEST",
             "title": "SENTINEL TEST — simulated breakdown on live load",
             "detail": "Tractor derated on I-80 near Des Moines, IA · 78% to destination · delivery appt at risk",
             "status": "open", "detected_at": _iso(_now())}
        await _ai_briefs([a])
        await db.ops_alerts.insert_one(dict(a))
        await _notify([a])
        a.pop("_id", None)
        return {"ok": True, "alert": a}

    api_router.include_router(router)
    logger.info("AI Load Sentinel registered (/api/alerts)")
