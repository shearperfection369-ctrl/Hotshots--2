"""routes.route_optimizer — Route Optimizer freight module.

Real geocoding (OpenStreetMap Nominatim) + real road routing (public OSRM,
no API key), plus a margin calculator (rate, fuel, MPG, driver pay, tolls →
net profit, rate-per-mile, GO/NO-GO verdict) and saved load history.

Endpoints — /api/route-optimizer/*
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger("orisei.route_optimizer")
UA = {"User-Agent": "OriseiTMS/1.0 (oliver@oriseifreightsolutions.com)"}
NOMINATIM = "https://nominatim.openstreetmap.org/search"
OSRM = "https://router.project-osrm.org/route/v1/driving"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Point(BaseModel):
    lat: float
    lon: float
    label: str = ""


class RouteIn(BaseModel):
    origin: Point
    dest: Point


class CalcInputs(BaseModel):
    rate: float = Field(..., ge=0)
    fuel_price: float = Field(..., ge=0)      # $/gal
    mpg: float = Field(..., gt=0)
    driver_pay_cpm: float = Field(..., ge=0)  # $/mile
    tolls: float = Field(0, ge=0)


class SaveLoadIn(BaseModel):
    origin: Point
    dest: Point
    miles: float = Field(..., gt=0)
    drive_hours: float = Field(..., ge=0)
    inputs: CalcInputs
    notes: Optional[str] = Field(default=None, max_length=500)


def compute_margin(miles: float, i: CalcInputs) -> Dict[str, Any]:
    fuel_cost = (miles / i.mpg) * i.fuel_price
    driver_cost = miles * i.driver_pay_cpm
    total_cost = fuel_cost + driver_cost + i.tolls
    net = i.rate - total_cost
    rpm = (i.rate / miles) if miles else 0
    cost_per_mile = (total_cost / miles) if miles else 0
    margin_pct = (net / i.rate * 100) if i.rate else 0
    if net <= 0:
        verdict, reason = "NO-GO", "Load loses money at these costs."
    elif rpm >= 2.0 and margin_pct >= 15:
        verdict, reason = "GO", "Healthy rate-per-mile and margin — book it."
    else:
        verdict, reason = "CAUTION", (
            "Profitable but thin — " +
            ("rate-per-mile below $2.00. " if rpm < 2.0 else "") +
            (f"margin below 15% ({margin_pct:.1f}%)." if margin_pct < 15 else ""))
    return {"fuel_cost": round(fuel_cost, 2), "driver_cost": round(driver_cost, 2),
            "tolls": round(i.tolls, 2), "total_cost": round(total_cost, 2),
            "net_profit": round(net, 2), "rpm": round(rpm, 2),
            "cost_per_mile": round(cost_per_mile, 2),
            "margin_pct": round(margin_pct, 1), "verdict": verdict, "verdict_reason": reason.strip()}


def build_route_optimizer_router(*, db, get_current_user: Callable,
                                 require_role: Callable) -> APIRouter:
    router = APIRouter(prefix="/route-optimizer", tags=["route-optimizer"])

    @router.get("/geocode")
    async def geocode(q: str, _=Depends(get_current_user)) -> Dict[str, Any]:
        if not q or len(q.strip()) < 2:
            return {"candidates": []}
        try:
            async with httpx.AsyncClient(timeout=12, headers=UA) as client:
                r = await client.get(NOMINATIM, params={
                    "q": q.strip(), "format": "json", "limit": 6,
                    "countrycodes": "us,ca,mx", "addressdetails": 0})
            r.raise_for_status()
            data = r.json()
        except Exception as e:  # noqa: BLE001
            raise HTTPException(status_code=502, detail=f"Geocoder unavailable: {str(e)[:120]}")
        return {"candidates": [
            {"label": d.get("display_name", ""), "lat": float(d["lat"]), "lon": float(d["lon"])}
            for d in data if d.get("lat") and d.get("lon")]}

    @router.post("/route")
    async def route(payload: RouteIn, _=Depends(get_current_user)) -> Dict[str, Any]:
        coords = f"{payload.origin.lon},{payload.origin.lat};{payload.dest.lon},{payload.dest.lat}"
        try:
            async with httpx.AsyncClient(timeout=20, headers=UA) as client:
                r = await client.get(f"{OSRM}/{coords}",
                                     params={"overview": "full", "geometries": "geojson", "steps": "false"})
            r.raise_for_status()
            data = r.json()
        except Exception as e:  # noqa: BLE001
            raise HTTPException(status_code=502, detail=f"Routing engine unavailable: {str(e)[:120]}")
        routes = data.get("routes") or []
        if data.get("code") != "Ok" or not routes:
            raise HTTPException(status_code=404, detail="No drivable route found between these points")
        best = routes[0]
        miles = best["distance"] / 1609.344
        drive_hours = best["duration"] / 3600
        # OSRM returns [lon,lat] — flip for Leaflet [lat,lon]
        geometry = [[c[1], c[0]] for c in best["geometry"]["coordinates"]]
        return {"miles": round(miles, 1), "drive_hours": round(drive_hours, 2),
                "geometry": geometry,
                "origin": payload.origin.model_dump(), "dest": payload.dest.model_dump()}

    @router.post("/calc")
    async def calc(miles: float, payload: CalcInputs, _=Depends(get_current_user)) -> Dict[str, Any]:
        if miles <= 0:
            raise HTTPException(status_code=400, detail="miles must be > 0")
        return compute_margin(miles, payload)

    @router.post("/loads")
    async def save_load(payload: SaveLoadIn, user=Depends(get_current_user)) -> Dict[str, Any]:
        results = compute_margin(payload.miles, payload.inputs)
        doc = {"load_id": f"RO-{uuid.uuid4().hex[:8].upper()}",
               "origin": payload.origin.model_dump(), "dest": payload.dest.model_dump(),
               "miles": round(payload.miles, 1), "drive_hours": round(payload.drive_hours, 2),
               "inputs": payload.inputs.model_dump(), "results": results,
               "notes": payload.notes or "", "created_by": user.email,
               "created_at": _now_iso()}
        await db.route_optimizer_loads.insert_one(dict(doc))
        doc.pop("_id", None)
        return doc

    @router.get("/loads")
    async def list_loads(limit: int = 100, _=Depends(get_current_user)) -> Dict[str, Any]:
        loads = await db.route_optimizer_loads.find({}, {"_id": 0}) \
            .sort("created_at", -1).to_list(min(limit, 300))
        return {"loads": loads}

    @router.delete("/loads/{load_id}")
    async def delete_load(load_id: str, _=Depends(require_role("admin", "dispatcher"))) -> Dict[str, Any]:
        r = await db.route_optimizer_loads.delete_one({"load_id": load_id})
        if r.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Load not found")
        return {"ok": True}

    return router
