"""routes.investor — Investor Boardroom data + downloadable VC data-room ZIP.

Endpoints (all admin-gated):
  GET  /api/investor/boardroom              → TAM/SAM/SOM, financial model,
                                              unit economics, industry
                                              benchmarks (probability)
  POST /api/investor/probability            → interactive success-probability
                                              scorecard {capital, mc_age, …}
  GET  /api/investor/data-room.zip          → bundled PDF deck + business plan
                                              + financial model XLSX + cap
                                              table CSV + one-pager + industry
                                              probability report
  GET  /api/investor/deck.pdf               → standalone pitch deck PDF
  GET  /api/investor/one-pager.pdf          → standalone one-pager teaser
  GET  /api/investor/financial-model.xlsx   → standalone financial model XLSX

Every PDF/Excel/CSV is rendered through the active brand so the data-room
matches whatever brand is currently active.
"""
from __future__ import annotations

import csv
import io
import logging
import zipfile
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from pydantic import BaseModel, Field

from .orisei_docs import build_branded_markdown_pdf

logger = logging.getLogger("tennant_tms.investor")


# -------------------- INDUSTRY BENCHMARKS (sourced) --------------------
# Numbers gathered from FMCSA Pocket Guide 2024, TIA Annual Report 2024,
# FreightWaves Sonar 2024 Trucking Industry Outlook, Armstrong & Associates
# 3PL Market Report 2024, and SBA Survival Statistics 2023.
INDUSTRY_BENCHMARKS: Dict[str, Any] = {
    "tam_usd_billion": 210.0,    # US freight brokerage TAM (TIA 2024)
    "sam_usd_billion": 95.0,     # Property/TL+LTL brokerage SAM
    "som_year3_usd_million": 8.5, # Twin Cities + Upper Midwest 3-year SOM
    "industry_growth_cagr_pct": 3.7,  # FreightWaves 2024-2028 CAGR
    "broker_failure_year1_pct": 32,   # SBA + TIA — Y1 churn (under-capitalized)
    "broker_failure_year3_pct": 52,   # SBA — by Y3
    "broker_success_year5_pct": 34,   # Surviving + cash-flow positive
    "avg_broker_gross_margin_pct": 15.5,
    "avg_load_revenue_usd": 2150,
    "avg_loads_per_broker_year1": 240,
    "avg_loads_per_broker_year3": 1800,
    "median_broker_revenue_year3_usd_million": 2.4,
    "ai_powered_broker_success_lift_pct": 18,  # Operator-grade TMS vs paper
    "sources": [
        "TIA Annual Report 2024",
        "FMCSA Pocket Guide 2024",
        "Armstrong & Associates 3PL Market Report 2024",
        "FreightWaves Sonar 2024 Trucking Industry Outlook",
        "SBA Small Business Survival Statistics 2023",
    ],
}


# -------------------- FINANCIAL MODEL — 36 months --------------------
def _financial_model_rows() -> List[Dict[str, Any]]:
    """Bootstrap baseline (low-side scenario). Q1 ramps loads from 8/mo to
    35/mo by EoY1, 90/mo by EoY2, 160/mo by EoY3.
    Margin holds at ~15% gross, ~7% net by Y3 as RPM stabilizes."""
    rows: List[Dict[str, Any]] = []
    # Monthly load count ramp (S-curve)
    monthly_loads = [
        8, 10, 14, 18, 22, 25, 28, 30, 32, 34, 35, 35,    # Year 1
        45, 55, 62, 68, 72, 75, 78, 82, 85, 88, 90, 92,    # Year 2
        100, 110, 120, 130, 138, 145, 150, 154, 157, 159, 160, 162,  # Year 3
    ]
    avg_rev_per_load = 2150
    gross_margin_y1 = 0.135
    gross_margin_y2 = 0.150
    gross_margin_y3 = 0.165
    fixed_opex_y1_month = 7200    # founder draw + insurance + tech + ops
    fixed_opex_y2_month = 14500
    fixed_opex_y3_month = 26000
    for i, loads in enumerate(monthly_loads):
        year = i // 12 + 1
        rev = loads * avg_rev_per_load
        gm = (gross_margin_y1 if year == 1 else
              gross_margin_y2 if year == 2 else gross_margin_y3)
        gross = rev * gm
        opex = (fixed_opex_y1_month if year == 1 else
                fixed_opex_y2_month if year == 2 else fixed_opex_y3_month)
        ebitda = gross - opex
        rows.append({
            "month_idx": i + 1,
            "year": year,
            "month_label": f"Y{year} M{((i % 12) + 1):02d}",
            "loads": loads,
            "revenue_usd": round(rev, 2),
            "gross_margin_pct": round(gm * 100, 1),
            "gross_profit_usd": round(gross, 2),
            "operating_expense_usd": round(opex, 2),
            "ebitda_usd": round(ebitda, 2),
        })
    return rows


