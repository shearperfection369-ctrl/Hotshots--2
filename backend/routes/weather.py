"""routes.weather — real-time NWS weather alerts + per-user monitored
locations. Extracted from server.py as the first conservative refactor."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Dict, List, Optional

import httpx
from cachetools import TTLCache
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel


logger = logging.getLogger("tennant_tms.weather")


# ---- NWS upstream cache: 1 call / coord / minute, shared across users ----
# Bounded LRU so a long-running pod never grows the cache unboundedly.
_NWS_CACHE: TTLCache = TTLCache(maxsize=512, ttl=60)
# Per-coordinate lock map prevents thundering-herd on cold cache fetches.
# When 50 users all ask for Denver at once, only ONE actually calls NWS;
# the other 49 await the lock and read from cache on the next tick.
_NWS_LOCKS: Dict[tuple, asyncio.Lock] = {}


def _lock_for(key: tuple) -> asyncio.Lock:
    lock = _NWS_LOCKS.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _NWS_LOCKS[key] = lock
    return lock


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
        "User-Agent": "Orisei-TMS/2.4 (oliver@oriseifreightsolutions.com)",
        "Accept": "application/geo+json",
    }
    sev_map = {"Extreme": "high", "Severe": "high", "Moderate": "moderate", "Minor": "low", "Unknown": "low"}

    async with httpx.AsyncClient(timeout=4.0, headers=headers) as http:
        for loc in locations:
            lat, lng = loc.get("lat"), loc.get("lng")
            if lat is None or lng is None:
                continue
            country = (loc.get("country") or "US").upper()
            if country and country != "US":
                continue
            cache_key = (round(float(lat), 3), round(float(lng), 3))

            cached_features = _NWS_CACHE.get(cache_key)
            if cached_features is not None:
                features: Optional[List[Dict[str, Any]]] = cached_features
            else:
                # Acquire per-coord lock so only one task actually hits NWS;
                # the rest find the result in cache the moment the lock
                # releases.
                async with _lock_for(cache_key):
                    cached_features = _NWS_CACHE.get(cache_key)
                    if cached_features is not None:
                        features = cached_features
                    else:
                        url = f"https://api.weather.gov/alerts/active?point={lat},{lng}"
                        try:
                            r = await http.get(url)
                            if r.status_code != 200:
                                logger.warning("NWS non-200 for (%s,%s): HTTP %s", lat, lng, r.status_code)
                                features = []
                            else:
                                features = (r.json() or {}).get("features") or []
                            _NWS_CACHE[cache_key] = features
                        except Exception as e:
                            logger.warning("NWS request failed for (%s,%s): %s: %s", lat, lng, type(e).__name__, e)
                            features = []

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
    """Geocode the active brand's facility cities so the user starts with
    sensible defaults. **No brand is special-cased** — named facilities are
    treated like any other brand's facilities (looked up via the same
    Open-Meteo geocoder). If the geocoder is unreachable we fall through to
    a tiny baked-in seed so the UI is never empty.
    """
    fallback_seed = [
        {"label": "Golden Valley, MN", "lat": 44.9847, "lng": -93.3486, "state": "MN"},
        {"label": "Holland, MI",       "lat": 42.7875, "lng": -86.1089, "state": "MI"},
        {"label": "Louisville, KY",    "lat": 38.2527, "lng": -85.7585, "state": "KY"},
    ]
    facilities = (brand or {}).get("facilities") or []
    if not facilities:
        return fallback_seed
    out: List[Dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=6.0) as http:
        for f in facilities[:6]:
            raw_label = (f.get("city") or f.get("name") or "").strip()
            if not raw_label:
                continue
            # The Open-Meteo geocoder doesn't accept "City, ST" — strip
            # the state suffix before calling it, otherwise we get zero hits
            # and silently fall through to the hard-coded fallback seed.
            city_only = raw_label.split(",", 1)[0].strip()
            try:
                r = await http.get(
                    "https://geocoding-api.open-meteo.com/v1/search",
                    params={"name": city_only, "count": 1, "language": "en", "format": "json"},
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
                else:
                    logger.info("Geocoder returned 0 hits for %s", city_only)
            except Exception as e:
                logger.warning("Geocoder failed for %s: %s", city_only, e)
                continue
    return out or fallback_seed


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
    async def weather_alerts_endpoint(
        lat: Optional[float] = None,
        lng: Optional[float] = None,
        label: Optional[str] = None,
        user=Depends(get_current_user),
    ):
        """Real-time weather advisories from api.weather.gov (US NWS).

        Three modes (in priority order):
          1. `?lat=&lng=` passed by the frontend from `navigator.geolocation`
             → live NWS lookup for that exact point, no mock, no seed.
          2. User has already saved monitored locations via
             POST /weather/alert-locations → fetch alerts for each.
          3. No location known → return an empty payload with
             `needs_location: true` so the FE can prompt for geolocation.

        NO mock/synthetic fallback is served anymore. If NWS returns zero
        active alerts, the response is an empty list with `no_active_alerts:
        true` — the FE renders a clean "all clear" state.
        """
        # 1. Explicit lat/lng from the caller's browser
        if lat is not None and lng is not None:
            live = await _fetch_live_nws_alerts([{
                "label": label or f"Your location ({lat:.3f}, {lng:.3f})",
                "lat": lat, "lng": lng, "country": "US",
            }])
            return {
                "items": await brand_swap(live),
                "count": len(live),
                "no_active_alerts": len(live) == 0,
                "resolved_from": "browser_geolocation",
                "needs_location": False,
            }

        # 2. Previously-saved monitored locations
        cfg = await db.weather_alert_locations.find_one(
            {"user_id": user.user_id}, {"_id": 0})
        locations = (cfg or {}).get("locations") or []
        if locations:
            live = await _fetch_live_nws_alerts(locations)
            return {
                "items": await brand_swap(live),
                "count": len(live),
                "no_active_alerts": len(live) == 0,
                "resolved_from": "saved_locations",
                "locations_monitored": len(locations),
                "needs_location": False,
            }

        # 3. No location known — ask the browser for one
        return {
            "items": [],
            "count": 0,
            "no_active_alerts": False,
            "needs_location": True,
            "resolved_from": None,
        }

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
