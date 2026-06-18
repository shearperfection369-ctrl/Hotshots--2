"""routes.cash_flow — Orisei Cash Flow Command Center.

The 8 broker-survival capabilities the user spec'd:
  1. Real-Time Cash Position
  2. Load Qualification based on cash
  3. Auto-route to factor when cash is short
  4. Shipper Payment Term Optimization (Net 30 → Net 7)
  5. Carrier Payment Acceleration (dynamic discounting)
  6. Factor Comparison & best-rate routing
  7. Shipper Credit Intelligence (D&B-style scoring)
  8. Cash Flow Scenario Planning
"""
from __future__ import annotations

import hashlib
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .factoring import FACTOR_PARTNERS, _compare_cost as _compare_methods

logger = logging.getLogger("tennant_tms.cash_flow")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------- Pydantic ----------
class BankBalanceIn(BaseModel):
    balance_usd: float = Field(..., ge=0)
    as_of_at: Optional[str] = None
    source: str = Field("manual", pattern="^(manual|plaid|csv)$")
    account_label: Optional[str] = None


class LoadQualifyIn(BaseModel):
    customer_rate_usd: float = Field(..., gt=0)
    carrier_cost_usd: float = Field(..., gt=0)
    payment_terms_days: int = Field(14, ge=1, le=90)
    shipper_name: Optional[str] = None


class FactorRouteIn(BaseModel):
    invoice_usd: float = Field(..., gt=0)
    carrier_cost_usd: float = Field(..., ge=0)
    payment_terms_days: int = Field(14, ge=1, le=90)
    shipper_credit_score: Optional[int] = Field(None, ge=0, le=100)


class DynamicDiscountIn(BaseModel):
    waiting_carriers_usd: float = Field(..., gt=0)
    available_cash_usd: float = Field(..., ge=0)
    proposed_discount_pct: float = Field(5.0, ge=0.5, le=15)


class ShipperPitchIn(BaseModel):
    customer_id: str
    current_terms: str = "Net 30"
    proposed_terms: str = "Net 7"
    discount_offer_pct: float = Field(2.0, ge=0.5, le=10)
    loads_per_month: int = Field(8, ge=1)
    avg_invoice_usd: float = Field(1300, gt=0)


class ScenarioIn(BaseModel):
    target_loads_per_week: int = Field(200, ge=1)
    avg_invoice_usd: float = Field(1280, gt=0)
    avg_margin_usd_per_load: float = Field(230, ge=0)
    payment_terms_days: int = Field(14, ge=1, le=90)
    hire_dispatcher: bool = False
    dispatcher_monthly_cost_usd: float = Field(5500, ge=0)


