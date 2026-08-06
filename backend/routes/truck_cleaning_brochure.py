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
        c.drawString(44, 16, "Orisei Truck Cleaning Solutions · Minneapolis–St. Paul, MN · (763) 443-4459 · oliver@oriseifreightsolutions.com")
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
    cards = [("ONE-TIME CLEAN", "$175", "per cab", AMBER, ["Full 45-minute showroom spec", "Before/after photo proof", "Perfect first-visit trial"]),
             ("BI-WEEKLY SUB", "$130", "per cab / visit", CYAN, ["We manage the schedule", "SMS reminders + reschedule", "Every 10th clean FREE"]),
             ("FLEET PROGRAM 10+", "$150", "per cab", EMERALD, ["Priority yard scheduling", "Monthly auto-billing", "Dedicated crew lead"])]
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
    b.band("BEDDING & PILLOW SERVICE — SLEEP LIKE A HOTEL, PARK LIKE A TRUCKER", ROSE)
    for u in [u for u in UPSELL_META if u["category"] == "bedding"]:
        b.price_row(u["label"], u["desc"], f"${u['price']:.0f}", ROSE)
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


def _yard_promo_brochure() -> bytes:
    b = Brochure("The Yard Manager Package", "Mobile cab cleaning for your whole yard · zero driver downtime · photo proof on every truck")
    c = b.c
    b.tint_panel(["Your drivers live in those cabs. A clean cab is cheaper than a new driver — retention studies put "
                  "replacement cost at $8,000+ per seat. We bring a uniformed, insured 2-person crew to YOUR yard, "
                  "clean each cab to a 45-minute showroom spec while the truck is parked anyway, and send you "
                  "time-stamped before/after photos of every single unit. No driver time lost. No detail-shop runs. "
                  "No excuses."], AMBER, title="WHY YARDS PARTNER WITH ORISEI")
    b.band("WHAT EVERY CAB GETS — THE 45-MINUTE SHOWROOM SPEC", CYAN)
    for i, ph in enumerate(CLEANING_GUIDE["phases"]):
        b.step(i + 1, f"{ph['phase']} ({ph['minutes']} min)", PALETTE[i % len(PALETTE)])
    b.y -= 6
    b.band("WHAT YOU GET AS THE YARD MANAGER", EMERALD)
    for n, t in enumerate([
            "Locked weekly or bi-weekly slot — same crew, same day, rain or shine",
            "Before/after photo proof link for every truck, the moment it's done",
            "Live schedule + one text to add or skip a unit",
            "One monthly invoice for the whole yard — card, ACH, or check, Net 15",
            "Insured, background-checked, uniformed crews with battery-powered gear (no cords, no water mess)",
            "Driver scent menu — let each driver pick their cab's finish"], 1):
        b.step(n, t, EMERALD)
    b.y -= 6
    b.band("YARD PRICING — LOCK-IN RATES", AMBER)
    b.price_row("Bi-Weekly Yard Lock-In", "Your slot every 2 weeks · most popular · every 10th clean FREE", "$130/cab", AMBER)
    b.price_row("Weekly Yard Lock-In", "High-turn yards & lease fleets · priority crew", "$110/cab", AMBER)
    b.price_row("Fleet Program 10+ cabs", "Monthly auto-billing · dedicated crew lead", "$150/cab", AMBER)
    b.price_row("One-Time Trial", "Prove-it visit — full spec, photo proof", "$175/cab", AMBER)
    b.tint_panel(["FOUNDING YARD OFFER — first 3 yards to sign a lock-in schedule get their first 2 cabs cleaned "
                  "FREE on the pilot visit, plus the founding rate locked for 12 months. We're building our Twin "
                  "Cities route now: the yards that anchor it get the best slots and the best price, permanently."],
                 ROSE, title="FOUNDING YARD OFFER")
    b.band("HOW A PILOT WORKS — ZERO RISK", VIOLET)
    for n, t in enumerate([
            "Pick a day — we bring the crew to your yard",
            "We clean 2 cabs free + any others at trial rate, 45 minutes each",
            "You get the photo-proof links and walk the cabs yourself",
            "Love it? We lock your weekly or bi-weekly slot on the spot"], 1):
        b.step(n, t, VIOLET)
    b.y -= 8
    b.tint_panel(["Call or text Oliver: (763) 443-4459 · oliver@oriseifreightsolutions.com · "
                  "Book online in 60 seconds at our booking page. Serving Minneapolis, St. Paul and every yard "
                  "within 50 miles."], CYAN, title="LOCK IN YOUR YARD'S SLOT")
    return b.finish()


MERCH_DIR = "/app/frontend/public/merch"


