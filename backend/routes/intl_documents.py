"""routes.intl_documents — Export/Import documentation suite.

Adds to the International module a full per-container document tracker plus
branded PDF generators for every document a containerized shipment needs:

  EXPORT:
    • AES Filing Worksheet         · AESDirect EEI prep (auto-populated)
    • Commercial Invoice           · with full HTS/Schedule B detail
    • Packing List                 · piece × commodity × marks/numbers
    • Certificate of Origin        · USMCA / generic
    • Phytosanitary Application    · USDA-APHIS PPQ Form 572 prep
    • Letter of Credit (draft)     · banker-ready LC presentation copy
    • Shipper's Export Declaration · legacy SED equivalent

  IMPORT:
    • ISF-10 Prep (Importer Security Filing)
    • CBP Entry Summary (7501) Prep
    • Customs Broker Cover Letter

  DOC TRACKER (internal + external):
    • Record any doc per container booking (DRAFT / READY / FILED / RECEIVED)
    • Upload external PDFs (carrier-issued BL, supplier invoice, phyto cert
      received from USDA, signed LC from issuing bank, etc.)
    • Each record stores type, status, source (INTERNAL_GEN / EXTERNAL),
      reference number (ITN, phyto cert #, LC #), filed_at, file_id (GridFS).
    • Optional ITN capture endpoint to attach the AES ITN once the broker
      has filed via AESDirect manually.

Endpoints — mounted under /api/international/* (extends the existing
international router):

  GET    /container-bookings/{id}/docs                   · list docs
  POST   /container-bookings/{id}/docs                   · record a doc
  POST   /container-bookings/{id}/docs/upload            · upload external file
  DELETE /container-bookings/{id}/docs/{doc_id}
  PUT    /container-bookings/{id}/docs/{doc_id}/status   · update status

  POST   /container-bookings/{id}/aes/filing             · record ITN

  GET    /container-bookings/{id}/pdf/aes-worksheet
  GET    /container-bookings/{id}/pdf/commercial-invoice
  GET    /container-bookings/{id}/pdf/packing-list
  GET    /container-bookings/{id}/pdf/certificate-of-origin
  GET    /container-bookings/{id}/pdf/phyto-application
  GET    /container-bookings/{id}/pdf/letter-of-credit
  GET    /container-bookings/{id}/pdf/isf-10
  GET    /container-bookings/{id}/pdf/cbp-7501-prep

  GET    /aes/help                                       · field cheat sheet
  GET    /phyto/help                                     · USDA phyto guide
"""
from __future__ import annotations

import io
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from fastapi import (APIRouter, Depends, File, Form, HTTPException, UploadFile)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

logger = logging.getLogger("orisei.intl_documents")


# -------------------- REFERENCE --------------------
INTL_DOC_TYPES = [
    {"code": "AES_WORKSHEET",        "name": "AES Filing Worksheet (EEI)",        "category": "Export · AES"},
    {"code": "ITN_RECEIPT",          "name": "AES ITN Receipt",                    "category": "Export · AES"},
    {"code": "COMMERCIAL_INVOICE",   "name": "Commercial Invoice",                "category": "Export · Commercial"},
    {"code": "PACKING_LIST",         "name": "Packing List",                       "category": "Export · Commercial"},
    {"code": "CERTIFICATE_OF_ORIGIN","name": "Certificate of Origin (Generic/USMCA)","category": "Export · Origin"},
    {"code": "PHYTOSANITARY_PREP",   "name": "Phytosanitary Application (USDA Form 572 prep)", "category": "Export · Phyto"},
    {"code": "PHYTOSANITARY_CERT",   "name": "Phytosanitary Certificate (issued by USDA)",     "category": "Export · Phyto"},
    {"code": "LETTER_OF_CREDIT",     "name": "Letter of Credit (presentation)",   "category": "Export · Banking"},
    {"code": "SED",                  "name": "Shipper's Export Declaration",      "category": "Export · Legacy"},
    {"code": "ISF_10",               "name": "ISF-10 Filing (Importer Security)", "category": "Import · CBP"},
    {"code": "CBP_7501_PREP",        "name": "CBP Entry Summary 7501 Prep",       "category": "Import · CBP"},
    {"code": "BROKER_COVER_LETTER",  "name": "Customs Broker Cover Letter",       "category": "Import · Broker"},
    {"code": "BOL_OCEAN",            "name": "Bill of Lading (Ocean — Master/House)", "category": "Transport"},
    {"code": "DOCK_RECEIPT",         "name": "Dock Receipt",                        "category": "Transport"},
    {"code": "DELIVERY_ORDER",       "name": "Delivery Order",                     "category": "Transport"},
    {"code": "OTHER",                "name": "Other / external attachment",         "category": "Misc"},
]

DOC_STATUSES = ["DRAFT", "READY", "FILED", "RECEIVED", "EXPIRED", "VOID"]
DOC_SOURCES = ["INTERNAL_GEN", "EXTERNAL_UPLOAD", "PARTNER_PORTAL"]

