"""routes.truck_cleaning_brochure — full-color, multi-page brochure PDFs (cleaning guide + services & pricing)."""
import io
from pathlib import Path
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen.canvas import Canvas

from routes.truck_cleaning import UPSELL_META, SCENT_MENU
from routes.truck_cleaning_sched import CLEANING_GUIDE

W, H = letter
LOGO = Path(__file__).resolve().parent / "_tc_logo_pdf.png"
INK = colors.HexColor("#0D1117")
PAPER = colors.HexColor("#FAFAF7")
AMBER = colors.HexColor("#F59E0B")
CYAN = colors.HexColor("#0891B2")
EMERALD = colors.HexColor("#059669")
VIOLET = colors.HexColor("#7C3AED")
ROSE = colors.HexColor("#E11D48")
SLATE = colors.HexColor("#334155")
GREY = colors.HexColor("#9CA3AF")
PALETTE = [AMBER, CYAN, EMERALD, VIOLET, ROSE]
TINTS = {AMBER: colors.HexColor("#FFF4DE"), CYAN: colors.HexColor("#E0F7FB"), EMERALD: colors.HexColor("#E2F7EE"),
         VIOLET: colors.HexColor("#F0E9FD"), ROSE: colors.HexColor("#FDE8ED")}


class Brochure:
    def __init__(self, title: str, subtitle: str):
        self.buf = io.BytesIO()
        self.c = Canvas(self.buf, pagesize=letter)
        self.title, self.subtitle = title, subtitle
        self.page = 0
        self._new_page()

    def _new_page(self):
        if self.page:
            self._footer()
            self.c.showPage()
        self.page += 1
        c = self.c
        c.setFillColor(PAPER); c.rect(0, 0, W, H, fill=1, stroke=0)
        hh = 120 if self.page == 1 else 64
        c.setFillColor(INK); c.rect(0, H - hh, W, hh, fill=1, stroke=0)
        c.setFillColor(AMBER); c.rect(0, H - hh - 5, W, 5, fill=1, stroke=0)
        x = 44
        if LOGO.exists():
            try:
                s = 96 if self.page == 1 else 48
                self.c.drawImage(str(LOGO), 40, H - hh + (hh - s) / 2, width=s, height=s,
                                 preserveAspectRatio=True, mask="auto")
                x = 40 + s + 14
            except Exception:  # noqa: BLE001
                pass
        if self.page == 1:
            c.setFont("Helvetica-Bold", 25); c.setFillColor(colors.white); c.drawString(x, H - 52, "ORISEI")
            c.setFillColor(AMBER); c.drawString(x + c.stringWidth("ORISEI ", "Helvetica-Bold", 25), H - 52, "TRUCK CLEANING")
            c.setFont("Helvetica-Bold", 14); c.setFillColor(colors.HexColor("#22D3EE")); c.drawString(x, H - 76, self.title.upper())
            c.setFont("Helvetica", 9.5); c.setFillColor(GREY); c.drawString(x, H - 94, self.subtitle)
        else:
            c.setFont("Helvetica-Bold", 13); c.setFillColor(colors.white); c.drawString(x, H - 34, "ORISEI ")
            c.setFillColor(AMBER); c.drawString(x + c.stringWidth("ORISEI ", "Helvetica-Bold", 13), H - 34, "TRUCK CLEANING")
            c.setFont("Helvetica", 8.5); c.setFillColor(GREY); c.drawString(x, H - 50, self.title)
        self.y = H - hh - 28

    def _footer(self):
        c = self.c
        c.setFillColor(INK); c.rect(0, 0, W, 40, fill=1, stroke=0)
        c.setFont("Helvetica", 7.5); c.setFillColor(GREY)
        c.drawString(44, 16, "Orisei Truck Cleaning Solutions · Minneapolis–St. Paul, MN · (612) 555-0117 · oliver@oriseifreight.com")
        c.setFillColor(AMBER); c.setFont("Helvetica-Bold", 8)
        c.drawRightString(W - 44, 16, f"PAGE {self.page}")

    def ensure(self, h: float):
        if self.y - h < 56:
            self._new_page()

    def band(self, text: str, color, chip: str = ""):
        self.ensure(46)
        c = self.c
        c.setFillColor(color); c.roundRect(40, self.y - 8, W - 80, 26, 8, fill=1, stroke=0)
        c.setFont("Helvetica-Bold", 12); c.setFillColor(colors.white); c.drawString(54, self.y, text)
        if chip:
            c.setFont("Helvetica-Bold", 9); c.drawRightString(W - 54, self.y, chip)
        self.y -= 36

    def step(self, n: int, text: str, color):
        lines = _wrap(text, 92)
        self.ensure(14 * len(lines) + 4)
        c = self.c
        c.setFillColor(color); c.circle(56, self.y + 3, 7, fill=1, stroke=0)
        c.setFont("Helvetica-Bold", 8); c.setFillColor(colors.white); c.drawCentredString(56, self.y, str(n))
        c.setFont("Helvetica", 9.5); c.setFillColor(SLATE)
        for i, ln in enumerate(lines):
            c.drawString(72, self.y - i * 13, ln)
        self.y -= 13 * len(lines) + 5

    def tint_panel(self, lines, color, title=""):
        wrapped = [w for ln in lines for w in _wrap(ln, 95)]
        h = 16 * len(wrapped) + (26 if title else 14) + 8
        self.ensure(h)
        c = self.c
        c.setFillColor(TINTS.get(color, colors.HexColor("#F1F5F9")))
        c.roundRect(40, self.y - h + 16, W - 80, h, 10, fill=1, stroke=0)
        c.setFillColor(color); c.rect(40, self.y - h + 16, 6, h, fill=1, stroke=0)
        yy = self.y - 4
        if title:
            c.setFont("Helvetica-Bold", 11); c.setFillColor(color); c.drawString(58, yy, title); yy -= 18
        c.setFont("Helvetica", 9.5); c.setFillColor(SLATE)
        for ln in wrapped:
            c.drawString(58, yy, ln); yy -= 15
        self.y = yy - 16

    def price_row(self, label: str, desc: str, price: str, color):
        lines = _wrap(desc, 78)
        h = 14 * len(lines) + 20
        self.ensure(h)
        c = self.c
        c.setFont("Helvetica-Bold", 10.5); c.setFillColor(INK); c.drawString(48, self.y, label)
        c.setFillColor(color); c.roundRect(W - 110, self.y - 5, 62, 18, 9, fill=1, stroke=0)
        c.setFont("Helvetica-Bold", 9.5); c.setFillColor(colors.white); c.drawCentredString(W - 79, self.y, price)
        yy = self.y - 14
        c.setFont("Helvetica", 8.5); c.setFillColor(colors.HexColor("#64748B"))
        for ln in lines:
            c.drawString(48, yy, ln); yy -= 12
        c.setStrokeColor(colors.HexColor("#E2E8F0")); c.line(44, yy - 2, W - 44, yy - 2)
        self.y = yy - 12

    def finish(self) -> bytes:
        self._footer()
        self.c.save()
        return self.buf.getvalue()


