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
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, EmailStr, Field
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from routes.connections import get_connection_credentials
from routes.loadboard_adapters import try_fetch_live
from routes.orisei_docs import (
    build_bol_pdf, build_branded_markdown_pdf, build_form_pdf, build_pod_pdf,
)


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
    # Optional customer-facing fields (surface on tracking + workflow)
    customer_name: Optional[str] = Field(None, max_length=200)
    customer_email: Optional[EmailStr] = None
    # OVERRIDES — pass when booking a load NOT from the synthetic board
    # (e.g. a real shipper-tender that was manually entered). Any field
    # provided here overwrites the value from the synthetic feed.
    override_origin: Optional[str] = Field(None, max_length=200)
    override_destination: Optional[str] = Field(None, max_length=200)
    override_miles: Optional[float] = Field(None, ge=0)
    override_equipment: Optional[str] = Field(None, max_length=40)
    override_rate_usd: Optional[float] = Field(None, ge=0)
    override_carrier_pay_usd: Optional[float] = Field(None, ge=0)
    override_pickup_date: Optional[str] = Field(None, max_length=32)
    override_delivery_date: Optional[str] = Field(None, max_length=32)


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


class CustomerInfoIn(BaseModel):
    """Customer info attached to a booked load — used as POD email recipient."""
    customer_name: str = Field(..., min_length=1, max_length=120)
    customer_contact: Optional[str] = Field(None, max_length=120)
    customer_email: Optional[EmailStr] = None
    customer_phone: Optional[str] = Field(None, max_length=40)
    consignee_address: Optional[str] = Field(None, max_length=200)
    shipper_name: Optional[str] = Field(None, max_length=120)
    shipper_address: Optional[str] = Field(None, max_length=200)


# Manual check-call lifecycle for in-transit loads. Operator logs one of
# these statuses each time a driver phones in or pings via the driver app.
CHECK_CALL_STATUSES = [
    "DISPATCHED", "AT_SHIPPER", "LOADED", "IN_TRANSIT",
    "AT_RECEIVER", "UNLOADED", "DELIVERED", "EXCEPTION",
]


class CheckCallIn(BaseModel):
    """Single dispatcher / driver check-call event."""
    status: str = Field(..., description="One of CHECK_CALL_STATUSES")
    location: Optional[str] = Field(None, max_length=200)
    miles_remaining: Optional[float] = Field(None, ge=0)
    eta_iso: Optional[str] = None
    driver_name: Optional[str] = Field(None, max_length=120)
    notes: Optional[str] = Field(None, max_length=1000)


class PodDeliveryIn(BaseModel):
    """Delivery details captured at the dock for POD generation."""
    delivered_at: Optional[str] = Field(None, max_length=40)         # ISO or human string
    received_by: Optional[str] = Field(None, max_length=120)
    driver_name: Optional[str] = Field(None, max_length=120)
    pieces_received: Optional[str] = Field(None, max_length=20)
    weight_received: Optional[str] = Field(None, max_length=40)
    condition: Optional[str] = Field(None, max_length=600)
    exceptions: Optional[List[str]] = None
    seal_intact: bool = True


class PodEmailIn(BaseModel):
    to_email: EmailStr
    to_name: Optional[str] = Field(None, max_length=120)
    cc_email: Optional[EmailStr] = None
    subject: Optional[str] = Field(None, max_length=200)
    message: Optional[str] = Field(None, max_length=2000)
    delivery: Optional[PodDeliveryIn] = None
    dry_run: bool = False



# ---------- PDF helpers ----------
def _markdown_to_pdf_bytes(md_text: str, title: str = "Business Plan",
                            brand: Optional[Dict[str, Any]] = None) -> bytes:
    """Render brokerage markdown docs (business plan, cost analysis, home-office,
    VC pitch) using the active brand's heraldic template."""
    return build_branded_markdown_pdf(md_text, title=title,
                                      subtitle="Founder Business Plan · Confidential",
                                      brand=brand)