# AES filing field requirements — used by the cheat sheet endpoint + the
# AES worksheet PDF. These are the fields AESDirect prompts for an EEI.
AES_REQUIRED_FIELDS = [
    {"key": "usppi",                       "label": "USPPI (U.S. Principal Party in Interest)",
        "help": "Person/entity in the US receiving the primary benefit of the export sale. Usually the shipper. Required: name, address, EIN/DUNS/SSN."},
    {"key": "ultimate_consignee",          "label": "Ultimate Consignee",
        "help": "Foreign party with the primary economic interest in receiving the goods. Required: name, address, country, role (direct consumer / reseller / govt entity / other)."},
    {"key": "intermediate_consignee",      "label": "Intermediate Consignee (if any)",
        "help": "Agent or party in the country of destination who acts on behalf of the ultimate consignee."},
    {"key": "forwarder",                   "label": "Authorized Forwarding Agent",
        "help": "Freight forwarder / NVOCC filing on behalf of the USPPI. Required: name, address, IRS ID."},
    {"key": "schedule_b_or_hts",           "label": "Schedule B / HTS code (10-digit)",
        "help": "10-digit Schedule B (export) or HTS (often used interchangeably). Census publishes Schedule B online."},
    {"key": "commodity_description",       "label": "Commodity description (plain English)",
        "help": "Short commercial description. AES uses to validate against Schedule B."},
    {"key": "quantity",                    "label": "Quantity (with unit of measure)",
        "help": "Must match the unit on the Schedule B (e.g. NO/EA, KG, M, L2). 1st & 2nd quantity required for some HTS codes."},
    {"key": "value_usd",                   "label": "Value (USD, FOB)",
        "help": "Selling price at the US port of export, exclusive of overseas freight/insurance. Round to whole dollars."},
    {"key": "shipping_weight_kg",          "label": "Shipping weight (kg)",
        "help": "Gross weight at time of export including packaging. Express in kilograms."},
    {"key": "country_of_origin",           "label": "Country of Origin",
        "help": "Country where the goods were grown/produced/manufactured. ISO-3166 alpha-2 code (US, CN, MX, etc.)."},
    {"key": "country_of_ultimate_destination","label": "Country of Ultimate Destination",
        "help": "Country where goods will be consumed/used/processed."},
    {"key": "port_of_export",              "label": "U.S. Port of Export",
        "help": "CBP port code (e.g. 2704 = Houston Seaport, 2704 = LA-Long Beach, 4601 = NYC JFK). See https://www.cbp.gov/document/forms/cbp-port-codes"},
    {"key": "mode_of_transport",           "label": "Mode of Transport",
        "help": "10 = Vessel (containerized), 11 = Vessel (non-containerized), 12 = Vessel (other), 20 = Rail, 30 = Truck, 40 = Air, 50 = Mail, 60 = Passenger/hand, 70 = Fixed transport (pipeline)."},
    {"key": "container_indicator",         "label": "Container Indicator",
        "help": "Y/N — Y if shipped in a closed container loaded at the shipper's site."},
    {"key": "carrier_scac",                "label": "Carrier SCAC",
        "help": "Ocean SCAC (4-letter Standard Carrier Alpha Code) — e.g. MAEU, MSCU."},
    {"key": "vessel_voyage",               "label": "Vessel name and Voyage #",
        "help": "Required for ocean shipments. Carrier provides on booking."},
    {"key": "export_date",                 "label": "Date of Export",
        "help": "Date the goods are scheduled to leave the US. Use ISO date."},
    {"key": "hazmat_indicator",            "label": "Hazardous materials indicator",
        "help": "Y/N. If Y, also provide IMDG class + UN number on the BL."},
    {"key": "ein",                         "label": "USPPI EIN / DUNS / SSN",
        "help": "USPPI's tax ID. EIN (preferred), DUNS (Dun & Bradstreet), or SSN (for non-business exporters only)."},
    {"key": "license_code",                "label": "Export License Code (if applicable)",
        "help": "C33 = NLR (No License Required) is most common. Otherwise BIS ECCN-specific code + license number."},
]

PHYTOSANITARY_REQUIRED_FIELDS = [
    {"key": "exporter_name",       "label": "Exporter name & address"},
    {"key": "exporter_phone",      "label": "Exporter phone number"},
    {"key": "importer_name",       "label": "Consignee/importer name & address"},
    {"key": "importer_country",    "label": "Country of import"},
    {"key": "place_of_origin",     "label": "Place of origin of the article(s)"},
    {"key": "means_of_conveyance", "label": "Declared means of conveyance (vessel + voyage, air carrier + flight, truck)"},
    {"key": "point_of_entry",      "label": "Declared point of entry (foreign port)"},
    {"key": "marks_numbers",       "label": "Distinguishing marks / numbers / quantity / nature of packages"},
    {"key": "botanical_name",      "label": "Botanical name of plants (scientific name)"},
    {"key": "quantity_declared",   "label": "Quantity declared (units of measure)"},
    {"key": "treatment",           "label": "Treatment (fumigation, heat, cold, etc.) — Form 572 Block 18"},
    {"key": "additional_declaration","label":"Additional declarations required by importing country"},
]


# -------------------- MODELS --------------------
class IntlDocIn(BaseModel):
    doc_type: str = Field(..., description="One of INTL_DOC_TYPES.code")
    status: str = Field("DRAFT", description="One of DOC_STATUSES")
    source: str = Field("INTERNAL_GEN", description="One of DOC_SOURCES")
    reference_number: Optional[str] = Field(None, max_length=80,
        description="ITN, Phyto cert#, LC#, BL#, etc.")
    counterparty: Optional[str] = Field(None, max_length=200)
    filed_with_agency: Optional[str] = Field(None, max_length=80,
        description="CBP, USDA-APHIS, US Census, issuing bank, etc.")
    filed_at: Optional[str] = None
    expires_at: Optional[str] = None
    notes: Optional[str] = Field(None, max_length=2000)


class DocStatusUpdate(BaseModel):
    status: str
    reference_number: Optional[str] = None
    note: Optional[str] = None


class AesFilingIn(BaseModel):
    itn: str = Field(..., min_length=14, max_length=20,
        description="AES Internal Transaction Number (14 chars, X-prefixed)")
    filed_at: Optional[str] = None
    filed_by: Optional[str] = Field(None, max_length=120)
    port_of_export: Optional[str] = None
    mode_of_transport: Optional[str] = None
    license_code: Optional[str] = Field(None, max_length=20)
    notes: Optional[str] = Field(None, max_length=1000)


