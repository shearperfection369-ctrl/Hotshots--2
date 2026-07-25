"""routes.shipper_intake — Branded shipper intake template + public submit.

Workflow:
  1. Dispatcher creates an intake request → mints unique token + branded PDF
     with a "Submit online" URL printed on it.
  2. Dispatcher emails the PDF (via Resend if configured, mailto fallback
     otherwise) to the shipper's contact.
  3. Shipper visits the public URL (no login), fills the form, hits submit.
  4. Submission creates a `brokerage_bookings` doc with
     status='pending_review' and source='shipper_intake', so the new
     booking lands in the broker's Workflow inbox.

Endpoints — all mounted under /api/intake/*:

  AUTH (broker):
    POST   /requests                       · create new intake request
    GET    /requests                       · list requests
    GET    /requests/{request_id}          · detail
    GET    /requests/{request_id}/pdf      · branded fillable template PDF
    POST   /requests/{request_id}/email    · email to shipper via Resend

  PUBLIC (shipper — token-gated, no auth):
    GET    /public/{token}                 · returns brand + prefill
    POST   /public/{token}/submit          · creates pending_review booking
"""
from __future__ import annotations

import io
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr, Field


# -------------------- MODELS --------------------
class IntakeRequestIn(BaseModel):
    shipper_name: str = Field(..., max_length=200)
    shipper_email: Optional[EmailStr] = None
    shipper_contact_name: Optional[str] = Field(None, max_length=120)
    expires_in_days: int = Field(30, ge=1, le=180)
    # Optional prefill — broker can pre-fill known fields before sending
    prefill_origin: Optional[str] = Field(None, max_length=200)
    prefill_destination: Optional[str] = Field(None, max_length=200)
    prefill_commodity: Optional[str] = Field(None, max_length=200)
    prefill_equipment: Optional[str] = Field(None, max_length=80)
    prefill_pickup_date: Optional[str] = None
    prefill_delivery_date: Optional[str] = None
    note_to_shipper: Optional[str] = Field(None, max_length=1000)


class IntakeSubmissionIn(BaseModel):
    shipper_name: str = Field(..., max_length=200)
    shipper_contact_name: Optional[str] = Field(None, max_length=120)
    shipper_email: Optional[EmailStr] = None
    shipper_phone: Optional[str] = Field(None, max_length=40)
    origin_address: str = Field(..., max_length=400)
    destination_address: str = Field(..., max_length=400)
    pickup_date: str = Field(..., max_length=20)
    pickup_window_start: Optional[str] = Field(None, max_length=20)
    pickup_window_end: Optional[str] = Field(None, max_length=20)
    delivery_date: Optional[str] = Field(None, max_length=20)
    delivery_window_start: Optional[str] = Field(None, max_length=20)
    delivery_window_end: Optional[str] = Field(None, max_length=20)
    commodity: str = Field(..., max_length=400)
    weight_lbs: Optional[float] = Field(None, ge=0)
    pieces: Optional[int] = Field(None, ge=0)
    equipment_required: str = Field("Dry Van", max_length=80)
    hazmat: bool = False
    un_number: Optional[str] = Field(None, max_length=10)
    hazmat_class: Optional[str] = Field(None, max_length=20)
    pickup_special_instructions: Optional[str] = Field(None, max_length=2000)
    delivery_special_instructions: Optional[str] = Field(None, max_length=2000)
    references: Optional[str] = Field(None, max_length=400)


# -------------------- HELPERS --------------------
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _public_base_url() -> str:
    """Where the public submit page lives — used in the PDF link/QR."""
    return (os.environ.get("PUBLIC_FRONTEND_URL")
            or os.environ.get("FRONTEND_URL")
            or "https://app.orisei.example.com").rstrip("/")


