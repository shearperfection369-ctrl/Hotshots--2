"""routes.truck_cleaning_crew — crew PIN portal (clock/checklists/photos/geo),
live crew map, timesheets, company updates, expenses/P&L, company vehicles,
gear sourcing list, and the public booking inbox."""
import hashlib
import hmac
import io
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

import bcrypt
import math
from bson import ObjectId
from fastapi import (APIRouter, Depends, File, Form, HTTPException, Request,
                     UploadFile)
from motor.motor_asyncio import AsyncIOMotorGridFSBucket
from PIL import Image
from pydantic import BaseModel, Field

from routes.truck_cleaning import UPSELL_META, UPSELLS, SCENT_MENU
from routes.truck_cleaning_sched import CLEANING_GUIDE

UPSELL_LABEL = {u["id"]: u["label"] for u in UPSELL_META}
SESSION_HOURS = 14
MAX_FAILURES = 5
LOCK_MINUTES = 15


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _pepper() -> bytes:
    return os.environ["HS_JWT_SECRET"].encode()


def _pin_lookup(pin: str) -> str:
    return hmac.new(_pepper(), pin.encode(), "sha256").hexdigest()


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _build_checklist(upsells: List[str]) -> List[Dict[str, Any]]:
    items = [{"id": f"phase-{i}", "label": p["phase"], "minutes": p["minutes"],
              "kind": "core", "done": False, "done_at": None}
             for i, p in enumerate(CLEANING_GUIDE["phases"])]
    for u in upsells:
        items.append({"id": f"upsell-{u}", "label": UPSELL_LABEL.get(u, u.replace("_", " ").title()),
                      "minutes": 10, "kind": "upsell", "done": False, "done_at": None})
    return items


GEAR = [
    {"cat": "Vacuums & Extraction", "items": [
        {"name": "DEWALT 20V MAX Cordless Wet/Dry Vacuum (DCV581H)", "store": "Amazon", "est": 139,
         "why": "Battery-powered, 2-gal, fits every yard job — no generator, no cords across lanes.",
         "url": "https://www.amazon.com/s?k=DEWALT+DCV581H+cordless+wet+dry+vacuum"},
        {"name": "Milwaukee M18 Compact Vacuum (0882-20)", "store": "Amazon", "est": 119,
         "why": "Crew favorite backup — shares M18 batteries with the blower.",
         "url": "https://www.amazon.com/s?k=Milwaukee+M18+0882-20+compact+vacuum"},
        {"name": "BISSELL Pet Stain Eraser PowerBrush (cordless shampooer)", "store": "Amazon", "est": 99,
         "why": "Battery spot shampooer for seats, carpet lanes and bunk mattresses.",
         "url": "https://www.amazon.com/s?k=BISSELL+Pet+Stain+Eraser+PowerBrush+cordless"},
        {"name": "BISSELL Little Green Pro (shop/base unit)", "store": "Amazon", "est": 123,
         "why": "Corded deep extractor kept in the van for heavy stain jobs.",
         "url": "https://www.amazon.com/s?k=Bissell+Little+Green+Pro+portable+carpet+cleaner"}]},
    {"cat": "Blowers", "items": [
        {"name": "Bauer 20V Cordless Blower", "store": "Harbor Freight", "est": 45,
         "why": "Cheap, powerful crew blower — blast crumbs from rails, vents and pedals before vacuuming.",
         "url": "https://www.harborfreight.com/search?q=bauer%2020v%20cordless%20blower"},
        {"name": "WORX 20V NITRO Cordless Blower (brushless)", "store": "Amazon", "est": 69,
         "why": "Higher CFM option for exterior dust-offs and floor mats.",
         "url": "https://www.amazon.com/s?k=WORX+20V+Nitro+cordless+blower"}]},
    {"cat": "Brushes", "items": [
        {"name": "Drill Brush Power Scrubber Kit (4-pc, soft/med/stiff)", "store": "Amazon", "est": 16,
         "why": "The upholstery workhorse — chucks into any drill for seats, mats and carpet.",
         "url": "https://www.amazon.com/s?k=drill+brush+power+scrubber+kit+4+piece"},
        {"name": "Wire Brush Set 6-pc (steel / brass / nylon)", "store": "Harbor Freight", "est": 4,
         "why": "Steel wire for pedals, steps and rusted brightwork; brass for softer metal.",
         "url": "https://www.harborfreight.com/search?q=wire%20brush%20set%206%20piece"},
        {"name": "Detail Brush Set (vent / seam / cup-holder)", "store": "Harbor Freight", "est": 6,
         "why": "Vents, buttons, stalks, seams — one set per tech bag.",
         "url": "https://www.harborfreight.com/search?q=detail%20brush%20set"},
        {"name": "Stiff Deck Scrub Brush + handle", "store": "Harbor Freight", "est": 9,
         "why": "Rubber floor mats and entry steps.",
         "url": "https://www.harborfreight.com/search?q=scrub%20brush"}]},
    {"cat": "Scents & Odor", "items": [
        {"name": "Little Trees Black Ice (24-pack)", "store": "Amazon", "est": 14,
         "why": "Top-requested scent on the menu — $0.58/unit, sells at $5.",
         "url": "https://www.amazon.com/s?k=little+trees+black+ice+24+pack"},
        {"name": "Chemical Guys New Car Smell (16 oz)", "store": "Amazon", "est": 11,
         "why": "Spray-based 'New Truck Smell' for the premium finish.",
         "url": "https://www.amazon.com/s?k=chemical+guys+new+car+smell+16+oz"},
        {"name": "Ozium Air Sanitizer 8 oz (2-pack)", "store": "Amazon", "est": 22,
         "why": "Smoke-odor killer for the Ozone Odor Bomb upsell prep.",
         "url": "https://www.amazon.com/s?k=ozium+air+sanitizer+8+oz"},
        {"name": "Rocco & Roxie Enzyme Odor Eliminator (gallon)", "store": "Amazon", "est": 50,
         "why": "Enzyme base for mattress refresh + odor-kill phase.",
         "url": "https://www.amazon.com/s?k=rocco+roxie+odor+eliminator+gallon"}]},
    {"cat": "Chemicals & Supplies", "items": [
        {"name": "Chemical Guys All-Purpose Cleaner (1 gal, dilute 10:1)", "store": "Amazon", "est": 25,
         "why": "One gallon = ~40 cabs of APC at dilution.",
         "url": "https://www.amazon.com/s?k=chemical+guys+all+purpose+cleaner+gallon"},
        {"name": "Invisible Glass ammonia-free (2-pack)", "store": "Amazon", "est": 13,
         "why": "Streak-free glass is the quality bar — ammonia-free protects tint.",
         "url": "https://www.amazon.com/s?k=invisible+glass+cleaner+2+pack"},
        {"name": "Microfiber Towels 36-pack (color-coded)", "store": "Amazon", "est": 21,
         "why": "Blue glass / yellow interior / red floors — 12 per tech.",
         "url": "https://www.amazon.com/s?k=microfiber+towels+36+pack"},
        {"name": "2-Gallon Pump Sprayer", "store": "Harbor Freight", "est": 15,
         "why": "Low-PSI pre-spray for mats and engine-bay upsell.",
         "url": "https://www.harborfreight.com/search?q=2%20gallon%20pump%20sprayer"},
        {"name": "Nitrile Gloves 100-pack", "store": "Harbor Freight", "est": 8,
         "why": "Chemical steps — one box per crew per month.",
         "url": "https://www.harborfreight.com/search?q=nitrile%20gloves"},
        {"name": "Heavy-Duty Storage Totes + knee pads", "store": "Harbor Freight", "est": 20,
         "why": "Driver-belongings tote (never throw anything away) + crew knee pads.",
         "url": "https://www.harborfreight.com/search?q=storage%20tote"}]},
]

EXPENSE_CATEGORIES = ["supplies", "fuel", "labor", "equipment", "marketing", "insurance", "vehicle", "other"]

YARD_PROSPECTS = [
    # Tier A — small/agile fleets & drayage yards (10-30 cabs, fast decisions)
    {"name": "CTX — Commodity Transfer Exchange", "city": "Minneapolis (NE)", "address": "2752 Central Ave NE, Minneapolis, MN 55418",
     "ptype": "Intermodal drayage yard", "est_cabs": "15–30 day cabs", "tier": "A",
     "angle": "Drayage day cabs live at the yard — perfect recurring lock-in. Ask for the terminal/ops manager."},
    {"name": "CMC / ITI Intermodal", "city": "Minneapolis (SE)", "address": "620 Malcolm Ave SE, Minneapolis, MN 55414",
     "ptype": "Intermodal drayage yard", "est_cabs": "15–40 day cabs", "tier": "A",
     "angle": "Same yard cluster as UP Twin Cities intermodal (525 Kasota Ave SE) — pitch both in one visit."},
    {"name": "Twin City Hauling", "city": "Twin Cities metro", "address": "",
     "ptype": "Local hauling fleet", "est_cabs": "10–25 (est.)", "tier": "A",
     "angle": "Small owner-run local fleet — owner picks up the phone. Driver-retention pitch lands hard."},
    {"name": "MJ Trucking Co", "city": "Twin Cities metro", "address": "",
     "ptype": "Small regional fleet", "est_cabs": "10–20 (est.)", "tier": "A",
     "angle": "Small fleet = one decision maker. Offer the 2-free-cab pilot on their yard day."},
    {"name": "A&H Cartage", "city": "St. Paul", "address": "",
     "ptype": "Cartage / local P&D", "est_cabs": "10–25 (est.)", "tier": "A",
     "angle": "Cartage cabs cycle through the yard daily — easy to clean without downtime."},
    {"name": "Jacobs Trucking", "city": "Twin Cities metro", "address": "",
     "ptype": "Regional fleet", "est_cabs": "10–30 (est.)", "tier": "A",
     "angle": "Family-run — pitch pride-of-fleet + driver retention, not price."},
    {"name": "Eilenson Trucking", "city": "Twin Cities metro", "address": "",
     "ptype": "Small fleet", "est_cabs": "10–20 (est.)", "tier": "A",
     "angle": "Small enough to sign a bi-weekly lock-in on the first call."},
    # Tier B — LTL service centers (fixed yards, day cabs, standardized budgets)
    {"name": "Estes Express — Minneapolis Terminal", "city": "Coon Rapids", "address": "11220 Xeon St NW, Coon Rapids, MN 55448",
     "ptype": "LTL service center", "est_cabs": "20–40 city cabs", "tier": "B",
     "angle": "LTL city cabs return to the yard nightly. Ask for the Service Center Manager; vendor setup is routine."},
    {"name": "XPO — Saint Paul Service Center", "city": "Eagan / St. Paul", "address": "3450 Dodd Rd, Saint Paul, MN 55123",
     "ptype": "LTL service center", "est_cabs": "20–40 city cabs", "tier": "B",
     "angle": "Same-yard nightly cabs; sell the photo-proof link as their internal QA record."},
    {"name": "Dayton Freight — Minneapolis SC", "city": "Twin Cities metro", "address": "",
     "ptype": "LTL service center", "est_cabs": "15–35 city cabs", "tier": "B",
     "angle": "Midwest family LTL — big on driver experience awards. Clean cabs = their brand."},
    {"name": "Old Dominion — Minneapolis SC", "city": "Twin Cities metro", "address": "",
     "ptype": "LTL service center", "est_cabs": "20–40 city cabs", "tier": "B",
     "angle": "OD wins 'best LTL to drive for' — pitch cab cleanliness as a retention line item."},
    {"name": "R+L Carriers — MN Service Center", "city": "Twin Cities metro", "address": "",
     "ptype": "LTL service center (new)", "est_cabs": "15–30 city cabs", "tier": "B",
     "angle": "Newly opened MN service center — new yards set up vendors fast."},
    {"name": "Magnum Logistics — MSP Terminal", "city": "Twin Cities metro", "address": "",
     "ptype": "Regional LTL terminal", "est_cabs": "10–25 (est.)", "tier": "B",
     "angle": "Regional carrier, terminal manager reachable directly."},
    {"name": "Sutton Transport — MN Terminal", "city": "Twin Cities metro", "address": "",
     "ptype": "Regional LTL terminal", "est_cabs": "10–25 (est.)", "tier": "B",
     "angle": "Regional Midwest LTL — decision at terminal level, not corporate."},
    {"name": "Hotline Freight — MN Terminal", "city": "Twin Cities metro", "address": "",
     "ptype": "Regional LTL terminal", "est_cabs": "10–20 (est.)", "tier": "B",
     "angle": "Small regional network; terminal manager owns the yard budget."},
    # Tier C — anchors & owner-operator networks (bigger, slower, but huge upside)
    {"name": "Bay & Bay Transportation", "city": "Eagan", "address": "Eagan, MN (HQ yard)",
     "ptype": "Mid-size carrier HQ", "est_cabs": "50+ at HQ yard", "tier": "C",
     "angle": "Confirmed Eagan HQ. Mid-size = real ops leadership on site; pitch a 10-cab pilot pod."},
    {"name": "Dart Transit", "city": "Eagan", "address": "Eagan, MN (HQ yard)",
     "ptype": "Owner-operator network", "est_cabs": "100+ O/O cabs through yard", "tier": "C",
     "angle": "GOLD: owner-operators pay for their OWN cabs. Set up a yard-day table — sell $175 cleans direct, no contract needed."},
    {"name": "Koch Trucking", "city": "Minneapolis", "address": "Minneapolis, MN (HQ yard)",
     "ptype": "Large carrier HQ", "est_cabs": "100+ (large)", "tier": "C",
     "angle": "Big fleet — start with one division (e.g. specialized) and their yard on a weekly slot."},
    {"name": "Transport America (TFI)", "city": "Eagan", "address": "Eagan, MN (HQ yard)",
     "ptype": "Large carrier HQ", "est_cabs": "100+ (large)", "tier": "C",
     "angle": "Corporate, but yard facilities manager can approve vendor trials."},
    {"name": "Long Haul Trucking", "city": "Albertville (NW metro)", "address": "Albertville, MN",
     "ptype": "Flatbed carrier", "est_cabs": "50+ (est.)", "tier": "C",
     "angle": "Flatbed cabs get filthy — dramatic before/after photos. 35 min NW, batch with Coon Rapids run."},
]


