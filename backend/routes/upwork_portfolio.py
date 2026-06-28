"""
Upwork Portfolio renderer — generates a polished, ready-to-paste Upwork
profile with three tiers of productized service offerings, leveraging the
founder's Stone Arch Commodities export-documentation credentials.

Endpoint
--------
* GET  /api/upwork-portfolio
    → structured JSON containing every section the user can copy-paste
      directly into Upwork (headline, hourly rate, overview, specialties,
      service catalog, skills, employment history, education,
      certifications, portfolio items).
* POST /api/upwork-portfolio/pdf
    → branded PDF rendering of the entire portfolio with the same
      Stone Arch award imagery used in shipper outreach.
"""
from __future__ import annotations

import io
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .orisei_docs import build_branded_markdown_pdf
from .shipper_outreach import FOUNDER_BIO_ASSETS, FOUNDER_CREDENTIALS


# ---------------------------------------------------------------------------
# Static portfolio content — calibrated to the founder's tier doc + Stone Arch
# track record. Every field is the polished copy ready to paste into Upwork.
# ---------------------------------------------------------------------------
HEADLINE = ("Logistics & DOT Compliance Expert · "
             "Ex-Top-100 U.S. Exporter · Fleet & Freight Specialist")

HOURLY_RATE_USD = 65          # $50–$100/hr effective rate, listed mid-band
MIN_PROJECT_BUDGET = 99

OVERVIEW = (
    "I spent five-plus years as the first employee and Export Documentation "
    "Specialist at Stone Arch Commodities (Minneapolis, MN) — a U.S. "
    "containerized agricultural-commodity exporter that earned the SBA "
    "Minnesota Small Business Exporter of the Year award and placed on the "
    "Journal of Commerce Top 100 U.S. Exporters list for two consecutive "
    "years (the youngest company on the 2020 list).\n\n"

    "I now build documentation systems, compliance playbooks, fleet-cost "
    "calculators, and custom logistics software for owner-operators, small "
    "carriers, freight brokers, and shippers who need their paperwork tight, "
    "their costs visible, and their drivers paid on time.\n\n"

    "What I bring to your project:\n"
    "• 5+ years of letters of credit, BOLs, USDA APHIS phyto certs, ISF "
    "10+2, AES filings via ACE, and ocean-carrier booking across every "
    "major NVOCC and steamship line.\n"
    "• Hands-on knowledge of FMCSA, DOT, Part 380/391/395/396 compliance, "
    "ELD, IFTA, hazmat (49 CFR), and BMC-84 broker authority.\n"
    "• Working freight brokerage I built from the ground up — Orisei Freight "
    "Solutions — so I know what actually breaks at 11 p.m. on a Friday "
    "and what doesn't.\n"
    "• I write things people can actually use: checklists that fit on one "
    "page, calculators that don't require a CPA, training modules drivers "
    "actually finish.\n\n"

    "If you need a quick deliverable I can have it in your inbox within "
    "48 hours. If you need a long-term operations partner I'll embed "
    "with your team as a fractional logistics consultant. Either way you "
    "get a single owner — me — accountable for the work.\n\n"

    "Reach out with the specifics of your project and I'll tell you "
    "exactly what it should cost, how long it'll take, and what the "
    "deliverable will look like before you spend a dollar."
)

SPECIALTIES = [
    "DOT compliance & FMCSA audits",
    "Hazmat (49 CFR) documentation",
    "Bill of lading & BOL template design",
    "CDL & hazmat endorsement training",
    "Fleet cost analysis & TCO modeling",
    "Route optimization (spreadsheet & software)",
    "Owner-operator business plans",
    "Freight broker authority setup (MC, BMC-84, UCR)",
    "Custom load-board / dispatch tooling",
    "Export documentation (LC, BL, ISF, AES, phyto)",
    "Containerized agricultural exports",
    "Logistics SaaS prototyping",
]

