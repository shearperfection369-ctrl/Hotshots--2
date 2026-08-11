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
    b.band("FULL CAR DETAIL — $150 / CAR (PERSONAL VEHICLES)", EMERALD, chip="~90 MIN")
    b.tint_panel(["Base includes: full interior vacuum & wipe-down → exterior two-bucket hand wash & dry → "
                  "windows in & out → door jambs & console detailed → tire shine & wheel clean → finishing air freshener. "
                  "Offer the detail add-ons (clay bar, wax/sealant, ceramic spray, headlight restore, seat/carpet shampoo, "
                  "pet hair, engine bay, ozone) on every car job — photograph before/after just like a cab."],
                 EMERALD, title="CAR DETAIL PROCEDURE")
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
    b.tint_panel(["Not just trucks — we detail personal vehicles too. Base $150/car includes full interior "
                  "vacuum & wipe-down, exterior hand wash, windows in & out, door jambs & console, "
                  "tire shine, and a finishing air freshener. Add anything below."],
                 EMERALD, title="FULL CAR DETAIL — $150 / CAR")
    b.band("CAR DETAIL ADD-ONS", EMERALD)
    for u in [u for u in UPSELL_META if u["category"] == "car_detail_addon"]:
        b.price_row(u["label"], u["desc"], f"${u['price']:.0f}", EMERALD)
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
    b.price_row("Full Car Detail", "Personal vehicles — complete inside & out, per car", "$150/car", AMBER)
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


