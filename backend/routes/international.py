"""routes.international — Ocean + Intermodal Rail module.

Adds an international shipping vertical to the TMS:
  • Reference data for major ocean carriers (SCAC + alliance), Class-I rails,
    intermodal terminals/yards, and container types.
  • Container booking CRUD (booking #, vessel, voyage, POL/POD, container #,
    SCAC, size/type, weight, hazmat, shipper, consignee).
  • Gate event log (ingate / outgate) per container with terminal + timestamp.
  • Rail waybill record (railroad SCAC, waybill #, BOL #, equipment init).
  • Branded PDF generation for the ocean **House BL** and the **SLI**
    (Shipper's Letter of Instruction) via `build_branded_markdown_pdf`.

Endpoints — all mounted under /api/international/*:
  GET   /reference                        · combined ref data for the UI
  GET   /ocean-carriers                   · major ocean SS lines
  GET   /rail-carriers                    · Class-I and major regionals
  GET   /rail-yards?railroad=BNSF&city=…  · intermodal facility lookup
  GET   /container-types                  · 20'DC, 40'HC, RF, OT, FR, etc.

  GET   /container-bookings               · list bookings (filterable)
  POST  /container-bookings               · create
  GET   /container-bookings/{id}          · detail (+ gate events + waybills)
  PUT   /container-bookings/{id}          · partial update
  POST  /container-bookings/{id}/status   · advance lifecycle status
  POST  /container-bookings/{id}/gate     · log ingate / outgate event
  POST  /container-bookings/{id}/waybill  · attach rail waybill
  GET   /container-bookings/{id}/house-bl.pdf
  GET   /container-bookings/{id}/sli.pdf
"""
from __future__ import annotations

import io
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr, Field

logger = logging.getLogger("tennant_tms.international")


# -------------------- REFERENCE DATA --------------------
OCEAN_CARRIERS: List[Dict[str, Any]] = [
    {"scac": "MAEU", "name": "Maersk",              "alliance": "Gemini",        "hq": "Copenhagen, DK",   "website": "https://www.maersk.com"},
    {"scac": "MSCU", "name": "MSC",                 "alliance": "Standalone",    "hq": "Geneva, CH",       "website": "https://www.msc.com"},
    {"scac": "CMDU", "name": "CMA CGM",             "alliance": "Ocean Alliance","hq": "Marseille, FR",    "website": "https://www.cma-cgm.com"},
    {"scac": "HLCU", "name": "Hapag-Lloyd",         "alliance": "Gemini",        "hq": "Hamburg, DE",      "website": "https://www.hapag-lloyd.com"},
    {"scac": "ONEY", "name": "ONE (Ocean Network Express)", "alliance": "Premier Alliance", "hq": "Singapore",   "website": "https://www.one-line.com"},
    {"scac": "EGLV", "name": "Evergreen Marine",    "alliance": "Ocean Alliance","hq": "Taipei, TW",       "website": "https://www.evergreen-marine.com"},
    {"scac": "COSU", "name": "COSCO Shipping Lines","alliance": "Ocean Alliance","hq": "Shanghai, CN",     "website": "https://lines.coscoshipping.com"},
    {"scac": "OOLU", "name": "OOCL",                "alliance": "Ocean Alliance","hq": "Hong Kong",        "website": "https://www.oocl.com"},
    {"scac": "HDMU", "name": "HMM",                 "alliance": "Premier Alliance","hq": "Seoul, KR",      "website": "https://www.hmm21.com"},
    {"scac": "YMLU", "name": "Yang Ming",           "alliance": "Premier Alliance","hq": "Keelung, TW",    "website": "https://www.yangming.com"},
    {"scac": "ZIMU", "name": "ZIM",                 "alliance": "Standalone",    "hq": "Haifa, IL",        "website": "https://www.zim.com"},
    {"scac": "PABV", "name": "Pacific International Lines (PIL)", "alliance": "Standalone", "hq": "Singapore", "website": "https://www.pilship.com"},
    {"scac": "WHLC", "name": "Wan Hai Lines",        "alliance": "Standalone",    "hq": "Taipei, TW",       "website": "https://www.wanhai.com"},
    {"scac": "TSLU", "name": "T.S. Lines",            "alliance": "Standalone",    "hq": "Taipei, TW",       "website": "https://www.tslines.com"},
    {"scac": "MATS", "name": "Matson",                "alliance": "Standalone",    "hq": "Honolulu, HI",     "website": "https://www.matson.com"},
    {"scac": "APLU", "name": "APL (CMA CGM)",         "alliance": "Ocean Alliance","hq": "Marseille, FR",   "website": "https://www.apl.com"},
    {"scac": "SUDU", "name": "Hamburg Süd (Maersk)",  "alliance": "Gemini",        "hq": "Hamburg, DE",     "website": "https://www.hamburgsud-line.com"},
    {"scac": "SAFM", "name": "Safmarine (Maersk)",    "alliance": "Gemini",        "hq": "Copenhagen, DK",  "website": "https://www.safmarine.com"},
    {"scac": "ANNU", "name": "Antillean Marine",      "alliance": "Standalone",    "hq": "Miami, FL",       "website": "https://www.antilleanmarine.com"},
    {"scac": "SEAU", "name": "SeaLand (Maersk)",      "alliance": "Gemini",        "hq": "Miami, FL",       "website": "https://www.sealandmaersk.com"},
]

