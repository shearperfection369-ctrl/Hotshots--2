"""routes.brokerage — full freight-brokerage operations stack.

Mocked-where-it-matters, real-where-it-matters:
  • Load boards (DAT, Truckstop, Convoy, Uber Freight, 123 Load Board) →
    deterministic synthetic feed per board with a per-board margin profile.
  • Margin tracker → real DB-backed records of settled vs forecast per load.
  • Accounting (invoices, expenses, P&L, aging, 1099 totals) → real DB.
  • Compliance forms → real ReportLab-rendered fillable-style PDFs.
  • QuickBooks → mocked "connection" + queue of pending syncs.
  • AI Assistant → real Emergent LLM (Claude Sonnet 4.5).
"""

from __future__ import annotations

import io
import logging
import random
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


logger = logging.getLogger("tennant_tms.brokerage")


# ---------- Static metadata used everywhere ----------
# Tier-A list-rate operating cost per integrated provider. Used by
# /api/brokerage/cost-summary to surface live spend on the Cost Analysis tab.
# Keep in sync with /app/COST_ANALYSIS.md.
PROVIDER_COSTS: Dict[str, Dict[str, Any]] = {
    "quickbooks":    {"name": "QuickBooks Online",      "category": "Accounting",       "model": "fixed",     "monthly_usd": 90,  "plan": "Online Plus"},
    "dat":           {"name": "DAT One",                "category": "Load Board",       "model": "fixed",     "monthly_usd": 279, "plan": "Power"},
    "truckstop":     {"name": "Truckstop",              "category": "Load Board",       "model": "fixed",     "monthly_usd": 199, "plan": "Premium"},
    "uber_freight":  {"name": "Uber Freight",           "category": "Load Board",       "model": "variable",  "monthly_usd": 0,   "plan": "Pay-as-you-go", "note": "Per-load fee on bookings"},
    "loadboard_123": {"name": "123Loadboard",           "category": "Load Board",       "model": "fixed",     "monthly_usd": 40,  "plan": "Standard"},
    "stripe":        {"name": "Stripe",                 "category": "Payments",         "model": "variable",  "monthly_usd": 0,   "plan": "Per-transaction", "note": "2.9% + $0.30 per card; 0.8% ACH"},
    "resend":        {"name": "Resend",                 "category": "Email",            "model": "fixed",     "monthly_usd": 20,  "plan": "Pro"},
    "twilio":        {"name": "Twilio SMS",             "category": "Messaging",        "model": "variable",  "monthly_usd": 0,   "plan": "Pay-as-you-go", "note": "~$0.0083 per SMS US/CA"},
    "macropoint":    {"name": "Macropoint / Project44", "category": "Tracking",         "model": "fixed",     "monthly_usd": 150, "plan": "Starter"},
    "rmis":          {"name": "RMIS",                   "category": "Carrier Vetting",  "model": "fixed",     "monthly_usd": 100, "plan": "Standard"},
    "apex_capital":  {"name": "Apex Capital",           "category": "Factoring",        "model": "factoring", "monthly_usd": 0,   "plan": "Per-invoice %", "default_rate_pct": 2.5,  "note": "Carrier-side factor"},
    "triumph":       {"name": "TriumphPay",             "category": "Factoring",        "model": "factoring", "monthly_usd": 0,   "plan": "Per-invoice %", "default_rate_pct": 2.0,  "note": "Quick-pay rails"},
    "otr_capital":   {"name": "OTR Capital",            "category": "Factoring",        "model": "factoring", "monthly_usd": 0,   "plan": "Per-invoice %", "default_rate_pct": 3.0,  "note": "Broker quick-pay line"},
    "rts_financial": {"name": "RTS Financial",          "category": "Factoring",        "model": "factoring", "monthly_usd": 0,   "plan": "Per-invoice %", "default_rate_pct": 2.5},
}


def _read_doc(filename: str, missing_msg: str) -> Dict[str, Any]:
    """Shared helper: load a top-level markdown asset and return its payload."""
    path = Path(__file__).resolve().parents[2] / filename
    if not path.exists():
        raise HTTPException(404, missing_msg)
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.exception("Failed to read %s: %s", filename, exc)
        raise HTTPException(500, f"Unable to read {filename}")
    stat = path.stat()
    return {
        "path": str(path),
        "filename": path.name,
        "size_bytes": stat.st_size,
        "updated_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        "markdown": content,
    }


LOAD_BOARDS = [
    {"id": "dat", "name": "DAT One", "color": "#FF6B35", "subscription_tier": "Power"},
    {"id": "truckstop", "name": "Truckstop", "color": "#0066CC", "subscription_tier": "Premium"},
    {"id": "convoy", "name": "Convoy", "color": "#7C3AED", "subscription_tier": "Plus"},
    {"id": "uberfreight", "name": "Uber Freight", "color": "#000000", "subscription_tier": "Pro"},
    {"id": "123loadboard", "name": "123Loadboard", "color": "#10B981", "subscription_tier": "Standard"},
]

