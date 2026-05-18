"""routes.public_site — Public marketing site endpoints (no auth).

Lightweight surface area exposed to anonymous visitors of livecleans.com /
oriseifreight.com:
  • POST /api/public/quote     — capture quote requests + email Oliver
  • POST /api/public/contact   — generic "get in touch" form
  • GET  /api/public/lanes     — list of preferred lanes for the marketing site
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import resend
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from routes.connections import get_connection_credentials

logger = logging.getLogger("tennant_tms.public_site")


class QuoteRequestIn(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=160)
    contact_name: str = Field(..., min_length=1, max_length=120)
    email: EmailStr
    phone: Optional[str] = Field(None, max_length=40)
    origin: Optional[str] = Field(None, max_length=160)
    destination: Optional[str] = Field(None, max_length=160)
    pickup_date: Optional[str] = Field(None, max_length=40)
    equipment: Optional[str] = Field(None, max_length=80)        # Van/Reefer/Flatbed/etc.
    weight_lbs: Optional[str] = Field(None, max_length=40)
    pieces: Optional[str] = Field(None, max_length=40)
    commodity: Optional[str] = Field(None, max_length=200)
    target_rate: Optional[str] = Field(None, max_length=40)
    notes: Optional[str] = Field(None, max_length=2000)
    # Honeypot — hidden field bots fill out
    website: Optional[str] = Field(None, max_length=200)


class ContactIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=160)
    email: EmailStr
    phone: Optional[str] = Field(None, max_length=40)
    company: Optional[str] = Field(None, max_length=160)
    subject: Optional[str] = Field(None, max_length=200)
    message: str = Field(..., min_length=5, max_length=4000)
    website: Optional[str] = None    # honeypot


class InvestorIntro(BaseModel):
    name: str = Field(..., min_length=1, max_length=160)
    email: EmailStr
    firm: Optional[str] = Field(None, max_length=160)
    check_size_usd: Optional[str] = Field(None, max_length=40)
    linkedin: Optional[str] = Field(None, max_length=300)
    message: Optional[str] = Field(None, max_length=2000)
    website: Optional[str] = None     # honeypot


def _quote_email_html(q: Dict[str, Any]) -> str:
    rows = [
        ("Company", q.get("company_name")),
        ("Contact", f"{q.get('contact_name')} · {q.get('email')}"),
        ("Phone", q.get("phone")),
        ("Lane", f"{q.get('origin', '—')}  →  {q.get('destination', '—')}"),
        ("Pickup", q.get("pickup_date")),
        ("Equipment", q.get("equipment")),
        ("Weight", q.get("weight_lbs")),
        ("Pieces", q.get("pieces")),
        ("Commodity", q.get("commodity")),
        ("Target rate", q.get("target_rate")),
    ]
    rows_html = "".join(
        f'<tr><td style="padding:6px 14px 6px 0;color:#475569;width:140px;font-size:12px;">{k}</td>'
        f'<td style="padding:6px 0;font-size:13px;color:#0B1320;">{v or "—"}</td></tr>'
        for k, v in rows
    )
    notes_html = ""
    if q.get("notes"):
        notes_html = (
            f'<p style="margin-top:16px;padding:10px 14px;background:#FBF8F0;'
            f'border-left:3px solid #C9A24A;font-size:13px;color:#0B1320;'
            f'white-space:pre-wrap;">{q["notes"]}</p>'
        )
    return f"""<!doctype html>
