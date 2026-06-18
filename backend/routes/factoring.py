"""routes.factoring — Freight factoring + ABL transition engine for Orisei.

Implements the playbook delivered by the user verbatim. Everything a broker
needs from day-1 → month-12 to:
  • Pick the right factor stage (spot → recourse → non-recourse → ABL)
  • Professionally reach out to factors with an AI-generated, personalized email
  • Submit invoices for factoring and track advance + reserve + fees
  • Calculate the real cost of factoring vs ABL for the broker's volume
  • Follow a stage-by-stage 12-month maturity roadmap

This module is read-write but contains zero secrets — all real-world factor
applications happen via mailto + the generated outreach email.
"""
from __future__ import annotations

import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field

logger = logging.getLogger("tennant_tms.factoring")


# ============================================================
# Factor partner catalog (from the playbook)
# ============================================================
FACTOR_PARTNERS: List[Dict[str, Any]] = [
    {
        "factor_id": "truckstop-capital",
        "name": "Truckstop Capital",
        "kind": "spot+recourse",
        "fee_pct_min": 2.5, "fee_pct_max": 3.5,
        "advance_pct": 85,
        "min_monthly_volume_usd": 5_000,
        "setup_time_hours": 36,
        "specialization": "Freight brokers · on-platform",
        "best_for": "Load board brokers, integrated platform",
        "midwest": True,
        "website": "https://www.truckstop.com/factoring/",
        "contact_methods": ["website-form", "phone:866-728-7826", "email"],
        "headquarters": "Bloomington, IN",
        "notes": "Built into the Truckstop load board — fastest integration if you book there.",
    },
    {
        "factor_id": "on-the-spot",
        "name": "On The Spot Capital",
        "kind": "recourse",
        "fee_pct_min": 2.5, "fee_pct_max": 3.0,
        "advance_pct": 85,
        "min_monthly_volume_usd": 15_000,
        "setup_time_hours": 48,
        "specialization": "Freight brokers · Midwest",
        "best_for": "Minnesota / Midwest brokers · responsive",
        "midwest": True,
        "website": "https://onthespotcapital.com",
        "contact_methods": ["website-form", "phone", "email"],
        "headquarters": "Minneapolis, MN",
        "notes": "Local. Understands MPLS / St. Paul market. **Priority outreach for you.**",
    },
    {
        "factor_id": "bluechip-financial",
        "name": "BlueChip Financial",
        "kind": "recourse",
        "fee_pct_min": 2.5, "fee_pct_max": 3.5,
        "advance_pct": 85,
        "min_monthly_volume_usd": 10_000,
        "setup_time_hours": 60,
        "specialization": "Freight brokers · Midwest",
        "best_for": "Good shipper credit · recourse · Midwest base",
        "midwest": True,
        "website": "https://bluechip-fin.com",
        "contact_methods": ["website-form", "phone", "email"],
        "headquarters": "Chicago, IL",
        "notes": "Heavy Midwest presence — works well with SUPERVALU / Target / 3M backed AR.",
    },
    {
        "factor_id": "apex-capital",
        "name": "Apex Capital",
        "kind": "spot+recourse",
        "fee_pct_min": 2.5, "fee_pct_max": 4.0,
        "advance_pct": 85,
        "min_monthly_volume_usd": 5_000,
        "setup_time_hours": 36,
        "specialization": "Freight brokers · flexible spot",
        "best_for": "Spot factoring · low-volume startups",
        "midwest": False,
        "website": "https://www.apexcapitalcorp.com",
        "contact_methods": ["website-form", "phone:855-784-4234", "email"],
        "headquarters": "Fort Worth, TX",
        "notes": "Best for month-1 testing. No commitment, fast approval.",
    },
    {
        "factor_id": "coyote-rxo",
        "name": "Coyote / RXO Financial",
        "kind": "recourse",
        "fee_pct_min": 2.0, "fee_pct_max": 3.5,
        "advance_pct": 85,
        "min_monthly_volume_usd": 25_000,
        "setup_time_hours": 240,  # 1-2 weeks
        "specialization": "Brokers on RXO / Coyote network",
        "best_for": "Brokers integrated into the Coyote / RXO platform",
        "midwest": False,
        "website": "https://rxo.com",
        "contact_methods": ["account-manager", "email"],
        "headquarters": "Charlotte, NC",
        "notes": "Best rates if you carry their freight already.",
    },
    {
        "factor_id": "rapid-finance",
        "name": "Rapid Finance",
        "kind": "recourse",
        "fee_pct_min": 3.0, "fee_pct_max": 4.0,
        "advance_pct": 80,
        "min_monthly_volume_usd": 10_000,
        "setup_time_hours": 48,
        "specialization": "Freight + 3PL",
        "best_for": "Growing brokers · slightly higher risk profile",
        "midwest": False,
        "website": "https://www.rapidfinance.com",
        "contact_methods": ["website-form", "phone"],
        "headquarters": "Bethesda, MD",
        "notes": "Higher rate but funds borderline shipper credit.",
    },
    {
        "factor_id": "factor-network",
        "name": "Factor Network",
        "kind": "recourse",
        "fee_pct_min": 2.5, "fee_pct_max": 3.5,
        "advance_pct": 85,
        "min_monthly_volume_usd": 5_000,
        "setup_time_hours": 36,
        "specialization": "Freight brokers",
        "best_for": "Recourse-focused · reliable settlement",
        "midwest": False,
        "website": "https://factornetwork.com",
        "contact_methods": ["website-form", "email"],
        "headquarters": "Tampa, FL",
        "notes": "Solid mid-volume choice once you exit spot factoring.",
    },
    {
        "factor_id": "republic-business-credit",
        "name": "Republic Business Credit",
        "kind": "recourse+abl",
        "fee_pct_min": 2.0, "fee_pct_max": 3.5,
        "advance_pct": 85,
        "min_monthly_volume_usd": 25_000,
        "setup_time_hours": 336,  # 2 weeks
        "specialization": "Brokers + 3PL · ABL transition",
        "best_for": "Higher volume · transition path to ABL",
        "midwest": False,
        "website": "https://www.republicbc.com",
        "contact_methods": ["account-manager", "email"],
        "headquarters": "Houston, TX",
        "notes": "Strong path to graduate from recourse → ABL when you scale.",
    },
]


