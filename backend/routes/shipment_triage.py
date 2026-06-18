"""routes.shipment_triage — Orisei AI Exception Detection & Triage.

For every active booking, compute exception signals (late pickup, late delivery,
no GPS, missing POD, margin drift). For each exception, an AI co-pilot generates:
  • Severity (low / medium / high / critical)
  • Root-cause hypothesis (deterministic + optional Claude polish)
  • 3-step action plan
  • Pre-written customer notification + carrier escalation messages
  • After-hours escalation routing (on-call rotation)
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger("tennant_tms.shipment_triage")


# ============================================================
# Exception detection rules
# ============================================================
EXCEPTION_TYPES = {
    "pickup_late": {
        "label": "Pickup Late",
        "icon": "Clock",
        "default_severity": "medium",
        "playbook": [
            "Call carrier dispatch (NOT the driver) and confirm asset location.",
            "Notify shipper proactively before they call you — buy goodwill.",
            "If >2 hr late, secure a backup carrier and start re-dispatch in parallel.",
        ],
    },
    "delivery_late": {
        "label": "Delivery Late",
        "icon": "AlertTriangle",
        "default_severity": "high",
        "playbook": [
            "Demand ETA from carrier dispatch within 15 minutes.",
            "Send customer a transparency note + revised ETA with cause.",
            "Document the late event in the file — needed for any service-credit claim.",
        ],
    },
    "no_gps_checkin": {
        "label": "No GPS / Check-in",
        "icon": "MapPin",
        "default_severity": "medium",
        "playbook": [
            "Phone the driver directly — confirm location + status.",
            "Re-activate Macropoint / project44 tracking handshake.",
            "Set a 2-hour SLA: if no resolution, escalate to medium-high.",
        ],
    },
    "lost_load": {
        "label": "Load Lost / Unreachable",
        "icon": "AlertOctagon",
        "default_severity": "critical",
        "playbook": [
            "Open cargo-claim file IMMEDIATELY — preserve recourse window.",
            "Notify shipper + insurance broker within the first hour.",
            "Escalate FMCSA carrier status + check theft hotline (CargoNet).",
        ],
    },
    "pod_missing": {
        "label": "POD Missing",
        "icon": "FileText",
        "default_severity": "low",
        "playbook": [
            "Text the driver — most PODs are sitting in their phone gallery.",
            "Email carrier dispatch with the BOL number and signed-by name.",
            "Block carrier payment until POD lands — leverage works.",
        ],
    },
    "margin_drift": {
        "label": "Margin Drift",
        "icon": "TrendingDown",
        "default_severity": "low",
        "playbook": [
            "Cross-check carrier rate confirmation vs settled rate.",
            "If lumper/detention was added without your approval, dispute.",
            "Adjust the margin manual override on the booking.",
        ],
    },
    "carrier_no_response": {
        "label": "Carrier Unresponsive",
        "icon": "PhoneOff",
        "default_severity": "medium",
        "playbook": [
            "3-strike rule: 2 calls + 1 email within 15 minutes.",
            "If silent, secure backup capacity and prepare to swap carriers.",
            "Flag the carrier — block them from future loads until clarified.",
        ],
    },
    "off_route": {
        "label": "Off Route",
        "icon": "Compass",
        "default_severity": "medium",
        "playbook": [
            "Open the GPS trail · last known location.",
            "Call dispatcher to confirm fuel / meal stop vs unauthorized detour.",
            "If unauthorized, escalate to carrier safety officer.",
        ],
    },
}

AFTER_HOURS_BAND = {"start_hour": 18, "end_hour": 7}  # 6pm - 7am local


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _hours_between(iso_str: Optional[str]) -> Optional[float]:
    """Hours between `iso_str` and now (positive = past)."""
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (_now() - dt).total_seconds() / 3600
    except (ValueError, TypeError):
        return None


def _is_after_hours() -> bool:
    h = _now().hour
    return h >= AFTER_HOURS_BAND["start_hour"] or h < AFTER_HOURS_BAND["end_hour"]


def _detect_exceptions(booking: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Apply rule-set against one booking; return list of exception candidates."""
    found: List[Dict[str, Any]] = []
    status = booking.get("status")
    if status not in ("booked",):  # only active loads
        return found

    # 1) Pickup late: booked_at > 6h ago and no in_transit_at
    booked_at_hrs = _hours_between(booking.get("booked_at"))
    if booked_at_hrs and booked_at_hrs > 6 and not booking.get("in_transit_at") and not booking.get("pickup_actual_at"):
        sev = "high" if booked_at_hrs > 12 else "medium"
        found.append({
            "exception_id": f"EX-{uuid.uuid4().hex[:8].upper()}",
            "exception_type": "pickup_late",
            "severity": sev,
            "detected_at": _now_iso(),
            "signal": f"Booked {booked_at_hrs:.1f}h ago · no pickup confirmation",
        })

    # 2) Delivery late: dispatched_at > 24h ago and no delivered_at
    disp_hrs = _hours_between(booking.get("dispatched_at") or booking.get("in_transit_at"))
    if disp_hrs and disp_hrs > 24 and not booking.get("delivered_at"):
        sev = "critical" if disp_hrs > 72 else "high"
        found.append({
            "exception_id": f"EX-{uuid.uuid4().hex[:8].upper()}",
            "exception_type": "delivery_late",
            "severity": sev,
            "detected_at": _now_iso(),
            "signal": f"In transit {disp_hrs:.1f}h · no delivery confirmation",
        })

    # 3) No GPS check-in: in_transit_at > 4h ago with no recent gps_last_at
    in_tr_hrs = _hours_between(booking.get("in_transit_at"))
    gps_hrs   = _hours_between(booking.get("gps_last_at"))
    if in_tr_hrs and not booking.get("delivered_at"):
        if gps_hrs is None or gps_hrs > 4:
            sev = "high" if (gps_hrs or in_tr_hrs) > 8 else "medium"
            found.append({
                "exception_id": f"EX-{uuid.uuid4().hex[:8].upper()}",
                "exception_type": "no_gps_checkin",
                "severity": sev,
                "detected_at": _now_iso(),
                "signal": f"Last GPS {gps_hrs or in_tr_hrs:.1f}h ago",
            })

    # 4) Lost load: in_transit > 48h with no GPS for 12h+
    if in_tr_hrs and in_tr_hrs > 48 and (gps_hrs is None or gps_hrs > 12):
        found.append({
            "exception_id": f"EX-{uuid.uuid4().hex[:8].upper()}",
            "exception_type": "lost_load",
            "severity": "critical",
            "detected_at": _now_iso(),
            "signal": f"In transit {in_tr_hrs:.1f}h · no GPS in {gps_hrs or '∞'}h",
        })

    # 5) POD missing: delivered_at > 24h and no pod_uploaded_at
    delivered_hrs = _hours_between(booking.get("delivered_at"))
    if delivered_hrs and delivered_hrs > 24 and not booking.get("pod_uploaded_at"):
        found.append({
            "exception_id": f"EX-{uuid.uuid4().hex[:8].upper()}",
            "exception_type": "pod_missing",
            "severity": "low" if delivered_hrs < 72 else "medium",
            "detected_at": _now_iso(),
            "signal": f"Delivered {delivered_hrs:.1f}h ago · POD still missing",
        })

    # 6) Margin drift: settled rate diverges from forecast > 8%
    forecast = booking.get("forecast_rate_usd") or 0
    settled  = booking.get("settled_rate_usd") or 0
    if forecast and settled:
        drift = abs(settled - forecast) / forecast
        if drift > 0.08:
            found.append({
                "exception_id": f"EX-{uuid.uuid4().hex[:8].upper()}",
                "exception_type": "margin_drift",
                "severity": "medium" if drift > 0.15 else "low",
                "detected_at": _now_iso(),
                "signal": f"Settled ${settled:,.0f} vs forecast ${forecast:,.0f} ({drift*100:.1f}% drift)",
            })

    return found


