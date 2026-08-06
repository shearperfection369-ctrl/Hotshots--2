"""routes.truck_cleaning_biz — Orisei Truck Cleaning: doc vault, client onboarding, invoicing & payments."""
import io
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import resend
import stripe
from bson import ObjectId
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from motor.motor_asyncio import AsyncIOMotorGridFSBucket
from pydantic import BaseModel, Field
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen.canvas import Canvas

from routes.connections import get_connection_credentials
from routes.truck_cleaning_field import _public_base

logger = logging.getLogger(__name__)
LOGO_PATH = Path(__file__).resolve().parent / "_tc_logo_pdf.png"
VAULT_CATEGORIES = ["Insurance / COI", "Signed Agreement", "W-9 / Tax", "Before-After Photos",
                    "Permits & Licenses", "Receipts", "Marketing Assets", "Other"]
PLAN_RATES = {"one_time": 150.0, "biweekly_sub": 120.0, "fleet_sub": 125.0}
INK, AMBER, CYAN = colors.HexColor("#0D1117"), colors.HexColor("#F59E0B"), colors.HexColor("#22D3EE")
SLATE, PAPER = colors.HexColor("#334155"), colors.HexColor("#FAFAF7")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def auto_invoice_for_job(db, job_id: str) -> Optional[Dict[str, Any]]:
    """Create a draft invoice for a freshly-completed job (idempotent)."""
    job = await db.tc_jobs.find_one({"job_id": job_id}, {"_id": 0})
    if not job:
        return None
    if await db.tc_invoices.find_one({"job_ids": job_id}, {"_id": 1}):
        return None
    client = await db.tc_clients.find_one({"client_id": job["client_id"]}, {"_id": 0}) or {}
    ups = f" + {', '.join(u.replace('_', ' ') for u in job.get('upsells', []))}" if job.get("upsells") else ""
    inv = {"invoice_id": f"INV-TC-{uuid.uuid4().hex[:6].upper()}", "client_id": job["client_id"],
           "company": client.get("company", job.get("company", "")), "email": client.get("email", ""),
           "line_items": [{"desc": f"{job['date']} — Cab cleaning × {job['cabs']}{ups} ({job_id})",
                           "amount": job.get("price", 0)}],
           "total": round(job.get("price", 0), 2), "status": "draft", "job_ids": [job_id],
           "notes": "Auto-created on job completion", "auto_created": True,
           "due_date": (datetime.now(timezone.utc) + timedelta(days=15)).isoformat(),
           "created_at": _now(), "paid_at": None, "stripe_session_id": None}
    await db.tc_invoices.insert_one(dict(inv))
    inv.pop("_id", None)
    await db.tc_jobs.update_one({"job_id": job_id}, {"$set": {"invoice_id": inv["invoice_id"]}})
    return inv


class OnboardInviteIn(BaseModel):
    company: str = Field("", max_length=150)
    contact: str = Field("", max_length=100)
    email: str = Field("", max_length=200)


class OnboardSubmitIn(BaseModel):
    company: str = Field(..., min_length=2, max_length=150)
    contact: str = Field(..., min_length=2, max_length=100)
    phone: str = Field("", max_length=40)
    email: str = Field(..., min_length=5, max_length=200)
    cabs: int = Field(1, ge=1, le=500)
    plan: str = Field("one_time")
    fleet_notes: str = Field("", max_length=800)
    yard_address: str = Field("", max_length=300)
    agreement_accepted: bool = False


class InvoiceCreateIn(BaseModel):
    client_id: str
    job_ids: List[str] = Field(default_factory=list)
    custom_items: List[Dict[str, Any]] = Field(default_factory=list)  # {desc, amount}
    due_days: int = Field(15, ge=0, le=90)
    notes: str = Field("", max_length=500)


class InvoiceEditIn(BaseModel):
    line_items: List[Dict[str, Any]] = Field(default_factory=list)  # {desc, amount}
    due_date: str = Field("", max_length=40)
    notes: str = Field("", max_length=500)


class InvoiceEmailIn(BaseModel):
    to_email: str = Field(..., min_length=5, max_length=200)
    message: str = Field("", max_length=800)


class CheckoutIn(BaseModel):
    origin_url: str = Field(..., max_length=300)