RAIL_CARRIERS: List[Dict[str, Any]] = [
    # Class I — North America
    {"scac": "BNSF", "name": "BNSF Railway",            "class": "I", "country": "USA",    "website": "https://www.bnsf.com"},
    {"scac": "UP",   "name": "Union Pacific",           "class": "I", "country": "USA",    "website": "https://www.up.com"},
    {"scac": "NS",   "name": "Norfolk Southern",        "class": "I", "country": "USA",    "website": "https://www.norfolksouthern.com"},
    {"scac": "CSXT", "name": "CSX Transportation",      "class": "I", "country": "USA",    "website": "https://www.csx.com"},
    {"scac": "CN",   "name": "Canadian National",       "class": "I", "country": "CA/USA", "website": "https://www.cn.ca"},
    {"scac": "CPKC", "name": "Canadian Pacific Kansas City", "class": "I", "country": "CA/USA/MX", "website": "https://www.cpkcr.com"},
    # Major regionals
    {"scac": "FXE",  "name": "Ferromex",                "class": "II","country": "MX",     "website": "https://www.ferromex.com.mx"},
    {"scac": "KCSM", "name": "Kansas City Southern de Mexico (now CPKC)", "class": "II", "country": "MX", "website": "https://www.cpkcr.com"},
    {"scac": "FEC",  "name": "Florida East Coast Rwy",  "class": "II","country": "USA",    "website": "https://www.fecrwy.com"},
    {"scac": "PAS",  "name": "Pan Am Southern",         "class": "II","country": "USA",    "website": "https://www.panamrailways.com"},
    {"scac": "MNA",  "name": "Missouri & Northern Arkansas","class": "III","country": "USA","website": "https://www.gwrr.com/mna"},
    {"scac": "BRC",  "name": "Belt Railway of Chicago", "class": "III","country": "USA",   "website": "https://www.beltrailway.com"},
]

