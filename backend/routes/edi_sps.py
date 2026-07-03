"""routes.edi_sps — SPS Commerce EDI Fulfillment API integration.

Live mode: Auth0 OAuth2 client-credentials → SPS Fulfillment REST.
Sample mode: seeds realistic 204/856 inbound docs and stores outbound
990/214/210 to Mongo, marking each with `mock: true`. Same JSON shape.

Supported freight transaction sets:
  · 204  Motor Carrier Load Tender          (inbound, poll)
  · 990  Response to Load Tender            (outbound, we accept/reject)
  · 214  Shipment Status Message            (outbound, milestone events)
  · 210  Motor Carrier Freight Invoice      (outbound, freight bill)
  · 856  Advance Ship Notice                (inbound, poll)

Endpoints — /api/edi/*
  GET  /provider                · integration status
  POST /connect                 · store Auth0 domain + client_id/secret
  POST /seed-samples            · admin: seed sample 204/856 into Mongo
  GET  /inbound/204             · list tenders (mock or SPS-live)
  GET  /inbound/856             · list ASNs   (mock or SPS-live)
  POST /outbound/990            · send tender response
  POST /outbound/214            · send shipment status update
  POST /outbound/210            · send freight invoice
  GET  /outbound/history        · unified outbound audit log
"""
from __future__ import annotations

import logging
import os
import random
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger("orisei.edi_sps")

DEFAULT_BASE_URL = "https://api.spscommerce.com/fulfillment"
DEFAULT_AUDIENCE = "https://api.spscommerce.com"


class ConnectSPS(BaseModel):
    auth0_domain: str = Field(..., min_length=6, max_length=200)
    client_id: str = Field(..., min_length=8, max_length=200)
    client_secret: str = Field(..., min_length=8, max_length=400)
    api_audience: Optional[str] = Field(None, max_length=300)
    base_url: Optional[str] = Field(None, max_length=300)


class Location(BaseModel):
    name: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None


class TenderResponse990(BaseModel):
    tender_id: str
    decision: str = Field(..., description="accept | reject | counter")
    notes: Optional[str] = Field(None, max_length=500)


class ShipmentStatus214(BaseModel):
    tender_id: Optional[str] = None
    shipment_id: Optional[str] = None
    status_code: str = Field(..., description="picked_up | in_transit | delayed | delivered")
    status_time: Optional[str] = None
    location: Optional[Location] = None
    details: Optional[str] = Field(None, max_length=500)


class FreightInvoice210(BaseModel):
    tender_id: Optional[str] = None
    shipment_id: Optional[str] = None
    invoice_number: str = Field(..., max_length=40)
    amount: float = Field(..., gt=0)
    currency: str = Field("USD", max_length=3)
    due_date: Optional[str] = None


