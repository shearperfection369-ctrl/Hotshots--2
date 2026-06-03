"""routes.orisei_operations — Real-world brokerage operations for Orisei.

The four missing pieces between "I have a TMS" and "I dispatched my first
paying load":

  1. Customer (shipper) records — full CRUD with contacts, terms, contracts
  2. Customer Quotes — emailed PDF a shipper signs back before booking
  3. Rate Confirmations — emailed PDF a carrier signs back when tendered
  4. Customer Self-Service Portal — token-gated, shows their loads + invoices

All four use the existing brand-aware document engine, QBO sync, Connections
Vault Resend pipeline, and Margin Shield scoring — no new infrastructure.
"""
from __future__ import annotations

import io
import logging
import secrets
import uuid
import zipfile
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr, Field

from .orisei_docs import build_branded_markdown_pdf

logger = logging.getLogger("tennant_tms.orisei_operations")


# -------------------- PYDANTIC --------------------
class CustomerContact(BaseModel):
    name: str
    role: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None


class CustomerIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    legal_name: Optional[str] = Field(None, max_length=200)
    billing_address: Optional[str] = Field(None, max_length=400)
    ap_email: Optional[EmailStr] = None
    primary_contact_name: Optional[str] = None
    primary_contact_email: Optional[EmailStr] = None
    primary_contact_phone: Optional[str] = None
    payment_terms: str = Field("Net 30", description="Net 15, Net 30, Net 45, Net 60")
    credit_limit_usd: Optional[float] = Field(None, ge=0)
    msa_signed_at: Optional[str] = None
    notes: Optional[str] = Field(None, max_length=2000)
    contacts: Optional[List[CustomerContact]] = None
    active: bool = True


class QuoteLineItem(BaseModel):
    label: str
    amount_usd: float


class QuoteIn(BaseModel):
    customer_id: str
    origin: str = Field(..., max_length=200)
    destination: str = Field(..., max_length=200)
    pickup_date: Optional[str] = None
    delivery_date: Optional[str] = None
    equipment: str = "Dry Van"
    miles: Optional[float] = Field(None, ge=0)
    weight_lbs: Optional[float] = Field(None, ge=0)
    line_haul_usd: float = Field(..., ge=0)
    fuel_surcharge_usd: float = 0.0
    accessorials: Optional[List[QuoteLineItem]] = None
    valid_for_days: int = Field(7, ge=1, le=90)
    notes: Optional[str] = None


class RateConfirmationIn(BaseModel):
    booking_id: str
    carrier_mc: str
    carrier_name: str
    carrier_contact_email: Optional[EmailStr] = None
    carrier_contact_phone: Optional[str] = None
    rate_usd: float = Field(..., ge=0)
    pickup_date: Optional[str] = None
    delivery_date: Optional[str] = None
    pickup_instructions: Optional[str] = None
    delivery_instructions: Optional[str] = None
    special_requirements: Optional[str] = None
    accessorial_notes: Optional[str] = None
    quickpay_offered: bool = True
    quickpay_fee_pct: float = 3.0


class PortalLinkIn(BaseModel):
    customer_id: str
    days_valid: Optional[int] = Field(90, ge=1, le=365)
    notes: Optional[str] = None


# -------------------- HELPERS --------------------
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _quote_total(payload: QuoteIn) -> float:
    accessorial_sum = sum(a.amount_usd for a in (payload.accessorials or []))
    return round(payload.line_haul_usd + payload.fuel_surcharge_usd + accessorial_sum, 2)


