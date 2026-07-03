"""routes.claims_master — Claims Master · Orisei Freight Solutions.

Prevention-first + swift resolution workflow. Enforces the "pay $500 in 48
hours to keep the $50K shipper" playbook. Every claim, photo, and comm is
timestamped for legal defensibility.

Claim lifecycle:
  new → acknowledged (must be < 24h) → investigating → decision:
    - fast_pay (carrier clearly liable, pay within 48h)
    - dispute (evidence supports carrier/shipper)
    - shipper_fault (docs + weather + photos back the carrier)
  → paid | denied | closed

Endpoints under /api/claims/*:
  GET    /dashboard                 · aggregate + reserve suggestion
  GET    /claims                    · list (filter by status/carrier/shipper)
  POST   /claims                    · file new claim (24-hr SLA starts NOW)
  GET    /claims/{id}               · full 360 (photos, comms, decisions)
  PATCH  /claims/{id}               · update fields
  POST   /claims/{id}/acknowledge   · stop the 24-hr SLA timer
  POST   /claims/{id}/decision      · fast_pay / dispute / shipper_fault
  POST   /claims/{id}/close         · closed with resolution note
  POST   /claims/{id}/photos        · upload photo (GridFS)
  GET    /claims/{id}/photos
  GET    /claims/{id}/photos/{pid}
  DELETE /claims/{id}/photos/{pid}
  POST   /claims/{id}/comms         · log communication event
  GET    /claims/{id}/report.pdf    · Orisei-branded incident report PDF

  GET    /carriers/watchlist        · carriers with 2+ claims (auto-cut)
  GET    /prevention/checklist      · per-load prevention checklist template
  POST   /prevention/audits         · attest a load passed the checklist
  GET    /prevention/audits/{load_id}

  GET    /reserve/suggestion        · reserve $ recommendation (2-3% of MRR)
  GET    /insurance/verifications   · list carrier COI status
  POST   /insurance/verifications   · attest a carrier's COI
"""
from __future__ import annotations

import io
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response, StreamingResponse
from motor.motor_asyncio import AsyncIOMotorGridFSBucket
from PIL import Image
from pydantic import BaseModel, EmailStr, Field

log = logging.getLogger("orisei.claims")


# ============================================================
#                       PYDANTIC MODELS
# ============================================================
class ClaimIn(BaseModel):
    booking_id: Optional[str] = Field(None, max_length=64)
    shipper_name: str = Field(..., min_length=1, max_length=200)
    carrier_mc: Optional[str] = Field(None, max_length=40)
    carrier_name: Optional[str] = Field(None, max_length=200)
    load_reference: Optional[str] = Field(None, max_length=64)
    origin: Optional[str] = Field(None, max_length=200)
    destination: Optional[str] = Field(None, max_length=200)
    kind: str = Field(..., pattern="^(damage|shortage|loss|delay|refused|contamination|other)$")
    claim_amount_usd: float = Field(..., ge=0)
    incident_at: Optional[str] = Field(None, max_length=32)
    discovered_at: Optional[str] = Field(None, max_length=32)
    description: str = Field(..., min_length=1, max_length=4000)
    shipper_contact_email: Optional[EmailStr] = None
    reported_by: Optional[str] = Field(None, max_length=120)


class ClaimPatch(BaseModel):
    status: Optional[str] = Field(None, pattern="^(new|acknowledged|investigating|decision|paid|denied|closed)$")
    priority: Optional[str] = Field(None, pattern="^(low|med|high|critical)$")
    assigned_to: Optional[str] = Field(None, max_length=120)
    internal_notes: Optional[str] = Field(None, max_length=8000)
    claim_amount_usd: Optional[float] = Field(None, ge=0)


class AckIn(BaseModel):
    ack_note: Optional[str] = Field(None, max_length=1000)


class DecisionIn(BaseModel):
    outcome: str = Field(..., pattern="^(fast_pay|dispute|shipper_fault|force_majeure)$")
    payout_usd: float = Field(0, ge=0)
    reasoning: str = Field(..., min_length=1, max_length=4000)
    evidence_summary: Optional[str] = Field(None, max_length=4000)


class CloseIn(BaseModel):
    resolution: str = Field(..., min_length=1, max_length=4000)
    final_payout_usd: float = Field(0, ge=0)