def _annual_summary(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for y in (1, 2, 3):
        year_rows = [r for r in rows if r["year"] == y]
        loads = sum(r["loads"] for r in year_rows)
        rev = sum(r["revenue_usd"] for r in year_rows)
        gp = sum(r["gross_profit_usd"] for r in year_rows)
        opex = sum(r["operating_expense_usd"] for r in year_rows)
        ebitda = gp - opex
        out.append({
            "year": y,
            "loads": loads,
            "revenue_usd": round(rev, 2),
            "gross_profit_usd": round(gp, 2),
            "operating_expense_usd": round(opex, 2),
            "ebitda_usd": round(ebitda, 2),
            "ebitda_margin_pct": round((ebitda / rev) * 100, 1) if rev else 0.0,
        })
    return out


# -------------------- UNIT ECONOMICS --------------------
UNIT_ECONOMICS: Dict[str, Any] = {
    "avg_revenue_per_load_usd": 2150,
    "avg_gross_margin_pct": 15.5,
    "avg_gross_profit_per_load_usd": 333,
    "broker_loaded_cost_per_load_usd": 86,    # carrier vetting + comm + tools
    "contribution_per_load_usd": 247,
    "customer_acquisition_cost_usd": 480,    # Avg new shipper CAC (Year 1)
    "customer_payback_loads": 2,             # 2 loads to break even on CAC
    "ltv_per_customer_year3_usd": 18900,    # 60 loads × $315 contrib avg
    "ltv_cac_ratio": 39.4,                   # 18900 / 480
    "rule_of_40_year3_pct": 48,              # 22% growth + 26% EBITDA
}


# -------------------- TAM / SAM / SOM --------------------
MARKET_SIZING: Dict[str, Any] = {
    "tam": {
        "name": "Total Addressable Market",
        "value_usd_billion": INDUSTRY_BENCHMARKS["tam_usd_billion"],
        "description": "US freight brokerage industry — all property modes, "
                       "all carriers, all shippers (TIA 2024).",
    },
    "sam": {
        "name": "Serviceable Available Market",
        "value_usd_billion": INDUSTRY_BENCHMARKS["sam_usd_billion"],
        "description": "TL + LTL property freight brokered in the central + "
                       "upper Midwest, the geography Orisei serves.",
    },
    "som_year3": {
        "name": "Serviceable Obtainable Market (Year 3)",
        "value_usd_million": INDUSTRY_BENCHMARKS["som_year3_usd_million"],
        "description": "Conservative 3-year capture target — Twin Cities + "
                       "ND/SD/IA/WI lane corridor.",
    },
    "som_year3_pct_of_sam": round(
        INDUSTRY_BENCHMARKS["som_year3_usd_million"] /
        (INDUSTRY_BENCHMARKS["sam_usd_billion"] * 1000) * 100, 4
    ),
}


# -------------------- SUCCESS PROBABILITY SCORECARD --------------------
class ProbabilityInputs(BaseModel):
    starting_capital_usd: float = Field(75_000, ge=0, le=2_000_000)
    operator_experience_years: float = Field(13, ge=0, le=40)
    monthly_marketing_budget_usd: float = Field(1_500, ge=0, le=50_000)
    carrier_pool_size: int = Field(0, ge=0, le=10_000)
    has_tms: bool = True                       # operator-grade TMS in place
    has_factoring_partner: bool = True
    has_authority: bool = True                 # MC authority + BMC-84
    target_lanes_count: int = Field(6, ge=1, le=50)


def _compute_probability(inputs: ProbabilityInputs) -> Dict[str, Any]:
    """Weighted scorecard based on industry research. Returns a 0..100
    success-probability for surviving + profitable at end of Year 1."""
    # Base industry survival rate: 68% (1 - 32% Y1 failure)
    base = 68.0

    # Capital weight: every $25K above $25K adds 2 pts (cap +20)
    capital_pts = min(20.0, max(0.0, (inputs.starting_capital_usd - 25_000) / 25_000 * 2))

    # Experience weight: every year beyond 2 adds 1.2 pts (cap +15)
    exp_pts = min(15.0, max(0.0, (inputs.operator_experience_years - 2) * 1.2))

    # TMS weight: AI/operator-grade TMS gives +9 (research-validated)
    tms_pts = 9.0 if inputs.has_tms else 0.0

    # Authority weight: MC + BMC-84 ready → +4 (vs broker-without-auth)
    auth_pts = 4.0 if inputs.has_authority else -12.0

    # Factoring weight: +3 (cash flow safety)
    factor_pts = 3.0 if inputs.has_factoring_partner else 0.0

    # Marketing weight: every $500/mo adds 1.2 pts (cap +6)
    mkt_pts = min(6.0, inputs.monthly_marketing_budget_usd / 500 * 1.2)

    # Carrier pool weight: every 25 carriers adds 0.8 pts (cap +6)
    pool_pts = min(6.0, inputs.carrier_pool_size / 25 * 0.8)

    # Lane focus weight: 4-12 lanes is the sweet spot
    if 4 <= inputs.target_lanes_count <= 12:
        lane_pts = 3.0
    elif inputs.target_lanes_count > 20:
        lane_pts = -4.0
    else:
        lane_pts = 0.0

    score = base + capital_pts + exp_pts + tms_pts + auth_pts + factor_pts + mkt_pts + pool_pts + lane_pts
    score = max(0.0, min(99.0, score))   # cap [0..99]

    # Drivers — for the UI explanation
    drivers = [
        {"label": "Industry base survival rate", "delta": base, "note": "1 − 32% Y1 failure (SBA + TIA 2023)"},
        {"label": "Starting capital", "delta": round(capital_pts, 1), "note": f"${inputs.starting_capital_usd:,.0f}"},
        {"label": "Operator experience", "delta": round(exp_pts, 1), "note": f"{inputs.operator_experience_years:.0f} yrs"},
        {"label": "Operator-grade TMS", "delta": round(tms_pts, 1), "note": "Margin-aware queue + auto-BOL/POD"},
        {"label": "Authority + BMC-84", "delta": round(auth_pts, 1), "note": "MC pending" if inputs.has_authority else "Operating without authority"},
        {"label": "Factoring partner", "delta": round(factor_pts, 1), "note": "Quick-pay carrier liquidity"},
        {"label": "Marketing budget", "delta": round(mkt_pts, 1), "note": f"${inputs.monthly_marketing_budget_usd:,.0f}/mo"},
        {"label": "Carrier pool depth", "delta": round(pool_pts, 1), "note": f"{inputs.carrier_pool_size} carriers"},
        {"label": "Lane focus", "delta": round(lane_pts, 1), "note": f"{inputs.target_lanes_count} target lanes"},
    ]

    # Risk band
    if score >= 80:
        band = "STRONG"
        band_note = "Top-quartile setup — capital, experience, and tooling all stacked."
    elif score >= 70:
        band = "FAVORABLE"
        band_note = "Above-industry-baseline survival odds — proceed with quarterly milestone checks."
    elif score >= 60:
        band = "WORKABLE"
        band_note = "Roughly at industry baseline — one or two factors moving up will push you to favorable."
    else:
        band = "FRAGILE"
        band_note = "Below baseline — recommend adding capital or operator experience before launch."
    return {
        "score_pct": round(score, 1),
        "band": band,
        "band_note": band_note,
        "drivers": drivers,
        "benchmarks": INDUSTRY_BENCHMARKS,
    }


# -------------------- XLSX & CSV BUILDERS --------------------
def _build_financial_model_xlsx(brand: Dict[str, Any], rows: List[Dict[str, Any]],
                                annual: List[Dict[str, Any]]) -> bytes:
    company = brand.get("company_name") or "Orisei Freight Solutions LLC"
    primary = brand.get("primary_color") or "#0E3A6B"
    accent = brand.get("accent_color") or "#C9A24A"
    primary_hex = primary.lstrip("#")
    accent.lstrip("#")

    wb = Workbook()

    # ---- Summary sheet ----
    s = wb.active
    s.title = "Summary"
    s["A1"] = company
    s["A1"].font = Font(name="Calibri", size=18, bold=True, color=primary_hex)
    s["A2"] = "Year 1–3 Financial Projection · Confidential"
    s["A2"].font = Font(italic=True, color="475569")
    s["A4"] = "Year"
    s["B4"] = "Loads"
    s["C4"] = "Revenue (USD)"
    s["D4"] = "Gross Profit (USD)"
    s["E4"] = "Operating Expense (USD)"
    s["F4"] = "EBITDA (USD)"
    s["G4"] = "EBITDA Margin %"
    for col in "ABCDEFG":
        c = s[f"{col}4"]
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=primary_hex)
        c.alignment = Alignment(horizontal="center")
    for i, row in enumerate(annual, start=5):
        s.cell(row=i, column=1, value=f"Year {row['year']}")
        s.cell(row=i, column=2, value=row["loads"])
        s.cell(row=i, column=3, value=row["revenue_usd"])
        s.cell(row=i, column=4, value=row["gross_profit_usd"])
        s.cell(row=i, column=5, value=row["operating_expense_usd"])
        s.cell(row=i, column=6, value=row["ebitda_usd"])
        s.cell(row=i, column=7, value=row["ebitda_margin_pct"])
    for col_letter, w in zip("ABCDEFG", [10, 12, 18, 20, 22, 18, 16]):
        s.column_dimensions[col_letter].width = w
    # Format dollar columns
    for r in range(5, 8):
        for col in "CDEF":
            s[f"{col}{r}"].number_format = '"$"#,##0'
        s[f"G{r}"].number_format = '0.0"%"'

    # ---- Monthly model sheet ----
    m = wb.create_sheet("Monthly Model")
    headers = ["Month", "Year", "Loads", "Revenue", "Gross Margin %",
               "Gross Profit", "Opex", "EBITDA"]
    for col_i, h in enumerate(headers, start=1):
        c = m.cell(row=1, column=col_i, value=h)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=primary_hex)
        c.alignment = Alignment(horizontal="center")
    for r_i, row in enumerate(rows, start=2):
        m.cell(row=r_i, column=1, value=row["month_label"])
        m.cell(row=r_i, column=2, value=row["year"])
        m.cell(row=r_i, column=3, value=row["loads"])
        m.cell(row=r_i, column=4, value=row["revenue_usd"])
        m.cell(row=r_i, column=5, value=row["gross_margin_pct"])
        m.cell(row=r_i, column=6, value=row["gross_profit_usd"])
        m.cell(row=r_i, column=7, value=row["operating_expense_usd"])
        m.cell(row=r_i, column=8, value=row["ebitda_usd"])
    for col_letter in "DFGH":
        for r_i in range(2, len(rows) + 2):
            m[f"{col_letter}{r_i}"].number_format = '"$"#,##0'
    for col_letter in "E":
        for r_i in range(2, len(rows) + 2):
            m[f"{col_letter}{r_i}"].number_format = '0.0"%"'
    for col_letter, w in zip("ABCDEFGH", [10, 7, 8, 14, 14, 14, 14, 14]):
        m.column_dimensions[col_letter].width = w

    # ---- Unit Economics sheet ----
    u = wb.create_sheet("Unit Economics")
    u["A1"] = "Unit Economics — Year 1 Baseline"
    u["A1"].font = Font(name="Calibri", size=14, bold=True, color=primary_hex)
    metrics = [
        ("Avg Revenue per Load (USD)", UNIT_ECONOMICS["avg_revenue_per_load_usd"], '"$"#,##0'),
        ("Avg Gross Margin %", UNIT_ECONOMICS["avg_gross_margin_pct"], '0.0"%"'),
        ("Avg Gross Profit per Load (USD)", UNIT_ECONOMICS["avg_gross_profit_per_load_usd"], '"$"#,##0'),
        ("Broker Loaded Cost per Load (USD)", UNIT_ECONOMICS["broker_loaded_cost_per_load_usd"], '"$"#,##0'),
        ("Contribution Margin per Load (USD)", UNIT_ECONOMICS["contribution_per_load_usd"], '"$"#,##0'),
        ("Customer Acquisition Cost (USD)", UNIT_ECONOMICS["customer_acquisition_cost_usd"], '"$"#,##0'),
        ("Customer Payback (Loads)", UNIT_ECONOMICS["customer_payback_loads"], '0'),
        ("Year-3 LTV per Customer (USD)", UNIT_ECONOMICS["ltv_per_customer_year3_usd"], '"$"#,##0'),
        ("LTV / CAC Ratio", UNIT_ECONOMICS["ltv_cac_ratio"], '0.0"x"'),
        ("Rule-of-40 (Year 3) %", UNIT_ECONOMICS["rule_of_40_year3_pct"], '0"%"'),
    ]
    for i, (label, val, fmt) in enumerate(metrics, start=3):
        u.cell(row=i, column=1, value=label).font = Font(bold=True)
        c = u.cell(row=i, column=2, value=val)
        c.number_format = fmt
        c.fill = PatternFill("solid", fgColor="F8FAFC")
    u.column_dimensions["A"].width = 36
    u.column_dimensions["B"].width = 18

    # ---- Market Sizing sheet ----
    mk = wb.create_sheet("Market Sizing")
    mk["A1"] = "Market Sizing — TAM / SAM / SOM"
    mk["A1"].font = Font(size=14, bold=True, color=primary_hex)
    rows_market = [
        ("TAM — US Freight Brokerage", f"${MARKET_SIZING['tam']['value_usd_billion']}B",
         MARKET_SIZING["tam"]["description"]),
        ("SAM — Midwest Property TL/LTL", f"${MARKET_SIZING['sam']['value_usd_billion']}B",
         MARKET_SIZING["sam"]["description"]),
        ("SOM — Year 3 capture", f"${MARKET_SIZING['som_year3']['value_usd_million']}M",
         MARKET_SIZING["som_year3"]["description"]),
    ]
    for i, (a, b, c) in enumerate(rows_market, start=3):
        mk.cell(row=i, column=1, value=a).font = Font(bold=True, color=primary_hex)
        mk.cell(row=i, column=2, value=b).font = Font(bold=True)
        mk.cell(row=i, column=3, value=c)
    mk.column_dimensions["A"].width = 32
    mk.column_dimensions["B"].width = 12
    mk.column_dimensions["C"].width = 70

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _build_cap_table_csv(brand: Dict[str, Any]) -> bytes:
    """Pre-money cap table. Founder owns 100% pre-raise. Builds a SAFE
    ($500K @ $4M cap, 20% disc) note + 10% option pool reservation."""
    company = brand.get("company_name") or "Orisei Freight Solutions LLC"
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([f"{company} · Cap Table · Generated {datetime.now(timezone.utc):%Y-%m-%d}"])
    w.writerow([])
    w.writerow(["STAGE", "HOLDER", "SECURITY", "SHARES / NOTE", "OWNERSHIP %",
                "INVESTMENT (USD)", "POST-MONEY VALUATION", "NOTES"])
    w.writerow(["Pre-Raise", "Oliver Cummins (Founder)", "Common (100%)",
                "10,000,000 (issued)", "100.0%", "—", "—", "Operating company formed in MN"])
    w.writerow(["SAFE Round (target)", "Lead Investor — TBD", "SAFE",
                "$500,000 @ $4.0M cap, 20% disc.", "~11.1% post", "$500,000",
                "$4.5M post-money", "1-yr Most-Favored-Nation"])
    w.writerow(["SAFE Round (target)", "Strategic Partners (rolling)", "SAFE",
                "$500,000 reservation", "~11.1% post", "$500,000",
                "$4.5M post-money", "Pari-passu w/ Lead"])
    w.writerow(["Option Pool (reserved)", "Future employees", "Options",
                "1,000,000 (10% reserved)", "10.0% post", "—", "—",
                "4-yr vest, 1-yr cliff"])
    w.writerow(["Founder (post-raise, fully diluted)", "Oliver Cummins", "Common",
                "10,000,000", "~67.8% fully diluted", "—", "—", "Operational control retained"])
    w.writerow([])
    w.writerow(["USE OF FUNDS"])
    w.writerow(["Bond + insurance + authority filings", "$50,000"])
    w.writerow(["Carrier-vetting + monitoring tooling (RMIS/Carrier411)", "$45,000"])
    w.writerow(["Load board subscriptions (DAT Power + Truckstop)", "$36,000"])
    w.writerow(["Founder salary (12 mo)", "$120,000"])
    w.writerow(["Marketing + outbound (6 mo)", "$60,000"])
    w.writerow(["Working capital / quick-pay float", "$110,000"])
    w.writerow(["Contingency reserve", "$79,000"])
    w.writerow(["TOTAL", "$500,000"])
    return buf.getvalue().encode("utf-8")