# -------------------- HELPERS --------------------
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _aes_worksheet_md(b: Dict[str, Any]) -> str:
    """Generate the AES Filing Worksheet markdown. The broker hands this to
    whoever files in AESDirect (or runs through a forwarder)."""
    return f"""# AES Filing Worksheet · EEI

**Container booking**: {b['booking_id']} · {b.get('booking_number')}
**Vessel**: {b.get('vessel_name') or 'TBA'} v.{b.get('voyage_number') or 'TBA'}
**ETD**: {b.get('etd') or 'TBA'}

---

## USPPI (U.S. Principal Party In Interest)
- **Name**: {b.get('shipper_name')}
- **Address**: {b.get('shipper_address') or '____________________'}
- **EIN / DUNS / SSN**: ____________________
- **Contact**: {b.get('shipper_contact_email') or '____________________'}

## Ultimate Consignee
- **Name**: {b.get('consignee_name')}
- **Address**: {b.get('consignee_address') or '____________________'}
- **Country**: {b.get('pod', '').split('-')[0] if '-' in (b.get('pod') or '') else (b.get('pod') or '____________________')}
- **Role**: ☐ Direct consumer  ☐ Reseller  ☐ Govt entity  ☐ Other

## Forwarding Agent (filer)
- **Name**: ____________________
- **IRS ID**: ____________________
- **Address**: ____________________

## Commodity (one row per line item)
- **Schedule B / HTS (10-digit)**: {b.get('hs_code') or '____________________'}
- **Commodity description**: {b.get('commodity')}
- **Quantity (unit)**: {b.get('container_count')} × {b.get('container_size_type')}
- **Shipping weight (kg)**: {b.get('weight_kg') or '____________________'}
- **Value (USD, FOB)**: {f"${b.get('cargo_value_usd', 0):,.2f}" if b.get('cargo_value_usd') else '____________________'}
- **Country of Origin**: ____________________
- **License code**: C33 (NLR) ☐  · Other ____________________

## Routing
- **U.S. Port of Export**: {b.get('pol')} (CBP port code: ____________________)
- **Country of ultimate destination**: ____________________
- **Mode of Transport**: 10 (Vessel · containerized) ☐  · Other ____________________
- **Container indicator**: Y ☐  · N ☐
- **Carrier SCAC**: {b.get('carrier_scac')}
- **Vessel name + voyage**: {b.get('vessel_name') or 'TBA'} · {b.get('voyage_number') or 'TBA'}
- **Date of export**: {b.get('etd') or '____________________'}
- **Hazmat?**: {'Y · IMDG ' + (b.get('imdg_class') or '__') + ' · UN ' + (b.get('un_number') or '__') if b.get('hazmat') else 'N'}

---

## After Filing — Record the ITN
- **ITN (Internal Transaction Number)**: ______________________________
- **Filed at**: ______________________________
- **Filed by**: ______________________________

> Once AESDirect returns the ITN, paste it into the TMS:
> POST /api/international/container-bookings/{b['booking_id']}/aes/filing
> with `{{"itn": "X..."}}` to bind it to this shipment.

---

## Quick Reference — Mode of Transport codes
- **10** Vessel (containerized) · **11** Vessel (non-containerized) · **12** Vessel (other)
- **20** Rail · **30** Truck · **40** Air · **50** Mail · **60** Hand-carried
"""


def _commercial_invoice_md(b: Dict[str, Any]) -> str:
    qty = b.get("container_count", 1)
    value = b.get("cargo_value_usd") or 0
    unit_price = value / max(qty, 1)
    weight = b.get("weight_kg") or "—"
    return f"""# Commercial Invoice · {b['booking_id']}

**Invoice date**: {_now_iso()[:10]}
**Container booking**: {b.get('booking_number')}
**Currency**: USD

---

## Seller (USPPI)
- **Name**: {b.get('shipper_name')}
- **Address**: {b.get('shipper_address') or '—'}
- **EIN**: ____________________

## Buyer (Consignee)
- **Name**: {b.get('consignee_name')}
- **Address**: {b.get('consignee_address') or '—'}
- **Country**: ____________________

## Routing
- **Mode of transport**: Vessel · containerized
- **Vessel / voyage**: {b.get('vessel_name') or 'TBA'} · {b.get('voyage_number') or 'TBA'}
- **POL → POD**: {b.get('pol')} → {b.get('pod')}
- **Final destination**: {b.get('final_destination') or b.get('pod')}
- **Incoterms 2020**: {b.get('incoterms')}

## Line Items
- **Description**: {b.get('commodity')}
- **HTS / Schedule B**: {b.get('hs_code') or '—'}
- **Quantity**: {qty} × {b.get('container_size_type')}
- **Unit price (USD)**: ${unit_price:,.2f}
- **Total weight (kg)**: {weight}
- **Country of origin**: ____________________

---

## Total · ${value:,.2f} USD

---

## Declarations
- The goods are of the country of origin stated above.
- The prices stated reflect the true selling price in arm's-length terms.
- No commission paid that is not declared.
- Buyer and seller are unrelated parties (or relationship has been declared).

## Authorized Signature
- **Signed**: ______________________________
- **Print name**: ______________________________
- **Title**: ______________________________
- **Date**: {_now_iso()[:10]}
"""


def _packing_list_md(b: Dict[str, Any]) -> str:
    qty = b.get("container_count", 1)
    weight = b.get("weight_kg") or 0
    per_ctr = weight / max(qty, 1) if weight else 0
    rows: List[str] = []
    for i in range(1, qty + 1):
        rows.append(f"- **Container #{i:02d}**: 1 × {b.get('container_size_type')} · "
                    f"{b.get('commodity')} · "
                    f"{per_ctr:,.0f} kg · CTNR# ____________ · Seal# ____________")
    body = "\n".join(rows) or "- (none — fill in when containers are stuffed)"
    return f"""# Packing List · {b['booking_id']}

**Issued**: {_now_iso()[:10]}
**Vessel / voyage**: {b.get('vessel_name') or 'TBA'} · {b.get('voyage_number') or 'TBA'}

---

## Shipper
- **Name**: {b.get('shipper_name')}
- **Address**: {b.get('shipper_address') or '—'}

## Consignee
- **Name**: {b.get('consignee_name')}
- **Address**: {b.get('consignee_address') or '—'}

## Routing
- **POL → POD**: {b.get('pol')} → {b.get('pod')}
- **Final destination**: {b.get('final_destination') or b.get('pod')}

---

## Containers / Packing Detail
{body}

## Totals
- **Containers**: {qty} × {b.get('container_size_type')}
- **Total weight (kg)**: {weight or '____________'}
- **Total value (USD)**: {f"${b.get('cargo_value_usd', 0):,.2f}" if b.get('cargo_value_usd') else '____________'}

## Authorized Signature
- **Signed**: ______________________________
- **Date**: {_now_iso()[:10]}
"""


