"""routes.plan_brochure — Colorful brochure-style PDF of the Orisei business plan.

Magazine-style layout drawn directly on the ReportLab canvas: full-bleed cover,
stat cards, founder panels, use-of-funds bars, launch-runway timeline, and a
3-year financial spread. Complements (does not replace) the formal
`build_branded_markdown_pdf` long-form document.
"""
from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen.canvas import Canvas

from .orisei_docs import LOGO_PATH

W, H = letter  # 612 x 792

AZURE = colors.HexColor("#0E3A6B")
AZURE_DEEP = colors.HexColor("#082445")
GOLD = colors.HexColor("#C9A24A")
GOLD_LIGHT = colors.HexColor("#E6CB85")
TEAL = colors.HexColor("#0E7C7B")
CORAL = colors.HexColor("#E2725B")
PLUM = colors.HexColor("#6D3B8E")
FOREST = colors.HexColor("#2E7D46")
INK = colors.HexColor("#0B1320")
SLATE = colors.HexColor("#475569")
PAPER = colors.HexColor("#FBF8F0")
WHITE = colors.white


def _wrap(c: Canvas, text: str, font: str, size: float, max_w: float) -> List[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if c.stringWidth(trial, font, size) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _para(c: Canvas, text: str, x: float, y: float, font: str, size: float,
          max_w: float, color=INK, leading: Optional[float] = None) -> float:
    c.setFont(font, size)
    c.setFillColor(color)
    lead = leading or size * 1.35
    for line in _wrap(c, text, font, size, max_w):
        c.drawString(x, y, line)
        y -= lead
    return y


def _card(c: Canvas, x: float, y: float, w: float, h: float, fill,
          stroke=None, radius: float = 8):
    c.setFillColor(fill)
    if stroke:
        c.setStrokeColor(stroke)
        c.setLineWidth(1)
        c.roundRect(x, y, w, h, radius, fill=1, stroke=1)
    else:
        c.roundRect(x, y, w, h, radius, fill=1, stroke=0)


def _footer(c: Canvas, page: int, total: int):
    c.setFillColor(GOLD)
    c.rect(0, 26, W, 2.5, fill=1, stroke=0)
    c.setFont("Helvetica", 7)
    c.setFillColor(SLATE)
    c.drawString(40, 14, "Orisei Freight Solutions LLC · Minneapolis · Saint Paul · Brooklyn Park · Minnesota")
    c.drawRightString(W - 40, 14, f"Business Plan Brochure · 2026 · Page {page} of {total}")


def _page_head(c: Canvas, kicker: str, title: str, accent):
    c.setFillColor(AZURE)
    c.rect(0, H - 74, W, 74, fill=1, stroke=0)
    c.setFillColor(accent)
    c.rect(0, H - 80, W, 6, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 8.5)
    c.setFillColor(GOLD_LIGHT)
    c.drawString(40, H - 34, kicker.upper())
    c.setFont("Helvetica-Bold", 22)
    c.setFillColor(WHITE)
    c.drawString(40, H - 60, title)


def _stat_card(c: Canvas, x: float, y: float, w: float, h: float,
               value: str, label: str, accent):
    _card(c, x, y, w, h, WHITE, stroke=colors.HexColor("#E2E8F0"))
    c.setFillColor(accent)
    c.roundRect(x, y + h - 5, w, 5, 2, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 19)
    c.setFillColor(accent)
    c.drawCentredString(x + w / 2, y + h - 34, value)
    c.setFont("Helvetica", 7.5)
    c.setFillColor(SLATE)
    lines = _wrap(c, label.upper(), "Helvetica", 7.5, w - 14)
    ly = y + h - 48
    for ln in lines[:2]:
        c.drawCentredString(x + w / 2, ly, ln)
        ly -= 10


def _cover(c: Canvas):
    c.setFillColor(AZURE_DEEP)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setFillColor(AZURE)
    c.rect(0, H * 0.42, W, H * 0.58, fill=1, stroke=0)
    # gold diagonal ribbons
    c.setFillColor(GOLD)
    c.saveState()
    c.translate(0, H * 0.42)
    p = c.beginPath()
    p.moveTo(0, -14); p.lineTo(W, 22); p.lineTo(W, 8); p.lineTo(0, -28); p.close()
    c.drawPath(p, fill=1, stroke=0)
    c.restoreState()
    # accent color chips
    for i, col in enumerate([TEAL, CORAL, GOLD, PLUM, FOREST]):
        c.setFillColor(col)
        c.rect(40 + i * 26, H - 52, 18, 8, fill=1, stroke=0)
    # logo
    try:
        c.drawImage(str(LOGO_PATH), W / 2 - 55, H - 250, width=110, height=110,
                    preserveAspectRatio=True, mask="auto")
    except Exception:
        pass
    c.setFont("Helvetica-Bold", 33)
    c.setFillColor(WHITE)
    c.drawCentredString(W / 2, H - 306, "ORISEI FREIGHT")
    c.drawCentredString(W / 2, H - 344, "SOLUTIONS LLC")
    c.setFillColor(GOLD)
    c.rect(W / 2 - 110, H - 366, 220, 3, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 14)
    c.setFillColor(GOLD_LIGHT)
    c.drawCentredString(W / 2, H - 392, "BUSINESS PLAN · 2026 · PARTNERSHIP EDITION")
    c.setFont("Helvetica", 11.5)
    c.setFillColor(WHITE)
    c.drawCentredString(W / 2, H - 420, "Operator-built freight brokerage · Twin Cities, Minnesota")

    # founders band
    _card(c, 60, 190, W - 120, 110, colors.HexColor("#0B2E55"), stroke=GOLD, radius=12)
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(GOLD)
    c.drawCentredString(W / 2, 276, "CO-FOUNDERS & PRINCIPAL OWNERS · EQUAL THIRDS")
    c.setFont("Helvetica-Bold", 13.5)
    c.setFillColor(WHITE)
    c.drawCentredString(W / 2 - 178, 246, "Oliver Cummins")
    c.drawCentredString(W / 2, 246, "Daniel W. Karsor")
    c.drawCentredString(W / 2 + 178, 246, "Doug Graham")
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.HexColor("#9FB6D4"))
    c.drawCentredString(W / 2 - 178, 231, "Principal Broker · Operations")
    c.drawCentredString(W / 2, 231, "Technology · Brand · Capital")
    c.drawCentredString(W / 2 + 178, 231, "Capacity · Carrier Relations")
    c.setFillColor(GOLD)
    c.rect(W / 2 - 90, 224, 1.5, 40, fill=1, stroke=0)
    c.rect(W / 2 + 90, 224, 1.5, 40, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 10.5)
    c.setFillColor(GOLD_LIGHT)
    c.drawCentredString(W / 2, 204, "Launched on $30,000 of member capital — $10,000 from each of three founders")

    c.setFont("Helvetica", 8.5)
    c.setFillColor(colors.HexColor("#7E96B8"))
    c.drawCentredString(W / 2, 120, "oliver@oriseifreightsolutions.com · oliver@oriseifreightsolutions.com · oliver@oriseifreightsolutions.com")
    c.drawCentredString(W / 2, 106, f"Confidential · Prepared {datetime.now(timezone.utc).strftime('%B %Y')}")
    c.showPage()