def _quote_markdown(quote: Dict[str, Any], customer: Dict[str, Any]) -> str:
    accessorials = quote.get("accessorials") or []
    accessorial_lines = "\n".join(
        f"- {a['label']}: ${a['amount_usd']:.2f}" for a in accessorials
    ) or "- *(None)*"
    rpm = (quote["total_usd"] / quote["miles"]) if quote.get("miles") else None
    return f"""# Freight Quote · {quote['quote_id']}

**Prepared for**: {customer.get('name', 'Customer')}
**Quote date**: {quote['issued_at'][:10]}
**Valid through**: {quote['valid_until'][:10]}

---

## Lane
- **Origin**: {quote['origin']}
- **Destination**: {quote['destination']}
- **Distance**: {quote.get('miles', '—')} miles
- **Equipment**: {quote['equipment']}
- **Pickup**: {quote.get('pickup_date') or '—'}
- **Delivery**: {quote.get('delivery_date') or '—'}
- **Weight**: {quote.get('weight_lbs', '—')} lbs

## Pricing
- Line haul: **${quote['line_haul_usd']:,.2f}**
- Fuel surcharge: ${quote.get('fuel_surcharge_usd', 0):,.2f}

### Accessorials
{accessorial_lines}

---

## Total · ${quote['total_usd']:,.2f}
{f"Rate per mile: **${rpm:.2f}/mi**" if rpm else ""}

---

## Terms
- Payment: **{customer.get('payment_terms', 'Net 30')}** from invoice date
- Quote valid for **{quote['valid_for_days']} days** from date above
- Acceptance: reply to this email or sign and return this document
- All shipments tendered under our standard Master Brokerage Agreement

{f"### Notes{chr(10)}{quote.get('notes')}" if quote.get('notes') else ""}

---

**Orisei Freight Solutions LLC** · Plymouth, Minnesota
shearperfection369@gmail.com
"""


def _rate_con_markdown(rc: Dict[str, Any], booking: Dict[str, Any]) -> str:
    return f"""# Rate Confirmation · {rc['rc_id']}

**Carrier**: {rc['carrier_name']}
**MC #**: {rc['carrier_mc']}
**Booking #**: {rc['booking_id']}
**Issued**: {rc['issued_at'][:16]} UTC

---

## Load Details
- **Origin**: {booking.get('origin', '—')}
- **Destination**: {booking.get('destination', '—')}
- **Pickup date**: {rc.get('pickup_date') or booking.get('pickup_date', '—')}
- **Delivery date**: {rc.get('delivery_date') or booking.get('delivery_date', '—')}
- **Commodity**: {booking.get('commodity', 'General freight')}
- **Equipment**: {booking.get('equipment', 'Dry Van')}
- **Weight**: {booking.get('weight_lbs', '—')} lbs
- **Miles**: {booking.get('miles', '—')}

## Pickup Instructions
{rc.get('pickup_instructions') or '*(Standard pickup — confirm with shipper before arrival.)*'}

## Delivery Instructions
{rc.get('delivery_instructions') or '*(Standard delivery — driver must obtain signed BOL/POD.)*'}

{f"## Special Requirements{chr(10)}{rc['special_requirements']}{chr(10)}" if rc.get('special_requirements') else ""}

---

## Compensation
- **All-in rate**: **${rc['rate_usd']:,.2f}** USD
{f"- Accessorial allowance: {rc['accessorial_notes']}" if rc.get('accessorial_notes') else ""}

### Payment Terms
{('- **QuickPay available** · ' + str(rc['quickpay_fee_pct']) + '%% fee · funds 1-2 business days after signed POD received' if rc.get('quickpay_offered') else '')}
- Standard payment: Net 30 from signed POD receipt
- Factoring: assignment of payment to your factor permitted (NOA required)

---

## Carrier Acknowledgement
By signing or returning this Rate Confirmation, carrier agrees to:
1. Pick up and deliver per the dates and addresses listed above
2. Maintain cargo insurance with minimum **$100,000** limit naming
   *Orisei Freight Solutions LLC* as certificate holder
3. Provide signed BOL/POD within 24 hours of delivery
4. Communicate any delay, exception, or claim within 4 hours of discovery
5. Bill all-inclusive at the rate above; no unauthorized accessorials

---

**Signed**: ___________________________  **Date**: ____________
*{rc['carrier_name']} · MC {rc['carrier_mc']}*

---

**Orisei Freight Solutions LLC** · Plymouth, Minnesota
Operations: shearperfection369@gmail.com
"""


def _portal_token() -> str:
    return secrets.token_urlsafe(20)


async def _resend_send(db, *, to: str, subject: str, html: str,
                        attachments: Optional[List[Dict[str, Any]]] = None) -> bool:
    """Send email via Connections vault Resend creds. Returns False if creds
    missing — caller should fall back to a draft entry."""
    try:
        from .connections import get_connection_credentials
        creds = await get_connection_credentials(db, "resend")
    except Exception:
        creds = None
    if not creds or not creds.get("api_key"):
        return False
    try:
        import asyncio
        import resend as _r
        _r.api_key = creds["api_key"]
        from_email = creds.get("from_email") or "onboarding@resend.dev"
        from_name = creds.get("from_name") or "Orisei Freight Solutions"
        payload = {
            "from": f"{from_name} <{from_email}>",
            "to": [to],
            "subject": subject,
            "html": html,
        }
        if attachments:
            payload["attachments"] = attachments
        await asyncio.to_thread(_r.Emails.send, payload)
        return True
    except Exception as exc:
        logger.warning("Resend send failed: %s", exc)
        return False


