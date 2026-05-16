"""routes.orisei_docs — Brand-aware, beautiful PDF generators for Orisei.

Renders the Bill of Lading (BOL) and Proof of Delivery (POD) with:
  • Embedded Orisei logo (Queen Calafia + griffin) and wordmark
  • Heraldic gold/azure palette inspired by the California flag's grizzly + crown
  • Decorative scroll-end corners and gold double-rule border
  • Clean parties / freight / signatures structure

Used by `routes/brokerage.py` for the load-board "Generate BOL" and
"Email POD" flows. Pure utility module — no FastAPI router needed.
"""
from __future__ import annotations

import io
import logging
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


# ---------- Page decoration ----------
def _draw_heraldic_border(canvas: Canvas, doc: BaseDocTemplate) -> None:
    """Decorative gold border + heraldic scroll-end corner flourishes."""
    canvas.saveState()
    width, height = letter
    # Outer hairline frame
    canvas.setStrokeColor(ORISEI_GOLD)
    canvas.setLineWidth(1.2)
    canvas.rect(0.35 * inch, 0.35 * inch, width - 0.7 * inch, height - 0.7 * inch, stroke=1, fill=0)
    # Inner hairline frame
    canvas.setStrokeColor(ORISEI_GOLD_LIGHT)
    canvas.setLineWidth(0.4)
    canvas.rect(0.42 * inch, 0.42 * inch, width - 0.84 * inch, height - 0.84 * inch, stroke=1, fill=0)

    # Heraldic scroll-end corners (small filled diamond + flanking lines)
    def _flourish(cx: float, cy: float, size: float = 7) -> None:
        canvas.setFillColor(ORISEI_GOLD)
        canvas.setStrokeColor(ORISEI_GOLD)
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
        canvas.setFillColor(ORISEI_GOLD_LIGHT)
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
    canvas.setFillColor(ORISEI_SLATE)
    canvas.setFont("Helvetica-Oblique", 7)
    canvas.drawCentredString(
        width / 2, 0.22 * inch,
        f"Orisei Freight Solutions LLC  ·  Minneapolis · Saint Paul, MN  ·  "
        f"oliver@oriseifreight.com  ·  Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
    )
    canvas.restoreState()


def _styles() -> Dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("title", parent=base["Title"], fontName="Helvetica-Bold",
                                fontSize=26, leading=30, textColor=ORISEI_AZURE,
                                alignment=2, spaceAfter=2),
        "subtitle": ParagraphStyle("subtitle", parent=base["Normal"], fontName="Helvetica-Oblique",
                                   fontSize=9, leading=11, textColor=ORISEI_GOLD,
                                   alignment=2, spaceAfter=2),
        "doc_id": ParagraphStyle("doc_id", parent=base["Normal"], fontName="Courier",
                                 fontSize=8, leading=10, textColor=ORISEI_SLATE,
                                 alignment=2),
        "section": ParagraphStyle("section", parent=base["Normal"], fontName="Helvetica-Bold",
                                  fontSize=8, leading=10, textColor=ORISEI_GOLD,
                                  spaceBefore=4, spaceAfter=4),
        "field_label": ParagraphStyle("flbl", parent=base["Normal"], fontName="Helvetica-Bold",
                                      fontSize=7, leading=9, textColor=ORISEI_SLATE),
        "field_value": ParagraphStyle("fval", parent=base["Normal"], fontName="Helvetica",
                                      fontSize=10, leading=13, textColor=ORISEI_INK),
        "body": ParagraphStyle("body", parent=base["Normal"], fontName="Helvetica",
                               fontSize=9, leading=12, textColor=ORISEI_INK),
        "legal": ParagraphStyle("legal", parent=base["Normal"], fontName="Helvetica",
                                fontSize=7, leading=9.5, textColor=ORISEI_SLATE),
    }