# Major North American intermodal yards / terminals
RAIL_YARDS: List[Dict[str, Any]] = [
    # BNSF
    {"code": "BNSF-LPC",   "name": "Logistics Park Chicago",              "city": "Elwood, IL",         "state": "IL", "railroad": "BNSF", "type": "Intermodal"},
    {"code": "BNSF-LPKC",  "name": "Logistics Park Kansas City",          "city": "Edgerton, KS",       "state": "KS", "railroad": "BNSF", "type": "Intermodal"},
    {"code": "BNSF-MEM",   "name": "Memphis (Tennessee) Intermodal",       "city": "Memphis, TN",        "state": "TN", "railroad": "BNSF", "type": "Intermodal"},
    {"code": "BNSF-ALP",   "name": "Alliance Intermodal",                  "city": "Fort Worth (Haslet), TX", "state": "TX", "railroad": "BNSF", "type": "Intermodal"},
    {"code": "BNSF-HTH",   "name": "Hobart (Los Angeles) Intermodal",      "city": "Los Angeles, CA",    "state": "CA", "railroad": "BNSF", "type": "Intermodal"},
    {"code": "BNSF-SBD",   "name": "San Bernardino Intermodal",            "city": "San Bernardino, CA", "state": "CA", "railroad": "BNSF", "type": "Intermodal"},
    {"code": "BNSF-COR",   "name": "Corwith (Chicago) Intermodal",         "city": "Chicago, IL",        "state": "IL", "railroad": "BNSF", "type": "Intermodal"},
    {"code": "BNSF-CIC",   "name": "Cicero Intermodal",                    "city": "Cicero, IL",         "state": "IL", "railroad": "BNSF", "type": "Intermodal"},
    {"code": "BNSF-WSP",   "name": "Willow Springs Intermodal",            "city": "Willow Springs, IL", "state": "IL", "railroad": "BNSF", "type": "Intermodal"},
    {"code": "BNSF-RIC",   "name": "Richmond (CA) Intermodal",             "city": "Richmond, CA",       "state": "CA", "railroad": "BNSF", "type": "Intermodal"},
    {"code": "BNSF-STX",   "name": "South Seattle Intermodal",             "city": "Seattle, WA",        "state": "WA", "railroad": "BNSF", "type": "Intermodal"},
    {"code": "BNSF-PRH",   "name": "Portland (Oregon) Intermodal",         "city": "Portland, OR",       "state": "OR", "railroad": "BNSF", "type": "Intermodal"},
    # UP
    {"code": "UP-LATC",    "name": "Los Angeles Transportation Center (ICTF)", "city": "Long Beach, CA", "state": "CA", "railroad": "UP",   "type": "Intermodal"},
    {"code": "UP-G4",      "name": "Global IV (Joliet)",                   "city": "Joliet, IL",         "state": "IL", "railroad": "UP",   "type": "Intermodal"},
    {"code": "UP-G1",      "name": "Global I (Northlake)",                 "city": "Northlake, IL",      "state": "IL", "railroad": "UP",   "type": "Intermodal"},
    {"code": "UP-G2",      "name": "Global II (Schiller Park)",            "city": "Schiller Park, IL",  "state": "IL", "railroad": "UP",   "type": "Intermodal"},
    {"code": "UP-OAK",     "name": "Oakland (OIG) Intermodal",             "city": "Oakland, CA",        "state": "CA", "railroad": "UP",   "type": "Intermodal"},
    {"code": "UP-ENG",     "name": "Englewood Intermodal",                 "city": "Houston, TX",        "state": "TX", "railroad": "UP",   "type": "Intermodal"},
    {"code": "UP-MSQ",     "name": "Mesquite (Dallas) Intermodal",         "city": "Mesquite, TX",       "state": "TX", "railroad": "UP",   "type": "Intermodal"},
    {"code": "UP-MEM",     "name": "Marion (Memphis) Intermodal",          "city": "Marion, AR",         "state": "AR", "railroad": "UP",   "type": "Intermodal"},
    {"code": "UP-LBY",     "name": "LATC Long Beach Pier (ICTF)",          "city": "Long Beach, CA",     "state": "CA", "railroad": "UP",   "type": "Intermodal"},
    {"code": "UP-SDC",     "name": "San Diego ICTF",                       "city": "San Diego, CA",      "state": "CA", "railroad": "UP",   "type": "Intermodal"},
    # NS
    {"code": "NS-INM",     "name": "Inman Yard (Atlanta)",                 "city": "Atlanta, GA",        "state": "GA", "railroad": "NS",   "type": "Intermodal"},
    {"code": "NS-LDX",     "name": "Landers Yard (Chicago)",               "city": "Chicago, IL",        "state": "IL", "railroad": "NS",   "type": "Intermodal"},
    {"code": "NS-CHX",     "name": "Charleston Intermodal",                "city": "Charleston, SC",     "state": "SC", "railroad": "NS",   "type": "Intermodal"},
    {"code": "NS-NRK",     "name": "Norfolk International Terminals",      "city": "Norfolk, VA",        "state": "VA", "railroad": "NS",   "type": "Intermodal"},
    {"code": "NS-CSL",     "name": "Crescent Corridor Memphis",            "city": "Memphis, TN",        "state": "TN", "railroad": "NS",   "type": "Intermodal"},
    {"code": "NS-RIC",     "name": "Croxton (Jersey City)",                "city": "Jersey City, NJ",    "state": "NJ", "railroad": "NS",   "type": "Intermodal"},
    # CSX
    {"code": "CSX-NWR",    "name": "North Baltimore Intermodal",           "city": "North Baltimore, OH","state": "OH", "railroad": "CSXT", "type": "Intermodal"},
    {"code": "CSX-FLO",    "name": "Fairburn (Atlanta) Intermodal",        "city": "Fairburn, GA",       "state": "GA", "railroad": "CSXT", "type": "Intermodal"},
    {"code": "CSX-JAX",    "name": "Jacksonville Intermodal",              "city": "Jacksonville, FL",   "state": "FL", "railroad": "CSXT", "type": "Intermodal"},
    {"code": "CSX-CHQ",    "name": "ExpressRail Elizabeth (Port NY/NJ)",   "city": "Elizabeth, NJ",      "state": "NJ", "railroad": "CSXT", "type": "Intermodal"},
    {"code": "CSX-NYM",    "name": "ExpressRail Newark",                   "city": "Newark, NJ",         "state": "NJ", "railroad": "CSXT", "type": "Intermodal"},
    {"code": "CSX-WVA",    "name": "Worcester Intermodal (MA)",            "city": "Worcester, MA",      "state": "MA", "railroad": "CSXT", "type": "Intermodal"},
    {"code": "CSX-MEM",    "name": "Memphis Intermodal (CSX)",             "city": "Memphis, TN",        "state": "TN", "railroad": "CSXT", "type": "Intermodal"},
    # CN
    {"code": "CN-MTL",     "name": "Taschereau Yard (Montréal)",           "city": "Montréal, QC",       "state": "QC", "railroad": "CN",   "type": "Intermodal"},
    {"code": "CN-TOR",     "name": "Brampton Intermodal (Toronto)",        "city": "Brampton, ON",       "state": "ON", "railroad": "CN",   "type": "Intermodal"},
    {"code": "CN-MEM",     "name": "Memphis CN Intermodal",                "city": "Memphis, TN",        "state": "TN", "railroad": "CN",   "type": "Intermodal"},
    {"code": "CN-CHI",     "name": "Harvey (Chicago) CN Intermodal",       "city": "Harvey, IL",         "state": "IL", "railroad": "CN",   "type": "Intermodal"},
    {"code": "CN-NOL",     "name": "Mays (New Orleans) Intermodal",        "city": "New Orleans, LA",    "state": "LA", "railroad": "CN",   "type": "Intermodal"},
    # CPKC
    {"code": "CPKC-VAN",   "name": "Vancouver Intermodal",                 "city": "Coquitlam, BC",      "state": "BC", "railroad": "CPKC", "type": "Intermodal"},
    {"code": "CPKC-MTL",   "name": "St-Luc (Montréal)",                    "city": "Montréal, QC",       "state": "QC", "railroad": "CPKC", "type": "Intermodal"},
    {"code": "CPKC-CHI",   "name": "Bensenville (Chicago)",                "city": "Bensenville, IL",    "state": "IL", "railroad": "CPKC", "type": "Intermodal"},
    {"code": "CPKC-KCK",   "name": "Kansas City Intermodal",               "city": "Kansas City, KS",    "state": "KS", "railroad": "CPKC", "type": "Intermodal"},
    {"code": "CPKC-LRD",   "name": "Laredo Intermodal (USMCA gateway)",    "city": "Laredo, TX",         "state": "TX", "railroad": "CPKC", "type": "Intermodal"},
    {"code": "CPKC-MTY",   "name": "Monterrey Intermodal",                 "city": "Monterrey, MX",      "state": "NL", "railroad": "CPKC", "type": "Intermodal"},
]

