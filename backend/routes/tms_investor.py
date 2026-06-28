"""routes.tms_investor — Hot Shot TMS public investor + VC package.

Separate from `routes.investor` (which is the Orisei Freight brokerage VC
package). This module pitches the **TMS PLATFORM ITSELF** to investors —
the white-label, re-themable, plug-and-play SaaS product Oliver built.

Public endpoints (no auth — VCs / press can hit directly):
  GET  /api/public/tms-pitch-summary        → hero + feature + market JSON
  GET  /api/public/tms-deck.pdf             → Hot Shot TMS pitch deck PDF
  GET  /api/public/tms-one-pager.pdf        → at-a-glance PDF
  GET  /api/public/tms-data-room.zip        → bundled deck + one-pager + plan PDF
"""
from __future__ import annotations

import io
import logging
import zipfile
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from .orisei_docs import build_branded_markdown_pdf

logger = logging.getLogger("tennant_tms.tms_investor")


HOT_SHOT_BRAND: Dict[str, Any] = {
    "company_name": "Hot Shot TMS",
    "short_name": "Hot Shot TMS",
    "tagline": "One TMS · Any Company · 60 seconds to skin",
    "primary_color": "#0EA5E9",
    "accent_color": "#22D3EE",
    "owner_name": "Oliver Cummins",
    "headquarters": "Plymouth, Minnesota",
}


PLUG_AND_PLAY: Dict[str, Any] = {
    "erp_connectors": [
        {"name": "SAP S/4HANA",       "category": "Tier-1 ERP"},
        {"name": "Oracle Fusion",     "category": "Tier-1 ERP"},
        {"name": "Microsoft D365 F&O", "category": "Tier-1 ERP"},
        {"name": "NetSuite",          "category": "Mid-market ERP"},
        {"name": "Infor M3",          "category": "Industrial ERP"},
        {"name": "Sage X3",           "category": "Mid-market ERP"},
        {"name": "Epicor Kinetic",    "category": "Industrial ERP"},
        {"name": "IFS Cloud",         "category": "Asset-heavy ERP"},
        {"name": "Custom REST",       "category": "Any modern API"},
    ],
    "launch_day_providers": [
        {"name": "DAT One",           "category": "Load Board"},
        {"name": "Truckstop",         "category": "Load Board"},
        {"name": "Convoy / Flexport", "category": "Load Board"},
        {"name": "Uber Freight",      "category": "Load Board"},
        {"name": "123Loadboard",      "category": "Load Board"},
        {"name": "Triumph",           "category": "Factoring"},
        {"name": "Apex Capital",      "category": "Factoring"},
        {"name": "OTR Capital",       "category": "Factoring"},
        {"name": "Resend",            "category": "Email Delivery"},
        {"name": "QuickBooks Online", "category": "Accounting"},
        {"name": "RMIS",              "category": "Carrier Vetting"},
        {"name": "Carrier411",        "category": "Carrier Vetting"},
        {"name": "FMCSA",             "category": "Regulatory"},
        {"name": "Tivly",             "category": "Insurance"},
    ],
    "encryption": "Fernet-encrypted credentials at rest · zero plaintext in logs",
    "activation_time_seconds": 60,
}


REBRANDING_DEMO: Dict[str, Any] = {
    "brand_reel": [
        {"name": "Orisei",     "color": "#0E3A6B"},
        {"name": "Walmart",     "color": "#0071CE"},
        {"name": "FedEx",       "color": "#4D148C"},
        {"name": "Caterpillar", "color": "#FFCD11"},
        {"name": "Apple",       "color": "#8E8E93"},
        {"name": "Amazon",      "color": "#FF9900"},
        {"name": "Tesla",       "color": "#CC0000"},
        {"name": "Coca-Cola",   "color": "#F40009"},
        {"name": "Boeing",      "color": "#0033A0"},
        {"name": "Nike",        "color": "#111111"},
    ],
    "what_changes": [
        "Company name, short name, tagline across every page",
        "Primary + accent palette (16+ named themes)",
        "Sample data — products, suppliers, lanes, facilities, drivers",
        "ERP context — connector defaults swap to match the brand",
        "Document headers — BOLs, PODs, compliance forms re-stamp instantly",
        "Marketing copy — landing page, services, contact, investor pages",
    ],
    "what_stays": [
        "User accounts, roles, RBAC",
        "Document history + audit trail",
        "Connections vault credentials",
        "Server-side encryption keys",
    ],
}