def _header(doc_type_title: str, doc_subtitle: str, doc_id: str) -> Table:
    s = _styles()
    # Left: logo + wordmark stacked
    if LOGO_PATH.exists():
        logo = Image(str(LOGO_PATH), width=0.95 * inch, height=0.95 * inch)
    else:
        logo = Paragraph("<b>ORISEI</b>", s["title"])

    if WORDMARK_PATH.exists():
        wordmark = Image(str(WORDMARK_PATH), width=2.2 * inch, height=0.55 * inch, kind="proportional")
    else:
        wordmark = Paragraph("ORISEI FREIGHT", s["section"])

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
        [Paragraph(f"Document ID: <font face='Courier' color='#0E3A6B'><b>{doc_id}</b></font>", s["doc_id"])],
        [Paragraph(f"Issued {datetime.now(timezone.utc).strftime('%Y-%m-%d')}", s["doc_id"])],
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
        ("LINEBELOW", (0, 0), (-1, -1), 1.5, ORISEI_GOLD),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    return header


def _parties_block(shipper: Dict[str, str], consignee: Dict[str, str]) -> Table:
    s = _styles()
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
        ("BACKGROUND", (0, 0), (-1, 0), ORISEI_PAPER),
        ("BOX", (0, 0), (-1, -1), 0.4, ORISEI_GOLD),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, ORISEI_GOLD_LIGHT),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return parties


def _shipment_meta(rows: List[List[str]]) -> Table:
    s = _styles()
    data = [[Paragraph(lbl.upper(), s["field_label"]) for lbl in [r[0] for r in rows]],
            [Paragraph(str(r[1] or "—"), s["field_value"]) for r in rows]]
    cols = max(len(rows), 1)
    width = 7.0 * inch
    col_widths = [width / cols] * cols
    t = Table(data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (-1, 0), ORISEI_AZURE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 7),
        ("BOX", (0, 0), (-1, -1), 0.4, ORISEI_GOLD),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, ORISEI_GOLD_LIGHT),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def _section_header(text: str) -> Paragraph:
    s = _styles()
    return Paragraph(
        f"<font color='#0E3A6B'><b>◆</b></font>  "
        f"<font color='#0E3A6B'><b>{text.upper()}</b></font>",
        ParagraphStyle("sh", parent=s["section"], fontSize=10, leading=14,
                       textColor=ORISEI_AZURE, spaceBefore=10, spaceAfter=4),
    )


def _signature_block(*, signed_label: str = "Authorized Signature",
                     signed_name: Optional[str] = None,
                     signed_at: Optional[str] = None,
                     extra_line: Optional[str] = None) -> Table:
    s = _styles()
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
        ("LINEBELOW", (0, 1), (-1, 1), 0.3, ORISEI_SLATE),
    ]))
    return t


def _build_doc(buf: io.BytesIO, title: str) -> BaseDocTemplate:
    doc = BaseDocTemplate(
        buf, pagesize=letter,
        leftMargin=0.6 * inch, rightMargin=0.6 * inch,
        topMargin=0.55 * inch, bottomMargin=0.55 * inch,
        title=title,
    )
    frame = Frame(0.6 * inch, 0.55 * inch,
                  letter[0] - 1.2 * inch, letter[1] - 1.1 * inch,
                  showBoundary=0)
    doc.addPageTemplates([PageTemplate(id="orisei", frames=[frame], onPage=_draw_heraldic_border)])
    return doc