def _page_glance(c: Canvas, page: int, total: int):
    c.setFillColor(PAPER)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    _page_head(c, "The Opportunity", "Freight Brokerage, At a Glance", TEAL)
    y = H - 120
    stats: List[Tuple[str, str, object]] = [
        ("$95B", "US brokerage market (2025)", TEAL),
        ("5–7%", "Market CAGR through 2028", CORAL),
        ("19–23%", "Orisei gross margin band", GOLD),
        ("$432K", "Year-1 revenue target", PLUM),
        ("$10K", "Total launch capital", FOREST),
        ("Mo 5", "Cash-flow positive", AZURE),
    ]
    cw, ch, gap = (W - 80 - 2 * 14) / 3, 78, 14
    for i, (v, l, col) in enumerate(stats):
        row, coln = divmod(i, 3)
        _stat_card(c, 40 + coln * (cw + gap), y - ch - row * (ch + gap), cw, ch, v, l, col)
    y -= 2 * (ch + gap) + 24

    _card(c, 40, y - 118, W - 80, 118, WHITE, stroke=GOLD_LIGHT, radius=10)
    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(AZURE)
    c.drawString(56, y - 26, "WHO WE ARE")
    _para(c, "Orisei Freight Solutions LLC is a lean, partner-operated property freight "
             "brokerage headquartered in the Twin Cities. We match vetted motor carriers to "
             "shipper freight across truckload, reefer, flatbed, LTL, expedited, and intermodal "
             "modes — powered by the proprietary Orisei Brokerage Command Deck TMS, built and "
             "maintained in-house by the founders.", 56, y - 44, "Helvetica", 9.5, W - 112, INK)
    y -= 142

    _card(c, 40, y - 128, W - 80, 128, AZURE, radius=10)
    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(GOLD)
    c.drawString(56, y - 26, "WHY WE WIN")
    bullets = [
        "13 years of shipper-side logistics operations — we quote a lane in 90 seconds.",
        "Two engineers on a homegrown TMS — a moat no single-agent shop can match.",
        "In-house podcast studio = zero-cost content engine for shippers and carriers.",
        "Trust-based West African diaspora carrier network across the Upper Midwest.",
        "Minnesota address + operator honesty: transparent margin on every QBR.",
    ]
    by = y - 44
    for b in bullets:
        c.setFillColor(GOLD)
        c.circle(62, by + 3, 2.2, fill=1, stroke=0)
        by = _para(c, b, 72, by, "Helvetica", 9, W - 130, WHITE, leading=15.5)
    _footer(c, page, total)
    c.showPage()


