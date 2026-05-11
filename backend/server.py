"""
Tennant Companies — Transportation Management System (TMS)
HUD-style command center backend
"""
from fastapi import FastAPI, APIRouter, Depends, HTTPException, Request, Response, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import io
import logging
import uuid
import json
import random
import httpx
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.units import inch

from emergentintegrations.llm.chat import LlmChat, UserMessage

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
    role: str = "dispatcher"  # admin | auditor | dispatcher | driver

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

# RBAC helpers
ROLE_HIERARCHY = {"driver": 0, "dispatcher": 1, "auditor": 2, "admin": 3}

def require_role(*allowed_roles: str):
    """Dependency factory: ensure current user has one of the allowed roles, or admin (which can do anything)."""
    async def _checker(user: User = Depends(get_current_user)) -> User:
        if user.role == "admin":
            return user
        if user.role in allowed_roles:
            return user
        raise HTTPException(status_code=403, detail=f"Requires one of roles: {', '.join(allowed_roles)}")
    return _checker

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
        # First user in the system becomes admin automatically
        user_count = await db.users.count_documents({})
        initial_role = "admin" if user_count == 0 else "dispatcher"
        await db.users.insert_one({
            "user_id": user_id,
            "email": email,
            "name": name,
            "picture": picture,
            "role": initial_role,
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
    {"id": "webex", "name": "Cisco Webex", "category": "Communication", "status": "connected", "last_sync": "1m ago", "endpoint": "webexapis.com/v1"},
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
async def pay_bill(bill_id: str, user: User = Depends(require_role("auditor"))):
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
async def approve_bill(bill_id: str, user: User = Depends(require_role("auditor"))):
    bill = await db.freight_bills.find_one({"bill_id": bill_id}, {"_id": 0})
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    await db.freight_bills.update_one({"bill_id": bill_id}, {"$set": {"status": "approved", "approved_by": user.name}})
    return {"ok": True}

@api_router.post("/freight-bills/{bill_id}/dispute")
async def dispute_bill(bill_id: str, request: Request, user: User = Depends(require_role("auditor"))):
    bill = await db.freight_bills.find_one({"bill_id": bill_id}, {"_id": 0})
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
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
async def decide_onboarding(oid: str, request: Request, user: User = Depends(require_role("admin"))):
    body = await request.json()
    decision = body.get("decision")  # approved | rejected
    if decision not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="Invalid decision")
    target = await db.carrier_onboarding.find_one({"onboarding_id": oid}, {"_id": 0})
    if not target:
        raise HTTPException(status_code=404, detail="Onboarding not found")
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

# -------------------- PDF DOCUMENT RENDERING --------------------
TENNANT_BLUE = colors.HexColor("#00A4E4")
TENNANT_DARK = colors.HexColor("#0B0E14")

def _doc_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="TennantTitle", parent=styles["Heading1"], fontSize=22, leading=26, textColor=TENNANT_DARK, alignment=0, spaceAfter=4))
    styles.add(ParagraphStyle(name="TennantSubtitle", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#475569"), spaceAfter=12))
    styles.add(ParagraphStyle(name="SectionLabel", parent=styles["Normal"], fontSize=7, textColor=TENNANT_BLUE, leading=9))
    styles.add(ParagraphStyle(name="FieldLabel", parent=styles["Normal"], fontSize=7, textColor=colors.HexColor("#64748B"), leading=9))
    styles.add(ParagraphStyle(name="FieldValue", parent=styles["Normal"], fontSize=10, textColor=TENNANT_DARK, leading=13))
    styles.add(ParagraphStyle(name="DocFooter", parent=styles["Normal"], fontSize=7, textColor=colors.HexColor("#94A3B8"), alignment=1))
    return styles

DOC_TYPE_TITLES = {
    "BOL": ("BILL OF LADING", "Straight Bill of Lading — Original Domestic"),
    "COMMERCIAL_INVOICE": ("COMMERCIAL INVOICE", "Export / Customs Invoice"),
    "PACKING_SLIP": ("PACKING SLIP", "Shipment Pack List"),
    "WEIGHT_CERT": ("WEIGHT CERTIFICATE", "Certified Scale Ticket"),
    "COO": ("CERTIFICATE OF ORIGIN", "Statement of Country of Origin"),
}

def _header_block(doc_id: str, doc_type: str):
    styles = _doc_styles()
    title, subtitle = DOC_TYPE_TITLES.get(doc_type, (doc_type, ""))
    header_data = [
        [
            Paragraph("<b><font color='#00A4E4'>TENNANT</font></b> COMPANY", styles["TennantTitle"]),
            Paragraph(f"<b>{title}</b><br/><font size=8 color='#64748B'>{subtitle}</font><br/><font size=7 color='#94A3B8'>Document ID: {doc_id}</font>", styles["FieldValue"]),
        ]
    ]
    t = Table(header_data, colWidths=[3.2 * inch, 3.8 * inch])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("LINEBELOW", (0, 0), (-1, -1), 2, TENNANT_BLUE),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
    ]))
    return t

