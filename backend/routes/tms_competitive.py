"""routes.tms_competitive — Feature parity with McLeod / MercuryGate / Descartes / TMW.

Bundles 10 features into one cohesive admin/portal module:

  A. Customer Portal spot-quote request
  B. Accessorial library (CRUD + seed)
  C. FMCSA SAFER auto-vetting on MC#
  D. Lane analytics (RPM trend, OTP per lane, capacity)
  E. Contract vs spot rate matrix
  F. Dock / appointment scheduling
  G. Multi-modal mode-shift recommender
  I. Freight audit & pay automation
  J. Public RFP / digital RFQ board

Plus driver PWA endpoints (H) under /api/driver-pwa/*.
"""
from __future__ import annotations

import logging
import os
import uuid
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel, EmailStr, Field

logger = logging.getLogger("tennant_tms.tms_competitive")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ============================ PYDANTIC ============================
class SpotQuoteRequestIn(BaseModel):
    origin: str = Field(..., max_length=200)
    destination: str = Field(..., max_length=200)
    pickup_date: Optional[str] = None
    equipment: str = "Dry Van"
    weight_lbs: Optional[float] = Field(None, ge=0)
    commodity: Optional[str] = Field(None, max_length=200)
    notes: Optional[str] = Field(None, max_length=2000)
    requester_name: Optional[str] = None
    requester_email: Optional[EmailStr] = None
    requester_phone: Optional[str] = None


class AccessorialIn(BaseModel):
    code: str = Field(..., max_length=20)
    label: str = Field(..., max_length=120)
    description: Optional[str] = Field(None, max_length=400)
    rate_usd: float = Field(0.0, ge=0)
    rate_type: str = "flat"     # flat | per_hour | per_mile | per_pallet
    chargeable_to: str = "customer"   # customer | carrier | both
    active: bool = True


class ContractRateIn(BaseModel):
    customer_id: str
    origin_state: str = Field(..., min_length=2, max_length=2)
    destination_state: str = Field(..., min_length=2, max_length=2)
    equipment: str = "Dry Van"
    line_haul_usd: float = Field(..., ge=0)
    fuel_surcharge_usd: float = 0.0
    effective_from: str
    effective_to: str
    min_commit_loads: Optional[int] = Field(None, ge=0)
    max_volume_loads: Optional[int] = Field(None, ge=0)
    notes: Optional[str] = None


class DockAppointmentIn(BaseModel):
    booking_id: Optional[str] = None
    facility_name: str
    facility_address: Optional[str] = None
    appointment_type: str = "pickup"   # pickup | delivery
    scheduled_at: str          # ISO datetime
    duration_minutes: int = Field(60, ge=15, le=480)
    carrier_name: Optional[str] = None
    carrier_mc: Optional[str] = None
    notes: Optional[str] = None
    customer_id: Optional[str] = None


class ModeShiftIn(BaseModel):
    origin: str
    destination: str
    miles: float
    weight_lbs: float
    equipment: str = "Dry Van"
    current_rate_usd: float


class FreightAuditIn(BaseModel):
    booking_id: str
    carrier_invoice_usd: float = Field(..., ge=0)
    accessorial_breakdown: Optional[List[Dict[str, Any]]] = None
    invoice_number: Optional[str] = None


class RfpIn(BaseModel):
    customer_id: Optional[str] = None
    shipper_name: str = Field(..., max_length=200)
    title: str = Field(..., max_length=200)
    description: Optional[str] = Field(None, max_length=4000)
    lanes: List[Dict[str, Any]]      # [{origin, destination, equipment, est_volume_per_week}]
    submission_deadline: str
    contract_start: Optional[str] = None
    contract_end: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    is_public: bool = True


class RfpBidIn(BaseModel):
    bidder_name: str = Field(..., max_length=200)
    bidder_email: Optional[EmailStr] = None
    bidder_mc: Optional[str] = None
    lane_rates: List[Dict[str, Any]]    # [{lane_index, rate_per_load}]
    notes: Optional[str] = None


# ============================ FMCSA SAFER (C) ============================
_SAFER_CACHE: Dict[str, Dict[str, Any]] = {}


