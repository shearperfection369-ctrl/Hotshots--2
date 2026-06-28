"""
Universal Autocomplete API
==========================

Powers the global <Autocomplete> input across every form in the TMS.
Returns short, alpha-sorted suggestion lists for the supplied field type,
merging live values from the DB with a curated "common terms" baseline so
the operator always sees sensible options on day one.

Endpoint
--------
* GET /api/autocomplete/{kind}?q=<prefix>&limit=20

`kind` is one of:
  - carriers        : carrier_name values from brokerage_bookings
  - customers       : name values from orisei_customers
  - commodities     : commodity values from shipments + brokerage_bookings
  - equipment       : equipment values from brokerage_bookings
  - modes           : transport mode (static + actual usage)
  - references      : recent BOL / RC / INV / BK ids
  - cities          : freight city list (curated)
  - terms           : payment terms (Net 7 / 10 / 14 / 30)
  - lanes           : origin → destination pairs from brokerage_bookings
  - hazmat_un       : common UN numbers for hazmat freight
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

CURATED: Dict[str, List[str]] = {
    "carriers": [
        "Schneider National", "JB Hunt", "Knight-Swift", "Werner Enterprises",
        "C.H. Robinson", "XPO Logistics", "TQL", "Coyote Logistics",
        "Landstar System", "Old Dominion", "Saia", "FedEx Freight",
        "Estes Express", "ArcBest", "ABF Freight", "YRC Freight",
        "R+L Carriers", "Dayton Freight", "Averitt", "Pitt Ohio",
        "Crete Carrier", "Hirschbach", "Maverick Transportation",
        "Mesilla Valley Transportation", "USA Truck", "Heartland Express",
    ],
    "commodities": [
        "Dry van freight", "Refrigerated produce", "Frozen food", "Dairy",
        "Meat & poultry", "Beverages", "Paper products", "Electronics",
        "Pharmaceuticals", "Apparel", "Furniture", "Building materials",
        "Steel beams", "Lumber", "Plastics", "Chemicals", "Hazmat (Class 3)",
        "Hazmat (Class 8)", "DDGS", "Soybean meal", "Animal feed",
        "Corn", "Soybeans", "Cotton", "Tobacco", "Auto parts",
        "Containerized exports", "FAK (Freight All Kinds)",
    ],
    "equipment": [
        "Dry Van 53'", "Reefer 53'", "Reefer 48'", "Flatbed 48'", "Flatbed 53'",
        "Step-Deck", "Conestoga", "RGN (Removable Gooseneck)", "Power Only",
        "Hot Shot", "Sprinter Van", "Box Truck 26'", "LTL", "Parcel",
        "20' Container", "40' Container", "40' HC Container", "45' HC Container",
        "Tanker", "Hopper", "Pneumatic Bulker",
    ],
    "modes": ["TL", "LTL", "Parcel", "Ocean", "Air", "Rail", "Intermodal", "Hot Shot"],
    "terms": ["Net 7", "Net 10", "Net 14", "Net 21", "Net 30", "Net 45", "Net 60", "Due on receipt"],
    "hazmat_un": [
        "UN1170 Ethanol", "UN1203 Gasoline", "UN1219 Isopropanol",
        "UN1263 Paint", "UN1789 Hydrochloric acid", "UN1830 Sulfuric acid",
        "UN1950 Aerosols", "UN1993 Flammable liquid n.o.s.",
        "UN2031 Nitric acid", "UN2735 Amines",
        "UN3077 Environmentally hazardous substance",
        "UN3082 Environmentally hazardous substance, liquid",
        "UN3091 Lithium metal batteries", "UN3480 Lithium-ion batteries",
    ],
}


def build_autocomplete_router(*, db, get_current_user, require_role):
    router = APIRouter(prefix="/autocomplete", tags=["autocomplete"])

    async def _live_values(kind: str) -> List[str]:
        if kind == "carriers":
            return await db.brokerage_bookings.distinct("carrier_name")
        if kind == "customers":
            return await db.orisei_customers.distinct("name")
        if kind == "commodities":
            a = await db.shipments.distinct("commodity")
            b = await db.brokerage_bookings.distinct("commodity")
            return list(set(a + b))
        if kind == "equipment":
            return await db.brokerage_bookings.distinct("equipment")
        if kind == "modes":
            return await db.shipments.distinct("mode")
        if kind == "references":
            cur = (db.brokerage_bookings.find({}, {"_id": 0, "booked_id": 1,
                                                     "load_id": 1})
                                          .sort("booked_at", -1).limit(60))
            out: List[str] = []
            async for r in cur:
                if r.get("booked_id"): out.append(r["booked_id"])
                if r.get("load_id"):   out.append(r["load_id"])
            return out
        if kind == "lanes":
            cur = (db.brokerage_bookings.find({}, {"_id": 0, "origin": 1,
                                                     "destination": 1})
                                          .sort("booked_at", -1).limit(120))
            seen = set()
            out = []
            async for r in cur:
                o = (r.get("origin") or "").strip()
                d = (r.get("destination") or "").strip()
                if o and d:
                    lane = f"{o} → {d}"
                    if lane not in seen:
                        seen.add(lane); out.append(lane)
            return out
        return []

    @router.get("/{kind}")
    async def autocomplete(kind: str,
                            q: str = Query(default=""),
                            limit: int = Query(default=20, ge=1, le=100),
                            _=Depends(get_current_user)) -> Dict[str, Any]:
        if kind not in (set(CURATED.keys()) | {
                "carriers", "customers", "commodities", "equipment", "modes",
                "references", "lanes"}):
            raise HTTPException(404, f"Unknown autocomplete kind '{kind}'")
        live = await _live_values(kind) if kind in (
            "carriers", "customers", "commodities", "equipment",
            "modes", "references", "lanes") else []
        merged = sorted(
            {x for x in (CURATED.get(kind, []) + live)
             if x and isinstance(x, str)},
            key=lambda s: s.lower(),
        )
        qn = (q or "").strip().lower()
        if qn:
            merged = [m for m in merged if qn in m.lower()]
        return {"kind": kind, "query": q,
                "suggestions": merged[:limit],
                "total_available": len(merged)}

    return router
