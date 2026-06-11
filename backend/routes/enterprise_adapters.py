"""routes.enterprise_adapters — third-party integration adapters with
graceful mock-mode fallback. Each adapter:

  · Reads credentials from the Connections vault (/api/connections)
  · If credentials present  → live API call
  · If credentials absent   → realistic synthetic response (clearly tagged)

Integrations:
  1. Mileage (PC*Miler / OpenRouteService) — replaces state-centroid haversine
  2. Parcel Rater (FedEx + UPS) — live rate quotes for parcel
  3. GPS Tracking (project44 / FourKites) — real-time shipment status
  4. EDI Gateway (SPS Commerce) — 204/210/214/990/856
  5. WMS / Yard Automation (AutoStore / Generic) — wave + pick + dock
  6. Load Board (DAT One) — replaces median × 1.04 proxy with live rates
  7. Freight Audit ML — statistical anomaly detection (no key needed)
"""
from __future__ import annotations

import logging
import math
import os
import statistics
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

import httpx
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger("tennant_tms.enterprise_adapters")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ============================ CONNECTION HELPER ============================
async def _get_creds(db, slug: str) -> Optional[Dict[str, Any]]:
    """Fetch decrypted credentials for an integration from the connections vault."""
    try:
        from routes.connections import get_connection_credentials
        return await get_connection_credentials(db, slug)
    except Exception as e:                                              # noqa: BLE001
        logger.info("Connection lookup failed for %s: %s", slug, e)
        return None


# ============================ 1 · MILEAGE ADAPTER ============================
# State centroids for haversine fallback
_STATE_CENTROID = {
    "AL": (32.8, -86.8), "AK": (64.2, -149.4), "AZ": (34.0, -111.7),
    "AR": (34.7, -92.4), "CA": (36.8, -119.4), "CO": (39.0, -105.6),
    "CT": (41.6, -72.7), "DE": (38.9, -75.5), "FL": (27.8, -81.7),
    "GA": (32.6, -83.4), "HI": (20.8, -156.3), "ID": (44.4, -114.5),
    "IL": (40.0, -89.1), "IN": (39.9, -86.3), "IA": (42.0, -93.5),
    "KS": (38.5, -98.4), "KY": (37.5, -85.3), "LA": (31.0, -91.8),
    "ME": (45.4, -69.2), "MD": (39.0, -76.7), "MA": (42.2, -71.5),
    "MI": (44.3, -85.4), "MN": (46.3, -94.3), "MS": (32.7, -89.7),
    "MO": (38.4, -92.3), "MT": (47.0, -109.6), "NE": (41.5, -99.8),
    "NV": (39.3, -116.6), "NH": (43.7, -71.6), "NJ": (40.2, -74.5),
    "NM": (34.4, -106.1), "NY": (42.9, -75.5), "NC": (35.6, -79.8),
    "ND": (47.5, -100.5), "OH": (40.3, -82.8), "OK": (35.5, -97.5),
    "OR": (44.0, -120.5), "PA": (40.6, -77.2), "RI": (41.7, -71.5),
    "SC": (33.9, -80.9), "SD": (44.4, -100.2), "TN": (35.7, -86.7),
    "TX": (31.0, -97.6), "UT": (39.3, -111.7), "VT": (44.1, -72.7),
    "VA": (37.5, -78.9), "WA": (47.4, -120.4), "WV": (38.5, -80.6),
    "WI": (44.3, -89.6), "WY": (42.8, -107.3),
}


def _extract_state(loc: str) -> Optional[str]:
    if not loc:
        return None
    for part in reversed([p.strip() for p in loc.split(",")]):
        if part[:2].upper() in _STATE_CENTROID:
            return part[:2].upper()
    return None


def _haversine_miles(o: str, d: str) -> float:
    os_, ds_ = _extract_state(o), _extract_state(d)
    if not os_ or not ds_:
        return 750.0
    if os_ == ds_:
        return 250.0
    (la1, lo1), (la2, lo2) = _STATE_CENTROID[os_], _STATE_CENTROID[ds_]
    R = 3958.8
    p1, p2 = math.radians(la1), math.radians(la2)
    dp, dl = math.radians(la2 - la1), math.radians(lo2 - lo1)
    a = math.sin(dp/2)**2 + math.cos(p1) * math.cos(p2) * math.sin(dl/2)**2
    return round(2 * R * math.asin(math.sqrt(a)) * 1.18, 0)