# ---------- PUBLIC: Bill of Lading ----------
def build_bol_pdf(*, doc_id: str, booking: Dict[str, Any],
                  shipper: Dict[str, str], consignee: Dict[str, str],
                  user_name: Optional[str] = None) -> bytes:
    """Render a beautiful Orisei-branded Bill of Lading PDF.

    `booking` should contain: load_id, origin, destination, miles, equipment,
    commodity, weight_lbs, pieces, carrier_name, carrier_mc, rate_usd,
    pickup_date (iso), delivery_date (iso). Missing fields render as "—".
    """
    s = _styles()
    buf = io.BytesIO()
    doc = _build_doc(buf, f"Orisei BOL · {doc_id}")
    story: List[Any] = []

    story.append(_header(
        "BILL OF LADING",
        "Straight Bill — Original · Non-Negotiable",
        doc_id,
    ))
    story.append(Spacer(1, 8))

    story.append(_section_header("Parties"))
    story.append(_parties_block(shipper, consignee))
    story.append(Spacer(1, 10))

    story.append(_section_header("Shipment Information"))
    meta_rows = [
        ["Load ID", booking.get("load_id") or booking.get("booked_id") or "—"],
        ["Carrier", booking.get("carrier_name") or "—"],
        ["MC #", booking.get("carrier_mc") or "—"],
        ["Equipment", booking.get("equipment") or "—"],
        ["Miles", booking.get("miles") and f"{booking['miles']:,}" or "—"],
        ["Pickup", booking.get("pickup_date") or "—"],
        ["Delivery", booking.get("delivery_date") or "—"],
    ]
    story.append(_shipment_meta(meta_rows))
    story.append(Spacer(1, 10))

    story.append(_section_header("Freight"))
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
        ("BACKGROUND", (0, 0), (-1, 0), ORISEI_AZURE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("GRID", (0, 0), (-1, -1), 0.3, ORISEI_GOLD_LIGHT),
        ("BOX", (0, 0), (-1, -1), 0.5, ORISEI_GOLD),
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
    story.append(_section_header("Special Instructions"))
    story.append(Paragraph(str(instructions), s["body"]))
    story.append(Spacer(1, 8))

    # Charges
    story.append(_section_header("Freight Charges"))
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
        ("BACKGROUND", (0, 0), (-1, 0), ORISEI_GOLD),
        ("TEXTCOLOR", (0, 0), (-1, 0), ORISEI_INK),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 1), (-1, -1), 11),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("BOX", (0, 0), (-1, -1), 0.5, ORISEI_AZURE),
        ("GRID", (0, 0), (-1, -1), 0.3, ORISEI_AZURE),
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
    story.append(_section_header("Signatures"))
    story.append(_signature_block(signed_label="Shipper Representative",
                                  signed_name=user_name))
    story.append(Spacer(1, 6))
    story.append(_signature_block(signed_label="Carrier / Driver Signature"))

    doc.build(story)
    return buf.getvalue()