# ---------------- branded PDF helpers ----------------
def _page_frame(c: Canvas, W: float, H: float, title: str, subtitle: str):
    c.setFillColor(INK); c.rect(0, H - 110, W, 110, fill=1, stroke=0)
    c.setFillColor(AMBER); c.rect(0, H - 116, W, 6, fill=1, stroke=0)
    x_text = 46
    if LOGO_PATH.exists():
        try:
            c.drawImage(str(LOGO_PATH), 42, H - 100, width=88, height=88,
                        preserveAspectRatio=True, mask="auto")
            x_text = 142
        except Exception:  # noqa: BLE001
            pass
    c.setFont("Helvetica-Bold", 22); c.setFillColor(colors.white)
    c.drawString(x_text, H - 50, "ORISEI")
    c.setFillColor(AMBER)
    c.drawString(x_text + c.stringWidth("ORISEI ", "Helvetica-Bold", 22), H - 50, "TRUCK CLEANING")
    c.setFont("Helvetica", 9.5); c.setFillColor(colors.HexColor("#9CA3AF"))
    c.drawString(x_text, H - 68, "Your cab. Showroom clean. Every time.  ·  Twin Cities, MN  ·  oliver@oriseifreightsolutions.com")
    c.setFont("Helvetica-Bold", 10); c.setFillColor(CYAN)
    c.drawString(x_text, H - 88, title.upper())
    if subtitle:
        c.setFont("Helvetica", 8.5); c.setFillColor(colors.HexColor("#9CA3AF"))
        c.drawString(x_text + c.stringWidth(title.upper() + "   ", "Helvetica-Bold", 10), H - 88, subtitle)
    c.setFillColor(PAPER); c.rect(0, 46, W, H - 162, fill=1, stroke=0)
    c.setFillColor(INK); c.rect(0, 0, W, 46, fill=1, stroke=0)
    c.setFont("Helvetica", 8); c.setFillColor(colors.HexColor("#9CA3AF"))
    c.drawCentredString(W / 2, 18, "Orisei Truck Cleaning Solutions · a division of Orisei Freight Solutions LLC · Minneapolis–St. Paul, MN")


def _welcome_packet_pdf(ob: Dict[str, Any]) -> bytes:
    W, H = letter
    buf = io.BytesIO()
    c = Canvas(buf, pagesize=letter)
    _page_frame(c, W, H, "Welcome Packet", ob.get("onboard_id", ""))
    y = H - 150
    c.setFont("Helvetica-Bold", 18); c.setFillColor(INK)
    c.drawString(46, y, f"Welcome aboard, {ob.get('company', 'Partner')}!"); y -= 26
    c.setFont("Helvetica", 10); c.setFillColor(SLATE)
    for line in [
        f"Contact: {ob.get('contact') or '—'}   ·   {ob.get('email') or ''}   ·   {ob.get('phone') or ''}",
        f"Fleet size: {ob.get('cabs', 1)} cab(s)   ·   Plan: {ob.get('plan', 'one_time').replace('_', ' ').title()}   ·   Rate: ${ob.get('rate', 150):.0f}/cab",
    ]:
        c.drawString(46, y, line); y -= 16
    y -= 12

    def h2(t, yy):
        c.setFont("Helvetica-Bold", 13); c.setFillColor(AMBER); c.drawString(46, yy, t); return yy - 20

    def li(t, yy, bold=""):
        c.setFillColor(CYAN); c.circle(52, yy + 3, 2, fill=1, stroke=0)
        x = 62
        if bold:
            c.setFont("Helvetica-Bold", 9.5); c.setFillColor(INK); c.drawString(x, yy, bold + " — ")
            x += c.stringWidth(bold + " — ", "Helvetica-Bold", 9.5)
        c.setFont("Helvetica", 9.5); c.setFillColor(SLATE); c.drawString(x, yy, t)
        return yy - 16

    y = h2("WHAT HAPPENS NEXT", y)
    y = li("Our crew lead calls within 1 business day to lock your first service window.", y, "Step 1")
    y = li("We confirm yard access + vehicle list 24h before every visit via SMS.", y, "Step 2")
    y = li("Every clean ships with time-stamped before/after photo proof.", y, "Step 3")
    y = li("Invoices auto-generate on completion — pay by card, ACH, or check. Net 15.", y, "Step 4")
    y -= 10; y = h2("YOUR 45-MINUTE SHOWROOM SPEC", y)
    for item in ["Dashboard wipe + full vacuum", "Seat deep clean — stain removal + odor treatment",
                 "Floor scrub: mats, undercarriage, pedals", "Windows inside + out",
                 "Air freshener + odor eliminator"]:
        y = li(item, y)
    y -= 10; y = h2("OPTIONAL UPSELLS", y)
    y = li("Engine bay degrease $25 · Tire dressing $20 · Cabin air filter $15", y)
    y -= 10; y = h2("LOYALTY", y)
    y = li("Every 10th cleaning is free. Refer a fleet — get $50 off your next service.", y)
    y -= 10; y = h2("YOUR DEDICATED CONTACT", y)
    y = li("Oliver Cummins · oliver@oriseifreightsolutions.com · (763) 443-4459", y, "Owner-operator")
    c.save()
    return buf.getvalue()


