"""routes.platform_manual — Orisei Command Deck Field Manual (brochure PDF).

Colorful step-by-step user manual for the whole brokerage platform: carrier
integration, daily workflow, AI Load Hunter, docs & money flow, and how to
run Operation Sandbox. Reuses the brochure drawing helpers.
"""
from __future__ import annotations

import io
from datetime import datetime, timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen.canvas import Canvas

from .orisei_docs import LOGO_PATH
from .plan_brochure import (
    AZURE, AZURE_DEEP, CORAL, FOREST, GOLD, GOLD_LIGHT, INK, PAPER, PLUM,
    SLATE, TEAL, WHITE, _card, _page_head, _para,
)

W, H = letter


def _footer(c: Canvas, page: int, total: int):
    c.setFillColor(GOLD)
    c.rect(0, 26, W, 2.5, fill=1, stroke=0)
    c.setFont("Helvetica", 7)
    c.setFillColor(SLATE)
    c.drawString(40, 14, "Orisei Command Deck · Field Manual v1.0 · Confidential — internal operations")
    c.drawRightString(W - 40, 14, f"Page {page} of {total}")


def _steps(c: Canvas, y: float, steps, accent):
    """Numbered step cards; returns new y."""
    for i, (title, desc) in enumerate(steps):
        h = 52
        _card(c, 40, y - h, W - 80, h, WHITE, stroke=colors.HexColor("#E2E8F0"), radius=8)
        c.setFillColor(accent)
        c.circle(62, y - h / 2, 11, fill=1, stroke=0)
        c.setFont("Helvetica-Bold", 11)
        c.setFillColor(WHITE)
        c.drawCentredString(62, y - h / 2 - 3.5, str(i + 1))
        c.setFont("Helvetica-Bold", 10)
        c.setFillColor(INK)
        c.drawString(84, y - 20, title)
        _para(c, desc, 84, y - 33, "Helvetica", 8, W - 150, SLATE, leading=10.5)
        y -= h + 10
    return y


def _cover(c: Canvas):
    c.setFillColor(AZURE_DEEP)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setFillColor(AZURE)
    c.rect(0, H * 0.44, W, H * 0.56, fill=1, stroke=0)
    c.setFillColor(GOLD)
    c.rect(0, H * 0.44 - 4, W, 6, fill=1, stroke=0)
    for i, col in enumerate([TEAL, CORAL, GOLD, PLUM, FOREST]):
        c.setFillColor(col)
        c.rect(40 + i * 26, H - 52, 18, 8, fill=1, stroke=0)
    try:
        c.drawImage(str(LOGO_PATH), W / 2 - 50, H - 232, width=100, height=100,
                    preserveAspectRatio=True, mask="auto")
    except Exception:
        pass
    c.setFont("Helvetica-Bold", 30)
    c.setFillColor(WHITE)
    c.drawCentredString(W / 2, H - 288, "COMMAND DECK")
    c.drawCentredString(W / 2, H - 322, "FIELD MANUAL")
    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(GOLD_LIGHT)
    c.drawCentredString(W / 2, H - 350, "THE COMPLETE OPERATOR'S GUIDE · 2026")
    c.setFont("Helvetica", 10)
    c.setFillColor(WHITE)
    c.drawCentredString(W / 2, H - 374, "Carrier integration · Daily ops · AI workflows · Docs & money · Operation Sandbox")

    _card(c, 70, 170, W - 140, 130, colors.HexColor("#0B2E55"), stroke=GOLD, radius=12)
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(GOLD)
    c.drawCentredString(W / 2, 278, "WHAT'S INSIDE")
    toc = ["1 · Platform map — every module at a glance",
           "2 · Carrier integration — onboard a carrier in 24 hours",
           "3 · The daily loop — morning to night operations",
           "4 · AI Load Hunter — autonomous load selection",
           "5 · Docs & money — BOL, POD, invoice, factoring, AR",
           "6 · Operation Sandbox — run a full sample week"]
    for i, t in enumerate(toc):
        c.setFont("Helvetica", 9)
        c.setFillColor(WHITE)
        c.drawString(96, 258 - i * 15, t)
    c.setFont("Helvetica", 8.5)
    c.setFillColor(colors.HexColor("#7E96B8"))
    c.drawCentredString(W / 2, 120, f"Orisei Freight Solutions LLC · Minneapolis, MN · Prepared {datetime.now(timezone.utc).strftime('%B %Y')}")
    c.showPage()