def _one_pager(base_url: str = "") -> bytes:
    """Clean one-page branded brochure — split layout: photos left, services/pricing/CTA right."""
    import os as _os
    buf = io.BytesIO()
    c = Canvas(buf, pagesize=letter)
    c.setFillColor(PAPER); c.rect(0, 0, W, H, fill=1, stroke=0)

    # header
    hh = 96
    c.setFillColor(INK); c.rect(0, H - hh, W, hh, fill=1, stroke=0)
    c.setFillColor(AMBER); c.rect(0, H - hh - 5, W, 5, fill=1, stroke=0)
    x = 40
    if LOGO.exists():
        c.drawImage(str(LOGO), 40, H - hh + 12, width=72, height=72, preserveAspectRatio=True, mask="auto")
        x = 126
    c.setFont("Helvetica-Bold", 26); c.setFillColor(colors.white); c.drawString(x, H - 46, "ORISEI")
    c.setFillColor(AMBER); c.drawString(x + c.stringWidth("ORISEI ", "Helvetica-Bold", 26), H - 46, "TRUCK CLEANING")
    c.setFont("Helvetica-Bold", 11); c.setFillColor(colors.HexColor("#22D3EE"))
    c.drawString(x, H - 66, "YOUR CAB. SHOWROOM CLEAN. ZERO DOWNTIME.")
    c.setFont("Helvetica", 9); c.setFillColor(GREY)
    c.drawString(x, H - 82, "Mobile semi-cab cleaning — we come to your yard, Twin Cities & 50 miles out")

    top = H - hh - 22

    # left column: photos
    lx, lw = 40, 252
    ih = lw / 1264 * 848
    for i, (fn, cap) in enumerate([("ts_crew.jpg", "Uniformed 2-person crews · battery-powered gear"),
                                   ("ts_cab.jpg", "Every interior finished to the 45-minute spec")]):
        y = top - ih - i * (ih + 34)
        p = f"{MERCH_DIR}/{fn}"
        if _os.path.exists(p):
            c.drawImage(p, lx, y, width=lw, height=ih, preserveAspectRatio=True, anchor="c")
        c.setStrokeColor(AMBER); c.setLineWidth(2); c.rect(lx, y, lw, ih, stroke=1, fill=0)
        c.setFont("Helvetica-Oblique", 7.5); c.setFillColor(SLATE)
        c.drawCentredString(lx + lw / 2, y - 12, cap)
    py = top - 2 * ih - 34 - 34
    ph_ = 74
    c.setFillColor(TINTS[CYAN]); c.roundRect(lx, py - ph_, lw, ph_, 10, fill=1, stroke=0)
    c.setFillColor(CYAN); c.rect(lx, py - ph_, 5, ph_, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 9.5); c.setFillColor(CYAN); c.drawString(lx + 14, py - 18, "PHOTO PROOF, EVERY TRUCK")
    c.setFont("Helvetica", 8); c.setFillColor(SLATE)
    for i, ln in enumerate(["Time-stamped before/after photos of", "every unit, sent the moment it's done.", "Insured · background-checked crews."]):
        c.drawString(lx + 14, py - 33 - i * 12, ln)

    # right column
    rx, rw = 316, W - 316 - 40

    def rband(y, text, color):
        c.setFillColor(color); c.roundRect(rx, y - 6, rw, 22, 7, fill=1, stroke=0)
        c.setFont("Helvetica-Bold", 10.5); c.setFillColor(colors.white); c.drawString(rx + 12, y, text)
        return y - 24

    y = top - 8
    y = rband(y, "THE 45-MINUTE SHOWROOM SPEC", INK)
    for s in ["Dashboard, console & vents detailed", "Full-cab vacuum — floor to bunk",
              "Seats deep-cleaned · stain & odor treatment", "Floor scrub — mats, pedals & undercarriage",
              "Windows & mirrors, inside and out", "Finishing scent — driver picks from our menu"]:
        c.setFillColor(AMBER); c.circle(rx + 8, y + 3, 2.6, fill=1, stroke=0)
        c.setFont("Helvetica", 9.3); c.setFillColor(SLATE); c.drawString(rx + 18, y, s)
        y -= 16
    y -= 10
    y = rband(y, "POPULAR ADD-ONS", VIOLET)
    for s in ["Bedding & pillow service — hotel-fresh bunk", "Premium air freshener packages",
              "Fridge / cooler clean-out"]:
        c.setFillColor(VIOLET); c.circle(rx + 8, y + 3, 2.6, fill=1, stroke=0)
        c.setFont("Helvetica", 9.3); c.setFillColor(SLATE); c.drawString(rx + 18, y, s)
        y -= 16
    y -= 10
    y = rband(y, "SIMPLE PRICING", AMBER)
    for label, sub, price, color in [("One-Time Cab Clean", "Full spec + photo proof — perfect trial", "$175", AMBER),
                                     ("Fleet Program 10+", "Priority scheduling · one monthly invoice", "$150", EMERALD),
                                     ("Bi-Weekly Lock-In", "Your slot, every 2 weeks · 10th clean FREE", "$130", CYAN),
                                     ("Full Car Detail", "Personal vehicles — inside & out, per car", "$150", VIOLET)]:
        c.setFont("Helvetica-Bold", 9.5); c.setFillColor(INK); c.drawString(rx + 4, y, label)
        c.setFillColor(color); c.roundRect(rx + rw - 56, y - 5, 56, 18, 9, fill=1, stroke=0)
        c.setFont("Helvetica-Bold", 9.5); c.setFillColor(colors.white); c.drawCentredString(rx + rw - 28, y, price)
        c.setFont("Helvetica", 7.6); c.setFillColor(colors.HexColor("#64748B")); c.drawString(rx + 4, y - 11, sub)
        c.setStrokeColor(colors.HexColor("#E2E8F0")); c.setLineWidth(1); c.line(rx, y - 18, rx + rw, y - 18)
        y -= 28
    y -= 2
    fh = 58
    c.setFillColor(TINTS[ROSE]); c.roundRect(rx, y - fh + 8, rw, fh, 10, fill=1, stroke=0)
    c.setFillColor(ROSE); c.rect(rx, y - fh + 8, 5, fh, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 9.5); c.setFillColor(ROSE); c.drawString(rx + 14, y - 8, "FOUNDING YARD OFFER")
    c.setFont("Helvetica", 8); c.setFillColor(SLATE)
    for i, ln in enumerate(["First 3 yards to lock a schedule get 2 cabs", "cleaned FREE on the pilot visit + founding", "rate locked for 12 months."]):
        c.drawString(rx + 14, y - 22 - i * 11, ln)

    # pilot steps strip
    sy = 168
    c.setFillColor(INK); c.roundRect(40, sy - 52, W - 80, 74, 12, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 10.5); c.setFillColor(AMBER); c.drawString(56, sy + 4, "HOW A PILOT WORKS — ZERO RISK")
    steps = [("1", "Pick a day —", "we come to you"), ("2", "2 cabs cleaned", "FREE on the pilot"),
             ("3", "Walk the cabs +", "photo-proof links"), ("4", "Love it? Lock your", "slot on the spot")]
    sw = (W - 112) / 4
    for i, (n, l1, l2) in enumerate(steps):
        x = 56 + i * sw
        c.setFillColor(AMBER); c.circle(x + 8, sy - 20, 8, fill=1, stroke=0)
        c.setFont("Helvetica-Bold", 9); c.setFillColor(INK); c.drawCentredString(x + 8, sy - 23, n)
        c.setFont("Helvetica-Bold", 8); c.setFillColor(colors.white)
        c.drawString(x + 22, sy - 17, l1); c.drawString(x + 22, sy - 28, l2)

    # CTA band
    cta_y = 40
    c.setFillColor(AMBER); c.rect(0, cta_y, W, 62, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 15); c.setFillColor(INK)
    c.drawString(40, cta_y + 36, "BOOK YOUR YARD'S PILOT DAY — ONE TEXT DOES IT")
    c.setFont("Helvetica-Bold", 10.5)
    c.drawString(40, cta_y + 16, "Call / text Oliver: (763) 443-4459   ·   oliver@oriseifreightsolutions.com")
    c.setFillColor(INK); c.rect(0, 0, W, cta_y, fill=1, stroke=0)
    c.setFont("Helvetica", 7.5); c.setFillColor(GREY)
    c.drawString(40, 15, "Orisei Truck Cleaning Solutions · Minneapolis–St. Paul, MN · Insured & background-checked crews")
    qr_drawn = False
    if base_url:
        try:
            import qrcode
            from reportlab.lib.utils import ImageReader
            q = qrcode.QRCode(box_size=10, border=1, error_correction=qrcode.constants.ERROR_CORRECT_M)
            q.add_data(f"{base_url.rstrip('/')}/wash")
            q.make(fit=True)
            qimg = q.make_image(fill_color="#0D1117", back_color="white").get_image()
            bx, bw = W - 40 - 88, 88
            c.setFillColor(colors.white); c.roundRect(bx, 10, bw, 96, 8, fill=1, stroke=0)
            c.drawImage(ImageReader(qimg), bx + 8, 30, width=72, height=72)
            c.setFont("Helvetica-Bold", 8); c.setFillColor(INK)
            c.drawCentredString(bx + bw / 2, 17, "SCAN TO BOOK")
            qr_drawn = True
        except Exception:  # noqa: BLE001
            pass
    if not qr_drawn:
        c.setFillColor(INK); c.setFont("Helvetica-Bold", 9); c.drawRightString(W - 40, cta_y + 16, "Book online in 60 seconds")
    c.setFillColor(AMBER); c.setFont("Helvetica-Bold", 8)
    c.drawRightString((W - 40 - 100) if qr_drawn else (W - 40), 15, "ORISEITRUCKCLEANING")

    c.save()
    return buf.getvalue()


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