def _coo_md(b: Dict[str, Any]) -> str:
    return f"""# Certificate of Origin · {b['booking_id']}

**Issued**: {_now_iso()[:10]}
**Vessel / voyage**: {b.get('vessel_name') or 'TBA'} · {b.get('voyage_number') or 'TBA'}

---

## Exporter
- **Name**: {b.get('shipper_name')}
- **Address**: {b.get('shipper_address') or '—'}

## Producer
- **Name**: ____________________ (☐ same as exporter)
- **Address**: ____________________

## Importer / Consignee
- **Name**: {b.get('consignee_name')}
- **Address**: {b.get('consignee_address') or '—'}

## Goods
- **Description**: {b.get('commodity')}
- **HTS / Schedule B**: {b.get('hs_code') or '—'}
- **Quantity**: {b.get('container_count')} × {b.get('container_size_type')}
- **Weight (kg)**: {b.get('weight_kg') or '—'}
- **Country of Origin**: ____________________
- **Origin Criterion (USMCA Article 4.2)**: ☐ A  ☐ B  ☐ C  ☐ D  ☐ E

---

## Declaration
I, the undersigned, certify that the information on this document is true
and accurate, and I assume responsibility for proving such representations.
I understand I am liable for any false statements or material omissions
made on or in connection with this document.

The goods originated in the territory of the country shown above and meet
all applicable origin requirements specified for such goods.

## Authorized Signature
- **Signed**: ______________________________
- **Print name**: ______________________________
- **Title**: ______________________________
- **Date**: {_now_iso()[:10]}
- **Telephone**: ______________________________
- **Email**: {b.get('shipper_contact_email') or '____________________'}
"""


def _phyto_md(b: Dict[str, Any]) -> str:
    return f"""# Phytosanitary Application Worksheet · USDA-APHIS PPQ Form 572

**Container booking**: {b['booking_id']} · {b.get('booking_number')}
**Issued**: {_now_iso()[:10]}

> This is a preparation worksheet for USDA-APHIS PPQ Form 572
> (Application for Federal Phytosanitary Certificate). The actual
> certificate is issued by a federal or state PPQ inspector after
> inspection. Use this to organize the data before applying via
> [PCIT (Phytosanitary Certificate Issuance & Tracking)](https://pcit.aphis.usda.gov).

---

## Exporter
- **Name & address**: {b.get('shipper_name')} · {b.get('shipper_address') or '____________________'}
- **Phone**: ____________________
- **Contact email**: {b.get('shipper_contact_email') or '____________________'}

## Consignee
- **Name & address**: {b.get('consignee_name')} · {b.get('consignee_address') or '____________________'}
- **Country of import**: ____________________

## Article(s) Description
- **Botanical name (genus + species)**: ______________________________
- **Commercial / common name**: {b.get('commodity')}
- **Place of origin**: ____________________
- **Quantity declared (units)**: ______________________________
- **Net weight (kg)**: {b.get('weight_kg') or '____________________'}
- **Distinguishing marks / lot numbers**: ______________________________

## Transport
- **Means of conveyance**: Vessel · {b.get('vessel_name') or 'TBA'} · v.{b.get('voyage_number') or 'TBA'}
- **Declared point of entry (foreign port)**: {b.get('pod') or '____________________'}
- **Date of departure**: {b.get('etd') or '____________________'}

## Treatment (Block 18)
- **Treatment applied**: ☐ Fumigation  ☐ Heat  ☐ Cold  ☐ Irradiation  ☐ Other ____________________
- **Chemical (active ingredient)**: ____________________
- **Concentration**: ____________________
- **Duration & temperature**: ____________________
- **Date treatment performed**: ____________________

## Additional Declarations
{('- ' + (b.get('phyto_additional_declarations') or 'None — list importing country-specific declarations here')).strip()}

---

## Inspector Use Only
- **Inspection date**: ____________________
- **Inspection place**: ____________________
- **Inspector name (signature)**: ______________________________
- **Phyto Certificate #**: ______________________________

> After USDA issues the certificate, upload the scanned PDF and record the
> cert number via POST /container-bookings/{b['booking_id']}/docs with
> doc_type=PHYTOSANITARY_CERT.
"""