CONTAINER_TYPES: List[Dict[str, Any]] = [
    {"code": "20DC", "name": "20' Standard Dry",        "iso": "22G1", "tare_kg": 2300,  "max_payload_kg": 28180, "cube_cbm": 33.2},
    {"code": "40DC", "name": "40' Standard Dry",        "iso": "42G1", "tare_kg": 3750,  "max_payload_kg": 26730, "cube_cbm": 67.7},
    {"code": "40HC", "name": "40' High Cube Dry",       "iso": "45G1", "tare_kg": 3900,  "max_payload_kg": 26580, "cube_cbm": 76.4},
    {"code": "45HC", "name": "45' High Cube Dry",       "iso": "L5G1", "tare_kg": 4800,  "max_payload_kg": 27700, "cube_cbm": 86.0},
    {"code": "20RF", "name": "20' Reefer (refrigerated)","iso": "22R1","tare_kg": 3050,  "max_payload_kg": 27430, "cube_cbm": 28.3},
    {"code": "40RF", "name": "40' Reefer (refrigerated)","iso": "42R1","tare_kg": 4800,  "max_payload_kg": 25680, "cube_cbm": 58.0},
    {"code": "40HR", "name": "40' High-Cube Reefer",     "iso": "45R1","tare_kg": 4900,  "max_payload_kg": 25580, "cube_cbm": 66.0},
    {"code": "20OT", "name": "20' Open Top",             "iso": "22U1","tare_kg": 2400,  "max_payload_kg": 28080, "cube_cbm": 32.0},
    {"code": "40OT", "name": "40' Open Top",             "iso": "42U1","tare_kg": 3900,  "max_payload_kg": 26580, "cube_cbm": 65.5},
    {"code": "20FR", "name": "20' Flat Rack",            "iso": "22P1","tare_kg": 2750,  "max_payload_kg": 27730, "cube_cbm": None},
    {"code": "40FR", "name": "40' Flat Rack",            "iso": "42P1","tare_kg": 5350,  "max_payload_kg": 40850, "cube_cbm": None},
    {"code": "20TK", "name": "20' ISO Tank",             "iso": "22T1","tare_kg": 3650,  "max_payload_kg": 26350, "cube_cbm": 26.0},
]

# Full ocean lifecycle — Booked → Gate-In Origin → On Vessel → Discharged POD
# → At Rail Ramp → Outgated → Delivered. Each step is acknowledged by a gate
# event or a manual status advance.
CONTAINER_STATUSES = [
    "BOOKED",          # carrier booking confirmed, container not yet picked up
    "GATE_IN_ORIGIN",  # container ingated at POL terminal (CY/CFS)
    "ON_VESSEL",       # loaded onboard, sailing
    "DISCHARGED",      # discharged at POD container yard
    "AT_RAIL_RAMP",    # railed to inland ramp (intermodal)
    "OUTGATED",        # picked up from terminal/ramp by trucker
    "DELIVERED",       # delivered to consignee
    "EMPTY_RETURNED",  # empty container returned per Detention/Demurrage tariff
]