def _kv_table(rows, col_widths=None):
    styles = _doc_styles()
    data = []
    for row in rows:
        data.append([
            Paragraph(row[0].upper(), styles["FieldLabel"]),
            Paragraph(str(row[1] or "—"), styles["FieldValue"]),
        ])
    t = Table(data, colWidths=col_widths or [1.4 * inch, 2.3 * inch])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
    ]))
    return t

def _build_pdf(doc: Dict[str, Any]) -> bytes:
    buf = io.BytesIO()
    pdf = SimpleDocTemplate(buf, pagesize=letter, leftMargin=0.6 * inch, rightMargin=0.6 * inch, topMargin=0.6 * inch, bottomMargin=0.6 * inch, title=doc["document_id"])
    styles = _doc_styles()
    data = doc.get("data", {}) or {}
    elements = []
    elements.append(_header_block(doc["document_id"], doc["type"]))
    elements.append(Spacer(1, 14))

    # Shipper / Consignee block
    parties_rows = [
        ["Shipper", data.get("shipper") or "Tennant Company"],
        ["Consignee", data.get("consignee")],
        ["Origin", data.get("origin")],
        ["Destination", data.get("destination")],
    ]
    shipment_rows = [
        ["Shipment Ref", doc.get("shipment_ref")],
        ["Carrier", data.get("carrier")],
        ["Commodity", data.get("commodity")],
        ["Pieces", data.get("pieces")],
        ["Weight (lbs)", data.get("weight")],
        ["Value (USD)", data.get("value") and f"${data.get('value')}"],
    ]

    parties_t = _kv_table(parties_rows, col_widths=[1.0 * inch, 2.4 * inch])
    shipment_t = _kv_table(shipment_rows, col_widths=[1.1 * inch, 2.3 * inch])
    columns = Table([[parties_t, shipment_t]], colWidths=[3.5 * inch, 3.5 * inch])
    columns.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOX", (0, 0), (0, 0), 0.5, colors.HexColor("#E2E8F0")),
        ("BOX", (1, 0), (1, 0), 0.5, colors.HexColor("#E2E8F0")),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    elements.append(columns)
    elements.append(Spacer(1, 16))

    # Type-specific section
    dtype = doc["type"]
    if dtype == "BOL":
        line_items = [["#", "Pieces", "Description", "Weight (lbs)", "Class"]]
        line_items.append(["1", data.get("pieces") or "—", data.get("commodity") or "Tennant industrial cleaning equipment", data.get("weight") or "—", "85"])
        items = Table(line_items, colWidths=[0.4 * inch, 0.8 * inch, 3.6 * inch, 1.0 * inch, 0.7 * inch])
        items.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), TENNANT_BLUE),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#E2E8F0")),
            ("PADDING", (0, 0), (-1, -1), 5),
        ]))
        elements.append(Paragraph("<b><font color='#00A4E4'>LINE ITEMS</font></b>", styles["FieldLabel"]))
        elements.append(Spacer(1, 4))
        elements.append(items)
        elements.append(Spacer(1, 14))
        elements.append(Paragraph("<font size=8 color='#475569'>RECEIVED, subject to the classifications and tariffs in effect on the date of issue, the property described above in apparent good order, except as noted (contents and condition of contents of packages unknown).</font>", styles["FieldValue"]))

    elif dtype == "COMMERCIAL_INVOICE":
        try:
            qty = float(data.get("pieces") or 0)
            total = float(data.get("value") or 0)
            unit_price = total / qty if qty else total
        except Exception:
            qty, total, unit_price = "—", "—", "—"
        rows = [["Qty", "HS Code (suggested)", "Description", "Unit Price", "Total"]]
        rows.append([data.get("pieces") or "—", "8479.89.94", data.get("commodity") or "—",
                     f"${unit_price:,.2f}" if isinstance(unit_price, float) else unit_price,
                     f"${total:,.2f}" if isinstance(total, float) else total])
        items = Table(rows, colWidths=[0.6 * inch, 1.3 * inch, 3.0 * inch, 1.0 * inch, 1.1 * inch])
        items.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), TENNANT_BLUE),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#E2E8F0")),
            ("PADDING", (0, 0), (-1, -1), 5),
        ]))
        elements.append(Paragraph("<b><font color='#00A4E4'>INVOICE LINES</font></b>", styles["FieldLabel"]))
        elements.append(Spacer(1, 4))
        elements.append(items)
        elements.append(Spacer(1, 12))
        elements.append(Paragraph(f"<b>TOTAL INVOICE VALUE: ${data.get('value', '—')} USD</b>", styles["FieldValue"]))
        elements.append(Spacer(1, 8))
        elements.append(Paragraph("<font size=7 color='#64748B'>Terms: Incoterms 2020 — DAP. No commission. Country of Origin: USA unless otherwise noted.</font>", styles["FieldValue"]))

    elif dtype == "PACKING_SLIP":
        rows = [["Carton", "Qty", "Description", "Weight", "Dimensions"]]
        pcs = int(data.get("pieces") or 1) if str(data.get("pieces") or "1").isdigit() else 1
        for i in range(1, min(pcs, 8) + 1):
            rows.append([f"#{i:03d}", "1", data.get("commodity") or "—", f"{(float(data.get('weight') or 0) / max(1, pcs)):,.0f} lbs" if data.get("weight") else "—", "48×40×60 in"])
        items = Table(rows, colWidths=[0.7 * inch, 0.5 * inch, 3.6 * inch, 0.9 * inch, 1.3 * inch])
        items.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), TENNANT_BLUE),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#E2E8F0")),
            ("PADDING", (0, 0), (-1, -1), 5),
        ]))
        elements.append(items)

    elif dtype == "WEIGHT_CERT":
        elements.append(Paragraph("<b><font color='#00A4E4'>CERTIFIED WEIGHT</font></b>", styles["FieldLabel"]))
        elements.append(Spacer(1, 4))
        wt_rows = [
            ["Gross Weight", f"{data.get('weight') or '—'} lbs"],
            ["Tare Weight", "14,200 lbs"],
            ["Net Weight (calc)", f"{(float(data.get('weight') or 0) - 14200):,.0f} lbs" if data.get('weight') else "—"],
            ["Scale ID", "MN-CERT-04287"],
            ["Operator", doc.get("created_by") or "—"],
            ["Date / Time", doc.get("created_at") or "—"],
        ]
        elements.append(_kv_table(wt_rows, col_widths=[1.6 * inch, 2.4 * inch]))
        elements.append(Spacer(1, 12))
        elements.append(Paragraph("<font size=7 color='#475569'>I hereby certify that the weights shown above were obtained on a scale certified by the State of Minnesota and accurate within tolerance NIST Handbook 44.</font>", styles["FieldValue"]))

    elif dtype == "COO":
        coo_rows = [
            ["Country of Origin", data.get("country_origin") or "USA"],
            ["Producer", "Tennant Company"],
            ["Producer Address", "10400 Clean Street, Eden Prairie, MN 55344, USA"],
            ["Exporter", "Tennant Company"],
            ["Marks & Numbers", doc.get("shipment_ref") or "—"],
        ]
        elements.append(_kv_table(coo_rows, col_widths=[1.6 * inch, 4.0 * inch]))
        elements.append(Spacer(1, 14))
        elements.append(Paragraph("<font size=8 color='#475569'>The undersigned hereby declares that the above-mentioned goods originate from the country shown above and meet all applicable origin criteria. This certificate is issued in accordance with applicable Free Trade Agreement rules of origin where claimed.</font>", styles["FieldValue"]))

    # Signature block
    elements.append(Spacer(1, 26))
    sig_data = [
        [Paragraph("<font size=7 color='#64748B'>Authorized Signature</font><br/><br/>______________________________", styles["FieldValue"]),
         Paragraph(f"<font size=7 color='#64748B'>Date</font><br/><br/>{datetime.now(timezone.utc).strftime('%Y-%m-%d')}", styles["FieldValue"]),
         Paragraph(f"<font size=7 color='#64748B'>Prepared By</font><br/><br/>{doc.get('created_by') or '—'}", styles["FieldValue"])],
    ]
    sig = Table(sig_data, colWidths=[2.7 * inch, 1.4 * inch, 2.7 * inch])
    sig.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    elements.append(sig)
    elements.append(Spacer(1, 8))
    elements.append(Paragraph(f"Tennant Company · TMS Generated Document · {datetime.now(timezone.utc).isoformat(timespec='seconds')}Z", styles["DocFooter"]))

    pdf.build(elements)
    buf.seek(0)
    return buf.getvalue()

