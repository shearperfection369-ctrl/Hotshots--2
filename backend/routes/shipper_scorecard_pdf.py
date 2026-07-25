"""routes.shipper_scorecard_pdf — branded per-account service scorecard PDF
plus the Orisei Service Standard (the 10 things shippers want, codified as SLAs)."""
from __future__ import annotations

import io
from datetime import datetime, timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen.canvas import Canvas

from .orisei_docs import LOGO_PATH
from .plan_brochure import AZURE, AZURE_DEEP, CORAL, FOREST, GOLD, GOLD_LIGHT, INK, PAPER, PLUM, SLATE, TEAL, WHITE, _card, _para

W, H = letter

SERVICE_STANDARD = [
    {"want": "Capacity that shows up", "commitment": "Committed carriers on your recurring lanes from our vetted bench — surge capacity via our owner-operator network.", "target": "98% tender acceptance", "metric": "tender_acceptance"},
    {"want": "On-time, every time", "commitment": "On-time pickup and delivery tracked on every load and published — not hidden — in your quarterly scorecard.", "target": "OTP ≥ 96% · OTD ≥ 95%", "metric": "otp_otd"},
    {"want": "Fast, accurate quotes", "commitment": "Quotes returned in 15 minutes or less, benchmarked against live market data. The quote IS the invoice.", "target": "≤ 15 min quote turnaround", "metric": "quote_speed"},
    {"want": "Proactive communication", "commitment": "We call you before you call us — exception alerts at pickup, in transit, and at delivery, from a named human.", "target": "100% exceptions flagged proactively", "metric": "proactive_comm"},
    {"want": "Real-time visibility", "commitment": "Free Command Deck portal login: live GPS, ETAs, documents. POD lands in your portal within the hour.", "target": "POD ≤ 1 hour post-delivery", "metric": "visibility"},
    {"want": "Honest, stable pricing", "commitment": "90-day fixed pricing on primary lanes, indexed fuel surcharge, zero fee creep, open-book margin at your QBR.", "target": "0 surprise accessorials", "metric": "pricing"},
    {"want": "Painless claims", "commitment": "Claims acknowledged in 24 hours, resolved target 30 days, backed by contingent cargo cover and a funded reserve.", "target": "Ack ≤ 24h · resolve ≤ 30 days", "metric": "claims"},
    {"want": "Billing accuracy", "commitment": "Invoice matches quote line for line. Net-30 respected. Disputes answered in one business day.", "target": "≥ 99% invoice accuracy", "metric": "billing"},
    {"want": "Compliance & stability", "commitment": "FMCSA authority, BMC-84 $75K bond, every carrier vetted for safety, authority and insurance. No double-brokering — in writing.", "target": "100% vetted carriers", "metric": "compliance"},
    {"want": "A named human, always", "commitment": "Dedicated account manager, the founder's cell on every rate con, 24/7 escalation — never a ticket queue.", "target": "24/7 human escalation", "metric": "human"},
]


def _usd(n) -> str:
    return f"${n:,.0f}" if n is not None else "—"


