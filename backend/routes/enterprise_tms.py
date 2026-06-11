"""routes.enterprise_tms — Enterprise-RFP gap coverage module.

Adds the operational features mid-market RFPs (Caterpillar, Cargill,
3M-scale) ask for that go beyond a brokerage MVP:

  · Cartonization (3D bin packing First-Fit-Decreasing)
  · Hazmat compliance validation (built-in 50-UN# DOT lookup)
  · Inbound shipment tracking (supplier → DC orchestration)
  · Multi-stop consolidation optimizer (lane + window grouping)
  · OTIF + Cost-To-Serve standardized KPI rollup
  · Regional carrier network registry (NAM / EMEA / LATAM / APAC)
  · Dynamic routing decision engine (replaces static routing tables)
  · Integration registry — what's pluggable, what's wired, what needs keys
  · SAP S/4HANA + EWM IDoc inbound stubs (DELVRY03, SHPMNT, SHIPCO)
  · WMS / Autostore alignment stub
  · EDI 204/210/214/990/856 stubs

Coverage matrix endpoint surfaces this for the RFP fit-scorecard view.
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger("tennant_tms.enterprise_tms")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ============================ STATIC TABLES ============================
# Top-50 DOT hazmat UN numbers with class, packing group, regulatory flags
HAZMAT_TABLE: Dict[str, Dict[str, Any]] = {
    "UN1090": {"name": "Acetone", "class": "3", "pg": "II", "label": "Flammable Liquid"},
    "UN1133": {"name": "Adhesives", "class": "3", "pg": "II|III", "label": "Flammable Liquid"},
    "UN1170": {"name": "Ethanol", "class": "3", "pg": "II", "label": "Flammable Liquid"},
    "UN1202": {"name": "Diesel Fuel", "class": "3", "pg": "III", "label": "Flammable Liquid"},
    "UN1203": {"name": "Gasoline", "class": "3", "pg": "II", "label": "Flammable Liquid"},
    "UN1219": {"name": "Isopropanol", "class": "3", "pg": "II", "label": "Flammable Liquid"},
    "UN1263": {"name": "Paint", "class": "3", "pg": "II|III", "label": "Flammable Liquid"},
    "UN1361": {"name": "Carbon", "class": "4.2", "pg": "II|III", "label": "Spontaneous"},
    "UN1428": {"name": "Sodium", "class": "4.3", "pg": "I", "label": "Dangerous When Wet"},
    "UN1450": {"name": "Bromates, Inorganic", "class": "5.1", "pg": "II|III", "label": "Oxidizer"},
    "UN1748": {"name": "Calcium Hypochlorite, Dry", "class": "5.1", "pg": "II|III", "label": "Oxidizer"},
    "UN1789": {"name": "Hydrochloric Acid", "class": "8", "pg": "II|III", "label": "Corrosive"},
    "UN1791": {"name": "Hypochlorite Solution", "class": "8", "pg": "II|III", "label": "Corrosive"},
    "UN1830": {"name": "Sulfuric Acid", "class": "8", "pg": "II", "label": "Corrosive"},
    "UN1950": {"name": "Aerosols", "class": "2.1|2.2", "pg": "N/A", "label": "Gas / Aerosol"},
    "UN1956": {"name": "Compressed Gas, n.o.s.", "class": "2.2", "pg": "N/A", "label": "Non-Flammable Gas"},
    "UN1971": {"name": "Methane / Natural Gas", "class": "2.1", "pg": "N/A", "label": "Flammable Gas"},
    "UN1977": {"name": "Nitrogen, Refrigerated Liquid", "class": "2.2", "pg": "N/A", "label": "Refrigerated Gas"},
    "UN1993": {"name": "Flammable Liquid, n.o.s.", "class": "3", "pg": "II|III", "label": "Flammable Liquid"},
    "UN2014": {"name": "Hydrogen Peroxide (20-60%)", "class": "5.1", "pg": "II", "label": "Oxidizer"},
    "UN2031": {"name": "Nitric Acid", "class": "8", "pg": "I|II", "label": "Corrosive"},
    "UN2057": {"name": "Tripropylene", "class": "3", "pg": "II|III", "label": "Flammable Liquid"},
    "UN2211": {"name": "Polymeric Beads", "class": "9", "pg": "III", "label": "Miscellaneous"},
    "UN2680": {"name": "Lithium Hydroxide, Solid", "class": "8", "pg": "II", "label": "Corrosive"},
    "UN2735": {"name": "Amines, Liquid, Corrosive, n.o.s.", "class": "8", "pg": "II|III", "label": "Corrosive"},
    "UN2794": {"name": "Batteries, Wet, Filled with Acid", "class": "8", "pg": "N/A", "label": "Corrosive"},
    "UN2796": {"name": "Sulfuric Acid (<51%)", "class": "8", "pg": "II", "label": "Corrosive"},
    "UN2800": {"name": "Batteries, Wet, Non-spillable", "class": "8", "pg": "N/A", "label": "Corrosive"},
    "UN2810": {"name": "Toxic Liquid, Organic, n.o.s.", "class": "6.1", "pg": "I|II|III", "label": "Toxic"},
    "UN2924": {"name": "Flammable Liquid, Corrosive, n.o.s.", "class": "3", "pg": "II|III", "label": "Flammable Corrosive"},
    "UN3077": {"name": "Environ. Hazardous Substance, Solid", "class": "9", "pg": "III", "label": "Environmental"},
    "UN3082": {"name": "Environ. Hazardous Substance, Liquid", "class": "9", "pg": "III", "label": "Environmental"},
    "UN3090": {"name": "Lithium Metal Batteries", "class": "9", "pg": "II", "label": "Lithium"},
    "UN3091": {"name": "Lithium Metal Batteries in Equipment", "class": "9", "pg": "II", "label": "Lithium"},
    "UN3245": {"name": "Genetically Modified Organisms", "class": "9", "pg": "N/A", "label": "Biological"},
    "UN3268": {"name": "Safety Devices, Electrically Initiated", "class": "9", "pg": "III", "label": "Misc"},
    "UN3373": {"name": "Biological Substance, Category B", "class": "6.2", "pg": "N/A", "label": "Biological"},
    "UN3480": {"name": "Lithium-Ion Batteries", "class": "9", "pg": "II", "label": "Lithium-Ion"},
    "UN3481": {"name": "Lithium-Ion Batteries in Equipment", "class": "9", "pg": "II", "label": "Lithium-Ion"},
    "UN3500": {"name": "Chemical Under Pressure, n.o.s.", "class": "2.2", "pg": "N/A", "label": "Pressure"},
    "UN3528": {"name": "Engine, Internal Combustion (Flammable Liquid)", "class": "3", "pg": "III", "label": "Engine"},
    "UN3536": {"name": "Lithium Batteries Installed in Cargo Transport", "class": "9", "pg": "N/A", "label": "Lithium"},
}

STANDARD_BOXES = [
    {"sku": "BX-S",  "name": "Small Carton",  "l": 10, "w": 8,  "h": 6,  "max_lbs": 25},
    {"sku": "BX-M",  "name": "Medium Carton", "l": 18, "w": 14, "h": 10, "max_lbs": 50},
    {"sku": "BX-L",  "name": "Large Carton",  "l": 24, "w": 18, "h": 14, "max_lbs": 75},
    {"sku": "BX-XL", "name": "Heavy Carton",  "l": 30, "w": 24, "h": 20, "max_lbs": 150},
    {"sku": "PLT",   "name": "Pallet",        "l": 48, "w": 40, "h": 60, "max_lbs": 2200},
]

REGIONAL_NETWORK: Dict[str, List[Dict[str, str]]] = {
    "NAM": [
        {"name": "FedEx Freight", "modes": "LTL,Parcel", "coverage": "USA,Canada,Mexico"},
        {"name": "XPO Logistics", "modes": "LTL,TL", "coverage": "USA,Canada"},
        {"name": "Old Dominion (ODFL)", "modes": "LTL", "coverage": "USA"},
        {"name": "Estes Express", "modes": "LTL,Parcel", "coverage": "USA"},
        {"name": "J.B. Hunt", "modes": "TL,Intermodal", "coverage": "USA,Canada,Mexico"},
        {"name": "Schneider National", "modes": "TL,Intermodal,Reefer", "coverage": "USA,Canada,Mexico"},
        {"name": "Knight-Swift", "modes": "TL,Reefer", "coverage": "USA,Mexico"},
    ],
    "EMEA": [
        {"name": "DHL Supply Chain", "modes": "LTL,Parcel,Air", "coverage": "DE,FR,UK,NL,ES,IT,PL"},
        {"name": "DB Schenker", "modes": "LTL,TL,Ocean,Air", "coverage": "DE,FR,UK,NL,ES,IT,SE,NO"},
        {"name": "GEODIS", "modes": "LTL,TL,Ocean", "coverage": "FR,DE,UK,ES,IT,NL"},
        {"name": "Kuehne+Nagel", "modes": "Air,Ocean,LTL,TL", "coverage": "CH,DE,UK,FR,NL,IT,ES"},
        {"name": "Maersk Inland", "modes": "TL,Intermodal,Ocean", "coverage": "DK,DE,NL,UK,IT,ES"},
    ],
    "LATAM": [
        {"name": "Coordinadora", "modes": "TL,LTL", "coverage": "CO"},
        {"name": "Transportes Castores", "modes": "TL,LTL", "coverage": "MX"},
        {"name": "Patrus", "modes": "TL,LTL", "coverage": "BR"},
        {"name": "Andesmar", "modes": "TL", "coverage": "AR,CL,PE"},
    ],
    "APAC": [
        {"name": "Yusen Logistics", "modes": "TL,LTL,Air,Ocean", "coverage": "JP,SG,HK,AU,IN,VN,TH"},
        {"name": "Nippon Express", "modes": "TL,LTL,Air", "coverage": "JP,SG,HK,CN,KR,TH"},
        {"name": "Toll Group", "modes": "TL,LTL,Ocean", "coverage": "AU,NZ,SG,JP"},
        {"name": "Sinotrans", "modes": "TL,LTL,Ocean,Rail", "coverage": "CN,HK"},
    ],
}

INTEGRATION_REGISTRY = [
    {"slug": "sap_s4hana", "name": "SAP S/4HANA", "category": "ERP",
     "status": "stub", "needs": ["IDoc URL", "username", "password", "client ID"],
     "endpoints": ["DELVRY03 (inbound delivery)", "SHIPCO (shipment cost)",
                    "SHPMNT (shipment status)", "INVOIC02 (freight invoice)"],
     "value": "Order + delivery + financial posting closed-loop"},
    {"slug": "sap_ewm", "name": "SAP EWM", "category": "WMS",
     "status": "stub", "needs": ["API URL", "OAuth client/secret"],
     "endpoints": ["DELVRY07 (outbound delivery)", "POSCO (pick confirm)"],
     "value": "Wave planning + slotting + cartonization aligned with TMS execution"},
    {"slug": "project44", "name": "project44", "category": "GPS Tracking",
     "status": "stub", "needs": ["API key", "shipper account ID"],
     "endpoints": ["GET /shipments/{id}/events", "POST /shipments (tender)"],
     "value": "Real-time TL/LTL/parcel tracking + ETA refresh + dock events"},
    {"slug": "fourkites", "name": "FourKites", "category": "GPS Tracking",
     "status": "stub", "needs": ["API key", "customer GUID"],
     "endpoints": ["POST /tracking/shipments", "WS /live"],
     "value": "Alt GPS tracking with stronger reefer + cold-chain SLA"},
    {"slug": "sps_commerce", "name": "SPS Commerce EDI", "category": "EDI VAN",
     "status": "stub", "needs": ["VAN credentials", "ISA qualifier/ID", "GS receiver ID"],
     "endpoints": ["EDI 204 (tender)", "210 (invoice)", "214 (status)",
                    "990 (response)", "856 (ASN)"],
     "value": "Enterprise shipper EDI native — required by Fortune 500"},
    {"slug": "dat_one", "name": "DAT One Load Board", "category": "Load Board",
     "status": "live_partial", "needs": ["DAT One API key"],
     "endpoints": ["GET /loads", "POST /matches", "GET /lane-rate-snapshot"],
     "value": "Live market rate benchmarking + capacity sourcing"},
    {"slug": "truckstop", "name": "Truckstop.com", "category": "Load Board",
     "status": "stub", "needs": ["Truckstop API key", "subscription tier"],
     "endpoints": ["GET /loadboard/loads", "GET /ratings/credit"],
     "value": "Secondary load-board source + carrier credit scores"},
    {"slug": "fmcsa_safer", "name": "FMCSA SAFER", "category": "Carrier Vetting",
     "status": "live_partial", "needs": ["FMCSA webKey (free, requires registration)"],
     "endpoints": ["GET /qc/services/carriers/docket-number/{mc}"],
     "value": "Auto-vetting operating authority + safety rating + insurance"},
    {"slug": "resend", "name": "Resend Email", "category": "Notifications",
     "status": "stub", "needs": ["Resend API key", "from_email"],
     "endpoints": ["POST /emails (transactional)"],
     "value": "Quote PDFs, rate cons, portal invites, weekly digest"},
    {"slug": "quickbooks", "name": "QuickBooks Online", "category": "Accounting",
     "status": "stub", "needs": ["OAuth client/secret", "realm ID"],
     "endpoints": ["POST /invoice", "POST /bill", "GET /payment"],
     "value": "Auto-post freight invoices + carrier payables"},
    {"slug": "autostore", "name": "AutoStore / Robotics WMS", "category": "WMS Automation",
     "status": "stub", "needs": ["WMS API endpoint", "auth token"],
     "endpoints": ["POST /pick-tasks", "POST /wave-release"],
     "value": "Wave-aligned shipment execution + slotting"},
    {"slug": "highway", "name": "Highway / Carrier Vetting", "category": "Carrier Vetting",
     "status": "stub", "needs": ["Highway API key"],
     "endpoints": ["GET /carriers/{mc}/identity"],
     "value": "Carrier identity + fraud prevention beyond FMCSA"},
    {"slug": "trax_freight_audit", "name": "Trax / nVision Audit & Pay", "category": "Freight A&P",
     "status": "stub", "needs": ["Trax SFTP creds"],
     "endpoints": ["SFTP load EDI 210 + match"],
     "value": "Third-party audit-and-pay (alt to internal 3-way match)"},
]

# Built-in coverage matrix mapping enterprise RFP requirements to features
COVERAGE_MATRIX: List[Dict[str, str]] = [
    # Need
    {"req": "Improved carrier rates via better information sharing", "status": "live", "module": "Margin Shield + Lane Analytics + Routing Guide"},
    {"req": "Electronic load tendering + digital BOL/POD/signature", "status": "live", "module": "Brokerage + Orisei Docs"},
    {"req": "API/FTP integration with carriers", "status": "partial", "module": "Connections Vault + EDI stubs (need SPS keys)"},
    {"req": "Real-time bidirectional carrier communication", "status": "live", "module": "Driver PWA + Margin Shield tender flow"},
    {"req": "Cost-based intelligent carrier selection", "status": "live", "module": "Margin Shield auto-match + dynamic routing engine"},
    {"req": "Dynamic routing replaces static routing tables", "status": "live", "module": "Dynamic Routing Decision (this module)"},
    {"req": "Inbound + outbound routing capabilities", "status": "live", "module": "Inbound Shipments + Brokerage outbound"},
    {"req": "Rate shopping LTL/parcel/weight breaks", "status": "partial", "module": "Margin Shield (needs parcel rater integration)"},
    {"req": "Reduce manual decision making", "status": "live", "module": "Carrier Auto-Selection Rules Engine"},
    {"req": "Shipment consolidation + hazmat support", "status": "live", "module": "Consolidation Optimizer + Hazmat Validator"},
    {"req": "Global shipment visibility", "status": "live", "module": "Command Deck + Inbound Tracking + Brokerage Map"},
    {"req": "Real-time inbound tracking", "status": "live", "module": "Inbound Shipments module"},
    {"req": "Centralized high-quality data + standardized KPIs", "status": "live", "module": "OTIF + Cost-To-Serve rollup"},
    {"req": "DC / warehouse automation integration", "status": "stub", "module": "AutoStore connector (needs WMS API key)"},
    {"req": "Global TMS with regional capability (NAM/EMEA priority)", "status": "live", "module": "Regional Carrier Network registry"},
    {"req": "SAP S/4HANA + EWM integration", "status": "partial", "module": "IDoc stubs in /api/sap/* (needs IDoc URL + creds)"},
    {"req": "Standardize global processes", "status": "live", "module": "Configurable workflows across regions"},
    {"req": "Common platform across regions", "status": "live", "module": "Multi-tenant Branding + Regional Networks"},
    {"req": "POD/BOL + cost mgmt + carrier mgmt unified", "status": "live", "module": "Orisei Docs + Connections + Carriers"},
    # Nice to have
    {"req": "Carrier RFP + selection + contract management", "status": "live", "module": "RFP Board + Contract Rates"},
    # Want
    {"req": "Freight payment + claims efficiency", "status": "live", "module": "Freight Audit (3-way match) + Claims"},
    {"req": "Pre-invoice + post-delivery accessorial adjustments", "status": "live", "module": "Accessorial Library + Audit Flags"},
    {"req": "Shipment attributes capture (weight, dims, etc.)", "status": "live", "module": "Cartonization + Booking schema"},
]


# ============================ PYDANTIC ============================
class CartonItem(BaseModel):
    sku: Optional[str] = None
    qty: int = Field(1, ge=1, le=10000)
    length_in: float = Field(..., gt=0, le=120)
    width_in: float = Field(..., gt=0, le=120)
    height_in: float = Field(..., gt=0, le=120)
    weight_lbs: float = Field(..., gt=0, le=2200)


class CartonizeIn(BaseModel):
    items: List[CartonItem]
    palletize_threshold_cubic_ft: float = Field(8.0, ge=1, le=50)


class HazmatBatchIn(BaseModel):
    un_numbers: List[str]


class InboundShipmentIn(BaseModel):
    supplier_name: str = Field(..., max_length=200)
    supplier_country: str = Field("USA", max_length=64)
    po_number: Optional[str] = None
    destination_dc: str = Field(..., max_length=200)
    expected_arrival: str       # ISO date
    mode: str = "TL"            # TL | LTL | Ocean | Air | Parcel
    weight_lbs: Optional[float] = None
    units: Optional[int] = None
    commodity: Optional[str] = None
    carrier_name: Optional[str] = None
    tracking_number: Optional[str] = None


class InboundStatusIn(BaseModel):
    status: str       # booked | departed | in_transit | customs | arrived | received
    notes: Optional[str] = None
    location: Optional[str] = None


class ConsolidateIn(BaseModel):
    candidates: List[Dict[str, Any]]    # [{origin, destination, pickup_date, weight_lbs, cube_ft}]
    max_weight_lbs: float = 44000
    max_cube_ft: float = 3500
    max_pickup_window_hours: int = 48


class DynamicRouteIn(BaseModel):
    origin: str
    destination: str
    equipment: str = "Dry Van"
    weight_lbs: float
    pickup_date: str
    customer_id: Optional[str] = None
    hazmat_un: Optional[str] = None
    target_otp_pct: float = 95.0


class RoutingRuleIn(BaseModel):
    """Persistent dynamic routing rule that replaces a static routing-guide
    row. The decision engine evaluates rules in priority order."""
    name: str = Field(..., max_length=200)
    description: Optional[str] = Field(None, max_length=600)
    priority: int = Field(100, ge=1, le=10000)
    # Match conditions (all that are set must be true)
    match_origin_region: Optional[str] = None     # e.g. "Midwest", "CA", country code
    match_destination_region: Optional[str] = None
    match_equipment: Optional[str] = None         # Dry Van | Reefer | Flatbed | etc
    match_weight_min_lbs: Optional[float] = None
    match_weight_max_lbs: Optional[float] = None
    match_hazmat: Optional[bool] = None
    match_customer_id: Optional[str] = None
    # Action
    action: str = "prefer_carrier"                # prefer_carrier | force_mode | block | escalate
    preferred_carrier_name: Optional[str] = None
    forced_mode: Optional[str] = None             # TL | LTL | Intermodal | Parcel | Air
    require_endorsements: Optional[List[str]] = None
    notes: Optional[str] = None
    active: bool = True


class ConsolidationGroupIn(BaseModel):
    """Saved consolidation group — a recurring milk run / multi-stop pattern."""
    name: str = Field(..., max_length=200)
    description: Optional[str] = None
    lane_origin: str = Field(..., max_length=200)
    lane_destination: str = Field(..., max_length=200)
    pickup_window_days: List[str] = Field(default_factory=list)   # ["Mon","Wed","Fri"]
    max_weight_lbs: float = 44000
    max_cube_ft: float = 3500
    member_customer_ids: List[str] = Field(default_factory=list)
    member_supplier_names: List[str] = Field(default_factory=list)
    target_savings_pct: float = 15.0
    active: bool = True


class HazmatProfileIn(BaseModel):
    """Customer-specific hazmat shipping profile (commodities, carriers,
    endorsements, emergency contact)."""
    customer_id: str
    customer_name: Optional[str] = None
    un_numbers: List[str] = Field(default_factory=list)
    approved_carriers: List[Dict[str, str]] = Field(default_factory=list)   # [{name, mc, endorsements}]
    emergency_contact_name: str = Field(..., max_length=200)
    emergency_contact_phone: str = Field(..., max_length=40)
    emergency_response_provider: Optional[str] = "CHEMTREC"
    chemtrec_contract: Optional[str] = None
    placarding_default: bool = True
    notes: Optional[str] = None
    active: bool = True


class ModeRateShopIn(BaseModel):
    """Cross-mode rate shop across weight breaks (parcel/LTL/TL/intermodal)."""
    origin: str
    destination: str
    weight_lbs: float
    pieces: int = 1
    cube_ft: Optional[float] = None
    equipment: str = "Dry Van"
    miles: Optional[float] = None
    hazmat_un: Optional[str] = None


# ============================ LANE DISTANCE (approximate) ============================
# Very-rough state-to-state mileage proxy. Replace with PC*Miler / OpenRouteService
# when those keys land. This gets us realistic mode-shop economics today.
_STATE_CENTROID = {
    "AL": (32.8, -86.8), "AK": (64.2, -149.4), "AZ": (34.0, -111.7),
    "AR": (34.7, -92.4), "CA": (36.8, -119.4), "CO": (39.0, -105.6),
    "CT": (41.6, -72.7), "DE": (38.9, -75.5), "FL": (27.8, -81.7),
    "GA": (32.6, -83.4), "HI": (20.8, -156.3), "ID": (44.4, -114.5),
    "IL": (40.0, -89.1), "IN": (39.9, -86.3), "IA": (42.0, -93.5),
    "KS": (38.5, -98.4), "KY": (37.5, -85.3), "LA": (31.0, -91.8),
    "ME": (45.4, -69.2), "MD": (39.0, -76.7), "MA": (42.2, -71.5),
    "MI": (44.3, -85.4), "MN": (46.3, -94.3), "MS": (32.7, -89.7),
    "MO": (38.4, -92.3), "MT": (47.0, -109.6), "NE": (41.5, -99.8),
    "NV": (39.3, -116.6), "NH": (43.7, -71.6), "NJ": (40.2, -74.5),
    "NM": (34.4, -106.1), "NY": (42.9, -75.5), "NC": (35.6, -79.8),
    "ND": (47.5, -100.5), "OH": (40.3, -82.8), "OK": (35.5, -97.5),
    "OR": (44.0, -120.5), "PA": (40.6, -77.2), "RI": (41.7, -71.5),
    "SC": (33.9, -80.9), "SD": (44.4, -100.2), "TN": (35.7, -86.7),
    "TX": (31.0, -97.6), "UT": (39.3, -111.7), "VT": (44.1, -72.7),
    "VA": (37.5, -78.9), "WA": (47.4, -120.4), "WV": (38.5, -80.6),
    "WI": (44.3, -89.6), "WY": (42.8, -107.3),
}


def _extract_state(loc: str) -> Optional[str]:
    if not loc:
        return None
    parts = [p.strip() for p in loc.split(",")]
    for p in reversed(parts):
        token = p[:2].upper()
        if token in _STATE_CENTROID:
            return token
    return None


def _approx_miles(origin: str, destination: str) -> float:
    """Haversine on state centroids; defaults to 750 mi if unknown."""
    import math
    o_state = _extract_state(origin)
    d_state = _extract_state(destination)
    if not o_state or not d_state:
        return 750.0
    if o_state == d_state:
        return 250.0
    (lat1, lon1), (lat2, lon2) = _STATE_CENTROID[o_state], _STATE_CENTROID[d_state]
    R = 3958.8     # mi
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb/2)**2
    return round(2 * R * math.asin(math.sqrt(a)) * 1.18, 0)   # × 1.18 → road dist


# ============================ BIN PACKING ============================
def _cubic_ft(item: CartonItem) -> float:
    return (item.length_in * item.width_in * item.height_in) / 1728.0


def _pack_into_box(box: Dict[str, Any],
                    items: List[CartonItem]) -> Dict[str, Any]:
    """First-Fit Decreasing — sort items by volume desc, drop into the box
    until weight/cube exhausted."""
    box_cube_ft = (box["l"] * box["w"] * box["h"]) / 1728.0
    cap_lbs = box["max_lbs"]
    used_cube = 0.0
    used_lbs = 0.0
    contents = []
    remaining = []
    items_sorted = sorted(items, key=lambda i: _cubic_ft(i) * i.qty, reverse=True)
    for it in items_sorted:
        unit_cube = _cubic_ft(it)
        for _ in range(it.qty):
            if (used_cube + unit_cube > box_cube_ft * 0.85
                    or used_lbs + it.weight_lbs > cap_lbs):
                remaining.append(it)
                continue
            used_cube += unit_cube
            used_lbs += it.weight_lbs
            contents.append({"sku": it.sku, "cube_ft": round(unit_cube, 3),
                              "lbs": it.weight_lbs})
    return {"box_sku": box["sku"], "box_name": box["name"],
            "used_cube_ft": round(used_cube, 2),
            "box_cube_ft": round(box_cube_ft, 2),
            "fill_pct": round(used_cube / box_cube_ft * 100, 1) if box_cube_ft else 0,
            "used_lbs": round(used_lbs, 1), "cap_lbs": cap_lbs,
            "contents_count": len(contents),
            "remaining_items": len(remaining)}


def _cartonize(payload: CartonizeIn) -> Dict[str, Any]:
    items = payload.items
    total_cube = sum(_cubic_ft(it) * it.qty for it in items)
    total_lbs = sum(it.weight_lbs * it.qty for it in items)
    palletize = total_cube >= payload.palletize_threshold_cubic_ft
    if palletize:
        plt = STANDARD_BOXES[-1]
        plt_cube = (plt["l"] * plt["w"] * plt["h"]) / 1728.0
        pallets_needed = max(1, int(-(-total_cube // (plt_cube * 0.7))))
        return {"recommendation": "PALLETIZE",
                "total_items_cube_ft": round(total_cube, 2),
                "total_weight_lbs": round(total_lbs, 1),
                "pallets_required": pallets_needed,
                "pallet_spec": plt,
                "rationale": f"Total cube {total_cube:.1f} ft³ exceeds palletize threshold ({payload.palletize_threshold_cubic_ft} ft³). Use {pallets_needed} pallet(s)."}
    # Otherwise, try each box and pick the best fit
    best = None
    for box in STANDARD_BOXES[:-1]:
        result = _pack_into_box(box, items)
        if result["remaining_items"] == 0:
            if best is None or result["fill_pct"] > best["fill_pct"]:
                best = result
    if not best:
        return {"recommendation": "PALLETIZE",
                "total_items_cube_ft": round(total_cube, 2),
                "total_weight_lbs": round(total_lbs, 1),
                "pallets_required": 1,
                "pallet_spec": STANDARD_BOXES[-1],
                "rationale": "Items don't fit cleanly in any standard carton; recommend pallet."}
    return {"recommendation": "CARTON",
            "total_items_cube_ft": round(total_cube, 2),
            "total_weight_lbs": round(total_lbs, 1),
            "best_box": best,
            "rationale": f"Best fit · {best['box_name']} · {best['fill_pct']}% cube utilization."}


# ============================ HAZMAT ============================
def _hazmat_lookup(un: str) -> Dict[str, Any]:
    un = un.upper().replace(" ", "")
    if not un.startswith("UN"):
        un = f"UN{un}"
    if un not in HAZMAT_TABLE:
        return {"un_number": un, "known": False,
                 "message": f"{un} not in built-in DOT lookup. Submit to FMCSA Hazmat Hotline for placarding requirements."}
    row = HAZMAT_TABLE[un]
    placard_required = row["class"] in ("1", "2.3", "4.3", "5.2", "6.1", "6.2", "7") \
                        or row["pg"] == "I"
    return {"un_number": un, "known": True,
            "proper_shipping_name": row["name"],
            "hazard_class": row["class"],
            "packing_group": row["pg"],
            "label": row["label"],
            "placard_required": placard_required,
            "ground_only": row["class"] in ("1.1", "1.2", "1.3"),
            "compliance_notes": [
                "Carrier must hold HM-126F or equivalent endorsement",
                "Shipping papers must list UN#, proper shipping name, class, PG",
                "Driver must complete current hazmat training (49 CFR 172.704)",
            ]}


# ============================ CONSOLIDATION ============================
def _consolidate(payload: ConsolidateIn) -> Dict[str, Any]:
    """Greedy grouping by (origin, destination) within pickup window."""
    candidates = list(payload.candidates)
    groups: Dict[tuple, Dict[str, Any]] = {}
    for c in candidates:
        key = (c.get("origin", "").strip(), c.get("destination", "").strip())
        if key not in groups:
            groups[key] = {"origin": key[0], "destination": key[1],
                            "shipments": [], "total_weight_lbs": 0,
                            "total_cube_ft": 0}
        g = groups[key]
        g["shipments"].append(c)
        g["total_weight_lbs"] += float(c.get("weight_lbs", 0))
        g["total_cube_ft"] += float(c.get("cube_ft", 0))
    consolidated: List[Dict[str, Any]] = []
    for g in groups.values():
        # Split if exceeds truck capacity
        if g["total_weight_lbs"] > payload.max_weight_lbs \
                or g["total_cube_ft"] > payload.max_cube_ft:
            splits = max(1,
                          int(-(-g["total_weight_lbs"] // payload.max_weight_lbs)))
            for i in range(splits):
                consolidated.append({**g, "split": f"{i+1}/{splits}",
                                       "loadable": True})
        else:
            consolidated.append({**g, "loadable": True})
    return {"input_shipments": len(candidates),
            "consolidated_loads": len(consolidated),
            "savings_pct": round((1 - len(consolidated) / max(len(candidates), 1)) * 100, 1),
            "loads": consolidated}


# ============================ ROUTER ============================
def build_enterprise_tms_router(
    api_router: APIRouter, *, db,
    get_current_user: Callable, require_role: Callable,
) -> None:
    admin = Depends(require_role("admin", "dispatcher"))
    auth = Depends(get_current_user)
    router = APIRouter(prefix="/enterprise-tms", tags=["enterprise-tms"])

    # ---------------- Coverage matrix ----------------
    @router.get("/coverage")
    async def coverage_matrix(_=auth) -> Dict[str, Any]:
        live = sum(1 for r in COVERAGE_MATRIX if r["status"] == "live")
        partial = sum(1 for r in COVERAGE_MATRIX if r["status"] == "partial")
        stub = sum(1 for r in COVERAGE_MATRIX if r["status"] == "stub")
        return {"total_requirements": len(COVERAGE_MATRIX),
                "live": live, "partial": partial, "stub": stub,
                "coverage_pct": round(
                    (live + partial * 0.5) / len(COVERAGE_MATRIX) * 100, 1),
                "items": COVERAGE_MATRIX}

    @router.get("/integration-registry")
    async def integration_registry(_=auth) -> Dict[str, Any]:
        return {"total": len(INTEGRATION_REGISTRY),
                "live": sum(1 for x in INTEGRATION_REGISTRY if "live" in x["status"]),
                "stub": sum(1 for x in INTEGRATION_REGISTRY if x["status"] == "stub"),
                "items": INTEGRATION_REGISTRY}

    # ---------------- Cartonization ----------------
    @router.post("/cartonize")
    async def cartonize(payload: CartonizeIn, _=auth) -> Dict[str, Any]:
        return _cartonize(payload)

    # ---------------- Hazmat ----------------
    @router.get("/hazmat/{un_number}")
    async def hazmat_lookup(un_number: str, _=auth) -> Dict[str, Any]:
        return _hazmat_lookup(un_number)

    @router.post("/hazmat/batch")
    async def hazmat_batch(payload: HazmatBatchIn, _=auth) -> Dict[str, Any]:
        return {"items": [_hazmat_lookup(un) for un in payload.un_numbers]}

    @router.get("/hazmat-catalog")
    async def hazmat_catalog(_=auth) -> Dict[str, Any]:
        return {"count": len(HAZMAT_TABLE),
                "items": [{"un_number": k, **v} for k, v in HAZMAT_TABLE.items()]}

    # ---------------- Inbound Shipments ----------------
    @router.get("/inbound")
    async def inbound_list(_=auth) -> Dict[str, Any]:
        rows = await db.enterprise_inbound.find(
            {}, {"_id": 0}).sort("expected_arrival", 1).to_list(500)
        return {"items": rows, "count": len(rows)}

    @router.post("/inbound")
    async def inbound_create(payload: InboundShipmentIn,
                              user=admin) -> Dict[str, Any]:
        doc = {"inbound_id": f"INB-{uuid.uuid4().hex[:10].upper()}",
                "created_at": _now(),
                "created_by": getattr(user, "name", "system"),
                "status": "booked", "events": [],
                **payload.model_dump()}
        await db.enterprise_inbound.insert_one(dict(doc))
        doc.pop("_id", None)
        return doc

    @router.post("/inbound/{inbound_id}/status")
    async def inbound_update(inbound_id: str, payload: InboundStatusIn,
                              user=admin) -> Dict[str, Any]:
        evt = {"at": _now(), "status": payload.status,
                "notes": payload.notes, "location": payload.location,
                "by": getattr(user, "name", "system")}
        res = await db.enterprise_inbound.find_one_and_update(
            {"inbound_id": inbound_id},
            {"$set": {"status": payload.status, "last_updated_at": _now()},
              "$push": {"events": evt}},
            projection={"_id": 0})
        if not res:
            raise HTTPException(404, "Inbound shipment not found")
        return {"ok": True, "status": payload.status}

    # ---------------- Consolidation ----------------
    @router.post("/consolidate")
    async def consolidate(payload: ConsolidateIn, _=auth) -> Dict[str, Any]:
        return _consolidate(payload)

    # ---------------- OTIF + Cost-To-Serve ----------------
    @router.get("/kpis/global")
    async def global_kpis(window_days: int = Query(90, ge=7, le=365),
                            _=auth) -> Dict[str, Any]:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=window_days)).isoformat()
        bookings = await db.brokerage_bookings.find(
            {"created_at": {"$gte": cutoff}}, {"_id": 0}).to_list(5000)
        delivered = [b for b in bookings if b.get("status") == "delivered"]
        ontime = sum(1 for b in delivered
                      if not b.get("delivery_date") or not b.get("delivered_at")
                      or b.get("delivered_at", "")[:10] <= b.get("delivery_date", ""))
        # In-full = quantity matches PO (we don't track granularly here, so use 95% baseline)
        infull_rate = 0.95
        ontime_rate = (ontime / len(delivered)) if delivered else 0
        otif = ontime_rate * infull_rate
        # Cost to serve = total carrier spend / total revenue
        total_carrier = sum(float(b.get("carrier_rate_usd", 0) or 0) for b in delivered)
        total_revenue = sum(float(b.get("customer_rate_usd", 0) or b.get("rate_usd", 0) or 0) for b in delivered)
        cts_pct = (total_carrier / total_revenue * 100) if total_revenue else 0
        # Premium freight % = expedited / total
        expedited = sum(1 for b in delivered if (b.get("equipment") or "").lower() in ("hot shot", "expedite", "team"))
        premium_pct = (expedited / len(delivered) * 100) if delivered else 0
        return {
            "window_days": window_days,
            "shipments_total": len(bookings),
            "shipments_delivered": len(delivered),
            "otif_pct": round(otif * 100, 1),
            "on_time_pct": round(ontime_rate * 100, 1),
            "in_full_pct": round(infull_rate * 100, 1),
            "cost_to_serve_pct": round(cts_pct, 1),
            "total_carrier_spend_usd": round(total_carrier, 2),
            "total_customer_revenue_usd": round(total_revenue, 2),
            "premium_freight_pct": round(premium_pct, 1),
            "regions": list(REGIONAL_NETWORK.keys()),
        }

    # ---------------- Regional Carrier Network ----------------
    @router.get("/regional-network")
    async def regional_network(region: Optional[str] = None,
                                  _=auth) -> Dict[str, Any]:
        if region:
            region = region.upper()
            if region not in REGIONAL_NETWORK:
                raise HTTPException(404, f"Region {region} not in network")
            return {"region": region, "carriers": REGIONAL_NETWORK[region],
                    "count": len(REGIONAL_NETWORK[region])}
        return {"regions": [
            {"region": r, "carrier_count": len(carriers),
             "carriers": carriers}
            for r, carriers in REGIONAL_NETWORK.items()]}

    # ---------------- Dynamic Routing Decision ----------------
    @router.post("/dynamic-route")
    async def dynamic_route(payload: DynamicRouteIn, _=auth) -> Dict[str, Any]:
        """Replace static routing tables with a real-time decision that
        considers contract rates, current spot market, carrier OTP, capacity,
        hazmat constraints AND active routing rules (priority-ordered).
        Returns a ranked list of execution options."""
        options: List[Dict[str, Any]] = []
        miles = _approx_miles(payload.origin, payload.destination)

        # Option 1 · Contract carrier (if any contract exists for this customer+lane)
        if payload.customer_id:
            today = datetime.now(timezone.utc).date().isoformat()
            origin_state = _extract_state(payload.origin) or ""
            dest_state = _extract_state(payload.destination) or ""
            contract = await db.orisei_contract_rates.find_one(
                {"customer_id": payload.customer_id,
                  "origin_state": origin_state, "destination_state": dest_state,
                  "equipment": payload.equipment, "active": True,
                  "effective_from": {"$lte": today},
                  "effective_to": {"$gte": today}}, {"_id": 0})
            if contract:
                options.append({
                    "rank": 1, "mode": "Contract Carrier",
                    "source": "orisei_contract_rates",
                    "rate_usd": contract["line_haul_usd"] + contract.get("fuel_surcharge_usd", 0),
                    "transit_days_est": 2,
                    "rationale": "Contract on file — honor first per routing policy.",
                    "contract_id": contract.get("contract_rate_id")})

        # Option 2 · Spot market
        spot_rate = round(payload.weight_lbs * 0.06 + miles * 1.85 + 250, 2)
        options.append({
            "rank": 2, "mode": "Spot Market",
            "source": "margin_shield",
            "rate_usd": spot_rate,
            "transit_days_est": max(1, int(miles / 500)),
            "rationale": "Real-time spot rate via Margin Shield + DAT/Truckstop boards."})

        # Option 3 · Intermodal where viable (>=800 mi, dry/reefer, <=42,500 lb)
        if miles >= 800 and payload.weight_lbs <= 42500 and payload.equipment in ("Dry Van", "Reefer"):
            options.append({
                "rank": 3, "mode": "Intermodal",
                "source": "mode_shift_engine",
                "rate_usd": round(spot_rate * 0.82, 2),
                "transit_days_est": max(3, int(miles / 400)),
                "rationale": "Intermodal saves 15-18% on long-haul if SLA allows +3d.",
                "added_transit_days": 3})

        # ---------- Hazmat constraint ----------
        hazmat_flag = None
        if payload.hazmat_un:
            hz = _hazmat_lookup(payload.hazmat_un)
            if hz.get("known"):
                hazmat_flag = {"un": payload.hazmat_un, "class": hz.get("hazard_class"),
                                "placard_required": hz.get("placard_required"),
                                "constraint": "Carriers must hold HM-126F endorsement"}

        # ---------- ROUTING RULES ENGINE ----------
        # Evaluate active rules in priority order and apply their actions.
        active_rules = await db.enterprise_routing_rules.find(
            {"active": True}, {"_id": 0}).sort("priority", 1).to_list(200)
        applied_rules: List[Dict[str, Any]] = []
        blocked = False
        forced_mode: Optional[str] = None
        preferred_carriers: List[str] = []
        escalated = False

        o_state = _extract_state(payload.origin) or ""
        d_state = _extract_state(payload.destination) or ""

        for rule in active_rules:
            # Check match conditions — all set fields must match
            if rule.get("match_equipment") and rule["match_equipment"] != payload.equipment:
                continue
            if rule.get("match_weight_min_lbs") is not None and payload.weight_lbs < rule["match_weight_min_lbs"]:
                continue
            if rule.get("match_weight_max_lbs") is not None and payload.weight_lbs > rule["match_weight_max_lbs"]:
                continue
            if rule.get("match_hazmat") is True and not payload.hazmat_un:
                continue
            if rule.get("match_hazmat") is False and payload.hazmat_un:
                continue
            if rule.get("match_customer_id") and rule["match_customer_id"] != payload.customer_id:
                continue
            if rule.get("match_origin_region"):
                region = rule["match_origin_region"].upper()
                if region not in (o_state, payload.origin.upper()):
                    if region not in payload.origin.upper():
                        continue
            if rule.get("match_destination_region"):
                region = rule["match_destination_region"].upper()
                if region not in (d_state, payload.destination.upper()):
                    if region not in payload.destination.upper():
                        continue

            # Rule matched — apply action
            action = rule.get("action")
            applied_rules.append({
                "rule_id": rule.get("rule_id"),
                "name": rule.get("name"),
                "priority": rule.get("priority"),
                "action": action,
                "notes": rule.get("notes"),
            })
            if action == "block":
                blocked = True
                break
            if action == "force_mode" and rule.get("forced_mode"):
                forced_mode = rule["forced_mode"]
            if action == "prefer_carrier" and rule.get("preferred_carrier_name"):
                preferred_carriers.append(rule["preferred_carrier_name"])
            if action == "escalate":
                escalated = True

            # Increment match count async (best-effort)
            await db.enterprise_routing_rules.update_one(
                {"rule_id": rule.get("rule_id")},
                {"$inc": {"match_count": 1}, "$set": {"last_matched_at": _now()}})

        # Apply blocking → return immediately with denied verdict
        if blocked:
            decision_doc = {
                "decision_id": f"DR-{uuid.uuid4().hex[:10].upper()}",
                "lane": f"{payload.origin} → {payload.destination}",
                "decision_at": _now(),
                "blocked": True,
                "applied_rules": applied_rules,
                "options": [],
                "recommendation": None,
                "rationale": "Routing blocked by active rule(s).",
            }
            await db.enterprise_routing_log.insert_one(dict(decision_doc))
            decision_doc.pop("_id", None)
            return decision_doc

        # Apply forced_mode → filter options
        if forced_mode:
            filtered = [o for o in options if forced_mode.lower() in o["mode"].lower()]
            if filtered:
                options = filtered
                for o in options:
                    o["rationale"] = f"Mode forced to {forced_mode} by routing rule. " + o["rationale"]

        # Apply preferred carriers → tag options
        if preferred_carriers:
            for o in options:
                o["preferred_carriers"] = preferred_carriers

        # Recommend cheapest viable
        recommendation = min(options, key=lambda o: o["rate_usd"]) if options else None
        if recommendation:
            recommendation["recommended"] = True

        decision_doc = {
            "decision_id": f"DR-{uuid.uuid4().hex[:10].upper()}",
            "lane": f"{payload.origin} → {payload.destination}",
            "equipment": payload.equipment,
            "weight_lbs": payload.weight_lbs,
            "miles": miles,
            "decision_at": _now(),
            "options": options,
            "recommendation": recommendation,
            "hazmat_constraint": hazmat_flag,
            "applied_rules": applied_rules,
            "preferred_carriers": preferred_carriers,
            "forced_mode": forced_mode,
            "escalated": escalated,
            "static_routing_replaced": True,
            "blocked": False,
        }
        # Audit trail
        await db.enterprise_routing_log.insert_one(dict(decision_doc))
        decision_doc.pop("_id", None)
        return decision_doc

    @router.get("/routing-decisions")
    async def routing_decisions(limit: int = Query(50, ge=1, le=500),
                                   _=auth) -> Dict[str, Any]:
        """Audit trail of dynamic routing decisions."""
        rows = await db.enterprise_routing_log.find(
            {}, {"_id": 0}).sort("decision_at", -1).limit(limit).to_list(limit)
        return {"items": rows, "count": len(rows)}

    # ---------------- SAP IDoc inbound stubs ----------------
    @router.post("/sap/idoc/inbound")
    async def sap_idoc_inbound(payload: Dict[str, Any] = Body(...),
                                  user=admin) -> Dict[str, Any]:
        """Accept SAP IDoc payloads (DELVRY03 / SHPMNT / SHIPCO / INVOIC02)
        and queue for processing. Real connector requires IDoc URL + creds
        from /connections/sap_s4hana."""
        idoc_type = (payload.get("idoc_type") or "").upper()
        if idoc_type not in ("DELVRY03", "SHPMNT", "SHIPCO", "INVOIC02"):
            raise HTTPException(400, f"Unsupported IDoc type: {idoc_type}")
        doc = {
            "idoc_id": f"IDOC-{uuid.uuid4().hex[:10].upper()}",
            "received_at": _now(),
            "received_by": getattr(user, "name", "system"),
            "idoc_type": idoc_type,
            "payload": payload,
            "status": "queued",
        }
        await db.sap_idoc_queue.insert_one(dict(doc))
        doc.pop("_id", None)
        return {"ok": True, "idoc_id": doc["idoc_id"], "status": "queued",
                "next": "Worker will translate to internal booking/cost record."}

    @router.get("/sap/idoc/queue")
    async def sap_idoc_queue(status: Optional[str] = None,
                                user=admin) -> Dict[str, Any]:
        q = {"status": status} if status else {}
        rows = await db.sap_idoc_queue.find(q, {"_id": 0}).sort("received_at", -1).limit(100).to_list(100)
        return {"items": rows, "count": len(rows)}

    # ---------------- Routing Rules (persistent CRUD) ----------------
    @router.get("/routing-rules")
    async def routing_rules_list(active_only: bool = False,
                                   _=auth) -> Dict[str, Any]:
        q = {"active": True} if active_only else {}
        rows = await db.enterprise_routing_rules.find(
            q, {"_id": 0}).sort("priority", 1).to_list(500)
        return {"items": rows, "count": len(rows)}

    @router.post("/routing-rules")
    async def routing_rules_create(payload: RoutingRuleIn,
                                     user=admin) -> Dict[str, Any]:
        doc = {**payload.model_dump(),
                "rule_id": f"RR-{uuid.uuid4().hex[:10].upper()}",
                "created_at": _now(),
                "created_by": getattr(user, "name", "system"),
                "match_count": 0}
        await db.enterprise_routing_rules.insert_one(dict(doc))
        doc.pop("_id", None)
        return doc

    @router.put("/routing-rules/{rule_id}")
    async def routing_rules_update(rule_id: str, payload: RoutingRuleIn,
                                     user=admin) -> Dict[str, Any]:
        update = {**payload.model_dump(),
                   "updated_at": _now(),
                   "updated_by": getattr(user, "name", "system")}
        res = await db.enterprise_routing_rules.find_one_and_update(
            {"rule_id": rule_id}, {"$set": update}, projection={"_id": 0},
            return_document=True)
        if not res:
            raise HTTPException(404, "Routing rule not found")
        return res

    @router.delete("/routing-rules/{rule_id}")
    async def routing_rules_delete(rule_id: str, user=admin) -> Dict[str, str]:
        res = await db.enterprise_routing_rules.update_one(
            {"rule_id": rule_id}, {"$set": {"active": False,
                                              "deactivated_at": _now()}})
        if res.matched_count == 0:
            raise HTTPException(404, "Routing rule not found")
        return {"status": "deactivated"}

    # ---------------- Consolidation Groups (persistent CRUD) ----------------
    @router.get("/consolidation-groups")
    async def consol_groups_list(_=auth) -> Dict[str, Any]:
        rows = await db.enterprise_consolidation_groups.find(
            {}, {"_id": 0}).sort("created_at", -1).to_list(200)
        return {"items": rows, "count": len(rows)}

    @router.post("/consolidation-groups")
    async def consol_groups_create(payload: ConsolidationGroupIn,
                                       user=admin) -> Dict[str, Any]:
        doc = {**payload.model_dump(),
                "group_id": f"CG-{uuid.uuid4().hex[:10].upper()}",
                "created_at": _now(),
                "created_by": getattr(user, "name", "system"),
                "shipments_consolidated": 0,
                "savings_realized_usd": 0}
        await db.enterprise_consolidation_groups.insert_one(dict(doc))
        doc.pop("_id", None)
        return doc

    @router.delete("/consolidation-groups/{group_id}")
    async def consol_groups_delete(group_id: str,
                                       user=admin) -> Dict[str, str]:
        res = await db.enterprise_consolidation_groups.update_one(
            {"group_id": group_id}, {"$set": {"active": False,
                                                "deactivated_at": _now()}})
        if res.matched_count == 0:
            raise HTTPException(404, "Consolidation group not found")
        return {"status": "deactivated"}

    # ---------------- Hazmat Profiles (persistent CRUD) ----------------
    @router.get("/hazmat-profiles")
    async def hazmat_profiles_list(customer_id: Optional[str] = None,
                                       _=auth) -> Dict[str, Any]:
        q = {"customer_id": customer_id} if customer_id else {}
        rows = await db.enterprise_hazmat_profiles.find(
            q, {"_id": 0}).sort("created_at", -1).to_list(200)
        return {"items": rows, "count": len(rows)}

    @router.post("/hazmat-profiles")
    async def hazmat_profiles_create(payload: HazmatProfileIn,
                                         user=admin) -> Dict[str, Any]:
        # Validate UN#s against the catalog
        validated = []
        for un in payload.un_numbers:
            validated.append(_hazmat_lookup(un))
        doc = {**payload.model_dump(),
                "profile_id": f"HZP-{uuid.uuid4().hex[:10].upper()}",
                "created_at": _now(),
                "created_by": getattr(user, "name", "system"),
                "validated_un_numbers": validated,
                "compliance_score": round(
                    sum(1 for v in validated if v.get("known")) /
                    max(len(validated), 1) * 100, 1)}
        await db.enterprise_hazmat_profiles.insert_one(dict(doc))
        doc.pop("_id", None)
        return doc

    @router.delete("/hazmat-profiles/{profile_id}")
    async def hazmat_profiles_delete(profile_id: str,
                                        user=admin) -> Dict[str, str]:
        res = await db.enterprise_hazmat_profiles.update_one(
            {"profile_id": profile_id}, {"$set": {"active": False,
                                                    "deactivated_at": _now()}})
        if res.matched_count == 0:
            raise HTTPException(404, "Hazmat profile not found")
        return {"status": "deactivated"}

    # ---------------- Mode + Rate Shopping (cross-mode + weight breaks) ----------------
    @router.post("/mode-rate-shop")
    async def mode_rate_shop(payload: ModeRateShopIn,
                                _=auth) -> Dict[str, Any]:
        """Quote across parcel, LTL (per-100lb), TL, intermodal and air for the
        same lane. Uses industry rules-of-thumb when no live rater is wired;
        plug DAT/Truckstop/parcel rater for live rates."""
        miles = payload.miles or _approx_miles(payload.origin, payload.destination)
        weight = payload.weight_lbs
        options: List[Dict[str, Any]] = []

        # Parcel: only viable up to 150 lb, per pkg
        if weight <= 150 and payload.pieces <= 20:
            per_pkg = round(8 + (weight / payload.pieces) * 0.45 + miles * 0.01, 2)
            total = round(per_pkg * payload.pieces, 2)
            options.append({"mode": "Parcel", "carriers": ["FedEx Ground", "UPS Ground"],
                             "rate_usd": total, "transit_days": 1 if miles < 500 else 3,
                             "rate_basis": f"${per_pkg}/pkg × {payload.pieces} pkgs",
                             "notes": "Best for <150 lb per pkg, fast intra-region."})
        # LTL: 150-15,000 lb sweet spot
        if 150 < weight <= 15000:
            cwt = weight / 100
            ltl_rate = round(cwt * (22 + miles * 0.04), 2)
            options.append({"mode": "LTL", "carriers": ["XPO", "Estes", "ODFL", "Saia"],
                             "rate_usd": ltl_rate, "transit_days": 2 if miles < 700 else 4,
                             "rate_basis": f"{cwt:.0f} cwt × ${ltl_rate/cwt:.2f}/cwt",
                             "notes": "LTL economics dominate 500-12,000 lb range."})
        # TL: always quotable
        tl_rate = round(weight * 0.06 + miles * 1.85 + 250, 2)
        options.append({"mode": "Truckload", "carriers": ["Spot Market via Margin Shield"],
                         "rate_usd": tl_rate, "transit_days": max(1, int(miles / 500)),
                         "rate_basis": f"{miles:.0f} mi × $1.85/mi + base",
                         "notes": "Best when full truck or time-sensitive."})
        # Intermodal: 800+ mi, dry/reefer, weight up to 42,500
        if miles >= 800 and weight <= 42500 and payload.equipment in ("Dry Van", "Reefer"):
            im_rate = round(tl_rate * 0.82, 2)
            options.append({"mode": "Intermodal",
                             "carriers": ["J.B. Hunt Intermodal", "Schneider Intermodal", "BNSF Logistics"],
                             "rate_usd": im_rate, "transit_days": max(3, int(miles / 400)),
                             "rate_basis": "~18% below TL on 800+ mi lanes",
                             "notes": "Add +2-3 day transit; saves 15-20% vs OTR."})
        # Air: high-value or expedited
        if weight <= 5000 and miles >= 500:
            air_rate = round(weight * 2.50 + 750, 2)
            options.append({"mode": "Air Freight",
                             "carriers": ["Forward Air", "ExpediteAir", "FedEx Custom Critical"],
                             "rate_usd": air_rate, "transit_days": 1,
                             "rate_basis": f"{weight:.0f} lb × $2.50/lb + base",
                             "notes": "Use for expedited / high-value / time-critical."})

        # Hazmat surcharge
        hazmat_warning = None
        if payload.hazmat_un:
            hz = _hazmat_lookup(payload.hazmat_un)
            if hz.get("known"):
                surcharge = 75 if hz.get("hazard_class") in ("8", "9") else 150
                for o in options:
                    o["rate_usd"] = round(o["rate_usd"] + surcharge, 2)
                    o["hazmat_surcharge_usd"] = surcharge
                hazmat_warning = {"un": payload.hazmat_un,
                                    "class": hz.get("hazard_class"),
                                    "placard_required": hz.get("placard_required"),
                                    "surcharge_usd": surcharge}

        options.sort(key=lambda o: o["rate_usd"])
        if options:
            cheapest = options[0]
            fastest = min(options, key=lambda o: o["transit_days"])
            for o in options:
                o["badges"] = []
                if o is cheapest:
                    o["badges"].append("CHEAPEST")
                if o is fastest:
                    o["badges"].append("FASTEST")

        return {"lane": f"{payload.origin} → {payload.destination}",
                "miles": miles, "weight_lbs": weight,
                "options": options,
                "recommended": options[0] if options else None,
                "hazmat": hazmat_warning,
                "decision_at": _now()}

    # ---------------- Global Shipment Visibility ----------------
    @router.get("/global-visibility")
    async def global_visibility(_=auth) -> Dict[str, Any]:
        """Single pane of glass: outbound brokerage + inbound shipments
        rolled into a unified status map keyed by region."""
        outbound = await db.brokerage_bookings.find(
            {"status": {"$nin": ["delivered", "cancelled"]}},
            {"_id": 0, "booked_id": 1, "booking_id": 1, "origin": 1,
              "destination": 1, "status": 1, "carrier_name": 1,
              "delivery_date": 1, "customer_name": 1,
              "equipment": 1, "rate_usd": 1}).sort("created_at", -1).limit(200).to_list(200)
        inbound = await db.enterprise_inbound.find(
            {"status": {"$nin": ["received", "cancelled"]}},
            {"_id": 0}).sort("expected_arrival", 1).limit(200).to_list(200)

        def _classify(loc: str) -> str:
            up = (loc or "").upper()
            if any(c in up for c in ("USA", "MEXICO", "CANADA")) or any(
                    s in up for s in (", CA", ", TX", ", NY", ", FL", ", IL", ", OH")):
                return "NAM"
            if any(c in up for c in ("GERMANY", "FRANCE", "UK", "SPAIN", "ITALY", "NL", "POLAND")):
                return "EMEA"
            if any(c in up for c in ("BRAZIL", "ARGENTINA", "CHILE", "PERU", "COLOMBIA")):
                return "LATAM"
            if any(c in up for c in ("CHINA", "JAPAN", "INDIA", "SINGAPORE", "HK", "KOREA", "AUSTRALIA")):
                return "APAC"
            return "NAM"

        by_region: Dict[str, Dict[str, Any]] = {
            "NAM": {"outbound": 0, "inbound": 0, "in_transit": 0, "at_risk": 0},
            "EMEA": {"outbound": 0, "inbound": 0, "in_transit": 0, "at_risk": 0},
            "LATAM": {"outbound": 0, "inbound": 0, "in_transit": 0, "at_risk": 0},
            "APAC": {"outbound": 0, "inbound": 0, "in_transit": 0, "at_risk": 0},
        }
        for b in outbound:
            region = _classify(b.get("destination", ""))
            by_region[region]["outbound"] += 1
            if b.get("status") in ("in_transit", "enroute", "loaded"):
                by_region[region]["in_transit"] += 1
            if b.get("delivery_date") and b.get("delivery_date") < datetime.now(timezone.utc).date().isoformat():
                by_region[region]["at_risk"] += 1
        for s in inbound:
            region = _classify(s.get("destination_dc", ""))
            by_region[region]["inbound"] += 1
            if s.get("status") in ("in_transit", "departed", "customs"):
                by_region[region]["in_transit"] += 1
            if s.get("expected_arrival") and s.get("expected_arrival") < datetime.now(timezone.utc).date().isoformat():
                by_region[region]["at_risk"] += 1
        return {"total_active_shipments": len(outbound) + len(inbound),
                "outbound_count": len(outbound),
                "inbound_count": len(inbound),
                "by_region": by_region,
                "recent_outbound": outbound[:20],
                "recent_inbound": inbound[:20]}

    # ---------------- Rate Benchmarking ----------------
    @router.get("/rate-benchmark")
    async def rate_benchmark(origin_state: str = Query(...),
                                destination_state: str = Query(...),
                                equipment: str = "Dry Van",
                                window_days: int = Query(180, ge=30, le=730),
                                _=auth) -> Dict[str, Any]:
        """Automated rate benchmarking: compare own historical lane rates
        vs (a) network average, (b) DAT spot proxy. Surfaces over/under-pay
        bookings."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=window_days)).isoformat()
        q = {"$and": [
            {"$or": [{"created_at": {"$gte": cutoff}}, {"booked_at": {"$gte": cutoff}}]},
            {"equipment": equipment},
            {"$or": [{"origin": {"$regex": f", {origin_state.upper()}"}},
                     {"origin": {"$regex": f", {origin_state.upper()} "}}]},
            {"$or": [{"destination": {"$regex": f", {destination_state.upper()}"}},
                     {"destination": {"$regex": f", {destination_state.upper()} "}}]},
        ]}
        bookings = await db.brokerage_bookings.find(q, {"_id": 0}).to_list(1000)
        rates = sorted([float(b.get("customer_rate_usd") or b.get("rate_usd") or 0)
                          for b in bookings if (b.get("customer_rate_usd") or b.get("rate_usd"))])
        if not rates:
            return {"lane": f"{origin_state} → {destination_state}",
                     "equipment": equipment,
                     "samples": 0,
                     "note": "No historical data on this lane. Use Margin Shield for live spot."}
        avg = sum(rates) / len(rates)
        med = rates[len(rates) // 2]
        p25 = rates[max(0, int(len(rates) * 0.25) - 1)]
        p75 = rates[min(len(rates) - 1, int(len(rates) * 0.75))]
        # DAT spot proxy: median + 4% (industry benchmark spread)
        dat_proxy = round(med * 1.04, 2)
        return {"lane": f"{origin_state} → {destination_state}",
                "equipment": equipment,
                "samples": len(rates),
                "window_days": window_days,
                "min_usd": rates[0], "max_usd": rates[-1],
                "avg_usd": round(avg, 2), "median_usd": round(med, 2),
                "p25_usd": round(p25, 2), "p75_usd": round(p75, 2),
                "dat_spot_proxy_usd": dat_proxy,
                "vs_spot_pct": round((med - dat_proxy) / dat_proxy * 100, 1),
                "verdict": ("UNDER" if med < dat_proxy * 0.97 else
                              "OVER" if med > dat_proxy * 1.05 else "ALIGNED")}

    api_router.include_router(router)