FEATURES: list[Dict[str, str]] = [
    {"title": "AI Company Themer",
     "body": "Type a company name → Claude Sonnet 4.5 writes the brand profile → app re-skins in 60 seconds. Zero implementation overhead."},
    {"title": "9 ERP Connectors",
     "body": "SAP, Oracle, Dynamics, NetSuite, Infor, Sage, Epicor, IFS, or any REST API. One-click test, two-click activate."},
    {"title": "14 Launch-Day Integrations",
     "body": "5 load boards, 3 factoring partners, Resend, QuickBooks, RMIS, Carrier411, FMCSA, Tivly — all pre-wired in the encrypted Connections vault."},
    {"title": "Multi-Modal Live Tracking",
     "body": "Truckload, LTL, parcel, ocean, air, rail on one Leaflet map with weather radar, storm alerts, and dwell timers."},
    {"title": "45-Metric Carrier Scorecard",
     "body": "OTD, tender accept %, claims ratio, dwell, accessorial spend — auto-emailed to leadership weekly. CSCMP/ATA/ISO 9001 aligned."},
    {"title": "Trade Compliance Desk",
     "body": "All 11 Incoterms 2020 · Section 301/232 watch · USMCA · FTZ · drawback · broker portal · ACE filings."},
    {"title": "Brand-Aware Document Engine",
     "body": "Every BOL, POD, and compliance form auto-stamps with the active brand's logo, palette, and footer in < 800ms."},
    {"title": "AI Co-Pilot",
     "body": "Draft carrier emails, summarize routing policies, lookup HS codes, extract BOL fields — Claude Sonnet 4.5 via the Emergent universal key."},
    {"title": "Truckload Booking Sheet",
     "body": "The team's live shared booking board. Click any cell, auto-saves to the cloud. Retires the daily emailed XLSX for good."},
    {"title": "Server Registry",
     "body": "Auto-detect TMS backend, MongoDB, Emergent LLM gateway, Kubernetes ingress + register custom servers with live health-checks."},
]