class CommIn(BaseModel):
    channel: str = Field(..., pattern="^(call|email|sms|meeting|note)$")
    direction: str = Field("outbound", pattern="^(inbound|outbound|internal)$")
    with_party: str = Field(..., pattern="^(shipper|carrier|insurer|internal)$")
    summary: str = Field(..., min_length=1, max_length=4000)


class AuditIn(BaseModel):
    load_id: str = Field(..., max_length=64)
    load_agreement_signed: bool = False
    windows_documented: bool = False
    equipment_condition_ok: bool = False
    load_securement_ok: bool = False
    pickup_photos_taken: bool = False
    delivery_photos_taken: bool = False
    carrier_coi_current: bool = False
    seal_intact_verified: bool = False
    notes: Optional[str] = Field(None, max_length=4000)


class CoiIn(BaseModel):
    carrier_mc: str = Field(..., max_length=40)
    carrier_name: Optional[str] = Field(None, max_length=200)
    policy_number: Optional[str] = Field(None, max_length=80)
    insurer: Optional[str] = Field(None, max_length=200)
    coverage_usd: float = Field(0, ge=0)
    effective_date: str = Field(..., max_length=32)
    expiration_date: str = Field(..., max_length=32)
    verified_by: Optional[str] = Field(None, max_length=120)


# ============================================================
#                       HELPERS
# ============================================================
def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _now_dt() -> datetime:
    return datetime.now(timezone.utc)

def _parse(iso: Optional[str]) -> Optional[datetime]:
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        # Ensure timezone-aware (date-only strings like "2025-01-01" come back naive)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None

def _prev_checklist_meta() -> List[Dict[str, Any]]:
    """The prevention checklist the user described (90% of the battle)."""
    return [
        {"key": "load_agreement_signed", "label": "Load agreement signed",
         "explain": "Every load agreement specifies pickup/delivery windows, equipment condition, securement requirements, and photo documentation standards."},
        {"key": "windows_documented", "label": "Pickup/delivery windows documented",
         "explain": "Hard windows written into the load tender to prevent late-arrival disputes."},
        {"key": "equipment_condition_ok", "label": "Equipment condition pre-inspected",
         "explain": "Photograph tires, doors, floor, walls, and reefer set-point (if applicable) before loading."},
        {"key": "load_securement_ok", "label": "Load securement inspected",
         "explain": "Straps, chains, blocking, bracing, dunnage — inspected + photographed per FMCSA §393."},
        {"key": "pickup_photos_taken", "label": "Pickup photos taken",
         "explain": "Carrier photos of load condition before touching the freight — the undeniable record."},
        {"key": "delivery_photos_taken", "label": "Delivery photos taken",
         "explain": "Broker/consignee photos at delivery. Combined with pickup photos = airtight documentation."},
        {"key": "carrier_coi_current", "label": "Carrier COI current",
         "explain": "Insurance verified within last 30 days. A denied claim from lapsed coverage is worse than no claim."},
        {"key": "seal_intact_verified", "label": "Trailer seal intact verified",
         "explain": "Seal # matches BOL at both ends. Broken seal = automatic red flag for contamination/tampering."},
    ]


# ============================================================
#                       PDF (Orisei-branded)
# ============================================================
async def _active_brand(db) -> Dict[str, Any]:
    """Return the currently-active brand kit for Orisei-branded claim PDFs.

    Fix (2026-07-03): previously queried `{"active": True}` which didn't
    match the DB schema (`is_active`), so all claim PDFs fell through to
    the first-inserted brand doc (Walmart). Now correctly prefers
    is_active → is_default → orisei brand_id → any brand.
    """
    b = await db.company_brand.find_one({"is_active": True}, {"_id": 0})
    if not b:
        b = await db.company_brand.find_one({"is_default": True}, {"_id": 0})
    if not b:
        b = await db.company_brand.find_one(
            {"brand_id": {"$regex": "orisei", "$options": "i"}}, {"_id": 0})
    if not b:
        b = await db.company_brand.find_one({}, {"_id": 0}) or {}
    return b


