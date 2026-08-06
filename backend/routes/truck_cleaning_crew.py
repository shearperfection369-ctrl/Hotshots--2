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

from routes.truck_cleaning import UPSELL_META, UPSELLS
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
    preferred_date: str = Field("", max_length=10)
    services: List[str] = Field(default_factory=list)
    notes: str = Field("", max_length=500)


class AutoAssignIn(BaseModel):
    date: str = Field("", max_length=10)


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
        return {"job_id": j["job_id"], "company": c.get("company", "?"), "address": c.get("notes", ""),
                "contact": c.get("contact", ""), "phone": c.get("phone", ""),
                "date": j["date"], "window": j.get("window", ""), "cabs": j["cabs"],
                "status": j["status"], "upsells": j.get("upsells", []),
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
        jobs = await db.tc_jobs.find({"date": date}, {"_id": 0}).to_list(300)
        unassigned = [j for j in jobs if j["status"] == "scheduled" and not j.get("tech_ids")]
        techs = await db.tc_techs.find({"active": True}, {"_id": 0, "pin_hash": 0, "pin_lookup": 0}).to_list(100)
        if not techs:
            raise HTTPException(400, "No active crews to assign")
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

        # lazy one-time yard geocode from client notes (booking form captures yard address there)
        from routes.routing_svc import _osm_geocode
        for j in unassigned:
            c = clients.get(j["client_id"]) or {}
            if c and c.get("yard_lat") is None and not c.get("yard_geo_tried"):
                addr = (c.get("notes") or "").split("\n")[0].strip()[:120]
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

    # ================= PUBLIC BOOKING =================
    @router.get("/public/site-info")
    async def site_info():
        return {"base_price": 150, "fleet_price": 125, "sub_price": 120,
                "services": [{"id": u["id"], "label": u["label"], "price": u["price"],
                              "desc": u["desc"], "category": u["category"]} for u in UPSELL_META],
                "phone": "(763) 443-4459", "email": "oliver@oriseifreightsolutions.com",
                "area": "Twin Cities metro — Minneapolis, St. Paul & every yard within 50 miles"}

    @router.post("/public/booking")
    async def public_booking(payload: BookingIn, request: Request):
        await _rate_limit(request, scope="booking")
        services = [s for s in payload.services if s in UPSELLS]
        doc = {**payload.model_dump(), "services": services,
               "booking_id": f"BOOK-{uuid.uuid4().hex[:6].upper()}",
               "status": "new", "created_at": _now()}
        await db.tc_bookings.insert_one(dict(doc))
        return {"ok": True, "booking_id": doc["booking_id"],
                "message": "Request received — we'll confirm your slot within one business day."}

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
                      "rate": 150.0, "source": "booking_page", "notes": b.get("notes", ""),
                      "created_at": _now()}
            await db.tc_clients.insert_one(dict(client))
            client.pop("_id", None)
        job = {"job_id": f"TCJ-{uuid.uuid4().hex[:8].upper()}", "client_id": client["client_id"],
               "company": client["company"], "date": b.get("preferred_date") or _today(),
               "cabs": b["cabs"], "upsells": b.get("services", []),
               "price": round(b["cabs"] * client.get("rate", 150) +
                              sum(UPSELLS[u] for u in b.get("services", [])), 2),
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