def _hot_shot_deck_md(founder: str = "Oliver Cummins") -> str:
    return f"""# Hot Shot TMS · VC Pitch Deck

## 1. Cover · The 30-Second Pitch
**Hot Shot TMS** — one Transportation Management System that re-themes itself
for any company in 60 seconds. Built by {founder}, a 13-year logistics
practitioner who has personally lived every workflow the platform surfaces.

## 2. The Problem
The TMS market is a $15B prison sentence. SAP TM, Oracle OTM, and Manhattan
each take 6–18 months to deploy, $500K–$2M to license, and require a 4-person
implementation team. Mid-market shippers ($100M–$2B revenue) are systematically
priced out, forced to run on Excel + email or duct-tape together a half-dozen
disconnected SaaS tools.

## 3. The Solution
A single white-label TMS that **skins itself for the prospect's company
DURING the sales call**:
- Type the company name → Claude Sonnet 4.5 generates the brand profile in 5 seconds.
- Watch the entire app — colors, sample data, ERP context, suppliers, lanes,
  document headers — re-shape around the prospect in real time.
- 60 seconds to a fully-themed live demo. 5 days to production deployment.
  No implementation lead time. No 18-month sales cycle.

## 4. Why Us · Founder Edge
{founder} has spent **13 years** in supply chain & logistics across all six
modes — truckload, LTL, parcel, ocean, air, rail. International specialist
(ocean booking lanes, customs clearance, FTAs, cross-border compliance).
Currently Transportation Analyst (prev. Fortune-500 industrials). Headquartered in
**Plymouth, Minnesota**.

Every screen in Hot Shot TMS was prototyped on **real loads, real BOLs, real
customer escalations**. Software houses can't fake 13 years of muscle memory.

## 5. The Platform · What's Built
**50+ integrated modules · 200+ API endpoints · 16 visual themes · 77-brand directory · 45 carrier-scorecard metrics**

- **Command Deck** — live map, weather, traffic, KPIs, broker feed, mini-calendar.
- **Truckload Booking Sheet** — team-shared live board with 4-second sync.
- **Multi-modal Live Tracking** — TL · LTL · parcel · ocean · air · rail on one map.
- **Equipment & Yard** — drag-drop XLSX → instant door map, dwell, carrier mix.
- **Carrier Onboarding** — MC/DOT/CSA vetting + W-9/COI + auto-stub on new names.
- **45-Metric Carrier Scorecard** — CSCMP/ATA/ISO 9001 aligned, weighted composite.
- **Trade Compliance Desk** — 11 Incoterms 2020, 301/232, USMCA, FTZ, ACE.
- **Document Vault** — GridFS-backed insurance, COI, W-9, contracts, MSDS.
- **AI Company Themer** — Claude Sonnet writes brand profiles in 5 seconds.
- **Connections Vault** — Fernet-encrypted credentials for 14 integrations.

## 6. Plug-and-Play Architecture
**9 ERP connectors out of the box**: SAP S/4HANA · Oracle Fusion · Microsoft
D365 F&O · NetSuite · Infor M3 · Sage X3 · Epicor Kinetic · IFS Cloud · Custom REST.

**14 launch-day integrations pre-wired**:
- Load Boards · DAT One, Truckstop, Convoy/Flexport, Uber Freight, 123Loadboard
- Factoring · Triumph, Apex Capital, OTR Capital
- Carrier Vetting · RMIS, Carrier411
- Email · Resend     · Accounting · QuickBooks Online
- Regulatory · FMCSA · Insurance · Tivly

Drop your endpoint URL, paste your service-user credentials, hit **Test
Connection** — done. Live orders, shipments, customers, and materials flow
into the app immediately. Encrypted at rest with Fernet. Zero plaintext in
logs. Multiple environments (PROD, QAS, DEV) side-by-side.

## 7. Changeability · The Re-Theme Wedge
**The wedge that wins enterprise deals.** Most TMS implementations take
6–18 months. Hot Shot TMS skins itself for the prospect's company **DURING**
the sales call.

What re-themes instantly:
- Company name + short name + tagline across every page
- Primary + accent palette (16+ named themes)
- Sample data: products, suppliers, lanes, facilities, drivers
- ERP context: connector defaults swap to match the brand
- Document headers: BOLs, PODs, compliance forms re-stamp instantly
- Marketing copy: landing page, services, contact, investor pages

What stays put:
- User accounts, roles, RBAC
- Document history + audit trail
- Connections vault credentials
- Server-side encryption keys

## 8. Market Size
- **TAM**: $15.3B global TMS market by 2030 (Gartner)
- **SAM**: $4.2B North American mid-market segment ($100M–$2B revenue shippers)
- **SOM (Y3 target)**: $12M (50 logos × $240K average ACV)

## 9. Go-to-Market
- **Year 1**: Founder-led sales. 5 anchor logos (5 MN-based industrials).
- **Year 2**: Productize playbook. 25 logos. First sales hire.
- **Year 3**: Scale to 50 logos. Channel partnerships with major 3PLs.
- **Distribution wedge**: 60-second skinned demo on every prospect call.

## 10. Business Model
- **Base license**: $24K/year per tenant
- **Per-integration**: $2K/year per active ERP/load-board/factoring connector
- **Per-shipment**: $0.10 metered (caps at $48K/year)
- **Average ACV**: $80K–$240K depending on integration count + volume
- **Gross margin**: 70% at scale (mostly Mongo + LLM token + Resend + hosting)
- **CAC**: sub-$5K via founder-led sales in Y1, $15K target via channel in Y3

## 11. Why Now
- SAP/Oracle implementation backlog at all-time high (18-month wait lists).
- Mid-market shipper IT budgets contracting — looking for opex SaaS, not capex.
- Claude Sonnet 4.5 finally makes "AI-generated brand profiles" production-quality.
- Emergent platform reduces SaaS deployment from 6 weeks to 6 hours.

## 12. Competition
- **SAP TM · Oracle OTM · Manhattan**: enterprise-grade but 6-18 month deploys, $500K-$2M licenses.
- **MercuryGate · BluJay · 3Gtms**: solid mid-market but no white-label, no re-theming.
- **Excel + email**: still the #1 competitor for $100M-$500M shippers.
- **Hot Shot TMS**: the rare hybrid — enterprise depth with 60-second skinning.

## 13. The Ask
Raising **$1.5M seed round** at a **$8M post-money cap, 20% discount SAFE**.

Use of funds:
- 1 senior full-stack engineer (12 mo) — $180K
- 1 founding sales hire — $120K base + commission
- Founder runway (12 mo) — $150K
- Marketing + outbound — $200K
- Customer success / implementation engineer — $130K
- Compliance + SOC 2 Type II audit — $90K
- Working capital / contingency — $230K
- Cloud infrastructure scaling (12 mo) — $100K
- Sales tooling + CRM + sales enablement — $80K
- Legal + IP + trademark — $50K
- Brand + content production — $40K
- Office + remote stipends — $130K

## 14. What's Already De-Risked
- **Platform shipped and operating in production today** — not a prototype.
- **9 ERP connectors live + tested** — connect to any tier-1 system today.
- **14 launch-day integrations pre-wired** — just drop credentials in the vault.
- **77-brand starter directory** — instant re-theme demos for any prospect.
- **Brand-aware document engine** — BOLs/PODs/forms render in < 800ms.
- **13-year founder operator track record** — references on request.

## 15. Contact
**{founder}** — Founder
Hot Shot TMS · Plymouth, Minnesota
shearperfection369@gmail.com
"""


