"""
Launch Runway — Orisei Freight Solutions founder cockpit.

Tracks the founder's 12-month launch plan as a series of milestones, with
auto-computed actuals pulled from real collections (shippers closed,
invoices generated, dollars collected, factor approval state, scale tier).

Endpoints
---------
* GET  /api/launch-runway          — full plan with computed KPIs
* POST /api/launch-runway/{id}/toggle — manually mark complete / undo
* POST /api/launch-runway/{id}/notes  — annotate a milestone
* GET  /api/launch-runway/summary  — header KPIs (% complete, current phase,
                                      next action, projected margin)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

log = logging.getLogger("orisei.launch_runway")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# The plan. Each milestone has an `auto_threshold` predicate evaluated against
# live computed actuals — when the threshold is met, the UI surfaces a "ready
# to close out" hint (but the user still confirms the close-out manually so
# the plan tracks reality, not optimism).
# ---------------------------------------------------------------------------
PLAN: List[Dict[str, Any]] = [
    # ---- Phase 1: Cold pipeline + first 3 shippers ----
    {
        "id": "p1-cold-call",
        "phase": "Week 1–2",
        "label": "Cold-call 5 shippers",
        "narrative": "Five qualified shipper outreach calls. Lead with SUPERVALU, Regional Auto, Food Distributor.",
        "kpi_key": "calls_logged",
        "kpi_target": 5,
        "kpi_label": "calls",
        "owner": "Founder",
        "depends_on": [],
    },
    {
        "id": "p1-close-3",
        "phase": "Week 1–2",
        "label": "Close 3 shippers (SUPERVALU + 2)",
        "narrative": "Convert at least three shippers from cold calls — anchor with SUPERVALU.",
        "kpi_key": "shippers_closed",
        "kpi_target": 3,
        "kpi_label": "shippers",
        "owner": "Founder",
        "depends_on": ["p1-cold-call"],
    },
    {
        "id": "p1-sign-agreements",
        "phase": "Week 1–2",
        "label": "Sign shipper agreements (Net 7 / 10 / 14)",
        "narrative": "Executed broker-shipper agreements on file for each customer.",
        "kpi_key": "agreements_signed",
        "kpi_target": 3,
        "kpi_label": "agreements",
        "owner": "Founder",
        "depends_on": ["p1-close-3"],
    },

    # ---- Phase 2: Build invoice book ----
    {
        "id": "p2-20-invoices",
        "phase": "Week 3–4",
        "label": "Generate 20 invoices · $18,000 total",
        "narrative": "Run 20 real loads, invoiced & PODs filed. Document everything for the factor.",
        "kpi_key": "invoices_generated",
        "kpi_target": 20,
        "kpi_label": "invoices",
        "kpi_dollar_target": 18_000,
        "owner": "Founder",
        "depends_on": ["p1-sign-agreements"],
    },
    {
        "id": "p2-collect-deposits",
        "phase": "Week 3–4",
        "label": "Collect shipper payments & deposit",
        "narrative": "Cash hits the business account. Every deposit timestamped.",
        "kpi_key": "dollars_collected",
        "kpi_target": 18_000,
        "kpi_label": "USD",
        "owner": "Founder",
        "depends_on": ["p2-20-invoices"],
    },

    # ---- Phase 3: Apply for factoring ----
    {
        "id": "p3-apply-factor",
        "phase": "Day 15",
        "label": "Apply: Rapid Finance + On The Spot",
        "narrative": "Submit factoring apps. Lead with: \"SUPERVALU + 2 A/B credit shippers, 20 paid invoices.\"",
        "kpi_key": "factor_apps_submitted",
        "kpi_target": 2,
        "kpi_label": "apps",
        "owner": "Founder",
        "depends_on": ["p2-collect-deposits"],
    },
    {
        "id": "p3-counter-offer",
        "phase": "Day 21",
        "label": "Negotiate 3.75% · 85% advance · $50k line",
        "narrative": "Rapid offers 4%, OTS 3.75%. Counter to lock 85% advance + $50k line with monthly reviews.",
        "kpi_key": "negotiation_status",
        "kpi_target": 1,
        "kpi_label": "agreed terms",
        "owner": "Founder",
        "depends_on": ["p3-apply-factor"],
    },
    {
        "id": "p3-ucc-filed",
        "phase": "Day 28",
        "label": "Factoring live · UCC-1 filed",
        "narrative": "Approved. UCC-1 lien on file. You can now factor invoices.",
        "kpi_key": "factor_live",
        "kpi_target": 1,
        "kpi_label": "active factor",
        "owner": "Founder",
        "depends_on": ["p3-counter-offer"],
    },

    # ---- Phase 4: Scale ----
    {
        "id": "p4-month2-volume",
        "phase": "Month 2",
        "label": "$40k invoiced · factor 80% · $6k margin",
        "narrative": "Generate $40k in invoices, factor 80% ($32k), pay carriers $26k, keep $6k margin.",
        "kpi_key": "month2_volume",
        "kpi_target": 40_000,
        "kpi_label": "USD invoiced",
        "kpi_dollar_target": 40_000,
        "owner": "Founder",
        "depends_on": ["p3-ucc-filed"],
    },
    {
        "id": "p4-scale-5to10",
        "phase": "Month 3–6",
        "label": "5–10 shippers · $80–120k / week",
        "narrative": "Diversify the book. Push for $80–120k weekly invoice volume. Negotiate factor fee down to 3.5%.",
        "kpi_key": "shippers_closed",
        "kpi_target": 5,
        "kpi_label": "shippers",
        "owner": "Founder",
        "depends_on": ["p4-month2-volume"],
    },

    # ---- Phase 5: The Win ----
    {
        "id": "p5-year1-shippers",
        "phase": "Month 12",
        "label": "20+ shippers · $200k / week",
        "narrative": "Scale to twenty active shippers running $200k/week in invoices.",
        "kpi_key": "shippers_closed",
        "kpi_target": 20,
        "kpi_label": "shippers",
        "owner": "Founder",
        "depends_on": ["p4-scale-5to10"],
    },
    {
        "id": "p5-margin-50to80",
        "phase": "Month 12",
        "label": "$50–80k margin · credit 650+",
        "narrative": "Margin compounds. Credit score rebuilds to 650+. Refinance options open up.",
        "kpi_key": "total_margin",
        "kpi_target": 50_000,
        "kpi_label": "USD margin",
        "kpi_dollar_target": 50_000,
        "owner": "Founder",
        "depends_on": ["p5-year1-shippers"],
    },
]


# ---------------------------------------------------------------------------
# Live actuals — computed by querying the existing collections so the plan
# stays honest. Anything that can't be computed yet returns 0 (founder
# manually closes out by toggling).
# ---------------------------------------------------------------------------
async def _compute_actuals(db) -> Dict[str, Any]:
    shippers = await db.orisei_customers.count_documents({})
    bookings = await db.brokerage_bookings.count_documents({})
    invoices = await db.orisei_invoices.count_documents({})
    invoice_rows = await (db.orisei_invoices
                          .find({}, {"_id": 0, "total_usd": 1, "paid": 1,
                                      "amount_usd": 1, "status": 1})
                          .to_list(5_000))
    invoiced_usd = sum(
        float(r.get("total_usd") or r.get("amount_usd") or 0)
        for r in invoice_rows)
    collected_usd = sum(
        float(r.get("total_usd") or r.get("amount_usd") or 0)
        for r in invoice_rows
        if r.get("paid") or r.get("status") in ("paid", "collected"))
    factor_state = await db.factoring_state.find_one({}, {"_id": 0}) or {}
    factor_live = 1 if factor_state.get("approved") else 0
    # Calls logged: outbound emails + audit log entries with action='cold_call'
    calls = await db.audit_log.count_documents({"action": "cold_call"})
    # margin: 15% of collected approximates broker net (subject to manual override)
    margin = round(collected_usd * 0.15)
    return {
        "shippers_closed":      shippers,
        "agreements_signed":    shippers,  # 1 agreement per shipper closed
        "calls_logged":         calls,
        "invoices_generated":   invoices,
        "dollars_collected":    round(collected_usd),
        "month2_volume":        round(invoiced_usd) if invoiced_usd > 0 else 0,
        "factor_apps_submitted":(factor_state.get("apps_submitted") or 0),
        "negotiation_status":   1 if factor_state.get("terms_agreed") else 0,
        "factor_live":          factor_live,
        "total_margin":         margin,
        "bookings":             bookings,
        "invoiced_usd":         round(invoiced_usd),
    }


def _status_for(milestone: Dict[str, Any], actual: int,
                manual_override: Optional[str]) -> str:
    if manual_override in ("done", "skipped", "in_progress"):
        return manual_override
    target = milestone["kpi_target"]
    if actual <= 0:
        return "todo"
    if actual >= target:
        return "ready"   # KPI hit — founder still confirms close-out
    return "in_progress"


# ---------------------------------------------------------------------------
# Router builder
# ---------------------------------------------------------------------------
class ToggleIn(BaseModel):
    status: str  # "done" | "todo" | "in_progress" | "skipped"


class NoteIn(BaseModel):
    note: str


def build_launch_runway_router(*, db, get_current_user, require_role):
    router = APIRouter(prefix="/launch-runway", tags=["launch-runway"])

    async def _load_overrides() -> Dict[str, Dict[str, Any]]:
        rows = await (db.launch_runway_state
                      .find({}, {"_id": 0}).to_list(200))
        return {r["milestone_id"]: r for r in rows}

    @router.get("")
    async def list_plan(_=Depends(get_current_user)) -> Dict[str, Any]:
        actuals = await _compute_actuals(db)
        overrides = await _load_overrides()
        out: List[Dict[str, Any]] = []
        for m in PLAN:
            ov = overrides.get(m["id"], {})
            actual = int(actuals.get(m["kpi_key"], 0))
            status = _status_for(m, actual, ov.get("status"))
            out.append({
                **m,
                "actual": actual,
                "actual_pct": min(100,
                    round(actual / max(1, m["kpi_target"]) * 100)),
                "status": status,
                "completed_at": ov.get("completed_at"),
                "note": ov.get("note"),
            })
        # phase grouping
        phases: Dict[str, List[str]] = {}
        for m in out:
            phases.setdefault(m["phase"], []).append(m["id"])
        return {
            "milestones": out,
            "actuals": actuals,
            "phases": phases,
            "generated_at": _now_iso(),
        }

    @router.get("/summary")
    async def get_summary(_=Depends(get_current_user)) -> Dict[str, Any]:
        actuals = await _compute_actuals(db)
        overrides = await _load_overrides()
        total = len(PLAN)
        done = 0
        in_progress = 0
        current: Optional[Dict[str, Any]] = None
        next_action: Optional[Dict[str, Any]] = None
        for m in PLAN:
            ov = overrides.get(m["id"], {})
            actual = int(actuals.get(m["kpi_key"], 0))
            st = _status_for(m, actual, ov.get("status"))
            if st == "done":
                done += 1
            elif st in ("in_progress", "ready"):
                in_progress += 1
                if current is None:
                    current = {**m, "actual": actual, "status": st}
            elif next_action is None and st == "todo":
                next_action = {**m, "actual": actual, "status": st}
        return {
            "total_milestones": total,
            "completed":        done,
            "in_progress":      in_progress,
            "pct_complete":     round(done / max(1, total) * 100),
            "current":          current,
            "next_action":      next_action or current,
            "actuals":          actuals,
            "target_y1_margin": 50_000,
        }

    @router.post("/{milestone_id}/toggle")
    async def toggle_milestone(milestone_id: str, payload: ToggleIn,
                                user=Depends(get_current_user)) -> Dict[str, Any]:
        if not any(m["id"] == milestone_id for m in PLAN):
            raise HTTPException(404, "Unknown milestone")
        if payload.status not in ("todo", "in_progress", "done", "skipped"):
            raise HTTPException(400, "Invalid status")
        upd: Dict[str, Any] = {
            "milestone_id": milestone_id,
            "status":       payload.status,
            "updated_at":   _now_iso(),
            "updated_by":   getattr(user, "name", "system"),
        }
        if payload.status == "done":
            upd["completed_at"] = _now_iso()
        else:
            upd["completed_at"] = None
        await db.launch_runway_state.update_one(
            {"milestone_id": milestone_id},
            {"$set": upd},
            upsert=True,
        )
        return {"ok": True, "milestone_id": milestone_id,
                "status": payload.status}

    @router.post("/{milestone_id}/notes")
    async def annotate_milestone(milestone_id: str, payload: NoteIn,
                                  user=Depends(get_current_user)) -> Dict[str, Any]:
        if not any(m["id"] == milestone_id for m in PLAN):
            raise HTTPException(404, "Unknown milestone")
        await db.launch_runway_state.update_one(
            {"milestone_id": milestone_id},
            {"$set": {"milestone_id": milestone_id,
                       "note": payload.note,
                       "updated_at": _now_iso(),
                       "updated_by": getattr(user, "name", "system")}},
            upsert=True,
        )
        return {"ok": True}

    return router
