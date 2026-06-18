"""routes.orisei_workflow — Orisei "Run-the-Load" Workflow Engine.

Adds 6 capabilities the broker UI was missing:

  1. AI Workflow Checklist  — per-shipment 8-step journey with AI prompted
     "next step" coaching that auto-completes when the underlying data hits.
  2. Quick Margin Calculator — manual carrier cost entry on a booking, returns
     live $/% margin without waiting for settlement.
  3. Editable Invite Templates — DB-backed carrier/shipper invite templates
     (subject + HTML body) with token substitution.
  4. Editable Document Field Overrides — any BOL/RateCon/Invoice field can be
     overridden, the PDF re-renders with the override values.
  5. Branded Invoice Generation — Orisei-themed customer invoice PDF + email.
  6. Domain Config — single admin setting that controls every public URL in
     the app (emails, generated marketing pages, embedded brand mark links).
"""
from __future__ import annotations

import base64
import io
import logging
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr, Field

from .orisei_docs import build_branded_markdown_pdf

logger = logging.getLogger("tennant_tms.orisei_workflow")


# ============================================================
# Constants
# ============================================================
WORKFLOW_STAGES = [
    {"id": "booked",          "label": "Load Booked",          "icon": "ClipboardCheck",
     "description": "Customer signed quote · brokerage commits to move freight"},
    {"id": "carrier_assigned", "label": "Carrier Assigned",     "icon": "Truck",
     "description": "MC verified · insurance valid · rate confirmation signed"},
    {"id": "bol_generated",    "label": "BOL Generated",        "icon": "FileText",
     "description": "Bill of Lading issued and shared with shipper + carrier"},
    {"id": "dispatched",       "label": "Dispatched",           "icon": "Send",
     "description": "Driver dispatched · ETA confirmed · departure scheduled"},
    {"id": "in_transit",       "label": "In Transit",           "icon": "Navigation",
     "description": "Pickup completed · load moving · GPS check-ins active"},
    {"id": "delivered",        "label": "Delivered",            "icon": "PackageCheck",
     "description": "Delivery confirmed · receiver signature captured"},
    {"id": "pod_uploaded",     "label": "POD Uploaded",         "icon": "CheckSquare",
     "description": "Proof of Delivery scanned · OS&D notes closed"},
    {"id": "invoiced",         "label": "Invoiced",             "icon": "Receipt",
     "description": "Customer invoiced · margin recognized · file closed"},
]

DEFAULT_CARRIER_INVITE = {
    "template_id": "carrier-invite-default",
    "kind": "carrier",
    "name": "Orisei Carrier Invite — Default",
    "subject": "Run with Orisei — premium freight, quick pay, zero claims",
    "from_name": "Oliver Cummins — Orisei Freight",
    "body_html": """<p>Hi {{carrier_name}},</p>
<p>Orisei is dispatching premium loads in {{lane_focus}} this week and your MC <b>{{carrier_mc}}</b> matched our shortlist.</p>
<ul>
  <li><b>QuickPay</b> in 24 hours at 3%</li>
  <li><b>$0</b> factoring lockout</li>
  <li><b>Pre-approved fuel advances</b></li>
</ul>
<p>Tap below to onboard in under 90 seconds (W-9, COI, MC verification — all in one).</p>
<p><a href="{{onboard_url}}" style="background:linear-gradient(135deg,#E0B85C,#B08A36);color:#0A2D55;padding:14px 28px;border-radius:8px;text-decoration:none;font-weight:700;">Onboard with Orisei →</a></p>
<p style="font-size:13px;color:#64748b;">This invite expires in {{expires_days}} days · No password required.</p>
<p>— Oliver Cummins<br>Orisei Freight Solutions<br>{{site_url}}</p>""",
    "tokens": ["carrier_name", "carrier_mc", "lane_focus", "onboard_url", "expires_days", "site_url"],
    "is_default": True,
}