def _merch_package() -> bytes:
    """Printer-ready apparel & merch spec package — light layout for print shops."""
    import io as _io
    import os as _os
    from reportlab.lib.colors import HexColor
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen.canvas import Canvas

    NAVY, BLUE, GOLD = HexColor("#123B5C"), HexColor("#2563EB"), HexColor("#F59E0B")
    INK2, MUT2, LINE2 = HexColor("#1C2430"), HexColor("#5B6472"), HexColor("#E2E8F0")
    PW, PH = letter
    buf = _io.BytesIO()
    c = Canvas(buf, pagesize=letter)

    def head(title, sub=""):
        c.setFillColor(NAVY)
        c.rect(0, PH - 74, PW, 74, stroke=0, fill=1)
        logo = "/app/frontend/public/tc-logo.png"
        if _os.path.exists(logo):
            c.drawImage(logo, 40, PH - 66, width=58, height=58, mask="auto", preserveAspectRatio=True)
        c.setFillColor(HexColor("#FFFFFF"))
        c.setFont("Helvetica-Bold", 16)
        c.drawString(112, PH - 40, title)
        c.setFillColor(GOLD)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(112, PH - 56, sub or "ORISEI TRUCK CLEANING · CREW APPAREL & MERCH — PRINTER PACKAGE")
        c.setFillColor(MUT2)
        c.setFont("Helvetica", 7)
        c.drawRightString(PW - 40, 28, "Orisei Freight Solutions LLC · Twin Cities, MN · (763) 443-4459 · oliver@oriseifreightsolutions.com")

    def sect(y, t):
        c.setFillColor(GOLD)
        c.rect(40, y - 4, PW - 80, 18, stroke=0, fill=1)
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(48, y, t)
        return y - 22

    def line(y, label, value, bold_val=False):
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 8.5)
        c.drawString(48, y, label)
        c.setFillColor(INK2)
        c.setFont("Helvetica-Bold" if bold_val else "Helvetica", 8.5)
        c.drawString(210, y, value)
        return y - 13

    # ---- PAGE 1: cover + mockup grid ----
    head("CREW APPAREL & MERCH PACKAGE", "PRINT-READY SPECS + MOCKUPS · WOMEN-MAJORITY CREW SIZING")
    imgs = [("tee_women.jpg", "Women's Tee — front"), ("tee_back.jpg", "Tee — back print"),
            ("hoodie.jpg", "Hoodie"), ("cap.jpg", "Trucker Cap"),
            ("beanie.jpg", "Beanie"), ("vest.jpg", "ANSI Safety Vest")]
    gw, gh, gx0, gy0 = 165, 165, 44, PH - 300
    for i, (fn, cap) in enumerate(imgs):
        x = gx0 + (i % 3) * (gw + 12)
        y = gy0 - (i // 3) * (gh + 34)
        p = f"{MERCH_DIR}/{fn}"
        if _os.path.exists(p):
            c.drawImage(p, x, y, width=gw, height=gh, preserveAspectRatio=True, anchor="c")
        c.setStrokeColor(LINE2)
        c.rect(x, y, gw, gh, stroke=1, fill=0)
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 8)
        c.drawCentredString(x + gw / 2, y - 12, cap)
    y = gy0 - gh - 60
    c.setFillColor(INK2)
    c.setFont("Helvetica", 8.5)
    for t in ["Mockups above are visual direction for the printer — final placement per the spec pages that follow.",
              "Crew is majority women: order the women's-cut size curve on page 3. Logo art: full-color shield",
              "(tc-logo.png, 300dpi) — request vector conversion (.AI/.EPS) from printer before first run."]:
        c.drawString(44, y, t)
        y -= 12
    c.showPage()

    # ---- PAGE 2: brand colors + decoration specs ----
    head("BRAND COLORS & DECORATION SPECS")
    y = PH - 100
    y = sect(y, "BRAND COLOR SYSTEM — MATCH TO THE SHIELD LOGO")
    swatches = [("DEEP NAVY (garment base)", "#123B5C", "PMS 2965C", "C100 M72 Y32 K28"),
                ("ORISEI BLUE (logo field)", "#2563EB", "PMS 2727C", "C79 M58 Y0 K0"),
                ("AMBER GOLD (accent/ink)", "#F59E0B", "PMS 1235C", "C0 M40 Y100 K0"),
                ("WHITE (text/outline)", "#FFFFFF", "White", "C0 M0 Y0 K0")]
    for name, hx, pms, cmyk in swatches:
        c.setFillColor(HexColor(hx))
        c.rect(48, y - 6, 34, 16, stroke=1, fill=1)
        c.setStrokeColor(LINE2)
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 8.5)
        c.drawString(92, y, name)
        c.setFillColor(INK2)
        c.setFont("Helvetica", 8.5)
        c.drawString(300, y, f"HEX {hx}  ·  {pms}  ·  {cmyk}")
        y -= 22
    y -= 6
    y = sect(y, "LOGO PLACEMENT & SIZES")
    for label, val in [("Tees/hoodies — left chest", 'Shield logo 3.5" wide, centered 3–4" below shoulder seam'),
                       ("Tees — full back", 'Arc "ORISEI TRUCK CLEANING" + shield + "YOUR CAB. SHOWROOM CLEAN." — 11" wide'),
                       ("Hoodie — center chest", 'Shield logo 8" wide, centered above pocket'),
                       ("Cap — front panel", 'Embroidered shield 2.4" wide (max 12k stitches), amber + white threads on navy'),
                       ("Beanie — cuff", 'Embroidered shield patch 2" wide on cuff front, amber stripe knit-in if available'),
                       ("Safety vest — left chest + back", 'Chest: shield 3.5" heat transfer. Back: "ORISEI TRUCK CLEANING" navy block text 10" wide')]:
        y = line(y, label, val)
    y -= 6
    y = sect(y, "DECORATION METHODS")
    for label, val in [("Tees / hoodies", "Screen print, plastisol — amber PMS 1235C + white on navy garments"),
                       ("Caps / beanies", "Embroidery — amber + white + royal threads (match swatches above)"),
                       ("Safety vests", "Heat-transfer vinyl (prints don't compromise ANSI fabric); navy + full-color chest"),
                       ("Art files", "tc-logo.png 300dpi supplied; request one-time vector redraw for embroidery digitizing")]:
        y = line(y, label, val)
    c.showPage()

    # ---- PAGE 3: garment lineup + size curve + vest compliance ----
    head("ORDER SHEET — GARMENTS, BLANKS & SIZE CURVE")
    y = PH - 100
    y = sect(y, "GARMENT LINEUP & SUGGESTED BLANKS (20-PERSON CREW STARTER ORDER)")
    rows = [("Women's tee (navy)", "Bella+Canvas 6400 (women's relaxed)", "42 pcs (3/worker × 14 women)"),
            ("Unisex tee (navy)", "Bella+Canvas 3001", "18 pcs (3/worker × 6)"),
            ("Women's hoodie (navy)", "Bella+Canvas 7519 / Gildan SF500FL", "14 pcs"),
            ("Unisex hoodie (navy)", "Gildan SF500 Softstyle", "6 pcs"),
            ("Trucker cap (navy/amber)", "Richardson 112 (navy front, amber mesh custom)", "20 pcs"),
            ("Cuffed beanie (navy)", "Yupoong 1501KC / Carhartt A18 style", "20 pcs"),
            ("ANSI Class 2 vest (hi-vis orange)", "ML Kishigo 1519 / Radians SV22 — NAVY trim binding", "40 pcs (2/worker)")]
    for g, blank, qty in rows:
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 8.5)
        c.drawString(48, y, g)
        c.setFillColor(INK2)
        c.setFont("Helvetica", 8)
        c.drawString(215, y, blank)
        c.setFillColor(GOLD)
        c.setFont("Helvetica-Bold", 8)
        c.drawRightString(PW - 48, y, qty)
        y -= 15
    y -= 8
    y = sect(y, "SIZE CURVE — WOMEN-MAJORITY CREW (per 20 workers)")
    c.setFillColor(INK2)
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(48, y, "Women's cut (14):")
    c.setFont("Helvetica", 8.5)
    c.drawString(150, y, "XS ×2   S ×4   M ×4   L ×2   XL ×1   2XL ×1")
    y -= 14
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(48, y, "Unisex (6):")
    c.setFont("Helvetica", 8.5)
    c.drawString(150, y, "S ×1   M ×2   L ×1   XL ×1   2XL ×1")
    y -= 14
    c.setFont("Helvetica-Oblique", 7.5)
    c.setFillColor(MUT2)
    c.drawString(48, y, "Scale curve proportionally per garment quantity. Vests: order S/M ×22, L/XL ×14, 2XL/3XL ×4 (fits over hoodies).")
    y -= 20
    y = sect(y, "SAFETY VEST COMPLIANCE — READ BEFORE PRINTING")
    for t in ["Vests MUST remain ANSI/ISEA 107 Class 2 compliant: hi-vis fluorescent orange background with",
              "2\" silver reflective bands. Brand elements ride on TRIM and PRINT only: navy binding/edging,",
              "shield heat-transfer on left chest, navy 'ORISEI TRUCK CLEANING' block across upper back.",
              "Do not cover reflective bands with print. Hi-vis amber-orange is the closest ANSI color to our",
              "brand gold — it reads as Orisei amber on the yard."]:
        c.setFillColor(INK2)
        c.setFont("Helvetica", 8.5)
        c.drawString(48, y, t)
        y -= 12
    y -= 10
    y = sect(y, "PRINTER CHECKLIST")
    for n, t in enumerate(["Confirm PMS matches on press proofs (2965C / 2727C / 1235C) before full run",
                           "Send digital proof of each placement for approval — email oliver@oriseifreightsolutions.com",
                           "First article: 1 of each garment for fit + wash test before bulk decoration",
                           "Deliver vector digitized files (.AI/.EPS/.DST) back with the order for future runs"], 1):
        c.setFillColor(GOLD)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(48, y, f"{n}.")
        c.setFillColor(INK2)
        c.setFont("Helvetica", 8.5)
        c.drawString(62, y, t)
        y -= 13
    c.save()
    return buf.getvalue()


