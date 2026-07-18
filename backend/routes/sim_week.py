"""routes.sim_week — OPERATION SANDBOX: a full-fidelity, week-long brokerage
simulation. Runs sample loads start-to-finish exactly like production:

  post → AI match → book (rate con) → dispatch → live GPS movement →
  pickup/detention → in-transit pings → delivery → POD → BOL → auto-invoice →
  factoring advance → shipper payment → ledger.

Everything is tagged is_sample=True and mirrored into the real collections
(brokerage_bookings / shipments / brokerage_invoices) so BOL/POD/invoice PDFs
and the live tracking map work unchanged. Time is compressed (default: one
sim day ≈ 2 real minutes). Exceptions (breakdowns, weather, detention) fire
realistically and route through an AI triage queue.

Endpoints — /api/sim/*
"""
from __future__ import annotations

import logging
import math
import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger("orisei.sim_week")

# ---------------------------------------------------------------- constants
DOE_DIESEL_AVG = 3.68          # $/gal — current national average (sim week)
FSC_PER_MILE = round((DOE_DIESEL_AVG - 1.20) / 6.0, 2)   # standard TL matrix
EFFECTIVE_MPH = 52 * (11 / 24)  # HOS-constrained around-the-clock speed

CITIES: Dict[str, tuple] = {
    "Minneapolis, MN": (44.98, -93.27), "Chicago, IL": (41.88, -87.63),
    "Milwaukee, WI": (43.04, -87.91), "Des Moines, IA": (41.59, -93.62),
    "Kansas City, MO": (39.10, -94.58), "St. Louis, MO": (38.63, -90.20),
    "Dallas, TX": (32.78, -96.80), "Houston, TX": (29.76, -95.37),
    "San Antonio, TX": (29.42, -98.49), "Atlanta, GA": (33.75, -84.39),
    "Charlotte, NC": (35.23, -80.84), "Memphis, TN": (35.15, -90.05),
    "Nashville, TN": (36.16, -86.78), "Indianapolis, IN": (39.77, -86.16),
    "Columbus, OH": (39.96, -83.00), "Detroit, MI": (42.33, -83.05),
    "Denver, CO": (39.74, -104.99), "Salt Lake City, UT": (40.76, -111.89),
    "Phoenix, AZ": (33.45, -112.07), "Los Angeles, CA": (34.05, -118.24),
    "Ontario, CA": (34.07, -117.65), "Oakland, CA": (37.80, -122.27),
    "Portland, OR": (45.52, -122.68), "Seattle, WA": (47.61, -122.33),
    "Newark, NJ": (40.74, -74.17), "Harrisburg, PA": (40.27, -76.88),
    "Boston, MA": (42.36, -71.06), "Jacksonville, FL": (30.33, -81.66),
    "Miami, FL": (25.76, -80.19), "Laredo, TX": (27.51, -99.51),
    "Oklahoma City, OK": (35.47, -97.52), "Fargo, ND": (46.88, -96.79),
    "Omaha, NE": (41.26, -95.94), "Louisville, KY": (38.25, -85.76),
    "Albuquerque, NM": (35.08, -106.65), "Duluth, MN": (46.79, -92.10),
    "Wilmington, OH": (39.45, -83.83), "Dayton, OH": (39.76, -84.19),
    "Green Bay, WI": (44.51, -88.01), "Richmond, VA": (37.54, -77.44),
    "Rosemount, MN": (44.74, -93.13),
}

SHIPPERS = [
    ("Walmart DC", 30), ("Target DC", 30), ("Costco DC", 21), ("Home Depot", 30),
    ("Lowe's RDC", 35), ("Pepsi", 30), ("Kraft Heinz", 45), ("Amazon FBA", 40),
    ("General Mills", 21), ("Cargill Ag Supply", 30), ("3M Distribution", 30),
    ("Polaris Industries", 30),
]

COMMODITIES = {
    "Van": ["Palletized CPG", "Paper products", "Packaged foods", "Retail fixtures",
            "Appliances", "Auto parts", "Consumer electronics"],
    "Reefer": ["Frozen foods", "Fresh produce", "Dairy", "Beverages (temp)", "Pharma (2-8C)"],
    "Flatbed": ["Steel coils", "Lumber", "Ag equipment", "Building materials", "Machinery"],
}

CARRIER_FLEET: List[Dict[str, Any]] = [
    # (name, base, equipment, otp) — the real partner roster
    {"name": "R+L Carriers",             "base": "Wilmington, OH",  "equipment": ["Van"],                       "otp": 95},
    {"name": "Saia LTL Freight",         "base": "Atlanta, GA",     "equipment": ["Van"],                       "otp": 94},
    {"name": "Dayton Freight Lines",     "base": "Dayton, OH",      "equipment": ["Van"],                       "otp": 96},
    {"name": "Schneider National",       "base": "Green Bay, WI",   "equipment": ["Van", "Reefer", "Flatbed"],  "otp": 95},
    {"name": "Estes Express Lines",      "base": "Richmond, VA",    "equipment": ["Van", "Flatbed"],            "otp": 93},
    {"name": "King Solutions",           "base": "Minneapolis, MN", "equipment": ["Van", "Reefer"],             "otp": 96},
    {"name": "Bay & Bay Transportation", "base": "Rosemount, MN",   "equipment": ["Van", "Reefer"],             "otp": 95},
]

# ------------------------------------------------- market realism: lane imbalance
REGION_OF: Dict[str, str] = {
    "Los Angeles, CA": "west", "Ontario, CA": "west", "Oakland, CA": "west",
    "Portland, OR": "pnw", "Seattle, WA": "pnw",
    "Denver, CO": "mountain", "Salt Lake City, UT": "mountain", "Albuquerque, NM": "mountain",
    "Phoenix, AZ": "southwest",
    "Dallas, TX": "south_central", "Houston, TX": "south_central",
    "San Antonio, TX": "south_central", "Laredo, TX": "south_central",
    "Oklahoma City, OK": "south_central",
    "Chicago, IL": "midwest", "Milwaukee, WI": "midwest", "Indianapolis, IN": "midwest",
    "Columbus, OH": "midwest", "Detroit, MI": "midwest", "St. Louis, MO": "midwest",
    "Louisville, KY": "midwest",
    "Minneapolis, MN": "plains", "Duluth, MN": "plains", "Fargo, ND": "plains",
    "Des Moines, IA": "plains", "Omaha, NE": "plains", "Kansas City, MO": "plains",
    "Atlanta, GA": "southeast", "Charlotte, NC": "southeast", "Memphis, TN": "southeast",
    "Nashville, TN": "southeast",
    "Jacksonville, FL": "florida", "Miami, FL": "florida",
    "Newark, NJ": "northeast", "Harrisburg, PA": "northeast", "Boston, MA": "northeast",
    "Wilmington, OH": "midwest", "Dayton, OH": "midwest", "Green Bay, WI": "midwest",
    "Richmond, VA": "southeast", "Rosemount, MN": "plains",
}

# out = strength of outbound (headhaul) demand · in = strength of inbound demand.
# Mirrors real DAT market behavior: CA outbound hot / inbound soft, FL inbound hot /
# outbound cheap backhaul, NE hard to leave cheap, Denver backhaul-poor, Midwest balanced.
REGION_MARKET: Dict[str, Dict[str, float]] = {
    "west":          {"out": 1.15, "in": 0.90},
    "pnw":           {"out": 0.97, "in": 1.05},
    "mountain":      {"out": 0.87, "in": 1.07},
    "southwest":     {"out": 0.94, "in": 1.03},
    "south_central": {"out": 1.04, "in": 0.98},
    "midwest":       {"out": 1.03, "in": 1.00},
    "plains":        {"out": 0.97, "in": 1.02},
    "southeast":     {"out": 1.02, "in": 0.99},
    "florida":       {"out": 0.80, "in": 1.18},
    "northeast":     {"out": 0.86, "in": 1.08},
}