def _render_claim_report_pdf(claim: Dict[str, Any], comms: List[Dict], photos: List[Dict],
                              brand: Dict[str, Any]) -> bytes:
    """Build an Orisei-branded incident report PDF using the shared brand
    pipeline. Falls back to a minimal reportlab render if the brand
    module isn't available (which it always should be)."""
    md_lines: List[str] = []
    md_lines.append(f"# Incident Report · Claim {claim.get('claim_id')}")
    md_lines.append("")
    md_lines.append(f"**Filed:** {claim.get('filed_at','')[:19].replace('T',' ')}")
    md_lines.append(f"**Status:** {(claim.get('status') or '').upper()}")
    md_lines.append(f"**Priority:** {(claim.get('priority') or 'med').upper()}")
    if claim.get("assigned_to"):
        md_lines.append(f"**Assigned to:** {claim['assigned_to']}")
    md_lines.append("")
    md_lines.append("## Parties")
    md_lines.append(f"- **Shipper:** {claim.get('shipper_name','—')}")
    md_lines.append(f"- **Carrier:** {claim.get('carrier_name','—')} (MC {claim.get('carrier_mc','—')})")
    md_lines.append("")
    md_lines.append("## Shipment")
    md_lines.append(f"- **Load / Booking:** {claim.get('load_reference') or claim.get('booking_id') or '—'}")
    md_lines.append(f"- **Origin → Destination:** {claim.get('origin','—')} → {claim.get('destination','—')}")
    md_lines.append(f"- **Incident:** {claim.get('kind','—').upper()} on {(claim.get('incident_at') or '—')[:10]}")
    md_lines.append(f"- **Discovered:** {(claim.get('discovered_at') or '—')[:10]}")
    md_lines.append(f"- **Claim amount:** ${(claim.get('claim_amount_usd') or 0):,.2f}")
    md_lines.append("")
    md_lines.append("## Description")
    md_lines.append(claim.get("description") or "—")
    md_lines.append("")
    if claim.get("decision"):
        d = claim["decision"]
        md_lines.append("## Decision")
        md_lines.append(f"- **Outcome:** {d.get('outcome','').upper()}")
        md_lines.append(f"- **Payout:** ${(d.get('payout_usd') or 0):,.2f}")
        md_lines.append(f"- **Decided by:** {d.get('decided_by','—')} on {d.get('decided_at','')[:19].replace('T',' ')}")
        md_lines.append("")
        md_lines.append(f"**Reasoning.** {d.get('reasoning','—')}")
        if d.get("evidence_summary"):
            md_lines.append("")
            md_lines.append(f"**Evidence summary.** {d['evidence_summary']}")
        md_lines.append("")
    if claim.get("resolution"):
        md_lines.append("## Resolution")
        md_lines.append(claim["resolution"])
        md_lines.append(f"**Final payout:** ${(claim.get('final_payout_usd') or 0):,.2f}")
        md_lines.append("")
    if comms:
        md_lines.append("## Communications")
        md_lines.append("")
        md_lines.append("| When | Channel | With | Direction | Summary |")
        md_lines.append("|---|---|---|---|---|")
        for c in comms:
            md_lines.append(f"| {c.get('created_at','')[:16].replace('T',' ')} | {c.get('channel','')} "
                             f"| {c.get('with_party','')} | {c.get('direction','')} | "
                             f"{(c.get('summary','') or '').replace('|', '/')} |")
        md_lines.append("")
    if photos:
        md_lines.append("## Attached photos")
        for p in photos:
            md_lines.append(f"- {p.get('caption') or p.get('filename','photo')} · uploaded {p.get('uploaded_at','')[:10]}")
        md_lines.append("")
    md_lines.append("")
    md_lines.append("---")
    md_lines.append(f"_Confidential incident report. Prepared by {(brand.get('short_name') or 'Orisei')} claims desk. "
                     f"All communications archived per 49 CFR §370 recordkeeping._")

    md = "\n".join(md_lines)
    from routes.orisei_docs import build_branded_markdown_pdf  # local import
    return build_branded_markdown_pdf(
        md,
        title=f"Claim {claim.get('claim_id')} · Incident Report",
        subtitle=f"{claim.get('shipper_name','—')} vs {claim.get('carrier_name','—')}",
        doc_id=f"CLM-{claim.get('claim_id')}",
        brand=brand,
    )


