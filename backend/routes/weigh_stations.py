"""routes.weigh_stations — nationwide weigh station reference + on-route AI
advice, plus lane-notes CRUD (special shipping instructions per lane)."""
from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from routes.routing_svc import (OSRM_BASE_URL, Coord, _mapbox_geocode,
                                _osm_geocode)

# Major fixed weigh/inspection stations on primary freight corridors.
WEIGH_STATIONS: List[Dict[str, Any]] = [
    {"state": "MN", "name": "St. Croix (Lakeland)", "hwy": "I-94 E/W", "lat": 44.9469, "lng": -92.7938},
    {"state": "MN", "name": "Worthington", "hwy": "I-90 E/W", "lat": 43.6355, "lng": -95.6122},
    {"state": "MN", "name": "Saginaw", "hwy": "US-2 / I-35 corridor", "lat": 46.8594, "lng": -92.4441},
    {"state": "WI", "name": "Hudson", "hwy": "I-94 E", "lat": 44.9634, "lng": -92.7205},
    {"state": "WI", "name": "Beloit", "hwy": "I-39/90 N", "lat": 42.5225, "lng": -89.0187},
    {"state": "WI", "name": "Kenosha", "hwy": "I-94 N/S", "lat": 42.5487, "lng": -87.9407},
    {"state": "IL", "name": "South Holland", "hwy": "I-80/94", "lat": 41.5892, "lng": -87.5906},
    {"state": "IL", "name": "East St. Louis", "hwy": "I-55/70", "lat": 38.6114, "lng": -90.1290},
    {"state": "IL", "name": "Marion", "hwy": "I-57 N/S", "lat": 37.7306, "lng": -88.9331},
    {"state": "IA", "name": "Jasper County", "hwy": "I-80 E/W", "lat": 41.6947, "lng": -93.0519},
    {"state": "IA", "name": "Salix", "hwy": "I-29 N/S", "lat": 42.3164, "lng": -96.2839},
    {"state": "MO", "name": "Platte County", "hwy": "I-29 S", "lat": 39.3672, "lng": -94.7738},
    {"state": "MO", "name": "Joplin", "hwy": "I-44 E/W", "lat": 37.0561, "lng": -94.4372},
    {"state": "MO", "name": "Foristell", "hwy": "I-70 E/W", "lat": 38.8103, "lng": -90.9629},
    {"state": "KS", "name": "Olathe", "hwy": "I-35 S", "lat": 38.8480, "lng": -94.8748},
    {"state": "KS", "name": "Goodland", "hwy": "I-70 E/W", "lat": 39.3286, "lng": -101.7302},
    {"state": "NE", "name": "Waverly", "hwy": "I-80 E/W", "lat": 40.9186, "lng": -96.5211},
    {"state": "NE", "name": "North Platte", "hwy": "I-80 E/W", "lat": 41.1130, "lng": -100.7180},
    {"state": "SD", "name": "Jefferson", "hwy": "I-29 N/S", "lat": 42.6011, "lng": -96.5567},
    {"state": "ND", "name": "Fargo (Mapleton)", "hwy": "I-94 E/W", "lat": 46.8890, "lng": -97.0537},
    {"state": "TX", "name": "Denton", "hwy": "I-35 S", "lat": 33.2645, "lng": -97.1839},
    {"state": "TX", "name": "New Waverly", "hwy": "I-45 N/S", "lat": 30.5372, "lng": -95.4830},
    {"state": "TX", "name": "Amarillo", "hwy": "I-40 E/W", "lat": 35.1930, "lng": -101.9520},
    {"state": "TX", "name": "El Paso (Anthony)", "hwy": "I-10 E/W", "lat": 31.9898, "lng": -106.5942},
    {"state": "OK", "name": "Love County", "hwy": "I-35 N", "lat": 33.9296, "lng": -97.1200},
    {"state": "OK", "name": "Sayre", "hwy": "I-40 E/W", "lat": 35.2909, "lng": -99.6400},
    {"state": "AR", "name": "Alma", "hwy": "I-40 E/W", "lat": 35.4770, "lng": -94.2166},
    {"state": "AR", "name": "Hope", "hwy": "I-30 E/W", "lat": 33.7101, "lng": -93.5507},
    {"state": "LA", "name": "Slidell", "hwy": "I-10/12/59", "lat": 30.2752, "lng": -89.7712},
    {"state": "CO", "name": "Monument", "hwy": "I-25 N/S", "lat": 39.0664, "lng": -104.8433},
    {"state": "CO", "name": "Limon", "hwy": "I-70 E/W", "lat": 39.2664, "lng": -103.6852},
    {"state": "WY", "name": "Cheyenne", "hwy": "I-80/25", "lat": 41.0997, "lng": -104.8735},
    {"state": "UT", "name": "Echo", "hwy": "I-80 E/W", "lat": 40.9702, "lng": -111.4380},
    {"state": "UT", "name": "St. George", "hwy": "I-15 N/S", "lat": 37.0300, "lng": -113.5250},
    {"state": "NM", "name": "Gallup", "hwy": "I-40 E/W", "lat": 35.5089, "lng": -108.8266},
    {"state": "NM", "name": "Lordsburg", "hwy": "I-10 E/W", "lat": 32.3406, "lng": -108.7080},
    {"state": "AZ", "name": "Ehrenberg", "hwy": "I-10 W", "lat": 33.6047, "lng": -114.5158},
    {"state": "AZ", "name": "Sanders", "hwy": "I-40 E/W", "lat": 35.2153, "lng": -109.3320},
    {"state": "NV", "name": "Wadsworth", "hwy": "I-80 E/W", "lat": 39.6329, "lng": -119.2831},
    {"state": "CA", "name": "Banning", "hwy": "I-10 E/W", "lat": 33.9280, "lng": -116.9160},
    {"state": "CA", "name": "Cordelia", "hwy": "I-80 E/W", "lat": 38.2116, "lng": -122.1300},
    {"state": "CA", "name": "Grapevine", "hwy": "I-5 N/S", "lat": 34.9345, "lng": -118.9250},
    {"state": "CA", "name": "Truckee", "hwy": "I-80 W", "lat": 39.3255, "lng": -120.1830},
    {"state": "OR", "name": "Ashland", "hwy": "I-5 N/S", "lat": 42.1655, "lng": -122.6470},
    {"state": "OR", "name": "Cascade Locks", "hwy": "I-84 E/W", "lat": 45.6702, "lng": -121.8850},
    {"state": "WA", "name": "Ridgefield", "hwy": "I-5 N/S", "lat": 45.7970, "lng": -122.6820},
    {"state": "ID", "name": "Boise (East)", "hwy": "I-84 E/W", "lat": 43.5407, "lng": -116.0940},
    {"state": "MT", "name": "Billings (Mossmain)", "hwy": "I-90 E/W", "lat": 45.7220, "lng": -108.7180},
    {"state": "IN", "name": "Lowell", "hwy": "I-65 N/S", "lat": 41.2500, "lng": -87.4310},
    {"state": "IN", "name": "Richmond", "hwy": "I-70 E/W", "lat": 39.8480, "lng": -84.9440},
    {"state": "OH", "name": "Delaware (Sunbury)", "hwy": "I-71 N/S", "lat": 40.2510, "lng": -82.8580},
    {"state": "OH", "name": "Hubbard", "hwy": "I-80 E/W", "lat": 41.1740, "lng": -80.5720},
    {"state": "MI", "name": "Monroe", "hwy": "I-75 N/S", "lat": 41.9530, "lng": -83.4110},
    {"state": "MI", "name": "Grass Lake", "hwy": "I-94 E/W", "lat": 42.2610, "lng": -84.2130},
    {"state": "KY", "name": "Kenton County", "hwy": "I-71/75 S", "lat": 38.9370, "lng": -84.5410},
    {"state": "KY", "name": "Simpson County", "hwy": "I-65 N", "lat": 36.7620, "lng": -86.5980},
    {"state": "TN", "name": "Knox County", "hwy": "I-40/75", "lat": 35.9130, "lng": -84.1550},
    {"state": "TN", "name": "Robertson County", "hwy": "I-65 S", "lat": 36.5680, "lng": -86.6980},
    {"state": "GA", "name": "Ringgold", "hwy": "I-75 S", "lat": 34.9160, "lng": -85.1310},
    {"state": "GA", "name": "Columbia County", "hwy": "I-20 E/W", "lat": 33.5450, "lng": -82.2280},
    {"state": "FL", "name": "Wildwood", "hwy": "I-75 N/S", "lat": 28.8420, "lng": -82.0570},
    {"state": "FL", "name": "Yulee", "hwy": "I-95 S", "lat": 30.6360, "lng": -81.5730},
    {"state": "AL", "name": "Heflin", "hwy": "I-20 E/W", "lat": 33.6440, "lng": -85.5960},
    {"state": "MS", "name": "Meridian", "hwy": "I-20/59", "lat": 32.3520, "lng": -88.6470},
    {"state": "NC", "name": "Hendersonville", "hwy": "I-26 E/W", "lat": 35.3480, "lng": -82.4420},
    {"state": "NC", "name": "Charlotte (I-77)", "hwy": "I-77 N/S", "lat": 35.4230, "lng": -80.8770},
    {"state": "SC", "name": "Blacksburg", "hwy": "I-85 N/S", "lat": 35.1140, "lng": -81.5210},
    {"state": "VA", "name": "Troutville", "hwy": "I-81 N/S", "lat": 37.4210, "lng": -79.8770},
    {"state": "VA", "name": "Dumfries", "hwy": "I-95 N/S", "lat": 38.5720, "lng": -77.3280},
    {"state": "PA", "name": "Mifflin County", "hwy": "US-322 / I-99", "lat": 40.5680, "lng": -77.5960},
    {"state": "PA", "name": "Greencastle", "hwy": "I-81 N/S", "lat": 39.7530, "lng": -77.7370},
    {"state": "NY", "name": "Schodack", "hwy": "I-90 E/W", "lat": 42.5290, "lng": -73.6920},
    {"state": "NJ", "name": "Knowlton", "hwy": "I-80 E/W", "lat": 40.9200, "lng": -75.0430},
    {"state": "MD", "name": "Perryville", "hwy": "I-95 N/S", "lat": 39.5680, "lng": -76.0730},
    {"state": "WV", "name": "Hurricane", "hwy": "I-64 E/W", "lat": 38.4270, "lng": -82.0180},
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dist_mi(lat1, lng1, lat2, lng2) -> float:
    r = 3958.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _seg_dist_mi(lat, lng, a, b) -> float:
    ax, ay, bx, by, px, py = a[1], a[0], b[1], b[0], lng, lat
    dx, dy = bx - ax, by - ay
    if dx == dy == 0:
        return _dist_mi(lat, lng, a[0], a[1])
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return _dist_mi(lat, lng, ay + t * dy, ax + t * dx)


def _station_advice(st: Dict[str, Any], hour_ct: int) -> Dict[str, Any]:
    likely_open = 6 <= hour_ct <= 20
    stop_required = likely_open
    tips = []
    if likely_open:
        tips.append("Likely OPEN this hour — plan to pull in unless bypass-approved.")
        tips.append("PrePass/Drivewyze users: watch for green light 1 mile out; red = pull in.")
    else:
        tips.append("Likely closed this hour, but ramp signage rules — if signed OPEN, stop.")
    tips.append("Have ELD, medical card, registration & rate con packet ready.")
    return {"likely_open": likely_open, "stop_required": stop_required, "advice": " ".join(tips)}


class Point(BaseModel):
    lat: float
    lon: float


class RouteAdviceIn(BaseModel):
    origin: Point
    dest: Point
    geometry: Optional[List[List[float]]] = None   # [[lat,lng]...]
    corridor_miles: float = 20.0


class LoadRouteIn(BaseModel):
    load_id: Optional[str] = None
    origin: Optional[str] = None
    destination: Optional[str] = None
    corridor_miles: float = 20.0


async def _full_route_geometry(o: Coord, d: Coord) -> Optional[Dict[str, Any]]:
    url = f"{OSRM_BASE_URL}/route/v1/driving/{o.lng},{o.lat};{d.lng},{d.lat}"
    try:
        async with httpx.AsyncClient(timeout=12.0) as c:
            r = await c.get(url, params={"overview": "full", "geometries": "geojson"})
            r.raise_for_status()
            routes = r.json().get("routes") or []
            if not routes:
                return None
            rt = routes[0]
            return {"provider": "osrm", "distance_m": rt.get("distance"),
                    "geometry": rt.get("geometry")}
    except Exception:
        return None


def _corridor_hits(pts: List[List[float]], corridor_miles: float, hour_ct: int) -> List[Dict[str, Any]]:
    step = max(1, len(pts) // 400)
    samples = pts[::step] + [pts[-1]]
    hits = []
    for s in WEIGH_STATIONS:
        best = min(_seg_dist_mi(s["lat"], s["lng"], samples[i], samples[i + 1])
                   for i in range(len(samples) - 1)) if len(samples) > 1 else 1e9
        if best <= corridor_miles:
            hits.append({**s, "off_route_mi": round(best, 1), **_station_advice(s, hour_ct)})
    return hits


def _route_summary(hits: List[Dict[str, Any]], hour_ct: int, o_label: str, d_label: str,
                   distance_mi: Optional[float]) -> str:
    open_hits = [h for h in hits if h["likely_open"]]
    dist_txt = f" ({distance_mi:,.0f} mi)" if distance_mi else ""
    return (f"Route scan {o_label} → {d_label}{dist_txt}: {len(hits)} weigh station(s) on this corridor, "
            f"{len(open_hits)} likely open right now ({hour_ct:02d}:00 CT). "
            + (f"Plan stops at: {', '.join(h['name'] + ' (' + h['state'] + ' · ' + h['hwy'] + ')' for h in open_hits[:4])}. "
               if open_hits else "No open scales expected — drive on, but obey ramp signage. ")
            + "Bypass devices (PrePass/Drivewyze) may waive pull-ins at green-light sites; "
              "always stop on red or posted OPEN.")


class LaneNoteIn(BaseModel):
    origin: str
    destination: str
    instructions: str
    flags: List[str] = []          # e.g. ["no-dock", "liftgate-required"]
    shipper: str = ""


def build_reference_router(*, db, get_current_user: Callable) -> APIRouter:
    router = APIRouter(prefix="/reference", tags=["reference"])

    @router.get("/weigh-stations")
    async def weigh_stations(state: Optional[str] = None, _=Depends(get_current_user)):
        hour_ct = (datetime.now(timezone.utc).hour - 6) % 24
        rows = [{**s, **_station_advice(s, hour_ct)} for s in WEIGH_STATIONS
                if not state or s["state"] == state.upper()]
        return {"stations": rows, "count": len(rows), "hour_ct": hour_ct}

    @router.post("/weigh-stations/route-advice")
    async def route_advice(payload: RouteAdviceIn, _=Depends(get_current_user)):
        hour_ct = (datetime.now(timezone.utc).hour - 6) % 24
        pts = payload.geometry or [[payload.origin.lat, payload.origin.lon],
                                   [payload.dest.lat, payload.dest.lon]]
        step = max(1, len(pts) // 60)
        samples = pts[::step] + [pts[-1]]
        hits = []
        for s in WEIGH_STATIONS:
            best = min(_seg_dist_mi(s["lat"], s["lng"], samples[i], samples[i + 1])
                       for i in range(len(samples) - 1)) if len(samples) > 1 else 1e9
            if best <= payload.corridor_miles:
                hits.append({**s, "off_route_mi": round(best, 1), **_station_advice(s, hour_ct)})
        hits.sort(key=lambda h: _dist_mi(payload.origin.lat, payload.origin.lon, h["lat"], h["lng"]))
        open_hits = [h for h in hits if h["likely_open"]]
        summary = (f"AI route scan: {len(hits)} weigh station(s) on this corridor, "
                   f"{len(open_hits)} likely open right now ({hour_ct:02d}:00 CT). "
                   + (f"Plan stops at: {', '.join(h['name'] + ' (' + h['state'] + ' · ' + h['hwy'] + ')' for h in open_hits[:4])}. "
                      if open_hits else "No open scales expected — drive on, but obey ramp signage. ")
                   + "Bypass devices (PrePass/Drivewyze) may waive pull-ins at green-light sites; "
                     "always stop on red or posted OPEN.")
        return {"stations": hits, "likely_open_count": len(open_hits),
                "hour_ct": hour_ct, "ai_summary": summary}

    @router.get("/active-loads")
    async def active_loads(_=Depends(get_current_user)):
        rows = await db.brokerage_bookings.find(
            {"status": {"$in": ["booked", "pending_review"]}},
            {"_id": 0, "booked_id": 1, "reference": 1, "origin": 1, "destination": 1,
             "origin_full": 1, "destination_full": 1, "status": 1, "pickup_date": 1,
             "carrier_name": 1, "equipment": 1},
        ).sort("booked_at", -1).to_list(50)
        return {"loads": rows, "count": len(rows)}

    @router.post("/weigh-stations/load-route")
    async def load_route_advice(payload: LoadRouteIn, _=Depends(get_current_user)):
        hour_ct = (datetime.now(timezone.utc).hour - 6) % 24
        o = d = None
        o_label, d_label = payload.origin or "", payload.destination or ""
        if payload.load_id:
            bk = await db.brokerage_bookings.find_one({"booked_id": payload.load_id}, {"_id": 0})
            if not bk:
                raise HTTPException(404, "Load not found")
            o_label, d_label = bk.get("origin", ""), bk.get("destination", "")
            of, df = bk.get("origin_full") or {}, bk.get("destination_full") or {}
            if of.get("lat") and of.get("lng"):
                o = Coord(lat=of["lat"], lng=of["lng"])
            if df.get("lat") and df.get("lng"):
                d = Coord(lat=df["lat"], lng=df["lng"])
        if o is None:
            if not o_label:
                raise HTTPException(400, "Provide a load_id or origin/destination")
            o = (await _mapbox_geocode(o_label)) or (await _osm_geocode(o_label))
        if d is None:
            if not d_label:
                raise HTTPException(400, "Provide a load_id or origin/destination")
            d = (await _mapbox_geocode(d_label)) or (await _osm_geocode(d_label))
        if o is None or d is None:
            raise HTTPException(422, "Could not geocode origin or destination — try 'City, ST' format")

        route = await _full_route_geometry(o, d)
        if route and route.get("geometry", {}).get("coordinates"):
            pts = [[c[1], c[0]] for c in route["geometry"]["coordinates"]]
            distance_mi = round((route.get("distance_m") or 0) / 1609.34, 1) or None
            provider = route.get("provider")
        else:
            pts = [[o.lat, o.lng], [d.lat, d.lng]]
            distance_mi = round(_dist_mi(o.lat, o.lng, d.lat, d.lng) * 1.2, 1)
            provider = "estimate"

        hits = _corridor_hits(pts, payload.corridor_miles, hour_ct)
        hits.sort(key=lambda h: _dist_mi(o.lat, o.lng, h["lat"], h["lng"]))
        gstep = max(1, len(pts) // 500)
        geometry_out = pts[::gstep] + [pts[-1]]
        return {
            "stations": hits,
            "likely_open_count": sum(1 for h in hits if h["likely_open"]),
            "hour_ct": hour_ct,
            "geometry": geometry_out,
            "origin": {"lat": o.lat, "lng": o.lng, "label": o_label},
            "destination": {"lat": d.lat, "lng": d.lng, "label": d_label},
            "distance_mi": distance_mi,
            "route_provider": provider,
            "ai_summary": _route_summary(hits, hour_ct, o_label or "origin", d_label or "destination", distance_mi),
        }

    # ---------------- Lane notes ----------------
    def _key(o: str, d: str) -> str:
        return f"{o.strip().lower()}|{d.strip().lower()}"

    @router.get("/lane-notes")
    async def list_notes(origin: Optional[str] = None, destination: Optional[str] = None,
                         _=Depends(get_current_user)):
        q = {}
        if origin and destination:
            q = {"lane_key": _key(origin, destination)}
        rows = await db.lane_notes.find(q, {"_id": 0}).sort("updated_at", -1).to_list(200)
        return {"notes": rows}

    @router.post("/lane-notes")
    async def upsert_note(payload: LaneNoteIn, _=Depends(get_current_user)):
        key = _key(payload.origin, payload.destination)
        doc = {**payload.model_dump(), "lane_key": key, "updated_at": _now_iso()}
        existing = await db.lane_notes.find_one({"lane_key": key})
        if existing:
            await db.lane_notes.update_one({"lane_key": key}, {"$set": doc})
        else:
            doc["id"] = str(uuid.uuid4())
            doc["created_at"] = _now_iso()
            await db.lane_notes.insert_one(dict(doc))
        doc.pop("_id", None)
        return {"ok": True, "note": doc}

    @router.delete("/lane-notes/{note_id}")
    async def delete_note(note_id: str, _=Depends(get_current_user)):
        res = await db.lane_notes.delete_one({"id": note_id})
        if res.deleted_count == 0:
            raise HTTPException(404, "Note not found")
        return {"ok": True}

    return router
