"""
Tennant Companies — Transportation Management System (TMS)
HUD-style command center backend
"""
from fastapi import FastAPI, APIRouter, Depends, HTTPException, Request, Response, WebSocket, WebSocketDisconnect, Query
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import uuid
import json
import random
import httpx
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI(title="Tennant TMS API")
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("tennant_tms")

# -------------------- MODELS --------------------
class User(BaseModel):
    user_id: str
    email: str
    name: str
    picture: Optional[str] = None
    role: str = "dispatcher"

class Shipment(BaseModel):
    shipment_id: str
    reference: str
    mode: str  # TL, LTL, Parcel, Ocean, Air, Rail
    carrier: str
    status: str  # in_transit, delayed, delivered, pending, at_origin, at_dest
    origin: Dict[str, Any]   # { name, city, lat, lng, facility? }
    destination: Dict[str, Any]
    current_location: Dict[str, Any]  # { lat, lng, city }
    eta: str
    pickup_date: str
    weight_lbs: float
    pieces: int
    commodity: str
    value_usd: float
    container_no: Optional[str] = None
    bol_no: Optional[str] = None
    pro_no: Optional[str] = None
    progress: float = 0.0

class Document(BaseModel):
    document_id: str
    type: str  # BOL, COMMERCIAL_INVOICE, PACKING_SLIP, WEIGHT_CERT, COO
    shipment_ref: str
    created_by: str
    created_at: str
    data: Dict[str, Any]

class ChatMessage(BaseModel):
    message_id: str
    channel: str
    user_id: str
    user_name: str
    user_picture: Optional[str] = None
    text: str
    created_at: str