<html><body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;background:#FBF8F0;padding:24px;color:#0B1320;">
  <div style="max-width:620px;margin:0 auto;background:#fff;border:1px solid #E6CB85;border-radius:8px;overflow:hidden;">
    <div style="background:#0E3A6B;color:#fff;padding:22px 26px;border-bottom:3px solid #C9A24A;">
      <div style="font-size:11px;letter-spacing:.3em;color:#C9A24A;text-transform:uppercase;font-family:Courier,monospace;">Orisei Freight Solutions</div>
      <div style="font-size:20px;font-weight:800;margin-top:6px;">New Quote Request · {q.get('company_name', '')}</div>
      <div style="font-size:12px;color:#E6CB85;margin-top:4px;">Submitted {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</div>
    </div>
    <div style="padding:24px 26px;">
      <table style="width:100%;border-collapse:collapse;">{rows_html}</table>
      {notes_html}
    </div>
  </div>
</body></html>"""


def _contact_email_html(c: Dict[str, Any]) -> str:
    msg = (c.get("message") or "").replace("\n", "<br>")
    return f"""<!doctype html>
<html><body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;background:#FBF8F0;padding:24px;color:#0B1320;">
  <div style="max-width:620px;margin:0 auto;background:#fff;border:1px solid #E6CB85;border-radius:8px;overflow:hidden;">
    <div style="background:#0E3A6B;color:#fff;padding:22px 26px;border-bottom:3px solid #C9A24A;">
      <div style="font-size:11px;letter-spacing:.3em;color:#C9A24A;text-transform:uppercase;font-family:Courier,monospace;">Orisei Freight Solutions</div>
      <div style="font-size:20px;font-weight:800;margin-top:6px;">New Contact · {c.get('name','')}</div>
    </div>
    <div style="padding:24px 26px;font-size:13px;line-height:1.6;">
      <p><b>From:</b> {c.get('name')} &lt;{c.get('email')}&gt;{(' · ' + c['phone']) if c.get('phone') else ''}</p>
      {f"<p><b>Company:</b> {c['company']}</p>" if c.get('company') else ''}
      {f"<p><b>Subject:</b> {c['subject']}</p>" if c.get('subject') else ''}
      <p style="margin-top:14px;padding:12px 14px;background:#FBF8F0;border-left:3px solid #C9A24A;white-space:pre-wrap;">{msg}</p>
    </div>
  </div>
</body></html>"""


PREFERRED_LANES = [
    {"origin": "Twin Cities, MN",      "destination": "Chicago, IL",        "equipment": "Reefer",   "miles": 410, "notes": "Daily food-grade volume"},
    {"origin": "Twin Cities, MN",      "destination": "Dallas, TX",         "equipment": "Van",      "miles": 980, "notes": "OEM weekly"},
    {"origin": "Saint Paul, MN",       "destination": "Atlanta, GA",        "equipment": "Reefer",   "miles": 1180, "notes": "Pharma cold-chain"},
    {"origin": "Minneapolis, MN",      "destination": "Los Angeles, CA",    "equipment": "Van",      "miles": 1900, "notes": "Retail consolidation"},
    {"origin": "Chicago, IL",          "destination": "Twin Cities, MN",    "equipment": "Flatbed",  "miles": 410, "notes": "Steel + machinery backhaul"},
    {"origin": "Saint Paul, MN",       "destination": "Toronto, ON",        "equipment": "Van",      "miles": 1320, "notes": "Cross-border, FAST-certified"},
    {"origin": "Minneapolis, MN",      "destination": "Salt Lake City, UT", "equipment": "Reefer",   "miles": 1180, "notes": "Produce out / dry back"},
    {"origin": "Twin Cities, MN",      "destination": "Seattle, WA",        "equipment": "Van",      "miles": 1660, "notes": "Tech / e-commerce"},
]


def build_public_router(api_router: APIRouter, db) -> None:
    router = APIRouter(prefix="/public", tags=["public"])

    async def _active_brand() -> Dict[str, Any]:
        """Same helper the rest of the app uses; pulled inline so this router
        doesn't depend on server.py state."""
        doc = await db.company_brand.find_one({"is_active": True}, {"_id": 0})
        if not doc:
            doc = await db.company_brand.find_one({}, {"_id": 0})
        return doc or {}

    @router.post("/quote")
    async def submit_quote(payload: QuoteRequestIn, request: Request):
        """Public quote-request submission. No auth. Honeypot-protected."""
        if payload.website:                                          # bot trap
            return {"ok": True, "id": "ignored"}
        rec = {
            "id": f"QR-{uuid.uuid4().hex[:10].upper()}",
            **payload.model_dump(exclude={"website"}),
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "ip": (request.client.host if request.client else None),
            "user_agent": request.headers.get("user-agent", "")[:300],
            "status": "new",
            "email_status": "pending",
        }
        await db.quote_requests.insert_one(dict(rec))

        creds = await get_connection_credentials(db, "resend") or {}
        api_key = creds.get("api_key")
        notify_to = creds.get("reply_to") or "oliver@oriseifreight.com"
        if api_key:
            try:
                resend.api_key = api_key
                resp = resend.Emails.send({
                    "from": creds.get("from_email") or "Orisei Quote <oliver@oriseifreight.com>",
                    "to": [notify_to],
                    "reply_to": payload.email,
                    "subject": f"New Quote · {payload.company_name} · "
                               f"{payload.origin or '?'} → {payload.destination or '?'}",
                    "html": _quote_email_html(rec),
                })
                rec["email_status"] = "sent"
                rec["message_id"] = (resp or {}).get("id") if isinstance(resp, dict) else None
                await db.quote_requests.update_one(
                    {"id": rec["id"]},
                    {"$set": {"email_status": "sent",
                              "message_id": rec.get("message_id")}},
                )
            except Exception as exc:                                # noqa: BLE001
                logger.exception("Quote email failed")
                await db.quote_requests.update_one(
                    {"id": rec["id"]},
                    {"$set": {"email_status": "error", "email_error": str(exc)[:300]}},
                )
        else:
            await db.quote_requests.update_one(
                {"id": rec["id"]},
                {"$set": {"email_status": "skipped", "email_error": "Resend not configured"}},
            )

        return {"ok": True, "id": rec["id"], "received_at": rec["submitted_at"]}

    @router.post("/contact")
    async def submit_contact(payload: ContactIn, request: Request):
        if payload.website:
            return {"ok": True, "id": "ignored"}
        rec = {
            "id": f"CO-{uuid.uuid4().hex[:10].upper()}",
            **payload.model_dump(exclude={"website"}),
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "ip": (request.client.host if request.client else None),
            "status": "new",
            "email_status": "pending",
        }
        await db.contact_messages.insert_one(dict(rec))
        creds = await get_connection_credentials(db, "resend") or {}
        api_key = creds.get("api_key")
        notify_to = creds.get("reply_to") or "oliver@oriseifreight.com"
        if api_key:
            try:
                resend.api_key = api_key
                resend.Emails.send({
                    "from": creds.get("from_email") or "Orisei Contact <oliver@oriseifreight.com>",
                    "to": [notify_to],
                    "reply_to": payload.email,
                    "subject": payload.subject or f"Website contact · {payload.name}",
                    "html": _contact_email_html(rec),
                })
                await db.contact_messages.update_one(
                    {"id": rec["id"]}, {"$set": {"email_status": "sent"}},
                )
            except Exception as exc:                                # noqa: BLE001
                logger.exception("Contact email failed")
                await db.contact_messages.update_one(
                    {"id": rec["id"]},
                    {"$set": {"email_status": "error", "email_error": str(exc)[:300]}},
                )
        else:
            await db.contact_messages.update_one(
                {"id": rec["id"]}, {"$set": {"email_status": "skipped"}},
            )
        return {"ok": True, "id": rec["id"]}

    @router.get("/lanes")
    async def list_lanes() -> Dict[str, Any]:
        return {"lanes": PREFERRED_LANES, "count": len(PREFERRED_LANES)}

    @router.get("/investor-summary")
    async def public_investor_summary() -> Dict[str, Any]:
        """Public-safe investor executive summary — TAM/SAM/SOM, headline
        financial trajectory, the ask, and a few proof points. Sensitive
        unit-economics details (CAC, exact OPEX) are intentionally omitted.
        Brand-aware: returns active brand identity for theming."""
        from .investor import (
            MARKET_SIZING, INDUSTRY_BENCHMARKS,
            _annual_summary, _financial_model_rows, _compute_probability,
            ProbabilityInputs, UNIT_ECONOMICS, CURRENT_STATUS,
        )
        brand = await _active_brand()
        rows = _financial_model_rows()
        annual = _annual_summary(rows)
        prob = _compute_probability(ProbabilityInputs())
        return {
            "current_status": CURRENT_STATUS,
            "brand": {
                "company_name": brand.get("company_name") or "Orisei Freight Solutions LLC",
                "short_name": brand.get("short_name") or "Orisei",
                "tagline": brand.get("tagline") or "Operator-built freight brokerage · Minneapolis · Saint Paul",
                "primary_color": brand.get("primary_color") or "#0E3A6B",
                "accent_color": brand.get("accent_color") or "#C9A24A",
                "owner_name": brand.get("owner_name") or "Oliver Cummins",
                "headquarters": brand.get("headquarters") or "Minneapolis · Saint Paul, MN",
                "contact_email": "oliver@oriseifreight.com",
            },
            "market_sizing": MARKET_SIZING,
            "headline_benchmarks": {
                "broker_failure_year1_pct": INDUSTRY_BENCHMARKS["broker_failure_year1_pct"],
                "broker_failure_year3_pct": INDUSTRY_BENCHMARKS["broker_failure_year3_pct"],
                "industry_growth_cagr_pct": INDUSTRY_BENCHMARKS["industry_growth_cagr_pct"],
                "ai_tooling_estimated_lift_pct": INDUSTRY_BENCHMARKS["ai_tooling_estimated_lift_pct"],
                "sources": INDUSTRY_BENCHMARKS["sources"],
                "honesty_note": INDUSTRY_BENCHMARKS["honesty_note"],
            },
            "trajectory": [
                {"year": r["year"], "revenue_usd": r["revenue_usd"],
                 "ebitda_usd": r["ebitda_usd"], "loads": r["loads"],
                 "ebitda_margin_pct": r["ebitda_margin_pct"]}
                for r in annual
            ],
            "monthly_revenue": [
                {"month": r["month_label"], "revenue_usd": r["revenue_usd"]}
                for r in rows
            ],
            "probability": {
                "score_pct": prob["score_pct"],
                "band": prob["band"],
                "band_note": prob["band_note"],
            },
            "unit_economics_public": {
                "ltv_cac_ratio": UNIT_ECONOMICS["ltv_cac_ratio"],
                "payback_loads": UNIT_ECONOMICS["customer_payback_loads"],
                "rule_of_40_year3_pct": UNIT_ECONOMICS["rule_of_40_year3_pct"],
                "avg_gross_margin_pct_y1": UNIT_ECONOMICS["avg_gross_margin_pct_y1"],
                "avg_gross_margin_pct_mature": UNIT_ECONOMICS["avg_gross_margin_pct_mature"],
                "honesty_note": UNIT_ECONOMICS["honesty_note"],
            },
            "ask": {
                "instrument": "SAFE",
                "amount_usd": 500_000,
                "valuation_cap_usd": 4_000_000,
                "discount_pct": 20,
                "use_of_funds": [
                    {"label": "Authority + bond + insurance", "amount_usd": 50_000},
                    {"label": "Carrier-vetting + monitoring tooling", "amount_usd": 45_000},
                    {"label": "Load board subscriptions", "amount_usd": 36_000},
                    {"label": "Founder runway (12 mo)", "amount_usd": 120_000},
                    {"label": "Marketing + outbound (6 mo)", "amount_usd": 60_000},
                    {"label": "Working capital / quick-pay float", "amount_usd": 110_000},
                    {"label": "Contingency reserve", "amount_usd": 79_000},
                ],
            },
            "proof_points": [
                "TMS Command Deck shipped and operating in production today.",
                "Brand-aware document engine: BOLs, PODs, and compliance forms render in < 800ms.",
                "Connections vault wired for DAT, Truckstop, Convoy, Resend, RMIS, Carrier411, QuickBooks (Fernet-encrypted) — credentials pending activation.",
                "Marketing pack live: carrier + shipper sell sheets, 3 LinkedIn posts, 3 cold-email sequences with follow-ups.",
                "13-year operator-founder edge — references available on request.",
                "Zero loads booked yet · pre-launch · the raise is what turns the platform into a brokerage.",
            ],
        }

    @router.get("/deck.pdf")
    async def public_deck_pdf():
        """Public download of the brand-stamped pitch deck PDF — no auth
        required so VCs / journalists / partners can grab it directly from a
        social-post link."""
        from fastapi.responses import StreamingResponse
        import io as _io
        from .investor import _deck_markdown, _compute_probability, ProbabilityInputs
        from .orisei_docs import build_branded_markdown_pdf
        brand = await _active_brand()
        company = brand.get("company_name") or "Orisei Freight Solutions LLC"
        prob = _compute_probability(ProbabilityInputs())
        pdf = build_branded_markdown_pdf(
            _deck_markdown(brand, prob),
            title=f"{company} · VC Pitch Deck",
            subtitle="Series Seed · Confidential",
            brand=brand,
        )
        return StreamingResponse(
            _io.BytesIO(pdf),
            media_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="{company.replace(" ", "_")}_Pitch_Deck.pdf"'},
        )

    @router.get("/one-pager.pdf")
    async def public_one_pager_pdf():
        """Public download of the brand-stamped one-pager PDF."""
        from fastapi.responses import StreamingResponse
        import io as _io
        from .investor import _one_pager_markdown
        from .orisei_docs import build_branded_markdown_pdf
        brand = await _active_brand()
        company = brand.get("company_name") or "Orisei Freight Solutions LLC"
        pdf = build_branded_markdown_pdf(
            _one_pager_markdown(brand),
            title=f"{company} · Investor One-Pager",
            subtitle="At-a-glance · Confidential",
            brand=brand,
        )
        return StreamingResponse(
            _io.BytesIO(pdf),
            media_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="{company.replace(" ", "_")}_One_Pager.pdf"'},
        )

    @router.post("/investor-intro")
    async def submit_investor_intro(payload: InvestorIntro, request: Request) -> Dict[str, Any]:
        """Capture investor intros from the public /investors page."""
        if payload.website:
            return {"ok": True, "id": "ignored"}
        rec = {
            "id": str(uuid.uuid4()),
            "kind": "investor_intro",
            "name": payload.name,
            "email": payload.email,
            "firm": payload.firm,
            "check_size_usd": payload.check_size_usd,
            "linkedin": payload.linkedin,
            "message": payload.message,
            "client_ip": request.client.host if request.client else None,
            "received_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.investor_intros.insert_one(dict(rec))
        # Best-effort email notification to the founder via Resend
        try:
            creds = await get_connection_credentials(db, "resend")
            if creds and creds.get("api_key"):
                resend.api_key = creds["api_key"]
                from_email = creds.get("from_email") or "onboarding@resend.dev"
                from_name = creds.get("from_name") or "Orisei"
                lines = [
                    f"<b>New investor intro from the public /investors page</b>",
                    f"<b>Name</b>: {payload.name}",
                    f"<b>Email</b>: {payload.email}",
                    f"<b>Firm</b>: {payload.firm or '—'}",
                    f"<b>Check size</b>: {payload.check_size_usd or '—'}",
                    f"<b>LinkedIn</b>: {payload.linkedin or '—'}",
                    f"<b>Message</b>: {payload.message or '—'}",
                ]
                resend.Emails.send({
                    "from": f"{from_name} <{from_email}>",
                    "to": ["oliver@oriseifreight.com"],
                    "subject": f"Investor intro · {payload.name} ({payload.firm or 'no firm'})",
                    "html": "<br/>".join(lines),
                })
        except Exception:                                            # noqa: BLE001
            logger.exception("Failed to email founder about investor_intro")
        return {"ok": True, "id": rec["id"]}

    api_router.include_router(router)