DEFAULT_SHIPPER_INVITE = {
    "template_id": "shipper-invite-default",
    "kind": "shipper",
    "name": "Orisei Shipper Invite — Default",
    "subject": "Stop overpaying for freight — Orisei runs your lanes 14–22% smarter",
    "from_name": "Oliver Cummins — Orisei Freight",
    "body_html": """<p>Hi {{shipper_name}},</p>
<p>Brokerages mark up your freight 20–35% and never show you the lane data. Orisei does the opposite:</p>
<ul>
  <li><b>14–22% lower</b> all-in cost than your incumbent — guaranteed</li>
  <li><b>Real-time GPS</b> on every load · zero hidden accessorials</li>
  <li><b>Customer Portal</b> with margin, lane, and on-time analytics</li>
</ul>
<p>Spin up a free read-only Customer Portal in 30 seconds:</p>
<p><a href="{{portal_url}}" style="background:linear-gradient(135deg,#E0B85C,#B08A36);color:#0A2D55;padding:14px 28px;border-radius:8px;text-decoration:none;font-weight:700;">View Your Lane Analysis →</a></p>
<p style="font-size:13px;color:#64748b;">Link active for {{expires_days}} days · No commitment.</p>
<p>— Oliver Cummins<br>Orisei Freight Solutions<br>{{site_url}}</p>""",
    "tokens": ["shipper_name", "portal_url", "expires_days", "site_url"],
    "is_default": True,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _substitute_tokens(text: str, mapping: Dict[str, Any]) -> str:
    """Replace `{{token}}` patterns with values from the mapping."""
    def repl(m: re.Match) -> str:
        key = m.group(1).strip()
        return str(mapping.get(key, m.group(0)))
    return re.sub(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}", repl, text)


# ============================================================
# Pydantic
# ============================================================
class WorkflowMarkIn(BaseModel):
    stage_id: str
    notes: Optional[str] = Field(None, max_length=2000)


class WorkflowChecklistOut(BaseModel):
    booked_id: str
    stages: List[Dict[str, Any]]
    current_stage_id: str
    next_action: Optional[Dict[str, Any]] = None
    pct_complete: float
    completed_count: int
    total_count: int


class MarginCalcIn(BaseModel):
    booked_id: str
    carrier_cost_usd: float = Field(..., ge=0)
    extra_costs_usd: Optional[float] = Field(0.0, ge=0)
    notes: Optional[str] = None


class InviteTemplateIn(BaseModel):
    kind: str = Field(..., pattern="^(carrier|shipper)$")
    name: str = Field(..., min_length=1, max_length=200)
    subject: str = Field(..., min_length=1, max_length=500)
    from_name: Optional[str] = "Orisei Freight"
    body_html: str = Field(..., min_length=10)


class InvitePreviewIn(BaseModel):
    template_id: str
    sample_tokens: Optional[Dict[str, Any]] = None


class DomainConfigIn(BaseModel):
    primary_domain: str = Field(..., min_length=3, max_length=255)
    site_url: Optional[str] = None
    apex_url: Optional[str] = None
    support_email: Optional[EmailStr] = None
    legal_name: Optional[str] = None
    propagate_to_static_site: bool = True


class DocOverrideIn(BaseModel):
    """Override one or many fields on a generated doc (BOL, RC, Invoice)."""
    doc_kind: str = Field(..., pattern="^(bol|rate_con|invoice|quote)$")
    doc_id: str
    overrides: Dict[str, Any]


class InvoiceCreateIn(BaseModel):
    customer_id: str
    booking_ids: List[str] = Field(default_factory=list)
    line_items: Optional[List[Dict[str, Any]]] = None
    notes: Optional[str] = None
    due_in_days: int = 30
    invoice_date: Optional[str] = None


# ============================================================
# Router builder
# ============================================================
def build_orisei_workflow_router(
    api_router: APIRouter, *, db,
    get_current_user: Callable, require_role: Callable,
) -> None:
    router = APIRouter(prefix="/orisei/workflow", tags=["orisei-workflow"])
    admin_dep = Depends(require_role("admin", "dispatcher"))

    # ============================================================
    # WORKFLOW CHECKLIST
    # ============================================================
    @router.get("/stages")
    async def workflow_stages(_=Depends(get_current_user)):
        """Return the static 8-stage workflow definition."""
        return {"stages": WORKFLOW_STAGES, "total": len(WORKFLOW_STAGES)}

    async def _booking(booked_id: str) -> Dict[str, Any]:
        b = await db.brokerage_bookings.find_one({"booked_id": booked_id}, {"_id": 0})
        if not b:
            raise HTTPException(404, "Booking not found")
        return b

    async def _auto_complete_from_booking(booking: Dict[str, Any]) -> Dict[str, str]:
        """Inspect booking + related collections, return {stage_id: iso_at} for
        every stage we can verify objectively."""
        booked_id = booking["booked_id"]
        completed: Dict[str, str] = {}
        if booking.get("booked_at"):
            completed["booked"] = booking["booked_at"]
        if booking.get("carrier_mc") or booking.get("rate_con_id"):
            completed["carrier_assigned"] = (booking.get("rate_con_signed_at")
                                              or booking.get("booked_at"))
        # BOL?
        if booking.get("bol_doc_id") or booking.get("bol_generated_at"):
            completed["bol_generated"] = (booking.get("bol_generated_at")
                                           or booking.get("booked_at"))
        if booking.get("tendered_at") or booking.get("dispatched_at"):
            completed["dispatched"] = (booking.get("dispatched_at")
                                        or booking.get("tendered_at"))
        if booking.get("pickup_actual_at") or booking.get("in_transit_at"):
            completed["in_transit"] = (booking.get("in_transit_at")
                                        or booking.get("pickup_actual_at"))
        if booking.get("delivered_at"):
            completed["delivered"] = booking["delivered_at"]
        # POD photos?
        pod_count = await db.brokerage_pod_photos.count_documents({"booked_id": booked_id})
        if pod_count > 0 or booking.get("pod_uploaded_at"):
            completed["pod_uploaded"] = (booking.get("pod_uploaded_at")
                                          or booking.get("delivered_at")
                                          or _now())
        # Invoiced?
        inv = await db.brokerage_invoices.find_one(
            {"booking_ids": {"$in": [booked_id]}}, {"_id": 0, "issued_at": 1})
        if inv or booking.get("settled_at"):
            completed["invoiced"] = (inv or {}).get("issued_at") or booking.get("settled_at")
        return completed

    async def _ai_next_action(booking: Dict[str, Any], next_stage_id: Optional[str]) -> Optional[Dict[str, Any]]:
        """Return a deterministic next-action coaching prompt for the broker."""
        if not next_stage_id:
            return None
        stage_def = next((s for s in WORKFLOW_STAGES if s["id"] == next_stage_id), None)
        if not stage_def:
            return None
        booked_id = booking["booked_id"]  # noqa: F841 — surfaced for future use
        origin = booking.get("origin", "origin")
        dest = booking.get("destination", "destination")
        prompts: Dict[str, Dict[str, str]] = {
            "carrier_assigned": {
                "title": "Tender to a vetted carrier",
                "advice": f"Pull top 3 MC matches for {origin} → {dest}. Verify FMCSA Safety Rating ≥ Satisfactory, insurance current, and email a signed Rate Confirmation before sharing pickup numbers.",
                "cta_label": "Issue Rate Confirmation",
                "cta_action": "open-rate-con",
            },
            "bol_generated": {
                "title": "Generate the Bill of Lading",
                "advice": "Confirm piece count, NMFC class, weight & hazmat status with the shipper. Issue BOL with both shipper and consignee signatures. Email PDF to shipper, carrier dispatch, and driver in one motion.",
                "cta_label": "Generate BOL",
                "cta_action": "open-bol",
            },
            "dispatched": {
                "title": "Confirm dispatch + pickup window",
                "advice": "Call the carrier dispatcher (NOT the driver) to confirm driver assigned, asset attached, and pickup window honored. Lock pickup number with shipper. If late by >30 min, escalate.",
                "cta_label": "Mark Dispatched",
                "cta_action": "mark-dispatched",
            },
            "in_transit": {
                "title": "Confirm pickup + activate tracking",
                "advice": "Capture pickup time + odometer. Activate macropoint / project44 tracking, or schedule a check-call every 4 hours. Send shipper an in-transit notification with ETA.",
                "cta_label": "Mark In Transit",
                "cta_action": "mark-in-transit",
            },
            "delivered": {
                "title": "Verify clean delivery",
                "advice": f"Confirm delivery time at {dest}, receiver name + signature, and OS&D (Over/Short/Damaged) status. If any claim, capture photos + open a claim before driver leaves the dock.",
                "cta_label": "Mark Delivered",
                "cta_action": "mark-delivered",
            },
            "pod_uploaded": {
                "title": "Upload Proof of Delivery",
                "advice": "Get a clear scan/photo of the signed POD from the driver. Upload to the load record — required for invoicing and any claim resolution.",
                "cta_label": "Upload POD",
                "cta_action": "upload-pod",
            },
            "invoiced": {
                "title": "Generate customer invoice",
                "advice": f"Bill {booking.get('customer_name') or 'the customer'} for the agreed all-in rate + any approved accessorials. Recognize margin against carrier cost and send invoice with POD + BOL attached.",
                "cta_label": "Generate Invoice",
                "cta_action": "open-invoice",
            },
        }
        prompt = prompts.get(next_stage_id, {
            "title": stage_def["label"],
            "advice": stage_def["description"],
            "cta_label": "Mark Complete",
            "cta_action": f"mark-{next_stage_id}",
        })
        return {**prompt, "stage_id": next_stage_id, "label": stage_def["label"], "icon": stage_def["icon"]}

    @router.get("/checklist/{booked_id}", response_model=None)
    async def get_checklist(booked_id: str, _=Depends(get_current_user)) -> Dict[str, Any]:
        booking = await _booking(booked_id)
        stored = await db.orisei_workflow_state.find_one({"booked_id": booked_id}, {"_id": 0}) or {}
        manual = stored.get("manual_completed") or {}
        auto = await _auto_complete_from_booking(booking)
        merged: Dict[str, str] = {**auto, **manual}
        stages_out = []
        current_id: Optional[str] = None
        for s in WORKFLOW_STAGES:
            sid = s["id"]
            completed_at = merged.get(sid)
            stages_out.append({
                **s,
                "completed": bool(completed_at),
                "completed_at": completed_at,
                "manual": sid in manual,
                "notes": (stored.get("notes") or {}).get(sid),
            })
            if current_id is None and not completed_at:
                current_id = sid
        if current_id is None:
            current_id = WORKFLOW_STAGES[-1]["id"]
        completed_count = sum(1 for s in stages_out if s["completed"])
        pct = round((completed_count / len(WORKFLOW_STAGES)) * 100, 1)
        next_stage_id: Optional[str] = current_id if completed_count < len(WORKFLOW_STAGES) else None
        next_action = await _ai_next_action(booking, next_stage_id)
        return {
            "booked_id": booked_id,
            "load_id": booking.get("load_id"),
            "origin": booking.get("origin"),
            "destination": booking.get("destination"),
            "carrier_name": booking.get("carrier_name"),
            "customer_name": booking.get("customer_name"),
            "stages": stages_out,
            "current_stage_id": current_id,
            "next_action": next_action,
            "pct_complete": pct,
            "completed_count": completed_count,
            "total_count": len(WORKFLOW_STAGES),
        }

    @router.post("/checklist/{booked_id}/mark")
    async def mark_stage(booked_id: str, payload: WorkflowMarkIn, user=admin_dep) -> Dict[str, Any]:
        await _booking(booked_id)  # 404 if not found
        if not any(s["id"] == payload.stage_id for s in WORKFLOW_STAGES):
            raise HTTPException(400, f"Unknown stage: {payload.stage_id}")
        now = _now()
        upd: Dict[str, Any] = {
            f"manual_completed.{payload.stage_id}": now,
            "updated_at": now,
            "updated_by": getattr(user, "name", "system"),
        }
        if payload.notes:
            upd[f"notes.{payload.stage_id}"] = payload.notes
        await db.orisei_workflow_state.update_one(
            {"booked_id": booked_id}, {"$set": upd}, upsert=True)
        # Mirror to booking for downstream collections
        mirror_field = {
            "dispatched": "dispatched_at", "in_transit": "in_transit_at",
            "delivered": "delivered_at",   "pod_uploaded": "pod_uploaded_at",
            "bol_generated": "bol_generated_at",
        }.get(payload.stage_id)
        if mirror_field:
            await db.brokerage_bookings.update_one(
                {"booked_id": booked_id}, {"$set": {mirror_field: now}})
        return await get_checklist(booked_id)  # type: ignore[arg-type]

    @router.post("/checklist/{booked_id}/unmark")
    async def unmark_stage(booked_id: str, payload: WorkflowMarkIn, user=admin_dep) -> Dict[str, Any]:
        await _booking(booked_id)
        await db.orisei_workflow_state.update_one(
            {"booked_id": booked_id},
            {"$unset": {f"manual_completed.{payload.stage_id}": "",
                        f"notes.{payload.stage_id}": ""}})
        return await get_checklist(booked_id)  # type: ignore[arg-type]

    # ============================================================
    # QUICK MARGIN CALCULATOR (manual carrier-cost entry)
    # ============================================================
    @router.post("/margin/quick")
    async def quick_margin(payload: MarginCalcIn, user=admin_dep) -> Dict[str, Any]:
        booking = await _booking(payload.booked_id)
        customer_rate = (booking.get("settled_rate_usd")
                          or booking.get("forecast_rate_usd")
                          or booking.get("customer_rate_usd") or 0)
        total_cost = (payload.carrier_cost_usd or 0) + (payload.extra_costs_usd or 0)
        margin_usd = round(customer_rate - total_cost, 2)
        margin_pct = round((margin_usd / customer_rate) * 100, 2) if customer_rate else 0.0
        update = {
            "carrier_cost_manual_usd": payload.carrier_cost_usd,
            "extra_costs_usd": payload.extra_costs_usd or 0,
            "margin_manual_usd": margin_usd,
            "margin_manual_pct": margin_pct,
            "margin_manual_at": _now(),
            "margin_manual_by": getattr(user, "name", "system"),
        }
        if payload.notes:
            update["margin_manual_notes"] = payload.notes
        await db.brokerage_bookings.update_one(
            {"booked_id": payload.booked_id}, {"$set": update})
        return {
            "booked_id": payload.booked_id,
            "customer_rate_usd": customer_rate,
            "carrier_cost_usd": payload.carrier_cost_usd,
            "extra_costs_usd": payload.extra_costs_usd or 0,
            "total_cost_usd": total_cost,
            "margin_usd": margin_usd,
            "margin_pct": margin_pct,
            "health": ("strong" if margin_pct >= 18 else
                       "healthy" if margin_pct >= 12 else
                       "thin" if margin_pct >= 6 else "loss"),
        }

    @router.get("/margin/{booked_id}")
    async def get_margin(booked_id: str, _=Depends(get_current_user)) -> Dict[str, Any]:
        b = await _booking(booked_id)
        customer_rate = (b.get("settled_rate_usd") or b.get("forecast_rate_usd") or 0)
        cc = b.get("carrier_cost_manual_usd")
        if cc is None:
            return {"booked_id": booked_id, "has_manual_cost": False,
                    "customer_rate_usd": customer_rate}
        extras = b.get("extra_costs_usd", 0)
        total = (cc or 0) + (extras or 0)
        margin_usd = round(customer_rate - total, 2)
        margin_pct = round((margin_usd / customer_rate) * 100, 2) if customer_rate else 0.0
        return {
            "booked_id": booked_id, "has_manual_cost": True,
            "customer_rate_usd": customer_rate, "carrier_cost_usd": cc,
            "extra_costs_usd": extras, "total_cost_usd": total,
            "margin_usd": margin_usd, "margin_pct": margin_pct,
            "health": ("strong" if margin_pct >= 18 else
                       "healthy" if margin_pct >= 12 else
                       "thin" if margin_pct >= 6 else "loss"),
            "notes": b.get("margin_manual_notes"),
            "updated_at": b.get("margin_manual_at"),
        }

    # ============================================================
    # EDITABLE INVITE TEMPLATES
    # ============================================================
    async def _seed_default_templates() -> None:
        for tpl in (DEFAULT_CARRIER_INVITE, DEFAULT_SHIPPER_INVITE):
            existing = await db.orisei_invite_templates.find_one(
                {"template_id": tpl["template_id"]})
            if not existing:
                doc = {**tpl, "created_at": _now(), "updated_at": _now()}
                await db.orisei_invite_templates.insert_one(dict(doc))

    @router.get("/invites/templates")
    async def list_invite_templates(kind: Optional[str] = None,
                                     _=Depends(get_current_user)) -> Dict[str, Any]:
        await _seed_default_templates()
        q: Dict[str, Any] = {}
        if kind:
            q["kind"] = kind
        rows = await db.orisei_invite_templates.find(q, {"_id": 0}).sort(
            [("is_default", -1), ("updated_at", -1)]).to_list(200)
        return {"items": rows, "count": len(rows)}

    @router.post("/invites/templates")
    async def create_invite_template(payload: InviteTemplateIn,
                                      user=admin_dep) -> Dict[str, Any]:
        doc = {
            "template_id": f"INV-{uuid.uuid4().hex[:10].upper()}",
            "created_at": _now(),
            "updated_at": _now(),
            "created_by": getattr(user, "name", "system"),
            "is_default": False,
            **payload.model_dump(),
        }
        # auto-extract tokens
        doc["tokens"] = sorted(set(re.findall(
            r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}",
            doc["subject"] + " " + doc["body_html"])))
        await db.orisei_invite_templates.insert_one(dict(doc))
        doc.pop("_id", None)
        return doc

    @router.put("/invites/templates/{template_id}")
    async def update_invite_template(template_id: str, payload: InviteTemplateIn,
                                      user=admin_dep) -> Dict[str, Any]:
        upd = payload.model_dump()
        upd["updated_at"] = _now()
        upd["updated_by"] = getattr(user, "name", "system")
        upd["tokens"] = sorted(set(re.findall(
            r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}",
            upd["subject"] + " " + upd["body_html"])))
        r = await db.orisei_invite_templates.update_one(
            {"template_id": template_id}, {"$set": upd})
        if r.matched_count == 0:
            raise HTTPException(404, "Template not found")
        return await db.orisei_invite_templates.find_one(
            {"template_id": template_id}, {"_id": 0}) or {}

    @router.delete("/invites/templates/{template_id}")
    async def delete_invite_template(template_id: str, user=admin_dep) -> Dict[str, str]:
        existing = await db.orisei_invite_templates.find_one(
            {"template_id": template_id}, {"_id": 0, "is_default": 1})
        if not existing:
            raise HTTPException(404, "Template not found")
        if existing.get("is_default"):
            raise HTTPException(400, "Cannot delete default template — duplicate and edit instead")
        await db.orisei_invite_templates.delete_one({"template_id": template_id})
        return {"status": "deleted"}

    @router.post("/invites/preview")
    async def preview_invite(payload: InvitePreviewIn,
                              _=Depends(get_current_user)) -> Dict[str, Any]:
        tpl = await db.orisei_invite_templates.find_one(
            {"template_id": payload.template_id}, {"_id": 0})
        if not tpl:
            raise HTTPException(404, "Template not found")
        domain = await _active_domain()
        defaults = {
            "carrier_name": "Acme Trucking", "carrier_mc": "MC-123456",
            "shipper_name": "Acme Manufacturing", "lane_focus": "Memphis → Atlanta",
            "onboard_url": f"{domain['site_url']}/carrier-onboard?token=SAMPLE",
            "portal_url": f"{domain['site_url']}/customer-portal?token=SAMPLE",
            "expires_days": 14, "site_url": domain["site_url"],
        }
        tokens = {**defaults, **(payload.sample_tokens or {})}
        return {
            "subject": _substitute_tokens(tpl["subject"], tokens),
            "body_html": _substitute_tokens(tpl["body_html"], tokens),
            "from_name": tpl.get("from_name", "Orisei Freight"),
            "tokens_used": tpl.get("tokens", []),
        }

    # ============================================================
    # EDITABLE DOC FIELD OVERRIDES
    # ============================================================
    @router.get("/doc-overrides/{doc_kind}/{doc_id}")
    async def get_doc_overrides(doc_kind: str, doc_id: str,
                                  _=Depends(get_current_user)) -> Dict[str, Any]:
        doc = await db.orisei_doc_overrides.find_one(
            {"doc_kind": doc_kind, "doc_id": doc_id}, {"_id": 0}) or {}
        return {"doc_kind": doc_kind, "doc_id": doc_id,
                "overrides": doc.get("overrides", {}),
                "updated_at": doc.get("updated_at")}

    @router.post("/doc-overrides")
    async def save_doc_overrides(payload: DocOverrideIn,
                                  user=admin_dep) -> Dict[str, Any]:
        await db.orisei_doc_overrides.update_one(
            {"doc_kind": payload.doc_kind, "doc_id": payload.doc_id},
            {"$set": {
                "doc_kind": payload.doc_kind, "doc_id": payload.doc_id,
                "overrides": payload.overrides,
                "updated_at": _now(),
                "updated_by": getattr(user, "name", "system"),
            }}, upsert=True)
        return {"status": "saved", "doc_kind": payload.doc_kind, "doc_id": payload.doc_id,
                "overrides": payload.overrides}

    @router.delete("/doc-overrides/{doc_kind}/{doc_id}")
    async def clear_doc_overrides(doc_kind: str, doc_id: str,
                                    user=admin_dep) -> Dict[str, str]:
        await db.orisei_doc_overrides.delete_one(
            {"doc_kind": doc_kind, "doc_id": doc_id})
        return {"status": "cleared"}

    # ============================================================
    # BRANDED INVOICE
    # ============================================================
    @router.get("/invoices")
    async def list_invoices(_=Depends(get_current_user)) -> Dict[str, Any]:
        rows = await db.brokerage_invoices.find(
            {}, {"_id": 0}).sort("issued_at", -1).limit(200).to_list(200)
        return {"items": rows, "count": len(rows)}

    @router.post("/invoices")
    async def create_invoice(payload: InvoiceCreateIn, user=admin_dep) -> Dict[str, Any]:
        customer = await db.orisei_customers.find_one(
            {"customer_id": payload.customer_id}, {"_id": 0})
        if not customer:
            raise HTTPException(404, "Customer not found")
        # Build line items from bookings if not provided
        bookings: List[Dict[str, Any]] = []
        line_items = list(payload.line_items or [])
        if payload.booking_ids:
            bookings = await db.brokerage_bookings.find(
                {"booked_id": {"$in": payload.booking_ids}},
                {"_id": 0}).to_list(100)
            if not line_items:
                for b in bookings:
                    amount = (b.get("settled_rate_usd")
                                or b.get("forecast_rate_usd")
                                or b.get("customer_rate_usd") or 0)
                    line_items.append({
                        "label": f"{b.get('booked_id')} · {b.get('origin','')} → {b.get('destination','')}",
                        "amount_usd": round(float(amount), 2),
                        "miles": b.get("miles"),
                        "equipment": b.get("equipment"),
                    })
        if not line_items:
            raise HTTPException(400, "Provide at least one line item or booking_id")
        subtotal = round(sum(float(li.get("amount_usd", 0)) for li in line_items), 2)
        now = datetime.now(timezone.utc)
        issued = payload.invoice_date or now.isoformat()
        due_at = (now + timedelta(days=payload.due_in_days)).isoformat()
        invoice = {
            "invoice_id": f"INV-{uuid.uuid4().hex[:10].upper()}",
            "customer_id": payload.customer_id,
            "customer_name": customer["name"],
            "customer_billing_address": customer.get("billing_address"),
            "customer_ap_email": customer.get("ap_email"),
            "booking_ids": payload.booking_ids,
            "line_items": line_items,
            "subtotal_usd": subtotal,
            "tax_usd": 0,
            "total_usd": subtotal,
            "issued_at": issued,
            "due_at": due_at,
            "due_in_days": payload.due_in_days,
            "status": "issued",
            "issued_by": getattr(user, "name", "system"),
            "notes": payload.notes,
            "payment_terms": customer.get("payment_terms", f"Net {payload.due_in_days}"),
        }
        await db.brokerage_invoices.insert_one(dict(invoice))
        invoice.pop("_id", None)
        return invoice

    def _invoice_markdown(inv: Dict[str, Any]) -> str:
        rows = "\n".join(
            f"| {li.get('label','')} | ${float(li.get('amount_usd',0)):,.2f} |"
            for li in inv.get("line_items", []))
        bill_to = inv.get("customer_billing_address", "—")
        notes_md = f"\n\n**Notes:** {inv.get('notes')}" if inv.get("notes") else ""
        return f"""# Invoice {inv['invoice_id']}

**Bill To**
{inv['customer_name']}
{bill_to}

**Issued:** {inv['issued_at'][:10]}
**Due:** {inv['due_at'][:10]} ({inv.get('payment_terms','Net 30')})

---

## Charges

| Description | Amount |
|---|---:|
{rows}
| **Total Due** | **${inv['total_usd']:,.2f}** |

## Payment Instructions
- ACH (preferred): routing & account on file or upon request
- Check payable to: **Orisei Freight Solutions**
- QuickPay & card via Stripe link upon request

Reference **{inv['invoice_id']}** on remittance.
{notes_md}
"""

    @router.get("/invoices/{invoice_id}")
    async def get_invoice(invoice_id: str, _=Depends(get_current_user)) -> Dict[str, Any]:
        inv = await db.brokerage_invoices.find_one(
            {"invoice_id": invoice_id}, {"_id": 0})
        if not inv:
            raise HTTPException(404, "Invoice not found")
        # Apply any saved overrides
        ovr = await db.orisei_doc_overrides.find_one(
            {"doc_kind": "invoice", "doc_id": invoice_id}, {"_id": 0})
        if ovr and ovr.get("overrides"):
            inv = {**inv, **ovr["overrides"]}
        return inv

    @router.get("/invoices/{invoice_id}/pdf")
    async def invoice_pdf(invoice_id: str, _=Depends(get_current_user)) -> StreamingResponse:
        inv = await db.brokerage_invoices.find_one(
            {"invoice_id": invoice_id}, {"_id": 0})
        if not inv:
            raise HTTPException(404, "Invoice not found")
        ovr = await db.orisei_doc_overrides.find_one(
            {"doc_kind": "invoice", "doc_id": invoice_id}, {"_id": 0})
        if ovr and ovr.get("overrides"):
            inv = {**inv, **ovr["overrides"]}
        brand = await db.company_brand.find_one(
            {"is_active": True}, {"_id": 0}) or {}
        pdf = build_branded_markdown_pdf(
            _invoice_markdown(inv),
            title=f"Invoice {inv['invoice_id']}",
            subtitle=f"Bill to {inv['customer_name']}",
            brand=brand,
        )
        return StreamingResponse(
            io.BytesIO(pdf), media_type="application/pdf",
            headers={"Content-Disposition":
                f'attachment; filename="Orisei_Invoice_{invoice_id}.pdf"'})

    @router.put("/invoices/{invoice_id}")
    async def edit_invoice(invoice_id: str, body: Dict[str, Any],
                            user=admin_dep) -> Dict[str, Any]:
        """Inline-edit any field on an invoice (e.g. line_items, total, notes)."""
        allowed = {"line_items", "notes", "due_at", "due_in_days", "tax_usd",
                   "payment_terms", "status", "customer_billing_address",
                   "customer_ap_email", "subtotal_usd", "total_usd"}
        upd = {k: v for k, v in (body or {}).items() if k in allowed}
        if "line_items" in upd:
            upd["subtotal_usd"] = round(sum(
                float(li.get("amount_usd", 0)) for li in upd["line_items"]), 2)
            upd["total_usd"] = round(upd["subtotal_usd"]
                                      + float(upd.get("tax_usd", 0) or 0), 2)
        upd["updated_at"] = _now()
        upd["updated_by"] = getattr(user, "name", "system")
        r = await db.brokerage_invoices.update_one(
            {"invoice_id": invoice_id}, {"$set": upd})
        if r.matched_count == 0:
            raise HTTPException(404, "Invoice not found")
        return await db.brokerage_invoices.find_one(
            {"invoice_id": invoice_id}, {"_id": 0}) or {}

    # ============================================================
    # DOMAIN CONFIG
    # ============================================================
    async def _active_domain() -> Dict[str, Any]:
        doc = await db.orisei_domain_config.find_one({"_id": "primary"}, {"_id": 0}) or {}
        primary = doc.get("primary_domain", "oriseifreight.com")
        return {
            "primary_domain": primary,
            "site_url": doc.get("site_url", f"https://{primary}"),
            "apex_url": doc.get("apex_url", f"https://{primary}"),
            "support_email": doc.get("support_email", f"hello@{primary}"),
            "legal_name": doc.get("legal_name", "Orisei Freight Solutions LLC"),
            "updated_at": doc.get("updated_at"),
            "propagate_to_static_site": doc.get("propagate_to_static_site", True),
        }

    @router.get("/domain-config")
    async def get_domain_config(_=Depends(get_current_user)) -> Dict[str, Any]:
        return await _active_domain()

    @router.post("/domain-config")
    async def set_domain_config(payload: DomainConfigIn, user=admin_dep) -> Dict[str, Any]:
        primary = payload.primary_domain.strip().lower()
        primary = re.sub(r"^https?://", "", primary).rstrip("/")
        doc = {
            "primary_domain": primary,
            "site_url": (payload.site_url or f"https://{primary}").rstrip("/"),
            "apex_url": (payload.apex_url or f"https://{primary}").rstrip("/"),
            "support_email": payload.support_email or f"hello@{primary}",
            "legal_name": payload.legal_name or "Orisei Freight Solutions LLC",
            "propagate_to_static_site": payload.propagate_to_static_site,
            "updated_at": _now(),
            "updated_by": getattr(user, "name", "system"),
        }
        await db.orisei_domain_config.update_one(
            {"_id": "primary"}, {"$set": doc}, upsert=True)
        propagated = False
        if payload.propagate_to_static_site:
            try:
                propagated = _propagate_domain_to_static(primary, doc["site_url"])
            except Exception as exc:                                           # noqa: BLE001
                logger.warning("Static site domain propagation failed: %s", exc)
        return {**doc, "propagated_to_static_site": propagated}

    api_router.include_router(router)


def _propagate_domain_to_static(primary_domain: str, site_url: str) -> bool:
    """Walk every static marketing HTML file and replace `oriseifreight.com`
    references with the user's chosen domain. Idempotent."""
    from pathlib import Path
    root = Path("/app/frontend/public/orisei-marketing")
    if not root.exists():
        return False
    targets = [
        ("oriseifreight.com", primary_domain),
        ("https://oriseifreight.com", site_url),
        ("http://oriseifreight.com", site_url),
    ]
    touched = 0
    for p in root.rglob("*.html"):
        try:
            txt = p.read_text(encoding="utf-8")
            new = txt
            for old, new_val in targets:
                new = new.replace(old, new_val)
            if new != txt:
                p.write_text(new, encoding="utf-8")
                touched += 1
        except Exception:                                                      # noqa: BLE001
            continue
    logger.info("Domain propagation touched %d static files", touched)
    return touched > 0