def _business_card(base_url: str = "") -> bytes:
    """Print-ready 3.5x2in business card — front + back with scan-to-book QR, crop marks."""
    buf = io.BytesIO()
    c = Canvas(buf, pagesize=letter)
    c.setFillColor(colors.HexColor("#EDEDEA")); c.rect(0, 0, W, H, fill=1, stroke=0)
    CW, CH = 252, 144  # 3.5in x 2in
    cx = (W - CW) / 2

    def crops(x, y):
        c.setStrokeColor(colors.HexColor("#94A3B8")); c.setLineWidth(0.6)
        for px, py in [(x, y), (x + CW, y), (x, y + CH), (x + CW, y + CH)]:
            c.line(px - 14, py, px - 4, py) if px == x else c.line(px + 4, py, px + 14, py)
            c.line(px, py - 14, px, py - 4) if py == y else c.line(px, py + 4, px, py + 14)

    c.setFont("Helvetica-Bold", 16); c.setFillColor(INK)
    c.drawString(60, H - 70, "ORISEI TRUCK CLEANING — BUSINESS CARD (PRINT-READY)")
    c.setFont("Helvetica", 9); c.setFillColor(SLATE)
    c.drawString(60, H - 88, 'Standard 3.5" × 2" · print at 100% scale · PMS 1235C amber on ink #0D1117 · 300dpi art')

    # FRONT
    fy = H - 320
    c.setFont("Helvetica-Bold", 9); c.setFillColor(SLATE); c.drawString(cx, fy + CH + 10, "FRONT")
    crops(cx, fy)
    c.setFillColor(INK); c.rect(cx, fy, CW, CH, fill=1, stroke=0)
    c.setFillColor(AMBER); c.rect(cx, fy + CH - 6, CW, 6, fill=1, stroke=0)
    if LOGO.exists():
        c.drawImage(str(LOGO), cx + 12, fy + CH - 76, width=62, height=62, preserveAspectRatio=True, mask="auto")
    tx = cx + 84
    c.setFont("Helvetica-Bold", 12.5); c.setFillColor(colors.white); c.drawString(tx, fy + CH - 34, "ORISEI")
    c.setFillColor(AMBER); c.drawString(tx + c.stringWidth("ORISEI ", "Helvetica-Bold", 12.5), fy + CH - 34, "TRUCK CLEANING")
    c.setFont("Helvetica", 7); c.setFillColor(colors.HexColor("#22D3EE"))
    c.drawString(tx, fy + CH - 47, "YOUR CAB. SHOWROOM CLEAN. EVERY TIME.")
    c.setFont("Helvetica-Bold", 10); c.setFillColor(colors.white); c.drawString(tx, fy + CH - 70, "Oliver Cummins")
    c.setFont("Helvetica", 7.5); c.setFillColor(GREY); c.drawString(tx, fy + CH - 82, "Founder · Fleet Cleaning Programs")
    c.setFont("Helvetica-Bold", 9); c.setFillColor(AMBER); c.drawString(cx + 14, fy + 30, "(763) 443-4459")
    c.setFont("Helvetica", 7.5); c.setFillColor(colors.white); c.drawString(cx + 14, fy + 17, "oliver@oriseifreightsolutions.com")
    c.setFont("Helvetica", 7); c.setFillColor(GREY); c.drawRightString(cx + CW - 12, fy + 17, "Twin Cities · mobile · insured")

    # BACK
    by = fy - CH - 90
    c.setFont("Helvetica-Bold", 9); c.setFillColor(SLATE); c.drawString(cx, by + CH + 10, "BACK")
    crops(cx, by)
    c.setFillColor(colors.white); c.rect(cx, by, CW, CH, fill=1, stroke=0)
    c.setFillColor(AMBER); c.rect(cx, by, CW, 6, fill=1, stroke=0)
    if base_url:
        try:
            import qrcode
            from reportlab.lib.utils import ImageReader
            q = qrcode.QRCode(box_size=10, border=1, error_correction=qrcode.constants.ERROR_CORRECT_M)
            q.add_data(f"{base_url.rstrip('/')}/wash")
            q.make(fit=True)
            qimg = q.make_image(fill_color="#0D1117", back_color="white").get_image()
            c.drawImage(ImageReader(qimg), cx + 14, by + 32, width=92, height=92)
        except Exception:  # noqa: BLE001
            pass
    c.setFont("Helvetica-Bold", 11); c.setFillColor(INK); c.drawString(cx + 118, by + CH - 34, "SCAN TO BOOK")
    c.setFont("Helvetica", 7.5); c.setFillColor(SLATE)
    for i, t in enumerate(["45-min cab spec · $150 car detail", "Before/after photo proof", "We come to your yard"]):
        c.setFillColor(AMBER); c.circle(cx + 121, by + CH - 52 - i * 13 + 2, 2, fill=1, stroke=0)
        c.setFillColor(SLATE); c.drawString(cx + 128, by + CH - 52 - i * 13, t)
    c.setFont("Helvetica-Bold", 8); c.setFillColor(INK)
    c.drawString(cx + 118, by + 20, "$175 cab · $150 car · $130 bi-wk")
    c.setFont("Helvetica", 6.5); c.setFillColor(GREY); c.drawString(cx + 14, by + 20, "book in 60 sec")

    # printer notes
    ny = by - 46
    c.setFont("Helvetica-Bold", 9); c.setFillColor(INK); c.drawString(60, ny, "PRINTER NOTES")
    c.setFont("Helvetica", 8); c.setFillColor(SLATE)
    for i, t in enumerate(["16pt matte or soft-touch stock · full bleed navy front (extend #0D1117 to trim)",
                           "Test the QR from a printed proof before the full run — it must scan from 12 inches",
                           "Colors: ink #0D1117 · amber PMS 1235C (#F59E0B) · cyan accent #22D3EE"]):
        c.drawString(60, ny - 14 - i * 12, t)
    c.save()
    return buf.getvalue()