COMPLIANCE_FORMS = [
    # MC/DOT essentials
    {"id": "mc-authority",     "category": "MC/DOT",       "name": "MC Authority Application Data Sheet",   "fmcsa": True,  "expires_in_days": 365},
    {"id": "boc-3",            "category": "MC/DOT",       "name": "BOC-3 Process Agent Designation",       "fmcsa": True,  "expires_in_days": None},
    {"id": "bmc-84",           "category": "MC/DOT",       "name": "BMC-84 Surety Bond ($75,000)",          "fmcsa": True,  "expires_in_days": 365},
    {"id": "ucr",              "category": "MC/DOT",       "name": "UCR Registration Tracker",              "fmcsa": True,  "expires_in_days": 365},
    # Operational
    {"id": "rate-conf",        "category": "Operational",  "name": "Rate Confirmation",                     "fmcsa": False, "expires_in_days": None},
    {"id": "load-tender",      "category": "Operational",  "name": "Load Tender",                           "fmcsa": False, "expires_in_days": None},
    {"id": "carrier-packet",   "category": "Operational",  "name": "Carrier Packet (W-9 / NOA / COI)",      "fmcsa": False, "expires_in_days": None},
    {"id": "msa",              "category": "Operational",  "name": "Master Service Agreement",              "fmcsa": False, "expires_in_days": None},
    {"id": "carrier-onboard",  "category": "Operational",  "name": "Carrier Onboarding Checklist",          "fmcsa": False, "expires_in_days": None},
    # Accounting
    {"id": "customer-invoice", "category": "Accounting",   "name": "Customer Invoice",                      "fmcsa": False, "expires_in_days": None},
    {"id": "aging-report",     "category": "Accounting",   "name": "A/R Aging Report",                      "fmcsa": False, "expires_in_days": None},
    {"id": "1099-summary",     "category": "Accounting",   "name": "1099-NEC Carrier Summary",              "fmcsa": False, "expires_in_days": None},
    {"id": "mileage-log",      "category": "Accounting",   "name": "Driver Mileage Log",                    "fmcsa": False, "expires_in_days": None},
    {"id": "factoring",        "category": "Accounting",   "name": "Factoring Assignment Notice",           "fmcsa": False, "expires_in_days": None},
    {"id": "quick-pay",        "category": "Accounting",   "name": "Quick-Pay Request",                     "fmcsa": False, "expires_in_days": None},
]


# ---------- Synthetic feed helpers ----------
LANES = [
    ("Atlanta, GA",     "Dallas, TX",      781),
    ("Chicago, IL",     "Los Angeles, CA", 2015),
    ("Phoenix, AZ",     "Seattle, WA",     1418),
    ("Miami, FL",       "Newark, NJ",      1289),
    ("Denver, CO",      "Minneapolis, MN", 911),
    ("Houston, TX",     "Charlotte, NC",   1058),
    ("Memphis, TN",     "Indianapolis, IN", 461),
    ("Salt Lake City, UT", "Portland, OR", 768),
    ("Kansas City, MO", "Columbus, OH",    652),
    ("San Antonio, TX", "Jacksonville, FL", 950),
]
EQUIPMENT = ["Van", "Reefer", "Flatbed", "Power Only", "Step Deck"]
COMMODITIES = ["General Freight", "Frozen Foods", "Steel Coils", "Auto Parts", "Lumber", "Packaged Goods", "Beverages"]
SHIPPERS = ["Walmart DC", "Target DC", "Amazon FBA", "Costco DC", "Home Depot", "Lowe's RDC", "Pepsi", "Kraft Heinz"]


def _gen_loads_for_board(board_id: str, count: int = 18) -> List[Dict[str, Any]]:
    """Deterministic synthetic loads with a board-specific bias profile."""
    rnd = random.Random(f"loads::{board_id}::{datetime.now(timezone.utc).strftime('%Y-%m-%d-%H')}")
    profile = {
        "dat":         {"rpm_base": 2.35, "margin_pct_base": 0.16, "post_age_h": (0, 6)},
        "truckstop":   {"rpm_base": 2.28, "margin_pct_base": 0.15, "post_age_h": (1, 8)},
        "convoy":      {"rpm_base": 2.42, "margin_pct_base": 0.18, "post_age_h": (0, 4)},
        "uberfreight": {"rpm_base": 2.31, "margin_pct_base": 0.13, "post_age_h": (0, 3)},
        "123loadboard": {"rpm_base": 2.18, "margin_pct_base": 0.12, "post_age_h": (2, 24)},
    }.get(board_id, {"rpm_base": 2.20, "margin_pct_base": 0.14, "post_age_h": (1, 12)})

    out: List[Dict[str, Any]] = []
    for i in range(count):
        origin, dest, miles = rnd.choice(LANES)
        eq = rnd.choice(EQUIPMENT)
        commodity = rnd.choice(COMMODITIES)
        shipper = rnd.choice(SHIPPERS)
        rpm = round(profile["rpm_base"] + rnd.uniform(-0.40, 0.55), 2)
        rate = round(rpm * miles, 2)
        margin_pct = max(0.04, min(0.32, profile["margin_pct_base"] + rnd.uniform(-0.06, 0.10)))
        carrier_pay = round(rate * (1 - margin_pct), 2)
        forecast_margin = round(rate - carrier_pay, 2)
        weight = rnd.randint(20000, 45000)
        post_age = rnd.randint(*profile["post_age_h"])
        ai_score = round(70 + (margin_pct - 0.10) * 200 + rnd.uniform(-12, 8), 1)
        ai_score = max(0, min(100, ai_score))
        out.append({
            "load_id": f"{board_id.upper()}-{rnd.randint(100000, 999999)}",
            "board_id": board_id,
            "origin": origin,
            "destination": dest,
            "miles": miles,
            "equipment": eq,
            "commodity": commodity,
            "shipper": shipper,
            "rate_usd": rate,
            "rpm": rpm,
            "carrier_pay_usd": carrier_pay,
            "forecast_margin_usd": forecast_margin,
            "margin_pct": round(margin_pct * 100, 1),
            "weight_lbs": weight,
            "pickup_date": (datetime.now(timezone.utc) + timedelta(days=rnd.randint(0, 4))).date().isoformat(),
            "delivery_date": (datetime.now(timezone.utc) + timedelta(days=rnd.randint(2, 7))).date().isoformat(),
            "posted_minutes_ago": post_age * 60,
            "ai_score": ai_score,
            "ai_tags": _ai_tags(margin_pct, rpm, post_age),
        })
    out.sort(key=lambda x: -x["ai_score"])
    return out