def _lane_multiplier(origin: str, dest: str) -> float:
    o = REGION_MARKET[REGION_OF[origin]]
    d = REGION_MARKET[REGION_OF[dest]]
    return round(max(0.72, min(1.38, o["out"] * d["in"])), 3)

# ------------------------------------------------- market realism: seasonality
# Monthly national rate curves per equipment (Jan..Dec), indexed to 1.00 annual avg.
# Van: Q4 retail peak, Jan/Feb soft. Reefer: produce season May-Jul + holiday peak.
# Flatbed: construction season Apr-Sep, dead in winter.
SEASONAL_CURVE: Dict[str, List[float]] = {
    "Van":     [0.93, 0.94, 0.97, 0.99, 1.01, 1.02, 1.00, 1.00, 1.02, 1.05, 1.08, 1.10],
    "Reefer":  [0.94, 0.95, 0.98, 1.02, 1.08, 1.12, 1.10, 1.04, 1.02, 1.04, 1.10, 1.12],
    "Flatbed": [0.90, 0.92, 1.00, 1.06, 1.08, 1.08, 1.06, 1.05, 1.03, 1.00, 0.95, 0.90],
}

# Regional produce surges layered on reefer: FL spring produce, CA summer produce.
PRODUCE_SURGE = {"florida": {4: 1.12, 5: 1.14, 6: 1.08}, "west": {5: 1.06, 6: 1.10, 7: 1.08}}

def _seasonal_multiplier(month: int, equipment: str, origin_region: str) -> float:
    m = SEASONAL_CURVE[equipment][month - 1]
    if equipment == "Reefer":
        m *= PRODUCE_SURGE.get(origin_region, {}).get(month, 1.0)
    return round(m, 3)

FIRST = ["Marcus", "Dwayne", "Elena", "Sam", "Kofi", "Tina", "Jorge", "Pete", "Angela",
         "Ray", "Deb", "Hassan", "Vlad", "Cherise", "Bobby", "Ana", "Duke", "Lamar"]
LAST = ["Johnson", "Okafor", "Reyes", "Nguyen", "Kowalski", "Sesay", "Thompson", "Diaz",
        "Karlsson", "Brooks", "Toure", "Miller", "Petrov", "Hale", "Ortiz", "Webb"]

EXCEPTION_TYPES = [
    ("breakdown", "Tractor breakdown — unit derated on shoulder", "high", 350.0,
     "Carrier dispatching relay unit from nearest terminal (tow on carrier's account). "
     "Orisei covers expedite assist. ETA impact ~6 sim hrs. Notify consignee, re-confirm "
     "delivery appointment, document for OS&D file."),
    ("weather", "Weather hold — high-wind / winter advisory on route", "moderate", 0.0,
     "Hold at nearest safe haven per NWS advisory. Reroute check via routing engine. "
     "ETA impact ~4 sim hrs. Proactive shipper notification sent."),
    ("detention", "Detention at shipper — dock running >2 hrs behind", "moderate", -130.0,
     "Detention clock started and documented with in/out photos. Bill $65/hr after "
     "2-hr grace to shipper per rate con. Driver HOS re-checked for legal delivery."),
    ("paperwork", "BOL discrepancy — piece count mismatch at pickup", "low", 0.0,
     "Driver noted exception on BOL, photographed count. Shipper ops confirmed revised "
     "count by email — document attached to load file. No claim exposure."),
    ("lumper", "Lumper fee demanded at receiver — $175 cash/EFS", "low", 175.0,
     "EFS check issued to driver, receipt photographed. Lumper billed back to shipper "
     "per rate con accessorial schedule — 100% recovery expected, cash-flow hit today."),
    ("layover", "Layover — receiver bumped appointment to next day", "moderate", 250.0,
     "Driver held overnight; $250 layover owed to carrier per rate con. Re-confirmed "
     "AM appointment, notified shipper, layover invoice added to load file."),
    ("reweigh", "Scale ticket — gross over on drive axle, reweigh + slide", "low", 45.0,
     "Driver slid tandems and re-scaled ($45 CAT scale, reimbursed). 20 min delay. "
     "Weight documented for the file."),
    ("appt_bump", "Appointment bumped — dock congestion at receiver", "low", 0.0,
     "FCFS window renegotiated with receiving. ETA re-broadcast to shipper. No cost, "
     "~3 sim hr delay documented."),
]

# En-route exception pool: (index into EXCEPTION_TYPES, weight)
EN_ROUTE_EXC = [(0, 3), (1, 4), (4, 3), (5, 2), (6, 2), (7, 3)]

# ------------------------------------------- industry variables: fixed overhead
# Real weekly cost stack of a working MN freight brokerage, amortized per sim day.
OVERHEAD_DAILY: Dict[str, float] = {
    "contingent_cargo_gl_ins": 28.0,   # $100k contingent cargo + GL (~$850/mo)
    "bmc84_surety_bond": 4.1,          # $75k FMCSA broker bond premium (~$1.5k/yr)
    "loadboard_subscriptions": 12.0,   # DAT One + Truckstop
    "tms_software_eld_data": 10.0,     # TMS, phones, tracking data
    "office_phone_misc": 7.0,
    "ucr_boc3_permits": 1.2,           # UCR, BOC-3 process agents, filings amortized
    "operator_draw": 143.0,            # member salary draw ($1,000/wk)
    "carrier_vetting_service": 5.0,    # MyCarrierPackets/Highway (~$150/mo)
    "insurance_cert_monitoring": 2.0,  # carrier COI monitoring (~$60/mo)
    "credit_check_service": 1.7,       # shipper credit reports (~$50/mo)
    "accounting_cpa": 6.6,             # bookkeeping + CPA (~$200/mo)
    "website_marketing": 3.3,          # site, email, brand spend (~$100/mo)
    "bank_fees_legal_reserve": 3.0,    # bank charges + legal reserve (~$90/mo)
}
OVERHEAD_DAY_TOTAL = round(sum(OVERHEAD_DAILY.values()), 2)

CARRIER_PAYMENT_FEE = 12.0  # ACH/wire/EFS fee per carrier settlement

CLAIM_PROB = 0.015          # OS&D cargo claim per delivered load
CLAIM_RANGE = (350, 4200)   # typical freight-damage claim after salvage
BAD_DEBT_PROB = 0.02        # shipper default/short-pay on reserve
FALLTHROUGH_PROB = 0.06     # booked carrier falls through pre-pickup
QUICKPAY_PROB = 0.30        # carriers electing 2% quick-pay (broker income)
QUICKPAY_FEE = 0.02


def _net_margin(ledger: Dict[str, float]) -> float:
    return round(ledger.get("revenue", 0) - ledger.get("carrier_pay", 0)
                 - ledger.get("factoring_fees", 0) - ledger.get("exception_costs", 0)
                 - ledger.get("overhead", 0) - ledger.get("claims", 0)
                 - ledger.get("bad_debt", 0) - ledger.get("transaction_fees", 0)
                 + ledger.get("quickpay_income", 0), 2)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _haversine_mi(a: tuple, b: tuple) -> float:
    r = 3958.8
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp, dl = math.radians(b[0] - a[0]), math.radians(b[1] - a[1])
    x = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(x))