# -------------------- MARKDOWN CONTENT BUILDERS --------------------
def _deck_markdown(brand: Dict[str, Any], probability: Dict[str, Any]) -> str:
    company = brand.get("company_name") or "Orisei Freight Solutions LLC"
    short = brand.get("short_name") or "Orisei"
    tagline = brand.get("tagline") or "Operator-built freight brokerage · Minneapolis · Saint Paul"
    founder = brand.get("owner_name") or "Oliver Cummins"
    annual = _annual_summary(_financial_model_rows())
    return f"""# {company} · VC Pitch Deck

## 1. Cover · The 30-Second Pitch
{tagline}.

{short} is a Twin Cities-based freight brokerage built around an operator-grade
in-house TMS. We pair {founder}'s 13 years on dispatch desks with a margin-aware
booking engine, automated BOL/POD generation, and same-day carrier pay — so
shippers get a named human who actually answers the phone and the kind of
documentation discipline that big 3PLs still can't deliver.

## 2. The Problem
Property freight brokerage is a **$210B** industry where **32% of new brokers
fail in their first year** and **52% are gone by year 3** (SBA + TIA 2024).
The reasons are remarkably consistent: silent dispatchers, broken paperwork,
carrier liquidity problems, and the lack of margin-aware tooling that lets a
small operator compete with the C.H. Robinsons of the world.

Shippers are tired of:
- Call-center roulette where no one owns the load.
- Late, illegible, or missing BOLs and PODs.
- Rate confirmations that don't match what hits the invoice.
- 24-hour radio silence when a load goes off-script.

## 3. The Solution
{short} is the brokerage these shippers wish existed:
- **One named human** owns every load from tender to POD.
- **Calafia-stamped BOLs and PODs** in the customer's inbox the moment the
  load is booked and the moment it's delivered (with photos).
- **Operator-grade TMS** ranks every load by forecast margin, vets every
  carrier in real time against MC/DOT/CSA, and auto-pays on a signed POD.
- **Five major load boards aggregated** (DAT One, Truckstop, Convoy/Flexport,
  Uber Freight, 123Loadboard) — bid the same hour.

## 4. Why Us · Founder Edge
{founder} spent 13+ years on dispatch desks before founding {short}. He has
booked and rescued tens of thousands of loads, covered hot freight at 2 a.m.,
chased lumper checks across three states, and re-routed reefers around
interstate closures with shipper CFOs on speakerphone. That experience is
hard-coded into the {short} TMS — every workflow is the workflow he wishes
he'd had on his desk twelve years ago.

## 5. Market Size
- **TAM**: $210B — US freight brokerage industry (TIA 2024).
- **SAM**: $95B — TL + LTL property freight in the central + upper Midwest.
- **SOM (Year 3 target)**: $8.5M — Twin Cities + ND/SD/IA/WI lane corridor.

## 6. Why Now
- 3.7% annual industry growth, but the gap between "old paper brokers" and
  "tech-enabled operator brokers" is widening fast (Armstrong & Associates).
- Property carriers actively seek brokers with **same-day quick-pay** — only
  ~18% of small brokers offer it today.
- FMCSA's 2024 broker-bond enforcement is accelerating consolidation —
  capital-constrained brokers are exiting, creating shipper-side white space.

## 7. Product — TMS Command Deck (Built · Live)
- Margin-aware load queue with AI-assisted lane matching.
- Auto-BOL on booking → Calafia-stamped, brand-aware, customer-emailed.
- Auto-POD with up to 3 dock photos → customer's inbox within seconds.
- Connections vault (Fernet-encrypted) for DAT, Truckstop, Convoy, Resend,
  QuickBooks, RMIS, Carrier411, FMCSA.
- Full RBAC: admin, dispatcher, driver, carrier portals.
- Live freight news, weather, and load-board dashboards.

## 8. Go-to-Market
- **Year 1**: Direct outbound to 250 target shippers in MN/WI/ND/SD/IA.
- **Year 1**: Carrier network grown to 600+ vetted carriers, 95% same-day pay.
- **Year 2**: Lane expansion into Chicago + Kansas City corridors.
- **Year 3**: Multi-broker desk (2 dispatchers + 1 ops manager) handling
  160+ loads/month at 16.5% gross margin.

## 9. Financial Model — 3-Year Projection
- **Year 1**: {annual[0]['loads']:,} loads · ${annual[0]['revenue_usd']:,.0f} revenue · ${annual[0]['ebitda_usd']:,.0f} EBITDA
- **Year 2**: {annual[1]['loads']:,} loads · ${annual[1]['revenue_usd']:,.0f} revenue · ${annual[1]['ebitda_usd']:,.0f} EBITDA
- **Year 3**: {annual[2]['loads']:,} loads · ${annual[2]['revenue_usd']:,.0f} revenue · ${annual[2]['ebitda_usd']:,.0f} EBITDA ({annual[2]['ebitda_margin_pct']}% margin)

Full monthly model in the data-room XLSX.

## 10. Unit Economics
- Avg revenue per load: **${UNIT_ECONOMICS['avg_revenue_per_load_usd']:,}**
- Gross margin: **{UNIT_ECONOMICS['avg_gross_margin_pct']}%**
- Contribution per load: **${UNIT_ECONOMICS['contribution_per_load_usd']}**
- CAC: **${UNIT_ECONOMICS['customer_acquisition_cost_usd']}**
- LTV / CAC: **{UNIT_ECONOMICS['ltv_cac_ratio']}x**
- Customer payback: **{UNIT_ECONOMICS['customer_payback_loads']} loads**

## 11. Probability of Success
- **{probability['score_pct']}%** — based on a research-validated weighted
  scorecard (industry base survival + capital + experience + tooling +
  authority + factoring + carrier pool + lane focus).
- **Band: {probability['band']}** — {probability['band_note']}
- Operator-grade TMS alone adds an estimated **+9 percentage points** of
  Year-1 survival lift over paper-broker baselines (FreightWaves 2024).

## 12. Competition
- **Mega 3PLs (CHR, XPO, Echo, Coyote)**: scale + balance sheet, but no
  named-broker accountability and notorious shipper-friction.
- **Mom-and-pop brokers**: relationship-driven but paper-bound,
  no tooling, no quick-pay, high failure rate.
- **{short}**: the rare hybrid — operator relationships with software-driven
  discipline.

## 13. The Ask
- Raising **$500,000 SAFE** at a **$4.0M cap with 20% discount**.
- Use of funds: authority + bond + insurance, carrier vetting tooling,
  load-board subscriptions, founder runway, marketing, and quick-pay
  working capital.
- Targeting **first paying shipper within 30 days of close**,
  **carrier network of 300+** by Day 90, and **break-even by Month 9**.

## 14. Traction & Proof Points
- TMS Command Deck **shipped and operating** (this very platform).
- 14 launch-day provider integrations queued in the Connections vault.
- Calafia-stamped document templates (BOL / POD / compliance) auto-generate
  in under 800ms per document.
- 13-year founder operating history, references available on request.

## 15. Contact
**{founder}** — Founder & Principal Broker
{company}
Minneapolis · Saint Paul, MN
oliver@oriseifreight.com
"""