def _founder_panel(c: Canvas, x: float, y: float, w: float, h: float,
                   accent, name: str, role: str, facts: List[str], quote: str):
    _card(c, x, y, w, h, WHITE, stroke=colors.HexColor("#E2E8F0"), radius=10)
    c.setFillColor(accent)
    c.roundRect(x, y + h - 54, w, 54, 10, fill=1, stroke=0)
    c.rect(x, y + h - 54, w, 12, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 15)
    c.setFillColor(WHITE)
    c.drawString(x + 16, y + h - 30, name)
    c.setFont("Helvetica", 8.5)
    c.drawString(x + 16, y + h - 44, role)
    fy = y + h - 72
    for f in facts:
        c.setFillColor(accent)
        c.circle(x + 20, fy + 3, 2, fill=1, stroke=0)
        fy = _para(c, f, x + 30, fy, "Helvetica", 8.5, w - 46, INK, leading=13.5)
        fy -= 2
    c.setFillColor(colors.HexColor("#F1F5F9"))
    c.roundRect(x + 12, y + 12, w - 24, max(40, fy - y - 18), 6, fill=1, stroke=0)
    _para(c, quote, x + 22, fy - 14, "Helvetica-Oblique", 8, w - 44, SLATE, leading=12.5)


def _page_founders(c: Canvas, page: int, total: int):
    c.setFillColor(PAPER)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    _page_head(c, "The Partnership", "Three Founders, One Machine", CORAL)
    pw = (W - 80 - 32) / 3
    ph = H - 260
    _founder_panel(
        c, 40, 130, pw, ph, AZURE,
        "Oliver Cummins", "Co-Founder · Principal Broker · Operator · 33 1/3%",
        [
            "13 years in supply chain & logistics across TL, LTL, parcel, ocean, air, and rail.",
            "International specialist: customs, FTA / USMCA, port-of-entry strategy.",
            "Author of the Orisei Brokerage Command Deck — the firm's proprietary TMS.",
            "Contributes $10,000 capital — PAID IN FULL in-kind: designed & built the Command Deck, structured the business, and paid all Company expenses to date.",
            "Sole salaried member per the Partnership Agreement (§3.5).",
        ],
        "\u201cI've chased a short-shipped pallet at midnight and rebuilt a tender lane after a "
        "carrier defaulted on a Friday. I built Orisei to do what shippers wish their broker "
        "would do — on the first call.\u201d",
    )
    _founder_panel(
        c, 40 + pw + 16, 130, pw, ph, TEAL,
        "Daniel W. Karsor", "Co-Founder · Technology, Brand & Capital · 33 1/3%",
        [
            "Serial entrepreneur in Brooklyn Park, MN — barbershop + podcast / media studio.",
            "Software developer — co-develops and maintains the Orisei Command Deck.",
            "Deep roots in Minnesota's West African diaspora business community — a direct owner-operator carrier pipeline.",
            "Contributes $10,000 capital ($2,500 received · ORI-RCT-0001).",
            "Turns the podcast studio into Orisei's in-house media engine.",
        ],
        "\u201cA barber chair doesn't earn if it's empty. Freight is the same discipline at a "
        "bigger scale. Oliver knows the lanes; I build the machine and tell the story.\u201d",
    )
    _founder_panel(
        c, 40 + (pw + 16) * 2, 130, pw, ph, FOREST,
        "Doug Graham", "Co-Founder · Capacity & Carrier Relations · 33 1/3%",
        [
            "CDL Class A owner/operator — 12 years over-the-road experience.",
            "Vets carriers with a driver's instinct: equipment, HOS, rate honesty.",
            "Working network of owner-operators and small fleets built on the road.",
            "Contributes $10,000 capital ($1,300 received · ORI-RCT-0002) + in-kind expertise.",
            "Keeps Orisei's buy rates honest on both sides of every load.",
        ],
        "\u201cBrokers who've never been in the truck guess at what carriers will take. "
        "I don't guess. I know what that lane pays and who will actually show up.\u201d",
    )
    _footer(c, page, total)
    c.showPage()