async def _ors_geocode(client: httpx.AsyncClient, query: str,
                          api_key: str) -> Optional[Dict[str, float]]:
    r = await client.get("https://api.openrouteservice.org/geocode/search",
                          params={"api_key": api_key, "text": query, "size": 1})
    if r.status_code != 200:
        return None
    feats = r.json().get("features") or []
    if not feats:
        return None
    coords = feats[0]["geometry"]["coordinates"]
    return {"lon": coords[0], "lat": coords[1]}


class MileageIn(BaseModel):
    origin: str
    destination: str
    via: Optional[List[str]] = None


async def get_mileage(db, payload: MileageIn) -> Dict[str, Any]:
    """Live PC*Miler → OpenRouteService → haversine fallback."""
    # PC*Miler (paid, weights road class restrictions, hazmat routes)
    pcm = await _get_creds(db, "pcmiler")
    if pcm and pcm.get("api_key"):
        try:
            async with httpx.AsyncClient(timeout=12) as client:
                r = await client.get(
                    "https://pcmiler.alk.com/apis/rest/v1.0/Service.svc/route/routeReports",
                    params={"stops": f"{payload.origin};{payload.destination}",
                             "authToken": pcm["api_key"]})
                if r.status_code == 200:
                    data = r.json()
                    miles = data[0]["TMiles"] if isinstance(data, list) and data else None
                    if miles:
                        return {"miles": round(float(miles), 0),
                                "source": "pcmiler", "live": True,
                                "minutes_est": int(float(miles) / 50 * 60)}
        except Exception as exc:                                          # noqa: BLE001
            logger.warning("PC*Miler error: %s", exc)

    # OpenRouteService (free tier, 2,000 calls/day)
    ors = await _get_creds(db, "openrouteservice")
    if ors and ors.get("api_key"):
        try:
            async with httpx.AsyncClient(timeout=12) as client:
                o = await _ors_geocode(client, payload.origin, ors["api_key"])
                d = await _ors_geocode(client, payload.destination, ors["api_key"])
                if o and d:
                    r = await client.post(
                        "https://api.openrouteservice.org/v2/directions/driving-hgv",
                        headers={"Authorization": ors["api_key"],
                                  "Content-Type": "application/json"},
                        json={"coordinates": [[o["lon"], o["lat"]], [d["lon"], d["lat"]]],
                              "units": "mi"})
                    if r.status_code == 200:
                        body = r.json()
                        s = body["routes"][0]["summary"]
                        return {"miles": round(s["distance"], 0),
                                "source": "openrouteservice", "live": True,
                                "minutes_est": int(s["duration"] / 60)}
        except Exception as exc:                                          # noqa: BLE001
            logger.warning("ORS error: %s", exc)

    # Haversine fallback
    miles = _haversine_miles(payload.origin, payload.destination)
    return {"miles": miles, "source": "haversine_fallback", "live": False,
            "minutes_est": int(miles / 50 * 60),
            "note": "Approximate — add PC*Miler or OpenRouteService key for live road miles."}


# ============================ 2 · PARCEL RATER ============================
class ParcelRateIn(BaseModel):
    origin_zip: str
    destination_zip: str
    weight_lbs: float = Field(..., gt=0, le=150)
    length_in: float = Field(12, gt=0)
    width_in: float = Field(12, gt=0)
    height_in: float = Field(12, gt=0)
    residential: bool = False
    services: Optional[List[str]] = None    # ["GROUND","2_DAY","NEXT_DAY"]