class _SPSAuth:
    def __init__(self):
        self._token: Optional[str] = None
        self._exp: float = 0.0

    def configured(self) -> bool:
        return bool(os.environ.get("SPS_AUTH0_DOMAIN")
                    and os.environ.get("SPS_CLIENT_ID")
                    and os.environ.get("SPS_CLIENT_SECRET"))

    async def token(self) -> Optional[str]:
        if not self.configured():
            return None
        now = time.time()
        if self._token and now < self._exp - 60:
            return self._token
        domain = os.environ["SPS_AUTH0_DOMAIN"].strip().rstrip("/")
        url = f"https://{domain}/oauth/token"
        payload = {
            "grant_type": "client_credentials",
            "client_id": os.environ["SPS_CLIENT_ID"],
            "client_secret": os.environ["SPS_CLIENT_SECRET"],
            "audience": os.environ.get("SPS_API_AUDIENCE", DEFAULT_AUDIENCE),
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as c:
                r = await c.post(url, json=payload)
                r.raise_for_status()
                d = r.json()
                self._token = d["access_token"]
                self._exp = now + int(d.get("expires_in", 3600))
                return self._token
        except Exception as e:                                          # noqa: BLE001
            logger.warning("SPS auth failed: %s", e)
            return None


_AUTH = _SPSAuth()


async def _sps_get(path: str) -> Optional[List[Dict[str, Any]]]:
    tok = await _AUTH.token()
    if not tok:
        return None
    base = os.environ.get("SPS_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=12.0,
            headers={"Authorization": f"Bearer {tok}", "Accept": "application/json"}) as c:
            r = await c.get(f"{base}{path}")
            r.raise_for_status()
            data = r.json()
            return data if isinstance(data, list) else data.get("items") or data.get("data") or []
    except Exception as e:                                              # noqa: BLE001
        logger.warning("SPS GET %s failed: %s", path, e)
        return None


async def _sps_post(path: str, body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    tok = await _AUTH.token()
    if not tok:
        return None
    base = os.environ.get("SPS_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=12.0,
            headers={"Authorization": f"Bearer {tok}",
                       "Accept": "application/json",
                       "Content-Type": "application/json"}) as c:
            r = await c.post(f"{base}{path}", json=body)
            r.raise_for_status()
            return r.json()
    except Exception as e:                                              # noqa: BLE001
        logger.warning("SPS POST %s failed: %s", path, e)
        return None


# ---------------------- Sample seed generators ----------------------
_SHIPPERS = ["Walmart DC-6011", "Target #T1289", "Home Depot RDC", "Costco #445",
             "Kroger DC", "Amazon DFW7", "Publix DC-9", "Lowe's RDC"]
_ORIGIN_CITIES = [("Chicago", "IL", "60601"), ("Dallas", "TX", "75201"),
                   ("Atlanta", "GA", "30301"), ("Phoenix", "AZ", "85001"),
                   ("Los Angeles", "CA", "90001"), ("Newark", "NJ", "07102")]
_DEST_CITIES = [("Denver", "CO", "80202"), ("Nashville", "TN", "37201"),
                 ("Miami", "FL", "33101"), ("Seattle", "WA", "98101"),
                 ("Houston", "TX", "77001"), ("Minneapolis", "MN", "55401")]
_COMMODITIES = ["General merchandise", "Grocery", "Electronics", "Building materials",
                 "Beverages", "Apparel", "Paper goods"]


def _gen_sample_204(count: int = 8) -> List[Dict[str, Any]]:
    rnd = random.Random("edi204::" + datetime.now(timezone.utc).strftime("%Y%m%d"))
    out = []
    for i in range(count):
        o = rnd.choice(_ORIGIN_CITIES)
        d = rnd.choice(_DEST_CITIES)
        pickup = datetime.now(timezone.utc) + timedelta(days=rnd.randint(0, 3))
        delivery = pickup + timedelta(days=rnd.randint(1, 4))
        out.append({
            "tender_id": f"T-{rnd.randint(100000, 999999)}",
            "shipper_reference": f"PO-{rnd.randint(10000, 99999)}",
            "shipper": rnd.choice(_SHIPPERS),
            "origin": {"name": f"{o[0]} DC", "city": o[0], "state": o[1], "postal_code": o[2]},
            "destination": {"name": f"Store {rnd.randint(100, 9999)}",
                             "city": d[0], "state": d[1], "postal_code": d[2]},
            "pickup_window_start": pickup.isoformat(),
            "delivery_window_end": delivery.isoformat(),
            "commodity": rnd.choice(_COMMODITIES),
            "weight_lbs": rnd.randint(8_000, 44_000),
            "equipment_type": rnd.choice(["Van 53", "Reefer 53", "Flatbed 48"]),
            "hazmat": rnd.random() < 0.08,
            "tender_amount_usd": round(rnd.uniform(1200, 4500), 2),
            "status": "new",
            "received_at": (datetime.now(timezone.utc) - timedelta(minutes=rnd.randint(5, 720))).isoformat(),
            "mock": True,
        })
    return out


def _gen_sample_856(count: int = 6) -> List[Dict[str, Any]]:
    rnd = random.Random("edi856::" + datetime.now(timezone.utc).strftime("%Y%m%d"))
    out = []
    for i in range(count):
        pallets = rnd.randint(8, 26)
        cartons = pallets * rnd.randint(24, 40)
        out.append({
            "asn_id": f"ASN-{rnd.randint(100000, 999999)}",
            "shipment_id": f"SHP-{rnd.randint(10000, 99999)}",
            "tender_id": f"T-{rnd.randint(100000, 999999)}",
            "shipper": rnd.choice(_SHIPPERS),
            "ship_date": (datetime.now(timezone.utc) - timedelta(days=rnd.randint(0, 2))).date().isoformat(),
            "expected_delivery_date": (datetime.now(timezone.utc) + timedelta(days=rnd.randint(1, 4))).date().isoformat(),
            "pallet_count": pallets,
            "carton_count": cartons,
            "sscc": f"00{rnd.randint(10**16, 10**17 - 1)}",
            "notes": rnd.choice(["Loaded floor-to-ceiling", "Reefer set 34°F",
                                  "Tarp required", "Do not stack"]),
            "mock": True,
        })
    return out


def build_edi_sps_router(
    *, api_router: APIRouter, db,
    get_current_user: Callable, require_role: Callable,
) -> None:
    router = APIRouter(prefix="/edi", tags=["edi-sps"])

    async def _ensure_seed():
        """Ensure sample inbound docs exist so the UI is never empty."""
        n204 = await db.sps_inbound_204.count_documents({})
        if n204 == 0:
            await db.sps_inbound_204.insert_many(_gen_sample_204())
        n856 = await db.sps_inbound_856.count_documents({})
        if n856 == 0:
            await db.sps_inbound_856.insert_many(_gen_sample_856())

    @router.get("/provider")
    async def provider(_=Depends(get_current_user)) -> Dict[str, Any]:
        connected = _AUTH.configured()
        return {
            "provider": "sps_commerce",
            "connected": connected,
            "mode": "live" if connected else "sample",
            "base_url": os.environ.get("SPS_BASE_URL", DEFAULT_BASE_URL),
            "supported_docs": ["204", "990", "214", "210", "856"],
            "hint": None if connected else
                "POST /api/edi/connect with your SPS Auth0 domain + client_id/secret to enable live mode.",
        }

    @router.post("/connect")
    async def connect(payload: ConnectSPS,
                       user=Depends(require_role("admin"))) -> Dict[str, Any]:
        os.environ["SPS_AUTH0_DOMAIN"] = payload.auth0_domain.strip()
        os.environ["SPS_CLIENT_ID"] = payload.client_id.strip()
        os.environ["SPS_CLIENT_SECRET"] = payload.client_secret.strip()
        if payload.api_audience:
            os.environ["SPS_API_AUDIENCE"] = payload.api_audience.strip()
        if payload.base_url:
            os.environ["SPS_BASE_URL"] = payload.base_url.strip()
        await db.edi_credentials.update_one(
            {"provider": "sps_commerce"},
            {"$set": {
                "provider": "sps_commerce",
                "connected_at": datetime.now(timezone.utc).isoformat(),
                "auth0_domain": payload.auth0_domain,
                "client_id_last6": payload.client_id[-6:],
                "connected_by": getattr(user, "user_id", None),
            }},
            upsert=True)
        return {"ok": True, "mode": "live"}

    @router.post("/seed-samples")
    async def seed_samples(user=Depends(require_role("admin"))) -> Dict[str, Any]:
        await db.sps_inbound_204.delete_many({"mock": True})
        await db.sps_inbound_856.delete_many({"mock": True})
        await db.sps_inbound_204.insert_many(_gen_sample_204())
        await db.sps_inbound_856.insert_many(_gen_sample_856())
        n204 = await db.sps_inbound_204.count_documents({})
        n856 = await db.sps_inbound_856.count_documents({})
        return {"ok": True, "inbound_204": n204, "inbound_856": n856}

    @router.get("/inbound/204")
    async def inbound_204(_=Depends(get_current_user)) -> Dict[str, Any]:
        live = await _sps_get("/inbound/204")
        if live is not None:
            return {"items": live, "count": len(live), "mode": "live"}
        await _ensure_seed()
        rows = await db.sps_inbound_204.find({}, {"_id": 0}).sort("received_at", -1).to_list(200)
        return {"items": rows, "count": len(rows), "mode": "sample"}

    @router.get("/inbound/856")
    async def inbound_856(_=Depends(get_current_user)) -> Dict[str, Any]:
        live = await _sps_get("/inbound/856")
        if live is not None:
            return {"items": live, "count": len(live), "mode": "live"}
        await _ensure_seed()
        rows = await db.sps_inbound_856.find({}, {"_id": 0}).sort("ship_date", -1).to_list(200)
        return {"items": rows, "count": len(rows), "mode": "sample"}

    async def _persist_outbound(kind: str, doc: Dict[str, Any], live_result: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        record = {
            "doc_id": f"{kind}-{uuid.uuid4().hex[:10].upper()}",
            "kind": kind,
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "mode": "live" if live_result else "sample",
            "payload": doc,
            "sps_response": live_result,
        }
        await db.sps_outbound.insert_one(dict(record))
        record.pop("_id", None)
        return record

    @router.post("/outbound/990")
    async def outbound_990(payload: TenderResponse990,
                            user=Depends(get_current_user)) -> Dict[str, Any]:
        if payload.decision not in {"accept", "reject", "counter"}:
            raise HTTPException(422, "decision must be one of accept/reject/counter")
        # Update the local tender status so the inbox reflects the decision.
        await db.sps_inbound_204.update_many(
            {"tender_id": payload.tender_id},
            {"$set": {"status": {"accept": "accepted",
                                    "reject": "rejected",
                                    "counter": "countered"}[payload.decision],
                       "decision_notes": payload.notes,
                       "decided_at": datetime.now(timezone.utc).isoformat(),
                       "decided_by": getattr(user, "user_id", None)}})
        live = await _sps_post("/outbound/990", payload.model_dump())
        rec = await _persist_outbound("990", payload.model_dump(), live)
        return rec

    @router.post("/outbound/214")
    async def outbound_214(payload: ShipmentStatus214,
                            user=Depends(get_current_user)) -> Dict[str, Any]:
        if not payload.status_time:
            payload.status_time = datetime.now(timezone.utc).isoformat()
        live = await _sps_post("/outbound/214", payload.model_dump())
        rec = await _persist_outbound("214", payload.model_dump(), live)
        return rec

    @router.post("/outbound/210")
    async def outbound_210(payload: FreightInvoice210,
                            user=Depends(get_current_user)) -> Dict[str, Any]:
        live = await _sps_post("/outbound/210", payload.model_dump())
        rec = await _persist_outbound("210", payload.model_dump(), live)
        return rec

    @router.get("/outbound/history")
    async def outbound_history(_=Depends(get_current_user)) -> Dict[str, Any]:
        rows = await db.sps_outbound.find({}, {"_id": 0}).sort("sent_at", -1).to_list(100)
        return {
            "items": rows, "count": len(rows),
            "by_kind": {k: sum(1 for r in rows if r.get("kind") == k)
                        for k in ("990", "214", "210")},
        }

    api_router.include_router(router)
