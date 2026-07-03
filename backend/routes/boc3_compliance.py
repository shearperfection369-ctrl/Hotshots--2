"""routes.boc3_compliance — 50-state process-agent (BOC-3) tracker.

Rivals the workflow of Oversize Permits Inc., ComplianceIQ, and Iron Bow
for brokers/carriers who need to keep continuous BOC-3 designation in
every state they operate in.

Features:
  • 51 US jurisdictions reference (50 states + DC).
  • Per-state filing record with process agent name/address/phone,
    filed_at, cert #, expires_at (renewal), status (PENDING_FILE, FILED,
    ACCEPTED, REJECTED, EXPIRED, RENEWAL_DUE), rejection_reason.
  • Renewal calendar: groups filings by month with color-coded alerts —
    yellow @ ≤60 days before expiry (review), red @ ≤30 days (file now).
  • Blanket BOC-3 mode — one process-agent service designated for all 51
    jurisdictions in a single filing.
  • Compliance doc storage — attach the BMC-84 cert / BOC-3 cert PDF per
    state via GridFS bucket "boc3_docs".

Endpoints — mounted under /api/boc3/*:
  GET   /states                        · 51 US jurisdictions reference
  GET   /filings                       · list all filings
  POST  /filings                       · upsert (create/update by state)
  PUT   /filings/{filing_id}/status    · advance status w/ rejection reason
  DELETE /filings/{filing_id}          · void a filing
  GET   /calendar                      · renewal calendar grouped by month
  GET   /alerts                        · yellow + red alerts
  GET   /coverage                      · % of 51 jurisdictions currently covered

  POST  /filings/{filing_id}/upload    · attach cert PDF via GridFS
  GET   /filings/{filing_id}/file      · download attached cert
"""
from __future__ import annotations

import io
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

from fastapi import (APIRouter, Depends, File, Form, HTTPException, UploadFile)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

logger = logging.getLogger("orisei.boc3")


US_JURISDICTIONS = [
    {"code": "AL", "name": "Alabama"},        {"code": "AK", "name": "Alaska"},
    {"code": "AZ", "name": "Arizona"},        {"code": "AR", "name": "Arkansas"},
    {"code": "CA", "name": "California"},     {"code": "CO", "name": "Colorado"},
    {"code": "CT", "name": "Connecticut"},    {"code": "DE", "name": "Delaware"},
    {"code": "DC", "name": "District of Columbia"},
    {"code": "FL", "name": "Florida"},        {"code": "GA", "name": "Georgia"},
    {"code": "HI", "name": "Hawaii"},         {"code": "ID", "name": "Idaho"},
    {"code": "IL", "name": "Illinois"},       {"code": "IN", "name": "Indiana"},
    {"code": "IA", "name": "Iowa"},           {"code": "KS", "name": "Kansas"},
    {"code": "KY", "name": "Kentucky"},       {"code": "LA", "name": "Louisiana"},
    {"code": "ME", "name": "Maine"},          {"code": "MD", "name": "Maryland"},
    {"code": "MA", "name": "Massachusetts"},  {"code": "MI", "name": "Michigan"},
    {"code": "MN", "name": "Minnesota"},      {"code": "MS", "name": "Mississippi"},
    {"code": "MO", "name": "Missouri"},       {"code": "MT", "name": "Montana"},
    {"code": "NE", "name": "Nebraska"},       {"code": "NV", "name": "Nevada"},
    {"code": "NH", "name": "New Hampshire"},  {"code": "NJ", "name": "New Jersey"},
    {"code": "NM", "name": "New Mexico"},     {"code": "NY", "name": "New York"},
    {"code": "NC", "name": "North Carolina"}, {"code": "ND", "name": "North Dakota"},
    {"code": "OH", "name": "Ohio"},           {"code": "OK", "name": "Oklahoma"},
    {"code": "OR", "name": "Oregon"},         {"code": "PA", "name": "Pennsylvania"},
    {"code": "RI", "name": "Rhode Island"},   {"code": "SC", "name": "South Carolina"},
    {"code": "SD", "name": "South Dakota"},   {"code": "TN", "name": "Tennessee"},
    {"code": "TX", "name": "Texas"},          {"code": "UT", "name": "Utah"},
    {"code": "VT", "name": "Vermont"},        {"code": "VA", "name": "Virginia"},
    {"code": "WA", "name": "Washington"},     {"code": "WV", "name": "West Virginia"},
    {"code": "WI", "name": "Wisconsin"},      {"code": "WY", "name": "Wyoming"},
]

