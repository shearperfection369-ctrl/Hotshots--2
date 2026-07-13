"""routes.ltl_rate_cards — Negotiated LTL rate-card engine.

Stores each carrier's negotiated tariff (discount off base, FSC, minimum
charge, zone-based CWT rates by weight break) and rates any LTL shipment
against every active card in one call — returning ranked net quotes with
automatic margin math so the broker knows sell price and margin BEFORE
booking.

Rating model (industry-standard CzarLite-style):
  gross = base_rate_cwt(zone, weight_break) × class_multiplier × CWT
  net   = max(min_charge, gross × (1 − discount)) × (1 + FSC) + accessorials

Zones derive from origin/dest state-centroid distance bands.
Endpoints — /api/ltl/*
"""
from __future__ import annotations

import logging
import math
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger("orisei.ltl_rates")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# State centroids for zone math (lat, lng)
STATE_CENTROIDS: Dict[str, tuple] = {
    "AL": (32.7, -86.8), "AZ": (34.2, -111.6), "AR": (34.8, -92.4), "CA": (37.2, -119.3),
    "CO": (39.0, -105.5), "CT": (41.6, -72.7), "DE": (39.0, -75.5), "FL": (28.6, -82.4),
    "GA": (32.6, -83.4), "ID": (44.4, -114.6), "IL": (40.0, -89.2), "IN": (39.9, -86.3),
    "IA": (42.0, -93.5), "KS": (38.5, -98.4), "KY": (37.5, -85.3), "LA": (31.0, -92.0),
    "ME": (45.4, -69.2), "MD": (39.0, -76.8), "MA": (42.3, -71.8), "MI": (44.3, -85.4),
    "MN": (46.3, -94.3), "MS": (32.7, -89.7), "MO": (38.4, -92.5), "MT": (47.0, -109.6),
    "NE": (41.5, -99.8), "NV": (39.3, -116.6), "NH": (43.7, -71.6), "NJ": (40.2, -74.7),
    "NM": (34.4, -106.1), "NY": (42.9, -75.5), "NC": (35.5, -79.4), "ND": (47.4, -100.5),
    "OH": (40.3, -82.8), "OK": (35.6, -97.5), "OR": (43.9, -120.6), "PA": (40.9, -77.8),
    "RI": (41.7, -71.6), "SC": (33.9, -80.9), "SD": (44.4, -100.2), "TN": (35.9, -86.4),
    "TX": (31.5, -99.3), "UT": (39.3, -111.7), "VT": (44.1, -72.7), "VA": (37.5, -78.9),
    "WA": (47.4, -120.5), "WV": (38.6, -80.6), "WI": (44.6, -89.9), "WY": (43.0, -107.6),
}

# NMFC class multipliers (relative to class 50)
CLASS_MULT: Dict[str, float] = {
    "50": 1.00, "55": 1.11, "60": 1.22, "65": 1.33, "70": 1.45, "77.5": 1.58,
    "85": 1.74, "92.5": 1.90, "100": 2.06, "110": 2.27, "125": 2.50, "150": 2.90,
    "175": 3.30, "200": 3.70, "250": 4.50, "300": 5.30, "400": 6.70, "500": 8.10,
}

WEIGHT_BREAKS = ["L5C", "5C", "1M", "2M", "5M", "10M"]  # <500, 500+, 1000+, 2000+, 5000+, 10000+

# Base class-50 rate per CWT by zone (1..6) and weight break. Higher zones =
# longer haul = higher rate; heavier breaks = lower per-CWT rate.
BASE_RATES: Dict[int, Dict[str, float]] = {
    1: {"L5C": 38.0, "5C": 32.0, "1M": 27.5, "2M": 23.0, "5M": 19.5, "10M": 16.5},
    2: {"L5C": 52.0, "5C": 44.0, "1M": 38.0, "2M": 32.0, "5M": 27.0, "10M": 23.0},
    3: {"L5C": 68.0, "5C": 58.0, "1M": 50.0, "2M": 42.0, "5M": 35.5, "10M": 30.0},
    4: {"L5C": 88.0, "5C": 75.0, "1M": 65.0, "2M": 54.5, "5M": 46.0, "10M": 39.0},
    5: {"L5C": 112.0, "5C": 95.0, "1M": 82.0, "2M": 69.0, "5M": 58.0, "10M": 49.0},
    6: {"L5C": 138.0, "5C": 118.0, "1M": 102.0, "2M": 86.0, "5M": 72.0, "10M": 61.0},
}

ACCESSORIAL_DEFAULTS: Dict[str, float] = {
    "liftgate_pickup": 75.0, "liftgate_delivery": 85.0, "residential": 95.0,
    "inside_delivery": 110.0, "limited_access": 90.0, "appointment": 35.0,
    "hazmat": 55.0, "protect_from_freeze": 45.0,
}