def _invoice_pdf(inv: Dict[str, Any], pay_url: str = "") -> bytes:
    W, H = letter
    buf = io.BytesIO()
    c = Canvas(buf, pagesize=letter)
    _page_frame(c, W, H, "Invoice", inv["invoice_id"])
    y = H - 150
    c.setFont("Helvetica-Bold", 18); c.setFillColor(INK); c.drawString(46, y, f"Invoice {inv['invoice_id']}")
    status = inv.get("status", "draft").upper()
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(colors.HexColor("#059669") if status == "PAID" else AMBER)
    c.drawRightString(W - 46, y, status)
    y -= 24
    c.setFont("Helvetica", 10); c.setFillColor(SLATE)
    c.drawString(46, y, f"Bill to: {inv.get('company', '')}   ·   {inv.get('email') or ''}")
    c.drawRightString(W - 46, y, f"Issued: {inv.get('created_at', '')[:10]}   ·   Due: {inv.get('due_date', '')[:10]}")
    y -= 30
    c.setFillColor(INK); c.rect(46, y - 6, W - 92, 22, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 9); c.setFillColor(colors.white)
    c.drawString(54, y, "DESCRIPTION"); c.drawRightString(W - 54, y, "AMOUNT")
    y -= 24
    for it in inv.get("line_items", []):
        c.setFont("Helvetica", 9.5); c.setFillColor(SLATE)
        c.drawString(54, y, str(it.get("desc", ""))[:95])
        c.drawRightString(W - 54, y, f"${float(it.get('amount', 0)):,.2f}")
        c.setStrokeColor(colors.HexColor("#E2E8F0")); c.line(46, y - 6, W - 46, y - 6)
        y -= 20
    y -= 8
    c.setFont("Helvetica-Bold", 14); c.setFillColor(INK)
    c.drawRightString(W - 54, y, f"TOTAL DUE:  ${float(inv.get('total', 0)):,.2f}")
    y -= 34
    if inv.get("notes"):
        c.setFont("Helvetica", 9); c.setFillColor(SLATE)
        c.drawString(46, y, f"Notes: {inv['notes'][:120]}"); y -= 18
    if pay_url and status != "PAID":
        c.setFillColor(AMBER); c.roundRect(46, y - 14, 220, 26, 6, fill=1, stroke=0)
        c.setFont("Helvetica-Bold", 10); c.setFillColor(INK)
        c.drawString(58, y - 5, "PAY ONLINE — card or ACH")
        c.setFont("Helvetica", 8); c.setFillColor(SLATE)
        c.drawString(46, y - 28, pay_url[:110])
        y -= 44
    c.setFont("Helvetica", 8.5); c.setFillColor(SLATE)
    c.drawString(46, y, "Net 15 · Card, ACH, or check accepted · Questions: oliver@oriseifreightsolutions.com")
    c.save()
    return buf.getvalue()


