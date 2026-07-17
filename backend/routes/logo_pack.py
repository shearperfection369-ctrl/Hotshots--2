"""routes.logo_pack — Official Orisei logo & brand pack PDF (launch edition).

Six-page print-ready pack: cover, Queen Califia seal, seal variations,
wordmark + palette, hoodie mockups, headwear mockups.
"""
import io
from pathlib import Path

from PIL import Image
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas

W, H = letter

AZURE = colors.HexColor("#0E3A6B")
NAVY_DEEP = colors.HexColor("#0B1320")
GOLD = colors.HexColor("#C9A24A")
GOLD_LIGHT = colors.HexColor("#E6CB85")
PAPER = colors.HexColor("#FBF8F0")
SLATE = colors.HexColor("#475569")
WHITE = colors.white

ROUTES = Path(__file__).resolve().parent
PACK = ROUTES / "_brand_pack"
SEAL_PRIMARY = ROUTES / "_orisei_logo_pdf.png"
WORDMARK = ROUTES / "_orisei_wordmark_pdf.png"


def _img(path: Path, jpeg: bool = True) -> ImageReader:
    im = Image.open(path).convert("RGB")
    buf = io.BytesIO()
    if jpeg:
        im.save(buf, "JPEG", quality=86)
    else:
        im.save(buf, "PNG")
    buf.seek(0)
    return ImageReader(buf)


def _footer(c: Canvas, page: int, total: int, dark: bool = False):
    c.setFont("Helvetica", 7.5)
    c.setFillColor(GOLD_LIGHT if dark else SLATE)
    c.drawString(40, 24, "Orisei Freight Solutions LLC · Official Logo & Brand Pack · Launch Edition 2026")
    c.drawRightString(W - 40, 24, f"Page {page} of {total}")


def _page_head(c: Canvas, kicker: str, title: str):
    c.setFillColor(PAPER)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setFillColor(AZURE)
    c.rect(0, H - 8, W, 8, fill=1, stroke=0)
    c.setFillColor(GOLD)
    c.rect(0, H - 12, W, 4, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 8.5)
    c.setFillColor(GOLD)
    c.drawString(40, H - 44, kicker.upper())
    c.setFont("Times-Bold", 24)
    c.setFillColor(AZURE)
    c.drawString(40, H - 70, title)
    c.setStrokeColor(GOLD)
    c.setLineWidth(1.2)
    c.line(40, H - 82, W - 40, H - 82)


def _panel(c: Canvas, x, y, w, h, fill, stroke=None):
    c.setFillColor(fill)
    if stroke:
        c.setStrokeColor(stroke)
        c.setLineWidth(1)
    c.roundRect(x, y, w, h, 10, fill=1, stroke=1 if stroke else 0)


def _caption(c: Canvas, cx, y, title, sub, dark=False):
    c.setFont("Helvetica-Bold", 9.5)
    c.setFillColor(GOLD_LIGHT if dark else AZURE)
    c.drawCentredString(cx, y, title)
    c.setFont("Helvetica", 7.5)
    c.setFillColor(colors.HexColor("#9FB4CC") if dark else SLATE)
    c.drawCentredString(cx, y - 12, sub)


def _cover(c: Canvas):
    c.setFillColor(NAVY_DEEP)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setFillColor(AZURE)
    c.rect(0, H - 260, W, 260, fill=1, stroke=0)
    c.setStrokeColor(GOLD)
    c.setLineWidth(2)
    c.rect(28, 28, W - 56, H - 56, fill=0, stroke=1)
    c.setLineWidth(0.6)
    c.rect(36, 36, W - 72, H - 72, fill=0, stroke=1)

    if SEAL_PRIMARY.exists():
        s = 300
        c.drawImage(ImageReader(str(SEAL_PRIMARY)), (W - s) / 2, H - 480, s, s,
                    mask="auto", preserveAspectRatio=True)

    c.setFont("Times-Bold", 34)
    c.setFillColor(GOLD_LIGHT)
    c.drawCentredString(W / 2, 260, "ORISEI FREIGHT SOLUTIONS")
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(WHITE)
    c.drawCentredString(W / 2, 236, "OFFICIAL LOGO & BRAND PACK")
    c.setStrokeColor(GOLD)
    c.setLineWidth(1)
    c.line(W / 2 - 110, 222, W / 2 + 110, 222)
    c.setFont("Helvetica", 9.5)
    c.setFillColor(GOLD_LIGHT)
    c.drawCentredString(W / 2, 202, "The Queen Califia Seal · Launch Edition · 2026")
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.HexColor("#9FB4CC"))
    c.drawCentredString(W / 2, 120, "Minneapolis · Saint Paul · Brooklyn Park · Minnesota")
    c.drawCentredString(W / 2, 106, "Prepared for the official launch of Orisei Freight Solutions LLC")
    c.showPage()