# ---------------------------------------------------------------------------
# Tier-based service catalog
# ---------------------------------------------------------------------------
TIERS = [
    {
        "tier": 1,
        "label": "Quick Deliverables",
        "price_range": "$99 – $299 fixed",
        "turnaround": "48–72 hours",
        "effective_rate": "$50–$75 / hr",
        "tagline": "One-page tools and templates you'll use the same day.",
        "services": [
            {
                "title": "DOT Hazmat Compliance Checklist",
                "upwork_listing": (
                    "I'll create a custom DOT hazmat compliance checklist for "
                    "your fleet — every 49 CFR touchpoint in one page."),
                "price": 149,
                "deliverables": [
                    "1-page printable PDF checklist branded for your fleet",
                    "Section-by-section 49 CFR citations",
                    "Driver acknowledgement signature block",
                    "Editable DOCX source file",
                ],
            },
            {
                "title": "Fuel Cost Tracker Spreadsheet",
                "upwork_listing": (
                    "Fleet Fuel Tracker — Excel/Google Sheets workbook that "
                    "calculates true cost-per-mile, IFTA exposure, and lane "
                    "profitability per truck."),
                "price": 199,
                "deliverables": [
                    "Excel + Google Sheets versions",
                    "Per-truck and per-driver dashboards",
                    "IFTA quarterly summary tab",
                    "30-minute walkthrough video",
                ],
            },
            {
                "title": "Bill of Lading Template Bundle",
                "upwork_listing": (
                    "Bill of Lading Template Bundle — VICS BOL, hazmat BOL, "
                    "international BOL, and ocean BL in editable PDF & DOCX."),
                "price": 129,
                "deliverables": [
                    "VICS standard BOL",
                    "Hazmat BOL with 49 CFR §172.201 fields",
                    "International straight BOL",
                    "Ocean bill of lading template",
                    "Editable PDF + DOCX for all four",
                ],
            },
            {
                "title": "CDL Study Guide (single topic)",
                "upwork_listing": (
                    "CDL Study Guide — pick one endorsement (Hazmat / Tanker / "
                    "Doubles-Triples / Air Brakes) and I'll deliver a tight "
                    "20-page study guide with practice questions."),
                "price": 179,
                "deliverables": [
                    "20-page printable PDF study guide",
                    "100 practice questions with answer key",
                    "Common-mistake checklist",
                    "Test-day cheat sheet (1 page)",
                ],
            },
        ],
    },
    {
        "tier": 2,
        "label": "Medium Projects",
        "price_range": "$499 – $1,499 fixed",
        "turnaround": "5–10 business days",
        "effective_rate": "$50–$100 / hr",
        "tagline": "Audit, analyze, train — productized consulting for "
                    "small carriers and brokers.",
        "services": [
            {
                "title": "Fleet Optimization Audit",
                "upwork_listing": (
                    "Fleet Optimization Audit — I'll analyze your costs and "
                    "deliver 15+ specific improvement recommendations with "
                    "dollar impact estimates."),
                "price": 799,
                "deliverables": [
                    "30-question intake questionnaire",
                    "1-hour discovery call",
                    "30+ page audit report with executive summary",
                    "15+ ranked recommendations with $ impact",
                    "Implementation roadmap (90 / 180 / 365 days)",
                    "Follow-up call after delivery",
                ],
            },
            {
                "title": "Complete CDL + Hazmat Endorsement Course",
                "upwork_listing": (
                    "Complete CDL Class A + Hazmat Endorsement training "
                    "package — 4 modules, practice tests, instructor notes."),
                "price": 1199,
                "deliverables": [
                    "4 study modules (General, Air Brakes, Combination, Hazmat)",
                    "500+ practice questions across the 4 modules",
                    "Instructor facilitation guide",
                    "Student-facing PDF + DOCX",
                    "Editable PowerPoint deck for in-person delivery",
                ],
            },
            {
                "title": "Custom Route Optimization Calculator",
                "upwork_listing": (
                    "Custom Route Optimization Calculator — your lanes, your "
                    "carriers, your fuel costs. Built in Excel / Google Sheets."),
                "price": 899,
                "deliverables": [
                    "Custom Excel / Google Sheets workbook",
                    "Up to 25 lanes pre-configured",
                    "Per-lane $/mile, margin, and ETA outputs",
                    "Fuel-cost & toll inputs by region",
                    "30-minute walkthrough video",
                ],
            },
            {
                "title": "Safety Training Video Script + Course Outline",
                "upwork_listing": (
                    "DOT / FMCSA Safety Training script + course outline — "
                    "ready to hand to a video team or read on camera."),
                "price": 699,
                "deliverables": [
                    "Word-for-word script (60-min total runtime)",
                    "Module outline with timing",
                    "On-screen graphic shot list",
                    "Knowledge-check questions (20)",
                    "Compliance citation appendix",
                ],
            },
            {
                "title": "Owner-Operator Business Plan Template Package",
                "upwork_listing": (
                    "Owner-Operator Business Plan + 3-year financial model — "
                    "lender-ready, FMCSA-compliant, customized to your truck."),
                "price": 749,
                "deliverables": [
                    "20-page narrative business plan template",
                    "3-year P&L + cash-flow model (Excel)",
                    "Startup-cost worksheet",
                    "Authority, insurance & UCR checklist",
                    "Executive summary 1-pager",
                ],
            },
        ],
    },
    {
        "tier": 3,
        "label": "Premium / Custom Builds",
        "price_range": "$2,000 – $10,000+ fixed · or $1,500–$3,000 / mo retainer",
        "turnaround": "3–8 weeks",
        "effective_rate": "$50–$100 / hr",
        "tagline": "Custom software builds and fractional CLO engagements "
                    "for fleets and brokerages ready to grow.",
        "services": [
            {
                "title": "Custom Fleet Management Software",
                "upwork_listing": (
                    "Custom Fleet Management Software — I'll build a load "
                    "board, dispatch tool, or cost tracker tailored to "
                    "your operation. React + FastAPI + MongoDB stack."),
                "price": 4500,
                "deliverables": [
                    "Discovery + spec doc",
                    "Custom React frontend (mobile + desktop)",
                    "FastAPI backend + MongoDB schema",
                    "User auth + role-based permissions",
                    "Cloud deploy + 30 days hypercare support",
                ],
            },
            {
                "title": "Full Compliance Training Program (20+ modules)",
                "upwork_listing": (
                    "Full DOT / FMCSA / Hazmat compliance training program — "
                    "20+ video-script-ready modules with assessments."),
                "price": 6500,
                "deliverables": [
                    "20+ module scripts (45-min average each)",
                    "Master facilitation guide",
                    "Per-module knowledge checks",
                    "Final certification exam + answer key",
                    "Editable slide decks for each module",
                    "SCORM-export-ready format on request",
                ],
            },
            {
                "title": "Fractional Logistics Consulting",
                "upwork_listing": (
                    "Fractional Chief Logistics Officer (CLO) — 10 hrs/week "
                    "retainer engagement for fleets, brokerages, and shippers."),
                "price": 2500,
                "price_unit": "/ month",
                "deliverables": [
                    "10 hrs/week dedicated time",
                    "Weekly office hours + Slack/email coverage",
                    "Monthly KPI digest + executive briefing",
                    "Vendor / carrier negotiation support",
                    "Compliance & audit posture review every 90 days",
                ],
            },
            {
                "title": "Multi-Fleet Optimization System",
                "upwork_listing": (
                    "Multi-Fleet Optimization System — for holding companies "
                    "or 3PLs managing 3+ fleets. Centralized lane pricing, "
                    "dispatch, and KPIs."),
                "price": 8500,
                "deliverables": [
                    "Multi-tenant architecture",
                    "Consolidated lane-cost dashboard",
                    "Cross-fleet driver / equipment routing",
                    "Per-fleet white-label branding",
                    "API + EDI interconnects (where applicable)",
                    "60 days hypercare + on-call support",
                ],
            },
        ],
    },
]