def build_gear_pdf() -> bytes:
    from reportlab.lib.colors import HexColor
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen.canvas import Canvas

    AZ, GD, INK, MUT = HexColor("#123B5C"), HexColor("#C9A227"), HexColor("#1C2430"), HexColor("#5B6472")
    AMZ, HF = HexColor("#B45309"), HexColor("#B91C1C")
    W, H = letter
    buf = io.BytesIO()
    c = Canvas(buf, pagesize=letter)
    total = round(sum(i["est"] for g in GEAR for i in g["items"]), 2)

    def header(first=False):
        c.setFillColor(AZ)
        c.rect(0, H - (110 if first else 60), W, 110 if first else 60, stroke=0, fill=1)
        c.setFillColor(HexColor("#FFFFFF"))
        c.setFont("Helvetica-Bold", 20 if first else 13)
        c.drawString(54, H - (44 if first else 38), "ORISEI TRUCK CLEANING")
        c.setFillColor(GD)
        c.setFont("Helvetica-Bold", 12 if first else 9)
        c.drawString(54, H - (66 if first else 52), "CREW GEAR & SUPPLY KIT — SOURCING LIST")
        if first:
            c.setFillColor(HexColor("#B9C6D4"))
            c.setFont("Helvetica", 8.5)
            c.drawString(54, H - 84, "Battery-powered field kit for one 2-person crew · sourced from Amazon & Harbor Freight")
            c.drawString(54, H - 96, "Links open the store search for the exact item · prices are live-market estimates")
            c.setFillColor(GD)
            c.setFont("Helvetica-Bold", 15)
            c.drawRightString(W - 54, H - 52, f"~${total:,.0f} / crew kit")
        c.setFillColor(MUT)
        c.setFont("Helvetica", 7)
        c.drawRightString(W - 54, 30, "Orisei Freight Solutions LLC · Twin Cities, MN · (763) 443-4459 · oliver@oriseifreightsolutions.com")

    header(first=True)
    y = H - 140
    for g in GEAR:
        need = 30 + len(g["items"]) * 58
        if y - need < 60 and y < H - 200:
            c.showPage()
            header()
            y = H - 90
        c.setFillColor(GD)
        c.rect(54, y - 4, W - 108, 20, stroke=0, fill=1)
        c.setFillColor(AZ)
        c.setFont("Helvetica-Bold", 10.5)
        c.drawString(62, y + 1, g["cat"].upper())
        y -= 26
        for i in g["items"]:
            if y < 96:
                c.showPage()
                header()
                y = H - 90
            c.setFillColor(INK)
            c.setFont("Helvetica-Bold", 9.5)
            c.drawString(62, y, i["name"])
            c.setFillColor(HexColor("#0E7A4E"))
            c.setFont("Helvetica-Bold", 10)
            c.drawRightString(W - 62, y, f"~${i['est']:,.0f}")
            y -= 12
            c.setFillColor(AMZ if i["store"] == "Amazon" else HF)
            c.setFont("Helvetica-Bold", 7.5)
            c.drawString(62, y, i["store"].upper())
            c.setFillColor(MUT)
            c.setFont("Helvetica", 8)
            c.drawString(62 + (48 if i["store"] == "Amazon" else 84), y, i["why"][:104])
            y -= 11
            c.setFillColor(HexColor("#2563EB"))
            c.setFont("Helvetica", 7)
            c.drawString(62, y, i["url"])
            c.linkURL(i["url"], (60, y - 2, W - 60, y + 8), relative=0)
            y -= 8
            c.setStrokeColor(HexColor("#E2E8F0"))
            c.setLineWidth(0.5)
            c.line(62, y, W - 62, y)
            y -= 14
        y -= 6
    if y < 120:
        c.showPage()
        header()
        y = H - 90
    c.setFillColor(AZ)
    c.rect(54, y - 34, W - 108, 34, stroke=0, fill=1)
    c.setFillColor(HexColor("#FFFFFF"))
    c.setFont("Helvetica-Bold", 11)
    c.drawString(62, y - 21, "FULL KIT ESTIMATE PER CREW")
    c.setFillColor(GD)
    c.setFont("Helvetica-Bold", 14)
    c.drawRightString(W - 62, y - 23, f"~${total:,.0f}")
    c.save()
    return buf.getvalue()


class GearSendIn(BaseModel):
    email: str = Field(..., min_length=5, max_length=200)
    note: str = Field("", max_length=500)


class LoginIn(BaseModel):
    pin: str = Field(..., pattern=r"^\d{4,6}$")


class ClockIn(BaseModel):
    action: str  # in | out
    lat: Optional[float] = None
    lng: Optional[float] = None


class TaskIn(BaseModel):
    task_id: str
    done: bool = True


class PingIn(BaseModel):
    lat: float
    lng: float


class UpdateIn(BaseModel):
    title: str = Field(..., min_length=2, max_length=140)
    body: str = Field("", max_length=2000)
    pinned: bool = False


class ExpenseIn(BaseModel):
    date: str = Field("", max_length=10)
    category: str = Field("supplies")
    vendor: str = Field("", max_length=120)
    desc: str = Field("", max_length=300)
    amount: float = Field(..., gt=0, le=1_000_000)


class VehicleIn(BaseModel):
    name: str = Field(..., min_length=2, max_length=80)
    plate: str = Field("", max_length=20)
    vtype: str = Field("van")  # van | truck | trailer
    status: str = Field("active")  # active | maintenance | idle
    assigned_tech_id: str = ""
    notes: str = Field("", max_length=300)


class BookingIn(BaseModel):
    company: str = Field(..., min_length=2, max_length=150)
    contact: str = Field("", max_length=100)
    phone: str = Field("", max_length=40)
    email: str = Field("", max_length=200)
    cabs: int = Field(1, ge=1, le=200)
    address: str = Field("", max_length=250)
    vehicle_location: str = Field("", max_length=250)
    preferred_date: str = Field("", max_length=10)
    services: List[str] = Field(default_factory=list)
    plan: str = Field("one_time", max_length=20)
    tier: str = Field("", max_length=20)
    heard_from: str = Field("", max_length=60)
    scent: str = Field("", max_length=60)
    notes: str = Field("", max_length=500)


class AutoAssignIn(BaseModel):
    date: str = Field("", max_length=10)


def _is_test_booking(b: dict) -> bool:
    """Suppress real alert emails for QA/test bookings (e.g. company 'TEST …')."""
    name = str(b.get("company", "")).strip().lower()
    email = str(b.get("email", "")).strip().lower()
    return (name.startswith(("test", "qa ", "ui_test")) or "_test" in name or "test_" in name
            or "@test." in email or email.endswith("@example.com") or email == "qa@test.com")


