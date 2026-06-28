"""routes.orisei_docs — Brand-aware, beautiful PDF generators.

Renders Bill of Lading (BOL), Proof of Delivery (POD), compliance forms,
and markdown PDFs using the currently-active company brand:
  • Embedded brand logo (Orisei → Calafia + griffin · others → monogram · etc.)
  • Brand palette derived from `primary_color` + `accent_color`
  • Brand-specific footer copy (company name, address, contact email)
  • Brand-specific doc-id prefix (`ORI-`, `TEN-`, etc.)

When `brand` is omitted or empty, defaults to the Orisei heraldic theme so
legacy callers keep working unchanged.
"""
from __future__ import annotations

import io
import logging
import re as _re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

logger = logging.getLogger("tennant_tms.orisei_docs")

# Heraldic palette: deep azure + gold leaf accents (Queen Calafia tribute)
ORISEI_AZURE = colors.HexColor("#0E3A6B")
ORISEI_GOLD = colors.HexColor("#C9A24A")
ORISEI_GOLD_LIGHT = colors.HexColor("#E6CB85")
ORISEI_INK = colors.HexColor("#0B1320")
ORISEI_SLATE = colors.HexColor("#475569")
ORISEI_PAPER = colors.HexColor("#FBF8F0")

BRAND_ROOT = Path("/app/frontend/public/brand")
# Use downsampled PDF-optimized versions to keep generated PDFs under 300 KB.
LOGO_PATH = Path(__file__).resolve().parent / "_orisei_logo_pdf.png"
WORDMARK_PATH = Path(__file__).resolve().parent / "_orisei_wordmark_pdf.png"
LOGO_FALLBACK = BRAND_ROOT / "orisei_logo.png"
WORDMARK_FALLBACK = BRAND_ROOT / "orisei_wordmark.png"
if not LOGO_PATH.exists():
    LOGO_PATH = LOGO_FALLBACK
if not WORDMARK_PATH.exists():
    WORDMARK_PATH = WORDMARK_FALLBACK


# ---------- Brand-aware theme resolution ----------
def _hex(c: Optional[str], fallback: str) -> "colors.Color":
    """Safely parse a hex color string; fall back when missing/bad."""
    if not c or not isinstance(c, str):
        return colors.HexColor(fallback)
    c = c.strip()
    if not c.startswith("#"):
        c = "#" + c
    try:
        return colors.HexColor(c)
    except Exception:
        return colors.HexColor(fallback)


def _lighten(c: "colors.Color", amount: float = 0.45) -> "colors.Color":
    """Mix a color toward white. `amount` 0..1 (0=same, 1=white)."""
    r = c.red + (1.0 - c.red) * amount
    g = c.green + (1.0 - c.green) * amount
    b = c.blue + (1.0 - c.blue) * amount
    return colors.Color(r, g, b)


def _paper_for(accent: "colors.Color") -> "colors.Color":
    """Derive a soft 'paper' tone tinted toward the brand accent."""
    return colors.Color(min(1.0, accent.red * 0.07 + 0.97),
                        min(1.0, accent.green * 0.07 + 0.97),
                        min(1.0, accent.blue * 0.07 + 0.92))


def _brand_doc_prefix(brand: Optional[Dict[str, Any]]) -> str:
    if not brand:
        return "ORI"
    short = (brand.get("short_name") or brand.get("company_name") or "DOC").strip()
    # First 3 alpha chars, uppercase
    letters = _re.sub(r"[^A-Za-z]", "", short).upper()
    return (letters[:3] or "DOC")