SKILLS = [
    "DOT compliance", "FMCSA regulations", "49 CFR (Hazmat)", "Part 391/395/396",
    "ELD mandate", "IFTA reporting", "BMC-84 broker authority", "MC authority filing",
    "Bill of Lading (VICS / Hazmat / Ocean BL)", "Letters of Credit", "ISF 10+2",
    "AES via ACE", "USDA APHIS phyto certs", "USSEC / FGIS inspections",
    "CDL Class A training", "Hazmat endorsement", "Owner-operator setup",
    "Fleet cost analysis", "Route optimization", "Load-board software",
    "Dispatch tooling", "Freight brokerage operations", "Customer onboarding",
    "Carrier sourcing", "Carrier qualification (MC, MCS-150)", "Factoring intake",
    "Cash-flow modeling", "Margin shield pricing", "FastAPI", "React", "MongoDB",
    "Microsoft Excel (advanced)", "Google Sheets (advanced)", "PowerPoint",
    "Adobe Acrobat / DOCX", "Project management",
]

EMPLOYMENT = [
    {
        "title": "Founder",
        "company": "Orisei Freight Solutions LLC",
        "location": "Minneapolis, MN",
        "start": "2026",
        "end": "Present",
        "summary": (
            "Built an asset-light freight brokerage from a clean sheet — "
            "Margin Shield pricing, immutable 7-year document vault, "
            "AI-coached Run-the-Load workflow, factoring & cash-flow command "
            "center, automated shipper outreach + onboarding."
        ),
    },
    {
        "title": "Export Documentation Specialist · First Employee",
        "company": "Stone Arch Commodities",
        "location": "Minneapolis, MN",
        "start": "2016",
        "end": "2021",
        "summary": (
            "Owned the full export documentation lifecycle for a U.S. "
            "containerized agricultural-commodity exporter. Built the doc "
            "stack from day one: letters of credit, bills of lading, USDA "
            "APHIS phyto certs, USSEC / FGIS inspection coordination, "
            "ISF 10+2 filings, AES submissions via ACE, ocean-carrier "
            "booking/release across every major NVOCC and steamship line "
            "moving DDGs, soybean meal, and animal-feed ingredients out "
            "of Minneapolis-area transload facilities to Asia, Latin "
            "America, and the Middle East."
        ),
    },
]