def _intake_template_md(req: Dict[str, Any], brand: Dict[str, Any]) -> str:
    """Build the markdown for the branded intake template PDF.

    Includes a "Submit online" callout with the public URL the shipper can
    use to fill the form via the web (no login). Bullets render as branded
    label/value tables via build_branded_markdown_pdf's coalescing logic.
    """
    submit_url = f"{_public_base_url()}/i/{req['token']}"
    company = (brand or {}).get("company_name") or "Orisei Freight Solutions LLC"
    note = (req.get("note_to_shipper") or "").strip()
    note_block = f"\n> {note}\n" if note else ""
    return f"""# Shipper Intake · {req['request_id']}

**Prepared for**: {req['shipper_name']}
**Issued**: {req['created_at'][:10]}
**Valid through**: {req['expires_at'][:10]}

---

## Submit Online · One-Click
- **URL**: {submit_url}
- **Token**: {req['token']}
- **Or**: complete the fields below, sign, and email back to
  `oliver@oriseifreightsolutions.com` — we'll key it in for you.

---

## Shipper
- **Company / Shipper name**: {req.get('shipper_name')}
- **Primary contact**: ____________________
- **Email**: ____________________
- **Phone**: ____________________

## Origin (Pickup)
- **Facility name**: ____________________
- **Street / Suite**: ____________________
- **City, State, ZIP**: ____________________
- **Pickup date (target)**: {req.get('prefill_pickup_date') or '____________________'}
- **Pickup window**: ____________________ to ____________________
- **Special instructions**: ____________________

## Destination (Delivery)
- **Facility name**: ____________________
- **Street / Suite**: ____________________
- **City, State, ZIP**: ____________________
- **Delivery date (target)**: {req.get('prefill_delivery_date') or '____________________'}
- **Delivery window**: ____________________ to ____________________
- **Special instructions**: ____________________

## Freight Details
- **Commodity**: {req.get('prefill_commodity') or '____________________'}
- **Total weight (lbs)**: ____________________
- **Piece count / pallet count**: ____________________
- **Equipment required**: {req.get('prefill_equipment') or '____________________  (Dry Van / Reefer / Flatbed / Step Deck)'}
- **Hazardous?**: ☐ No  ☐ Yes — UN # ____________  Class ____________
- **Customer references / PO #**: ____________________
{note_block}
---

## Shipper Authorization
By signing below, the shipper authorizes {company} to arrange the freight
described above and confirms the information is true and complete.

- **Signed**: ______________________________
- **Print name**: ______________________________
- **Title**: ______________________________
- **Date**: ______________________________
"""