# ============================================================
# Stage roadmap (the playbook table)
# ============================================================
STAGES: List[Dict[str, Any]] = [
    {
        "stage_id": "startup",
        "label": "Stage 1 · Startup",
        "month_range": "Month 1–3",
        "loads_per_week_min": 5, "loads_per_week_max": 20,
        "monthly_margin_usd_min": 2_200, "monthly_margin_usd_max": 8_800,
        "type": "spot",
        "type_label": "Spot Factoring",
        "fee_pct": 3.5,
        "advance_pct": 85,
        "rationale": "Low volume · no commitment · test factor relationships before signing recourse contracts.",
        "actions": [
            "Open spot factoring with Apex Capital + Truckstop Capital (no monthly minimums).",
            "Establish business credit (Dun & Bradstreet number, biz bank account, EIN).",
            "Track every shipper's payment history — feed it into your factor application data.",
            "Keep margin ≥18% on every load — the 3.5% factor fee is coming out of that.",
        ],
        "success_metric": "≥3 shippers paying invoices on time, ≥20 loads completed.",
    },
    {
        "stage_id": "early-growth",
        "label": "Stage 2 · Early Growth",
        "month_range": "Month 4–6",
        "loads_per_week_min": 20, "loads_per_week_max": 50,
        "monthly_margin_usd_min": 8_800, "monthly_margin_usd_max": 22_000,
        "type": "recourse",
        "type_label": "Recourse Factoring",
        "fee_pct": 3.0,
        "advance_pct": 85,
        "rationale": "Volume + shipper quality improves. Switch to a single recourse partner for predictable rates.",
        "actions": [
            "Submit recourse application to On The Spot Capital (Minneapolis-based · priority).",
            "Send shipper-notification letters to your top 10 customers.",
            "File UCC-1 with Minnesota Secretary of State (factor pays the fee).",
            "Reduce factor fee from 3.5% → 3.0% by submitting volume forecast.",
            "Negotiate 30-day reserve release (push back on 60-day default).",
        ],
        "success_metric": "1 primary factor active · ≥5 named shippers in your AR list.",
    },
    {
        "stage_id": "growth",
        "label": "Stage 3 · Growth",
        "month_range": "Month 5–9",
        "loads_per_week_min": 50, "loads_per_week_max": 150,
        "monthly_margin_usd_min": 22_000, "monthly_margin_usd_max": 65_000,
        "type": "recourse-multi",
        "type_label": "Multi-Factor Recourse",
        "fee_pct": 2.75,
        "advance_pct": 87,
        "rationale": "Add a 2nd factor for redundancy + leverage to push the primary rate down.",
        "actions": [
            "Onboard 2nd factor partner (BlueChip Financial or Factor Network) — split 60/40.",
            "Negotiate primary factor rate down to 2.75% using competing offer.",
            "Introduce early-pay discount (e.g. Net 7 for 0.5% off) to shippers with weak credit.",
            "Diversify: top shipper ≤ 25% of volume, top 3 ≤ 60%.",
            "Start tracking AR aging weekly — surface >45 day invoices for collections.",
        ],
        "success_metric": "≥2 factors active · ≥10 named shippers · AR aging healthy (<10% >30 days).",
    },
    {
        "stage_id": "scale",
        "label": "Stage 4 · Scale",
        "month_range": "Month 9–11",
        "loads_per_week_min": 150, "loads_per_week_max": 300,
        "monthly_margin_usd_min": 65_000, "monthly_margin_usd_max": 130_000,
        "type": "recourse+abl-overflow",
        "type_label": "Recourse + ABL Overflow",
        "fee_pct": 2.5,
        "advance_pct": 87,
        "rationale": "Volume justifies an ABL line for overflow. Keep recourse for spot loads, use ABL for everything else.",
        "actions": [
            "Apply for ABL line ($250k–$500k) with Republic Business Credit OR a regional bank (Bell Bank, Stearns).",
            "Provide 9 months of P&L, AR aging report, top-15 shipper list, audited shipper payment history.",
            "Move stable shippers onto ABL (better margin) · keep volatile/new shippers on recourse.",
            "Renegotiate factor reserve hold to 14 days post-shipper-payment.",
            "Build internal AR controller role (or fractional CFO) — required from here on.",
        ],
        "success_metric": "ABL line approved · ≥$100k outstanding AR · cost-to-float < 5% of margin.",
    },
    {
        "stage_id": "enterprise",
        "label": "Stage 5 · Enterprise",
        "month_range": "Month 12+",
        "loads_per_week_min": 300, "loads_per_week_max": 1000,
        "monthly_margin_usd_min": 130_000, "monthly_margin_usd_max": 500_000,
        "type": "abl",
        "type_label": "Asset-Based Lending (Primary)",
        "fee_pct": 2.0,   # really monthly interest, expressed as annual equivalent for comparison
        "advance_pct": 90,
        "rationale": "ABL becomes primary funding. Recourse only for non-bankable shippers.",
        "actions": [
            "Graduate the ABL line to $1M+ ceiling — base on 90 days of trailing AR.",
            "Negotiate interest down to 1.5–1.75% monthly via competing bank offer.",
            "Maintain a single recourse factor for new / unrated shippers (risk firewall).",
            "Quarterly covenant compliance — keep AR turnover < 35 days, top-5 concentration < 40%.",
            "Consider invoice insurance (Allianz, Coface) to bring effective cost under 1%.",
        ],
        "success_metric": "ABL cost < 2.5% of margin · concentration < 40% · DSO < 30 days.",
    },
]