async def quote_parcel(db, payload: ParcelRateIn) -> Dict[str, Any]:
    """Live FedEx Web Services + UPS OAuth Rate API → heuristic fallback."""
    results: List[Dict[str, Any]] = []
    live = False

    # FedEx (OAuth2 — Web Services API)
    fedex = await _get_creds(db, "fedex")
    if fedex and fedex.get("api_key") and fedex.get("api_secret"):
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                tok_r = await client.post(
                    "https://apis.fedex.com/oauth/token",
                    data={"grant_type": "client_credentials",
                           "client_id": fedex["api_key"],
                           "client_secret": fedex["api_secret"]})
                if tok_r.status_code == 200:
                    access = tok_r.json()["access_token"]
                    r = await client.post(
                        "https://apis.fedex.com/rate/v1/rates/quotes",
                        headers={"Authorization": f"Bearer {access}",
                                  "Content-Type": "application/json"},
                        json={
                            "accountNumber": {"value": fedex.get("account_number", "0")},
                            "requestedShipment": {
                                "shipper": {"address": {"postalCode": payload.origin_zip, "countryCode": "US"}},
                                "recipient": {"address": {"postalCode": payload.destination_zip, "countryCode": "US", "residential": payload.residential}},
                                "pickupType": "USE_SCHEDULED_PICKUP",
                                "rateRequestType": ["LIST", "ACCOUNT"],
                                "requestedPackageLineItems": [{
                                    "weight": {"units": "LB", "value": payload.weight_lbs},
                                    "dimensions": {"length": payload.length_in,
                                                   "width": payload.width_in,
                                                   "height": payload.height_in, "units": "IN"}}]}})
                    if r.status_code == 200:
                        live = True
                        for rd in r.json().get("output", {}).get("rateReplyDetails", []):
                            amt = rd.get("ratedShipmentDetails", [{}])[0].get("totalNetCharge")
                            results.append({"carrier": "FedEx", "service": rd.get("serviceName"),
                                             "rate_usd": float(amt) if amt else None,
                                             "transit_days": rd.get("operationalDetail", {}).get("transitTime"),
                                             "live": True})
        except Exception as exc:                                          # noqa: BLE001
            logger.warning("FedEx rater error: %s", exc)

    # UPS (OAuth2 — Rate API)
    ups = await _get_creds(db, "ups")
    if ups and ups.get("api_key") and ups.get("api_secret"):
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                tok_r = await client.post(
                    "https://onlinetools.ups.com/security/v1/oauth/token",
                    auth=(ups["api_key"], ups["api_secret"]),
                    data={"grant_type": "client_credentials"})
                if tok_r.status_code == 200:
                    access = tok_r.json()["access_token"]
                    r = await client.post(
                        "https://onlinetools.ups.com/api/rating/v2403/Shop",
                        headers={"Authorization": f"Bearer {access}",
                                  "Content-Type": "application/json"},
                        json={"RateRequest": {
                            "Shipment": {
                                "Shipper": {"Address": {"PostalCode": payload.origin_zip, "CountryCode": "US"}},
                                "ShipTo": {"Address": {"PostalCode": payload.destination_zip, "CountryCode": "US", "ResidentialAddressIndicator": "" if not payload.residential else "1"}},
                                "ShipFrom": {"Address": {"PostalCode": payload.origin_zip, "CountryCode": "US"}},
                                "Package": {"PackagingType": {"Code": "02"},
                                            "Dimensions": {"UnitOfMeasurement": {"Code": "IN"},
                                                           "Length": str(payload.length_in), "Width": str(payload.width_in), "Height": str(payload.height_in)},
                                            "PackageWeight": {"UnitOfMeasurement": {"Code": "LBS"}, "Weight": str(payload.weight_lbs)}}}}})
                    if r.status_code == 200:
                        live = True
                        for rs in r.json().get("RateResponse", {}).get("RatedShipment", []):
                            results.append({"carrier": "UPS",
                                             "service": rs.get("Service", {}).get("Code"),
                                             "rate_usd": float(rs.get("TotalCharges", {}).get("MonetaryValue", 0)),
                                             "transit_days": rs.get("GuaranteedDelivery", {}).get("BusinessDaysInTransit"),
                                             "live": True})
        except Exception as exc:                                          # noqa: BLE001
            logger.warning("UPS rater error: %s", exc)

    # Heuristic fallback
    if not results:
        # Distance proxy via ZIP first-3 digit diff
        dist_proxy = abs(int(payload.origin_zip[:3]) - int(payload.destination_zip[:3])) * 7
        for svc, mult, days in [("GROUND", 1.0, 3), ("2_DAY", 1.8, 2), ("NEXT_DAY", 3.2, 1)]:
            base = 8 + payload.weight_lbs * 0.45 + dist_proxy * 0.01
            if payload.residential:
                base += 4.95
            for carrier in ("FedEx", "UPS"):
                results.append({
                    "carrier": carrier, "service": svc,
                    "rate_usd": round(base * mult, 2),
                    "transit_days": days, "live": False})

    results.sort(key=lambda r: (r["rate_usd"] or 9999))
    if results:
        cheapest = results[0]
        cheapest["badges"] = ["CHEAPEST"]
        fastest = min(results, key=lambda r: r["transit_days"] or 99)
        if fastest is not cheapest:
            fastest["badges"] = fastest.get("badges", []) + ["FASTEST"]

    return {"origin_zip": payload.origin_zip,
            "destination_zip": payload.destination_zip,
            "weight_lbs": payload.weight_lbs,
            "rates": results, "live": live,
            "source": "fedex+ups_live" if live else "heuristic_fallback",
            "quoted_at": _now()}