def _page_funds(c: Canvas, page: int, total: int):
    c.setFillColor(PAPER)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    _page_head(c, "Capitalization", "Use of Funds — $30,000 · $10,000 Per Member", GOLD)
    cats = [
        ("Working Capital / Quick-Pay Float", 14000, TEAL,
         "Carrier quick-pay bridge until factoring is live — also seeds the in-house QuickPay spread program"),
        ("Growth & Contingency Reserve", 6000, PLUM,
         "Growth & Continued Operations Account — shipper acquisition, deferred tech, true contingency"),
        ("Owner Launch Runway Reserve", 4374, FOREST,
         "90-day member cushion — released only by unanimous consent"),
        ("Regulatory & Authority", 3316, AZURE,
         "LLC amendment · FMCSA OP-1FF · BMC-84 bond · BOC-3 · UCR · insurance down payment"),
        ("Technology (lean stack)", 1310, CORAL,
         "DAT One · QuickBooks · Carrier411 · domain, Workspace & VoIP — Command Deck is $0"),
        ("Marketing & Brand", 500, GOLD,
         "Website launch · outreach tooling · print & brochure collateral"),
        ("Legal & Professional", 500, SLATE,
         "Attorney review: partnership agreement + broker/carrier templates"),
    ]
    max_v = max(v for _, v, _, _ in cats)
    bar_max = W - 80 - 170
    y = H - 128
    for name, val, col, desc in cats:
        c.setFont("Helvetica-Bold", 10)
        c.setFillColor(INK)
        c.drawString(40, y, name)
        c.setFont("Helvetica-Bold", 10)
        c.setFillColor(col)
        c.drawRightString(W - 40, y, f"${val:,}")
        bw = max(30, bar_max * (val / max_v))
        c.setFillColor(colors.HexColor("#E9E4D6"))
        c.roundRect(40, y - 18, bar_max, 11, 5, fill=1, stroke=0)
        c.setFillColor(col)
        c.roundRect(40, y - 18, bw, 11, 5, fill=1, stroke=0)
        c.setFont("Helvetica-Bold", 7)
        c.setFillColor(WHITE if bw > 60 else col)
        pct = val / 30000 * 100
        c.drawString(46 if bw > 60 else 44 + bw + 4, y - 15.5, f"{pct:.1f}%")
        y = _para(c, desc, 40, y - 30, "Helvetica", 8, W - 90, SLATE, leading=11)
        y -= 14
    _card(c, 40, y - 46, W - 80, 44, AZURE, radius=8)
    c.setFont("Helvetica-Bold", 13)
    c.setFillColor(GOLD)
    c.drawString(56, y - 30, "TOTAL DEPLOYED")
    c.drawRightString(W - 56, y - 30, "$30,000")
    c.setFont("Helvetica", 7.5)
    c.setFillColor(WHITE)
    c.drawString(56, y - 41, "Every disbursement over $500 requires a second member's sign-off · float untouchable until first load books")
    _footer(c, page, total)
    c.showPage()