# -------------------- PYDANTIC --------------------
class ContainerBookingIn(BaseModel):
    carrier_scac: str = Field(..., min_length=2, max_length=8)
    booking_number: str = Field(..., max_length=40)
    vessel_name: Optional[str] = Field(None, max_length=80)
    voyage_number: Optional[str] = Field(None, max_length=40)
    etd: Optional[str] = None  # ISO date
    eta: Optional[str] = None  # ISO date
    pol: str = Field(..., description="Port of Loading (e.g. CNSHA)", max_length=80)
    pod: str = Field(..., description="Port of Discharge (e.g. USLAX)", max_length=80)
    final_destination: Optional[str] = Field(None, max_length=120)
    container_size_type: str = Field("40HC", description="20DC, 40HC, 20RF, etc.")
    container_count: int = Field(1, ge=1, le=200)
    container_numbers: Optional[List[str]] = None
    commodity: str = Field(..., max_length=200)
    hs_code: Optional[str] = Field(None, max_length=20)
    weight_kg: Optional[float] = Field(None, ge=0)
    cargo_value_usd: Optional[float] = Field(None, ge=0)
    hazmat: bool = False
    imdg_class: Optional[str] = Field(None, max_length=10)
    un_number: Optional[str] = Field(None, max_length=10)
    shipper_name: str = Field(..., max_length=200)
    shipper_address: Optional[str] = Field(None, max_length=400)
    shipper_contact_email: Optional[EmailStr] = None
    consignee_name: str = Field(..., max_length=200)
    consignee_address: Optional[str] = Field(None, max_length=400)
    consignee_contact_email: Optional[EmailStr] = None
    notify_party_name: Optional[str] = Field(None, max_length=200)
    incoterms: str = Field("FOB", max_length=10)
    freight_terms: str = Field("Prepaid", description="Prepaid / Collect")
    rate_usd: Optional[float] = Field(None, ge=0)
    notes: Optional[str] = Field(None, max_length=2000)


class GateEventIn(BaseModel):
    event_type: str = Field(..., description="ingate | outgate")
    terminal_code: str = Field(..., max_length=40)
    container_number: Optional[str] = Field(None, max_length=20)
    chassis_number: Optional[str] = Field(None, max_length=20)
    trucker_scac: Optional[str] = Field(None, max_length=8)
    occurred_at: Optional[str] = None  # ISO; defaults to now
    notes: Optional[str] = Field(None, max_length=500)


class RailWaybillIn(BaseModel):
    railroad_scac: str = Field(..., max_length=8)
    waybill_number: str = Field(..., max_length=40)
    equipment_initial: Optional[str] = Field(None, max_length=8)
    equipment_number: Optional[str] = Field(None, max_length=20)
    origin_yard_code: Optional[str] = Field(None, max_length=20)
    destination_yard_code: Optional[str] = Field(None, max_length=20)
    waybill_date: Optional[str] = None
    rate_usd: Optional[float] = Field(None, ge=0)
    notes: Optional[str] = Field(None, max_length=500)


class StatusAdvanceIn(BaseModel):
    new_status: str
    note: Optional[str] = None


# -------------------- HELPERS --------------------
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _container_booking_md(b: Dict[str, Any], brand: Dict[str, Any]) -> str:
    """Build the markdown for a House BL — consumed by build_branded_markdown_pdf."""
    haz_block = ""
    if b.get("hazmat"):
        haz_block = (f"\n## Dangerous Goods\n"
                     f"- **IMDG Class**: {b.get('imdg_class') or '—'}\n"
                     f"- **UN Number**: {b.get('un_number') or '—'}\n"
                     f"- **Proper Shipping Name**: {b.get('commodity')}\n")
    containers = ", ".join(b.get("container_numbers") or []) or "TBA"
    return f"""# House Bill of Lading · {b['booking_id']}

**Issued**: {b['created_at'][:10]}  ·  **Carrier**: {b['carrier_name']} ({b['carrier_scac']})

## Shipper
- **Name**: {b['shipper_name']}
- **Address**: {b.get('shipper_address') or '—'}
- **Contact**: {b.get('shipper_contact_email') or '—'}

## Consignee
- **Name**: {b['consignee_name']}
- **Address**: {b.get('consignee_address') or '—'}
- **Contact**: {b.get('consignee_contact_email') or '—'}

## Notify Party
- **Name**: {b.get('notify_party_name') or 'Same as consignee'}

## Vessel / Voyage
- **Vessel**: {b.get('vessel_name') or 'TBA'}
- **Voyage**: {b.get('voyage_number') or 'TBA'}
- **POL (Port of Loading)**: {b['pol']}
- **POD (Port of Discharge)**: {b['pod']}
- **Final destination**: {b.get('final_destination') or b['pod']}
- **ETD**: {b.get('etd') or 'TBA'}
- **ETA**: {b.get('eta') or 'TBA'}

## Cargo
- **Container size/type**: {b['container_size_type']}
- **Container count**: {b['container_count']}
- **Container numbers**: {containers}
- **Commodity**: {b['commodity']}
- **HS code**: {b.get('hs_code') or '—'}
- **Weight (kg)**: {b.get('weight_kg') or '—'}
- **Declared value (USD)**: {f"${b['cargo_value_usd']:,.2f}" if b.get('cargo_value_usd') else '—'}
{haz_block}
## Commercial Terms
- **Incoterms**: {b['incoterms']}
- **Freight terms**: {b['freight_terms']}
- **Rate (USD)**: {f"${b['rate_usd']:,.2f}" if b.get('rate_usd') else '—'}

---

> Received by the carrier from the shipper in apparent good order and
> condition (unless otherwise indicated herein), the goods or container(s)
> said to contain the cargo herein mentioned, to be transported subject to
> all the terms and conditions appearing on the front and reverse of this
> bill of lading to which the merchant agrees by accepting this bill of
> lading. Any local privileges and customs notwithstanding.

## Authorized Signature
- **For carrier**: ______________________________
- **Date**: {b['created_at'][:10]}
"""