# ============================================================
# Strategies (4 critical from playbook)
# ============================================================
STRATEGIES: List[Dict[str, Any]] = [
    {
        "id": "multi-factor",
        "title": "Multi-Factor Redundancy",
        "icon": "Network",
        "summary": "Avoid single-factor outage. Always run 2+ factors once monthly volume > $100k.",
        "implementation": [
            "Sign two factor agreements (e.g. On The Spot + BlueChip).",
            "Tag each invoice in the TMS with a factor_route key.",
            "Submit Tier-1 shippers (Target / SUPERVALU / 3M) to the lowest-fee factor.",
            "Route higher-risk shippers to the secondary factor.",
            "Monitor weekly: if one factor's approvals dip, shift volume to the other.",
        ],
    },
    {
        "id": "shipper-terms",
        "title": "Shipper Payment Term Compression",
        "icon": "Clock",
        "summary": "Pay a small early-pay discount and dramatically cut factoring costs.",
        "implementation": [
            "Quote shippers Net 30 with a 2–3% discount for Net 7.",
            "Most Tier-1 shippers (Target, 3M) accept — they save more than you give.",
            "Net effect: factor only carries 7 days of AR vs 30 → fees cut roughly 60%.",
            "Track the discount as a line item on every PO so you preserve audit history.",
        ],
    },
    {
        "id": "reserve-mgmt",
        "title": "Reserve Release Negotiation",
        "icon": "PiggyBank",
        "summary": "Don't let the factor sit on 15% of your revenue for 60 days.",
        "implementation": [
            "Once monthly volume hits $1M, request 14-day reserve release.",
            "Cite a competing offer (even informal).",
            "Push 'release 50% after 30 days, balance after 60' as a fallback.",
            "Reconcile the reserve register monthly — chase any unreleased reserves > 60 days.",
        ],
    },
    {
        "id": "diversification",
        "title": "Shipper Concentration Control",
        "icon": "PieChart",
        "summary": "Factors penalize concentration. Keep top customer ≤ 25% to unlock cheaper rates.",
        "implementation": [
            "Track shipper concentration weekly (top-1 %, top-3 %, top-5 %).",
            "If top-1 > 25%, prioritize sales pipeline calls on alternative shippers that week.",
            "Surface concentration alerts on the Brokerage dashboard.",
            "Use it as ammunition in factor renegotiation: 'I have 18 active shippers, none over 22%'.",
        ],
    },
]