def build_scorecard_pdf(acc: dict, qbrs: list) -> bytes:
    buf = io.BytesIO()
    c = Canvas(buf, pagesize=letter)
    c.setTitle(f"Orisei Service Scorecard · {acc.get('company_name', '')}")
    latest = qbrs[0] if qbrs else {}

    c.setFillColor(PAPER)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setFillColor(AZURE)
    c.rect(0, H - 100, W, 100, fill=1, stroke=0)
    c.setFillColor(GOLD)
    c.rect(0, H - 106, W, 6, fill=1, stroke=0)
    try:
        c.drawImage(str(LOGO_PATH), 40, H - 88, width=58, height=58, preserveAspectRatio=True, mask="auto")
    except Exception:
        pass
    c.setFont("Helvetica-Bold", 20)
    c.setFillColor(WHITE)
    c.drawString(112, H - 52, "SERVICE SCORECARD")
    c.setFont("Helvetica", 8.5)
    c.setFillColor(GOLD_LIGHT)
    c.drawString(112, H - 68, "Orisei Freight Solutions LLC · performance we publish, not promise")
    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(GOLD)
    c.drawRightString(W - 40, H - 48, acc.get("company_name", ""))
    c.setFont("Helvetica", 8.5)
    c.setFillColor(WHITE)
    c.drawRightString(W - 40, H - 64, f"Period: {latest.get('period', 'No QBR recorded yet')}")
    c.drawRightString(W - 40, H - 78, f"Generated {datetime.now(timezone.utc).date().isoformat()}")

    # Metric cards
    metrics = [
        ("ON-TIME PICKUP", latest.get("otp_pct"), "%", "target ≥ 96%", TEAL),
        ("ON-TIME DELIVERY", latest.get("otd_pct"), "%", "target ≥ 95%", FOREST),
        ("DAMAGE-FREE", latest.get("damage_free_pct"), "%", "target ≥ 99%", GOLD),
        ("NPS", latest.get("nps_score"), "", "target ≥ 60", PLUM),
        ("LOADS (PERIOD)", latest.get("volume_loads"), "", "", AZURE),
        ("REVENUE (PERIOD)", latest.get("revenue_usd"), "$", "", CORAL),
    ]
    y0 = H - 128
    cw = (W - 100) / 3
    for i, (label, val, unit, tgt, accent) in enumerate(metrics):
        x = 40 + (i % 3) * (cw + 10)
        y = y0 - (i // 3) * 78
        _card(c, x, y - 68, cw, 68, WHITE, stroke=colors.HexColor("#E2D9C3"), radius=10)
        c.setFillColor(accent)
        c.rect(x, y - 68, 5, 68, fill=1, stroke=0)
        c.setFont("Helvetica-Bold", 7.5)
        c.setFillColor(SLATE)
        c.drawString(x + 14, y - 16, label)
        c.setFont("Helvetica-Bold", 19)
        c.setFillColor(AZURE)
        if val is None:
            disp = "—"
        elif unit == "$":
            disp = _usd(val)
        else:
            disp = f"{val:g}{unit}"
        c.drawString(x + 14, y - 40, disp)
        if tgt:
            c.setFont("Helvetica", 7.5)
            c.setFillColor(SLATE)
            c.drawString(x + 14, y - 56, tgt)

    # QBR history
    ty = y0 - 176
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(AZURE)
    c.drawString(40, ty, "QBR HISTORY")
    ty -= 8
    c.setFillColor(AZURE)
    c.roundRect(40, ty - 18, W - 80, 18, 4, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 7.5)
    c.setFillColor(WHITE)
    for x, htxt in [(46, "PERIOD"), (150, "OTP"), (205, "OTD"), (260, "DMG-FREE"), (330, "NPS"), (380, "LOADS"), (445, "REVENUE")]:
        c.drawString(x, ty - 13, htxt)
    ty -= 18
    c.setFont("Helvetica", 8)
    if not qbrs:
        c.setFillColor(SLATE)
        c.drawString(46, ty - 13, "No QBRs recorded yet — first review scheduled at end of launch quarter.")
        ty -= 20
    for q in qbrs[:6]:
        c.setFillColor(INK)
        c.drawString(46, ty - 13, str(q.get("period", ""))[:18])
        for x, k, u in [(150, "otp_pct", "%"), (205, "otd_pct", "%"), (260, "damage_free_pct", "%"), (330, "nps_score", ""), (380, "volume_loads", "")]:
            v = q.get(k)
            c.drawString(x, ty - 13, f"{v:g}{u}" if isinstance(v, (int, float)) else "—")
        rv = q.get("revenue_usd")
        c.drawString(445, ty - 13, _usd(rv) if isinstance(rv, (int, float)) else "—")
        ty -= 17

    # Action items
    items = latest.get("action_items") or []
    if items:
        ty -= 10
        c.setFont("Helvetica-Bold", 10)
        c.setFillColor(AZURE)
        c.drawString(40, ty, "OPEN ACTION ITEMS")
        ty -= 16
        c.setFont("Helvetica", 8.5)
        for it in items[:5]:
            c.setFillColor(GOLD)
            c.circle(46, ty + 3, 2.5, fill=1, stroke=0)
            c.setFillColor(INK)
            c.drawString(56, ty, str(it)[:110])
            ty -= 14

    # Service standard strip
    _card(c, 40, 64, W - 80, 96, AZURE_DEEP, stroke=GOLD, radius=10)
    c.setFont("Helvetica-Bold", 8.5)
    c.setFillColor(GOLD)
    c.drawString(54, 140, "MEASURED AGAINST THE ORISEI SERVICE STANDARD")
    _para(c, "98% tender acceptance · OTP ≥96% / OTD ≥95% · quotes ≤15 min · proactive exception alerts · "
             "POD ≤1 hr · zero fee creep · claims acknowledged ≤24 h · ≥99% invoice accuracy · 100% vetted "
             "carriers, no double-brokering · dedicated account manager with 24/7 human escalation.",
          54, 126, "Helvetica", 8.2, W - 108, WHITE, leading=12)

    c.setFillColor(GOLD)
    c.rect(0, 26, W, 2.5, fill=1, stroke=0)
    c.setFont("Helvetica", 7)
    c.setFillColor(SLATE)
    c.drawString(40, 14, "Orisei Freight Solutions LLC · oliver@oriseifreightsolutions.com · (612) 555-0117")
    c.drawRightString(W - 40, 14, f"Service Scorecard · {acc.get('account_id', '')}")
    c.save()
    return buf.getvalue()