# Seed: realistic negotiated cards for the carriers the operator runs
CARD_SEED: List[Dict[str, Any]] = [
    {"carrier_name": "R+L Carriers",      "scac": "RLCA", "discount_pct": 72.0, "fsc_pct": 30.5, "min_charge_usd": 128.0, "base_factor": 1.00, "transit_note": "Strong Midwest/Southeast · direct MN coverage"},
    {"carrier_name": "SAIA LTL Freight",  "scac": "SAIA", "discount_pct": 74.0, "fsc_pct": 29.5, "min_charge_usd": 135.0, "base_factor": 1.03, "transit_note": "National · aggressive on 1M+ shipments"},
    {"carrier_name": "Dayton Freight",    "scac": "DYLT", "discount_pct": 70.0, "fsc_pct": 28.9, "min_charge_usd": 118.0, "base_factor": 0.96, "transit_note": "Midwest specialist · best MSP–Chicago corridor"},
    {"carrier_name": "Old Dominion",      "scac": "ODFL", "discount_pct": 68.0, "fsc_pct": 31.5, "min_charge_usd": 152.0, "base_factor": 1.08, "transit_note": "Premium service · lowest claims ratio"},
    {"carrier_name": "XPO Logistics",     "scac": "CNWY", "discount_pct": 76.0, "fsc_pct": 30.9, "min_charge_usd": 130.0, "base_factor": 1.02, "transit_note": "National · deep discount on long haul"},
    {"carrier_name": "Estes Express",     "scac": "EXLA", "discount_pct": 73.0, "fsc_pct": 29.9, "min_charge_usd": 125.0, "base_factor": 0.99, "transit_note": "Southeast strength · flexible accessorials"},
]


class CardIn(BaseModel):
    card_id: Optional[str] = None
    carrier_name: str = Field(..., max_length=120)
    scac: str = Field(..., max_length=8)
    discount_pct: float = Field(..., ge=0, le=95)
    fsc_pct: float = Field(..., ge=0, le=80)
    min_charge_usd: float = Field(..., ge=0)
    base_factor: float = Field(1.0, ge=0.5, le=2.0)
    accessorials: Optional[Dict[str, float]] = None
    effective_date: Optional[str] = None
    expires_date: Optional[str] = None
    active: bool = True
    transit_note: Optional[str] = Field(None, max_length=300)


class QuoteIn(BaseModel):
    origin_state: str = Field(..., min_length=2, max_length=2)
    dest_state: str = Field(..., min_length=2, max_length=2)
    weight_lbs: float = Field(..., gt=0, le=20000)
    freight_class: str = Field("70")
    accessorials: List[str] = []
    sell_rate_usd: Optional[float] = Field(None, ge=0)
    target_margin_pct: float = Field(22.0, ge=0, le=60)


def _haversine_mi(a: tuple, b: tuple) -> float:
    r = 3958.8
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp, dl = math.radians(b[0] - a[0]), math.radians(b[1] - a[1])
    x = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(x))


def _zone(o: str, d: str) -> Dict[str, Any]:
    co, cd = STATE_CENTROIDS.get(o.upper()), STATE_CENTROIDS.get(d.upper())
    if not co or not cd:
        raise HTTPException(400, f"Unknown state code: {o if not co else d}")
    miles = _haversine_mi(co, cd)
    if miles < 250: z = 1
    elif miles < 500: z = 2
    elif miles < 800: z = 3
    elif miles < 1200: z = 4
    elif miles < 1800: z = 5
    else: z = 6
    return {"zone": z, "linehaul_miles_est": round(miles)}


def _weight_break(lbs: float) -> str:
    if lbs < 500: return "L5C"
    if lbs < 1000: return "5C"
    if lbs < 2000: return "1M"
    if lbs < 5000: return "2M"
    if lbs < 10000: return "5M"
    return "10M"


def _rate_card(card: Dict[str, Any], q: QuoteIn, zone: int) -> Dict[str, Any]:
    wb = _weight_break(q.weight_lbs)
    cls_mult = CLASS_MULT.get(str(q.freight_class))
    if cls_mult is None:
        raise HTTPException(400, f"Unknown freight class {q.freight_class}. Valid: {list(CLASS_MULT)}")
    cwt = q.weight_lbs / 100.0
    base_cwt = BASE_RATES[zone][wb] * float(card.get("base_factor") or 1.0)
    gross = base_cwt * cls_mult * cwt
    discount = float(card["discount_pct"]) / 100.0
    net_linehaul = max(float(card["min_charge_usd"]), gross * (1 - discount))
    fsc_usd = net_linehaul * float(card["fsc_pct"]) / 100.0
    acc_map = {**ACCESSORIAL_DEFAULTS, **(card.get("accessorials") or {})}
    acc_lines = [{"code": a, "amount_usd": round(acc_map.get(a, 0.0), 2)}
                 for a in q.accessorials if a in acc_map]
    acc_total = sum(x["amount_usd"] for x in acc_lines)
    net_total = round(net_linehaul + fsc_usd + acc_total, 2)

    sell = q.sell_rate_usd if q.sell_rate_usd else round(net_total / (1 - q.target_margin_pct / 100.0), 2)
    margin_usd = round(sell - net_total, 2)
    margin_pct = round(margin_usd / sell * 100, 1) if sell else 0.0
    return {
        "carrier_name": card["carrier_name"], "scac": card["scac"],
        "card_id": card.get("card_id"),
        "weight_break": wb, "freight_class": q.freight_class,
        "base_rate_cwt": round(base_cwt, 2), "gross_usd": round(gross, 2),
        "discount_pct": card["discount_pct"],
        "net_linehaul_usd": round(net_linehaul, 2),
        "min_charge_applied": gross * (1 - discount) < float(card["min_charge_usd"]),
        "fsc_pct": card["fsc_pct"], "fsc_usd": round(fsc_usd, 2),
        "accessorial_lines": acc_lines, "accessorials_usd": round(acc_total, 2),
        "net_total_usd": net_total,
        "suggested_sell_usd": sell, "margin_usd": margin_usd, "margin_pct": margin_pct,
        "transit_note": card.get("transit_note"),
    }