# ============================================================
# AI triage advice (deterministic + optional polish)
# ============================================================
def _triage_advice(booking: Dict[str, Any], ex: Dict[str, Any]) -> Dict[str, Any]:
    et = ex["exception_type"]
    meta = EXCEPTION_TYPES.get(et, {})
    label = meta.get("label", et)
    customer = booking.get("customer_name") or "the customer"
    carrier  = booking.get("carrier_name")  or "the carrier"
    origin   = booking.get("origin")  or "origin"
    dest     = booking.get("destination") or "destination"
    booked_id = booking.get("booked_id")

    root_causes = {
        "pickup_late":         f"Carrier dispatch over-promised capacity, or driver hit HOS limits before {origin} pickup.",
        "delivery_late":       f"Most likely root cause: traffic/weather between {origin} and {dest}, or a driver re-route to refuel.",
        "no_gps_checkin":      "Driver disabled the macro-point app, low signal corridor, or unauthorized stop.",
        "lost_load":           "Driver phone off + carrier dispatch unresponsive = potential carrier abandonment or theft. Open the cargo-claim window now.",
        "pod_missing":         "Driver completed delivery but never uploaded the signed BOL. Common on Friday late deliveries.",
        "margin_drift":        "Unexpected accessorial (lumper, detention, layover) or carrier rate addendum signed without your approval.",
        "carrier_no_response": "Dispatch off-shift or carrier intentionally going dark on a problem load.",
        "off_route":           "Driver took an unauthorized detour — meal/fuel/personal — or the routing engine pushed them off the agreed lane.",
    }
    rc = root_causes.get(et, "Anomaly detected — investigate carrier dispatch and shipper expectations.")

    playbook = meta.get("playbook", ["Investigate", "Notify stakeholders", "Document"])

    # Customer-facing message
    customer_msg = {
        "pickup_late": (
            f"Hi {customer.split(' ')[0]} team — quick update on load {booked_id} from {origin}: "
            f"carrier is delayed on pickup. We're tracking dispatch in real time and will confirm a revised pickup window within 30 minutes. "
            f"Will update you the moment we have eyes on the trailer."
        ),
        "delivery_late": (
            f"Hi {customer.split(' ')[0]} team — load {booked_id} is running behind on delivery to {dest}. "
            f"Carrier ETA being confirmed now. We'll send a revised window in the next 30 minutes with the cause. "
            f"Apologies for the friction — we own this."
        ),
        "no_gps_checkin": (
            f"Quick note on load {booked_id}: tracking just stalled. Driver has been contacted directly — "
            f"we'll update you within the hour with a confirmed location. No reason for concern yet."
        ),
        "lost_load": (
            f"Urgent: load {booked_id} from {origin} → {dest}. We have lost contact with the carrier for an extended period. "
            f"Cargo claim file is OPEN. CargoNet has been notified. Will call you in 5 minutes to walk through the situation. "
            f"We are on this until it's resolved."
        ),
        "pod_missing": (
            f"Hi {customer.split(' ')[0]} — load {booked_id} delivered. We're chasing the signed POD from the driver "
            f"and will send it as soon as it lands."
        ),
        "margin_drift": (
            f"Internal: settled rate on {booked_id} drifted vs forecast — review carrier rate confirmation for unauthorized accessorials."
        ),
        "carrier_no_response": (
            f"Internal: carrier {carrier} unresponsive on {booked_id}. 3-strike protocol active. Backup capacity being sourced."
        ),
        "off_route": (
            f"Hi {customer.split(' ')[0]} — load {booked_id} is currently off the agreed routing. "
            f"Verifying with carrier dispatch now. We'll have an update in 30 minutes."
        ),
    }.get(et, f"Update on load {booked_id}: monitoring an exception. Will follow up shortly.")

    # Carrier-facing escalation
    carrier_msg = (
        f"URGENT · {label} on load {booked_id} ({origin} → {dest}).\n\n"
        f"Signal: {ex.get('signal','')}\n\n"
        f"Need:\n"
        f"  • Confirmation of driver name, phone, asset.\n"
        f"  • ETA / location update within 15 minutes.\n"
        f"  • Acknowledgement that this load is your top priority.\n\n"
        f"If no reply within 15, we move to backup capacity per Orisei carrier-pact terms."
    )

    after_hours = _is_after_hours()
    if after_hours and ex["severity"] in ("high", "critical"):
        escalation = "After-hours · paging on-call broker AND backup-carrier desk simultaneously."
    elif ex["severity"] == "critical":
        escalation = "Immediate · open cargo claim window + notify insurance broker."
    elif ex["severity"] == "high":
        escalation = "Hot · own this through the rest of the shift before clocking out."
    else:
        escalation = "Standard · resolve before end of business day."

    return {
        "title": label,
        "severity": ex["severity"],
        "root_cause": rc,
        "playbook": playbook,
        "customer_message": customer_msg,
        "carrier_message":  carrier_msg,
        "escalation":       escalation,
        "after_hours":      after_hours,
    }


