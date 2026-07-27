"""routes.quote_pdf — branded one-page freight quote PDF (Orisei blue/gold)."""
from __future__ import annotations

import io
from datetime import datetime, timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen.canvas import Canvas

from .orisei_docs import LOGO_PATH
from .plan_brochure import AZURE, AZURE_DEEP, GOLD, GOLD_LIGHT, INK, PAPER, SLATE, TEAL, WHITE, _card, _para

W, H = letter


def _usd(n) -> str:
    return f"${n:,.2f}" if n is not None else "—"


def build_quote_pdf(q: dict) -> bytes:
    buf = io.BytesIO()
    c = Canvas(buf, pagesize=letter)
    c.setTitle(f"Orisei Freight Quote {q['id']}")

    c.setFillColor(PAPER)
    c.rect(0, 0, W, H, fill=1, stroke=0)

    # Header band
    c.setFillColor(AZURE)
    c.rect(0, H - 110, W, 110, fill=1, stroke=0)
    c.setFillColor(GOLD)
    c.rect(0, H - 116, W, 6, fill=1, stroke=0)
    try:
        c.drawImage(str(LOGO_PATH), 40, H - 96, width=64, height=64, preserveAspectRatio=True, mask="auto")
    except Exception:
        pass
    c.setFont("Helvetica-Bold", 22)
    c.setFillColor(WHITE)
    c.drawString(118, H - 58, "FREIGHT QUOTE")
    c.setFont("Helvetica", 8.5)
    c.setFillColor(GOLD_LIGHT)
    c.drawString(118, H - 76, "Orisei Freight Solutions LLC · Minneapolis, MN · FMCSA broker authority · BMC-84 bonded")
    c.setFont("Helvetica-Bold", 13)
    c.setFillColor(GOLD)
    c.drawRightString(W - 40, H - 44, q["id"])
    c.setFont("Helvetica", 9)
    c.setFillColor(WHITE)
    c.drawRightString(W - 40, H - 76, f"Issued: {q.get('created_at', '')[:10]}")
    c.drawRightString(W - 40, H - 90, f"Valid until: {q.get('valid_until', '—')}")

    # Prepared for / by
    y = H - 140
    _card(c, 40, y - 78, (W - 100) / 2, 78, WHITE, stroke=colors.HexColor("#E2D9C3"), radius=8)
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(SLATE)
    c.drawString(52, y - 16, "PREPARED FOR")
    c.setFont("Helvetica-Bold", 11.5)
    c.setFillColor(AZURE)
    c.drawString(52, y - 32, q.get("shipper", ""))
    c.setFont("Helvetica", 9)
    c.setFillColor(INK)
    c.drawString(52, y - 47, f"{q.get('contact_name', '')}  {q.get('contact_phone', '')}".strip())
    c.drawString(52, y - 60, q.get("contact_email", ""))

    x2 = 40 + (W - 100) / 2 + 20
    _card(c, x2, y - 78, (W - 100) / 2, 78, WHITE, stroke=colors.HexColor("#E2D9C3"), radius=8)
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(SLATE)
    c.drawString(x2 + 12, y - 16, "PREPARED BY")
    c.setFont("Helvetica-Bold", 11.5)
    c.setFillColor(AZURE)
    c.drawString(x2 + 12, y - 32, "Oliver Cummins · Principal Broker")
    c.setFont("Helvetica", 9)
    c.setFillColor(INK)
    c.drawString(x2 + 12, y - 47, "oliver@oriseifreightsolutions.com")
    c.drawString(x2 + 12, y - 60, "(763) 443-4459 · oriseifreight.com")

    # Lane table
    ty = y - 104
    cols = [40, 62, 200, 246, 288, 396, 452, 492, W - 40]
    heads = ["#", "Lane", "Equip", "Miles", "Market ref*", "Orisei rate", "FSC", "Line total"]
    c.setFillColor(AZURE)
    c.roundRect(40, ty - 22, W - 80, 22, 5, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(WHITE)
    for i, htxt in enumerate(heads):
        if i in (0, 1, 2):
            c.drawString(cols[i] + 6, ty - 15, htxt)
        else:
            c.drawRightString(cols[i + 1] - 6, ty - 15, htxt)
    ty -= 22
    c.setFont("Helvetica", 8.5)
    for idx, ln in enumerate(q.get("lines", []), start=1):
        row_h = 26
        if idx % 2 == 0:
            c.setFillColor(colors.HexColor("#F3EEDF"))
            c.rect(40, ty - row_h, W - 80, row_h, fill=1, stroke=0)
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", 8.5)
        c.drawString(cols[0] + 6, ty - 12, str(idx))
        c.drawString(cols[1] + 6, ty - 12, f"{ln['origin']} → {ln['destination']}"[:34])
        c.setFont("Helvetica", 8.5)
        if ln.get("notes"):
            c.setFillColor(SLATE)
            c.setFont("Helvetica", 7)
            c.drawString(cols[1] + 6, ty - 21, ln["notes"][:48])
            c.setFont("Helvetica", 8.5)
            c.setFillColor(INK)
        c.drawString(cols[2] + 6, ty - 12, str(ln.get("equipment", ""))[:9])
        c.drawRightString(cols[4] - 6, ty - 12, f"{ln.get('miles', 0):,}")
        c.setFillColor(SLATE)
        mt = ln.get("market_total")
        c.setFont("Helvetica", 7.5)
        c.drawRightString(cols[5] - 6, ty - 12, f"{_usd(mt)} ({_usd(ln.get('market_per_mile'))}/mi)" if mt else "—")
        c.setFont("Helvetica", 8.5)
        c.setFillColor(INK)
        c.drawRightString(cols[6] - 6, ty - 12, _usd(ln.get("rate_usd")))
        c.drawRightString(cols[7] - 6, ty - 12, f"{ln.get('fuel_pct', 0):g}%")
        c.setFont("Helvetica-Bold", 8.5)
        c.drawRightString(cols[8] - 6, ty - 12, _usd(ln.get("line_total")))
        c.setFont("Helvetica", 8.5)
        ty -= row_h

    # Totals
    ty -= 12
    _card(c, W - 260, ty - 66, 220, 66, AZURE_DEEP, stroke=GOLD, radius=8)
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(GOLD_LIGHT)
    c.drawString(W - 246, ty - 18, "QUOTE TOTAL (all-in)")
    c.setFont("Helvetica-Bold", 17)
    c.setFillColor(WHITE)
    c.drawString(W - 246, ty - 38, _usd(q.get("total_usd")))
    vs = q.get("vs_market_usd")
    if vs is not None and q.get("market_total_usd"):
        c.setFont("Helvetica", 8)
        c.setFillColor(GOLD if vs >= 0 else GOLD_LIGHT)
        label = f"{_usd(abs(vs))} under market reference" if vs >= 0 else f"{_usd(abs(vs))} over market reference"
        c.drawString(W - 246, ty - 54, label)

    if q.get("notes"):
        _para(c, f"Notes: {q['notes']}", 40, ty - 20, "Helvetica", 8.5, W - 320, INK, leading=11.5)

    # Terms
    _card(c, 40, 66, W - 80, 74, WHITE, stroke=colors.HexColor("#E2D9C3"), radius=8)
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(TEAL)
    c.drawString(52, 122, "TERMS & THE ORISEI PLEDGE")
    _para(c, f"Rates valid through {q.get('valid_until', '—')} and include linehaul + listed fuel surcharge + listed accessorials. "
             "Net-30 from clean POD; zero fee creep — the quote is the invoice. Every load moves on a directly vetted "
             "Orisei carrier — no double-brokering, ever. Live GPS tracking and hourly-POD portal access included free. "
             "*Market ref: blended spot-market benchmark for the lane/equipment, informational only.",
          52, 110, "Helvetica", 7.8, W - 104, INK, leading=10.5)

    c.setFillColor(GOLD)
    c.rect(0, 26, W, 2.5, fill=1, stroke=0)
    c.setFont("Helvetica", 7)
    c.setFillColor(SLATE)
    c.drawString(40, 14, "Orisei Freight Solutions LLC · oliver@oriseifreightsolutions.com · (763) 443-4459")
    c.drawRightString(W - 40, 14, f"Freight Quote {q['id']} · generated {datetime.now(timezone.utc).date().isoformat()}")

    c.save()
    return buf.getvalue()
