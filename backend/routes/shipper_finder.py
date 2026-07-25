"""routes.shipper_finder — shipper prospecting CRM + acquisition playbook.

Pipeline: lead → contacted → meeting → quoted → trial → contracted (or lost).
Includes AI outreach generator (Claude via Emergent) and the branded
shipper-facing brochure PDF.
"""
from __future__ import annotations

import io
import logging
import uuid
from datetime import datetime, timezone
from typing import Callable, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

logger = logging.getLogger("tennant_tms.shipper_finder")

STAGES = ["lead", "contacted", "meeting", "quoted", "trial", "contracted", "lost"]

PLAYBOOK = {
    "competitive_advantages": [
        {"title": "The operator triad", "detail": "13 years on the shipper side (Oliver) + 12 years behind the wheel (Doug) + in-house software (Daniel). No other Minneapolis brokerage has all three founders' perspectives on every load."},
        {"title": "No-double-broker pledge", "detail": "Every load moves on a directly vetted carrier from our own bench. We put it in writing in the broker-shipper agreement — the #1 fraud fear shippers have in 2026."},
        {"title": "Open-book margin", "detail": "We disclose our margin at the quarterly business review. Radical transparency nobody at CH Robinson or TQL will match."},
        {"title": "Command Deck visibility", "detail": "Shippers get a free portal login: live GPS tracking, PODs, invoices, lane analytics — the tech of a mega-broker with the service of a boutique."},
        {"title": "Diaspora carrier network", "detail": "Daniel's Brooklyn Park West-African owner-operator community gives Orisei surge capacity competitors can't tap."},
        {"title": "A named human, 24/7", "detail": "No ticket queues. Oliver's cell is on the rate con. After-hours escalation answered by a founder."},
        {"title": "Small-book economics", "detail": "At 8-20 accounts we can treat every shipper as a top account. Mega-brokers churn small shippers to junior reps."},
    ],
    "offer_stack": [
        {"offer": "Fixed-rate trial", "detail": "4 loads on one lane at a locked rate, with a money-back margin guarantee if we miss a pickup or delivery window."},
        {"offer": "Free lane benchmark PDF", "detail": "24-hour turnaround: their top 3 lanes quoted against DAT iQ market data with our margin disclosed."},
        {"offer": "24-hour onboarding", "detail": "Broker-shipper agreement, COI, W-9 and portal access returned within one business day."},
        {"offer": "90-day fixed pricing on primary lanes", "detail": "Rate stability spot brokers won't offer — powered by our margin model."},
        {"offer": "Dedicated capacity commitment", "detail": "Named carriers from Doug's bench committed to recurring lanes — trucks that show up."},
        {"offer": "Detention advocacy", "detail": "We fight for and pass through carrier detention honestly — drivers prioritize our freight because of it."},
        {"offer": "Net-30 respected, zero fee creep", "detail": "No fuel surcharge games, no hidden accessorials. The quote is the invoice."},
        {"offer": "Quarterly business review", "detail": "Lane analytics, on-time scorecard, market forecast and open-book margin — free."},
    ],
    "sourcing_channels": [
        {"channel": "Founder warm network", "how": "60 1:1 outreaches to former colleagues across MN industrials. Highest close rate of any channel (~7%)."},
        {"channel": "Load-board intelligence", "how": "Watch DAT/Truckstop for shipper-direct postings — then call the SHIPPER to go direct next time. The board is a prospecting database, not a freight source."},
        {"channel": "Carrier referrals", "how": "Doug's owner-operator network hauls for shippers whose brokers drop balls. Carriers know which docks are underserved."},
        {"channel": "MNI / manufacturers directories", "how": "Minnesota Manufacturers Register lists every plant, product and traffic manager. Filter by SIC codes that ship FTL."},
        {"channel": "Import/export records", "how": "Customs data (ImportYeti-style) reveals inbound container volume = drayage + domestic legs to quote."},
        {"channel": "Industrial-park canvassing", "how": "Drive the parks in Brooklyn Park / Rogers / Shakopee. Count dock doors, note carrier trailers, drop the brochure with the shipping office."},
        {"channel": "Trade associations & events", "how": "MN Trucking Assoc, CSCMP MN Roundtable, MHEDA. Logistics managers attend; brokers who show up win routing-guide slots."},
        {"channel": "LinkedIn outbound", "how": "Sales-Nav search 'logistics manager' + 'shipping supervisor' within 50mi of Minneapolis. 2 value-posts/week make cold DMs warm."},
        {"channel": "Referral partnerships", "how": "Customs brokers, freight forwarders, 3PL warehouses and packaging suppliers all get asked 'know a good truck broker?' — build a 10% referral circle."},
        {"channel": "Podcast + inbound", "how": "Orisei Freight Brief positions the desk as the MN freight authority; every guest is a prospect or a referrer."},
    ],
    "what_shippers_want": [
        "Capacity that shows up — shippers rank tender acceptance #1. Orisei answer: committed carriers on recurring lanes + surge capacity from the owner-operator network (98% acceptance target).",
        "On-time performance — OTP/OTD is the scorecard metric that gets you fired or promoted on the routing guide. Orisei answer: ≥96% OTP / ≥95% OTD, tracked per load, published in the QBR scorecard.",
        "Speed-to-quote — the #1 stated reason shippers switch brokers. Orisei answer: 15-minute quote SLA, market-benchmarked via the Quote Builder.",
        "Proactive communication — shippers hate chasing updates. Orisei answer: exception alerts before they ask, at pickup / transit / delivery, from a named human.",
        "Real-time visibility — 'where's my truck?' should never need a phone call. Orisei answer: free portal with live GPS, ETAs, and POD within 1 hour.",
        "Honest, stable pricing — no gouging when the market tightens. Orisei answer: 90-day fixed pricing on primary lanes, indexed FSC, open-book margin at QBR.",
        "Painless claims — one bad claim experience ends relationships. Orisei answer: acknowledged ≤24h, resolved ≤30 days target, funded reserve.",
        "Billing accuracy — invoice disputes burn more goodwill than late trucks. Orisei answer: quote = invoice, ≥99% accuracy, disputes answered in 1 business day.",
        "Compliance & financial stability — shippers vet the broker's bond, insurance and carrier standards. Orisei answer: BMC-84 $75K, 100% vetted carriers, written no-double-broker pledge.",
        "A single accountable human — not a rotating rep or ticket queue. Orisei answer: dedicated AM, founder's cell on the rate con, 24/7 escalation.",
    ],
    "outreach_tips": [
        "Call 7:15–8:30 AM — logistics managers plan their day early and gatekeepers aren't in yet.",
        "Lead with a specific lane and rate, never a capability pitch: 'I can cover your Minneapolis→Chicago dry van at $1,850 all-in this week.'",
        "Reference their actual freight (from board postings or dock observation) — instant credibility.",
        "Ask for the overflow/backup slot, not the primary. Get on the routing guide as #2, then out-service the incumbent.",
        "It takes 8–12 touches to convert a cold shipper. Most brokers quit at 3. The pipeline discipline IS the edge.",
        "Quote in under 15 minutes. Speed-to-quote is the #1 stated reason shippers switch brokers.",
        "Win the trial load, then be flawless: early check calls, proactive ETA updates, POD within the hour of delivery.",
        "After the first flawless load, ask for two things: the next load and one referral.",
        "Never bad-mouth the incumbent broker. Be the calm, reliable alternative for the day they fail.",
        "Re-touch dormant leads quarterly with a lane-rate update — markets shift and yesterday's 'no' becomes today's 'send me a quote'.",
        "Track every touch in the CRM. Next-action date on every prospect, no exceptions.",
        "Sell the QBR: 'even if you never give us a load, take the free lane benchmark' — it opens 40% of doors.",
    ],
}