# ============================================================
# Pydantic
# ============================================================
class ExceptionStatusIn(BaseModel):
    status: str = Field(..., pattern="^(open|acknowledged|in_progress|resolved|escalated)$")
    resolution_notes: Optional[str] = Field(None, max_length=2000)


class ManualExceptionIn(BaseModel):
    booked_id: str
    exception_type: str
    severity: str = Field("medium", pattern="^(low|medium|high|critical)$")
    signal: Optional[str] = None
    notes: Optional[str] = Field(None, max_length=2000)


# ============================================================
# Router
# ============================================================
def build_shipment_triage_router(
    api_router: APIRouter, *, db,
    get_current_user: Callable, require_role: Callable,
    emergent_llm_key: Optional[str] = None,
    LlmChat: Any = None, UserMessage: Any = None,
) -> None:
    router = APIRouter(prefix="/shipment-triage", tags=["shipment-triage"])
    admin_dep = Depends(require_role("admin", "dispatcher"))

    # ----- catalog -----
    @router.get("/exception-types")
    async def list_exception_types(_=Depends(get_current_user)) -> Dict[str, Any]:
        return {
            "items": [{"id": k, **v} for k, v in EXCEPTION_TYPES.items()],
            "after_hours_band": AFTER_HOURS_BAND,
            "is_after_hours": _is_after_hours(),
        }

    # ----- scan -----
    @router.post("/scan")
    async def scan(user=admin_dep) -> Dict[str, Any]:
        """Scan all active bookings and persist any new exceptions."""
        bookings = await db.brokerage_bookings.find(
            {"status": "booked"}, {"_id": 0}).to_list(500)
        existing = await db.shipment_exceptions.find(
            {"status": {"$in": ["open", "acknowledged", "in_progress"]}},
            {"_id": 0, "booked_id": 1, "exception_type": 1}).to_list(1000)
        already = {(e["booked_id"], e["exception_type"]) for e in existing}

        created: List[Dict[str, Any]] = []
        for bk in bookings:
            excs = _detect_exceptions(bk)
            for ex in excs:
                key = (bk["booked_id"], ex["exception_type"])
                if key in already:
                    continue
                advice = _triage_advice(bk, ex)
                doc = {
                    **ex,
                    "booked_id": bk["booked_id"],
                    "customer_name": bk.get("customer_name"),
                    "carrier_name":  bk.get("carrier_name"),
                    "origin": bk.get("origin"),
                    "destination": bk.get("destination"),
                    "status": "open",
                    "created_at": _now_iso(),
                    "created_by": "ai-scanner",
                    "advice": advice,
                }
                await db.shipment_exceptions.insert_one(dict(doc))
                doc.pop("_id", None)
                created.append(doc)
        return {
            "scanned_bookings": len(bookings),
            "created_count": len(created),
            "created": created,
            "is_after_hours": _is_after_hours(),
        }

    # ----- list -----
    @router.get("/exceptions")
    async def list_exceptions(
        status: Optional[str] = None,
        booked_id: Optional[str] = None,
        _=Depends(get_current_user),
    ) -> Dict[str, Any]:
        q: Dict[str, Any] = {}
        if status:
            q["status"] = status
        if booked_id:
            q["booked_id"] = booked_id
        rows = await db.shipment_exceptions.find(
            q, {"_id": 0}).sort([("severity", -1), ("created_at", -1)]).to_list(500)
        # Severity sort (Mongo can't enum-sort): map manually
        sev_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        rows.sort(key=lambda r: (sev_order.get(r.get("severity"), 9),
                                  r.get("created_at", "")), reverse=False)
        summary = {
            "open":         sum(1 for r in rows if r.get("status") == "open"),
            "acknowledged": sum(1 for r in rows if r.get("status") == "acknowledged"),
            "in_progress":  sum(1 for r in rows if r.get("status") == "in_progress"),
            "resolved":     sum(1 for r in rows if r.get("status") == "resolved"),
            "escalated":    sum(1 for r in rows if r.get("status") == "escalated"),
            "critical":     sum(1 for r in rows if r.get("severity") == "critical" and r.get("status") in ("open","acknowledged","in_progress")),
            "high":         sum(1 for r in rows if r.get("severity") == "high"     and r.get("status") in ("open","acknowledged","in_progress")),
        }
        return {"items": rows, "count": len(rows), "summary": summary,
                "is_after_hours": _is_after_hours()}

    # ----- update status -----
    @router.post("/exceptions/{exception_id}/status")
    async def set_status(exception_id: str, payload: ExceptionStatusIn,
                          user=admin_dep) -> Dict[str, Any]:
        upd: Dict[str, Any] = {
            "status": payload.status,
            "updated_at": _now_iso(),
            "updated_by": getattr(user, "name", "system"),
        }
        if payload.status == "resolved":
            upd["resolved_at"] = _now_iso()
        if payload.resolution_notes:
            upd["resolution_notes"] = payload.resolution_notes
        r = await db.shipment_exceptions.update_one(
            {"exception_id": exception_id}, {"$set": upd})
        if r.matched_count == 0:
            raise HTTPException(404, "Exception not found")
        return await db.shipment_exceptions.find_one(
            {"exception_id": exception_id}, {"_id": 0}) or {}

    # ----- manual exception -----
    @router.post("/exceptions")
    async def create_manual_exception(payload: ManualExceptionIn,
                                        user=admin_dep) -> Dict[str, Any]:
        if payload.exception_type not in EXCEPTION_TYPES:
            raise HTTPException(400, f"Unknown exception type: {payload.exception_type}")
        bk = await db.brokerage_bookings.find_one(
            {"booked_id": payload.booked_id}, {"_id": 0})
        if not bk:
            raise HTTPException(404, "Booking not found")
        ex = {
            "exception_id":   f"EX-{uuid.uuid4().hex[:8].upper()}",
            "exception_type": payload.exception_type,
            "severity":       payload.severity,
            "detected_at":    _now_iso(),
            "signal":         payload.signal or "Manual report by dispatcher",
        }
        advice = _triage_advice(bk, ex)
        doc = {
            **ex, "booked_id": payload.booked_id,
            "customer_name": bk.get("customer_name"),
            "carrier_name":  bk.get("carrier_name"),
            "origin": bk.get("origin"),
            "destination": bk.get("destination"),
            "status": "open",
            "created_at": _now_iso(),
            "created_by": getattr(user, "name", "system"),
            "manual_notes": payload.notes,
            "advice": advice,
        }
        await db.shipment_exceptions.insert_one(dict(doc))
        doc.pop("_id", None)
        return doc

    # ----- AI-polished advice (Claude) -----
    @router.post("/exceptions/{exception_id}/ai-polish")
    async def ai_polish(exception_id: str, user=admin_dep) -> Dict[str, Any]:
        ex = await db.shipment_exceptions.find_one(
            {"exception_id": exception_id}, {"_id": 0})
        if not ex:
            raise HTTPException(404, "Exception not found")
        if not (emergent_llm_key and LlmChat and UserMessage):
            return {**ex, "ai_polished": False, "note": "AI key unavailable"}
        try:
            chat = LlmChat(
                api_key=emergent_llm_key,
                session_id=f"triage-{exception_id}-{uuid.uuid4().hex[:6]}",
                system_message=(
                    "You are a 20-year freight brokerage operations director "
                    "triaging a live shipment exception. Reply in this exact format:\n"
                    "ROOT CAUSE: <one tight sentence>\n"
                    "IMMEDIATE ACTIONS:\n  1. ...\n  2. ...\n  3. ...\n"
                    "CUSTOMER MESSAGE (≤55 words, calm, transparent):\n<text>\n"
                    "CARRIER ESCALATION (firm, no emojis):\n<text>"
                ),
            )
            chat.with_model("anthropic", "claude-sonnet-4-5-20250929")
            ctx = (
                f"Exception type: {ex['exception_type']}\n"
                f"Severity: {ex['severity']}\n"
                f"Signal: {ex.get('signal','')}\n"
                f"Booking: {ex['booked_id']} · {ex.get('origin')} → {ex.get('destination')}\n"
                f"Carrier: {ex.get('carrier_name','—')}\n"
                f"Customer: {ex.get('customer_name','—')}\n"
                f"After-hours: {_is_after_hours()}\n"
            )
            resp = await chat.send_message(UserMessage(text=ctx))
            polished = resp if isinstance(resp, str) else getattr(resp, "content", "") or str(resp)
            await db.shipment_exceptions.update_one(
                {"exception_id": exception_id},
                {"$set": {"advice_ai_polished": polished,
                          "ai_polished_at": _now_iso(),
                          "ai_polished_by": getattr(user, "name", "system")}})
            return {**ex, "advice_ai_polished": polished, "ai_polished": True}
        except Exception as exc:                                                # noqa: BLE001
            logger.warning("AI polish triage failed: %s", exc)
            return {**ex, "ai_polished": False, "error": str(exc)[:200]}

    # ----- dashboard -----
    @router.get("/dashboard")
    async def dashboard(_=Depends(get_current_user)) -> Dict[str, Any]:
        rows = await db.shipment_exceptions.find({}, {"_id": 0}).to_list(2000)
        active = [r for r in rows if r.get("status") in ("open", "acknowledged", "in_progress")]
        by_type: Dict[str, int] = {}
        for r in active:
            by_type[r["exception_type"]] = by_type.get(r["exception_type"], 0) + 1
        by_sev: Dict[str, int] = {}
        for r in active:
            by_sev[r["severity"]] = by_sev.get(r["severity"], 0) + 1
        # MTTR
        resolved = [r for r in rows if r.get("status") == "resolved" and r.get("resolved_at")]
        mttr_hours: Optional[float] = None
        if resolved:
            durs: List[float] = []
            for r in resolved:
                d = _hours_between(r.get("created_at"))
                rd = _hours_between(r.get("resolved_at"))
                if d is not None and rd is not None:
                    durs.append(d - rd)
            if durs:
                mttr_hours = round(sum(durs) / len(durs), 2)
        return {
            "active_count": len(active),
            "critical_count": by_sev.get("critical", 0),
            "high_count":     by_sev.get("high", 0),
            "by_type": by_type,
            "by_severity": by_sev,
            "mttr_hours":  mttr_hours,
            "resolved_total": len(resolved),
            "is_after_hours": _is_after_hours(),
        }

    api_router.include_router(router)
