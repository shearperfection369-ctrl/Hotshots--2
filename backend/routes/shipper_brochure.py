"""routes.shipper_brochure — Colorful shipper-facing PDF brochure.

The "woo packet": why ship with Orisei, the offer stack, the platform,
and 24-hour onboarding. Reuses drawing helpers from plan_brochure.
"""
from __future__ import annotations

import io
from typing import List, Tuple

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
    c.drawString(40, 14, "Orisei Freight Solutions LLC · Ship With Orisei · Minneapolis, Minnesota")
    c.drawRightString(W - 40, 14, f"oliver@oriseifreightsolutions.com · (612) 555-0117 · Page {page} of {total}")


def _cover(c: Canvas):
    c.setFillColor(AZURE_DEEP)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setFillColor(AZURE)
    c.rect(0, H * 0.40, W, H * 0.60, fill=1, stroke=0)
    c.setFillColor(GOLD)
    c.saveState()
    c.translate(0, H * 0.40)
    p = c.beginPath()
    p.moveTo(0, -14); p.lineTo(W, 22); p.lineTo(W, 8); p.lineTo(0, -28); p.close()
    c.drawPath(p, fill=1, stroke=0)
    c.restoreState()
    for i, col in enumerate([TEAL, CORAL, GOLD, PLUM, FOREST]):
        c.setFillColor(col)
        c.rect(40 + i * 26, H - 52, 18, 8, fill=1, stroke=0)
    try:
        c.drawImage(str(LOGO_PATH), W / 2 - 52, H - 240, width=104, height=104,
                    preserveAspectRatio=True, mask="auto")
    except Exception:
        pass
    c.setFont("Helvetica-Bold", 31)
    c.setFillColor(WHITE)
    c.drawCentredString(W / 2, H - 296, "SHIP WITH ORISEI")
    c.setFillColor(GOLD)
    c.rect(W / 2 - 110, H - 316, 220, 3, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 14)
    c.setFillColor(GOLD_LIGHT)
    c.drawCentredString(W / 2, H - 340, "SHIPPER PARTNER PROGRAM · 2026")
    c.setFont("Helvetica", 11)
    c.setFillColor(WHITE)
    c.drawCentredString(W / 2, H - 366, "Operator-built brokerage · Live tracking · Open-book margin · Answers the phone")

    _card(c, 60, 168, W - 120, 148, colors.HexColor("#0B2E55"), stroke=GOLD, radius=12)
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(GOLD)
    c.drawCentredString(W / 2, 292, "OUR PROMISE TO EVERY SHIPPER")
    for i, (t, col) in enumerate([
            ("No double-brokering. Every load rides on a carrier we vetted ourselves.", TEAL),
            ("Quote in under 15 minutes. The quote IS the invoice — zero fee creep.", GOLD),
            ("Live GPS tracking + proactive ETA updates on a free portal login.", CORAL),
            ("Open-book margin at your quarterly business review.", PLUM),
            ("A founder's cell number on every rate con — 24/7 human escalation.", FOREST)]):
        y = 268 - i * 20
        c.setFillColor(col)
        c.circle(84, y + 3, 3, fill=1, stroke=0)
        c.setFont("Helvetica", 9.5)
        c.setFillColor(WHITE)
        c.drawString(96, y, t)
    _footer(c, 1, 6)
    c.showPage()


def _page_why(c: Canvas, page: int, total: int):
    c.setFillColor(PAPER)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    _page_head(c, "Why Orisei", "Three Founders. Every Side of Your Freight.", TEAL)
    items: List[Tuple[str, str, object]] = [
        ("13 YEARS ON YOUR SIDE OF THE DOCK", "Principal broker Oliver Cummins spent 13 years tendering, tracking and auditing freight for major Minnesota industrials. He has sat in your chair — and built the desk he wished his brokers had.", TEAL),
        ("12 YEARS BEHIND THE WHEEL", "Co-founder Doug Graham is a CDL owner-operator with 12 years OTR. He vets every carrier with a driver's eye: equipment, maintenance, HOS reality. Trucks that show up.", CORAL),
        ("IN-HOUSE TECHNOLOGY", "Co-founder Daniel W. Karsor engineered the Orisei Command Deck — live tracking, instant docs, lane analytics. Mega-broker technology, boutique-desk service. You get portal access free.", PLUM),
        ("SURGE CAPACITY OTHERS CAN'T TAP", "Our Brooklyn Park owner-operator network gives Orisei committed trucks when the spot market tightens — capacity your incumbent can't call.", FOREST),
        ("SMALL BOOK, BIG ATTENTION", "We cap our account list so every shipper is a top account. No junior-rep churn, no ticket queues, no 'your rep changed again' emails.", GOLD),
    ]
    y = H - 116
    for title, body, accent in items:
        _card(c, 40, y - 96, W - 80, 100, WHITE, stroke=colors.HexColor("#E2D9C3"), radius=10)
        c.setFillColor(accent)
        c.rect(40, y - 96, 6, 100, fill=1, stroke=0)
        c.setFont("Helvetica-Bold", 10.5)
        c.setFillColor(AZURE)
        c.drawString(60, y - 18, title)
        _para(c, body, 60, y - 36, "Helvetica", 9.2, W - 130, INK, leading=12.5)
        y -= 112
    _footer(c, page, total)
    c.showPage()


