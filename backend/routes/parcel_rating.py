"""routes.parcel_rating — FedEx + UPS real-time rating.

Live mode: OAuth2 client-credentials against sandbox/production, returns
carrier rates for a package. Sample mode (no keys wired): deterministic
synthetic rate quotes derived from ZIP-code haversine + carrier service
matrix. Same JSON shape either way.

Endpoints — /api/parcel/*
  GET  /provider           · which carriers are wired live
  POST /quote              · unified rate quote across FedEx + UPS
  POST /connect/fedex      · store FedEx client_id/secret + account
  POST /connect/ups        · store UPS client_id/secret + account
"""
from __future__ import annotations

import logging
import math
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

logger = logging.getLogger("orisei.parcel")

# ZIP-code centroids for a handful of common lanes — used by the sample-
# mode estimator. In live mode carriers geocode ZIPs on their side.
ZIP_CENTROIDS = {
    "30301": (33.7490, -84.3880),  "90210": (34.0900, -118.4065),
    "60601": (41.8858, -87.6229),  "10001": (40.7506, -73.9970),
    "77002": (29.7568, -95.3663),  "85001": (33.4484, -112.0740),
    "94102": (37.7793, -122.4193), "98101": (47.6089, -122.3345),
    "33101": (25.7743, -80.1937),  "80202": (39.7524, -104.9994),
    "37201": (36.1622, -86.7744),  "63101": (38.6270, -90.1994),
}