def _brand_footer(brand: Optional[Dict[str, Any]]) -> str:
    """One-line footer with company + headquarters + contact email."""
    if not brand:
        company = "Orisei Freight Solutions LLC"
        hq = "Minneapolis · Saint Paul, MN"
        contact = "oliver@oriseifreight.com"
    else:
        company = brand.get("company_name") or "Orisei Freight Solutions LLC"
        hq = brand.get("headquarters") or "Minneapolis · Saint Paul, MN"
        contact_emails = brand.get("contact_emails") or {}
        contact = (
            contact_emails.get("ops")
            or contact_emails.get("primary")
            or brand.get("contact_email")
        )
        if not contact:
            # Orisei-specific: keep the founder's email as the canonical contact
            if brand.get("brand_id") in ("orisei", "orisei-freight"):
                contact = "oliver@oriseifreight.com"
            else:
                contact = _derive_contact_email(brand)
    return (f"{company}  ·  {hq}  ·  {contact}  ·  "
            f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")


def _derive_contact_email(brand: Dict[str, Any]) -> str:
    short = (brand.get("short_name") or "ops").strip()
    slug = _re.sub(r"[^a-z0-9]+", "", short.lower())[:20] or "ops"
    return f"ops@{slug}.com"


# Generated brand-monogram logos (per brand_id) — produced by
# backend/scripts/generate_brand_logos.py. Whenever a new brand is created
# via /api/branding, we regenerate this folder so PDFs immediately pick up
# the new brand's color-correct monogram.
GENERATED_LOGO_DIR = Path(__file__).resolve().parent / "_brand_logos"


def _brand_logo_path(brand: Optional[Dict[str, Any]]) -> Optional[Path]:
    """Returns the PDF logo path for the active brand. Orisei → Calafia
    griffin asset. Other brands → custom logo if `brand.logo_pdf_path` is
    set, else the generated monogram under `_brand_logos/{brand_id}.png`,
    else None so we fall back to an inline text monogram."""
    if not brand or brand.get("brand_id") in (None, "orisei", "orisei-freight"):
        return LOGO_PATH if LOGO_PATH.exists() else None
    # Explicit override on the brand doc takes precedence
    p = brand.get("logo_pdf_path") or brand.get("logo_local_path")
    if p:
        path = Path(p)
        if path.exists():
            return path
    # Fall back to the auto-generated monogram for this brand_id
    bid = brand.get("brand_id")
    if bid:
        gen = GENERATED_LOGO_DIR / f"{bid}.png"
        if gen.exists():
            return gen
    return None  # ultimately falls back to the in-PDF text monogram


def _brand_wordmark_path(brand: Optional[Dict[str, Any]]) -> Optional[Path]:
    if not brand or brand.get("brand_id") in (None, "orisei", "orisei-freight"):
        return WORDMARK_PATH if WORDMARK_PATH.exists() else None
    p = brand.get("wordmark_pdf_path") or brand.get("wordmark_local_path")
    if p and Path(p).exists():
        return Path(p)
    return None


def _theme(brand: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Resolve a brand to a complete theme dict for PDF rendering."""
    if not brand:
        return {
            "company": "Orisei Freight Solutions LLC",
            "short": "Orisei",
            "azure": ORISEI_AZURE,
            "gold": ORISEI_GOLD,
            "gold_light": ORISEI_GOLD_LIGHT,
            "ink": ORISEI_INK,
            "slate": ORISEI_SLATE,
            "paper": ORISEI_PAPER,
            "doc_prefix": "ORI",
            "footer": _brand_footer(None),
            "logo_path": LOGO_PATH if LOGO_PATH.exists() else None,
            "wordmark_path": WORDMARK_PATH if WORDMARK_PATH.exists() else None,
            "monogram": "O",
        }
    azure = _hex(brand.get("primary_color"), "#0E3A6B")
    gold = _hex(brand.get("accent_color"), "#C9A24A")
    gold_light = _lighten(gold, 0.45)
    company = brand.get("company_name") or "Company"
    short = brand.get("short_name") or company.split()[0]
    monogram = (brand.get("logo_letter") or short[:1] or "?").upper()
    return {
        "company": company,
        "short": short,
        "azure": azure,
        "gold": gold,
        "gold_light": gold_light,
        "ink": ORISEI_INK,
        "slate": ORISEI_SLATE,
        "paper": _paper_for(gold),
        "doc_prefix": _brand_doc_prefix(brand),
        "footer": _brand_footer(brand),
        "logo_path": _brand_logo_path(brand),
        "wordmark_path": _brand_wordmark_path(brand),
        "monogram": monogram,
    }


# ---------- Page decoration ----------
def _draw_heraldic_border(theme: Dict[str, Any], personalization: Optional[Dict[str, Any]] = None):
    """Returns a `onPage` callback that draws the brand-themed border + footer.

    When `personalization` is supplied (e.g. {"firm_name": "Greylock Partners",
    "contact_name": "Reid Hoffman", "prepared_date": "18 Feb 2026"}), a discreet
    "Confidential · Prepared for {firm} · {date}" banner is drawn at the top of
    every page and a faint diagonal watermark is laid behind the content.
    """
    azure = theme["azure"]
    gold = theme["gold"]
    gold_light = theme["gold_light"]
    slate = theme["slate"]
    footer_text = theme["footer"]
    p = personalization or None

    def _on_page(canvas: Canvas, doc: BaseDocTemplate) -> None:
        canvas.saveState()
        width, height = letter
        # Outer hairline frame
        canvas.setStrokeColor(gold)
        canvas.setLineWidth(1.2)
        canvas.rect(0.35 * inch, 0.35 * inch, width - 0.7 * inch, height - 0.7 * inch, stroke=1, fill=0)
        # Inner hairline frame
        canvas.setStrokeColor(gold_light)
        canvas.setLineWidth(0.4)
        canvas.rect(0.42 * inch, 0.42 * inch, width - 0.84 * inch, height - 0.84 * inch, stroke=1, fill=0)

        # Heraldic scroll-end corners (small filled diamond + flanking lines)
        def _flourish(cx: float, cy: float, size: float = 7) -> None:
            canvas.setFillColor(gold)
            canvas.setStrokeColor(gold)
            # Central diamond
            canvas.setLineWidth(0.8)
            path = canvas.beginPath()
            path.moveTo(cx, cy + size)
            path.lineTo(cx + size, cy)
            path.lineTo(cx, cy - size)
            path.lineTo(cx - size, cy)
            path.close()
            canvas.drawPath(path, stroke=0, fill=1)
            # Inner highlight
            canvas.setFillColor(gold_light)
            path2 = canvas.beginPath()
            path2.moveTo(cx, cy + size * 0.45)
            path2.lineTo(cx + size * 0.45, cy)
            path2.lineTo(cx, cy - size * 0.45)
            path2.lineTo(cx - size * 0.45, cy)
            path2.close()
            canvas.drawPath(path2, stroke=0, fill=1)

        margin = 0.55 * inch
        _flourish(margin, margin)
        _flourish(width - margin, margin)
        _flourish(margin, height - margin)
        _flourish(width - margin, height - margin)

        # Footer text
        canvas.setFillColor(slate)
        canvas.setFont("Helvetica-Oblique", 7)
        canvas.drawCentredString(width / 2, 0.22 * inch, footer_text)
        # Subtle brand azure tick to anchor the footer
        canvas.setFillColor(azure)
        canvas.circle(width / 2 - 4.0 * inch, 0.235 * inch, 1.2, stroke=0, fill=1)
        canvas.circle(width / 2 + 4.0 * inch, 0.235 * inch, 1.2, stroke=0, fill=1)

        # ---- Personalization overlay (only when supplied) ----
        if p:
            firm = (p.get("firm_name") or "").strip()
            contact = (p.get("contact_name") or "").strip()
            prepared = (p.get("prepared_date") or "").strip()
            if firm or contact or prepared:
                # Diagonal CONFIDENTIAL watermark behind content
                if firm:
                    canvas.saveState()
                    canvas.setFillColor(colors.Color(gold.red, gold.green, gold.blue, alpha=0.07))
                    canvas.translate(width / 2, height / 2)
                    canvas.rotate(35)
                    canvas.setFont("Helvetica-Bold", 72)
                    canvas.drawCentredString(0, 0, f"CONFIDENTIAL · {firm.upper()}")
                    canvas.restoreState()
                # Top "Prepared for" banner (above outer border)
                bits: List[str] = ["CONFIDENTIAL"]
                if firm:
                    bits.append(f"Prepared for {firm}")
                if contact:
                    bits.append(f"Attn: {contact}")
                if prepared:
                    bits.append(prepared)
                banner_text = "  ·  ".join(bits)
                canvas.setFillColor(azure)
                canvas.setFont("Helvetica-Bold", 7.5)
                canvas.drawCentredString(width / 2, height - 0.22 * inch, banner_text)
        canvas.restoreState()
    return _on_page


def _styles(theme: Dict[str, Any]) -> Dict[str, ParagraphStyle]:
    azure = theme["azure"]
    gold = theme["gold"]
    slate = theme["slate"]
    ink = theme["ink"]
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("title", parent=base["Title"], fontName="Helvetica-Bold",
                                fontSize=26, leading=30, textColor=azure,
                                alignment=2, spaceAfter=2),
        "subtitle": ParagraphStyle("subtitle", parent=base["Normal"], fontName="Helvetica-Oblique",
                                   fontSize=9, leading=11, textColor=gold,
                                   alignment=2, spaceAfter=2),
        "doc_id": ParagraphStyle("doc_id", parent=base["Normal"], fontName="Courier",
                                 fontSize=8, leading=10, textColor=slate,
                                 alignment=2),
        "section": ParagraphStyle("section", parent=base["Normal"], fontName="Helvetica-Bold",
                                  fontSize=8, leading=10, textColor=gold,
                                  spaceBefore=4, spaceAfter=4),
        "field_label": ParagraphStyle("flbl", parent=base["Normal"], fontName="Helvetica-Bold",
                                      fontSize=7, leading=9, textColor=slate),
        "field_value": ParagraphStyle("fval", parent=base["Normal"], fontName="Helvetica",
                                      fontSize=10, leading=13, textColor=ink),
        "body": ParagraphStyle("body", parent=base["Normal"], fontName="Helvetica",
                               fontSize=9, leading=12, textColor=ink),
        "legal": ParagraphStyle("legal", parent=base["Normal"], fontName="Helvetica",
                                fontSize=7, leading=9.5, textColor=slate),
    }


def _header(theme: Dict[str, Any], doc_type_title: str, doc_subtitle: str, doc_id: str) -> Table:
    s = _styles(theme)
    short = theme["short"]
    company = theme["company"]
    logo_path = theme["logo_path"]
    wordmark_path = theme["wordmark_path"]
    monogram = theme["monogram"]
    azure_hex = theme["azure"].hexval().replace("0x", "#")[:7] if hasattr(theme["azure"], "hexval") else "#0E3A6B"

    # Left: logo + wordmark stacked
    if logo_path and Path(logo_path).exists():
        logo = Image(str(logo_path), width=0.95 * inch, height=0.95 * inch)
    else:
        # Filled monogram disc fallback
        logo = Paragraph(
            f"<font color='{azure_hex}' size='30'><b>{monogram}</b></font>",
            ParagraphStyle("mono", alignment=1, leading=34),
        )

    if wordmark_path and Path(wordmark_path).exists():
        wordmark = Image(str(wordmark_path), width=2.2 * inch, height=0.55 * inch, kind="proportional")
    else:
        wordmark = Paragraph(f"<b>{short.upper()}</b>", s["section"])

    left_stack = Table([[logo], [wordmark]],
                      colWidths=[2.4 * inch],
                      rowHeights=[1.0 * inch, 0.6 * inch])
    left_stack.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))

    right_stack = [
        [Paragraph(doc_type_title, s["title"])],
        [Paragraph(doc_subtitle, s["subtitle"])],
        [Paragraph(f"Document ID: <font face='Courier' color='{azure_hex}'><b>{doc_id}</b></font>", s["doc_id"])],
        [Paragraph(f"Issued by {company} · {datetime.now(timezone.utc).strftime('%Y-%m-%d')}", s["doc_id"])],
    ]
    right_tbl = Table(right_stack, colWidths=[4.6 * inch])
    right_tbl.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))

    header = Table([[left_stack, right_tbl]], colWidths=[2.5 * inch, 4.7 * inch])
    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, -1), 1.5, theme["gold"]),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    return header


def _parties_block(theme: Dict[str, Any], shipper: Dict[str, str], consignee: Dict[str, str]) -> Table:
    s = _styles(theme)
    def _party(label: str, p: Dict[str, str]) -> List[Any]:
        return [
            Paragraph(label, s["section"]),
            Paragraph(f"<b>{p.get('name') or '—'}</b>", s["field_value"]),
            Paragraph(p.get("address") or "—", s["body"]),
            Paragraph(p.get("city_state_zip") or "—", s["body"]),
            Paragraph(f"<i>{p.get('contact') or ''}</i>", s["legal"]),
        ]

    shipper_cell = _party("SHIPPER", shipper)
    consignee_cell = _party("CONSIGNEE", consignee)

    parties = Table(
        [[shipper_cell, consignee_cell]],
        colWidths=[3.5 * inch, 3.5 * inch],
    )
    parties.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (-1, 0), theme["paper"]),
        ("BOX", (0, 0), (-1, -1), 0.4, theme["gold"]),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, theme["gold_light"]),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return parties


def _shipment_meta(theme: Dict[str, Any], rows: List[List[str]]) -> Table:
    s = _styles(theme)
    data = [[Paragraph(lbl.upper(), s["field_label"]) for lbl in [r[0] for r in rows]],
            [Paragraph(str(r[1] or "—"), s["field_value"]) for r in rows]]
    cols = max(len(rows), 1)
    width = 7.0 * inch
    col_widths = [width / cols] * cols
    t = Table(data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (-1, 0), theme["azure"]),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 7),
        ("BOX", (0, 0), (-1, -1), 0.4, theme["gold"]),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, theme["gold_light"]),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def _section_header(theme: Dict[str, Any], text: str) -> Paragraph:
    azure_hex = "#%02X%02X%02X" % (int(theme["azure"].red * 255),
                                    int(theme["azure"].green * 255),
                                    int(theme["azure"].blue * 255))
    return Paragraph(
        f"<font color='{azure_hex}'><b>◆</b></font>  "
        f"<font color='{azure_hex}'><b>{text.upper()}</b></font>",
        ParagraphStyle("sh", fontName="Helvetica-Bold", fontSize=10, leading=14,
                       textColor=theme["azure"], spaceBefore=10, spaceAfter=4),
    )


def _signature_block(theme: Dict[str, Any], *, signed_label: str = "Authorized Signature",
                     signed_name: Optional[str] = None,
                     signed_at: Optional[str] = None,
                     extra_line: Optional[str] = None) -> Table:
    s = _styles(theme)
    sig_line = "______________________________________"
    rows = [
        [Paragraph(f"<b>{signed_label}</b>", s["field_label"]),
         Paragraph("<b>PRINT NAME</b>", s["field_label"]),
         Paragraph("<b>DATE</b>", s["field_label"])],
        [Paragraph(sig_line, s["body"]),
         Paragraph(signed_name or sig_line, s["body"]),
         Paragraph(signed_at or "_________________", s["body"])],
    ]
    t = Table(rows, colWidths=[3.0 * inch, 2.4 * inch, 1.6 * inch])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 1), (-1, 1), 0.3, theme["slate"]),
    ]))
    return t


def _build_doc(buf: io.BytesIO, title: str, theme: Dict[str, Any],
               personalization: Optional[Dict[str, Any]] = None) -> BaseDocTemplate:
    doc = BaseDocTemplate(
        buf, pagesize=letter,
        leftMargin=0.6 * inch, rightMargin=0.6 * inch,
        topMargin=0.55 * inch, bottomMargin=0.55 * inch,
        title=title,
    )
    frame = Frame(0.6 * inch, 0.55 * inch,
                  letter[0] - 1.2 * inch, letter[1] - 1.1 * inch,
                  showBoundary=0)
    doc.addPageTemplates([PageTemplate(id="branded", frames=[frame],
                                       onPage=_draw_heraldic_border(theme, personalization))])
    return doc


# ---------- PUBLIC: Bill of Lading ----------
def build_bol_pdf(*, doc_id: str, booking: Dict[str, Any],
                  shipper: Dict[str, str], consignee: Dict[str, str],
                  user_name: Optional[str] = None,
                  brand: Optional[Dict[str, Any]] = None) -> bytes:
    """Render a branded Bill of Lading PDF using the currently-active brand.

    `booking` should contain: load_id, origin, destination, miles, equipment,
    commodity, weight_lbs, pieces, carrier_name, carrier_mc, rate_usd,
    pickup_date (iso), delivery_date (iso). Missing fields render as "—".
    `brand` is the active `company_brand` document; when omitted the Orisei
    theme is used.
    """
    theme = _theme(brand)
    s = _styles(theme)
    buf = io.BytesIO()
    doc = _build_doc(buf, f"{theme['short']} BOL · {doc_id}", theme)
    story: List[Any] = []

    story.append(_header(theme,
        "BILL OF LADING",
        "Straight Bill — Original · Non-Negotiable",
        doc_id,
    ))
    story.append(Spacer(1, 8))

    story.append(_section_header(theme, "Parties"))
    story.append(_parties_block(theme, shipper, consignee))
    story.append(Spacer(1, 10))

    story.append(_section_header(theme, "Shipment Information"))
    meta_rows = [
        ["Load ID", booking.get("load_id") or booking.get("booked_id") or "—"],
        ["Carrier", booking.get("carrier_name") or "—"],
        ["MC #", booking.get("carrier_mc") or "—"],
        ["Equipment", booking.get("equipment") or "—"],
        ["Miles", booking.get("miles") and f"{booking['miles']:,}" or "—"],
        ["Pickup", booking.get("pickup_date") or "—"],
        ["Delivery", booking.get("delivery_date") or "—"],
    ]
    story.append(_shipment_meta(theme, meta_rows))
    story.append(Spacer(1, 10))

    story.append(_section_header(theme, "Freight"))
    pieces = booking.get("pieces") or "—"
    weight = booking.get("weight_lbs") or booking.get("weight") or "—"
    if isinstance(weight, (int, float)):
        weight = f"{int(weight):,} lbs"
    commodity = booking.get("commodity") or "General Freight"
    freight_data = [
        ["#", "PIECES", "DESCRIPTION", "WEIGHT", "CLASS", "NMFC"],
        ["1", str(pieces), str(commodity), str(weight), "85", "—"],
    ]
    freight_tbl = Table(freight_data, colWidths=[0.4 * inch, 0.7 * inch,
                                                 3.4 * inch, 1.0 * inch,
                                                 0.7 * inch, 0.8 * inch])
    freight_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), theme["azure"]),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("GRID", (0, 0), (-1, -1), 0.3, theme["gold_light"]),
        ("BOX", (0, 0), (-1, -1), 0.5, theme["gold"]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(freight_tbl)
    story.append(Spacer(1, 8))

    # Special instructions / Hazmat / Notes
    notes = booking.get("notes") or "—"
    instructions = booking.get("special_instructions") or notes
    story.append(_section_header(theme, "Special Instructions"))
    story.append(Paragraph(str(instructions), s["body"]))
    story.append(Spacer(1, 8))

    # Charges
    story.append(_section_header(theme, "Freight Charges"))
    rate = booking.get("rate_usd") or booking.get("forecast_rate_usd") or 0
    try:
        rate_str = f"${float(rate):,.2f}" if rate else "—"
    except (TypeError, ValueError):
        rate_str = "—"
    charges_data = [
        ["LINEHAUL", "FUEL SURCHARGE", "ACCESSORIALS", "TOTAL"],
        [rate_str, "INCL.", "—", rate_str],
    ]
    charges_tbl = Table(charges_data, colWidths=[1.75 * inch] * 4)
    charges_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), theme["gold"]),
        ("TEXTCOLOR", (0, 0), (-1, 0), theme["ink"]),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 1), (-1, -1), 11),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("BOX", (0, 0), (-1, -1), 0.5, theme["azure"]),
        ("GRID", (0, 0), (-1, -1), 0.3, theme["azure"]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(charges_tbl)
    story.append(Spacer(1, 12))

    # Legal
    story.append(Paragraph(
        "RECEIVED, subject to the classifications and tariffs in effect on the date of "
        "issue, the property described above in apparent good order, except as noted "
        "(contents and condition of contents of packages unknown), marked, consigned, and "
        "destined as indicated above, which said carrier agrees to carry to said destination "
        "if on its own route, otherwise to deliver to another carrier on the route to said "
        "destination. It is mutually agreed as to each carrier of all or any of, said property "
        "over all or any portion of said route to destination and as to each party at any time "
        "interested in all or any of said property, that every service to be performed hereunder "
        "shall be subject to all bill of lading terms and conditions in the governing "
        "classification on the date of receipt by the carrier.",
        s["legal"],
    ))
    story.append(Spacer(1, 16))

    # Signatures
    story.append(_section_header(theme, "Signatures"))
    story.append(_signature_block(theme, signed_label="Shipper Representative",
                                  signed_name=user_name))
    story.append(Spacer(1, 6))
    story.append(_signature_block(theme, signed_label="Carrier / Driver Signature"))

    doc.build(story)
    return buf.getvalue()


# ---------- PUBLIC: Compliance Form ----------
def build_form_pdf(*, form_meta: Dict[str, Any], schema_rows: List[List[str]],
                   fields: Dict[str, Any], legal_text: str,
                   user_name: Optional[str] = None,
                   brand: Optional[Dict[str, Any]] = None) -> bytes:
    """Render any brokerage compliance form (BOC-3, BMC-84, Rate Confirmation,
    Carrier Packet, NOA, etc.) using the same heraldic template as the BOL
    and POD — branded with the currently-active company.
    """
    theme = _theme(brand)
    s = _styles(theme)
    buf = io.BytesIO()
    title = form_meta.get("name") or "Compliance Form"
    doc_id = f"{theme['doc_prefix']}-{form_meta.get('id','FORM').upper()}-{__import__('uuid').uuid4().hex[:8].upper()}"
    doc = _build_doc(buf, f"{theme['short']} {title} · {doc_id}", theme)
    story: List[Any] = []

    # Header
    subtitle = form_meta.get("category") or "Compliance Document"
    if form_meta.get("fmcsa"):
        subtitle = f"{subtitle} · FMCSA-Required"
    story.append(_header(theme, title.upper(), subtitle, doc_id))
    story.append(Spacer(1, 8))

    # Generated-by note
    gen_note = (f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
                f"{' · by ' + user_name if user_name else ''}")
    story.append(Paragraph(f"<font size='8' color='#64748B'>{gen_note}</font>", s["body"]))
    story.append(Spacer(1, 8))

    # Field table
    story.append(_section_header(theme, "Form Fields"))
    rows: List[List[Any]] = [[
        Paragraph("<b>FIELD</b>", s["field_label"]),
        Paragraph("<b>VALUE</b>", s["field_label"]),
    ]]
    for label, key in schema_rows:
        val = str(fields.get(key, "") or "________________________________")
        rows.append([
            Paragraph(label, s["field_label"]),
            Paragraph(val, s["field_value"]),
        ])
    field_tbl = Table(rows, colWidths=[2.2 * inch, 4.8 * inch])
    field_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), theme["azure"]),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [theme["paper"], colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.3, theme["gold_light"]),
        ("BOX", (0, 0), (-1, -1), 0.5, theme["gold"]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(field_tbl)
    story.append(Spacer(1, 14))

    # Acknowledgement / legal text
    story.append(_section_header(theme, "Acknowledgement & Signature"))
    story.append(Paragraph(legal_text, s["legal"]))
    story.append(Spacer(1, 18))

    # Signature block
    story.append(_signature_block(theme,
        signed_label="Authorized Signature",
        signed_name=user_name,
    ))
    story.append(Spacer(1, 12))

    # Footer doc-id stamp
    azure_hex = "#%02X%02X%02X" % (int(theme["azure"].red * 255),
                                    int(theme["azure"].green * 255),
                                    int(theme["azure"].blue * 255))
    story.append(Paragraph(
        f"<font face='Courier' color='{azure_hex}' size='7'><b>DOC ID: {doc_id}</b></font> "
        f"<font size='7' color='#94A3B8'>· Generated by the {theme['company']} TMS Brokerage module</font>",
        s["legal"],
    ))

    doc.build(story)
    return buf.getvalue()


# ---------- PUBLIC: Branded Markdown / Business Plan ----------
def build_branded_markdown_pdf(md_text: str, *, title: str = "Business Plan",
                               subtitle: Optional[str] = None,
                               doc_id: Optional[str] = None,
                               brand: Optional[Dict[str, Any]] = None,
                               personalization: Optional[Dict[str, Any]] = None) -> bytes:
    """Render a markdown document (business plan, quote, rate confirmation,
    invoice, etc.) using the active brand's heraldic template.

    Visual upgrades over a plain markdown renderer:
      • H2 headings render as branded ◆ section headers (matches BOL/POD).
      • Adjacent ``- **Label**: value`` bullets coalesce into a boxed
        2-column shipment-meta table (azure label header, paper rows, gold
        border) — gives quotes/rate-cons the same visual weight as a BOL.
      • Lines starting with ``## Total`` (or ``**Total**``) render as a
        gold-banner callout matching the BOL "Freight Charges" treatment.
      • Founder/contact signature lines from the markdown render as a real
        signature block table at the bottom when detected.

    Pass `personalization={"firm_name": "...", "contact_name": "...",
    "prepared_date": "..."}` to stamp every page with a top
    "Confidential · Prepared for {firm}" banner + diagonal watermark.
    """
    theme = _theme(brand)
    s = _styles(theme)
    base_styles = getSampleStyleSheet()
    md_styles = {
        "h1":  ParagraphStyle("h1",  parent=base_styles["Heading1"], fontSize=18, leading=22,
                              textColor=theme["azure"], spaceBefore=10, spaceAfter=8),
        "h3":  ParagraphStyle("h3",  parent=base_styles["Heading3"], fontSize=11, leading=15,
                              textColor=theme["azure"], spaceBefore=8, spaceAfter=4,
                              fontName="Helvetica-Bold"),
        "p":   ParagraphStyle("p",   parent=base_styles["BodyText"], fontSize=9.5, leading=13,
                              textColor=theme["ink"], spaceAfter=4),
        "li":  ParagraphStyle("li",  parent=base_styles["BodyText"], fontSize=9.5, leading=13,
                              leftIndent=14, bulletIndent=2, textColor=theme["ink"], spaceAfter=2),
        "quo": ParagraphStyle("quo", parent=base_styles["BodyText"], fontSize=9.5, leading=13,
                              leftIndent=14, textColor=theme["slate"], italic=True, spaceAfter=4),
    }
    buf = io.BytesIO()
    final_doc_id = doc_id or f"{theme['doc_prefix']}-{__import__('uuid').uuid4().hex[:10].upper()}"
    doc_pdf = _build_doc(buf, title, theme, personalization)
    story: List[Any] = []
    story.append(_header(theme, title.upper(), subtitle or "Founder Business Plan", final_doc_id))
    story.append(Spacer(1, 12))

    def _inline(text: str) -> str:
        text = _re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
        text = _re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<i>\1</i>", text)
        text = _re.sub(r"`([^`]+?)`", r'<font face="Courier">\1</font>', text)
        text = (text.replace("&", "&amp;")
                    .replace("<b>", "\x00b\x00").replace("</b>", "\x00B\x00")
                    .replace("<i>", "\x00i\x00").replace("</i>", "\x00I\x00"))
        text = text.replace("<", "&lt;").replace(">", "&gt;")
        text = (text.replace("\x00b\x00", "<b>").replace("\x00B\x00", "</b>")
                    .replace("\x00i\x00", "<i>").replace("\x00I\x00", "</i>"))
        return text

    # Helper: render a 2-column "label / value" boxed table mirroring the
    # BOL's `_shipment_meta` aesthetic. Falls back to plain bullets if pairs
    # list is empty.
    def _label_value_table(pairs: List[tuple]) -> Optional[Table]:
        if not pairs:
            return None
        rows: List[List[Any]] = [[
            Paragraph("<b>FIELD</b>", s["field_label"]),
            Paragraph("<b>DETAIL</b>", s["field_label"]),
        ]]
        for label, value in pairs:
            rows.append([
                Paragraph(label.upper(), s["field_label"]),
                Paragraph(value or "—", s["field_value"]),
            ])
        t = Table(rows, colWidths=[2.0 * inch, 5.0 * inch])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), theme["azure"]),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 7.5),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [theme["paper"], colors.white]),
            ("BOX", (0, 0), (-1, -1), 0.5, theme["gold"]),
            ("INNERGRID", (0, 0), (-1, -1), 0.3, theme["gold_light"]),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        return t

    # Helper: gold-banner callout used for "Total / Grand Total / Amount Due".
    def _gold_callout(text: str) -> Table:
        banner = Table([[Paragraph(
            f"<font color='{theme['ink'].hexval().replace('0x','#')[:7]}' size='14'><b>{text}</b></font>",
            ParagraphStyle("cb", alignment=1, leading=18)
        )]], colWidths=[7.0 * inch])
        banner.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), theme["gold"]),
            ("BOX", (0, 0), (-1, -1), 1.2, theme["azure"]),
            ("TOPPADDING", (0, 0), (-1, -1), 12),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))
        return banner

    # Pattern for "- **Label**: value" bullets (used to coalesce into a table)
    LV_PATTERN = _re.compile(r"^[-*+]\s+\*\*([^*]+?)\*\*\s*[:：]\s*(.+)$")
    TOTAL_PATTERN = _re.compile(r"^##\s+(.*\bTotal\b.*)$", _re.IGNORECASE)

    lines = md_text.splitlines()
    i = 0
    skipped_first_h1 = False
    while i < len(lines):
        line = lines[i].rstrip()
        stripped = line.strip()
        if not stripped or _re.fullmatch(r"-{3,}|={3,}|\*{3,}", stripped):
            story.append(Spacer(1, 4)); i += 1; continue
        # Inline image: ![alt](path)  — path can be local file or absolute
        m_img = _re.match(r"^!\[([^\]]*)\]\(([^)]+)\)$", stripped)
        if m_img:
            from reportlab.platypus import Image as _Img
            from pathlib import Path as _Pp
            img_path = m_img.group(2)
            p = _Pp(img_path)
            if p.exists():
                try:
                    story.append(_Img(str(p), width=5.2 * inch,
                                       height=2.9 * inch, kind="proportional"))
                    story.append(Spacer(1, 4))
                    if m_img.group(1):
                        story.append(Paragraph(
                            f"<i>{_inline(m_img.group(1))}</i>", md_styles["quo"]))
                    story.append(Spacer(1, 6))
                except Exception:                                # noqa: BLE001
                    story.append(Paragraph(
                        f"<i>[image: {m_img.group(1)}]</i>", md_styles["quo"]))
            else:
                story.append(Paragraph(
                    f"<i>[image not found: {img_path}]</i>", md_styles["quo"]))
            i += 1; continue
        if "|" in stripped and i + 1 < len(lines) and _re.match(r"\|?\s*[:-]+\s*\|", lines[i + 1]):
            j = i
            while j < len(lines) and lines[j].strip().startswith("|"):
                j += 1
            story.append(Paragraph("<i>[Table omitted — see full plan online]</i>", md_styles["quo"]))
            i = j; continue
        if stripped.startswith("### "):
            story.append(Paragraph(_inline(stripped[4:]), md_styles["h3"])); i += 1; continue
        # H2 → gold callout if it mentions Total, else branded ◆ section header
        m_total = TOTAL_PATTERN.match(stripped)
        if m_total:
            # Strip markdown emphasis from callout text
            callout = _re.sub(r"\*+", "", m_total.group(1)).strip()
            story.append(Spacer(1, 4))
            story.append(_gold_callout(callout))
            story.append(Spacer(1, 6))
            i += 1; continue
        if stripped.startswith("## "):
            story.append(_section_header(theme, stripped[3:].strip()))
            i += 1; continue
        if stripped.startswith("# "):
            if not skipped_first_h1:
                skipped_first_h1 = True; i += 1; continue
            story.append(Paragraph(_inline(stripped[2:]), md_styles["h1"])); i += 1; continue
        if stripped.startswith("> "):
            story.append(Paragraph(_inline(stripped[2:]), md_styles["quo"])); i += 1; continue
        # Coalesce consecutive "- **Label**: value" lines into a branded table.
        m_lv = LV_PATTERN.match(stripped)
        if m_lv:
            pairs: List[tuple] = []
            j = i
            while j < len(lines):
                s_j = lines[j].strip()
                m_j = LV_PATTERN.match(s_j)
                if not m_j:
                    break
                pairs.append((m_j.group(1).strip(), _inline(m_j.group(2).strip())))
                j += 1
            if len(pairs) >= 2:
                tbl = _label_value_table(pairs)
                if tbl is not None:
                    story.append(tbl)
                    story.append(Spacer(1, 6))
                i = j; continue
            # Single label/value pair → render as one-row table for consistency.
            tbl = _label_value_table(pairs)
            if tbl is not None:
                story.append(tbl)
                story.append(Spacer(1, 4))
                i = j; continue
        m = _re.match(r"^[-*+]\s+(.+)$", stripped)
        if m:
            story.append(Paragraph(_inline(m.group(1)), md_styles["li"], bulletText="•"))
            i += 1; continue
        m = _re.match(r"^(\d+)\.\s+(.+)$", stripped)
        if m:
            story.append(Paragraph(_inline(m.group(2)), md_styles["li"], bulletText=f"{m.group(1)}."))
            i += 1; continue
        story.append(Paragraph(_inline(stripped), md_styles["p"]))
        i += 1

    doc_pdf.build(story)
    return buf.getvalue()


def build_pod_pdf(*, doc_id: str, booking: Dict[str, Any],
                  shipper: Dict[str, str], consignee: Dict[str, str],
                  delivery: Dict[str, Any],
                  user_name: Optional[str] = None,
                  brand: Optional[Dict[str, Any]] = None) -> bytes:
    """Render a branded Proof of Delivery PDF using the active brand."""
    theme = _theme(brand)
    s = _styles(theme)
    buf = io.BytesIO()
    doc = _build_doc(buf, f"{theme['short']} POD · {doc_id}", theme)
    story: List[Any] = []

    story.append(_header(theme,
        "PROOF OF DELIVERY",
        "Customer Receipt · Final Mile Confirmation",
        doc_id,
    ))
    story.append(Spacer(1, 8))

    story.append(_section_header(theme, "Parties"))
    story.append(_parties_block(theme, shipper, consignee))
    story.append(Spacer(1, 10))

    story.append(_section_header(theme, "Shipment Reference"))
    ref_rows = [
        ["Load ID", booking.get("load_id") or booking.get("booked_id") or "—"],
        ["BOL #", booking.get("bol_no") or doc_id.replace("POD", "BOL")],
        ["Carrier", booking.get("carrier_name") or "—"],
        ["MC #", booking.get("carrier_mc") or "—"],
        ["Origin", booking.get("origin") or "—"],
        ["Destination", booking.get("destination") or "—"],
    ]
    story.append(_shipment_meta(theme, ref_rows))
    story.append(Spacer(1, 10))

    story.append(_section_header(theme, "Delivery Confirmation"))
    delivered_at = delivery.get("delivered_at") or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    pieces_rcv = delivery.get("pieces_received") or booking.get("pieces") or "—"
    weight_rcv = delivery.get("weight_received") or booking.get("weight_lbs") or "—"
    if isinstance(weight_rcv, (int, float)):
        weight_rcv = f"{int(weight_rcv):,} lbs"
    condition = delivery.get("condition") or "Received in apparent good order — no visible damage."
    seal = "INTACT" if delivery.get("seal_intact", True) else "BROKEN"
    delivery_rows = [
        ["Delivered At", delivered_at],
        ["Pieces Received", str(pieces_rcv)],
        ["Weight Received", str(weight_rcv)],
        ["Seal Status", seal],
    ]
    story.append(_shipment_meta(theme, delivery_rows))
    story.append(Spacer(1, 8))

    story.append(Paragraph("<b>Condition on arrival:</b>", s["field_label"]))
    story.append(Paragraph(str(condition), s["body"]))
    story.append(Spacer(1, 6))

    exceptions = delivery.get("exceptions") or []
    if isinstance(exceptions, str):
        exceptions = [exceptions] if exceptions else []
    story.append(Paragraph("<b>Exceptions / OS&D Notes:</b>", s["field_label"]))
    if exceptions:
        for e in exceptions:
            story.append(Paragraph(f"• {e}", s["body"]))
    else:
        story.append(Paragraph("None — clean delivery.", s["body"]))
    story.append(Spacer(1, 12))

    # Highlighted "DELIVERED" stamp-style banner
    banner_data = [[
        Paragraph(
            f"<font color='#FBF8F0' size='16'><b>◆  DELIVERED  ◆</b></font><br/>"
            f"<font color='#E6CB85' size='8'>{delivered_at}</font>",
            ParagraphStyle("ban", fontName="Helvetica-Bold", alignment=1,
                           textColor=colors.white)
        )
    ]]
    banner = Table(banner_data, colWidths=[7.0 * inch])
    banner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), theme["azure"]),
        ("BOX", (0, 0), (-1, -1), 1.5, theme["gold"]),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    story.append(banner)
    story.append(Spacer(1, 16))

    # Legal
    story.append(Paragraph(
        "By signing below, the consignee acknowledges receipt of the freight described above "
        "in the apparent condition noted. Any claims for damage, loss, or shortage must be "
        f"submitted in writing to {theme['company']} within nine (9) months of delivery "
        "in accordance with 49 CFR § 370 and the National Motor Freight Classification. "
        "Concealed-damage claims must be filed within fifteen (15) calendar days.",
        s["legal"],
    ))
    story.append(Spacer(1, 14))

    story.append(_section_header(theme, "Signatures"))
    story.append(_signature_block(theme,
        signed_label="Consignee / Receiver",
        signed_name=delivery.get("received_by"),
        signed_at=delivered_at,
    ))
    story.append(Spacer(1, 6))
    story.append(_signature_block(theme,
        signed_label="Driver / Carrier",
        signed_name=delivery.get("driver_name") or booking.get("driver_name"),
    ))
    story.append(Spacer(1, 6))
    story.append(_signature_block(theme,
        signed_label=f"{theme['short']} Operator",
        signed_name=user_name,
    ))

    # Dock photos (optional) — up to 3 thumbnails on a second page
    photos = delivery.get("photos") or []
    if photos:
        from reportlab.platypus import PageBreak
        story.append(PageBreak())
        story.append(_header(theme,
            "DELIVERY PHOTOS",
            f"Dock photos — {len(photos)} attached",
            doc_id,
        ))
        story.append(Spacer(1, 12))
        story.append(_section_header(theme, "Photo evidence captured at delivery"))
        story.append(Spacer(1, 8))
        cells: List[Any] = []
        for p in photos[:3]:
            try:
                img = Image(io.BytesIO(p["bytes"]), width=2.2 * inch, height=2.2 * inch, kind="proportional")
                cap = Paragraph(
                    f"<font size='7' color='#475569'>{p.get('caption') or p.get('filename') or 'Photo'}</font>",
                    s["legal"],
                )
                cell = Table([[img], [cap]], colWidths=[2.3 * inch])
                cell.setStyle(TableStyle([
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("BOX", (0, 0), (-1, 0), 0.5, theme["gold"]),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]))
                cells.append(cell)
            except Exception:                                        # noqa: BLE001
                logger.exception("Failed to embed delivery photo")
        if cells:
            while len(cells) < 3:
                cells.append(Paragraph("", s["body"]))
            grid = Table([cells], colWidths=[2.4 * inch, 2.4 * inch, 2.4 * inch])
            grid.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
            story.append(grid)

    doc.build(story)
    return buf.getvalue()