AD_DIR = "/app/frontend/public/ads"

CL_CAB_TITLE = "Mobile Semi-Cab & Fleet Cleaning — We Come To Your Yard (Twin Cities)"
CL_CAB_BODY = [
    "Your drivers live in that cab. We make it showroom clean — at YOUR yard, zero downtime.",
    "THE 45-MINUTE SHOWROOM SPEC (every clean): dashboard, console & vents detailed / full-cab",
    "vacuum floor to bunk / seats deep-cleaned with stain & odor treatment / floor scrub /",
    "windows in & out / finishing scent — driver's pick.",
    "PRICING: $175 one-time cab clean · $150/cab fleet program (10+) · $130/cab bi-weekly",
    "lock-in (every 10th clean FREE). Add-ons: tire dressing, ozone odor bomb, bedding service.",
    "Every truck gets time-stamped BEFORE/AFTER photo proof sent to you. Insured,",
    "background-checked, uniformed crews. Battery-powered gear — no yard hookups needed.",
    "FOUNDING YARD OFFER: first yards to lock a schedule get 2 cabs cleaned FREE on the",
    "pilot visit + rate locked for 12 months.",
    "Call/text Oliver: (763) 443-4459 · Book online in 60 seconds:",
    "https://oriseifreightsolutions.com/wash",
]
CL_CAR_TITLE = "Full Mobile Car Detail $150 — Inside & Out, We Come To You (Twin Cities)"
CL_CAR_BODY = [
    "Skip the detail-shop line. We bring the full detail to your driveway or office parking lot.",
    "$150 FULL DETAIL INCLUDES: complete interior vacuum & wipe-down / exterior hand wash",
    "& dry / windows & mirrors in and out / door jambs & console detailed / tire shine &",
    "wheel clean / finishing air freshener.",
    "ADD-ONS: ceramic spray coating $75 · seat & carpet shampoo $60 · hand wax & sealant $50 ·",
    "headlight restoration $45 · ozone odor treatment $40 · engine bay $35 · pet hair removal $30.",
    "Insured & background-checked. Before/after photos on every job.",
    "Call/text: (763) 443-4459 · Book online: https://oriseifreightsolutions.com/wash",
]
FB_FLEET_POST = [
    "TWIN CITIES FLEET OWNERS & OWNER-OPS — your drivers sit in that cab 11 hours a day.",
    "When did it last get a REAL clean?",
    "We bring a 2-person crew to YOUR yard and turn every cab showroom-clean in 45 minutes —",
    "while your trucks are parked anyway. Zero downtime. Before/after photo proof on every unit.",
    "$175 one-time · $150/cab for fleets 10+ · $130/cab bi-weekly lock-in (10th clean FREE).",
    "First yards to lock a schedule: 2 cabs FREE on the pilot visit.",
    "Call/text (763) 443-4459 or book in 60 seconds: oriseifreightsolutions.com/wash",
]
FB_CAR_POST = [
    "$150 FULL CAR DETAIL — WE COME TO YOU (Twin Cities + 50 miles).",
    "Inside & out: interior vacuum + wipe-down, hand wash, windows, door jambs, tire shine,",
    "air freshener. Add ceramic coating, seat shampoo, pet hair removal & more.",
    "Insured crews · before/after photos · book from your phone in 60 seconds.",
    "(763) 443-4459 · oriseifreightsolutions.com/wash",
]
POST_TIPS = [
    "Craigslist: post under Services > Automotive. Repost every 48 hours (delete + repost keeps you on top).",
    "Craigslist: attach ad_wide_1200x628.png first (it becomes the thumbnail), then the square ads.",
    "Facebook: post the square images in local trucking groups, owner-operator groups, and neighborhood",
    "groups (Nextdoor works too for car details). Post 8-10am or 7-9pm for best reach.",
    "Always reply to comments with the booking link — the algorithm boosts posts with replies.",
    "Rotate headlines weekly. Track which ad each caller mentions so you know what pulls.",
]