async def _fmcsa_safer_lookup(mc_number: str) -> Dict[str, Any]:
    """Query the public FMCSA SAFER snapshot. No API key required.

    Returns a sanitized dict with operating_status, safety_rating, insurance_on_file,
    drivers, power_units, plus a `raw` blob for the UI. Cached 6h to be polite.
    """
    mc = (mc_number or "").strip().replace("MC", "").replace("-", "")
    if not mc:
        return {"error": "missing_mc"}
    if mc in _SAFER_CACHE:
        cached = _SAFER_CACHE[mc]
        if (datetime.now(timezone.utc)
                - datetime.fromisoformat(cached["_cached_at"])).seconds < 21600:
            return cached
    try:
        async with httpx.AsyncClient(timeout=10) as http:
            r = await http.get(
                f"https://mobile.fmcsa.dot.gov/qc/services/carriers/docket-number/{mc}",
                params={"webKey": os.environ.get("FMCSA_WEBKEY", "FREE")},
                headers={"Accept": "application/json"},
            )
            if r.status_code != 200:
                return {"error": "fmcsa_unreachable", "status_code": r.status_code}
            payload = r.json()
    except Exception as exc:                                          # noqa: BLE001
        logger.warning("FMCSA SAFER lookup failed for %s: %s", mc, exc)
        return {"error": "fmcsa_unreachable", "detail": str(exc)[:200]}
    content = payload.get("content") or []
    if not content:
        return {"error": "not_found", "mc": mc}
    item = content[0].get("carrier") or {}
    flags = []
    op_status = (item.get("statusCode") or "").strip()
    if op_status and op_status != "A":
        flags.append({"level": "red", "code": "AUTHORITY_INACTIVE",
                       "msg": f"Operating status: {op_status}"})
    safety = (item.get("safetyRating") or "").strip()
    if safety in ("U", "C"):                                          # Unsatisfactory / Conditional
        flags.append({"level": "red", "code": "SAFETY_RATING",
                       "msg": f"Safety rating: {safety}"})
    if item.get("brokerAuthorityStatus") not in ("A", None) and item.get("brokerAuthorityStatus"):
        flags.append({"level": "amber", "code": "BROKER_AUTH",
                       "msg": "Broker authority flagged"})
    result = {
        "mc": mc,
        "legal_name": item.get("legalName"),
        "dba_name": item.get("dbaName"),
        "operating_status": op_status or "unknown",
        "safety_rating": safety or "—",
        "insurance_on_file": bool(item.get("bipdInsuranceOnFile")),
        "drivers": item.get("totalDrivers"),
        "power_units": item.get("totalPowerUnits"),
        "phone": item.get("phyPhone"),
        "address": item.get("phyStreet"),
        "city_state": f"{item.get('phyCity') or ''}, {item.get('phyState') or ''}",
        "flags": flags,
        "verdict": "RED" if any(f["level"] == "red" for f in flags) else
                    ("AMBER" if flags else "GREEN"),
        "_cached_at": _now(),
    }
    _SAFER_CACHE[mc] = result
    return result


# ============================ MODE-SHIFT (G) ============================
def _mode_shift_recommendation(payload: ModeShiftIn) -> Dict[str, Any]:
    """Tiny heuristic — replace with rail rate API later. For now uses
    industry-published intermodal rules of thumb: viable for 800+ mi,
    saves 12-18% vs OTR but adds 2-3 transit days."""
    options: List[Dict[str, Any]] = []
    if payload.miles >= 800 and payload.equipment in ("Dry Van", "Reefer"):
        savings_pct = 0.15
        if payload.miles >= 1500:
            savings_pct = 0.18
        intermodal_rate = round(payload.current_rate_usd * (1 - savings_pct), 2)
        options.append({
            "mode": "Intermodal (rail + drayage)",
            "estimated_rate_usd": intermodal_rate,
            "savings_usd": round(payload.current_rate_usd - intermodal_rate, 2),
            "savings_pct": round(savings_pct * 100, 1),
            "added_days": 2 if payload.miles < 1500 else 3,
            "viability": "high" if payload.miles >= 1000 else "medium",
            "carriers": ["BNSF Logistics", "J.B. Hunt Intermodal", "Schneider Intermodal"],
            "notes": ("Intermodal viable for 800+ mile dry/reefer freight. "
                       "Add lead time for ramp drayage at both ends."),
        })
    if payload.weight_lbs <= 5000 and payload.equipment == "Dry Van":
        options.append({
            "mode": "LTL consolidation",
            "estimated_rate_usd": round(payload.current_rate_usd * 0.55, 2),
            "savings_usd": round(payload.current_rate_usd * 0.45, 2),
            "savings_pct": 45.0,
            "added_days": 1,
            "viability": "high",
            "carriers": ["XPO", "Estes", "Saia", "ODFL"],
            "notes": "LTL economics dominate under 5,000 lbs.",
        })
    if not options:
        options.append({
            "mode": "OTR Truckload (current)",
            "estimated_rate_usd": payload.current_rate_usd,
            "savings_usd": 0,
            "savings_pct": 0,
            "added_days": 0,
            "viability": "n/a",
            "notes": "No mode-shift alternative for this lane/weight profile.",
        })
    return {
        "lane": f"{payload.origin} → {payload.destination}",
        "miles": payload.miles,
        "options": options,
        "recommendation": options[0] if options[0]["savings_usd"] > 0 else None,
    }


