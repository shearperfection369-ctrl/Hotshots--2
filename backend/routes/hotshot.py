"""routes.hotshot — HOT SHOT TMS: white-label SaaS go-to-market.

Public landing support (lead capture, one-pager PDF) + internal sales ops.
Endpoints — /api/hotshot/*
"""
import io
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen.canvas import Canvas

logger = logging.getLogger("orisei.hotshot")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
W, H = letter

INK = colors.HexColor("#0D1117")
AMBER = colors.HexColor("#F59E0B")
ORANGE = colors.HexColor("#EA580C")
SLATE = colors.HexColor("#475569")
PAPER = colors.HexColor("#FAFAF7")

TIERS = [
    ("STARTER", "$600/mo", ["Core TMS + live shipment tracking", "Load aggregator (DAT-style board feed)",
                            "Instant quote engine", "Docs: rate cons, BOLs, invoices", "Email support"]),
    ("GROWTH", "$1,500/mo", ["Everything in Starter", "AI Load Hunter — hunts and scores loads 24/7",
                             "AI Triage — exceptions resolved with playbooks", "Workflow automation + AR aging",
                             "Route optimizer + margin calculator", "Priority support"]),
    ("DONE-WITH-YOU", "$4,000/mo", ["Everything in Growth", "White-glove onboarding + data migration",
                                    "Weekly optimization call with a 13-yr freight operator",
                                    "Custom workflows built for your desk", "We help you run it"]),
]