def _ad_kit() -> bytes:
    b = Brochure("Craigslist & Facebook Ad Kit", "Paste-ready copy + where to find the ad images")
    b.tint_panel(["Ad images live at oriseifreightsolutions.com/ads/ — download all three:",
                  "fb_fleet_1080.png (Facebook square, fleet/cab) · fb_cardetail_1080.png (Facebook square,",
                  "car detail) · ad_wide_1200x628.png (Craigslist header / FB link post)."],
                 CYAN, title="YOUR AD IMAGES")
    for img in ("fb_fleet_1080.png", "ad_wide_1200x628.png"):
        p = f"{AD_DIR}/{img}"
        try:
            ih = 150
            iw = ih if "1080" in img else ih * 1200 / 628
            b.ensure(ih + 26)
            b.c.drawImage(p, 44, b.y - ih, width=iw, height=ih, preserveAspectRatio=True, anchor="sw")
            b.c.setFont("Helvetica", 7.5)
            b.c.setFillColor(SLATE)
            b.c.drawString(44, b.y - ih - 11, img)
            b.y -= ih + 26
        except Exception:  # noqa: BLE001
            pass
    b.band("CRAIGSLIST AD 1 — FLEET / SEMI-CAB CLEANING", AMBER)
    b.tint_panel([f'TITLE: {CL_CAB_TITLE}'], AMBER, title="COPY EVERYTHING BELOW")
    b.tint_panel(CL_CAB_BODY, AMBER, title="BODY")
    b.band("CRAIGSLIST AD 2 — FULL CAR DETAIL", EMERALD)
    b.tint_panel([f'TITLE: {CL_CAR_TITLE}'], EMERALD, title="COPY EVERYTHING BELOW")
    b.tint_panel(CL_CAR_BODY, EMERALD, title="BODY")
    b.band("FACEBOOK GROUP POST 1 — FLEET / OWNER-OPS", CYAN)
    b.tint_panel(FB_FLEET_POST, CYAN, title="PASTE AS THE POST TEXT · ATTACH fb_fleet_1080.png")
    b.band("FACEBOOK GROUP POST 2 — CAR DETAIL", VIOLET)
    b.tint_panel(FB_CAR_POST, VIOLET, title="PASTE AS THE POST TEXT · ATTACH fb_cardetail_1080.png")
    b.band("POSTING PLAYBOOK — GET THE PHONE RINGING", ROSE)
    b.tint_panel(POST_TIPS, ROSE)
    return b.finish()