def _page_map(c: Canvas, page, total):
    c.setFillColor(PAPER); c.rect(0, 0, W, H, fill=1, stroke=0)
    _page_head(c, "Section 1", "Platform Map — Every Module At A Glance", TEAL)
    mods = [
        ("Command Center", TEAL, "Live KPIs, real weather (NWS), real road closures (state DOT), shipment pulse."),
        ("Brokerage · Aggregator", GOLD, "DAT + Truckstop + 123LB merged into one de-duped, margin-ranked feed."),
        ("AI Load Hunter", PLUM, "Autonomous scan-score-match engine. Review queue or full auto-book under a $ cap."),
        ("LTL Rates", CORAL, "Negotiated rate cards (R+L, SAIA, Dayton…) rated instantly with margin math."),
        ("Dispatch Autopilot", FOREST, "Carrier↔load ML matching, auto-offers, acceptance tracking."),
        ("Live Tracking", AZURE, "Leaflet map, ELD/GPS pings, driver console, check-calls."),
        ("Workflow · Run-the-Load", TEAL, "Stage checklist per load: rate con → dispatch → track → POD → invoice."),
        ("Accounting + AR Engine", GOLD, "P&L, aging buckets, auto-invoice on delivery, dunning, risk sync."),
        ("Factoring & Cash Flow", PLUM, "Factor routing, advances, reserve tracking, cash HUD."),
        ("Claims · QBR · CRM", CORAL, "Claims master, quarterly reviews, shipper relations deck."),
        ("Operation Sandbox", FOREST, "Full-fidelity sample week: 36 carriers, GPS, docs, money. All marked SAMPLE."),
        ("Marketing & Investor Hub", AZURE, "Brochures, business plan, pitch decks, outreach engine."),
    ]
    y = H - 108
    ph, pw = 74, (W - 80 - 2 * 12) / 3
    for i, (t, col, d) in enumerate(mods):
        row, coln = divmod(i, 3)
        x = 40 + coln * (pw + 12)
        py = y - ph - row * (ph + 10)
        _card(c, x, py, pw, ph, WHITE, stroke=colors.HexColor("#E2E8F0"), radius=8)
        c.setFillColor(col); c.rect(x, py + ph - 4, pw, 4, fill=1, stroke=0)
        c.setFont("Helvetica-Bold", 8.5); c.setFillColor(col)
        c.drawString(x + 10, py + ph - 18, t.upper())
        _para(c, d, x + 10, py + ph - 30, "Helvetica", 7, pw - 20, SLATE, leading=9.5)
    _footer(c, page, total); c.showPage()


def _page_carrier(c: Canvas, page, total):
    c.setFillColor(PAPER); c.rect(0, 0, W, H, fill=1, stroke=0)
    _page_head(c, "Section 2", "Integrate A Carrier In 24 Hours", GOLD)
    y = _steps(c, H - 104, [
        ("Collect the packet", "Request MC#, DOT#, W-9, and COI ($1M auto / $100K cargo). Brokerage → Drivers tab → send the Carrier Brochure + packet link in one email."),
        ("Vet in under 30 minutes", "FMCSA SAFER + Carrier411 check: authority age, safety rating, OOS ratio, double-broker alerts. Verify banking by phone call-back — never email-only."),
        ("Sign & load the roster", "DocuSign the carrier packet + NOA (if factoring). Add the carrier in Dispatch Autopilot → Carriers with equipment, service states, and insurance flags."),
        ("Connect their systems (optional)", "ELD/Samsara token for auto-tracking · EDI 204/990/214/210 via SPS Commerce for TMS-to-TMS · or REST API + webhooks. Phone/SMS/email fallback always works."),
        ("First load", "The AI Load Hunter pre-matches them automatically once active. Book from the winners queue — rate con is generated and e-signed in minutes."),
        ("Pay them their way", "Quick-pay (~48h), standard Net 30, or factor-direct with same-day NOA honor. Settlement status is visible to them in real time."),
    ], GOLD)
    _card(c, 40, y - 40, W - 80, 38, AZURE, radius=8)
    c.setFont("Helvetica-Bold", 8.5); c.setFillColor(GOLD)
    c.drawString(56, y - 18, "PRO TIP")
    _para(c, "Pre-onboard 15 carriers before authority activates — the Sandbox fleet shows you exactly what a healthy nationwide roster looks like.",
          56, y - 29, "Helvetica", 8, W - 112, WHITE, leading=10.5)
    _footer(c, page, total); c.showPage()


def _page_daily(c: Canvas, page, total):
    c.setFillColor(PAPER); c.rect(0, 0, W, H, fill=1, stroke=0)
    _page_head(c, "Section 3", "The Daily Loop — Morning To Night", CORAL)
    _steps(c, H - 104, [
        ("06:00 · Board sweep", "Open Brokerage → AI Hunter. Hit Hunt Now (or leave auto-scan on 45s). Review overnight winners, check the risk registry flags."),
        ("07:00 · Dispatch & check-calls", "Confirm every driver rolling: Live Tracking map + driver console pings. Chase any load without a morning position."),
        ("09:00 · Book the day", "Work the winners queue — pre-matched carriers, margin verified. One click books, generates the rate con, and creates the shipment."),
        ("12:00 · Money block", "Accounting tab: run Auto-Invoice Delivered, review AR aging, fire reminders on watch/escalate accounts, Sync Risk Flags into the Hunter."),
        ("15:00 · Exceptions & triage", "AI Triage Console + Sandbox-style playbooks: breakdowns, weather holds, detention clocks. Execute the AI plan or override."),
        ("17:00 · POD & settle", "Collect PODs (driver photo upload), generate invoices, route factoring. Check Margin-by-Day on Ops KPIs before signing off."),
    ], CORAL)
    _footer(c, page, total); c.showPage()


