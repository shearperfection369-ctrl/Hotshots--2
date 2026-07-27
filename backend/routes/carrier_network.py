"""routes.carrier_network — Carrier Relationship Network.

Implements the overflow/backhaul carrier strategy: own the overflow and
backhaul lanes of regional carriers instead of fighting for scraps on DAT.
Four relationship categories, a stage pipeline, capacity-window board,
discovery-question tracking, and a live scoreboard against the
"realistic play" targets (2-3 mid-size overflow + 4-6 owner-ops).
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

log = logging.getLogger("tennant_tms.carrier_network")

CATEGORIES = {
    "owner_op": {
        "label": "Owner-Ops & Small Fleets (5–15 trucks)",
        "target_locked": 6, "target_locked_min": 4,
        "why": "Bread and butter. They live on DAT/TruckStop hunting loads — flexible, responsive, loyal if you feed them consistent volume.",
        "pitch": "I book consistent upper-Midwest freight and I'd rather feed the same 5 trucks every week than post to a board. "
                 "Give me your preferred lanes and empty days — I'll fill them first, pay quick-pay, and never ghost your dispatcher.",
    },
    "regional_overflow": {
        "label": "Regional Dedicated Carriers (overflow)",
        "target_locked": 3, "target_locked_min": 2,
        "why": "SAIA / R&L / Heartland types have dedicated lanes AND excess capacity they'll broker out. Their relationship contact tells you the open windows — that's your load.",
        "pitch": "I'm not competing with you — I'm your overflow valve. When you're full, I take the board loads you can't fit. "
                 "I'll get your drivers backhaul freight on the way home. You keep utilization up, I get volume. "
                 "If you trust my execution, refer me the loads you turn down.",
    },
    "specialty": {
        "label": "Specialty / Niche Fleets (flatbed · reefer · hazmat)",
        "target_locked": 2, "target_locked_min": 1,
        "why": "Margin-rich on boards because most brokers can't match them. Flatbed/reefer/hazmat loads move at $2K–$4K per haul with fatter margin.",
        "pitch": "Specialty freight is where I make my margin and where you make yours. I'll bring you tarped, permitted, "
                 "temp-controlled loads that generic brokers can't cover — priced for the work, not the board average.",
    },
    "backhauler": {
        "label": "Backhaulers (deadhead into/out of MSP)",
        "target_locked": 3, "target_locked_min": 2,
        "why": "Carriers who consistently deadhead into the Twin Cities or out to Denver/Dallas. Empty trucks = negotiating leverage; they eat the margin loss, you get fast volume.",
        "pitch": "You're running empty into Minneapolis every week — I can put freight in that trailer. "
                 "Below-board rate, sure, but it beats hauling air. Tell me your regular deadhead lanes and I'll watch them for you.",
    },
}

STAGES = ["target", "contacted", "meeting", "pilot_load", "locked_in"]

DISCOVERY_QUESTIONS = [
    {"key": "capacity_lanes", "q": "Which lanes do they chronically have capacity on?",
     "why": "Those windows are your loads — you own them."},
    {"key": "avg_load_time", "q": "What's their average load time?",
     "why": "Quick turnarounds = better margins for you."},
    {"key": "has_owner_ops", "q": "Do they have owner-ops or contractors?",
     "why": "Those folks will work with you directly."},
    {"key": "deadhead_rate", "q": "What's their current deadhead rate?",
     "why": "That tells you where the backhaul opportunity is."},
]

# Twin Cities / upper-Midwest prospect seed (sample data — wipeable).
SEED_PROSPECTS: List[Dict[str, Any]] = [
    # Owner-ops & small fleets
    {"name": "North Star Haulers LLC", "category": "owner_op", "city": "Blaine, MN", "trucks": 8,
     "equipment": ["Van"], "contact_name": "Pete Lindqvist", "contact_phone": "(763) 555-0141",
     "lanes": ["MSP → Chicago", "MSP → Milwaukee"], "notes": "Runs DAT daily; wants steady Tue/Wed freight."},
    {"name": "Gopher State Transport", "category": "owner_op", "city": "Eagan, MN", "trucks": 6,
     "equipment": ["Reefer"], "contact_name": "Maria Vang", "contact_phone": "(651) 555-0177",
     "lanes": ["MSP → Des Moines", "MSP → Kansas City"], "notes": "Reefer-only; quick-pay preferred."},
    {"name": "Lakeville Express Inc", "category": "owner_op", "city": "Lakeville, MN", "trucks": 12,
     "equipment": ["Van", "Flatbed"], "contact_name": "Dan Okafor", "contact_phone": "(952) 555-0163",
     "lanes": ["MSP → Fargo", "MSP → Sioux Falls"], "notes": "Two flatbeds usually open Thu–Fri."},
    {"name": "Viking Freight Lines", "category": "owner_op", "city": "St. Cloud, MN", "trucks": 9,
     "equipment": ["Van"], "contact_name": "Erik Solheim", "contact_phone": "(320) 555-0129",
     "lanes": ["MSP → Duluth", "MSP → Green Bay"], "notes": "Hunts TruckStop; loyal if fed weekly."},
    {"name": "Mendota Cartage Co", "category": "owner_op", "city": "Mendota Heights, MN", "trucks": 7,
     "equipment": ["Van", "Reefer"], "contact_name": "Sam Rezac", "contact_phone": "(651) 555-0102",
     "lanes": ["MSP local", "MSP → Rochester"], "notes": "Short-haul specialist; same-day capable."},
    {"name": "Twin Ports Trucking", "category": "owner_op", "city": "Duluth, MN", "trucks": 5,
     "equipment": ["Flatbed"], "contact_name": "Lena Aho", "contact_phone": "(218) 555-0188",
     "lanes": ["Duluth → MSP", "Duluth → Chicago"], "notes": "Port steel and lumber; tarps on hand."},
    # Regional dedicated / overflow
    {"name": "SAIA LTL Freight — Roseville terminal", "category": "regional_overflow", "city": "Roseville, MN",
     "trucks": 40, "equipment": ["Van"], "contact_name": "Terminal ops mgr (TBD)",
     "lanes": ["MSP → Chicago", "MSP → Kansas City"],
     "notes": "Anchor target. Pitch = overflow valve, not competitor. Ask for Tue–Thu open windows."},
    {"name": "R&L Carriers — Eagan terminal", "category": "regional_overflow", "city": "Eagan, MN",
     "trucks": 35, "equipment": ["Van"], "contact_name": "Terminal ops mgr (TBD)",
     "lanes": ["MSP → Milwaukee", "MSP → Omaha"],
     "notes": "Anchor target. Predictable lane coverage; broker out excess capacity."},
    {"name": "Heartland Express (regional)", "category": "regional_overflow", "city": "Iowa / MN corridor",
     "trucks": 50, "equipment": ["Van"], "contact_name": "Capacity desk (TBD)",
     "lanes": ["MSP → Des Moines", "MSP → Kansas City"],
     "notes": "Dedicated contract carrier with brokered overflow."},
    {"name": "Dart Transit Co", "category": "regional_overflow", "city": "Eagan, MN",
     "trucks": 45, "equipment": ["Van"], "contact_name": "Capacity desk (TBD)",
     "lanes": ["MSP → Chicago", "MSP → Dallas"],
     "notes": "Local HQ; ask about owner-op network for direct deals."},
    # Specialty / niche
    {"name": "TCX Flatbed Group", "category": "specialty", "city": "Shakopee, MN", "trucks": 14,
     "equipment": ["Flatbed"], "contact_name": "Gus Werner", "contact_phone": "(952) 555-0150",
     "lanes": ["MSP → Denver", "MSP → Chicago"], "notes": "Steel/building products; $2K–$4K hauls."},
    {"name": "Polar Reefer Logistics", "category": "specialty", "city": "Brooklyn Park, MN", "trucks": 11,
     "equipment": ["Reefer"], "contact_name": "Ida Bergstrom", "contact_phone": "(763) 555-0134",
     "lanes": ["MSP → Chicago", "MSP → Kansas City"], "notes": "Food-grade, washouts documented."},
    {"name": "NorthGuard Hazmat Carriers", "category": "specialty", "city": "Rogers, MN", "trucks": 8,
     "equipment": ["Van"], "contact_name": "Ray Kowalski", "contact_phone": "(763) 555-0119",
     "lanes": ["MSP → Omaha", "MSP → Milwaukee"], "notes": "Hazmat-endorsed drivers; premium lanes."},
    # Backhaulers
    {"name": "Mile High Returns", "category": "backhauler", "city": "Denver, CO", "trucks": 10,
     "equipment": ["Van"], "contact_name": "Dispatch (TBD)",
     "lanes": ["MSP → Denver"], "deadhead_lanes": ["Denver → MSP (empty ~3x/wk)"],
     "notes": "Consistently deadheads into MSP — negotiate hard, they're grateful."},
    {"name": "Lone Star Backhaul Co", "category": "backhauler", "city": "Dallas, TX", "trucks": 12,
     "equipment": ["Van", "Reefer"], "contact_name": "Dispatch (TBD)",
     "lanes": ["MSP → Dallas"], "deadhead_lanes": ["MSP → Dallas (empty southbound Mon/Tue)"],
     "notes": "Runs produce north; southbound trailers often empty."},
    {"name": "Windy City Shuttle", "category": "backhauler", "city": "Chicago, IL", "trucks": 9,
     "equipment": ["Van"], "contact_name": "Dispatch (TBD)",
     "lanes": ["Chicago → MSP"], "deadhead_lanes": ["Chicago → MSP (empty inbound daily)"],
     "notes": "Daily CHI–MSP shuttle; inbound leg is the opportunity."},
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProspectIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=160)
    category: str
    city: str = ""
    trucks: int = Field(1, ge=1, le=2000)
    equipment: List[str] = []
    contact_name: str = ""
    contact_email: str = ""
    contact_phone: str = ""
    mc_number: str = ""
    lanes: List[str] = []
    deadhead_lanes: List[str] = []
    notes: str = ""


class ProspectPatch(BaseModel):
    stage: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    mc_number: Optional[str] = None
    trucks: Optional[int] = None
    lanes: Optional[List[str]] = None
    deadhead_lanes: Optional[List[str]] = None
    notes: Optional[str] = None
    discovery: Optional[Dict[str, str]] = None   # answers keyed by question key


class CapacityWindowIn(BaseModel):
    carrier_name: str
    lane: str                                    # e.g. "Chicago → Kansas City"
    days: str = ""                               # e.g. "Tue–Thu"
    trucks_available: int = Field(1, ge=1, le=200)
    equipment: str = "Van"
    rate_note: str = ""
    expires: str = ""                            # ISO date optional


class OutreachIn(BaseModel):
    email: Optional[str] = None


def build_carrier_network_router(*, db, get_current_user: Callable,
                                 require_role: Callable) -> APIRouter:
    router = APIRouter(prefix="/carrier-network", tags=["carrier-network"])

    async def _ensure_seed():
        if await db.carrier_network_prospects.count_documents({}) == 0:
            rows = []
            for p in SEED_PROSPECTS:
                rows.append({**p, "id": f"CN-{uuid.uuid4().hex[:8].upper()}",
                             "stage": "target", "discovery": {},
                             "is_sample": True, "created_at": _now_iso(),
                             "updated_at": _now_iso()})
            await db.carrier_network_prospects.insert_many(rows)
            log.info("Seeded %d Twin Cities carrier-network prospects", len(rows))

    @router.get("/playbook")
    async def playbook(_=Depends(get_current_user)):
        return {
            "strategy": "Don't compete for scraps on DAT — own the overflow and backhaul lanes. "
                        "Pitch regional carriers as their overflow valve: when they're full, you take the "
                        "board loads they can't fit and get their drivers backhaul freight home.",
            "categories": [{"key": k, **v} for k, v in CATEGORIES.items()],
            "discovery_questions": DISCOVERY_QUESTIONS,
            "stages": STAGES,
            "realistic_play": {
                "midsize_relationships": "2–3 mid-sized carriers (20–50 trucks) with predictable overflow",
                "owner_ops": "4–6 owner-ops who hunt boards daily",
                "trucks_moving": "12–20 trucks · 2–3 loads each per week",
                "loads_per_month": "24–60 loads/month",
                "gross_per_month": "$28K–$72K gross/month",
                "with_referrals": "Layer in SAIA/R&L referral overflow → 80–100 loads/month",
            },
        }

    @router.get("/prospects")
    async def list_prospects(category: Optional[str] = None,
                             _=Depends(get_current_user)):
        await _ensure_seed()
        q = {"category": category} if category else {}
        rows = await db.carrier_network_prospects.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
        return {"prospects": rows, "count": len(rows)}

    @router.post("/prospects")
    async def create_prospect(payload: ProspectIn, _=Depends(get_current_user)):
        if payload.category not in CATEGORIES:
            raise HTTPException(400, f"category must be one of {list(CATEGORIES)}")
        doc = {**payload.model_dump(), "id": f"CN-{uuid.uuid4().hex[:8].upper()}",
               "stage": "target", "discovery": {}, "is_sample": False,
               "created_at": _now_iso(), "updated_at": _now_iso()}
        await db.carrier_network_prospects.insert_one(dict(doc))
        return {"ok": True, "prospect": doc}

    @router.patch("/prospects/{pid}")
    async def patch_prospect(pid: str, payload: ProspectPatch,
                             _=Depends(get_current_user)):
        patch = {k: v for k, v in payload.model_dump(exclude_unset=True).items()}
        if "stage" in patch and patch["stage"] not in STAGES:
            raise HTTPException(400, f"stage must be one of {STAGES}")
        if not patch:
            raise HTTPException(400, "Nothing to update")
        if "discovery" in patch:
            existing = await db.carrier_network_prospects.find_one({"id": pid}, {"_id": 0, "discovery": 1})
            if not existing:
                raise HTTPException(404, "Prospect not found")
            merged = {**(existing.get("discovery") or {}), **(patch["discovery"] or {})}
            patch["discovery"] = merged
        patch["updated_at"] = _now_iso()
        r = await db.carrier_network_prospects.find_one_and_update(
            {"id": pid}, {"$set": patch}, return_document=True, projection={"_id": 0})
        if not r:
            raise HTTPException(404, "Prospect not found")
        return {"ok": True, "prospect": r}

    @router.delete("/prospects/{pid}")
    async def delete_prospect(pid: str, _=Depends(get_current_user)):
        r = await db.carrier_network_prospects.delete_one({"id": pid})
        if r.deleted_count == 0:
            raise HTTPException(404, "Prospect not found")
        return {"ok": True}

    # ---------------- One-click branded outreach email (pitch + carrier packet)
    @router.post("/outreach/{pid}")
    async def send_outreach(pid: str, payload: OutreachIn,
                            user=Depends(get_current_user)):
        p = await db.carrier_network_prospects.find_one({"id": pid}, {"_id": 0})
        if not p:
            raise HTTPException(404, "Prospect not found")
        to = (payload.email or p.get("contact_email") or "").strip()
        if not to or "@" not in to:
            raise HTTPException(400, "No contact email on file — provide one to send the pitch.")
        meta = CATEGORIES.get(p.get("category")) or {}
        brand = await db.company_brand.find_one({}, {"_id": 0}) or {}
        company = brand.get("company_name") or "Orisei Freight Solutions"
        accent = brand.get("accent_color") or "#0891b2"
        reply_to = brand.get("contact_email") or "oliver@oriseifreightsolutions.com"
        contact = (p.get("contact_name") or "").split("(")[0].strip() or "there"
        lanes = " · ".join((p.get("lanes") or [])[:3])
        subject = f"{company} × {p['name']} — consistent freight for your trucks"
        html = f"""
        <div style="font-family:Arial,Helvetica,sans-serif;max-width:640px;margin:0 auto;color:#1a202c">
          <div style="background:#0b0e14;padding:20px 28px;border-radius:8px 8px 0 0">
            <span style="color:{accent};font-size:20px;font-weight:800;letter-spacing:1px">{company.upper()}</span>
          </div>
          <div style="border:1px solid #e2e8f0;border-top:none;padding:28px;border-radius:0 0 8px 8px">
            <p>Hi {contact},</p>
            <p>{meta.get('pitch', '')}</p>
            {f'<p style="font-size:13px;color:#475569"><b>Lanes we have in mind for you:</b> {lanes}</p>' if lanes else ''}
            <p style="font-size:13px;color:#475569">I've attached our carrier packet — one page on who we are,
            how we pay (quick-pay available), and how dispatch works. Fifteen minutes on the phone and
            I can tell you exactly how many loads a week we can put on your trucks.</p>
            <p>— {company}<br/><a href="mailto:{reply_to}" style="color:{accent}">{reply_to}</a></p>
          </div>
        </div>"""
        pdf_bytes = None
        try:
            from routes.carrier_brochure import build_carrier_brochure_pdf
            pdf_bytes = build_carrier_brochure_pdf()
        except Exception:
            pass
        from routes.orisei_auto_digest import _resend_creds, _send_via_resend
        creds = await _resend_creds(db)
        res = await _send_via_resend(creds, to=to, subject=subject, html=html,
                                     pdf_bytes=pdf_bytes,
                                     pdf_filename="Carrier_Packet.pdf") if creds else \
            {"sent": False, "error": "no_resend_creds"}
        status = "sent" if res.get("sent") else "recorded_no_key"
        await db.outbound_emails.insert_one({
            "to": to, "subject": subject, "html": html, "status": status,
            "error": res.get("error"), "kind": "carrier_outreach",
            "prospect_id": pid, "at": _now_iso(),
            "sent_by": getattr(user, "name", "system"),
        })
        patch: Dict[str, Any] = {"contact_email": to, "updated_at": _now_iso()}
        if p.get("stage") == "target":
            patch["stage"] = "contacted"
        await db.carrier_network_prospects.update_one({"id": pid}, {"$set": patch})
        return {"ok": True, "sent": res.get("sent", False), "status": status,
                "error": res.get("error"), "subject": subject,
                "stage": patch.get("stage") or p.get("stage"),
                "packet_attached": bool(pdf_bytes)}

    # ---------------- Capacity windows (the "12 trucks Tue–Thu CHI–KC" board)
    @router.get("/capacity-windows")
    async def list_windows(_=Depends(get_current_user)):
        rows = await db.carrier_capacity_windows.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)
        return {"windows": rows}

    @router.post("/capacity-windows")
    async def create_window(payload: CapacityWindowIn, _=Depends(get_current_user)):
        doc = {**payload.model_dump(), "id": f"CW-{uuid.uuid4().hex[:8].upper()}",
               "is_sample": False, "created_at": _now_iso()}
        await db.carrier_capacity_windows.insert_one(dict(doc))
        return {"ok": True, "window": doc}

    @router.delete("/capacity-windows/{wid}")
    async def delete_window(wid: str, _=Depends(get_current_user)):
        r = await db.carrier_capacity_windows.delete_one({"id": wid})
        if r.deleted_count == 0:
            raise HTTPException(404, "Window not found")
        return {"ok": True}

    # ---------------- Scoreboard vs the realistic play
    @router.get("/scoreboard")
    async def scoreboard(_=Depends(get_current_user)):
        await _ensure_seed()
        rows = await db.carrier_network_prospects.find({}, {"_id": 0}).to_list(500)
        windows = await db.carrier_capacity_windows.count_documents({})
        by_cat: Dict[str, Dict[str, Any]] = {}
        trucks_secured = 0
        for k, meta in CATEGORIES.items():
            cat_rows = [r for r in rows if r.get("category") == k]
            locked = [r for r in cat_rows if r.get("stage") == "locked_in"]
            in_pipe = [r for r in cat_rows if r.get("stage") in ("contacted", "meeting", "pilot_load")]
            t = sum(min(int(r.get("trucks") or 1), 20) for r in locked)  # cap credit at 20/carrier
            trucks_secured += t
            by_cat[k] = {"label": meta["label"], "total": len(cat_rows),
                         "locked_in": len(locked), "in_pipeline": len(in_pipe),
                         "target": meta["target_locked"], "target_min": meta["target_locked_min"],
                         "trucks_secured": t}
        trucks_for_play = min(trucks_secured, 20)
        loads_month_low = trucks_secured * 2
        loads_month_high = trucks_secured * 3
        gross_low = loads_month_low * 1167
        gross_high = loads_month_high * 1200
        referral_ready = by_cat["regional_overflow"]["locked_in"] >= 2
        return {
            "by_category": by_cat,
            "trucks_secured": trucks_secured,
            "trucks_in_play_window": f"{trucks_for_play} of 12–20 target",
            "capacity_windows_open": windows,
            "projection": {
                "loads_per_month": [loads_month_low, loads_month_high],
                "gross_margin_usd": [gross_low, gross_high],
                "assumption": "2–3 loads per truck per week at ~$1,150–$1,200 avg margin/load",
                "referral_overflow_unlocked": referral_ready,
                "referral_note": ("SAIA/R&L-class referral overflow unlocked — realistic ceiling 80–100 loads/month"
                                  if referral_ready else
                                  "Lock in 2+ regional overflow carriers to unlock referral volume (80–100 loads/mo ceiling)"),
            },
        }

    return router
