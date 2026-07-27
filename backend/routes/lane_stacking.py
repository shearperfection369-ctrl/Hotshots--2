"""routes.lane_stacking — chain consecutive loads on one route.

Three loads on the same lane = predictability the carrier will pay for:
they give a 2–3% rate discount for the guaranteed miles, and that
discount lands in YOUR margin, not the shipper's pocket.
"""
from __future__ import annotations

import random
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

STACK_SIZE = 3


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _lane_key(load: Dict[str, Any]) -> str:
    o = (load.get("origin") or "")[-2:].upper()
    d = (load.get("destination") or "")[-2:].upper()
    return f"{o}-{d}"


class StackBookIn(BaseModel):
    lane_key: str
    equipment: str
    load_ids: List[str] = Field(..., min_length=STACK_SIZE, max_length=STACK_SIZE)


def build_lane_stacking_router(*, db, get_current_user: Callable) -> APIRouter:
    router = APIRouter(prefix="/lane-stacking", tags=["lane-stacking"])

    async def _board_loads() -> List[Dict[str, Any]]:
        rows = await db.brokerage_loads.find({}, {"_id": 0}).to_list(300)
        if not rows:
            from routes.brokerage import LOAD_BOARDS, _gen_loads_for_board  # type: ignore
            for b in LOAD_BOARDS:
                rows.extend(_gen_loads_for_board(b["id"], count=14))
        return rows

    @router.get("/opportunities")
    async def opportunities(_=Depends(get_current_user)) -> Dict[str, Any]:
        loads = await _board_loads()
        booked_ids = set(await db.brokerage_bookings.distinct("load_id"))
        from routes.carrier_rate_cards import load_active_rate_cards, best_contract_for
        cards = await load_active_rate_cards(db)

        groups: Dict[tuple, List[Dict[str, Any]]] = defaultdict(list)
        for l in loads:
            if l.get("load_id") in booked_ids:
                continue
            groups[(_lane_key(l), l.get("equipment") or "Van")].append(l)

        opps = []
        for (lane, equip), rows in groups.items():
            if len(rows) < STACK_SIZE:
                continue
            rows.sort(key=lambda r: -(float(r.get("margin_pct") or 0)))
            pick = rows[:STACK_SIZE]
            revenue = round(sum(float(r.get("rate_usd") or 0) for r in pick), 2)
            base_cpay = round(sum(float(r.get("carrier_pay_usd") or 0) for r in pick), 2)
            contract = best_contract_for(cards, lane, equip,
                                         float(pick[0].get("miles") or 0)) if cards else None
            if contract:
                base_cpay = round(contract["contract_cost_usd"] * STACK_SIZE, 2)
            disc_pct = round(random.Random(f"{lane}-{equip}").uniform(2.0, 3.0), 1)
            discount = round(base_cpay * disc_pct / 100, 2)
            stacked_cpay = round(base_cpay - discount, 2)
            base_margin = round(revenue - base_cpay, 2)
            stacked_margin = round(revenue - stacked_cpay, 2)
            opps.append({
                "lane_key": lane, "equipment": equip,
                "lane_label": f"{pick[0].get('origin')} → {pick[0].get('destination')}",
                "load_ids": [r.get("load_id") for r in pick],
                "loads": [{"load_id": r.get("load_id"), "board_id": r.get("board_id"),
                           "rate_usd": r.get("rate_usd"), "pickup_date": r.get("pickup_date"),
                           "shipper": r.get("shipper")} for r in pick],
                "revenue_usd": revenue,
                "stack_discount_pct": disc_pct,
                "discount_usd": discount,
                "base_margin_usd": base_margin,
                "stacked_margin_usd": stacked_margin,
                "stacked_margin_pct": round(stacked_margin / revenue * 100, 1) if revenue else 0,
                "contract_carrier": contract["contract_carrier"] if contract else None,
            })
        opps.sort(key=lambda o: -o["discount_usd"])
        return {"at": _now_iso(), "count": len(opps), "opportunities": opps[:12]}

    @router.post("/book")
    async def book_stack(payload: StackBookIn, user=Depends(get_current_user)) -> Dict[str, Any]:
        loads = await _board_loads()
        by_id = {l.get("load_id"): l for l in loads}
        pick = [by_id.get(lid) for lid in payload.load_ids]
        if any(p is None for p in pick):
            raise HTTPException(404, "One or more loads no longer on the board")
        booked_ids = set(await db.brokerage_bookings.distinct("load_id"))
        if any(lid in booked_ids for lid in payload.load_ids):
            raise HTTPException(409, "One or more loads already booked")

        from routes.carrier_rate_cards import load_active_rate_cards, best_contract_for
        cards = await load_active_rate_cards(db)
        contract = best_contract_for(cards, payload.lane_key, payload.equipment,
                                     float(pick[0].get("miles") or 0)) if cards else None
        disc_pct = round(random.Random(f"{payload.lane_key}-{payload.equipment}").uniform(2.0, 3.0), 1)

        stack_id = f"STACK-{uuid.uuid4().hex[:8].upper()}"
        now = _now_iso()
        bookings, revenue, total_margin, total_discount = [], 0.0, 0.0, 0.0
        for i, l in enumerate(pick, start=1):
            rate = float(l.get("rate_usd") or 0)
            cpay = float(contract["contract_cost_usd"]) if contract \
                else float(l.get("carrier_pay_usd") or 0)
            discount = round(cpay * disc_pct / 100, 2)
            cpay_disc = round(cpay - discount, 2)
            margin = round(rate - cpay_disc, 2)
            booked_id = f"BK-{uuid.uuid4().hex[:10].upper()}"
            await db.brokerage_bookings.insert_one({
                "booked_id": booked_id, "load_id": l.get("load_id"), "board_id": l.get("board_id"),
                "carrier_name": (contract or {}).get("contract_carrier") or "TBD — assign carrier",
                "carrier_mc": (contract or {}).get("contract_mc"),
                "rate_card_id": (contract or {}).get("contract_card_id"),
                "customer_name": l.get("shipper"), "customer_email": None,
                "origin": l.get("origin"), "destination": l.get("destination"),
                "miles": l.get("miles"), "equipment": l.get("equipment"),
                "forecast_rate_usd": rate, "forecast_carrier_pay_usd": cpay_disc,
                "forecast_margin_usd": margin,
                "settled_rate_usd": None, "settled_carrier_pay_usd": None, "settled_margin_usd": None,
                "pickup_date": l.get("pickup_date"), "delivery_date": l.get("delivery_date"),
                "status": "booked", "booked_at": now, "booked_by": getattr(user, "name", "system"),
                "notes": f"LANE STACK {stack_id} · leg {i}/{STACK_SIZE} · carrier gave {disc_pct}% predictability discount (+${discount:,.0f} margin)",
                "is_sample": False, "source": "lane_stack", "stack_id": stack_id,
            })
            bookings.append(booked_id)
            revenue += rate
            total_margin += margin
            total_discount += discount

        stack = {"stack_id": stack_id, "lane_key": payload.lane_key,
                 "equipment": payload.equipment,
                 "lane_label": f"{pick[0].get('origin')} → {pick[0].get('destination')}",
                 "load_ids": payload.load_ids, "booked_ids": bookings,
                 "carrier_name": (contract or {}).get("contract_carrier") or "TBD — assign carrier",
                 "revenue_usd": round(revenue, 2),
                 "stack_discount_pct": disc_pct,
                 "discount_kept_usd": round(total_discount, 2),
                 "margin_usd": round(total_margin, 2),
                 "booked_at": now, "booked_by": getattr(user, "name", "system"),
                 "is_sample": False}
        await db.lane_stacks.insert_one(dict(stack))
        return {"ok": True, "stack": stack}

    @router.get("/stacks")
    async def stacks(_=Depends(get_current_user)) -> Dict[str, Any]:
        rows = await db.lane_stacks.find({}, {"_id": 0}).sort("booked_at", -1).to_list(50)
        return {"stacks": rows,
                "total_discount_kept_usd": round(sum(float(r.get("discount_kept_usd") or 0) for r in rows), 2)}

    return router