def _page_runway(c: Canvas, page: int, total: int):
    c.setFillColor(PAPER)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    _page_head(c, "Execution", "Owner Launch Runway — 12 Months", PLUM)
    phases = [
        ("WEEK 1–2", "First Shippers", TEAL,
         "Cold-call 5 qualified shippers · close 3 accounts (SUPERVALU anchor + 2) · sign Net 7/10/14 agreements."),
        ("WEEK 3–4", "Invoice Book", GOLD,
         "Run 20 real loads — invoiced, PODs filed · collect and bank $18,000 in shipper payments."),
        ("DAY 15–28", "Factoring Live", CORAL,
         "Apply to Rapid Finance + On The Spot · negotiate 3.75% fee, 85% advance, $50K line · UCC-1 filed by Day 28."),
        ("MONTH 2", "Prove the Engine", PLUM,
         "$40K invoiced · factor 80% ($32K) · pay carriers $26K · keep $6K margin."),
        ("MONTH 3–6", "Scale the Book", AZURE,
         "5–10 shippers · $80–120K weekly invoice volume · negotiate factor fee down to 3.5%."),
        ("MONTH 12", "The Win", FOREST,
         "20+ active shippers · $200K/week invoiced · $50–80K cumulative margin · business credit established."),
    ]
    y = H - 116
    rail_x = 88
    c.setFillColor(colors.HexColor("#D9D2BE"))
    c.rect(rail_x - 1.5, 128, 3, y - 128, fill=1, stroke=0)
    step_h = (y - 140) / len(phases)
    for i, (when, title, col, desc) in enumerate(phases):
        cy = y - i * step_h - 14
        c.setFillColor(col)
        c.circle(rail_x, cy, 7, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 7)
        c.drawCentredString(rail_x, cy - 2.3, str(i + 1))
        _card(c, rail_x + 22, cy - step_h + 26, W - rail_x - 62, step_h - 14, WHITE,
              stroke=colors.HexColor("#E2E8F0"), radius=8)
        c.setFillColor(col)
        c.rect(rail_x + 22, cy - step_h + 26, 5, step_h - 14, fill=1, stroke=0)
        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(col)
        c.drawString(rail_x + 38, cy - 4, when)
        c.setFont("Helvetica-Bold", 11.5)
        c.setFillColor(INK)
        c.drawString(rail_x + 38, cy - 18, title)
        _para(c, desc, rail_x + 38, cy - 32, "Helvetica", 8.5, W - rail_x - 110, SLATE, leading=12)
    _card(c, 40, 40, W - 80, 54, colors.HexColor("#123C22"), radius=8)
    c.setFont("Helvetica-Bold", 9.5)
    c.setFillColor(colors.HexColor("#9BE8B4"))
    c.drawString(56, 74, "WHY $10K IS ENOUGH")
    _para(c, "The plan never needs more cash than the $3,200 quick-pay float — factoring takes "
             "over working capital by Day 28. The $10K is a bridge to the factoring line, not fuel "
             "for the whole year.", 56, 61, "Helvetica", 8.5, W - 112, WHITE, leading=12)
    _footer(c, page, total)
    c.showPage()