def build_truck_cleaning_brochure_router(*, db, require_role: Callable) -> APIRouter:
    router = APIRouter(prefix="/truck-cleaning", tags=["truck-cleaning-brochures"])
    guard = require_role("admin", "owner", "dispatcher")

    @router.get("/brochures/{doc_id}.pdf")
    async def brochure(doc_id: str, _=Depends(guard)) -> Response:
        builders = {"cleaning-guide": (_guide_brochure, "Orisei_Cleaning_Guide_Brochure"),
                    "services": (_services_brochure, "Orisei_Services_Pricing_Brochure"),
                    "yard-promo": (_yard_promo_brochure, "Orisei_Yard_Manager_Package"),
                    "merch-package": (_merch_package, "Orisei_Crew_Apparel_Printer_Package")}
        if doc_id not in builders:
            raise HTTPException(status_code=404, detail="Unknown brochure")
        fn, name = builders[doc_id]
        return Response(content=fn(), media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="{name}.pdf"'})

    @router.post("/brochures/yard-promo/send")
    async def send_yard_promo(payload: dict, user=Depends(guard)):
        to = str(payload.get("email", "")).strip()
        company = str(payload.get("company", "")).strip()
        note = str(payload.get("note", "")).strip()[:500]
        if "@" not in to:
            raise HTTPException(400, "Valid email required")
        greet = f" for {company}" if company else ""
        note_html = f"<p style='background:#FFF4DE;padding:10px 14px;border-radius:8px'>{note}</p>" if note else ""
        subject = f"Orisei Truck Cleaning — yard cleaning program{greet}"
        html = (f"<div style='font-family:Arial,Helvetica,sans-serif;max-width:620px;margin:0 auto;color:#0D1117'>"
                f"<div style='background:#0D1117;padding:20px 26px;border-bottom:4px solid #F59E0B'>"
                f"<span style='color:#F59E0B;font-size:11px;letter-spacing:3px;font-family:Courier,monospace'>ORISEI TRUCK CLEANING</span>"
                f"<div style='color:#fff;font-size:20px;font-weight:800;margin-top:6px'>Your yard. Showroom-clean cabs. Zero downtime.</div></div>"
                f"<div style='padding:24px 26px;border:1px solid #E2E8F0;border-top:none;font-size:14px;line-height:1.6'>"
                f"<p>Attached is our full yard program{greet} — the 45-minute showroom spec, lock-in weekly/bi-weekly "
                f"pricing, and the <b>Founding Yard Offer: your first 2 cabs cleaned free</b> on a pilot visit.</p>"
                f"{note_html}"
                f"<p>We come to your yard, clean cabs while they're parked anyway, and send photo proof of every unit. "
                f"One reply or one text books your pilot day.</p>"
                f"<p><b>Oliver — Orisei Truck Cleaning</b><br>(763) 443-4459 · oliver@oriseifreightsolutions.com</p>"
                f"</div></div>")
        from routes.orisei_auto_digest import _resend_creds, _send_via_resend
        creds = await _resend_creds(db)
        res = await _send_via_resend(creds, to=to, subject=subject, html=html,
                                     pdf_bytes=_yard_promo_brochure(),
                                     pdf_filename="Orisei_Yard_Manager_Package.pdf") \
            if creds else {"sent": False, "error": "no_resend_creds"}
        status = "sent" if res.get("sent") else "recorded_no_key"
        from datetime import datetime, timezone
        await db.outbound_emails.insert_one({
            "to": to, "subject": subject, "html": html, "status": status, "error": res.get("error"),
            "kind": "tc_yard_promo", "company": company, "at": datetime.now(timezone.utc).isoformat()})
        return {"ok": True, "sent": res.get("sent", False), "status": status, "to": to}

    return router
