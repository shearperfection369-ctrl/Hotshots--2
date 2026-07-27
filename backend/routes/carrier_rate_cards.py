"""routes.carrier_rate_cards — pre-negotiated carrier lane rates.

The margin moat: contracted carrier costs per lane feed First Strike's
bid math so every strike bid is priced off YOUR real cost, with a hard
margin floor — not off spot-market guesswork.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

EQUIPMENT = ["Van", "Reefer", "Flatbed", "Any"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _card_cost(card: Dict[str, Any], miles: float) -> Optional[float]:
    if card.get("rate_type") == "per_mile":
        rpm = float(card.get("rpm_usd") or 0)
        return round(rpm * miles, 2) if rpm and miles else None
    rate = float(card.get("rate_usd") or 0)
    return rate or None


def _is_live(card: Dict[str, Any]) -> bool:
    if not card.get("active", True):
        return False
    vu = card.get("valid_until") or ""
    return not vu or vu >= _today()


async def load_active_rate_cards(db) -> List[Dict[str, Any]]:
    rows = await db.carrier_lane_rate_cards.find({}, {"_id": 0}).to_list(500)
    return [r for r in rows if _is_live(r)]


def best_contract_for(cards: List[Dict[str, Any]], lane_key: str,
                      equipment: str, miles: float) -> Optional[Dict[str, Any]]:
    """Cheapest live contracted cost for a lane+equipment, or None."""
    best = None
    for c in cards:
        if c.get("lane_key") != lane_key:
            continue
        if c.get("equipment") not in ("Any", equipment):
            continue
        cost = _card_cost(c, miles)
        if cost is None:
            continue
        if best is None or cost < best["contract_cost_usd"]:
            best = {"contract_cost_usd": cost, "contract_carrier": c.get("carrier_name"),
                    "contract_mc": c.get("carrier_mc") or None, "contract_card_id": c.get("id")}
    return best


class RateCardIn(BaseModel):
    carrier_name: str = Field(..., min_length=1, max_length=160)
    carrier_mc: str = ""
    origin: str = Field(..., min_length=2)        # "Minneapolis, MN"
    destination: str = Field(..., min_length=2)   # "Chicago, IL"
    equipment: str = "Van"
    rate_type: str = "flat"                       # flat | per_mile
    rate_usd: float = Field(0, ge=0)
    rpm_usd: float = Field(0, ge=0)
    valid_until: str = ""                         # ISO date or "" = evergreen
    loads_per_week: int = Field(0, ge=0, le=200)  # committed capacity
    notes: str = ""


class RateCardPatch(BaseModel):
    active: Optional[bool] = None
    rate_usd: Optional[float] = None
    rpm_usd: Optional[float] = None
    valid_until: Optional[str] = None
    loads_per_week: Optional[int] = None
    notes: Optional[str] = None


def _lane_key_of(origin: str, destination: str) -> str:
    return f"{origin.strip()[-2:].upper()}-{destination.strip()[-2:].upper()}"


def build_rate_cards_router(*, db, get_current_user: Callable) -> APIRouter:
    router = APIRouter(prefix="/carrier-rate-cards", tags=["carrier-rate-cards"])

    @router.get("")
    async def list_cards(_=Depends(get_current_user)) -> Dict[str, Any]:
        rows = await db.carrier_lane_rate_cards.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
        # utilization: loads booked against each card since Monday
        now = datetime.now(timezone.utc)
        week_start = (now - timedelta(days=now.weekday())).date().isoformat()
        pipe = [{"$match": {"rate_card_id": {"$ne": None}, "booked_at": {"$gte": week_start}}},
                {"$group": {"_id": "$rate_card_id", "n": {"$sum": 1}}}]
        moved = {r["_id"]: r["n"] async for r in db.brokerage_bookings.aggregate(pipe)}
        total_moved = 0
        for r in rows:
            r["live"] = _is_live(r)
            r["moved_this_week"] = int(moved.get(r["id"], 0))
            total_moved += r["moved_this_week"]
            committed = int(r.get("loads_per_week") or 0)
            r["utilization_pct"] = round(r["moved_this_week"] / committed * 100) if committed else None
        live = [r for r in rows if r["live"]]
        return {"cards": rows, "count": len(rows), "live_count": len(live),
                "lanes_covered": len({r["lane_key"] for r in live}),
                "weekly_capacity_committed": sum(int(r.get("loads_per_week") or 0) for r in live),
                "moved_this_week_total": total_moved, "week_start": week_start}

    @router.post("")
    async def create_card(payload: RateCardIn, _=Depends(get_current_user)) -> Dict[str, Any]:
        if payload.equipment not in EQUIPMENT:
            raise HTTPException(400, f"equipment must be one of {EQUIPMENT}")
        if payload.rate_type not in ("flat", "per_mile"):
            raise HTTPException(400, "rate_type must be flat or per_mile")
        if payload.rate_type == "flat" and payload.rate_usd <= 0:
            raise HTTPException(400, "rate_usd required for flat cards")
        if payload.rate_type == "per_mile" and payload.rpm_usd <= 0:
            raise HTTPException(400, "rpm_usd required for per-mile cards")
        doc = {**payload.model_dump(), "id": f"RC-{uuid.uuid4().hex[:8].upper()}",
               "lane_key": _lane_key_of(payload.origin, payload.destination),
               "active": True, "is_sample": False,
               "created_at": _now_iso(), "updated_at": _now_iso()}
        await db.carrier_lane_rate_cards.insert_one(dict(doc))
        return {"ok": True, "card": doc}

    @router.patch("/{cid}")
    async def patch_card(cid: str, payload: RateCardPatch, _=Depends(get_current_user)) -> Dict[str, Any]:
        patch = payload.model_dump(exclude_unset=True)
        if not patch:
            raise HTTPException(400, "Nothing to update")
        patch["updated_at"] = _now_iso()
        r = await db.carrier_lane_rate_cards.find_one_and_update(
            {"id": cid}, {"$set": patch}, return_document=True, projection={"_id": 0})
        if not r:
            raise HTTPException(404, "Rate card not found")
        return {"ok": True, "card": r}

    @router.delete("/{cid}")
    async def delete_card(cid: str, _=Depends(get_current_user)) -> Dict[str, Any]:
        r = await db.carrier_lane_rate_cards.delete_one({"id": cid})
        if r.deleted_count == 0:
            raise HTTPException(404, "Rate card not found")
        return {"ok": True}

    return router
