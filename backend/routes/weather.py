"""routes.weather — real-time NWS weather alerts + per-user monitored
locations. Extracted from server.py as the first conservative refactor."""

from __future__ import annotations

import logging
import time as _time
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel


logger = logging.getLogger("tennant_tms.weather")


# ---- NWS upstream cache: 1 call / coord / minute, shared across users ----
_NWS_CACHE: Dict[Tuple[float, float], Tuple[float, List[Dict[str, Any]]]] = {}
_NWS_CACHE_TTL_S = 60.0


class WeatherAlertLocationIn(BaseModel):
    label: str
    lat: float
    lng: float
    state: Optional[str] = None
    country: Optional[str] = "US"


async def _fetch_live_nws_alerts(locations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Hit api.weather.gov for each location and translate the GeoJSON
    payload to the schema the frontend already speaks. Per-coordinate
    responses are cached for 60s so that 100 polling users monitoring
    the same city generate one upstream call per minute.
    """
    if not locations:
        return []
    out: List[Dict[str, Any]] = []
    seen_ids: set[str] = set()
    headers = {
        "User-Agent": "Tennant-TMS/2.4 (ops@tennantco.com)",
        "Accept": "application/geo+json",
    }
    sev_map = {"Extreme": "high", "Severe": "high", "Moderate": "moderate", "Minor": "low", "Unknown": "low"}
    now = _time.monotonic()

    async with httpx.AsyncClient(timeout=4.0, headers=headers) as http:
        for loc in locations:
            lat, lng = loc.get("lat"), loc.get("lng")
            if lat is None or lng is None:
                continue
            country = (loc.get("country") or "US").upper()
            if country and country != "US":
                continue
            cache_key = (round(float(lat), 3), round(float(lng), 3))

            cached = _NWS_CACHE.get(cache_key)
            features: Optional[List[Dict[str, Any]]] = None
            if cached and (now - cached[0]) < _NWS_CACHE_TTL_S:
                features = cached[1]
            else:
                url = f"https://api.weather.gov/alerts/active?point={lat},{lng}"
                try:
                    r = await http.get(url)
                    if r.status_code != 200:
                        logger.warning("NWS non-200 for (%s,%s): HTTP %s", lat, lng, r.status_code)
                        features = []
                    else:
                        features = (r.json() or {}).get("features") or []
                    _NWS_CACHE[cache_key] = (now, features)
                except Exception as e:
                    logger.warning("NWS request failed for (%s,%s): %s: %s", lat, lng, type(e).__name__, e)
                    features = cached[1] if cached else []

            for feat in features or []:
                p = feat.get("properties") or {}
                aid = p.get("id") or feat.get("id")
                if not aid or aid in seen_ids:
                    continue
                seen_ids.add(aid)
                out.append({
                    "alert_id": aid,
                    "type": p.get("event") or "Weather Alert",
                    "severity": sev_map.get(p.get("severity"), "low"),
                    "area": p.get("areaDesc") or loc.get("label"),
                    "affected_facility": loc.get("label"),
                    "headline": p.get("headline") or p.get("event"),
                    "body": p.get("description") or "",
                    "issued_at": p.get("sent") or datetime.now(timezone.utc).isoformat(),
                    "expires_at": p.get("expires") or (datetime.now(timezone.utc) + timedelta(hours=6)).isoformat(),
                    "source": p.get("senderName") or "National Weather Service",
                    "source_url": p.get("@id") or "https://www.weather.gov/",
                    "live": True,
                })
    sev_rank = {"high": 0, "moderate": 1, "low": 2}
    out.sort(key=lambda a: (sev_rank.get(a.get("severity"), 9), -1 * len(a.get("issued_at") or "")))
    return out


async def _seed_alert_locations_from_brand(brand: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Best-effort: geocode the active brand's facility cities so the user
    starts with sensible defaults. Falls back to Tennant's 3 US plants.
    """
    defaults = [
        {"label": "Golden Valley, MN", "lat": 44.9847, "lng": -93.3486, "state": "MN"},
        {"label": "Holland, MI",       "lat": 42.7875, "lng": -86.1089, "state": "MI"},
        {"label": "Louisville, KY",    "lat": 38.2527, "lng": -85.7585, "state": "KY"},
    ]
    if not brand or brand.get("brand_id") == "tennant":
        return defaults
    facilities = brand.get("facilities") or []
    if not facilities:
        return defaults
    out: List[Dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=6.0) as http:
        for f in facilities[:6]:
            label = (f.get("city") or f.get("name") or "").strip()
            if not label:
                continue
            try:
                r = await http.get(
                    "https://geocoding-api.open-meteo.com/v1/search",
                    params={"name": label, "count": 1, "language": "en", "format": "json"},
                )
                hits = (r.json() or {}).get("results") or []
                if hits:
                    h = hits[0]
                    out.append({
                        "label": f"{h.get('name')}{', ' + h.get('admin1') if h.get('admin1') else ''}",
                        "lat": h.get("latitude"),
                        "lng": h.get("longitude"),
                        "state": (h.get("admin1") or "")[:2].upper() if h.get("country_code") == "US" else None,
                        "country": h.get("country_code"),
                    })
            except Exception as e:
                logger.warning("Geocoder failed for %s: %s", label, e)
                continue
    return out or defaults


def build_weather_router(
    *,
    db,
    get_current_user: Callable,
    brand_swap: Callable,
    active_brand_doc: Callable,
    mock_weather_alerts: List[Dict[str, Any]],
) -> APIRouter:
    """Factory: returns an APIRouter wired to the live NWS feed.

    All shared state (db handle, helpers, mock fallback) is injected so
    this module has no circular dependency on server.py.
    """
    router = APIRouter()

    @router.get("/weather/alerts")
    async def weather_alerts_endpoint(user=Depends(get_current_user)):
        """Real-time weather advisories — live NWS feed with brand mock fallback."""
        cfg = await db.weather_alert_locations.find_one({"user_id": user.user_id}, {"_id": 0})
        if not cfg or not cfg.get("locations"):
            brand = await active_brand_doc()
            seeded = await _seed_alert_locations_from_brand(brand)
            await db.weather_alert_locations.update_one(
                {"user_id": user.user_id},
                {"$set": {"user_id": user.user_id, "locations": seeded,
                          "updated_at": datetime.now(timezone.utc).isoformat()}},
                upsert=True,
            )
            locations = seeded
        else:
            locations = cfg.get("locations") or []

        live = await _fetch_live_nws_alerts(locations)
        if live:
            return await brand_swap(live)
        return await brand_swap(mock_weather_alerts)

    @router.get("/weather/alert-locations")
    async def get_weather_alert_locations(user=Depends(get_current_user)):
        """Return the user's currently-monitored locations."""
        cfg = await db.weather_alert_locations.find_one({"user_id": user.user_id}, {"_id": 0})
        return {"locations": (cfg or {}).get("locations") or []}

    @router.post("/weather/alert-locations")
    async def set_weather_alert_locations(payload: Dict[str, Any], user=Depends(get_current_user)):
        """Replace the user's monitored-location list. Body: {locations: [...]}.
        Each row must have label / lat / lng. List capped at 12."""
        raw = payload.get("locations") if isinstance(payload, dict) else None
        if not isinstance(raw, list):
            raise HTTPException(400, "Body must be {locations: [...]}")
        cleaned: List[Dict[str, Any]] = []
        dropped = 0
        for item in raw[:12]:
            if not isinstance(item, dict):
                dropped += 1
                continue
            try:
                row = WeatherAlertLocationIn(**item).model_dump()
                row["label"] = (row.get("label") or "Unnamed").strip()[:80] or "Unnamed"
                row["state"] = (row.get("state") or "").upper()[:2] or None
                row["country"] = (row.get("country") or "US").upper()[:2]
                cleaned.append(row)
            except Exception:
                dropped += 1
        await db.weather_alert_locations.update_one(
            {"user_id": user.user_id},
            {"$set": {"user_id": user.user_id, "locations": cleaned,
                      "updated_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True,
        )
        return {"ok": True, "locations": cleaned, "dropped": dropped}

    return router