class ProspectIn(BaseModel):
    company: str
    contact_name: str = ""
    title: str = ""
    email: str = ""
    phone: str = ""
    city: str = ""
    state: str = "MN"
    industry: str = ""
    est_loads_per_week: int = 0
    lanes: str = ""
    source: str = "cold"
    credit_score: Optional[int] = None
    stage: str = "lead"
    notes: str = ""
    next_action: str = ""
    next_action_date: str = ""


class ProspectPatch(BaseModel):
    company: Optional[str] = None
    contact_name: Optional[str] = None
    title: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    industry: Optional[str] = None
    est_loads_per_week: Optional[int] = None
    lanes: Optional[str] = None
    source: Optional[str] = None
    credit_score: Optional[int] = None
    stage: Optional[str] = None
    notes: Optional[str] = None
    next_action: Optional[str] = None
    next_action_date: Optional[str] = None


class TouchIn(BaseModel):
    kind: str = "call"
    note: str = ""


class OutreachIn(BaseModel):
    channel: str = Field("email", pattern="^(email|call|linkedin)$")


SEED = [
    {"company": "Viking Beverage Co", "contact_name": "Marcy Holt", "title": "Logistics Manager", "city": "Minneapolis", "industry": "Beverage / CPG", "est_loads_per_week": 12, "lanes": "MSP→Chicago · MSP→Kansas City", "source": "warm", "credit_score": 92, "stage": "quoted", "notes": "Ex-Tennant contact. Wants 90-day fixed pricing on Chicago lane.", "next_action": "Send lane benchmark PDF", "email": "m.holt@vikingbev.example.com", "phone": "(612) 555-0141"},
    {"company": "Great Lakes Pet Foods", "contact_name": "Dan Okafor", "title": "Shipping Supervisor", "city": "St. Cloud", "industry": "Pet food (reefer)", "est_loads_per_week": 8, "lanes": "STC→Denver · STC→Dallas (reefer)", "source": "board-intel", "credit_score": 88, "stage": "contacted", "notes": "Posts direct on DAT Tuesdays. Incumbent broker missing pickups.", "next_action": "Call 7:30 AM Tuesday before they post", "email": "d.okafor@glpetfoods.example.com", "phone": "(320) 555-0177"},
    {"company": "TwinCity Fabricators", "contact_name": "Sue Lindqvist", "title": "Traffic Manager", "city": "Rogers", "industry": "Fabricated metals (flatbed)", "est_loads_per_week": 6, "lanes": "Rogers→Houston · Rogers→Atlanta (flatbed)", "source": "canvassing", "credit_score": 90, "stage": "trial", "notes": "Trial: 4 flatbed loads at fixed rate. Load 2 delivers Friday.", "next_action": "Proactive ETA update Friday AM", "email": "slindqvist@tcfab.example.com", "phone": "(763) 555-0122"},
    {"company": "Prairie Ag Supply", "contact_name": "Bill Tanner", "title": "Ops Director", "city": "Mankato", "industry": "Ag inputs", "est_loads_per_week": 10, "lanes": "Mankato→Fargo · Mankato→Sioux Falls", "source": "referral", "credit_score": 85, "stage": "lead", "notes": "Referred by Doug's carrier contact. Seasonal surge in spring.", "next_action": "Intro call + brochure", "email": "btanner@prairieag.example.com", "phone": "(507) 555-0165"},
    {"company": "Medline North", "contact_name": "Grace Yang", "title": "Sr. Logistics Analyst", "city": "Maple Grove", "industry": "Medical devices", "est_loads_per_week": 15, "lanes": "Maple Grove→Memphis · inbound Chicago", "source": "linkedin", "credit_score": 95, "stage": "meeting", "notes": "Booked 20-min discovery Thursday. High-value, net-45 terms.", "next_action": "Discovery call Thursday 10 AM", "email": "gyang@medlinenorth.example.com", "phone": "(763) 555-0198"},
    {"company": "North Star Millwork", "contact_name": "Pete Aronson", "title": "Owner", "city": "Duluth", "industry": "Building products", "est_loads_per_week": 4, "lanes": "Duluth→Milwaukee · Duluth→Des Moines", "source": "event", "credit_score": 82, "stage": "contracted", "notes": "Signed after MN Trucking Assoc meet. First recurring lane live.", "next_action": "QBR prep for Q3", "email": "pete@nsmillwork.example.com", "phone": "(218) 555-0133"},
]