class LeadIn(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: str = Field(..., max_length=200)
    company: str = Field("", max_length=150)
    phone: str = Field("", max_length=40)
    fleet_or_volume: str = Field("", max_length=120)
    message: str = Field("", max_length=1000)
    tier_interest: str = Field("", max_length=40)


def _one_pager_pdf() -> bytes:
    buf = io.BytesIO()
    c = Canvas(buf, pagesize=letter)
    c.setTitle("Hot Shot TMS — One-Pager")
    # header band
    c.setFillColor(INK)
    c.rect(0, H - 150, W, 150, fill=1, stroke=0)
    c.setFillColor(AMBER)
    c.rect(0, H - 156, W, 6, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 34)
    c.setFillColor(AMBER)
    c.drawString(46, H - 72, "HOT SHOT TMS")
    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(colors.white)
    c.drawString(46, H - 96, "The AI-driven TMS built by a working freight brokerage — not a software company.")
    c.setFont("Helvetica", 9)
    c.setFillColor(colors.HexColor("#9CA3AF"))
    c.drawString(46, H - 116, "Battle-tested daily on real loads at Orisei Freight Solutions · 13 years of logistics experience in every screen")

    y = H - 190
    c.setFillColor(PAPER)
    c.rect(0, 0, W, y + 20, fill=1, stroke=0)

    def h2(txt, yy):
        c.setFont("Helvetica-Bold", 13)
        c.setFillColor(ORANGE)
        c.drawString(46, yy, txt)
        return yy - 18

    def li(txt, yy, bold=None):
        c.setFillColor(AMBER)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(52, yy, "▸")
        c.setFillColor(SLATE)
        if bold:
            c.setFont("Helvetica-Bold", 9)
            c.drawString(64, yy, bold)
            c.setFont("Helvetica", 9)
            c.drawString(64 + c.stringWidth(bold, "Helvetica-Bold", 9), yy, " — " + txt)
        else:
            c.setFont("Helvetica", 9)
            c.drawString(64, yy, txt)
        return yy - 14

    y = h2("WHAT IT DOES", y)
    y = li("one command deck for quotes, booking, live GPS map tracking, docs, invoicing, and AR", y, "Full freight lifecycle")
    y = li("posts from DAT, Truckstop, Uber Freight and more in one scored feed", y, "Load aggregator")
    y = li("rate cons, BOLs, PODs, invoices generated and filed automatically", y, "Paperwork on autopilot")
    y = li("simulate a full 31-day brokerage month — real diesel prices, real overhead math", y, "Operational Sandbox")
    y = li("cost/mile, margin %, fill rate, OTP + 45-metric carrier scorecards graded A+ to F", y, "KPI intelligence")
    y -= 6
    y = h2("THE AI SUITE (THIS IS THE MOAT)", y)
    y = li("hunts load boards 24/7, scores every load against YOUR lanes, margins and trucks", y, "AI Load Hunter")
    y = li("breakdowns, detention, claims — detected and resolved with operator-grade playbooks", y, "AI Triage")
    y = li("check calls, status updates, invoicing, collections chased without a human", y, "Workflow automation")
    y = li("a business copilot that plans your route to $20k/week net margin — and tracks it", y, "AI Growth Copilot")
    y = li("ML load-matching + one-click tender to the top-3 scored carriers with compliance checks", y, "Dispatch Autopilot")
    y = li("auto-invoice on POD, AR aging chased automatically, QuickBooks OAuth sync", y, "Money on autopilot")
    y -= 6
    y = h2("WHO IT'S FOR", y)
    y = li("replace spreadsheets and 2005-era TMS tools in an afternoon", y, "Small brokerages ($500K–$5M/yr)")
    y = li("compete with the big fleets: dispatch, margins and paperwork handled", y, "Owner-operators (3–10 trucks)")
    y = li("your entire back office running on day one of your authority", y, "New MC holders")
    y -= 6
    y = h2("PRICING — FOUNDER RATE: 35% OFF FOR THE FIRST 5 CLIENTS", y)
    col_w = (W - 92 - 24) / 3
    for i, (name, price, feats) in enumerate(TIERS):
        x = 46 + i * (col_w + 12)
        c.setFillColor(INK if i == 1 else colors.white)
        c.setStrokeColor(AMBER)
        c.roundRect(x, y - 148, col_w, 148, 8, fill=1, stroke=1)
        c.setFont("Helvetica-Bold", 10)
        c.setFillColor(AMBER)
        c.drawString(x + 10, y - 20, name)
        c.setFont("Helvetica-Bold", 14)
        c.setFillColor(colors.white if i == 1 else INK)
        c.drawString(x + 10, y - 38, price)
        c.setFont("Helvetica", 6.8)
        c.setFillColor(colors.HexColor("#C9D1D9") if i == 1 else SLATE)
        yy = y - 54
        for f in feats:
            c.drawString(x + 10, yy, "• " + f[:44])
            yy -= 10
    y -= 168
    c.setFillColor(INK)
    c.rect(0, 0, W, 64, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(AMBER)
    c.drawCentredString(W / 2, 38, "BOOK A LIVE DEMO — WATCH THE AI HUNT LOADS IN REAL TIME")
    c.setFont("Helvetica", 8.5)
    c.setFillColor(colors.white)
    import os
    base = (os.environ.get("PUBLIC_FRONTEND_URL") or "").replace("https://", "")
    c.drawCentredString(W / 2, 22, f"{base}/hotshot · oliver@oriseifreight.com · Built & operated by Orisei Freight Solutions LLC, Minnesota")
    c.save()
    return buf.getvalue()


def build_hotshot_router(*, db, get_current_user: Callable,
                         require_role: Callable) -> APIRouter:
    router = APIRouter(prefix="/hotshot", tags=["hotshot-tms"])

    @router.post("/leads")  # PUBLIC — landing page form
    async def create_lead(payload: LeadIn) -> Dict[str, Any]:
        email = payload.email.strip().lower()
        if not EMAIL_RE.match(email):
            raise HTTPException(status_code=400, detail="Enter a valid email address")
        recent = await db.hotshot_leads.count_documents({"email": email})
        lead = {"lead_id": f"HSL-{uuid.uuid4().hex[:6].upper()}", **payload.model_dump(),
                "email": email, "status": "new", "duplicate": recent > 0,
                "created_at": datetime.now(timezone.utc).isoformat()}
        await db.hotshot_leads.insert_one(dict(lead))
        logger.info("HOT SHOT lead captured: %s (%s)", payload.name, email)
        return {"ok": True, "message": "You're on the list — we'll reach out within one business day to book your demo."}

    @router.get("/leads")
    async def list_leads(_=Depends(require_role("owner", "dispatcher"))) -> Dict[str, Any]:
        leads = await db.hotshot_leads.find({}, {"_id": 0}).sort("created_at", -1).to_list(300)
        return {"leads": leads, "count": len(leads)}

    @router.post("/leads/{lead_id}/status")
    async def lead_status(lead_id: str, payload: Dict[str, str],
                          _=Depends(require_role("owner", "dispatcher"))) -> Dict[str, Any]:
        status = payload.get("status", "")
        if status not in ("new", "contacted", "demo_booked", "won", "lost"):
            raise HTTPException(status_code=400, detail="Invalid status")
        r = await db.hotshot_leads.update_one({"lead_id": lead_id}, {"$set": {"status": status}})
        if r.matched_count == 0:
            raise HTTPException(status_code=404, detail="Lead not found")
        return {"ok": True}

    @router.get("/one-pager.pdf")  # PUBLIC — shareable collateral
    async def one_pager() -> StreamingResponse:
        return StreamingResponse(io.BytesIO(_one_pager_pdf()), media_type="application/pdf",
                                 headers={"Content-Disposition": 'attachment; filename="HotShot_TMS_One_Pager.pdf"'})

    return router
