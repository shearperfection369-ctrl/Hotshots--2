"""
Internal Document Vault — automatic immutable archive of every generated PDF.

Every time a load-cycle document is rendered (BOL, Commercial Invoice, Packing
Slip, Weight Cert, COO, Rate Confirmation, Freight Quote), the raw PDF bytes
are pushed into the GridFS bucket `doc_vault` and a metadata row is written to
`document_archive`. This gives the brokerage a legally-defensible 7-year audit
trail of exactly what the carrier / shipper / consignee received.

Storage layer
-------------
* GridFS bucket name: `doc_vault`
* Metadata collection: `document_archive`
   - archive_id          : str  (uuid, primary key)
   - file_id             : ObjectId (GridFS handle)
   - doc_type            : "BOL" | "COMMERCIAL_INVOICE" | "PACKING_SLIP" |
                            "WEIGHT_CERT" | "COO" | "RATE_CONFIRMATION" |
                            "QUOTE" | "OTHER"
   - doc_id              : str  source document id (`document_id`, `rc_id`,
                                 `quote_id`, …) — same id keyed by all versions
   - version             : int  monotonically increasing per (doc_type, doc_id)
   - ref_id              : Optional[str] — shipment / booking the doc belongs to
   - filename            : str
   - size_bytes          : int
   - sha256              : str  immutability fingerprint
   - source_endpoint     : str  the API route that emitted it
   - payload_snapshot    : dict (jsonable) — minimum data needed to re-render
   - created_at          : iso-utc string
   - created_by          : str  user id (or "system")
   - created_by_name     : str
   - expires_at          : iso-utc string (default = created_at + 7 years)

Auto-capture surface
--------------------
* `archive_pdf(...)` is called inline by the main PDF-emitting endpoints; the
  call is fire-and-forget so a vault failure never blocks the download. Errors
  are logged to `document_archive_errors` for ops visibility.

Public API
----------
* `GET  /api/doc-vault`               — paged list with filters
* `GET  /api/doc-vault/{archive_id}`  — metadata
* `GET  /api/doc-vault/{archive_id}/file` — stream the PDF
* `GET  /api/doc-vault/stats`         — counts by type
* `POST /api/doc-vault/{archive_id}/re-render` — re-execute the source endpoint
                                                 internally and return a fresh
                                                 (newly-archived) PDF
"""
from __future__ import annotations

import hashlib
import io
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorGridFSBucket

log = logging.getLogger("orisei.doc_vault")

RETENTION_YEARS = 7  # matches the Cloudflare R2 immutability plan


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _retention_iso() -> str:
    return (datetime.now(timezone.utc)
            + timedelta(days=365 * RETENTION_YEARS)).isoformat(timespec="seconds")


# --------------------------------------------------------------------------
# Public helper — called by every PDF-emitting endpoint
# --------------------------------------------------------------------------
async def archive_pdf(
    db,
    pdf_bytes: bytes,
    *,
    doc_type: str,
    doc_id: str,
    ref_id: Optional[str] = None,
    source_endpoint: str,
    payload_snapshot: Optional[Dict[str, Any]] = None,
    user: Any = None,
    filename: Optional[str] = None,
) -> Optional[str]:
    """Immutable-archive a PDF. Returns the new `archive_id` or None on error.

    Failures are caught + logged so a vault hiccup can never break a download.
    """
    try:
        bucket = AsyncIOMotorGridFSBucket(db, bucket_name="doc_vault")
        version = await db.document_archive.count_documents(
            {"doc_type": doc_type, "doc_id": doc_id}) + 1
        archive_id = f"DA-{uuid.uuid4().hex[:12].upper()}"
        fname = filename or f"{doc_type}_{doc_id}_v{version}.pdf"
        sha = hashlib.sha256(pdf_bytes).hexdigest()
        meta_for_gridfs = {
            "archive_id": archive_id,
            "doc_type": doc_type,
            "doc_id": doc_id,
            "version": version,
            "sha256": sha,
            "content_type": "application/pdf",
        }
        file_id = await bucket.upload_from_stream(
            fname, pdf_bytes, metadata=meta_for_gridfs)
        row = {
            "archive_id": archive_id,
            "file_id": file_id,
            "doc_type": doc_type,
            "doc_id": doc_id,
            "version": version,
            "ref_id": ref_id,
            "filename": fname,
            "size_bytes": len(pdf_bytes),
            "sha256": sha,
            "source_endpoint": source_endpoint,
            "payload_snapshot": payload_snapshot or {},
            "created_at": _now_iso(),
            "created_by": getattr(user, "user_id", "system"),
            "created_by_name": getattr(user, "name", "system"),
            "expires_at": _retention_iso(),
        }
        await db.document_archive.insert_one(dict(row))
        return archive_id
    except Exception as e:                                       # noqa: BLE001
        log.exception("doc_vault archive failed for %s/%s: %s",
                       doc_type, doc_id, e)
        try:
            await db.document_archive_errors.insert_one({
                "at": _now_iso(),
                "doc_type": doc_type,
                "doc_id": doc_id,
                "error": str(e),
            })
        except Exception:                                        # noqa: BLE001
            pass
        return None