def build_shipper_finder_router(
    *,
    db,
    get_current_user: Callable,
    emergent_llm_key: Optional[str],
    LlmChat,        # noqa: N803
    UserMessage,    # noqa: N803
) -> APIRouter:
    router = APIRouter(prefix="/shipper-finder")
    col = db.shipper_prospects

    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    async def _seed_if_empty():
        if await col.count_documents({}) == 0:
            docs = []
            for s in SEED:
                docs.append({**s, "id": f"SHP-{uuid.uuid4().hex[:8].upper()}",
                             "next_action_date": "", "touches": [],
                             "created_at": _now(), "updated_at": _now(),
                             "state": s.get("state", "MN")})
            await col.insert_many(docs)

    @router.get("/prospects")
    async def list_prospects(_=Depends(get_current_user)):
        await _seed_if_empty()
        rows = await col.find({}, {"_id": 0}).sort("updated_at", -1).to_list(500)
        counts = {s: 0 for s in STAGES}
        for r in rows:
            counts[r.get("stage", "lead")] = counts.get(r.get("stage", "lead"), 0) + 1
        pipeline_loads = sum(r.get("est_loads_per_week", 0) for r in rows if r.get("stage") not in ("lost",))
        return {"prospects": rows, "counts": counts, "stages": STAGES,
                "pipeline_loads_per_week": pipeline_loads,
                "contracted_loads_per_week": sum(r.get("est_loads_per_week", 0) for r in rows if r.get("stage") == "contracted")}

    @router.post("/prospects")
    async def create_prospect(payload: ProspectIn, _=Depends(get_current_user)):
        if payload.stage not in STAGES:
            raise HTTPException(400, "Invalid stage")
        doc = {**payload.model_dump(), "id": f"SHP-{uuid.uuid4().hex[:8].upper()}",
               "touches": [], "created_at": _now(), "updated_at": _now()}
        await col.insert_one({**doc})
        doc.pop("_id", None)
        return {"ok": True, "prospect": doc}

    @router.patch("/prospects/{pid}")
    async def update_prospect(pid: str, payload: ProspectPatch, _=Depends(get_current_user)):
        updates = {k: v for k, v in payload.model_dump().items() if v is not None}
        if "stage" in updates and updates["stage"] not in STAGES:
            raise HTTPException(400, "Invalid stage")
        updates["updated_at"] = _now()
        res = await col.update_one({"id": pid}, {"$set": updates})
        if res.matched_count == 0:
            raise HTTPException(404, "Prospect not found")
        doc = await col.find_one({"id": pid}, {"_id": 0})
        return {"ok": True, "prospect": doc}

    @router.delete("/prospects/{pid}")
    async def delete_prospect(pid: str, _=Depends(get_current_user)):
        res = await col.delete_one({"id": pid})
        if res.deleted_count == 0:
            raise HTTPException(404, "Prospect not found")
        return {"ok": True}

    @router.post("/prospects/{pid}/touch")
    async def log_touch(pid: str, payload: TouchIn, user=Depends(get_current_user)):
        touch = {"kind": payload.kind, "note": payload.note, "at": _now(),
                 "by": getattr(user, "name", None) or (user.get("name") if isinstance(user, dict) else "desk")}
        res = await col.update_one({"id": pid}, {"$push": {"touches": touch}, "$set": {"updated_at": _now()}})
        if res.matched_count == 0:
            raise HTTPException(404, "Prospect not found")
        return {"ok": True, "touch": touch}

    @router.get("/playbook")
    async def playbook(_=Depends(get_current_user)):
        return PLAYBOOK

    @router.post("/prospects/{pid}/outreach")
    async def generate_outreach(pid: str, payload: OutreachIn, _=Depends(get_current_user)):
        if not emergent_llm_key:
            raise HTTPException(500, "EMERGENT_LLM_KEY not configured")
        p = await col.find_one({"id": pid}, {"_id": 0})
        if not p:
            raise HTTPException(404, "Prospect not found")
        fmt = {"email": "a cold email (subject line + body, under 150 words)",
               "call": "a 60-second cold-call script with a pattern interrupt opener and one qualifying question",
               "linkedin": "a LinkedIn DM under 80 words"}[payload.channel]
        system = (
            "You are the shipper-acquisition copywriter for Orisei Freight Solutions, a three-founder Minneapolis "
            "freight brokerage (13yr shipper-side operator, 12yr owner-operator, in-house TMS engineer). "
            "Competitive edges: no-double-broker pledge, open-book margin, free live-tracking portal, 24hr onboarding, "
            "fixed-rate 4-load trial with margin guarantee, free lane benchmark PDF vs DAT market data. "
            "Write like a blunt, helpful freight operator — zero corporate fluff, one specific ask. "
            "Lead with THEIR lanes and pain, not our features."
        )
        prompt = (
            f"Write {fmt} to this prospect:\n"
            f"Company: {p['company']} ({p.get('industry','')}) in {p.get('city','')}, {p.get('state','MN')}\n"
            f"Contact: {p.get('contact_name','')} — {p.get('title','')}\n"
            f"Lanes: {p.get('lanes','unknown')} · Est volume: {p.get('est_loads_per_week',0)} loads/wk\n"
            f"Source/context: {p.get('source','cold')} · Notes: {p.get('notes','')}\n"
            f"Pipeline stage: {p.get('stage','lead')} — match the tone to that stage."
        )
        try:
            chat = LlmChat(api_key=emergent_llm_key,
                           session_id=f"shipper-outreach-{uuid.uuid4().hex[:8]}",
                           system_message=system).with_model("anthropic", "claude-sonnet-4-5-20250929")
            reply = await chat.send_message(UserMessage(text=prompt))
            return {"ok": True, "channel": payload.channel, "script": reply}
        except Exception as e:
            logger.exception("Outreach generation failed")
            raise HTTPException(502, f"AI provider error: {e}")

    @router.get("/brochure.pdf")
    async def shipper_brochure(_=Depends(get_current_user)):
        from .shipper_brochure import build_shipper_brochure_pdf
        pdf_bytes = build_shipper_brochure_pdf()
        return StreamingResponse(
            io.BytesIO(pdf_bytes), media_type="application/pdf",
            headers={"Content-Disposition": 'attachment; filename="Ship_With_Orisei_Brochure.pdf"'})

    return router
