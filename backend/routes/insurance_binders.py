"""routes.insurance_binders — policy tracking behind the dual-insured promise.

Cargo liability + contingent cargo (and the rest of the stack) with
expiry countdowns so the "painless claims" commitment never quietly lapses.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

POLICY_TYPES = ["cargo_liability", "contingent_cargo", "auto_liability",
                "general_liability", "bmc84_bond", "eo_professional"]

SEED_POLICIES = [
    {"policy_type": "cargo_liability", "insurer": "Great West Casualty (sample)",
     "policy_number": "GWC-CL-2026-0417", "coverage_usd": 100000,
     "premium_monthly_usd": 385, "effective": "2026-01-01", "expires": "2026-12-31",
     "notes": "Primary cargo liability — $100K per load."},
    {"policy_type": "contingent_cargo", "insurer": "RLI Insurance (sample)",
     "policy_number": "RLI-CC-2026-1188", "coverage_usd": 100000,
     "premium_monthly_usd": 240, "effective": "2026-01-01", "expires": "2026-12-31",
     "notes": "Contingent cover — pays when the carrier's policy fails."},
    {"policy_type": "bmc84_bond", "insurer": "Pacific Financial (sample)",
     "policy_number": "BMC84-75K-3312", "coverage_usd": 75000,
     "premium_monthly_usd": 165, "effective": "2026-03-01", "expires": "2027-03-01",
     "notes": "FMCSA $75K broker surety bond."},
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _status(expires: str) -> Dict[str, Any]:
    try:
        days = (datetime.fromisoformat(expires).date() - datetime.now(timezone.utc).date()).days
    except Exception:
        return {"status": "unknown", "days_to_expiry": None}
    if days < 0:
        return {"status": "expired", "days_to_expiry": days}
    if days <= 30:
        return {"status": "expiring_soon", "days_to_expiry": days}
    return {"status": "active", "days_to_expiry": days}


class PolicyIn(BaseModel):
    policy_type: str
    insurer: str = Field(..., min_length=1)
    policy_number: str = ""
    coverage_usd: float = Field(0, ge=0)
    premium_monthly_usd: float = Field(0, ge=0)
    effective: str = ""
    expires: str = Field(..., min_length=8)
    notes: str = ""


class PolicyPatch(BaseModel):
    insurer: Optional[str] = None
    policy_number: Optional[str] = None
    coverage_usd: Optional[float] = None
    premium_monthly_usd: Optional[float] = None
    expires: Optional[str] = None
    notes: Optional[str] = None


def build_insurance_router(*, db, get_current_user: Callable) -> APIRouter:
    router = APIRouter(prefix="/insurance", tags=["insurance-binders"])

    async def _seed():
        if await db.insurance_policies.count_documents({}) == 0:
            for p in SEED_POLICIES:
                await db.insurance_policies.insert_one(
                    {**p, "id": f"POL-{uuid.uuid4().hex[:8].upper()}",
                     "is_sample": True, "created_at": _now_iso()})

    @router.get("/policies")
    async def list_policies(_=Depends(get_current_user)) -> Dict[str, Any]:
        await _seed()
        rows = await db.insurance_policies.find({}, {"_id": 0}).sort("expires", 1).to_list(50)
        for r in rows:
            r.update(_status(r.get("expires") or ""))
        types_active = {r["policy_type"] for r in rows if r["status"] in ("active", "expiring_soon")}
        dual = "cargo_liability" in types_active and "contingent_cargo" in types_active
        alerts = []
        for r in rows:
            if r["status"] == "expired":
                alerts.append(f"{r['policy_type'].replace('_', ' ').title()} ({r['insurer']}) EXPIRED")
            elif r["status"] == "expiring_soon":
                alerts.append(f"{r['policy_type'].replace('_', ' ').title()} ({r['insurer']}) "
                              f"expires in {r['days_to_expiry']} days")
        return {"policies": rows, "dual_insured": dual,
                "alerts": alerts,
                "monthly_premium_total_usd": round(sum(float(r.get("premium_monthly_usd") or 0)
                                                       for r in rows if r["status"] != "expired"), 2)}

    @router.post("/policies")
    async def create_policy(payload: PolicyIn, _=Depends(get_current_user)) -> Dict[str, Any]:
        if payload.policy_type not in POLICY_TYPES:
            raise HTTPException(400, f"policy_type must be one of {POLICY_TYPES}")
        doc = {**payload.model_dump(), "id": f"POL-{uuid.uuid4().hex[:8].upper()}",
               "is_sample": False, "created_at": _now_iso()}
        await db.insurance_policies.insert_one(dict(doc))
        doc.update(_status(doc["expires"]))
        return {"ok": True, "policy": doc}

    @router.patch("/policies/{pid}")
    async def patch_policy(pid: str, payload: PolicyPatch, _=Depends(get_current_user)) -> Dict[str, Any]:
        patch = payload.model_dump(exclude_unset=True)
        if not patch:
            raise HTTPException(400, "Nothing to update")
        r = await db.insurance_policies.find_one_and_update(
            {"id": pid}, {"$set": patch}, return_document=True, projection={"_id": 0})
        if not r:
            raise HTTPException(404, "Policy not found")
        r.update(_status(r.get("expires") or ""))
        return {"ok": True, "policy": r}

    @router.delete("/policies/{pid}")
    async def delete_policy(pid: str, _=Depends(get_current_user)) -> Dict[str, Any]:
        r = await db.insurance_policies.delete_one({"id": pid})
        if r.deleted_count == 0:
            raise HTTPException(404, "Policy not found")
        return {"ok": True}

    return router