def _haversine_mi(lat1, lng1, lat2, lng2) -> float:
    r = 3958.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def build_truck_cleaning_crew_router(*, db, require_role: Callable) -> APIRouter:
    router = APIRouter(prefix="/truck-cleaning", tags=["truck-cleaning-crew"])
    guard = require_role("admin", "owner", "dispatcher")
    photos = AsyncIOMotorGridFSBucket(db, bucket_name="tc_photos")

    # ================= CREW AUTH =================
    async def _rate_limit(request: Request, scope: str = "login"):
        ip = request.client.host if request.client else "unknown"
        t = datetime.now(timezone.utc)
        key = f"tc-{scope}:{ip}"
        doc = await db.tc_login_attempts.find_one({"_id": key})
        if doc and doc["expires_at"] > t.isoformat():
            if doc["count"] >= 10:
                raise HTTPException(429, "Too many attempts — wait a minute and try again")
            await db.tc_login_attempts.update_one({"_id": key}, {"$inc": {"count": 1}})
        else:
            await db.tc_login_attempts.replace_one(
                {"_id": key}, {"_id": key, "count": 1,
                               "expires_at": (t + timedelta(minutes=1)).isoformat()}, upsert=True)

    @router.post("/crew/login")
    async def crew_login(payload: LoginIn, request: Request):
        await _rate_limit(request)
        t = datetime.now(timezone.utc)
        tech = await db.tc_techs.find_one({"pin_lookup": _pin_lookup(payload.pin), "active": True}, {"_id": 0})
        if not tech or (tech.get("locked_until") or "") > t.isoformat():
            raise HTTPException(401, "Invalid PIN")
        if not bcrypt.checkpw(payload.pin.encode(), tech["pin_hash"].encode()):
            fails = (tech.get("failed_attempts") or 0) + 1
            upd: Dict[str, Any] = {"failed_attempts": fails}
            if fails >= MAX_FAILURES:
                upd["locked_until"] = (t + timedelta(minutes=LOCK_MINUTES)).isoformat()
            await db.tc_techs.update_one({"tech_id": tech["tech_id"]}, {"$set": upd})
            raise HTTPException(401, "Invalid PIN")
        await db.tc_techs.update_one({"tech_id": tech["tech_id"]},
                                     {"$set": {"failed_attempts": 0}, "$unset": {"locked_until": ""}})
        raw = secrets.token_urlsafe(32)
        await db.tc_crew_sessions.insert_one({
            "_id": _token_digest(raw), "tech_id": tech["tech_id"], "created_at": _now(),
            "expires_at": (t + timedelta(hours=SESSION_HOURS)).isoformat(), "revoked_at": None})
        return {"token": raw, "crew": {"tech_id": tech["tech_id"], "name": tech["name"], "role": tech["role"]}}

    async def get_crew(request: Request) -> Dict[str, Any]:
        token = request.headers.get("X-Crew-Token", "")
        if not token:
            raise HTTPException(401, "Crew sign-in required")
        sess = await db.tc_crew_sessions.find_one({
            "_id": _token_digest(token), "revoked_at": None, "expires_at": {"$gt": _now()}})
        if not sess:
            raise HTTPException(401, "Session expired — sign in again")
        tech = await db.tc_techs.find_one({"tech_id": sess["tech_id"], "active": True},
                                          {"_id": 0, "pin_hash": 0, "pin_lookup": 0})
        if not tech:
            raise HTTPException(401, "Crew account disabled")
        return tech

    @router.post("/crew/logout")
    async def crew_logout(request: Request):
        token = request.headers.get("X-Crew-Token", "")
        if token:
            await db.tc_crew_sessions.update_one({"_id": _token_digest(token)},
                                                 {"$set": {"revoked_at": _now()}})
        return {"ok": True}

    # ------- admin PIN management -------
    @router.post("/crew-admin/{tech_id}/pin")
    async def issue_pin(tech_id: str, _=Depends(guard)):
        tech = await db.tc_techs.find_one({"tech_id": tech_id, "active": True})
        if not tech:
            raise HTTPException(404, "Tech not found")
        for _attempt in range(8):
            pin = f"{secrets.randbelow(900000) + 100000}"
            if len(set(pin)) < 3:
                continue
            if not await db.tc_techs.find_one({"pin_lookup": _pin_lookup(pin)}):
                break
        else:
            raise HTTPException(500, "Could not generate a unique PIN — retry")
        await db.tc_techs.update_one({"tech_id": tech_id}, {"$set": {
            "pin_hash": bcrypt.hashpw(pin.encode(), bcrypt.gensalt()).decode(),
            "pin_lookup": _pin_lookup(pin), "pin_set_at": _now(), "failed_attempts": 0},
            "$unset": {"locked_until": ""}})
        await db.tc_crew_sessions.update_many({"tech_id": tech_id, "revoked_at": None},
                                              {"$set": {"revoked_at": _now()}})
        return {"ok": True, "tech_id": tech_id, "pin": pin,
                "note": "Shown once — text it to the crew member now."}

    # ================= CLOCK IN/OUT =================
    async def _open_shift(tech_id: str):
        return await db.tc_timeclock.find_one({"tech_id": tech_id, "out_at": None}, {"_id": 0})

    @router.post("/crew/clock")
    async def clock(payload: ClockIn, crew=Depends(get_crew)):
        open_shift = await _open_shift(crew["tech_id"])
        if payload.action == "in":
            if open_shift:
                raise HTTPException(400, "Already clocked in")
            entry = {"entry_id": f"TCK-{uuid.uuid4().hex[:8].upper()}", "tech_id": crew["tech_id"],
                     "tech_name": crew["name"], "date": _today(), "in_at": _now(), "out_at": None,
                     "hours": None, "in_loc": {"lat": payload.lat, "lng": payload.lng}}
            await db.tc_timeclock.insert_one(dict(entry))
            return {"ok": True, "clocked_in": True, "entry": entry}
        if payload.action == "out":
            if not open_shift:
                raise HTTPException(400, "Not clocked in")
            t_in = datetime.fromisoformat(open_shift["in_at"])
            hours = round((datetime.now(timezone.utc) - t_in).total_seconds() / 3600, 2)
            await db.tc_timeclock.update_one({"entry_id": open_shift["entry_id"]}, {"$set": {
                "out_at": _now(), "hours": hours, "out_loc": {"lat": payload.lat, "lng": payload.lng}}})
            return {"ok": True, "clocked_in": False, "hours": hours}
        raise HTTPException(400, "action must be in|out")

    @router.get("/crew/me")
    async def crew_me(crew=Depends(get_crew)):
        shift = await _open_shift(crew["tech_id"])
        return {"crew": crew, "clocked_in": bool(shift), "shift": shift}

    # ================= TODAY'S SCHEDULE + CHECKLISTS =================
    async def _job_view(j: Dict[str, Any], client_map: Dict[str, Any]) -> Dict[str, Any]:
        c = client_map.get(j["client_id"], {})
        if not j.get("checklist"):
            checklist = _build_checklist(j.get("upsells", []))
            await db.tc_jobs.update_one({"job_id": j["job_id"]}, {"$set": {"checklist": checklist}})
            j["checklist"] = checklist
        done = sum(1 for t in j["checklist"] if t["done"])
        photos_meta = await db["tc_photos.files"].find({"metadata.job_id": j["job_id"]}).to_list(20)
        return {"job_id": j["job_id"], "company": c.get("company", "?"),
                "address": j.get("address") or c.get("address") or c.get("notes", ""),
                "vehicle_location": j.get("vehicle_location", ""),
                "contact": c.get("contact", ""), "phone": c.get("phone", ""),
                "date": j["date"], "window": j.get("window", ""), "cabs": j["cabs"],
                "status": j["status"], "upsells": j.get("upsells", []),
                "upsell_labels": [UPSELL_LABEL.get(u, u) for u in j.get("upsells", [])],
                "est_minutes": j["cabs"] * 45 + len(j.get("upsells", [])) * 12,
                "checklist": j["checklist"], "progress_pct": round(done / max(len(j["checklist"]), 1) * 100),
                "photos_before": sum(1 for p in photos_meta if (p.get("metadata") or {}).get("kind") == "before"),
                "photos_after": sum(1 for p in photos_meta if (p.get("metadata") or {}).get("kind") == "after"),
                "notes": j.get("notes", ""), "tech_ids": j.get("tech_ids", [])}

    @router.get("/crew/today")
    async def crew_today(crew=Depends(get_crew)):
        today = _today()
        jobs = await db.tc_jobs.find({"date": today}, {"_id": 0}).to_list(200)
        clients = await db.tc_clients.find({}, {"_id": 0}).to_list(500)
        cmap = {c["client_id"]: c for c in clients}
        mine, open_jobs = [], []
        for j in jobs:
            v = await _job_view(j, cmap)
            if crew["tech_id"] in (j.get("tech_ids") or []):
                mine.append(v)
            elif j["status"] == "scheduled" and not j.get("tech_ids"):
                open_jobs.append(v)
        mine.sort(key=lambda x: x.get("window") or "99")
        return {"date": today, "my_jobs": mine, "open_jobs": open_jobs}

    @router.get("/crew/tomorrow")
    async def crew_tomorrow(crew=Depends(get_crew)):
        tomorrow = (datetime.now(timezone.utc).date() + timedelta(days=1)).isoformat()
        jobs = await db.tc_jobs.find({"date": tomorrow, "status": "scheduled"}, {"_id": 0}).to_list(200)
        clients = await db.tc_clients.find({}, {"_id": 0}).to_list(500)
        cmap = {c["client_id"]: c for c in clients}
        mine = [await _job_view(j, cmap) for j in jobs if crew["tech_id"] in (j.get("tech_ids") or [])]
        open_jobs = [await _job_view(j, cmap) for j in jobs if not j.get("tech_ids")]
        mine.sort(key=lambda x: x.get("window") or "99")
        total_min = sum(j["est_minutes"] for j in mine)
        return {"date": tomorrow, "my_jobs": mine, "open_jobs": open_jobs,
                "total_cabs": sum(j["cabs"] for j in mine), "total_minutes": total_min}

    @router.post("/crew/jobs/{job_id}/claim")
    async def claim_job(job_id: str, crew=Depends(get_crew)):
        j = await db.tc_jobs.find_one({"job_id": job_id}, {"_id": 0})
        if not j:
            raise HTTPException(404, "Job not found")
        if crew["tech_id"] in (j.get("tech_ids") or []):
            return {"ok": True}
        await db.tc_jobs.update_one({"job_id": job_id}, {"$addToSet": {"tech_ids": crew["tech_id"]},
                                                         "$set": {"assigned_at": _now()}})
        return {"ok": True}

    @router.post("/crew/jobs/{job_id}/task")
    async def toggle_task(job_id: str, payload: TaskIn, crew=Depends(get_crew)):
        j = await db.tc_jobs.find_one({"job_id": job_id}, {"_id": 0})
        if not j or not j.get("checklist"):
            raise HTTPException(404, "Job or checklist not found")
        found = False
        for t in j["checklist"]:
            if t["id"] == payload.task_id:
                t["done"] = payload.done
                t["done_at"] = _now() if payload.done else None
                t["done_by"] = crew["name"] if payload.done else None
                found = True
        if not found:
            raise HTTPException(404, "Task not found")
        await db.tc_jobs.update_one({"job_id": job_id}, {"$set": {"checklist": j["checklist"]}})
        done = sum(1 for t in j["checklist"] if t["done"])
        return {"ok": True, "progress_pct": round(done / len(j["checklist"]) * 100)}

    # crew photo upload (same GridFS bucket + rules as admin)
    @router.post("/crew/jobs/{job_id}/photos")
    async def crew_photo(job_id: str, file: UploadFile = File(...), kind: str = Form("before"),
                         crew=Depends(get_crew)):
        job = await db.tc_jobs.find_one({"job_id": job_id}, {"_id": 0})
        if not job:
            raise HTTPException(404, "Job not found")
        if kind not in ("before", "after"):
            raise HTTPException(400, "kind must be before|after")
        if await db["tc_photos.files"].count_documents({"metadata.job_id": job_id}) >= 8:
            raise HTTPException(400, "Max 8 photos per job")
        raw = await file.read()
        try:
            im = Image.open(io.BytesIO(raw)).convert("RGB")
        except Exception:
            raise HTTPException(400, "Not a valid image")
        im.thumbnail((1280, 1280))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=82)
        fid = await photos.upload_from_stream(f"{job_id}_{kind}.jpg", buf.getvalue(), metadata={
            "job_id": job_id, "kind": kind, "caption": f"by {crew['name']}",
            "size_bytes": buf.getbuffer().nbytes, "uploaded_at": _now()})
        return {"ok": True, "photo_id": str(fid), "kind": kind}

    @router.get("/crew/jobs/{job_id}/photo/{photo_id}")
    async def crew_photo_view(job_id: str, photo_id: str, crew=Depends(get_crew)):
        from fastapi.responses import Response as Resp
        f = await db["tc_photos.files"].find_one({"_id": ObjectId(photo_id), "metadata.job_id": job_id})
        if not f:
            raise HTTPException(404, "Photo not found")
        stream = await photos.open_download_stream(ObjectId(photo_id))
        return Resp(await stream.read(), media_type="image/jpeg")

    @router.post("/crew/jobs/{job_id}/complete")
    async def complete_job(job_id: str, crew=Depends(get_crew)):
        j = await db.tc_jobs.find_one({"job_id": job_id}, {"_id": 0})
        if not j:
            raise HTTPException(404, "Job not found")
        checklist = j.get("checklist") or []
        blockers = [f"Check off: {t['label']}" for t in checklist if t["kind"] == "core" and not t["done"]]
        blockers += [f"Upsell not checked: {t['label']}" for t in checklist if t["kind"] == "upsell" and not t["done"]]
        pm = await db["tc_photos.files"].find({"metadata.job_id": job_id}).to_list(20)
        before = sum(1 for p in pm if (p.get("metadata") or {}).get("kind") == "before")
        after = sum(1 for p in pm if (p.get("metadata") or {}).get("kind") == "after")
        if before < 1:
            blockers.append("Upload at least 1 BEFORE photo")
        if after < 1:
            blockers.append("Upload at least 1 AFTER photo")
        if blockers:
            return {"ok": False, "blockers": blockers}
        proof_token = j.get("proof_token") or uuid.uuid4().hex
        await db.tc_jobs.update_one({"job_id": job_id}, {"$set": {
            "status": "completed", "completed_at": _now(), "completed_by": crew["name"],
            "completed_by_tech_id": crew["tech_id"], "proof_token": proof_token}})
        from routes.truck_cleaning_biz import auto_invoice_for_job
        inv = await auto_invoice_for_job(db, job_id)
        from routes.truck_cleaning_field import _public_base
        proof_url = f"{_public_base()}/tc/proof/{proof_token}"
        import asyncio as _aio

        async def _auto_proof():
            try:
                client = await db.tc_clients.find_one({"client_id": j["client_id"]}, {"_id": 0}) or {}
                # SMS the proof link (queued if Twilio unconfigured)
                if client.get("phone"):
                    from routes.truck_cleaning_field import _send_sms
                    await _send_sms(db, client["phone"],
                                    f"Orisei Truck Cleaning: your {j['cabs']}-cab job is done! "
                                    f"Before/after photo proof: {proof_url}",
                                    job_id=job_id, kind="proof_auto")
                # Email the proof gallery (recorded if Resend unconfigured)
                to = (client.get("email") or "").strip()
                if to:
                    from routes.connections import get_connection_credentials
                    creds = await get_connection_credentials(db, "resend") or {}
                    subject = f"Photo proof — {j.get('company', client.get('company', ''))} cab cleaning {j['date']}"
                    html = (f"<div style='font-family:Arial,sans-serif;max-width:600px;margin:0 auto'>"
                            f"<div style='background:#0D1117;padding:18px 24px;border-bottom:4px solid #F59E0B'>"
                            f"<span style='color:#F59E0B;font-weight:800;letter-spacing:2px'>ORISEI TRUCK CLEANING</span></div>"
                            f"<div style='padding:22px 24px;border:1px solid #E2E8F0;border-top:none'>"
                            f"<p>Job complete — {j['cabs']} cab(s) cleaned to the 45-minute showroom spec by {crew['name']}'s crew.</p>"
                            f"<p style='text-align:center;margin:20px 0'><a href='{proof_url}' "
                            f"style='background:#F59E0B;color:#0D1117;font-weight:800;padding:12px 26px;"
                            f"border-radius:999px;text-decoration:none'>VIEW BEFORE / AFTER PHOTOS</a></p>"
                            f"<p>— Orisei Truck Cleaning Solutions · (763) 443-4459</p></div></div>")
                    sent = False
                    if creds.get("api_key"):
                        try:
                            import resend as _r
                            _r.api_key = creds["api_key"]
                            _r.Emails.send({"from": creds.get("from_email") or
                                            "Orisei Truck Cleaning <oliver@oriseifreightsolutions.com>",
                                            "to": [to], "subject": subject, "html": html})
                            sent = True
                        except Exception:
                            pass
                    await db.outbound_emails.insert_one({
                        "to": to, "subject": subject, "html": html,
                        "status": "sent" if sent else "recorded_no_key",
                        "kind": "tc_proof_auto", "job_id": job_id, "at": _now()})
                    await db.tc_jobs.update_one({"job_id": job_id}, {"$set": {
                        "proof_sent_at": _now(), "proof_sent_to": to,
                        "proof_send_status": "sent" if sent else "recorded_no_key"}})
            except Exception:
                pass

        async def _ai_note():
            try:
                from emergentintegrations.llm.chat import LlmChat, UserMessage
                key = os.environ.get("EMERGENT_LLM_KEY")
                if not key:
                    return
                chat = LlmChat(api_key=key, session_id=f"tc-qc-{job_id}",
                               system_message="You are a quality coach for a truck cab cleaning crew. "
                                              "In ONE short encouraging sentence, note anything to watch next time "
                                              "based on the job data. No preamble.").with_model(
                    "anthropic", "claude-sonnet-4-5-20250929")
                dur = [t for t in checklist if t.get("done_at")]
                msg = (f"Job {job_id}: {j['cabs']} cabs, upsells {j.get('upsells', [])}, "
                       f"{before} before / {after} after photos, {len(dur)}/{len(checklist)} tasks checked, "
                       f"completed by {crew['name']}.")
                note = str(await chat.send_message(UserMessage(text=msg)))
                await db.tc_jobs.update_one({"job_id": job_id}, {"$set": {"ai_quality_note": note[:400]}})
            except Exception:
                pass
        _aio.create_task(_auto_proof())
        _aio.create_task(_ai_note())
        return {"ok": True, "status": "completed", "proof_url": proof_url,
                "invoice_id": (inv or {}).get("invoice_id"),
                "message": "Job complete — client gets their photo-proof link and a draft invoice is queued for billing. Nice work."}

    # ================= GEO PINGS + LIVE MAP =================
    @router.post("/crew/ping")
    async def crew_ping(payload: PingIn, crew=Depends(get_crew)):
        await db.tc_crew_pings.replace_one({"tech_id": crew["tech_id"]}, {
            "tech_id": crew["tech_id"], "name": crew["name"], "lat": payload.lat,
            "lng": payload.lng, "at": _now()}, upsert=True)
        return {"ok": True}

    @router.get("/crew/guide")
    async def crew_guide(crew=Depends(get_crew)):
        return CLEANING_GUIDE

    @router.get("/crew/updates")
    async def crew_updates(crew=Depends(get_crew)):
        rows = await db.tc_updates.find({}, {"_id": 0}).sort([("pinned", -1), ("created_at", -1)]).to_list(30)
        return {"updates": rows}

    @router.get("/crew-live")
    async def crew_live(_=Depends(guard)):
        techs = await db.tc_techs.find({"active": True}, {"_id": 0, "pin_hash": 0, "pin_lookup": 0}).to_list(100)
        pings = {p["tech_id"]: p for p in await db.tc_crew_pings.find({}, {"_id": 0}).to_list(100)}
        open_shifts = {s["tech_id"]: s for s in
                       await db.tc_timeclock.find({"out_at": None}, {"_id": 0}).to_list(100)}
        today = _today()
        jobs_today = await db.tc_jobs.find({"date": today}, {"_id": 0, "job_id": 1, "tech_ids": 1,
                                                             "status": 1, "client_id": 1}).to_list(200)
        rows = []
        for t in techs:
            my_jobs = [j for j in jobs_today if t["tech_id"] in (j.get("tech_ids") or [])]
            rows.append({"tech_id": t["tech_id"], "name": t["name"], "role": t["role"],
                         "has_pin": bool(t.get("pin_set_at")),
                         "clocked_in": t["tech_id"] in open_shifts,
                         "in_at": (open_shifts.get(t["tech_id"]) or {}).get("in_at"),
                         "ping": pings.get(t["tech_id"]),
                         "jobs_today": len(my_jobs),
                         "jobs_done_today": sum(1 for j in my_jobs if j["status"] in ("completed", "paid"))})
        return {"crews": rows, "clocked_in": sum(1 for r in rows if r["clocked_in"]),
                "date": today}

    @router.get("/timesheets")
    async def timesheets(start: str = "", days: int = 7, _=Depends(guard)):
        try:
            d0 = datetime.strptime(start, "%Y-%m-%d").date() if start \
                else datetime.now(timezone.utc).date() - timedelta(days=6)
        except ValueError:
            raise HTTPException(400, "start must be YYYY-MM-DD")
        dates = [(d0 + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(max(1, min(days, 31)))]
        rows = await db.tc_timeclock.find({"date": {"$in": dates}}, {"_id": 0}).sort("in_at", -1).to_list(500)
        techs = await db.tc_techs.find({"active": True}, {"_id": 0, "tech_id": 1, "hourly_rate": 1}).to_list(100)
        rate = {t["tech_id"]: t.get("hourly_rate", 25) for t in techs}
        total_h = round(sum(r.get("hours") or 0 for r in rows), 2)
        total_cost = round(sum((r.get("hours") or 0) * rate.get(r["tech_id"], 25) for r in rows), 2)
        return {"entries": rows, "total_hours": total_h, "labor_cost": total_cost, "dates": dates}

    # ================= CREW JOB ROUTER (one-tap dispatch) =================
    @router.post("/router/auto-assign")
    async def auto_assign(payload: AutoAssignIn, _=Depends(guard)):
        date = payload.date or _today()
        techs = await db.tc_techs.find({"active": True}, {"_id": 0, "pin_hash": 0, "pin_lookup": 0}).to_list(100)
        if not techs:
            raise HTTPException(400, "No active crews to assign")
        return await _route_date(date)

    async def _route_date(date: str):
        jobs = await db.tc_jobs.find({"date": date}, {"_id": 0}).to_list(300)
        unassigned = [j for j in jobs if j["status"] == "scheduled" and not j.get("tech_ids")]
        techs = await db.tc_techs.find({"active": True}, {"_id": 0, "pin_hash": 0, "pin_lookup": 0}).to_list(100)
        if not techs:
            return {"ok": False, "date": date, "assigned": [], "message": "No active crews in the system yet."}
        if not unassigned:
            return {"ok": True, "date": date, "assigned": [], "message": "Nothing to route — every job already has a crew."}
        pings = {p["tech_id"]: p for p in await db.tc_crew_pings.find({}, {"_id": 0}).to_list(100)}
        on_clock = {s["tech_id"] for s in await db.tc_timeclock.find({"out_at": None}, {"_id": 0, "tech_id": 1}).to_list(100)}
        clients = {c["client_id"]: c for c in await db.tc_clients.find({}, {"_id": 0}).to_list(500)}

        def job_minutes(j):
            return j["cabs"] * 45 + len(j.get("upsells", [])) * 12

        load = {t["tech_id"]: 0 for t in techs}
        for j in jobs:
            for tid in (j.get("tech_ids") or []):
                if tid in load:
                    load[tid] += job_minutes(j)

        # lazy one-time yard geocode — prefer the structured address field, fall back to notes
        from routes.routing_svc import _osm_geocode
        for j in unassigned:
            c = clients.get(j["client_id"]) or {}
            if c and c.get("yard_lat") is None and not c.get("yard_geo_tried"):
                addr = (c.get("address") or "").strip()[:120] or (c.get("notes") or "").split("\n")[0].strip()[:120]
                coord = await _osm_geocode(addr) if len(addr) > 8 else None
                upd = {"yard_geo_tried": True}
                if coord:
                    upd.update({"yard_lat": coord.lat, "yard_lng": coord.lng})
                await db.tc_clients.update_one({"client_id": c["client_id"]}, {"$set": upd})
                c.update(upd)

        results = []
        for j in sorted(unassigned, key=job_minutes, reverse=True):
            c = clients.get(j["client_id"]) or {}
            best, best_score = None, 1e12
            for t in techs:
                score = load[t["tech_id"]]
                if t["tech_id"] not in on_clock:
                    score += 90  # prefer crews already on the clock
                p = pings.get(t["tech_id"])
                if c.get("yard_lat") is not None:
                    if p:
                        score += _haversine_mi(p["lat"], p["lng"], c["yard_lat"], c["yard_lng"]) * 4
                    else:
                        score += 60  # unknown location — prefer a crew we can place near the yard
                if score < best_score:
                    best, best_score = t, score
            load[best["tech_id"]] += job_minutes(j)
            dist = None
            p = pings.get(best["tech_id"])
            if p and c.get("yard_lat") is not None:
                dist = round(_haversine_mi(p["lat"], p["lng"], c["yard_lat"], c["yard_lng"]), 1)
            await db.tc_jobs.update_one({"job_id": j["job_id"]}, {"$set": {
                "tech_ids": [best["tech_id"]], "assigned_at": _now(), "auto_assigned": True}})
            results.append({"job_id": j["job_id"], "company": c.get("company", j.get("company", "?")),
                            "cabs": j["cabs"], "tech_id": best["tech_id"], "tech_name": best["name"],
                            "distance_mi": dist, "est_minutes": job_minutes(j)})
        crews_used = len({r["tech_id"] for r in results})
        return {"ok": True, "date": date, "assigned": results,
                "message": f"{len(results)} job(s) routed across {crews_used} crew(s) — "
                           f"balanced by workload{', yard distance' if any(r['distance_mi'] is not None for r in results) else ''} and clock status."}

    # ================= PAYROLL =================
    async def _payroll_data(start: str, days: int):
        try:
            d0 = datetime.strptime(start, "%Y-%m-%d").date() if start \
                else datetime.now(timezone.utc).date() - timedelta(days=6)
        except ValueError:
            raise HTTPException(400, "start must be YYYY-MM-DD")
        dates = [(d0 + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(max(1, min(days, 31)))]
        entries = await db.tc_timeclock.find({"date": {"$in": dates}}, {"_id": 0}).to_list(1000)
        techs = await db.tc_techs.find({"active": True}, {"_id": 0, "pin_hash": 0, "pin_lookup": 0}).to_list(100)
        rows = []
        for t in techs:
            mine = [e for e in entries if e["tech_id"] == t["tech_id"]]
            hours = round(sum(e.get("hours") or 0 for e in mine), 2)
            rate = t.get("hourly_rate", 25)
            rows.append({"tech_id": t["tech_id"], "name": t["name"], "role": t["role"],
                         "hourly_rate": rate, "shifts": len(mine), "hours": hours,
                         "open_shift": any(e.get("out_at") is None for e in mine),
                         "gross_pay": round(hours * rate, 2)})
        rows.sort(key=lambda r: -r["gross_pay"])
        return {"period_start": dates[0], "period_end": dates[-1], "rows": rows,
                "total_hours": round(sum(r["hours"] for r in rows), 2),
                "total_gross": round(sum(r["gross_pay"] for r in rows), 2)}

    @router.get("/payroll")
    async def payroll(start: str = "", days: int = 7, _=Depends(guard)):
        return await _payroll_data(start, days)

    @router.get("/payroll.csv")
    async def payroll_csv(start: str = "", days: int = 7, _=Depends(guard)):
        from fastapi.responses import Response as Resp
        d = await _payroll_data(start, days)
        lines = [f"Orisei Truck Cleaning Payroll,{d['period_start']} to {d['period_end']}",
                 "Crew,Role,Hourly Rate,Shifts,Hours,Gross Pay,Open Shift"]
        for r in d["rows"]:
            lines.append(f"{r['name']},{r['role']},{r['hourly_rate']},{r['shifts']},{r['hours']},"
                         f"{r['gross_pay']},{'YES' if r['open_shift'] else ''}")
        lines.append(f"TOTAL,,,,{d['total_hours']},{d['total_gross']},")
        return Resp("\n".join(lines), media_type="text/csv", headers={
            "Content-Disposition": f'attachment; filename="Orisei-Payroll-{d["period_start"]}_{d["period_end"]}.csv"'})

    # ================= REVENUE TARGET TRACKER =================
    @router.get("/target")
    async def target_tracker(_=Depends(guard)):
        now = datetime.now(timezone.utc)
        month_start = now.strftime("%Y-%m-01")
        next_month = (now.replace(day=28) + timedelta(days=5)).strftime("%Y-%m-01")
        jobs = await db.tc_jobs.find({"date": {"$gte": month_start, "$lt": next_month}}, {"_id": 0}).to_list(3000)
        done = [j for j in jobs if j["status"] in ("completed", "paid")]
        booked = [j for j in jobs if j["status"] == "scheduled"]
        revenue_done = round(sum(j.get("price", 0) for j in done), 2)
        revenue_booked = round(sum(j.get("price", 0) for j in booked), 2)
        projected = round(revenue_done + revenue_booked, 2)
        rules = await db.tc_recurring.find({}, {"_id": 0}).to_list(200)
        run_rate = round(sum(r["monthly_value"] for r in rules), 2)
        target = 10000.0
        gap = round(max(0, target - projected), 2)
        cabs_done = sum(j["cabs"] for j in done)
        cabs_booked = sum(j["cabs"] for j in booked)
        cabs_target = 45
        # deal math: what closes the gap
        biweekly_yard = round(4 * 130 * 2.17, 2)   # 4-cab yard, bi-weekly
        weekly_yard = round(4 * 110 * 4.33, 2)     # 4-cab yard, weekly
        fleet_monthly = round(10 * 150 * 1, 2)     # 10-cab fleet, monthly
        days_in_month = ((datetime.strptime(next_month, "%Y-%m-01") - timedelta(days=1)).day)
        month_pct = round(now.day / days_in_month * 100)
        clients_active = len({j["client_id"] for j in jobs})
        return {"month": now.strftime("%B %Y"), "target": target,
                "revenue_done": revenue_done, "revenue_booked": revenue_booked,
                "projected": projected, "gap": gap,
                "progress_pct": round(min(projected / target, 1) * 100),
                "month_elapsed_pct": month_pct,
                "on_pace": projected >= target * now.day / days_in_month,
                "recurring_run_rate": run_rate, "recurring_rules": len(rules),
                "cabs_done": cabs_done, "cabs_booked": cabs_booked,
                "cabs_total": cabs_done + cabs_booked, "cabs_target": cabs_target,
                "cabs_gap": max(0, cabs_target - cabs_done - cabs_booked),
                "clients_active": clients_active,
                "gap_closers": [
                    {"label": "Bi-weekly yard lock-ins (4 cabs @ $130)", "value_mo": biweekly_yard,
                     "needed": math.ceil(gap / biweekly_yard) if gap else 0},
                    {"label": "Weekly yard lock-ins (4 cabs @ $110)", "value_mo": weekly_yard,
                     "needed": math.ceil(gap / weekly_yard) if gap else 0},
                    {"label": "Fleet accounts (10 cabs monthly @ $150)", "value_mo": fleet_monthly,
                     "needed": math.ceil(gap / fleet_monthly) if gap else 0},
                ]}

    # ================= CREW SCOREBOARD =================
    async def _scoreboard() -> Dict[str, Any]:
        since = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
        jobs = await db.tc_jobs.find({"status": {"$in": ["completed", "paid"]},
                                      "date": {"$gte": since}}, {"_id": 0}).to_list(2000)
        techs = await db.tc_techs.find({"active": True}, {"_id": 0, "pin_hash": 0, "pin_lookup": 0}).to_list(100)
        job_ids = [j["job_id"] for j in jobs]
        photo_counts: Dict[str, int] = {}
        if job_ids:
            async for f in db["tc_photos.files"].find({"metadata.job_id": {"$in": job_ids}},
                                                      {"metadata.job_id": 1}):
                jid = (f.get("metadata") or {}).get("job_id")
                photo_counts[jid] = photo_counts.get(jid, 0) + 1
        rows = []
        for t in techs:
            mine = [j for j in jobs if t["tech_id"] in (j.get("tech_ids") or [])
                    or j.get("completed_by_tech_id") == t["tech_id"]]
            done = len(mine)
            cabs = sum(j["cabs"] for j in mine)
            upsells = sum(len(j.get("upsells", [])) for j in mine)
            photos = sum(photo_counts.get(j["job_id"], 0) for j in mine)
            avg_photos = round(photos / done, 1) if done else 0
            photo_stars = min(5, round(avg_photos * 1.25)) if done else 0
            score = done * 10 + cabs * 2 + upsells * 3 + photo_stars * 4
            rows.append({"tech_id": t["tech_id"], "name": t["name"], "role": t["role"],
                         "jobs_done": done, "cabs": cabs, "upsells": upsells,
                         "avg_photos": avg_photos, "photo_stars": photo_stars, "score": score})
        rows.sort(key=lambda r: -r["score"])
        for i, r in enumerate(rows):
            r["rank"] = i + 1
        return {"since": since, "rows": rows}

    @router.get("/crew/scoreboard")
    async def crew_scoreboard(crew=Depends(get_crew)):
        data = await _scoreboard()
        data["me"] = crew["tech_id"]
        return data

    @router.get("/scoreboard")
    async def admin_scoreboard(_=Depends(guard)):
        return await _scoreboard()

    # ================= COMPANY UPDATES =================
    @router.post("/updates")
    async def add_update(payload: UpdateIn, _=Depends(guard)):
        doc = {**payload.model_dump(), "update_id": f"UPD-{uuid.uuid4().hex[:6].upper()}",
               "created_at": _now()}
        await db.tc_updates.insert_one(dict(doc))
        doc.pop("_id", None)
        return {"ok": True, "update": doc}

    @router.get("/updates")
    async def list_updates(_=Depends(guard)):
        rows = await db.tc_updates.find({}, {"_id": 0}).sort([("pinned", -1), ("created_at", -1)]).to_list(50)
        return {"updates": rows}

    @router.delete("/updates/{update_id}")
    async def del_update(update_id: str, _=Depends(guard)):
        r = await db.tc_updates.delete_one({"update_id": update_id})
        if r.deleted_count == 0:
            raise HTTPException(404, "Update not found")
        return {"ok": True}

    # ================= EXPENSES + P&L =================
    @router.post("/expenses")
    async def add_expense(payload: ExpenseIn, _=Depends(guard)):
        if payload.category not in EXPENSE_CATEGORIES:
            raise HTTPException(400, f"category must be one of {EXPENSE_CATEGORIES}")
        doc = {**payload.model_dump(), "expense_id": f"EXP-{uuid.uuid4().hex[:6].upper()}",
               "date": payload.date or _today(), "created_at": _now()}
        await db.tc_expenses.insert_one(dict(doc))
        doc.pop("_id", None)
        return {"ok": True, "expense": doc}

    @router.get("/expenses")
    async def list_expenses(_=Depends(guard)):
        rows = await db.tc_expenses.find({}, {"_id": 0}).sort("date", -1).to_list(500)
        return {"expenses": rows, "categories": EXPENSE_CATEGORIES,
                "total": round(sum(r["amount"] for r in rows), 2)}

    @router.delete("/expenses/{expense_id}")
    async def del_expense(expense_id: str, _=Depends(guard)):
        r = await db.tc_expenses.delete_one({"expense_id": expense_id})
        if r.deleted_count == 0:
            raise HTTPException(404, "Expense not found")
        return {"ok": True}

    @router.get("/pnl")
    async def pnl(_=Depends(guard)):
        jobs = await db.tc_jobs.find({"status": {"$in": ["completed", "paid"]}}, {"_id": 0}).to_list(2000)
        expenses = await db.tc_expenses.find({}, {"_id": 0}).to_list(2000)
        revenue = round(sum(j.get("price", 0) for j in jobs), 2)
        cogs = round(sum(j.get("cogs", 0) for j in jobs), 2)
        exp_total = round(sum(e["amount"] for e in expenses), 2)
        by_cat: Dict[str, float] = {}
        for e in expenses:
            by_cat[e["category"]] = round(by_cat.get(e["category"], 0) + e["amount"], 2)
        months: Dict[str, Dict[str, float]] = {}
        for j in jobs:
            mk = (j.get("date") or j.get("created_at", ""))[:7]
            if mk:
                months.setdefault(mk, {"revenue": 0, "expenses": 0})["revenue"] += j.get("price", 0)
        for e in expenses:
            mk = (e.get("date") or "")[:7]
            if mk:
                months.setdefault(mk, {"revenue": 0, "expenses": 0})["expenses"] += e["amount"]
        series = [{"month": k, "revenue": round(v["revenue"], 2), "expenses": round(v["expenses"], 2),
                   "net": round(v["revenue"] - v["expenses"], 2)}
                  for k, v in sorted(months.items())][-8:]
        return {"revenue": revenue, "cogs_estimate": cogs, "expenses_total": exp_total,
                "net": round(revenue - exp_total, 2), "by_category": by_cat, "series": series}

    # ================= COMPANY VEHICLES =================
    @router.post("/vehicles")
    async def add_vehicle(payload: VehicleIn, _=Depends(guard)):
        doc = {**payload.model_dump(), "vehicle_id": f"VEH-{uuid.uuid4().hex[:6].upper()}",
               "created_at": _now()}
        await db.tc_vehicles.insert_one(dict(doc))
        doc.pop("_id", None)
        return {"ok": True, "vehicle": doc}

    @router.get("/vehicles")
    async def list_vehicles(_=Depends(guard)):
        rows = await db.tc_vehicles.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
        techs = {t["tech_id"]: t["name"] for t in
                 await db.tc_techs.find({"active": True}, {"_id": 0, "tech_id": 1, "name": 1}).to_list(100)}
        pings = {p["tech_id"]: p for p in await db.tc_crew_pings.find({}, {"_id": 0}).to_list(100)}
        for r in rows:
            r["assigned_tech_name"] = techs.get(r.get("assigned_tech_id"), "")
            r["location"] = pings.get(r.get("assigned_tech_id"))
        return {"vehicles": rows}

    @router.put("/vehicles/{vehicle_id}")
    async def update_vehicle(vehicle_id: str, payload: VehicleIn, _=Depends(guard)):
        r = await db.tc_vehicles.update_one({"vehicle_id": vehicle_id},
                                            {"$set": {**payload.model_dump(), "updated_at": _now()}})
        if r.matched_count == 0:
            raise HTTPException(404, "Vehicle not found")
        return {"ok": True}

    @router.delete("/vehicles/{vehicle_id}")
    async def del_vehicle(vehicle_id: str, _=Depends(guard)):
        r = await db.tc_vehicles.delete_one({"vehicle_id": vehicle_id})
        if r.deleted_count == 0:
            raise HTTPException(404, "Vehicle not found")
        return {"ok": True}

    # ================= GEAR SOURCING =================
    @router.get("/gear")
    async def gear(_=Depends(guard)):
        total = round(sum(i["est"] for g in GEAR for i in g["items"]), 2)
        return {"gear": GEAR, "kit_total_est": total,
                "note": "Prices are live-market estimates — links open the store search for the exact item."}

    @router.get("/gear.pdf")
    async def gear_pdf(_=Depends(guard)):
        from fastapi.responses import Response as Resp
        return Resp(build_gear_pdf(), media_type="application/pdf", headers={
            "Content-Disposition": 'attachment; filename="Orisei-Crew-Gear-Kit.pdf"'})

    @router.post("/gear/send")
    async def gear_send(payload: GearSendIn, user=Depends(guard)):
        to = payload.email.strip()
        if "@" not in to:
            raise HTTPException(400, "Valid email required")
        total = round(sum(i["est"] for g in GEAR for i in g["items"]), 2)
        note_html = f"<p style='background:#FFF6DA;padding:10px 14px;border-radius:8px'>{payload.note}</p>" \
            if payload.note.strip() else ""
        subject = "Orisei Truck Cleaning — crew gear & supply kit to purchase"
        html = (f"<div style='font-family:Arial,Helvetica,sans-serif;max-width:620px;margin:0 auto;color:#1a202c'>"
                f"<div style='background:#123B5C;padding:18px 24px'><span style='color:#fff;font-weight:800;"
                f"letter-spacing:1px'>ORISEI TRUCK CLEANING</span><br>"
                f"<span style='color:#C9A227;font-size:12px;font-weight:700'>CREW GEAR &amp; SUPPLY KIT</span></div>"
                f"<div style='padding:22px 24px;border:1px solid #E2E8F0;border-top:none;font-size:14px'>"
                f"<p>Attached is the full sourcing list for one crew's field kit — battery vacuum &amp; shampooer, "
                f"blower, brushes (incl. steel wire), scents and supplies, with store links and prices "
                f"(<b>~${total:,.0f} per crew</b>).</p>{note_html}"
                f"<p>Every link in the PDF is clickable and opens the item at Amazon or Harbor Freight — "
                f"purchase straight from the list.</p>"
                f"<p>— Orisei Freight Solutions LLC · (763) 443-4459</p></div></div>")
        from routes.orisei_auto_digest import _resend_creds, _send_via_resend
        creds = await _resend_creds(db)
        res = await _send_via_resend(creds, to=to, subject=subject, html=html,
                                     pdf_bytes=build_gear_pdf(),
                                     pdf_filename="Orisei-Crew-Gear-Kit.pdf") \
            if creds else {"sent": False, "error": "no_resend_creds"}
        status = "sent" if res.get("sent") else "recorded_no_key"
        await db.outbound_emails.insert_one({
            "to": to, "subject": subject, "html": html, "status": status, "error": res.get("error"),
            "kind": "tc_gear_kit", "at": _now()})
        return {"ok": True, "sent": res.get("sent", False), "status": status, "to": to}

    # ================= YARD PROSPECT HIT LIST =================
    PROSPECT_STAGES = ["prospect", "pitched", "meeting", "pilot", "signed", "dead"]

    async def _ensure_prospects():
        if await db.tc_yard_prospects.count_documents({}) == 0:
            for i, p in enumerate(YARD_PROSPECTS):
                await db.tc_yard_prospects.insert_one({
                    **p, "prospect_id": f"YP-{i+1:02d}", "rank": i + 1, "stage": "prospect",
                    "contact": "", "phone": "", "email": "", "notes": "", "last_touch": None,
                    "created_at": _now()})

    @router.get("/yard-prospects")
    async def yard_prospects(_=Depends(guard)):
        await _ensure_prospects()
        rows = await db.tc_yard_prospects.find({}, {"_id": 0}).sort("rank", 1).to_list(100)
        return {"prospects": rows, "stages": PROSPECT_STAGES,
                "counts": {s: sum(1 for r in rows if r["stage"] == s) for s in PROSPECT_STAGES}}

    @router.patch("/yard-prospects/{prospect_id}")
    async def patch_prospect(prospect_id: str, payload: Dict[str, Any], _=Depends(guard)):
        upd = {}
        if "stage" in payload:
            if payload["stage"] not in PROSPECT_STAGES:
                raise HTTPException(400, f"stage must be one of {PROSPECT_STAGES}")
            upd["stage"] = payload["stage"]
            upd["last_touch"] = _now()
        for k in ("contact", "phone", "email", "notes"):
            if k in payload:
                upd[k] = str(payload[k])[:300]
        if not upd:
            raise HTTPException(400, "Nothing to update")
        r = await db.tc_yard_prospects.update_one({"prospect_id": prospect_id}, {"$set": upd})
        if r.matched_count == 0:
            raise HTTPException(404, "Prospect not found")
        fresh = await db.tc_yard_prospects.find_one({"prospect_id": prospect_id}, {"_id": 0})
        return {"ok": True, "prospect": fresh}

    # ================= MERCH STORE (crew size requests) =================
    MERCH_ITEMS = [
        {"id": "tee", "name": "Crew Tee (navy)", "img": "/merch/tee_women.jpg", "cuts": ["women", "unisex"]},
        {"id": "hoodie", "name": "Crew Hoodie (navy)", "img": "/merch/hoodie.jpg", "cuts": ["women", "unisex"]},
        {"id": "cap", "name": "Trucker Cap", "img": "/merch/cap.jpg", "cuts": ["one-size"]},
        {"id": "beanie", "name": "Cuffed Beanie", "img": "/merch/beanie.jpg", "cuts": ["one-size"]},
        {"id": "vest", "name": "ANSI Safety Vest", "img": "/merch/vest.jpg", "cuts": ["s-m", "l-xl", "2xl-3xl"]},
    ]
    MERCH_SIZES = ["XS", "S", "M", "L", "XL", "2XL", "3XL", "one-size"]

    @router.get("/crew/merch")
    async def crew_merch(crew=Depends(get_crew)):
        mine = await db.tc_merch_requests.find({"tech_id": crew["tech_id"]}, {"_id": 0}).sort("at", -1).to_list(50)
        return {"items": MERCH_ITEMS, "sizes": MERCH_SIZES, "my_requests": mine}

    @router.post("/crew/merch-request")
    async def merch_request(payload: Dict[str, Any], crew=Depends(get_crew)):
        item = str(payload.get("item", ""))
        if item not in {i["id"] for i in MERCH_ITEMS}:
            raise HTTPException(400, "Unknown item")
        size = str(payload.get("size", "M"))[:10]
        cut = str(payload.get("cut", ""))[:12]
        doc = {"request_id": f"MR-{uuid.uuid4().hex[:6].upper()}", "tech_id": crew["tech_id"],
               "tech_name": crew["name"], "item": item, "size": size, "cut": cut,
               "status": "requested", "at": _now()}
        await db.tc_merch_requests.insert_one(dict(doc))
        doc.pop("_id", None)
        return {"ok": True, "request": doc}

    @router.get("/merch-requests")
    async def merch_requests(_=Depends(guard)):
        rows = await db.tc_merch_requests.find({}, {"_id": 0}).sort("at", -1).to_list(300)
        return {"requests": rows}

    # ================= PROSPECT CALL LOG =================
    @router.post("/yard-prospects/{prospect_id}/call")
    async def log_call(prospect_id: str, payload: Dict[str, Any], _=Depends(guard)):
        p = await db.tc_yard_prospects.find_one({"prospect_id": prospect_id}, {"_id": 0})
        if not p:
            raise HTTPException(404, "Prospect not found")
        outcome = str(payload.get("outcome", "no_answer"))
        if outcome not in ("no_answer", "voicemail", "spoke", "meeting_set", "not_interested"):
            raise HTTPException(400, "Bad outcome")
        doc = {"call_id": f"CL-{uuid.uuid4().hex[:6].upper()}", "prospect_id": prospect_id,
               "outcome": outcome, "notes": str(payload.get("notes", ""))[:400],
               "callback_date": str(payload.get("callback_date", ""))[:10], "at": _now()}
        await db.tc_prospect_calls.insert_one(dict(doc))
        upd = {"last_touch": _now(), "last_call_outcome": outcome}
        if doc["callback_date"]:
            upd["callback_date"] = doc["callback_date"]
        if outcome == "meeting_set" and p["stage"] in ("prospect", "pitched"):
            upd["stage"] = "meeting"
        elif outcome in ("spoke", "voicemail") and p["stage"] == "prospect":
            upd["stage"] = "pitched"
        elif outcome == "not_interested":
            upd["stage"] = "dead"
        await db.tc_yard_prospects.update_one({"prospect_id": prospect_id}, {"$set": upd, "$inc": {"call_count": 1}})
        doc.pop("_id", None)
        return {"ok": True, "call": doc, "stage": upd.get("stage", p["stage"])}

    # ================= CONTRACT E-SIGN =================
    @router.post("/agreements")
    async def create_agreement(payload: Dict[str, Any], _=Depends(guard)):
        company = str(payload.get("company", "")).strip()
        if len(company) < 2:
            raise HTTPException(400, "Company required")
        freq = payload.get("frequency", "biweekly")
        cabs = max(1, min(int(payload.get("cabs", 4)), 200))
        rate = 110.0 if freq == "weekly" else 130.0
        doc = {"token": uuid.uuid4().hex, "company": company,
               "contact": str(payload.get("contact", ""))[:100], "email": str(payload.get("email", ""))[:200],
               "prospect_id": str(payload.get("prospect_id", ""))[:20],
               "frequency": freq, "cabs": cabs, "rate": rate,
               "monthly_value": round(cabs * rate * (4.33 if freq == "weekly" else 2.17), 2),
               "status": "sent", "created_at": _now(), "signed_at": None, "signature": None}
        await db.tc_agreements.insert_one(dict(doc))
        base = str(payload.get("base", "")).strip()[:200]
        if not base.startswith("http"):
            from routes.truck_cleaning_field import _public_base
            base = _public_base()
        sign_url = f"{base.rstrip('/')}/tc/sign/{doc['token']}"
        emailed = False
        if "@" in doc["email"]:
            try:
                from routes.orisei_auto_digest import _resend_creds, _send_via_resend
                subject = f"Orisei Truck Cleaning — your lock-in agreement for {company}"
                html = (f"<div style='font-family:Arial,Helvetica,sans-serif;max-width:560px;margin:0 auto;color:#0D1117'>"
                        f"<div style='background:#0D1117;padding:18px 24px;border-bottom:4px solid #F59E0B'>"
                        f"<span style='color:#F59E0B;font-size:11px;letter-spacing:3px;font-family:Courier,monospace'>ORISEI TRUCK CLEANING</span>"
                        f"<div style='color:#fff;font-size:19px;font-weight:800;margin-top:6px'>Your yard's lock-in agreement is ready</div></div>"
                        f"<div style='padding:20px 24px;border:1px solid #E2E8F0;border-top:none;font-size:14px;line-height:1.6'>"
                        f"<p>{company} — {cabs} cab(s), {'weekly' if freq == 'weekly' else 'bi-weekly'} at ${rate:.0f}/cab.</p>"
                        f"<p>Review and sign from your phone in under a minute:</p>"
                        f"<p><a href='{sign_url}' style='display:inline-block;background:#F59E0B;color:#0D1117;font-weight:800;"
                        f"padding:12px 26px;border-radius:999px;text-decoration:none'>REVIEW &amp; SIGN</a></p>"
                        f"<p style='font-size:12px;color:#64748B'>Questions? Call or text Oliver: (763) 443-4459</p></div></div>")
                creds = await _resend_creds(db)
                res = await _send_via_resend(creds, to=doc["email"], subject=subject, html=html,
                                             bcc="oliver@oriseifreightsolutions.com") if creds \
                    else {"sent": False, "error": "no_resend_creds"}
                emailed = bool(res.get("sent"))
                await db.outbound_emails.insert_one({
                    "to": doc["email"], "subject": subject, "html": html,
                    "status": "sent" if emailed else "recorded_no_key", "error": res.get("error"),
                    "kind": "tc_agreement_link", "company": company, "at": _now()})
            except Exception:  # noqa: BLE001
                pass
        return {"ok": True, "token": doc["token"], "sign_url": sign_url, "emailed": emailed}

    @router.get("/agreements")
    async def list_agreements(_=Depends(guard)):
        rows = await db.tc_agreements.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
        return {"agreements": rows}

    @router.get("/public/agreement/{token}")
    async def public_agreement(token: str):
        a = await db.tc_agreements.find_one({"token": token}, {"_id": 0})
        if not a:
            raise HTTPException(404, "Agreement not found")
        return a

    @router.post("/public/agreement/{token}/sign")
    async def sign_agreement(token: str, payload: Dict[str, Any], request: Request):
        a = await db.tc_agreements.find_one({"token": token}, {"_id": 0})
        if not a:
            raise HTTPException(404, "Agreement not found")
        if a["status"] == "signed":
            raise HTTPException(400, "Already signed")
        name = str(payload.get("name", "")).strip()
        if len(name) < 3:
            raise HTTPException(400, "Type your full legal name to sign")
        sig = {"name": name[:100], "title": str(payload.get("title", ""))[:100],
               "ip": request.client.host if request.client else "", "at": _now()}
        await db.tc_agreements.update_one({"token": token}, {"$set": {
            "status": "signed", "signed_at": _now(), "signature": sig}})
        client = await db.tc_clients.find_one({"company": a["company"]}, {"_id": 0})
        if not client:
            client = {"client_id": f"TCC-{uuid.uuid4().hex[:8].upper()}", "company": a["company"],
                      "contact": a.get("contact") or name, "phone": "", "email": a.get("email", ""),
                      "cabs": a["cabs"], "plan": "biweekly_sub" if a["frequency"] == "biweekly" else "fleet_sub",
                      "rate": a["rate"], "source": "esign", "notes": "Signed lock-in agreement",
                      "created_at": _now()}
            await db.tc_clients.insert_one(dict(client))
        await db.tc_recurring.replace_one({"client_id": client["client_id"]}, {
            "rule_id": f"REC-{uuid.uuid4().hex[:6].upper()}", "client_id": client["client_id"],
            "company": a["company"], "frequency": a["frequency"], "weekday": 1,
            "window": "08:00-10:00", "cabs": a["cabs"], "rate": a["rate"],
            "monthly_value": a["monthly_value"], "created_at": _now()}, upsert=True)
        if a.get("prospect_id"):
            await db.tc_yard_prospects.update_one({"prospect_id": a["prospect_id"]},
                                                  {"$set": {"stage": "signed", "last_touch": _now()}})
        try:
            from routes.orisei_auto_digest import _resend_creds, _send_via_resend
            subject = f"CONTRACT SIGNED — {a['company']} · {a['cabs']} cabs {a['frequency']} · ${a['monthly_value']:,.0f}/mo"
            html = (f"<div style='font-family:Arial,Helvetica,sans-serif;max-width:560px;margin:0 auto;color:#0D1117'>"
                    f"<div style='background:#059669;padding:18px 24px'>"
                    f"<span style='color:#fff;font-size:11px;letter-spacing:3px;font-family:Courier,monospace'>ORISEI TRUCK CLEANING</span>"
                    f"<div style='color:#fff;font-size:20px;font-weight:800;margin-top:6px'>You just won a yard.</div></div>"
                    f"<div style='padding:20px 24px;border:1px solid #E2E8F0;border-top:none;font-size:14px;line-height:1.7'>"
                    f"<p><b>{a['company']}</b> signed the {a['frequency']} lock-in.</p>"
                    f"<p>Signed by: <b>{sig['name']}</b>{(' — ' + sig['title']) if sig.get('title') else ''}<br>"
                    f"Cabs: <b>{a['cabs']}</b> · Rate: <b>${a['rate']:.0f}/cab</b> · Est. monthly: <b>${a['monthly_value']:,.0f}</b></p>"
                    f"<p>The client + recurring yard slot were created automatically. Call to confirm their first yard day.</p></div></div>")
            creds = await _resend_creds(db)
            for to in ("oliver@oriseifreightsolutions.com",):
                res = await _send_via_resend(creds, to=to, subject=subject, html=html) if creds \
                    else {"sent": False, "error": "no_resend_creds"}
                await db.outbound_emails.insert_one({
                    "to": to, "subject": subject, "html": html,
                    "status": "sent" if res.get("sent") else "recorded_no_key", "error": res.get("error"),
                    "kind": "tc_contract_won", "company": a["company"], "at": _now()})
        except Exception:  # noqa: BLE001
            pass
        return {"ok": True, "message": f"Signed — welcome aboard, {a['company']}! Your lock-in slot is reserved; "
                                       "we'll call to confirm your yard day."}

    # ================= PUBLIC GALLERY =================
    @router.get("/public/gallery")
    async def public_gallery():
        jobs = await db.tc_jobs.find({"status": {"$in": ["completed", "paid"]}},
                                     {"_id": 0, "job_id": 1, "company": 1, "date": 1}).sort("completed_at", -1).to_list(40)
        pairs = []
        for j in jobs:
            pm = await db["tc_photos.files"].find({"metadata.job_id": j["job_id"]}).to_list(10)
            before = next((str(p["_id"]) for p in pm if (p.get("metadata") or {}).get("kind") == "before"), None)
            after = next((str(p["_id"]) for p in pm if (p.get("metadata") or {}).get("kind") == "after"), None)
            if before and after:
                pairs.append({"job_id": j["job_id"], "before": before, "after": after, "date": j["date"]})
            if len(pairs) >= 6:
                break
        return {"pairs": pairs}

    @router.get("/public/photo/{photo_id}")
    async def public_photo(photo_id: str):
        from fastapi.responses import Response as Resp
        try:
            oid = ObjectId(photo_id)
        except Exception:
            raise HTTPException(404, "Not found")
        f = await db["tc_photos.files"].find_one({"_id": oid})
        if not f:
            raise HTTPException(404, "Not found")
        job = await db.tc_jobs.find_one({"job_id": (f.get("metadata") or {}).get("job_id"),
                                         "status": {"$in": ["completed", "paid"]}}, {"_id": 1})
        if not job:
            raise HTTPException(404, "Not found")
        stream = await photos.open_download_stream(oid)
        return Resp(await stream.read(), media_type="image/jpeg",
                    headers={"Cache-Control": "public, max-age=3600"})

    # ================= SENT EMAIL LOG =================
    @router.get("/emails")
    async def sent_emails(limit: int = 100, _=Depends(guard)):
        rows = await db.outbound_emails.find(
            {}, {"_id": 0, "to": 1, "subject": 1, "status": 1, "error": 1, "kind": 1,
                 "company": 1, "at": 1}).sort("at", -1).to_list(min(limit, 300))
        return {"emails": rows,
                "sent": sum(1 for r in rows if r.get("status") == "sent"),
                "failed": sum(1 for r in rows if r.get("status") != "sent")}

    # ================= JOBS MAP =================
    @router.get("/jobs-map")
    async def jobs_map(date: str = "", _=Depends(guard)):
        q: Dict[str, Any] = {"status": {"$in": ["scheduled", "in_progress"]}}
        if date:
            q["date"] = date
        jobs = await db.tc_jobs.find(q, {"_id": 0}).to_list(300)
        clients = {c["client_id"]: c async for c in db.tc_clients.find({}, {"_id": 0})}
        from routes.routing_svc import _osm_geocode
        pins, geocoded = [], 0
        for j in jobs:
            c = clients.get(j.get("client_id")) or {}
            lat, lng = c.get("yard_lat"), c.get("yard_lng")
            if lat is None and geocoded < 5 and not c.get("yard_geo_tried"):
                addr = (j.get("address") or c.get("address") or "").strip()[:120]
                coord = await _osm_geocode(addr) if len(addr) > 8 else None
                upd: Dict[str, Any] = {"yard_geo_tried": True}
                if coord:
                    upd.update({"yard_lat": coord.lat, "yard_lng": coord.lng})
                    lat, lng = coord.lat, coord.lng
                if c.get("client_id"):
                    await db.tc_clients.update_one({"client_id": c["client_id"]}, {"$set": upd})
                geocoded += 1
            if lat is None:
                continue
            pins.append({"job_id": j["job_id"], "company": j.get("company", ""), "date": j.get("date", ""),
                         "cabs": j.get("cabs", 1), "price": j.get("price", 0), "status": j.get("status", ""),
                         "address": j.get("address") or c.get("address") or "",
                         "vehicle_location": j.get("vehicle_location", ""), "lat": lat, "lng": lng})
        return {"pins": pins, "total_jobs": len(jobs)}

    # ================= PUBLIC BOOKING =================
    @router.get("/public/booking-qr.png")
    async def booking_qr(url: str = "", download: int = 0):
        from fastapi.responses import Response as Resp
        import qrcode
        target = url.strip()[:300]
        if not target.startswith("http"):
            target = (os.environ.get("PUBLIC_FRONTEND_URL") or "").rstrip("/") + "/wash"
        qr = qrcode.QRCode(box_size=10, border=2, error_correction=qrcode.constants.ERROR_CORRECT_H)
        qr.add_data(target)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#0D1117", back_color="white")
        b = io.BytesIO()
        img.save(b, format="PNG")
        headers = {"Cache-Control": "public, max-age=3600"}
        if download:
            headers["Content-Disposition"] = 'attachment; filename="Orisei_Booking_QR.png"'
        return Resp(b.getvalue(), media_type="image/png", headers=headers)

    @router.get("/public/site-info")
    async def site_info():
        return {"base_price": 175, "fleet_price": 150, "sub_price": 130, "car_detail_price": 150,
                "services": [{"id": u["id"], "label": u["label"], "price": u["price"],
                              "desc": u["desc"], "category": u["category"]} for u in UPSELL_META],
                "phone": "(763) 443-4459", "email": "oliver@oriseifreightsolutions.com",
                "scents": SCENT_MENU,
                "area": "Twin Cities metro — Minneapolis, St. Paul & every yard within 50 miles"}

    @router.post("/public/booking")
    async def public_booking(payload: BookingIn, request: Request):
        await _rate_limit(request, scope="booking")
        services = [s for s in payload.services if s in UPSELLS]
        plan = payload.plan if payload.plan in ("one_time", "fleet", "biweekly", "car_detail") else "one_time"
        doc = {**payload.model_dump(), "services": services, "plan": plan,
               "booking_id": f"BOOK-{uuid.uuid4().hex[:6].upper()}",
               "status": "new", "created_at": _now()}
        await db.tc_bookings.insert_one(dict(doc))
        # ---- AI autopilot: create client + job, pick the date, route a crew ----
        try:
            auto = await _booking_autopilot(doc)
            doc.update(auto)
        except Exception:  # noqa: BLE001
            pass
        try:
            if not _is_test_booking(doc):
                await _booking_alert_email(doc)
        except Exception:  # noqa: BLE001
            pass
        if doc.get("job_id"):
            when = doc.get("scheduled_date", "")
            crew = f" Crew {doc['tech_name']} is on it." if doc.get("tech_name") else ""
            return {"ok": True, "booking_id": doc["booking_id"], "scheduled_date": when,
                    "tech_name": doc.get("tech_name", ""),
                    "message": f"You're booked for {when}!{crew} We'll call to confirm the yard window."}
        return {"ok": True, "booking_id": doc["booking_id"],
                "message": "Request received — we'll confirm your slot within one business day."}

    async def _booking_autopilot(b: dict) -> dict:
        """Auto-convert a public booking: client + scheduled job + crew routing."""
        rates = {"one_time": 175.0, "fleet": 150.0, "biweekly": 130.0, "car_detail": 150.0}
        plans = {"one_time": "one_time", "fleet": "fleet_sub", "biweekly": "biweekly_sub", "car_detail": "car_detail"}
        rate = rates[b["plan"]]
        tier = ""
        if b["plan"] == "car_detail":
            from routes.truck_cleaning import CAR_TIERS
            tier = b.get("tier") if b.get("tier") in CAR_TIERS else "silver"
            rate = CAR_TIERS[tier]["price"]
            included = set(CAR_TIERS[tier]["includes"])
            b["services"] = [s for s in b.get("services", []) if s not in included]
        client = await db.tc_clients.find_one({"company": b["company"]}, {"_id": 0})
        if not client:
            client = {"client_id": f"TCC-{uuid.uuid4().hex[:8].upper()}", "company": b["company"],
                      "contact": b.get("contact", ""), "phone": b.get("phone", ""),
                      "email": b.get("email", ""), "cabs": b["cabs"], "plan": plans[b["plan"]],
                      "rate": rate, "source": "booking_autopilot", "notes": b.get("notes", ""),
                      "address": b.get("address", ""), "created_at": _now()}
            await db.tc_clients.insert_one(dict(client))
            client.pop("_id", None)
        elif b.get("address") and b["address"] != client.get("address"):
            await db.tc_clients.update_one({"client_id": client["client_id"]},
                                           {"$set": {"address": b["address"]}})
            client["address"] = b["address"]
        today = _today()
        date = b.get("preferred_date") or ""
        try:
            datetime.strptime(date, "%Y-%m-%d")
            if date < today:
                date = ""
        except ValueError:
            date = ""
        if not date:
            from zoneinfo import ZoneInfo
            now_ct = datetime.now(ZoneInfo("America/Chicago"))
            date = now_ct.date().isoformat() if now_ct.hour < 12 else (now_ct.date() + timedelta(days=1)).isoformat()
        scent_note = f" Scent: {b['scent']}." if b.get("scent") else ""
        veh_note = f" Vehicles: {b['vehicle_location']}." if b.get("vehicle_location") else ""
        tier_note = f"/{tier}" if tier else ""
        job = {"job_id": f"TCJ-{uuid.uuid4().hex[:8].upper()}", "client_id": client["client_id"],
               "company": client["company"], "date": date, "cabs": b["cabs"],
               "address": b.get("address", "") or client.get("address", ""),
               "vehicle_location": b.get("vehicle_location", ""), "tier": tier,
               "upsells": b.get("services", []),
               "price": round(b["cabs"] * rate + sum(UPSELLS.get(u, 0) for u in b.get("services", [])), 2),
               "cogs": round(b["cabs"] * 46.0, 2), "status": "scheduled",
               "notes": f"AI-booked from {b['booking_id']} ({b['plan']}{tier_note}).{scent_note}{veh_note} {b.get('notes', '')}".strip(),
               "checklist": _build_checklist(b.get("services", [])), "created_at": _now()}
        await db.tc_jobs.insert_one(dict(job))
        routing = await _route_date(date)
        tech_name = next((r["tech_name"] for r in routing.get("assigned", []) if r["job_id"] == job["job_id"]), "")
        await db.tc_bookings.update_one({"booking_id": b["booking_id"]}, {"$set": {
            "status": "converted", "converted_at": _now(), "auto_piloted": True,
            "client_id": client["client_id"], "job_id": job["job_id"],
            "scheduled_date": date, "tech_name": tech_name}})
        return {"client_id": client["client_id"], "job_id": job["job_id"],
                "scheduled_date": date, "tech_name": tech_name}

    async def _booking_alert_email(b: dict):
        from routes.orisei_auto_digest import _resend_creds, _send_via_resend
        recipients = ["oliver@oriseifreightsolutions.com"]
        svc_labels = [u["label"] for u in UPSELL_META if u["id"] in b.get("services", [])]
        rows = [("Company", b.get("company", "—")), ("Contact", b.get("contact") or "—"),
                ("Phone", b.get("phone") or "—"), ("Email", b.get("email") or "—"),
                ("Cabs", str(b.get("cabs", 1))),
                ("Service address", b.get("address") or "—"),
                ("Vehicle location", b.get("vehicle_location") or "—"),
                ("Plan", {"one_time": "One-Time $175", "fleet": "Fleet $150", "biweekly": "Bi-Weekly $130", "car_detail": "Full Car Detail"}.get(b.get("plan", ""), b.get("plan") or "—")),
                ("Detail tier", (b.get("tier") or "—").title()),
                ("Heard about us", b.get("heard_from") or "—"),
                ("Preferred date", b.get("preferred_date") or "flexible"),
                ("Add-ons", ", ".join(svc_labels) or "none"),
                ("Scent", b.get("scent") or "—"), ("Notes", b.get("notes") or "—"),
                ("Booking ID", b.get("booking_id", ""))]
        if b.get("job_id"):
            rows += [("AI AUTOPILOT", f"Job {b['job_id']} scheduled for {b.get('scheduled_date', '?')}"),
                     ("Crew assigned", b.get("tech_name") or "NO ACTIVE CREW — assign in the TMS")]
        table = "".join(f"<tr><td style='padding:6px 14px 6px 0;color:#64748B;font-size:12px;white-space:nowrap'>{k}</td>"
                        f"<td style='padding:6px 0;font-size:13px;font-weight:600'>{v}</td></tr>" for k, v in rows)
        subject = f"NEW BOOKING — {b.get('company', 'Unknown')} · {b.get('cabs', 1)} cab(s)"
        html = (f"<div style='font-family:Arial,Helvetica,sans-serif;max-width:560px;margin:0 auto;color:#0D1117'>"
                f"<div style='background:#0D1117;padding:18px 24px;border-bottom:4px solid #F59E0B'>"
                f"<span style='color:#F59E0B;font-size:11px;letter-spacing:3px;font-family:Courier,monospace'>ORISEI TRUCK CLEANING</span>"
                f"<div style='color:#fff;font-size:19px;font-weight:800;margin-top:6px'>Someone just booked a spot</div></div>"
                f"<div style='padding:20px 24px;border:1px solid #E2E8F0;border-top:none'>"
                f"<table style='border-collapse:collapse'>{table}</table>"
                f"<p style='margin-top:16px;font-size:13px'>Open the TMS &rarr; Truck Cleaning &rarr; Bookings to convert it into a job.</p>"
                f"</div></div>")
        creds = await _resend_creds(db)
        for to in recipients:
            res = await _send_via_resend(creds, to=to, subject=subject, html=html) if creds \
                else {"sent": False, "error": "no_resend_creds"}
            status = "sent" if res.get("sent") else "recorded_no_key"
            await db.outbound_emails.insert_one({
                "to": to, "subject": subject, "html": html, "status": status, "error": res.get("error"),
                "kind": "tc_booking_alert", "booking_id": b.get("booking_id"), "at": _now()})

    @router.get("/bookings")
    async def list_bookings(_=Depends(guard)):
        rows = await db.tc_bookings.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)
        return {"bookings": rows, "new": sum(1 for r in rows if r["status"] == "new")}

    @router.post("/bookings/{booking_id}/convert")
    async def convert_booking(booking_id: str, _=Depends(guard)):
        b = await db.tc_bookings.find_one({"booking_id": booking_id}, {"_id": 0})
        if not b:
            raise HTTPException(404, "Booking not found")
        if b["status"] == "converted":
            raise HTTPException(400, "Already converted")
        client = await db.tc_clients.find_one({"company": b["company"]}, {"_id": 0})
        if not client:
            client = {"client_id": f"TCC-{uuid.uuid4().hex[:8].upper()}", "company": b["company"],
                      "contact": b.get("contact", ""), "phone": b.get("phone", ""),
                      "email": b.get("email", ""), "cabs": b["cabs"], "plan": "one_time",
                      "rate": 175.0, "source": "booking_page", "notes": b.get("notes", ""),
                      "created_at": _now()}
            await db.tc_clients.insert_one(dict(client))
            client.pop("_id", None)
        job = {"job_id": f"TCJ-{uuid.uuid4().hex[:8].upper()}", "client_id": client["client_id"],
               "company": client["company"], "date": b.get("preferred_date") or _today(),
               "cabs": b["cabs"], "upsells": b.get("services", []),
               "price": round(b["cabs"] * client.get("rate", 175) +
                              sum(UPSELLS.get(u, 0) for u in b.get("services", [])), 2),
               "cogs": round(b["cabs"] * 46.0, 2), "status": "scheduled",
               "notes": f"From booking {booking_id}. {b.get('notes', '')}".strip(),
               "checklist": _build_checklist(b.get("services", [])), "created_at": _now()}
        await db.tc_jobs.insert_one(dict(job))
        job.pop("_id", None)
        await db.tc_bookings.update_one({"booking_id": booking_id},
                                        {"$set": {"status": "converted", "converted_at": _now(),
                                                  "client_id": client["client_id"], "job_id": job["job_id"]}})
        return {"ok": True, "client_id": client["client_id"], "job_id": job["job_id"]}

    @router.post("/bookings/{booking_id}/dismiss")
    async def dismiss_booking(booking_id: str, _=Depends(guard)):
        r = await db.tc_bookings.update_one({"booking_id": booking_id},
                                            {"$set": {"status": "dismissed", "dismissed_at": _now()}})
        if r.matched_count == 0:
            raise HTTPException(404, "Booking not found")
        return {"ok": True}

    return router