# ============================ 3 · GPS TRACKING ============================
class TrackingIn(BaseModel):
    booking_id: str
    carrier_scac: Optional[str] = None
    carrier_pro: Optional[str] = None
    bol_number: Optional[str] = None


async def gps_track(db, payload: TrackingIn) -> Dict[str, Any]:
    """project44 → FourKites → internal driver PWA fallback."""
    # project44
    p44 = await _get_creds(db, "project44")
    if p44 and p44.get("api_key"):
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    f"https://na12.api.project44.com/api/v4/tl/shipments/identifiers/bolNumber/{payload.bol_number}/statusUpdates",
                    headers={"Authorization": f"Bearer {p44['api_key']}"})
                if r.status_code == 200:
                    body = r.json()
                    return {"booking_id": payload.booking_id,
                            "source": "project44", "live": True,
                            "events": body.get("statusUpdates", []),
                            "current_status": body.get("currentStatus")}
        except Exception as exc:                                          # noqa: BLE001
            logger.warning("project44 error: %s", exc)

    # FourKites
    fk = await _get_creds(db, "fourkites")
    if fk and fk.get("api_key") and fk.get("customer_id"):
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    f"https://api.fourkites.com/api/v2/shipments?customerId={fk['customer_id']}&bolNumber={payload.bol_number}",
                    headers={"Authorization": f"Bearer {fk['api_key']}"})
                if r.status_code == 200:
                    return {"booking_id": payload.booking_id,
                            "source": "fourkites", "live": True,
                            "events": r.json().get("data", [])}
        except Exception as exc:                                          # noqa: BLE001
            logger.warning("FourKites error: %s", exc)

    # Internal Driver PWA fallback
    booking = await db.brokerage_bookings.find_one(
        {"$or": [{"booked_id": payload.booking_id}, {"booking_id": payload.booking_id}]},
        {"_id": 0, "driver_updates": 1, "status": 1, "last_driver_location": 1})
    if not booking:
        return {"source": "none", "live": False, "events": [],
                "note": "No external tracking available; add project44 or FourKites key."}
    return {"booking_id": payload.booking_id,
            "source": "driver_pwa", "live": True,
            "current_status": booking.get("status"),
            "current_location": booking.get("last_driver_location"),
            "events": booking.get("driver_updates", [])}


# ============================ 4 · EDI GATEWAY (SPS Commerce) ============================
class EdiInboundIn(BaseModel):
    edi_type: str       # 204 | 210 | 214 | 990 | 856
    sender_isa: str
    receiver_isa: str
    payload: Dict[str, Any]


async def edi_inbound(db, payload: EdiInboundIn,
                         user_name: str = "system") -> Dict[str, Any]:
    """Receive EDI transactions, persist, and emit ack if SPS Commerce wired."""
    if payload.edi_type not in ("204", "210", "214", "990", "856"):
        raise HTTPException(400, f"Unsupported EDI type: {payload.edi_type}")
    doc = {
        "edi_id": f"EDI-{uuid.uuid4().hex[:10].upper()}",
        "edi_type": payload.edi_type,
        "direction": "inbound",
        "sender_isa": payload.sender_isa,
        "receiver_isa": payload.receiver_isa,
        "payload": payload.payload,
        "received_at": _now(),
        "received_by": user_name,
        "status": "received",
    }
    await db.enterprise_edi_log.insert_one(dict(doc))
    doc.pop("_id", None)

    # Try to emit 990 (response) automatically for 204 (tender)
    if payload.edi_type == "204":
        ack = {
            "edi_id": f"EDI-{uuid.uuid4().hex[:10].upper()}",
            "edi_type": "990",
            "direction": "outbound",
            "in_response_to": doc["edi_id"],
            "sender_isa": payload.receiver_isa,
            "receiver_isa": payload.sender_isa,
            "payload": {"response_code": "A", "shipment_id": payload.payload.get("shipment_id")},
            "received_at": _now(),
            "status": "queued_outbound",
        }
        await db.enterprise_edi_log.insert_one(dict(ack))

    # If SPS Commerce wired, post via their API
    sps = await _get_creds(db, "sps_commerce")
    if sps and sps.get("api_key"):
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.post(
                    "https://api.spscommerce.com/v1/transactions",
                    headers={"Authorization": f"Bearer {sps['api_key']}",
                              "Content-Type": "application/json"},
                    json=payload.payload)
                doc["sps_posted"] = r.status_code == 200
        except Exception as exc:                                          # noqa: BLE001
            doc["sps_error"] = str(exc)[:200]

    return {"ok": True, "edi_id": doc["edi_id"], "status": doc["status"],
            "auto_ack_sent": payload.edi_type == "204"}