BOC3_STATUSES = [
    "PENDING_FILE",   # broker has drafted the filing but not yet submitted
    "FILED",          # submitted to FMCSA/state; awaiting acknowledgment
    "ACCEPTED",       # active and in good standing
    "REJECTED",       # FMCSA/state rejected the filing — needs re-file
    "EXPIRED",        # coverage lapsed — must re-file immediately
    "RENEWAL_DUE",    # ≤ 30 days to expiry — auto-flagged by calendar
    "VOID",           # cancelled/withdrawn
]


class Boc3FilingIn(BaseModel):
    state_code: str = Field(..., min_length=2, max_length=3)
    process_agent_name: str = Field(..., max_length=200)
    process_agent_address: str = Field(..., max_length=400)
    process_agent_phone: Optional[str] = Field(None, max_length=40)
    process_agent_email: Optional[str] = Field(None, max_length=200)
    is_blanket: bool = Field(False, description="One filing covers all 51 jurisdictions")
    filed_at: Optional[str] = None
    effective_date: Optional[str] = None
    expires_at: Optional[str] = None
    certificate_number: Optional[str] = Field(None, max_length=80)
    status: str = Field("PENDING_FILE")
    fees_usd: Optional[float] = Field(None, ge=0)
    notes: Optional[str] = Field(None, max_length=2000)


class Boc3StatusUpdate(BaseModel):
    status: str
    rejection_reason: Optional[str] = Field(None, max_length=1000)
    certificate_number: Optional[str] = Field(None, max_length=80)
    filed_at: Optional[str] = None
    expires_at: Optional[str] = None
    note: Optional[str] = Field(None, max_length=1000)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _days_until(iso: Optional[str]) -> Optional[int]:
    if not iso:
        return None
    try:
        d = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return (d - datetime.now(timezone.utc)).days
    except Exception:                                       # noqa: BLE001
        return None


def _alert_level(days: Optional[int]) -> Optional[str]:
    """RED for ≤30 days, YELLOW for ≤60, None otherwise."""
    if days is None:
        return None
    if days < 0:
        return "EXPIRED"
    if days <= 30:
        return "RED"
    if days <= 60:
        return "YELLOW"
    return None


