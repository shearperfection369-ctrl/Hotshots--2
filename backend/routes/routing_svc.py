"""routes.routing_svc — lightweight driving-directions service.

Preferred provider: **Mapbox Directions** (when `MAPBOX_TOKEN` is set).
Fallback: **OSRM public instance** (no key needed, `router.project-osrm.org`).
Ultra-fallback (offline / rate-limited): great-circle distance estimate.

Every response is normalized so the FE sees the same shape regardless of
provider. Records are persisted to `route_lookups` for compliance + reuse.

Endpoints — under /api/routing/*:
  POST /route          · compute driving distance/duration between two points
  POST /geocode        · resolve a free-form address into lat/lng
  GET  /provider       · which routing provider is currently active
  GET  /recent         · latest lookups (audit)
"""
from __future__ import annotations

import logging
import math
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger("orisei.routing")

MAPBOX_TOKEN = os.environ.get("MAPBOX_TOKEN") or os.environ.get("MAPBOX_SECRET_TOKEN") or ""
OSRM_BASE_URL = os.environ.get("OSRM_BASE_URL", "https://router.project-osrm.org")
MAPBOX_BASE_URL = "https://api.mapbox.com"


class Coord(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)


class RouteIn(BaseModel):
    origin: Optional[Coord] = None
    destination: Optional[Coord] = None
    origin_address: Optional[str] = Field(None, max_length=300)
    destination_address: Optional[str] = Field(None, max_length=300)
    profile: str = Field("driving", description="driving | driving-traffic | truck")


class GeocodeIn(BaseModel):
    address: str = Field(..., max_length=300)


def _haversine_m(a: Coord, b: Coord) -> float:
    """Great-circle distance in meters between two coords."""
    R = 6_371_000
    p1, p2 = math.radians(a.lat), math.radians(b.lat)
    dp = math.radians(b.lat - a.lat)
    dl = math.radians(b.lng - a.lng)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


async def _mapbox_geocode(address: str) -> Optional[Coord]:
    if not MAPBOX_TOKEN:
        return None
    url = f"{MAPBOX_BASE_URL}/geocoding/v5/mapbox.places/{httpx.URL(address).path}.json"
    # httpx.URL does not directly help here — encode manually:
    from urllib.parse import quote
    url = f"{MAPBOX_BASE_URL}/geocoding/v5/mapbox.places/{quote(address)}.json"
    try:
        async with httpx.AsyncClient(timeout=8.0) as c:
            r = await c.get(url, params={"access_token": MAPBOX_TOKEN, "limit": 1})
            r.raise_for_status()
            feats = r.json().get("features") or []
            if not feats:
                return None
            lon, lat = feats[0]["center"]
            return Coord(lat=lat, lng=lon)
    except Exception as e:                                              # noqa: BLE001
        logger.warning("Mapbox geocode failed: %s", e)
        return None


async def _osm_geocode(address: str) -> Optional[Coord]:
    """Nominatim OSM geocoder as an OSS fallback for Mapbox."""
    try:
        async with httpx.AsyncClient(timeout=8.0, headers={"User-Agent": "orisei-tms/1.0"}) as c:
            r = await c.get("https://nominatim.openstreetmap.org/search",
                            params={"q": address, "format": "json", "limit": 1})
            r.raise_for_status()
            arr = r.json() or []
            if not arr:
                return None
            return Coord(lat=float(arr[0]["lat"]), lng=float(arr[0]["lon"]))
    except Exception as e:                                              # noqa: BLE001
        logger.warning("OSM geocode failed: %s", e)
        return None


async def _resolve(coord: Optional[Coord], address: Optional[str]) -> Optional[Coord]:
    if coord:
        return coord
    if not address:
        return None
    return (await _mapbox_geocode(address)) or (await _osm_geocode(address))


async def _mapbox_route(o: Coord, d: Coord, profile: str) -> Optional[Dict[str, Any]]:
    if not MAPBOX_TOKEN:
        return None
    prof = {"driving-traffic": "driving-traffic", "truck": "driving", "driving": "driving"}.get(profile, "driving")
    coords = f"{o.lng},{o.lat};{d.lng},{d.lat}"
    url = f"{MAPBOX_BASE_URL}/directions/v5/mapbox/{prof}/{coords}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.get(url, params={
                "access_token": MAPBOX_TOKEN,
                "geometries": "geojson",
                "overview": "simplified",
                "annotations": "duration,distance",
            })
            r.raise_for_status()
            data = r.json()
            routes = data.get("routes") or []
            if not routes:
                return None
            rt = routes[0]
            return {
                "provider": "mapbox",
                "distance_m": rt.get("distance"),
                "duration_s": rt.get("duration"),
                "geometry": rt.get("geometry"),
            }
    except Exception as e:                                              # noqa: BLE001
        logger.warning("Mapbox route failed: %s", e)
        return None