def _page_offer(c: Canvas, page: int, total: int):
    c.setFillColor(PAPER)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    _page_head(c, "The Offer", "What You Get When You Contract With Orisei", GOLD)
    offers = [
        ("FIXED-RATE TRIAL", "4 loads on one lane at a locked rate — money-back margin guarantee if we miss a window.", TEAL),
        ("FREE LANE BENCHMARK", "Your top 3 lanes quoted against DAT market data in 24 hours, our margin disclosed.", CORAL),
        ("24-HOUR ONBOARDING", "Agreement, COI, W-9 and portal login returned within one business day.", PLUM),
        ("90-DAY FIXED PRICING", "Rate stability on primary lanes that spot brokers won't offer.", FOREST),
        ("DEDICATED CAPACITY", "Named carriers committed to your recurring lanes from our vetted bench.", AZURE),
        ("DETENTION ADVOCACY", "Honest detention pass-through — which is why drivers prioritize our freight.", GOLD),
        ("ZERO FEE CREEP", "Net-30 respected. No fuel-surcharge games, no surprise accessorials. Quote = invoice.", TEAL),
        ("QUARTERLY BUSINESS REVIEW", "Lane analytics, on-time scorecard, market forecast, open-book margin. Free.", CORAL),
    ]
    y = H - 116
    col_w = (W - 100) / 2
    for i, (title, body, accent) in enumerate(offers):
        x = 40 + (i % 2) * (col_w + 20)
        yy = y - (i // 2) * 118
        _card(c, x, yy - 100, col_w, 104, WHITE, stroke=colors.HexColor("#E2D9C3"), radius=10)
        c.setFillColor(accent)
        c.roundRect(x + 14, yy - 22, 10, 10, 2, fill=1, stroke=0)
        c.setFont("Helvetica-Bold", 9.5)
        c.setFillColor(AZURE)
        c.drawString(x + 32, yy - 21, title)
        _para(c, body, x + 14, yy - 40, "Helvetica", 8.8, col_w - 28, INK, leading=11.8)
    _card(c, 40, 64, W - 80, 54, AZURE, radius=10)
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(GOLD_LIGHT)
    c.drawString(56, 96, "THE ORISEI GUARANTEE")
    c.setFont("Helvetica", 9)
    c.setFillColor(WHITE)
    c.drawString(56, 80, "Miss a pickup or delivery window on your trial lane and the margin on that load is refunded. In writing.")
    _footer(c, page, total)
    c.showPage()


def _page_platform(c: Canvas, page: int, total: int):
    c.setFillColor(PAPER)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    _page_head(c, "The Platform", "Your Freight on the Orisei Command Deck", PLUM)
    feats = [
        ("LIVE TRACKING", "GPS position + proactive ETA updates on every load. No more 'where's my truck?' calls — you already know.", TEAL),
        ("INSTANT DOCUMENTS", "PODs land in your portal within the hour of delivery. Rate cons, invoices and BOLs in one place, forever searchable.", CORAL),
        ("LANE ANALYTICS", "Your lanes benchmarked against live market data every quarter — know when to lock rates and when to float.", FOREST),
        ("CARRIER VETTING TRANSPARENCY", "See the safety score, authority status and insurance of every carrier that touches your freight.", GOLD),
        ("ONE-CLICK TENDERING", "Email, EDI or portal — tender the way your team already works. We adapt to your workflow, not the reverse.", PLUM),
    ]
    y = H - 116
    for title, body, accent in feats:
        _card(c, 40, y - 88, W - 80, 92, WHITE, stroke=colors.HexColor("#E2D9C3"), radius=10)
        c.setFillColor(accent)
        c.circle(62, y - 40, 9, fill=1, stroke=0)
        c.setFont("Helvetica-Bold", 10.5)
        c.setFillColor(AZURE)
        c.drawString(84, y - 20, title)
        _para(c, body, 84, y - 38, "Helvetica", 9.2, W - 160, INK, leading=12.5)
        y -= 104
    _footer(c, page, total)
    c.showPage()


def _page_onboarding(c: Canvas, page: int, total: int):
    c.setFillColor(PAPER)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    _page_head(c, "Getting Started", "Onboarded in 24 Business Hours", FOREST)
    steps = [
        ("1", "DISCOVERY CALL — 15 MIN", "Your top 3 lanes, weekly volume, and what your current broker gets wrong.", TEAL),
        ("2", "LANE BENCHMARK — 24 HR", "We return a written quote on your lanes against DAT market data, margin disclosed.", CORAL),
        ("3", "PAPERWORK — SAME DAY", "Broker-shipper agreement, COI, W-9, portal credentials. One business day, done.", PLUM),
        ("4", "TRIAL LANE — WEEK 1", "4 loads, fixed rate, margin-back guarantee. We earn the routing-guide slot.", GOLD),
        ("5", "SCALE — QUARTER 1", "Add lanes as we prove out. QBR #1 books your Q2 capacity before the market moves.", FOREST),
    ]
    y = H - 124
    for num, title, body, accent in steps:
        _card(c, 40, y - 82, W - 80, 86, WHITE, stroke=colors.HexColor("#E2D9C3"), radius=10)
        c.setFillColor(accent)
        c.circle(66, y - 38, 15, fill=1, stroke=0)
        c.setFont("Helvetica-Bold", 13)
        c.setFillColor(WHITE)
        c.drawCentredString(66, y - 43, num)
        c.setFont("Helvetica-Bold", 10.5)
        c.setFillColor(AZURE)
        c.drawString(94, y - 22, title)
        _para(c, body, 94, y - 40, "Helvetica", 9.2, W - 170, INK, leading=12.5)
        y -= 98
    _footer(c, page, total)
    c.showPage()


def _page_contact(c: Canvas, page: int, total: int):
    c.setFillColor(AZURE_DEEP)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    _page_head(c, "Next Step", "Let's Move Your Freight", GOLD)
    _card(c, 60, H - 400, W - 120, 250, colors.HexColor("#0B2E55"), stroke=GOLD, radius=14)
    c.setFont("Helvetica-Bold", 15)
    c.setFillColor(WHITE)
    c.drawCentredString(W / 2, H - 190, "Take the free lane benchmark.")
    c.setFont("Helvetica", 10.5)
    c.setFillColor(GOLD_LIGHT)
    c.drawCentredString(W / 2, H - 212, "Even if you never tender us a load — know what the market says your lanes are worth.")
    rows = [
        ("Shipper desk", "oliver@oriseifreightsolutions.com"),
        ("Phone (Oliver Cummins, Principal Broker)", "(612) 555-0117"),
        ("Portal", "oriseifreight.com/shippers"),
        ("Headquarters", "Minneapolis - Saint Paul - Brooklyn Park, Minnesota"),
    ]
    y = H - 250
    for label, val in rows:
        c.setFont("Helvetica-Bold", 9)
        c.setFillColor(GOLD)
        c.drawString(96, y, label.upper())
        c.setFont("Helvetica", 11)
        c.setFillColor(WHITE)
        c.drawString(96, y - 15, val)
        y -= 42
    _para(c, "Orisei Freight Solutions LLC · FMCSA property-broker authority · BMC-84 $75,000 surety bond · "
             "Contingent cargo & E&O insured · Member-owned, Minneapolis-built.",
          96, H - 440, "Helvetica", 8.5, W - 192, GOLD_LIGHT, leading=12)
    _footer(c, page, total)
    c.showPage()


def _page_service_standard(c: Canvas, page: int, total: int):
    from .shipper_scorecard_pdf import SERVICE_STANDARD
    c.setFillColor(PAPER)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    _page_head(c, "The Service Standard", "Ten Commitments. Measured. Published.", CORAL)
    accents = [TEAL, CORAL, GOLD, PLUM, FOREST, TEAL, CORAL, GOLD, PLUM, FOREST]
    y = H - 108
    for i, s in enumerate(SERVICE_STANDARD):
        _card(c, 40, y - 54, W - 80, 56, WHITE, stroke=colors.HexColor("#E2D9C3"), radius=8)
        c.setFillColor(accents[i])
        c.rect(40, y - 54, 5, 56, fill=1, stroke=0)
        c.setFont("Helvetica-Bold", 9.5)
        c.setFillColor(AZURE)
        c.drawString(56, y - 15, s["want"].upper())
        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(accents[i])
        c.drawRightString(W - 52, y - 15, s["target"])
        _para(c, s["commitment"], 56, y - 30, "Helvetica", 8, W - 120, INK, leading=10.5)
        y -= 62
    _footer(c, page, total)
    c.showPage()


def build_shipper_brochure_pdf() -> bytes:
    buf = io.BytesIO()
    c = Canvas(buf, pagesize=letter)
    c.setTitle("Ship With Orisei · Shipper Partner Program 2026")
    total = 7
    _cover(c)
    _page_why(c, 2, total)
    _page_offer(c, 3, total)
    _page_service_standard(c, 4, total)
    _page_platform(c, 5, total)
    _page_onboarding(c, 6, total)
    _page_contact(c, 7, total)
    c.save()
    return buf.getvalue()