CERTIFICATIONS_AWARDS = [
    {
        "name": "SBA Minnesota Small Business Exporter of the Year",
        "year": 2019,
        "issuer": "U.S. Small Business Administration",
        "context": "Awarded to Stone Arch Commodities for excellence in "
                    "international trade.",
    },
    {
        "name": "JOC Top 100 U.S. Exporters",
        "year": "2019 & 2020",
        "issuer": "Journal of Commerce",
        "context": "Two consecutive years — youngest company on the 2020 list.",
    },
    {
        "name": "Canadian Pacific Transload Growth & Innovation Award",
        "year": 2019,
        "issuer": "Canadian Pacific Railway",
        "context": "Shoreham Minneapolis rail-to-container transload facility.",
    },
    {
        "name": "U.S. Grains Council essential-business feature",
        "year": 2020,
        "issuer": "U.S. Grains Council",
        "context": "COVID-era video feature at the Ag Transfer Minneapolis "
                    "transload facility.",
    },
]

PORTFOLIO_ITEMS = [
    {
        "title": "Orisei Freight Solutions — full-stack TMS",
        "category": "Custom Logistics Software",
        "description": (
            "Designed and built a complete Transportation Management System "
            "from scratch: Margin Shield broker pricing, immutable 7-year "
            "document vault, AI-coached 8-stage Run-the-Load workflow, "
            "factoring & cash-flow command center, automated shipper "
            "outreach & onboarding packets, KPI dashboards. React + "
            "FastAPI + MongoDB."
        ),
        "result": "Working production TMS handling real Book Load → Workflow "
                   "→ Factoring → Invoicing flow with immutable audit trail.",
    },
    {
        "title": "Stone Arch Commodities — export documentation system",
        "category": "Documentation & Compliance",
        "description": (
            "Built the export documentation backbone for a U.S. agricultural "
            "exporter from day one. LCs, BLs, ISF 10+2, AES via ACE, USDA "
            "APHIS phyto certs, USSEC / FGIS inspection coordination across "
            "every major NVOCC and steamship line."
        ),
        "result": "Helped scale the company onto the JOC Top 100 U.S. "
                   "Exporters list for two consecutive years.",
    },
    {
        "title": "Branded BOL / Rate Confirmation / Invoice templates",
        "category": "Templates & Tools",
        "description": (
            "Production-quality bills of lading, rate confirmations, and "
            "commercial invoices with auto-stamped immutable vault tracking "
            "— rendered server-side from markdown."
        ),
        "result": "Used daily by Orisei to issue legally-defensible paperwork "
                   "in 30 seconds per document.",
    },
]


# ---------------------------------------------------------------------------
# Router builder
# ---------------------------------------------------------------------------
class PortfolioPdfIn(BaseModel):
    include_pricing: bool = True
    include_awards: bool = True