def _loc_md(b: Dict[str, Any]) -> str:
    value = b.get("cargo_value_usd") or 0
    return f"""# Letter of Credit · Presentation Copy

**Container booking**: {b['booking_id']} · {b.get('booking_number')}
**Drafted**: {_now_iso()[:10]}

---

## Issuing Bank
- **Bank name**: ____________________
- **SWIFT BIC**: ____________________
- **L/C number**: ______________________________
- **Date of issue**: ____________________
- **Expiry date / place**: ____________________ · ____________________

## Applicant (Buyer)
- **Name**: {b.get('consignee_name')}
- **Address**: {b.get('consignee_address') or '—'}

## Beneficiary (Seller)
- **Name**: {b.get('shipper_name')}
- **Address**: {b.get('shipper_address') or '—'}

## Amount & Terms
- **Currency / amount**: USD ${value:,.2f}
- **Tolerance (+/-%)**: ____________________
- **Tenor**: ☐ Sight  ☐ {{30/60/90}} days after sight
- **Confirmation requested**: ☐ Yes  ☐ No
- **Incoterms 2020**: {b.get('incoterms')}
- **Partial shipments**: ☐ Allowed  ☐ Not allowed
- **Transshipment**: ☐ Allowed  ☐ Not allowed
- **Latest shipment date**: {b.get('etd') or '____________________'}

## Shipment
- **From**: {b.get('pol')}
- **To**: {b.get('pod')}
- **Goods**: {b.get('commodity')}
- **HTS / Schedule B**: {b.get('hs_code') or '____________________'}
- **Quantity**: {b.get('container_count')} × {b.get('container_size_type')}

## Documents Required (typical UCP 600 set)
- ☐ Signed Commercial Invoice (3 originals)
- ☐ Full set of Clean On-Board Ocean B/L (3/3 originals + 2 copies)
- ☐ Packing List (3 originals)
- ☐ Certificate of Origin (1 original)
- ☐ Phytosanitary Certificate (1 original) — if perishable / plant-based
- ☐ Insurance Policy or Certificate (110% of CIF value)
- ☐ Inspection Certificate (SGS / Bureau Veritas / Intertek)
- ☐ Beneficiary's Certificate of conformity

## Additional Conditions
- Documents must be presented within ____________________ days after B/L date
  but within L/C validity.
- Discrepancy fee for the account of: ☐ Applicant  ☐ Beneficiary
- This credit is subject to UCP 600 (2007 Revision · ICC Publication 600).

---

## Beneficiary Acceptance
- **Signed**: ______________________________
- **Date**: ______________________________
"""


def _isf10_md(b: Dict[str, Any]) -> str:
    return f"""# ISF-10 Filing Worksheet · CBP 19 CFR 149

**Container booking**: {b['booking_id']} · {b.get('booking_number')}
**Issued**: {_now_iso()[:10]}

> File ISF-10 (Importer Security Filing) at least **24 hours prior to
> vessel loading at the foreign port** to avoid CBP "Do Not Load" holds and
> $5,000+ penalties per violation. Filed via ABI / a customs broker.

---

## ISF Filer
- **Name**: ____________________ (typically your customs broker)
- **ABI filer code**: ____________________

## Importer of Record
- **Name**: {b.get('consignee_name')}
- **Address**: {b.get('consignee_address') or '—'}
- **EIN / IRS ID**: ____________________

## ISF Importer (if different from Importer of Record)
- **Name**: ____________________
- **Address**: ____________________

## The 10 Data Elements (24-hour rule)
1. **Seller (Owner) name & address**: {b.get('shipper_name')} · {b.get('shipper_address') or '____________________'}
2. **Buyer (Owner) name & address**: {b.get('consignee_name')} · {b.get('consignee_address') or '____________________'}
3. **Importer of Record number / Consignee number**: ____________________
4. **Consignee number(s)**: ____________________
5. **Manufacturer (or supplier) name & address**: ____________________
6. **Ship-to party name & address**: ____________________
7. **Country of origin**: ____________________
8. **HTS-US 6-digit minimum (10 preferred)**: {(b.get('hs_code') or '____________________')[:10]}
9. **Container stuffing location**: ____________________
10. **Consolidator (stuffer) name & address**: ____________________

## Plus 2 elements (24 hours prior to arrival)
- **Vessel stow plan**: ____________________ (provided by carrier)
- **Container Status Messages (CSM)**: ____________________ (provided by carrier)

## Vessel / Voyage
- **Carrier SCAC**: {b.get('carrier_scac')}
- **Vessel / voyage**: {b.get('vessel_name') or 'TBA'} · {b.get('voyage_number') or 'TBA'}
- **Port of Loading**: {b.get('pol')}
- **Port of Discharge**: {b.get('pod')}
- **ETA U.S.**: {b.get('eta') or 'TBA'}

---

## Filer Acknowledgement
- **ISF transaction #**: ____________________ (returned by CBP after filing)
- **Filed at**: ____________________
- **Filed by**: ______________________________
"""


def _cbp_7501_md(b: Dict[str, Any]) -> str:
    return f"""# CBP Entry Summary Prep · Form 7501

**Container booking**: {b['booking_id']} · {b.get('booking_number')}
**Issued**: {_now_iso()[:10]}

> Worksheet for CBP Form 7501 (Entry Summary). Submitted by the customs
> broker via ABI after the cargo arrives and is released. Liquidation
> occurs ~314 days after entry.

---

## Header
- **Filer Code / Entry Number**: ____________________
- **Entry Type**: ☐ 01 Consumption  ☐ 03 Antidumping/CVD  ☐ 11 Informal  ☐ 21 Warehouse  ☐ Other ____________________
- **Summary date**: ____________________
- **Surety code / bond amount**: ____________________ / $____________________
- **Mode of transport**: 10 (Vessel · containerized)
- **Carrier SCAC code**: {b.get('carrier_scac')}
- **Vessel / voyage**: {b.get('vessel_name') or 'TBA'} · {b.get('voyage_number') or 'TBA'}
- **Port of unlading**: {b.get('pod')}
- **Port of entry**: ____________________

## Parties
- **Importer of Record + EIN**: {b.get('consignee_name')} · EIN ____________________
- **Consignee + EIN**: ____________________
- **Manufacturer + MID**: ____________________
- **Selling Party / Exporter**: {b.get('shipper_name')}

## Line Items
- **HTSUS**: {b.get('hs_code') or '____________________'}
- **Description**: {b.get('commodity')}
- **Quantity (HTSUS unit)**: ____________________
- **Gross weight (kg)**: {b.get('weight_kg') or '____________________'}
- **Entered value (USD, CIF basis as required)**: {f"${b.get('cargo_value_usd', 0):,.2f}" if b.get('cargo_value_usd') else '____________________'}
- **Country of origin (ISO)**: ____________________
- **Country of export (ISO)**: ____________________

## Duty & Fee Calculation
- **Ad valorem duty rate**: ____________________ %
- **Estimated duty**: $____________________
- **Merchandise Processing Fee (MPF, 0.3464% min $32.71 max $634.62)**: $____________________
- **Harbor Maintenance Fee (HMF, 0.125%)**: $____________________
- **Total**: $____________________

## Special Programs
- **FTA / preference claimed**: ☐ USMCA  ☐ GSP  ☐ AGOA  ☐ KORUS  ☐ Other ____________________
- **AD/CVD case number**: ____________________ (if applicable)

---

## Broker Sign-off
- **Filer signature**: ______________________________
- **Date**: ______________________________
"""