# -------------------- ROUTER --------------------
def build_shipper_intake_router(
    api_router: APIRouter, *, db,
    get_current_user: Callable, require_role: Callable,
    send_email_fn: Optional[Callable] = None,
) -> None:
    """Mount the shipper intake module under /api/intake/*."""
    router = APIRouter(prefix="/intake", tags=["intake"])
    admin_dep = Depends(require_role("admin", "dispatcher"))

    async def _active_brand() -> Dict[str, Any]:
        return await db.company_brand.find_one({"is_active": True}, {"_id": 0}) or {}

    async def _build_pdf(req: Dict[str, Any]) -> bytes:
        brand = await _active_brand()
        from routes.orisei_docs import build_branded_markdown_pdf
        return build_branded_markdown_pdf(
            _intake_template_md(req, brand),
            title=f"Shipper Intake · {req['request_id']}",
            subtitle=f"Prepared for {req['shipper_name']}",
            doc_id=req["request_id"], brand=brand,
        )

    # ======================== AUTH ENDPOINTS ========================
    @router.post("/requests")
    async def create_request(payload: IntakeRequestIn,
                              user=admin_dep) -> Dict[str, Any]:
        expires_at = (datetime.now(timezone.utc)
                      + timedelta(days=payload.expires_in_days))
        doc = {
            "request_id": f"INTAKE-{uuid.uuid4().hex[:10].upper()}",
            "token": secrets.token_urlsafe(20),
            "status": "pending",  # pending → submitted → booked
            "created_at": _now_iso(),
            "created_by": getattr(user, "name", "system"),
            "created_by_email": getattr(user, "email", None),
            "expires_at": expires_at.isoformat(),
            "shipper_name": payload.shipper_name,
            "shipper_email": payload.shipper_email,
            "shipper_contact_name": payload.shipper_contact_name,
            "prefill_origin": payload.prefill_origin,
            "prefill_destination": payload.prefill_destination,
            "prefill_commodity": payload.prefill_commodity,
            "prefill_equipment": payload.prefill_equipment,
            "prefill_pickup_date": payload.prefill_pickup_date,
            "prefill_delivery_date": payload.prefill_delivery_date,
            "note_to_shipper": payload.note_to_shipper,
        }
        await db.shipper_intake_requests.insert_one(dict(doc))
        doc.pop("_id", None)
        doc["submit_url"] = f"{_public_base_url()}/i/{doc['token']}"
        return doc

    @router.get("/requests")
    async def list_requests(_=Depends(get_current_user)) -> Dict[str, Any]:
        rows = await db.shipper_intake_requests.find(
            {}, {"_id": 0}).sort("created_at", -1).limit(200).to_list(200)
        for r in rows:
            r["submit_url"] = f"{_public_base_url()}/i/{r['token']}"
        return {"items": rows, "count": len(rows)}

    @router.get("/requests/{request_id}")
    async def get_request(request_id: str,
                           _=Depends(get_current_user)) -> Dict[str, Any]:
        r = await db.shipper_intake_requests.find_one(
            {"request_id": request_id}, {"_id": 0})
        if not r:
            raise HTTPException(404, "Intake request not found")
        r["submit_url"] = f"{_public_base_url()}/i/{r['token']}"
        return r

    @router.get("/requests/{request_id}/pdf")
    async def request_pdf(request_id: str,
                           _=Depends(get_current_user)) -> StreamingResponse:
        r = await db.shipper_intake_requests.find_one(
            {"request_id": request_id}, {"_id": 0})
        if not r:
            raise HTTPException(404, "Intake request not found")
        pdf = await _build_pdf(r)
        return StreamingResponse(
            io.BytesIO(pdf), media_type="application/pdf",
            headers={"Content-Disposition":
                f'attachment; filename="ShipperIntake_{request_id}.pdf"'})

    @router.post("/requests/{request_id}/email")
    async def email_request(request_id: str,
                             user=admin_dep) -> Dict[str, Any]:
        r = await db.shipper_intake_requests.find_one(
            {"request_id": request_id}, {"_id": 0})
        if not r:
            raise HTTPException(404, "Intake request not found")
        if not r.get("shipper_email"):
            raise HTTPException(400, "Shipper email not on file — set it before emailing")
        pdf = await _build_pdf(r)
        submit_url = f"{_public_base_url()}/i/{r['token']}"
        subject = f"Freight Intake · please complete · {r['request_id']}"
        body = (
            f"Hi {r.get('shipper_contact_name') or r['shipper_name']},\n\n"
            f"Please complete the attached freight intake form so we can "
            f"begin sourcing your shipment.\n\n"
            f"You can submit online with one click here:\n  {submit_url}\n\n"
            f"This link is valid until {r['expires_at'][:10]}.\n\n"
            f"Questions? Reply to this email.\n\n"
            f"— {r.get('created_by') or 'Orisei Operations'}"
        )
        delivered_via = "mocked"
        delivery_id: Optional[str] = None
        if send_email_fn:
            try:
                delivery_id = await send_email_fn(
                    to=r["shipper_email"], subject=subject, text=body,
                    attachments=[{"filename": f"ShipperIntake_{request_id}.pdf",
                                   "content": pdf,
                                   "content_type": "application/pdf"}],
                )
                delivered_via = "resend"
            except Exception as e:                                  # noqa: BLE001
                delivered_via = f"failed: {e!s}"
        await db.shipper_intake_requests.update_one(
            {"request_id": request_id},
            {"$set": {
                "last_emailed_at": _now_iso(),
                "last_emailed_to": r["shipper_email"],
                "last_email_delivery_via": delivered_via,
                "last_email_delivery_id": delivery_id,
            }})
        return {"ok": True, "via": delivered_via, "delivery_id": delivery_id,
                "submit_url": submit_url}

    # ======================== PUBLIC ENDPOINTS ========================
    public = APIRouter(prefix="/intake/public", tags=["intake-public"])

    @public.get("/{token}")
    async def public_get(token: str) -> Dict[str, Any]:
        r = await db.shipper_intake_requests.find_one({"token": token}, {"_id": 0})
        if not r:
            raise HTTPException(404, "Intake link not found or has been deleted")
        now = datetime.now(timezone.utc).isoformat()
        if (r.get("expires_at") or "") < now:
            raise HTTPException(410, "Intake link has expired — please request a new one")
        if r["status"] == "submitted":
            return {"status": "already_submitted",
                    "submitted_at": r.get("submitted_at"),
                    "message": "This intake form has already been submitted. Thank you."}
        brand = await _active_brand()
        # Strip internal fields before returning to the public.
        return {
            "status": "ready",
            "request_id": r["request_id"],
            "shipper_name": r["shipper_name"],
            "shipper_contact_name": r.get("shipper_contact_name"),
            "shipper_email": r.get("shipper_email"),
            "prefill": {
                "origin": r.get("prefill_origin"),
                "destination": r.get("prefill_destination"),
                "commodity": r.get("prefill_commodity"),
                "equipment": r.get("prefill_equipment"),
                "pickup_date": r.get("prefill_pickup_date"),
                "delivery_date": r.get("prefill_delivery_date"),
            },
            "note_to_shipper": r.get("note_to_shipper"),
            "expires_at": r.get("expires_at"),
            "brand": {
                "company_name": brand.get("company_name") or "Orisei Freight Solutions LLC",
                "short_name": brand.get("short_name") or "Orisei",
                "primary_color": brand.get("primary_color") or "#0E3A6B",
                "accent_color": brand.get("accent_color") or "#C9A24A",
                "tagline": brand.get("tagline") or "Mission-control transportation",
            },
        }

    @public.post("/{token}/submit")
    async def public_submit(token: str,
                              payload: IntakeSubmissionIn) -> Dict[str, Any]:
        r = await db.shipper_intake_requests.find_one({"token": token})
        if not r:
            raise HTTPException(404, "Intake link not found")
        now_iso = _now_iso()
        if (r.get("expires_at") or "") < now_iso:
            raise HTTPException(410, "Intake link has expired — please request a new one")
        if r.get("status") == "submitted":
            raise HTTPException(409, "This intake has already been submitted")

        # Persist the submission payload + spawn a pending_review brokerage
        # booking so the broker sees it in their inbox.
        booked_id = f"BK-{uuid.uuid4().hex[:10].upper()}"
        booking = {
            "booked_id": booked_id,
            "status": "pending_review",
            "source": "shipper_intake",
            "intake_request_id": r["request_id"],
            "intake_token": token,
            "is_sample": False,
            "booked_at": now_iso,
            "booked_by": "shipper-self-service",
            # Standard brokerage_booking shape so it lights up the workflow grid
            "shipper_name": payload.shipper_name,
            "shipper_contact_name": payload.shipper_contact_name,
            "shipper_contact_email": payload.shipper_email,
            "shipper_contact_phone": payload.shipper_phone,
            "origin": payload.origin_address,
            "destination": payload.destination_address,
            "pickup_date": payload.pickup_date,
            "pickup_window_start": payload.pickup_window_start,
            "pickup_window_end": payload.pickup_window_end,
            "delivery_date": payload.delivery_date,
            "delivery_window_start": payload.delivery_window_start,
            "delivery_window_end": payload.delivery_window_end,
            "commodity": payload.commodity,
            "weight_lbs": payload.weight_lbs,
            "pieces": payload.pieces,
            "equipment": payload.equipment_required,
            "hazmat": payload.hazmat,
            "un_number": payload.un_number,
            "hazmat_class": payload.hazmat_class,
            "pickup_instructions": payload.pickup_special_instructions,
            "delivery_instructions": payload.delivery_special_instructions,
            "references": payload.references,
            # margin/rate fields left null — broker fills in on accept
            "rate_usd": None, "carrier_name": None, "carrier_mc": None,
            "margin_pct": None, "forecast_margin_usd": None,
        }
        await db.brokerage_bookings.insert_one(dict(booking))

        await db.shipper_intake_requests.update_one(
            {"token": token},
            {"$set": {
                "status": "submitted",
                "submitted_at": now_iso,
                "submitted_payload": payload.model_dump(),
                "linked_booked_id": booked_id,
            }})

        # Notify the broker if Resend wiring is provided.
        if send_email_fn and r.get("created_by_email"):
            try:
                await send_email_fn(
                    to=r["created_by_email"],
                    subject=f"New shipper intake submitted · {payload.shipper_name}",
                    text=(f"A shipper just submitted intake form {r['request_id']}.\n\n"
                          f"Shipper: {payload.shipper_name}\n"
                          f"Origin: {payload.origin_address}\n"
                          f"Destination: {payload.destination_address}\n"
                          f"Pickup: {payload.pickup_date}\n"
                          f"Commodity: {payload.commodity}\n"
                          f"Equipment: {payload.equipment_required}\n\n"
                          f"New booking is in Workflow with status 'pending_review':\n"
                          f"  {_public_base_url()}/workflow?booked_id={booked_id}\n"),
                )
            except Exception:                                       # noqa: BLE001
                pass

        return {
            "ok": True,
            "booked_id": booked_id,
            "message": "Thank you. Your freight request has been received "
                       "and a member of our operations team will reach out "
                       "within 4 business hours to confirm carrier + rate.",
        }

    api_router.include_router(router)
    api_router.include_router(public)