def build_upwork_portfolio_router(*, db, get_current_user,
                                    require_role, active_brand_doc):
    router = APIRouter(prefix="/upwork-portfolio", tags=["upwork-portfolio"])

    @router.get("")
    async def get_portfolio(_=Depends(get_current_user)) -> Dict[str, Any]:
        return {
            "headline":          HEADLINE,
            "hourly_rate_usd":   HOURLY_RATE_USD,
            "min_project_budget": MIN_PROJECT_BUDGET,
            "overview":          OVERVIEW,
            "specialties":       SPECIALTIES,
            "tiers":             TIERS,
            "skills":            SKILLS,
            "employment":        EMPLOYMENT,
            "certifications":    CERTIFICATIONS_AWARDS,
            "portfolio_items":   PORTFOLIO_ITEMS,
            "credentials":       FOUNDER_CREDENTIALS,
        }

    def _portfolio_md(meta: Dict[str, str], opts: PortfolioPdfIn) -> str:
        lines: List[str] = []
        lines += [
            f"# {meta['founder'].upper()} · UPWORK PORTFOLIO",
            "",
            f"**{HEADLINE}**",
            "",
            f"**Hourly rate:** ${HOURLY_RATE_USD} / hr ·"
            f" **Minimum project budget:** ${MIN_PROJECT_BUDGET}",
            f"**Location:** {meta['city']} · **Site:** {meta['site']}",
            "",
            "---", "",
            "## Overview", "",
            OVERVIEW.replace("\n", "\n\n"),
            "",
            f"![SBA Minnesota Small Business Exporter of the Year — Stone Arch Commodities, May 2019]"
            f"({FOUNDER_BIO_ASSETS}/sba_award_team.jpg)",
            "",
            f"![JOC Top 100 U.S. Exporters listing — 2019]"
            f"({FOUNDER_BIO_ASSETS}/joc_top_100.png)",
            "",
        ]
        if opts.include_awards:
            lines += ["## Awards & Recognition", ""]
            for c in CERTIFICATIONS_AWARDS:
                lines.append(
                    f"- **{c['name']}** ({c['year']}, {c['issuer']}) — "
                    f"{c['context']}")
            lines += [
                "",
                f"![Canadian Pacific 2019 Transload Growth & Innovation Award — "
                f"Shoreham yard]({FOUNDER_BIO_ASSETS}/cp_transload_award.jpg)",
                "",
            ]

        lines += ["## Specialties", ""]
        lines.append(" · ".join(SPECIALTIES))
        lines += ["", "---", "", "## Service Catalog", ""]

        for t in TIERS:
            lines += [
                f"### Tier {t['tier']} · {t['label']}",
                "",
                f"**{t['tagline']}**",
                "",
                f"*Price range:* {t['price_range']}  ·  "
                f"*Turnaround:* {t['turnaround']}  ·  "
                f"*Effective hourly:* {t['effective_rate']}",
                "",
            ]
            for s in t["services"]:
                price_label = (f"${s['price']:,}{s.get('price_unit', '')}"
                                if opts.include_pricing else "")
                lines += [
                    f"#### {s['title']}" + (f" — {price_label}" if price_label else ""),
                    "",
                    f"> *Upwork listing:* {s['upwork_listing']}",
                    "",
                    "**Deliverables:**",
                ]
                for d in s["deliverables"]:
                    lines.append(f"- {d}")
                lines.append("")
            lines += ["---", ""]

        lines += ["## Selected Portfolio", ""]
        for p in PORTFOLIO_ITEMS:
            lines += [
                f"### {p['title']}",
                "",
                f"*Category:* {p['category']}",
                "",
                p["description"],
                "",
                f"**Result:** {p['result']}",
                "", "---", "",
            ]

        lines += ["## Employment", ""]
        for e in EMPLOYMENT:
            lines += [
                f"### {e['title']} — {e['company']}",
                f"*{e['location']} · {e['start']} – {e['end']}*",
                "",
                e["summary"], "",
            ]

        lines += [
            "## Skills", "",
            " · ".join(SKILLS),
            "",
            "---", "",
            f"**Contact:** {meta['contact']} · {meta['phone']} · {meta['site']}",
        ]
        return "\n".join(lines)

    @router.post("/pdf")
    async def get_pdf(opts: PortfolioPdfIn,
                       user=Depends(get_current_user)) -> StreamingResponse:
        brand = await active_brand_doc()
        from .shipper_outreach import _brand_meta as _bm
        meta = _bm(brand)
        md = _portfolio_md(meta, opts)
        pdf = build_branded_markdown_pdf(
            md,
            title=f"{meta['founder']} · Upwork Portfolio",
            subtitle="Logistics · DOT compliance · Fleet & freight specialist",
            brand=brand,
            personalization={"firm_name": "Upwork Profile",
                              "contact_name": meta["founder"],
                              "prepared_date": __import__("datetime").datetime
                                  .now(__import__("datetime").timezone.utc)
                                  .strftime("%B %-d, %Y")},
        )
        # Auto-archive into the immutable Document Vault
        try:
            from .doc_vault import archive_pdf
            await archive_pdf(
                db, pdf,
                doc_type="UPWORK_PORTFOLIO",
                doc_id=f"PORTFOLIO-{meta['founder'].replace(' ', '_').upper()}",
                ref_id=None,
                source_endpoint="/api/upwork-portfolio/pdf",
                payload_snapshot=opts.model_dump(),
                user=user,
                filename=f"Upwork_Portfolio_{meta['founder'].replace(' ', '_')}.pdf",
            )
        except Exception:                                      # noqa: BLE001
            pass
        return StreamingResponse(
            io.BytesIO(pdf), media_type="application/pdf",
            headers={"Content-Disposition":
                f'attachment; filename="Upwork_Portfolio_{meta["founder"].replace(" ", "_")}.pdf"'},
        )

    return router