def _broker_cover_md(b: Dict[str, Any]) -> str:
    return f"""# Customs Broker Cover Letter

**Container booking**: {b['booking_id']} · {b.get('booking_number')}
**Date**: {_now_iso()[:10]}

---

To: ____________________ (Customs Broker name)
From: {b.get('consignee_name')}
Re: Customs clearance instructions for inbound container shipment

Please clear the following inbound shipment on our behalf:

- **Carrier / SCAC**: {b.get('carrier_name')} ({b.get('carrier_scac')})
- **B/L number**: {b.get('booking_number')}
- **Vessel / voyage**: {b.get('vessel_name') or 'TBA'} · {b.get('voyage_number') or 'TBA'}
- **POL → POD**: {b.get('pol')} → {b.get('pod')}
- **ETA**: {b.get('eta') or 'TBA'}
- **Final destination (FF / inland)**: {b.get('final_destination') or b.get('pod')}
- **Containers**: {b.get('container_count')} × {b.get('container_size_type')}
- **Commodity**: {b.get('commodity')}
- **HTSUS (10-digit)**: {b.get('hs_code') or 'TBC'}
- **Declared value (USD)**: {f"${b.get('cargo_value_usd', 0):,.2f}" if b.get('cargo_value_usd') else 'TBC'}

## Attached Documents
- ☐ Commercial Invoice
- ☐ Packing List
- ☐ Bill of Lading (telex release / express release)
- ☐ Certificate of Origin (USMCA / Form A / generic)
- ☐ ISF-10 filing reference (if already filed)
- ☐ Phytosanitary cert (if regulated)

## Instructions
- Entry type: ☐ Consumption (01)  ☐ Other ____________________
- File entry by: ____________________
- Bond: ☐ Continuous (#____________________) ☐ Single-transaction
- Delivery instructions: drayage to {b.get('final_destination') or b.get('pod')}.
  Use chassis pool ____________________.
- Free Days: {{LFD = ____________________}}; please monitor and notify
  before chassis demurrage / port detention begins.

## Authorization
This letter authorizes the named broker to act on our behalf for the
shipment above, including but not limited to: filing CBP Entry Summary
(7501), paying duties/MPF/HMF, and obtaining cargo release.

- **Signed**: ______________________________
- **Print name**: ______________________________
- **Title**: ______________________________
"""


def _sed_md(b: Dict[str, Any]) -> str:
    """Legacy SED equivalent. Modern AES filings replaced paper SEDs but
    some destination customs still ask for an SED-style page."""
    return f"""# Shipper's Export Declaration (legacy SED format)

**Container booking**: {b['booking_id']}
**Issued**: {_now_iso()[:10]}

---

## USPPI
- **Name & address**: {b.get('shipper_name')} · {b.get('shipper_address') or '—'}
- **EIN / DUNS**: ____________________

## Ultimate Consignee
- **Name & address**: {b.get('consignee_name')} · {b.get('consignee_address') or '—'}
- **Country**: ____________________

## Forwarding Agent
- **Name & address**: ____________________

## Routing
- **Vessel / voyage**: {b.get('vessel_name') or 'TBA'} · {b.get('voyage_number') or 'TBA'}
- **Carrier SCAC**: {b.get('carrier_scac')}
- **Port of export (US)**: {b.get('pol')}
- **Country of ultimate destination**: ____________________
- **Final destination**: {b.get('final_destination') or b.get('pod')}
- **Date of export**: {b.get('etd') or '____________________'}

## Commodity
- **Schedule B (10-digit)**: {b.get('hs_code') or '____________________'}
- **Description**: {b.get('commodity')}
- **Quantity (Schedule B unit)**: {b.get('container_count')} × {b.get('container_size_type')}
- **Shipping weight (kg)**: {b.get('weight_kg') or '____________________'}
- **Value (USD, FOB)**: {f"${b.get('cargo_value_usd', 0):,.2f}" if b.get('cargo_value_usd') else '____________________'}
- **Country of origin**: ____________________
- **License code**: C33 (NLR) ☐ · Other ____________________

## ITN
- **AES ITN**: ______________________________
"""


# Map doc_type → markdown generator
PDF_GENERATORS: Dict[str, Callable] = {
    "AES_WORKSHEET":         _aes_worksheet_md,
    "COMMERCIAL_INVOICE":    _commercial_invoice_md,
    "PACKING_LIST":          _packing_list_md,
    "CERTIFICATE_OF_ORIGIN": _coo_md,
    "PHYTOSANITARY_PREP":    _phyto_md,
    "LETTER_OF_CREDIT":      _loc_md,
    "SED":                   _sed_md,
    "ISF_10":                _isf10_md,
    "CBP_7501_PREP":         _cbp_7501_md,
    "BROKER_COVER_LETTER":   _broker_cover_md,
}

DOC_TYPE_TITLES = {
    "AES_WORKSHEET":         ("AES Filing Worksheet (EEI)", "Export · AES prep"),
    "COMMERCIAL_INVOICE":    ("Commercial Invoice", "Export · Commercial"),
    "PACKING_LIST":          ("Packing List", "Export · Commercial"),
    "CERTIFICATE_OF_ORIGIN": ("Certificate of Origin", "Export · Origin"),
    "PHYTOSANITARY_PREP":    ("Phytosanitary Application", "Export · USDA-APHIS PPQ Form 572"),
    "LETTER_OF_CREDIT":      ("Letter of Credit", "Export · Banking · UCP 600"),
    "SED":                   ("Shipper's Export Declaration", "Export · Legacy"),
    "ISF_10":                ("ISF-10 Filing", "Import · CBP 19 CFR 149"),
    "CBP_7501_PREP":         ("CBP Entry Summary (7501)", "Import · CBP"),
    "BROKER_COVER_LETTER":   ("Customs Broker Cover Letter", "Import · Broker hand-off"),
}