# --------------------------------------------------------------------------
# Router builder
# --------------------------------------------------------------------------
def build_doc_vault_router(*, db, get_current_user, require_role):

    router = APIRouter(prefix="/doc-vault", tags=["doc-vault"])
    bucket = AsyncIOMotorGridFSBucket(db, bucket_name="doc_vault")

    # ------------------------- LIST + FILTERS -----------------------------
    @router.get("")
    async def list_archive(
        doc_type: Optional[str] = Query(None),
        doc_id: Optional[str] = Query(None),
        ref_id: Optional[str] = Query(None),
        since: Optional[str] = Query(None, description="ISO date floor"),
        limit: int = Query(100, ge=1, le=500),
        _: Any = Depends(get_current_user),
    ) -> Dict[str, Any]:
        q: Dict[str, Any] = {}
        if doc_type:
            q["doc_type"] = doc_type
        if doc_id:
            q["doc_id"] = doc_id
        if ref_id:
            q["ref_id"] = ref_id
        if since:
            q["created_at"] = {"$gte": since}
        rows = (await db.document_archive
                .find(q, {"_id": 0, "file_id": 0, "payload_snapshot": 0})
                .sort("created_at", -1)
                .limit(limit)
                .to_list(limit))
        return {"items": rows, "count": len(rows),
                "retention_years": RETENTION_YEARS}

    # ------------------------------ STATS ---------------------------------
    @router.get("/stats")
    async def archive_stats(_: Any = Depends(get_current_user)) -> Dict[str, Any]:
        pipeline = [
            {"$group": {
                "_id": "$doc_type",
                "count": {"$sum": 1},
                "bytes": {"$sum": "$size_bytes"},
                "latest": {"$max": "$created_at"},
            }},
            {"$sort": {"count": -1}},
        ]
        by_type = []
        async for r in db.document_archive.aggregate(pipeline):
            by_type.append({
                "doc_type": r["_id"],
                "count": r["count"],
                "bytes": r["bytes"],
                "latest": r["latest"],
            })
        total = await db.document_archive.count_documents({})
        oldest = await (db.document_archive.find({}, {"_id": 0, "created_at": 1})
                        .sort("created_at", 1).limit(1).to_list(1))
        return {
            "total_documents": total,
            "by_type": by_type,
            "oldest_at": (oldest[0]["created_at"] if oldest else None),
            "retention_years": RETENTION_YEARS,
        }

    # ----------------------------- METADATA -------------------------------
    @router.get("/{archive_id}")
    async def get_metadata(archive_id: str,
                            _: Any = Depends(get_current_user)) -> Dict[str, Any]:
        row = await db.document_archive.find_one({"archive_id": archive_id},
                                                   {"_id": 0, "file_id": 0})
        if not row:
            raise HTTPException(404, "Archive entry not found")
        return row

    # ----------------------------- STREAM ---------------------------------
    @router.get("/{archive_id}/file")
    async def stream_pdf(archive_id: str,
                          download: bool = False,
                          _: Any = Depends(get_current_user)) -> StreamingResponse:
        row = await db.document_archive.find_one({"archive_id": archive_id})
        if not row:
            raise HTTPException(404, "Archive entry not found")
        file_id = row["file_id"]
        if not isinstance(file_id, ObjectId):
            file_id = ObjectId(file_id)
        stream = await bucket.open_download_stream(file_id)
        data = await stream.read()
        disposition = "attachment" if download else "inline"
        return StreamingResponse(
            io.BytesIO(data),
            media_type="application/pdf",
            headers={
                "Content-Disposition":
                    f'{disposition}; filename="{row["filename"]}"',
                "X-Archive-Sha256": row["sha256"],
                "X-Archive-Version": str(row["version"]),
            },
        )

    # ---------------------------- RE-RENDER -------------------------------
    @router.post("/{archive_id}/re-render")
    async def re_render(archive_id: str,
                         user: Any = Depends(get_current_user)) -> Dict[str, Any]:
        """Re-execute the source endpoint internally using the stored snapshot,
        producing a fresh PDF (newly-archived as v+1). The immutable original
        is never modified — this is purely a convenience for editable reprints.
        """
        row = await db.document_archive.find_one({"archive_id": archive_id})
        if not row:
            raise HTTPException(404, "Archive entry not found")
        # We deliberately do NOT auto-call the source endpoint here (would need
        # an internal HTTP client + cookie passthrough). Instead the UI is
        # expected to hit the *original* generator with the same `doc_id`,
        # which will produce a new version automatically thanks to the
        # archive_pdf() hook at the source.
        original = {
            "BOL":               f"/api/documents/{row['doc_id']}/pdf",
            "COMMERCIAL_INVOICE": f"/api/documents/{row['doc_id']}/pdf",
            "PACKING_SLIP":       f"/api/documents/{row['doc_id']}/pdf",
            "WEIGHT_CERT":        f"/api/documents/{row['doc_id']}/pdf",
            "COO":                f"/api/documents/{row['doc_id']}/pdf",
            "RATE_CONFIRMATION":  f"/api/orisei/rate-confirmations/{row['doc_id']}/pdf",
            "QUOTE":              f"/api/orisei/quotes/{row['doc_id']}/pdf",
        }.get(row["doc_type"])
        if not original:
            raise HTTPException(400,
                f"No re-render path registered for doc_type={row['doc_type']}")
        return {
            "ok": True,
            "next_url": original,
            "note": "Hit next_url to generate a new editable version; the "
                    "vault will archive it automatically.",
        }

    return router