def _page_seal(c: Canvas, page, total):
    _page_head(c, "01 · The Mark", "The Queen Califia Seal")
    c.setFont("Helvetica", 9.5)
    c.setFillColor(SLATE)
    text = [
        "Queen Califia — the legendary warrior queen of California — rides the Orisei griffin,",
        "sword raised. She is the guardian of every load we move: vigilant, sovereign, and",
        "unbought. The griffin joins the eagle's sight with the lion's strength — visibility",
        "and muscle, the two promises of a great freight broker.",
    ]
    y = H - 106
    for ln in text:
        c.drawString(40, y, ln)
        y -= 14

    _panel(c, 40, 210, W - 80, 380, NAVY_DEEP, GOLD)
    if SEAL_PRIMARY.exists():
        s = 320
        c.drawImage(ImageReader(str(SEAL_PRIMARY)), (W - s) / 2, 240, s, s,
                    mask="auto", preserveAspectRatio=True)
    _caption(c, W / 2, 226, "PRIMARY SEAL — GOLD ON NAVY", "Default mark for decks, documents, apparel and signage", dark=True)

    y = 186
    specs = [
        ("MINIMUM SIZE", "0.75 in print · 48 px digital"),
        ("CLEAR SPACE", "Keep 25% of seal width clear on all sides"),
        ("BACKGROUNDS", "Navy #0E3A6B, ink #0B1320, or white only"),
    ]
    cw = (W - 80 - 24) / 3
    for i, (t, s_) in enumerate(specs):
        x = 40 + i * (cw + 12)
        _panel(c, x, y - 60, cw, 60, WHITE, GOLD)
        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(GOLD)
        c.drawString(x + 12, y - 22, t)
        c.setFont("Helvetica", 8)
        c.setFillColor(SLATE)
        c.drawString(x + 12, y - 38, s_)
    _footer(c, page, total)
    c.showPage()


def _page_variations(c: Canvas, page, total):
    _page_head(c, "02 · Versions", "Seal Variations")
    cw = (W - 80 - 24) / 2
    y_top = H - 110

    _panel(c, 40, y_top - 300, cw, 300, WHITE, GOLD)
    p = PACK / "seal_gold_light.png"
    if p.exists():
        c.drawImage(_img(p), 40 + (cw - 230) / 2, y_top - 265, 230, 230, preserveAspectRatio=True)
    _caption(c, 40 + cw / 2, y_top - 278, "GOLD ON LIGHT", "Letterhead, invoices, light decks")

    _panel(c, 52 + cw, y_top - 300, cw, 300, WHITE, AZURE)
    p = PACK / "seal_navy_mono.png"
    if p.exists():
        c.drawImage(_img(p), 52 + cw + (cw - 230) / 2, y_top - 265, 230, 230, preserveAspectRatio=True)
    _caption(c, 52 + cw + cw / 2, y_top - 278, "NAVY MONO — OFFICIAL STAMP", "Contracts, BOLs, notary-style embossing")

    y = y_top - 330
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(AZURE)
    c.drawString(40, y, "Never do this")
    c.setFont("Helvetica", 8.5)
    c.setFillColor(SLATE)
    donts = [
        "· Do not recolor the seal outside the gold / navy / mono palette",
        "· Do not stretch, rotate, outline, or add drop shadows",
        "· Do not crop Queen Califia or the griffin out of the ring",
        "· Do not place the gold seal on busy photography without a navy scrim",
    ]
    for d in donts:
        y -= 14
        c.drawString(40, y, d)
    _footer(c, page, total)
    c.showPage()


