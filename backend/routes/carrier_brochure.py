"""routes.carrier_brochure — Colorful carrier-facing PDF brochure.

Explains the Orisei brokerage platform's capabilities to prospective carrier
partners: why haul for Orisei, the tech they get for free, how onboarding and
systems integration work, the load lifecycle, and how they get paid.
Reuses the brochure drawing helpers from plan_brochure.
"""
from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import List, Tuple

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen.canvas import Canvas

from .orisei_docs import LOGO_PATH
from .plan_brochure import (
    AZURE, AZURE_DEEP, CORAL, FOREST, GOLD, GOLD_LIGHT, INK, PAPER, PLUM,
    SLATE, TEAL, WHITE, _card, _page_head, _para, _stat_card, _wrap,
)

W, H = letter


def _footer(c: Canvas, page: int, total: int):
    c.setFillColor(GOLD)
    c.rect(0, 26, W, 2.5, fill=1, stroke=0)
    c.setFont("Helvetica", 7)
    c.setFillColor(SLATE)
    c.drawString(40, 14, "Orisei Freight Solutions LLC · Carrier Partner Program · Minneapolis, Minnesota")
    c.drawRightString(W - 40, 14, f"oliver@oriseifreightsolutions.com · (763) 443-4459 · Page {page} of {total}")


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
    c.drawCentredString(W / 2, H - 296, "HAUL WITH ORISEI")
    c.setFillColor(GOLD)
    c.rect(W / 2 - 110, H - 316, 220, 3, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 14)
    c.setFillColor(GOLD_LIGHT)
    c.drawCentredString(W / 2, H - 340, "CARRIER PARTNER PROGRAM · 2026")
    c.setFont("Helvetica", 11)
    c.setFillColor(WHITE)
    c.drawCentredString(W / 2, H - 366, "Real freight · Fast pay · Free technology · A dispatcher who answers")

    _card(c, 60, 180, W - 120, 132, colors.HexColor("#0B2E55"), stroke=GOLD, radius=12)
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(GOLD)
    c.drawCentredString(W / 2, 288, "OUR PROMISE TO EVERY CARRIER")
    for i, (t, col) in enumerate([
            ("No double-brokering. Ever. Every load is our direct shipper freight.", TEAL),
            ("Quick-pay available on every load — get paid in days, not weeks.", GOLD),
            ("Fair detention, honored on the first invoice. No fights.", CORAL),
            ("24/7 dispatch escalation to a named human — never a ticket queue.", FOREST)]):
        y = 266 - i * 20
        c.setFillColor(col)
        c.circle(84, y + 3, 3, fill=1, stroke=0)
        c.setFont("Helvetica", 9.5)
        c.setFillColor(WHITE)
        c.drawString(96, y, t)
    c.setFont("Helvetica", 8.5)
    c.setFillColor(colors.HexColor("#7E96B8"))
    c.drawCentredString(W / 2, 120, "oliver@oriseifreightsolutions.com  ·  (763) 443-4459  ·  oriseifreight.com/carriers")
    c.drawCentredString(W / 2, 106, f"MC pending activation · BMC-84 $75,000 bond · Prepared {datetime.now(timezone.utc).strftime('%B %Y')}")
    c.showPage()


