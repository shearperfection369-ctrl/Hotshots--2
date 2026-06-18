"""
Data Status & Sample-Data Management
====================================

Centralized status endpoint + admin tools to keep operators honest about
what's real vs seeded sample data inside the TMS.

Conventions
-----------
Every row that *originated from a real user action* is stamped with
`is_sample: False`. Anything else (legacy seed rows, demo bootstraps) is
treated as sample data.

The list of collections we track lives in `TRACKED_COLLECTIONS`.

Endpoints
---------
* GET  /api/data-status
    → counts per collection (total / real / sample) and a `mode` value
      ("sample_heavy" | "mixed" | "live")
* POST /api/admin/backfill-sample-flags
    → one-time backfill: stamps every row missing `is_sample` as
      `is_sample: true` so the next /data-status call is accurate.
* POST /api/admin/clear-sample-data
    → wipes rows that are explicitly `is_sample: true` across all tracked
      collections. Real (`is_sample: false`) rows are kept. Returns the
      deletion summary.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException

log = logging.getLogger("orisei.data_status")

TRACKED_COLLECTIONS: List[str] = [
    "shipments",
    "brokerage_bookings",
    "orisei_customers",
    "orisei_invoices",
    "orisei_quotes",
    "orisei_rate_confirmations",
    "documents",
    "freight_bills",
    "drivers",
    "trailers",
    "carrier_onboarding",
    "specialty_carriers_custom",
    "chat_messages",
    "outbound_emails",
]


async def _counts(db, name: str) -> Dict[str, int]:
    total = await db[name].count_documents({})
    real  = await db[name].count_documents({"is_sample": False})
    # everything else (missing flag OR is_sample True) is treated as sample
    sample = total - real
    return {"total": total, "real": real, "sample": sample}


def build_data_status_router(*, db, get_current_user, require_role):
    router = APIRouter(tags=["data-status"])

    @router.get("/data-status")
    async def get_status(_=Depends(get_current_user)) -> Dict[str, Any]:
        rows: List[Dict[str, Any]] = []
        total_real = 0
        total_sample = 0
        for name in TRACKED_COLLECTIONS:
            c = await _counts(db, name)
            rows.append({"collection": name, **c})
            total_real += c["real"]
            total_sample += c["sample"]
        total = total_real + total_sample
        if total == 0:
            mode = "empty"
        elif total_real == 0:
            mode = "sample_only"
        elif total_sample == 0:
            mode = "live"
        elif total_real > total_sample:
            mode = "mostly_live"
        else:
            mode = "sample_heavy"
        return {
            "mode": mode,
            "total_real": total_real,
            "total_sample": total_sample,
            "collections": rows,
        }

    @router.post("/admin/backfill-sample-flags")
    async def backfill_sample(
        _=Depends(require_role("admin"))) -> Dict[str, Any]:
        """One-time: stamp every row currently missing `is_sample`
        with `is_sample: true`. New rows created through real user
        flows already get `is_sample: false`."""
        updated: List[Dict[str, Any]] = []
        for name in TRACKED_COLLECTIONS:
            r = await db[name].update_many(
                {"is_sample": {"$exists": False}},
                {"$set": {"is_sample": True}},
            )
            updated.append({"collection": name,
                             "stamped_as_sample": r.modified_count})
        return {"ok": True, "collections": updated}

    @router.post("/admin/clear-sample-data")
    async def clear_sample(confirm: bool = False,
                            _=Depends(require_role("admin"))) -> Dict[str, Any]:
        if not confirm:
            raise HTTPException(400,
                "Pass ?confirm=true to actually delete sample data.")
        removed: List[Dict[str, Any]] = []
        for name in TRACKED_COLLECTIONS:
            r = await db[name].delete_many({"is_sample": True})
            removed.append({"collection": name,
                             "deleted": r.deleted_count})
        return {"ok": True, "collections": removed}

    return router