# ========================================================================
def build_orisei_operations_router(
    api_router: APIRouter, *, db,
    get_current_user: Callable, require_role: Callable,
) -> None:
    """Wire Orisei real-world ops endpoints into the main api_router."""
    router = APIRouter(prefix="/orisei", tags=["orisei-operations"])
    admin_dep = Depends(require_role("admin", "dispatcher"))

    async def _get_active_brand() -> Dict[str, Any]:
        return await db.company_brand.find_one({"is_active": True}, {"_id": 0}) or {}

    # ============================ CUSTOMERS ============================
    @router.get("/customers")
    async def list_customers(active_only: bool = True,
                              user=Depends(get_current_user)) -> Dict[str, Any]:
        q = {"active": True} if active_only else {}
        rows = await db.orisei_customers.find(q, {"_id": 0}).sort("name", 1).to_list(500)
        return {"items": rows, "count": len(rows)}

    @router.get("/customers/{customer_id}")
    async def get_customer(customer_id: str,
                            _=Depends(get_current_user)) -> Dict[str, Any]:
        doc = await db.orisei_customers.find_one({"customer_id": customer_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Customer not found")
        # Attach recent bookings + invoices + open quotes for one-shot UX
        bookings = await db.brokerage_bookings.find(
            {"customer_id": customer_id}, {"_id": 0}
        ).sort("created_at", -1).limit(20).to_list(20)
        invoices = await db.brokerage_invoices.find(
            {"customer_id": customer_id}, {"_id": 0}
        ).sort("issued_at", -1).limit(20).to_list(20)
        quotes = await db.orisei_quotes.find(
            {"customer_id": customer_id}, {"_id": 0}
        ).sort("issued_at", -1).limit(10).to_list(10)
        return {**doc, "recent_bookings": bookings,
                "recent_invoices": invoices, "recent_quotes": quotes}

    @router.post("/customers")
    async def create_customer(payload: CustomerIn, user=admin_dep) -> Dict[str, Any]:
        doc = {
            "customer_id": f"CUST-{uuid.uuid4().hex[:10].upper()}",
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
            "created_by": getattr(user, "name", "system"),
            **payload.model_dump(),
        }
        # contacts is List[BaseModel], convert
        if doc.get("contacts"):
            doc["contacts"] = [c if isinstance(c, dict) else c.model_dump()
                                for c in doc["contacts"]]
        await db.orisei_customers.insert_one(dict(doc))
        doc.pop("_id", None)
        return doc

    @router.put("/customers/{customer_id}")
    async def update_customer(customer_id: str, payload: CustomerIn,
                                user=admin_dep) -> Dict[str, Any]:
        upd = payload.model_dump()
        if upd.get("contacts"):
            upd["contacts"] = [c if isinstance(c, dict) else c
                                for c in upd["contacts"]]
        upd["updated_at"] = _now_iso()
        res = await db.orisei_customers.update_one(
            {"customer_id": customer_id}, {"$set": upd})
        if res.matched_count == 0:
            raise HTTPException(404, "Customer not found")
        return await db.orisei_customers.find_one(
            {"customer_id": customer_id}, {"_id": 0}) or {}

    @router.delete("/customers/{customer_id}")
    async def deactivate_customer(customer_id: str,
                                    user=admin_dep) -> Dict[str, str]:
        res = await db.orisei_customers.update_one(
            {"customer_id": customer_id},
            {"$set": {"active": False, "deactivated_at": _now_iso()}})
        if res.matched_count == 0:
            raise HTTPException(404, "Customer not found")
        return {"status": "deactivated"}

    # ============================ QUOTES ============================
    @router.get("/quotes")
    async def list_quotes(_=Depends(get_current_user)) -> Dict[str, Any]:
        rows = await db.orisei_quotes.find({}, {"_id": 0}).sort(
            "issued_at", -1).limit(100).to_list(100)
        return {"items": rows, "count": len(rows)}

    @router.post("/quotes")
    async def create_quote(payload: QuoteIn, user=admin_dep) -> Dict[str, Any]:
        customer = await db.orisei_customers.find_one(
            {"customer_id": payload.customer_id}, {"_id": 0})
        if not customer:
            raise HTTPException(404, "Customer not found")
        now = datetime.now(timezone.utc)
        quote = {
            "quote_id": f"Q-{uuid.uuid4().hex[:10].upper()}",
            "customer_id": payload.customer_id,
            "customer_name": customer["name"],
            "issued_at": now.isoformat(),
            "valid_until": (now + timedelta(days=payload.valid_for_days)).isoformat(),
            "status": "open",
            "issued_by": getattr(user, "name", "system"),
            "total_usd": _quote_total(payload),
            "accessorials": [a.model_dump() for a in (payload.accessorials or [])],
            **payload.model_dump(exclude={"accessorials"}),
        }
        await db.orisei_quotes.insert_one(dict(quote))
        quote.pop("_id", None)
        return quote

    @router.get("/quotes/{quote_id}/pdf")
    async def quote_pdf(quote_id: str,
                         _=Depends(get_current_user)) -> StreamingResponse:
        quote = await db.orisei_quotes.find_one({"quote_id": quote_id}, {"_id": 0})
        if not quote:
            raise HTTPException(404, "Quote not found")
        customer = await db.orisei_customers.find_one(
            {"customer_id": quote["customer_id"]}, {"_id": 0}) or {}
        brand = await _get_active_brand()
        pdf = build_branded_markdown_pdf(
            _quote_markdown(quote, customer),
            title=f"Freight Quote · {quote_id}",
            subtitle=f"Prepared for {customer.get('name', 'Customer')}",
            brand=brand,
        )
        return StreamingResponse(io.BytesIO(pdf), media_type="application/pdf",
            headers={"Content-Disposition":
                f'attachment; filename="Orisei_Quote_{quote_id}.pdf"'})

    @router.post("/quotes/{quote_id}/send")
    async def send_quote(quote_id: str, user=admin_dep) -> Dict[str, Any]:
        quote = await db.orisei_quotes.find_one({"quote_id": quote_id}, {"_id": 0})
        if not quote:
            raise HTTPException(404, "Quote not found")
        customer = await db.orisei_customers.find_one(
            {"customer_id": quote["customer_id"]}, {"_id": 0}) or {}
        to_email = (customer.get("primary_contact_email")
                     or customer.get("ap_email"))
        if not to_email:
            raise HTTPException(400, "Customer has no primary contact or AP email")
        brand = await _get_active_brand()
        pdf = build_branded_markdown_pdf(
            _quote_markdown(quote, customer),
            title=f"Freight Quote · {quote_id}",
            subtitle=f"Prepared for {customer.get('name', 'Customer')}",
            brand=brand,
        )
        import base64
        html = (f"<p>Hi {customer.get('primary_contact_name', 'team')},</p>"
                f"<p>Freight quote <b>{quote_id}</b> attached for "
                f"<b>{quote['origin']} → {quote['destination']}</b>.</p>"
                f"<p>All-in: <b>${quote['total_usd']:,.2f}</b> · "
                f"valid {quote['valid_for_days']} days · "
                f"terms {customer.get('payment_terms', 'Net 30')}.</p>"
                f"<p>Reply to accept and we'll dispatch a carrier "
                f"within 4 hours.</p>"
                f"<p>Thanks,<br>Oliver Cummins<br>Orisei Freight Solutions</p>")
        sent = await _resend_send(db, to=to_email,
            subject=f"Orisei freight quote · {quote['origin']} → {quote['destination']} · ${quote['total_usd']:,.0f}",
            html=html, attachments=[{
                "filename": f"Orisei_Quote_{quote_id}.pdf",
                "content": base64.b64encode(pdf).decode(),
            }])
        await db.orisei_quotes.update_one({"quote_id": quote_id},
            {"$set": {"sent_at": _now_iso(), "sent_to": to_email,
                      "send_status": "sent" if sent else "drafted"}})
        return {"sent": sent, "to": to_email, "status": "sent" if sent else "drafted"}

    # ============================ RATE CONFIRMATIONS ============================
    @router.get("/rate-confirmations")
    async def list_rate_cons(_=Depends(get_current_user)) -> Dict[str, Any]:
        rows = await db.orisei_rate_confirmations.find(
            {}, {"_id": 0}).sort("issued_at", -1).limit(100).to_list(100)
        return {"items": rows, "count": len(rows)}

    @router.post("/rate-confirmations")
    async def create_rate_con(payload: RateConfirmationIn,
                                user=admin_dep) -> Dict[str, Any]:
        booking = await db.brokerage_bookings.find_one(
            {"booking_id": payload.booking_id}, {"_id": 0})
        if not booking:
            raise HTTPException(404, "Booking not found")
        rc = {
            "rc_id": f"RC-{uuid.uuid4().hex[:10].upper()}",
            "issued_at": _now_iso(),
            "issued_by": getattr(user, "name", "system"),
            "status": "issued",
            **payload.model_dump(),
        }
        await db.orisei_rate_confirmations.insert_one(dict(rc))
        # Stamp booking with rate-con
        await db.brokerage_bookings.update_one(
            {"booking_id": payload.booking_id},
            {"$set": {"rate_con_id": rc["rc_id"],
                      "carrier_mc": payload.carrier_mc,
                      "carrier_rate_usd": payload.rate_usd}})
        rc.pop("_id", None)
        return rc

    @router.get("/rate-confirmations/{rc_id}/pdf")
    async def rate_con_pdf(rc_id: str,
                            _=Depends(get_current_user)) -> StreamingResponse:
        rc = await db.orisei_rate_confirmations.find_one({"rc_id": rc_id}, {"_id": 0})
        if not rc:
            raise HTTPException(404, "Rate confirmation not found")
        booking = await db.brokerage_bookings.find_one(
            {"booking_id": rc["booking_id"]}, {"_id": 0}) or {}
        brand = await _get_active_brand()
        pdf = build_branded_markdown_pdf(
            _rate_con_markdown(rc, booking),
            title=f"Rate Confirmation · {rc_id}",
            subtitle=f"For {rc['carrier_name']} · MC {rc['carrier_mc']}",
            brand=brand,
        )
        return StreamingResponse(io.BytesIO(pdf), media_type="application/pdf",
            headers={"Content-Disposition":
                f'attachment; filename="Orisei_RateCon_{rc_id}.pdf"'})

    @router.post("/rate-confirmations/{rc_id}/send")
    async def send_rate_con(rc_id: str, user=admin_dep) -> Dict[str, Any]:
        rc = await db.orisei_rate_confirmations.find_one({"rc_id": rc_id}, {"_id": 0})
        if not rc:
            raise HTTPException(404, "Rate confirmation not found")
        to_email = rc.get("carrier_contact_email")
        if not to_email:
            raise HTTPException(400, "Carrier has no contact email on this rate-con")
        booking = await db.brokerage_bookings.find_one(
            {"booking_id": rc["booking_id"]}, {"_id": 0}) or {}
        brand = await _get_active_brand()
        pdf = build_branded_markdown_pdf(
            _rate_con_markdown(rc, booking),
            title=f"Rate Confirmation · {rc_id}",
            subtitle=f"For {rc['carrier_name']} · MC {rc['carrier_mc']}",
            brand=brand,
        )
        import base64
        html = (f"<p>Hi {rc['carrier_name']} team,</p>"
                f"<p>Rate confirmation <b>{rc_id}</b> attached for booking "
                f"<b>{rc['booking_id']}</b>:</p>"
                f"<ul>"
                f"<li>{booking.get('origin')} → {booking.get('destination')}</li>"
                f"<li>Pickup {rc.get('pickup_date') or booking.get('pickup_date', 'TBD')}</li>"
                f"<li>All-in rate: <b>${rc['rate_usd']:,.2f}</b></li>"
                f"</ul>"
                f"<p>Please sign and return within 2 hours to confirm. "
                f"QuickPay {'available at ' + str(rc.get('quickpay_fee_pct', 3)) + '%' if rc.get('quickpay_offered') else 'not offered on this load'}.</p>"
                f"<p>Oliver Cummins<br>Orisei Freight Solutions<br>"
                f"shearperfection369@gmail.com</p>")
        sent = await _resend_send(db, to=to_email,
            subject=f"Rate Con {rc_id} · {booking.get('origin')} → {booking.get('destination')} · ${rc['rate_usd']:,.0f}",
            html=html, attachments=[{
                "filename": f"Orisei_RateCon_{rc_id}.pdf",
                "content": base64.b64encode(pdf).decode(),
            }])
        await db.orisei_rate_confirmations.update_one({"rc_id": rc_id},
            {"$set": {"sent_at": _now_iso(), "sent_to": to_email,
                      "send_status": "sent" if sent else "drafted"}})
        return {"sent": sent, "to": to_email, "status": "sent" if sent else "drafted"}

    # ============================ CUSTOMER PORTAL ============================
    @router.post("/customers/{customer_id}/portal-link")
    async def generate_portal_link(customer_id: str, payload: PortalLinkIn,
                                    request: Request,
                                    user=admin_dep) -> Dict[str, Any]:
        customer = await db.orisei_customers.find_one(
            {"customer_id": customer_id}, {"_id": 0})
        if not customer:
            raise HTTPException(404, "Customer not found")
        token = _portal_token()
        doc = {
            "token": token, "customer_id": customer_id,
            "customer_name": customer["name"],
            "created_at": _now_iso(),
            "expires_at": (datetime.now(timezone.utc)
                           + timedelta(days=payload.days_valid or 90)).isoformat(),
            "status": "active",
            "notes": payload.notes,
            "visits": [],
        }
        await db.orisei_customer_portal_tokens.insert_one(dict(doc))
        origin = request.headers.get("origin") or ""
        if not origin:
            ref = request.headers.get("referer") or ""
            if ref:
                from urllib.parse import urlparse
                p = urlparse(ref)
                if p.scheme and p.netloc:
                    origin = f"{p.scheme}://{p.netloc}"
        share_url = f"{origin.rstrip('/')}/customer-portal?token={token}"
        return {"token": token, "share_url": share_url,
                "expires_at": doc["expires_at"], "customer_name": customer["name"]}

    api_router.include_router(router)

    # ============================ PUBLIC CUSTOMER PORTAL ============================
    public = APIRouter(prefix="/public/customer-portal", tags=["customer-portal", "public"])

    @public.get("/{token}")
    async def customer_portal_data(token: str, request: Request) -> Dict[str, Any]:
        doc = await db.orisei_customer_portal_tokens.find_one(
            {"token": token}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Portal link not found")
        if doc.get("status") == "disabled":
            raise HTTPException(410, "Portal link disabled")
        try:
            exp = datetime.fromisoformat(doc["expires_at"].replace("Z", "+00:00"))
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > exp:
                raise HTTPException(410, "Portal link expired")
        except ValueError:
            pass
        # Log visit
        await db.orisei_customer_portal_tokens.update_one({"token": token},
            {"$push": {"visits": {"at": _now_iso(),
                                   "ip": (request.client.host if request.client else None),
                                   "ua": request.headers.get("user-agent", "")[:300]}}})
        customer = await db.orisei_customers.find_one(
            {"customer_id": doc["customer_id"]}, {"_id": 0}) or {}
        # Bookings + invoices + open quotes for this customer
        bookings = await db.brokerage_bookings.find(
            {"$or": [{"customer_id": doc["customer_id"]},
                     {"customer_name": doc["customer_name"]}]}, {"_id": 0}
        ).sort("created_at", -1).limit(50).to_list(50)
        invoices = await db.brokerage_invoices.find(
            {"$or": [{"customer_id": doc["customer_id"]},
                     {"customer_name": doc["customer_name"]}]}, {"_id": 0}
        ).sort("issued_at", -1).limit(50).to_list(50)
        quotes = await db.orisei_quotes.find(
            {"customer_id": doc["customer_id"]}, {"_id": 0}
        ).sort("issued_at", -1).limit(20).to_list(20)
        # Summary
        active = sum(1 for b in bookings if b.get("status")
                      in ("booked", "tendered", "in_transit"))
        delivered_30d = sum(1 for b in bookings if b.get("status") == "delivered"
                             and b.get("delivered_at", "") > (datetime.now(timezone.utc)
                             - timedelta(days=30)).isoformat())
        outstanding_invoices = sum(float(i.get("amount_usd") or 0)
                                    for i in invoices if i.get("status") == "issued")
        return {
            "customer_name": doc["customer_name"],
            "customer": {
                "name": customer.get("name"),
                "primary_contact_name": customer.get("primary_contact_name"),
                "payment_terms": customer.get("payment_terms", "Net 30"),
            },
            "summary": {
                "active_shipments": active,
                "delivered_past_30d": delivered_30d,
                "outstanding_invoices_usd": round(outstanding_invoices, 2),
                "open_quotes": sum(1 for q in quotes if q.get("status") == "open"),
            },
            "bookings": bookings, "invoices": invoices, "quotes": quotes,
        }

    api_router.include_router(public)
