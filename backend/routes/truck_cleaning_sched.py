"""routes.truck_cleaning_sched — master scheduler, tech dispatch board, and the step-by-step cab cleaning guide."""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from routes.truck_cleaning import UPSELLS, COGS_PER_CAB


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TechIn(BaseModel):
    name: str = Field(..., min_length=2, max_length=80)
    phone: str = Field("", max_length=40)
    role: str = Field("junior")  # lead | junior
    hourly_rate: float = Field(25.0, ge=10, le=100)
    skills: List[str] = Field(default_factory=list)


class AssignIn(BaseModel):
    tech_ids: List[str] = Field(default_factory=list)
    window: str = Field("", max_length=30)  # e.g. "08:00-10:00"


class JobUpdateIn(BaseModel):
    date: str = Field("", max_length=10)
    cabs: int = Field(0, ge=0, le=500)
    window: Optional[str] = Field(None, max_length=30)
    tech_ids: Optional[List[str]] = None
    status: str = Field("", max_length=20)
    upsells: Optional[List[str]] = None


class TechUpdateIn(BaseModel):
    name: str = Field("", max_length=80)
    phone: str = Field("", max_length=40)
    role: str = Field("", max_length=10)
    hourly_rate: float = Field(0, ge=0, le=100)


CLEANING_GUIDE = {
    "title": "The Orisei 45-Minute Showroom Spec — Full Step-by-Step",
    "intro": "One cab, one tech, 45 minutes flat. Two techs on a sleeper cab. Work top-down, front-to-back, dry-before-wet. Photos are part of the job — no photos, no proof, no invoice.",
    "supply_kit": ["Shop vac + crevice & brush heads", "Pressure sprayer (low PSI) + wash mitt", "APC (all-purpose cleaner) diluted 10:1", "Interior detailer spray", "Glass cleaner (ammonia-free) + waffle towels", "Carpet/upholstery extractor or drill brush + towels", "Odor eliminator (enzyme) + air freshener", "Microfiber towels ×12 (color-coded: blue glass, yellow interior, red floors)", "Detail brushes (vent, seam, cup-holder)", "Nitrile gloves + knee pad", "Phone/tablet for before-after photos"],
    "phases": [
        {"phase": "0 · Walk-Around & BEFORE Photos", "minutes": 3, "steps": [
            "Greet the driver, confirm the work order (cabs, upsells) and any problem areas.",
            "Photograph 4 angles minimum: driver seat, passenger area, dash, sleeper/floor. Time-stamped.",
            "Note pre-existing damage (cracked trim, torn seat) on the report card — protects you from claims.",
            "Remove driver's personal items to a labeled tote. NEVER throw anything away."]},
        {"phase": "1 · Declutter & Trash", "minutes": 4, "steps": [
            "Trash bag every visible item that is obviously waste — cups, wrappers, receipts.",
            "Pull floor mats out and shake/hang them.",
            "Empty ashtrays and cup holders. Soak removable cup-holder inserts in APC.",
            "Open both doors and the sleeper vents to air the cab out while you work."]},
        {"phase": "2 · Full Vacuum (top-down)", "minutes": 7, "steps": [
            "Vacuum headliner seams and visors with the brush head — dust rains down, so this comes first.",
            "Vacuum dash top, vents (brush head), and console crevices with the crevice tool.",
            "Vacuum seats: back, base, seams, under-seat rails. Slide seats full-forward then full-back.",
            "Vacuum floors last: pedals area, under mats, sleeper floor, mattress surface.",
            "Pro tip: a quick blast of compressed air in vents before vacuuming pushes hidden dust out."]},
        {"phase": "3 · Dashboard, Console & Trim", "minutes": 8, "steps": [
            "Spray interior detailer on a towel (never directly on the dash — it fogs the windshield).",
            "Wipe dash top, instrument cluster surround, steering wheel and column.",
            "Detail brushes on vents, buttons, stalks and seams; follow with a dry towel pass.",
            "Clean cup holders, door pockets, grab handles and door panels with APC.",
            "Steering wheel gets a dedicated APC pass — it is the dirtiest surface in the cab.",
            "Finish trim with a matte (not greasy) protectant. Drivers hate glare and slick wheels."]},
        {"phase": "4 · Seats & Upholstery Deep Clean", "minutes": 8, "steps": [
            "Cloth: pre-spray APC, agitate with drill brush in overlapping circles, extract or towel-lift.",
            "Leather/vinyl: APC on towel, wipe, then conditioner. No soaking the seams.",
            "Stain protocol: blot (never rub), treat with enzyme cleaner, agitate light, blot dry.",
            "Seatbelts: extend fully, APC wipe, hold extended until dry so they retract clean.",
            "Sleeper bunk: strip and fold bedding, vacuum mattress, spot-treat, spray odor eliminator."]},
        {"phase": "5 · Floors & Pedals", "minutes": 6, "steps": [
            "Scrub rubber mats with APC + stiff brush, rinse, hang to dry.",
            "Carpet: pre-spray traffic lanes, drill-brush, towel-extract. Work rear-to-front.",
            "Degrease pedals and kick panels — grip surfaces must be residue-free (safety).",
            "Wipe door sills and steps; these are the first thing a driver sees climbing in."]},
        {"phase": "6 · Glass — Inside & Out", "minutes": 5, "steps": [
            "Inside first: windshield with a reach tool, ammonia-free glass cleaner, waffle towel.",
            "Two-towel method: one wet pass, one dry buff. Check from outside for streaks.",
            "Side windows: roll down 2 inches to hit the top edge channel, then up and finish.",
            "Mirrors and sleeper windows last. Glass sells the clean — zero streaks, zero excuses."]},
        {"phase": "7 · Odor Kill & Finish", "minutes": 3, "steps": [
            "Enzyme odor eliminator misted on carpet, seats, and headliner edge (not electronics).",
            "One air freshener clipped low (not on a vent blasting the driver's face). Ask scent preference.",
            "Replace mats, return the driver's tote exactly where it was, wipe your own boot prints."]},
        {"phase": "8 · AFTER Photos & Sign-Off", "minutes": 1, "steps": [
            "Photograph the same 4 angles as the BEFORE set.",
            "Walk the driver through the cab, get the report-card rating + signature.",
            "Upload photos to the job in the TMS and hit 'Send to client' — proof closes repeat business."]},
    ],
    "upsells": [
        {"name": "Bunk Bed Change — $25 service + bedding products (add 10 min)", "steps": ["Strip old bedding, bag it for the driver (or swap into our laundry rotation)", "Vacuum + enzyme-treat the mattress while it's bare", "Install the new set: protector first, fitted sheet, flat sheet hotel-corner tucked, pillow", "Upsell the product: Fresh Start set $59, Premium Sleep Kit $99, pillows $29-39 — installed free with the service"]},
        {"name": "Engine Bay Degrease — $25 (add 15 min)", "steps": ["Engine cool + battery covered", "Dry-brush loose debris", "Degreaser on painted/plastic surfaces, agitate, low-PSI rinse AVOIDING alternator/fuse box/intake", "Dress plastics matte"]},
        {"name": "Tire Dressing — $20 (add 10 min)", "steps": ["Wash sidewalls with APC + brush", "Dry fully", "Water-based dressing, two thin coats", "No sling: wipe excess before rolling"]},
        {"name": "Cabin Air Filter — $15 (add 5 min)", "steps": ["Locate housing (usually behind glovebox/under dash)", "Photo the old filter next to the new one — instant visual upsell proof", "Install airflow-arrow correct", "Log filter size on the client record for reorder"]},
    ],
    "safety": ["Three points of contact climbing in/out — always", "Chock check + parking brake before working around a cab", "No wet products on pedals, wheel or shifter grip surfaces", "Ventilate when using solvents; nitrile gloves on chemical steps", "Never run cords/hoses across a live yard lane"],
    "quality_bar": ["Zero streaks on glass at eye level", "No product glare on dash or wheel", "Cup holders pass the fingertip test", "Cab smells neutral-clean, not perfumed", "BEFORE/AFTER photos uploaded before you leave the yard"],
}