def _page_why(c: Canvas, page: int, total: int):
    c.setFillColor(PAPER)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    _page_head(c, "Why Carriers Choose Orisei", "Built By Operators, Not Call Centers", TEAL)
    y = H - 120
    stats: List[Tuple[str, str, object]] = [
        ("48h", "Quick-pay turnaround option", GOLD),
        ("<30min", "Carrier setup & vetting decision", TEAL),
        ("$0", "Cost to use our carrier tech", FOREST),
        ("24/7", "Live dispatch escalation line", CORAL),
        ("100%", "Direct shipper freight — no re-brokering", PLUM),
        ("1 hr", "Detention clock honored from appt", AZURE),
    ]
    cw, ch, gap = (W - 80 - 2 * 14) / 3, 78, 14
    for i, (v, l, col) in enumerate(stats):
        row, coln = divmod(i, 3)
        _stat_card(c, 40 + coln * (cw + gap), y - ch - row * (ch + gap), cw, ch, v, l, col)
    y -= 2 * (ch + gap) + 24

    _card(c, 40, y - 130, W - 80, 130, WHITE, stroke=GOLD_LIGHT, radius=10)
    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(AZURE)
    c.drawString(56, y - 26, "WHO WE ARE")
    _para(c, "Orisei Freight Solutions is a Minneapolis-based freight brokerage founded by a "
             "13-year shipper-side logistics operator and a software engineer. We book truckload, "
             "reefer, flatbed, LTL, expedited, and intermodal freight for Minnesota industrials "
             "and national shippers — and we treat carriers as partners in the margin, not a cost "
             "to be squeezed. Our dispatchers have chased midnight recoveries and fought detention "
             "battles from the shipper side. We know what you deal with, because we've caused it "
             "and fixed it.", 56, y - 44, "Helvetica", 9.5, W - 112, INK)
    y -= 154

    _card(c, 40, y - 118, W - 80, 118, AZURE, radius=10)
    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(GOLD)
    c.drawString(56, y - 26, "WHAT THAT MEANS FOR YOUR TRUCKS")
    bullets = [
        "Rate confirmations in minutes with all accessorials spelled out — no surprise deductions.",
        "Lumper and detention pre-approved by phone, paid on the settlement — not 'disputed'.",
        "Consistent reload lanes out of MSP, Chicago, Dallas, and the I-94 corridor.",
        "Your dispatcher talks to a broker who can actually make a decision on the spot.",
    ]
    by = y - 44
    for b in bullets:
        c.setFillColor(GOLD)
        c.circle(62, by + 3, 2.2, fill=1, stroke=0)
        by = _para(c, b, 72, by, "Helvetica", 9, W - 130, WHITE, leading=15.5)
    _footer(c, page, total)
    c.showPage()


def _page_platform(c: Canvas, page: int, total: int):
    c.setFillColor(PAPER)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    _page_head(c, "The Technology", "The Command Deck — Free To Every Carrier", PLUM)
    feats = [
        ("AI Load Matching", TEAL,
         "Our AI Load Hunter scores every load against your equipment, lanes, and history — "
         "you get offered freight that actually fits your trucks, with the rate up front."),
        ("Live Tracking, Zero Hassle", GOLD,
         "Track by ELD integration, a one-tap driver link, or a simple check-call — your choice. "
         "No forced app installs, no per-load fees."),
        ("Digital Docs End-To-End", CORAL,
         "Rate cons e-signed in one tap. BOLs generated for you. PODs photographed from the cab "
         "and attached instantly — which is what releases your payment faster."),
        ("Driver Console", PLUM,
         "A free mobile console for your drivers: load details, addresses, appointment times, "
         "check-in buttons, and POD upload — works in any phone browser."),
        ("Instant Settlement Visibility", FOREST,
         "See exactly what you're owed, what's been factored or quick-paid, and when the money "
         "lands. No calling accounting and waiting on hold."),
        ("Weather & Road Intelligence", AZURE,
         "Live NWS weather alerts and real state-DOT road closure data pushed to dispatch on "
         "every active lane — we reroute with you before the delay, not after."),
    ]
    y = H - 116
    ph = 88
    for i, (title, col, desc) in enumerate(feats):
        row, coln = divmod(i, 2)
        pw = (W - 80 - 14) / 2
        x = 40 + coln * (pw + 14)
        py = y - ph - row * (ph + 12)
        _card(c, x, py, pw, ph, WHITE, stroke=colors.HexColor("#E2E8F0"), radius=8)
        c.setFillColor(col)
        c.rect(x, py, 5, ph, fill=1, stroke=0)
        c.setFont("Helvetica-Bold", 10.5)
        c.setFillColor(col)
        c.drawString(x + 14, py + ph - 18, title.upper())
        _para(c, desc, x + 14, py + ph - 32, "Helvetica", 8, pw - 26, SLATE, leading=11.5)
    y -= 3 * (ph + 12) + 12
    _card(c, 40, y - 44, W - 80, 44, colors.HexColor("#123C22"), radius=8)
    c.setFont("Helvetica-Bold", 9.5)
    c.setFillColor(colors.HexColor("#9BE8B4"))
    c.drawString(56, y - 18, "PROPRIETARY — AND FREE")
    _para(c, "The Command Deck is built and maintained in-house by our founders. There is no seat "
             "fee, no tech charge, and no rate deduction to use it.", 56, y - 30, "Helvetica", 8.5,
          W - 112, WHITE, leading=11.5)
    _footer(c, page, total)
    c.showPage()


