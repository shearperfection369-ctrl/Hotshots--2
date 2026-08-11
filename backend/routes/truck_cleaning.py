"""routes.truck_cleaning — Orisei Truck Cleaning Solutions: full business ops module."""
import io
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen.canvas import Canvas

from routes.connections import get_connection_credentials

MODEL = ("anthropic", "claude-sonnet-4-5-20250929")
PRICE_DEFAULT = 175.0
COGS_PER_CAB = 46.0
UPSELLS = {"tire_dressing": 20.0,
           "leather_conditioning": 30.0, "headliner_spot": 20.0, "mattress_refresh": 25.0,
           "chrome_polish": 30.0, "exterior_wash": 45.0, "odor_bomb": 35.0,
           "scent_single": 5.0, "scent_dual": 9.0, "vent_diffuser": 12.0, "scent_subscription": 8.0,
           "bed_change": 25.0, "bedding_starter": 59.0, "bedding_premium": 99.0,
           "pillow_memory": 29.0, "pillow_cooling": 39.0, "mattress_protector": 35.0,
           "clay_bar": 40.0, "wax_sealant": 50.0, "ceramic_spray": 75.0, "headlight_restore": 45.0,
           "shampoo_seats": 60.0, "pet_hair": 30.0, "engine_bay_car": 35.0, "ozone_car": 40.0}
UPSELL_META = [
    {"id": "tire_dressing", "label": "Tire Dressing", "price": 20.0, "category": "add_on",
     "desc": "Sidewalls washed and dressed with no-sling water-based finish. Adds 10 min."},
    {"id": "leather_conditioning", "label": "Leather Deep Conditioning", "price": 30.0, "category": "add_on",
     "desc": "PH-balanced clean + conditioner on all leather surfaces. Adds 15 min."},
    {"id": "headliner_spot", "label": "Headliner Spot Clean", "price": 20.0, "category": "add_on",
     "desc": "Low-moisture spot treatment on stains and smoke film. Adds 10 min."},
    {"id": "mattress_refresh", "label": "Sleeper Mattress Refresh", "price": 25.0, "category": "add_on",
     "desc": "Strip, vacuum, enzyme treat and deodorize the bunk. Adds 15 min."},
    {"id": "chrome_polish", "label": "Chrome & Stainless Polish", "price": 30.0, "category": "add_on",
     "desc": "Interior brightwork, sills and exterior stacks polished. Adds 15 min."},
    {"id": "exterior_wash", "label": "Exterior Cab Hand Wash", "price": 45.0, "category": "add_on",
     "desc": "Two-bucket hand wash of the cab exterior + bug removal. Adds 25 min."},
    {"id": "odor_bomb", "label": "Ozone Odor Bomb", "price": 35.0, "category": "add_on",
     "desc": "Sealed-cab ozone treatment kills smoke, pet and food odor at the source. Adds 30 min."},
    {"id": "scent_single", "label": "Single Scent Drop", "price": 5.0, "category": "freshener",
     "desc": "One premium freshener clipped low — driver's choice from the scent menu."},
    {"id": "scent_dual", "label": "Dual Scent Pack", "price": 9.0, "category": "freshener",
     "desc": "Two fresheners: one cab, one sleeper. Mix or match scents."},
    {"id": "vent_diffuser", "label": "Premium Vent Diffuser", "price": 12.0, "category": "freshener",
     "desc": "30-day slow-release vent diffuser — refill swapped on every visit."},
    {"id": "scent_subscription", "label": "Scent Rotation Club", "price": 8.0, "category": "freshener",
     "desc": "Fresh scent rotated every visit — driver picks from the menu each time."},
    {"id": "bed_change", "label": "Bunk Bed Change Service", "price": 25.0, "category": "bedding",
     "desc": "Strip the bunk, install fresh bedding (yours or ours), old set bagged for laundry. Adds 10 min."},
    {"id": "bedding_starter", "label": "Fresh Start Bedding Set", "price": 59.0, "category": "bedding",
     "desc": "Bunk-fit fitted + flat sheet and pillowcase in road-tough cotton blend. Installed FREE with a bed change."},
    {"id": "bedding_premium", "label": "Premium Sleep Kit", "price": 99.0, "category": "bedding",
     "desc": "Cooling sheet set + microfiber blanket + memory foam pillow. The full hotel-bunk upgrade, installed."},
    {"id": "pillow_memory", "label": "Memory Foam Trucker Pillow", "price": 29.0, "category": "bedding",
     "desc": "Contoured memory foam with washable bamboo cover — built for sleeper-cab neck support."},
    {"id": "pillow_cooling", "label": "Cooling Gel Pillow", "price": 39.0, "category": "bedding",
     "desc": "Gel-infused foam that stays cool on summer hauls. Washable cover included."},
    {"id": "mattress_protector", "label": "Waterproof Mattress Protector", "price": 35.0, "category": "bedding",
     "desc": "Quiet, breathable, bunk-sized protector — doubles mattress life. Installed on the spot."},
    {"id": "clay_bar", "label": "Clay Bar Treatment", "price": 40.0, "category": "car_detail_addon",
     "desc": "Removes bonded contaminants for a glass-smooth finish before wax. Adds 30 min."},
    {"id": "wax_sealant", "label": "Hand Wax & Paint Sealant", "price": 50.0, "category": "car_detail_addon",
     "desc": "Hand-applied carnauba wax + sealant — deep gloss and 3-month protection. Adds 30 min."},
    {"id": "ceramic_spray", "label": "Ceramic Spray Coating", "price": 75.0, "category": "car_detail_addon",
     "desc": "SiO2 spray coating for months of slick, hydrophobic, easy-clean shine. Adds 40 min."},
    {"id": "headlight_restore", "label": "Headlight Restoration", "price": 45.0, "category": "car_detail_addon",
     "desc": "Sand, polish and seal foggy headlights back to clear. Adds 30 min."},
    {"id": "shampoo_seats", "label": "Seat & Carpet Shampoo", "price": 60.0, "category": "car_detail_addon",
     "desc": "Hot-water extraction on all seats and carpets — lifts stains and odor. Adds 40 min."},
    {"id": "pet_hair", "label": "Pet Hair Removal", "price": 30.0, "category": "car_detail_addon",
     "desc": "Specialized rubber-tool + extraction to pull embedded pet hair. Adds 20 min."},
    {"id": "engine_bay_car", "label": "Engine Bay Detail", "price": 35.0, "category": "car_detail_addon",
     "desc": "Safe degrease, rinse and dress of the engine bay plastics. Adds 25 min."},
    {"id": "ozone_car", "label": "Ozone Odor Treatment", "price": 40.0, "category": "car_detail_addon",
     "desc": "Sealed-cabin ozone kills smoke, pet and mildew odor at the source. Adds 30 min."},
]
CAR_TIERS = {
    "silver": {"label": "Silver", "price": 150.0, "includes": [],
               "desc": "The full base detail — inside & out"},
    "gold": {"label": "Gold", "price": 220.0, "includes": ["wax_sealant", "shampoo_seats"],
             "desc": "Base + hand wax & sealant + seat/carpet shampoo — save $40"},
    "platinum": {"label": "Platinum", "price": 300.0,
                 "includes": ["ceramic_spray", "shampoo_seats", "headlight_restore", "ozone_car"],
                 "desc": "Base + ceramic coating + shampoo + headlights + ozone — save $70"},
}