def build_truck_cleaning_biz_router(*, db, require_role: Callable) -> APIRouter:
    router = APIRouter(prefix="/truck-cleaning", tags=["truck-cleaning-biz"])
    guard = require_role("admin", "owner", "dispatcher")
    bucket = AsyncIOMotorGridFSBucket(db, bucket_name="tc_vault")
    stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")

    # ================= DOCUMENT VAULT =================
    @router.get("/vault/categories")
    async def vault_categories(_=Depends(guard)) -> Dict[str, Any]:
        return {"categories": VAULT_CATEGORIES}

    @router.post("/vault/upload")
    async def vault_upload(file: UploadFile = File(...), category: str = Form("Other"),
                           client_id: str = Form(""), notes: str = Form(""), user=Depends(guard)) -> Dict[str, Any]:
        data = await file.read()
        if len(data) > 25 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="File too large (25MB max)")
        company = ""
        if client_id:
            cl = await db.tc_clients.find_one({"client_id": client_id}, {"_id": 0, "company": 1})
            company = (cl or {}).get("company", "")
        fid = await bucket.upload_from_stream(file.filename or "untitled", data, metadata={
            "content_type": file.content_type or "application/octet-stream",
            "category": category if category in VAULT_CATEGORIES else "Other",
            "client_id": client_id, "company": company, "notes": notes,
            "size_bytes": len(data), "uploaded_at": _now(),
        })
        return {"ok": True, "file_id": str(fid), "filename": file.filename}

    @router.get("/vault/files")
    async def vault_files(category: Optional[str] = None, client_id: Optional[str] = None,
                          _=Depends(guard)) -> Dict[str, Any]:
        q: Dict[str, Any] = {}
        if category:
            q["metadata.category"] = category
        if client_id:
            q["metadata.client_id"] = client_id
        rows = await db["tc_vault.files"].find(q).sort("uploadDate", -1).limit(500).to_list(500)
        out = []
        for f in rows:
            md = f.get("metadata") or {}
            out.append({"file_id": str(f["_id"]), "filename": f.get("filename"), "length": f.get("length"),
                        "category": md.get("category"), "client_id": md.get("client_id"),
                        "company": md.get("company"), "notes": md.get("notes"),
                        "content_type": md.get("content_type"), "uploaded_at": md.get("uploaded_at")})
        return {"files": out}

    @router.get("/vault/files/{file_id}/download")
    async def vault_download(file_id: str, _=Depends(guard)) -> Response:
        try:
            oid = ObjectId(file_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid file_id")
        try:
            grid_out = await bucket.open_download_stream(oid)
        except Exception:
            raise HTTPException(status_code=404, detail="File not found")
        data = await grid_out.read()
        md = grid_out.metadata or {}
        return Response(content=data, media_type=md.get("content_type", "application/octet-stream"),
                        headers={"Content-Disposition": f'attachment; filename="{grid_out.filename}"'})

    @router.delete("/vault/files/{file_id}")
    async def vault_delete(file_id: str, _=Depends(guard)) -> Dict[str, Any]:
        try:
            await bucket.delete(ObjectId(file_id))
        except Exception:
            raise HTTPException(status_code=404, detail="File not found")
        return {"ok": True}

    # ================= CLIENT ONBOARDING =================
    @router.post("/onboarding")
    async def create_onboarding(payload: OnboardInviteIn, _=Depends(guard)) -> Dict[str, Any]:
        row = {"onboard_id": f"OB-TC-{uuid.uuid4().hex[:6].upper()}", "token": uuid.uuid4().hex,
               "company": payload.company, "contact": payload.contact, "email": payload.email,
               "phone": "", "cabs": 1, "plan": "one_time", "fleet_notes": "", "yard_address": "",
               "agreement_accepted": False, "status": "invited", "client_id": None,
               "created_at": _now(), "submitted_at": None}
        await db.tc_onboarding.insert_one(dict(row))
        return {"ok": True, "onboarding": row, "link_path": f"/tc/onboard/{row['token']}"}

    @router.get("/onboarding")
    async def list_onboarding(_=Depends(guard)) -> Dict[str, Any]:
        rows = await db.tc_onboarding.find({}, {"_id": 0}).sort("created_at", -1).to_list(300)
        return {"onboardings": rows}

    @router.post("/onboarding/{onboard_id}/approve")
    async def approve_onboarding(onboard_id: str, _=Depends(guard)) -> Dict[str, Any]:
        ob = await db.tc_onboarding.find_one({"onboard_id": onboard_id}, {"_id": 0})
        if not ob:
            raise HTTPException(status_code=404, detail="Onboarding not found")
        if ob["status"] != "submitted":
            raise HTTPException(status_code=400, detail=f"Cannot approve from status '{ob['status']}'")
        rate = PLAN_RATES.get(ob.get("plan", "one_time"), 150.0)
        client = {"client_id": f"TC-{uuid.uuid4().hex[:6].upper()}", "company": ob["company"],
                  "contact": ob["contact"], "phone": ob.get("phone", ""), "email": ob.get("email", ""),
                  "cabs": ob.get("cabs", 1), "plan": ob.get("plan", "one_time"), "rate": rate,
                  "source": "Onboarding portal", "notes": ob.get("fleet_notes", ""),
                  "is_sample": False, "created_at": _now()}
        await db.tc_clients.insert_one(dict(client))
        await db.tc_onboarding.update_one({"onboard_id": onboard_id},
                                          {"$set": {"status": "approved", "client_id": client["client_id"],
                                                    "rate": rate, "approved_at": _now()}})
        return {"ok": True, "client": client}

    @router.post("/onboarding/{onboard_id}/reject")
    async def reject_onboarding(onboard_id: str, _=Depends(guard)) -> Dict[str, Any]:
        r = await db.tc_onboarding.update_one({"onboard_id": onboard_id, "status": "submitted"},
                                              {"$set": {"status": "rejected"}})
        if r.matched_count == 0:
            raise HTTPException(status_code=404, detail="Submitted onboarding not found")
        return {"ok": True}

    @router.get("/onboarding/{onboard_id}/welcome-packet.pdf")
    async def welcome_packet(onboard_id: str, _=Depends(guard)) -> Response:
        ob = await db.tc_onboarding.find_one({"onboard_id": onboard_id}, {"_id": 0})
        if not ob:
            raise HTTPException(status_code=404, detail="Onboarding not found")
        ob["rate"] = ob.get("rate") or PLAN_RATES.get(ob.get("plan", "one_time"), 150.0)
        pdf = _welcome_packet_pdf(ob)
        return Response(content=pdf, media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="Orisei_Welcome_Packet_{onboard_id}.pdf"'})

    # -------- public onboarding (no auth) --------
    @router.get("/onboard/{token}")
    async def public_onboard_info(token: str) -> Dict[str, Any]:
        ob = await db.tc_onboarding.find_one({"token": token}, {"_id": 0})
        if not ob:
            raise HTTPException(status_code=404, detail="Onboarding link not found")
        return {"onboard_id": ob["onboard_id"], "status": ob["status"],
                "prefill": {"company": ob.get("company", ""), "contact": ob.get("contact", ""),
                            "email": ob.get("email", "")}}

    @router.post("/onboard/{token}/submit")
    async def public_onboard_submit(token: str, payload: OnboardSubmitIn) -> Dict[str, Any]:
        ob = await db.tc_onboarding.find_one({"token": token}, {"_id": 0})
        if not ob:
            raise HTTPException(status_code=404, detail="Onboarding link not found")
        if ob["status"] not in ("invited", "submitted"):
            raise HTTPException(status_code=400, detail="This onboarding is already finalized")
        if payload.plan not in PLAN_RATES:
            raise HTTPException(status_code=400, detail="Invalid plan")
        if not payload.agreement_accepted:
            raise HTTPException(status_code=400, detail="You must accept the service agreement")
        await db.tc_onboarding.update_one({"token": token}, {"$set": {
            **payload.model_dump(), "status": "submitted", "submitted_at": _now(),
            "rate": PLAN_RATES[payload.plan]}})
        return {"ok": True, "message": "Application received — our crew lead will call within 1 business day."}

    # ================= INVOICING & PAYMENTS =================
    @router.post("/invoices")
    async def create_invoice(payload: InvoiceCreateIn, _=Depends(guard)) -> Dict[str, Any]:
        client = await db.tc_clients.find_one({"client_id": payload.client_id}, {"_id": 0})
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        items: List[Dict[str, Any]] = []
        job_ids: List[str] = []
        if payload.job_ids:
            jobs = await db.tc_jobs.find({"job_id": {"$in": payload.job_ids}}, {"_id": 0}).to_list(200)
            for j in jobs:
                ups = f" + {', '.join(u.replace('_', ' ') for u in j.get('upsells', []))}" if j.get("upsells") else ""
                items.append({"desc": f"{j['date']} — Cab cleaning × {j['cabs']}{ups} ({j['job_id']})",
                              "amount": j["price"]})
                job_ids.append(j["job_id"])
        for ci in payload.custom_items:
            desc, amount = str(ci.get("desc", "")).strip(), float(ci.get("amount", 0) or 0)
            if desc and amount > 0:
                items.append({"desc": desc, "amount": round(amount, 2)})
        if not items:
            raise HTTPException(status_code=400, detail="Invoice needs at least one job or line item")
        total = round(sum(i["amount"] for i in items), 2)
        inv = {"invoice_id": f"INV-TC-{uuid.uuid4().hex[:6].upper()}", "client_id": client["client_id"],
               "company": client["company"], "email": client.get("email", ""), "line_items": items,
               "total": total, "status": "draft", "job_ids": job_ids, "notes": payload.notes,
               "due_date": (datetime.now(timezone.utc) + timedelta(days=payload.due_days)).isoformat(),
               "created_at": _now(), "paid_at": None, "stripe_session_id": None}
        await db.tc_invoices.insert_one(dict(inv))
        return {"ok": True, "invoice": inv, "pay_path": f"/tc/invoice/{inv['invoice_id']}"}

    @router.get("/invoices")
    async def list_invoices(_=Depends(guard)) -> Dict[str, Any]:
        rows = await db.tc_invoices.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
        now = _now()
        for r in rows:
            if r["status"] in ("draft", "sent") and (r.get("due_date") or "9999") < now:
                r["status"] = "overdue"
        return {"invoices": rows}

    @router.put("/invoices/{invoice_id}")
    async def edit_invoice(invoice_id: str, payload: InvoiceEditIn, _=Depends(guard)) -> Dict[str, Any]:
        inv = await db.tc_invoices.find_one({"invoice_id": invoice_id}, {"_id": 0})
        if not inv:
            raise HTTPException(status_code=404, detail="Invoice not found")
        if inv["status"] == "paid":
            raise HTTPException(status_code=400, detail="Paid invoices can't be edited")
        items = []
        for ci in payload.line_items:
            desc, amount = str(ci.get("desc", "")).strip(), float(ci.get("amount", 0) or 0)
            if desc and amount > 0:
                items.append({"desc": desc[:200], "amount": round(amount, 2)})
        if not items:
            raise HTTPException(status_code=400, detail="Invoice needs at least one line item")
        upd = {"line_items": items, "total": round(sum(i["amount"] for i in items), 2),
               "notes": payload.notes, "updated_at": _now()}
        if payload.due_date:
            upd["due_date"] = payload.due_date
        await db.tc_invoices.update_one({"invoice_id": invoice_id}, {"$set": upd})
        fresh = await db.tc_invoices.find_one({"invoice_id": invoice_id}, {"_id": 0})
        return {"ok": True, "invoice": fresh}

    @router.post("/invoices/{invoice_id}/mark-paid")
    async def mark_paid(invoice_id: str, _=Depends(guard)) -> Dict[str, Any]:
        inv = await db.tc_invoices.find_one({"invoice_id": invoice_id}, {"_id": 0})
        if not inv:
            raise HTTPException(status_code=404, detail="Invoice not found")
        await _settle_invoice(invoice_id, inv, method="manual")
        return {"ok": True}

    @router.get("/invoices/{invoice_id}/pdf")
    async def invoice_pdf(invoice_id: str, _=Depends(guard)) -> Response:
        inv = await db.tc_invoices.find_one({"invoice_id": invoice_id}, {"_id": 0})
        if not inv:
            raise HTTPException(status_code=404, detail="Invoice not found")
        pdf = _invoice_pdf(inv, pay_url=f"{_public_base()}/tc/invoice/{invoice_id}")
        return Response(content=pdf, media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="Orisei_{invoice_id}.pdf"'})

    @router.post("/invoices/{invoice_id}/email")
    async def email_invoice(invoice_id: str, payload: InvoiceEmailIn, _=Depends(guard)) -> Dict[str, Any]:
        inv = await db.tc_invoices.find_one({"invoice_id": invoice_id}, {"_id": 0})
        if not inv:
            raise HTTPException(status_code=404, detail="Invoice not found")
        creds = await get_connection_credentials(db, "resend") or {}
        api_key = creds.get("api_key")
        if not api_key:
            raise HTTPException(status_code=400,
                                detail="Resend is not configured — add your Resend API key in Connections · Keys, then retry.")
        pay_url = f"{_public_base()}/tc/invoice/{invoice_id}"
        pdf = _invoice_pdf(inv, pay_url=pay_url)
        msg = f'<p style="background:#FFF8EB;border-left:3px solid #F59E0B;padding:10px 14px;">{payload.message}</p>' if payload.message else ""
        html = f"""<!doctype html><html><body style="font-family:-apple-system,'Segoe UI',Helvetica,Arial,sans-serif;background:#F8FAFC;padding:24px;color:#0D1117;">
<div style="max-width:620px;margin:0 auto;background:#fff;border:1px solid #E2E8F0;border-radius:10px;overflow:hidden;">
  <div style="background:#0D1117;color:#fff;padding:22px 26px;border-bottom:4px solid #F59E0B;">
    <div style="font-size:11px;letter-spacing:.3em;color:#F59E0B;text-transform:uppercase;font-family:Courier,monospace;">Orisei Truck Cleaning</div>
    <div style="font-size:22px;font-weight:800;margin-top:6px;">Invoice {invoice_id}</div>
  </div>
  <div style="padding:24px 26px;font-size:14px;line-height:1.6;">
    <p>Hi {inv.get('company', 'Team')},</p>
    <p>Your invoice for <b>${inv['total']:,.2f}</b> is attached. You can pay securely online by card or ACH:</p>
    {msg}
    <p style="text-align:center;margin:26px 0;">
      <a href="{pay_url}" style="background:#F59E0B;color:#0D1117;font-weight:800;padding:12px 28px;border-radius:999px;text-decoration:none;">PAY ${inv['total']:,.2f} NOW</a>
    </p>
    <p style="font-size:12px;color:#64748B;">Due {inv.get('due_date', '')[:10]} · Net 15 · Card, ACH, or check accepted.</p>
    <p style="margin-top:20px;">— Oliver Cummins<br><b>Orisei Truck Cleaning Solutions</b><br>oliver@oriseifreightsolutions.com · (763) 443-4459</p>
  </div></div></body></html>"""
        try:
            resend.api_key = api_key
            resp = resend.Emails.send({
                "from": creds.get("from_email") or "Orisei Truck Cleaning <oliver@oriseifreightsolutions.com>",
                "to": [payload.to_email], "subject": f"Invoice {invoice_id} · ${inv['total']:,.2f} · Orisei Truck Cleaning",
                "html": html, "attachments": [{"filename": f"Orisei_{invoice_id}.pdf", "content": list(pdf)}],
            })
        except Exception as exc:  # noqa: BLE001
            logger.exception("TC invoice email failed")
            raise HTTPException(status_code=502, detail=f"Resend send failed: {str(exc)[:180]}")
        await db.tc_invoices.update_one({"invoice_id": invoice_id},
                                        {"$set": {"status": "sent", "sent_at": _now(), "sent_to": payload.to_email}})
        return {"ok": True, "message_id": (resp or {}).get("id") if isinstance(resp, dict) else None}

    # -------- public pay page (no auth) --------
    @router.get("/pay/{invoice_id}")
    async def public_invoice(invoice_id: str) -> Dict[str, Any]:
        inv = await db.tc_invoices.find_one({"invoice_id": invoice_id}, {"_id": 0})
        if not inv:
            raise HTTPException(status_code=404, detail="Invoice not found")
        return {k: inv.get(k) for k in ("invoice_id", "company", "line_items", "total", "status",
                                        "due_date", "created_at", "paid_at", "notes")}

    @router.get("/pay/{invoice_id}/pdf")
    async def public_invoice_pdf(invoice_id: str) -> Response:
        inv = await db.tc_invoices.find_one({"invoice_id": invoice_id}, {"_id": 0})
        if not inv:
            raise HTTPException(status_code=404, detail="Invoice not found")
        pdf = _invoice_pdf(inv, pay_url=f"{_public_base()}/tc/invoice/{invoice_id}")
        return Response(content=pdf, media_type="application/pdf",
                        headers={"Content-Disposition": f'inline; filename="Orisei_{invoice_id}.pdf"'})

    @router.post("/pay/{invoice_id}/checkout")
    async def public_checkout(invoice_id: str, payload: CheckoutIn) -> Dict[str, Any]:
        inv = await db.tc_invoices.find_one({"invoice_id": invoice_id}, {"_id": 0})
        if not inv:
            raise HTTPException(status_code=404, detail="Invoice not found")
        if inv["status"] == "paid":
            raise HTTPException(status_code=400, detail="Invoice already paid")
        origin = payload.origin_url.rstrip("/")
        kwargs = dict(
            mode="payment",
            line_items=[{"price_data": {"currency": "usd",
                                        "product_data": {"name": f"Orisei Truck Cleaning · Invoice {invoice_id}",
                                                         "description": f"Fleet cab cleaning services for {inv.get('company', '')}"},
                                        "unit_amount": int(round(inv["total"] * 100))}, "quantity": 1}],
            success_url=f"{origin}/tc/invoice/{invoice_id}?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{origin}/tc/invoice/{invoice_id}?cancelled=1",
            metadata={"invoice_id": invoice_id, "module": "truck_cleaning"},
        )
        try:
            session = stripe.checkout.Session.create(**kwargs, managed_payments={"enabled": True})
        except stripe.error.InvalidRequestError:
            session = stripe.checkout.Session.create(**kwargs)
        await db.tc_invoices.update_one({"invoice_id": invoice_id},
                                        {"$set": {"stripe_session_id": session.id}})
        return {"checkout_url": session.url, "session_id": session.id}

    @router.get("/pay/{invoice_id}/status")
    async def public_pay_status(invoice_id: str, session_id: str = "") -> Dict[str, Any]:
        inv = await db.tc_invoices.find_one({"invoice_id": invoice_id}, {"_id": 0})
        if not inv:
            raise HTTPException(status_code=404, detail="Invoice not found")
        if inv["status"] == "paid":
            return {"status": "paid", "paid_at": inv.get("paid_at")}
        sid = session_id or inv.get("stripe_session_id")
        if sid:
            try:
                s = stripe.checkout.Session.retrieve(sid)
                if s.payment_status == "paid":
                    await _settle_invoice(invoice_id, inv, method="stripe")
                    return {"status": "paid", "paid_at": _now()}
            except stripe.error.StripeError:
                pass
        return {"status": inv["status"]}

    async def _settle_invoice(invoice_id: str, inv: Dict[str, Any], *, method: str):
        await db.tc_invoices.update_one({"invoice_id": invoice_id},
                                        {"$set": {"status": "paid", "paid_at": _now(), "paid_method": method}})
        if inv.get("job_ids"):
            await db.tc_jobs.update_many({"job_id": {"$in": inv["job_ids"]}}, {"$set": {"status": "paid"}})
        import asyncio as _aio
        _aio.create_task(_request_review(invoice_id, inv))

    async def _request_review(invoice_id: str, inv: Dict[str, Any]):
        try:
            if await db.tc_review_requests.find_one({"invoice_id": invoice_id}):
                return
            client = await db.tc_clients.find_one({"client_id": inv.get("client_id")}, {"_id": 0}) or {}
            phone = (client.get("phone") or "").strip()
            settings = await db.tc_settings.find_one({"_id": "settings"}) or {}
            url = settings.get("google_review_url") or \
                "https://www.google.com/search?q=Orisei+Truck+Cleaning+Minneapolis+reviews"
            status = "no_phone"
            if phone:
                from routes.truck_cleaning_field import _send_sms
                await _send_sms(db, phone,
                                f"Thanks for your payment, {client.get('company', '')}! If your drivers loved "
                                f"their clean cabs, a quick Google review means the world to our crews: {url} "
                                f"— Orisei Truck Cleaning", job_id=invoice_id, kind="review_request")
                status = "sms_queued"
            await db.tc_review_requests.insert_one({
                "invoice_id": invoice_id, "client_id": inv.get("client_id"),
                "company": client.get("company", inv.get("company", "")), "to": phone,
                "url": url, "status": status, "at": _now()})
        except Exception:
            logger.exception("review request failed for %s", invoice_id)

    @router.get("/settings")
    async def get_settings(_=Depends(guard)) -> Dict[str, Any]:
        s = await db.tc_settings.find_one({"_id": "settings"}) or {}
        s.pop("_id", None)
        return {"settings": s}

    @router.put("/settings")
    async def put_settings(payload: Dict[str, Any], _=Depends(guard)) -> Dict[str, Any]:
        allowed = {k: str(v)[:400] for k, v in payload.items() if k in ("google_review_url",)}
        await db.tc_settings.update_one({"_id": "settings"}, {"$set": allowed}, upsert=True)
        return {"ok": True, "settings": allowed}

    @router.get("/review-requests")
    async def review_requests(_=Depends(guard)) -> Dict[str, Any]:
        rows = await db.tc_review_requests.find({}, {"_id": 0}).sort("at", -1).to_list(100)
        return {"requests": rows}

    return router