# ============================================================
# Pydantic models
# ============================================================
class ApplicationIn(BaseModel):
    factor_id: str
    contact_name: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = None
    status: str = Field("preparing", pattern="^(preparing|sent|underwriting|approved|declined|live)$")
    notes: Optional[str] = Field(None, max_length=3000)
    monthly_volume_target_usd: Optional[float] = Field(None, ge=0)


class OutreachGenerateIn(BaseModel):
    factor_id: str
    broker_name: str = "Orisei Freight Solutions LLC"
    contact_name: str = "Oliver Cummins"
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = None
    current_loads_per_month: int = Field(25, ge=1)
    projected_3mo_loads: int = Field(80, ge=1)
    projected_6mo_loads: int = Field(250, ge=1)
    top_shippers: List[str] = Field(default_factory=lambda: ["SUPERVALU", "Target", "3M"])
    lanes: List[str] = Field(default_factory=lambda: ["MPLS → Chicago", "MPLS → Milwaukee"])
    state: str = "Minnesota"
    custom_note: Optional[str] = Field(None, max_length=600)


class SubmissionIn(BaseModel):
    factor_id: str
    invoice_id: str
    customer_name: Optional[str] = None
    invoice_usd: float = Field(..., gt=0)
    carrier_cost_usd: Optional[float] = Field(None, ge=0)
    payment_terms_days: int = Field(14, ge=1, le=120)
    fee_pct_override: Optional[float] = Field(None, ge=0, le=15)
    advance_pct_override: Optional[float] = Field(None, ge=50, le=100)


class StageRecommendationIn(BaseModel):
    monthly_loads: int = Field(..., ge=0)
    avg_invoice_usd: float = Field(1300, ge=0)
    avg_margin_pct: float = Field(17.0, ge=0, le=80)
    payment_terms_days: int = Field(14, ge=1, le=90)


class CompareIn(BaseModel):
    monthly_loads: int = Field(..., ge=0)
    avg_invoice_usd: float = Field(..., ge=0)
    avg_margin_usd_per_load: float = Field(..., ge=0)
    payment_terms_days: int = Field(14, ge=1, le=90)


# ============================================================
# Helpers
# ============================================================
def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _factor_or_404(factor_id: str) -> Dict[str, Any]:
    for f in FACTOR_PARTNERS:
        if f["factor_id"] == factor_id:
            return f
    raise HTTPException(404, f"Unknown factor: {factor_id}")


def _stage_for(monthly_loads: int) -> Dict[str, Any]:
    weekly = monthly_loads / 4.33
    for stg in STAGES:
        if stg["loads_per_week_min"] <= weekly <= stg["loads_per_week_max"]:
            return stg
    return STAGES[-1] if weekly > STAGES[-1]["loads_per_week_max"] else STAGES[0]


def _compare_cost(monthly_loads: int, avg_invoice: float,
                   avg_margin: float, terms_days: int) -> Dict[str, Any]:
    """Return four cost rows for spot / recourse / non-recourse / ABL based on
    the playbook math."""
    total_invoices = monthly_loads * avg_invoice
    total_margin = monthly_loads * avg_margin
    if total_invoices == 0:
        return {"total_invoices_usd": 0, "total_margin_usd": 0, "rows": []}

    def _row(label: str, kind: str, fee_or_apr_pct: float, advance_pct: float,
             *, is_interest: bool = False) -> Dict[str, Any]:
        if is_interest:
            # ABL: pay interest on outstanding AR ≈ terms_days portion of total
            outstanding = total_invoices * (terms_days / 30.0)
            cost = outstanding * (fee_or_apr_pct / 100.0)
        else:
            cost = total_invoices * (fee_or_apr_pct / 100.0)
        advance_now = total_invoices * (advance_pct / 100.0)
        net_margin = total_margin - cost
        margin_cost_pct = (cost / total_margin * 100.0) if total_margin else 0
        return {
            "kind": kind, "label": label,
            "fee_or_apr_pct": fee_or_apr_pct,
            "advance_pct": advance_pct,
            "advance_usd": round(advance_now, 2),
            "cost_usd": round(cost, 2),
            "net_margin_usd": round(net_margin, 2),
            "margin_cost_pct": round(margin_cost_pct, 2),
            "is_interest": is_interest,
        }

    rows = [
        _row("Spot Factoring",     "spot",     3.5, 85),
        _row("Recourse Factoring", "recourse", 2.75, 85),
        _row("Non-Recourse",       "non-recourse", 4.5, 85),
        _row("ABL (interest)",     "abl",      2.0, 90, is_interest=True),
    ]
    # Best = lowest cost
    best = min(rows, key=lambda r: r["cost_usd"])
    for r in rows:
        r["is_best"] = (r["kind"] == best["kind"])
    return {
        "total_invoices_usd": round(total_invoices, 2),
        "total_margin_usd":   round(total_margin, 2),
        "outstanding_ar_usd": round(total_invoices * (terms_days / 30.0), 2),
        "rows": rows,
        "recommended_kind": best["kind"],
    }