# -------------------- AUTH HELPERS --------------------
async def get_current_user(request: Request) -> User:
    """Get user from session_token cookie or Authorization header."""
    token = request.cookies.get("session_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    session = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=401, detail="Invalid session")
    expires_at = session["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Session expired")
    user_doc = await db.users.find_one({"user_id": session["user_id"]}, {"_id": 0})
    if not user_doc:
        raise HTTPException(status_code=401, detail="User not found")
    return User(**user_doc)

async def get_optional_user(request: Request) -> Optional[User]:
    try:
        return await get_current_user(request)
    except HTTPException:
        return None

# -------------------- AUTH ENDPOINTS --------------------
@api_router.post("/auth/session")
async def create_session(request: Request, response: Response):
    body = await request.json()
    session_id = body.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id required")
    async with httpx.AsyncClient(timeout=15.0) as http:
        r = await http.get(
            "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
            headers={"X-Session-ID": session_id}
        )
        if r.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid session_id")
        data = r.json()
    email = data["email"]
    name = data["name"]
    picture = data.get("picture")
    session_token = data["session_token"]

    existing = await db.users.find_one({"email": email}, {"_id": 0})
    if existing:
        user_id = existing["user_id"]
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {"name": name, "picture": picture}}
        )
    else:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        await db.users.insert_one({
            "user_id": user_id,
            "email": email,
            "name": name,
            "picture": picture,
            "role": "dispatcher",
            "created_at": datetime.now(timezone.utc).isoformat()
        })

    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    await db.user_sessions.insert_one({
        "user_id": user_id,
        "session_token": session_token,
        "expires_at": expires_at.isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        secure=True,
        samesite="none",
        path="/",
        max_age=7 * 24 * 60 * 60,
    )
    return {"user_id": user_id, "email": email, "name": name, "picture": picture, "role": "dispatcher"}

@api_router.get("/auth/me", response_model=User)
async def me(user: User = Depends(get_current_user)):
    return user

@api_router.post("/auth/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get("session_token")
    if token:
        await db.user_sessions.delete_one({"session_token": token})
    response.delete_cookie("session_token", path="/")
    return {"ok": True}

# -------------------- FACILITIES --------------------
TENNANT_FACILITIES = [
    {"id": "GVM", "name": "Golden Valley, MN (HQ)", "city": "Golden Valley", "state": "MN", "lat": 44.9858, "lng": -93.3499, "type": "Headquarters / Manufacturing"},
    {"id": "HOM", "name": "Holland, MI Plant", "city": "Holland", "state": "MI", "lat": 42.7875, "lng": -86.1089, "type": "Manufacturing"},
    {"id": "LVK", "name": "Louisville, KY Plant", "city": "Louisville", "state": "KY", "lat": 38.2527, "lng": -85.7585, "type": "Manufacturing"},
]

@api_router.get("/facilities")
async def get_facilities(_: User = Depends(get_current_user)):
    return TENNANT_FACILITIES

# -------------------- SHIPMENTS --------------------
@api_router.get("/shipments", response_model=List[Shipment])
async def list_shipments(_: User = Depends(get_current_user), mode: Optional[str] = None, status: Optional[str] = None, limit: int = 200):
    q: Dict[str, Any] = {}
    if mode:
        q["mode"] = mode
    if status:
        q["status"] = status
    docs = await db.shipments.find(q, {"_id": 0}).limit(limit).to_list(limit)
    return [Shipment(**d) for d in docs]

@api_router.get("/shipments/{shipment_id}", response_model=Shipment)
async def get_shipment(shipment_id: str, _: User = Depends(get_current_user)):
    doc = await db.shipments.find_one({"shipment_id": shipment_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Shipment not found")
    return Shipment(**doc)

class ShipmentCreate(BaseModel):
    reference: Optional[str] = None
    mode: str
    carrier: str
    origin_facility: Optional[str] = None
    origin_city: Optional[str] = None
    destination_city: str
    destination_lat: float
    destination_lng: float
    pickup_date: str
    weight_lbs: float
    pieces: int
    commodity: str
    value_usd: float

@api_router.post("/shipments", response_model=Shipment)
async def create_shipment(payload: ShipmentCreate, user: User = Depends(get_current_user)):
    origin = None
    if payload.origin_facility:
        f = next((x for x in TENNANT_FACILITIES if x["id"] == payload.origin_facility), None)
        if f:
            origin = {"name": f["name"], "city": f["city"], "lat": f["lat"], "lng": f["lng"], "facility": f["id"]}
    if not origin:
        origin = {"name": payload.origin_city or "Origin", "city": payload.origin_city or "Origin", "lat": 44.9858, "lng": -93.3499}
    destination = {"name": payload.destination_city, "city": payload.destination_city, "lat": payload.destination_lat, "lng": payload.destination_lng}
    sid = f"SHP-{uuid.uuid4().hex[:8].upper()}"
    eta_days = random.randint(2, 14)
    shipment = {
        "shipment_id": sid,
        "reference": payload.reference or f"TN-{random.randint(10000, 99999)}",
        "mode": payload.mode,
        "carrier": payload.carrier,
        "status": "pending",
        "origin": origin,
        "destination": destination,
        "current_location": {"lat": origin["lat"], "lng": origin["lng"], "city": origin["city"]},
        "eta": (datetime.now(timezone.utc) + timedelta(days=eta_days)).isoformat(),
        "pickup_date": payload.pickup_date,
        "weight_lbs": payload.weight_lbs,
        "pieces": payload.pieces,
        "commodity": payload.commodity,
        "value_usd": payload.value_usd,
        "container_no": f"TCLU{random.randint(1000000,9999999)}" if payload.mode == "Ocean" else None,
        "bol_no": f"BOL{random.randint(100000,999999)}",
        "pro_no": f"PRO{random.randint(100000,999999)}",
        "progress": 0.0,
        "created_by": user.user_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.shipments.insert_one(dict(shipment))
    return Shipment(**shipment)

# -------------------- DOCUMENTS --------------------
@api_router.get("/documents", response_model=List[Document])
async def list_documents(_: User = Depends(get_current_user)):
    docs = await db.documents.find({}, {"_id": 0}).sort("created_at", -1).limit(200).to_list(200)
    return [Document(**d) for d in docs]

class DocumentCreate(BaseModel):
    type: str
    shipment_ref: str
    data: Dict[str, Any]

@api_router.post("/documents", response_model=Document)
async def create_document(payload: DocumentCreate, user: User = Depends(get_current_user)):
    doc = {
        "document_id": f"DOC-{uuid.uuid4().hex[:8].upper()}",
        "type": payload.type,
        "shipment_ref": payload.shipment_ref,
        "created_by": user.name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "data": payload.data,
    }
    await db.documents.insert_one(dict(doc))
    return Document(**doc)

# -------------------- KPIs --------------------
@api_router.get("/kpis")
async def get_kpis(_: User = Depends(get_current_user)):
    all_shipments = await db.shipments.find({}, {"_id": 0}).to_list(2000)
    total = len(all_shipments)
    in_transit = sum(1 for s in all_shipments if s["status"] == "in_transit")
    delayed = sum(1 for s in all_shipments if s["status"] == "delayed")
    delivered = sum(1 for s in all_shipments if s["status"] == "delivered")
    pending = sum(1 for s in all_shipments if s["status"] == "pending")
    by_mode: Dict[str, int] = {}
    by_carrier: Dict[str, Dict[str, int]] = {}
    total_weight = 0.0
    total_value = 0.0
    for s in all_shipments:
        by_mode[s["mode"]] = by_mode.get(s["mode"], 0) + 1
        c = s["carrier"]
        if c not in by_carrier:
            by_carrier[c] = {"total": 0, "on_time": 0, "delayed": 0}
        by_carrier[c]["total"] += 1
        if s["status"] == "delivered":
            by_carrier[c]["on_time"] += 1
        if s["status"] == "delayed":
            by_carrier[c]["delayed"] += 1
        total_weight += s.get("weight_lbs", 0)
        total_value += s.get("value_usd", 0)
    on_time_rate = round((delivered / max(1, total)) * 100, 1)
    # Trend last 14 days
    today = datetime.now(timezone.utc).date()
    trend = []
    for i in range(13, -1, -1):
        d = today - timedelta(days=i)
        trend.append({
            "date": d.isoformat(),
            "shipments": random.randint(8, 26),
            "on_time": random.randint(7, 25),
            "cost": round(random.uniform(45000, 92000), 2),
        })
    return {
        "totals": {
            "total": total,
            "in_transit": in_transit,
            "delayed": delayed,
            "delivered": delivered,
            "pending": pending,
            "weight_lbs": round(total_weight, 0),
            "value_usd": round(total_value, 0),
            "on_time_rate": on_time_rate,
        },
        "by_mode": by_mode,
        "by_carrier": [{"carrier": k, **v} for k, v in by_carrier.items()],
        "trend": trend,
    }

# -------------------- LIVE FEEDS --------------------
@api_router.get("/weather")
async def get_weather(_: User = Depends(get_current_user)):
    """Real weather via Open-Meteo (no key)."""
    results = []
    async with httpx.AsyncClient(timeout=10.0) as http:
        for f in TENNANT_FACILITIES:
            try:
                r = await http.get(
                    "https://api.open-meteo.com/v1/forecast",
                    params={
                        "latitude": f["lat"],
                        "longitude": f["lng"],
                        "current": "temperature_2m,wind_speed_10m,weather_code,relative_humidity_2m",
                        "temperature_unit": "fahrenheit",
                        "wind_speed_unit": "mph",
                    },
                )
                d = r.json().get("current", {})
                results.append({
                    "facility_id": f["id"],
                    "facility_name": f["name"],
                    "temperature_f": d.get("temperature_2m"),
                    "humidity": d.get("relative_humidity_2m"),
                    "wind_mph": d.get("wind_speed_10m"),
                    "weather_code": d.get("weather_code"),
                })
            except Exception as e:
                logger.warning(f"Weather fetch failed for {f['id']}: {e}")
                results.append({"facility_id": f["id"], "facility_name": f["name"], "error": str(e)})
    return results

MOCK_NEWS = [
    {"title": "Diesel prices ease 4¢ as Midwest refineries return", "source": "FreightWaves", "category": "fuel", "time": "12m"},
    {"title": "Port of Long Beach reports 8% volume increase YoY", "source": "JOC", "category": "ocean", "time": "1h"},
    {"title": "FMCSA proposes new HOS exemption for short-haul drivers", "source": "Transport Topics", "category": "regulatory", "time": "2h"},
    {"title": "UPS adds 12 new electric ground-support tugs in Louisville hub", "source": "DC Velocity", "category": "carrier", "time": "3h"},
    {"title": "Severe winter weather forecast for Upper Midwest this week", "source": "Weather.gov", "category": "weather", "time": "4h"},
    {"title": "USTR considering new Section 301 review on imported components", "source": "Reuters", "category": "trade", "time": "5h"},
    {"title": "Kuehne+Nagel expands North America air freight network", "source": "Air Cargo News", "category": "carrier", "time": "6h"},
    {"title": "ELD malfunction reports rise 15% in Q4 — FMCSA notice", "source": "CDLLife", "category": "regulatory", "time": "8h"},
]

@api_router.get("/news")
async def get_news(_: User = Depends(get_current_user)):
    return MOCK_NEWS

MOCK_TRAFFIC = [
    {"location": "I-94 EB at Mile 215 (MI)", "type": "Crash", "severity": "moderate", "delay_min": 25, "lat": 42.65, "lng": -86.10},
    {"location": "I-65 N at Louisville Spaghetti Junction", "type": "Construction", "severity": "low", "delay_min": 12, "lat": 38.26, "lng": -85.75},
    {"location": "I-394 W approach to Golden Valley", "type": "Weather - Snow", "severity": "high", "delay_min": 40, "lat": 44.98, "lng": -93.35},
    {"location": "I-80 EB Ohio Turnpike Mile 161", "type": "Stalled vehicle", "severity": "low", "delay_min": 8, "lat": 41.36, "lng": -82.22},
    {"location": "I-71 N Cincinnati", "type": "Congestion", "severity": "moderate", "delay_min": 18, "lat": 39.16, "lng": -84.45},
]

@api_router.get("/traffic")
async def get_traffic(_: User = Depends(get_current_user)):
    return MOCK_TRAFFIC

# -------------------- INTEGRATIONS --------------------
INTEGRATIONS = [
    {"id": "sap_s4hana", "name": "SAP S/4HANA", "category": "ERP", "status": "connected", "last_sync": "2m ago", "endpoint": "api.tennantco.s4.sap.com"},
    {"id": "sharepoint", "name": "Microsoft SharePoint", "category": "Productivity", "status": "connected", "last_sync": "5m ago", "endpoint": "tennantco.sharepoint.com"},
    {"id": "powerbi", "name": "Microsoft PowerBI", "category": "Analytics", "status": "connected", "last_sync": "8m ago", "endpoint": "app.powerbi.com/tennant"},
    {"id": "outlook", "name": "Microsoft Outlook", "category": "Communication", "status": "connected", "last_sync": "1m ago", "endpoint": "outlook.office365.com"},
    {"id": "logix", "name": "Logix Transportation", "category": "TMS", "status": "connected", "last_sync": "3m ago", "endpoint": "api.logixtms.com"},
    {"id": "ups", "name": "UPS", "category": "Parcel", "status": "connected", "last_sync": "1m ago", "endpoint": "onlinetools.ups.com"},
    {"id": "fedex", "name": "FedEx", "category": "Parcel", "status": "connected", "last_sync": "2m ago", "endpoint": "ws.api.fedex.com"},
    {"id": "dhl", "name": "DHL Express", "category": "Air/Intl", "status": "connected", "last_sync": "4m ago", "endpoint": "api-eu.dhl.com"},
    {"id": "arcbest", "name": "ArcBest", "category": "LTL", "status": "connected", "last_sync": "6m ago", "endpoint": "api.arcb.com"},
    {"id": "fastfrate", "name": "Consolidated Fastfrate", "category": "LTL (Canada)", "status": "connected", "last_sync": "9m ago", "endpoint": "api.fastfrate.com"},
    {"id": "rl", "name": "R&L Carriers", "category": "LTL", "status": "connected", "last_sync": "12m ago", "endpoint": "api.rlc.com"},
    {"id": "xpo", "name": "XPO Logistics", "category": "LTL", "status": "warning", "last_sync": "1h ago", "endpoint": "api.xpo.com"},
    {"id": "saia", "name": "SAIA LTL Freight", "category": "LTL", "status": "connected", "last_sync": "7m ago", "endpoint": "api.saia.com"},
    {"id": "kuehne", "name": "Kuehne+Nagel", "category": "Ocean/Air", "status": "connected", "last_sync": "3m ago", "endpoint": "api.kuehne-nagel.com"},
]

@api_router.get("/integrations")
async def get_integrations(_: User = Depends(get_current_user)):
    return INTEGRATIONS

# -------------------- TRAILER SPECS --------------------
TRAILER_SPECS = [
    {"id": "53dv", "name": "53' Dry Van", "length_ft": 53, "width_ft": 8.5, "height_ft": 9, "max_weight_lbs": 45000, "pallets": 26, "uses": ["General freight", "Palletized goods", "Scrubber assemblies"], "color": "#00E5FF"},
    {"id": "48dv", "name": "48' Dry Van", "length_ft": 48, "width_ft": 8.5, "height_ft": 9, "max_weight_lbs": 44000, "pallets": 24, "uses": ["Regional freight", "Northeast lanes (low bridges)"], "color": "#00FF66"},
    {"id": "28pup", "name": "28' Pup Trailer", "length_ft": 28, "width_ft": 8, "height_ft": 9, "max_weight_lbs": 22000, "pallets": 14, "uses": ["LTL doubles/triples", "City delivery"], "color": "#FFCC00"},
    {"id": "53reef", "name": "53' Reefer", "length_ft": 53, "width_ft": 8.5, "height_ft": 8.5, "max_weight_lbs": 43500, "pallets": 26, "uses": ["Temperature-sensitive batteries", "Sensitive electronics"], "color": "#FF3B30"},
    {"id": "48flat", "name": "48' Flatbed", "length_ft": 48, "width_ft": 8.5, "height_ft": 5, "max_weight_lbs": 48000, "pallets": 0, "uses": ["Oversized scrubbers", "Machinery", "Steel components"], "color": "#A78BFA"},
    {"id": "20ctr", "name": "20' Ocean Container", "length_ft": 20, "width_ft": 8, "height_ft": 8.5, "max_weight_lbs": 47900, "pallets": 10, "uses": ["Heavy imports", "Single SKU consolidations"], "color": "#3B82F6"},
    {"id": "40ctr", "name": "40' Ocean Container", "length_ft": 40, "width_ft": 8, "height_ft": 8.5, "max_weight_lbs": 59000, "pallets": 20, "uses": ["Standard ocean imports from K+N", "Mixed SKU"], "color": "#06B6D4"},
    {"id": "40hc", "name": "40' High Cube", "length_ft": 40, "width_ft": 8, "height_ft": 9.5, "max_weight_lbs": 58000, "pallets": 20, "uses": ["Tall machinery", "Volume-out before weight-out"], "color": "#10B981"},
]

@api_router.get("/trailers")
async def get_trailers(_: User = Depends(get_current_user)):
    return TRAILER_SPECS

# -------------------- HS CODES --------------------
HS_CODES = [
    {"code": "8479.89.94", "description": "Floor scrubbing/sweeping machines, self-propelled, industrial", "duty_pct": 2.5, "category": "Machinery"},
    {"code": "8479.89.65", "description": "Industrial cleaning machines, electromechanical", "duty_pct": 2.5, "category": "Machinery"},
    {"code": "8508.11.00", "description": "Vacuum cleaners with self-contained electric motor, ≤1500W", "duty_pct": 0, "category": "Machinery"},
    {"code": "8508.19.00", "description": "Vacuum cleaners, other (industrial)", "duty_pct": 0, "category": "Machinery"},
    {"code": "8413.81.00", "description": "Pumps for liquids, other (cleaning solution pumps)", "duty_pct": 0, "category": "Pumps"},
    {"code": "8501.31.50", "description": "DC motors, ≤750W (drive motors for scrubbers)", "duty_pct": 4.0, "category": "Electrical"},
    {"code": "8507.60.00", "description": "Lithium-ion batteries (battery packs)", "duty_pct": 3.4, "category": "Batteries"},
    {"code": "8507.20.80", "description": "Lead-acid storage batteries, other", "duty_pct": 3.5, "category": "Batteries"},
    {"code": "9603.50.00", "description": "Brushes constituting parts of machines (scrubber brushes)", "duty_pct": 0, "category": "Parts"},
    {"code": "8431.49.90", "description": "Parts suitable for use with machinery of headings 8425-8430", "duty_pct": 0, "category": "Parts"},
    {"code": "3926.90.99", "description": "Other articles of plastics (tanks, housings)", "duty_pct": 5.3, "category": "Plastics"},
    {"code": "7326.90.86", "description": "Articles of iron or steel, other (frames, brackets)", "duty_pct": 2.9, "category": "Steel"},
    {"code": "8536.50.90", "description": "Switches for voltage ≤1000V (control switches)", "duty_pct": 2.7, "category": "Electrical"},
    {"code": "4016.93.50", "description": "Rubber gaskets, washers and other seals", "duty_pct": 2.5, "category": "Rubber"},
    {"code": "8544.30.00", "description": "Ignition wiring sets and other wiring sets used in vehicles", "duty_pct": 5.0, "category": "Wiring"},
    {"code": "9026.10.20", "description": "Flow meters (water/solution flow)", "duty_pct": 0, "category": "Instruments"},
    {"code": "8536.69.40", "description": "Connectors for voltage ≤1000V (battery & motor connectors)", "duty_pct": 0, "category": "Electrical"},
    {"code": "3917.32.00", "description": "Plastic tubes/hoses, not reinforced", "duty_pct": 3.1, "category": "Plastics"},
]

@api_router.get("/hs-lookup")
async def hs_lookup(q: str = Query(""), _: User = Depends(get_current_user)):
    if not q:
        return HS_CODES
    ql = q.lower()
    return [c for c in HS_CODES if ql in c["code"].lower() or ql in c["description"].lower() or ql in c["category"].lower()]

# -------------------- QUICK LINKS --------------------
QUICK_LINKS = [
    {"name": "ACE Portal (CBP)", "url": "https://ace.cbp.dhs.gov/", "category": "Import/Export", "description": "Automated Commercial Environment - U.S. Customs"},
    {"name": "DOT FMCSA SAFER", "url": "https://safer.fmcsa.dot.gov/", "category": "DOT", "description": "Carrier safety lookup & insurance verification"},
    {"name": "FMCSA Portal", "url": "https://portal.fmcsa.dot.gov/", "category": "DOT", "description": "Federal Motor Carrier Safety Administration"},
    {"name": "USDOT - Transportation.gov", "url": "https://www.transportation.gov/", "category": "DOT", "description": "U.S. Department of Transportation"},
    {"name": "CBP Trade", "url": "https://www.cbp.gov/trade", "category": "Import/Export", "description": "Customs and Border Protection - Trade"},
    {"name": "USTR HTS Search", "url": "https://hts.usitc.gov/", "category": "Tariff", "description": "Harmonized Tariff Schedule of the United States"},
    {"name": "Census Schedule B Search", "url": "https://www.census.gov/foreign-trade/schedules/b/", "category": "Tariff", "description": "Schedule B (export commodity codes)"},
    {"name": "Port of Long Beach", "url": "https://www.polb.com/", "category": "Ports", "description": "Major West Coast port"},
    {"name": "Port of New York/NJ", "url": "https://www.panynj.gov/port/", "category": "Ports", "description": "East Coast major port"},
    {"name": "Weather.gov Aviation", "url": "https://aviationweather.gov/", "category": "Weather", "description": "Aviation weather products"},
    {"name": "FAA NOTAMs", "url": "https://www.faa.gov/", "category": "Air", "description": "Federal Aviation Administration"},
]

@api_router.get("/links")
async def get_links(_: User = Depends(get_current_user)):
    return QUICK_LINKS

# -------------------- CHAT --------------------
DEFAULT_CHANNELS = [
    {"id": "general", "name": "general", "description": "Company-wide updates"},
    {"id": "ops-dispatch", "name": "ops-dispatch", "description": "Daily dispatch coordination"},
    {"id": "import-export", "name": "import-export", "description": "Customs, HS codes, ACE filings"},
    {"id": "carrier-issues", "name": "carrier-issues", "description": "Carrier escalations & exceptions"},
    {"id": "louisville", "name": "louisville", "description": "Louisville, KY plant team"},
    {"id": "holland", "name": "holland", "description": "Holland, MI plant team"},
    {"id": "golden-valley", "name": "golden-valley", "description": "Golden Valley, MN HQ"},
]

@api_router.get("/chat/channels")
async def get_channels(_: User = Depends(get_current_user)):
    return DEFAULT_CHANNELS

@api_router.get("/chat/messages")
async def get_messages(channel: str, _: User = Depends(get_current_user)):
    msgs = await db.chat_messages.find({"channel": channel}, {"_id": 0}).sort("created_at", 1).limit(200).to_list(200)
    return msgs

# WebSocket manager
class ConnectionManager:
    def __init__(self):
        self.active: List[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, data: dict):
        dead = []
        for ws in self.active:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for d in dead:
            self.disconnect(d)

manager = ConnectionManager()

@app.websocket("/api/ws/chat")
async def ws_chat(websocket: WebSocket, token: str = Query(...)):
    session = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if not session:
        await websocket.close(code=1008)
        return
    user_doc = await db.users.find_one({"user_id": session["user_id"]}, {"_id": 0})
    if not user_doc:
        await websocket.close(code=1008)
        return
    await manager.connect(websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            text = (data.get("text") or "").strip()
            channel = data.get("channel", "general")
            if not text:
                continue
            msg = {
                "message_id": f"msg_{uuid.uuid4().hex[:10]}",
                "channel": channel,
                "user_id": user_doc["user_id"],
                "user_name": user_doc["name"],
                "user_picture": user_doc.get("picture"),
                "text": text,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.chat_messages.insert_one(dict(msg))
            await manager.broadcast({"type": "message", "data": msg})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.warning(f"WS error: {e}")
        manager.disconnect(websocket)

# -------------------- TEAM --------------------
@api_router.get("/team")
async def team(_: User = Depends(get_current_user)):
    docs = await db.users.find({}, {"_id": 0}).limit(50).to_list(50)
    return docs

# -------------------- FREIGHT AUDIT & PAY --------------------
class FreightBill(BaseModel):
    bill_id: str
    shipment_ref: str
    carrier: str
    invoice_no: str
    base_charge: float
    accessorials: List[Dict[str, Any]]  # [{code, description, amount}]
    fuel_surcharge: float
    total: float
    quoted_total: float
    variance: float
    status: str  # pending, approved, paid, disputed, audit
    invoice_date: str
    due_date: str
    paid_at: Optional[str] = None

@api_router.get("/freight-bills")
async def list_bills(_: User = Depends(get_current_user), status: Optional[str] = None, carrier: Optional[str] = None):
    q: Dict[str, Any] = {}
    if status: q["status"] = status
    if carrier: q["carrier"] = carrier
    docs = await db.freight_bills.find(q, {"_id": 0}).sort("invoice_date", -1).limit(500).to_list(500)
    return docs

@api_router.post("/freight-bills/{bill_id}/pay")
async def pay_bill(bill_id: str, user: User = Depends(get_current_user)):
    bill = await db.freight_bills.find_one({"bill_id": bill_id}, {"_id": 0})
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    if bill["status"] == "paid":
        return {"ok": True, "already_paid": True}
    await db.freight_bills.update_one(
        {"bill_id": bill_id},
        {"$set": {"status": "paid", "paid_at": datetime.now(timezone.utc).isoformat(), "paid_by": user.name}}
    )
    return {"ok": True, "bill_id": bill_id}

@api_router.post("/freight-bills/{bill_id}/approve")
async def approve_bill(bill_id: str, user: User = Depends(get_current_user)):
    await db.freight_bills.update_one({"bill_id": bill_id}, {"$set": {"status": "approved", "approved_by": user.name}})
    return {"ok": True}

@api_router.post("/freight-bills/{bill_id}/dispute")
async def dispute_bill(bill_id: str, request: Request, user: User = Depends(get_current_user)):
    body = await request.json()
    await db.freight_bills.update_one(
        {"bill_id": bill_id},
        {"$set": {"status": "disputed", "dispute_reason": body.get("reason", ""), "disputed_by": user.name}}
    )
    return {"ok": True}

@api_router.get("/freight-bills/summary")
async def bills_summary(_: User = Depends(get_current_user)):
    bills = await db.freight_bills.find({}, {"_id": 0}).to_list(2000)
    total = sum(b["total"] for b in bills)
    paid = sum(b["total"] for b in bills if b["status"] == "paid")
    pending = sum(b["total"] for b in bills if b["status"] in ("pending", "audit"))
    disputed = sum(b["total"] for b in bills if b["status"] == "disputed")
    overcharges = sum(b["variance"] for b in bills if b.get("variance", 0) > 0)
    return {
        "total_billed": round(total, 2),
        "paid": round(paid, 2),
        "pending": round(pending, 2),
        "disputed": round(disputed, 2),
        "overcharges_detected": round(overcharges, 2),
        "count": len(bills),
        "count_disputed": sum(1 for b in bills if b["status"] == "disputed"),
    }

# -------------------- CARRIER ONBOARDING --------------------
class CarrierOnboarding(BaseModel):
    onboarding_id: str
    legal_name: str
    dba: Optional[str] = None
    mc_number: Optional[str] = None
    dot_number: Optional[str] = None
    scac: Optional[str] = None
    mode: str
    contact_name: str
    contact_email: str
    contact_phone: str
    insurance_amount: float
    insurance_expiry: str
    safety_rating: str  # Satisfactory, Conditional, Unsatisfactory, NotRated
    csa_score: int
    w9_received: bool
    coi_received: bool
    contract_signed: bool
    status: str  # invited, in_review, approved, rejected
    submitted_at: str
    notes: Optional[str] = ""

class CarrierOnboardingCreate(BaseModel):
    legal_name: str
    dba: Optional[str] = None
    mc_number: Optional[str] = None
    dot_number: Optional[str] = None
    scac: Optional[str] = None
    mode: str = "TL"
    contact_name: str
    contact_email: str
    contact_phone: str
    insurance_amount: float = 1000000
    insurance_expiry: str
    safety_rating: str = "Satisfactory"
    csa_score: int = 50
    notes: Optional[str] = ""

@api_router.get("/carriers/onboarding")
async def list_onboarding(_: User = Depends(get_current_user), status: Optional[str] = None):
    q: Dict[str, Any] = {}
    if status: q["status"] = status
    docs = await db.carrier_onboarding.find(q, {"_id": 0}).sort("submitted_at", -1).to_list(500)
    return docs

@api_router.post("/carriers/onboarding")
async def create_onboarding(payload: CarrierOnboardingCreate, user: User = Depends(get_current_user)):
    doc = {
        "onboarding_id": f"OB-{uuid.uuid4().hex[:8].upper()}",
        **payload.model_dump(),
        "w9_received": False,
        "coi_received": False,
        "contract_signed": False,
        "status": "in_review",
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "submitted_by": user.name,
    }
    await db.carrier_onboarding.insert_one(dict(doc))
    return doc

@api_router.post("/carriers/onboarding/{oid}/decision")
async def decide_onboarding(oid: str, request: Request, user: User = Depends(get_current_user)):
    body = await request.json()
    decision = body.get("decision")  # approved | rejected
    if decision not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="Invalid decision")
    await db.carrier_onboarding.update_one(
        {"onboarding_id": oid},
        {"$set": {"status": decision, "decided_by": user.name, "decision_notes": body.get("notes", "")}}
    )
    return {"ok": True}

@api_router.post("/carriers/onboarding/{oid}/toggle")
async def toggle_doc(oid: str, request: Request, _: User = Depends(get_current_user)):
    body = await request.json()
    field = body.get("field")
    if field not in ("w9_received", "coi_received", "contract_signed"):
        raise HTTPException(status_code=400, detail="Invalid field")
    doc = await db.carrier_onboarding.find_one({"onboarding_id": oid}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    await db.carrier_onboarding.update_one({"onboarding_id": oid}, {"$set": {field: not doc.get(field, False)}})
    return {"ok": True}

# -------------------- DRIVER MOBILE --------------------
class DriverCheckIn(BaseModel):
    checkin_id: str
    shipment_id: str
    driver_name: str
    driver_phone: str
    status: str  # arriving_pickup, loaded, en_route, fuel, rest, delayed, arriving_dest, delivered
    lat: Optional[float] = None
    lng: Optional[float] = None
    location_text: Optional[str] = None
    note: Optional[str] = None
    created_at: str
    odometer: Optional[float] = None
    fuel_pct: Optional[int] = None

class DriverCheckInCreate(BaseModel):
    shipment_id: str
    driver_name: str
    driver_phone: str
    status: str
    lat: Optional[float] = None
    lng: Optional[float] = None
    location_text: Optional[str] = None
    note: Optional[str] = None
    odometer: Optional[float] = None
    fuel_pct: Optional[int] = None

@api_router.post("/driver/checkin")
async def driver_checkin(payload: DriverCheckInCreate):
    """Driver-side endpoint — open (auth-free) for in-cab mobile use, identified by shipment_id + driver_phone."""
    shipment = await db.shipments.find_one({"shipment_id": payload.shipment_id}, {"_id": 0})
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")

    ci = {
        "checkin_id": f"CI-{uuid.uuid4().hex[:8].upper()}",
        **payload.model_dump(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.driver_checkins.insert_one(dict(ci))

    # Map driver status -> shipment status & current_location
    status_map = {
        "arriving_pickup": "at_origin",
        "loaded": "in_transit",
        "en_route": "in_transit",
        "fuel": "in_transit",
        "rest": "in_transit",
        "delayed": "delayed",
        "arriving_dest": "in_transit",
        "delivered": "delivered",
    }
    updates: Dict[str, Any] = {}
    new_status = status_map.get(payload.status)
    if new_status:
        updates["status"] = new_status
    if payload.lat is not None and payload.lng is not None:
        updates["current_location"] = {"lat": payload.lat, "lng": payload.lng, "city": payload.location_text or "En route"}
        # rough progress estimate
        try:
            o = shipment["origin"]; d = shipment["destination"]
            total = ((d["lat"] - o["lat"]) ** 2 + (d["lng"] - o["lng"]) ** 2) ** 0.5
            done = ((payload.lat - o["lat"]) ** 2 + (payload.lng - o["lng"]) ** 2) ** 0.5
            if total > 0:
                updates["progress"] = max(0.0, min(1.0, done / total))
        except Exception:
            pass
    if updates:
        await db.shipments.update_one({"shipment_id": payload.shipment_id}, {"$set": updates})

    return {"ok": True, "checkin_id": ci["checkin_id"], "shipment_status": updates.get("status", shipment["status"])}

@api_router.get("/driver/shipment/{shipment_id}")
async def driver_get_shipment(shipment_id: str):
    """Driver-facing view (auth-free) — minimal shipment info + recent check-ins."""
    s = await db.shipments.find_one({"shipment_id": shipment_id}, {"_id": 0})
    if not s:
        raise HTTPException(status_code=404, detail="Shipment not found")
    checkins = await db.driver_checkins.find({"shipment_id": shipment_id}, {"_id": 0}).sort("created_at", -1).limit(20).to_list(20)
    return {"shipment": s, "checkins": checkins}

@api_router.get("/driver/checkins")
async def list_checkins(_: User = Depends(get_current_user), shipment_id: Optional[str] = None):
    q: Dict[str, Any] = {}
    if shipment_id: q["shipment_id"] = shipment_id
    docs = await db.driver_checkins.find(q, {"_id": 0}).sort("created_at", -1).limit(200).to_list(200)
    return docs

# -------------------- SEED --------------------
@api_router.post("/admin/seed")
async def seed_data(force: bool = False):
    """Seed mock shipments. Idempotent unless force=True."""
    count = await db.shipments.count_documents({})
    if count > 0 and not force:
        return {"ok": True, "skipped": True, "count": count}
    if force:
        await db.shipments.delete_many({})

    carriers_by_mode = {
        "TL": ["XPO Logistics", "ArcBest", "Schneider", "J.B. Hunt"],
        "LTL": ["SAIA", "R&L Carriers", "ArcBest", "XPO Logistics", "Consolidated Fastfrate"],
        "Parcel": ["UPS", "FedEx", "DHL Express"],
        "Ocean": ["Kuehne+Nagel", "Maersk", "MSC"],
        "Air": ["FedEx", "DHL Express", "Kuehne+Nagel"],
        "Rail": ["BNSF", "Union Pacific", "CSX"],
    }
    destinations = [
        {"city": "Dallas, TX", "lat": 32.7767, "lng": -96.7970},
        {"city": "Atlanta, GA", "lat": 33.7490, "lng": -84.3880},
        {"city": "Los Angeles, CA", "lat": 34.0522, "lng": -118.2437},
        {"city": "Phoenix, AZ", "lat": 33.4484, "lng": -112.0740},
        {"city": "Seattle, WA", "lat": 47.6062, "lng": -122.3321},
        {"city": "Chicago, IL", "lat": 41.8781, "lng": -87.6298},
        {"city": "Houston, TX", "lat": 29.7604, "lng": -95.3698},
        {"city": "Miami, FL", "lat": 25.7617, "lng": -80.1918},
        {"city": "Denver, CO", "lat": 39.7392, "lng": -104.9903},
        {"city": "Boston, MA", "lat": 42.3601, "lng": -71.0589},
        {"city": "Toronto, ON", "lat": 43.6532, "lng": -79.3832},
        {"city": "Mexico City, MX", "lat": 19.4326, "lng": -99.1332},
        {"city": "Rotterdam, NL (Port)", "lat": 51.9244, "lng": 4.4777},
        {"city": "Shanghai, CN (Port)", "lat": 31.2304, "lng": 121.4737},
        {"city": "Hamburg, DE (Port)", "lat": 53.5511, "lng": 9.9937},
    ]
    commodities = [
        "Floor scrubbers (T16AMR)", "Industrial cleaners (M30)", "Sweeper components", "Battery packs (Li-ion)",
        "DC motors", "Scrubber brushes", "Plastic tanks", "Steel frames", "Control assemblies", "Replacement parts",
    ]
    statuses = ["in_transit", "in_transit", "in_transit", "delayed", "delivered", "delivered", "pending", "at_origin"]

    shipments = []
    for i in range(48):
        mode = random.choice(["TL", "LTL", "Parcel", "Ocean", "Air", "Rail", "LTL", "TL"])
        carrier = random.choice(carriers_by_mode[mode])
        origin_facility = random.choice(TENNANT_FACILITIES)
        dest = random.choice(destinations)
        status = random.choice(statuses)
        # Compute current location based on status / progress
        if status in ("pending", "at_origin"):
            progress = 0.0
            cur = {"lat": origin_facility["lat"], "lng": origin_facility["lng"], "city": origin_facility["city"]}
        elif status == "delivered":
            progress = 1.0
            cur = {"lat": dest["lat"], "lng": dest["lng"], "city": dest["city"]}
        else:
            progress = round(random.uniform(0.15, 0.85), 2)
            cur = {
                "lat": origin_facility["lat"] + (dest["lat"] - origin_facility["lat"]) * progress + random.uniform(-0.5, 0.5),
                "lng": origin_facility["lng"] + (dest["lng"] - origin_facility["lng"]) * progress + random.uniform(-0.5, 0.5),
                "city": "En route",
            }
        sid = f"SHP-{uuid.uuid4().hex[:8].upper()}"
        pickup = datetime.now(timezone.utc) - timedelta(days=random.randint(0, 10))
        eta = pickup + timedelta(days=random.randint(2, 16))
        shipments.append({
            "shipment_id": sid,
            "reference": f"TN-{random.randint(10000, 99999)}",
            "mode": mode,
            "carrier": carrier,
            "status": status,
            "origin": {
                "name": origin_facility["name"], "city": origin_facility["city"],
                "lat": origin_facility["lat"], "lng": origin_facility["lng"],
                "facility": origin_facility["id"],
            },
            "destination": {"name": dest["city"], "city": dest["city"], "lat": dest["lat"], "lng": dest["lng"]},
            "current_location": cur,
            "eta": eta.isoformat(),
            "pickup_date": pickup.date().isoformat(),
            "weight_lbs": round(random.uniform(800, 42000), 0),
            "pieces": random.randint(1, 26),
            "commodity": random.choice(commodities),
            "value_usd": round(random.uniform(2500, 285000), 2),
            "container_no": f"TCLU{random.randint(1000000,9999999)}" if mode == "Ocean" else None,
            "bol_no": f"BOL{random.randint(100000,999999)}",
            "pro_no": f"PRO{random.randint(100000,999999)}",
            "progress": progress,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    await db.shipments.insert_many([dict(s) for s in shipments])

    # Seed a few documents
    doc_types = ["BOL", "COMMERCIAL_INVOICE", "PACKING_SLIP", "WEIGHT_CERT", "COO"]
    docs = []
    for s in shipments[:12]:
        t = random.choice(doc_types)
        docs.append({
            "document_id": f"DOC-{uuid.uuid4().hex[:8].upper()}",
            "type": t,
            "shipment_ref": s["reference"],
            "created_by": "System Seed",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "data": {"carrier": s["carrier"], "commodity": s["commodity"], "weight_lbs": s["weight_lbs"]},
        })
    if docs:
        await db.documents.insert_many([dict(d) for d in docs])

    # Seed some chat messages
    seed_msgs = [
        {"channel": "general", "text": "Welcome to the Tennant TMS HUD. Live data streaming."},
        {"channel": "general", "text": "Reminder: ACE filing cutoff for Tuesday departures is 17:00 ET."},
        {"channel": "ops-dispatch", "text": "Holland → Dallas TL booked with XPO. Pickup 0700 CT tomorrow."},
        {"channel": "ops-dispatch", "text": "Two parcel exceptions on UPS tracker — see /shipments?status=delayed"},
        {"channel": "import-export", "text": "K+N container TCLU6543210 cleared at LA. Drayage scheduled."},
        {"channel": "carrier-issues", "text": "XPO API latency spike noted at 14:22 — monitoring."},
    ]
    chat_docs = []
    for m in seed_msgs:
        chat_docs.append({
            "message_id": f"msg_{uuid.uuid4().hex[:10]}",
            "channel": m["channel"],
            "user_id": "system",
            "user_name": "Dispatch Bot",
            "user_picture": None,
            "text": m["text"],
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    if chat_docs:
        await db.chat_messages.insert_many(chat_docs)

    # Seed freight bills
    accessorial_codes = [
        ("DET", "Detention", 75.0), ("LIFT", "Liftgate Service", 95.0),
        ("RES", "Residential Delivery", 110.0), ("INS", "Inside Delivery", 145.0),
        ("REW", "Reweigh", 35.0), ("REC", "Reclassification", 50.0),
        ("HAZ", "Hazardous Materials", 65.0), ("APPT", "Delivery Appointment", 45.0),
    ]
    bill_statuses = ["pending", "approved", "paid", "disputed", "audit"]
    bills = []
    for s in shipments[:30]:
        base = round(s["weight_lbs"] * random.uniform(0.08, 0.45), 2)
        accs_count = random.randint(0, 3)
        accs = []
        for _ in range(accs_count):
            c = random.choice(accessorial_codes)
            accs.append({"code": c[0], "description": c[1], "amount": c[2] + round(random.uniform(0, 25), 2)})
        fuel = round(base * random.uniform(0.12, 0.28), 2)
        total = round(base + fuel + sum(a["amount"] for a in accs), 2)
        quoted = round(total * random.uniform(0.85, 1.0), 2)
        variance = round(total - quoted, 2)
        bills.append({
            "bill_id": f"FB-{uuid.uuid4().hex[:8].upper()}",
            "shipment_ref": s["reference"],
            "carrier": s["carrier"],
            "invoice_no": f"INV-{random.randint(100000, 999999)}",
            "base_charge": base,
            "accessorials": accs,
            "fuel_surcharge": fuel,
            "total": total,
            "quoted_total": quoted,
            "variance": variance,
            "status": random.choice(bill_statuses),
            "invoice_date": (datetime.now(timezone.utc) - timedelta(days=random.randint(0, 28))).isoformat(),
            "due_date": (datetime.now(timezone.utc) + timedelta(days=random.randint(5, 30))).isoformat(),
        })
    await db.freight_bills.insert_many([dict(b) for b in bills])

    # Seed carrier onboardings
    onboarding_seeds = [
        {"legal_name": "Prairie Stream Logistics LLC", "dba": "Prairie Stream", "mc_number": "MC-887214", "dot_number": "3621198", "scac": "PSLG", "mode": "TL",
         "contact_name": "Brett Halverson", "contact_email": "brett@prairiestream.com", "contact_phone": "+1-612-555-0188",
         "insurance_amount": 1500000, "insurance_expiry": (datetime.now(timezone.utc) + timedelta(days=180)).date().isoformat(),
         "safety_rating": "Satisfactory", "csa_score": 32, "status": "in_review"},
        {"legal_name": "Lakeshore Freight Co", "dba": None, "mc_number": "MC-742019", "dot_number": "2874321", "scac": "LSFC", "mode": "LTL",
         "contact_name": "Marisol Tran", "contact_email": "marisol@lakeshorefreight.com", "contact_phone": "+1-616-555-0142",
         "insurance_amount": 1000000, "insurance_expiry": (datetime.now(timezone.utc) + timedelta(days=92)).date().isoformat(),
         "safety_rating": "Satisfactory", "csa_score": 48, "status": "approved"},
        {"legal_name": "Bluegrass Express Inc", "dba": "BlueX", "mc_number": "MC-558821", "dot_number": "1842099", "scac": "BLGX", "mode": "TL",
         "contact_name": "Darnell McKee", "contact_email": "darnell@bluegrassx.com", "contact_phone": "+1-502-555-0199",
         "insurance_amount": 1000000, "insurance_expiry": (datetime.now(timezone.utc) - timedelta(days=10)).date().isoformat(),
         "safety_rating": "Conditional", "csa_score": 78, "status": "in_review"},
    ]
    onboarding_docs = []
    for ob in onboarding_seeds:
        onboarding_docs.append({
            "onboarding_id": f"OB-{uuid.uuid4().hex[:8].upper()}",
            **ob,
            "w9_received": random.choice([True, False]),
            "coi_received": random.choice([True, False]),
            "contract_signed": ob["status"] == "approved",
            "submitted_at": (datetime.now(timezone.utc) - timedelta(days=random.randint(1, 14))).isoformat(),
            "submitted_by": "Seed",
            "notes": "",
        })
    await db.carrier_onboarding.insert_many([dict(o) for o in onboarding_docs])

    return {"ok": True, "shipments": len(shipments), "documents": len(docs), "messages": len(chat_docs), "bills": len(bills), "onboardings": len(onboarding_docs)}

# -------------------- ROOT --------------------
@api_router.get("/")
async def root():
    return {"service": "Tennant TMS API", "status": "ok", "time": datetime.now(timezone.utc).isoformat()}

# -------------------- WIRE UP --------------------
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    # Auto-seed if empty
    try:
        count = await db.shipments.count_documents({})
        if count == 0:
            logger.info("Auto-seeding shipments...")
            # call seed
            from fastapi import BackgroundTasks  # noqa
            await seed_data(force=False)
    except Exception as e:
        logger.warning(f"Seed on startup failed: {e}")

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