def build_truck_cleaning_sched_router(*, db, require_role: Callable) -> APIRouter:
    router = APIRouter(prefix="/truck-cleaning", tags=["truck-cleaning-sched"])
    guard = require_role("admin", "owner", "dispatcher")

    async def _seed_techs():
        if await db.tc_techs.count_documents({}) > 0:
            return
        for name, role, rate, skills in [
            ("Marcus Reyes", "lead", 32.0, ["deep-clean", "engine-bay", "training"]),
            ("Jaylen Brooks", "junior", 25.0, ["deep-clean", "glass"]),
            ("Tommy Nguyen", "junior", 25.0, ["deep-clean", "upholstery"]),
        ]:
            await db.tc_techs.insert_one({"tech_id": f"TECH-{uuid.uuid4().hex[:6].upper()}", "name": name,
                                          "phone": "", "role": role, "hourly_rate": rate, "skills": skills,
                                          "active": True, "is_sample": True, "created_at": _now()})

    # ---------------- techs ----------------
    @router.get("/techs")
    async def techs(_=Depends(guard)) -> Dict[str, Any]:
        await _seed_techs()
        rows = await db.tc_techs.find({"active": True}, {"_id": 0}).sort("role", 1).to_list(100)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        jobs_today = await db.tc_jobs.find({"date": today, "status": "scheduled"}, {"_id": 0}).to_list(200)
        for t in rows:
            assigned = [j for j in jobs_today if t["tech_id"] in (j.get("tech_ids") or [])]
            t["jobs_today"] = len(assigned)
            t["cabs_today"] = sum(j["cabs"] for j in assigned)
            t["status_today"] = "on_job" if assigned else "available"
        return {"techs": rows}

    @router.post("/techs")
    async def add_tech(payload: TechIn, _=Depends(guard)) -> Dict[str, Any]:
        if payload.role not in ("lead", "junior"):
            raise HTTPException(status_code=400, detail="role must be lead|junior")
        row = {"tech_id": f"TECH-{uuid.uuid4().hex[:6].upper()}", **payload.model_dump(),
               "active": True, "is_sample": False, "created_at": _now()}
        await db.tc_techs.insert_one(dict(row))
        return {"ok": True, "tech": row}

    @router.delete("/techs/{tech_id}")
    async def remove_tech(tech_id: str, _=Depends(guard)) -> Dict[str, Any]:
        r = await db.tc_techs.update_one({"tech_id": tech_id}, {"$set": {"active": False}})
        if r.matched_count == 0:
            raise HTTPException(status_code=404, detail="Tech not found")
        await db.tc_jobs.update_many({"status": "scheduled"}, {"$pull": {"tech_ids": tech_id}})
        return {"ok": True}

    # ---------------- assignment ----------------
    @router.post("/jobs/{job_id}/assign")
    async def assign(job_id: str, payload: AssignIn, _=Depends(guard)) -> Dict[str, Any]:
        job = await db.tc_jobs.find_one({"job_id": job_id}, {"_id": 0})
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        valid = await db.tc_techs.find({"tech_id": {"$in": payload.tech_ids}, "active": True},
                                       {"_id": 0, "tech_id": 1}).to_list(50)
        ids = [t["tech_id"] for t in valid]
        await db.tc_jobs.update_one({"job_id": job_id},
                                    {"$set": {"tech_ids": ids, "window": payload.window, "assigned_at": _now()}})
        return {"ok": True, "tech_ids": ids, "window": payload.window}

    # ---------------- job edit / delete ----------------
    @router.post("/jobs/{job_id}/update")
    async def update_job(job_id: str, payload: JobUpdateIn, _=Depends(guard)) -> Dict[str, Any]:
        job = await db.tc_jobs.find_one({"job_id": job_id}, {"_id": 0})
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        upd: Dict[str, Any] = {}
        if payload.date:
            upd["date"] = payload.date
            upd["reminder_for_date"] = None
        if payload.window is not None:
            upd["window"] = payload.window
        if payload.status:
            if payload.status not in ("scheduled", "completed", "paid"):
                raise HTTPException(status_code=400, detail="status must be scheduled|completed|paid")
            upd["status"] = payload.status
        if payload.tech_ids is not None:
            valid = await db.tc_techs.find({"tech_id": {"$in": payload.tech_ids}, "active": True},
                                           {"_id": 0, "tech_id": 1}).to_list(50)
            upd["tech_ids"] = [t["tech_id"] for t in valid]
        cabs = payload.cabs or job["cabs"]
        ups = [u for u in payload.upsells if u in UPSELLS] if payload.upsells is not None else job.get("upsells", [])
        if payload.cabs or payload.upsells is not None:
            client = await db.tc_clients.find_one({"client_id": job["client_id"]}, {"_id": 0}) or {}
            upd["cabs"] = cabs
            upd["upsells"] = ups
            upd["price"] = round(cabs * client.get("rate", 150) + sum(UPSELLS[u] for u in ups), 2)
            upd["cogs"] = round(cabs * COGS_PER_CAB, 2)
        if not upd:
            raise HTTPException(status_code=400, detail="Nothing to update")
        upd["updated_at"] = _now()
        await db.tc_jobs.update_one({"job_id": job_id}, {"$set": upd})
        fresh = await db.tc_jobs.find_one({"job_id": job_id}, {"_id": 0})
        return {"ok": True, "job": fresh}

    @router.delete("/jobs/{job_id}")
    async def delete_job(job_id: str, _=Depends(guard)) -> Dict[str, Any]:
        r = await db.tc_jobs.delete_one({"job_id": job_id})
        if r.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Job not found")
        return {"ok": True}

    @router.post("/techs/{tech_id}/update")
    async def update_tech(tech_id: str, payload: TechUpdateIn, _=Depends(guard)) -> Dict[str, Any]:
        upd = {}
        if payload.name:
            upd["name"] = payload.name
        if payload.phone or payload.phone == "":
            upd["phone"] = payload.phone
        if payload.role:
            if payload.role not in ("lead", "junior"):
                raise HTTPException(status_code=400, detail="role must be lead|junior")
            upd["role"] = payload.role
        if payload.hourly_rate:
            upd["hourly_rate"] = payload.hourly_rate
        if not upd:
            raise HTTPException(status_code=400, detail="Nothing to update")
        r = await db.tc_techs.update_one({"tech_id": tech_id, "active": True}, {"$set": upd})
        if r.matched_count == 0:
            raise HTTPException(status_code=404, detail="Tech not found")
        return {"ok": True}

    # ---------------- schedule board ----------------
    @router.get("/schedule")
    async def schedule(start: str = "", days: int = 7, _=Depends(guard)) -> Dict[str, Any]:
        await _seed_techs()
        days = max(1, min(days, 45))
        try:
            d0 = datetime.strptime(start, "%Y-%m-%d").date() if start else datetime.now(timezone.utc).date()
        except ValueError:
            raise HTTPException(status_code=400, detail="start must be YYYY-MM-DD")
        dates = [(d0 + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]
        jobs = await db.tc_jobs.find({"date": {"$in": dates}}, {"_id": 0}).to_list(500)
        techs_all = await db.tc_techs.find({"active": True}, {"_id": 0}).to_list(100)
        tmap = {t["tech_id"]: t["name"] for t in techs_all}
        board = []
        for d in dates:
            day_jobs = sorted([j for j in jobs if j["date"] == d], key=lambda j: j.get("window") or "99")
            for j in day_jobs:
                j["tech_names"] = [tmap.get(tid, "?") for tid in (j.get("tech_ids") or [])]
            board.append({"date": d, "jobs": day_jobs,
                          "cabs": sum(j["cabs"] for j in day_jobs),
                          "revenue": round(sum(j["price"] for j in day_jobs), 2),
                          "unassigned": sum(1 for j in day_jobs if j["status"] == "scheduled" and not j.get("tech_ids"))})
        crew_min = sum(j["cabs"] for j in jobs if j["status"] == "scheduled") * 45
        return {"start": dates[0], "days": board,
                "summary": {"jobs": len(jobs), "cabs": sum(j["cabs"] for j in jobs),
                            "revenue": round(sum(j["price"] for j in jobs), 2),
                            "crew_hours_needed": round(crew_min / 60, 1),
                            "techs": len(techs_all)}}

    # ---------------- cleaning guide ----------------
    @router.get("/guide")
    async def guide(_=Depends(guard)) -> Dict[str, Any]:
        return CLEANING_GUIDE

    return router