def _page_financials(c: Canvas, page: int, total: int):
    c.setFillColor(PAPER)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    _page_head(c, "The Numbers", "3-Year Projections — Base Case (Brokerage-Only)", FOREST)
    rows = [
        ("Loads brokered (shipper-led ramp)", "2,000", "5,200", "6,760", False),
        ("Gross revenue ($2,000 avg FTL)", "$4,000,000", "$10,400,000", "$13,520,000", True),
        ("Carrier pay (85.5%)", "$3,420,000", "$8,892,000", "$11,559,600", False),
        ("Gross margin (14.5%)", "$580,000", "$1,508,000", "$1,960,400", True),
        ("Factoring / financing", "$130,000", "$208,000", "$162,240", False),
        ("OpEx (staff, boards, provisions)", "$249,600", "$696,600", "$959,600", False),
        ("EBITDA before partner pay", "$200,400", "$603,400", "$838,560", True),
        ("Net cash to members", "$140,000", "$350,000", "$530,000", True),
        ("Per-member share (1/3)", "$46,667", "$116,667", "$176,667", True),
    ]
    x0, tw = 40, W - 80
    col_w = [tw * 0.37, tw * 0.21, tw * 0.21, tw * 0.21]
    y = H - 112
    c.setFillColor(AZURE)
    c.roundRect(x0, y - 24, tw, 24, 6, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(WHITE)
    c.drawString(x0 + 12, y - 16, "LINE")
    for i, hdr in enumerate(["YEAR 1 · 2026", "YEAR 2 · 2027", "YEAR 3 · 2028"]):
        c.drawRightString(x0 + col_w[0] + sum(col_w[1:i + 2]) - 10, y - 16, hdr)
    y -= 24
    for label, y1, y2, y3, hilite in rows:
        rh = 21
        c.setFillColor(colors.HexColor("#FFF7E0") if hilite else WHITE)
        c.rect(x0, y - rh, tw, rh, fill=1, stroke=0)
        c.setStrokeColor(colors.HexColor("#EADFC4"))
        c.setLineWidth(0.4)
        c.line(x0, y - rh, x0 + tw, y - rh)
        c.setFont("Helvetica-Bold" if hilite else "Helvetica", 9)
        c.setFillColor(INK)
        c.drawString(x0 + 12, y - 14, label)
        for i, v in enumerate([y1, y2, y3]):
            c.setFillColor(FOREST if hilite else SLATE)
            c.drawRightString(x0 + col_w[0] + sum(col_w[1:i + 2]) - 10, y - 14, v)
        y -= rh
    y -= 24

    cw, ch, gap = (tw - 2 * 12) / 3, 70, 12
    for i, (v, l, col) in enumerate([
            ("Mo 2", "Lean break-even (~11 loads/mo)", TEAL),
            ("Mo 5", "Cash-flow positive incl. draws", CORAL),
            ("$0", "Outside equity — partner-controlled", PLUM)]):
        _stat_card(c, x0 + i * (cw + gap), y - ch, cw, ch, v, l, col)
    y -= ch + 26

    _card(c, x0, y - 96, tw, 96, AZURE, radius=10)
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(GOLD)
    c.drawString(x0 + 16, y - 24, "GOVERNANCE — THREE-MEMBER MINNESOTA PARTNERSHIP · EQUAL 33 1/3%")
    _para(c, "Member-managed LLC under Minn. Stat. Ch. 322C. Profits, losses, and distributions "
             "split equally among three members after a 10% reinvestment holdback. Operator salary "
             "to Oliver Cummins only (§3.5). Unanimous consent on all major decisions. Deadlock "
             "resolved by mediation, then buy-sell. Notarized agreement executed by all three "
             "members and stored in the Command Deck Document Vault.",
          x0 + 16, y - 42, "Helvetica", 9, tw - 32, WHITE, leading=13.5)
    y -= 118
    c.setFont("Helvetica-Bold", 8.5)
    c.setFillColor(AZURE)
    c.drawCentredString(W / 2, y, "Oliver Cummins · oliver@oriseifreightsolutions.com   |   Daniel W. Karsor · oliver@oriseifreightsolutions.com   |   Doug Graham · oliver@oriseifreightsolutions.com")
    c.setFont("Helvetica", 8)
    c.setFillColor(SLATE)
    c.drawCentredString(W / 2, y - 14, "Confidential — prepared for the members of Orisei Freight Solutions LLC")
    _footer(c, page, total)
    c.showPage()


def _page_hybrid(c: Canvas, page: int, total: int):
    c.setFillColor(PAPER)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    _page_head(c, "The Numbers", "Scenario B — 2-Truck Hybrid (Assets + Brokerage)", CORAL)
    rows = [
        ("Fleet loads (2 owned trucks)", "340", "430", "450", False),
        ("Fleet gross revenue (~$2.05/mi)", "$340,000", "$430,000", "$451,000", True),
        ("Fuel, maintenance & insurance", "$186,000", "$228,000", "$232,000", False),
        ("Driver pay & truck notes", "$72,000", "$86,000", "$90,000", False),
        ("Fleet net contribution", "$82,000", "$116,000", "$129,000", True),
        ("Brokerage EBITDA (base case)", "$200,400", "$603,400", "$838,560", False),
        ("Combined EBITDA", "$282,400", "$719,400", "$967,560", True),
        ("Net cash to members", "$195,000", "$445,000", "$640,000", True),
        ("Per-member share (1/3)", "$65,000", "$148,333", "$213,333", True),
    ]
    x0, tw = 40, W - 80
    col_w = [tw * 0.37, tw * 0.21, tw * 0.21, tw * 0.21]
    y = H - 112
    c.setFillColor(colors.HexColor("#5A2E1F"))
    c.roundRect(x0, y - 24, tw, 24, 6, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(WHITE)
    c.drawString(x0 + 12, y - 16, "LINE")
    for i, hdr in enumerate(["YEAR 1 · 2026", "YEAR 2 · 2027", "YEAR 3 · 2028"]):
        c.drawRightString(x0 + col_w[0] + sum(col_w[1:i + 2]) - 10, y - 16, hdr)
    y -= 24
    for label, y1, y2, y3, hilite in rows:
        rh = 21
        c.setFillColor(colors.HexColor("#FFF1E8") if hilite else WHITE)
        c.rect(x0, y - rh, tw, rh, fill=1, stroke=0)
        c.setStrokeColor(colors.HexColor("#EADFC4"))
        c.setLineWidth(0.4)
        c.line(x0, y - rh, x0 + tw, y - rh)
        c.setFont("Helvetica-Bold" if hilite else "Helvetica", 9)
        c.setFillColor(INK)
        c.drawString(x0 + 12, y - 14, label)
        for i, v in enumerate([y1, y2, y3]):
            c.setFillColor(CORAL if hilite else SLATE)
            c.drawRightString(x0 + col_w[0] + sum(col_w[1:i + 2]) - 10, y - 14, v)
        y -= rh
    y -= 24

    cw, ch, gap = (tw - 2 * 12) / 3, 70, 12
    for i, (v, l, col) in enumerate([
            ("2", "Trucks owned outright by the partnership", TEAL),
            ("+$129K", "Year-3 fleet net on top of brokerage EBITDA", CORAL),
            ("100%", "Tender acceptance on anchor shipper lanes", FOREST)]):
        _stat_card(c, x0 + i * (cw + gap), y - ch, cw, ch, v, l, col)
    y -= ch + 26

    _card(c, x0, y - 108, tw, 108, colors.HexColor("#123C22"), radius=10)
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(colors.HexColor("#9BE8B4"))
    c.drawString(x0 + 16, y - 24, "WHY OWNED TRUCKS CHANGE THE MATH")
    _para(c, "Two company trucks give Orisei guaranteed capacity on its anchor shipper lanes — no "
             "scrambling the spot market when a committed load drops. The fleet captures the full "
             "linehaul (not just the 14.5% brokerage spread), the Command Deck's backhaul matcher "
             "keeps both trucks loaded in every direction, and every mile builds asset equity the "
             "brokerage-only model never touches. Overflow beyond the two trucks flows straight to "
             "the brokered carrier network, so no freight is ever turned away.",
          x0 + 16, y - 42, "Helvetica", 9, tw - 32, WHITE, leading=13.5)
    y -= 130
    c.setFont("Helvetica", 8)
    c.setFillColor(SLATE)
    c.drawCentredString(W / 2, y, "Fleet assumptions: ~100K revenue miles/truck/yr · $2.05/mi blended · fuel $0.58/mi · trucks live Month 3 of Year 1")
    _footer(c, page, total)
    c.showPage()


def build_plan_brochure_pdf() -> bytes:
    buf = io.BytesIO()
    c = Canvas(buf, pagesize=letter)
    c.setTitle("Orisei Freight Solutions · Business Plan Brochure 2026")
    total = 7
    _cover(c)
    _page_glance(c, 2, total)
    _page_founders(c, 3, total)
    _page_funds(c, 4, total)
    _page_runway(c, 5, total)
    _page_financials(c, 6, total)
    _page_hybrid(c, 7, total)
    c.save()
    return buf.getvalue()