def _page_integration(c: Canvas, page: int, total: int):
    c.setFillColor(PAPER)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    _page_head(c, "Systems Integration", "Plug In Your Way — Or Don't Plug In At All", GOLD)
    rows = [
        ("ELD / TELEMATICS", TEAL, "Samsara-class GPS integration",
         "Connect your ELD once and location updates flow automatically — no driver calls, no "
         "texting 'where are you'. Supported out of the box; other providers via secure API token."),
        ("EDI", GOLD, "204 · 990 · 214 · 210 · 856 via SPS Commerce",
         "Running your own TMS? We exchange full EDI load tenders (204), accept/decline (990), "
         "status updates (214), and invoices (210) through SPS Commerce — standards-compliant."),
        ("API + WEBHOOKS", PLUM, "REST endpoints for dispatch systems",
         "Pull your assigned loads, push status updates, and receive webhook notifications on "
         "tender, rate-con, and settlement events. Simple bearer-token auth, JSON payloads."),
        ("NO TECH? NO PROBLEM", CORAL, "Phone · SMS · email workflows",
         "Plenty of great carriers run on a phone and a clipboard. Every digital step has a "
         "human fallback: verbal rate cons confirmed by email, SMS tracking links, emailed PODs."),
    ]
    y = H - 116
    ph = 92
    for title, col, sub, desc in rows:
        _card(c, 40, y - ph, W - 80, ph, WHITE, stroke=colors.HexColor("#E2E8F0"), radius=8)
        c.setFillColor(col)
        c.rect(40, y - ph, 5, ph, fill=1, stroke=0)
        c.setFont("Helvetica-Bold", 11)
        c.setFillColor(col)
        c.drawString(56, y - 20, title)
        c.setFont("Helvetica-Bold", 8.5)
        c.setFillColor(INK)
        c.drawString(56, y - 34, sub)
        _para(c, desc, 56, y - 48, "Helvetica", 8.5, W - 130, SLATE, leading=12)
        y -= ph + 12
    _card(c, 40, y - 58, W - 80, 54, AZURE, radius=8)
    c.setFont("Helvetica-Bold", 9.5)
    c.setFillColor(GOLD)
    c.drawString(56, y - 22, "ONBOARDING IN UNDER 24 BUSINESS HOURS")
    _para(c, "Send your MC#, W-9, and COI ($1M auto / $100K cargo). We run FMCSA SAFER + "
             "Carrier411 vetting in under 30 minutes, DocuSign the carrier packet, and your first "
             "load offer can arrive the same day.", 56, y - 34, "Helvetica", 8.5, W - 112, WHITE,
          leading=11.5)
    _footer(c, page, total)
    c.showPage()


def _page_lifecycle(c: Canvas, page: int, total: int):
    c.setFillColor(PAPER)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    _page_head(c, "How A Load Flows", "From Offer To Money In The Bank", CORAL)
    phases = [
        ("MATCH", TEAL, "Our AI matches the load to your trucks — equipment, lane, weight, and your preferences — before a human even calls."),
        ("OFFER", GOLD, "You get the full picture up front: rate, miles, appointment windows, commodity, accessorials. Accept by tap, text, or phone."),
        ("RATE CON", PLUM, "E-signed rate confirmation in minutes with every charge itemized. Verbal + email fallback if you prefer paper."),
        ("DISPATCH & TRACK", AZURE, "Driver gets a console link with addresses and check-in buttons. Tracking runs off your ELD or a one-tap ping — your call."),
        ("POD", CORAL, "Driver photographs the signed BOL from the cab. The POD lands in our system instantly — no scanning at a truck stop."),
        ("GET PAID", FOREST, "Standard terms, quick-pay in ~48 hours, or factor-direct with NOA honored same day. Settlement visible in real time."),
    ]
    y = H - 110
    rail_x = 88
    c.setFillColor(colors.HexColor("#D9D2BE"))
    c.rect(rail_x - 1.5, 120, 3, y - 120, fill=1, stroke=0)
    step_h = (y - 132) / len(phases)
    for i, (title, col, desc) in enumerate(phases):
        cy = y - i * step_h - 12
        c.setFillColor(col)
        c.circle(rail_x, cy, 7, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 7)
        c.drawCentredString(rail_x, cy - 2.3, str(i + 1))
        _card(c, rail_x + 22, cy - step_h + 24, W - rail_x - 62, step_h - 12, WHITE,
              stroke=colors.HexColor("#E2E8F0"), radius=8)
        c.setFillColor(col)
        c.rect(rail_x + 22, cy - step_h + 24, 5, step_h - 12, fill=1, stroke=0)
        c.setFont("Helvetica-Bold", 11.5)
        c.setFillColor(col)
        c.drawString(rail_x + 38, cy - 8, title)
        _para(c, desc, rail_x + 38, cy - 23, "Helvetica", 8.5, W - rail_x - 110, SLATE, leading=12)
    _footer(c, page, total)
    c.showPage()