def _hot_shot_one_pager_md(founder: str = "Oliver Cummins") -> str:
    return f"""# Hot Shot TMS · Investor One-Pager

**One TMS · Any Company · 60 seconds to skin**

## The 60-Second Pitch
Hot Shot TMS is the first Transportation Management System that **re-themes
itself for any company in 60 seconds**. Type the company name → Claude Sonnet
generates the brand profile → the entire app — colors, sample data, ERP
context, document headers — reshapes around the prospect during the sales call.

## Why Now · Why Us
- SAP/Oracle TM implementations take 6–18 months and cost $500K–$2M.
- Mid-market shippers ($100M–$2B) are systematically priced out.
- {founder} has spent **13 years** in supply chain & logistics across all six
  modes. Currently Transportation Analyst (prev. Fortune-500 industrials). Plymouth, MN.
- Every screen was prototyped on real loads, real BOLs, real escalations.

## The Platform
- **50+ modules · 200+ API endpoints · 16 themes · 77-brand directory**
- **9 ERP connectors**: SAP, Oracle, D365, NetSuite, Infor, Sage, Epicor, IFS, REST
- **14 launch-day integrations**: 5 load boards, 3 factoring, RMIS, Carrier411,
  Resend, QuickBooks, FMCSA, Tivly — all pre-wired, Fernet-encrypted vault
- **45-metric carrier scorecard** · CSCMP/ATA/ISO 9001 aligned
- **AI Co-Pilot** · Claude Sonnet 4.5 via Emergent universal key
- **Brand-aware document engine** · BOLs/PODs render in < 800ms

## Market & Business Model
- **TAM**: $15.3B global TMS (Gartner 2030 forecast)
- **SAM**: $4.2B North American mid-market
- **SOM (Y3)**: $12M (50 logos × $240K ACV)
- **Pricing**: $24K base + $2K/integration + $0.10/shipment
- **70% gross margin** at scale · sub-$5K CAC via founder-led sales

## The Ask
**$1.5M seed SAFE @ $8M cap, 20% discount.** 5 anchor logos by EOY 1.
25 logos by EOY 2. 50 logos and Series A milestone by EOY 3.

## Contact
**{founder}** · Founder · Hot Shot TMS · Plymouth, Minnesota
shearperfection369@gmail.com
"""