# ============================ 5 · WMS / AUTOSTORE ============================
class WmsWaveIn(BaseModel):
    wave_id: Optional[str] = None
    facility: str
    order_ids: List[str]
    target_release_at: Optional[str] = None
    aligned_shipment_ids: List[str] = Field(default_factory=list)


async def wms_release_wave(db, payload: WmsWaveIn,
                              user_name: str = "system") -> Dict[str, Any]:
    """Release a pick wave. AutoStore live mode if creds present."""
    doc = {
        "wave_id": payload.wave_id or f"WV-{uuid.uuid4().hex[:8].upper()}",
        "facility": payload.facility,
        "order_ids": payload.order_ids,
        "aligned_shipment_ids": payload.aligned_shipment_ids,
        "target_release_at": payload.target_release_at or _now(),
        "released_at": _now(),
        "released_by": user_name,
        "status": "released",
        "pick_tasks_generated": len(payload.order_ids),
    }
    autostore = await _get_creds(db, "autostore")
    if autostore and autostore.get("api_key") and autostore.get("base_url"):
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.post(
                    f"{autostore['base_url']}/api/wave/release",
                    headers={"Authorization": f"Bearer {autostore['api_key']}"},
                    json={"orders": payload.order_ids, "facility": payload.facility})
                doc["autostore_released"] = r.status_code in (200, 201)
                doc["live"] = True
        except Exception as exc:                                          # noqa: BLE001
            doc["autostore_error"] = str(exc)[:200]
            doc["live"] = False
    else:
        doc["live"] = False
        doc["note"] = "AutoStore creds absent — wave logged for manual pick."

    await db.enterprise_wms_waves.insert_one(dict(doc))
    doc.pop("_id", None)
    return doc


# ============================ 6 · LOAD BOARD (DAT One) ============================
class DatRateIn(BaseModel):
    origin: str
    destination: str
    equipment: str = "Dry Van"


