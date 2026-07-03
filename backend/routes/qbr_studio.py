"""routes.qbr_studio — Quarterly Business Review Studio.

Auto-generates a comprehensive QBR read-out per shipper per period by
aggregating data from every relevant TMS collection:

  • **brokerage_bookings** → volume, revenue, avg RPM, lane mix
  • **shipments**          → OTD / OTP / status breakdown
  • **claims_master**      → damage rate, claim $, resolution SLAs
  • **shipper_relations**  → CRM context, incentive uptake
  • **prior period**        → comparative deltas (QoQ, YoY)

Endpoints under /api/qbr-studio/*:
  GET  /shippers                     · list eligible shippers (auto-detected from bookings + accounts)
  GET  /period/{period}/{shipper}    · auto-computed QBR data + prior-period comparison
  POST /generate                     · persist a QBR draft with computed + user narrative
  GET  /drafts                       · list all drafts
  GET  /drafts/{draft_id}
  PATCH /drafts/{draft_id}           · edit narrative fields
  DELETE /drafts/{draft_id}
  GET  /drafts/{draft_id}/report.pdf · Orisei-branded distributable PDF
  POST /drafts/{draft_id}/distribute · email to shipper contact (queues outbound_emails)
"""
from __future__ import annotations

import io
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr, Field

log = logging.getLogger("orisei.qbr_studio")


# ============================================================
#                       PYDANTIC MODELS
# ============================================================
class GenerateIn(BaseModel):
    period: str = Field(..., max_length=40)     # e.g. "Q1 2026"
    shipper_name: str = Field(..., min_length=1, max_length=200)
    executive_summary: Optional[str] = Field(None, max_length=8000)
    strengths: Optional[str] = Field(None, max_length=8000)
    gaps: Optional[str] = Field(None, max_length=8000)
    action_items: Optional[List[str]] = None
    next_review_date: Optional[str] = None


class DraftPatch(BaseModel):
    executive_summary: Optional[str] = None
    strengths: Optional[str] = None
    gaps: Optional[str] = None
    action_items: Optional[List[str]] = None
    next_review_date: Optional[str] = None


class DistributeIn(BaseModel):
    to_email: EmailStr
    cc: Optional[List[EmailStr]] = None
    subject: Optional[str] = Field(None, max_length=200)
    message: Optional[str] = Field(None, max_length=4000)