def build_tms_investor_router(api_router: APIRouter) -> None:
    """Wire up public Hot Shot TMS investor endpoints under /api/public/tms-*."""
    router = APIRouter(prefix="/public", tags=["public", "hot-shot-tms"])

    @router.get("/tms-pitch-summary")
    async def tms_pitch_summary() -> Dict[str, Any]:
        """Public payload for the Hot Shot TMS investor pitch page."""
        return {
            "brand": HOT_SHOT_BRAND,
            "founder": {
                "name": "Oliver Cummins",
                "title": "Founder · Builder · Operator",
                "tenure_years": 13,
                "location": "Plymouth, Minnesota",
                "current_role": "Transportation Analyst (prior)",
                "modes": ["Truckload", "LTL", "Parcel", "Ocean", "Air", "Rail"],
                "international_specialist": True,
                "bio": (
                    "Oliver has spent 13 years in supply chain and logistics across "
                    "all six modes — truckload, LTL, parcel, ocean, air, and rail. "
                    "He specializes in international logistics with deep experience "
                    "navigating ocean booking lanes, customs clearance, FTAs, and "
                    "cross-border compliance. He has worked at several major Minnesota "
                    "corporations and currently serves as a Transportation Analyst at "
                    "Fortune-500 industrials. Every screen was prototyped on "
                    "real loads, real BOLs, real customer escalations."
                ),
            },
            "platform_stats": {
                "modules": 50,
                "api_endpoints": 200,
                "visual_themes": 16,
                "brand_directory": 77,
                "scorecard_metrics": 45,
                "erp_connectors": 9,
                "launch_day_integrations": 14,
            },
            "features": FEATURES,
            "plug_and_play": PLUG_AND_PLAY,
            "rebranding": REBRANDING_DEMO,
            "market": {
                "tam_usd_billion": 15.3,
                "sam_usd_billion": 4.2,
                "som_year3_usd_million": 12.0,
                "source": "Gartner 2030 TMS market forecast",
            },
            "ask": {
                "instrument": "SAFE",
                "amount_usd": 1_500_000,
                "valuation_cap_usd": 8_000_000,
                "discount_pct": 20,
                "milestone_year1": "5 anchor logos · 5 MN industrials",
                "milestone_year2": "25 logos · first sales hire · productize playbook",
                "milestone_year3": "50 logos · Series A milestone · channel partnerships",
            },
            "video": {
                "primary_url": "/promo.mp4",
                "youtube_fallback_id": "BvIfgEW2NQE",
                "caption": (
                    "Watch Hot Shot TMS re-theme itself for FedEx, Coca-Cola, "
                    "Tesla, Apple, and any other company — in real time."
                ),
            },
            "deck_pdf_url":      "/api/public/tms-deck.pdf",
            "one_pager_pdf_url": "/api/public/tms-one-pager.pdf",
            "data_room_zip_url": "/api/public/tms-data-room.zip",
        }

    @router.get("/tms-deck.pdf")
    async def tms_deck_pdf() -> StreamingResponse:
        pdf = build_branded_markdown_pdf(
            _hot_shot_deck_md(),
            title="Hot Shot TMS · VC Pitch Deck",
            subtitle="Series Seed · Confidential",
            brand=HOT_SHOT_BRAND,
        )
        return StreamingResponse(
            io.BytesIO(pdf),
            media_type="application/pdf",
            headers={"Content-Disposition": 'inline; filename="Hot_Shot_TMS_Pitch_Deck.pdf"'},
        )

    @router.get("/tms-one-pager.pdf")
    async def tms_one_pager_pdf() -> StreamingResponse:
        pdf = build_branded_markdown_pdf(
            _hot_shot_one_pager_md(),
            title="Hot Shot TMS · Investor One-Pager",
            subtitle="At-a-glance · Confidential",
            brand=HOT_SHOT_BRAND,
        )
        return StreamingResponse(
            io.BytesIO(pdf),
            media_type="application/pdf",
            headers={"Content-Disposition": 'inline; filename="Hot_Shot_TMS_One_Pager.pdf"'},
        )

    @router.get("/tms-data-room.zip")
    async def tms_data_room_zip() -> StreamingResponse:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("01_Hot_Shot_TMS_Pitch_Deck.pdf",
                        build_branded_markdown_pdf(
                            _hot_shot_deck_md(),
                            title="Hot Shot TMS · VC Pitch Deck",
                            subtitle="Series Seed · Confidential",
                            brand=HOT_SHOT_BRAND,
                        ))
            zf.writestr("02_Hot_Shot_TMS_One_Pager.pdf",
                        build_branded_markdown_pdf(
                            _hot_shot_one_pager_md(),
                            title="Hot Shot TMS · Investor One-Pager",
                            subtitle="At-a-glance · Confidential",
                            brand=HOT_SHOT_BRAND,
                        ))
            zf.writestr("README.txt",
                        "Hot Shot TMS · VC Data Room\n"
                        f"Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}\n"
                        "\nContents:\n"
                        "  01_Hot_Shot_TMS_Pitch_Deck.pdf\n"
                        "  02_Hot_Shot_TMS_One_Pager.pdf\n"
                        "\nFounder: Oliver Cummins · shearperfection369@gmail.com\n"
                        "HQ: Plymouth, Minnesota\n")
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type="application/zip",
            headers={"Content-Disposition":
                     'attachment; filename="Hot_Shot_TMS_VC_Data_Room.zip"'},
        )

    api_router.include_router(router)