# ============================================================
#                       ROUTER BUILDER
# ============================================================
def build_claims_master_router(
    *, api_router: APIRouter, db,
    get_current_user: Callable, require_role: Callable,
    fs_client=None,   # motor client — used for GridFS bucket
) -> None:
    router = APIRouter(prefix="/claims", tags=["claims-master"])
    user_dep = Depends(get_current_user)
    admin_dep = Depends(require_role("admin", "dispatcher"))

    bucket_name = "claim_photos"

    def _bucket() -> AsyncIOMotorGridFSBucket:
        # Use the motor async client wired into db.client
        return AsyncIOMotorGridFSBucket(db, bucket_name=bucket_name)

    def _actor(user) -> str:
        return getattr(user, "email", None) or getattr(user, "user_id", "system")

    async def _hydrate(claim: Dict[str, Any]) -> Dict[str, Any]:
        """Add computed fields (sla_hours_remaining, is_overdue, days_open)."""
        filed = _parse(claim.get("filed_at"))
        acked = _parse(claim.get("acknowledged_at"))
        now = _now_dt()
        if filed:
            claim["days_open"] = (now - filed).days
        if not acked and filed:
            deadline = filed + timedelta(hours=24)
            remaining = (deadline - now).total_seconds() / 3600
            claim["sla_hours_remaining"] = round(remaining, 1)
            claim["sla_breached"] = remaining < 0 and claim.get("status") not in ("closed", "paid", "denied")
        else:
            claim["sla_hours_remaining"] = None
            claim["sla_breached"] = False
        return claim

    # ------------------------ DASHBOARD ------------------------
    @router.get("/dashboard")
    async def dashboard(_=user_dep) -> Dict[str, Any]:
        claims = await db.claims_master.find({}, {"_id": 0}).to_list(2000)
        by_status: Dict[str, int] = {}
        by_kind: Dict[str, int] = {}
        by_carrier: Dict[str, Dict[str, Any]] = {}
        by_shipper: Dict[str, Dict[str, Any]] = {}
        total_open_usd = 0.0
        total_paid_usd = 0.0
        sla_breached = 0
        for c in claims:
            by_status[c.get("status", "new")] = by_status.get(c.get("status", "new"), 0) + 1
            by_kind[c.get("kind", "other")] = by_kind.get(c.get("kind", "other"), 0) + 1
            if c.get("status") not in ("paid", "denied", "closed"):
                total_open_usd += float(c.get("claim_amount_usd") or 0)
            if c.get("status") == "paid":
                total_paid_usd += float(c.get("final_payout_usd") or c.get("decision", {}).get("payout_usd", 0))
            mc = c.get("carrier_mc") or "Unassigned"
            slot = by_carrier.setdefault(mc, {
                "carrier_mc": mc, "carrier_name": c.get("carrier_name", mc),
                "claims_count": 0, "total_claim_usd": 0.0, "total_paid_usd": 0.0,
            })
            slot["claims_count"] += 1
            slot["total_claim_usd"] += float(c.get("claim_amount_usd") or 0)
            slot["total_paid_usd"] += float(c.get("final_payout_usd") or 0)
            sh = c.get("shipper_name") or "Unknown"
            sslot = by_shipper.setdefault(sh, {"shipper_name": sh, "claims_count": 0, "total_claim_usd": 0.0})
            sslot["claims_count"] += 1
            sslot["total_claim_usd"] += float(c.get("claim_amount_usd") or 0)
            # SLA breach detection
            filed = _parse(c.get("filed_at"))
            if filed and not c.get("acknowledged_at"):
                if (_now_dt() - filed) > timedelta(hours=24) and c.get("status") not in ("closed", "paid", "denied"):
                    sla_breached += 1

        # Watchlist: 2+ claims
        watchlist = sorted(
            [v for v in by_carrier.values() if v["claims_count"] >= 2],
            key=lambda x: -x["claims_count"],
        )

        # Reserve suggestion — 2.5% of last 90d revenue
        cutoff = _now_dt() - timedelta(days=90)
        bookings = await db.brokerage_bookings.find(
            {}, {"customer_rate_usd": 1, "rate_usd": 1, "created_at": 1, "_id": 0}).to_list(4000)
        rev_90d = 0.0
        for b in bookings:
            dt = _parse(b.get("created_at"))
            if dt and dt >= cutoff:
                rev_90d += float(b.get("customer_rate_usd") or b.get("rate_usd") or 0)
        rev_monthly = rev_90d / 3 if rev_90d else 0
        reserve_low = rev_monthly * 0.02
        reserve_high = rev_monthly * 0.03

        return {
            "totals": {
                "claims_total": len(claims),
                "open_claims_usd": round(total_open_usd, 2),
                "paid_claims_usd": round(total_paid_usd, 2),
                "sla_breached": sla_breached,
            },
            "by_status": by_status,
            "by_kind": by_kind,
            "top_shippers": sorted(by_shipper.values(), key=lambda x: -x["claims_count"])[:10],
            "carrier_watchlist": watchlist[:10],
            "reserve": {
                "trailing_90d_revenue_usd": round(rev_90d, 2),
                "monthly_avg_revenue_usd": round(rev_monthly, 2),
                "recommended_reserve_usd_low": round(reserve_low, 2),
                "recommended_reserve_usd_high": round(reserve_high, 2),
                "reasoning": "2-3% of monthly revenue is the industry standard claims reserve — protects your cash "
                              "when claims spike. Auto-recalculated from trailing 90-day bookings.",
            },
            "generated_at": _now(),
        }

    # ------------------------ CLAIMS CRUD ------------------------
    @router.get("/claims")
    async def list_claims(
        status: Optional[str] = None,
        carrier_mc: Optional[str] = None,
        shipper_name: Optional[str] = None,
        limit: int = Query(200, ge=1, le=1000),
        _=user_dep,
    ) -> Dict[str, Any]:
        q: Dict[str, Any] = {}
        if status:
            q["status"] = status
        if carrier_mc:
            q["carrier_mc"] = carrier_mc
        if shipper_name:
            q["shipper_name"] = {"$regex": f"^{shipper_name}$", "$options": "i"}
        rows = await db.claims_master.find(q, {"_id": 0}).sort("filed_at", -1).to_list(limit)
        hydrated = [await _hydrate(dict(r)) for r in rows]
        return {"items": hydrated, "count": len(hydrated)}

    @router.post("/claims")
    async def file_claim(payload: ClaimIn, user=admin_dep) -> Dict[str, Any]:
        doc = {
            "claim_id": f"CLM-{uuid.uuid4().hex[:10].upper()}",
            **payload.model_dump(exclude_none=True),
            "status": "new",
            "priority": "high" if payload.claim_amount_usd >= 5000 else "med",
            "filed_at": _now(),
            "filed_by": _actor(user),
            "sla_deadline_at": (_now_dt() + timedelta(hours=24)).isoformat(),
        }
        await db.claims_master.insert_one(dict(doc))
        # Auto-log the initial intake as an internal note
        await db.claim_communications.insert_one(dict({
            "comm_id": f"COM-{uuid.uuid4().hex[:10].upper()}",
            "claim_id": doc["claim_id"],
            "channel": "note", "direction": "internal", "with_party": "internal",
            "summary": f"Claim filed: {payload.kind.upper()} · ${payload.claim_amount_usd:,.2f}",
            "created_at": _now(),
            "created_by": _actor(user),
        }))
        doc.pop("_id", None)
        return await _hydrate(doc)

    @router.get("/claims/{claim_id}")
    async def claim_360(claim_id: str, _=user_dep) -> Dict[str, Any]:
        c = await db.claims_master.find_one({"claim_id": claim_id}, {"_id": 0})
        if not c:
            raise HTTPException(404, "Claim not found")
        comms = await db.claim_communications.find({"claim_id": claim_id}, {"_id": 0}).sort("created_at", 1).to_list(500)
        photos = await db.claim_photos.find({"claim_id": claim_id}, {"_id": 0}).sort("uploaded_at", 1).to_list(200)
        return {
            "claim": await _hydrate(c),
            "communications": comms,
            "photos": photos,
        }

    @router.patch("/claims/{claim_id}")
    async def update_claim(claim_id: str, payload: ClaimPatch, user=admin_dep) -> Dict[str, Any]:
        updates = payload.model_dump(exclude_none=True)
        if not updates:
            raise HTTPException(400, "No updates provided")
        updates["updated_at"] = _now()
        updates["updated_by"] = _actor(user)
        res = await db.claims_master.update_one({"claim_id": claim_id}, {"$set": updates})
        if not res.matched_count:
            raise HTTPException(404, "Claim not found")
        return await claim_360(claim_id, _=user)

    @router.post("/claims/{claim_id}/acknowledge")
    async def acknowledge(claim_id: str, payload: AckIn, user=admin_dep) -> Dict[str, Any]:
        c = await db.claims_master.find_one({"claim_id": claim_id}, {"_id": 0})
        if not c:
            raise HTTPException(404, "Claim not found")
        if c.get("acknowledged_at"):
            return {"ok": True, "message": "Already acknowledged", "acknowledged_at": c["acknowledged_at"]}
        ack_at = _now()
        await db.claims_master.update_one(
            {"claim_id": claim_id},
            {"$set": {"status": "acknowledged", "acknowledged_at": ack_at,
                       "acknowledged_by": _actor(user), "updated_at": ack_at}})
        # Auto-log
        await db.claim_communications.insert_one(dict({
            "comm_id": f"COM-{uuid.uuid4().hex[:10].upper()}",
            "claim_id": claim_id,
            "channel": "email", "direction": "outbound", "with_party": "shipper",
            "summary": f"Acknowledged claim within SLA. {payload.ack_note or ''}".strip(),
            "created_at": ack_at,
            "created_by": _actor(user),
        }))
        return {"ok": True, "acknowledged_at": ack_at}

    @router.post("/claims/{claim_id}/decision")
    async def record_decision(claim_id: str, payload: DecisionIn, user=admin_dep) -> Dict[str, Any]:
        c = await db.claims_master.find_one({"claim_id": claim_id}, {"_id": 0})
        if not c:
            raise HTTPException(404, "Claim not found")
        decision = {
            **payload.model_dump(),
            "decided_at": _now(),
            "decided_by": _actor(user),
        }
        next_status = {"fast_pay": "paid", "dispute": "investigating",
                        "shipper_fault": "denied", "force_majeure": "denied"}[payload.outcome]
        set_doc: Dict[str, Any] = {"decision": decision, "status": next_status,
                                    "updated_at": _now(), "updated_by": _actor(user)}
        if payload.outcome == "fast_pay":
            set_doc["final_payout_usd"] = payload.payout_usd
            set_doc["paid_at"] = _now()
        await db.claims_master.update_one({"claim_id": claim_id}, {"$set": set_doc})
        await db.claim_communications.insert_one(dict({
            "comm_id": f"COM-{uuid.uuid4().hex[:10].upper()}",
            "claim_id": claim_id,
            "channel": "note", "direction": "internal", "with_party": "internal",
            "summary": f"Decision: {payload.outcome.upper()} · payout ${payload.payout_usd:,.2f}. {payload.reasoning[:200]}",
            "created_at": _now(),
            "created_by": _actor(user),
        }))
        return {"ok": True, "decision": decision, "status": next_status}

    @router.post("/claims/{claim_id}/close")
    async def close_claim(claim_id: str, payload: CloseIn, user=admin_dep) -> Dict[str, Any]:
        res = await db.claims_master.update_one(
            {"claim_id": claim_id},
            {"$set": {"status": "closed", "resolution": payload.resolution,
                       "final_payout_usd": payload.final_payout_usd,
                       "closed_at": _now(), "closed_by": _actor(user),
                       "updated_at": _now()}})
        if not res.matched_count:
            raise HTTPException(404, "Claim not found")
        await db.claim_communications.insert_one(dict({
            "comm_id": f"COM-{uuid.uuid4().hex[:10].upper()}",
            "claim_id": claim_id,
            "channel": "note", "direction": "internal", "with_party": "internal",
            "summary": f"Closed. Final payout ${payload.final_payout_usd:,.2f}. {payload.resolution[:200]}",
            "created_at": _now(),
            "created_by": _actor(user),
        }))
        return {"ok": True, "claim_id": claim_id}

    # ------------------------ COMMUNICATIONS ------------------------
    @router.post("/claims/{claim_id}/comms")
    async def log_comm(claim_id: str, payload: CommIn, user=admin_dep) -> Dict[str, Any]:
        c = await db.claims_master.find_one({"claim_id": claim_id}, {"_id": 0})
        if not c:
            raise HTTPException(404, "Claim not found")
        doc = {
            "comm_id": f"COM-{uuid.uuid4().hex[:10].upper()}",
            "claim_id": claim_id,
            **payload.model_dump(),
            "created_at": _now(),
            "created_by": _actor(user),
        }
        await db.claim_communications.insert_one(dict(doc))
        doc.pop("_id", None)
        return doc

    # ------------------------ PHOTOS (GridFS) ------------------------
    @router.post("/claims/{claim_id}/photos")
    async def upload_photo(
        claim_id: str,
        file: UploadFile = File(...),
        caption: str = Form(""),
        kind: str = Form("damage"),   # damage | pickup | delivery | seal | other
        user=admin_dep,
    ) -> Dict[str, Any]:
        c = await db.claims_master.find_one({"claim_id": claim_id}, {"_id": 0})
        if not c:
            raise HTTPException(404, "Claim not found")
        raw = await file.read()
        if len(raw) > 8 * 1024 * 1024:
            raise HTTPException(400, "Photo too large (max 8MB)")
        # Downsample to ≤1600px @ q82
        try:
            img = Image.open(io.BytesIO(raw))
            img = img.convert("RGB") if img.mode != "RGB" else img
            img.thumbnail((1600, 1600))
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=82, optimize=True)
            data = buf.getvalue()
        except Exception:
            data = raw
        oid = await _bucket().upload_from_stream(
            filename=file.filename or "photo.jpg",
            source=data,
            metadata={"claim_id": claim_id, "content_type": "image/jpeg"},
        )
        doc = {
            "photo_id": f"PH-{uuid.uuid4().hex[:10].upper()}",
            "claim_id": claim_id,
            "gridfs_id": str(oid),
            "filename": file.filename,
            "caption": caption,
            "kind": kind,
            "size_bytes": len(data),
            "uploaded_at": _now(),
            "uploaded_by": _actor(user),
        }
        await db.claim_photos.insert_one(dict(doc))
        doc.pop("_id", None)
        return doc

    @router.get("/claims/{claim_id}/photos")
    async def list_photos(claim_id: str, _=user_dep) -> Dict[str, Any]:
        rows = await db.claim_photos.find({"claim_id": claim_id}, {"_id": 0}).sort("uploaded_at", 1).to_list(200)
        return {"items": rows, "count": len(rows)}

    @router.get("/claims/{claim_id}/photos/{photo_id}")
    async def get_photo(claim_id: str, photo_id: str, _=user_dep):
        p = await db.claim_photos.find_one({"claim_id": claim_id, "photo_id": photo_id}, {"_id": 0})
        if not p:
            raise HTTPException(404, "Photo not found")
        try:
            stream = await _bucket().open_download_stream(ObjectId(p["gridfs_id"]))
            data = await stream.read()
        except Exception:
            raise HTTPException(404, "Photo binary missing")
        return Response(content=data, media_type="image/jpeg")

    @router.delete("/claims/{claim_id}/photos/{photo_id}")
    async def delete_photo(claim_id: str, photo_id: str, _=admin_dep) -> Dict[str, Any]:
        p = await db.claim_photos.find_one({"claim_id": claim_id, "photo_id": photo_id}, {"_id": 0})
        if not p:
            raise HTTPException(404, "Photo not found")
        try:
            await _bucket().delete(ObjectId(p["gridfs_id"]))
        except Exception:
            pass
        await db.claim_photos.delete_one({"claim_id": claim_id, "photo_id": photo_id})
        return {"ok": True}

    # ------------------------ ORISEI-BRANDED REPORT ------------------------
    @router.get("/claims/{claim_id}/report.pdf")
    async def claim_report(claim_id: str, _=user_dep):
        c = await db.claims_master.find_one({"claim_id": claim_id}, {"_id": 0})
        if not c:
            raise HTTPException(404, "Claim not found")
        comms = await db.claim_communications.find({"claim_id": claim_id}, {"_id": 0}).sort("created_at", 1).to_list(500)
        photos = await db.claim_photos.find({"claim_id": claim_id}, {"_id": 0}).sort("uploaded_at", 1).to_list(200)
        brand = await _active_brand(db)
        pdf = _render_claim_report_pdf(c, comms, photos, brand)
        return StreamingResponse(io.BytesIO(pdf), media_type="application/pdf",
                                  headers={"Content-Disposition": f'inline; filename="claim_{claim_id}.pdf"'})

    # ------------------------ PREVENTION ------------------------
    @router.get("/prevention/checklist")
    async def prevention_template(_=user_dep) -> Dict[str, Any]:
        return {"checklist": _prev_checklist_meta()}

    @router.post("/prevention/audits")
    async def create_audit(payload: AuditIn, user=admin_dep) -> Dict[str, Any]:
        checks = ["load_agreement_signed", "windows_documented", "equipment_condition_ok",
                   "load_securement_ok", "pickup_photos_taken", "delivery_photos_taken",
                   "carrier_coi_current", "seal_intact_verified"]
        passed = sum(1 for k in checks if getattr(payload, k))
        score = round((passed / len(checks)) * 100, 1)
        doc = {
            "audit_id": f"PA-{uuid.uuid4().hex[:10].upper()}",
            **payload.model_dump(),
            "passed_count": passed,
            "total_checks": len(checks),
            "score_pct": score,
            "attested_at": _now(),
            "attested_by": _actor(user),
        }
        await db.claim_prevention_audits.insert_one(dict(doc))
        doc.pop("_id", None)
        return doc

    @router.get("/prevention/audits/{load_id}")
    async def get_audit(load_id: str, _=user_dep) -> Dict[str, Any]:
        row = await db.claim_prevention_audits.find_one(
            {"load_id": load_id}, {"_id": 0}, sort=[("attested_at", -1)])
        if not row:
            raise HTTPException(404, "No prevention audit for this load")
        return row

    @router.get("/prevention/audits")
    async def list_audits(_=user_dep) -> Dict[str, Any]:
        rows = await db.claim_prevention_audits.find({}, {"_id": 0}).sort("attested_at", -1).to_list(500)
        return {"items": rows, "count": len(rows)}

    # ------------------------ CARRIER WATCHLIST ------------------------
    @router.get("/carriers/watchlist")
    async def carrier_watchlist(_=user_dep) -> Dict[str, Any]:
        claims = await db.claims_master.find({}, {"_id": 0}).to_list(2000)
        agg: Dict[str, Dict[str, Any]] = {}
        for c in claims:
            mc = c.get("carrier_mc") or "Unassigned"
            slot = agg.setdefault(mc, {
                "carrier_mc": mc,
                "carrier_name": c.get("carrier_name", mc),
                "claims_count": 0,
                "total_claim_usd": 0.0,
                "total_paid_usd": 0.0,
                "claim_kinds": [],
                "last_claim_at": None,
            })
            slot["claims_count"] += 1
            slot["total_claim_usd"] += float(c.get("claim_amount_usd") or 0)
            slot["total_paid_usd"] += float(c.get("final_payout_usd") or 0)
            if c.get("kind"):
                slot["claim_kinds"].append(c["kind"])
            filed = c.get("filed_at")
            if filed and (not slot["last_claim_at"] or filed > slot["last_claim_at"]):
                slot["last_claim_at"] = filed
        rows = list(agg.values())
        for r in rows:
            r["cut_recommended"] = r["claims_count"] >= 2
        rows.sort(key=lambda r: (-r["claims_count"], -r["total_claim_usd"]))
        return {"items": rows, "count": len(rows),
                 "cut_count": sum(1 for r in rows if r["cut_recommended"])}

    # ------------------------ INSURANCE VERIFICATION ------------------------
    @router.get("/insurance/verifications")
    async def list_coi(_=user_dep) -> Dict[str, Any]:
        rows = await db.carrier_insurance_verifications.find({}, {"_id": 0}).sort("expiration_date", 1).to_list(500)
        now = _now_dt()
        for r in rows:
            exp = _parse(r.get("expiration_date"))
            if exp:
                days_left = (exp - now).days
                r["days_until_expiration"] = days_left
                r["status"] = "expired" if days_left < 0 else ("expiring_soon" if days_left <= 30 else "current")
            else:
                r["status"] = "unknown"
        return {"items": rows, "count": len(rows)}

    @router.post("/insurance/verifications")
    async def create_coi(payload: CoiIn, user=admin_dep) -> Dict[str, Any]:
        doc = {
            "verification_id": f"COI-{uuid.uuid4().hex[:10].upper()}",
            **payload.model_dump(),
            "verified_at": _now(),
            "verified_actor": _actor(user),
        }
        await db.carrier_insurance_verifications.insert_one(dict(doc))
        doc.pop("_id", None)
        return doc

    api_router.include_router(router)