# ============================ DEFAULT ACCESSORIALS (B seed) ============================
DEFAULT_ACCESSORIALS = [
    {"code": "DET", "label": "Detention", "description": "Driver/truck held beyond 2 hr free time",
     "rate_usd": 50, "rate_type": "per_hour", "chargeable_to": "customer"},
    {"code": "LMP", "label": "Lumper", "description": "Third-party loading/unloading service",
     "rate_usd": 150, "rate_type": "flat", "chargeable_to": "customer"},
    {"code": "LAY", "label": "Layover", "description": "Driver held overnight",
     "rate_usd": 250, "rate_type": "flat", "chargeable_to": "customer"},
    {"code": "TONU", "label": "Truck Ordered Not Used", "description": "Carrier dispatched, shipper cancels",
     "rate_usd": 150, "rate_type": "flat", "chargeable_to": "customer"},
    {"code": "DA", "label": "Driver Assist", "description": "Driver helps load/unload",
     "rate_usd": 75, "rate_type": "flat", "chargeable_to": "customer"},
    {"code": "STP", "label": "Stop-Off", "description": "Additional pickup or delivery stop",
     "rate_usd": 50, "rate_type": "flat", "chargeable_to": "customer"},
    {"code": "FSC", "label": "Fuel Surcharge", "description": "Variable fuel adjustment",
     "rate_usd": 0.55, "rate_type": "per_mile", "chargeable_to": "customer"},
    {"code": "TARP", "label": "Tarping", "description": "Flatbed tarp service",
     "rate_usd": 75, "rate_type": "flat", "chargeable_to": "customer"},
    {"code": "RES", "label": "Residential Delivery", "description": "Non-commercial delivery address",
     "rate_usd": 95, "rate_type": "flat", "chargeable_to": "customer"},
    {"code": "REWG", "label": "Reweigh", "description": "Truck reweigh request",
     "rate_usd": 35, "rate_type": "flat", "chargeable_to": "customer"},
    {"code": "INSIDE", "label": "Inside Delivery", "description": "Beyond the dock",
     "rate_usd": 125, "rate_type": "flat", "chargeable_to": "customer"},
    {"code": "OVRDIM", "label": "Over-Dimensional", "description": "Permit fees, escort",
     "rate_usd": 0, "rate_type": "flat", "chargeable_to": "customer"},
]


async def _seed_accessorials(db):
    """Idempotent seed of the default accessorial catalog."""
    existing = await db.orisei_accessorials.count_documents({})
    if existing > 0:
        return
    docs = []
    for a in DEFAULT_ACCESSORIALS:
        docs.append({**a, "created_at": _now(),
                      "accessorial_id": f"ACC-{uuid.uuid4().hex[:8].upper()}",
                      "active": True, "is_default": True})
    if docs:
        await db.orisei_accessorials.insert_many(docs)


