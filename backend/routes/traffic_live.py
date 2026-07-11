"""routes.traffic_live — Real roadwork / lane-closure incidents from public
state-DOT WZDx (Work Zone Data Exchange) feeds. No API keys, no mocks.

The caller passes a lat/lng (from browser geolocation); we fetch the nearest
state feeds, filter to currently-active events within a radius, and rank by
severity + distance. Feeds are cached per-state for 10 minutes.

Note: MnDOT's own WZDx feed (mn.carsprogram.org) blocks cloud IPs, so Twin
Cities users see the adjacent WI / IA / MO corridors — still real I-94 / I-35
freight-lane data.
"""
from __future__ import annotations

import asyncio
import logging
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger("tennant_tms.traffic_live")

# state -> (label, feed_url, centroid_lat, centroid_lng, public_511_url)
FEEDS: Dict[str, Tuple[str, str, float, float, str]] = {
    "WI": ("Wisconsin DOT · 511WI", "https://511wi.gov/api/wzdx", 44.6, -89.9, "https://511wi.gov"),
    "IA": ("Iowa DOT · 511IA", "https://iowa-atms.cloud-q-free.com/api/rest/dataprism/wzdx/wzdxfeed", 42.0, -93.5, "https://511ia.org"),
    "IN": ("Indiana DOT · CARS", "https://in.carsprogram.org/carsapi_v1/api/wzdx", 39.9, -86.3, "https://511in.org"),
    "MO": ("Missouri DOT", "https://traveler.modot.org/timconfig/feed/desktop/mo_wzdx.json", 38.4, -92.5, "https://traveler.modot.org"),
    "KY": ("Kentucky Transportation Cabinet", "https://storage.googleapis.com/kytc-its-2020-openrecords/public/feeds/WZDx/kytc_wzdx_v4.1.geojson", 37.5, -85.3, "https://goky.ky.gov"),
    "NY": ("New York DOT · 511NY", "https://511ny.org/api/wzdx", 42.9, -75.5, "https://511ny.org"),
    "WA": ("Washington State DOT", "https://wzdx.wsdot.wa.gov/api/v4/WorkZoneFeed", 47.4, -120.5, "https://wsdot.com/travel"),
    "UT": ("Utah DOT", "https://udottraffic.utah.gov/wzdx/udot/v40/data", 39.3, -111.7, "https://udottraffic.utah.gov"),
    "ID": ("Idaho DOT · 511", "https://511.idaho.gov/api/wzdx", 44.4, -114.6, "https://511.idaho.gov"),
    "DE": ("Delaware DOT", "https://wzdx.e-dot.com/del_dot_feed_wzdx_v4.1.geojson", 39.0, -75.5, "https://deldot.gov"),
    "LA": ("Louisiana DOTD", "https://wzdx.e-dot.com/la_dot_d_feed_wzdx_v4.1.geojson", 31.0, -92.0, "https://511la.org"),
}

_CACHE: Dict[str, Dict[str, Any]] = {}   # state -> {"items": [...], "at": datetime}
_TTL_SECONDS = 600
_LOCKS: Dict[str, asyncio.Lock] = {}


