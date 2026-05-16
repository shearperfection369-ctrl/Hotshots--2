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

import asyncio
import base64
import io
import logging
import random
import re
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import resend
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr, Field
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from routes.connections import get_connection_credentials


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


async def _build_cost_summary(db) -> Dict[str, Any]:
    """Compute the live cost-summary payload from the current DB state."""
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    settled_cursor = db.brokerage_bookings.find(
        {"status": "settled", "booked_at": {"$gte": month_start.isoformat()}},
        {"_id": 0, "settled_carrier_pay_usd": 1},
    )
    settled_carrier_pay_mtd = 0.0
    async for b in settled_cursor:
        settled_carrier_pay_mtd += float(b.get("settled_carrier_pay_usd") or 0)

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
        tuner_value: Optional[float] = None
        tuner_label: Optional[str] = None

        if is_enabled:
            fields = (conn or {}).get("fields") or {}

            def _read_num(key: str) -> Optional[float]:
                cell = fields.get(key) or {}
                if not isinstance(cell, dict):
                    return None
                raw = cell.get("value")
                if raw in (None, ""):
                    return None
                try:
                    return float(raw)
                except (TypeError, ValueError):
                    return None

            if meta["model"] == "factoring":
                rate_pct = _read_num("factor_rate") or meta.get("default_rate_pct", 2.5)
                usage_pct = _read_num("quick_pay_usage_pct")
                if usage_pct is None or usage_pct < 0 or usage_pct > 100:
                    usage_pct = 25.0
                tuner_value = usage_pct
                tuner_label = f"{usage_pct:.0f}% quick-pay usage × {rate_pct:.1f}% factor"
                est_mtd = round(settled_carrier_pay_mtd * (usage_pct / 100) * (rate_pct / 100), 2)
                variable_mtd_estimate += est_mtd

            elif pid == "twilio":
                volume = _read_num("monthly_sms_volume") or 5000.0
                tuner_value = volume
                tuner_label = f"{int(volume):,} SMS/mo × $0.0083"
                est_mtd = round(volume * 0.0083, 2)
                variable_mtd_estimate += est_mtd

        items.append({
            "provider_id": pid,
            "name": meta["name"],
            "category": meta["category"],
            "plan": meta.get("plan", "—"),
            "model": meta["model"],
            "monthly_cost_usd": meta.get("monthly_usd", 0),
            "enabled": is_enabled,
            "mtd_estimate_usd": est_mtd,
            "tuner_value": tuner_value,
            "tuner_label": tuner_label,
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


async def _persist_snapshot(db, summary: Dict[str, Any], *, force: bool = False) -> None:
    """Upsert a daily cost snapshot keyed on UTC date.

    If `force=False` (the default), we only persist if the row doesn't already
    exist for today — this lets the endpoint be hit every minute on the UI
    without spamming writes. `force=True` overwrites the row.
    """
    today = datetime.now(timezone.utc).date().isoformat()
    payload = {
        "date": today,
        "taken_at": summary["as_of"],
        "projected_monthly_total_usd": summary["projected_monthly_total_usd"],
        "fixed_saas_monthly_usd": summary["fixed_saas_monthly_usd"],
        "variable_mtd_estimate_usd": summary["variable_mtd_estimate_usd"],
        "baseline_usd": summary["baseline"]["total_usd"],
        "enabled_count": summary["enabled_count"],
        "settled_carrier_pay_mtd_usd": summary["settled_carrier_pay_mtd_usd"],
    }
    if force:
        await db.cost_snapshots.update_one({"date": today}, {"$set": payload}, upsert=True)
    else:
        await db.cost_snapshots.update_one(
            {"date": today},
            {"$setOnInsert": payload},
            upsert=True,
        )


def _is_expiring_soon(iso_date: Optional[str], within_days: int = 45) -> bool:
    """Return True if `iso_date` (YYYY-MM-DD) is within `within_days` of today."""
    if not iso_date or not isinstance(iso_date, str):
        return False
    try:
        d = datetime.strptime(iso_date[:10], "%Y-%m-%d").date()
    except ValueError:
        return False
    delta = (d - datetime.now(timezone.utc).date()).days
    return -30 <= delta <= within_days




async def _active_brand(db) -> Dict[str, Any]:
    """Return the currently-active company brand profile (without _id)."""
    doc = await db.company_brand.find_one({"is_active": True}, {"_id": 0})
    if doc:
        return doc
    return {
        "company_name": "Orisei Freight Solutions LLC",
        "tagline": "Operator-built freight brokerage · Minneapolis · Saint Paul",
        "primary_color": "#22D3EE",
        "owner_name": "Oliver Cummins",
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

    contact_first = ["Maria", "James", "Sara", "David", "Linda", "Carlos", "Priya", "Mike", "Janet", "Aiden"]
    contact_last  = ["Lopez", "Chen", "Patel", "Johnson", "Schmidt", "Nguyen", "Olson", "Rivera", "Brooks", "Wong"]
    street_words  = ["Industrial", "Commerce", "Logistics", "Distribution", "Gateway", "Freight", "Hub", "Service"]

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

        # Enriched detail fields
        is_reefer = eq == "Reefer"
        is_flat   = eq in ("Flatbed", "Step Deck")
        length_ft = 53 if eq in ("Van", "Reefer") else (rnd.choice([48, 53]) if is_flat else 53)
        pallet_count = rnd.randint(18, 26) if not is_flat else 0
        temp_f       = rnd.choice([-10, 0, 34, 38, 50]) if is_reefer else None
        hazmat       = rnd.random() < 0.08
        team         = rnd.random() < 0.12 and miles > 900
        tarp         = is_flat and rnd.random() < 0.55
        driver_assist = rnd.random() < 0.3
        appt_required = rnd.random() < 0.7
        shipper_first = rnd.choice(contact_first); shipper_last = rnd.choice(contact_last)
        consignee_first = rnd.choice(contact_first); consignee_last = rnd.choice(contact_last)
        pickup_street = f"{rnd.randint(100, 9999)} {rnd.choice(street_words)} {rnd.choice(['Pkwy', 'Blvd', 'Way', 'Dr'])}"
        delivery_street = f"{rnd.randint(100, 9999)} {rnd.choice(street_words)} {rnd.choice(['Pkwy', 'Blvd', 'Way', 'Dr'])}"

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
            # ----- enriched detail -----
            "pickup_full_address":    f"{shipper} · {pickup_street}, {origin}",
            "delivery_full_address":  f"Consignee · {delivery_street}, {dest}",
            "pickup_window_start":    f"{rnd.choice(['06:00', '07:00', '08:00', '09:00', '10:00'])}",
            "pickup_window_end":      f"{rnd.choice(['11:00', '13:00', '15:00', '17:00'])}",
            "delivery_window_start":  f"{rnd.choice(['07:00', '08:00', '10:00', '13:00'])}",
            "delivery_window_end":    f"{rnd.choice(['12:00', '15:00', '17:00', '19:00'])}",
            "appointment_required":   appt_required,
            "length_ft":              length_ft,
            "width_ft":               8 if not is_flat else rnd.choice([8.5, 10, 12]),
            "height_ft":              13.5 if not is_flat else rnd.choice([8, 10, 13]),
            "pallet_count":           pallet_count,
            "temperature_f":          temp_f,
            "hazmat":                 hazmat,
            "team_required":          team,
            "tarp_required":          tarp,
            "driver_assist_required": driver_assist,
            "shipper_contact_name":   f"{shipper_first} {shipper_last}",
            "shipper_phone":          f"({rnd.randint(200, 989)}) {rnd.randint(200, 989)}-{rnd.randint(1000, 9999)}",
            "shipper_email":          f"{shipper_first.lower()}.{shipper_last.lower()}@{shipper.lower().replace(' ', '').replace('.', '')}.com",
            "consignee_name":         f"{consignee_first} {consignee_last}",
            "consignee_phone":        f"({rnd.randint(200, 989)}) {rnd.randint(200, 989)}-{rnd.randint(1000, 9999)}",
            "special_instructions":   _gen_special_instructions(rnd, hazmat, tarp, team, appt_required, is_reefer, temp_f),
            "broker_reference":       f"ORI-{rnd.randint(10000, 99999)}",
            "load_type":              "TL · partial" if rate < 1200 else "TL · full truckload",
            "stop_count":              rnd.choice([1, 1, 1, 2]) if not is_flat else 1,
        })
    out.sort(key=lambda x: -x["ai_score"])
    return out


def _gen_special_instructions(rnd: random.Random, hazmat: bool, tarp: bool, team: bool, appt: bool,
                              is_reefer: bool, temp_f: Optional[int]) -> str:
    parts: List[str] = []
    if appt: parts.append("Appointment required at both ends; arrive 15 min early.")
    if is_reefer and temp_f is not None: parts.append(f"Continuous reefer — maintain {temp_f}°F · download temp logs at delivery.")
    if hazmat:                            parts.append("HAZMAT — placards required; current HM-181 endorsement mandatory.")
    if tarp:                              parts.append("Tarping required (6-ft minimum) — provide proof-of-tarp photo.")
    if team:                              parts.append("Team service required — no relay drops permitted.")
    if rnd.random() < 0.4:                parts.append("No idling at facility · driver must remain with vehicle during loading.")
    return " ".join(parts) or "Standard tender · no special handling."


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
    driver_id: Optional[str] = None
    notes: Optional[str] = None


class DriverIn(BaseModel):
    name: str = Field(..., min_length=2, max_length=80)
    cdl_number: Optional[str] = Field(None, max_length=40)
    cdl_state: Optional[str] = Field(None, max_length=2)
    cdl_expires: Optional[str] = Field(None, max_length=10)         # YYYY-MM-DD
    medcard_expires: Optional[str] = Field(None, max_length=10)
    phone: Optional[str] = Field(None, max_length=30)
    email: Optional[str] = Field(None, max_length=120)
    carrier_name: Optional[str] = Field(None, max_length=80)
    carrier_mc: Optional[str] = Field(None, max_length=20)
    equipment_type: Optional[str] = Field(None, max_length=30)
    current_city: Optional[str] = Field(None, max_length=60)
    current_state: Optional[str] = Field(None, max_length=2)
    status: Optional[str] = Field("available", max_length=20)        # available | dispatched | off_duty | terminated
    hos_drive_remaining_hours: Optional[float] = Field(None, ge=0, le=11)
    hire_date: Optional[str] = Field(None, max_length=10)
    notes: Optional[str] = Field(None, max_length=1000)


class DriverAssignIn(BaseModel):
    load_id: str
    board_id: Optional[str] = None
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


class InvestorPitchIn(BaseModel):
    to_email: EmailStr
    to_name: Optional[str] = Field(None, max_length=120)
    subject: Optional[str] = Field(None, max_length=200)
    personal_note: Optional[str] = Field(None, max_length=2000)
    founder_name: Optional[str] = Field(None, max_length=120)
    linkedin_url: Optional[str] = Field(None, max_length=300)
    reply_to: Optional[EmailStr] = None
    attach_pdf: bool = True
    dry_run: bool = False                       # Render but don't send


# ---------- PDF helpers ----------
def _markdown_to_pdf_bytes(md_text: str, title: str = "Business Plan") -> bytes:
    """Render a freight-brokerage markdown document to a clean reportlab PDF.

    Honors headings (#, ##, ###), bold/italic, bullet/numbered lists, and
    pipe-tables. Output is intentionally minimal — designed to look professional
    on an investor's iPad without battling email-client renderers.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, leftMargin=0.7*inch, rightMargin=0.7*inch, topMargin=0.7*inch, bottomMargin=0.7*inch, title=title)
    base = getSampleStyleSheet()
    styles = {
        "h1":  ParagraphStyle("h1",  parent=base["Heading1"], fontSize=22, leading=26, textColor=colors.HexColor("#0F172A"), spaceAfter=10),
        "h2":  ParagraphStyle("h2",  parent=base["Heading2"], fontSize=15, leading=19, textColor=colors.HexColor("#0E7490"), spaceBefore=14, spaceAfter=6),
        "h3":  ParagraphStyle("h3",  parent=base["Heading3"], fontSize=12, leading=16, textColor=colors.HexColor("#0F172A"), spaceBefore=8, spaceAfter=4),
        "p":   ParagraphStyle("p",   parent=base["BodyText"], fontSize=9.5, leading=13, textColor=colors.HexColor("#1F2937"), spaceAfter=4),
        "li":  ParagraphStyle("li",  parent=base["BodyText"], fontSize=9.5, leading=13, leftIndent=14, bulletIndent=2, textColor=colors.HexColor("#1F2937"), spaceAfter=2),
        "quo": ParagraphStyle("quo", parent=base["BodyText"], fontSize=9.5, leading=13, leftIndent=14, textColor=colors.HexColor("#475569"), italic=True, spaceAfter=4),
    }
    story: List[Any] = []

    def _inline(text: str) -> str:
        # Markdown bold/italic/code → minimal reportlab HTML
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
        text = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<i>\1</i>", text)
        text = re.sub(r"`([^`]+?)`", r'<font face="Courier">\1</font>', text)
        # Escape leftover & / < / > that could confuse reportlab. (Order matters.)
        text = text.replace("&", "&amp;").replace("<b>", "\x00b\x00").replace("</b>", "\x00B\x00").replace("<i>", "\x00i\x00").replace("</i>", "\x00I\x00")
        text = text.replace("<", "&lt;").replace(">", "&gt;")
        text = text.replace("\x00b\x00", "<b>").replace("\x00B\x00", "</b>").replace("\x00i\x00", "<i>").replace("\x00I\x00", "</i>")
        return text

    lines = md_text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        stripped = line.strip()
        # Skip horizontal rules and stray separators
        if not stripped or re.fullmatch(r"-{3,}|={3,}|\*{3,}", stripped):
            story.append(Spacer(1, 4)); i += 1; continue
        # Tables — skip the rendering (would blow up PDF length); leave a hint
        if "|" in stripped and i + 1 < len(lines) and re.match(r"\|?\s*[:-]+\s*\|", lines[i+1]):
            j = i
            while j < len(lines) and lines[j].strip().startswith("|"):
                j += 1
            story.append(Paragraph("<i>[Table omitted — see full plan online]</i>", styles["quo"]))
            i = j; continue
        # Headings
        if stripped.startswith("### "):
            story.append(Paragraph(_inline(stripped[4:]), styles["h3"])); i += 1; continue
        if stripped.startswith("## "):
            story.append(Paragraph(_inline(stripped[3:]), styles["h2"])); i += 1; continue
        if stripped.startswith("# "):
            story.append(Paragraph(_inline(stripped[2:]), styles["h1"])); i += 1; continue
        # Blockquote
        if stripped.startswith("> "):
            story.append(Paragraph(_inline(stripped[2:]), styles["quo"])); i += 1; continue
        # Bullets
        m = re.match(r"^[-*+]\s+(.+)$", stripped)
        if m:
            story.append(Paragraph(_inline(m.group(1)), styles["li"], bulletText="•"))
            i += 1; continue
        # Numbered lists
        m = re.match(r"^(\d+)\.\s+(.+)$", stripped)
        if m:
            story.append(Paragraph(_inline(m.group(2)), styles["li"], bulletText=f"{m.group(1)}."))
            i += 1; continue
        # Paragraph
        story.append(Paragraph(_inline(stripped), styles["p"]))
        i += 1
    doc.build(story)
    return buf.getvalue()


def _build_investor_email_html(*, brand: Dict[str, Any], to_name: Optional[str], founder_name: str,
                               linkedin_url: Optional[str], personal_note: Optional[str]) -> str:
    """Render the investor outreach email body. Inline-CSS, table-layout — email-client safe."""
    company = brand.get("company_name") or "Orisei Freight Solutions LLC"
    tagline = brand.get("tagline") or "Operator-built freight brokerage · Minneapolis · Saint Paul"
    accent  = brand.get("primary_color") or "#22D3EE"
    greeting = f"Hi {to_name}," if to_name else "Hello,"
    note_block = f"""
      <tr><td style="padding:0 0 14px 0;color:#334155;font-size:14px;line-height:1.55;">
        {personal_note}
      </td></tr>
    """ if personal_note else ""
    linkedin_btn = f"""
      <a href="{linkedin_url}" style="display:inline-block;padding:10px 16px;border-radius:6px;background:#0A66C2;color:#ffffff;text-decoration:none;font-weight:600;font-size:13px;margin-right:8px;">
        Connect on LinkedIn &rarr;
      </a>
    """ if linkedin_url else ""
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8" /></head>
<body style="margin:0;padding:0;background:#F1F5F9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;color:#0F172A;">
  <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background:#F1F5F9;padding:24px 0;">
    <tr><td align="center">
      <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="600" style="background:#ffffff;border-radius:10px;overflow:hidden;box-shadow:0 4px 12px rgba(15,23,42,0.06);">
        <tr><td style="padding:24px 28px;border-bottom:3px solid {accent};">
          <div style="font-family:'Inter',-apple-system,Helvetica,Arial,sans-serif;font-weight:800;font-size:22px;letter-spacing:-0.01em;color:#0F172A;">{company}</div>
          <div style="font-size:12px;color:#64748B;margin-top:2px;">{tagline}</div>
        </td></tr>

        <tr><td style="padding:22px 28px 6px 28px;">
          <div style="font-size:14px;color:#0F172A;margin-bottom:14px;">{greeting}</div>
          <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
            {note_block}
            <tr><td style="padding:0 0 14px 0;color:#334155;font-size:14px;line-height:1.55;">
              I'm <strong>{founder_name}</strong>, founder of <strong>{company}</strong> — a Twin Cities-based property freight brokerage built around an operator-grade in-house TMS. I'm reaching out because I'd value 15 minutes to share my launch plan and explore where we might be useful to each other.
            </td></tr>
            <tr><td style="padding:0 0 14px 0;color:#334155;font-size:14px;line-height:1.55;">
              The attached <strong>business plan</strong> covers the founder background, market thesis, 3-year financial projections (bootstrap baseline ~$432K → $1.9M revenue), regulatory roadmap (MC authority · BMC-84 · BOC-3), and the step-by-step entry plan I'm executing through Q1.
            </td></tr>
          </table>
        </td></tr>

        <tr><td style="padding:6px 28px 22px 28px;">
          <table role="presentation" cellspacing="0" cellpadding="0" border="0">
            <tr><td>
              {linkedin_btn}
            </td></tr>
          </table>
        </td></tr>

        <tr><td style="padding:18px 28px;border-top:1px solid #E2E8F0;background:#F8FAFC;font-size:12px;color:#64748B;line-height:1.5;">
          <div><strong style="color:#0F172A;">{founder_name}</strong> · Founder &amp; Principal Broker</div>
          <div>{company} · Minneapolis &middot; Saint Paul, MN</div>
          {f'<div><a href="{linkedin_url}" style="color:#0A66C2;text-decoration:none;">LinkedIn profile</a></div>' if linkedin_url else ""}
        </td></tr>

        <tr><td style="padding:14px 28px;background:#0F172A;color:#94A3B8;font-size:11px;line-height:1.5;">
          You received this message because {founder_name} identified you as a potential partner or investor. Reply directly to opt out or to schedule a 15-minute intro call.
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>"""


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

    @router.get("/boards/{board_id}/loads/{load_id}")
    async def board_load_detail(board_id: str, load_id: str, _=Depends(get_current_user)):
        """Return the FULL detail for a single load — dimensions, contacts, special instructions."""
        rows = _gen_loads_for_board(board_id)
        load = next((r for r in rows if r["load_id"] == load_id), None)
        if not load:
            # Also check across boards in case the user navigated via the AI match list.
            for b in LOAD_BOARDS:
                if b["id"] == board_id:
                    continue
                cand = next((r for r in _gen_loads_for_board(b["id"]) if r["load_id"] == load_id), None)
                if cand:
                    load = cand
                    break
        if not load:
            raise HTTPException(404, "Load not found")

        # Booking status (if a broker has already booked this load)
        booking = await db.brokerage_bookings.find_one({"load_id": load_id}, {"_id": 0})
        # Assigned driver (if any)
        assigned_driver = None
        if booking:
            assigned_driver = await db.brokerage_drivers.find_one(
                {"current_load_id": load_id},
                {"_id": 0, "cdl_number": 0, "email": 0},   # don't ship the secret driver PII back unnecessarily
            )
        return {"load": load, "booking": booking, "assigned_driver": assigned_driver}

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

    # ============================ DRIVER ROSTER ============================
    @router.get("/drivers")
    async def list_drivers(status: Optional[str] = None, _=Depends(get_current_user)):
        q: Dict[str, Any] = {}
        if status: q["status"] = status
        rows = await db.brokerage_drivers.find(q, {"_id": 0}).sort("name", 1).to_list(500)
        kpi = {
            "total":      len(rows),
            "available":  sum(1 for r in rows if r.get("status") == "available"),
            "dispatched": sum(1 for r in rows if r.get("status") == "dispatched"),
            "off_duty":   sum(1 for r in rows if r.get("status") == "off_duty"),
            "expiring_soon": sum(1 for r in rows if _is_expiring_soon(r.get("cdl_expires")) or _is_expiring_soon(r.get("medcard_expires"))),
        }
        return {"drivers": rows, "kpi": kpi}

    @router.post("/drivers")
    async def create_driver(payload: DriverIn, user=Depends(get_current_user)):
        doc = {
            "id": f"DRV-{uuid.uuid4().hex[:10].upper()}",
            **payload.model_dump(exclude_none=False),
            "current_load_id": None,
            "performance_score": 95.0,
            "on_time_pct": 98.0,
            "loads_completed": 0,
            "miles_ytd": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": getattr(user, "user_id", None),
        }
        await db.brokerage_drivers.insert_one(dict(doc))
        doc.pop("_id", None)
        return doc

    @router.put("/drivers/{driver_id}")
    async def update_driver(driver_id: str, payload: DriverIn, _=Depends(get_current_user)):
        r = await db.brokerage_drivers.find_one_and_update(
            {"id": driver_id},
            {"$set": payload.model_dump(exclude_none=True)},
            return_document=True, projection={"_id": 0},
        )
        if not r:
            raise HTTPException(404, "Driver not found")
        return r

    @router.delete("/drivers/{driver_id}")
    async def delete_driver(driver_id: str, _=Depends(get_current_user)):
        res = await db.brokerage_drivers.delete_one({"id": driver_id})
        if not res.deleted_count:
            raise HTTPException(404, "Driver not found")
        return {"deleted": True, "id": driver_id}

    @router.post("/drivers/{driver_id}/assign")
    async def assign_driver(driver_id: str, payload: DriverAssignIn, _=Depends(get_current_user)):
        driver = await db.brokerage_drivers.find_one({"id": driver_id}, {"_id": 0})
        if not driver:
            raise HTTPException(404, "Driver not found")
        r = await db.brokerage_drivers.find_one_and_update(
            {"id": driver_id},
            {"$set": {
                "current_load_id": payload.load_id,
                "status": "dispatched",
                "last_assignment_at": datetime.now(timezone.utc).isoformat(),
                "last_assignment_notes": payload.notes,
            }},
            return_document=True, projection={"_id": 0},
        )
        return {"ok": True, "driver": r}

    @router.post("/drivers/{driver_id}/clear")
    async def clear_driver(driver_id: str, _=Depends(get_current_user)):
        r = await db.brokerage_drivers.find_one_and_update(
            {"id": driver_id},
            {"$set": {"current_load_id": None, "status": "available"}, "$inc": {"loads_completed": 1}},
            return_document=True, projection={"_id": 0},
        )
        if not r:
            raise HTTPException(404, "Driver not found")
        return r

    # ============================ FACTORING NETWORK STATUS ============================
    @router.get("/factoring/status")
    async def factoring_status(_=Depends(get_current_user)):
        """Aggregate of enabled factoring connections + MTD spend + simulated activity."""
        rows: List[Dict[str, Any]] = []
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        settled = 0.0
        async for b in db.brokerage_bookings.find(
            {"status": "settled", "booked_at": {"$gte": month_start.isoformat()}},
            {"_id": 0, "settled_carrier_pay_usd": 1},
        ):
            settled += float(b.get("settled_carrier_pay_usd") or 0)

        async for c in db.connections.find({"enabled": True}, {"_id": 0}):
            pid = c.get("provider_id")
            meta = PROVIDER_COSTS.get(pid)
            if not meta or meta.get("model") != "factoring":
                continue
            fields = c.get("fields") or {}
            def _read(k):
                cell = fields.get(k) or {}
                return cell.get("value") if isinstance(cell, dict) else None
            try:    rate_pct = float(_read("factor_rate") or meta.get("default_rate_pct", 2.5))
            except (TypeError, ValueError): rate_pct = float(meta.get("default_rate_pct", 2.5))
            try:    usage_pct = float(_read("quick_pay_usage_pct") or 25.0)
            except (TypeError, ValueError): usage_pct = 25.0
            mtd_spend = round(settled * (usage_pct / 100) * (rate_pct / 100), 2)
            factored_carrier_pay = round(settled * (usage_pct / 100), 2)
            rnd = random.Random(f"fact::{pid}::{now.date().isoformat()}")
            rows.append({
                "provider_id": pid,
                "name": meta["name"],
                "factor_rate_pct": rate_pct,
                "quick_pay_usage_pct": usage_pct,
                "monthly_carrier_pay_mtd_usd": factored_carrier_pay,
                "monthly_fee_mtd_usd": mtd_spend,
                "carriers_verified_30d": rnd.randint(8, 42),
                "noa_letters_processed_mtd": rnd.randint(3, 22),
                "quick_pay_advances_mtd": rnd.randint(2, 18),
                "next_ach_in_days": rnd.choice([1, 1, 2, 3]),
                "last_sync_at": (now - timedelta(minutes=rnd.randint(5, 90))).isoformat(),
                "status": "connected",
                "tuner_label": f"{usage_pct:.0f}% quick-pay × {rate_pct:.1f}% factor",
            })
        rows.sort(key=lambda x: x["name"])
        totals = {
            "providers": len(rows),
            "monthly_fee_mtd_usd": round(sum(r["monthly_fee_mtd_usd"] for r in rows), 2),
            "factored_carrier_pay_mtd_usd": round(sum(r["monthly_carrier_pay_mtd_usd"] for r in rows), 2),
            "noa_letters_mtd": sum(r["noa_letters_processed_mtd"] for r in rows),
            "quick_pay_advances_mtd": sum(r["quick_pay_advances_mtd"] for r in rows),
        }
        return {"providers": rows, "totals": totals}



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

    @router.get("/home-office-setup")
    async def home_office_setup(_=Depends(get_current_user)):
        """Return the step-by-step home-office self-hosting plan markdown."""
        return _read_doc("HOME_OFFICE_SETUP.md", "Home office setup document not found")

    # ============================ INVESTOR OUTREACH ============================
    @router.post("/investor-pitch/preview")
    async def investor_pitch_preview(payload: InvestorPitchIn, _=Depends(get_current_user)):
        """Render the email HTML + (optional) PDF size, WITHOUT sending."""
        brand = await _active_brand(db)
        founder = payload.founder_name or brand.get("owner_name") or "Oliver Cummins"
        html = _build_investor_email_html(
            brand=brand, to_name=payload.to_name, founder_name=founder,
            linkedin_url=payload.linkedin_url, personal_note=payload.personal_note,
        )
        out: Dict[str, Any] = {
            "subject": payload.subject or f"{brand.get('company_name', 'Orisei Freight Solutions LLC')} · Business Plan & Founder Introduction",
            "html": html,
            "preview_text": (payload.personal_note or "")[:120],
            "attach_pdf": payload.attach_pdf,
        }
        if payload.attach_pdf:
            doc = _read_doc("BROKERAGE_BUSINESS_PLAN.md", "Business plan document not found")
            pdf_bytes = _markdown_to_pdf_bytes(doc["markdown"], title=brand.get("company_name", "Business Plan"))
            out["pdf_size_kb"] = round(len(pdf_bytes) / 1024, 1)
        return out

    @router.post("/investor-pitch")
    async def investor_pitch_send(payload: InvestorPitchIn, user=Depends(get_current_user)):
        """Send the investor pitch via Resend (credentials pulled from Connections vault)."""
        brand = await _active_brand(db)
        founder = payload.founder_name or brand.get("owner_name") or "Oliver Cummins"
        company = brand.get("company_name") or "Orisei Freight Solutions LLC"
        subject = payload.subject or f"{company} · Business Plan & Founder Introduction"

        html = _build_investor_email_html(
            brand=brand, to_name=payload.to_name, founder_name=founder,
            linkedin_url=payload.linkedin_url, personal_note=payload.personal_note,
        )

        attachments: List[Dict[str, str]] = []
        pdf_size_kb = 0.0
        if payload.attach_pdf:
            doc = _read_doc("BROKERAGE_BUSINESS_PLAN.md", "Business plan document not found")
            pdf_bytes = _markdown_to_pdf_bytes(doc["markdown"], title=company)
            pdf_size_kb = round(len(pdf_bytes) / 1024, 1)
            attachments.append({
                "filename": f"{company.replace(' ', '_')}_Business_Plan.pdf",
                "content":  base64.b64encode(pdf_bytes).decode("ascii"),
            })

        creds = await get_connection_credentials(db, "resend")
        outreach_record: Dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "sent_by": getattr(user, "user_id", None),
            "sent_by_email": getattr(user, "email", None),
            "to_email": str(payload.to_email),
            "to_name": payload.to_name,
            "subject": subject,
            "founder_name": founder,
            "linkedin_url": payload.linkedin_url,
            "personal_note": payload.personal_note,
            "pdf_attached": bool(attachments),
            "pdf_size_kb": pdf_size_kb,
            "status": "queued",
            "provider": "resend" if creds else "not_configured",
            "dry_run": payload.dry_run,
            "company_name": company,
        }

        # Dry run: just record & return
        if payload.dry_run:
            outreach_record["status"] = "dry_run"
            await db.investor_outreach.insert_one(dict(outreach_record))
            outreach_record.pop("_id", None)
            return {"ok": True, "dry_run": True, **outreach_record}

        if not creds or not creds.get("api_key"):
            outreach_record["status"] = "blocked"
            outreach_record["error"] = "Resend connection not configured. Open Connections · Keys and enable Resend."
            await db.investor_outreach.insert_one(dict(outreach_record))
            raise HTTPException(400, outreach_record["error"])

        from_email = creds.get("from_email") or "onboarding@resend.dev"
        from_display = f"{founder} <{from_email}>"
        params = {
            "from": from_display,
            "to": [str(payload.to_email)],
            "subject": subject,
            "html": html,
            "attachments": attachments,
        }
        if payload.reply_to:
            params["reply_to"] = [str(payload.reply_to)]

        try:
            resend.api_key = creds["api_key"]
            result = await asyncio.to_thread(resend.Emails.send, params)
            outreach_record["status"] = "sent"
            outreach_record["provider_message_id"] = result.get("id") if isinstance(result, dict) else None
        except Exception as exc:
            logger.exception("investor_pitch_send failed")
            outreach_record["status"] = "failed"
            outreach_record["error"] = str(exc)[:400]
            await db.investor_outreach.insert_one(dict(outreach_record))
            raise HTTPException(502, f"Resend failed: {exc}")

        await db.investor_outreach.insert_one(dict(outreach_record))
        outreach_record.pop("_id", None)
        return {"ok": True, **outreach_record}

    @router.get("/investor-outreach")
    async def investor_outreach_list(limit: int = 50, _=Depends(get_current_user)):
        """Recent investor pitch history (newest first)."""
        limit = max(1, min(int(limit or 50), 500))
        cursor = db.investor_outreach.find({}, {"_id": 0, "personal_note": 0}).sort("sent_at", -1).limit(limit)
        out: List[Dict[str, Any]] = []
        async for r in cursor:
            out.append(r)
        return {"count": len(out), "items": out}

    # ============================ LIVE COST SUMMARY ============================
    @router.get("/cost-summary")
    async def cost_summary(_=Depends(get_current_user)):
        """Live spend snapshot — per-provider monthly cost based on currently-enabled Connections.

        Every successful call also persists today's snapshot into the
        `cost_snapshots` collection (one upsert per UTC date) so the Cost tab
        can render a 30-day trend sparkline without us standing up a cron job.
        """
        summary = await _build_cost_summary(db)
        # Best-effort daily persistence — never fail the endpoint on a DB write error.
        try:
            await _persist_snapshot(db, summary)
        except Exception:                                          # pragma: no cover
            logger.exception("cost_summary: snapshot persist failed")
        return summary

    @router.post("/cost-summary/snapshot")
    async def force_snapshot(_=Depends(get_current_user)):
        """Manual snapshot trigger — overwrites today's record."""
        summary = await _build_cost_summary(db)
        await _persist_snapshot(db, summary, force=True)
        return {"ok": True, "date": summary["month_start"], "projected_monthly_total_usd": summary["projected_monthly_total_usd"]}

    @router.get("/cost-history")
    async def cost_history(days: int = 30, _=Depends(get_current_user)):
        """Return up to `days` of daily cost snapshots (oldest → newest)."""
        days = max(1, min(int(days or 30), 365))
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
        cursor = db.cost_snapshots.find(
            {"date": {"$gte": cutoff}},
            {"_id": 0},
        ).sort("date", 1)
        snapshots: List[Dict[str, Any]] = []
        async for s in cursor:
            snapshots.append(s)
        return {"days": days, "count": len(snapshots), "snapshots": snapshots}

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