def build_boc3_router(
    api_router: APIRouter, *, db,
    get_current_user: Callable, require_role: Callable,
) -> None:
    router = APIRouter(prefix="/boc3", tags=["boc3"])
    admin_dep = Depends(require_role("admin", "dispatcher"))
    JURIS_CODES = {j["code"] for j in US_JURISDICTIONS}

    @router.get("/states")
    async def states(_=Depends(get_current_user)) -> Dict[str, Any]:
        return {"items": US_JURISDICTIONS, "count": len(US_JURISDICTIONS),
                "statuses": BOC3_STATUSES}

    @router.get("/filings")
    async def list_filings(_=Depends(get_current_user)) -> Dict[str, Any]:
        rows = await db.boc3_filings.find({}, {"_id": 0}).sort(
            "state_code", 1).to_list(200)
        # Auto-compute alert level per row
        for r in rows:
            days = _days_until(r.get("expires_at"))
            r["days_to_expiry"] = days
            r["alert"] = _alert_level(days)
            # Auto-transition to RENEWAL_DUE if within 30 days and still ACCEPTED
            if r.get("status") == "ACCEPTED" and days is not None and days <= 30:
                r["status_effective"] = "RENEWAL_DUE"
            else:
                r["status_effective"] = r.get("status")
        return {"items": rows, "count": len(rows)}

    @router.post("/filings")
    async def upsert_filing(payload: Boc3FilingIn,
                              user=admin_dep) -> Dict[str, Any]:
        state_up = payload.state_code.upper()
        if state_up not in JURIS_CODES and not payload.is_blanket:
            raise HTTPException(400, f"Unknown state '{payload.state_code}'")
        if payload.status not in BOC3_STATUSES:
            raise HTTPException(400, f"Invalid status. Valid: {BOC3_STATUSES}")

        existing = await db.boc3_filings.find_one(
            {"state_code": state_up}, {"_id": 0})
        now = _now_iso()

        if existing:
            update = {**payload.model_dump(exclude_unset=True),
                       "state_code": state_up,
                       "updated_at": now,
                       "updated_by": getattr(user, "name", "system")}
            await db.boc3_filings.update_one(
                {"state_code": state_up}, {"$set": update})
            merged = {**existing, **update}
            return merged

        doc = {
            "filing_id": f"BOC3-{uuid.uuid4().hex[:10].upper()}",
            "created_at": now,
            "created_by": getattr(user, "name", "system"),
            **payload.model_dump(),
            "state_code": state_up,
            "history": [{"at": now, "by": getattr(user, "name", "system"),
                          "status": payload.status,
                          "note": "Initial filing draft"}],
        }
        await db.boc3_filings.insert_one(dict(doc))
        doc.pop("_id", None)
        return doc

    @router.put("/filings/{filing_id}/status")
    async def update_status(filing_id: str, payload: Boc3StatusUpdate,
                              user=admin_dep) -> Dict[str, Any]:
        if payload.status not in BOC3_STATUSES:
            raise HTTPException(400, f"Invalid status. Valid: {BOC3_STATUSES}")
        upd: Dict[str, Any] = {"status": payload.status,
                                "updated_at": _now_iso(),
                                "updated_by": getattr(user, "name", "system")}
        if payload.rejection_reason is not None:
            upd["rejection_reason"] = payload.rejection_reason
        if payload.certificate_number is not None:
            upd["certificate_number"] = payload.certificate_number
        if payload.filed_at is not None:
            upd["filed_at"] = payload.filed_at
        if payload.expires_at is not None:
            upd["expires_at"] = payload.expires_at
        history_entry = {"at": _now_iso(),
                         "by": getattr(user, "name", "system"),
                         "status": payload.status,
                         "note": payload.note or payload.rejection_reason}
        res = await db.boc3_filings.find_one_and_update(
            {"filing_id": filing_id},
            {"$set": upd, "$push": {"history": history_entry}},
            projection={"_id": 0}, return_document=True,
        )
        if not res:
            raise HTTPException(404, "Filing not found")
        return res

    @router.delete("/filings/{filing_id}")
    async def void_filing(filing_id: str,
                            user=admin_dep) -> Dict[str, Any]:
        res = await db.boc3_filings.find_one_and_update(
            {"filing_id": filing_id},
            {"$set": {"status": "VOID",
                       "voided_at": _now_iso(),
                       "voided_by": getattr(user, "name", "system")}},
            projection={"_id": 0}, return_document=True,
        )
        if not res:
            raise HTTPException(404, "Filing not found")
        return res

    @router.get("/calendar")
    async def renewal_calendar(_=Depends(get_current_user)) -> Dict[str, Any]:
        """Group filings by expiry month for the next 24 months + tag each
        with an alert level. Frontend renders a color-coded matrix."""
        rows = await db.boc3_filings.find(
            {"status": {"$nin": ["VOID"]}}, {"_id": 0}).to_list(200)
        buckets: Dict[str, List[Dict[str, Any]]] = {}
        for r in rows:
            if not r.get("expires_at"):
                buckets.setdefault("no-expiry-set", []).append(r)
                continue
            try:
                d = datetime.fromisoformat(r["expires_at"].replace("Z", "+00:00"))
            except Exception:                                    # noqa: BLE001
                continue
            month_key = d.strftime("%Y-%m")
            days = (d - datetime.now(timezone.utc)).days
            r["days_to_expiry"] = days
            r["alert"] = _alert_level(days)
            buckets.setdefault(month_key, []).append(r)
        # Emit sorted 24-month window
        now = datetime.now(timezone.utc)
        months: List[Dict[str, Any]] = []
        for i in range(24):
            m = (now.replace(day=1) + timedelta(days=31 * i))
            key = m.strftime("%Y-%m")
            months.append({
                "month": key,
                "label": m.strftime("%b %Y"),
                "filings": sorted(buckets.get(key, []),
                                    key=lambda x: x.get("state_code", "")),
            })
        return {
            "months": months,
            "no_expiry_set": buckets.get("no-expiry-set", []),
        }

    @router.get("/alerts")
    async def alerts(_=Depends(get_current_user)) -> Dict[str, Any]:
        """Return YELLOW (≤60d) and RED (≤30d) alerts across all filings."""
        rows = await db.boc3_filings.find(
            {"status": {"$in": ["ACCEPTED", "FILED"]}},
            {"_id": 0}).to_list(200)
        red: List[Dict[str, Any]] = []
        yellow: List[Dict[str, Any]] = []
        expired: List[Dict[str, Any]] = []
        for r in rows:
            days = _days_until(r.get("expires_at"))
            r["days_to_expiry"] = days
            r["alert"] = _alert_level(days)
            if r["alert"] == "RED":
                red.append(r)
            elif r["alert"] == "YELLOW":
                yellow.append(r)
            elif r["alert"] == "EXPIRED":
                expired.append(r)
        red.sort(key=lambda x: x.get("days_to_expiry") or 0)
        yellow.sort(key=lambda x: x.get("days_to_expiry") or 0)
        return {"red": red, "yellow": yellow, "expired": expired,
                "red_count": len(red), "yellow_count": len(yellow),
                "expired_count": len(expired)}

    @router.get("/coverage")
    async def coverage(_=Depends(get_current_user)) -> Dict[str, Any]:
        rows = await db.boc3_filings.find(
            {"status": {"$in": ["ACCEPTED", "FILED"]}},
            {"_id": 0, "state_code": 1, "is_blanket": 1}).to_list(200)
        covered_states = set()
        blanket = any(r.get("is_blanket") for r in rows)
        if blanket:
            covered_states = JURIS_CODES.copy()
        else:
            for r in rows:
                covered_states.add(r.get("state_code"))
        covered = covered_states & JURIS_CODES
        missing = JURIS_CODES - covered
        return {
            "total_jurisdictions": len(JURIS_CODES),
            "covered": sorted(covered),
            "missing": sorted(missing),
            "covered_count": len(covered),
            "missing_count": len(missing),
            "percent_covered": round(100 * len(covered) / len(JURIS_CODES), 1),
            "has_blanket": blanket,
        }

    # ---------------- FILE UPLOAD ----------------
    @router.post("/filings/{filing_id}/upload")
    async def upload_cert(filing_id: str,
                           file: UploadFile = File(...),
                           note: Optional[str] = Form(None),
                           user=admin_dep) -> Dict[str, Any]:
        existing = await db.boc3_filings.find_one(
            {"filing_id": filing_id}, {"_id": 0})
        if not existing:
            raise HTTPException(404, "Filing not found")
        from motor.motor_asyncio import AsyncIOMotorGridFSBucket
        bucket = AsyncIOMotorGridFSBucket(db, bucket_name="boc3_docs")
        data = await file.read()
        gridfs_id = await bucket.upload_from_stream(
            file.filename or "cert.pdf",
            data,
            metadata={"filing_id": filing_id,
                       "uploaded_by": getattr(user, "name", "system"),
                       "content_type": file.content_type},
        )
        upd = {
            "cert_file_id": str(gridfs_id),
            "cert_filename": file.filename,
            "cert_content_type": file.content_type,
            "cert_size": len(data),
            "cert_uploaded_at": _now_iso(),
            "cert_note": note,
        }
        await db.boc3_filings.update_one(
            {"filing_id": filing_id}, {"$set": upd})
        return {"ok": True, **upd}

    @router.get("/filings/{filing_id}/file")
    async def download_cert(filing_id: str,
                              _=Depends(get_current_user)) -> StreamingResponse:
        r = await db.boc3_filings.find_one(
            {"filing_id": filing_id}, {"_id": 0})
        if not r or not r.get("cert_file_id"):
            raise HTTPException(404, "No certificate attached")
        from bson import ObjectId
        from motor.motor_asyncio import AsyncIOMotorGridFSBucket
        bucket = AsyncIOMotorGridFSBucket(db, bucket_name="boc3_docs")
        stream = await bucket.open_download_stream(ObjectId(r["cert_file_id"]))
        data = await stream.read()
        filename = r.get("cert_filename") or "boc3_cert.pdf"
        return StreamingResponse(
            io.BytesIO(data),
            media_type=r.get("cert_content_type") or "application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'})

    api_router.include_router(router)
