"""routes.loadboard_gateway — Layer 3: direct load-board integrations with failover.

Failover chain: DAT -> Truckstop -> Convoy -> internal simulation. Real connectors
activate the moment credentials are saved in Connections; until then the gateway
degrades gracefully to the internal board and reports per-board health.
"""
import logging
import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx

from routes.connections import get_connection_credentials

logger = logging.getLogger(__name__)

FAILOVER_ORDER = ["dat", "truckstop", "convoy", "internal_sim"]
BOARD_LABELS = {"dat": "DAT One", "truckstop": "Truckstop.com", "convoy": "Convoy", "internal_sim": "Internal Sim Board"}
BOARD_URLS = {
    "dat": "https://freight.api.dat.com/search/v3/loads",
    "truckstop": "https://api.truckstop.com/v1/loads/search",
    "convoy": "https://api.convoy.com/v1/shipments/available",
}
LANES = [("Minneapolis, MN", "Chicago, IL", 408), ("Chicago, IL", "Dallas, TX", 967), ("Minneapolis, MN", "Denver, CO", 914),
         ("St. Paul, MN", "Kansas City, MO", 441), ("Milwaukee, WI", "Atlanta, GA", 809), ("Des Moines, IA", "Columbus, OH", 624),
         ("Fargo, ND", "Minneapolis, MN", 240), ("Omaha, NE", "St. Louis, MO", 438), ("Chicago, IL", "Nashville, TN", 472),
         ("Green Bay, WI", "Indianapolis, IN", 400)]
COMMODITIES = ["Packaged foods", "Auto parts", "Paper products", "Machinery", "Building materials",
               "Beverages", "Plastics", "Retail freight", "Ag equipment parts", "Electronics"]
EQUIP = ["Dry Van", "Reefer", "Flatbed"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sim_loads(n: int = 14) -> List[Dict[str, Any]]:
    out = []
    for _ in range(n):
        origin, dest, miles = random.choice(LANES)
        rpm = round(random.uniform(2.05, 3.15), 2)
        out.append({"board_id": f"SIM-{uuid.uuid4().hex[:7].upper()}", "board": "Internal Sim",
                    "origin": origin, "dest": dest, "miles": miles, "equipment": random.choice(EQUIP),
                    "commodity": random.choice(COMMODITIES), "weight_lbs": random.randint(12000, 44000),
                    "shipper_rate": round(miles * rpm, 0), "rpm": rpm,
                    "pickup_date": (datetime.now(timezone.utc) + timedelta(days=random.randint(0, 2))).strftime("%Y-%m-%d")})
    return out


def _map_board_load(board: str, x: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Best-effort normalization of a real board payload into the internal load shape."""
    try:
        origin = x.get("origin") or f"{x.get('originCity', '')}, {x.get('originState', '')}"
        dest = x.get("destination") or f"{x.get('destCity', '')}, {x.get('destState', '')}"
        miles = int(x.get("miles") or x.get("tripMiles") or 0)
        rate = float(x.get("rate") or x.get("postedRate") or 0)
        if not origin.strip(", ") or not dest.strip(", ") or not miles:
            return None
        return {"board_id": str(x.get("id") or x.get("loadId") or uuid.uuid4().hex[:8].upper()),
                "board": BOARD_LABELS[board], "origin": origin, "dest": dest, "miles": miles,
                "equipment": x.get("equipmentType") or x.get("equipment") or "Dry Van",
                "commodity": x.get("commodity") or "General freight",
                "weight_lbs": int(x.get("weight") or x.get("weightLbs") or 30000),
                "shipper_rate": rate or round(miles * 2.5, 0),
                "rpm": round((rate / miles), 2) if rate and miles else 2.5,
                "pickup_date": str(x.get("pickupDate") or datetime.now(timezone.utc).strftime("%Y-%m-%d"))[:10]}
    except Exception:  # noqa: BLE001
        return None


async def _try_real_board(db, board: str) -> Tuple[Optional[List[Dict[str, Any]]], str]:
    creds = await get_connection_credentials(db, board)
    if not creds or not creds.get("api_key"):
        return None, "no_credentials"
    try:
        async with httpx.AsyncClient(timeout=8) as cx:
            r = await cx.get(BOARD_URLS[board], headers={"Authorization": f"Bearer {creds['api_key']}"})
            r.raise_for_status()
            data = r.json()
            raw = data if isinstance(data, list) else data.get("loads") or data.get("results") or []
            loads = [m for m in (_map_board_load(board, x) for x in raw[:30]) if m]
            if loads:
                return loads, "connected"
            return None, "connected_empty"
    except Exception as e:  # noqa: BLE001
        logger.warning("loadboard %s failed: %s", board, e)
        return None, f"error: {type(e).__name__}"


async def gateway_fetch_loads(db, n: int = 14) -> Dict[str, Any]:
    """Walk the failover chain; always returns loads (sim as last resort)."""
    loads: Optional[List[Dict[str, Any]]] = None
    source = "internal_sim"
    for board in ("dat", "truckstop", "convoy"):
        result, status = await _try_real_board(db, board)
        await db.loadboard_health.update_one(
            {"board": board},
            {"$set": {"board": board, "label": BOARD_LABELS[board], "status": status, "checked_at": _now()}},
            upsert=True)
        if result and loads is None:
            loads, source = result, board
    if loads is None:
        loads = _sim_loads(n)
    await db.loadboard_health.update_one(
        {"board": "internal_sim"},
        {"$set": {"board": "internal_sim", "label": BOARD_LABELS["internal_sim"], "status": "healthy",
                  "checked_at": _now()}},
        upsert=True)
    await db.loadboard_state.update_one(
        {"_id": "state"},
        {"$set": {"last_fetch_at": _now(), "last_source": source, "loads_fetched": len(loads)},
         "$inc": {"total_fetches": 1}},
        upsert=True)
    return {"source": source, "source_label": BOARD_LABELS[source], "loads": loads}


def build_loadboard_gateway_router(*, api_router, db, get_current_user):
    from fastapi import Depends

    @api_router.get("/loadboard-gateway/status")
    async def gateway_status(_=Depends(get_current_user)) -> Dict[str, Any]:
        health = await db.loadboard_health.find({}, {"_id": 0}).to_list(10)
        by_board = {h["board"]: h for h in health}
        state = await db.loadboard_state.find_one({"_id": "state"}, {"_id": 0}) or {}
        chain = [{"board": b, "label": BOARD_LABELS[b],
                  **(by_board.get(b) or {"status": "healthy" if b == "internal_sim" else "no_credentials",
                                         "checked_at": None})}
                 for b in FAILOVER_ORDER]
        return {"failover_order": FAILOVER_ORDER, "chain": chain, "state": state,
                "note": "Real boards activate automatically once API keys are saved in Connections."}

    @api_router.post("/loadboard-gateway/fetch")
    async def gateway_fetch(_=Depends(get_current_user)) -> Dict[str, Any]:
        res = await gateway_fetch_loads(db)
        return {"ok": True, "source": res["source"], "source_label": res["source_label"],
                "count": len(res["loads"]), "sample": res["loads"][:6]}