# ============================================================
#                       HELPERS
# ============================================================
QUARTERS = {
    1: ("Q1", 1, 3), 2: ("Q1", 1, 3), 3: ("Q1", 1, 3),
    4: ("Q2", 4, 6), 5: ("Q2", 4, 6), 6: ("Q2", 4, 6),
    7: ("Q3", 7, 9), 8: ("Q3", 7, 9), 9: ("Q3", 7, 9),
   10: ("Q4", 10, 12), 11: ("Q4", 10, 12), 12: ("Q4", 10, 12),
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _quarter_bounds(period: str) -> Optional[Tuple[datetime, datetime, str]]:
    """Parse 'Q1 2026' → (start, end, label). Also accepts 'YTD 2026'."""
    period = (period or "").strip().upper()
    if period.startswith("YTD"):
        try:
            year = int(period.split()[-1])
        except Exception:
            return None
        start = datetime(year, 1, 1, tzinfo=timezone.utc)
        end = _now()
        return start, end, f"YTD {year}"
    if len(period) >= 6 and period[0] == "Q":
        try:
            q = int(period[1])
            year = int(period.split()[-1])
        except Exception:
            return None
        first_month = (q - 1) * 3 + 1
        start = datetime(year, first_month, 1, tzinfo=timezone.utc)
        # end = first day of next quarter
        if q == 4:
            end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end = datetime(year, first_month + 3, 1, tzinfo=timezone.utc)
        return start, end, f"Q{q} {year}"
    return None


def _prior_quarter(period: str) -> Optional[str]:
    if not period or not period.upper().startswith("Q"):
        return None
    try:
        q = int(period[1])
        year = int(period.split()[-1])
    except Exception:
        return None
    if q == 1:
        return f"Q4 {year - 1}"
    return f"Q{q - 1} {year}"


def _parse(iso: Optional[str]) -> Optional[datetime]:
    if not iso:
        return None
    try:
        return datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except Exception:
        return None


async def _compute_metrics(db, shipper_name: str, start: datetime, end: datetime) -> Dict[str, Any]:
    """Aggregate every relevant collection for a shipper within [start, end)."""
    # Shipper is matched loosely: brokerage_bookings.customer_name, shipments.consignee/supplier
    shipper_lc = shipper_name.strip().lower()

    # -------- Bookings --------
    bookings = await db.brokerage_bookings.find({}, {"_id": 0}).to_list(5000)
    in_period = []
    for b in bookings:
        cust = (b.get("customer_name") or "").lower().strip()
        if cust != shipper_lc:
            continue
        dt = _parse(b.get("booked_at"))
        if not dt or dt < start or dt >= end:
            continue
        in_period.append(b)

    total_loads = len(in_period)
    total_revenue = sum(float(b.get("forecast_rate_usd") or b.get("settled_rate_usd") or 0) for b in in_period)
    total_carrier_cost = sum(float(b.get("forecast_carrier_pay_usd") or b.get("settled_carrier_pay_usd") or 0) for b in in_period)
    total_miles = sum(float(b.get("miles") or 0) for b in in_period)
    total_margin = total_revenue - total_carrier_cost
    avg_rate = total_revenue / total_loads if total_loads else 0
    avg_rpm = (total_revenue / total_miles) if total_miles else 0
    margin_pct = (total_margin / total_revenue * 100) if total_revenue else 0

    # Lane concentration (top 5)
    by_lane: Dict[str, int] = {}
    for b in in_period:
        lane = f"{b.get('origin','—')} → {b.get('destination','—')}"
        by_lane[lane] = by_lane.get(lane, 0) + 1
    top_lanes = sorted(by_lane.items(), key=lambda x: -x[1])[:5]

    # Equipment mix
    by_eq: Dict[str, int] = {}
    for b in in_period:
        eq = b.get("equipment") or "Van"
        by_eq[eq] = by_eq.get(eq, 0) + 1

    # -------- Shipments (OTD / OTP / status breakdown) --------
    shipments = await db.shipments.find({}, {"_id": 0}).to_list(5000)
    ship_in_period = []
    for s in shipments:
        # match by consignee or supplier
        matches = shipper_lc in (s.get("consignee") or "").lower() or \
                   shipper_lc in (s.get("supplier") or "").lower() or \
                   shipper_lc in ((s.get("customer") or "").lower() if isinstance(s.get("customer"), str) else "")
        if not matches:
            continue
        dt = _parse(s.get("created_at") or s.get("pickup_date"))
        if not dt or dt < start or dt >= end:
            continue
        ship_in_period.append(s)

    total_shipments = len(ship_in_period)
    by_status: Dict[str, int] = {}
    for s in ship_in_period:
        st = s.get("status") or "unknown"
        by_status[st] = by_status.get(st, 0) + 1
    delivered = by_status.get("delivered", 0)
    in_transit = by_status.get("in_transit", 0)
    delayed = by_status.get("delayed", 0)
    otd_pct = None
    if delivered + delayed > 0:
        otd_pct = round((delivered / (delivered + delayed)) * 100, 1)
    otp_pct = otd_pct  # best-available proxy — we don't track pickup separately

    # -------- Claims (damage / SLA / cost) --------
    claims = await db.claims_master.find({}, {"_id": 0}).to_list(5000)
    claims_in_period = []
    for c in claims:
        if (c.get("shipper_name") or "").strip().lower() != shipper_lc:
            continue
        dt = _parse(c.get("filed_at"))
        if not dt or dt < start or dt >= end:
            continue
        claims_in_period.append(c)
    total_claims = len(claims_in_period)
    claim_amount_total = sum(float(c.get("claim_amount_usd") or 0) for c in claims_in_period)
    claim_paid_total = sum(float(c.get("final_payout_usd") or c.get("decision", {}).get("payout_usd", 0) or 0)
                             for c in claims_in_period)
    damage_free_loads = max(total_loads - total_claims, 0)
    damage_free_pct = (damage_free_loads / total_loads * 100) if total_loads else None
    claims_by_kind: Dict[str, int] = {}
    for c in claims_in_period:
        k = c.get("kind") or "other"
        claims_by_kind[k] = claims_by_kind.get(k, 0) + 1

    # SLA adherence (24-hr ack)
    ack_within_sla = sum(1 for c in claims_in_period if c.get("acknowledged_at") and
                          _parse(c["acknowledged_at"]) and _parse(c.get("filed_at")) and
                          (_parse(c["acknowledged_at"]) - _parse(c["filed_at"])) <= timedelta(hours=24))
    sla_adherence_pct = (ack_within_sla / total_claims * 100) if total_claims else 100.0

    # -------- Account CRM context --------
    account = await db.shipper_accounts.find_one(
        {"company_name": {"$regex": f"^{shipper_name}$", "$options": "i"}},
        {"_id": 0},
    )
    incentives = []
    if account and account.get("assigned_incentives"):
        incentives = await db.shipper_incentives.find(
            {"incentive_id": {"$in": account["assigned_incentives"]}}, {"_id": 0}).to_list(50)

    return {
        "shipper_name": shipper_name,
        "loads": {
            "total": total_loads,
            "revenue_usd": round(total_revenue, 2),
            "carrier_cost_usd": round(total_carrier_cost, 2),
            "margin_usd": round(total_margin, 2),
            "margin_pct": round(margin_pct, 2),
            "avg_rate_usd": round(avg_rate, 2),
            "avg_rpm": round(avg_rpm, 2),
            "total_miles": round(total_miles, 0),
        },
        "lanes": {"top": [{"lane": lane, "count": n} for lane, n in top_lanes]},
        "equipment": [{"kind": k, "count": v} for k, v in sorted(by_eq.items(), key=lambda x: -x[1])],
        "shipments": {
            "total": total_shipments,
            "by_status": by_status,
            "otd_pct": otd_pct,
            "otp_pct": otp_pct,
            "delivered": delivered,
            "delayed": delayed,
            "in_transit": in_transit,
        },
        "claims": {
            "total": total_claims,
            "amount_usd": round(claim_amount_total, 2),
            "paid_usd": round(claim_paid_total, 2),
            "damage_free_pct": round(damage_free_pct, 2) if damage_free_pct is not None else None,
            "sla_adherence_pct": round(sla_adherence_pct, 1),
            "by_kind": claims_by_kind,
        },
        "account": {
            "lifecycle": (account or {}).get("lifecycle"),
            "payment_terms": (account or {}).get("payment_terms"),
            "dedicated_am": (account or {}).get("dedicated_am"),
            "annual_volume_loads": (account or {}).get("annual_volume_loads"),
            "annual_revenue_usd": (account or {}).get("annual_revenue_usd"),
            "assigned_incentives": [i.get("name") for i in incentives],
        },
    }


def _delta(current: Optional[float], prior: Optional[float]) -> Dict[str, Any]:
    if current is None or prior is None:
        return {"abs": None, "pct": None, "direction": "n/a"}
    delta_abs = round(current - prior, 2)
    pct = round((delta_abs / prior * 100), 1) if prior else None
    direction = "flat"
    if delta_abs > 0:
        direction = "up"
    elif delta_abs < 0:
        direction = "down"
    return {"abs": delta_abs, "pct": pct, "direction": direction}


def _delta_kpis(current: Dict[str, Any], prior: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "loads_total": _delta(current["loads"]["total"], prior["loads"]["total"]),
        "revenue_usd": _delta(current["loads"]["revenue_usd"], prior["loads"]["revenue_usd"]),
        "margin_usd": _delta(current["loads"]["margin_usd"], prior["loads"]["margin_usd"]),
        "margin_pct": _delta(current["loads"]["margin_pct"], prior["loads"]["margin_pct"]),
        "avg_rpm": _delta(current["loads"]["avg_rpm"], prior["loads"]["avg_rpm"]),
        "otd_pct": _delta(current["shipments"]["otd_pct"], prior["shipments"]["otd_pct"]),
        "damage_free_pct": _delta(current["claims"]["damage_free_pct"], prior["claims"]["damage_free_pct"]),
        "claims_count": _delta(current["claims"]["total"], prior["claims"]["total"]),
        "claims_amount_usd": _delta(current["claims"]["amount_usd"], prior["claims"]["amount_usd"]),
    }


# ============================================================
#                       PDF RENDERING
# ============================================================
async def _active_brand(db) -> Dict[str, Any]:
    """Return the currently-active brand kit for Orisei-branded PDFs.

    Fix (2026-07-03): previously queried `{"active": True}` which didn't
    match the DB schema (`is_active`), so all QBR PDFs fell through to the
    first-inserted brand doc (Walmart). Now correctly prefers is_active →
    is_default → orisei brand_id → any brand.
    """
    b = await db.company_brand.find_one({"is_active": True}, {"_id": 0})
    if not b:
        b = await db.company_brand.find_one({"is_default": True}, {"_id": 0})
    if not b:
        b = await db.company_brand.find_one(
            {"brand_id": {"$regex": "orisei", "$options": "i"}}, {"_id": 0})
    if not b:
        b = await db.company_brand.find_one({}, {"_id": 0}) or {}
    return b


def _render_qbr_pdf(draft: Dict[str, Any], brand: Dict[str, Any]) -> bytes:
    m = draft["metrics"]
    prior = draft.get("prior_metrics") or {}
    deltas = draft.get("deltas") or {}
    lines: List[str] = []
    short = brand.get("short_name") or "Orisei"
    lines.append(f"# {short} · Quarterly Business Review")
    lines.append(f"## {draft['shipper_name']} — {draft['period']}")
    lines.append("")
    if draft.get("executive_summary"):
        lines.append("### Executive Summary")
        lines.append(draft["executive_summary"])
        lines.append("")

    # ---- KPI table ----
    lines.append("### Headline Metrics")
    lines.append("")
    lines.append("| Metric | This Period | Prior Period | Δ Abs | Δ % |")
    lines.append("|---|---|---|---|---|")
    def _fmt(v, kind="num"):
        if v is None:
            return "—"
        if kind == "usd":
            return f"${v:,.2f}"
        if kind == "pct":
            return f"{v}%"
        return f"{v:,}"
    def _row(label, cur, prev, dkey, kind="num"):
        d = deltas.get(dkey, {})
        return f"| {label} | {_fmt(cur, kind)} | {_fmt(prev, kind)} | {_fmt(d.get('abs'), kind)} | {_fmt(d.get('pct'), 'pct')} |"

    prior_loads = prior.get("loads", {})
    prior_ship = prior.get("shipments", {})
    prior_claims = prior.get("claims", {})
    lines.append(_row("Total loads", m["loads"]["total"], prior_loads.get("total"), "loads_total"))
    lines.append(_row("Revenue",    m["loads"]["revenue_usd"], prior_loads.get("revenue_usd"), "revenue_usd", "usd"))
    lines.append(_row("Margin $",   m["loads"]["margin_usd"], prior_loads.get("margin_usd"), "margin_usd", "usd"))
    lines.append(_row("Margin %",   m["loads"]["margin_pct"], prior_loads.get("margin_pct"), "margin_pct", "pct"))
    lines.append(_row("Avg RPM",    m["loads"]["avg_rpm"], prior_loads.get("avg_rpm"), "avg_rpm", "usd"))
    lines.append(_row("OTD %",      m["shipments"]["otd_pct"], prior_ship.get("otd_pct"), "otd_pct", "pct"))
    lines.append(_row("Damage-Free %", m["claims"]["damage_free_pct"], prior_claims.get("damage_free_pct"), "damage_free_pct", "pct"))
    lines.append(_row("Claims count",  m["claims"]["total"], prior_claims.get("total"), "claims_count"))
    lines.append(_row("Claims $",      m["claims"]["amount_usd"], prior_claims.get("amount_usd"), "claims_amount_usd", "usd"))
    lines.append("")

    # ---- Lanes ----
    if m["lanes"]["top"]:
        lines.append("### Top Lanes")
        lines.append("")
        lines.append("| Lane | Loads |")
        lines.append("|---|---|")
        for lane_row in m["lanes"]["top"]:
            lines.append(f"| {lane_row['lane']} | {lane_row['count']} |")
        lines.append("")

    # ---- Equipment ----
    if m["equipment"]:
        lines.append("### Equipment Mix")
        lines.append("")
        lines.append("| Equipment | Loads |")
        lines.append("|---|---|")
        for row in m["equipment"]:
            lines.append(f"| {row['kind']} | {row['count']} |")
        lines.append("")

    # ---- Claims breakdown ----
    if m["claims"]["by_kind"]:
        lines.append("### Claims by Type")
        lines.append("")
        lines.append("| Kind | Count |")
        lines.append("|---|---|")
        for k, v in m["claims"]["by_kind"].items():
            lines.append(f"| {k} | {v} |")
        lines.append("")

    # ---- Account snapshot ----
    acc = m.get("account", {})
    if acc.get("lifecycle"):
        lines.append("### Account Snapshot")
        lines.append(f"- **Lifecycle:** {acc['lifecycle'].upper()}")
        if acc.get("payment_terms"):
            lines.append(f"- **Payment terms:** {acc['payment_terms'].upper().replace('_', '-')}")
        if acc.get("dedicated_am"):
            lines.append(f"- **Dedicated AM:** {acc['dedicated_am']}")
        if acc.get("annual_volume_loads"):
            lines.append(f"- **Annual commitment:** {acc['annual_volume_loads']} loads")
        if acc.get("annual_revenue_usd"):
            lines.append(f"- **Annual revenue commitment:** ${acc['annual_revenue_usd']:,.0f}")
        if acc.get("assigned_incentives"):
            lines.append(f"- **Active incentives:** {', '.join(acc['assigned_incentives'])}")
        lines.append("")

    # ---- Strengths / Gaps ----
    if draft.get("strengths"):
        lines.append("### Strengths")
        lines.append(draft["strengths"])
        lines.append("")
    if draft.get("gaps"):
        lines.append("### Gaps & Opportunities")
        lines.append(draft["gaps"])
        lines.append("")
    if draft.get("action_items"):
        lines.append("### Action Items")
        for a in draft["action_items"]:
            lines.append(f"- [ ] {a}")
        lines.append("")
    if draft.get("next_review_date"):
        lines.append(f"**Next review:** {draft['next_review_date']}")
        lines.append("")

    lines.append("---")
    lines.append(f"_Prepared by {short} Account Team. Data pulled directly from the {short} TMS as of {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}._")

    md = "\n".join(lines)
    from routes.orisei_docs import build_branded_markdown_pdf
    return build_branded_markdown_pdf(
        md,
        title=f"QBR · {draft['shipper_name']}",
        subtitle=f"{draft['period']} · {short} Freight Solutions",
        doc_id=f"QBR-{draft.get('draft_id')}",
        brand=brand,
    )


# ============================================================
#                       ROUTER BUILDER
# ============================================================
def build_qbr_studio_router(
    *, api_router: APIRouter, db,
    get_current_user: Callable, require_role: Callable,
) -> None:
    router = APIRouter(prefix="/qbr-studio", tags=["qbr-studio"])
    user_dep = Depends(get_current_user)
    admin_dep = Depends(require_role("admin", "dispatcher"))

    def _actor(user) -> str:
        return getattr(user, "email", None) or getattr(user, "user_id", "system")

    # ------------------------ ELIGIBLE SHIPPERS ------------------------
    @router.get("/shippers")
    async def list_shippers(_=user_dep) -> Dict[str, Any]:
        """Union of every source that names a shipper: bookings, accounts, claims."""
        names: Dict[str, Dict[str, Any]] = {}
        # From accounts (preferred — has CRM context)
        accts = await db.shipper_accounts.find({}, {"_id": 0}).to_list(1000)
        for a in accts:
            n = (a.get("company_name") or "").strip()
            if not n:
                continue
            names[n.lower()] = {"name": n, "source": "account",
                                 "lifecycle": a.get("lifecycle"),
                                 "annual_volume_loads": a.get("annual_volume_loads")}
        # From bookings
        bookings = await db.brokerage_bookings.find({}, {"customer_name": 1, "_id": 0}).to_list(5000)
        for b in bookings:
            n = (b.get("customer_name") or "").strip()
            if not n:
                continue
            key = n.lower()
            if key not in names:
                names[key] = {"name": n, "source": "booking"}
        # From claims
        claims = await db.claims_master.find({}, {"shipper_name": 1, "_id": 0}).to_list(5000)
        for c in claims:
            n = (c.get("shipper_name") or "").strip()
            if not n:
                continue
            key = n.lower()
            if key not in names:
                names[key] = {"name": n, "source": "claim"}
        items = sorted(names.values(), key=lambda x: x["name"].lower())
        return {"items": items, "count": len(items)}

    # ------------------------ AUTO-COMPUTE ------------------------
    @router.get("/period/{period}/{shipper_name}")
    async def compute(period: str, shipper_name: str, _=user_dep) -> Dict[str, Any]:
        bounds = _quarter_bounds(period)
        if not bounds:
            raise HTTPException(400, "Invalid period. Use 'Q1 2026' or 'YTD 2026'.")
        start, end, label = bounds
        current = await _compute_metrics(db, shipper_name, start, end)
        prior_label = _prior_quarter(period)
        prior = None
        if prior_label:
            pb = _quarter_bounds(prior_label)
            if pb:
                prior = await _compute_metrics(db, shipper_name, pb[0], pb[1])
        deltas = _delta_kpis(current, prior) if prior else {}
        return {
            "shipper_name": shipper_name,
            "period": label,
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "prior_period": prior_label,
            "metrics": current,
            "prior_metrics": prior,
            "deltas": deltas,
        }

    # ------------------------ DRAFTS ------------------------
    @router.post("/generate")
    async def generate(payload: GenerateIn, user=admin_dep) -> Dict[str, Any]:
        bounds = _quarter_bounds(payload.period)
        if not bounds:
            raise HTTPException(400, "Invalid period")
        start, end, label = bounds
        current = await _compute_metrics(db, payload.shipper_name, start, end)
        prior_label = _prior_quarter(payload.period)
        prior = None
        if prior_label:
            pb = _quarter_bounds(prior_label)
            if pb:
                prior = await _compute_metrics(db, payload.shipper_name, pb[0], pb[1])
        deltas = _delta_kpis(current, prior) if prior else {}
        doc = {
            "draft_id": f"QBR-{uuid.uuid4().hex[:10].upper()}",
            "shipper_name": payload.shipper_name,
            "period": label,
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "prior_period": prior_label,
            "metrics": current,
            "prior_metrics": prior,
            "deltas": deltas,
            "executive_summary": payload.executive_summary,
            "strengths": payload.strengths,
            "gaps": payload.gaps,
            "action_items": payload.action_items or [],
            "next_review_date": payload.next_review_date,
            "status": "draft",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": _actor(user),
        }
        await db.qbr_drafts.insert_one(dict(doc))
        doc.pop("_id", None)
        return doc

    @router.get("/drafts")
    async def list_drafts(_=user_dep) -> Dict[str, Any]:
        rows = await db.qbr_drafts.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
        return {"items": rows, "count": len(rows)}

    @router.get("/drafts/{draft_id}")
    async def get_draft(draft_id: str, _=user_dep) -> Dict[str, Any]:
        row = await db.qbr_drafts.find_one({"draft_id": draft_id}, {"_id": 0})
        if not row:
            raise HTTPException(404, "Draft not found")
        return row

    @router.patch("/drafts/{draft_id}")
    async def patch_draft(draft_id: str, payload: DraftPatch, user=admin_dep) -> Dict[str, Any]:
        updates = payload.model_dump(exclude_none=True)
        if not updates:
            raise HTTPException(400, "No updates provided")
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        updates["updated_by"] = _actor(user)
        res = await db.qbr_drafts.update_one({"draft_id": draft_id}, {"$set": updates})
        if not res.matched_count:
            raise HTTPException(404, "Draft not found")
        return await db.qbr_drafts.find_one({"draft_id": draft_id}, {"_id": 0})

    @router.delete("/drafts/{draft_id}")
    async def delete_draft(draft_id: str, _=admin_dep) -> Dict[str, Any]:
        res = await db.qbr_drafts.delete_one({"draft_id": draft_id})
        if not res.deleted_count:
            raise HTTPException(404, "Draft not found")
        return {"ok": True}

    @router.get("/drafts/{draft_id}/report.pdf")
    async def report_pdf(draft_id: str, _=user_dep):
        draft = await db.qbr_drafts.find_one({"draft_id": draft_id}, {"_id": 0})
        if not draft:
            raise HTTPException(404, "Draft not found")
        brand = await _active_brand(db)
        pdf = _render_qbr_pdf(draft, brand)
        return StreamingResponse(io.BytesIO(pdf), media_type="application/pdf",
                                  headers={"Content-Disposition": f'inline; filename="qbr_{draft_id}.pdf"'})

    # ------------------------ DISTRIBUTE ------------------------
    @router.post("/drafts/{draft_id}/distribute")
    async def distribute(draft_id: str, payload: DistributeIn, user=admin_dep) -> Dict[str, Any]:
        draft = await db.qbr_drafts.find_one({"draft_id": draft_id}, {"_id": 0})
        if not draft:
            raise HTTPException(404, "Draft not found")
        brand = await _active_brand(db)
        short = brand.get("short_name") or "Orisei"
        # Queue outbound email — real Resend send happens when the key is wired
        env = {
            "email_id": f"EM-{uuid.uuid4().hex[:10].upper()}",
            "kind": "qbr_distribution",
            "to": payload.to_email,
            "cc": payload.cc or [],
            "subject": payload.subject or f"{short} QBR · {draft['shipper_name']} · {draft['period']}",
            "body": payload.message or (
                f"Attached is our {draft['period']} Business Review for {draft['shipper_name']}. "
                f"Key metrics: {draft['metrics']['loads']['total']} loads, "
                f"${draft['metrics']['loads']['revenue_usd']:,.0f} revenue, "
                f"OTD {draft['metrics']['shipments'].get('otd_pct') or '—'}%. "
                f"Reply directly to schedule the review meeting."
            ),
            "reference": draft_id,
            "attachment_url": f"/api/qbr-studio/drafts/{draft_id}/report.pdf",
            "queued_at": datetime.now(timezone.utc).isoformat(),
            "queued_by": _actor(user),
            "status": "queued",
        }
        await db.outbound_emails.insert_one(dict(env))
        await db.qbr_drafts.update_one(
            {"draft_id": draft_id},
            {"$set": {"status": "distributed",
                       "distributed_at": env["queued_at"],
                       "distributed_to": payload.to_email,
                       "distributed_by": _actor(user)}})
        env.pop("_id", None)
        return {"ok": True, "email": env}

    api_router.include_router(router)