def _page_pay(c: Canvas, page: int, total: int):
    c.setFillColor(PAPER)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    _page_head(c, "Getting Paid", "Pick The Terms That Fit Your Cash Flow", FOREST)
    y = H - 116
    opts = [
        ("QUICK-PAY", GOLD, "~48 hours", "Small percentage fee",
         "POD in, money out. Best for owner-operators managing tight fuel cycles."),
        ("STANDARD", TEAL, "Net 30", "No fee — 100% of the rate",
         "Full rate, predictable schedule, settlement visibility the whole way."),
        ("FACTOR-DIRECT", PLUM, "Your factor's schedule", "NOA honored same day",
         "We pay your factoring company directly and confirm the NOA on file at setup."),
    ]
    cw = (W - 80 - 2 * 14) / 3
    ch = 130
    for i, (title, col, speed, fee, desc) in enumerate(opts):
        x = 40 + i * (cw + 14)
        _card(c, x, y - ch, cw, ch, WHITE, stroke=colors.HexColor("#E2E8F0"), radius=10)
        c.setFillColor(col)
        c.roundRect(x, y - 34, cw, 34, 10, fill=1, stroke=0)
        c.rect(x, y - 34, cw, 12, fill=1, stroke=0)
        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(WHITE)
        c.drawCentredString(x + cw / 2, y - 24, title)
        c.setFont("Helvetica-Bold", 15)
        c.setFillColor(col)
        c.drawCentredString(x + cw / 2, y - 56, speed)
        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(INK)
        c.drawCentredString(x + cw / 2, y - 70, fee)
        _para(c, desc, x + 12, y - 86, "Helvetica", 7.8, cw - 24, SLATE, leading=10.5)
    y -= ch + 26

    _card(c, 40, y - 96, W - 80, 96, WHITE, stroke=GOLD_LIGHT, radius=10)
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(AZURE)
    c.drawString(56, y - 22, "WHAT WE NEED FROM YOU")
    items = ["Active MC + DOT authority (90+ days, or references)",
             "COI: $1M auto liability · $100K cargo", "W-9 and signed carrier packet (DocuSign)",
             "NOA from your factor, if factoring", "Dispatcher + after-hours contact",
             "ELD provider name (optional, for auto-tracking)"]
    for i, t in enumerate(items):
        row, coln = divmod(i, 2)
        x = 56 + coln * ((W - 112) / 2)
        iy = y - 40 - row * 16
        c.setFillColor(TEAL)
        c.circle(x + 3, iy + 3, 2.2, fill=1, stroke=0)
        c.setFont("Helvetica", 8.5)
        c.setFillColor(INK)
        c.drawString(x + 12, iy, t)
    y -= 120

    _card(c, 40, y - 84, W - 80, 84, AZURE, radius=10)
    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(GOLD)
    c.drawCentredString(W / 2, y - 26, "READY TO ROLL?")
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(WHITE)
    c.drawCentredString(W / 2, y - 44, "oliver@oriseifreightsolutions.com   ·   (763) 443-4459   ·   oriseifreight.com/carriers")
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.HexColor("#9FB6D4"))
    c.drawCentredString(W / 2, y - 60, "Send your MC# and COI — most carriers are hauling within 24 business hours.")
    _footer(c, page, total)
    c.showPage()


def build_carrier_brochure_pdf() -> bytes:
    buf = io.BytesIO()
    c = Canvas(buf, pagesize=letter)
    c.setTitle("Haul With Orisei · Carrier Partner Program 2026")
    total = 6
    _cover(c)
    _page_why(c, 2, total)
    _page_platform(c, 3, total)
    _page_integration(c, 4, total)
    _page_lifecycle(c, 5, total)
    _page_pay(c, 6, total)
    c.save()
    return buf.getvalue()