# ============================ MAIN ROUTER ============================
def build_tms_competitive_router(
    api_router: APIRouter, *, db,
    get_current_user: Callable, require_role: Callable,
) -> None:
    asyncio.create_task(_seed_accessorials(db))
    admin_dep = Depends(require_role("admin", "dispatcher"))
    router = APIRouter(prefix="/tms-competitive", tags=["tms-competitive"])

    # ============================ B · ACCESSORIAL LIBRARY ============================
    @router.get("/accessorials")
    async def list_accessorials(active_only: bool = True,
                                  _=Depends(get_current_user)) -> Dict[str, Any]:
        q = {"active": True} if active_only else {}
        rows = await db.orisei_accessorials.find(q, {"_id": 0}).sort("code", 1).to_list(200)
        return {"items": rows, "count": len(rows)}

    @router.post("/accessorials")
    async def create_accessorial(payload: AccessorialIn, user=admin_dep) -> Dict[str, Any]:
        doc = {**payload.model_dump(),
                "accessorial_id": f"ACC-{uuid.uuid4().hex[:8].upper()}",
                "created_at": _now(),
                "created_by": getattr(user, "name", "system"),
                "is_default": False}
        await db.orisei_accessorials.insert_one(dict(doc))
        doc.pop("_id", None)
        return doc

    @router.delete("/accessorials/{accessorial_id}")
    async def delete_accessorial(accessorial_id: str, user=admin_dep) -> Dict[str, str]:
        res = await db.orisei_accessorials.update_one(
            {"accessorial_id": accessorial_id},
            {"$set": {"active": False}})
        if res.matched_count == 0:
            raise HTTPException(404, "Accessorial not found")
        return {"status": "deactivated"}

    # ============================ C · FMCSA AUTO-VETTING ============================
    @router.get("/fmcsa/{mc_number}")
    async def fmcsa_lookup(mc_number: str, _=Depends(get_current_user)) -> Dict[str, Any]:
        result = await _fmcsa_safer_lookup(mc_number)
        await db.orisei_fmcsa_lookups.insert_one({
            "mc": mc_number, "result": result, "looked_up_at": _now(),
        })
        return result

    # ============================ D · LANE ANALYTICS ============================
    @router.get("/lane-analytics")
    async def lane_analytics(window_days: int = Query(90, ge=7, le=365),
                              _=Depends(get_current_user)) -> Dict[str, Any]:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=window_days)).isoformat()
        bookings = await db.brokerage_bookings.find(
            {"$or": [{"created_at": {"$gte": cutoff}},
                     {"booked_at": {"$gte": cutoff}}]},
            {"_id": 0}).to_list(2000)
        lanes: Dict[tuple, Dict[str, Any]] = {}
        for b in bookings:
            origin = (b.get("origin") or "").strip()
            dest = (b.get("destination") or "").strip()
            if not origin or not dest:
                continue
            key = (origin, dest)
            if key not in lanes:
                lanes[key] = {
                    "origin": origin, "destination": dest,
                    "loads": 0, "rates": [], "miles": [],
                    "delivered": 0, "on_time": 0, "dwell_hours": [],
                }
            row = lanes[key]
            row["loads"] += 1
            rate = b.get("customer_rate_usd") or b.get("rate_usd")
            if rate:
                row["rates"].append(float(rate))
            if b.get("miles"):
                row["miles"].append(float(b["miles"]))
            if b.get("status") == "delivered":
                row["delivered"] += 1
                if not b.get("delivery_date") or not b.get("delivered_at") \
                        or b.get("delivered_at", "")[:10] <= b.get("delivery_date", ""):
                    row["on_time"] += 1
        out = []
        for (origin, dest), row in lanes.items():
            rates = sorted(row["rates"])
            miles = sum(row["miles"]) / len(row["miles"]) if row["miles"] else None
            rpm = None
            if rates and miles:
                rpm = round(sum(rates) / len(rates) / miles, 2)
            otp = (row["on_time"] / row["delivered"] * 100) if row["delivered"] else None
            tightness = "high" if row["loads"] >= 8 and rpm and rpm >= 2.5 else (
                         "low" if row["loads"] < 3 else "medium")
            out.append({
                "origin": origin, "destination": dest,
                "loads": row["loads"], "delivered": row["delivered"],
                "avg_rate_usd": round(sum(rates) / len(rates), 2) if rates else None,
                "median_rate_usd": rates[len(rates) // 2] if rates else None,
                "rpm": rpm, "avg_miles": round(miles, 0) if miles else None,
                "on_time_pct": round(otp, 1) if otp is not None else None,
                "capacity_tightness": tightness,
            })
        out.sort(key=lambda x: x["loads"], reverse=True)
        # Network rollup
        total_loads = sum(L["loads"] for L in out)
        avg_rpm = round(sum(L["rpm"] for L in out if L["rpm"]) /
                          max(sum(1 for L in out if L["rpm"]), 1), 2)
        return {
            "window_days": window_days,
            "lane_count": len(out),
            "total_loads": total_loads,
            "network_avg_rpm": avg_rpm,
            "lanes": out,
        }

    # ============================ E · CONTRACT RATES ============================
    @router.get("/contract-rates")
    async def list_contract_rates(customer_id: Optional[str] = None,
                                    _=Depends(get_current_user)) -> Dict[str, Any]:
        q = {"customer_id": customer_id} if customer_id else {}
        rows = await db.orisei_contract_rates.find(q, {"_id": 0}).sort("effective_from", -1).to_list(500)
        return {"items": rows, "count": len(rows)}

    @router.post("/contract-rates")
    async def create_contract_rate(payload: ContractRateIn, user=admin_dep) -> Dict[str, Any]:
        doc = {**payload.model_dump(),
                "contract_rate_id": f"CTR-{uuid.uuid4().hex[:10].upper()}",
                "created_at": _now(),
                "created_by": getattr(user, "name", "system"),
                "loads_used": 0, "active": True}
        await db.orisei_contract_rates.insert_one(dict(doc))
        doc.pop("_id", None)
        return doc

    @router.delete("/contract-rates/{contract_rate_id}")
    async def delete_contract_rate(contract_rate_id: str, user=admin_dep) -> Dict[str, str]:
        res = await db.orisei_contract_rates.update_one(
            {"contract_rate_id": contract_rate_id}, {"$set": {"active": False}})
        if res.matched_count == 0:
            raise HTTPException(404, "Contract rate not found")
        return {"status": "deactivated"}

    @router.get("/rate-lookup")
    async def rate_lookup(origin_state: str, destination_state: str,
                           equipment: str = "Dry Van",
                           customer_id: Optional[str] = None,
                           _=Depends(get_current_user)) -> Dict[str, Any]:
        """Auto-prefer contract rate over spot."""
        today = datetime.now(timezone.utc).date().isoformat()
        q: Dict[str, Any] = {
            "origin_state": origin_state.upper(),
            "destination_state": destination_state.upper(),
            "equipment": equipment, "active": True,
            "effective_from": {"$lte": today},
            "effective_to": {"$gte": today},
        }
        if customer_id:
            q["customer_id"] = customer_id
        contract = await db.orisei_contract_rates.find_one(q, {"_id": 0})
        return {
            "source": "contract" if contract else "spot",
            "contract_rate": contract,
            "note": "Contract rate found — honor first" if contract
                     else "No contract — quote spot market",
        }

    # ============================ F · DOCK SCHEDULING ============================
    @router.get("/dock-appointments")
    async def list_appointments(_=Depends(get_current_user)) -> Dict[str, Any]:
        rows = await db.orisei_dock_appointments.find(
            {}, {"_id": 0}).sort("scheduled_at", 1).to_list(500)
        return {"items": rows, "count": len(rows)}

    @router.post("/dock-appointments")
    async def create_appointment(payload: DockAppointmentIn, user=admin_dep) -> Dict[str, Any]:
        doc = {**payload.model_dump(),
                "appt_id": f"APPT-{uuid.uuid4().hex[:8].upper()}",
                "created_at": _now(),
                "created_by": getattr(user, "name", "system"),
                "status": "scheduled"}
        await db.orisei_dock_appointments.insert_one(dict(doc))
        doc.pop("_id", None)
        return doc

    @router.delete("/dock-appointments/{appt_id}")
    async def cancel_appointment(appt_id: str, user=admin_dep) -> Dict[str, str]:
        res = await db.orisei_dock_appointments.update_one(
            {"appt_id": appt_id}, {"$set": {"status": "cancelled",
                                              "cancelled_at": _now()}})
        if res.matched_count == 0:
            raise HTTPException(404, "Appointment not found")
        return {"status": "cancelled"}

    # ============================ G · MODE-SHIFT ============================
    @router.post("/mode-shift")
    async def mode_shift(payload: ModeShiftIn, _=Depends(get_current_user)) -> Dict[str, Any]:
        return _mode_shift_recommendation(payload)

    # ============================ I · FREIGHT AUDIT ============================
    @router.post("/freight-audit")
    async def freight_audit(payload: FreightAuditIn, user=admin_dep) -> Dict[str, Any]:
        booking = await db.brokerage_bookings.find_one(
            {"booked_id": payload.booking_id}, {"_id": 0})
        if not booking:
            booking = await db.brokerage_bookings.find_one(
                {"booking_id": payload.booking_id}, {"_id": 0})
        if not booking:
            raise HTTPException(404, "Booking not found")
        rate_con_amt = float(booking.get("carrier_rate_usd")
                              or booking.get("rate_usd")
                              or booking.get("settled_carrier_pay_usd")
                              or booking.get("forecast_carrier_pay_usd") or 0)
        accessorial_amt = sum(float(a.get("amount_usd") or 0)
                               for a in (payload.accessorial_breakdown or []))
        expected = rate_con_amt + accessorial_amt
        diff = round(payload.carrier_invoice_usd - expected, 2)
        flags = []
        if diff > expected * 0.05 and diff > 25:
            flags.append({"level": "red", "code": "OVER_BILL",
                           "msg": f"Carrier invoice exceeds rate-con by ${diff:.2f} ({diff/expected*100:.1f}%)"})
        if accessorial_amt > 0 and not payload.accessorial_breakdown:
            flags.append({"level": "amber", "code": "UNDOCUMENTED_ACCESSORIAL",
                           "msg": "Accessorials present but not itemized"})
        if rate_con_amt == 0:
            flags.append({"level": "red", "code": "NO_RATE_CON",
                           "msg": "No rate confirmation on file — cannot audit"})
        audit_doc = {
            "audit_id": f"AUD-{uuid.uuid4().hex[:10].upper()}",
            "booking_id": payload.booking_id,
            "rate_con_usd": rate_con_amt,
            "accessorial_usd": accessorial_amt,
            "expected_total_usd": expected,
            "carrier_invoice_usd": payload.carrier_invoice_usd,
            "diff_usd": diff,
            "verdict": "RED" if any(f["level"] == "red" for f in flags) else
                        ("AMBER" if flags else "GREEN"),
            "flags": flags,
            "audited_at": _now(),
            "audited_by": getattr(user, "name", "system"),
            "invoice_number": payload.invoice_number,
        }
        await db.orisei_freight_audits.insert_one(dict(audit_doc))
        audit_doc.pop("_id", None)
        return audit_doc

    @router.get("/freight-audits")
    async def list_audits(_=Depends(get_current_user)) -> Dict[str, Any]:
        rows = await db.orisei_freight_audits.find({}, {"_id": 0}).sort("audited_at", -1).limit(100).to_list(100)
        return {"items": rows, "count": len(rows)}

    # ============================ A · SPOT-QUOTE REQUESTS ============================
    @router.get("/spot-quote-requests")
    async def list_spot_quote_requests(status: Optional[str] = None,
                                          _=Depends(get_current_user)) -> Dict[str, Any]:
        q = {"status": status} if status else {}
        rows = await db.orisei_spot_quote_requests.find(q, {"_id": 0}).sort("submitted_at", -1).limit(200).to_list(200)
        return {"items": rows, "count": len(rows)}

    @router.post("/spot-quote-requests/{request_id}/quote")
    async def quote_spot_request(request_id: str, user=admin_dep) -> Dict[str, str]:
        res = await db.orisei_spot_quote_requests.update_one(
            {"request_id": request_id},
            {"$set": {"status": "quoted", "quoted_at": _now(),
                       "quoted_by": getattr(user, "name", "system")}})
        if res.matched_count == 0:
            raise HTTPException(404, "Request not found")
        return {"status": "quoted"}

    # ============================ J · PUBLIC RFP / DIGITAL RFQ ============================
    @router.get("/rfps")
    async def list_rfps(_=Depends(get_current_user)) -> Dict[str, Any]:
        rows = await db.orisei_rfps.find({}, {"_id": 0}).sort("submission_deadline", 1).to_list(200)
        return {"items": rows, "count": len(rows)}

    @router.post("/rfps")
    async def create_rfp(payload: RfpIn, user=admin_dep) -> Dict[str, Any]:
        doc = {**payload.model_dump(),
                "rfp_id": f"RFP-{uuid.uuid4().hex[:10].upper()}",
                "created_at": _now(),
                "created_by": getattr(user, "name", "system"),
                "status": "open", "bid_count": 0}
        await db.orisei_rfps.insert_one(dict(doc))
        doc.pop("_id", None)
        return doc

    @router.get("/rfps/{rfp_id}/bids")
    async def list_rfp_bids(rfp_id: str, _=Depends(get_current_user)) -> Dict[str, Any]:
        rows = await db.orisei_rfp_bids.find(
            {"rfp_id": rfp_id}, {"_id": 0}).sort("submitted_at", -1).to_list(100)
        return {"items": rows, "count": len(rows)}

    api_router.include_router(router)

    # ============================ PUBLIC SUBROUTES ============================
    # A · Public: shipper requests a spot quote from the customer portal
    @api_router.post("/public/customer-portal/{token}/spot-quote-request",
                       tags=["customer-portal", "public"])
    async def submit_spot_quote_request(token: str,
                                          payload: SpotQuoteRequestIn) -> Dict[str, Any]:
        tok = await db.orisei_customer_portal_tokens.find_one(
            {"token": token}, {"_id": 0})
        if not tok or tok.get("status") == "disabled":
            raise HTTPException(404, "Portal link not found or disabled")
        doc = {
            "request_id": f"SQR-{uuid.uuid4().hex[:10].upper()}",
            "submitted_at": _now(),
            "status": "open",
            "customer_id": tok["customer_id"],
            "customer_name": tok["customer_name"],
            "source": "customer_portal",
            **payload.model_dump(),
        }
        await db.orisei_spot_quote_requests.insert_one(dict(doc))
        # Best-effort: email Oliver immediately
        try:
            from .connections import get_connection_credentials
            creds = await get_connection_credentials(db, "resend")
            if creds and creds.get("api_key"):
                import resend as _r
                _r.api_key = creds["api_key"]
                from_email = creds.get("from_email") or "onboarding@resend.dev"
                _r.Emails.send({
                    "from": f"Orisei Portal <{from_email}>",
                    "to": ["oliver@oriseifreightsolutions.com"],
                    "subject": f"Spot quote request · {tok['customer_name']} · {payload.origin} → {payload.destination}",
                    "html": (f"<p>New spot quote from <b>{tok['customer_name']}</b>:</p>"
                              f"<ul><li>Lane: {payload.origin} → {payload.destination}</li>"
                              f"<li>Pickup: {payload.pickup_date or '—'}</li>"
                              f"<li>Equipment: {payload.equipment}</li>"
                              f"<li>Weight: {payload.weight_lbs or '—'} lbs</li>"
                              f"<li>Commodity: {payload.commodity or '—'}</li>"
                              f"</ul><p>{payload.notes or ''}</p>"),
                })
        except Exception as exc:                                      # noqa: BLE001
            logger.info("Portal spot quote: Resend not configured (%s)", exc)
        doc.pop("_id", None)
        return {"ok": True, "request_id": doc["request_id"],
                "status": "received", "expected_response_time_hours": 4}

    # J · Public: list open RFPs (carrier-facing)
    @api_router.get("/public/rfps", tags=["rfp", "public"])
    async def public_list_rfps() -> Dict[str, Any]:
        rows = await db.orisei_rfps.find(
            {"is_public": True, "status": "open"},
            {"_id": 0, "created_by": 0}
        ).sort("submission_deadline", 1).to_list(50)
        return {"items": rows, "count": len(rows)}

    @api_router.get("/public/rfps/{rfp_id}", tags=["rfp", "public"])
    async def public_get_rfp(rfp_id: str) -> Dict[str, Any]:
        doc = await db.orisei_rfps.find_one(
            {"rfp_id": rfp_id, "is_public": True}, {"_id": 0, "created_by": 0})
        if not doc:
            raise HTTPException(404, "RFP not found")
        return doc

    @api_router.post("/public/rfps/{rfp_id}/bid", tags=["rfp", "public"])
    async def public_submit_bid(rfp_id: str, payload: RfpBidIn,
                                  request: Request) -> Dict[str, Any]:
        # Minimal abuse protection: per-IP throttle (5 bids / hour)
        client_ip = (request.headers.get("x-forwarded-for", "").split(",")[0].strip()
                       or (request.client.host if request.client else "anon"))
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        recent = await db.orisei_rfp_bids.count_documents(
            {"submitted_from_ip": client_ip, "submitted_at": {"$gte": cutoff}})
        if recent >= 5:
            raise HTTPException(429, "Too many bids from this IP. Please wait.")
        rfp = await db.orisei_rfps.find_one(
            {"rfp_id": rfp_id, "is_public": True}, {"_id": 0})
        if not rfp:
            raise HTTPException(404, "RFP not found")
        if rfp.get("status") != "open":
            raise HTTPException(410, "RFP closed")
        doc = {
            "bid_id": f"BID-{uuid.uuid4().hex[:10].upper()}",
            "rfp_id": rfp_id, "submitted_at": _now(),
            "status": "submitted",
            "submitted_from_ip": client_ip,
            **payload.model_dump(),
        }
        await db.orisei_rfp_bids.insert_one(dict(doc))
        await db.orisei_rfps.update_one({"rfp_id": rfp_id},
            {"$inc": {"bid_count": 1}})
        doc.pop("_id", None)
        return {"ok": True, "bid_id": doc["bid_id"]}

    # ============================ H · ADMIN-SIDE DRIVER PIN ============================
    class DriverPinIn(BaseModel):
        driver_name: Optional[str] = None
        driver_phone: Optional[str] = None

    @api_router.post("/brokerage/bookings/{booking_id}/driver-pin",
                       tags=["driver-pwa", "admin"])
    async def set_driver_pin(booking_id: str, payload: DriverPinIn,
                                 user=admin_dep) -> Dict[str, Any]:
        """Generate a 4-digit driver PIN + text-ready PWA link for a booking."""
        pin = f"{int.from_bytes(uuid.uuid4().bytes[:2], 'big') % 10000:04d}"
        res = await db.brokerage_bookings.find_one_and_update(
            {"$or": [{"booked_id": booking_id}, {"booking_id": booking_id}]},
            {"$set": {"driver_pin": pin,
                       "driver_name": payload.driver_name,
                       "driver_phone": payload.driver_phone,
                       "driver_pin_issued_at": _now()}},
            projection={"_id": 0, "booked_id": 1, "booking_id": 1})
        if not res:
            raise HTTPException(404, "Booking not found")
        return {
            "ok": True, "pin": pin, "booking_id": booking_id,
            "driver_url_template": "/driver?booking={booking_id}&pin={pin}",
        }


# ============================ H · DRIVER PWA ============================
class DriverStatusUpdate(BaseModel):
    booking_id: str
    status: str       # arrived_pickup | loaded | enroute | arrived_delivery | delivered
    notes: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None


def build_driver_pwa_router(
    api_router: APIRouter, *, db, get_current_user: Callable,
) -> None:
    """H · Lightweight driver-status update endpoints. Driver auth = booking
    ID + 4-digit PIN (stored on the booking when tendered)."""
    router = APIRouter(prefix="/driver-pwa", tags=["driver-pwa"])

    @router.get("/booking/{booking_id}")
    async def driver_get_booking(booking_id: str, pin: str = Query(...,
                                   min_length=4, max_length=8)) -> Dict[str, Any]:
        booking = await db.brokerage_bookings.find_one(
            {"booked_id": booking_id, "driver_pin": pin}, {"_id": 0})
        if not booking:
            booking = await db.brokerage_bookings.find_one(
                {"booking_id": booking_id, "driver_pin": pin}, {"_id": 0})
        if not booking:
            raise HTTPException(404, "Invalid booking or PIN")
        return booking

    @router.post("/status")
    async def driver_update_status(payload: DriverStatusUpdate,
                                      pin: str = Query(..., min_length=4)) -> Dict[str, Any]:
        booking = await db.brokerage_bookings.find_one_and_update(
            {"$or": [{"booked_id": payload.booking_id, "driver_pin": pin},
                     {"booking_id": payload.booking_id, "driver_pin": pin}]},
            {"$set": {"status": payload.status,
                       f"{payload.status}_at": _now(),
                       "last_driver_update_at": _now(),
                       "last_driver_location": ({"lat": payload.lat, "lng": payload.lng}
                                                  if payload.lat and payload.lng else None)},
             "$push": {"driver_updates": {
                 "status": payload.status, "notes": payload.notes,
                 "at": _now(),
                 "location": ({"lat": payload.lat, "lng": payload.lng}
                                if payload.lat and payload.lng else None)}}},
            return_document=False,
            projection={"_id": 0})
        if not booking:
            raise HTTPException(404, "Invalid booking or PIN")
        return {"ok": True, "status": payload.status, "at": _now()}

    api_router.include_router(router)