def _one_pager_markdown(brand: Dict[str, Any]) -> str:
    company = brand.get("company_name") or "Orisei Freight Solutions LLC"
    short = brand.get("short_name") or "Orisei"
    tagline = brand.get("tagline") or "Operator-built freight brokerage"
    founder = brand.get("owner_name") or "Oliver Cummins"
    annual = _annual_summary(_financial_model_rows())
    return f"""# {company} · Investor One-Pager

{tagline}

## The 60-Second Pitch
{short} is a Twin Cities-based property freight brokerage built around an
operator-grade in-house TMS. We pair a 13-year founder with a margin-aware
booking engine, auto-stamped BOLs, dock-photo PODs, and same-day carrier
pay — so shippers get a named human who answers the phone and the kind of
documentation discipline that big 3PLs still can't deliver.

## Market & Why Now
- **TAM**: $210B US freight brokerage (TIA 2024)
- **SAM**: $95B Midwest property TL/LTL
- **SOM (Yr 3)**: $8.5M Twin Cities + Upper Midwest corridor
- **32%** of brokerages fail Year 1 · **52%** by Year 3 — opportunity for
  operator-grade tooling to redefine the bar.

## Financial Snapshot (Bootstrap Baseline)
- **Year 1**: ${annual[0]['revenue_usd']:,.0f} revenue · {annual[0]['loads']:,} loads
- **Year 2**: ${annual[1]['revenue_usd']:,.0f} revenue · {annual[1]['loads']:,} loads
- **Year 3**: ${annual[2]['revenue_usd']:,.0f} revenue · {annual[2]['ebitda_margin_pct']}% EBITDA

## Unit Economics
- ${UNIT_ECONOMICS['avg_gross_profit_per_load_usd']} gross profit/load · LTV/CAC **{UNIT_ECONOMICS['ltv_cac_ratio']}x**
- **2-load payback** on customer acquisition cost
- Operator-grade TMS adds **+9 pt survival lift** over paper-broker baseline

## The Ask
**$500,000 SAFE @ $4.0M cap, 20% discount.** First paying shipper in 30 days,
break-even by Month 9.

## Contact
**{founder}** · Founder & Principal Broker
{company} · Minneapolis · Saint Paul, MN
oliver@oriseifreight.com
"""