def _hav_mi(a, b) -> float:
    R = 3958.8
    la1, la2 = math.radians(a[0]), math.radians(b[0])
    dla = math.radians(b[0] - a[0])
    dlo = math.radians(b[1] - a[1])
    h = math.sin(dla / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin(dlo / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def _zip_dist_mi(z1: str, z2: str) -> float:
    a = ZIP_CENTROIDS.get(z1[:5])
    b = ZIP_CENTROIDS.get(z2[:5])
    if not a or not b:
        # crude approximation: numeric ZIP delta
        try:
            return abs(int(z1[:5]) - int(z2[:5])) * 0.35
        except Exception:                                               # noqa: BLE001
            return 500.0
    return _hav_mi(a, b)


class RateIn(BaseModel):
    origin_zip: str = Field(..., min_length=5, max_length=10)
    destination_zip: str = Field(..., min_length=5, max_length=10)
    weight_lbs: float = Field(..., gt=0, le=150)
    length_in: float = Field(12, gt=0, le=108)
    width_in: float = Field(12, gt=0, le=108)
    height_in: float = Field(12, gt=0, le=108)
    package_count: int = Field(1, ge=1, le=50)
    residential: bool = False


class ConnectFedEx(BaseModel):
    client_id: str = Field(..., min_length=8, max_length=200)
    client_secret: str = Field(..., min_length=8, max_length=400)
    account_number: str = Field(..., min_length=4, max_length=32)


class ConnectUPS(BaseModel):
    client_id: str = Field(..., min_length=8, max_length=200)
    client_secret: str = Field(..., min_length=8, max_length=400)
    account_number: str = Field(..., min_length=4, max_length=32)


# --------- Sample-mode rate synthesis (works with zero keys) ---------
_FEDEX_SERVICES = [
    ("FEDEX_GROUND",             "FedEx Ground",             0.60, 4),
    ("FEDEX_HOME_DELIVERY",      "FedEx Home Delivery",      0.65, 4),
    ("FEDEX_2_DAY",              "FedEx 2Day",               1.15, 2),
    ("STANDARD_OVERNIGHT",       "FedEx Standard Overnight", 2.10, 1),
    ("PRIORITY_OVERNIGHT",       "FedEx Priority Overnight", 2.65, 1),
]
_UPS_SERVICES = [
    ("03", "UPS Ground",                 0.58, 4),
    ("12", "UPS 3 Day Select",           0.90, 3),
    ("02", "UPS 2nd Day Air",            1.20, 2),
    ("13", "UPS Next Day Air Saver",     2.00, 1),
    ("01", "UPS Next Day Air",           2.55, 1),
]


def _sample_quote(carrier: str, services, req: RateIn, dist_mi: float) -> List[Dict[str, Any]]:
    """Deterministic pricing: base = $8.50 + weight×$0.55/lb + distance×$0.012/mi,
    then × service-multiplier × package_count × (1.15 if residential)."""
    base = 8.50 + (req.weight_lbs * 0.55) + (dist_mi * 0.012)
    dim_factor = ((req.length_in * req.width_in * req.height_in) / 166) / max(req.weight_lbs, 1)
    if dim_factor > 1:  # dim-weight surcharge
        base *= 1 + min(0.35, (dim_factor - 1) * 0.15)
    out: List[Dict[str, Any]] = []
    for code, name, mult, transit in services:
        # Longer lanes bump air transit by 0 days; ground scales with distance
        eff_transit = transit
        if transit >= 3 and dist_mi > 1500:
            eff_transit = min(6, transit + 1)
        charge = round(base * mult * req.package_count * (1.15 if req.residential else 1.0), 2)
        delivery = (datetime.now(timezone.utc) + timedelta(days=eff_transit)).date().isoformat()
        out.append({
            "carrier": carrier,
            "service_code": code,
            "service_name": name,
            "total_charge": charge,
            "currency": "USD",
            "transit_days": eff_transit,
            "delivery_date": delivery,
        })
    return out


# --------- Live OAuth clients ---------
class _FedExClient:
    def __init__(self):
        self._token: Optional[str] = None
        self._exp: float = 0.0

    def configured(self) -> bool:
        return bool(os.environ.get("FEDEX_CLIENT_ID") and os.environ.get("FEDEX_CLIENT_SECRET"))

    async def token(self) -> Optional[str]:
        if not self.configured():
            return None
        now = time.time()
        if self._token and now < self._exp - 60:
            return self._token
        base = os.environ.get("FEDEX_BASE_URL", "https://apis-sandbox.fedex.com")
        try:
            async with httpx.AsyncClient(timeout=10.0) as c:
                r = await c.post(f"{base}/oauth/token", data={
                    "grant_type": "client_credentials",
                    "client_id": os.environ["FEDEX_CLIENT_ID"],
                    "client_secret": os.environ["FEDEX_CLIENT_SECRET"],
                }, headers={"Content-Type": "application/x-www-form-urlencoded"})
                r.raise_for_status()
                p = r.json()
                self._token = p["access_token"]
                self._exp = now + p.get("expires_in", 3600)
                return self._token
        except Exception as e:                                          # noqa: BLE001
            logger.warning("FedEx token failed: %s", e)
            return None

    async def rate(self, req: RateIn) -> Optional[List[Dict[str, Any]]]:
        tok = await self.token()
        if not tok:
            return None
        base = os.environ.get("FEDEX_BASE_URL", "https://apis-sandbox.fedex.com")
        acct = os.environ.get("FEDEX_ACCOUNT_NUMBER", "")
        payload = {
            "accountNumber": {"value": acct},
            "requestedShipment": {
                "shipper":   {"address": {"postalCode": req.origin_zip,      "countryCode": "US"}},
                "recipient": {"address": {"postalCode": req.destination_zip, "countryCode": "US",
                                            "residential": req.residential}},
                "pickupType": "DROPOFF_AT_FEDEX_LOCATION",
                "rateRequestType": ["ACCOUNT"],
                "requestedPackageLineItems": [{
                    "weight": {"units": "LB", "value": req.weight_lbs},
                    "dimensions": {"length": req.length_in, "width": req.width_in,
                                    "height": req.height_in, "units": "IN"},
                }] * req.package_count,
            },
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as c:
                r = await c.post(f"{base}/rate/v1/rates/quotes", json=payload,
                                 headers={"Authorization": f"Bearer {tok}",
                                          "Content-Type": "application/json"})
                r.raise_for_status()
                data = r.json()
                out = []
                for svc in ((data.get("output") or {}).get("rateReplyDetails") or []):
                    total = ((svc.get("ratedShipmentDetails") or [{}])[0].get("totalNetCharge") or 0)
                    if isinstance(total, dict):
                        total = float(total.get("amount") or 0)
                    out.append({
                        "carrier": "FEDEX",
                        "service_code": svc.get("serviceType", ""),
                        "service_name": svc.get("serviceName") or svc.get("serviceType", ""),
                        "total_charge": float(total),
                        "currency": "USD",
                        "transit_days": svc.get("commit", {}).get("transitDays"),
                        "delivery_date": svc.get("commit", {}).get("dateDetail", {}).get("dayFormat"),
                    })
                return out
        except Exception as e:                                          # noqa: BLE001
            logger.warning("FedEx rate failed: %s", e)
            return None


class _UPSClient:
    def __init__(self):
        self._token: Optional[str] = None
        self._exp: float = 0.0

    def configured(self) -> bool:
        return bool(os.environ.get("UPS_CLIENT_ID") and os.environ.get("UPS_CLIENT_SECRET"))

    async def token(self) -> Optional[str]:
        if not self.configured():
            return None
        now = time.time()
        if self._token and now < self._exp - 60:
            return self._token
        base = os.environ.get("UPS_BASE_URL", "https://wwwcie.ups.com")
        try:
            import base64
            auth = base64.b64encode(
                f"{os.environ['UPS_CLIENT_ID']}:{os.environ['UPS_CLIENT_SECRET']}".encode()
            ).decode()
            async with httpx.AsyncClient(timeout=10.0) as c:
                r = await c.post(f"{base}/security/v1/oauth/token",
                                 data={"grant_type": "client_credentials"},
                                 headers={"Authorization": f"Basic {auth}",
                                          "Content-Type": "application/x-www-form-urlencoded"})
                r.raise_for_status()
                p = r.json()
                self._token = p["access_token"]
                self._exp = now + int(p.get("expires_in", 14399))
                return self._token
        except Exception as e:                                          # noqa: BLE001
            logger.warning("UPS token failed: %s", e)
            return None

    async def rate(self, req: RateIn) -> Optional[List[Dict[str, Any]]]:
        tok = await self.token()
        if not tok:
            return None
        base = os.environ.get("UPS_BASE_URL", "https://wwwcie.ups.com")
        acct = os.environ.get("UPS_ACCOUNT_NUMBER", "")
        payload = {"RateRequest": {
            "Request": {"TransactionReference": {"CustomerContext": "orisei-tms"}},
            "Shipment": {
                "Shipper":   {"ShipperNumber": acct, "Address": {
                    "PostalCode": req.origin_zip, "CountryCode": "US"}},
                "ShipTo":    {"Address": {"PostalCode": req.destination_zip,
                                            "CountryCode": "US",
                                            "ResidentialAddressIndicator": "1" if req.residential else ""}},
                "ShipFrom":  {"Address": {"PostalCode": req.origin_zip, "CountryCode": "US"}},
                "Package": [{
                    "PackagingType": {"Code": "02"},
                    "Dimensions": {"UnitOfMeasurement": {"Code": "IN"},
                                    "Length": str(req.length_in), "Width": str(req.width_in),
                                    "Height": str(req.height_in)},
                    "PackageWeight": {"UnitOfMeasurement": {"Code": "LBS"},
                                       "Weight": str(req.weight_lbs)},
                }] * req.package_count,
            }
        }}
        try:
            async with httpx.AsyncClient(timeout=15.0) as c:
                r = await c.post(f"{base}/api/rating/v2409/Shop", json=payload,
                                 headers={"Authorization": f"Bearer {tok}",
                                          "Content-Type": "application/json"})
                r.raise_for_status()
                data = r.json()
                out = []
                for s in ((data.get("RateResponse") or {}).get("RatedShipment") or []):
                    svc = s.get("Service", {})
                    tot = s.get("TotalCharges", {})
                    tr = s.get("GuaranteedDelivery", {}).get("BusinessDaysInTransit")
                    out.append({
                        "carrier": "UPS",
                        "service_code": svc.get("Code", ""),
                        "service_name": svc.get("Description") or f"UPS Service {svc.get('Code','')}",
                        "total_charge": float(tot.get("MonetaryValue") or 0),
                        "currency": tot.get("CurrencyCode", "USD"),
                        "transit_days": int(tr) if tr else None,
                        "delivery_date": s.get("GuaranteedDelivery", {}).get("DeliveryDate"),
                    })
                return out
        except Exception as e:                                          # noqa: BLE001
            logger.warning("UPS rate failed: %s", e)
            return None


_FEDEX = _FedExClient()
_UPS = _UPSClient()


def build_parcel_rating_router(
    *, api_router: APIRouter, db,
    get_current_user: Callable, require_role: Callable,
) -> None:
    router = APIRouter(prefix="/parcel", tags=["parcel"])

    @router.get("/provider")
    async def provider(_=Depends(get_current_user)) -> Dict[str, Any]:
        return {
            "fedex": {"connected": _FEDEX.configured(),
                      "env": "sandbox" if "sandbox" in os.environ.get("FEDEX_BASE_URL", "sandbox") else "production"},
            "ups":   {"connected": _UPS.configured(),
                      "env": "sandbox" if "wwwcie" in os.environ.get("UPS_BASE_URL", "wwwcie") else "production"},
            "sample_mode": not (_FEDEX.configured() and _UPS.configured()),
        }

    @router.post("/connect/fedex")
    async def connect_fedex(payload: ConnectFedEx,
                             user=Depends(require_role("admin"))) -> Dict[str, Any]:
        os.environ["FEDEX_CLIENT_ID"] = payload.client_id
        os.environ["FEDEX_CLIENT_SECRET"] = payload.client_secret
        os.environ["FEDEX_ACCOUNT_NUMBER"] = payload.account_number
        await db.parcel_credentials.update_one(
            {"carrier": "fedex"},
            {"$set": {"carrier": "fedex", "connected_at": datetime.now(timezone.utc).isoformat(),
                       "account_last4": payload.account_number[-4:],
                       "client_id_last6": payload.client_id[-6:]}},
            upsert=True)
        return {"ok": True, "carrier": "fedex"}

    @router.post("/connect/ups")
    async def connect_ups(payload: ConnectUPS,
                           user=Depends(require_role("admin"))) -> Dict[str, Any]:
        os.environ["UPS_CLIENT_ID"] = payload.client_id
        os.environ["UPS_CLIENT_SECRET"] = payload.client_secret
        os.environ["UPS_ACCOUNT_NUMBER"] = payload.account_number
        await db.parcel_credentials.update_one(
            {"carrier": "ups"},
            {"$set": {"carrier": "ups", "connected_at": datetime.now(timezone.utc).isoformat(),
                       "account_last4": payload.account_number[-4:],
                       "client_id_last6": payload.client_id[-6:]}},
            upsert=True)
        return {"ok": True, "carrier": "ups"}

    @router.post("/quote")
    async def quote(payload: RateIn, user=Depends(get_current_user)) -> Dict[str, Any]:
        # Try live carriers, fall back to sample for any that fail
        dist_mi = _zip_dist_mi(payload.origin_zip, payload.destination_zip)
        fedex_rows = await _FEDEX.rate(payload)
        ups_rows = await _UPS.rate(payload)
        fedex_mode = "live" if fedex_rows else "sample"
        ups_mode = "live" if ups_rows else "sample"
        if not fedex_rows:
            fedex_rows = _sample_quote("FEDEX", _FEDEX_SERVICES, payload, dist_mi)
        if not ups_rows:
            ups_rows = _sample_quote("UPS", _UPS_SERVICES, payload, dist_mi)
        all_rows = [*fedex_rows, *ups_rows]
        all_rows.sort(key=lambda r: r["total_charge"])
        cheapest = all_rows[0] if all_rows else None
        fastest = min(all_rows, key=lambda r: (r.get("transit_days") or 99)) if all_rows else None

        record = {
            "quoted_at": datetime.now(timezone.utc).isoformat(),
            "user_id": getattr(user, "user_id", None),
            "origin_zip": payload.origin_zip,
            "destination_zip": payload.destination_zip,
            "weight_lbs": payload.weight_lbs,
            "distance_mi": round(dist_mi, 1),
            "cheapest": cheapest, "fastest": fastest,
            "quote_count": len(all_rows),
            "fedex_mode": fedex_mode, "ups_mode": ups_mode,
        }
        try:
            await db.parcel_quotes.insert_one(dict(record))
        except Exception:                                               # noqa: BLE001
            pass
        return {
            "items": all_rows,
            "distance_mi": round(dist_mi, 1),
            "cheapest": cheapest,
            "fastest": fastest,
            "fedex_mode": fedex_mode,
            "ups_mode": ups_mode,
        }

    @router.get("/recent")
    async def recent(_=Depends(get_current_user)) -> Dict[str, Any]:
        rows = await db.parcel_quotes.find({}, {"_id": 0}).sort("quoted_at", -1).to_list(50)
        return {"items": rows, "count": len(rows)}

    api_router.include_router(router)