def _legacy_markdown_to_pdf_unused(md_text: str, title: str = "Business Plan") -> bytes:
    """Deprecated cyan markdown renderer — preserved for reference, no callers."""
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
class PlanReviewAckIn(BaseModel):
    partner: str = Field(..., min_length=2, max_length=60)
    decision: str = Field("approved", pattern="^(approved|changes_requested)$")
    note: str = Field("", max_length=500)


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
        # Try live adapter first if API keys are configured in the Connections vault.
        live_source: Optional[str] = None
        rows: List[Dict[str, Any]] = []
        try:
            creds = await get_connection_credentials(db, board_id)
        except Exception:
            creds = None
        if creds:
            live = await try_fetch_live(board_id, creds)
            if live:
                rows = live
                live_source = "live"
        if not rows:
            rows = _gen_loads_for_board(board_id)
            live_source = "synthetic"
        if equipment: rows = [r for r in rows if r["equipment"].lower() == equipment.lower()]
        if origin:    rows = [r for r in rows if origin.lower() in r["origin"].lower()]
        return {"board_id": board_id, "count": len(rows), "loads": rows, "source": live_source}

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
        """Book a load → creates a `brokerage_bookings` row AND a matching
        `shipments` row so the load flows straight into `/workflow` and
        `/tracking` without any extra step.

        Supports two modes:
          • **Synthetic feed** — looks up the load on the board's generator.
          • **Real tender** — pass `override_*` fields to book a load that
            wasn't on the synthetic feed (e.g. a shipper called it in).
        """
        # Try to find the load on the synthetic feed first
        all_loads = _gen_loads_for_board(payload.board_id)
        load = next((row for row in all_loads if row["load_id"] == payload.load_id), None)

        # If not found and no overrides, error
        has_overrides = any([payload.override_origin, payload.override_destination,
                              payload.override_miles is not None, payload.override_equipment,
                              payload.override_rate_usd is not None])
        if not load and not has_overrides:
            raise HTTPException(404,
                "Load not found on that board. Pass override_* fields to book a manual/real load.")

        # Resolve final values (overrides > synthetic > default)
        base = load or {}
        origin        = payload.override_origin       or base.get("origin", "—")
        destination   = payload.override_destination  or base.get("destination", "—")
        miles         = payload.override_miles         if payload.override_miles is not None else base.get("miles", 0)
        equipment     = payload.override_equipment    or base.get("equipment", "Van")
        rate_usd      = payload.override_rate_usd      if payload.override_rate_usd is not None else base.get("rate_usd", 0.0)
        carrier_pay   = payload.override_carrier_pay_usd if payload.override_carrier_pay_usd is not None else base.get("carrier_pay_usd", 0.0)
        pickup_date   = payload.override_pickup_date  or base.get("pickup_date")
        delivery_date = payload.override_delivery_date or base.get("delivery_date")
        margin_usd    = round((rate_usd or 0) - (carrier_pay or 0), 2)

        now = datetime.now(timezone.utc).isoformat()
        doc = {
            "booked_id": f"BK-{uuid.uuid4().hex[:10].upper()}",
            "load_id": payload.load_id,
            "board_id": payload.board_id,
            "carrier_name": payload.carrier_name,
            "carrier_mc": payload.carrier_mc,
            "customer_name": payload.customer_name,
            "customer_email": payload.customer_email,
            "origin": origin,
            "destination": destination,
            "miles": miles,
            "equipment": equipment,
            "forecast_rate_usd": rate_usd,
            "forecast_carrier_pay_usd": carrier_pay,
            "forecast_margin_usd": margin_usd,
            "settled_rate_usd": None,
            "settled_carrier_pay_usd": None,
            "settled_margin_usd": None,
            "pickup_date": pickup_date,
            "delivery_date": delivery_date,
            "status": "booked",
            "booked_at": now,
            "booked_by": user.user_id,
            "notes": payload.notes,
            # PRODUCTION-READY: real bookings survive "Wipe Sample"
            "is_sample": False,
            # Cross-reference for tracking + workflow
            "shipment_id": f"SH-{uuid.uuid4().hex[:10].upper()}",
        }
        await db.brokerage_bookings.insert_one(dict(doc))

        # ALSO create a matching shipment row so the load auto-appears on
        # /tracking with proper origin/destination + status. This is the
        # single-source pipeline the operator has been asking for.
        def _split_city_state(loc: str) -> Dict[str, str]:
            if not loc or "," not in loc:
                return {"city": loc or "—", "state": "", "name": loc or "—"}
            city, _, state = loc.partition(",")
            return {"city": city.strip(), "state": state.strip()[:4], "name": loc}

        shipment = {
            "shipment_id": doc["shipment_id"],
            "reference": payload.load_id,
            "booking_number": doc["booked_id"],
            "carrier": payload.carrier_name,
            "carrier_mc": payload.carrier_mc,
            "mode": "TL",
            "status": "pending",
            "origin":      _split_city_state(origin),
            "destination": _split_city_state(destination),
            "current_location": _split_city_state(origin),  # starts at origin
            "eta": delivery_date or (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()[:10],
            "pickup_date":   pickup_date or datetime.now(timezone.utc).isoformat()[:10],
            "delivery_date": delivery_date,
            "weight_lbs": float(base.get("weight_lbs") or 0),
            "pieces": int(base.get("pieces") or 1),
            "commodity": base.get("commodity") or equipment or "General freight",
            "value_usd": float(rate_usd or 0),
            "consignee": payload.customer_name,
            "supplier":  payload.customer_name,
            "customer_rate_usd": rate_usd,
            "carrier_rate_usd": carrier_pay,
            "miles": miles,
            "progress": 0.0,
            "direction": "outbound",
            "hazmat": bool(base.get("hazmat")),
            "notes": payload.notes,
            "created_at": now,
            "updated_at": now,
            "created_by": user.user_id,
            "is_sample": False,
            "_from_brokerage": True,
        }
        try:
            await db.shipments.insert_one(dict(shipment))
        except Exception as e:                                     # noqa: BLE001
            logger.warning("Shipment row create failed for %s: %s", doc["booked_id"], e)

        doc["shipment_created"] = True
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

    # ============================ BOOKED LOADS · BOL / POD ============================
    @router.get("/bookings")
    async def list_bookings(_=Depends(get_current_user)):
        """List recent bookings ready for BOL/POD generation + customer mailing."""
        rows = await db.brokerage_bookings.find({}, {"_id": 0}).sort("booked_at", -1).to_list(200)
        return {"bookings": rows, "count": len(rows)}

    # ---------- Check-Call HUD ----------
    # Drivers/dispatchers log manual status updates while a load is in
    # transit. Lifecycle = DISPATCHED → AT_SHIPPER → LOADED → IN_TRANSIT →
    # AT_RECEIVER → UNLOADED → DELIVERED. Each call writes one row to
    # `check_calls` array on the booking + advances the `transit_status`.

    @router.post("/bookings/{booked_id}/check-call")
    async def log_check_call(booked_id: str, payload: CheckCallIn,
                              user=Depends(get_current_user)):
        if payload.status not in CHECK_CALL_STATUSES:
            raise HTTPException(400, f"status must be one of {CHECK_CALL_STATUSES}")
        call = {
            "call_id": f"CC-{uuid.uuid4().hex[:10].upper()}",
            "at": datetime.now(timezone.utc).isoformat(),
            "by": getattr(user, "name", "system"),
            **payload.model_dump(),
        }
        r = await db.brokerage_bookings.find_one_and_update(
            {"booked_id": booked_id},
            {"$push": {"check_calls": call},
              "$set": {"transit_status": payload.status,
                        "last_check_call_at": call["at"]}},
            return_document=True, projection={"_id": 0},
        )
        if not r:
            raise HTTPException(404, "Booking not found")
        return r

    @router.get("/bookings/{booked_id}/check-calls")
    async def list_check_calls(booked_id: str,
                                _=Depends(get_current_user)):
        r = await db.brokerage_bookings.find_one(
            {"booked_id": booked_id},
            {"_id": 0, "check_calls": 1, "transit_status": 1,
              "last_check_call_at": 1, "booked_id": 1})
        if not r:
            raise HTTPException(404, "Booking not found")
        calls = sorted(r.get("check_calls") or [], key=lambda c: c.get("at", ""), reverse=True)
        return {"booked_id": booked_id, "transit_status": r.get("transit_status"),
                "last_check_call_at": r.get("last_check_call_at"),
                "calls": calls, "count": len(calls),
                "available_statuses": CHECK_CALL_STATUSES}

    @router.put("/bookings/{booked_id}/customer")
    async def set_booking_customer(booked_id: str, payload: CustomerInfoIn, user=Depends(get_current_user)):
        """Attach customer contact info to a booked load so we can email POD.

        If `auto_email_bol_on_book` is enabled in /settings and the saved
        customer has an email, the freshly-rendered BOL is mailed to them
        automatically as a one-step "book → tender" hand-off.
        """
        update = payload.model_dump(exclude_none=True)
        had_email_before = bool((await db.brokerage_bookings.find_one(
            {"booked_id": booked_id}, {"_id": 0, "customer_email": 1}
        ) or {}).get("customer_email"))
        r = await db.brokerage_bookings.find_one_and_update(
            {"booked_id": booked_id},
            {"$set": update},
            return_document=True,
            projection={"_id": 0},
        )
        if not r:
            raise HTTPException(404, "Booking not found")

        settings = await db.brokerage_settings.find_one({"_id": "main"}, {"_id": 0}) or {}
        auto_result: Dict[str, Any] = {}
        if (settings.get("auto_email_bol_on_book")
                and r.get("customer_email")
                and not had_email_before):
            try:
                auto_result = await _send_bol_email(r, settings.get("bol_message_template"), user)
            except HTTPException as exc:
                auto_result = {"auto_email_error": exc.detail}
            except Exception as exc:                                # noqa: BLE001
                logger.exception("Auto-BOL email failed")
                auto_result = {"auto_email_error": str(exc)[:200]}
        if auto_result:
            r["_auto_bol"] = auto_result
        return r

    async def _send_bol_email(booking: Dict[str, Any], message_template: Optional[str], user) -> Dict[str, Any]:
        """Render BOL PDF + send to booking.customer_email via Resend. Mirrors POD flow."""
        brand = await _active_brand(db)
        shipper, consignee = _brand_addresses(booking, brand)
        doc_prefix = (brand.get("short_name") or "ORI")[:3].upper()
        doc_id = f"{doc_prefix}-BOL-{booking['booked_id'].replace('BK-', '')}"
        pdf_bytes = build_bol_pdf(
            doc_id=doc_id, booking=booking,
            shipper=shipper, consignee=consignee,
            user_name=getattr(user, "name", None),
            brand=brand,
        )
        await db.brokerage_bookings.update_one(
            {"booked_id": booking["booked_id"]},
            {"$set": {"bol_no": doc_id, "bol_generated_at": datetime.now(timezone.utc).isoformat()}},
        )
        creds = await get_connection_credentials(db, "resend") or {}
        api_key = creds.get("api_key")
        if not api_key:
            return {"auto_email_error": "Resend not configured", "doc_id": doc_id}
        from_addr = creds.get("from_email") or "Orisei Freight <oliver@oriseifreight.com>"
        reply_to = creds.get("reply_to") or "oliver@oriseifreight.com"
        subject = f"BOL · {booking.get('load_id') or booking['booked_id']} · {booking.get('origin','')} → {booking.get('destination','')}"
        msg_html = (message_template or "").replace("\n", "<br>")
        body_html = f"""<!doctype html><html><body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;background:#FBF8F0;padding:24px;color:#0B1320;">
<div style="max-width:620px;margin:0 auto;background:#fff;border:1px solid #E6CB85;border-radius:8px;overflow:hidden;">
  <div style="background:#0E3A6B;color:#fff;padding:22px 26px;border-bottom:3px solid #C9A24A;">
    <div style="font-size:11px;letter-spacing:.3em;color:#C9A24A;text-transform:uppercase;font-family:Courier,monospace;">Orisei Freight Solutions</div>
    <div style="font-size:22px;font-weight:800;margin-top:6px;">Bill of Lading · {booking.get('load_id') or booking['booked_id']}</div>
  </div>
  <div style="padding:24px 26px;font-size:14px;line-height:1.6;">
    <p>Hi {booking.get('customer_contact') or booking.get('customer_name') or 'Team'},</p>
    <p>Attached is the signed BOL for the tendered load. Pickup will be confirmed shortly.</p>
    {f'<p style="background:#FBF8F0;border-left:3px solid #C9A24A;padding:10px 14px;font-style:italic;">{msg_html}</p>' if msg_html else ''}
    <p style="margin-top:20px;">— Operations<br><b>Orisei Freight Solutions LLC</b><br>oliver@oriseifreight.com · (612) 555-0117</p>
  </div></div></body></html>"""
        try:
            resend.api_key = api_key
            resp = resend.Emails.send({
                "from": from_addr, "to": [booking["customer_email"]],
                "subject": subject, "html": body_html, "reply_to": reply_to,
                "attachments": [{"filename": f"{doc_id}.pdf", "content": list(pdf_bytes)}],
            })
        except Exception as exc:                                    # noqa: BLE001
            logger.exception("BOL auto-email Resend failed")
            return {"auto_email_error": str(exc)[:200], "doc_id": doc_id}
        msg_id = (resp or {}).get("id") if isinstance(resp, dict) else None
        await db.bol_outreach.insert_one({
            "id": f"BOL-{uuid.uuid4().hex[:10].upper()}",
            "booked_id": booking["booked_id"], "doc_id": doc_id,
            "to_email": booking["customer_email"],
            "subject": subject,
            "message_id": msg_id, "status": "sent",
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "sent_by": getattr(user, "user_id", None),
        })
        return {"auto_email_sent": True, "doc_id": doc_id, "message_id": msg_id}


    async def _booking_or_404(booked_id: str) -> Dict[str, Any]:
        b = await db.brokerage_bookings.find_one({"booked_id": booked_id}, {"_id": 0})
        if not b:
            raise HTTPException(404, "Booking not found")
        return b

    async def _load_pod_photos(booked_id: str) -> List[Dict[str, Any]]:
        """Load up to 3 attached delivery photos as bytes for PDF embedding."""
        rows = await db.pod_photos.find(
            {"booked_id": booked_id}, {"_id": 0}
        ).sort("uploaded_at", 1).to_list(3)
        out: List[Dict[str, Any]] = []
        for r in rows:
            data = r.get("data")
            if isinstance(data, bytes):
                out.append({"bytes": data, "filename": r.get("filename"), "caption": r.get("caption")})
            elif isinstance(data, str):
                import base64 as _b64
                try:
                    out.append({"bytes": _b64.b64decode(data), "filename": r.get("filename"), "caption": r.get("caption")})
                except Exception:                                    # noqa: BLE001
                    continue
        return out

    def _brand_addresses(booking: Dict[str, Any], brand: Dict[str, Any]):
        shipper = {
            "name": booking.get("shipper_name") or brand.get("company_name") or "Orisei Freight Solutions LLC",
            "address": booking.get("shipper_address") or "Operations HQ",
            "city_state_zip": booking.get("origin") or "Minneapolis, MN",
            "contact": "dispatch@oriseifreight.com  ·  +1 (612) 555-0117",
        }
        consignee = {
            "name": booking.get("customer_name") or "Customer / Consignee",
            "address": booking.get("consignee_address") or "—",
            "city_state_zip": booking.get("destination") or "—",
            "contact": booking.get("customer_contact") or booking.get("customer_email") or "—",
        }
        return shipper, consignee

    @router.get("/bookings/{booked_id}/bol.pdf")
    async def generate_booking_bol(booked_id: str, user=Depends(get_current_user)):
        """Beautiful, brand-aware Bill of Lading for a booked load."""
        booking = await _booking_or_404(booked_id)
        brand = await _active_brand(db)
        shipper, consignee = _brand_addresses(booking, brand)
        doc_prefix = (brand.get("short_name") or "ORI")[:3].upper()
        doc_id = f"{doc_prefix}-BOL-{booked_id.replace('BK-', '')}"
        pdf = build_bol_pdf(
            doc_id=doc_id, booking=booking,
            shipper=shipper, consignee=consignee,
            user_name=getattr(user, "name", None),
            brand=brand,
        )
        # Stamp the BOL # on the booking for later POD reference
        await db.brokerage_bookings.update_one(
            {"booked_id": booked_id},
            {"$set": {"bol_no": doc_id, "bol_generated_at": datetime.now(timezone.utc).isoformat()}},
        )
        return StreamingResponse(
            io.BytesIO(pdf),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{doc_id}.pdf"'},
        )

    @router.get("/bookings/{booked_id}/pod.pdf")
    async def generate_booking_pod(booked_id: str, user=Depends(get_current_user)):
        """Generate a beautiful Proof of Delivery PDF (uses any saved delivery data)."""
        booking = await _booking_or_404(booked_id)
        brand = await _active_brand(db)
        shipper, consignee = _brand_addresses(booking, brand)
        delivery = dict(booking.get("delivery") or {})
        delivery["photos"] = await _load_pod_photos(booked_id)
        doc_prefix = (brand.get("short_name") or "ORI")[:3].upper()
        doc_id = f"{doc_prefix}-POD-{booked_id.replace('BK-', '')}"
        pdf = build_pod_pdf(
            doc_id=doc_id, booking=booking,
            shipper=shipper, consignee=consignee,
            delivery=delivery,
            user_name=getattr(user, "name", None),
            brand=brand,
        )
        return StreamingResponse(
            io.BytesIO(pdf),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{doc_id}.pdf"'},
        )

    @router.post("/bookings/{booked_id}/pod/email")
    async def email_booking_pod(booked_id: str, payload: PodEmailIn, user=Depends(get_current_user)):
        """Email the POD straight from the load board to the customer.

        Pulls Resend creds from the Connections vault. Falls back to dry-run mode
        when Resend is not configured so the front-end still gets a clean response.
        """
        booking = await _booking_or_404(booked_id)
        brand = await _active_brand(db)
        shipper, consignee = _brand_addresses(booking, brand)

        # Persist delivery info onto the booking so the next POD download mirrors it
        delivery_payload: Dict[str, Any] = {}
        if payload.delivery:
            delivery_payload = payload.delivery.model_dump(exclude_none=True)
            await db.brokerage_bookings.update_one(
                {"booked_id": booked_id},
                {"$set": {
                    "delivery": delivery_payload,
                    "status": "delivered",
                    "delivered_at": delivery_payload.get("delivered_at") or datetime.now(timezone.utc).isoformat(),
                }},
            )

        delivery_render = {**(booking.get("delivery") or {}), **delivery_payload}
        doc_prefix = (brand.get("short_name") or "ORI")[:3].upper()
        doc_id = f"{doc_prefix}-POD-{booked_id.replace('BK-', '')}"
        pdf_bytes = build_pod_pdf(
            doc_id=doc_id, booking={**booking, **delivery_payload},
            shipper=shipper, consignee=consignee,
            delivery=delivery_render,
            user_name=getattr(user, "name", None),
            brand=brand,
        )

        subject = payload.subject or (
            f"Proof of Delivery · {booking.get('load_id') or booked_id} · "
            f"{booking.get('origin', '')} → {booking.get('destination', '')}"
        )
        greeting = payload.to_name or booking.get("customer_contact") or booking.get("customer_name") or "Team"
        delivered_at_html = (delivery_render.get("delivered_at")
                              or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))
        message_html = (payload.message or "").replace("\n", "<br>")
        body_html = f"""<!doctype html>
<html><body style="font-family: -apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; background:#FBF8F0; padding:24px; color:#0B1320;">
  <div style="max-width:620px; margin:0 auto; background:#fff; border:1px solid #E6CB85; border-radius:8px; overflow:hidden;">
    <div style="background:#0E3A6B; color:#fff; padding:22px 26px; border-bottom:3px solid #C9A24A;">
      <div style="font-size:11px; letter-spacing:0.3em; color:#C9A24A; text-transform:uppercase; font-family:Courier,monospace;">Orisei Freight Solutions</div>
      <div style="font-size:22px; font-weight:800; margin-top:6px;">Proof of Delivery · {booking.get('load_id') or booked_id}</div>
      <div style="font-size:12px; color:#E6CB85; margin-top:2px;">Delivered {delivered_at_html}</div>
    </div>
    <div style="padding:24px 26px; font-size:14px; line-height:1.6;">
      <p>Hi {greeting},</p>
      <p>Your freight has been delivered. The signed Proof of Delivery is attached as a PDF for your records.</p>
      <table style="width:100%; border-collapse:collapse; margin:14px 0; font-size:13px;">
        <tr><td style="padding:6px 0; color:#475569; width:140px;">Load ID</td><td style="padding:6px 0;"><b>{booking.get('load_id') or booked_id}</b></td></tr>
        <tr><td style="padding:6px 0; color:#475569;">BOL #</td><td style="padding:6px 0;"><b>{booking.get('bol_no') or doc_id.replace('POD', 'BOL')}</b></td></tr>
        <tr><td style="padding:6px 0; color:#475569;">Carrier</td><td style="padding:6px 0;"><b>{booking.get('carrier_name', '—')}</b> · MC {booking.get('carrier_mc') or '—'}</td></tr>
        <tr><td style="padding:6px 0; color:#475569;">Lane</td><td style="padding:6px 0;"><b>{booking.get('origin', '—')} → {booking.get('destination', '—')}</b></td></tr>
        <tr><td style="padding:6px 0; color:#475569;">Received By</td><td style="padding:6px 0;">{delivery_render.get('received_by') or '—'}</td></tr>
        <tr><td style="padding:6px 0; color:#475569;">Condition</td><td style="padding:6px 0;">{delivery_render.get('condition') or 'Apparent good order'}</td></tr>
      </table>
      {f'<p style="background:#FBF8F0; border-left:3px solid #C9A24A; padding:10px 14px; font-style:italic; color:#0B1320;">{message_html}</p>' if message_html else ''}
      <p>If anything looks off — concealed damage, shortage, or a billing question — reply to this email within nine months and we will open a claim immediately.</p>
      <p style="margin-top:20px;">— Operations<br><b>Orisei Freight Solutions LLC</b><br>oliver@oriseifreight.com · (612) 555-0117</p>
    </div>
    <div style="background:#FBF8F0; color:#94A3B8; font-size:10px; text-align:center; padding:10px; font-family:Courier,monospace;">
      ORISEI FREIGHT SOLUTIONS · MINNEAPOLIS · SAINT PAUL · MN
    </div>
  </div>
</body></html>"""

        outreach_record = {
            "id": f"POD-{uuid.uuid4().hex[:10].upper()}",
            "booked_id": booked_id,
            "doc_id": doc_id,
            "to_email": payload.to_email,
            "cc_email": payload.cc_email,
            "subject": subject,
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "sent_by": getattr(user, "user_id", None),
            "pdf_bytes": len(pdf_bytes),
            "status": "pending",
        }

        if payload.dry_run:
            outreach_record["status"] = "dry_run"
            outreach_record["message_id"] = f"dryrun_{uuid.uuid4().hex[:10]}"
            await db.pod_outreach.insert_one(dict(outreach_record))
            outreach_record.pop("_id", None)
            return {"ok": True, **outreach_record, "html_preview": body_html, "dry_run": True}

        creds = await get_connection_credentials(db, "resend")
        api_key = (creds or {}).get("api_key")
        if not api_key:
            # Resend not configured — soft fail in dry-run mode so the UX is still helpful
            outreach_record["status"] = "missing_credentials"
            await db.pod_outreach.insert_one(dict(outreach_record))
            outreach_record.pop("_id", None)
            raise HTTPException(
                400,
                "Resend is not configured. Open Connections → Resend and paste a Resend API key, "
                "then retry. The POD PDF was generated and is downloadable.",
            )

        from_addr = (creds or {}).get("from_email") or "Orisei Freight <oliver@oriseifreight.com>"
        reply_to = (creds or {}).get("reply_to") or "oliver@oriseifreight.com"
        try:
            resend.api_key = api_key
            attachment = {
                "filename": f"{doc_id}.pdf",
                "content": list(pdf_bytes),
            }
            params = {
                "from": from_addr,
                "to": [payload.to_email],
                "subject": subject,
                "html": body_html,
                "reply_to": reply_to,
                "attachments": [attachment],
            }
            if payload.cc_email:
                params["cc"] = [payload.cc_email]
            resp = resend.Emails.send(params)
            outreach_record["status"] = "sent"
            outreach_record["message_id"] = (resp or {}).get("id") if isinstance(resp, dict) else None
        except Exception as exc:                                # noqa: BLE001
            logger.exception("POD email failed: %s", exc)
            outreach_record["status"] = "error"
            outreach_record["error"] = str(exc)[:300]
            await db.pod_outreach.insert_one(dict(outreach_record))
            raise HTTPException(502, f"Resend send failed: {exc}")

        await db.pod_outreach.insert_one(dict(outreach_record))
        outreach_record.pop("_id", None)
        return {"ok": True, **outreach_record}

    @router.get("/bookings/{booked_id}/pod-history")
    async def pod_history(booked_id: str, _=Depends(get_current_user)):
        rows = await db.pod_outreach.find({"booked_id": booked_id}, {"_id": 0}).sort("sent_at", -1).to_list(50)
        return {"items": rows, "count": len(rows)}

    # ---------- POD photo attachments (max 3 per booking, mobile-friendly) ----------
    @router.post("/bookings/{booked_id}/pod/photos")
    async def upload_pod_photo(
        booked_id: str,
        file: UploadFile = File(...),
        caption: Optional[str] = Form(None),
        user=Depends(get_current_user),
    ):
        await _booking_or_404(booked_id)
        existing = await db.pod_photos.count_documents({"booked_id": booked_id})
        if existing >= 3:
            raise HTTPException(400, "Maximum 3 photos per booking — delete one first")
        content = await file.read()
        if not content:
            raise HTTPException(400, "Empty upload")
        if len(content) > 8 * 1024 * 1024:
            raise HTTPException(400, "Photo too large (8 MB max)")
        # Downsample to ~1024px max edge before storing to keep DB lean.
        try:
            from PIL import Image as PILImage
            im = PILImage.open(io.BytesIO(content)).convert("RGB")
            im.thumbnail((1024, 1024), PILImage.LANCZOS)
            out = io.BytesIO()
            im.save(out, format="JPEG", quality=82, optimize=True)
            content = out.getvalue()
        except Exception:                                            # noqa: BLE001
            logger.exception("PIL downsample failed — storing original")
        photo_id = f"PHO-{uuid.uuid4().hex[:10].upper()}"
        await db.pod_photos.insert_one({
            "photo_id": photo_id,
            "booked_id": booked_id,
            "filename": file.filename or f"{photo_id}.jpg",
            "caption": caption or None,
            "data": content,
            "size_bytes": len(content),
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
            "uploaded_by": getattr(user, "user_id", None),
        })
        return {"photo_id": photo_id, "size_bytes": len(content),
                "filename": file.filename, "caption": caption}

    @router.get("/bookings/{booked_id}/pod/photos")
    async def list_pod_photos(booked_id: str, _=Depends(get_current_user)):
        rows = await db.pod_photos.find(
            {"booked_id": booked_id},
            {"_id": 0, "data": 0},
        ).sort("uploaded_at", 1).to_list(10)
        return {"photos": rows, "count": len(rows)}

    @router.get("/bookings/{booked_id}/pod/photos/{photo_id}")
    async def get_pod_photo(booked_id: str, photo_id: str, _=Depends(get_current_user)):
        row = await db.pod_photos.find_one(
            {"booked_id": booked_id, "photo_id": photo_id},
            {"_id": 0},
        )
        if not row:
            raise HTTPException(404, "Photo not found")
        return Response(content=row["data"], media_type="image/jpeg")

    @router.delete("/bookings/{booked_id}/pod/photos/{photo_id}")
    async def delete_pod_photo(booked_id: str, photo_id: str, _=Depends(get_current_user)):
        r = await db.pod_photos.delete_one({"booked_id": booked_id, "photo_id": photo_id})
        if not r.deleted_count:
            raise HTTPException(404, "Photo not found")
        return {"deleted": True}

    # ---------- Brokerage settings (auto-mail toggles) ----------
    @router.get("/settings")
    async def get_settings(_=Depends(get_current_user)):
        doc = await db.brokerage_settings.find_one({"_id": "main"}, {"_id": 0})
        return doc or {
            "auto_email_bol_on_book": False,
            "auto_email_pod_on_delivery": False,
            "bol_message_template": "",
            "pod_message_template": "",
        }

    @router.put("/settings")
    async def update_settings(payload: Dict[str, Any], _=Depends(require_role("admin"))):
        allowed = {"auto_email_bol_on_book", "auto_email_pod_on_delivery",
                   "bol_message_template", "pod_message_template"}
        clean = {k: v for k, v in (payload or {}).items() if k in allowed}
        if not clean:
            raise HTTPException(400, "No valid settings keys provided")
        await db.brokerage_settings.update_one(
            {"_id": "main"}, {"$set": clean}, upsert=True,
        )
        doc = await db.brokerage_settings.find_one({"_id": "main"}, {"_id": 0})
        return doc

    # ---------- Mark Delivered (triggers POD auto-mail when enabled) ----------
    @router.post("/bookings/{booked_id}/mark-delivered")
    async def mark_delivered(booked_id: str, payload: PodDeliveryIn, user=Depends(get_current_user)):
        """One-tap 'mark delivered' for dispatchers.

        Stores delivery fields, flips booking.status='delivered', and — if
        auto_email_pod_on_delivery is enabled in brokerage_settings AND a
        customer_email is on the booking — emails the POD automatically.
        """
        booking = await _booking_or_404(booked_id)
        delivery_payload = payload.model_dump(exclude_none=True)
        delivery_payload.setdefault("delivered_at",
                                    datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))
        await db.brokerage_bookings.update_one(
            {"booked_id": booked_id},
            {"$set": {
                "delivery": delivery_payload,
                "status": "delivered",
                "delivered_at": delivery_payload["delivered_at"],
            }},
        )
        booking = await db.brokerage_bookings.find_one({"booked_id": booked_id}, {"_id": 0})

        settings = await db.brokerage_settings.find_one({"_id": "main"}, {"_id": 0}) or {}
        result = {"ok": True, "auto_email_sent": False}
        if (settings.get("auto_email_pod_on_delivery")
                and booking and booking.get("customer_email")):
            try:
                auto_payload = PodEmailIn(
                    to_email=booking["customer_email"],
                    to_name=booking.get("customer_contact") or booking.get("customer_name"),
                    subject=None, message=settings.get("pod_message_template"),
                    delivery=payload, dry_run=False,
                )
                resp = await email_booking_pod(booked_id, auto_payload, user)  # type: ignore[arg-type]
                result["auto_email_sent"] = True
                result["pod_outreach_id"] = resp.get("id")
            except HTTPException as exc:
                result["auto_email_error"] = exc.detail
            except Exception as exc:                                # noqa: BLE001
                logger.exception("Auto-POD email failed")
                result["auto_email_error"] = str(exc)[:200]
        return result

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
            "company": (payload or {}).get("company") or "Orisei Brokerage LLC",
            "realm_id": f"qb-{uuid.uuid4().hex[:10]}",
            "connected_at": datetime.now(timezone.utc).isoformat(),
            "last_sync_at": None,
        }
        await db.brokerage_qb_config.update_one({"_id": "qb"}, {"$set": cfg}, upsert=True)
        cfg.pop("_id", None)
        return {"ok": True, **cfg}

    @router.get("/quickbooks/oauth/start")
    async def qb_oauth_start(_=Depends(require_role("admin"))):
        """Build the Intuit OAuth authorization URL from the Connections vault.

        Requires QuickBooks credentials (client_id, redirect_uri, environment) to
        be saved in the Connections page. Returns `{ authorize_url, state }` —
        the frontend opens `authorize_url` in a new tab; Intuit redirects back
        to `redirect_uri` (which should point to `/api/brokerage/quickbooks/oauth/callback`).
        """
        creds = await get_connection_credentials(db, "quickbooks") or {}
        client_id = creds.get("client_id")
        redirect_uri = creds.get("redirect_uri")
        env = (creds.get("environment") or "sandbox").lower()
        if not client_id or not redirect_uri:
            raise HTTPException(
                400,
                "QuickBooks credentials missing. Open Connections → QuickBooks Online and "
                "fill in Client ID, Client Secret, Environment, and Redirect URI.",
            )
        state = uuid.uuid4().hex
        await db.brokerage_qb_oauth_state.insert_one({
            "state": state,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "env": env,
        })
        from urllib.parse import urlencode
        params = {
            "client_id": client_id,
            "response_type": "code",
            "scope": "com.intuit.quickbooks.accounting",
            "redirect_uri": redirect_uri,
            "state": state,
        }
        base = "https://appcenter.intuit.com/connect/oauth2"
        return {
            "authorize_url": f"{base}?{urlencode(params)}",
            "state": state,
            "environment": env,
            "redirect_uri": redirect_uri,
        }

    @router.get("/quickbooks/oauth/callback")
    async def qb_oauth_callback(code: Optional[str] = None, state: Optional[str] = None,
                                realmId: Optional[str] = None, error: Optional[str] = None,
                                _=Depends(require_role("admin"))):
        """Intuit OAuth callback — exchanges the auth code for access tokens.

        Stores tokens against the brokerage_qb_config doc. Tokens are encrypted
        only in transit; the access_token is short-lived (1 hr) and the refresh
        token rotates on each refresh, so the surface area is bounded.
        """
        if error:
            raise HTTPException(400, f"QuickBooks OAuth error: {error}")
        if not code or not state:
            raise HTTPException(400, "Missing code/state in callback")
        st = await db.brokerage_qb_oauth_state.find_one({"state": state}, {"_id": 0})
        if not st:
            raise HTTPException(400, "Invalid or expired OAuth state")
        await db.brokerage_qb_oauth_state.delete_one({"state": state})

        creds = await get_connection_credentials(db, "quickbooks") or {}
        client_id = creds.get("client_id")
        client_secret = creds.get("client_secret")
        redirect_uri = creds.get("redirect_uri")
        if not (client_id and client_secret and redirect_uri):
            raise HTTPException(400, "QuickBooks credentials missing from Connections vault")

        import httpx
        token_url = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
        auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.post(
                    token_url,
                    data={"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri},
                    headers={
                        "Authorization": f"Basic {auth}",
                        "Accept": "application/json",
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                )
        except httpx.RequestError as exc:
            raise HTTPException(502, f"Intuit token endpoint unreachable: {exc}")
        if r.status_code >= 400:
            raise HTTPException(r.status_code, f"Intuit OAuth exchange failed: {r.text[:300]}")
        tok = r.json()
        cfg = {
            "_id": "qb",
            "connected": True,
            "company": f"QuickBooks Realm {realmId or 'sandbox'}",
            "realm_id": realmId,
            "access_token": tok.get("access_token"),
            "refresh_token": tok.get("refresh_token"),
            "expires_in": tok.get("expires_in"),
            "token_type": tok.get("token_type"),
            "connected_at": datetime.now(timezone.utc).isoformat(),
            "last_sync_at": None,
            "environment": st.get("env"),
        }
        await db.brokerage_qb_config.update_one({"_id": "qb"}, {"$set": cfg}, upsert=True)
        cfg.pop("_id", None)
        cfg.pop("access_token", None)
        cfg.pop("refresh_token", None)
        return {"ok": True, **cfg}

    @router.post("/quickbooks/disconnect")
    async def qb_disconnect(_=Depends(require_role("admin"))):
        await db.brokerage_qb_config.delete_one({"_id": "qb"})
        return {"ok": True}

    async def _qb_refresh_token_if_needed(cfg: Dict[str, Any]) -> Dict[str, Any]:
        """Refresh the QB access token if it's older than 50 min. Returns the
        updated cfg (also persisted to db.brokerage_qb_config)."""
        connected_at = cfg.get("connected_at")
        if not (cfg.get("refresh_token") and connected_at):
            return cfg
        try:
            connected_dt = datetime.fromisoformat(connected_at.replace("Z", "+00:00"))
        except Exception:                                            # noqa: BLE001
            return cfg
        age = (datetime.now(timezone.utc) - connected_dt).total_seconds()
        if age < 50 * 60:                                            # 50 min — token TTL is 60 min
            return cfg
        creds = await get_connection_credentials(db, "quickbooks") or {}
        client_id = creds.get("client_id")
        client_secret = creds.get("client_secret")
        if not (client_id and client_secret):
            return cfg
        import httpx as _httpx
        auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
        try:
            async with _httpx.AsyncClient(timeout=15.0) as client:
                r = await client.post(
                    "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer",
                    data={"grant_type": "refresh_token", "refresh_token": cfg["refresh_token"]},
                    headers={
                        "Authorization": f"Basic {auth}",
                        "Accept": "application/json",
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                )
            if r.status_code >= 400:
                logger.warning("QB token refresh failed %s", r.status_code)
                return cfg
            tok = r.json()
        except _httpx.RequestError as exc:
            logger.warning("QB token refresh network err: %s", exc)
            return cfg
        cfg = {
            **cfg,
            "access_token": tok.get("access_token") or cfg.get("access_token"),
            "refresh_token": tok.get("refresh_token") or cfg.get("refresh_token"),
            "expires_in": tok.get("expires_in"),
            "connected_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.brokerage_qb_config.update_one({"_id": "qb"}, {"$set": cfg})
        return cfg

    def _qb_api_base(cfg: Dict[str, Any]) -> str:
        env = (cfg.get("environment") or "sandbox").lower()
        if env == "production":
            return "https://quickbooks.api.intuit.com"
        return "https://sandbox-quickbooks.api.intuit.com"

    async def _qb_push_invoice(cfg: Dict[str, Any], inv: Dict[str, Any]) -> Dict[str, Any]:
        """POST a single invoice to QuickBooks Online. Returns push status dict."""
        import httpx as _httpx
        base = _qb_api_base(cfg)
        realm = cfg.get("realm_id")
        if not realm:
            return {"status": "error", "error": "Missing realm_id"}
        url = f"{base}/v3/company/{realm}/invoice?minorversion=70"
        # Minimal QB invoice — relies on a default Income Account; works in
        # sandbox out-of-the-box. Production may need an explicit ItemRef.
        amount = float(inv.get("amount_usd") or 0)
        body = {
            "Line": [{
                "Amount": amount,
                "DetailType": "SalesItemLineDetail",
                "Description": f"Orisei load {inv.get('load_id') or inv.get('invoice_id')}",
                "SalesItemLineDetail": {"ItemRef": {"value": "1"}},   # default 'Services' item in sandbox
            }],
            "CustomerRef": {"value": "1"},                            # default sandbox customer
            "DocNumber": (inv.get("invoice_id") or "")[:21],
            "PrivateNote": f"Auto-pushed from Orisei TMS · {inv.get('invoice_id')}",
        }
        try:
            async with _httpx.AsyncClient(timeout=15.0) as client:
                r = await client.post(
                    url, json=body,
                    headers={
                        "Authorization": f"Bearer {cfg.get('access_token')}",
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                    },
                )
        except _httpx.RequestError as exc:
            return {"status": "error", "error": f"network: {exc}"}
        if r.status_code >= 400:
            return {"status": "error", "code": r.status_code, "error": r.text[:300]}
        payload = r.json() if r.text else {}
        qb_id = (payload.get("Invoice") or {}).get("Id")
        return {"status": "sent", "qb_id": qb_id}

    async def _qb_push_expense(cfg: Dict[str, Any], exp: Dict[str, Any]) -> Dict[str, Any]:
        """POST a single expense to QuickBooks Online as a Purchase entry."""
        import httpx as _httpx
        base = _qb_api_base(cfg)
        realm = cfg.get("realm_id")
        if not realm:
            return {"status": "error", "error": "Missing realm_id"}
        url = f"{base}/v3/company/{realm}/purchase?minorversion=70"
        amount = float(exp.get("amount_usd") or 0)
        body = {
            "AccountRef": {"value": "35"},                            # sandbox: 'Checking'
            "PaymentType": "Cash",
            "Line": [{
                "Amount": amount,
                "DetailType": "AccountBasedExpenseLineDetail",
                "Description": exp.get("description") or exp.get("category") or "Orisei expense",
                "AccountBasedExpenseLineDetail": {"AccountRef": {"value": "7"}},  # sandbox: 'Job Expenses'
            }],
            "PrivateNote": f"Auto-pushed from Orisei TMS · {exp.get('expense_id')}",
        }
        try:
            async with _httpx.AsyncClient(timeout=15.0) as client:
                r = await client.post(
                    url, json=body,
                    headers={
                        "Authorization": f"Bearer {cfg.get('access_token')}",
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                    },
                )
        except _httpx.RequestError as exc:
            return {"status": "error", "error": f"network: {exc}"}
        if r.status_code >= 400:
            return {"status": "error", "code": r.status_code, "error": r.text[:300]}
        payload = r.json() if r.text else {}
        qb_id = (payload.get("Purchase") or {}).get("Id")
        return {"status": "sent", "qb_id": qb_id}

    @router.post("/quickbooks/sync")
    async def qb_sync(_=Depends(require_role("admin"))):
        """Push all pending invoices + expenses to QuickBooks Online live.

        Falls back to mock-mode (just flips synced_to_qb) when the connected
        config has no access_token (i.e. operator used the dev mock-connect).
        """
        cfg = await db.brokerage_qb_config.find_one({"_id": "qb"})
        if not cfg:
            raise HTTPException(400, "QuickBooks not connected")
        cfg = await _qb_refresh_token_if_needed(cfg)

        live = bool(cfg.get("access_token") and cfg.get("realm_id"))
        invoice_results: List[Dict[str, Any]] = []
        expense_results: List[Dict[str, Any]] = []

        if not live:
            # Dev / mock connect — preserve old behavior so the dashboard demo works
            inv_res = await db.brokerage_invoices.update_many(
                {"synced_to_qb": False}, {"$set": {"synced_to_qb": True}})
            exp_res = await db.brokerage_expenses.update_many(
                {"synced_to_qb": False}, {"$set": {"synced_to_qb": True}})
            await db.brokerage_qb_config.update_one(
                {"_id": "qb"},
                {"$set": {"last_sync_at": datetime.now(timezone.utc).isoformat()}},
            )
            return {
                "ok": True,
                "mode": "mock",
                "synced_invoices": inv_res.modified_count,
                "synced_expenses": exp_res.modified_count,
            }

        # Live push
        pending_invoices = await db.brokerage_invoices.find(
            {"synced_to_qb": {"$ne": True}}, {"_id": 0},
        ).to_list(200)
        pending_expenses = await db.brokerage_expenses.find(
            {"synced_to_qb": {"$ne": True}}, {"_id": 0},
        ).to_list(200)

        for inv in pending_invoices:
            res = await _qb_push_invoice(cfg, inv)
            invoice_results.append({"invoice_id": inv.get("invoice_id"), **res})
            update_doc: Dict[str, Any] = {"qb_push_attempted_at": datetime.now(timezone.utc).isoformat()}
            if res.get("status") == "sent":
                update_doc["synced_to_qb"] = True
                update_doc["qb_id"] = res.get("qb_id")
            else:
                update_doc["qb_push_error"] = res.get("error", "")[:300]
            await db.brokerage_invoices.update_one(
                {"invoice_id": inv["invoice_id"]}, {"$set": update_doc},
            )

        for exp in pending_expenses:
            res = await _qb_push_expense(cfg, exp)
            expense_results.append({"expense_id": exp.get("expense_id"), **res})
            update_doc = {"qb_push_attempted_at": datetime.now(timezone.utc).isoformat()}
            if res.get("status") == "sent":
                update_doc["synced_to_qb"] = True
                update_doc["qb_id"] = res.get("qb_id")
            else:
                update_doc["qb_push_error"] = res.get("error", "")[:300]
            await db.brokerage_expenses.update_one(
                {"expense_id": exp["expense_id"]}, {"$set": update_doc},
            )

        sent_inv = sum(1 for r in invoice_results if r.get("status") == "sent")
        sent_exp = sum(1 for r in expense_results if r.get("status") == "sent")
        err_inv = sum(1 for r in invoice_results if r.get("status") == "error")
        err_exp = sum(1 for r in expense_results if r.get("status") == "error")

        await db.brokerage_qb_config.update_one(
            {"_id": "qb"},
            {"$set": {"last_sync_at": datetime.now(timezone.utc).isoformat()}},
        )
        await db.brokerage_qb_sync_log.insert_one({
            "id": f"QBSYNC-{uuid.uuid4().hex[:10].upper()}",
            "synced_at": datetime.now(timezone.utc).isoformat(),
            "mode": "live",
            "invoices_sent": sent_inv, "invoices_failed": err_inv,
            "expenses_sent": sent_exp, "expenses_failed": err_exp,
            "invoice_results": invoice_results,
            "expense_results": expense_results,
        })
        return {
            "ok": True, "mode": "live",
            "synced_invoices": sent_inv,
            "failed_invoices": err_inv,
            "synced_expenses": sent_exp,
            "failed_expenses": err_exp,
            "invoice_results": invoice_results[:50],
            "expense_results": expense_results[:50],
        }

    @router.get("/quickbooks/sync-log")
    async def qb_sync_log(_=Depends(get_current_user)):
        rows = await db.brokerage_qb_sync_log.find(
            {}, {"_id": 0, "invoice_results": 0, "expense_results": 0},
        ).sort("synced_at", -1).to_list(50)
        return {"items": rows, "count": len(rows)}

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
        brand = await _active_brand(db)
        pdf_bytes = _render_form_pdf(form_meta, payload.fields, user, brand)
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
    @router.get("/plan-review")
    async def plan_review(_=Depends(get_current_user)):
        acks = await db.plan_review_acks.find({}, {"_id": 0}).to_list(10)
        return {
            "revision_note": "June 2026 rev-2: plan recalibrated to nationwide FTL at sandbox scale — "
                             "$2,000 avg loads, 14.5% margin, volume ramp to 20 loads/day (3,250 loads Y1). "
                             "Salary $5,000/mo (§3.6, trigger clears Month 1); all members equal 33⅓%; "
                             "P&L rebuilt with loss provisions, staff and financing fully charged.",
            "ownership": [
                {"name": "Oliver Cummins", "role": "Operator — ops, carrier vetting, pricing, shipper book",
                 "stake": "33⅓%", "contribution": "$10,000 in-kind — PAID IN FULL (ORI-RCT-0003)"},
                {"name": "Daniel W. Karsor", "role": "Software & media — Command Deck, brand engine",
                 "stake": "33⅓%", "contribution": "$10,000 cash — $2,500 received (ORI-RCT-0001)"},
                {"name": "Doug Graham", "role": "Member — capital + in-kind (§2.5)",
                 "stake": "33⅓%", "contribution": "$10,000 cash + in-kind — $1,300 received (ORI-RCT-0002)"},
            ],
            "salary": {"recipient": "Oliver Cummins", "amount_monthly": 5000,
                       "trigger": "Trigger (gross margin > $10,000/mo) clears in Month 1 at plan volume — "
                                  "salaried from launch",
                       "only_salaried_member": True, "reference": "Partnership Agreement §3.6"},
            "pnl": [
                {"metric": "Gross revenue (3,250 / 5,200 / 6,760 loads @ $2,000)", "y1": 6500000, "y2": 10400000, "y3": 13520000},
                {"metric": "Gross margin (14.5%)", "y1": 942500, "y2": 1508000, "y3": 1960400},
                {"metric": "Factoring / financing", "y1": 211250, "y2": 208000, "y3": 162240},
                {"metric": "OpEx (staff, boards, loss provisions)", "y1": 374300, "y2": 696600, "y3": 959600},
                {"metric": "EBITDA before partner pay", "y1": 356950, "y2": 603400, "y3": 838560, "bold": True},
                {"metric": "Operator salary — Oliver Cummins", "y1": 60000, "y2": 60000, "y3": 60000},
                {"metric": "Member distributions (combined)", "y1": 60000, "y2": 240000, "y3": 420000},
                {"metric": "Net income (retained → working capital)", "y1": 232350, "y2": 298800, "y3": 353960, "bold": True},
                {"metric": "Net cash to members (combined)", "y1": 352350, "y2": 598800, "y3": 833960, "bold": True},
                {"metric": "Per-member share (1/3)", "y1": 117450, "y2": 199600, "y3": 277987, "bold": True},
            ],
            "scenario_b": {
                "note": "All figures POSITIVE — 'est.' means estimate. Rev-2 adopts sandbox-scale volume: "
                        "at 20 loads/day the plan's weekly economics land within ~4% of the observed sandbox run. "
                        "Net desk profit is after loss provisions (claims 1.5% + bad debt 2%), financing, staff & overhead.",
                "columns": ["Plan Y1 exit / Y2 (20/day)", "Sandbox Day-6 observed (~17.5/day)", "Plan Y3 (26/day)"],
                "rows": [
                    {"metric": "Loads / week", "a": "100", "b": "68 closed", "c": "130"},
                    {"metric": "Avg revenue / load", "a": "$2,000", "b": "$3,141", "c": "$2,000"},
                    {"metric": "Gross margin / load", "a": "$290 (14.5%)", "b": "$423 (13.5%)", "c": "$290 (14.5%)"},
                    {"metric": "Gross margin / week", "a": "$29,000", "b": "$28,600", "c": "$37,700"},
                    {"metric": "Net desk profit / week", "a": "est. $11,600", "b": "est. $12,100", "c": "est. $16,100", "bold": True},
                    {"metric": "Annualized EBITDA", "a": "est. $603,400", "b": "est. $630,000", "c": "$838,560", "bold": True},
                ],
            },
            "working_capital": {
                "formula": "Cash need ≈ (DSO 37 − blended DPO 19) ÷ 365 × annual revenue · factor advances 92%",
                "phases": [
                    {"phase": "P1 · Launch (Mo 1-3)", "volume": "25 loads/wk", "revenue": "$2.6M run-rate",
                     "ar": "≈ $265K", "cash_needed": "$40-60K",
                     "funding": "$30K partner capital + Month 1-2 retained profit + factor 92% advance"},
                    {"phase": "P2 · Ramp (Mo 4-9)", "volume": "50-75 loads/wk", "revenue": "$5.2-7.8M",
                     "ar": "$530-790K", "cash_needed": "$90-150K",
                     "funding": "Year-1 retained earnings ($232K) + factoring volume tier (~3.0%)"},
                    {"phase": "P3 · Full volume (Mo 10+)", "volume": "100-130 loads/wk", "revenue": "$10.4-13.5M",
                     "ar": "$1.05-1.4M", "cash_needed": "$250-400K cushion",
                     "funding": "Bank AR line $500-750K by Mo 12-15 (saves ≈ $150K/yr vs factoring)"},
                ],
                "guardrails": ["Credit-check every new shipper", "Max 20% of AR in any one shipper",
                               "2% bad-debt reserve held monthly", "Quick-pay 2% fee = profit center",
                               "No fuel advances", "DSO reviewed weekly"],
                "bottom_line": "No new equity required: $30K capital + factoring funds the launch quarter; "
                               "Year-1 retained earnings ($232K) fund the ramp; bank AR line by Month 12-15 "
                               "carries full volume.",
            },
            "acks": acks,
        }

    @router.post("/plan-review/ack")
    async def plan_review_ack(payload: PlanReviewAckIn, _=Depends(get_current_user)):
        valid = {"Oliver Cummins", "Daniel W. Karsor", "Doug Graham"}
        if payload.partner not in valid:
            raise HTTPException(status_code=400, detail="Unknown partner")
        doc = {"partner": payload.partner, "decision": payload.decision, "note": payload.note,
               "at": datetime.now(timezone.utc).isoformat()}
        await db.plan_review_acks.update_one({"partner": payload.partner}, {"$set": doc}, upsert=True)
        return {"ok": True, "ack": doc}

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

    @router.get("/partnership-agreement")
    async def partnership_agreement(_=Depends(get_current_user)):
        """Return the MN three-member partnership agreement markdown."""
        return _read_doc("PARTNERSHIP_AGREEMENT.md", "Partnership agreement document not found")

    @router.get("/partnership-agreement/pdf")
    async def partnership_agreement_pdf(_=Depends(get_current_user)):
        """Branded PDF of the MN three-member partnership agreement."""
        doc = _read_doc("PARTNERSHIP_AGREEMENT.md", "Partnership agreement document not found")
        brand = await _active_brand(db)
        company = brand.get("company_name") or "Orisei Freight Solutions LLC"
        pdf_bytes = build_branded_markdown_pdf(
            doc["markdown"], title="Partnership Agreement",
            subtitle="Member-Controlled LLC · Minnesota · Three Members · Equal 33 1/3% · Notarized",
            brand=brand,
        )
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{company.replace(" ", "_")}_Partnership_Agreement.pdf"'},
        )

    @router.get("/operating-agreement")
    async def operating_agreement(_=Depends(get_current_user)):
        """Return the MN three-member operating agreement markdown."""
        return _read_doc("OPERATING_AGREEMENT.md", "Operating agreement document not found")

    @router.get("/operating-agreement/pdf")
    async def operating_agreement_pdf(_=Depends(get_current_user)):
        """Branded PDF of the MN three-member operating agreement."""
        doc = _read_doc("OPERATING_AGREEMENT.md", "Operating agreement document not found")
        brand = await _active_brand(db)
        company = brand.get("company_name") or "Orisei Freight Solutions LLC"
        pdf_bytes = build_branded_markdown_pdf(
            doc["markdown"], title="Operating Agreement",
            subtitle="Ownership · Capital Calls · Decisions · Buyout · Non-Compete · Notarized",
            brand=brand,
        )
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{company.replace(" ", "_")}_Operating_Agreement.pdf"'},
        )

    @router.get("/business-plan/brochure.pdf")
    async def business_plan_brochure(_=Depends(get_current_user)):
        """Colorful brochure-style PDF of the business plan."""
        from .plan_brochure import build_plan_brochure_pdf
        pdf_bytes = build_plan_brochure_pdf()
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": 'attachment; filename="Orisei_Business_Plan_Brochure.pdf"'},
        )

    @router.get("/carrier-brochure.pdf")
    async def carrier_brochure(_=Depends(get_current_user)):
        """Colorful carrier-facing brochure: platform capabilities + integration."""
        from .carrier_brochure import build_carrier_brochure_pdf
        pdf_bytes = build_carrier_brochure_pdf()
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": 'attachment; filename="Orisei_Carrier_Partner_Brochure.pdf"'},
        )

    @router.get("/logo-pack.pdf")
    async def logo_pack(_=Depends(get_current_user)):
        """Official logo & brand pack: Queen Califia seal + apparel mockups."""
        from .logo_pack import build_logo_pack_pdf
        pdf_bytes = build_logo_pack_pdf()
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": 'attachment; filename="Orisei_Logo_Brand_Pack.pdf"'},
        )

    @router.get("/platform-manual.pdf")
    async def platform_manual(_=Depends(get_current_user)):
        """Colorful field-manual brochure for the entire platform."""
        from .platform_manual import build_platform_manual_pdf
        pdf_bytes = build_platform_manual_pdf()
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": 'attachment; filename="Orisei_Command_Deck_Field_Manual.pdf"'},
        )

    # ---- Branded PDF downloads of the markdown documents ----
    @router.get("/business-plan/pdf")
    async def business_plan_pdf(_=Depends(get_current_user)):
        """Direct download of the brand-themed business plan PDF."""
        doc = _read_doc("BROKERAGE_BUSINESS_PLAN.md", "Business plan document not found")
        brand = await _active_brand(db)
        company = brand.get("company_name") or "Orisei Freight Solutions LLC"
        pdf_bytes = build_branded_markdown_pdf(
            doc["markdown"], title=company,
            subtitle="Founder Business Plan · Confidential",
            brand=brand,
        )
        filename = f"{company.replace(' ', '_')}_Business_Plan.pdf"
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @router.get("/cost-analysis/pdf")
    async def cost_analysis_pdf(_=Depends(get_current_user)):
        doc = _read_doc("COST_ANALYSIS.md", "Cost analysis document not found")
        brand = await _active_brand(db)
        company = brand.get("company_name") or "Orisei Freight Solutions LLC"
        pdf_bytes = build_branded_markdown_pdf(
            doc["markdown"], title="Cost Analysis",
            subtitle="Live operating-cost forecast · Confidential",
            brand=brand,
        )
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{company.replace(" ", "_")}_Cost_Analysis.pdf"'},
        )

    @router.get("/home-office-setup/pdf")
    async def home_office_setup_pdf(_=Depends(get_current_user)):
        doc = _read_doc("HOME_OFFICE_SETUP.md", "Home office setup document not found")
        brand = await _active_brand(db)
        company = brand.get("company_name") or "Orisei Freight Solutions LLC"
        hq = brand.get("headquarters") or "Saint Paul, MN"
        pdf_bytes = build_branded_markdown_pdf(
            doc["markdown"], title="Home Office Setup",
            subtitle=f"Operator playbook · {hq}",
            brand=brand,
        )
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{company.replace(" ", "_")}_Home_Office_Setup.pdf"'},
        )

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
            pdf_bytes = _markdown_to_pdf_bytes(doc["markdown"], title=brand.get("company_name", "Business Plan"), brand=brand)
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
            pdf_bytes = _markdown_to_pdf_bytes(doc["markdown"], title=company, brand=brand)
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
def _render_form_pdf(form_meta: Dict[str, Any], fields: Dict[str, Any], user: Any,
                      brand: Optional[Dict[str, Any]] = None) -> bytes:
    """Render a brokerage compliance form to PDF using the active-brand template."""
    schema = _form_schema(form_meta["id"])
    legal = _form_legal_text(form_meta["id"])
    return build_form_pdf(
        form_meta=form_meta,
        schema_rows=schema,
        fields=fields or {},
        legal_text=legal,
        user_name=getattr(user, "name", None),
        brand=brand,
    )


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