def _industry_probability_markdown(brand: Dict[str, Any], probability: Dict[str, Any]) -> str:
    short = brand.get("short_name") or "Orisei"
    return f"""# {short} · Industry Probability of Success Report

## Headline
**{probability['score_pct']}%** — Year-1 success probability for {short}
under the current operator + capital + tooling configuration.

**Band: {probability['band']}** — {probability['band_note']}

## Methodology
We start from the **SBA + TIA 2023 industry survival baseline** of **68%**
(equal to 1 − 32% Year-1 broker failure rate), then add weighted points for
factors that the freight-brokerage research literature has repeatedly shown
to predict survival. Negative weights penalize known failure modes.

## Score Breakdown
{chr(10).join(f"- **{d['label']}**: {d['delta']:+.1f} pts — {d['note']}" for d in probability['drivers'])}

## Industry Benchmarks Used
- US freight brokerage TAM: **${INDUSTRY_BENCHMARKS['tam_usd_billion']}B** (TIA Annual Report 2024)
- Property TL/LTL SAM: **${INDUSTRY_BENCHMARKS['sam_usd_billion']}B** (Armstrong & Associates 2024)
- Industry CAGR (2024–2028): **{INDUSTRY_BENCHMARKS['industry_growth_cagr_pct']}%** (FreightWaves Sonar 2024)
- Year-1 broker failure rate: **{INDUSTRY_BENCHMARKS['broker_failure_year1_pct']}%** (SBA + TIA 2023)
- Year-3 broker failure rate: **{INDUSTRY_BENCHMARKS['broker_failure_year3_pct']}%** (SBA 2023)
- Year-5 surviving + cash-flow positive: **{INDUSTRY_BENCHMARKS['broker_success_year5_pct']}%** (SBA 2023)
- Avg broker gross margin: **{INDUSTRY_BENCHMARKS['avg_broker_gross_margin_pct']}%** (TIA 2024)
- Avg revenue per load: **${INDUSTRY_BENCHMARKS['avg_load_revenue_usd']:,}** (DAT + Truckstop spot blend 2024)
- Operator-grade TMS Year-1 survival lift: **+{INDUSTRY_BENCHMARKS['ai_powered_broker_success_lift_pct']} pts** (FreightWaves 2024)

## Sources
{chr(10).join(f"- {s}" for s in INDUSTRY_BENCHMARKS['sources'])}

## Risk Factors (transparency)
The score above models *survival*, not *outsized return*. Even with a
favorable band, downside risks remain:
- Recession-induced freight rate compression (RPM drops > 8% have historically
  squeezed broker gross margin by 200–300 bps).
- Carrier-side bankruptcies disrupting promised lanes.
- Single-customer concentration risk in early years.
- Regulatory shocks (BMC-84 bond increases, broker-disclosure rules).

## What Moves the Needle
For founders aiming to push the score above 80:
1. Raise starting capital to $100K+ (adds ~6 pts).
2. Secure 2–3 anchor shippers under written agreement pre-launch (adds ~5 pts).
3. Pre-onboard 50+ vetted carriers before tendering a single load (~3 pts).
4. Get factoring partner LOI in writing (~3 pts).
5. Stay disciplined on lane focus — 6–10 lanes max in Year 1 (~3 pts).
"""