def _ai_tags(margin_pct: float, rpm: float, post_age_h: int) -> List[str]:
    tags = []
    if margin_pct > 0.20: tags.append("high-margin")
    if rpm > 2.60:        tags.append("above-market")
    if rpm < 2.00:        tags.append("below-market")
    if post_age_h < 2:    tags.append("fresh-post")
    if post_age_h > 12:   tags.append("stale")
    return tags


# ---------- Pydantic models ----------
class BookLoadIn(BaseModel):
    load_id: str
    board_id: str
    carrier_name: str = Field(..., min_length=1, max_length=80)
    carrier_mc: Optional[str] = None
    notes: Optional[str] = None


class SettleLoadIn(BaseModel):
    booked_id: str
    settled_rate_usd: float = Field(..., ge=0)
    settled_carrier_pay_usd: float = Field(..., ge=0)
    invoice_paid_at: Optional[str] = None


class InvoiceIn(BaseModel):
    customer: str = Field(..., min_length=1, max_length=120)
    customer_email: Optional[str] = None
    load_ref: Optional[str] = None
    amount_usd: float = Field(..., ge=0)
    due_date: str   # ISO date


class ExpenseIn(BaseModel):
    category: str = Field(..., min_length=1, max_length=60)
    vendor: str = Field(..., min_length=1, max_length=120)
    amount_usd: float = Field(..., ge=0)
    paid_date: str
    notes: Optional[str] = None


class FormFillIn(BaseModel):
    form_id: str
    fields: Dict[str, Any] = {}


class BrokerageAIIn(BaseModel):
    question: str = Field(..., min_length=2, max_length=1500)
    context: Optional[str] = None