def _page_wordmark(c: Canvas, page, total):
    _page_head(c, "03 · Type & Color", "Wordmark & Palette")
    _panel(c, 40, H - 300, W - 80, 170, WHITE, GOLD)
    if WORDMARK.exists():
        c.drawImage(ImageReader(str(WORDMARK)), 70, H - 290, W - 140, 150,
                    mask="auto", preserveAspectRatio=True)
    _caption(c, W / 2, H - 316, "PRIMARY WORDMARK", "Griffin-crested O · serif capitals · letter-spaced descriptor")

    y = H - 360
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(AZURE)
    c.drawString(40, y, "Brand palette")
    swatches = [
        ("ORISEI AZURE", "#0E3A6B", AZURE, WHITE),
        ("DEEP INK", "#0B1320", NAVY_DEEP, WHITE),
        ("CALIFIA GOLD", "#C9A24A", GOLD, NAVY_DEEP),
        ("GOLD LIGHT", "#E6CB85", GOLD_LIGHT, NAVY_DEEP),
        ("PAPER", "#FBF8F0", PAPER, AZURE),
    ]
    sw = (W - 80 - 4 * 10) / 5
    for i, (name, hexv, col, txt) in enumerate(swatches):
        x = 40 + i * (sw + 10)
        c.setFillColor(col)
        c.setStrokeColor(colors.HexColor("#D8D2C2"))
        c.roundRect(x, y - 90, sw, 74, 8, fill=1, stroke=1)
        c.setFont("Helvetica-Bold", 7)
        c.setFillColor(txt)
        c.drawString(x + 8, y - 40, name)
        c.setFont("Helvetica", 7)
        c.drawString(x + 8, y - 52, hexv)

    y -= 124
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(AZURE)
    c.drawString(40, y, "Typography")
    c.setFont("Helvetica", 8.5)
    c.setFillColor(SLATE)
    for ln in [
        "Display — Cormorant Garamond / Times-style serif, bold, tracked capitals (ORISEI).",
        "Descriptor — geometric sans or mono caps, wide letter-spacing (FREIGHT SOLUTIONS).",
        "Body — Helvetica / Inter-class sans for documents, quotes, and system UI.",
    ]:
        y -= 14
        c.drawString(40, y, ln)
    _footer(c, page, total)
    c.showPage()


def _mockup_page(c: Canvas, page, total, kicker, title, items, note):
    _page_head(c, kicker, title)
    cw = (W - 80 - 24) / 2
    y_top = H - 104
    for i, (fname, cap, sub) in enumerate(items):
        x = 40 + i * (cw + 12)
        _panel(c, x, y_top - 330, cw, 330, WHITE, GOLD)
        p = PACK / fname
        if p.exists():
            c.drawImage(_img(p), x + (cw - 250) / 2, y_top - 300, 250, 290, preserveAspectRatio=True)
    for i, (fname, cap, sub) in enumerate(items):
        x = 40 + i * (cw + 12)
        _caption(c, x + cw / 2, y_top - 318, cap, sub)

    y = y_top - 366
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(AZURE)
    c.drawString(40, y, "Production notes")
    c.setFont("Helvetica", 8.5)
    c.setFillColor(SLATE)
    for ln in note:
        y -= 14
        c.drawString(40, y, ln)
    _footer(c, page, total)
    c.showPage()


def build_logo_pack_pdf() -> bytes:
    buf = io.BytesIO()
    c = Canvas(buf, pagesize=letter)
    c.setTitle("Orisei Freight Solutions · Official Logo & Brand Pack")
    total = 6
    _cover(c)
    _page_seal(c, 2, total)
    _page_variations(c, 3, total)
    _page_wordmark(c, 4, total)
    _mockup_page(
        c, 5, total, "04 · Apparel", "Hoodie Program",
        [
            ("hoodie_front.png", "PULLOVER — FRONT", "Large chest seal + wordmark underline"),
            ("hoodie_back.png", "ZIP HOODIE — BACK", "ORISEI back-print with seal anchor"),
        ],
        [
            "· Garment: premium heavyweight fleece in Orisei Navy (nearest stock: Navy Blazer / PMS 533C).",
            "· Print: Califia Gold (PMS 465C) single-color screen print or gold-foil transfer.",
            "· Front seal 9–10 in wide on chest; back wordmark 11 in wide across shoulders.",
        ],
    )
    _mockup_page(
        c, 6, total, "05 · Headwear", "Cap & Beanie Program",
        [
            ("hat_cap.png", "STRUCTURED CAP", "Gold embroidered seal, front panel"),
            ("beanie_trucker.png", "TRUCKER + BEANIE", "Seal patch snapback · woven-label knit"),
        ],
        [
            "· Embroidery: metallic gold thread (Madeira 4). Seal 2.5 in diameter on front panel.",
            "· Trucker: navy crown / white mesh with woven seal patch; Beanie: woven gold label on fold.",
            "· Driver giveaway spec: cap + beanie bundle for carrier partner onboarding kits.",
        ],
    )
    c.save()
    return buf.getvalue()