async def _osrm_route(o: Coord, d: Coord) -> Optional[Dict[str, Any]]:
    url = f"{OSRM_BASE_URL}/route/v1/driving/{o.lng},{o.lat};{d.lng},{d.lat}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.get(url, params={"overview": "simplified", "geometries": "geojson"})
            r.raise_for_status()
            data = r.json()
            routes = data.get("routes") or []
            if not routes:
                return None
            rt = routes[0]
            return {
                "provider": "osrm",
                "distance_m": rt.get("distance"),
                "duration_s": rt.get("duration"),
                "geometry": rt.get("geometry"),
            }
    except Exception as e:                                              # noqa: BLE001
        logger.warning("OSRM route failed: %s", e)
        return None


def _fallback_route(o: Coord, d: Coord) -> Dict[str, Any]:
    """Great-circle estimate — used when both providers fail. Assumes 55mph
    average truck cruise + 20% detour factor to approximate road distance."""
    gc = _haversine_m(o, d)
    detour = gc * 1.20
    duration = detour / (55 * 1609.34 / 3600)                             # 55mph in m/s
    return {
        "provider": "estimate",
        "distance_m": round(detour, 1),
        "duration_s": round(duration, 1),
        "geometry": {"type": "LineString", "coordinates": [[o.lng, o.lat], [d.lng, d.lat]]},
    }


def build_routing_router(
    *, api_router: APIRouter, db,
    get_current_user: Callable, require_role: Callable,
) -> None:
    router = APIRouter(prefix="/routing", tags=["routing"])

    @router.get("/provider")
    async def provider(_=Depends(get_current_user)) -> Dict[str, Any]:
        return {
            "primary": "mapbox" if MAPBOX_TOKEN else "osrm",
            "mapbox_enabled": bool(MAPBOX_TOKEN),
            "osrm_base_url": OSRM_BASE_URL,
            "fallback": "estimate (haversine × 1.20 detour, 55mph avg)",
        }

    @router.post("/geocode")
    async def geocode(payload: GeocodeIn, _=Depends(get_current_user)) -> Dict[str, Any]:
        c = (await _mapbox_geocode(payload.address)) or (await _osm_geocode(payload.address))
        if not c:
            raise HTTPException(422, f"Could not resolve address: '{payload.address}'")
        return {
            "provider": "mapbox" if MAPBOX_TOKEN else "osm-nominatim",
            "address": payload.address,
            "lat": c.lat,
            "lng": c.lng,
        }

    @router.post("/route")
    async def compute_route(payload: RouteIn, user=Depends(get_current_user)) -> Dict[str, Any]:
        o = await _resolve(payload.origin, payload.origin_address)
        d = await _resolve(payload.destination, payload.destination_address)
        if not o or not d:
            raise HTTPException(422, "Both origin and destination must be resolvable (coord or address).")

        route = (await _mapbox_route(o, d, payload.profile)) or (await _osrm_route(o, d)) or _fallback_route(o, d)

        distance_m = float(route.get("distance_m") or 0)
        duration_s = float(route.get("duration_s") or 0)
        out = {
            "route_id": f"RT-{uuid.uuid4().hex[:10].upper()}",
            "provider": route["provider"],
            "profile": payload.profile,
            "origin": o.model_dump(),
            "destination": d.model_dump(),
            "distance_m": round(distance_m, 1),
            "distance_mi": round(distance_m / 1609.34, 2),
            "distance_km": round(distance_m / 1000, 2),
            "duration_s": round(duration_s, 1),
            "duration_min": round(duration_s / 60, 1),
            "duration_hr": round(duration_s / 3600, 2),
            "geometry": route.get("geometry"),
            "computed_at": datetime.now(timezone.utc).isoformat(),
        }

        # Persist for audit + repeat lookups
        try:
            await db.route_lookups.insert_one({
                **{k: v for k, v in out.items() if k != "geometry"},
                "user_id": getattr(user, "user_id", None),
                "origin_address": payload.origin_address,
                "destination_address": payload.destination_address,
            })
        except Exception as e:                                          # noqa: BLE001
            logger.warning("route persist failed: %s", e)

        return out

    @router.get("/recent")
    async def recent(_=Depends(get_current_user)) -> Dict[str, Any]:
        rows = await db.route_lookups.find({}, {"_id": 0}).sort("computed_at", -1).to_list(50)
        return {"items": rows, "count": len(rows)}

    api_router.include_router(router)