def _outreach_template(factor: Dict[str, Any], payload: OutreachGenerateIn) -> Dict[str, str]:
    """Deterministic, ready-to-send outreach email — no AI required."""
    shippers = ", ".join(payload.top_shippers[:5]) or "regional Midwest shippers"
    lanes = "; ".join(payload.lanes[:3]) or "MPLS → Chicago"
    proj_3mo_margin = payload.projected_3mo_loads * 215
    proj_6mo_margin = payload.projected_6mo_loads * 230

    subject = (
        f"Factoring Application · {payload.broker_name} · {payload.state}"
        f" · {payload.current_loads_per_month}/mo today"
    )
    body = f"""Hi {factor['name']} Team,

I'm building {payload.broker_name}, a {payload.state}-based freight brokerage focused on regional Midwest lanes. We're currently posting on DAT + Truckstop and steadily converting our top shippers to direct contracts.

**Volume Snapshot**
- Today:    {payload.current_loads_per_month} loads/mo · ~$215 avg margin/load
- Month 3:  {payload.projected_3mo_loads} loads/mo · ~${proj_3mo_margin:,.0f} margin
- Month 6:  {payload.projected_6mo_loads} loads/mo · ~${proj_6mo_margin:,.0f} margin

**Top Shippers (creditworthy, Midwest-anchored)**
{shippers}

**Primary Lanes**
{lanes}

I'm looking for a {factor['kind'].replace('+', ' + ')} relationship — your published range of {factor['fee_pct_min']}–{factor['fee_pct_max']}% fee and {factor['advance_pct']}% advance fits where we are.

I can send the following on request:
  • Signed personal guarantee + 2 yrs personal tax returns
  • Articles of Org, EIN letter, MN business license, MC/DOT authority
  • 3 months business bank statements + AR aging
  • Top-10 shipper list with D&B numbers and payment history
  • Sample BOL + sample invoice in our brand format

{("Note: " + payload.custom_note) if payload.custom_note else ""}

Looking to set up a 15-min call this week.

{payload.contact_name}
{payload.broker_name}
{payload.contact_phone or ''}  ·  {payload.contact_email or ''}
"""
    return {"subject": subject, "body": body.strip()}