async def dat_spot_rate(db, payload: DatRateIn) -> Dict[str, Any]:
    """DAT One live rate snapshot → median-of-historical fallback."""
    dat = await _get_creds(db, "dat_one")
    if dat and dat.get("api_key"):
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    "https://analytics.api.dat.com/linehaulrates/v3/lookups",
                    headers={"Authorization": f"Bearer {dat['api_key']}"},
                    params={"origin": payload.origin,
                             "destination": payload.destination,
                             "equipment": payload.equipment})
                if r.status_code == 200:
                    body = r.json()
                    return {"source": "dat_one", "live": True,
                            "avg_usd": body.get("averageLinehaul"),
                            "low_usd": body.get("lowLinehaul"),
                            "high_usd": body.get("highLinehaul"),
                            "samples": body.get("rateUsageCount")}
        except Exception as exc:                                          # noqa: BLE001
            logger.warning("DAT One error: %s", exc)

    # Fallback: query own bookings for same lane median
    o_state = _extract_state(payload.origin) or ""
    d_state = _extract_state(payload.destination) or ""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=120)).isoformat()
    bookings = await db.brokerage_bookings.find({
        "$and": [{"$or": [{"created_at": {"$gte": cutoff}}, {"booked_at": {"$gte": cutoff}}]},
                 {"equipment": payload.equipment},
                 {"origin": {"$regex": f", {o_state}"}},
                 {"destination": {"$regex": f", {d_state}"}}]},
        {"_id": 0, "rate_usd": 1, "customer_rate_usd": 1}).to_list(500)
    rates = sorted([float(b.get("customer_rate_usd") or b.get("rate_usd") or 0)
                     for b in bookings if (b.get("customer_rate_usd") or b.get("rate_usd"))])
    if not rates:
        return {"source": "none", "live": False, "note":
                "No DAT key and no historical bookings. Add DAT One key for live spot rates."}
    median = rates[len(rates) // 2]
    return {"source": "historical_median", "live": False,
            "avg_usd": round(sum(rates) / len(rates), 2),
            "low_usd": rates[0], "high_usd": rates[-1],
            "median_usd": median,
            "samples": len(rates),
            "note": "Using internal historical median. Add DAT One key for live market."}


# ============================ 7 · FREIGHT AUDIT ML ============================
class AuditMlIn(BaseModel):
    window_days: int = Field(180, ge=30, le=730)
    z_threshold: float = Field(2.0, ge=1.0, le=5.0)


async def freight_audit_ml(db, payload: AuditMlIn) -> Dict[str, Any]:
    """Statistical anomaly detection on carrier invoices. Computes per-lane
    baseline (median, MAD) from delivered bookings and flags invoices whose
    z-score |z| > threshold. No external ML key needed."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=payload.window_days)).isoformat()
    bookings = await db.brokerage_bookings.find(
        {"$or": [{"created_at": {"$gte": cutoff}}, {"booked_at": {"$gte": cutoff}}],
          "status": "delivered"}, {"_id": 0}).to_list(5000)

    # Group by (origin_state, destination_state, equipment) → list of rates
    lane_rates: Dict[tuple, List[float]] = {}
    for b in bookings:
        o = _extract_state(b.get("origin", ""))
        d = _extract_state(b.get("destination", ""))
        eq = b.get("equipment") or "Dry Van"
        if not o or not d:
            continue
        rate = float(b.get("carrier_rate_usd") or b.get("settled_carrier_pay_usd")
                       or b.get("rate_usd") or 0)
        if rate <= 0:
            continue
        lane_rates.setdefault((o, d, eq), []).append(rate)

    # Build per-lane baselines
    baselines: Dict[str, Dict[str, Any]] = {}
    for (o, d, eq), rates in lane_rates.items():
        if len(rates) < 3:
            continue
        med = statistics.median(rates)
        # Median Absolute Deviation — robust to outliers
        mad = statistics.median([abs(r - med) for r in rates]) or 1.0
        baselines[f"{o}-{d}-{eq}"] = {
            "lane": f"{o} → {d}", "equipment": eq,
            "samples": len(rates), "median_usd": round(med, 2),
            "mad_usd": round(mad, 2),
            "p25_usd": round(rates[int(len(rates)*0.25)], 2) if len(rates) >= 4 else None,
            "p75_usd": round(rates[int(len(rates)*0.75)], 2) if len(rates) >= 4 else None,
        }

    # Score every booking; flag outliers
    flagged: List[Dict[str, Any]] = []
    for b in bookings:
        o = _extract_state(b.get("origin", ""))
        d = _extract_state(b.get("destination", ""))
        eq = b.get("equipment") or "Dry Van"
        key = f"{o}-{d}-{eq}"
        if key not in baselines:
            continue
        rate = float(b.get("carrier_rate_usd") or b.get("settled_carrier_pay_usd")
                       or b.get("rate_usd") or 0)
        if rate <= 0:
            continue
        bl = baselines[key]
        # Modified z-score using MAD (Iglewicz & Hoaglin 1993)
        z = 0.6745 * (rate - bl["median_usd"]) / max(bl["mad_usd"], 1.0)
        if abs(z) > payload.z_threshold:
            flagged.append({
                "booking_id": b.get("booked_id") or b.get("booking_id"),
                "carrier": b.get("carrier_name"),
                "lane": bl["lane"], "equipment": eq,
                "invoice_usd": rate,
                "expected_median_usd": bl["median_usd"],
                "delta_usd": round(rate - bl["median_usd"], 2),
                "z_score": round(z, 2),
                "direction": "OVER" if z > 0 else "UNDER",
                "severity": "HIGH" if abs(z) > 4 else "MEDIUM",
                "samples_in_baseline": bl["samples"],
            })

    flagged.sort(key=lambda f: abs(f["z_score"]), reverse=True)
    total_over = sum(f["delta_usd"] for f in flagged if f["direction"] == "OVER")
    total_under = sum(-f["delta_usd"] for f in flagged if f["direction"] == "UNDER")

    return {
        "window_days": payload.window_days,
        "z_threshold": payload.z_threshold,
        "bookings_audited": len(bookings),
        "lanes_modeled": len(baselines),
        "flags": len(flagged),
        "total_overbilled_usd": round(total_over, 2),
        "total_underbilled_usd": round(total_under, 2),
        "estimated_recovery_usd": round(total_over, 2),
        "lane_baselines": list(baselines.values())[:25],
        "anomalies": flagged[:100],
        "model": "modified_z_score_mad",
        "audited_at": _now(),
    }


# ============================ ROUTER ============================
def build_enterprise_adapters_router(
    api_router: APIRouter, *, db,
    get_current_user: Callable, require_role: Callable,
) -> None:
    admin = Depends(require_role("admin", "dispatcher"))
    auth = Depends(get_current_user)
    router = APIRouter(prefix="/enterprise-adapters", tags=["enterprise-adapters"])

    @router.post("/mileage")
    async def adapter_mileage(payload: MileageIn, _=auth) -> Dict[str, Any]:
        return await get_mileage(db, payload)

    @router.post("/parcel-rate")
    async def adapter_parcel(payload: ParcelRateIn, _=auth) -> Dict[str, Any]:
        return await quote_parcel(db, payload)

    @router.post("/gps-track")
    async def adapter_gps(payload: TrackingIn, _=auth) -> Dict[str, Any]:
        return await gps_track(db, payload)

    @router.post("/edi/inbound")
    async def adapter_edi_in(payload: EdiInboundIn, user=admin) -> Dict[str, Any]:
        return await edi_inbound(db, payload,
                                    user_name=getattr(user, "name", "system"))

    @router.get("/edi/log")
    async def adapter_edi_log(edi_type: Optional[str] = None,
                                 direction: Optional[str] = None,
                                 _=auth) -> Dict[str, Any]:
        q: Dict[str, Any] = {}
        if edi_type:
            q["edi_type"] = edi_type
        if direction:
            q["direction"] = direction
        rows = await db.enterprise_edi_log.find(
            q, {"_id": 0}).sort("received_at", -1).limit(200).to_list(200)
        return {"items": rows, "count": len(rows)}

    @router.post("/wms/wave")
    async def adapter_wms_wave(payload: WmsWaveIn, user=admin) -> Dict[str, Any]:
        return await wms_release_wave(db, payload,
                                          user_name=getattr(user, "name", "system"))

    @router.get("/wms/waves")
    async def adapter_wms_list(_=auth) -> Dict[str, Any]:
        rows = await db.enterprise_wms_waves.find(
            {}, {"_id": 0}).sort("released_at", -1).limit(100).to_list(100)
        return {"items": rows, "count": len(rows)}

    @router.post("/dat-spot")
    async def adapter_dat(payload: DatRateIn, _=auth) -> Dict[str, Any]:
        return await dat_spot_rate(db, payload)

    @router.post("/freight-audit-ml")
    async def adapter_audit_ml(payload: AuditMlIn = Body(default=AuditMlIn()),
                                  _=auth) -> Dict[str, Any]:
        return await freight_audit_ml(db, payload)

    # Adapter health: which integrations are live vs mock?
    @router.get("/adapter-status")
    async def adapter_status(_=auth) -> Dict[str, Any]:
        async def check(slug: str, required_keys: List[str]) -> str:
            creds = await _get_creds(db, slug)
            if not creds:
                return "absent"
            for k in required_keys:
                if not creds.get(k):
                    return "partial"
            return "live"

        statuses = {
            "pcmiler": await check("pcmiler", ["api_key"]),
            "openrouteservice": await check("openrouteservice", ["api_key"]),
            "fedex": await check("fedex", ["api_key", "api_secret"]),
            "ups": await check("ups", ["api_key", "api_secret"]),
            "project44": await check("project44", ["api_key"]),
            "fourkites": await check("fourkites", ["api_key", "customer_id"]),
            "sps_commerce": await check("sps_commerce", ["api_key"]),
            "autostore": await check("autostore", ["api_key", "base_url"]),
            "dat_one": await check("dat_one", ["api_key"]),
            "freight_audit_ml": "live",      # no creds needed
        }
        return {"adapters": statuses,
                "live_count": sum(1 for s in statuses.values() if s == "live"),
                "total": len(statuses)}

    api_router.include_router(router)