# -------------------- ROUTER --------------------
def attach_intl_documents_router(
    router: APIRouter, *, db,
    get_current_user: Callable, require_role: Callable,
) -> None:
    """Attach extra endpoints onto an already-built international router.

    Designed to be called from inside `build_international_router` after the
    main routes are registered so it shares the same /international prefix.
    """
    admin_dep = Depends(require_role("admin", "dispatcher"))

    async def _booking(booking_id: str) -> Dict[str, Any]:
        b = await db.intl_container_bookings.find_one(
            {"booking_id": booking_id}, {"_id": 0})
        if not b:
            raise HTTPException(404, "Container booking not found")
        return b

    async def _active_brand() -> Dict[str, Any]:
        return await db.company_brand.find_one({"is_active": True}, {"_id": 0}) or {}

    async def _generate_pdf(booking_id: str, doc_type: str) -> bytes:
        gen = PDF_GENERATORS.get(doc_type)
        if not gen:
            raise HTTPException(400, f"No internal PDF generator for type '{doc_type}'")
        b = await _booking(booking_id)
        brand = await _active_brand()
        from routes.orisei_docs import build_branded_markdown_pdf
        title, subtitle = DOC_TYPE_TITLES.get(doc_type, (doc_type.replace("_", " "), ""))
        return build_branded_markdown_pdf(
            gen(b), title=f"{title} · {booking_id}",
            subtitle=subtitle or f"Container shipment {b.get('pol')} → {b.get('pod')}",
            doc_id=booking_id, brand=brand,
        )

    # =========== REFERENCE ENDPOINTS ===========
    @router.get("/aes/help")
    async def aes_help(_=Depends(get_current_user)) -> Dict[str, Any]:
        return {
            "fields": AES_REQUIRED_FIELDS,
            "filing_portal": "https://aesdirect.census.gov",
            "filer_help": "1-800-549-0595 (US Census AES help desk)",
            "notes": [
                "ITN format: X20240301000001 — 14 chars, X-prefix.",
                "File at least 24h before vessel loading for ocean shipments.",
                "Penalties up to $10,000 per violation; civil/criminal for false statements.",
                "Filings under $2,500 per Schedule B usually exempt — confirm with current FTR.",
            ],
        }

    @router.get("/phyto/help")
    async def phyto_help(_=Depends(get_current_user)) -> Dict[str, Any]:
        return {
            "fields": PHYTOSANITARY_REQUIRED_FIELDS,
            "filing_portal": "https://pcit.aphis.usda.gov",
            "form_number": "USDA-APHIS PPQ Form 572",
            "notes": [
                "Cert is issued by a state or federal PPQ inspector after inspection.",
                "Some destinations require additional declarations (e.g. 'Fumigated with methyl bromide at 48 g/m³ for 24h at 21°C').",
                "Apply at least 5–7 business days before vessel cut-off.",
                "Fee schedule lives at 7 CFR 354.3 (about $135 per cert in 2026).",
            ],
        }

    @router.get("/document-types")
    async def doc_types(_=Depends(get_current_user)) -> Dict[str, Any]:
        return {"items": INTL_DOC_TYPES, "statuses": DOC_STATUSES, "sources": DOC_SOURCES}

    # =========== DOC TRACKER ===========
    @router.get("/container-bookings/{booking_id}/docs")
    async def list_docs(booking_id: str,
                          _=Depends(get_current_user)) -> Dict[str, Any]:
        b = await _booking(booking_id)
        return {"items": b.get("documents") or [], "count": len(b.get("documents") or [])}

    @router.post("/container-bookings/{booking_id}/docs")
    async def add_doc(booking_id: str, payload: IntlDocIn,
                       user=admin_dep) -> Dict[str, Any]:
        if payload.doc_type not in {d["code"] for d in INTL_DOC_TYPES}:
            raise HTTPException(400, "Unknown doc_type")
        if payload.status not in DOC_STATUSES:
            raise HTTPException(400, "Invalid status")
        if payload.source not in DOC_SOURCES:
            raise HTTPException(400, "Invalid source")
        doc = {
            "doc_id": f"DOC-{uuid.uuid4().hex[:10].upper()}",
            "added_at": _now_iso(),
            "added_by": getattr(user, "name", "system"),
            "file_id": None,
            "filename": None,
            "content_type": None,
            **payload.model_dump(),
        }
        await db.intl_container_bookings.update_one(
            {"booking_id": booking_id},
            {"$push": {"documents": doc}})
        return doc

    @router.post("/container-bookings/{booking_id}/docs/upload")
    async def upload_doc(booking_id: str,
                          doc_type: str = Form(...),
                          status: str = Form("RECEIVED"),
                          reference_number: Optional[str] = Form(None),
                          counterparty: Optional[str] = Form(None),
                          filed_with_agency: Optional[str] = Form(None),
                          notes: Optional[str] = Form(None),
                          file: UploadFile = File(...),
                          user=admin_dep) -> Dict[str, Any]:
        """Upload an external doc (carrier-issued BL, USDA-issued phyto
        cert, signed LC, supplier invoice, etc.) and attach it to the
        container booking. File is stored in GridFS for retrieval."""
        if doc_type not in {d["code"] for d in INTL_DOC_TYPES}:
            raise HTTPException(400, "Unknown doc_type")
        await _booking(booking_id)  # validates booking exists
        from motor.motor_asyncio import AsyncIOMotorGridFSBucket
        bucket = AsyncIOMotorGridFSBucket(db, bucket_name="intl_docs")
        data = await file.read()
        gridfs_id = await bucket.upload_from_stream(
            file.filename or f"{doc_type}.pdf",
            data,
            metadata={"booking_id": booking_id, "doc_type": doc_type,
                       "uploaded_by": getattr(user, "name", "system"),
                       "content_type": file.content_type},
        )
        doc = {
            "doc_id": f"DOC-{uuid.uuid4().hex[:10].upper()}",
            "added_at": _now_iso(),
            "added_by": getattr(user, "name", "system"),
            "doc_type": doc_type,
            "status": status if status in DOC_STATUSES else "RECEIVED",
            "source": "EXTERNAL_UPLOAD",
            "reference_number": reference_number,
            "counterparty": counterparty,
            "filed_with_agency": filed_with_agency,
            "filed_at": None,
            "expires_at": None,
            "notes": notes,
            "file_id": str(gridfs_id),
            "filename": file.filename,
            "content_type": file.content_type,
            "file_size": len(data),
        }
        await db.intl_container_bookings.update_one(
            {"booking_id": booking_id},
            {"$push": {"documents": doc}})
        return doc

    @router.get("/container-bookings/{booking_id}/docs/{doc_id}/file")
    async def download_doc_file(booking_id: str, doc_id: str,
                                  _=Depends(get_current_user)) -> StreamingResponse:
        b = await _booking(booking_id)
        doc = next((d for d in (b.get("documents") or []) if d.get("doc_id") == doc_id), None)
        if not doc:
            raise HTTPException(404, "Doc not found on this booking")
        if not doc.get("file_id"):
            raise HTTPException(404, "This doc has no uploaded file — it is a tracker-only record")
        from bson import ObjectId
        from motor.motor_asyncio import AsyncIOMotorGridFSBucket
        bucket = AsyncIOMotorGridFSBucket(db, bucket_name="intl_docs")
        stream = await bucket.open_download_stream(ObjectId(doc["file_id"]))
        data = await stream.read()
        filename = doc.get("filename") or f"{doc['doc_type']}.pdf"
        return StreamingResponse(
            io.BytesIO(data),
            media_type=doc.get("content_type") or "application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'})

    @router.put("/container-bookings/{booking_id}/docs/{doc_id}/status")
    async def update_doc_status(booking_id: str, doc_id: str,
                                  payload: DocStatusUpdate,
                                  user=admin_dep) -> Dict[str, Any]:
        if payload.status not in DOC_STATUSES:
            raise HTTPException(400, "Invalid status")
        upd: Dict[str, Any] = {
            "documents.$.status": payload.status,
            "documents.$.updated_at": _now_iso(),
            "documents.$.updated_by": getattr(user, "name", "system"),
        }
        if payload.reference_number is not None:
            upd["documents.$.reference_number"] = payload.reference_number
        if payload.note:
            upd["documents.$.notes"] = payload.note
        res = await db.intl_container_bookings.update_one(
            {"booking_id": booking_id, "documents.doc_id": doc_id},
            {"$set": upd})
        if res.matched_count == 0:
            raise HTTPException(404, "Doc not found on this booking")
        return {"ok": True}

    @router.delete("/container-bookings/{booking_id}/docs/{doc_id}")
    async def delete_doc(booking_id: str, doc_id: str,
                          user=admin_dep) -> Dict[str, Any]:
        await db.intl_container_bookings.update_one(
            {"booking_id": booking_id},
            {"$pull": {"documents": {"doc_id": doc_id}}})
        return {"ok": True}

    # =========== ITN CAPTURE ===========
    @router.post("/container-bookings/{booking_id}/aes/filing")
    async def record_itn(booking_id: str, payload: AesFilingIn,
                          user=admin_dep) -> Dict[str, Any]:
        b = await _booking(booking_id)
        rec = {
            "itn": payload.itn.strip(),
            "filed_at": payload.filed_at or _now_iso(),
            "filed_by": payload.filed_by or getattr(user, "name", "system"),
            "port_of_export": payload.port_of_export or b.get("pol"),
            "mode_of_transport": payload.mode_of_transport or "10",
            "license_code": payload.license_code or "C33",
            "notes": payload.notes,
        }
        # Also auto-add an ITN_RECEIPT doc tracker entry
        tracker = {
            "doc_id": f"DOC-{uuid.uuid4().hex[:10].upper()}",
            "added_at": _now_iso(),
            "added_by": getattr(user, "name", "system"),
            "doc_type": "ITN_RECEIPT",
            "status": "FILED",
            "source": "PARTNER_PORTAL",
            "reference_number": payload.itn.strip(),
            "filed_with_agency": "US Census · AESDirect",
            "filed_at": rec["filed_at"],
            "notes": payload.notes,
            "file_id": None, "filename": None,
        }
        await db.intl_container_bookings.update_one(
            {"booking_id": booking_id},
            {"$set": {"aes_filing": rec},
              "$push": {"documents": tracker}})
        return {"ok": True, "aes_filing": rec}

    # =========== BRANDED DOC PDFS ===========
    @router.get("/container-bookings/{booking_id}/pdf/{doc_type}")
    async def pdf_for_type(booking_id: str, doc_type: str,
                            _=Depends(get_current_user)) -> StreamingResponse:
        # Normalize URL-friendly slugs → DOC_TYPE constants
        slug_map = {
            "aes-worksheet": "AES_WORKSHEET",
            "commercial-invoice": "COMMERCIAL_INVOICE",
            "packing-list": "PACKING_LIST",
            "certificate-of-origin": "CERTIFICATE_OF_ORIGIN",
            "phyto-application": "PHYTOSANITARY_PREP",
            "letter-of-credit": "LETTER_OF_CREDIT",
            "isf-10": "ISF_10",
            "cbp-7501-prep": "CBP_7501_PREP",
            "broker-cover-letter": "BROKER_COVER_LETTER",
            "sed": "SED",
        }
        norm = slug_map.get(doc_type.lower(), doc_type.upper())
        pdf = await _generate_pdf(booking_id, norm)
        filename = f"{norm}_{booking_id}.pdf"
        return StreamingResponse(
            io.BytesIO(pdf), media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'})