def _wrap(text: str, width: int):
    out, line = [], ""
    for word in str(text).split():
        if len(line) + len(word) + 1 > width:
            out.append(line); line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        out.append(line)
    return out or [""]


def _guide_brochure() -> bytes:
    g = CLEANING_GUIDE
    b = Brochure("The 45-Minute Showroom Spec", "Full step-by-step crew guide · print for every van")
    b.tint_panel([g["intro"]], CYAN, title="HOW WE WORK")
    b.band("SUPPLY KIT — EVERY VAN, EVERY DAY", INK)
    half = (len(g["supply_kit"]) + 1) // 2
    rows = max(half, len(g["supply_kit"]) - half)
    b.ensure(rows * 15 + 10)
    c = b.c
    c.setFont("Helvetica", 9); c.setFillColor(SLATE)
    for i, item in enumerate(g["supply_kit"]):
        col = 0 if i < half else 1
        yy = b.y - (i % half if col == 0 else i - half) * 15
        x = 52 + col * ((W - 92) / 2)
        c.setFillColor(AMBER); c.circle(x, yy + 3, 2.2, fill=1, stroke=0)
        c.setFillColor(SLATE); c.drawString(x + 10, yy, item[:58])
    b.y -= rows * 15 + 14
    for i, ph in enumerate(g["phases"]):
        color = PALETTE[i % len(PALETTE)]
        b.band(ph["phase"].upper(), color, chip=f"{ph['minutes']} MIN")
        for n, st in enumerate(ph["steps"], 1):
            b.step(n, st, color)
        b.y -= 6
    b.band("UPSELL PROCEDURES — ASK ON EVERY JOB", EMERALD)
    for u in g["upsells"]:
        b.tint_panel([" → ".join(u["steps"])], EMERALD, title=u["name"])
    b.band("SAFETY — NON-NEGOTIABLE", ROSE)
    b.tint_panel(g["safety"], ROSE)
    b.band("QUALITY BAR — BEFORE YOU LEAVE THE YARD", AMBER)
    b.tint_panel(g["quality_bar"], AMBER)
    return b.finish()