def _haversine_mi(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 3958.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _first_coord(geom: Optional[Dict[str, Any]]) -> Optional[Tuple[float, float]]:
    """Return (lat, lng) of the first coordinate in any GeoJSON geometry."""
    if not geom:
        return None
    coords = geom.get("coordinates")
    gtype = geom.get("type")
    try:
        if gtype == "Point":
            lng, lat = coords[0], coords[1]
        elif gtype in ("LineString", "MultiPoint"):
            lng, lat = coords[0][0], coords[0][1]
        elif gtype in ("MultiLineString", "Polygon"):
            lng, lat = coords[0][0][0], coords[0][0][1]
        else:
            return None
        return float(lat), float(lng)
    except (TypeError, IndexError, ValueError):
        return None


def _parse_dt(v: Optional[str]) -> Optional[datetime]:
    if not v:
        return None
    try:
        dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


_IMPACT_LABEL = {
    "all-lanes-closed": ("Road closed", "high"),
    "some-lanes-closed": ("Lane closure", "moderate"),
    "some-lanes-closed-merge-left": ("Lane closure · merge left", "moderate"),
    "some-lanes-closed-merge-right": ("Lane closure · merge right", "moderate"),
    "alternating-one-way": ("Alternating one-way", "moderate"),
    "all-lanes-open": ("Roadwork · lanes open", "low"),
}


def _simplify(state: str, feature: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    props = feature.get("properties") or {}
    core = props.get("core_details") or props
    label, _feed_url, _clat, _clng, site = FEEDS[state]

    now = datetime.now(timezone.utc)
    start = _parse_dt(props.get("start_date"))
    end = _parse_dt(props.get("end_date"))
    if start and start > now:          # not started yet
        return None
    if end and end < now:              # already over
        return None

    coord = _first_coord(feature.get("geometry"))
    if not coord:
        return None

    roads = core.get("road_names") or []
    highway = str(roads[0]) if roads else ""
    direction = (core.get("direction") or "").replace("undefined", "").strip()
    impact = (props.get("vehicle_impact") or "").lower()
    type_label, severity = _IMPACT_LABEL.get(impact, ("Roadwork", "low"))
    desc = (core.get("description") or "").strip()
    if len(desc) > 240:
        desc = desc[:237] + "…"

    dir_label = {"northbound": "NB", "southbound": "SB", "eastbound": "EB",
                 "westbound": "WB"}.get(direction.lower(), direction.upper()[:2] if direction else "")
    if dir_label and highway.upper().endswith(f" {dir_label}"):
        dir_label = ""
    location = " ".join(x for x in [highway, dir_label] if x) or f"{state} roadway"

    return {
        "location": location,
        "highway": highway,
        "direction": dir_label,
        "type": type_label,
        "severity": severity,
        "lat": coord[0],
        "lng": coord[1],
        "description": desc,
        "agency": label,
        "state": state,
        "source_url": site,
        "reported_at": core.get("update_date") or props.get("start_date"),
        "starts": props.get("start_date"),
        "ends": props.get("end_date"),
    }


async def _fetch_state(client: httpx.AsyncClient, state: str) -> List[Dict[str, Any]]:
    cached = _CACHE.get(state)
    now = datetime.now(timezone.utc)
    if cached and (now - cached["at"]).total_seconds() < _TTL_SECONDS:
        return cached["items"]
    lock = _LOCKS.setdefault(state, asyncio.Lock())
    async with lock:
        cached = _CACHE.get(state)
        if cached and (datetime.now(timezone.utc) - cached["at"]).total_seconds() < _TTL_SECONDS:
            return cached["items"]
        _label, url, _clat, _clng, _site = FEEDS[state]
        try:
            r = await client.get(url, headers={"User-Agent": "OriseiTMS/1.0 (freight dispatch)"})
            r.raise_for_status()
            features = r.json().get("features") or []
        except Exception as e:
            logger.warning("WZDx fetch failed for %s: %s: %s", state, type(e).__name__, e)
            # keep stale cache on failure rather than dropping to nothing
            return cached["items"] if cached else []
        items = []
        for f in features:
            s = _simplify(state, f)
            if s:
                items.append(s)
        _CACHE[state] = {"items": items, "at": datetime.now(timezone.utc)}
        logger.info("WZDx %s: %d active events cached", state, len(items))
        return items


async def get_live_incidents(lat: float, lng: float, *, radius_mi: float = 250,
                             limit: int = 30) -> List[Dict[str, Any]]:
    """Real active work-zone incidents within `radius_mi` of (lat, lng)."""
    nearest = sorted(FEEDS, key=lambda s: _haversine_mi(lat, lng, FEEDS[s][2], FEEDS[s][3]))[:3]
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        batches = await asyncio.gather(*[_fetch_state(client, s) for s in nearest])
    out: List[Dict[str, Any]] = []
    seen = set()
    for batch in batches:
        for inc in batch:
            d = _haversine_mi(lat, lng, inc["lat"], inc["lng"])
            if d > radius_mi:
                continue
            key = (inc["location"], inc["type"], round(d / 5))
            if key in seen:
                continue
            seen.add(key)
            out.append({**inc, "distance_mi": round(d)})
    sev_rank = {"high": 0, "moderate": 1, "low": 2}
    out.sort(key=lambda x: (sev_rank.get(x["severity"], 9), x["distance_mi"]))
    return out[:limit]