# ---------- Router builder ----------
def build_brokerage_router(
    *,
    db,
    get_current_user: Callable,
    require_role: Callable,
    emergent_llm_key: Optional[str],
    LlmChat,            # noqa: N803
    UserMessage,        # noqa: N803
) -> APIRouter:
    router = APIRouter(prefix="/brokerage")

    # ============================ LOAD BOARDS ============================
    @router.get("/boards")
    async def list_boards(_=Depends(get_current_user)):
        """Returns the load-board catalog + per-board live load count."""
        out = []
        for b in LOAD_BOARDS:
            out.append({**b, "live_loads": len(_gen_loads_for_board(b["id"]))})
        return {"boards": out}

    @router.get("/boards/{board_id}/loads")
    async def board_loads(
        board_id: str,
        equipment: Optional[str] = None,
        origin: Optional[str] = None,
        _=Depends(get_current_user),
    ):
        rows = _gen_loads_for_board(board_id)
        if equipment: rows = [r for r in rows if r["equipment"].lower() == equipment.lower()]
        if origin:    rows = [r for r in rows if origin.lower() in r["origin"].lower()]
        return {"board_id": board_id, "count": len(rows), "loads": rows}

    @router.get("/loads/match")
    async def ai_match_loads(_=Depends(get_current_user), top: int = 12):
        """AI-ranked top loads across **all** boards."""
        all_loads = []
        for b in LOAD_BOARDS:
            all_loads.extend(_gen_loads_for_board(b["id"]))
        all_loads.sort(key=lambda x: -x["ai_score"])
        return {"loads": all_loads[:top], "considered": len(all_loads)}

    # ============================ MARGIN TRACKER ============================
    @router.post("/loads/book")
    async def book_load(payload: BookLoadIn, user=Depends(get_current_user)):
        """Book a load → store as a forecasted margin row."""
        all_loads = _gen_loads_for_board(payload.board_id)
        load = next((l for l in all_loads if l["load_id"] == payload.load_id), None)
        if not load:
            raise HTTPException(404, "Load not found on that board")
        doc = {
            "booked_id": f"BK-{uuid.uuid4().hex[:10].upper()}",
            "load_id": payload.load_id,
            "board_id": payload.board_id,
            "carrier_name": payload.carrier_name,
            "carrier_mc": payload.carrier_mc,
            "origin": load["origin"],
            "destination": load["destination"],
            "miles": load["miles"],
            "equipment": load["equipment"],
            "forecast_rate_usd": load["rate_usd"],
            "forecast_carrier_pay_usd": load["carrier_pay_usd"],
            "forecast_margin_usd": load["forecast_margin_usd"],
            "settled_rate_usd": None,
            "settled_carrier_pay_usd": None,
            "settled_margin_usd": None,
            "status": "booked",
            "booked_at": datetime.now(timezone.utc).isoformat(),
            "booked_by": user.user_id,
            "notes": payload.notes,
        }
        await db.brokerage_bookings.insert_one(dict(doc))
        return doc

    @router.post("/loads/settle")
    async def settle_load(payload: SettleLoadIn, _=Depends(get_current_user)):
        """Mark a booked load as settled (invoice paid)."""
        margin = round(payload.settled_rate_usd - payload.settled_carrier_pay_usd, 2)
        r = await db.brokerage_bookings.find_one_and_update(
            {"booked_id": payload.booked_id},
            {"$set": {
                "settled_rate_usd": payload.settled_rate_usd,
                "settled_carrier_pay_usd": payload.settled_carrier_pay_usd,
                "settled_margin_usd": margin,
                "status": "settled",
                "settled_at": datetime.now(timezone.utc).isoformat(),
            }},
            return_document=True,
            projection={"_id": 0},
        )
        if not r:
            raise HTTPException(404, "Booking not found")
        return r

    @router.get("/margins")
    async def margins(_=Depends(get_current_user)):
        """Margin scorecard per board: forecast vs settled."""
        rows = await db.brokerage_bookings.find({}, {"_id": 0}).sort("booked_at", -1).to_list(500)
        by_board: Dict[str, Dict[str, Any]] = {}
        for b in LOAD_BOARDS:
            by_board[b["id"]] = {
                "board_id": b["id"], "name": b["name"], "color": b["color"],
                "loads_booked": 0, "loads_settled": 0,
                "forecast_margin_usd": 0.0, "settled_margin_usd": 0.0,
                "win_rate": 0.0,
            }
        for r in rows:
            bid = r.get("board_id")
            if bid not in by_board:
                continue
            slot = by_board[bid]
            slot["loads_booked"] += 1
            slot["forecast_margin_usd"] += r.get("forecast_margin_usd") or 0
            if r.get("status") == "settled":
                slot["loads_settled"] += 1
                slot["settled_margin_usd"] += r.get("settled_margin_usd") or 0
        for slot in by_board.values():
            if slot["forecast_margin_usd"]:
                slot["win_rate"] = round(slot["settled_margin_usd"] / slot["forecast_margin_usd"] * 100, 1)
            slot["forecast_margin_usd"] = round(slot["forecast_margin_usd"], 2)
            slot["settled_margin_usd"] = round(slot["settled_margin_usd"], 2)
        return {"by_board": list(by_board.values()), "bookings": rows[:50]}

    # ============================ ACCOUNTING ============================
    @router.post("/accounting/invoices")
    async def create_invoice(payload: InvoiceIn, user=Depends(get_current_user)):
        doc = {
            "invoice_id": f"INV-{datetime.now(timezone.utc).strftime('%y%m')}-{uuid.uuid4().hex[:6].upper()}",
            "customer": payload.customer,
            "customer_email": payload.customer_email,
            "load_ref": payload.load_ref,
            "amount_usd": round(payload.amount_usd, 2),
            "balance_usd": round(payload.amount_usd, 2),
            "due_date": payload.due_date,
            "issued_date": datetime.now(timezone.utc).date().isoformat(),
            "status": "open",
            "created_by": user.user_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "synced_to_qb": False,
        }
        await db.brokerage_invoices.insert_one(dict(doc))
        return doc

    @router.get("/accounting/invoices")
    async def list_invoices(_=Depends(get_current_user)):
        rows = await db.brokerage_invoices.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
        return {"invoices": rows}

    @router.post("/accounting/invoices/{invoice_id}/pay")
    async def pay_invoice(invoice_id: str, _=Depends(get_current_user)):
        r = await db.brokerage_invoices.find_one_and_update(
            {"invoice_id": invoice_id, "status": "open"},
            {"$set": {"status": "paid", "balance_usd": 0,
                      "paid_at": datetime.now(timezone.utc).isoformat()}},
            return_document=True, projection={"_id": 0},
        )
        if not r:
            raise HTTPException(404, "Invoice not found or already paid")
        return r

    @router.post("/accounting/expenses")
    async def create_expense(payload: ExpenseIn, user=Depends(get_current_user)):
        doc = {
            "expense_id": f"EXP-{datetime.now(timezone.utc).strftime('%y%m')}-{uuid.uuid4().hex[:6].upper()}",
            "category": payload.category,
            "vendor": payload.vendor,
            "amount_usd": round(payload.amount_usd, 2),
            "paid_date": payload.paid_date,
            "notes": payload.notes,
            "created_by": user.user_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "synced_to_qb": False,
        }
        await db.brokerage_expenses.insert_one(dict(doc))
        return doc

    @router.get("/accounting/expenses")
    async def list_expenses(_=Depends(get_current_user)):
        rows = await db.brokerage_expenses.find({}, {"_id": 0}).sort("paid_date", -1).to_list(500)
        return {"expenses": rows}

    @router.get("/accounting/pnl")
    async def profit_and_loss(_=Depends(get_current_user)):
        """Real-time P&L: revenue (paid invoices) − expenses − carrier pay (settled bookings)."""
        invoices = await db.brokerage_invoices.find({}, {"_id": 0}).to_list(2000)
        expenses = await db.brokerage_expenses.find({}, {"_id": 0}).to_list(2000)
        bookings = await db.brokerage_bookings.find({"status": "settled"}, {"_id": 0}).to_list(2000)

        revenue = sum((i.get("amount_usd") or 0) for i in invoices if i.get("status") == "paid")
        ar_open = sum((i.get("balance_usd") or 0) for i in invoices if i.get("status") == "open")
        opex = sum((e.get("amount_usd") or 0) for e in expenses)
        carrier_pay = sum((b.get("settled_carrier_pay_usd") or 0) for b in bookings)
        gross_margin = revenue - carrier_pay
        net_income = gross_margin - opex

        # Aging buckets
        today = datetime.now(timezone.utc).date()
        aging = {"current": 0, "31_60": 0, "61_90": 0, "over_90": 0}
        for i in invoices:
            if i.get("status") != "open":
                continue
            try:
                due = datetime.fromisoformat(i["due_date"]).date()
            except Exception:
                continue
            days_past = (today - due).days
            amt = i.get("balance_usd") or 0
            if days_past <= 0:           aging["current"] += amt
            elif days_past <= 30:        aging["31_60"] += amt
            elif days_past <= 60:        aging["61_90"] += amt
            else:                        aging["over_90"] += amt
        aging = {k: round(v, 2) for k, v in aging.items()}

        # Expenses by category
        by_cat: Dict[str, float] = {}
        for e in expenses:
            by_cat[e.get("category", "Other")] = by_cat.get(e.get("category", "Other"), 0) + (e.get("amount_usd") or 0)
        expenses_by_category = [{"category": k, "amount": round(v, 2)} for k, v in sorted(by_cat.items(), key=lambda x: -x[1])]

        return {
            "revenue_usd": round(revenue, 2),
            "ar_open_usd": round(ar_open, 2),
            "carrier_pay_usd": round(carrier_pay, 2),
            "gross_margin_usd": round(gross_margin, 2),
            "gross_margin_pct": round((gross_margin / revenue * 100) if revenue else 0, 1),
            "operating_expenses_usd": round(opex, 2),
            "net_income_usd": round(net_income, 2),
            "invoice_count": len(invoices),
            "expense_count": len(expenses),
            "aging": aging,
            "expenses_by_category": expenses_by_category,
        }

    # ============================ QUICKBOOKS HYBRID ============================
    @router.get("/quickbooks/status")
    async def qb_status(_=Depends(get_current_user)):
        cfg = await db.brokerage_qb_config.find_one({"_id": "qb"}, {"_id": 0})
        if not cfg:
            return {"connected": False, "company": None, "last_sync_at": None,
                    "pending_invoices": 0, "pending_expenses": 0}
        pending_inv = await db.brokerage_invoices.count_documents({"synced_to_qb": False})
        pending_exp = await db.brokerage_expenses.count_documents({"synced_to_qb": False})
        return {**cfg, "pending_invoices": pending_inv, "pending_expenses": pending_exp}

    @router.post("/quickbooks/connect")
    async def qb_connect(payload: Dict[str, Any], _=Depends(require_role("admin"))):
        """Mock OAuth: pretend we exchanged a code for tokens. Stores a flag."""
        cfg = {
            "_id": "qb",
            "connected": True,
            "company": (payload or {}).get("company") or "Tennant Brokerage LLC",
            "realm_id": f"qb-{uuid.uuid4().hex[:10]}",
            "connected_at": datetime.now(timezone.utc).isoformat(),
            "last_sync_at": None,
        }
        await db.brokerage_qb_config.update_one({"_id": "qb"}, {"$set": cfg}, upsert=True)
        cfg.pop("_id", None)
        return {"ok": True, **cfg}

    @router.post("/quickbooks/disconnect")
    async def qb_disconnect(_=Depends(require_role("admin"))):
        await db.brokerage_qb_config.delete_one({"_id": "qb"})
        return {"ok": True}

    @router.post("/quickbooks/sync")
    async def qb_sync(_=Depends(require_role("admin"))):
        """Flush all pending invoices + expenses to QB (mocked)."""
        cfg = await db.brokerage_qb_config.find_one({"_id": "qb"})
        if not cfg:
            raise HTTPException(400, "QuickBooks not connected")
        inv_res = await db.brokerage_invoices.update_many({"synced_to_qb": False}, {"$set": {"synced_to_qb": True}})
        exp_res = await db.brokerage_expenses.update_many({"synced_to_qb": False}, {"$set": {"synced_to_qb": True}})
        await db.brokerage_qb_config.update_one(
            {"_id": "qb"},
            {"$set": {"last_sync_at": datetime.now(timezone.utc).isoformat()}},
        )
        return {"ok": True, "synced_invoices": inv_res.modified_count, "synced_expenses": exp_res.modified_count}

    # ============================ FORMS LIBRARY ============================
    @router.get("/forms")
    async def list_forms(_=Depends(get_current_user)):
        return {"forms": COMPLIANCE_FORMS}

    @router.post("/forms/fill")
    async def fill_form(payload: FormFillIn, user=Depends(get_current_user)):
        """Render any form to a PDF. Streams the file straight back."""
        form_meta = next((f for f in COMPLIANCE_FORMS if f["id"] == payload.form_id), None)
        if not form_meta:
            raise HTTPException(404, "Unknown form_id")
        pdf_bytes = _render_form_pdf(form_meta, payload.fields, user)
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{payload.form_id}-{datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")}.pdf"',
            },
        )

    # ============================ AI ASSISTANT ============================
    @router.post("/ai/ask")
    async def ai_ask(payload: BrokerageAIIn, _=Depends(get_current_user)):
        """Brokerage-savvy AI co-pilot. Uses Claude Sonnet 4.5 via Emergent."""
        if not emergent_llm_key:
            raise HTTPException(500, "EMERGENT_LLM_KEY not configured")
        # Build context-rich prompt from current P&L + margins
        pnl_resp = await profit_and_loss()
        margins_resp = await margins()
        system = (
            "You are LEDGER, the AI accountant + freight-brokerage strategist baked into a TMS. "
            "You analyze P&L, margins by load-board, aging A/R, and operational mix. "
            "Be specific, numbers-first, and dispatch-room blunt. Cite the user's actual numbers. "
            "Format with short paragraphs and bullets. Max ~250 words."
        )
        context_block = (
            f"\n=== LIVE NUMBERS ===\n"
            f"Revenue: ${pnl_resp['revenue_usd']:,.0f} · A/R open: ${pnl_resp['ar_open_usd']:,.0f}\n"
            f"Carrier pay: ${pnl_resp['carrier_pay_usd']:,.0f} · Opex: ${pnl_resp['operating_expenses_usd']:,.0f}\n"
            f"Gross margin: ${pnl_resp['gross_margin_usd']:,.0f} ({pnl_resp['gross_margin_pct']}%)\n"
            f"Net income: ${pnl_resp['net_income_usd']:,.0f}\n"
            f"Aging (current/31-60/61-90/90+): "
            f"{pnl_resp['aging']['current']:.0f} / {pnl_resp['aging']['31_60']:.0f} / "
            f"{pnl_resp['aging']['61_90']:.0f} / {pnl_resp['aging']['over_90']:.0f}\n"
            f"\nLoad-board scorecard:\n"
            + "\n".join(
                f"  {b['name']}: {b['loads_booked']} booked, {b['loads_settled']} settled, "
                f"settled-margin ${b['settled_margin_usd']:,.0f} ({b['win_rate']}% of forecast)"
                for b in margins_resp["by_board"]
            )
        )
        user_block = f"USER QUESTION:\n{payload.question}\n{('CONTEXT: ' + payload.context) if payload.context else ''}"
        try:
            chat = LlmChat(
                api_key=emergent_llm_key,
                session_id=f"brokerage-ai-{uuid.uuid4().hex[:8]}",
                system_message=system + context_block,
            ).with_model("anthropic", "claude-sonnet-4-5-20250929")
            reply = await chat.send_message(UserMessage(text=user_block))
            return {"answer": reply, "model": "claude-sonnet-4.5"}
        except Exception as e:
            logger.exception("Brokerage AI failed")
            raise HTTPException(502, f"AI provider error: {e}")

    # ============================ DASHBOARD ROLLUP ============================
    # ============================ BUSINESS PLAN ============================
    @router.get("/business-plan")
    async def business_plan(_=Depends(get_current_user)):
        """Return the freight-brokerage business plan markdown (rendered in the UI tab)."""
        return _read_doc("BROKERAGE_BUSINESS_PLAN.md", "Business plan document not found")

    @router.get("/cost-analysis")
    async def cost_analysis(_=Depends(get_current_user)):
        """Return the real-world operating cost analysis markdown."""
        return _read_doc("COST_ANALYSIS.md", "Cost analysis document not found")

    # ============================ LIVE COST SUMMARY ============================
    @router.get("/cost-summary")
    async def cost_summary(_=Depends(get_current_user)):
        """Live spend snapshot — per-provider monthly cost based on currently-enabled Connections.

        Fixed providers (DAT, Truckstop, RMIS, QB, etc.) contribute their list-rate
        monthly cost. Variable providers (Stripe, factoring, Twilio) show their
        billing model + an MTD estimate derived from real bookings/invoices when
        we have the data.
        """
        # Pull billed booking volume MTD for factoring estimates
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        settled_cursor = db.brokerage_bookings.find(
            {"status": "settled", "booked_at": {"$gte": month_start.isoformat()}},
            {"_id": 0, "settled_carrier_pay_usd": 1},
        )
        settled_carrier_pay_mtd = 0.0
        async for b in settled_cursor:
            settled_carrier_pay_mtd += float(b.get("settled_carrier_pay_usd") or 0)

        # Pull enabled connection records (need .fields for factor_rate, etc.)
        enabled_map: Dict[str, Dict[str, Any]] = {}
        cursor = db.connections.find({"enabled": True}, {"_id": 0})
        async for doc in cursor:
            enabled_map[doc["provider_id"]] = doc

        items: List[Dict[str, Any]] = []
        fixed_total = 0.0
        variable_mtd_estimate = 0.0
        for pid, meta in PROVIDER_COSTS.items():
            conn = enabled_map.get(pid)
            is_enabled = conn is not None
            est_mtd = 0.0
            if is_enabled and meta["model"] == "factoring":
                # Pull factor_rate from connection (non-secret field)
                fields = (conn or {}).get("fields") or {}
                fr_cell = fields.get("factor_rate") or {}
                try:
                    rate_pct = float(fr_cell.get("value")) if isinstance(fr_cell, dict) else 0.0
                except (TypeError, ValueError):
                    rate_pct = 0.0
                if rate_pct <= 0:
                    rate_pct = meta.get("default_rate_pct", 2.5)
                # Assume ~25% of settled book uses factoring quick-pay
                est_mtd = round(settled_carrier_pay_mtd * 0.25 * (rate_pct / 100), 2)
                variable_mtd_estimate += est_mtd
            items.append({
                "provider_id": pid,
                "name": meta["name"],
                "category": meta["category"],
                "plan": meta.get("plan", "—"),
                "model": meta["model"],                  # fixed | variable | factoring
                "monthly_cost_usd": meta.get("monthly_usd", 0),
                "enabled": is_enabled,
                "mtd_estimate_usd": est_mtd,
                "note": meta.get("note"),
            })
            if is_enabled and meta["model"] == "fixed":
                fixed_total += float(meta.get("monthly_usd") or 0)

        items.sort(key=lambda x: (0 if x["enabled"] else 1, x["category"], x["name"]))

        baseline = {
            "app_hosting_usd": 25.0,
            "mongodb_atlas_usd": 57.0,
            "domain_dns_usd": 1.50,
            "llm_universal_key_usd": 25.0,
            "total_usd": 108.50,
            "tier": "Solo (Tier A baseline)",
        }

        return {
            "as_of": now.isoformat(),
            "month_start": month_start.date().isoformat(),
            "settled_carrier_pay_mtd_usd": round(settled_carrier_pay_mtd, 2),
            "baseline": baseline,
            "enabled_count": len(enabled_map),
            "fixed_saas_monthly_usd": round(fixed_total, 2),
            "variable_mtd_estimate_usd": round(variable_mtd_estimate, 2),
            "projected_monthly_total_usd": round(baseline["total_usd"] + fixed_total + variable_mtd_estimate, 2),
            "items": items,
        }

    @router.get("/dashboard")
    async def dashboard(_=Depends(get_current_user)):
        """Single rollup the dashboard tab consumes."""
        pnl_resp = await profit_and_loss()
        margins_resp = await margins()
        match_resp = await ai_match_loads(top=6)
        qb = await qb_status()
        return {
            "pnl": pnl_resp,
            "margins": margins_resp,
            "top_loads": match_resp["loads"],
            "quickbooks": qb,
            "boards_meta": LOAD_BOARDS,
        }

    return router