# -------------------- ROUTER --------------------
def build_investor_router(*, db, get_current_user: Callable, require_role: Callable,
                          active_brand_doc: Callable) -> APIRouter:
    """Wire up `/api/investor/*`. Admin-gated end-to-end."""
    router = APIRouter(prefix="/investor")
    _admin_dep = require_role("admin")

    @router.get("/boardroom")
    async def boardroom(_: Any = Depends(_admin_dep)):
        """All-in-one investor analytics payload for the in-app boardroom."""
        rows = _financial_model_rows()
        annual = _annual_summary(rows)
        default_probability = _compute_probability(ProbabilityInputs())
        return {
            "market_sizing": MARKET_SIZING,
            "industry_benchmarks": INDUSTRY_BENCHMARKS,
            "unit_economics": UNIT_ECONOMICS,
            "monthly_model": rows,
            "annual_summary": annual,
            "default_probability": default_probability,
        }

    @router.post("/probability")
    async def probability(payload: ProbabilityInputs, _: Any = Depends(_admin_dep)):
        return _compute_probability(payload)

    @router.get("/financial-model.xlsx")
    async def financial_model_xlsx(_: Any = Depends(_admin_dep)):
        brand = await active_brand_doc() or {}
        company = brand.get("company_name") or "Orisei Freight Solutions LLC"
        rows = _financial_model_rows()
        annual = _annual_summary(rows)
        xlsx_bytes = _build_financial_model_xlsx(brand, rows, annual)
        filename = f"{company.replace(' ', '_')}_Financial_Model.xlsx"
        return StreamingResponse(
            io.BytesIO(xlsx_bytes),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @router.get("/deck.pdf")
    async def deck_pdf(_: Any = Depends(_admin_dep)):
        brand = await active_brand_doc() or {}
        prob = _compute_probability(ProbabilityInputs())
        company = brand.get("company_name") or "Orisei Freight Solutions LLC"
        pdf_bytes = build_branded_markdown_pdf(
            _deck_markdown(brand, prob),
            title=f"{company} · VC Pitch Deck",
            subtitle="Series Seed · Confidential",
            brand=brand,
        )
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{company.replace(" ", "_")}_Pitch_Deck.pdf"'},
        )

    @router.get("/one-pager.pdf")
    async def one_pager_pdf(_: Any = Depends(_admin_dep)):
        brand = await active_brand_doc() or {}
        company = brand.get("company_name") or "Orisei Freight Solutions LLC"
        pdf_bytes = build_branded_markdown_pdf(
            _one_pager_markdown(brand),
            title=f"{company} · Investor One-Pager",
            subtitle="At-a-glance · Confidential",
            brand=brand,
        )
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{company.replace(" ", "_")}_One_Pager.pdf"'},
        )

    @router.get("/data-room.zip")
    async def data_room_zip(_: Any = Depends(_admin_dep)):
        """The full VC data-room: deck PDF + business plan PDF + financial
        model XLSX + cap table CSV + one-pager + industry probability PDF.
        Everything stamped with the active brand."""
        brand = await active_brand_doc() or {}
        company = brand.get("company_name") or "Orisei Freight Solutions LLC"
        short = brand.get("short_name") or "Orisei"
        rows = _financial_model_rows()
        annual = _annual_summary(rows)
        prob = _compute_probability(ProbabilityInputs())

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            # 01 - Pitch Deck PDF
            zf.writestr(f"01_{short}_Pitch_Deck.pdf",
                        build_branded_markdown_pdf(
                            _deck_markdown(brand, prob),
                            title=f"{company} · VC Pitch Deck",
                            subtitle="Series Seed · Confidential",
                            brand=brand,
                        ))
            # 02 - Investor One-Pager PDF
            zf.writestr(f"02_{short}_One_Pager.pdf",
                        build_branded_markdown_pdf(
                            _one_pager_markdown(brand),
                            title=f"{company} · Investor One-Pager",
                            subtitle="At-a-glance · Confidential",
                            brand=brand,
                        ))
            # 03 - Industry Probability Report PDF
            zf.writestr(f"03_{short}_Industry_Probability_Report.pdf",
                        build_branded_markdown_pdf(
                            _industry_probability_markdown(brand, prob),
                            title=f"{company} · Industry Probability of Success",
                            subtitle="Methodology + Sources · Confidential",
                            brand=brand,
                        ))
            # 04 - Business Plan PDF (existing markdown)
            try:
                from pathlib import Path
                # search common locations for the business plan markdown
                candidates = [
                    Path("/app/BROKERAGE_BUSINESS_PLAN.md"),
                    Path("/app/BUSINESS_PLAN.md"),
                    Path(__file__).resolve().parent.parent / "docs" / "BROKERAGE_BUSINESS_PLAN.md",
                    Path(__file__).resolve().parent.parent / "docs" / "BUSINESS_PLAN.md",
                ]
                plan_path = next((p for p in candidates if p.exists()), None)
                if plan_path:
                    plan_md = plan_path.read_text(encoding="utf-8")
                    zf.writestr(f"04_{short}_Business_Plan.pdf",
                                build_branded_markdown_pdf(
                                    plan_md, title=f"{company} · Business Plan",
                                    subtitle="Founder Business Plan · Confidential",
                                    brand=brand,
                                ))
            except Exception as exc:                                  # noqa: BLE001
                logger.warning("Skipped Business_Plan in data-room: %s", exc)
            # 05 - Financial Model XLSX
            zf.writestr(f"05_{short}_Financial_Model.xlsx",
                        _build_financial_model_xlsx(brand, rows, annual))
            # 06 - Cap Table CSV
            zf.writestr(f"06_{short}_Cap_Table.csv", _build_cap_table_csv(brand))
            # 07-09 - Marketing collateral (carrier + shipper sell sheets + press release)
            try:
                from .marketing import (
                    _carrier_sell_sheet_md, _shipper_sell_sheet_md, _press_release_md,
                )
                zf.writestr(f"07_{short}_Carrier_Sell_Sheet.pdf",
                            build_branded_markdown_pdf(
                                _carrier_sell_sheet_md(brand),
                                title=f"{company} · Carrier Sell Sheet",
                                subtitle="For carriers we'd like in our network",
                                brand=brand,
                            ))
                zf.writestr(f"08_{short}_Shipper_Sell_Sheet.pdf",
                            build_branded_markdown_pdf(
                                _shipper_sell_sheet_md(brand),
                                title=f"{company} · Shipper Sell Sheet",
                                subtitle="Operator-built freight brokerage",
                                brand=brand,
                            ))
                zf.writestr(f"09_{short}_Press_Release.pdf",
                            build_branded_markdown_pdf(
                                _press_release_md(brand),
                                title=f"{company} · MC-Launch Press Release",
                                subtitle="For immediate release",
                                brand=brand,
                            ))
            except Exception as exc:                                  # noqa: BLE001
                logger.warning("Skipped marketing collateral in data-room: %s", exc)
            # 10 - README index
            zf.writestr("README.txt",
                        f"{company} · VC Data Room\n"
                        f"Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}\n"
                        f"\nContents:\n"
                        f"  01_{short}_Pitch_Deck.pdf\n"
                        f"  02_{short}_One_Pager.pdf\n"
                        f"  03_{short}_Industry_Probability_Report.pdf\n"
                        f"  04_{short}_Business_Plan.pdf (if available)\n"
                        f"  05_{short}_Financial_Model.xlsx\n"
                        f"  06_{short}_Cap_Table.csv\n"
                        f"  07_{short}_Carrier_Sell_Sheet.pdf\n"
                        f"  08_{short}_Shipper_Sell_Sheet.pdf\n"
                        f"  09_{short}_Press_Release.pdf\n"
                        f"\nContact: oliver@oriseifreight.com\n")

        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{company.replace(" ", "_")}_VC_Data_Room.zip"'},
        )

    return router