def _lerp(a: tuple, b: tuple, t: float) -> tuple:
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


class StartIn(BaseModel):
    duration_days: int = Field(7, ge=1, le=14)
    loads_per_day: int = Field(10, ge=3, le=25)
    sim_minutes_per_real_second: float = Field(12.0, ge=1, le=120)
    autopilot: bool = True
    auto_triage: bool = True


def build_sim_router(*, api_router: APIRouter, db,
                     get_current_user: Callable, require_role: Callable) -> None:
    router = APIRouter(prefix="/sim", tags=["operation-sandbox"])
    rnd = random.Random()

    # ------------------------------------------------------------- helpers
    async def _active_sim() -> Optional[Dict[str, Any]]:
        return await db.sim_state.find_one({"status": {"$in": ["running", "paused", "complete"]}},
                                           {"_id": 0}, sort=[("started_at", -1)])

    async def _event(sim: Dict[str, Any], etype: str, msg: str,
                     load_id: Optional[str] = None, severity: str = "info"):
        await db.sim_events.insert_one({
            "id": uuid.uuid4().hex[:10], "sim_id": sim["sim_id"],
            "sim_time": sim["sim_clock"], "at": _iso(_now()),
            "type": etype, "load_id": load_id, "message": msg, "severity": severity,
        })

    def _fleet_with_ids() -> List[Dict[str, Any]]:
        out = []
        for i, c in enumerate(CARRIER_FLEET):
            fsc = round(FSC_PER_MILE + rnd.uniform(-0.02, 0.02), 2)
            out.append({**c, "mc_number": f"MC-9{40000 + i * 137}", "dot": f"3{500000 + i * 911}",
                        "fsc_per_mile": fsc, "insurance": "1M/100K", "is_sample": True})
        return out

    def _gen_load(sim: Dict[str, Any], day: int) -> Dict[str, Any]:
        origin = rnd.choice(list(CITIES))
        dest = rnd.choice([c for c in CITIES if c != origin])
        o, d = CITIES[origin], CITIES[dest]
        miles = round(_haversine_mi(o, d) * 1.18)  # road factor
        if miles < 120:
            miles = 120
        equipment = rnd.choices(["Van", "Reefer", "Flatbed"], weights=[58, 26, 16])[0]
        rpm = {"Van": rnd.uniform(1.95, 2.55), "Reefer": rnd.uniform(2.35, 3.05),
               "Flatbed": rnd.uniform(2.25, 2.90)}[equipment]
        clock = datetime.fromisoformat(sim["sim_clock"])
        o_region, d_region = REGION_OF[origin], REGION_OF[dest]
        lane_mult = _lane_multiplier(origin, dest)
        seas_mult = _seasonal_multiplier(clock.month, equipment, o_region)
        mkt = sim.get("market") or {}
        spot_index = mkt.get("spot_index", 1.0)
        diesel = mkt.get("diesel", DOE_DIESEL_AVG)
        fsc_pm = round(FSC_PER_MILE * diesel / DOE_DIESEL_AVG, 2)
        rpm = rpm * lane_mult * seas_mult * spot_index
        headhaul = "headhaul" if lane_mult >= 1.08 else "backhaul" if lane_mult <= 0.92 else "balanced"
        linehaul = round(rpm * miles, 2)
        fsc = round(fsc_pm * miles, 2)
        carrier_pay = round(linehaul + fsc, 2)
        # brokers compress margin on hot headhauls, widen it on backhauls
        margin_pct = {"headhaul": rnd.uniform(0.10, 0.17), "backhaul": rnd.uniform(0.15, 0.25),
                      "balanced": rnd.uniform(0.13, 0.22)}[headhaul]
        sell = round(carrier_pay / (1 - margin_pct), 2)
        shipper, terms = rnd.choice(SHIPPERS)
        pickup = clock + timedelta(hours=rnd.uniform(2, 14))
        return {
            "load_id": f"SMPL-{uuid.uuid4().hex[:6].upper()}",
            "sim_id": sim["sim_id"], "day_posted": day, "status": "posted",
            "board": rnd.choices(
                ["DAT One", "Truckstop", "Convoy (Flexport)", "Uber Freight", "123Loadboard", "Direct Shipper Tender"],
                weights=[40, 24, 10, 12, 6, 8])[0],
            "shipper": shipper, "terms_days": terms,
            "origin": {"name": origin, "lat": o[0], "lng": o[1]},
            "dest": {"name": dest, "lat": d[0], "lng": d[1]},
            "miles": miles, "equipment": equipment,
            "commodity": rnd.choice(COMMODITIES[equipment]),
            "weight_lbs": rnd.randint(18000, 44500),
            "linehaul_usd": linehaul, "fsc_usd": fsc, "fsc_per_mile": fsc_pm,
            "carrier_pay_usd": carrier_pay, "sell_usd": sell,
            "margin_usd": round(sell - carrier_pay, 2),
            "margin_pct": round(margin_pct * 100, 1),
            "rpm_all_in": round(sell / miles, 2),
            "market": {"lane_mult": lane_mult, "seasonal_mult": seas_mult,
                       "spot_index": spot_index, "diesel": diesel,
                       "headhaul": headhaul, "o_region": o_region, "d_region": d_region},
            "pickup_appt": _iso(pickup),
            "delivery_appt": _iso(pickup + timedelta(hours=miles / EFFECTIVE_MPH + 6)),
            "position": {"lat": o[0], "lng": o[1]}, "progress": 0.0,
            "carrier": None, "driver": None, "timeline": [
                {"t": sim["sim_clock"], "e": f"Posted to {'/'.join(['board'])} — ${sell:,.0f} all-in"}],
            "docs": {}, "exception": None, "is_sample": True,
            "posted_at": sim["sim_clock"],
        }

    def _match_carrier(load: Dict[str, Any], fleet: List[Dict[str, Any]]) -> Dict[str, Any]:
        o = (load["origin"]["lat"], load["origin"]["lng"])
        scored = []
        for c in fleet:
            if load["equipment"] not in c["equipment"]:
                continue
            dead = _haversine_mi(o, CITIES[c["base"]])
            score = c["otp"] * 1.2 - dead / 18 + rnd.uniform(-4, 4)
            scored.append((score, dead, c))
        scored.sort(key=lambda x: -x[0])
        _, dead, best = scored[0]
        return {**best, "deadhead_mi": round(dead),
                "driver": f"{rnd.choice(FIRST)} {rnd.choice(LAST)}",
                "truck": f"#{rnd.randint(100, 899)}"}

    async def _mirror_booking(load: Dict[str, Any], user_id: str):
        """Mirror into real collections so BOL/POD/invoice PDFs + main map work."""
        booked_id = f"BK-{load['load_id'].replace('SMPL-', 'S')}{uuid.uuid4().hex[:4].upper()}"
        load["booked_id"] = booked_id
        now = _iso(_now())
        await db.brokerage_bookings.insert_one({
            "booked_id": booked_id, "load_id": load["load_id"], "board_id": "sandbox",
            "carrier_name": load["carrier"]["name"], "carrier_mc": load["carrier"]["mc_number"],
            "customer_name": load["shipper"], "origin": load["origin"]["name"],
            "destination": load["dest"]["name"], "miles": load["miles"],
            "equipment": load["equipment"], "commodity": load["commodity"],
            "weight_lbs": load["weight_lbs"],
            "forecast_rate_usd": load["sell_usd"], "forecast_carrier_pay_usd": load["carrier_pay_usd"],
            "forecast_margin_usd": load["margin_usd"],
            "customer_rate_usd": load["sell_usd"], "carrier_rate_usd": load["carrier_pay_usd"],
            "pickup_date": load["pickup_appt"], "delivery_date": load["delivery_appt"],
            "status": "booked", "booked_at": now, "booked_by": user_id,
            "notes": f"SAMPLE · Operation Sandbox · driver {load['carrier']['driver']} {load['carrier']['truck']} · FSC ${load['fsc_per_mile']}/mi (DOE ${DOE_DIESEL_AVG})",
            "is_sample": True, "sim_id": load["sim_id"],
        })
        def _split(loc):
            city, _, st = loc.partition(",")
            return {"city": city.strip(), "state": st.strip(), "name": loc}
        await db.shipments.insert_one({
            "shipment_id": f"SH-{booked_id.replace('BK-','')}", "reference": load["load_id"],
            "booking_number": booked_id, "carrier": load["carrier"]["name"],
            "carrier_mc": load["carrier"]["mc_number"], "mode": "TL", "status": "in_transit",
            "origin": _split(load["origin"]["name"]), "destination": _split(load["dest"]["name"]),
            "current_location": {**_split(load["origin"]["name"]),
                                 "lat": load["origin"]["lat"], "lng": load["origin"]["lng"]},
            "eta": load["delivery_appt"], "pickup_date": load["pickup_appt"],
            "delivery_date": load["delivery_appt"], "weight_lbs": load["weight_lbs"],
            "pieces": rnd.randint(10, 26), "commodity": f"SAMPLE · {load['commodity']}",
            "value_usd": load["sell_usd"], "consignee": load["shipper"], "supplier": load["shipper"],
            "customer_rate_usd": load["sell_usd"], "carrier_rate_usd": load["carrier_pay_usd"],
            "miles": load["miles"], "progress": 0.0, "direction": "outbound", "hazmat": False,
            "notes": "SAMPLE load — Operation Sandbox", "created_at": now, "updated_at": now,
            "created_by": user_id, "is_sample": True, "sim_id": load["sim_id"],
            "_from_brokerage": True,
        })

    async def _invoice_load(sim: Dict[str, Any], load: Dict[str, Any]):
        inv_id = f"INV-{load['load_id'].replace('SMPL-', 'S')}"
        clock = sim["sim_clock"]
        await db.brokerage_invoices.insert_one({
            "invoice_id": inv_id, "customer_name": load["shipper"],
            "booking_ids": [load.get("booked_id")],
            "line_items": [
                {"label": f"{load['load_id']} · {load['origin']['name']} → {load['dest']['name']} · linehaul", "amount_usd": round(load["sell_usd"] - load["fsc_usd"], 2)},
                {"label": f"Fuel surcharge · {load['miles']} mi @ ${load['fsc_per_mile']}/mi (DOE ${DOE_DIESEL_AVG})", "amount_usd": load["fsc_usd"]},
            ],
            "subtotal_usd": load["sell_usd"], "tax_usd": 0, "total_usd": load["sell_usd"],
            "issued_at": clock, "due_at": _iso(datetime.fromisoformat(clock) + timedelta(days=load["terms_days"])),
            "payment_terms": f"Net {load['terms_days']}", "status": "issued",
            "auto_generated": True, "is_sample": True, "sim_id": sim["sim_id"],
        })
        load["docs"]["invoice_id"] = inv_id

    # ----------------------------------------------------------- lifecycle
    async def _advance_load(sim: Dict[str, Any], load: Dict[str, Any],
                            sim_hours: float, ledger: Dict[str, float],
                            fleet: List[Dict[str, Any]], user_id: str) -> None:
        clock = datetime.fromisoformat(sim["sim_clock"])
        st = load["status"]
        tl = load["timeline"]

        def log(msg):
            tl.append({"t": _iso(clock), "e": msg})

        if st == "posted" and sim.get("autopilot"):
            c = _match_carrier(load, fleet)
            load["carrier"] = c
            load["status"] = "booked"
            log(f"AI matched → {c['name']} ({c['mc_number']}) · deadhead {c['deadhead_mi']} mi · rate con e-signed")
            load["docs"]["ratecon_at"] = _iso(clock)
            await _mirror_booking(load, user_id)
            await _event(sim, "book", f"🤖 {load['load_id']} booked → {c['name']} · ${load['sell_usd']:,.0f} all-in · margin ${load['margin_usd']:,.0f}", load["load_id"])
            return

        if st == "booked":
            # carrier fall-through: truck no-shows pre-pickup, rebook at a premium
            if not load.get("_fallthrough_done") and rnd.random() < min(FALLTHROUGH_PROB, 0.008 * sim_hours):
                load["_fallthrough_done"] = True
                old_name = load["carrier"]["name"]
                c = _match_carrier(load, [f for f in fleet if f["name"] != old_name])
                bump = round(load["carrier_pay_usd"] * rnd.uniform(0.05, 0.08), 2)
                load["carrier"] = c
                load["carrier_pay_usd"] = round(load["carrier_pay_usd"] + bump, 2)
                load["margin_usd"] = round(load["margin_usd"] - bump, 2)
                log(f"CARRIER FELL THROUGH — {old_name} no-show. Rebooked {c['name']} at +${bump:,.0f}")
                await _event(sim, "exception", f"🚨 {load['load_id']}: carrier fall-through — rebooked {c['name']} (+${bump:,.0f} to cover)", load["load_id"], "warn")
            if clock >= datetime.fromisoformat(load["pickup_appt"]):
                load["status"] = "at_pickup"
                load["arrived_pu_at"] = _iso(clock)
                dwell = rnd.uniform(0.7, 3.4)
                load["_dwell_left"] = dwell
                log(f"Arrived shipper dock · {load['origin']['name']}")
                if dwell > 2.0 and not load["exception"]:
                    et = EXCEPTION_TYPES[2]
                    load["exception"] = {"type": et[0], "title": et[1], "severity": et[2],
                                         "cost": et[3], "plan": et[4], "opened_at": _iso(clock)}
                    await _event(sim, "exception", f"⚠️ {load['load_id']}: {et[1]}", load["load_id"], "warn")
            return

        if st == "at_pickup":
            load["_dwell_left"] = load.get("_dwell_left", 1.0) - sim_hours
            if load["_dwell_left"] <= 0:
                load["status"] = "in_transit"
                load["dispatched_at"] = _iso(clock)
                log(f"Loaded {load['weight_lbs']:,} lbs {load['commodity']} · BOL signed · rolling")
                load["docs"]["bol_no"] = f"ORI-BOL-{load['load_id'].replace('SMPL-','')}"
                if load["exception"] and load["exception"]["type"] == "detention":
                    hrs = round(rnd.uniform(1.0, 3.0), 1)
                    det = round(hrs * 65, 2)
                    ledger["detention_billed"] = ledger.get("detention_billed", 0) + det
                    load["sell_usd"] = round(load["sell_usd"] + det, 2)
                    load["margin_usd"] = round(load["margin_usd"] + det * 0.5, 2)
                    load["carrier_pay_usd"] = round(load["carrier_pay_usd"] + det * 0.5, 2)
                    load["exception"]["resolved_at"] = _iso(clock)
                    load["exception"]["resolution"] = f"Detention billed: {hrs}h @ $65 = ${det:,.0f} (split 50/50 with carrier)"
                    await _event(sim, "resolve", f"✅ {load['load_id']} detention billed ${det:,.0f} · rolling", load["load_id"])
                    load["exception"] = None
            return

        if st == "in_transit":
            # random en-route exception (rate-capped so high speed stays realistic)
            if not load["exception"] and rnd.random() < min(0.10, 0.004 * sim_hours):
                idx = rnd.choices([i for i, _ in EN_ROUTE_EXC], weights=[w for _, w in EN_ROUTE_EXC])[0]
                et = EXCEPTION_TYPES[idx]
                load["exception"] = {"type": et[0], "title": et[1], "severity": et[2],
                                     "cost": et[3], "plan": et[4], "opened_at": _iso(clock),
                                     "hold_hours": {"breakdown": 6, "weather": 4, "layover": 10,
                                                    "lumper": 1.5, "reweigh": 1, "appt_bump": 3}.get(et[0], 3)}
                await _event(sim, "exception", f"🚨 {load['load_id']}: {et[1]}", load["load_id"], "error")
            if load["exception"] and load["exception"].get("hold_hours"):
                if sim.get("auto_triage"):
                    load["exception"]["hold_hours"] -= sim_hours
                    if load["exception"]["hold_hours"] <= 0:
                        cost = load["exception"]["cost"]
                        if cost > 0:
                            ledger["exception_costs"] = ledger.get("exception_costs", 0) + cost
                            load["margin_usd"] = round(load["margin_usd"] - cost * 0.4, 2)
                        await _event(sim, "resolve", f"✅ AI triage resolved {load['load_id']}: {load['exception']['type']} · plan executed", load["load_id"])
                        load["exception"]["resolved_at"] = _iso(clock)
                        load["exception"] = None
                return  # truck holds while exception open
            # movement (back-compute true arrival so big ticks stay accurate)
            hours_needed = (1.0 - load["progress"]) * load["miles"] / EFFECTIVE_MPH
            arrived = sim_hours >= hours_needed
            arrival_dt = clock - timedelta(hours=max(0.0, sim_hours - hours_needed))
            delta = (EFFECTIVE_MPH * sim_hours) / max(load["miles"], 1)
            load["progress"] = min(1.0, load["progress"] + delta)
            o = (load["origin"]["lat"], load["origin"]["lng"])
            d = (load["dest"]["lat"], load["dest"]["lng"])
            lat, lng = _lerp(o, d, load["progress"])
            load["position"] = {"lat": round(lat, 4), "lng": round(lng, 4)}
            if load.get("booked_id"):
                await db.shipments.update_one(
                    {"booking_number": load["booked_id"]},
                    {"$set": {"current_location.lat": lat, "current_location.lng": lng,
                              "progress": round(load["progress"], 3),
                              "updated_at": _iso(_now())}})
            if load["progress"] >= 1.0 and arrived:
                load["status"] = "delivered"
                load["delivered_at"] = _iso(arrival_dt)
                load["docs"]["pod_at"] = _iso(arrival_dt)
                on_time = arrival_dt <= datetime.fromisoformat(load["delivery_appt"]) + timedelta(hours=2)
                load["on_time"] = on_time
                log(f"Delivered {load['dest']['name']} · POD photographed from cab · {'ON TIME' if on_time else 'LATE'}")
                if load.get("booked_id"):
                    await db.brokerage_bookings.update_one(
                        {"booked_id": load["booked_id"]},
                        {"$set": {"status": "delivered", "delivered_at": _iso(clock),
                                  "delivery": {"receiver_name": f"{rnd.choice(FIRST)} {rnd.choice(LAST)}",
                                               "delivered_at": _iso(clock), "pieces_ok": True}}})
                    await db.shipments.update_one({"booking_number": load["booked_id"]},
                                                  {"$set": {"status": "delivered", "progress": 1.0}})
                await _event(sim, "deliver", f"📦 {load['load_id']} DELIVERED {load['dest']['name']} · POD in · margin ${load['margin_usd']:,.0f}", load["load_id"])
            return

        if st == "delivered":
            load["status"] = "invoiced"
            await _invoice_load(sim, load)
            ledger["revenue"] = ledger.get("revenue", 0) + load["sell_usd"]
            ledger["carrier_pay"] = ledger.get("carrier_pay", 0) + load["carrier_pay_usd"]
            ledger["fsc_billed"] = ledger.get("fsc_billed", 0) + load["fsc_usd"]
            # OS&D cargo claim — contingent cargo deductible + admin burden
            if rnd.random() < CLAIM_PROB:
                claim = round(rnd.uniform(*CLAIM_RANGE), 2)
                ledger["claims"] = ledger.get("claims", 0) + claim
                load["claim"] = {"amount_usd": claim, "opened_at": _iso(clock)}
                await _event(sim, "exception", f"📦💥 {load['load_id']}: OS&D CARGO CLAIM filed — ${claim:,.0f} (49 CFR 370 clock started, carrier insurer noticed)", load["load_id"], "error")
            # quick-pay income: carrier elects 2% for 24-hr pay
            if rnd.random() < QUICKPAY_PROB:
                qp = round(load["carrier_pay_usd"] * QUICKPAY_FEE, 2)
                ledger["quickpay_income"] = ledger.get("quickpay_income", 0) + qp
                await _event(sim, "factor", f"⚡ {load['load_id']}: carrier took 2% quick-pay — ${qp:,.0f} earned", load["load_id"])
            # carrier settlement transaction fee (ACH/wire/EFS)
            ledger["transaction_fees"] = ledger.get("transaction_fees", 0) + CARRIER_PAYMENT_FEE
            await _event(sim, "invoice", f"🧾 {load['docs']['invoice_id']} issued → {load['shipper']} · ${load['sell_usd']:,.0f} · Net {load['terms_days']}", load["load_id"])
            load["_factor_in"] = 3.0
            return

        if st == "invoiced":
            load["_factor_in"] = load.get("_factor_in", 3.0) - sim_hours
            if load["_factor_in"] <= 0:
                load["status"] = "factored"
                fee = round(load["sell_usd"] * 0.0375, 2)
                advance = round(load["sell_usd"] * 0.85 - fee, 2)
                load["factoring"] = {"fee_usd": fee, "advance_usd": advance,
                                     "reserve_usd": round(load["sell_usd"] * 0.15, 2)}
                ledger["factoring_fees"] = ledger.get("factoring_fees", 0) + fee
                ledger["cash_collected"] = ledger.get("cash_collected", 0) + advance
                await _event(sim, "factor", f"🏦 {load['docs']['invoice_id']} factored · 85% advance ${advance:,.0f} wired (fee ${fee:,.0f} @ 3.75%)", load["load_id"])
                load["_pays_in"] = load["terms_days"] * 2.0  # compressed: 1 term day = 2 sim hrs
            return

        if st == "factored":
            load["_pays_in"] = load.get("_pays_in", 24.0) - sim_hours
            if load["_pays_in"] <= 0:
                load["status"] = "paid"
                reserve = load["factoring"]["reserve_usd"]
                if rnd.random() < BAD_DEBT_PROB:
                    ledger["bad_debt"] = ledger.get("bad_debt", 0) + reserve
                    await _event(sim, "exception", f"🏴 {load['shipper']} SHORT-PAID {load['docs'].get('invoice_id')} — reserve ${reserve:,.0f} written off to bad debt. Credit hold placed.", load["load_id"], "error")
                else:
                    ledger["cash_collected"] = ledger.get("cash_collected", 0) + reserve
                    await _event(sim, "paid", f"💰 {load['shipper']} paid {load['docs'].get('invoice_id')} · reserve ${reserve:,.0f} released · load CLOSED", load["load_id"])
                if load["docs"].get("invoice_id"):
                    await db.brokerage_invoices.update_one(
                        {"invoice_id": load["docs"]["invoice_id"]},
                        {"$set": {"status": "paid", "paid_at": sim["sim_clock"]}})
            return

    # ------------------------------------------------------------ endpoints
    @router.post("/start")
    async def start(payload: StartIn, user=Depends(require_role("admin", "dispatcher"))) -> Dict[str, Any]:
        existing = await db.sim_state.find_one({"status": {"$in": ["running", "paused"]}})
        if existing:
            raise HTTPException(400, "A simulation is already active — reset it first")
        sim_id = f"SIM-{uuid.uuid4().hex[:6].upper()}"
        sim_start = datetime(2026, 7, 13, 6, 0, tzinfo=timezone.utc)  # Monday 06:00
        sim = {
            "sim_id": sim_id, "status": "running",
            "started_at": _iso(_now()), "last_tick_at": _iso(_now()),
            "sim_clock": _iso(sim_start), "sim_start": _iso(sim_start),
            "sim_day": 1, "duration_days": payload.duration_days,
            "loads_per_day": payload.loads_per_day,
            "speed": payload.sim_minutes_per_real_second,
            "autopilot": payload.autopilot, "auto_triage": payload.auto_triage,
            "doe_diesel": DOE_DIESEL_AVG, "fsc_per_mile": FSC_PER_MILE,
            "market": {"diesel": DOE_DIESEL_AVG, "spot_index": 1.0, "cycle": "balanced"},
            "ledger": {"revenue": 0, "carrier_pay": 0, "fsc_billed": 0,
                       "factoring_fees": 0, "detention_billed": 0,
                       "exception_costs": 0, "cash_collected": 0,
                       "overhead": OVERHEAD_DAY_TOTAL, "claims": 0,
                       "bad_debt": 0, "quickpay_income": 0, "transaction_fees": 0},
            "daily": [], "spawned_today": 0,
        }
        await db.sim_state.insert_one(dict(sim))
        # day-1 opening board
        loads = [_gen_load(sim, 1) for _ in range(max(3, payload.loads_per_day // 2))]
        if loads:
            await db.sim_loads.insert_many([dict(x) for x in loads])
        sim["spawned_today"] = len(loads)
        await db.sim_state.update_one({"sim_id": sim_id}, {"$set": {"spawned_today": len(loads)}})
        await _event(sim, "start", f"🚀 OPERATION SANDBOX launched · {payload.duration_days}-day week · {len(CARRIER_FLEET)} carriers staged nationwide · DOE diesel ${DOE_DIESEL_AVG}/gal → FSC ${FSC_PER_MILE}/mi")
        return {"ok": True, "sim_id": sim_id, "carriers": len(CARRIER_FLEET)}

    @router.post("/tick")
    async def tick(user=Depends(get_current_user)) -> Dict[str, Any]:
        sim = await _active_sim()
        if not sim or sim["status"] != "running":
            return await state(user)  # type: ignore
        now = _now()
        real_elapsed = (now - datetime.fromisoformat(sim["last_tick_at"])).total_seconds()
        real_elapsed = min(real_elapsed, 30)  # clamp long gaps
        sim_minutes = real_elapsed * sim["speed"]
        sim_hours = sim_minutes / 60.0
        clock = datetime.fromisoformat(sim["sim_clock"]) + timedelta(minutes=sim_minutes)
        sim["sim_clock"] = _iso(clock)
        sim["last_tick_at"] = _iso(now)
        start_dt = datetime.fromisoformat(sim["sim_start"])
        day = int((clock - start_dt).total_seconds() // 86400) + 1

        ledger = sim["ledger"]
        fleet = _fleet_with_ids()
        user_id = getattr(user, "user_id", "sandbox")

        # day rollover — daily P&L via ledger deltas + market walk + overhead accrual
        if day > sim["sim_day"]:
            loads_all = await db.sim_loads.find({"sim_id": sim["sim_id"]}, {"_id": 0}).to_list(500)
            prev = sim.get("_ledger_snap") or {}
            days_rolled = day - sim["sim_day"]
            ledger["overhead"] = round(ledger.get("overhead", 0) + OVERHEAD_DAY_TOTAL * days_rolled, 2)
            # market random walk: DOE diesel drift + spot market cycle
            mkt = sim.get("market") or {"diesel": DOE_DIESEL_AVG, "spot_index": 1.0}
            mkt["diesel"] = round(min(4.75, max(3.05, mkt.get("diesel", DOE_DIESEL_AVG) + rnd.uniform(-0.07, 0.08))), 2)
            mkt["spot_index"] = round(min(1.14, max(0.90, mkt.get("spot_index", 1.0) + rnd.uniform(-0.03, 0.035))), 3)
            mkt["cycle"] = "tight" if mkt["spot_index"] >= 1.05 else "soft" if mkt["spot_index"] <= 0.96 else "balanced"
            sim["market"] = mkt
            net_now = _net_margin(ledger)
            net_prev = _net_margin(prev)
            sim["daily"].append({"day": sim["sim_day"],
                                 "revenue": round(ledger.get("revenue", 0) - prev.get("revenue", 0), 2),
                                 "margin": round(net_now - net_prev, 2),
                                 "booked": sum(1 for l in loads_all if l.get("day_posted") == sim["sim_day"] and l["status"] != "posted")})
            sim["_ledger_snap"] = dict(ledger)
            sim["sim_day"] = day
            sim["spawned_today"] = 0
            if day <= sim["duration_days"]:
                await _event(sim, "day", f"🌅 DAY {day} of {sim['duration_days']} — DOE diesel ${mkt['diesel']}/gal · spot market {mkt['cycle'].upper()} (idx {mkt['spot_index']}) · overhead accrued ${OVERHEAD_DAY_TOTAL:,.0f}/day")

        # spawn + advance first, then evaluate completion
        if day <= sim["duration_days"]:
            # spawn new freight through the day
            target = sim["loads_per_day"]
            expected = target * min(1.0, ((clock - start_dt).total_seconds() % 86400) / 64800)
            while sim["spawned_today"] < expected and sim["spawned_today"] < target:
                nl = _gen_load(sim, day)
                await db.sim_loads.insert_one(dict(nl))
                sim["spawned_today"] += 1
                await _event(sim, "post", f"📋 {nl['load_id']} posted on {nl['board']} · {nl['origin']['name']} → {nl['dest']['name']} · {nl['equipment']} · ${nl['sell_usd']:,.0f}", nl["load_id"])

        # advance every open load — multiple lifecycle passes when the clock jumps
        passes = max(1, min(6, int(sim_hours // 2) + 1))
        open_loads = await db.sim_loads.find(
            {"sim_id": sim["sim_id"], "status": {"$ne": "paid"}}, {"_id": 0}).to_list(400)
        for load in open_loads:
            for _ in range(passes):
                before = load["status"]
                await _advance_load(sim, load, sim_hours, ledger, fleet, user_id)
                if load["status"] == before:
                    break
            await db.sim_loads.replace_one({"load_id": load["load_id"]}, dict(load))

        # completion — week over AND all loads settled (factored = cash advanced = settled)
        if day > sim["duration_days"]:
            open_n = await db.sim_loads.count_documents(
                {"sim_id": sim["sim_id"], "status": {"$nin": ["paid", "factored", "posted"]}})
            if open_n == 0 or day > sim["duration_days"] + 3:
                sim["status"] = "complete"
                await _event(sim, "complete", f"🏁 WEEK COMPLETE · revenue ${ledger.get('revenue',0):,.0f} · TRUE net margin ${_net_margin(ledger):,.0f} (after carrier pay, factoring, overhead, claims, bad debt)")
            elif not sim.get("_settling"):
                sim["_settling"] = True
                await _event(sim, "day", f"🏁 Trading week over — {open_n} load(s) still settling: deliveries, invoices, factoring, shipper payments")

        await db.sim_state.update_one({"sim_id": sim["sim_id"]}, {"$set": {
            "sim_clock": sim["sim_clock"], "last_tick_at": sim["last_tick_at"],
            "sim_day": min(sim["sim_day"], sim["duration_days"]), "status": sim["status"],
            "ledger": ledger, "daily": sim["daily"], "spawned_today": sim["spawned_today"],
            "market": sim.get("market") or {},
            "_settling": sim.get("_settling", False),
            "_ledger_snap": sim.get("_ledger_snap") or {}}})
        return await state(user)  # type: ignore

    @router.get("/state")
    async def state(user=Depends(get_current_user)) -> Dict[str, Any]:
        sim = await _active_sim()
        if not sim:
            return {"active": False, "fleet_size": len(CARRIER_FLEET),
                    "doe_diesel": DOE_DIESEL_AVG, "fsc_per_mile": FSC_PER_MILE}
        loads = await db.sim_loads.find({"sim_id": sim["sim_id"]}, {"_id": 0}).to_list(500)
        events = await db.sim_events.find({"sim_id": sim["sim_id"]}, {"_id": 0}).sort("at", -1).to_list(45)
        ledger = sim["ledger"]
        net = _net_margin(ledger)
        by_status: Dict[str, int] = {}
        for l in loads:
            by_status[l["status"]] = by_status.get(l["status"], 0) + 1
        delivered = [l for l in loads if l["status"] in ("delivered", "invoiced", "factored", "paid")]
        otp = round(sum(1 for l in delivered if l.get("on_time")) / len(delivered) * 100, 1) if delivered else 100.0
        booked_n = sum(1 for l in loads if l["status"] != "posted")
        avg_daily = round(booked_n / max(1, sim["sim_day"]), 1)
        # carrier leaderboard
        cmap: Dict[str, Dict[str, Any]] = {}
        for l in loads:
            if not l.get("carrier"):
                continue
            c = cmap.setdefault(l["carrier"]["name"], {"carrier": l["carrier"]["name"], "loads": 0, "margin": 0.0})
            c["loads"] += 1
            if l["status"] in ("delivered", "invoiced", "factored", "paid"):
                c["margin"] += l["margin_usd"]
        leaderboard = sorted(cmap.values(), key=lambda x: -x["margin"])[:8]
        triage = [{"load_id": l["load_id"], **l["exception"],
                   "lane": f"{l['origin']['name']} → {l['dest']['name']}",
                   "carrier": (l.get("carrier") or {}).get("name")}
                  for l in loads if l.get("exception")]
        return {
            "active": True, "sim": {k: sim[k] for k in
                ("sim_id", "status", "sim_clock", "sim_day", "duration_days", "speed",
                 "autopilot", "auto_triage", "doe_diesel", "fsc_per_mile", "daily")},
            "market": sim.get("market") or {"diesel": DOE_DIESEL_AVG, "spot_index": 1.0, "cycle": "balanced"},
            "industry": {"overhead_daily": OVERHEAD_DAILY, "overhead_day_total": OVERHEAD_DAY_TOTAL,
                         "claim_prob": CLAIM_PROB, "bad_debt_prob": BAD_DEBT_PROB,
                         "fallthrough_prob": FALLTHROUGH_PROB, "quickpay_fee": QUICKPAY_FEE,
                         "carrier_payment_fee": CARRIER_PAYMENT_FEE},
            "ledger": {**ledger, "net_margin": net,
                       "outstanding_ar": round(ledger.get("revenue", 0) - ledger.get("cash_collected", 0), 2)},
            "kpis": {"total_loads": len(loads), "delivered": len(delivered),
                     "active_transit": by_status.get("in_transit", 0),
                     "on_time_pct": otp, "by_status": by_status,
                     "booked": booked_n, "avg_daily_loads": avg_daily},
            "loads": sorted(loads, key=lambda x: x.get("posted_at", ""), reverse=True),
            "events": events, "triage": triage, "leaderboard": leaderboard,
            "analysis": sim.get("analysis"),
        }

    async def _sim_summary_text(sim: Dict[str, Any]) -> str:
        loads = await db.sim_loads.find({"sim_id": sim["sim_id"]}, {"_id": 0}).to_list(500)
        led = sim["ledger"]
        delivered = [l for l in loads if l["status"] in ("delivered", "invoiced", "factored", "paid")]
        otp = round(sum(1 for l in delivered if l.get("on_time")) / len(delivered) * 100, 1) if delivered else 100.0
        lanes: Dict[str, Dict[str, float]] = {}
        cmap: Dict[str, Dict[str, float]] = {}
        exc = 0
        for l in loads:
            key = f"{l['origin']['name']} → {l['dest']['name']}"
            la = lanes.setdefault(key, {"loads": 0, "margin": 0.0})
            la["loads"] += 1
            if l["status"] in ("invoiced", "factored", "paid", "delivered"):
                la["margin"] += l["margin_usd"]
            if l.get("carrier"):
                c = cmap.setdefault(l["carrier"]["name"], {"loads": 0, "margin": 0.0})
                c["loads"] += 1
                c["margin"] += l["margin_usd"] if l["status"] in ("invoiced", "factored", "paid", "delivered") else 0
            if l.get("exception") or "resolved" in str(l.get("timeline", [])):
                pass
        exc = await db.sim_events.count_documents({"sim_id": sim["sim_id"], "type": "exception"})
        top_lanes = sorted(lanes.items(), key=lambda x: -x[1]["margin"])[:6]
        top_carr = sorted(cmap.items(), key=lambda x: -x[1]["margin"])[:6]
        hh = [l for l in loads if (l.get("market") or {}).get("headhaul") == "headhaul"]
        bh = [l for l in loads if (l.get("market") or {}).get("headhaul") == "backhaul"]
        def _avg_mpct(rows): return round(sum(r["margin_pct"] for r in rows) / len(rows), 1) if rows else 0
        market_line = (
            f"Market model: regional lane-imbalance + seasonality active. "
            f"Headhaul loads {len(hh)} (avg margin {_avg_mpct(hh)}%), "
            f"backhaul loads {len(bh)} (avg margin {_avg_mpct(bh)}%), balanced {len(loads) - len(hh) - len(bh)}. "
            f"Hot outbound: CA, Midwest. Hot inbound: FL, Northeast, Mountain. Backhaul-cheap: outbound FL/NE/Denver. "
            f"Seasonality month={_now().month} (reefer produce season May-Jul, van Q4 peak, flatbed Apr-Sep construction).\n"
        )
        net = led.get("revenue", 0) - led.get("carrier_pay", 0) - led.get("factoring_fees", 0) - led.get("exception_costs", 0)
        return (
            f"SIM WEEK RESULTS ({sim['sim_id']}, {sim['duration_days']} days, DOE diesel ${sim['doe_diesel']}, FSC ${sim['fsc_per_mile']}/mi):\n"
            f"Loads: {len(loads)} total, {len(delivered)} delivered, avg {round(sum(1 for l in loads if l['status']!='posted')/max(1,sim['duration_days']),1)}/day. On-time {otp}%.\n"
            f"Money: revenue ${led.get('revenue',0):,.0f} · carrier pay ${led.get('carrier_pay',0):,.0f} · FSC billed ${led.get('fsc_billed',0):,.0f} · "
            f"factoring fees ${led.get('factoring_fees',0):,.0f} · detention billed ${led.get('detention_billed',0):,.0f} · exception costs ${led.get('exception_costs',0):,.0f} · NET MARGIN ${net:,.0f} "
            f"({round(net/max(led.get('revenue',1),1)*100,1)}%). Cash collected ${led.get('cash_collected',0):,.0f}, AR outstanding ${led.get('revenue',0)-led.get('cash_collected',0):,.0f}.\n"
            f"Daily P&L: {sim.get('daily')}\n"
            f"Exceptions fired: {exc}.\n"
            f"{market_line}"
            f"Top lanes by margin: {[(k, v['loads'], round(v['margin'])) for k, v in top_lanes]}\n"
            f"Top carriers by margin: {[(k, v['loads'], round(v['margin'])) for k, v in top_carr]}\n"
        )

    @router.post("/analyze")
    async def analyze(user=Depends(get_current_user)) -> Dict[str, Any]:
        """Deep AI post-mortem of the sim week (Claude via Emergent key)."""
        sim = await _active_sim()
        if not sim:
            raise HTTPException(404, "No simulation found — run a week first")
        import os
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        summary = await _sim_summary_text(sim)
        try:
            chat = LlmChat(
                api_key=os.environ.get("EMERGENT_LLM_KEY"),
                session_id=f"sim-analyze-{sim['sim_id']}",
                system_message=(
                    "You are an elite freight brokerage operations analyst reviewing a simulated "
                    "operating week for Orisei Freight Solutions. Produce a sharp, actionable "
                    "post-mortem in markdown with sections: ## Verdict (one paragraph), "
                    "## What Worked, ## What Leaked Money, ## Lane & Carrier Strategy, "
                    "## Risk & Exceptions, ## 5 Moves For Next Week. Use the actual numbers. "
                    "Be direct — this operator wants truth, not cheerleading."),
            ).with_model("anthropic", "claude-sonnet-4-5-20250929")
            reply = await chat.send_message(UserMessage(text=summary))
        except Exception as e:
            raise HTTPException(502, f"AI provider error: {e}")
        await db.sim_state.update_one({"sim_id": sim["sim_id"]},
                                      {"$set": {"analysis": reply, "analyzed_at": _iso(_now())}})
        return {"ok": True, "analysis": reply}

    @router.post("/ask")
    async def ask(payload: Dict[str, Any], user=Depends(get_current_user)) -> Dict[str, Any]:
        """Interactive Q&A about the sim week, grounded in the actual results."""
        question = (payload.get("question") or "").strip()
        if not question:
            raise HTTPException(400, "question required")
        sim = await _active_sim()
        if not sim:
            raise HTTPException(404, "No simulation found")
        import os
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        summary = await _sim_summary_text(sim)
        history = await db.sim_qa.find({"sim_id": sim["sim_id"]}, {"_id": 0}).sort("at", -1).to_list(6)
        hist_txt = "\n".join(f"Q: {h['q']}\nA: {h['a'][:400]}" for h in reversed(history))
        try:
            chat = LlmChat(
                api_key=os.environ.get("EMERGENT_LLM_KEY"),
                session_id=f"sim-qa-{sim['sim_id']}",
                system_message=(
                    "You are the AI operations analyst for Orisei Freight Solutions, answering "
                    "questions about a simulated brokerage week. Ground every answer in the data "
                    "below. Be concise (under 180 words), numeric, and direct.\n\n"
                    f"{summary}\n\nPrior Q&A:\n{hist_txt}"),
            ).with_model("anthropic", "claude-sonnet-4-5-20250929")
            reply = await chat.send_message(UserMessage(text=question))
        except Exception as e:
            raise HTTPException(502, f"AI provider error: {e}")
        await db.sim_qa.insert_one({"sim_id": sim["sim_id"], "q": question, "a": reply,
                                    "at": _iso(_now()), "by": getattr(user, "user_id", None)})
        return {"ok": True, "question": question, "answer": reply}

    @router.post("/triage/{load_id}/resolve")
    async def resolve_triage(load_id: str, user=Depends(get_current_user)) -> Dict[str, Any]:
        load = await db.sim_loads.find_one({"load_id": load_id}, {"_id": 0})
        if not load or not load.get("exception"):
            raise HTTPException(404, "No open exception on that load")
        sim = await _active_sim()
        exc = load["exception"]
        cost = exc.get("cost", 0)
        if cost > 0 and sim:
            sim["ledger"]["exception_costs"] = sim["ledger"].get("exception_costs", 0) + cost
            await db.sim_state.update_one({"sim_id": sim["sim_id"]}, {"$set": {"ledger": sim["ledger"]}})
        load["exception"] = None
        await db.sim_loads.replace_one({"load_id": load_id}, dict(load))
        if sim:
            await _event(sim, "resolve", f"✅ Dispatcher resolved {load_id}: {exc['type']} — {exc['plan'][:80]}…", load_id)
        return {"ok": True, "plan_executed": exc["plan"], "cost_usd": cost}

    @router.post("/pause")
    async def pause(_=Depends(get_current_user)) -> Dict[str, Any]:
        r = await db.sim_state.update_one({"status": "running"}, {"$set": {"status": "paused"}})
        return {"ok": bool(r.modified_count)}

    @router.post("/resume")
    async def resume(_=Depends(get_current_user)) -> Dict[str, Any]:
        r = await db.sim_state.update_one({"status": "paused"},
                                          {"$set": {"status": "running", "last_tick_at": _iso(_now())}})
        return {"ok": bool(r.modified_count)}

    @router.post("/reset")
    async def reset(_=Depends(require_role("admin", "dispatcher"))) -> Dict[str, Any]:
        sims = await db.sim_state.find({}, {"sim_id": 1}).to_list(20)
        ids = [s["sim_id"] for s in sims]
        r1 = await db.sim_loads.delete_many({})
        r2 = await db.sim_events.delete_many({})
        r3 = await db.sim_state.delete_many({})
        r4 = await db.brokerage_bookings.delete_many({"sim_id": {"$in": ids}})
        r5 = await db.shipments.delete_many({"sim_id": {"$in": ids}})
        r6 = await db.brokerage_invoices.delete_many({"sim_id": {"$in": ids}})
        return {"ok": True, "purged": {"loads": r1.deleted_count, "events": r2.deleted_count,
                                        "sims": r3.deleted_count, "bookings": r4.deleted_count,
                                        "shipments": r5.deleted_count, "invoices": r6.deleted_count}}

    @router.get("/carriers")
    async def carriers(_=Depends(get_current_user)) -> Dict[str, Any]:
        return {"items": _fleet_with_ids(), "count": len(CARRIER_FLEET),
                "doe_diesel": DOE_DIESEL_AVG, "fsc_per_mile": FSC_PER_MILE}

    api_router.include_router(router)
    logger.info("Operation Sandbox router registered (/api/sim)")