# ---------- PDF rendering ----------
def _render_form_pdf(form_meta: Dict[str, Any], fields: Dict[str, Any], user: Any) -> bytes:
    """Render a brokerage compliance form to PDF bytes using ReportLab."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter,
                            leftMargin=0.6 * inch, rightMargin=0.6 * inch,
                            topMargin=0.6 * inch, bottomMargin=0.6 * inch,
                            title=form_meta["name"])
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("title", parent=styles["Title"], fontSize=18, leading=22, textColor=colors.HexColor("#0F172A"))
    sub_style = ParagraphStyle("sub", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#475569"))
    h2_style = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=12, leading=16, textColor=colors.HexColor("#0EA5E9"))
    body_style = ParagraphStyle("body", parent=styles["Normal"], fontSize=10, leading=14)

    story: List[Any] = [
        Paragraph(form_meta["name"], title_style),
        Paragraph(
            f"Category: {form_meta['category']}"
            f"{' · FMCSA Required' if form_meta.get('fmcsa') else ''}"
            f" · Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} by {getattr(user, 'name', 'user')}",
            sub_style,
        ),
        Spacer(1, 0.25 * inch),
    ]

    # Field table (key → value or blank line)
    schema = _form_schema(form_meta["id"])
    rows = [["FIELD", "VALUE"]]
    for label, key in schema:
        rows.append([label, str(fields.get(key, "") or "___________________________________")])
    tbl = Table(rows, colWidths=[2.0 * inch, 5.0 * inch])
    tbl.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0EA5E9")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONT", (0, 1), (-1, -1), "Helvetica", 10),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F1F5F9")]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(tbl)

    # Form-specific legal blurb
    story.append(Spacer(1, 0.3 * inch))
    story.append(Paragraph("Acknowledgement & Signature", h2_style))
    story.append(Paragraph(_form_legal_text(form_meta["id"]), body_style))
    story.append(Spacer(1, 0.5 * inch))

    sig_rows = [
        ["Authorized Signature", "Print Name", "Date"],
        ["_____________________________", "_____________________________", "________________"],
    ]
    sig_tbl = Table(sig_rows, colWidths=[2.6 * inch, 2.6 * inch, 1.8 * inch])
    sig_tbl.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, 0), "Helvetica", 8),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#475569")),
        ("FONT", (0, 1), (-1, 1), "Helvetica", 10),
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
    ]))
    story.append(sig_tbl)
    story.append(Spacer(1, 0.35 * inch))
    story.append(Paragraph(
        f"Document ID: BRK-{form_meta['id'].upper()}-{uuid.uuid4().hex[:8]} · "
        f"Generated by the Tennant TMS Brokerage module.",
        sub_style,
    ))

    doc.build(story)
    return buf.getvalue()


def _form_schema(form_id: str) -> List[List[str]]:
    base = [["Carrier / Customer Name", "carrier_name"],
            ["MC #", "mc_number"], ["DOT #", "dot_number"],
            ["Contact Email", "email"], ["Phone", "phone"],
            ["Effective Date", "effective_date"]]
    extras = {
        "rate-conf": [["Load ID", "load_id"], ["Origin", "origin"], ["Destination", "destination"],
                      ["Pickup Date", "pickup_date"], ["Delivery Date", "delivery_date"],
                      ["Equipment", "equipment"], ["Commodity", "commodity"], ["Rate (USD)", "rate_usd"]],
        "load-tender": [["Load ID", "load_id"], ["Pickup", "pickup_address"], ["Delivery", "delivery_address"],
                        ["Weight (lbs)", "weight"], ["Pieces", "pieces"]],
        "carrier-packet": [["Insurance Carrier", "insurance_carrier"],
                           ["Auto Liability $", "auto_liab"], ["Cargo $", "cargo_liab"],
                           ["W-9 TIN", "tin"], ["Factoring NOA?", "factoring"]],
        "customer-invoice": [["Invoice #", "invoice_no"], ["Customer", "customer"],
                             ["Load Ref", "load_ref"], ["Amount Due (USD)", "amount"],
                             ["Due Date", "due_date"], ["Terms", "terms"]],
        "1099-summary": [["Carrier Legal Name", "carrier_legal_name"], ["EIN/TIN", "tin"],
                         ["Total Paid YTD", "total_paid"], ["Tax Year", "tax_year"]],
        "bmc-84": [["Surety Company", "surety"], ["Bond #", "bond_no"],
                   ["Amount", "amount"], ["Effective Date", "effective_date"],
                   ["Expiration Date", "expiration_date"]],
        "boc-3": [["Process Agent", "agent"], ["Agent Address", "agent_address"],
                  ["States Covered", "states_covered"]],
        "factoring": [["Factor", "factor"], ["Account #", "factor_account"],
                      ["Remit-To Address", "remit_to"]],
    }
    return base + extras.get(form_id, [["Reference / Notes", "notes"]])


def _form_legal_text(form_id: str) -> str:
    blurbs = {
        "bmc-84": "This bond is issued in accordance with 49 U.S.C. § 13906 and 49 CFR § 387 to guarantee the financial responsibility of the licensed property broker.",
        "boc-3": "The undersigned hereby designates the process agent named above to receive service of legal process in any proceeding brought against the carrier or broker in any state.",
        "rate-conf": "By signing below, the carrier agrees to transport the freight described above for the agreed rate, in accordance with all applicable broker-carrier terms, insurance, and load-tender requirements.",
        "carrier-packet": "Carrier represents that all information furnished is true and complete and authorizes broker to verify any of the data above with the FMCSA SAFER system or insurance carriers of record.",
        "customer-invoice": "Payment is due per the terms above. Interest at 1.5%/mo accrues on past-due balances. All claims must be submitted in writing within 30 days of invoice date.",
        "factoring": "Pursuant to UCC § 9-406, all payments owed to the carrier under this assignment must be remitted directly to the assigning factor at the address above until written notice of revocation is received.",
    }
    return blurbs.get(
        form_id,
        "The undersigned acknowledges that the information furnished is true and complete to the best of their knowledge and that all applicable regulatory requirements have been satisfied prior to execution.",
    )