def build_ltl_rate_router(
    *, api_router: APIRouter, db,
    get_current_user: Callable, require_role: Callable,
) -> None:
    router = APIRouter(prefix="/ltl", tags=["ltl-rate-cards"])

    async def _cards(active_only: bool = False) -> List[Dict[str, Any]]:
        q = {"active": True} if active_only else {}
        rows = await db.ltl_rate_cards.find(q, {"_id": 0}).to_list(100)
        if not rows and not active_only:
            seeded = []
            for c in CARD_SEED:
                seeded.append({**c, "card_id": f"RC-{uuid.uuid4().hex[:8].upper()}",
                               "accessorials": dict(ACCESSORIAL_DEFAULTS),
                               "active": True, "effective_date": _now_iso()[:10],
                               "expires_date": None, "created_at": _now_iso()})
            await db.ltl_rate_cards.insert_many([dict(x) for x in seeded])
            rows = seeded
        return rows

    @router.get("/cards")
    async def list_cards(_=Depends(get_current_user)) -> Dict[str, Any]:
        rows = await _cards()
        return {"items": rows, "count": len(rows),
                "weight_breaks": WEIGHT_BREAKS, "classes": list(CLASS_MULT),
                "accessorial_codes": list(ACCESSORIAL_DEFAULTS)}

    @router.post("/cards")
    async def upsert_card(payload: CardIn,
                          user=Depends(require_role("admin", "dispatcher"))) -> Dict[str, Any]:
        doc = payload.model_dump()
        doc["card_id"] = doc.get("card_id") or f"RC-{uuid.uuid4().hex[:8].upper()}"
        doc["accessorials"] = doc.get("accessorials") or dict(ACCESSORIAL_DEFAULTS)
        doc["updated_at"] = _now_iso()
        doc["updated_by"] = getattr(user, "user_id", None)
        await db.ltl_rate_cards.update_one({"card_id": doc["card_id"]},
                                           {"$set": doc}, upsert=True)
        return {"ok": True, **doc}

    @router.delete("/cards/{card_id}")
    async def retire_card(card_id: str,
                          _=Depends(require_role("admin", "dispatcher"))) -> Dict[str, Any]:
        r = await db.ltl_rate_cards.update_one(
            {"card_id": card_id}, {"$set": {"active": False, "updated_at": _now_iso()}})
        if not r.matched_count:
            raise HTTPException(404, "Card not found")
        return {"ok": True}

    @router.post("/quote")
    async def quote(payload: QuoteIn, user=Depends(get_current_user)) -> Dict[str, Any]:
        """Rate the shipment against every active negotiated card, ranked
        cheapest-first, with sell price + margin computed per carrier."""
        z = _zone(payload.origin_state, payload.dest_state)
        cards = await _cards(active_only=True) or await _cards()
        quotes = [_rate_card(c, payload, z["zone"]) for c in cards if c.get("active", True)]
        quotes.sort(key=lambda x: x["net_total_usd"])
        if quotes:
            quotes[0]["cheapest"] = True
        result = {
            "quote_id": f"LQ-{uuid.uuid4().hex[:8].upper()}",
            "lane": f"{payload.origin_state.upper()} → {payload.dest_state.upper()}",
            **z, "weight_lbs": payload.weight_lbs,
            "freight_class": payload.freight_class,
            "accessorials": payload.accessorials,
            "target_margin_pct": payload.target_margin_pct,
            "sell_rate_usd": payload.sell_rate_usd,
            "quotes": quotes, "carrier_count": len(quotes),
            "quoted_at": _now_iso(),
            "quoted_by": getattr(user, "user_id", None),
        }
        await db.ltl_quotes.insert_one(dict(result))
        return result

    @router.get("/quotes")
    async def quote_history(limit: int = 25, _=Depends(get_current_user)) -> Dict[str, Any]:
        rows = await db.ltl_quotes.find({}, {"_id": 0}).sort("quoted_at", -1).to_list(min(limit, 100))
        return {"items": rows, "count": len(rows)}

    api_router.include_router(router)
    logger.info("LTL rate-card router registered (/api/ltl)")