def _sli_md(b: Dict[str, Any], brand: Dict[str, Any]) -> str:
    """Shipper's Letter of Instruction — what the shipper signs / returns to
    authorize the booking and the freight forwarder."""
    return f"""# Shipper's Letter of Instruction · {b['booking_id']}

**Carrier**: {b['carrier_name']} ({b['carrier_scac']})
**Booking #**: {b['booking_number']}
**Issued**: {b['created_at'][:10]}

## Shipper
- **Name**: {b['shipper_name']}
- **Address**: {b.get('shipper_address') or '—'}
- **Email**: {b.get('shipper_contact_email') or '—'}
- **Tax ID / EIN**: ______________________

## Consignee
- **Name**: {b['consignee_name']}
- **Address**: {b.get('consignee_address') or '—'}
- **Email**: {b.get('consignee_contact_email') or '—'}

## Routing
- **POL**: {b['pol']}
- **POD**: {b['pod']}
- **Final destination**: {b.get('final_destination') or b['pod']}
- **Vessel / voyage**: {b.get('vessel_name') or 'TBA'} / {b.get('voyage_number') or 'TBA'}
- **ETD**: {b.get('etd') or 'TBA'}
- **ETA**: {b.get('eta') or 'TBA'}

## Cargo
- **Container(s)**: {b['container_count']} × {b['container_size_type']}
- **Commodity**: {b['commodity']}
- **HS code**: {b.get('hs_code') or '—'}
- **Weight (kg)**: {b.get('weight_kg') or '—'}
- **Cargo value (USD)**: {f"${b['cargo_value_usd']:,.2f}" if b.get('cargo_value_usd') else '—'}
- **Hazmat**: {'Yes' if b.get('hazmat') else 'No'}{f" · IMDG {b.get('imdg_class')} · UN {b.get('un_number')}" if b.get('hazmat') else ''}

## Commercial Terms
- **Incoterms**: {b['incoterms']}
- **Freight terms**: {b['freight_terms']}

## Documents Required
- Commercial invoice
- Packing list
- Certificate of origin (if FTA)
- ISF-10 filing (US imports only — Importer Security Filing)
- Hazmat declaration / DG note (if applicable)
- Phyto / Health certs (if applicable)

## Shipper Authorization
By signing below, the shipper authorizes the brokerage and the named ocean
carrier to ship the above cargo under the terms shown and certifies the
information provided is true and complete.

- **Signed**: ______________________________
- **Print name**: ______________________________
- **Title**: ______________________________
- **Date**: ______________________________
"""


