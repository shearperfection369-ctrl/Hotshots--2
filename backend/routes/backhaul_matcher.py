"""routes.backhaul_matcher — turn empty return legs into paid loads.

Scans trucks currently out delivering (active bookings) plus standing
deadhead demands from the Carrier Network, and matches them against
board loads heading back the other way. A truck delivering in Memphis
gets a loaded return to its home lane instead of hauling air.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Depends

STATE_RE = re.compile(r",\s*([A-Z]{2})\b")
CITY_ALIASES = {"MSP": "Minneapolis", "CHI": "Chicago", "KC": "Kansas City",
                "STL": "St. Louis", "DFW": "Dallas", "ATL": "Atlanta"}


def _state_of(place: str) -> str:
    m = STATE_RE.search(place or "")
    return m.group(1) if m else (place or "")[-2:].upper()


def _city_of(place: str) -> str:
    return (place or "").split(",")[0].strip().lower()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_backhaul_router(*, db, get_current_user: Callable) -> APIRouter:
    router = APIRouter(prefix="/backhaul", tags=["backhaul-matcher"])

    async def _board_loads() -> List[Dict[str, Any]]:
        rows = await db.brokerage_loads.find({}, {"_id": 0}).to_list(300)
        if not rows:
            from routes.brokerage import LOAD_BOARDS, _gen_loads_for_board  # type: ignore
            for b in LOAD_BOARDS:
                rows.extend(_gen_loads_for_board(b["id"], count=14))
        return rows

    async def _delivering_trucks() -> List[Dict[str, Any]]:
        since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        rows = await db.brokerage_bookings.find(
            {"status": {"$in": ["booked", "in_transit", "dispatched"]},
             "booked_at": {"$gte": since}},
            {"_id": 0, "booked_id": 1, "carrier_name": 1, "origin": 1,
             "destination": 1, "delivery_date": 1, "equipment": 1}).to_list(100)
        return rows

    async def _standing_demands() -> List[Dict[str, Any]]:
        """Deadhead lanes recorded on Carrier Network backhaulers."""
        rows = await db.carrier_network_prospects.find(
            {"deadhead_lanes.0": {"$exists": True}},
            {"_id": 0, "name": 1, "deadhead_lanes": 1, "equipment": 1}).to_list(100)
        out = []
        for p in rows:
            for lane in p.get("deadhead_lanes") or []:
                parts = re.split(r"→|->", lane)
                if len(parts) < 2:
                    continue
                frm, to = parts[0].strip(), re.sub(r"\(.*\)", "", parts[1]).strip()
                frm = CITY_ALIASES.get(frm.upper(), frm)
                to = CITY_ALIASES.get(to.upper(), to)
                out.append({"carrier": p["name"], "from": frm, "to": to,
                            "equipment": p.get("equipment") or [], "raw": lane})
        return out

    def _match_quality(truck: Dict[str, Any], load: Dict[str, Any]) -> Optional[str]:
        t_dest_st, t_org_st = _state_of(truck["destination"]), _state_of(truck["origin"])
        l_org_st, l_dest_st = _state_of(load.get("origin")), _state_of(load.get("destination"))
        if t_dest_st != l_org_st:
            return None
        if truck.get("equipment") and load.get("equipment") and \
                truck["equipment"] not in (load["equipment"], "Any"):
            return None
        if l_dest_st == t_org_st:
            return "perfect"       # loaded all the way home
        return "reposition"        # at least not hauling air out of the market

    @router.get("/matches")
    async def matches(_=Depends(get_current_user)) -> Dict[str, Any]:
        loads = await _board_loads()
        trucks = await _delivering_trucks()
        demands = await _standing_demands()

        results: List[Dict[str, Any]] = []
        for t in trucks:
            for l in loads:
                q = _match_quality(t, l)
                if not q:
                    continue
                results.append({
                    "type": "truck", "quality": q,
                    "carrier": t.get("carrier_name") or "TBD",
                    "truck_lane": f"{t['origin']} → {t['destination']}",
                    "delivery_date": t.get("delivery_date"),
                    "booked_id": t.get("booked_id"),
                    "load_id": l.get("load_id"), "board_id": l.get("board_id"),
                    "return_lane": f"{l.get('origin')} → {l.get('destination')}",
                    "rate_usd": l.get("rate_usd"), "miles": l.get("miles"),
                    "margin_pct": l.get("margin_pct"), "equipment": l.get("equipment"),
                })
        # standing deadhead demands from Carrier Network backhaulers
        for d in demands:
            frm_city = _city_of(d["from"])
            for l in loads:
                if frm_city and frm_city in _city_of(l.get("origin")):
                    results.append({
                        "type": "standing", "quality": "standing",
                        "carrier": d["carrier"],
                        "truck_lane": f"deadhead: {d['raw']}",
                        "load_id": l.get("load_id"), "board_id": l.get("board_id"),
                        "return_lane": f"{l.get('origin')} → {l.get('destination')}",
                        "rate_usd": l.get("rate_usd"), "miles": l.get("miles"),
                        "margin_pct": l.get("margin_pct"), "equipment": l.get("equipment"),
                    })
        order = {"perfect": 0, "reposition": 1, "standing": 2}
        results.sort(key=lambda r: (order.get(r["quality"], 9), -(r.get("margin_pct") or 0)))
        results = results[:40]
        await db.backhaul_matches.update_one(
            {"_id": "latest"},
            {"$set": {"at": _now_iso(), "matches": results,
                      "trucks_out": len(trucks), "standing_demands": len(demands)}},
            upsert=True)
        return {"at": _now_iso(), "trucks_out": len(trucks),
                "standing_demands": len(demands), "count": len(results),
                "matches": results}

    return router