def _page_hunter(c: Canvas, page, total):
    c.setFillColor(PAPER); c.rect(0, 0, W, H, fill=1, stroke=0)
    _page_head(c, "Section 4", "AI Load Hunter — Your Unfair Advantage", PLUM)
    _steps(c, H - 104, [
        ("Pick your mode", "Balanced (default) · High-Margin (cash-flow builder) · High-Volume (scaling). Each re-weights the 6 scoring components: margin %, shipper reliability, lane profitability, fuel economics, detention risk, driver match."),
        ("Set the guardrails", "Min score (default 70), risk floor (payment score 60), and the margin override — risky shippers only surface when margin justifies it."),
        ("Scan", "Hunt Now sweeps every board in one pass (~20 ms) and surfaces winners with the full score breakdown and a pre-matched carrier."),
        ("Book or auto-book", "One-click book from the queue — or flip Auto-Book with a $ cap, score floor, and daily max. The AI books clean freight while you sleep."),
        ("Audit everything", "Every surface, risk-reject, and auto-book decision is logged with its score breakdown. Compliance guardrail: business metrics only, never protected characteristics."),
    ], PLUM)
    _footer(c, page, total); c.showPage()


def _page_money(c: Canvas, page, total):
    c.setFillColor(PAPER); c.rect(0, 0, W, H, fill=1, stroke=0)
    _page_head(c, "Section 5", "Docs & Money — BOL To Bank", FOREST)
    _steps(c, H - 104, [
        ("Rate con", "Generated at booking with all accessorials itemized. E-sign or verbal + email confirm."),
        ("BOL", "One click on the booking → branded Bill of Lading PDF, stamped with the BOL#. Driver carries it digital or paper."),
        ("POD", "Driver photographs the signed BOL from the cab → POD PDF with photos attached. This is the payment trigger."),
        ("Invoice", "AR Engine auto-invoices every delivered load (line items + FSC breakout, terms from the customer record). Manual invoices any time from Accounting."),
        ("Factoring", "Route the invoice to the best factor: 85% advance, ~3.75% fee, reserve released when the shipper pays. Cash Flow HUD tracks every dollar."),
        ("AR & collections", "Aging buckets (30/60/90+), dunning reminders, mark-paid, and Sync Risk Flags — chronic slow-payers get auto-rejected by the Hunter."),
    ], FOREST)
    _footer(c, page, total); c.showPage()


def _page_sandbox(c: Canvas, page, total):
    c.setFillColor(PAPER); c.rect(0, 0, W, H, fill=1, stroke=0)
    _page_head(c, "Section 6", "Operation Sandbox — Run A Full Sample Week", AZURE)
    y = _steps(c, H - 104, [
        ("Launch", "Sidebar → Operation Sandbox. Set week length (7 days), loads/day, and time compression (default: 1 sim day ≈ 2 real minutes). Flip AI Autopilot + AI Triage on. Hit LAUNCH."),
        ("Watch the AI work", "36 sample carriers staged nationwide with current FSC (DOE $3.68/gal → $0.41/mi). The AI matches, books, and dispatches every load — rate cons, BOLs, GPS movement on the live map."),
        ("Handle exceptions", "Breakdowns, weather holds, and detention fire realistically. AI Triage resolves them automatically — or execute the plan yourself from the queue."),
        ("Follow the money", "Delivery → POD → auto-invoice → factoring advance (85%) → shipper payment at compressed net terms. Revenue, margin, cash, and AR update live on the scoreboard."),
        ("Read the scorecard", "Margin-by-day chart, carrier leaderboard, on-time %, and the full ops feed. Open any load's BOL/POD PDFs — they're real documents from the real generators."),
        ("Reset clean", "Every record is marked SAMPLE. One click purges all sandbox loads, bookings, shipments, and invoices — production data untouched."),
    ], AZURE)
    _card(c, 40, y - 46, W - 80, 44, colors.HexColor("#123C22"), radius=8)
    c.setFont("Helvetica-Bold", 9); c.setFillColor(colors.HexColor("#9BE8B4"))
    c.drawString(56, y - 18, "WHY IT MATTERS")
    _para(c, "The Sandbox is a dress rehearsal for opening day: prove the machine end-to-end, train on triage, and see a week's P&L before a single real dollar moves.",
          56, y - 30, "Helvetica", 8, W - 112, WHITE, leading=10.5)
    _footer(c, page, total); c.showPage()


def build_platform_manual_pdf() -> bytes:
    buf = io.BytesIO()
    c = Canvas(buf, pagesize=letter)
    c.setTitle("Orisei Command Deck · Field Manual")
    total = 7
    _cover(c)
    _page_map(c, 2, total)
    _page_carrier(c, 3, total)
    _page_daily(c, 4, total)
    _page_hunter(c, 5, total)
    _page_money(c, 6, total)
    _page_sandbox(c, 7, total)
    c.save()
    return buf.getvalue()