# -------------------- ROUTER --------------------
def build_international_router(
    api_router: APIRouter, *, db,
    get_current_user: Callable, require_role: Callable,
) -> None:
    """Mount the international shipping module under /api/international/*."""
    router = APIRouter(prefix="/international", tags=["international"])
    admin_dep = Depends(require_role("admin", "dispatcher"))

    async def _active_brand() -> Dict[str, Any]:
        return await db.company_brand.find_one({"is_active": True}, {"_id": 0}) or {}

    # ============================ REFERENCE ============================
    @router.get("/reference")
    async def reference(_=Depends(get_current_user)) -> Dict[str, Any]:
        return {
            "ocean_carriers": OCEAN_CARRIERS,
            "rail_carriers": RAIL_CARRIERS,
            "rail_yards": RAIL_YARDS,
            "container_types": CONTAINER_TYPES,
            "container_statuses": CONTAINER_STATUSES,
        }

    @router.get("/ocean-carriers")
    async def ocean_carriers(_=Depends(get_current_user)) -> Dict[str, Any]:
        return {"items": OCEAN_CARRIERS, "count": len(OCEAN_CARRIERS)}

    @router.get("/rail-carriers")
    async def rail_carriers(_=Depends(get_current_user)) -> Dict[str, Any]:
        return {"items": RAIL_CARRIERS, "count": len(RAIL_CARRIERS)}

    @router.get("/rail-yards")
    async def rail_yards(railroad: Optional[str] = None,
                          city: Optional[str] = None,
                          _=Depends(get_current_user)) -> Dict[str, Any]:
        rows = RAIL_YARDS
        if railroad:
            rows = [r for r in rows if r["railroad"].lower() == railroad.lower()]
        if city:
            cl = city.lower()
            rows = [r for r in rows if cl in r["city"].lower()]
        return {"items": rows, "count": len(rows)}

    @router.get("/container-types")
    async def container_types(_=Depends(get_current_user)) -> Dict[str, Any]:
        return {"items": CONTAINER_TYPES, "count": len(CONTAINER_TYPES)}

    # ============================ BOOKINGS ============================
    @router.get("/container-bookings")
    async def list_bookings(status: Optional[str] = None,
                              carrier_scac: Optional[str] = None,
                              limit: int = Query(default=100, ge=1, le=500),
                              _=Depends(get_current_user)) -> Dict[str, Any]:
        q: Dict[str, Any] = {}
        if status:
            q["status"] = status
        if carrier_scac:
            q["carrier_scac"] = carrier_scac.upper()
        rows = await db.intl_container_bookings.find(
            q, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
        return {"items": rows, "count": len(rows)}

    @router.post("/container-bookings")
    async def create_booking(payload: ContainerBookingIn,
                              user=admin_dep) -> Dict[str, Any]:
        carrier = next((c for c in OCEAN_CARRIERS
                        if c["scac"].lower() == payload.carrier_scac.lower()), None)
        if not carrier:
            raise HTTPException(404, f"Unknown ocean carrier SCAC '{payload.carrier_scac}'. "
                                       f"See GET /international/ocean-carriers")
        doc = {
            "booking_id": f"INTL-{uuid.uuid4().hex[:10].upper()}",
            "carrier_scac": carrier["scac"],
            "carrier_name": carrier["name"],
            "alliance": carrier.get("alliance"),
            "status": "BOOKED",
            "created_at": _now_iso(),
            "created_by": getattr(user, "name", "system"),
            "gate_events": [],
            "rail_waybills": [],
            "status_history": [{"status": "BOOKED", "at": _now_iso(),
                                  "by": getattr(user, "name", "system")}],
            **payload.model_dump(),
        }
        await db.intl_container_bookings.insert_one(dict(doc))
        doc.pop("_id", None)
        return doc

    @router.get("/container-bookings/{booking_id}")
    async def get_booking(booking_id: str,
                            _=Depends(get_current_user)) -> Dict[str, Any]:
        doc = await db.intl_container_bookings.find_one(
            {"booking_id": booking_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Container booking not found")
        return doc

    @router.put("/container-bookings/{booking_id}")
    async def update_booking(booking_id: str,
                              body: Dict[str, Any],
                              user=admin_dep) -> Dict[str, Any]:
        allowed = {"vessel_name", "voyage_number", "etd", "eta", "pol", "pod",
                    "final_destination", "container_numbers", "weight_kg",
                    "cargo_value_usd", "rate_usd", "freight_terms", "incoterms",
                    "notes", "notify_party_name", "shipper_contact_email",
                    "consignee_contact_email"}
        upd = {k: v for k, v in body.items() if k in allowed}
        if not upd:
            raise HTTPException(400, "No editable fields supplied")
        upd["updated_at"] = _now_iso()
        upd["updated_by"] = getattr(user, "name", "system")
        res = await db.intl_container_bookings.update_one(
            {"booking_id": booking_id}, {"$set": upd})
        if res.matched_count == 0:
            raise HTTPException(404, "Container booking not found")
        return await db.intl_container_bookings.find_one(
            {"booking_id": booking_id}, {"_id": 0}) or {}

    @router.post("/container-bookings/{booking_id}/status")
    async def advance_status(booking_id: str, payload: StatusAdvanceIn,
                              user=admin_dep) -> Dict[str, Any]:
        if payload.new_status not in CONTAINER_STATUSES:
            raise HTTPException(400, f"Unknown status. Valid: {CONTAINER_STATUSES}")
        entry = {"status": payload.new_status, "at": _now_iso(),
                  "by": getattr(user, "name", "system"),
                  "note": payload.note}
        res = await db.intl_container_bookings.find_one_and_update(
            {"booking_id": booking_id},
            {"$set": {"status": payload.new_status},
              "$push": {"status_history": entry}},
            projection={"_id": 0},
            return_document=True,
        )
        if not res:
            raise HTTPException(404, "Container booking not found")
        return res

    @router.post("/container-bookings/{booking_id}/gate")
    async def log_gate_event(booking_id: str, payload: GateEventIn,
                              user=admin_dep) -> Dict[str, Any]:
        if payload.event_type not in ("ingate", "outgate"):
            raise HTTPException(400, "event_type must be 'ingate' or 'outgate'")
        event = {
            "event_id": f"GATE-{uuid.uuid4().hex[:10].upper()}",
            "at": payload.occurred_at or _now_iso(),
            "by": getattr(user, "name", "system"),
            **payload.model_dump(),
        }
        # Auto-advance status when the gate event maps cleanly
        new_status = None
        if payload.event_type == "ingate":
            new_status = "GATE_IN_ORIGIN"
        elif payload.event_type == "outgate":
            new_status = "OUTGATED"
        update: Dict[str, Any] = {"$push": {"gate_events": event}}
        if new_status:
            update["$set"] = {"status": new_status}
            update.setdefault("$push", {})
            update["$push"]["status_history"] = {
                "status": new_status, "at": event["at"],
                "by": event["by"],
                "note": f"Auto-advanced from {payload.event_type} at {payload.terminal_code}",
            }
        res = await db.intl_container_bookings.find_one_and_update(
            {"booking_id": booking_id}, update,
            projection={"_id": 0}, return_document=True,
        )
        if not res:
            raise HTTPException(404, "Container booking not found")
        return res

    @router.post("/container-bookings/{booking_id}/waybill")
    async def attach_waybill(booking_id: str, payload: RailWaybillIn,
                              user=admin_dep) -> Dict[str, Any]:
        rail = next((r for r in RAIL_CARRIERS
                     if r["scac"].lower() == payload.railroad_scac.lower()), None)
        if not rail:
            raise HTTPException(404, f"Unknown railroad SCAC '{payload.railroad_scac}'")
        wb = {
            "waybill_id": f"WB-{uuid.uuid4().hex[:10].upper()}",
            "railroad_name": rail["name"],
            "logged_at": _now_iso(),
            "logged_by": getattr(user, "name", "system"),
            **payload.model_dump(),
        }
        res = await db.intl_container_bookings.find_one_and_update(
            {"booking_id": booking_id},
            {"$push": {"rail_waybills": wb}},
            projection={"_id": 0}, return_document=True,
        )
        if not res:
            raise HTTPException(404, "Container booking not found")
        return res

    # ============================ PDFs ============================
    @router.get("/container-bookings/{booking_id}/house-bl.pdf")
    async def house_bl_pdf(booking_id: str,
                            _=Depends(get_current_user)) -> StreamingResponse:
        booking = await db.intl_container_bookings.find_one(
            {"booking_id": booking_id}, {"_id": 0})
        if not booking:
            raise HTTPException(404, "Container booking not found")
        brand = await _active_brand()
        from routes.orisei_docs import build_branded_markdown_pdf
        pdf = build_branded_markdown_pdf(
            _container_booking_md(booking, brand),
            title=f"House Bill of Lading · {booking_id}",
            subtitle=f"Ocean shipment · {booking['pol']} → {booking['pod']}",
            doc_id=booking_id, brand=brand,
        )
        # Archive into Document Vault (fire-and-forget)
        try:
            from routes.doc_vault import archive_pdf
            await archive_pdf(
                db, pdf,
                doc_type="HOUSE_BL", doc_id=booking_id,
                ref_id=booking.get("booking_number"),
                source_endpoint=f"/api/international/container-bookings/{booking_id}/house-bl.pdf",
                payload_snapshot={"booking": booking}, user=_,
                filename=f"HouseBL_{booking_id}.pdf",
            )
        except Exception:                                       # noqa: BLE001
            pass
        return StreamingResponse(io.BytesIO(pdf), media_type="application/pdf",
            headers={"Content-Disposition":
                f'attachment; filename="HouseBL_{booking_id}.pdf"'})

    @router.get("/container-bookings/{booking_id}/sli.pdf")
    async def sli_pdf(booking_id: str,
                       _=Depends(get_current_user)) -> StreamingResponse:
        booking = await db.intl_container_bookings.find_one(
            {"booking_id": booking_id}, {"_id": 0})
        if not booking:
            raise HTTPException(404, "Container booking not found")
        brand = await _active_brand()
        from routes.orisei_docs import build_branded_markdown_pdf
        pdf = build_branded_markdown_pdf(
            _sli_md(booking, brand),
            title=f"Shipper's Letter of Instruction · {booking_id}",
            subtitle=f"For {booking['carrier_name']} booking {booking['booking_number']}",
            doc_id=booking_id, brand=brand,
        )
        try:
            from routes.doc_vault import archive_pdf
            await archive_pdf(
                db, pdf,
                doc_type="SLI", doc_id=booking_id,
                ref_id=booking.get("booking_number"),
                source_endpoint=f"/api/international/container-bookings/{booking_id}/sli.pdf",
                payload_snapshot={"booking": booking}, user=_,
                filename=f"SLI_{booking_id}.pdf",
            )
        except Exception:                                       # noqa: BLE001
            pass
        return StreamingResponse(io.BytesIO(pdf), media_type="application/pdf",
            headers={"Content-Disposition":
                f'attachment; filename="SLI_{booking_id}.pdf"'})

    api_router.include_router(router)