def build_truck_cleaning_brochure_router(*, db, require_role: Callable) -> APIRouter:
    router = APIRouter(prefix="/truck-cleaning", tags=["truck-cleaning-brochures"])
    guard = require_role("admin", "owner", "dispatcher")

    @router.get("/brochures/{doc_id}.pdf")
    async def brochure(doc_id: str, base: str = "", _=Depends(guard)) -> Response:
        builders = {"one-pager": (_one_pager, "Orisei_Truck_Cleaning_One_Pager"),
                    "business-card": (_business_card, "Orisei_Business_Card_Print"),
                    "ad-kit": (_ad_kit, "Orisei_Craigslist_Facebook_Ad_Kit"),
                    "cleaning-guide": (_guide_brochure, "Orisei_Cleaning_Guide_Brochure"),
                    "services": (_services_brochure, "Orisei_Services_Pricing_Brochure"),
                    "yard-promo": (_yard_promo_brochure, "Orisei_Yard_Manager_Package"),
                    "merch-package": (_merch_package, "Orisei_Crew_Apparel_Printer_Package")}
        if doc_id not in builders:
            raise HTTPException(status_code=404, detail="Unknown brochure")
        fn, name = builders[doc_id]
        content = fn(base.strip()[:200]) if doc_id in ("one-pager", "business-card") else fn()
        return Response(content=content, media_type="application/pdf",
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
                                     pdf_filename="Orisei_Yard_Manager_Package.pdf",
                                     bcc="oliver@oriseifreightsolutions.com") \
            if creds else {"sent": False, "error": "no_resend_creds"}
        status = "sent" if res.get("sent") else "recorded_no_key"
        from datetime import datetime, timezone
        await db.outbound_emails.insert_one({
            "to": to, "subject": subject, "html": html, "status": status, "error": res.get("error"),
            "kind": "tc_yard_promo", "company": company, "at": datetime.now(timezone.utc).isoformat()})
        return {"ok": True, "sent": res.get("sent", False), "status": status, "to": to}

    return router
