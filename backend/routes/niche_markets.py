"""routes.niche_markets — MN High-Margin Niche Market Network.

Operationalizes the 10-vertical Minnesota niche plan: tiered vertical playbook,
named target-company CRM pipeline, AI battle cards + personalized pitch emails
(Claude via Emergent key), live outreach through Resend, and a phase tracker
against the 765 loads/month · $4.5M Year-1 goal.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

log = logging.getLogger("tennant_tms.niche_markets")

MODEL = ("anthropic", "claude-sonnet-4-5-20250929")
STAGES = ["target", "researched", "contacted", "meeting", "pilot_proposed", "pilot", "contracted"]
STAGE_PROB = {"target": 0.02, "researched": 0.05, "contacted": 0.12,
              "meeting": 0.30, "pilot_proposed": 0.45, "pilot": 0.60, "contracted": 1.0}
OUTCOMES = ["active", "maybe", "no"]
FEATURE_STATUSES = ["done", "in_progress", "missing"]
PLAN_GOALS = {"loads_per_month": 765, "y1_revenue": 4_500_000}

VERTICALS: Dict[str, Dict[str, Any]] = {
    "medical_devices": {
        "label": "Medical Device Manufacturing", "tier": 1,
        "margin_per_load": [800, 2000], "margin_pct": "40%+",
        "pilot_ask": "10–20 loads/month", "contact_role": "VP Logistics / Supply Chain",
        "y1_per_client": [120_000, 300_000],
        "why": ["High-value freight ($5K–$50K per load, small volume)",
                "Temperature-controlled / time-critical — premium rates",
                "Dedicated repeat lanes, 3–5 year agreements — not spot market"],
        "pitch": "Dedicated capacity for your high-value shipments — guaranteed next-day arrival, "
                 "temperature control, and branded shipper-facing tracking for your customers.",
    },
    "food_beverage": {
        "label": "Food & Beverage Manufacturing", "tier": 1,
        "margin_per_load": [400, 800], "margin_pct": "20–30%",
        "pilot_ask": "50–100 loads/month", "contact_role": "Transportation Manager",
        "y1_per_client": [300_000, 600_000],
        "why": ["High volume — 500+ loads/month per shipper",
                "Predictable daily lanes; dedicated capacity beats spot volatility",
                "Multi-year contract relationships"],
        "pitch": "Dedicated weekly volume contract — we guarantee capacity, pricing, and service "
                 "level so you lock in your freight costs.",
    },
    "electronics": {
        "label": "Electronics & High-Tech", "tier": 1,
        "margin_per_load": [600, 1500], "margin_pct": "30–40%",
        "pilot_ask": "20–50 loads/month", "contact_role": "VP Logistics / Procurement",
        "y1_per_client": [150_000, 450_000],
        "why": ["Time-critical freight with damage risk — premium rates",
                "High value per load ($3K–$10K), cross-dock dedicated lanes",
                "Year-round volume, not seasonal"],
        "pitch": "Dedicated carrier for high-value electronics — real-time tracking, climate "
                 "protection, and cargo insurance on every load.",
    },
    "pharma_healthcare": {
        "label": "Pharmaceutical & Healthcare Distribution", "tier": 2,
        "margin_per_load": [800, 2000], "margin_pct": "35%+",
        "pilot_ask": "10–30 loads/month", "contact_role": "Director of Transportation",
        "y1_per_client": [120_000, 360_000],
        "why": ["Regulated freight — DEA compliance, traceability, cold chain",
                "Compliance requirements keep competitors out — sticky, multi-year",
                "Premium margins on regulated lanes"],
        "pitch": "Compliance-ready dedicated carrier — cold chain, traceability, and regulatory "
                 "documentation handled end to end.",
    },
    "construction_equipment": {
        "label": "Construction & Heavy Equipment", "tier": 2,
        "margin_per_load": [500, 1200], "margin_pct": "25–35%",
        "pilot_ask": "30–75 loads/month", "contact_role": "Fleet / Logistics Manager",
        "y1_per_client": [180_000, 540_000],
        "why": ["Heavy, bulky freight on dedicated repeat lanes",
                "Predictable manufacturing-schedule volume",
                "Long OEM relationships"],
        "pitch": "Dedicated capacity for oversized and heavy loads — equipment experience and "
                 "specialized handling on every move.",
    },
    "retail_ecommerce": {
        "label": "Retail & E-Commerce Distribution", "tier": 2,
        "margin_per_load": [200, 400], "margin_pct": "15–20%",
        "pilot_ask": "200–400 loads/month", "contact_role": "Director of Transportation",
        "y1_per_client": [600_000, 1_200_000],
        "why": ["Extremely high volume — 1,000+ loads/month per shipper",
                "Locked contracts; they buy predictability",
                "Lower per-load margin, but 300 loads × $300 = $90K/month from ONE shipper"],
        "pitch": "Dedicated capacity contract for your network — we scale to 500+ loads/week on "
                 "your lanes with fixed pricing.",
    },
    "craft_beverage": {
        "label": "Craft Beverage & Specialty Food", "tier": 3,
        "margin_per_load": [800, 1500], "margin_pct": "35–40%",
        "pilot_ask": "10–20 loads/month", "contact_role": "Operations Manager",
        "y1_per_client": [120_000, 300_000],
        "why": ["High-margin loads on weekly distributor routes",
                "Craft market growing 8–10% annually",
                "Small companies stay loyal to reliable carriers"],
        "pitch": "Dedicated weekly distribution carrier — we understand craft beverage logistics "
                 "and scale with your growth.",
    },
    "agriculture": {
        "label": "Agriculture & Farm Equipment", "tier": 3,
        "margin_per_load": [600, 1200], "margin_pct": "30–40%",
        "pilot_ask": "100–200 loads/month (peak season)", "contact_role": "Logistics Manager",
        "y1_per_client": [150_000, 400_000],
        "why": ["Planting/harvest season = huge surge demand at premium rates",
                "Predictable farm-to-elevator and dealer-to-farm lanes",
                "Farmers stick with the distributors that show up"],
        "pitch": "Peak-season capacity for ag logistics — we scale up during planting and harvest "
                 "so you never miss a window.",
    },
    "chemicals": {
        "label": "Chemical & Industrial Distribution", "tier": 3,
        "margin_per_load": [1000, 2500], "margin_pct": "30–45%",
        "pilot_ask": "20–50 loads/month", "contact_role": "Transportation Manager",
        "y1_per_client": [240_000, 600_000],
        "why": ["Hazmat freight pays a premium — $1,000–$2,500/load",
                "DOT/EPA compliance keeps competitors out",
                "Dedicated, predictable lanes"],
        "pitch": "Hazmat-certified dedicated carrier — compliance, documentation, and specialized "
                 "handling built into every load.",
    },
    "paper_packaging": {
        "label": "Paper & Packaging Distribution", "tier": 3,
        "margin_per_load": [400, 800], "margin_pct": "25–30%",
        "pilot_ask": "50–100 loads/month", "contact_role": "Logistics Manager",
        "y1_per_client": [240_000, 600_000],
        "why": ["High-volume, consistent mill-to-converter lanes",
                "Dedicated capacity contracts — they buy predictability",
                "Year-round volume with seasonal upside"],
        "pitch": "Dedicated capacity for your regional distribution — we handle paper and "
                 "packaging weight and cube efficiently.",
    },
}

# Realistic named targets. phase 1/2/3 = the recommended target sequence;
# phase 0 = bench (work when bandwidth allows). Notes flag realism corrections.
SEED_TARGETS: List[Dict[str, Any]] = [
    # --- Phase 1 · Quick wins (Months 1–2) ---
    {"name": "The Toro Company", "vertical": "construction_equipment", "city": "Bloomington, MN",
     "phase": 1, "est_loads_month": 30, "margin_per_load_est": 500,
     "notes": "Turf equipment, distribution-heavy. Phase-1 anchor: pilot 30 loads/mo."},
    {"name": "Summit Brewing Co", "vertical": "craft_beverage", "city": "St. Paul, MN",
     "phase": 1, "est_loads_month": 15, "margin_per_load_est": 1000,
     "notes": "Largest MN craft brewer. Weekly distributor routes across Upper Midwest."},
    {"name": "Bobcat Company", "vertical": "construction_equipment", "city": "Litchfield, MN",
     "phase": 1, "est_loads_month": 40, "margin_per_load_est": 600,
     "notes": "Compact equipment. Litchfield MN plant + Gwinner ND HQ — flatbed/step-deck lanes."},
    # --- Phase 2 · Scale (Months 3–6) ---
    {"name": "Land O'Lakes", "vertical": "food_beverage", "city": "Arden Hills, MN",
     "phase": 2, "est_loads_month": 75, "margin_per_load_est": 500,
     "notes": "Dairy co-op. Reefer-heavy; WinField ag-inputs division is a second door in."},
    {"name": "Medtronic", "vertical": "medical_devices", "city": "Fridley, MN",
     "phase": 2, "est_loads_month": 20, "margin_per_load_est": 1250,
     "notes": "Operational HQ in Fridley. High-value, time-critical device freight."},
    {"name": "Cargill", "vertical": "agriculture", "city": "Wayzata, MN",
     "phase": 2, "est_loads_month": 100, "margin_per_load_est": 250,
     "notes": "Seasonal ag surge play — planting/harvest overflow capacity."},
    # --- Phase 3 · Consolidate (Months 7–12) ---
    {"name": "Target Corporation", "vertical": "retail_ecommerce", "city": "Minneapolis, MN",
     "phase": 3, "est_loads_month": 300, "margin_per_load_est": 250,
     "notes": "HQ + regional DCs. Enter via routing-guide backup slot, not primary."},
    {"name": "Best Buy", "vertical": "retail_ecommerce", "city": "Richfield, MN",
     "phase": 3, "est_loads_month": 200, "margin_per_load_est": 250,
     "notes": "Cross-dock network. High-value electronics handling is the wedge."},
    {"name": "General Mills", "vertical": "food_beverage", "city": "Golden Valley, MN",
     "phase": 3, "est_loads_month": 100, "margin_per_load_est": 500,
     "notes": "Massive outbound DC freight. Long procurement cycle — start touches in Month 3."},
    # --- Bench · Medical devices ---
    {"name": "Abbott (St. Jude Medical campus)", "vertical": "medical_devices", "city": "St. Paul, MN",
     "phase": 0, "est_loads_month": 15, "margin_per_load_est": 1200,
     "notes": "REALISM: St. Jude Medical was acquired by Abbott (2017) — pitch Abbott Structural Heart, St. Paul campus."},
    {"name": "Boston Scientific", "vertical": "medical_devices", "city": "Maple Grove, MN",
     "phase": 0, "est_loads_month": 18, "margin_per_load_est": 1200,
     "notes": "Major Maple Grove + Arden Hills campuses. Added — larger MN freight footprint than most on the original list."},
    {"name": "Teleflex (Vascular Solutions)", "vertical": "medical_devices", "city": "Maple Grove, MN",
     "phase": 0, "est_loads_month": 8, "margin_per_load_est": 1000,
     "notes": "REALISM: Vascular Solutions acquired by Teleflex (2017) — Maple Grove operations."},
    {"name": "Surmodics", "vertical": "medical_devices", "city": "Eden Prairie, MN",
     "phase": 0, "est_loads_month": 6, "margin_per_load_est": 900,
     "notes": "Medical coatings — small, precision freight. Good pilot-sized account."},
    {"name": "Tactile Medical", "vertical": "medical_devices", "city": "Minneapolis, MN",
     "phase": 0, "est_loads_month": 6, "margin_per_load_est": 900,
     "notes": "Compression therapy devices. Direct-to-clinic distribution."},
    # --- Bench · Food & beverage ---
    {"name": "Hormel Foods", "vertical": "food_beverage", "city": "Austin, MN",
     "phase": 0, "est_loads_month": 80, "margin_per_load_est": 450,
     "notes": "Meat processing — reefer lanes out of Austin MN."},
    {"name": "Schwan's Company", "vertical": "food_beverage", "city": "Marshall, MN",
     "phase": 0, "est_loads_month": 60, "margin_per_load_est": 500,
     "notes": "Frozen food — deep reefer network from Marshall MN. Replaces vague 'Ims Bakery' seed."},
    {"name": "Post Consumer Brands", "vertical": "food_beverage", "city": "Lakeville, MN",
     "phase": 0, "est_loads_month": 50, "margin_per_load_est": 450,
     "notes": "Cereal HQ + plant in Lakeville/Northfield. Dry-van dense."},
    # --- Bench · Electronics ---
    {"name": "Digi-Key Electronics", "vertical": "electronics", "city": "Thief River Falls, MN",
     "phase": 0, "est_loads_month": 40, "margin_per_load_est": 800,
     "notes": "REALISM ADD: one of the largest electronics distributors in the US, shipping from northern MN daily. Replaces defunct Imation."},
    {"name": "Honeywell", "vertical": "electronics", "city": "Golden Valley, MN",
     "phase": 0, "est_loads_month": 25, "margin_per_load_est": 800,
     "notes": "Aerospace / industrial controls (original list typo 'Honewell')."},
    {"name": "3M", "vertical": "electronics", "city": "Maplewood, MN",
     "phase": 0, "est_loads_month": 60, "margin_per_load_est": 700,
     "notes": "Diverse manufacturing; enter through one division (safety or electronics), not corporate."},
    {"name": "TD SYNNEX", "vertical": "electronics", "city": "Bloomington, MN (regional)",
     "phase": 0, "est_loads_month": 30, "margin_per_load_est": 700,
     "notes": "REALISM: Tech Data merged into TD SYNNEX (2021) — pitch the combined entity's regional DC freight."},
    # --- Bench · Pharma / healthcare ---
    {"name": "McKesson (regional DC)", "vertical": "pharma_healthcare", "city": "Twin Cities metro",
     "phase": 0, "est_loads_month": 20, "margin_per_load_est": 1200,
     "notes": "Healthcare distribution. Compliance story is the door-opener."},
    {"name": "Cardinal Health (regional hub)", "vertical": "pharma_healthcare", "city": "Twin Cities metro",
     "phase": 0, "est_loads_month": 20, "margin_per_load_est": 1200,
     "notes": "Pharma distributor. Multi-year contracts once in."},
    {"name": "Upsher-Smith Laboratories", "vertical": "pharma_healthcare", "city": "Maple Grove, MN",
     "phase": 0, "est_loads_month": 10, "margin_per_load_est": 1000,
     "notes": "REALISM ADD: actual MN pharma manufacturer — replaces unverifiable 'Aspenmark'."},
    {"name": "Padagis", "vertical": "pharma_healthcare", "city": "Minneapolis, MN",
     "phase": 0, "est_loads_month": 10, "margin_per_load_est": 1000,
     "notes": "REALISM ADD: generic pharma with Minneapolis operations."},
    # --- Bench · Construction / heavy equipment ---
    {"name": "CNH Industrial (Benson plant)", "vertical": "construction_equipment", "city": "Benson, MN",
     "phase": 0, "est_loads_month": 25, "margin_per_load_est": 800,
     "notes": "REALISM: CNH has an actual MN plant in Benson (application equipment) — closer than Racine WI."},
    {"name": "Ziegler CAT", "vertical": "construction_equipment", "city": "Bloomington, MN",
     "phase": 0, "est_loads_month": 20, "margin_per_load_est": 700,
     "notes": "CAT dealer network — heavy-haul + parts distribution across MN/IA."},
    {"name": "Daikin Applied", "vertical": "construction_equipment", "city": "Plymouth, MN",
     "phase": 0, "est_loads_month": 20, "margin_per_load_est": 650,
     "notes": "REALISM: HVAC manufacturing actually headquartered in MN — replaces Lennox (TX)."},
    # --- Bench · Retail ---
    {"name": "Amazon (MSP fulfillment)", "vertical": "retail_ecommerce", "city": "Shakopee, MN",
     "phase": 0, "est_loads_month": 150, "margin_per_load_est": 200,
     "notes": "Relay/middle-mile program — apps-based entry, thin but scalable."},
    {"name": "Fleet Farm", "vertical": "retail_ecommerce", "city": "Appleton, WI / MN DCs",
     "phase": 0, "est_loads_month": 60, "margin_per_load_est": 300,
     "notes": "REALISM ADD: Upper-Midwest retail DC network — replaces defunct Heilig-Meyers and non-MN Crayola."},
    # --- Bench · Craft beverage ---
    {"name": "Surly Brewing", "vertical": "craft_beverage", "city": "Minneapolis, MN",
     "phase": 0, "est_loads_month": 10, "margin_per_load_est": 900,
     "notes": "Destination brewery + regional distribution."},
    {"name": "Indeed Brewing", "vertical": "craft_beverage", "city": "Minneapolis, MN",
     "phase": 0, "est_loads_month": 6, "margin_per_load_est": 850,
     "notes": "Northeast Mpls — smaller, loyal once served well."},
    {"name": "Bent Paddle Brewing", "vertical": "craft_beverage", "city": "Duluth, MN",
     "phase": 0, "est_loads_month": 6, "margin_per_load_est": 900,
     "notes": "Duluth → Twin Cities lane pairs with Twin Ports backhauls."},
    {"name": "Fulton Beer", "vertical": "craft_beverage", "city": "Minneapolis, MN",
     "phase": 0, "est_loads_month": 6, "margin_per_load_est": 850,
     "notes": "North Loop brewery, statewide distribution."},
    # --- Bench · Agriculture ---
    {"name": "CHS Inc", "vertical": "agriculture", "city": "Inver Grove Heights, MN",
     "phase": 0, "est_loads_month": 80, "margin_per_load_est": 350,
     "notes": "Largest US ag co-op — hopper/flatbed/intermodal mix."},
    {"name": "AGCO (Jackson plant)", "vertical": "agriculture", "city": "Jackson, MN",
     "phase": 0, "est_loads_month": 20, "margin_per_load_est": 800,
     "notes": "REALISM: AGCO builds application equipment in Jackson MN — oversize/flatbed freight."},
    {"name": "RDO Equipment (Deere dealer network)", "vertical": "agriculture", "city": "MN/ND dealer network",
     "phase": 0, "est_loads_month": 15, "margin_per_load_est": 700,
     "notes": "John Deere dealer group — dealer-to-farm equipment moves."},
    # --- Bench · Chemicals ---
    {"name": "Hawkins Inc", "vertical": "chemicals", "city": "Roseville, MN",
     "phase": 0, "est_loads_month": 25, "margin_per_load_est": 1200,
     "notes": "REALISM ADD: MN-headquartered chemical distributor — best local chemical target on the board."},
    {"name": "Ecolab", "vertical": "chemicals", "city": "St. Paul, MN",
     "phase": 0, "est_loads_month": 40, "margin_per_load_est": 1000,
     "notes": "REALISM ADD: $15B St. Paul HQ — cleaning/water chemistry freight statewide."},
    {"name": "Brenntag Great Lakes", "vertical": "chemicals", "city": "Twin Cities metro",
     "phase": 0, "est_loads_month": 20, "margin_per_load_est": 1300,
     "notes": "Hazmat distributor — certification required before pitching."},
    {"name": "Univar Solutions", "vertical": "chemicals", "city": "Minneapolis, MN",
     "phase": 0, "est_loads_month": 20, "margin_per_load_est": 1300,
     "notes": "Chemical & specialty products distribution."},
    # --- Bench · Paper / packaging ---
    {"name": "Sappi North America (Cloquet mill)", "vertical": "paper_packaging", "city": "Cloquet, MN",
     "phase": 0, "est_loads_month": 40, "margin_per_load_est": 550,
     "notes": "REALISM: Sappi runs an actual MN mill in Cloquet — mill-outbound paper lanes."},
    {"name": "Packaging Corp of America (Int'l Falls)", "vertical": "paper_packaging", "city": "International Falls, MN",
     "phase": 0, "est_loads_month": 35, "margin_per_load_est": 550,
     "notes": "REALISM ADD: actual MN paper mill — long-haul lanes south, backhaul friendly."},
    {"name": "Smurfit Westrock (regional)", "vertical": "paper_packaging", "city": "Twin Cities metro",
     "phase": 0, "est_loads_month": 30, "margin_per_load_est": 500,
     "notes": "Corrugated — converter-to-brand lanes."},
    {"name": "Liberty Packaging", "vertical": "paper_packaging", "city": "Brooklyn Park, MN",
     "phase": 0, "est_loads_month": 20, "margin_per_load_est": 500,
     "notes": "REALISM ADD: MN-based corrugated packager in Brooklyn Park — warm-intro territory (Daniel's backyard)."},
]

PHASE_PLAN = {
    1: {"label": "Phase 1 · Quick Wins (Mo 1–2)", "loads_target": 85, "y1_revenue_target": 570_000},
    2: {"label": "Phase 2 · Scale (Mo 3–6)", "loads_target": 280, "y1_revenue_target": 1_620_000},
    3: {"label": "Phase 3 · Consolidate (Mo 7–12)", "loads_target": 765, "y1_revenue_target": 4_500_000},
}


# Ops-readiness enrichment for the 9 phase anchors (applied by _ensure_seed migration).
ANCHOR_READINESS: Dict[str, Dict[str, Any]] = {
    "The Toro Company": {"carriers_required": 6, "features_required": [
        {"name": "Flatbed/step-deck carrier bench (fixed rates)", "status": "in_progress"}]},
    "Summit Brewing Co": {"carriers_required": 3, "features_required": [
        {"name": "Weekly dedicated distributor routing", "status": "done"}]},
    "Bobcat Company": {"carriers_required": 8, "features_required": [
        {"name": "Oversize/permit load workflow", "status": "in_progress"}]},
    "Land O'Lakes": {"carriers_required": 12, "features_required": [
        {"name": "Reefer temp monitoring & alerts", "status": "missing"}]},
    "Medtronic": {"carriers_required": 4, "features_required": [
        {"name": "Temp-controlled tracking (telematics)", "status": "missing"},
        {"name": "High-value cargo insurance ($100K+)", "status": "in_progress"}]},
    "Cargill": {"carriers_required": 15, "features_required": [
        {"name": "Hopper/bulk carrier bench", "status": "missing"}]},
    "Target Corporation": {"carriers_required": 30, "features_required": [
        {"name": "Shipper portal real-time visibility", "status": "done"},
        {"name": "EDI 204/214 tendering", "status": "missing"}]},
    "Best Buy": {"carriers_required": 20, "features_required": [
        {"name": "Shipper portal real-time visibility", "status": "done"},
        {"name": "High-value electronics security protocol", "status": "in_progress"}]},
    "General Mills": {"carriers_required": 12, "features_required": [
        {"name": "EDI 204/214 tendering", "status": "missing"}]},
}



def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class TargetIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=160)
    vertical: str
    city: str = ""
    phase: int = Field(0, ge=0, le=3)
    est_loads_month: int = Field(10, ge=1, le=5000)
    margin_per_load_est: float = Field(400, ge=0)
    contact_name: str = ""
    contact_email: str = ""
    contact_phone: str = ""
    notes: str = ""


class TargetPatch(BaseModel):
    stage: Optional[str] = None
    outcome: Optional[str] = None                 # active | maybe | no
    decision_deadline: Optional[str] = None       # ISO date "" = none
    last_touchpoint: Optional[str] = None         # free text; auto-stamps last_touch_at
    carriers_required: Optional[int] = Field(None, ge=0, le=500)
    carriers_secured: Optional[int] = Field(None, ge=0, le=500)
    features_required: Optional[List[Dict[str, str]]] = None  # [{name, status}]
    phase: Optional[int] = Field(None, ge=0, le=3)
    est_loads_month: Optional[int] = None
    margin_per_load_est: Optional[float] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    notes: Optional[str] = None


class PitchIn(BaseModel):
    send: bool = False
    email: Optional[str] = None


def build_niche_markets_router(*, db, get_current_user: Callable) -> APIRouter:
    router = APIRouter(prefix="/niche-markets", tags=["niche-markets"])

    async def _ensure_seed():
        if await db.niche_targets.count_documents({}) == 0:
            rows = [{**t, "id": f"NM-{uuid.uuid4().hex[:8].upper()}", "stage": "target",
                     "contact_name": "", "contact_email": "", "contact_phone": "",
                     "battle_card": None, "last_pitch": None, "outreach_count": 0,
                     "is_sample": False, "created_at": _now_iso(), "updated_at": _now_iso()}
                    for t in SEED_TARGETS]
            await db.niche_targets.insert_many(rows)
            log.info("Seeded %d MN niche-market targets", len(rows))
        # migration: ops-readiness fields for docs created before v2
        missing = await db.niche_targets.count_documents({"outcome": {"$exists": False}})
        if missing:
            rows = await db.niche_targets.find({"outcome": {"$exists": False}}).to_list(500)
            for r in rows:
                enrich = ANCHOR_READINESS.get(r["name"], {})
                await db.niche_targets.update_one({"id": r["id"]}, {"$set": {
                    "outcome": "active", "decision_deadline": "",
                    "last_touchpoint": "", "last_touch_at": r.get("last_outreach_at") or "",
                    "carriers_required": enrich.get("carriers_required",
                                                    max(2, round(r.get("est_loads_month", 10) / 8))),
                    "carriers_secured": 0,
                    "features_required": enrich.get("features_required", [])}})
            log.info("Migrated %d niche targets to ops-readiness schema", missing)

    def _y1_potential(t: Dict[str, Any]) -> float:
        return round(t.get("est_loads_month", 0) * t.get("margin_per_load_est", 0) * 12, 2)

    @router.get("/playbook")
    async def playbook(_=Depends(get_current_user)):
        return {"verticals": [{"key": k, **v} for k, v in VERTICALS.items()],
                "stages": STAGES, "stage_probabilities": STAGE_PROB,
                "outcomes": OUTCOMES, "feature_statuses": FEATURE_STATUSES,
                "phase_plan": [{"phase": p, **v} for p, v in PHASE_PLAN.items()],
                "goals": PLAN_GOALS}

    @router.get("/targets")
    async def list_targets(vertical: Optional[str] = None, phase: Optional[int] = None,
                           _=Depends(get_current_user)):
        await _ensure_seed()
        q: Dict[str, Any] = {}
        if vertical:
            q["vertical"] = vertical
        if phase is not None:
            q["phase"] = phase
        rows = await db.niche_targets.find(q, {"_id": 0}).sort([("phase", -1), ("name", 1)]).to_list(500)
        for r in rows:
            r["y1_potential"] = _y1_potential(r)
        return {"targets": rows, "count": len(rows)}

    @router.post("/targets")
    async def create_target(payload: TargetIn, _=Depends(get_current_user)):
        if payload.vertical not in VERTICALS:
            raise HTTPException(400, f"vertical must be one of {list(VERTICALS)}")
        doc = {**payload.model_dump(), "id": f"NM-{uuid.uuid4().hex[:8].upper()}",
               "stage": "target", "battle_card": None, "last_pitch": None,
               "outcome": "active", "decision_deadline": "", "last_touchpoint": "",
               "last_touch_at": "", "carriers_required": max(2, round(payload.est_loads_month / 8)),
               "carriers_secured": 0, "features_required": [],
               "outreach_count": 0, "is_sample": False,
               "created_at": _now_iso(), "updated_at": _now_iso()}
        await db.niche_targets.insert_one(dict(doc))
        doc["y1_potential"] = _y1_potential(doc)
        return {"ok": True, "target": doc}

    @router.patch("/targets/{tid}")
    async def patch_target(tid: str, payload: TargetPatch, _=Depends(get_current_user)):
        patch = payload.model_dump(exclude_unset=True)
        if not patch:
            raise HTTPException(400, "Nothing to update")
        if "stage" in patch and patch["stage"] not in STAGES:
            raise HTTPException(400, f"stage must be one of {STAGES}")
        if "outcome" in patch and patch["outcome"] not in OUTCOMES:
            raise HTTPException(400, f"outcome must be one of {OUTCOMES}")
        if "features_required" in patch:
            for f in patch["features_required"] or []:
                if f.get("status") not in FEATURE_STATUSES:
                    raise HTTPException(400, f"feature status must be one of {FEATURE_STATUSES}")
        if patch.get("last_touchpoint"):
            patch["last_touch_at"] = _now_iso()
        patch["updated_at"] = _now_iso()
        r = await db.niche_targets.find_one_and_update(
            {"id": tid}, {"$set": patch}, return_document=True, projection={"_id": 0})
        if not r:
            raise HTTPException(404, "Target not found")
        r["y1_potential"] = _y1_potential(r)
        return {"ok": True, "target": r}

    @router.delete("/targets/{tid}")
    async def delete_target(tid: str, _=Depends(get_current_user)):
        r = await db.niche_targets.delete_one({"id": tid})
        if r.deleted_count == 0:
            raise HTTPException(404, "Target not found")
        return {"ok": True}

    async def _claude(system: str, prompt: str) -> str:
        key = os.environ.get("EMERGENT_LLM_KEY")
        if not key:
            raise HTTPException(503, "AI key not configured")
        import asyncio
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(api_key=key, session_id=f"niche-{uuid.uuid4().hex[:8]}",
                       system_message=system).with_model(*MODEL)
        try:
            return str(await asyncio.wait_for(chat.send_message(UserMessage(text=prompt)), timeout=90)).strip()
        except asyncio.TimeoutError:
            raise HTTPException(504, "AI took too long — try again")

    def _json_of(raw: str) -> Dict[str, Any]:
        raw = raw.strip().strip("`")
        raw = raw[raw.find("{"):raw.rfind("}") + 1]
        return json.loads(raw)

    @router.post("/targets/{tid}/battle-card")
    async def battle_card(tid: str, _=Depends(get_current_user)):
        t = await db.niche_targets.find_one({"id": tid}, {"_id": 0})
        if not t:
            raise HTTPException(404, "Target not found")
        v = VERTICALS[t["vertical"]]
        try:
            raw = await _claude(
                "You are a freight-brokerage sales intelligence analyst for Orisei Freight Solutions, "
                "a three-founder Minneapolis brokerage with a 2-truck asset division. Produce a factual, "
                "practical account battle card. Return STRICT JSON with keys: what_they_ship (string), "
                "likely_lanes (array of 3-5 strings like 'Fridley, MN -> Memphis, TN (air hub)'), "
                "decision_makers (array of 2-4 title strings to hunt on LinkedIn), "
                "objections (array of 3 objects {objection, counter}), "
                "hook (one killer opening line for a cold call), "
                "compliance_notes (string; certifications/insurance needed, or 'None beyond standard').",
                json.dumps({"company": t["name"], "city": t["city"], "vertical": v["label"],
                            "vertical_pitch": v["pitch"], "est_loads_month": t["est_loads_month"],
                            "margin_target_per_load": t["margin_per_load_est"], "notes": t["notes"]}))
            card = _json_of(raw)
        except HTTPException:
            raise
        except Exception:
            log.exception("battle card AI failed")
            raise HTTPException(502, "AI battle card generation failed — try again")
        card["generated_at"] = _now_iso()
        await db.niche_targets.update_one(
            {"id": tid}, {"$set": {"battle_card": card, "updated_at": _now_iso()}})
        if t["stage"] == "target":
            await db.niche_targets.update_one({"id": tid}, {"$set": {"stage": "researched"}})
        return {"ok": True, "battle_card": card}

    @router.post("/targets/{tid}/pitch")
    async def pitch(tid: str, payload: PitchIn, user=Depends(get_current_user)):
        t = await db.niche_targets.find_one({"id": tid}, {"_id": 0})
        if not t:
            raise HTTPException(404, "Target not found")
        v = VERTICALS[t["vertical"]]
        try:
            raw = await _claude(
                "You write cold outreach for Orisei Freight Solutions — a Minneapolis freight brokerage "
                "run by three founders: a 13-year shipper-side logistics operator, a software developer "
                "who built the in-house TMS, and a 12-year CDL owner/operator. The company runs 2 of its "
                "own trucks plus a vetted carrier network. Write a short, specific pilot-pitch email "
                "(under 170 words, no fluff, no exclamation marks). Ask for a 30-60 day pilot at the "
                "stated volume. Return STRICT JSON: {subject, greeting, paragraphs (array of 2-4 short "
                "strings), bullets (array of 3-4 offer strings), closing}.",
                json.dumps({"company": t["name"], "city": t["city"], "vertical": v["label"],
                            "vertical_pitch": v["pitch"], "pilot_ask": v["pilot_ask"],
                            "contact_role": v["contact_role"],
                            "contact_name": t.get("contact_name") or "",
                            "battle_card_hook": (t.get("battle_card") or {}).get("hook", "")}))
            p = _json_of(raw)
        except HTTPException:
            raise
        except Exception:
            log.exception("pitch AI failed")
            raise HTTPException(502, "AI pitch generation failed — try again")

        body_text = "\n\n".join([p.get("greeting", "Hi,")] + p.get("paragraphs", [])
                                + ["• " + b for b in p.get("bullets", [])]
                                + [p.get("closing", "— Orisei Freight Solutions")])
        pitch_doc = {"subject": p.get("subject", f"Orisei × {t['name']} — dedicated capacity pilot"),
                     "body_text": body_text, "generated_at": _now_iso(), "sent": False, "sent_to": None}

        to = (payload.email or t.get("contact_email") or "").strip()
        if payload.send:
            if not to or "@" not in to:
                raise HTTPException(400, "No contact email on file — add one to send.")
            brand = await db.company_brand.find_one({"is_active": True}, {"_id": 0}) or {}
            company = brand.get("name") or brand.get("company_name") or "Orisei Freight Solutions"
            accent = brand.get("accent_color") or "#0891b2"
            reply_to = brand.get("contact_email") or "oliver@oriseifreightsolutions.com"
            paras = "".join(f"<p>{x}</p>" for x in p.get("paragraphs", []))
            bullets = "".join(f"<li>{b}</li>" for b in p.get("bullets", []))
            html = f"""
            <div style="font-family:Arial,Helvetica,sans-serif;max-width:640px;margin:0 auto;color:#1a202c">
              <div style="background:#0b0e14;padding:18px 28px;border-radius:8px 8px 0 0">
                <span style="color:{accent};font-size:19px;font-weight:800;letter-spacing:1px">{company.upper()}</span>
              </div>
              <div style="border:1px solid #e2e8f0;border-top:none;padding:26px;border-radius:0 0 8px 8px">
                <p>{p.get('greeting', 'Hi,')}</p>{paras}
                <ul style="font-size:13.5px;color:#334155">{bullets}</ul>
                <p>{p.get('closing', '')}</p>
                <p>— {company}<br/><a href="mailto:{reply_to}" style="color:{accent}">{reply_to}</a></p>
              </div>
            </div>"""
            from routes.orisei_auto_digest import _resend_creds, _send_via_resend
            creds = await _resend_creds(db)
            res = await _send_via_resend(creds, to=to, subject=pitch_doc["subject"], html=html) \
                if creds else {"sent": False, "error": "no_resend_creds"}
            status = "sent" if res.get("sent") else "recorded_no_key"
            await db.outbound_emails.insert_one({
                "to": to, "subject": pitch_doc["subject"], "html": html, "status": status,
                "error": res.get("error"), "kind": "niche_market_pitch", "target_id": tid,
                "at": _now_iso(), "sent_by": getattr(user, "name", "system")})
            pitch_doc.update({"sent": res.get("sent", False), "sent_to": to, "send_status": status})
            upd = {"last_pitch": pitch_doc, "contact_email": to, "updated_at": _now_iso(),
                   "last_outreach_at": _now_iso(), "last_touch_at": _now_iso(),
                   "last_touchpoint": f"Pitch emailed to {to}" + ("" if res.get("sent") else " (queued — no Resend key)")}
            if t["stage"] in ("target", "researched"):
                upd["stage"] = "contacted"
            await db.niche_targets.update_one({"id": tid}, {"$set": upd, "$inc": {"outreach_count": 1}})
        else:
            await db.niche_targets.update_one(
                {"id": tid}, {"$set": {"last_pitch": pitch_doc, "updated_at": _now_iso()}})
        return {"ok": True, "pitch": pitch_doc}

    @router.get("/dashboard")
    async def dashboard(_=Depends(get_current_user)):
        await _ensure_seed()
        rows = await db.niche_targets.find({}, {"_id": 0}).to_list(500)
        for r in rows:
            r["y1_potential"] = _y1_potential(r)
        contracted = [r for r in rows if r["stage"] == "contracted"]
        pilots = [r for r in rows if r["stage"] == "pilot"]
        contracted_loads = sum(r["est_loads_month"] for r in contracted)
        pilot_loads = sum(r["est_loads_month"] for r in pilots)
        weighted = sum(r["y1_potential"] * STAGE_PROB.get(r["stage"], 0) for r in rows)
        by_vertical = {}
        for r in rows:
            b = by_vertical.setdefault(r["vertical"], {
                "vertical": r["vertical"], "label": VERTICALS[r["vertical"]]["label"],
                "tier": VERTICALS[r["vertical"]]["tier"], "targets": 0, "contracted": 0,
                "pipeline_y1": 0.0, "weighted_y1": 0.0,
                "margin_per_load": VERTICALS[r["vertical"]]["margin_per_load"]})
            b["targets"] += 1
            b["contracted"] += 1 if r["stage"] == "contracted" else 0
            b["pipeline_y1"] += r["y1_potential"]
            b["weighted_y1"] += r["y1_potential"] * STAGE_PROB.get(r["stage"], 0)
        phases = []
        for pnum, meta in PHASE_PLAN.items():
            pt = [r for r in rows if r["phase"] == pnum]
            phases.append({"phase": pnum, **meta,
                           "targets": [{"id": r["id"], "name": r["name"], "stage": r["stage"],
                                        "est_loads_month": r["est_loads_month"],
                                        "y1_potential": r["y1_potential"]} for r in pt],
                           "loads_committed": sum(r["est_loads_month"] for r in pt
                                                  if r["stage"] in ("pilot", "contracted")),
                           "y1_committed": sum(r["y1_potential"] for r in pt
                                               if r["stage"] == "contracted")})
        stage_counts = {s: sum(1 for r in rows if r["stage"] == s) for s in STAGES}
        nos = [r for r in rows if r.get("outcome") == "no"]
        maybes = [r for r in rows if r.get("outcome") == "maybe"]
        pitching = [r for r in rows if r.get("outcome") != "no"
                    and r["stage"] in ("contacted", "meeting", "pilot_proposed", "pilot")]
        meetings = [r for r in rows if r["stage"] in ("meeting", "pilot_proposed", "pilot", "contracted")]
        decided = len(contracted) + len(nos)
        today = datetime.now(timezone.utc).date().isoformat()
        urgent = sorted([r for r in rows if r.get("decision_deadline")
                         and r["stage"] != "contracted" and r.get("outcome") != "no"],
                        key=lambda r: r["decision_deadline"])
        carrier_gap = sum(max(0, (r.get("carriers_required") or 0) - (r.get("carriers_secured") or 0))
                          for r in rows if r["stage"] in ("meeting", "pilot_proposed", "pilot", "contracted"))
        feature_blockers: Dict[str, Dict[str, Any]] = {}
        for r in rows:
            if r["stage"] in ("meeting", "pilot_proposed", "pilot") and r.get("outcome") != "no":
                for f in r.get("features_required") or []:
                    if f.get("status") != "done":
                        feature_blockers.setdefault(f["name"], {"feature": f["name"], "status": f["status"],
                                                                "blocking": []})["blocking"].append(r["name"])
        win_rate = {"actively_pitching": len(pitching), "meetings_taken": len(meetings),
                    "maybe": len(maybes), "no_deprioritized": len(nos),
                    "win_rate_pct": round(len(contracted) / decided * 100, 1) if decided else None}
        readiness = {"carrier_gap_active_deals": carrier_gap,
                     "feature_blockers": sorted(feature_blockers.values(), key=lambda x: -len(x["blocking"])),
                     "urgent_deadlines": [{"id": r["id"], "name": r["name"],
                                           "deadline": r["decision_deadline"], "stage": r["stage"],
                                           "overdue": r["decision_deadline"] < today} for r in urgent[:6]]}
        return {"goals": PLAN_GOALS,
                "stats": {"targets_total": len(rows), "verticals": len(by_vertical),
                          "contracted_accounts": len(contracted), "pilots_active": len(pilots),
                          "contracted_loads_month": contracted_loads,
                          "pilot_loads_month": pilot_loads,
                          "loads_pct_of_goal": round(contracted_loads / PLAN_GOALS["loads_per_month"] * 100, 1),
                          "contracted_y1_revenue": round(sum(r["y1_potential"] for r in contracted), 2),
                          "weighted_pipeline_y1": round(weighted, 2),
                          "total_pipeline_y1": round(sum(r["y1_potential"] for r in rows), 2)},
                "stage_counts": stage_counts, "win_rate": win_rate, "readiness": readiness,
                "verticals": sorted(by_vertical.values(), key=lambda x: (x["tier"], -x["weighted_y1"])),
                "phases": phases}

    return router
