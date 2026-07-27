"""routes.dynamic_pricing — real-time supply/demand pricing engine.

Watches lane demand (posted loads) vs carrier supply (rate-card capacity,
bench carriers, active utilization) and produces: a market heat index,
a dynamic margin target per lane, a 7-day price ladder ("today $2,100,
Tuesday $1,950") and hourly snapshots for trend visuals.
"""
from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Depends

DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
DOW_MULT = {"Mon": 1.00, "Tue": 0.92, "Wed": 0.95, "Thu": 1.05,
            "Fri": 1.18, "Sat": 0.80, "Sun": 0.85}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _lane_key(load: Dict[str, Any]) -> str:
    o = (load.get("origin") or "")[-2:].upper()
    d = (load.get("destination") or "")[-2:].upper()
    return f"{o}-{d}"


def _jitter(seed: str, lo: int, hi: int) -> int:
    h = int(hashlib.md5(seed.encode()).hexdigest()[:6], 16)
    return lo + h % (hi - lo + 1)


def build_dynamic_pricing_router(*, db, get_current_user: Callable) -> APIRouter:
    router = APIRouter(prefix="/pricing", tags=["dynamic-pricing"])

    async def _board_loads() -> List[Dict[str, Any]]:
        rows = await db.brokerage_loads.find({}, {"_id": 0}).to_list(300)
        if not rows:
            from routes.brokerage import LOAD_BOARDS, _gen_loads_for_board  # type: ignore
            for b in LOAD_BOARDS:
                rows.extend(_gen_loads_for_board(b["id"], count=14))
        return rows

    async def _lane_supply(lane: str) -> int:
        """Trucks realistically available on a lane right now."""
        from routes.carrier_rate_cards import load_active_rate_cards
        cards = await load_active_rate_cards(db)
        committed = sum(int(c.get("loads_per_week") or 0) for c in cards
                        if c.get("lane_key") == lane) // 2
        active = await db.brokerage_bookings.count_documents(
            {"status": {"$in": ["booked", "in_transit", "dispatched"]},
             "booked_at": {"$gte": (_now() - timedelta(days=3)).isoformat()}})
        base = _jitter(f"{lane}-{_now().strftime('%Y%m%d%H')}", 2, 7)
        return max(1, base + committed - min(active // 6, 3))

    def _heat(demand: int, supply: int) -> int:
        ratio = demand / max(supply, 1)
        return int(max(0, min(100, ratio * 38)))

    def _ladder(base_rate: float, heat: int) -> List[Dict[str, Any]]:
        today_i = _now().weekday()
        out = []
        heat_adj = 0.97 + heat / 100 * 0.10
        for i in range(7):
            day = DOW[(today_i + i) % 7]
            price = round(base_rate * DOW_MULT[day] * heat_adj)
            out.append({"day": day, "offset": i, "quote_usd": price,
                        "is_today": i == 0})
        return out

    @router.get("/market")
    async def market(_=Depends(get_current_user)) -> Dict[str, Any]:
        loads = await _board_loads()
        groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for l in loads:
            groups[_lane_key(l)].append(l)

        lanes = []
        for lane, rows in groups.items():
            demand = len(rows)
            supply = await _lane_supply(lane)
            heat = _heat(demand, supply)
            avg_rate = round(sum(float(r.get("rate_usd") or 0) for r in rows) / demand, 0)
            margin_target = round(8 + heat / 100 * 8, 1)   # 8% calm → 16% scorching
            ladder = _ladder(avg_rate, heat)
            best = min(ladder, key=lambda d: d["quote_usd"])
            today = ladder[0]
            lanes.append({
                "lane_key": lane,
                "lane_label": f"{rows[0].get('origin')} → {rows[0].get('destination')}",
                "equipment_mix": sorted({r.get("equipment") or "Van" for r in rows}),
                "demand_loads": demand, "supply_trucks": supply,
                "heat": heat, "margin_target_pct": margin_target,
                "avg_posted_rate_usd": avg_rate,
                "quote_today_usd": today["quote_usd"],
                "ladder": ladder,
                "best_day": {"day": best["day"], "quote_usd": best["quote_usd"],
                             "savings_usd": round(today["quote_usd"] - best["quote_usd"])},
            })
        lanes.sort(key=lambda x: -x["heat"])
        idx = round(sum(l["heat"] for l in lanes) / len(lanes), 1) if lanes else 0.0

        hour_key = _now().strftime("%Y-%m-%dT%H")
        await db.pricing_snapshots.update_one(
            {"hour": hour_key},
            {"$set": {"hour": hour_key, "at": _now().isoformat(),
                      "heat_index": idx, "lanes": len(lanes),
                      "total_demand": sum(l["demand_loads"] for l in lanes),
                      "total_supply": sum(l["supply_trucks"] for l in lanes)}},
            upsert=True)

        return {"at": _now().isoformat(), "market_heat_index": idx,
                "regime": ("SCORCHING — push margin" if idx >= 65 else
                           "BALANCED — hold targets" if idx >= 35 else
                           "SOFT — capture volume"),
                "lanes": lanes[:20],
                "hottest": lanes[0]["lane_label"] if lanes else None,
                "softest": lanes[-1]["lane_label"] if lanes else None}

    @router.get("/trend")
    async def trend(_=Depends(get_current_user)) -> Dict[str, Any]:
        rows = await db.pricing_snapshots.find({}, {"_id": 0}).sort("hour", -1).to_list(48)
        rows.reverse()
        return {"points": [{"hour": r["hour"][-2:] + ":00", "heat_index": r["heat_index"],
                            "demand": r.get("total_demand"), "supply": r.get("total_supply")}
                           for r in rows]}

    @router.get("/quote-suggest")
    async def quote_suggest(origin: str, destination: str,
                            posted_rate: Optional[float] = None,
                            _=Depends(get_current_user)) -> Dict[str, Any]:
        lane = f"{origin.strip()[-2:].upper()}-{destination.strip()[-2:].upper()}"
        loads = await _board_loads()
        rows = [l for l in loads if _lane_key(l) == lane]
        demand = len(rows)
        supply = await _lane_supply(lane)
        heat = _heat(demand, supply)
        base = posted_rate or (round(sum(float(r.get("rate_usd") or 0) for r in rows) / demand)
                               if rows else 2200)
        ladder = _ladder(float(base), heat)
        best = min(ladder, key=lambda d: d["quote_usd"])
        margin_target = round(8 + heat / 100 * 8, 1)
        return {"lane_key": lane, "heat": heat, "demand_loads": demand,
                "supply_trucks": supply, "margin_target_pct": margin_target,
                "ladder": ladder,
                "shipper_pitch": (f"Today this lane is ${ladder[0]['quote_usd']:,}, but "
                                  f"{best['day']} it'll be ${best['quote_usd']:,} "
                                  f"(${ladder[0]['quote_usd'] - best['quote_usd']:,} less — lower demand)."),
                }

    return router