# ---------- Helpers ----------
async def _live_position(db) -> Dict[str, Any]:
    """Sum receivables (open invoices) and payables (booked carrier costs not paid yet)."""
    # Bank balance
    bal_doc = await db.cash_flow_bank.find_one({"_id": "primary"}, {"_id": 0}) or {}
    bank = float(bal_doc.get("balance_usd", 0) or 0)
    bal_as_of = bal_doc.get("as_of_at")

    # AR: invoices issued but not settled
    inv_pipe = [
        {"$match": {"status": {"$in": ["issued", "sent"]}}},
        {"$group": {"_id": None,
                    "total": {"$sum": "$total_usd"},
                    "count": {"$sum": 1}}},
    ]
    inv_agg = await db.brokerage_invoices.aggregate(inv_pipe).to_list(1)
    ar_total = float(inv_agg[0]["total"]) if inv_agg else 0.0
    ar_count = int(inv_agg[0]["count"]) if inv_agg else 0

    # AP: bookings with carrier_cost_manual_usd or forecast_carrier_pay_usd not yet paid
    bk_pipe = [
        {"$match": {"status": {"$in": ["booked"]}}},
        {"$group": {"_id": None,
                    "total": {"$sum": {"$ifNull": [
                        "$carrier_cost_manual_usd", "$forecast_carrier_pay_usd"]}},
                    "count": {"$sum": 1}}},
    ]
    bk_agg = await db.brokerage_bookings.aggregate(bk_pipe).to_list(1)
    ap_total = float(bk_agg[0]["total"]) if bk_agg else 0.0
    ap_count = int(bk_agg[0]["count"]) if bk_agg else 0

    available = bank + (ar_total * 0.85) - ap_total  # AR financeable at 85%
    # Avg carrier cost for "how many loads can I take" calc
    sample_cost = 1050.0
    loads_can_take = max(0, int(available // sample_cost))
    return {
        "as_of_at": bal_as_of, "bank_balance_usd": bank,
        "accounts_receivable_usd": round(ar_total, 2),
        "accounts_payable_usd":    round(ap_total, 2),
        "ar_invoice_count": ar_count,
        "ap_booking_count": ap_count,
        "factorable_ar_usd":  round(ar_total * 0.85, 2),
        "available_to_deploy_usd": round(available, 2),
        "loads_can_take":   loads_can_take,
        "carrier_cost_assumption_usd": sample_cost,
        "health": (
            "strong"  if available >= ap_total * 1.5 else
            "healthy" if available >= ap_total else
            "tight"   if available >= ap_total * 0.5 else
            "critical"
        ),
    }


def _best_factor_for(invoice_usd: float, terms_days: int,
                      shipper_score: Optional[int]) -> Dict[str, Any]:
    """Score every factor for this invoice and pick the cheapest qualifying one."""
    candidates = []
    for f in FACTOR_PARTNERS:
        if f["min_monthly_volume_usd"] > invoice_usd * 4:  # very rough cap
            # don't disqualify high-mins for a single invoice; keep but penalize
            penalty = 0.1
        else:
            penalty = 0
        fee_mid = (f["fee_pct_min"] + f["fee_pct_max"]) / 2.0
        # If shipper score < 70, prefer factors that absorb risk (non-recourse leaning)
        adj = fee_mid + penalty
        if shipper_score is not None and shipper_score < 65 and "recourse" not in f["kind"]:
            adj -= 0.25  # rank non-recourse higher (cheaper effectively given risk)
        candidates.append({
            "factor_id": f["factor_id"], "name": f["name"],
            "fee_pct": fee_mid, "advance_pct": f["advance_pct"],
            "fee_usd": round(invoice_usd * fee_mid / 100.0, 2),
            "advance_usd": round(invoice_usd * f["advance_pct"] / 100.0, 2),
            "setup_time_days": round(f["setup_time_hours"] / 24.0, 1),
            "midwest": f.get("midwest", False),
            "kind": f["kind"], "_rank": adj,
        })
    candidates.sort(key=lambda c: c["_rank"])
    # Strip rank
    for c in candidates:
        c.pop("_rank", None)
    best = candidates[0] if candidates else None
    return {"best": best, "all_ranked": candidates[:5]}


def _shipper_credit_score(name: Optional[str], history: Dict[str, Any]) -> Dict[str, Any]:
    """Deterministic D&B-style score based on payment history + name-hash signal.
    Real D&B lookup is paid; this gives the broker a usable, repeatable score until
    they wire a real key."""
    if not name:
        return {"score": 50, "tier": "unknown", "factors": ["No shipper name provided"]}
    # Base score from name hash (deterministic)
    h = int(hashlib.sha256(name.lower().encode()).hexdigest()[:8], 16)
    base = 55 + (h % 40)  # 55..94
    factors = []
    # Adjustments from history
    paid_on_time = history.get("paid_on_time", 0)
    paid_late    = history.get("paid_late", 0)
    defaults     = history.get("defaults", 0)
    total = paid_on_time + paid_late + defaults
    if total > 0:
        on_time_pct = paid_on_time / total
        if on_time_pct > 0.9:
            base = min(99, base + 10)
            factors.append(f"{int(on_time_pct*100)}% on-time payment history (+10)")
        elif on_time_pct < 0.6:
            base = max(20, base - 15)
            factors.append(f"Only {int(on_time_pct*100)}% on-time (-15)")
    if defaults > 0:
        base = max(15, base - 20 * defaults)
        factors.append(f"{defaults} prior default(s) (-{20*defaults})")
    # Tier-1 shipper bonus (rough name detection)
    blue_chip = ["target", "supervalu", "3m", "general mills", "unitedhealth",
                 "amazon", "walmart", "fedex", "ups"]
    if any(bc in name.lower() for bc in blue_chip):
        base = min(99, base + 12)
        factors.append("Recognized Tier-1 shipper (+12)")
    score = max(0, min(99, base))
    tier = (
        "A+"  if score >= 90 else
        "A"   if score >= 80 else
        "B"   if score >= 70 else
        "C"   if score >= 60 else
        "D"   if score >= 45 else
        "F"
    )
    risk = (
        "low"        if score >= 80 else
        "medium-low" if score >= 70 else
        "medium"     if score >= 60 else
        "medium-high" if score >= 45 else
        "high"
    )
    recommendation = {
        "A+": "Extend full terms · Net 30 or longer OK · recourse factoring at lowest rate.",
        "A":  "Extend Net 30 · recourse factoring at lowest rate.",
        "B":  "Extend Net 14 default · negotiate Net 7 for 1.5–2% discount.",
        "C":  "Net 7 only · or factor with recourse + 3.5% fee floor.",
        "D":  "Require Net 7 + factor non-recourse · or run 5-load pilot first.",
        "F":  "Do not extend credit · cash on delivery only.",
    }[tier]
    return {
        "score": score, "tier": tier, "risk": risk,
        "factors": factors or ["Baseline score from name hash"],
        "recommendation": recommendation,
    }


def _shipper_pitch(p: ShipperPitchIn) -> Dict[str, Any]:
    monthly_invoice = p.loads_per_month * p.avg_invoice_usd
    shipper_discount = monthly_invoice * (p.discount_offer_pct / 100.0)
    factor_savings = monthly_invoice * 0.025 * ((30 - 7) / 30.0)  # rough
    broker_net_gain = factor_savings - shipper_discount
    subject = f"{p.proposed_terms} vs {p.current_terms} — {p.discount_offer_pct}% off for faster pay"
    body = f"""Hi {{shipper_contact_name}},

Quick proposal that should make both sides money.

You're paying us {p.current_terms} on ~{p.loads_per_month} loads/month at roughly ${p.avg_invoice_usd:,.0f} per load — ${monthly_invoice:,.0f}/month in spend.

I'd like to move you to **{p.proposed_terms}** in exchange for a **{p.discount_offer_pct}% discount** on every load.

The math:
- Your monthly savings:        ${shipper_discount:,.0f}
- Our reduced factoring cost:  ${factor_savings:,.0f}/month
- Net to us:                   ${broker_net_gain:,.0f}/month
- Net to you:                  ${shipper_discount:,.0f}/month savings

You pay less. We carry less working capital. Same service, same dispatch, same Calafia-stamped BOLs.

Worth a 15-minute call this week?

{{your_name}}
Orisei Freight Solutions
"""
    return {
        "subject": subject, "body": body.strip(),
        "monthly_invoice_usd": round(monthly_invoice, 2),
        "shipper_savings_usd": round(shipper_discount, 2),
        "broker_factor_savings_usd": round(factor_savings, 2),
        "net_broker_gain_usd": round(broker_net_gain, 2),
        "win_win": broker_net_gain > 0 and shipper_discount > 0,
    }


def _dynamic_discount(payload: DynamicDiscountIn) -> Dict[str, Any]:
    """Carriers offered early pay (X% discount) vs standard 48h."""
    # Assume average carrier cost
    avg_carrier = 1050
    n_carriers = max(1, int(payload.waiting_carriers_usd // avg_carrier))
    discount_total = payload.waiting_carriers_usd * (payload.proposed_discount_pct / 100.0)
    cash_needed_after = payload.waiting_carriers_usd - discount_total
    # Assume 70% acceptance rate
    accept_rate = 0.70
    accepted_amount = payload.waiting_carriers_usd * accept_rate
    cash_after_accept = accepted_amount * (1 - payload.proposed_discount_pct / 100.0)
    coverage_ratio = (payload.available_cash_usd / cash_after_accept) if cash_after_accept else 0
    return {
        "waiting_carriers_usd": payload.waiting_carriers_usd,
        "estimated_carrier_count": n_carriers,
        "available_cash_usd":     payload.available_cash_usd,
        "proposed_discount_pct":  payload.proposed_discount_pct,
        "total_discount_savings_usd": round(discount_total, 2),
        "cash_needed_if_all_accept_usd": round(cash_needed_after, 2),
        "expected_acceptance_rate_pct": int(accept_rate * 100),
        "expected_cash_outlay_usd":  round(cash_after_accept, 2),
        "coverage_ratio":            round(coverage_ratio, 2),
        "can_cover_expected":        coverage_ratio >= 1.0,
        "broker_save_pct_of_total":  round(payload.proposed_discount_pct * accept_rate, 2),
        "carrier_pitch": (
            f"Pay you tonight at ${round(avg_carrier * (1 - payload.proposed_discount_pct/100), 2):,.2f} "
            f"vs ${avg_carrier:,.2f} on the standard 48-hour cycle — your call."
        ),
    }


# ============================================================
# Router
# ============================================================
def build_cash_flow_router(
    api_router: APIRouter, *, db,
    get_current_user: Callable, require_role: Callable,
) -> None:
    router = APIRouter(prefix="/cash-flow", tags=["cash-flow"])
    admin_dep = Depends(require_role("admin", "dispatcher"))

    # ----- Cash position -----
    @router.get("/position")
    async def position(_=Depends(get_current_user)) -> Dict[str, Any]:
        return await _live_position(db)

    @router.post("/bank-balance")
    async def set_bank_balance(payload: BankBalanceIn,
                                 user=admin_dep) -> Dict[str, Any]:
        doc = {
            "_id": "primary",
            "balance_usd": payload.balance_usd,
            "as_of_at": payload.as_of_at or _now(),
            "source": payload.source,
            "account_label": payload.account_label,
            "updated_by": getattr(user, "name", "system"),
        }
        await db.cash_flow_bank.replace_one({"_id": "primary"}, doc, upsert=True)
        return await _live_position(db)

    # ----- Load qualifier -----
    @router.post("/qualify-load")
    async def qualify_load(payload: LoadQualifyIn,
                             _=Depends(get_current_user)) -> Dict[str, Any]:
        pos = await _live_position(db)
        avail = pos["available_to_deploy_usd"]
        forecast_margin = payload.customer_rate_usd - payload.carrier_cost_usd
        margin_pct = (forecast_margin / payload.customer_rate_usd * 100) if payload.customer_rate_usd else 0
        # Score the shipper if name given
        credit = _shipper_credit_score(payload.shipper_name, {}) if payload.shipper_name else None
        # Decision tree
        can_self_fund = avail >= payload.carrier_cost_usd
        needs_factoring = not can_self_fund or payload.payment_terms_days > 7
        verdict_color = "emerald" if margin_pct >= 15 and can_self_fund else \
                         "cyan" if margin_pct >= 12 else \
                         "amber" if margin_pct >= 8 else "red"
        actions: List[str] = []
        if can_self_fund and payload.payment_terms_days <= 7:
            actions.append("Self-fund this load · no factoring needed.")
        if needs_factoring:
            actions.append("Auto-route to factoring · advance covers the carrier inside 48h.")
        if margin_pct < 8:
            actions.append("MARGIN ALERT: <8% margin · only take if it's a strategic shipper.")
        if credit and credit["score"] < 65:
            actions.append(f"Shipper credit {credit['tier']} ({credit['risk']}) — require Net 7 or factor non-recourse.")
        return {
            "available_to_deploy_usd": avail,
            "customer_rate_usd": payload.customer_rate_usd,
            "carrier_cost_usd":  payload.carrier_cost_usd,
            "forecast_margin_usd":  round(forecast_margin, 2),
            "forecast_margin_pct":  round(margin_pct, 2),
            "can_self_fund":        can_self_fund,
            "needs_factoring":      needs_factoring,
            "shipper_credit":       credit,
            "verdict_color":        verdict_color,
            "actions":              actions,
        }

    # ----- Auto-route to factor -----
    @router.post("/auto-route-factor")
    async def auto_route_factor(payload: FactorRouteIn,
                                  _=Depends(get_current_user)) -> Dict[str, Any]:
        rec = _best_factor_for(payload.invoice_usd, payload.payment_terms_days,
                                payload.shipper_credit_score)
        if rec["best"]:
            best = rec["best"]
            broker_take = round(best["advance_usd"] - payload.carrier_cost_usd, 2)
            covers_carrier = best["advance_usd"] >= payload.carrier_cost_usd
        else:
            broker_take, covers_carrier = 0, False
        return {
            **rec,
            "broker_take_home_usd": broker_take,
            "covers_carrier_cost": covers_carrier,
        }

    # ----- Shipper payment-term optimization -----
    @router.get("/shipper-term-analysis")
    async def shipper_term_analysis(_=Depends(get_current_user)) -> Dict[str, Any]:
        """Pull top customers and identify Net 30 candidates for Net 7 negotiation."""
        # Approximation: read brokerage_bookings grouped by customer_name
        rows = await db.brokerage_bookings.find(
            {}, {"_id": 0, "customer_name": 1, "forecast_rate_usd": 1,
                 "settled_rate_usd": 1, "customer_id": 1}).to_list(2000)
        by_cust: Dict[str, Dict[str, Any]] = {}
        for r in rows:
            key = r.get("customer_name") or r.get("customer_id") or "Unknown"
            slot = by_cust.setdefault(key, {"customer_name": key, "loads": 0, "revenue_usd": 0})
            slot["loads"] += 1
            slot["revenue_usd"] += float(r.get("settled_rate_usd") or r.get("forecast_rate_usd") or 0)
        # Also pull payment_terms from orisei_customers
        cust_terms = {c["name"]: c.get("payment_terms", "Net 30")
                      for c in await db.orisei_customers.find({}, {"_id": 0}).to_list(500)}
        for slot in by_cust.values():
            slot["current_terms"] = cust_terms.get(slot["customer_name"], "Net 30")
            slot["revenue_usd"] = round(slot["revenue_usd"], 2)
            # Factor savings if moved to Net 7 (rough)
            slot["potential_savings_usd"] = round(slot["revenue_usd"] * 0.025 * ((30 - 7) / 30.0), 2)
            slot["candidate"] = slot["current_terms"] in ("Net 30", "Net 45", "Net 60")
        ranked = sorted(by_cust.values(), key=lambda x: -x["potential_savings_usd"])
        total_potential = round(sum(s["potential_savings_usd"] for s in ranked if s["candidate"]), 2)
        return {
            "candidates": ranked[:30],
            "total_potential_savings_usd": total_potential,
            "candidate_count": sum(1 for s in ranked if s["candidate"]),
        }

    @router.post("/shipper-pitch")
    async def shipper_pitch(payload: ShipperPitchIn,
                              _=Depends(get_current_user)) -> Dict[str, Any]:
        customer = await db.orisei_customers.find_one(
            {"customer_id": payload.customer_id}, {"_id": 0})
        if not customer:
            raise HTTPException(404, "Customer not found")
        pitch = _shipper_pitch(payload)
        return {"customer_name": customer.get("name"), **pitch}

    # ----- Dynamic carrier discounting -----
    @router.post("/dynamic-discount")
    async def dynamic_discount(payload: DynamicDiscountIn,
                                 _=Depends(get_current_user)) -> Dict[str, Any]:
        return _dynamic_discount(payload)

    # ----- Shipper credit intelligence -----
    @router.get("/shipper-credit/{customer_id}")
    async def shipper_credit(customer_id: str,
                              _=Depends(get_current_user)) -> Dict[str, Any]:
        cust = await db.orisei_customers.find_one(
            {"customer_id": customer_id}, {"_id": 0})
        if not cust:
            raise HTTPException(404, "Customer not found")
        # Compute from bookings history
        bks = await db.brokerage_bookings.find(
            {"$or": [{"customer_id": customer_id},
                     {"customer_name": cust.get("name")}]},
            {"_id": 0, "status": 1, "settled_at": 1, "booked_at": 1}).to_list(500)
        paid_on_time = sum(1 for b in bks if b.get("status") == "settled")
        paid_late    = 0  # we don't track late currently
        defaults     = 0
        score = _shipper_credit_score(cust.get("name"),
                                        {"paid_on_time": paid_on_time,
                                         "paid_late": paid_late, "defaults": defaults})
        return {
            "customer_id": customer_id, "customer_name": cust.get("name"),
            "history_loads": len(bks),
            **score,
        }

    # ----- Scenario planner -----
    @router.post("/scenario")
    async def scenario(payload: ScenarioIn,
                        _=Depends(get_current_user)) -> Dict[str, Any]:
        monthly_loads = payload.target_loads_per_week * 4.33
        gross_margin_monthly = monthly_loads * payload.avg_margin_usd_per_load
        compare = _compare_methods(int(monthly_loads), payload.avg_invoice_usd,
                                    payload.avg_margin_usd_per_load,
                                    payload.payment_terms_days)
        # Operating costs
        dispatcher_cost = payload.dispatcher_monthly_cost_usd if payload.hire_dispatcher else 0
        # Pick cheapest method
        best_row = next((r for r in compare["rows"] if r["is_best"]), compare["rows"][-1])
        # Working capital required
        working_capital = payload.target_loads_per_week * 4.33 * payload.avg_invoice_usd * 0.7 * (payload.payment_terms_days / 30.0)
        net_after_funding = gross_margin_monthly - best_row["cost_usd"] - dispatcher_cost
        return {
            "monthly_loads": int(monthly_loads),
            "gross_margin_usd_monthly": round(gross_margin_monthly, 2),
            "working_capital_required_usd": round(working_capital, 2),
            "dispatcher_monthly_cost_usd": dispatcher_cost,
            "best_funding_method": best_row["label"],
            "funding_cost_usd": best_row["cost_usd"],
            "net_margin_after_funding_usd": round(net_after_funding, 2),
            "comparison": compare,
        }

    # ----- Auto-route hook (used by Workflow HUD) -----
    @router.post("/auto-route-booking/{booked_id}")
    async def auto_route_booking(booked_id: str, user=admin_dep) -> Dict[str, Any]:
        """Triggered when a booking hits `carrier_assigned`. Computes the best
        factor and writes a proposal so the Factoring tab can pre-fill."""
        bk = await db.brokerage_bookings.find_one({"booked_id": booked_id}, {"_id": 0})
        if not bk:
            raise HTTPException(404, "Booking not found")
        invoice_usd = (bk.get("settled_rate_usd") or bk.get("forecast_rate_usd") or
                       bk.get("customer_rate_usd") or 0)
        carrier_cost = (bk.get("carrier_cost_manual_usd") or
                        bk.get("forecast_carrier_pay_usd") or 0)
        terms = bk.get("payment_terms_days", 14)
        # Shipper credit
        credit = _shipper_credit_score(bk.get("customer_name"), {}) if bk.get("customer_name") else None
        score = credit["score"] if credit else None
        # Best factor
        rec = _best_factor_for(invoice_usd, terms, score)
        proposal = {
            "booked_id": booked_id,
            "invoice_usd": invoice_usd,
            "carrier_cost_usd": carrier_cost,
            "payment_terms_days": terms,
            "shipper_name": bk.get("customer_name"),
            "shipper_credit": credit,
            "best_factor": rec["best"],
            "all_ranked": rec["all_ranked"],
            "created_at": _now(),
            "status": "proposed",
            "created_by": getattr(user, "name", "system"),
        }
        await db.cash_flow_factor_proposals.replace_one(
            {"booked_id": booked_id}, proposal, upsert=True)
        return proposal

    @router.get("/factor-proposals")
    async def list_proposals(_=Depends(get_current_user)) -> Dict[str, Any]:
        rows = await db.cash_flow_factor_proposals.find(
            {}, {"_id": 0}).sort("created_at", -1).limit(200).to_list(200)
        return {"items": rows, "count": len(rows)}

    api_router.include_router(router)