@api_router.get("/documents/{document_id}/pdf")
async def download_document_pdf(document_id: str, _: User = Depends(get_current_user)):
    doc = await db.documents.find_one({"document_id": document_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        pdf_bytes = _build_pdf(doc)
    except Exception as e:
        logger.exception("PDF render failed")
        raise HTTPException(status_code=500, detail=f"PDF render failed: {e}")
    filename = f"{doc['type']}_{doc['document_id']}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

# -------------------- ADMIN / RBAC --------------------
@api_router.get("/admin/users")
async def list_users(_: User = Depends(require_role("admin"))):
    docs = await db.users.find({}, {"_id": 0}).sort("created_at", 1).to_list(500)
    return docs

class RoleChange(BaseModel):
    role: str  # admin | auditor | dispatcher | driver

@api_router.post("/admin/users/{user_id}/role")
async def change_role(user_id: str, payload: RoleChange, actor: User = Depends(require_role("admin"))):
    if payload.role not in ROLE_HIERARCHY:
        raise HTTPException(status_code=400, detail="Invalid role")
    target = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    # Don't allow the actor to demote themselves if they are the only admin
    if target["user_id"] == actor.user_id and payload.role != "admin":
        admin_count = await db.users.count_documents({"role": "admin"})
        if admin_count <= 1:
            raise HTTPException(status_code=400, detail="Cannot demote the only remaining admin")
    await db.users.update_one({"user_id": user_id}, {"$set": {"role": payload.role}})
    return {"ok": True, "user_id": user_id, "role": payload.role}

@api_router.post("/admin/seed-team")
async def seed_team_users(_: User = Depends(require_role("admin"))):
    """Seed sample team members across roles for demo."""
    samples = [
        {"name": "Avery Lindgren", "email": "avery.lindgren@tennantco.com", "role": "auditor"},
        {"name": "Devon Marquez", "email": "devon.marquez@tennantco.com", "role": "dispatcher"},
        {"name": "Priya Iyer", "email": "priya.iyer@tennantco.com", "role": "dispatcher"},
        {"name": "Sam Chen", "email": "sam.chen@tennantco.com", "role": "driver"},
        {"name": "Riley Park", "email": "riley.park@tennantco.com", "role": "driver"},
    ]
    inserted = 0
    for s in samples:
        if await db.users.find_one({"email": s["email"]}):
            continue
        await db.users.insert_one({
            "user_id": f"user_{uuid.uuid4().hex[:12]}",
            "email": s["email"], "name": s["name"], "picture": None,
            "role": s["role"], "created_at": datetime.now(timezone.utc).isoformat(),
        })
        inserted += 1
    return {"ok": True, "inserted": inserted}

# -------------------- SAP S/4HANA OData CONNECTOR (mocked) --------------------
SAP_MOCK_CONFIG = {
    "system_id": "S4P",
    "host": "https://s4hana.tennantco.sap.com",
    "service": "/sap/opu/odata/sap/API_SALES_ORDER_SRV",
    "client": "100",
    "user": "TMS_SVC_ACCT",
    "auth_type": "OAuth 2.0 (SAML Bearer Assertion)",
}

def _gen_sap_sales_orders(n: int = 24) -> List[Dict[str, Any]]:
    """Deterministic-ish sales order data (uses random but reseeded per call for stable demo)."""
    random.seed(42)
    customers = [
        ("CUST-100214", "Walmart Distribution — Bentonville"),
        ("CUST-100755", "Amazon Fulfillment — Phoenix"),
        ("CUST-100928", "FedEx Freight HQ — Memphis"),
        ("CUST-101044", "U.S. Postal Service — Washington DC"),
        ("CUST-101188", "Target Distribution — Minneapolis"),
        ("CUST-101332", "Costco Wholesale — Issaquah"),
        ("CUST-101501", "Boeing Everett Plant"),
        ("CUST-101677", "Ford F-150 Plant — Dearborn"),
    ]
    materials = [
        ("MAT-T16AMR", "Tennant T16 AMR Ride-On Scrubber", 38500.00),
        ("MAT-M30", "Tennant M30 Integrated Sweeper-Scrubber", 52000.00),
        ("MAT-S30", "Tennant S30 Industrial Sweeper", 41200.00),
        ("MAT-T7AMR", "Tennant T7 AMR Compact Robotic", 28900.00),
        ("MAT-M17", "Tennant M17 Mid-Size Sweeper-Scrubber", 33400.00),
        ("MAT-PARTS-BAT", "Tennant Lithium-Ion Battery Pack (Service Part)", 2150.00),
    ]
    plants = [("1010", "Golden Valley, MN"), ("1020", "Holland, MI"), ("1030", "Louisville, KY")]
    statuses = ["Open", "Open", "In Production", "Released to Shipping", "Confirmed", "Partial Delivery"]
    out = []
    for i in range(n):
        c = random.choice(customers)
        m = random.choice(materials)
        p = random.choice(plants)
        qty = random.randint(1, 6)
        net = round(m[2] * qty, 2)
        order_date = (datetime.now(timezone.utc) - timedelta(days=random.randint(0, 45))).date().isoformat()
        req_date = (datetime.now(timezone.utc) + timedelta(days=random.randint(7, 60))).date().isoformat()
        out.append({
            "SalesOrder": f"SO-{500000 + i}",
            "SalesOrderType": "OR",
            "SoldToParty": c[0],
            "SoldToPartyName": c[1],
            "PurchaseOrderByCustomer": f"PO-{random.randint(70000, 99999)}",
            "Material": m[0],
            "MaterialDescription": m[1],
            "RequestedQuantity": qty,
            "NetAmount": net,
            "Currency": "USD",
            "Plant": p[0],
            "PlantName": p[1],
            "RequestedDeliveryDate": req_date,
            "CreationDate": order_date,
            "OverallStatus": random.choice(statuses),
            "IncoTerms": random.choice(["FCA", "DAP", "DDP", "EXW"]),
        })
    return out

def _gen_sap_purchase_orders(n: int = 16) -> List[Dict[str, Any]]:
    random.seed(7)
    vendors = [
        ("VEND-KNS", "Kuehne+Nagel Services (Import Logistics)"),
        ("VEND-MOTREX", "Motrex Co. Ltd — Drive Motors (KR)"),
        ("VEND-BATTCO", "BattCo Industries — Battery Cells (DE)"),
        ("VEND-PLASTIC", "Premier Polymers — Tank Bodies (US)"),
        ("VEND-STEEL", "Midwest Steel Frame Co (US)"),
        ("VEND-WIRING", "Yazaki Wiring Harness (JP)"),
    ]
    components = [
        ("CMP-DCMOT-750W", "DC Drive Motor 750W"),
        ("CMP-BATT-LI24V", "Li-ion Battery Module 24V 100Ah"),
        ("CMP-TANK-50G", "Solution Tank 50 Gallon — Molded"),
        ("CMP-FRAME-T16", "Chassis Frame Assy T16AMR"),
        ("CMP-HARNESS-S30", "Wiring Harness S30 Master Assy"),
        ("CMP-BRUSH-32", "Cylindrical Brush 32-inch"),
    ]
    plants = [("1010", "Golden Valley, MN"), ("1020", "Holland, MI"), ("1030", "Louisville, KY")]
    statuses = ["Open", "Released", "Goods Issued", "In Transit", "Partial GR", "Closed"]
    out = []
    for i in range(n):
        v = random.choice(vendors)
        c = random.choice(components)
        p = random.choice(plants)
        qty = random.randint(40, 800)
        unit_price = round(random.uniform(38, 1450), 2)
        net = round(unit_price * qty, 2)
        out.append({
            "PurchaseOrder": f"PO-{4500000 + i}",
            "Supplier": v[0],
            "SupplierName": v[1],
            "Material": c[0],
            "MaterialDescription": c[1],
            "OrderQuantity": qty,
            "NetPriceAmount": unit_price,
            "NetAmount": net,
            "Currency": "USD",
            "Plant": p[0],
            "PlantName": p[1],
            "CreationDate": (datetime.now(timezone.utc) - timedelta(days=random.randint(2, 30))).date().isoformat(),
            "DeliveryDate": (datetime.now(timezone.utc) + timedelta(days=random.randint(5, 45))).date().isoformat(),
            "OverallStatus": random.choice(statuses),
            "IncoTerms": random.choice(["FCA", "DAP", "DDP"]),
            "IsImport": v[0] == "VEND-KNS" or "(KR)" in v[1] or "(DE)" in v[1] or "(JP)" in v[1],
        })
    return out

@api_router.get("/sap/config")
async def sap_config(_: User = Depends(get_current_user)):
    return SAP_MOCK_CONFIG

@api_router.get("/sap/sales-orders")
async def sap_sales_orders(_: User = Depends(get_current_user), plant: Optional[str] = None, status: Optional[str] = None):
    orders = _gen_sap_sales_orders()
    if plant: orders = [o for o in orders if o["Plant"] == plant]
    if status: orders = [o for o in orders if o["OverallStatus"] == status]
    return {"value": orders, "@odata.count": len(orders), "source": SAP_MOCK_CONFIG["host"] + SAP_MOCK_CONFIG["service"]}

@api_router.get("/sap/purchase-orders")
async def sap_purchase_orders(_: User = Depends(get_current_user), plant: Optional[str] = None, only_imports: bool = False):
    orders = _gen_sap_purchase_orders()
    if plant: orders = [o for o in orders if o["Plant"] == plant]
    if only_imports: orders = [o for o in orders if o["IsImport"]]
    return {"value": orders, "@odata.count": len(orders), "source": SAP_MOCK_CONFIG["host"] + "/sap/opu/odata/sap/API_PURCHASEORDER_PROCESS_SRV"}

@api_router.post("/sap/sync")
async def sap_sync(_: User = Depends(require_role("admin", "dispatcher"))):
    """Simulate triggering an OData sync — records timestamp in db.sync_logs."""
    sales = _gen_sap_sales_orders()
    purch = _gen_sap_purchase_orders()
    log = {
        "log_id": f"SYNC-{uuid.uuid4().hex[:8].upper()}",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "sales_count": len(sales),
        "purchase_count": len(purch),
        "duration_ms": random.randint(820, 1850),
        "status": "success",
    }
    await db.sap_sync_logs.insert_one(dict(log))
    return log

@api_router.get("/sap/sync-logs")
async def sap_sync_logs(_: User = Depends(get_current_user)):
    docs = await db.sap_sync_logs.find({}, {"_id": 0}).sort("started_at", -1).limit(30).to_list(30)
    return docs

# -------------------- SEED --------------------
# -------------------- AI ASSISTANT (Claude Sonnet 4.5) --------------------
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY")

AI_SYSTEM_PROMPT = """You are HUDLINK, the AI co-pilot inside the Tennant Companies Transportation Management System (TMS).

Tennant Company is a Minnesota-based manufacturer of industrial and commercial floor scrubbers and cleaners with manufacturing facilities in Louisville KY, Holland MI, and Golden Valley MN (HQ). Parts are imported via Kuehne+Nagel.

You help dispatchers, freight auditors, and operations leaders with:
- Shipment status, lane-level decisions, mode selection (TL, LTL, Parcel, Ocean, Air, Rail)
- Freight bill audit: accessorial charges, fuel surcharge norms, when to dispute
- Carrier scorecards and routing recommendations
- HS code classification for cleaning machinery, lithium batteries, motors, brushes (HTS chapter 8479, 8508, 8507, etc.)
- Document requirements: BOL, Commercial Invoice, Packing Slip, Weight Certificate, Certificate of Origin
- Compliance: DOT/FMCSA, ACE filings, Incoterms 2020, CBP
- SAP S/4HANA SO/PO context — sales orders ship from plants 1010 (Golden Valley), 1020 (Holland), 1030 (Louisville)

Style: terse, technical, action-oriented. Use bullet points and numbers. When asked for recommendations, give a clear primary answer, then 1-2 alternatives. Cite HS codes, Incoterms, and section names when relevant. Never invent data — if asked for live shipment IDs, tell the user to query the dashboard.
"""

class AIMessageIn(BaseModel):
    session_id: str
    message: str

@api_router.post("/ai/chat")
async def ai_chat(payload: AIMessageIn, user: User = Depends(get_current_user)):
    if not EMERGENT_LLM_KEY:
        raise HTTPException(status_code=500, detail="EMERGENT_LLM_KEY not configured")
    # Persist user message
    user_msg_doc = {
        "session_id": payload.session_id,
        "user_id": user.user_id,
        "role": "user",
        "text": payload.message,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.ai_messages.insert_one(dict(user_msg_doc))

    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=payload.session_id,
            system_message=AI_SYSTEM_PROMPT,
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")
        reply = await chat.send_message(UserMessage(text=payload.message))
    except Exception as e:
        logger.exception("AI chat failed")
        raise HTTPException(status_code=502, detail=f"AI provider error: {e}")

    assistant_doc = {
        "session_id": payload.session_id,
        "user_id": user.user_id,
        "role": "assistant",
        "text": reply,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.ai_messages.insert_one(dict(assistant_doc))
    return {"reply": reply}

@api_router.get("/ai/history")
async def ai_history(session_id: str, user: User = Depends(get_current_user)):
    docs = await db.ai_messages.find(
        {"session_id": session_id, "user_id": user.user_id},
        {"_id": 0}
    ).sort("created_at", 1).limit(200).to_list(200)
    return docs

@api_router.delete("/ai/history")
async def ai_clear(session_id: str, user: User = Depends(get_current_user)):
    await db.ai_messages.delete_many({"session_id": session_id, "user_id": user.user_id})
    return {"ok": True}

# -------------------- WEBEX INTEGRATION (mocked) --------------------
WEBEX_CONFIG = {
    "org_id": "Y2lzY29zcGFyazovL3VzL09SR0FOSVpBVElPTi90ZW5uYW50Y28",
    "site": "tennantco.webex.com",
    "bot_email": "tms-bot@tennantco.webex.bot",
    "scopes": ["spark:rooms_read", "spark:messages_write", "meetings:schedules_write"],
    "status": "connected",
}

WEBEX_SPACES = [
    {"id": "SPC-OPS-DISP", "title": "Ops Dispatch — Daily Stand-up", "type": "group", "members": 14, "last_activity": "8m"},
    {"id": "SPC-IMPORT", "title": "Import / K+N Coordination", "type": "group", "members": 9, "last_activity": "22m"},
    {"id": "SPC-CARR-ESC", "title": "Carrier Escalations", "type": "group", "members": 22, "last_activity": "1h"},
    {"id": "SPC-PLANT-LVK", "title": "Louisville Plant Logistics", "type": "group", "members": 11, "last_activity": "3h"},
    {"id": "SPC-PLANT-HOM", "title": "Holland Plant Logistics", "type": "group", "members": 8, "last_activity": "5h"},
    {"id": "SPC-PLANT-GVM", "title": "Golden Valley HQ — All-Hands", "type": "group", "members": 47, "last_activity": "Yesterday"},
    {"id": "SPC-KIRK-1on1", "title": "Kirk Juergins — Direct Messages", "type": "direct", "members": 2, "last_activity": "2d"},
]

WEBEX_MEETINGS = [
    {"id": "MTG-7821", "title": "Weekly Carrier Performance Review", "host": "Kirk Juergins", "start": "2026-05-12T14:00:00Z", "duration_min": 60, "attendees": 8, "join_url": "https://tennantco.webex.com/meet/kirk.j/MTG-7821"},
    {"id": "MTG-7822", "title": "K+N Import Coordination — May Cycle", "host": "Avery Lindgren", "start": "2026-05-13T15:30:00Z", "duration_min": 45, "attendees": 6, "join_url": "https://tennantco.webex.com/meet/avery.l/MTG-7822"},
    {"id": "MTG-7825", "title": "SAP S/4HANA TMS Integration — Sprint Demo", "host": "Devon Marquez", "start": "2026-05-14T17:00:00Z", "duration_min": 30, "attendees": 12, "join_url": "https://tennantco.webex.com/meet/devon.m/MTG-7825"},
    {"id": "MTG-7830", "title": "Q2 Freight Spend Audit Findings", "host": "Avery Lindgren", "start": "2026-05-15T19:00:00Z", "duration_min": 60, "attendees": 5, "join_url": "https://tennantco.webex.com/meet/avery.l/MTG-7830"},
]

@api_router.get("/webex/config")
async def webex_config(_: User = Depends(get_current_user)):
    return WEBEX_CONFIG

@api_router.get("/webex/spaces")
async def webex_spaces(_: User = Depends(get_current_user)):
    return WEBEX_SPACES

@api_router.get("/webex/meetings")
async def webex_meetings(_: User = Depends(get_current_user)):
    return WEBEX_MEETINGS

class WebexNotifyIn(BaseModel):
    space_id: str
    text: str
    shipment_ref: Optional[str] = None

@api_router.post("/webex/notify")
async def webex_notify(payload: WebexNotifyIn, user: User = Depends(get_current_user)):
    """Simulate posting a message to a Webex space."""
    record = {
        "log_id": f"WBX-{uuid.uuid4().hex[:8].upper()}",
        "space_id": payload.space_id,
        "user_id": user.user_id,
        "user_name": user.name,
        "text": payload.text,
        "shipment_ref": payload.shipment_ref,
        "posted_at": datetime.now(timezone.utc).isoformat(),
        "status": "delivered",
    }
    await db.webex_log.insert_one(dict(record))
    return record

@api_router.get("/webex/log")
async def webex_log(_: User = Depends(get_current_user)):
    docs = await db.webex_log.find({}, {"_id": 0}).sort("posted_at", -1).limit(50).to_list(50)
    return docs

class WebexScheduleIn(BaseModel):
    title: str
    when: str  # ISO datetime
    duration_min: int = 30
    invitees: List[str] = []

@api_router.post("/webex/schedule")
async def webex_schedule(payload: WebexScheduleIn, user: User = Depends(get_current_user)):
    meeting = {
        "id": f"MTG-{random.randint(8000, 9999)}",
        "title": payload.title,
        "host": user.name,
        "start": payload.when,
        "duration_min": payload.duration_min,
        "attendees": len(payload.invitees),
        "join_url": f"https://tennantco.webex.com/meet/{user.user_id}/MTG-{uuid.uuid4().hex[:6].upper()}",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.webex_meetings.insert_one(dict(meeting))
    return meeting

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