# ---------- PUBLIC: Compliance Form ----------
def build_form_pdf(*, form_meta: Dict[str, Any], schema_rows: List[List[str]],
                   fields: Dict[str, Any], legal_text: str,
                   user_name: Optional[str] = None) -> bytes:
    """Render any brokerage compliance form (BOC-3, BMC-84, Rate Confirmation,
    Carrier Packet, NOA, etc.) using the same Calafia heraldic template as
    the BOL and POD. `schema_rows` is a list of `[label, key]` tuples — the
    same shape `_form_schema` returns in `routes.brokerage`.
    """
    s = _styles()
    buf = io.BytesIO()
    title = form_meta.get("name") or "Compliance Form"
    doc_id = f"ORI-{form_meta.get('id','FORM').upper()}-{__import__('uuid').uuid4().hex[:8].upper()}"
    doc = _build_doc(buf, f"Orisei {title} · {doc_id}")
    story: List[Any] = []

    # Header
    subtitle = form_meta.get("category") or "Compliance Document"
    if form_meta.get("fmcsa"):
        subtitle = f"{subtitle} · FMCSA-Required"
    story.append(_header(title.upper(), subtitle, doc_id))
    story.append(Spacer(1, 8))

    # Generated-by note
    gen_note = (f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
                f"{' · by ' + user_name if user_name else ''}")
    story.append(Paragraph(f"<font size='8' color='#64748B'>{gen_note}</font>", s["body"]))
    story.append(Spacer(1, 8))

    # Field table
    story.append(_section_header("Form Fields"))
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
        ("BACKGROUND", (0, 0), (-1, 0), ORISEI_AZURE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [ORISEI_PAPER, colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.3, ORISEI_GOLD_LIGHT),
        ("BOX", (0, 0), (-1, -1), 0.5, ORISEI_GOLD),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(field_tbl)
    story.append(Spacer(1, 14))

    # Acknowledgement / legal text
    story.append(_section_header("Acknowledgement & Signature"))
    story.append(Paragraph(legal_text, s["legal"]))
    story.append(Spacer(1, 18))

    # Signature block
    story.append(_signature_block(
        signed_label="Authorized Signature",
        signed_name=user_name,
    ))
    story.append(Spacer(1, 12))

    # Footer doc-id stamp
    story.append(Paragraph(
        f"<font face='Courier' color='#0E3A6B' size='7'><b>DOC ID: {doc_id}</b></font> "
        f"<font size='7' color='#94A3B8'>· Generated by the Orisei Freight Solutions TMS Brokerage module</font>",
        s["legal"],
    ))

    doc.build(story)
    return buf.getvalue()


# ---------- PUBLIC: Branded Markdown / Business Plan ----------
def build_branded_markdown_pdf(md_text: str, *, title: str = "Business Plan",
                               subtitle: Optional[str] = None,
                               doc_id: Optional[str] = None) -> bytes:
    """Render a markdown document (business plan, cost analysis, home-office
    setup, etc.) using the Calafia heraldic template — Orisei logo header,
    gold corner diamonds, navy headings, gold rule.
    """
    import re as _re
    base_styles = getSampleStyleSheet()
    md_styles = {
        "h1":  ParagraphStyle("h1",  parent=base_styles["Heading1"], fontSize=18, leading=22,
                              textColor=ORISEI_AZURE, spaceBefore=10, spaceAfter=8),
        "h2":  ParagraphStyle("h2",  parent=base_styles["Heading2"], fontSize=14, leading=18,
                              textColor=ORISEI_GOLD, spaceBefore=12, spaceAfter=6),
        "h3":  ParagraphStyle("h3",  parent=base_styles["Heading3"], fontSize=11, leading=15,
                              textColor=ORISEI_AZURE, spaceBefore=8, spaceAfter=4),
        "p":   ParagraphStyle("p",   parent=base_styles["BodyText"], fontSize=9.5, leading=13,
                              textColor=ORISEI_INK, spaceAfter=4),
        "li":  ParagraphStyle("li",  parent=base_styles["BodyText"], fontSize=9.5, leading=13,
                              leftIndent=14, bulletIndent=2, textColor=ORISEI_INK, spaceAfter=2),
        "quo": ParagraphStyle("quo", parent=base_styles["BodyText"], fontSize=9.5, leading=13,
                              leftIndent=14, textColor=ORISEI_SLATE, italic=True, spaceAfter=4),
    }
    buf = io.BytesIO()
    final_doc_id = doc_id or f"ORI-{__import__('uuid').uuid4().hex[:10].upper()}"
    doc_pdf = _build_doc(buf, title)
    story: List[Any] = []
    story.append(_header(title.upper(), subtitle or "Founder Business Plan", final_doc_id))
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

    lines = md_text.splitlines()
    i = 0
    skipped_first_h1 = False
    while i < len(lines):
        line = lines[i].rstrip()
        stripped = line.strip()
        if not stripped or _re.fullmatch(r"-{3,}|={3,}|\*{3,}", stripped):
            story.append(Spacer(1, 4)); i += 1; continue
        if "|" in stripped and i + 1 < len(lines) and _re.match(r"\|?\s*[:-]+\s*\|", lines[i + 1]):
            j = i
            while j < len(lines) and lines[j].strip().startswith("|"):
                j += 1
            story.append(Paragraph("<i>[Table omitted — see full plan online]</i>", md_styles["quo"]))
            i = j; continue
        if stripped.startswith("### "):
            story.append(Paragraph(_inline(stripped[4:]), md_styles["h3"])); i += 1; continue
        if stripped.startswith("## "):
            story.append(Paragraph(_inline(stripped[3:]), md_styles["h2"])); i += 1; continue
        if stripped.startswith("# "):
            if not skipped_first_h1:
                skipped_first_h1 = True; i += 1; continue
            story.append(Paragraph(_inline(stripped[2:]), md_styles["h1"])); i += 1; continue
        if stripped.startswith("> "):
            story.append(Paragraph(_inline(stripped[2:]), md_styles["quo"])); i += 1; continue
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
                  user_name: Optional[str] = None) -> bytes:
    """Render a beautiful Orisei-branded Proof of Delivery PDF.

    `delivery` should contain: delivered_at, received_by, condition,
    exceptions (list[str] or str), pieces_received, weight_received,
    seal_intact (bool), pod_signature (text), driver_name.
    """
    s = _styles()
    buf = io.BytesIO()
    doc = _build_doc(buf, f"Orisei POD · {doc_id}")
    story: List[Any] = []

    story.append(_header(
        "PROOF OF DELIVERY",
        "Customer Receipt · Final Mile Confirmation",
        doc_id,
    ))
    story.append(Spacer(1, 8))

    story.append(_section_header("Parties"))
    story.append(_parties_block(shipper, consignee))
    story.append(Spacer(1, 10))

    story.append(_section_header("Shipment Reference"))
    ref_rows = [
        ["Load ID", booking.get("load_id") or booking.get("booked_id") or "—"],
        ["BOL #", booking.get("bol_no") or doc_id.replace("POD", "BOL")],
        ["Carrier", booking.get("carrier_name") or "—"],
        ["MC #", booking.get("carrier_mc") or "—"],
        ["Origin", booking.get("origin") or "—"],
        ["Destination", booking.get("destination") or "—"],
    ]
    story.append(_shipment_meta(ref_rows))
    story.append(Spacer(1, 10))

    story.append(_section_header("Delivery Confirmation"))
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
    story.append(_shipment_meta(delivery_rows))
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
        ("BACKGROUND", (0, 0), (-1, -1), ORISEI_AZURE),
        ("BOX", (0, 0), (-1, -1), 1.5, ORISEI_GOLD),
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
        "submitted in writing to Orisei Freight Solutions within nine (9) months of delivery "
        "in accordance with 49 CFR § 370 and the National Motor Freight Classification. "
        "Concealed-damage claims must be filed within fifteen (15) calendar days.",
        s["legal"],
    ))
    story.append(Spacer(1, 14))

    story.append(_section_header("Signatures"))
    story.append(_signature_block(
        signed_label="Consignee / Receiver",
        signed_name=delivery.get("received_by"),
        signed_at=delivered_at,
    ))
    story.append(Spacer(1, 6))
    story.append(_signature_block(
        signed_label="Driver / Carrier",
        signed_name=delivery.get("driver_name") or booking.get("driver_name"),
    ))
    story.append(Spacer(1, 6))
    story.append(_signature_block(
        signed_label="Orisei Operator",
        signed_name=user_name,
    ))

    # Dock photos (optional) — up to 3 thumbnails on a second page
    photos = delivery.get("photos") or []
    if photos:
        from reportlab.platypus import PageBreak
        story.append(PageBreak())
        story.append(_header(
            "DELIVERY PHOTOS",
            f"Dock photos — {len(photos)} attached",
            doc_id,
        ))
        story.append(Spacer(1, 12))
        story.append(_section_header("Photo evidence captured at delivery"))
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
                    ("BOX", (0, 0), (-1, 0), 0.5, ORISEI_GOLD),
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