def _services_brochure() -> bytes:
    b = Brochure("Services & Pricing", "Mobile semi-cab cleaning · we come to your yard · photo proof on every job")
    # pricing cards
    b.ensure(120)
    c = b.c
    cards = [("ONE-TIME CLEAN", "$150", "per cab", AMBER, ["Full 45-minute showroom spec", "Before/after photo proof", "Perfect first-visit trial"]),
             ("BI-WEEKLY SUB", "$120", "per cab / visit", CYAN, ["We manage the schedule", "SMS reminders + reschedule", "Every 10th clean FREE"]),
             ("FLEET PROGRAM 10+", "$125", "per cab", EMERALD, ["Priority yard scheduling", "Monthly auto-billing", "Dedicated crew lead"])]
    cw = (W - 80 - 24) / 3
    for i, (name, price, per, color, feats) in enumerate(cards):
        x = 40 + i * (cw + 12)
        c.setFillColor(colors.white); c.roundRect(x, b.y - 104, cw, 112, 10, fill=1, stroke=0)
        c.setFillColor(color); c.roundRect(x, b.y - 104 + 112 - 26, cw, 26, 10, fill=1, stroke=0)
        c.rect(x, b.y - 104 + 112 - 36, cw, 12, fill=1, stroke=0)
        c.setFont("Helvetica-Bold", 9.5); c.setFillColor(colors.white); c.drawCentredString(x + cw / 2, b.y - 104 + 112 - 18, name)
        c.setFont("Helvetica-Bold", 21); c.setFillColor(INK); c.drawCentredString(x + cw / 2, b.y - 104 + 62, price)
        c.setFont("Helvetica", 8); c.setFillColor(colors.HexColor("#64748B")); c.drawCentredString(x + cw / 2, b.y - 104 + 50, per)
        c.setFont("Helvetica", 7.6); c.setFillColor(SLATE)
        for j, f in enumerate(feats):
            c.drawCentredString(x + cw / 2, b.y - 104 + 34 - j * 11, f)
    b.y -= 126
    b.tint_panel(["Every clean includes: dashboard wipe + full vacuum · seat deep clean with stain & odor treatment · "
                  "floor scrub (mats, pedals, undercarriage) · windows inside & out · finishing air freshener. "
                  "45 minutes per cab. Insured, background-checked, uniformed crews."], INK if INK in TINTS else CYAN,
                 title="THE CORE SPEC — INCLUDED IN EVERY PLAN")
    b.band("ADD-ON SERVICES MENU", VIOLET)
    for u in [u for u in UPSELL_META if u["category"] == "add_on"]:
        b.price_row(u["label"], u["desc"], f"${u['price']:.0f}", VIOLET)
    b.band("AIR FRESHENER PACKAGES", CYAN)
    for u in [u for u in UPSELL_META if u["category"] == "freshener"]:
        b.price_row(u["label"], u["desc"], f"${u['price']:.0f}", CYAN)
    b.ensure(58)
    c.setFont("Helvetica-Bold", 10); c.setFillColor(INK); c.drawString(44, b.y, "THE SCENT MENU")
    b.y -= 20
    x = 44
    for s in SCENT_MENU:
        wpx = c.stringWidth(s, "Helvetica-Bold", 8) + 18
        if x + wpx > W - 44:
            x = 44; b.y -= 22
        c.setFillColor(TINTS[CYAN]); c.roundRect(x, b.y - 5, wpx, 17, 8, fill=1, stroke=0)
        c.setFont("Helvetica-Bold", 8); c.setFillColor(CYAN); c.drawString(x + 9, b.y, s)
        x += wpx + 8
    b.y -= 30
    b.tint_panel(["Loyalty: every 10th cleaning free. Referrals: send us a fleet, take $50 off your next service. "
                  "Book by text, email, or the one-tap link on any reminder. Net 15 · card, ACH, or check."],
                 AMBER, title="LOYALTY & BOOKING")
    return b.finish()


def build_truck_cleaning_brochure_router(*, db, require_role: Callable) -> APIRouter:
    router = APIRouter(prefix="/truck-cleaning", tags=["truck-cleaning-brochures"])
    guard = require_role("admin", "owner", "dispatcher")

    @router.get("/brochures/{doc_id}.pdf")
    async def brochure(doc_id: str, _=Depends(guard)) -> Response:
        builders = {"cleaning-guide": (_guide_brochure, "Orisei_Cleaning_Guide_Brochure"),
                    "services": (_services_brochure, "Orisei_Services_Pricing_Brochure")}
        if doc_id not in builders:
            raise HTTPException(status_code=404, detail="Unknown brochure")
        fn, name = builders[doc_id]
        return Response(content=fn(), media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="{name}.pdf"'})

    return router