# ============================================================
# Router
# ============================================================
def build_factoring_router(
    api_router: APIRouter, *, db,
    get_current_user: Callable, require_role: Callable,
    emergent_llm_key: Optional[str] = None,
    LlmChat: Any = None, UserMessage: Any = None,
) -> None:
    router = APIRouter(prefix="/factoring", tags=["factoring"])
    admin_dep = Depends(require_role("admin", "dispatcher"))

    # --------------- CATALOG ---------------
    @router.get("/factors")
    async def list_factors(_=Depends(get_current_user)) -> Dict[str, Any]:
        # Allow admin overrides (rate caps, notes etc.) merged on top
        overrides = await db.factoring_factor_overrides.find({}, {"_id": 0}).to_list(50)
        idx = {o["factor_id"]: o for o in overrides}
        merged = []
        for f in FACTOR_PARTNERS:
            ovr = idx.get(f["factor_id"], {})
            merged.append({**f, **{k: v for k, v in ovr.items() if k != "factor_id"}})
        return {"items": merged, "count": len(merged)}

    @router.get("/factors/{factor_id}")
    async def get_factor(factor_id: str, _=Depends(get_current_user)) -> Dict[str, Any]:
        return _factor_or_404(factor_id)

    # --------------- STAGES / ROADMAP ---------------
    @router.get("/stages")
    async def list_stages(_=Depends(get_current_user)) -> Dict[str, Any]:
        return {"stages": STAGES, "count": len(STAGES)}

    @router.post("/recommend-stage")
    async def recommend_stage(payload: StageRecommendationIn,
                                _=Depends(get_current_user)) -> Dict[str, Any]:
        stage = _stage_for(payload.monthly_loads)
        avg_margin = payload.avg_invoice_usd * (payload.avg_margin_pct / 100.0)
        compare = _compare_cost(
            payload.monthly_loads, payload.avg_invoice_usd, avg_margin,
            payload.payment_terms_days)
        # Pick factors matching this stage's kind
        kind = stage["type"]
        recommended_factors: List[Dict[str, Any]] = []
        for f in FACTOR_PARTNERS:
            if kind == "spot" and "spot" in f["kind"]:
                recommended_factors.append(f)
            elif kind == "recourse" and "recourse" in f["kind"] and f["min_monthly_volume_usd"] <= (payload.monthly_loads * payload.avg_invoice_usd):
                recommended_factors.append(f)
            elif kind == "recourse-multi" and "recourse" in f["kind"]:
                recommended_factors.append(f)
            elif kind == "recourse+abl-overflow" and ("recourse" in f["kind"] or "abl" in f["kind"]):
                recommended_factors.append(f)
            elif kind == "abl" and "abl" in f["kind"]:
                recommended_factors.append(f)
        # Prioritize Midwest factors
        recommended_factors.sort(key=lambda x: (not x.get("midwest"), x["fee_pct_min"]))
        return {
            "stage": stage,
            "compare": compare,
            "recommended_factors": recommended_factors[:5],
        }

    # --------------- COST CALCULATOR ---------------
    @router.post("/compare-cost")
    async def compare_cost(payload: CompareIn,
                            _=Depends(get_current_user)) -> Dict[str, Any]:
        return _compare_cost(payload.monthly_loads, payload.avg_invoice_usd,
                             payload.avg_margin_usd_per_load, payload.payment_terms_days)

    # --------------- STRATEGIES ---------------
    @router.get("/strategies")
    async def list_strategies(_=Depends(get_current_user)) -> Dict[str, Any]:
        return {"strategies": STRATEGIES, "count": len(STRATEGIES)}

    # --------------- OUTREACH ---------------
    @router.post("/outreach/generate")
    async def outreach_generate(payload: OutreachGenerateIn,
                                  _=Depends(get_current_user)) -> Dict[str, Any]:
        factor = _factor_or_404(payload.factor_id)
        tpl = _outreach_template(factor, payload)
        # Mailto link
        # Many factor sites accept first-touch via website form; we offer email too.
        mailto = (
            f"mailto:?subject={tpl['subject'].replace(' ', '%20')}"
            f"&body={tpl['body'].replace(chr(10), '%0A').replace(' ', '%20')}"
        )
        return {
            "factor": {"factor_id": factor["factor_id"],
                       "name": factor["name"],
                       "website": factor["website"],
                       "contact_methods": factor["contact_methods"]},
            "subject": tpl["subject"],
            "body":    tpl["body"],
            "mailto":  mailto,
        }

    @router.post("/outreach/ai-polish")
    async def outreach_ai_polish(payload: OutreachGenerateIn,
                                  _=Depends(get_current_user)) -> Dict[str, Any]:
        """Use Claude Sonnet to polish the deterministic template into a
        more personalized first-touch."""
        factor = _factor_or_404(payload.factor_id)
        tpl = _outreach_template(factor, payload)
        if not (emergent_llm_key and LlmChat and UserMessage):
            # AI not wired; return deterministic
            return {**tpl, "factor_name": factor["name"], "ai_polished": False}
        try:
            chat = LlmChat(api_key=emergent_llm_key,
                           session_id=f"factoring-outreach-{uuid.uuid4().hex[:8]}",
                           system_message=(
                               "You are a freight-industry sales operator helping a brand-new "
                               "Minneapolis freight brokerage write a single, confident first-touch "
                               "email to a factoring company. Keep it under 220 words. Preserve every "
                               "data point exactly. Tighten the prose, add a single line of confident "
                               "context, and end with a one-line CTA for a 15-minute call. "
                               "Do not use emojis. Do not over-promise volume."
                           ))
            chat.with_model("anthropic", "claude-sonnet-4-5-20250929")
            msg = UserMessage(text=(
                "Rewrite the following factoring-outreach email body. Keep the subject line unchanged."
                f"\n\nSUBJECT: {tpl['subject']}\n\nBODY:\n{tpl['body']}"
            ))
            polished = await chat.send_message(msg)
            polished_text = polished if isinstance(polished, str) else getattr(polished, "content", "") or str(polished)
            return {"subject": tpl["subject"], "body": polished_text.strip(),
                    "factor_name": factor["name"], "ai_polished": True}
        except Exception as exc:                                               # noqa: BLE001
            logger.warning("AI polish failed: %s", exc)
            return {**tpl, "factor_name": factor["name"], "ai_polished": False,
                    "ai_error": str(exc)[:200]}

    # --------------- APPLICATIONS ---------------
    @router.get("/applications")
    async def list_applications(_=Depends(get_current_user)) -> Dict[str, Any]:
        rows = await db.factoring_applications.find(
            {}, {"_id": 0}).sort("created_at", -1).to_list(200)
        # Attach factor name
        idx = {f["factor_id"]: f["name"] for f in FACTOR_PARTNERS}
        for r in rows:
            r["factor_name"] = idx.get(r.get("factor_id"), r.get("factor_id"))
        return {"items": rows, "count": len(rows)}

    @router.post("/applications")
    async def create_application(payload: ApplicationIn,
                                  user=admin_dep) -> Dict[str, Any]:
        _factor_or_404(payload.factor_id)
        doc = {
            "application_id": f"FAPP-{uuid.uuid4().hex[:10].upper()}",
            "created_at": _now(),
            "updated_at": _now(),
            "created_by": getattr(user, "name", "system"),
            **payload.model_dump(),
        }
        await db.factoring_applications.insert_one(dict(doc))
        doc.pop("_id", None)
        return doc

    @router.put("/applications/{application_id}")
    async def update_application(application_id: str, payload: ApplicationIn,
                                  user=admin_dep) -> Dict[str, Any]:
        upd = payload.model_dump()
        upd["updated_at"] = _now()
        upd["updated_by"] = getattr(user, "name", "system")
        r = await db.factoring_applications.update_one(
            {"application_id": application_id}, {"$set": upd})
        if r.matched_count == 0:
            raise HTTPException(404, "Application not found")
        return await db.factoring_applications.find_one(
            {"application_id": application_id}, {"_id": 0}) or {}

    @router.delete("/applications/{application_id}")
    async def delete_application(application_id: str, user=admin_dep) -> Dict[str, str]:
        r = await db.factoring_applications.delete_one(
            {"application_id": application_id})
        if r.deleted_count == 0:
            raise HTTPException(404, "Application not found")
        return {"status": "deleted"}

    # --------------- INVOICE SUBMISSIONS ---------------
    def _compute_submission(factor: Dict[str, Any], s: SubmissionIn) -> Dict[str, Any]:
        fee_pct = s.fee_pct_override or ((factor["fee_pct_min"] + factor["fee_pct_max"]) / 2.0)
        adv_pct = s.advance_pct_override or factor["advance_pct"]
        fee_usd = round(s.invoice_usd * fee_pct / 100.0, 2)
        advance_usd = round(s.invoice_usd * adv_pct / 100.0, 2)
        reserve_usd = round(s.invoice_usd - advance_usd, 2)
        # Carrier-pay readiness
        carrier_short = (s.carrier_cost_usd or 0) - advance_usd
        return {
            "fee_pct": fee_pct, "advance_pct": adv_pct,
            "fee_usd": fee_usd, "advance_usd": advance_usd,
            "reserve_usd": reserve_usd,
            "carrier_cost_usd": s.carrier_cost_usd or 0,
            "covers_carrier": (s.carrier_cost_usd or 0) <= advance_usd,
            "shortfall_usd": max(0, carrier_short),
            "broker_take_home_usd": round(advance_usd - (s.carrier_cost_usd or 0), 2),
        }

    @router.get("/submissions")
    async def list_submissions(_=Depends(get_current_user)) -> Dict[str, Any]:
        rows = await db.factoring_submissions.find(
            {}, {"_id": 0}).sort("submitted_at", -1).to_list(500)
        idx = {f["factor_id"]: f["name"] for f in FACTOR_PARTNERS}
        for r in rows:
            r["factor_name"] = idx.get(r.get("factor_id"), r.get("factor_id"))
        # Aggregates
        total_invoices = sum(r.get("invoice_usd", 0) for r in rows)
        total_advance = sum(r.get("advance_usd", 0) for r in rows)
        total_fee = sum(r.get("fee_usd", 0) for r in rows)
        total_reserve = sum(r.get("reserve_usd", 0) for r in rows)
        return {
            "items": rows, "count": len(rows),
            "totals": {
                "invoices_usd": round(total_invoices, 2),
                "advance_usd": round(total_advance, 2),
                "fee_usd":     round(total_fee, 2),
                "reserve_usd": round(total_reserve, 2),
                "effective_fee_pct": round((total_fee / total_invoices * 100), 2) if total_invoices else 0,
            },
        }

    @router.post("/submissions")
    async def create_submission(payload: SubmissionIn,
                                  user=admin_dep) -> Dict[str, Any]:
        factor = _factor_or_404(payload.factor_id)
        calc = _compute_submission(factor, payload)
        doc = {
            "submission_id": f"FSUB-{uuid.uuid4().hex[:10].upper()}",
            "submitted_at": _now(),
            "submitted_by": getattr(user, "name", "system"),
            "status": "submitted",   # submitted | approved | funded | settled | declined
            "factor_id": payload.factor_id,
            "invoice_id": payload.invoice_id,
            "customer_name": payload.customer_name,
            "invoice_usd": payload.invoice_usd,
            "payment_terms_days": payload.payment_terms_days,
            **calc,
        }
        await db.factoring_submissions.insert_one(dict(doc))
        doc.pop("_id", None)
        return doc

    @router.post("/submissions/{submission_id}/status")
    async def update_submission_status(submission_id: str,
                                         body: Dict[str, str],
                                         user=admin_dep) -> Dict[str, Any]:
        status = (body or {}).get("status")
        if status not in ("submitted", "approved", "funded", "settled", "declined"):
            raise HTTPException(400, "Invalid status")
        ts_field = {"approved": "approved_at", "funded": "funded_at",
                    "settled": "settled_at", "declined": "declined_at"}.get(status)
        upd: Dict[str, Any] = {"status": status, "updated_at": _now(),
                                "updated_by": getattr(user, "name", "system")}
        if ts_field:
            upd[ts_field] = _now()
        r = await db.factoring_submissions.update_one(
            {"submission_id": submission_id}, {"$set": upd})
        if r.matched_count == 0:
            raise HTTPException(404, "Submission not found")
        return await db.factoring_submissions.find_one(
            {"submission_id": submission_id}, {"_id": 0}) or {}

    @router.delete("/submissions/{submission_id}")
    async def delete_submission(submission_id: str, user=admin_dep) -> Dict[str, str]:
        r = await db.factoring_submissions.delete_one(
            {"submission_id": submission_id})
        if r.deleted_count == 0:
            raise HTTPException(404, "Submission not found")
        return {"status": "deleted"}

    # --------------- DASHBOARD ---------------
    @router.get("/dashboard")
    async def dashboard(_=Depends(get_current_user)) -> Dict[str, Any]:
        # Submissions totals (last 90 days)
        cutoff = (datetime.now(timezone.utc) - __import__("datetime").timedelta(days=90)).isoformat()
        subs = await db.factoring_submissions.find(
            {"submitted_at": {"$gte": cutoff}}, {"_id": 0}).to_list(2000)
        # Applications
        apps = await db.factoring_applications.find({}, {"_id": 0}).to_list(200)
        live_factors = [a for a in apps if a.get("status") in ("live", "approved")]
        # Per-factor mix
        by_factor: Dict[str, Dict[str, Any]] = {}
        idx = {f["factor_id"]: f for f in FACTOR_PARTNERS}
        for s in subs:
            fid = s.get("factor_id")
            slot = by_factor.setdefault(fid, {
                "factor_id": fid,
                "name": idx.get(fid, {}).get("name", fid),
                "invoices_usd": 0, "fee_usd": 0,
                "advance_usd": 0, "count": 0,
            })
            slot["invoices_usd"] += s.get("invoice_usd", 0)
            slot["fee_usd"]      += s.get("fee_usd", 0)
            slot["advance_usd"]  += s.get("advance_usd", 0)
            slot["count"]        += 1
        for slot in by_factor.values():
            slot["invoices_usd"] = round(slot["invoices_usd"], 2)
            slot["fee_usd"]      = round(slot["fee_usd"], 2)
            slot["advance_usd"]  = round(slot["advance_usd"], 2)
            slot["effective_fee_pct"] = round(slot["fee_usd"] / slot["invoices_usd"] * 100, 2) if slot["invoices_usd"] else 0
        total_inv = sum(v["invoices_usd"] for v in by_factor.values())
        total_fee = sum(v["fee_usd"]      for v in by_factor.values())
        monthly_loads = len(subs) // 3 if subs else 0  # rough 90-day → monthly
        stage = _stage_for(monthly_loads)
        return {
            "monthly_loads_est": monthly_loads,
            "live_factor_count": len(live_factors),
            "application_count": len(apps),
            "totals_90d": {
                "invoices_usd": round(total_inv, 2),
                "fee_usd":      round(total_fee, 2),
                "effective_fee_pct": round(total_fee / total_inv * 100, 2) if total_inv else 0,
                "submissions":  len(subs),
            },
            "by_factor": sorted(by_factor.values(), key=lambda x: -x["invoices_usd"]),
            "stage": stage,
            "applications_summary": {
                "preparing":  sum(1 for a in apps if a.get("status") == "preparing"),
                "sent":       sum(1 for a in apps if a.get("status") == "sent"),
                "underwriting": sum(1 for a in apps if a.get("status") == "underwriting"),
                "approved":   sum(1 for a in apps if a.get("status") == "approved"),
                "live":       sum(1 for a in apps if a.get("status") == "live"),
                "declined":   sum(1 for a in apps if a.get("status") == "declined"),
            },
        }

    api_router.include_router(router)