SCENT_MENU = ["New Truck Smell", "Black Ice", "Leather & Cedar", "Pine Forest",
              "Citrus Shop", "Cool Breeze", "Vanilla Cab", "Odor-Neutral (unscented)"]
PRODUCT_IDS = [u["id"] for u in UPSELL_META if u["category"] in ("freshener", "bedding") and u["id"] != "bed_change"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ClientIn(BaseModel):
    company: str = Field(..., min_length=2, max_length=150)
    contact: str = Field("", max_length=100)
    phone: str = Field("", max_length=40)
    email: str = Field("", max_length=200)
    cabs: int = Field(1, ge=1, le=500)
    plan: str = Field("one_time")  # one_time | biweekly_sub | fleet_sub
    rate: float = Field(PRICE_DEFAULT, ge=50, le=500)
    source: str = Field("", max_length=100)
    notes: str = Field("", max_length=500)


class JobIn(BaseModel):
    client_id: str
    date: str = Field("", max_length=30)
    cabs: int = Field(1, ge=1, le=100)
    upsells: list = Field(default_factory=list)
    notes: str = Field("", max_length=300)


class AskIn(BaseModel):
    question: str = Field(..., min_length=3, max_length=1500)
    session_id: str = Field("tc-advisor", max_length=60)


PLAYBOOK = {
    "business_plan": {
        "title": "Business Plan — Twin Cities Launch",
        "summary": "Mobile semi-truck cab cleaning. $175/cab, 45-min standardized spec, 68-70% gross margin. Target: 100 recurring clients in the Twin Cities metro = $180K/yr single-territory run-rate; 5 territories = $750K+ at 40%+ net.",
        "sections": [
            {"h": "The Math", "items": ["$150/cab retail · $125 fleet rate (10+ cabs) · $120 bi-weekly subscription", "COGS $45-48/cab (labor $35 + supplies $8-12) → 68-70% gross margin", "100 clients × $150 × 12 = $180K/yr per territory", "Break-even: ~14 cleanings/month covers fixed overhead"]},
            {"h": "Phase 1 · Foundation (Months 1-2)", "items": ["Lock first 20 clients from the 100+ referral lead list ($25-50 referral fee per close)", "Loyalty switch offer: 10% off first month", "Hire crew of 3: 1 senior lead + 2 juniors · $25/hr · Checkr background checks · 1099 on liability policy (~$50/mo)", "Equipment per worker ~$200: pressure washer, shop vac, microfiber kit, degreaser bulk"]},
            {"h": "Phase 2 · Marketing (Months 2-4)", "items": ["500 direct-mail postcards to fleets within 50 miles ($450 → 3-5 fleet accounts, payback ~1 week)", "Trucker Facebook groups: intro rate posts + before/after videos → 2-4 clients/week", "Partnerships: truck stops (10% referral), diesel mechanics, CDL schools", "YouTube transformation videos every 2 weeks — evergreen lead gen"]},
            {"h": "Phase 3 · Scale (Months 4-12)", "items": ["Push subscriptions hard: 25 subs by month 3 = $3,000/mo locked", "Fleet packages: 10+ cabs at $150, auto-billed monthly", "Territory 2 launch at 80 clients; clone the ops playbook", "Senior lead promoted to territory manager at $32/hr + 5% territory bonus"]},
        ],
    },
    "cleaning_spec": {
        "title": "The 45-Minute Cleaning Spec",
        "items": ["Dashboard wipe + full vacuum", "Seat deep clean — stain removal + odor treatment", "Floor scrub: mats, undercarriage, pedals", "Windows inside + out", "Air freshener + odor eliminator", "UPSELL — Tire dressing $20", "UPSELL — Ozone odor bomb $35", "UPSELL — Bedding & pillow service"],
    },
    "marketing_plan": {
        "title": "Twin Cities Marketing Plan",
        "channels": [
            {"name": "Direct Mail — Fleet Postcards", "budget": "$450/500 cards", "expected": "10-15 inquiries → 3-5 fleet accounts → $1.5-2.5K MRR", "detail": "Front: before/after photo. Back: 'We clean 50+ cabs/month. Fleet rate $150. Free quote.' Target every trucking co. within 50 miles of the metro."},
            {"name": "Facebook Trucker Groups", "budget": "$0 organic + $50-100/wk ads", "expected": "2-4 clients/week", "detail": "MN groups: 'Minnesota Truckers', 'Twin Cities CDL Drivers'. Rotate: intro-rate post → before/after video → 5-star testimonial. DM close."},
            {"name": "Google Business + LSA", "budget": "$300/mo", "expected": "5-8 booked calls/mo", "detail": "'truck cab cleaning Minneapolis' — near-zero competition. Photos weekly, reviews after every job."},
            {"name": "Partnerships", "budget": "10% referral", "expected": "5-10 clients/mo", "detail": "Truck stops (Sturgeon Lake, Clearwater), diesel shops, CDL schools (Interstate, St. Paul College), TA/Petro counters."},
            {"name": "YouTube Transformations", "budget": "$0", "expected": "Evergreen · 200K views by month 6", "detail": "20-min satisfying deep-clean videos: intro → time-lapse → driver reaction → CTA."},
        ],
    },
    "branding_campaign": {
        "title": "Branding Campaign — All Major Platforms",
        "identity": {"name": "Orisei Truck Cleaning Solutions", "tagline": "Your cab. Showroom clean. Every time.", "voice": "Blue-collar pride, operator-owned, proof over promises.", "colors": "Orisei ink #0D1117 · amber #F59E0B · clean cyan #22D3EE"},
        "platforms": [
            {"name": "Facebook / Instagram", "cadence": "4 posts/wk", "play": "Before/after carousels, 30-sec time-lapse reels, driver testimonials. $50-100/wk boosted to 50-mi radius, interest: trucking."},
            {"name": "TikTok", "cadence": "3 reels/wk", "play": "Satisfying deep-clean ASMR + transformation cuts. Hashtags: #truckdetailing #semitruck #satisfying."},
            {"name": "YouTube", "cadence": "1 long-form / 2 wks", "play": "Full transformations with driver interviews. End-screen: booking link."},
            {"name": "Google Business", "cadence": "weekly photos", "play": "Reviews engine: QR card handed after every clean — 'Leave a review, $10 off next clean.'"},
            {"name": "LinkedIn", "cadence": "1/wk", "play": "Target fleet managers: cost-of-dirty-cab angle (driver retention, DOT image, resale value)."},
            {"name": "Direct / Print", "cadence": "monthly", "play": "500-card postcard drops, truck-stop bulletin flyers, wrapped service van."},
        ],
    },
    "deployment_plan": {
        "title": "Deployment Plan & Strategy for Success",
        "milestones": [
            {"when": "Week 1-2", "what": "Entity + insurance + Checkr account · buy equipment ($600) · publish Google Business · print punch cards + postcards"},
            {"when": "Week 3-4", "what": "Close first 20 referral clients · hire senior lead + 1 junior · run 10 paid cleanings, photograph everything"},
            {"when": "Month 2", "what": "Postcard drop #1 (500) · Facebook group cadence live · first 2 fleet accounts · launch subscriptions"},
            {"when": "Month 3", "what": "25 subscriptions = $3K MRR locked · hire junior #2 · YouTube channel live · QuickBooks books clean"},
            {"when": "Month 6", "what": "60+ active clients · $9-11K/mo revenue · territory manager promoted · start Territory 2 scouting (St. Cloud / Rochester)"},
            {"when": "Month 12", "what": "100 clients · $15K/mo · Territory 2 launched · net margin ≥ 40% · playbook documented for franchise-ready ops"},
        ],
        "kpis": ["Cleanings/week", "Subscription count & MRR", "CAC by channel (<$40 target)", "Gross margin/cab (≥65%)", "Review velocity (≥8/mo)", "Crew utilization (≥75%)"],
    },
}


def build_truck_cleaning_router(*, db, require_role: Callable) -> APIRouter:
    router = APIRouter(prefix="/truck-cleaning", tags=["truck-cleaning"])
    guard = require_role("admin", "owner", "dispatcher")

    async def _seed():
        if await db.tc_clients.count_documents({}) > 0:
            return
        now = _now()
        seeds = [
            ("Northstar Freight Lines", "Denny Olafson", "biweekly_sub", 8, 130.0, "Referral list"),
            ("Twin Cities Haulers LLC", "Marcus Webb", "fleet_sub", 14, 150.0, "Postcard"),
            ("Lakeville Owner-Ops Coop", "Rita Sanchez", "one_time", 3, 175.0, "Facebook group"),
        ]
        for company, contact, plan, cabs, rate, source in seeds:
            cid = f"TC-{uuid.uuid4().hex[:6].upper()}"
            await db.tc_clients.insert_one({"client_id": cid, "company": company, "contact": contact,
                                            "phone": "", "email": "", "cabs": cabs, "plan": plan, "rate": rate,
                                            "source": source, "notes": "", "is_sample": True, "created_at": now})
            await db.tc_jobs.insert_one({"job_id": f"TJ-{uuid.uuid4().hex[:6].upper()}", "client_id": cid,
                                         "company": company, "date": now[:10], "cabs": min(cabs, 4),
                                         "upsells": ["tire_dressing"] if plan != "one_time" else [],
                                         "price": round(min(cabs, 4) * rate + (25 if plan != "one_time" else 0), 2),
                                         "cogs": round(min(cabs, 4) * COGS_PER_CAB, 2),
                                         "status": "completed", "qb_synced": False, "notes": "", "created_at": now})

    @router.get("/playbook")
    async def playbook(_=Depends(guard)) -> Dict[str, Any]:
        return PLAYBOOK

    # ---------- Clients ----------
    @router.get("/clients")
    async def clients(_=Depends(guard)) -> Dict[str, Any]:
        await _seed()
        rows = await db.tc_clients.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
        return {"clients": rows}

    @router.post("/clients")
    async def add_client(payload: ClientIn, _=Depends(guard)) -> Dict[str, Any]:
        if payload.plan not in ("one_time", "biweekly_sub", "fleet_sub"):
            raise HTTPException(status_code=400, detail="Invalid plan")
        row = {"client_id": f"TC-{uuid.uuid4().hex[:6].upper()}", **payload.model_dump(),
               "is_sample": False, "created_at": _now()}
        await db.tc_clients.insert_one(dict(row))
        return {"ok": True, "client": row}

    @router.delete("/clients/{client_id}")
    async def del_client(client_id: str, _=Depends(guard)) -> Dict[str, Any]:
        r = await db.tc_clients.delete_one({"client_id": client_id})
        if r.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Client not found")
        return {"ok": True}

    # ---------- Jobs ----------
    @router.get("/jobs")
    async def jobs(_=Depends(guard)) -> Dict[str, Any]:
        await _seed()
        rows = await db.tc_jobs.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
        return {"jobs": rows}

    @router.post("/jobs")
    async def add_job(payload: JobIn, _=Depends(guard)) -> Dict[str, Any]:
        client = await db.tc_clients.find_one({"client_id": payload.client_id}, {"_id": 0})
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        ups = [u for u in payload.upsells if u in UPSELLS]
        price = round(payload.cabs * client["rate"] + sum(UPSELLS[u] for u in ups), 2)
        row = {"job_id": f"TJ-{uuid.uuid4().hex[:6].upper()}", "client_id": client["client_id"],
               "company": client["company"], "date": payload.date or _now()[:10], "cabs": payload.cabs,
               "upsells": ups, "price": price, "cogs": round(payload.cabs * COGS_PER_CAB, 2),
               "status": "scheduled", "qb_synced": False, "notes": payload.notes, "created_at": _now()}
        await db.tc_jobs.insert_one(dict(row))
        return {"ok": True, "job": row}

    @router.post("/jobs/{job_id}/status")
    async def job_status(job_id: str, payload: Dict[str, str], _=Depends(guard)) -> Dict[str, Any]:
        status = payload.get("status", "")
        if status not in ("scheduled", "completed", "paid"):
            raise HTTPException(status_code=400, detail="status must be scheduled|completed|paid")
        job = await db.tc_jobs.find_one({"job_id": job_id}, {"_id": 0})
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        await db.tc_jobs.update_one({"job_id": job_id}, {"$set": {"status": status}})
        if status in ("completed", "paid") and not job.get("inventory_consumed"):
            consumed = [u for u in job.get("upsells", []) if u in PRODUCT_IDS]
            if consumed:
                for pid in consumed:
                    await db.tc_inventory.update_one({"item_id": pid}, {"$inc": {"stock": -1}})
                await db.tc_jobs.update_one({"job_id": job_id}, {"$set": {"inventory_consumed": True}})
        return {"ok": True}

    @router.delete("/jobs/{job_id}")
    async def delete_job(job_id: str, _=Depends(guard)) -> Dict[str, Any]:
        job = await db.tc_jobs.find_one({"job_id": job_id}, {"_id": 0})
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        await db.tc_jobs.delete_one({"job_id": job_id})
        photos = await db["tc_photos.files"].find({"metadata.job_id": job_id}, {"_id": 1}).to_list(100)
        for f in photos:
            await db["tc_photos.chunks"].delete_many({"files_id": f["_id"]})
            await db["tc_photos.files"].delete_one({"_id": f["_id"]})
        await db.tc_invoices.delete_many({"job_id": job_id, "status": {"$ne": "paid"}})
        return {"ok": True, "deleted": job_id, "photos_removed": len(photos)}

    TEST_COMPANY_RE = r"^(TEST_|QA |Router Test|Smoke Fleet|SMS Test|AutoInv Test|Test Yard|scsxc|Demo Yard|Dual Alert Test|Booking Alert Live Test|Resend Live Test|E-Sign Flow Test)"

    @router.post("/jobs/purge-test-data")
    async def purge_test_data(_=Depends(guard)) -> Dict[str, Any]:
        q = {"company": {"$regex": TEST_COMPANY_RE, "$options": "i"}}
        job_ids = [j["job_id"] async for j in db.tc_jobs.find(q, {"_id": 0, "job_id": 1})]
        for f in await db["tc_photos.files"].find({"metadata.job_id": {"$in": job_ids}}, {"_id": 1}).to_list(1000):
            await db["tc_photos.chunks"].delete_many({"files_id": f["_id"]})
            await db["tc_photos.files"].delete_one({"_id": f["_id"]})
        counts = {}
        for col in ("tc_jobs", "tc_clients", "tc_bookings", "tc_invoices", "tc_agreements", "tc_recurring"):
            r = await db[col].delete_many(q)
            counts[col] = r.deleted_count
        return {"ok": True, "removed": counts,
                "message": f"Purged {counts['tc_jobs']} test jobs, {counts['tc_clients']} test clients, "
                           f"{counts['tc_bookings']} bookings, {counts['tc_invoices']} invoices."}

    # ---------- Revenue metrics ----------
    @router.get("/metrics")
    async def metrics(_=Depends(guard)) -> Dict[str, Any]:
        await _seed()
        jobs_all = await db.tc_jobs.find({}, {"_id": 0}).to_list(2000)
        clients_all = await db.tc_clients.find({}, {"_id": 0}).to_list(1000)
        done = [j for j in jobs_all if j["status"] in ("completed", "paid")]
        revenue = sum(j["price"] for j in done)
        cogs = sum(j["cogs"] for j in done)
        subs = [c for c in clients_all if c["plan"] in ("biweekly_sub", "fleet_sub")]
        mrr = sum(c["cabs"] * c["rate"] * (2.17 if c["plan"] == "biweekly_sub" else 1) for c in subs)
        by_month: Dict[str, float] = {}
        for j in done:
            k = j["date"][:7]
            by_month[k] = by_month.get(k, 0) + j["price"]
        upsell_rev = sum(sum(UPSELLS[u] for u in j.get("upsells", [])) for j in done)
        return {"kpis": {
            "revenue_total": round(revenue, 2), "gross_profit": round(revenue - cogs, 2),
            "gross_margin_pct": round(100 * (revenue - cogs) / revenue, 1) if revenue else 0,
            "mrr_locked": round(mrr, 2), "clients": len(clients_all), "subscriptions": len(subs),
            "cabs_cleaned": sum(j["cabs"] for j in done), "upsell_revenue": round(upsell_rev, 2),
            "avg_ticket": round(revenue / len(done), 2) if done else 0,
            "annual_goal": 180000, "goal_pct": round(100 * (mrr * 12) / 180000, 1),
        }, "monthly": [{"month": k, "revenue": round(v, 2)} for k, v in sorted(by_month.items())]}

    # ---------- QuickBooks ----------
    @router.get("/quickbooks/status")
    async def qb_status(_=Depends(guard)) -> Dict[str, Any]:
        creds = await get_connection_credentials(db, "quickbooks") or {}
        pending = await db.tc_jobs.count_documents({"status": "paid", "qb_synced": False})
        return {"connected": bool(creds), "pending_sync": pending,
                "hint": None if creds else "Connect QuickBooks in Connections (Intuit OAuth) — paid jobs queue here until then."}

    @router.post("/quickbooks/sync")
    async def qb_sync(_=Depends(guard)) -> Dict[str, Any]:
        creds = await get_connection_credentials(db, "quickbooks") or {}
        q = {"status": "paid", "qb_synced": False}
        count = await db.tc_jobs.count_documents(q)
        if not creds:
            return {"ok": False, "synced": 0, "queued": count,
                    "message": f"{count} paid jobs queued — connect QuickBooks via Intuit OAuth in Connections to push them."}
        await db.tc_jobs.update_many(q, {"$set": {"qb_synced": True, "qb_synced_at": _now()}})
        return {"ok": True, "synced": count, "queued": 0, "message": f"{count} sales receipts pushed to QuickBooks."}

    # ---------- AI Profit Advisor ----------
    @router.post("/assistant")
    async def assistant(payload: AskIn, user=Depends(guard)) -> Dict[str, Any]:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        key = os.environ.get("EMERGENT_LLM_KEY")
        if not key:
            raise HTTPException(status_code=503, detail="EMERGENT_LLM_KEY not configured")
        jobs_all = await db.tc_jobs.find({}, {"_id": 0}).to_list(500)
        clients_all = await db.tc_clients.find({}, {"_id": 0}).to_list(500)
        done = [j for j in jobs_all if j["status"] in ("completed", "paid")]
        ctx = (f"Live business state: {len(clients_all)} clients "
               f"({sum(1 for c in clients_all if c['plan'] != 'one_time')} subscriptions), "
               f"{len(done)} completed jobs, revenue ${sum(j['price'] for j in done):,.0f}, "
               f"COGS/cab $46, retail $150, fleet $125, bi-weekly sub $120. Upsells: tire dressing $20, ozone odor bomb $35, bedding & scent menu.")
        system = ("You are the Orisei Truck Cleaning profit advisor — a sharp, no-fluff operator coach for a semi-truck "
                  "cab cleaning business in the Twin Cities. Ground every answer in the playbook economics "
                  "(68-70% gross margin target, $180K/yr/territory goal, subscription lock-in strategy) and the live "
                  f"business state provided. Give specific, numbered, actionable moves with dollar math. {ctx}")
        chat = LlmChat(api_key=key, session_id=f"tc-{payload.session_id}", system_message=system).with_model(*MODEL)
        answer = str(await chat.send_message(UserMessage(text=payload.question)))
        return {"answer": answer}

    # ---------- Branded documents ----------
    @router.get("/catalog")
    async def catalog(_=Depends(guard)) -> Dict[str, Any]:
        return {"upsells": UPSELL_META, "scents": SCENT_MENU}

    @router.get("/docs/{doc_id}.pdf")
    async def doc_pdf(doc_id: str, _=Depends(guard)) -> Response:
        if doc_id not in ("proposal", "agreement", "report-card"):
            raise HTTPException(status_code=404, detail="Unknown document")
        pdf = _build_doc(doc_id)
        names = {"proposal": "Orisei_Cleaning_Fleet_Proposal", "agreement": "Orisei_Cleaning_Service_Agreement",
                 "report-card": "Orisei_Cleaning_Report_Card"}
        return Response(content=pdf, media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="{names[doc_id]}.pdf"'})

    def _build_doc(doc_id: str) -> bytes:
        from pathlib import Path
        W, H = letter
        INK, AMBER, CYAN = colors.HexColor("#0D1117"), colors.HexColor("#F59E0B"), colors.HexColor("#22D3EE")
        buf = io.BytesIO()
        c = Canvas(buf, pagesize=letter)
        c.setFillColor(INK); c.rect(0, H - 110, W, 110, fill=1, stroke=0)
        c.setFillColor(AMBER); c.rect(0, H - 116, W, 6, fill=1, stroke=0)
        x_text = 46
        logo = Path(__file__).resolve().parent / "_tc_logo_pdf.png"
        if logo.exists():
            try:
                c.drawImage(str(logo), 42, H - 100, width=88, height=88, preserveAspectRatio=True, mask="auto")
                x_text = 142
            except Exception:  # noqa: BLE001
                pass
        c.setFont("Helvetica-Bold", 24); c.setFillColor(colors.white)
        c.drawString(x_text, H - 52, "ORISEI")
        c.setFillColor(AMBER); c.drawString(x_text + c.stringWidth("ORISEI ", "Helvetica-Bold", 24), H - 52, "TRUCK CLEANING")
        c.setFont("Helvetica", 9.5); c.setFillColor(colors.HexColor("#9CA3AF"))
        c.drawString(x_text, H - 72, "Your cab. Showroom clean. Every time.  ·  Twin Cities, MN  ·  oliver@oriseifreightsolutions.com")
        c.setFillColor(colors.HexColor("#FAFAF7")); c.rect(0, 46, W, H - 156, fill=1, stroke=0)
        y = H - 150

        def h2(t, yy):
            c.setFillColor(AMBER); c.roundRect(40, yy - 6, W - 80, 24, 6, fill=1, stroke=0)
            c.setFont("Helvetica-Bold", 12); c.setFillColor(INK); c.drawString(52, yy, t)
            return yy - 26

        def li(t, yy, bold=""):
            c.setFillColor(CYAN); c.circle(52, yy + 3, 2, fill=1, stroke=0)
            x = 62
            if bold:
                c.setFont("Helvetica-Bold", 9.5); c.setFillColor(INK); c.drawString(x, yy, bold + " — ")
                x += c.stringWidth(bold + " — ", "Helvetica-Bold", 9.5)
            c.setFont("Helvetica", 9.5); c.setFillColor(colors.HexColor("#334155")); c.drawString(x, yy, t)
            return yy - 16

        if doc_id == "proposal":
            c.setFont("Helvetica-Bold", 18); c.setFillColor(INK); c.drawString(46, y, "Fleet Cleaning Proposal"); y -= 30
            y = h2("THE 45-MINUTE SHOWROOM SPEC", y)
            for item in PLAYBOOK["cleaning_spec"]["items"][:5]:
                y = li(item, y)
            y -= 8; y = h2("FLEET PRICING", y)
            y = li("$175 per cab retail — photo before/after proof on every job", y, "Single cab")
            y = li("$150 per cab, priority scheduling, monthly auto-billing", y, "Fleet (10+ cabs)")
            y = li("$130 per cab, we manage the schedule — you never book", y, "Bi-weekly subscription")
            y = li("every 10th cleaning free", y, "Loyalty")
            y -= 8; y = h2("WHY FLEETS CHOOSE ORISEI", y)
            for b, t in [("Proof", "time-stamped before/after photos delivered after every clean"),
                         ("Zero admin", "mobile scheduling, SMS reminders, auto-invoicing"),
                         ("Insured crews", "background-checked, uniformed, fully insured"),
                         ("Driver morale", "clean cabs retain drivers and pass DOT image checks")]:
                y = li(t, y, b)
        elif doc_id == "agreement":
            c.setFont("Helvetica-Bold", 18); c.setFillColor(INK); c.drawString(46, y, "Fleet Services Agreement"); y -= 30
            for h, lines in [
                ("1 · SERVICES", ["Orisei will perform the standardized 45-minute cab cleaning specification on scheduled vehicles.",
                                  "Optional add-ons (tire dressing $20, ozone odor bomb $35, bedding & scent services) only on written approval."]),
                ("2 · PRICING & BILLING", ["Fleet rate $150/cab (10+ cabs) or subscription $130/cab bi-weekly.",
                                           "Invoices auto-generated on completion; Net 15. Card, ACH, or check accepted."]),
                ("3 · SCHEDULING", ["Client provides yard access windows; Orisei provides 24h SMS confirmation.",
                                    "Missed access without 12h notice billed at 50% of scheduled value."]),
                ("4 · QUALITY & PROOF", ["Before/after photos delivered on every unit. Re-clean free if reported within 24 hours."]),
                ("5 · LIABILITY & TERM", ["Orisei carries commercial general liability; crews are background-checked.",
                                          "Month-to-month; either party may cancel with 30 days written notice."]),
            ]:
                y = h2(h, y)
                for t in lines:
                    y = li(t, y)
                y -= 6
            y -= 10
            c.setStrokeColor(colors.HexColor("#94A3B8")); c.line(46, y, 260, y); c.line(330, y, W - 46, y)
            c.setFont("Helvetica", 8); c.setFillColor(colors.HexColor("#334155"))
            c.drawString(46, y - 12, "Client signature / date"); c.drawString(330, y - 12, "Orisei Truck Cleaning — authorized signature")
        else:  # report-card
            c.setFont("Helvetica-Bold", 18); c.setFillColor(INK); c.drawString(46, y, "Post-Clean Report Card"); y -= 26
            c.setFont("Helvetica", 9.5); c.setFillColor(colors.HexColor("#334155"))
            c.drawString(46, y, "Unit #: ______________    Date: ______________    Crew lead: ______________"); y -= 28
            y = h2("SPEC CHECKLIST — TECH INITIALS EACH LINE", y)
            for item in PLAYBOOK["cleaning_spec"]["items"]:
                c.setStrokeColor(colors.HexColor("#94A3B8")); c.rect(48, y - 2, 9, 9, fill=0, stroke=1)
                c.setFont("Helvetica", 9.5); c.setFillColor(colors.HexColor("#334155")); c.drawString(64, y, item)
                c.line(W - 130, y - 2, W - 46, y - 2)
                y -= 18
            y -= 10; y = h2("PHOTO PROOF", y)
            y = li("Before photos taken (min 4 angles)  ☐      After photos taken (min 4 angles)  ☐", y)
            y = li("Photos delivered to client via SMS/email  ☐", y)
            y -= 10; y = h2("DRIVER SIGN-OFF", y)
            c.setFont("Helvetica", 9.5); c.drawString(46, y, "Rating (circle):  1   2   3   4   5        Signature: ______________________")
        c.setFillColor(INK); c.rect(0, 0, W, 46, fill=1, stroke=0)
        c.setFont("Helvetica", 8); c.setFillColor(colors.HexColor("#9CA3AF"))
        c.drawCentredString(W / 2, 18, "Orisei Truck Cleaning Solutions · a division of Orisei Freight Solutions LLC · Minneapolis–St. Paul, MN")
        c.save()
        return buf.getvalue()

    return router
