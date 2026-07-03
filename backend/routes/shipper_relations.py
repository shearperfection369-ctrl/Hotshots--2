"""routes.shipper_relations — Shipper Relations Command Deck.

A full CRM + loyalty + incentives engine for building **quality shipper
relationships**. Distinct from the existing `shipper_outreach` module
(which handles PDF/email outreach templates). This module owns:

- Prospect / active-account CRM (lifecycle: lead → qualified → active →
  at-risk → churned)
- Versioned volume-discount rate cards
- Loyalty rebate programs (accrual against shipment thresholds)
- Fuel surcharge policy per shipper (fixed / indexed to EIA / negotiated)
- Damage-free guarantee tracker (claims %, OTD %, OTP %)
- Payment-term catalog (Net-15 / 30 / 45 / 60)
- Dedicated Account Manager assignment
- TMS integration registry (API / EDI / Portal / Email)
- Quarterly Business Review (QBR) scorecards with action items
- Pickup-window & delivery-window guarantees

Endpoints — mounted under /api/shipper-relations/*:
  GET    /dashboard                  · headline KPIs
  GET    /accounts                   · list all shipper accounts
  POST   /accounts                   · create prospect / account
  GET    /accounts/{id}              · full 360° view (incentives, QBRs, TMS, activity)
  PATCH  /accounts/{id}              · update basic fields
  DELETE /accounts/{id}              · soft-delete (status=churned)
  POST   /accounts/{id}/activity     · log call/email/meeting
  POST   /accounts/{id}/tier         · move lifecycle tier

  GET    /rate-cards                 · list all
  POST   /rate-cards                 · create new versioned card
  GET    /rate-cards/{id}
  PATCH  /rate-cards/{id}            · edit tier / commodity mix
  DELETE /rate-cards/{id}

  GET    /incentives                 · list incentive programs
  POST   /incentives                 · configure new program
  PATCH  /incentives/{id}
  DELETE /incentives/{id}
  POST   /accounts/{id}/assign-incentive   · attach program to shipper

  POST   /accounts/{id}/qbr          · record a QBR
  GET    /accounts/{id}/qbrs

  POST   /accounts/{id}/tms          · register TMS integration
  GET    /accounts/{id}/tms
  DELETE /accounts/{id}/tms/{tms_id}

Data model philosophy: every write includes `created_at`, `created_by`.
Every read excludes `_id`.
"""
from __future__ import annotations

import io
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, EmailStr

log = logging.getLogger("orisei.shipper_relations")


# ============================================================
#                       PYDANTIC MODELS
# ============================================================
class AccountIn(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=200)
    dba: Optional[str] = Field(None, max_length=200)
    industry: Optional[str] = Field(None, max_length=80)
    hq_city: Optional[str] = Field(None, max_length=80)
    hq_state: Optional[str] = Field(None, max_length=4)
    contact_name: Optional[str] = Field(None, max_length=120)
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = Field(None, max_length=40)
    annual_volume_loads: Optional[int] = Field(None, ge=0)
    annual_revenue_usd: Optional[float] = Field(None, ge=0)
    primary_lanes: Optional[List[str]] = None
    equipment_needs: Optional[List[str]] = None
    lifecycle: str = Field("lead", pattern="^(lead|qualified|active|at_risk|churned)$")
    payment_terms: str = Field("net_30", pattern="^(net_15|net_30|net_45|net_60|quick_pay)$")
    dedicated_am: Optional[str] = Field(None, max_length=120)
    notes: Optional[str] = Field(None, max_length=4000)


class AccountPatch(BaseModel):
    dba: Optional[str] = Field(None, max_length=200)
    industry: Optional[str] = Field(None, max_length=80)
    hq_city: Optional[str] = None
    hq_state: Optional[str] = Field(None, max_length=4)
    contact_name: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = None
    annual_volume_loads: Optional[int] = Field(None, ge=0)
    annual_revenue_usd: Optional[float] = Field(None, ge=0)
    primary_lanes: Optional[List[str]] = None
    equipment_needs: Optional[List[str]] = None
    payment_terms: Optional[str] = Field(None, pattern="^(net_15|net_30|net_45|net_60|quick_pay)$")
    dedicated_am: Optional[str] = None
    notes: Optional[str] = None


class LifecycleIn(BaseModel):
    lifecycle: str = Field(..., pattern="^(lead|qualified|active|at_risk|churned)$")
    reason: Optional[str] = Field(None, max_length=1000)


class ActivityIn(BaseModel):
    kind: str = Field(..., pattern="^(call|email|meeting|proposal|contract|note)$")
    summary: str = Field(..., max_length=2000)
    outcome: Optional[str] = Field(None, max_length=200)
    next_step: Optional[str] = Field(None, max_length=500)


class RateTier(BaseModel):
    min_loads_per_month: int = Field(..., ge=0)
    discount_pct: float = Field(..., ge=0, le=50)
    rate_per_mile_floor: Optional[float] = Field(None, ge=0)


class RateCardIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=140)
    equipment: str = Field(..., max_length=40)
    origin_region: Optional[str] = Field(None, max_length=80)
    dest_region: Optional[str] = Field(None, max_length=80)
    base_rpm: float = Field(..., ge=0)
    fuel_surcharge_pct: float = Field(0.0, ge=0, le=100)
    valid_from: str = Field(..., max_length=32)
    valid_to: Optional[str] = Field(None, max_length=32)
    tiers: List[RateTier]
    notes: Optional[str] = Field(None, max_length=1000)


class IncentiveIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=140)
    kind: str = Field(..., pattern="^(volume_rebate|damage_free_guarantee|otp_guarantee|dedicated_am|"
                                    "fuel_flex|payment_terms|flex_pickup|loyalty_tier|"
                                    "tms_integration|performance_review)$")
    threshold_loads: Optional[int] = Field(None, ge=0)
    threshold_revenue_usd: Optional[float] = Field(None, ge=0)
    reward_type: str = Field(..., pattern="^(rebate_pct|credit_usd|free_service|priority|guarantee)$")
    reward_value: float = Field(0, ge=0)
    frequency: str = Field("quarterly", pattern="^(one_time|monthly|quarterly|annual)$")
    description: Optional[str] = Field(None, max_length=2000)
    active: bool = True


class AssignIncentiveIn(BaseModel):
    incentive_id: str


class QBRIn(BaseModel):
    period: str = Field(..., max_length=40)            # e.g. "Q1 2026"
    otd_pct: Optional[float] = Field(None, ge=0, le=100)
    otp_pct: Optional[float] = Field(None, ge=0, le=100)
    damage_free_pct: Optional[float] = Field(None, ge=0, le=100)
    volume_loads: Optional[int] = Field(None, ge=0)
    revenue_usd: Optional[float] = Field(None, ge=0)
    nps_score: Optional[int] = Field(None, ge=-100, le=100)
    strengths: Optional[str] = Field(None, max_length=2000)
    gaps: Optional[str] = Field(None, max_length=2000)
    action_items: Optional[List[str]] = None
    next_review_date: Optional[str] = None


class TmsRegistrationIn(BaseModel):
    system: str = Field(..., min_length=1, max_length=80)   # e.g. "MercuryGate", "SAP TM"
    method: str = Field(..., pattern="^(api|edi|portal|email|sftp)$")
    endpoint: Optional[str] = Field(None, max_length=500)
    contact_it: Optional[str] = Field(None, max_length=120)
    status: str = Field("planned", pattern="^(planned|in_test|live|paused)$")
    notes: Optional[str] = Field(None, max_length=2000)


class SendWelcomeIn(BaseModel):
    sender_name: Optional[str] = Field(None, max_length=120)
    cc: Optional[List[EmailStr]] = None
    note_override: Optional[str] = Field(None, max_length=4000,
        description="If provided, replaces the auto-generated greeting body")
    subject_override: Optional[str] = Field(None, max_length=200)


# ============================================================
#                       ROUTER BUILDER
# ============================================================
def build_shipper_relations_router(
    *, api_router: APIRouter, db,
    get_current_user: Callable, require_role: Callable,
) -> None:
    router = APIRouter(prefix="/shipper-relations", tags=["shipper-relations"])
    user_dep = Depends(get_current_user)
    admin_dep = Depends(require_role("admin", "dispatcher"))

    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _actor(user) -> str:
        return getattr(user, "email", None) or getattr(user, "user_id", "system")

    # ------------------------ DASHBOARD ------------------------
    @router.get("/dashboard")
    async def dashboard(_=user_dep) -> Dict[str, Any]:
        accounts = await db.shipper_accounts.find({}, {"_id": 0}).to_list(2000)
        rate_cards = await db.shipper_rate_cards.count_documents({})
        incentives = await db.shipper_incentives.find({}, {"_id": 0}).to_list(500)
        qbrs = await db.shipper_qbrs.count_documents({})
        tms_integrations = await db.shipper_tms.count_documents({})

        by_stage: Dict[str, int] = {}
        for a in accounts:
            by_stage[a.get("lifecycle", "lead")] = by_stage.get(a.get("lifecycle", "lead"), 0) + 1
        total_annual_volume = sum(int(a.get("annual_volume_loads") or 0) for a in accounts)
        total_annual_revenue = sum(float(a.get("annual_revenue_usd") or 0) for a in accounts)

        # Portfolio quality (average scorecards from most recent QBR per account)
        all_qbrs = await db.shipper_qbrs.find({}, {"_id": 0}).sort("created_at", -1).to_list(2000)
        latest_by_acc: Dict[str, Dict[str, Any]] = {}
        for q in all_qbrs:
            if q["account_id"] not in latest_by_acc:
                latest_by_acc[q["account_id"]] = q
        def _avg(field: str) -> Optional[float]:
            vals = [q.get(field) for q in latest_by_acc.values() if isinstance(q.get(field), (int, float))]
            return round(sum(vals) / len(vals), 1) if vals else None

        # Loyalty rebate accrued (sum of estimated rebate across active shippers)
        rebate_accrued = 0.0
        for a in accounts:
            if a.get("lifecycle") != "active":
                continue
            rev = float(a.get("annual_revenue_usd") or 0)
            for iid in a.get("assigned_incentives", []) or []:
                inc = next((i for i in incentives if i.get("incentive_id") == iid), None)
                if inc and inc.get("kind") == "volume_rebate" and inc.get("reward_type") == "rebate_pct":
                    rebate_accrued += rev * (float(inc.get("reward_value") or 0) / 100)

        return {
            "totals": {
                "accounts": len(accounts),
                "rate_cards": rate_cards,
                "incentive_programs": len(incentives),
                "qbrs": qbrs,
                "tms_integrations": tms_integrations,
            },
            "pipeline": {
                "lead": by_stage.get("lead", 0),
                "qualified": by_stage.get("qualified", 0),
                "active": by_stage.get("active", 0),
                "at_risk": by_stage.get("at_risk", 0),
                "churned": by_stage.get("churned", 0),
            },
            "portfolio": {
                "annual_volume_loads": total_annual_volume,
                "annual_revenue_usd": round(total_annual_revenue, 2),
                "avg_otd_pct": _avg("otd_pct"),
                "avg_otp_pct": _avg("otp_pct"),
                "avg_damage_free_pct": _avg("damage_free_pct"),
                "avg_nps": _avg("nps_score"),
                "loyalty_rebate_accrued_usd": round(rebate_accrued, 2),
            },
            "generated_at": _now(),
        }

    # ------------------------ ACCOUNTS ------------------------
    @router.get("/accounts")
    async def list_accounts(_=user_dep) -> Dict[str, Any]:
        rows = await db.shipper_accounts.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
        return {"items": rows, "count": len(rows)}

    @router.post("/accounts")
    async def create_account(payload: AccountIn, user=admin_dep) -> Dict[str, Any]:
        # De-dupe on (company_name)
        exists = await db.shipper_accounts.find_one(
            {"company_name": {"$regex": f"^{payload.company_name}$", "$options": "i"}},
            {"_id": 0})
        if exists:
            raise HTTPException(409, f"Account '{payload.company_name}' already exists")
        doc = {
            "account_id": f"SHP-{uuid.uuid4().hex[:10].upper()}",
            **payload.model_dump(exclude_none=True),
            "assigned_incentives": [],
            "created_at": _now(),
            "created_by": _actor(user),
            "updated_at": _now(),
        }
        await db.shipper_accounts.insert_one(dict(doc))
        doc.pop("_id", None)
        return doc

    @router.get("/accounts/{account_id}")
    async def account_360(account_id: str, _=user_dep) -> Dict[str, Any]:
        acct = await db.shipper_accounts.find_one({"account_id": account_id}, {"_id": 0})
        if not acct:
            raise HTTPException(404, "Account not found")
        incentive_ids = acct.get("assigned_incentives") or []
        incentives = await db.shipper_incentives.find(
            {"incentive_id": {"$in": incentive_ids}}, {"_id": 0}).to_list(200)
        qbrs = await db.shipper_qbrs.find({"account_id": account_id}, {"_id": 0}).sort("created_at", -1).to_list(200)
        tms = await db.shipper_tms.find({"account_id": account_id}, {"_id": 0}).to_list(200)
        activity = await db.shipper_activity_log.find({"account_id": account_id}, {"_id": 0}).sort("created_at", -1).to_list(200)
        return {
            "account": acct,
            "incentives": incentives,
            "qbrs": qbrs,
            "tms_integrations": tms,
            "activity": activity,
        }

    @router.patch("/accounts/{account_id}")
    async def update_account(account_id: str, payload: AccountPatch, user=admin_dep) -> Dict[str, Any]:
        updates = payload.model_dump(exclude_none=True)
        if not updates:
            raise HTTPException(400, "No updates provided")
        updates["updated_at"] = _now()
        updates["updated_by"] = _actor(user)
        res = await db.shipper_accounts.update_one({"account_id": account_id}, {"$set": updates})
        if not res.matched_count:
            raise HTTPException(404, "Account not found")
        return await account_360(account_id, _=user)

    @router.delete("/accounts/{account_id}")
    async def churn_account(account_id: str, user=admin_dep) -> Dict[str, Any]:
        res = await db.shipper_accounts.update_one(
            {"account_id": account_id},
            {"$set": {"lifecycle": "churned", "churned_at": _now(),
                       "churned_by": _actor(user), "updated_at": _now()}})
        if not res.matched_count:
            raise HTTPException(404, "Account not found")
        return {"ok": True, "account_id": account_id}

    @router.post("/accounts/{account_id}/tier")
    async def move_tier(account_id: str, payload: LifecycleIn, user=admin_dep) -> Dict[str, Any]:
        res = await db.shipper_accounts.update_one(
            {"account_id": account_id},
            {"$set": {"lifecycle": payload.lifecycle, "updated_at": _now(),
                       "updated_by": _actor(user)}})
        if not res.matched_count:
            raise HTTPException(404, "Account not found")
        # Log to activity feed
        await db.shipper_activity_log.insert_one(dict({
            "activity_id": f"ACT-{uuid.uuid4().hex[:10].upper()}",
            "account_id": account_id,
            "kind": "note",
            "summary": f"Lifecycle → {payload.lifecycle.upper()}",
            "outcome": payload.reason or "",
            "created_at": _now(),
            "created_by": _actor(user),
        }))
        return {"ok": True, "lifecycle": payload.lifecycle}

    @router.post("/accounts/{account_id}/activity")
    async def log_activity(account_id: str, payload: ActivityIn, user=admin_dep) -> Dict[str, Any]:
        acct = await db.shipper_accounts.find_one({"account_id": account_id}, {"_id": 0})
        if not acct:
            raise HTTPException(404, "Account not found")
        doc = {
            "activity_id": f"ACT-{uuid.uuid4().hex[:10].upper()}",
            "account_id": account_id,
            **payload.model_dump(exclude_none=True),
            "created_at": _now(),
            "created_by": _actor(user),
        }
        await db.shipper_activity_log.insert_one(dict(doc))
        doc.pop("_id", None)
        return doc

    # ------------------------ RATE CARDS ------------------------
    @router.get("/rate-cards")
    async def list_rate_cards(_=user_dep) -> Dict[str, Any]:
        rows = await db.shipper_rate_cards.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
        return {"items": rows, "count": len(rows)}

    @router.post("/rate-cards")
    async def create_rate_card(payload: RateCardIn, user=admin_dep) -> Dict[str, Any]:
        doc = {
            "rate_card_id": f"RC-{uuid.uuid4().hex[:10].upper()}",
            **payload.model_dump(),
            "created_at": _now(),
            "created_by": _actor(user),
        }
        await db.shipper_rate_cards.insert_one(dict(doc))
        doc.pop("_id", None)
        return doc

    @router.patch("/rate-cards/{rate_card_id}")
    async def update_rate_card(rate_card_id: str, payload: RateCardIn, user=admin_dep) -> Dict[str, Any]:
        updates = payload.model_dump()
        updates["updated_at"] = _now()
        updates["updated_by"] = _actor(user)
        res = await db.shipper_rate_cards.update_one({"rate_card_id": rate_card_id}, {"$set": updates})
        if not res.matched_count:
            raise HTTPException(404, "Rate card not found")
        return await db.shipper_rate_cards.find_one({"rate_card_id": rate_card_id}, {"_id": 0})

    @router.delete("/rate-cards/{rate_card_id}")
    async def delete_rate_card(rate_card_id: str, _=admin_dep) -> Dict[str, Any]:
        res = await db.shipper_rate_cards.delete_one({"rate_card_id": rate_card_id})
        if not res.deleted_count:
            raise HTTPException(404, "Rate card not found")
        return {"ok": True}

    # ------------------------ INCENTIVES ------------------------
    @router.get("/incentives")
    async def list_incentives(_=user_dep) -> Dict[str, Any]:
        rows = await db.shipper_incentives.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
        return {"items": rows, "count": len(rows)}

    @router.post("/incentives")
    async def create_incentive(payload: IncentiveIn, user=admin_dep) -> Dict[str, Any]:
        doc = {
            "incentive_id": f"INC-{uuid.uuid4().hex[:10].upper()}",
            **payload.model_dump(),
            "created_at": _now(),
            "created_by": _actor(user),
        }
        await db.shipper_incentives.insert_one(dict(doc))
        doc.pop("_id", None)
        return doc

    @router.patch("/incentives/{incentive_id}")
    async def update_incentive(incentive_id: str, payload: IncentiveIn, user=admin_dep) -> Dict[str, Any]:
        updates = payload.model_dump()
        updates["updated_at"] = _now()
        updates["updated_by"] = _actor(user)
        res = await db.shipper_incentives.update_one({"incentive_id": incentive_id}, {"$set": updates})
        if not res.matched_count:
            raise HTTPException(404, "Incentive not found")
        return await db.shipper_incentives.find_one({"incentive_id": incentive_id}, {"_id": 0})

    @router.delete("/incentives/{incentive_id}")
    async def delete_incentive(incentive_id: str, _=admin_dep) -> Dict[str, Any]:
        res = await db.shipper_incentives.delete_one({"incentive_id": incentive_id})
        if not res.deleted_count:
            raise HTTPException(404, "Incentive not found")
        # Also unassign from any accounts
        await db.shipper_accounts.update_many(
            {"assigned_incentives": incentive_id},
            {"$pull": {"assigned_incentives": incentive_id}})
        return {"ok": True}

    @router.post("/accounts/{account_id}/assign-incentive")
    async def assign_incentive(account_id: str, payload: AssignIncentiveIn, user=admin_dep) -> Dict[str, Any]:
        acct = await db.shipper_accounts.find_one({"account_id": account_id}, {"_id": 0})
        if not acct:
            raise HTTPException(404, "Account not found")
        inc = await db.shipper_incentives.find_one({"incentive_id": payload.incentive_id}, {"_id": 0})
        if not inc:
            raise HTTPException(404, "Incentive not found")
        await db.shipper_accounts.update_one(
            {"account_id": account_id},
            {"$addToSet": {"assigned_incentives": payload.incentive_id},
             "$set": {"updated_at": _now(), "updated_by": _actor(user)}})
        return {"ok": True, "account_id": account_id, "incentive_id": payload.incentive_id}

    @router.delete("/accounts/{account_id}/incentives/{incentive_id}")
    async def unassign_incentive(account_id: str, incentive_id: str, user=admin_dep) -> Dict[str, Any]:
        res = await db.shipper_accounts.update_one(
            {"account_id": account_id},
            {"$pull": {"assigned_incentives": incentive_id},
             "$set": {"updated_at": _now(), "updated_by": _actor(user)}})
        if not res.matched_count:
            raise HTTPException(404, "Account not found")
        return {"ok": True}

    # ------------------------ QBRs ------------------------
    @router.post("/accounts/{account_id}/qbr")
    async def create_qbr(account_id: str, payload: QBRIn, user=admin_dep) -> Dict[str, Any]:
        acct = await db.shipper_accounts.find_one({"account_id": account_id}, {"_id": 0})
        if not acct:
            raise HTTPException(404, "Account not found")
        doc = {
            "qbr_id": f"QBR-{uuid.uuid4().hex[:10].upper()}",
            "account_id": account_id,
            **payload.model_dump(exclude_none=True),
            "created_at": _now(),
            "created_by": _actor(user),
        }
        await db.shipper_qbrs.insert_one(dict(doc))
        doc.pop("_id", None)
        return doc

    @router.get("/accounts/{account_id}/qbrs")
    async def list_qbrs(account_id: str, _=user_dep) -> Dict[str, Any]:
        rows = await db.shipper_qbrs.find({"account_id": account_id}, {"_id": 0}).sort("created_at", -1).to_list(200)
        return {"items": rows, "count": len(rows)}

    # ------------------------ TMS Integrations ------------------------
    @router.post("/accounts/{account_id}/tms")
    async def register_tms(account_id: str, payload: TmsRegistrationIn, user=admin_dep) -> Dict[str, Any]:
        acct = await db.shipper_accounts.find_one({"account_id": account_id}, {"_id": 0})
        if not acct:
            raise HTTPException(404, "Account not found")
        doc = {
            "tms_id": f"TMS-{uuid.uuid4().hex[:10].upper()}",
            "account_id": account_id,
            **payload.model_dump(exclude_none=True),
            "created_at": _now(),
            "created_by": _actor(user),
        }
        await db.shipper_tms.insert_one(dict(doc))
        doc.pop("_id", None)
        return doc

    @router.get("/accounts/{account_id}/tms")
    async def list_tms(account_id: str, _=user_dep) -> Dict[str, Any]:
        rows = await db.shipper_tms.find({"account_id": account_id}, {"_id": 0}).to_list(200)
        return {"items": rows, "count": len(rows)}

    @router.delete("/accounts/{account_id}/tms/{tms_id}")
    async def delete_tms(account_id: str, tms_id: str, _=admin_dep) -> Dict[str, Any]:
        res = await db.shipper_tms.delete_one({"tms_id": tms_id, "account_id": account_id})
        if not res.deleted_count:
            raise HTTPException(404, "TMS integration not found")
        return {"ok": True}

    # ------------------------ SEED INCENTIVE CATALOG ------------------------
    @router.post("/seed-incentive-catalog")
    async def seed_catalog(_=admin_dep) -> Dict[str, Any]:
        """Idempotent — pre-loads the 11 canonical Orisei incentive programs.
        Safe to call repeatedly; only inserts missing entries."""
        catalog = [
            {"name": "Volume Rebate · 2% back at 100 loads/qtr",
             "kind": "volume_rebate", "threshold_loads": 100, "threshold_revenue_usd": None,
             "reward_type": "rebate_pct", "reward_value": 2.0, "frequency": "quarterly",
             "description": "Automatic 2% rebate on total invoiced revenue after 100 loads shipped in a quarter."},
            {"name": "Loyalty Tier · Silver → Gold → Platinum",
             "kind": "loyalty_tier", "threshold_loads": 250, "threshold_revenue_usd": None,
             "reward_type": "priority", "reward_value": 0, "frequency": "annual",
             "description": "Tiered service level: Silver <100/mo, Gold 100-249/mo, Platinum 250+/mo. Higher tiers unlock priority capacity, dedicated dispatcher, guaranteed pickup windows."},
            {"name": "Damage-Free Guarantee · 100% claim-free credit",
             "kind": "damage_free_guarantee", "threshold_loads": None, "threshold_revenue_usd": None,
             "reward_type": "credit_usd", "reward_value": 500.0, "frequency": "one_time",
             "description": "$500 credit issued per confirmed cargo claim, escalating to full freight refund on repeated failures. Independent claim adjuster on retainer."},
            {"name": "On-Time Pickup Guarantee · 98% or credit",
             "kind": "otp_guarantee", "threshold_loads": None, "threshold_revenue_usd": None,
             "reward_type": "credit_usd", "reward_value": 250.0, "frequency": "monthly",
             "description": "If monthly on-time pickup rate falls below 98%, shipper receives $250 credit per late pickup after the threshold breach."},
            {"name": "Dedicated Account Manager",
             "kind": "dedicated_am", "threshold_loads": 50, "threshold_revenue_usd": 500_000,
             "reward_type": "free_service", "reward_value": 0, "frequency": "annual",
             "description": "Assigned senior AM with direct dial + 4-hour response SLA. Included for accounts >50 loads/mo or >$500K annual spend."},
            {"name": "Fuel Surcharge Flexibility · EIA-indexed",
             "kind": "fuel_flex", "threshold_loads": None, "threshold_revenue_usd": None,
             "reward_type": "guarantee", "reward_value": 0, "frequency": "monthly",
             "description": "Fuel surcharge auto-adjusts weekly to EIA national diesel index. Shipper can lock a ceiling for the quarter."},
            {"name": "Extended Payment Terms · Net-60 for Platinum",
             "kind": "payment_terms", "threshold_loads": 250, "threshold_revenue_usd": 1_000_000,
             "reward_type": "guarantee", "reward_value": 60, "frequency": "annual",
             "description": "Net-60 payment terms unlocked for Platinum tier. Net-30 default across all active accounts. Quick-Pay at 2% discount available."},
            {"name": "Flexible Pickup Scheduling · Same-day",
             "kind": "flex_pickup", "threshold_loads": None, "threshold_revenue_usd": None,
             "reward_type": "priority", "reward_value": 0, "frequency": "monthly",
             "description": "0-4 hour pickup windows available with 24-hr notice. After-hours + weekend pickups at standard rates."},
            {"name": "TMS Integration Setup · Free",
             "kind": "tms_integration", "threshold_loads": None, "threshold_revenue_usd": None,
             "reward_type": "free_service", "reward_value": 0, "frequency": "one_time",
             "description": "Free API/EDI 204/210/214 integration with shipper's TMS (MercuryGate, SAP TM, Oracle OTM, McLeod, Descartes)."},
            {"name": "Quarterly Business Review · With action items",
             "kind": "performance_review", "threshold_loads": None, "threshold_revenue_usd": None,
             "reward_type": "free_service", "reward_value": 0, "frequency": "quarterly",
             "description": "Formal QBR every quarter — OTD/OTP/damage scorecards, lane performance, cost trend, action items with owners + due dates."},
            {"name": "Transparent Live Tracking · POD photo",
             "kind": "tms_integration", "threshold_loads": None, "threshold_revenue_usd": None,
             "reward_type": "guarantee", "reward_value": 0, "frequency": "monthly",
             "description": "Every load streams GPS + status updates to a shipper-branded portal. Delivery includes 3 photo-POD attachments emailed on-signature."},
        ]
        inserted = 0
        for entry in catalog:
            exists = await db.shipper_incentives.find_one({"name": entry["name"]}, {"_id": 0})
            if exists:
                continue
            doc = {
                "incentive_id": f"INC-{uuid.uuid4().hex[:10].upper()}",
                **entry,
                "active": True,
                "created_at": _now(),
                "created_by": "system::seed",
            }
            await db.shipper_incentives.insert_one(dict(doc))
            inserted += 1
        return {"ok": True, "inserted": inserted, "existing": len(catalog) - inserted}

    # ------------------------ WELCOME KIT (Orisei-branded PDF + mocked email) ------------------------
    async def _active_brand() -> Dict[str, Any]:
        """Match the same is_active → is_default → orisei → any fallback
        used everywhere else (fixed in iter 56)."""
        b = await db.company_brand.find_one({"is_active": True}, {"_id": 0})
        if not b:
            b = await db.company_brand.find_one({"is_default": True}, {"_id": 0})
        if not b:
            b = await db.company_brand.find_one(
                {"brand_id": {"$regex": "orisei", "$options": "i"}}, {"_id": 0})
        if not b:
            b = await db.company_brand.find_one({}, {"_id": 0}) or {}
        return b

    def _greeting(account: Dict[str, Any], sender_name: Optional[str],
                    brand: Dict[str, Any]) -> str:
        """Professional Orisei greeting, personalized to the shipper."""
        contact = account.get("contact_name") or "there"
        company = account.get("company_name") or "your team"
        first_name = contact.split(" ")[0] if contact and contact != "there" else "there"
        short = brand.get("short_name") or "Orisei"
        signer = sender_name or "The Orisei Freight Team"
        return (
            f"Hi {first_name},\n\n"
            f"On behalf of everyone at {short} Freight Solutions, welcome — we’re "
            f"delighted to have {company} exploring a partnership with us.\n\n"
            f"The document attached walks through what makes Orisei different: a single "
            f"purpose-built TMS covering brokerage ops, live tracking, claims, QBRs, "
            f"international, factoring, and cash-flow — all under your own branding, "
            f"backed by a real dispatch autopilot that shortens the time between load "
            f"posted and truck booked from hours down to seconds.\n\n"
            f"You’ll find a lane-level ROI snapshot, our onboarding roadmap, "
            f"payment-term options, and the direct contact information for your "
            f"dedicated account manager. If anything looks off, or you’d prefer a "
            f"quick call to walk through it live, hit reply — we’ll be on it the "
            f"same business day.\n\n"
            f"Looking forward to earning your freight.\n\n"
            f"Warm regards,\n"
            f"{signer}"
        )

    def _render_welcome_pdf(account: Dict[str, Any], brand: Dict[str, Any],
                              greeting: str, incentives: List[Dict[str, Any]]) -> bytes:
        short = brand.get("short_name") or "Orisei"
        company = account.get("company_name") or "Shipper"
        contact = account.get("contact_name") or ""
        md: List[str] = []
        md.append(f"# Welcome to {short} Freight Solutions")
        md.append(f"### Prepared for: {company}" + (f" · Attn: {contact}" if contact else ""))
        md.append("")
        # Greeting block
        md.append("## A note from our team")
        for line in greeting.split("\n\n"):
            md.append(line.strip())
            md.append("")
        md.append("---")
        md.append("")
        # Executive summary
        md.append(f"## Why {short}")
        md.append("- **One TMS. Every workflow.** Brokerage, live tracking, claims, QBRs, international, factoring, cash-flow — all in one branded production build.")
        md.append("- **Dispatch Autopilot.** Real-time load-matching engine with ML-scored carrier selection (accept probability + optimal rate suggestion) — cuts time-to-book from hours to seconds.")
        md.append("- **Aggregated load boards** — DAT · Truckstop · Convoy · Uber Freight · 123Loadboard, scored and margin-flagged before you see them.")
        md.append(f"- **Prevention-first claims desk** — 24-hr SLA, photo evidence chain, insurance verification, {short}-branded incident reports.")
        md.append("- **Auto-computed QBRs** — pull volume/OTD/damage/spend from the TMS, distribute a shipper-facing PDF in minutes, not days.")
        md.append("")
        # Account snapshot
        md.append(f"## What we know about {company}")
        md.append(f"- **Industry:** {account.get('industry') or '—'}")
        md.append(f"- **HQ:** {account.get('hq_city') or '—'}, {account.get('hq_state') or '—'}")
        md.append(f"- **Annual volume:** {(account.get('annual_volume_loads') or 0):,} loads")
        md.append(f"- **Annual revenue:** ${(account.get('annual_revenue_usd') or 0):,.0f}")
        md.append(f"- **Primary lanes:** {', '.join(account.get('primary_lanes') or []) or '—'}")
        md.append(f"- **Equipment focus:** {', '.join(account.get('equipment_needs') or []) or '—'}")
        md.append(f"- **Preferred payment terms:** {(account.get('payment_terms') or 'net_30').replace('_',' ').title()}")
        md.append(f"- **Dedicated AM:** {account.get('dedicated_am') or 'Assigning within 24 hrs'}")
        md.append("")
        # ROI snapshot
        volume = int(account.get("annual_volume_loads") or 0)
        if volume:
            avg_rev = 2450
            annual_rev = volume * avg_rev
            curr_margin = annual_rev * 0.125
            target_margin = annual_rev * 0.146
            lift = target_margin - curr_margin
            md.append("## Your ROI snapshot")
            md.append(f"- **Annual revenue (est.):** ${annual_rev:,.0f}")
            md.append("")
            md.append("| Metric | Today | With Orisei |")
            md.append("|---|---|---|")
            md.append("| Gross margin % | 12.5% | 14.6% |")
            md.append(f"| Annual gross margin | ${curr_margin:,.0f} | ${target_margin:,.0f} |")
            md.append(f"| **Annual lift** | — | **+${lift:,.0f}** |")
            md.append("")
        # Incentives shortlist
        if incentives:
            md.append("## Incentives available to your account")
            for inc in incentives[:6]:
                md.append(f"- **{inc.get('name')}** — {inc.get('description') or inc.get('kind','').replace('_',' ')}")
            md.append("")
        # 30-day onboarding map
        md.append("## Your 30-day onboarding roadmap")
        md.append("| Week | Milestones |")
        md.append("|---|---|")
        md.append("| Week 1 | Kickoff · brand kit uploaded · seed users · workspace live |")
        md.append("| Week 2 | Import lane list + rate cards · connect first load board · first booked load runs end-to-end |")
        md.append("| Week 3 | Claims desk + insurance verifications live · first Orisei-branded QBR distributed |")
        md.append("| Week 4 | Full team enabled · autopilot armed · executive health-check |")
        md.append("")
        # Contact block
        md.append("## Next step")
        md.append(f"Reply to this email or book a 15-minute walkthrough at **{short.lower()}freight.com/tour**. "
                    "Your dedicated account manager will follow up within one business day.")
        md.append("")
        md.append("---")
        md.append(f"_{short} Freight Solutions · confidential · rendered "
                    f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}._")
        text = "\n".join(md)
        from routes.orisei_docs import build_branded_markdown_pdf
        return build_branded_markdown_pdf(
            text,
            title=f"Welcome to {short} Freight Solutions",
            subtitle=f"Prepared for {company}",
            doc_id=f"WK-{uuid.uuid4().hex[:8].upper()}",
            brand=brand,
        )

    async def _account_incentives(account_id: str) -> List[Dict[str, Any]]:
        assignments = await db.shipper_incentive_assignments.find(
            {"account_id": account_id}, {"_id": 0}).to_list(50)
        if not assignments:
            return []
        ids = [a["incentive_id"] for a in assignments]
        return await db.shipper_incentives.find(
            {"incentive_id": {"$in": ids}}, {"_id": 0}).to_list(50)

    class SendWelcomeIn_inner:  # noqa: F841  (kept for backward-compat symbol reference)
        pass  # actual pydantic model is module-level SendWelcomeIn

    @router.get("/accounts/{account_id}/welcome.pdf")
    async def welcome_pdf(account_id: str, _=user_dep):
        account = await db.shipper_accounts.find_one({"account_id": account_id}, {"_id": 0})
        if not account:
            raise HTTPException(404, "Account not found")
        brand = await _active_brand()
        incentives = await _account_incentives(account_id)
        greeting = _greeting(account, None, brand)
        pdf = _render_welcome_pdf(account, brand, greeting, incentives)
        return StreamingResponse(io.BytesIO(pdf), media_type="application/pdf",
            headers={"Content-Disposition":
                     f'inline; filename="orisei_welcome_{account_id}.pdf"'})

    @router.post("/accounts/{account_id}/send-welcome")
    async def send_welcome(account_id: str, payload: SendWelcomeIn,
                            user=admin_dep) -> Dict[str, Any]:
        account = await db.shipper_accounts.find_one({"account_id": account_id}, {"_id": 0})
        if not account:
            raise HTTPException(404, "Account not found")
        to_email = account.get("contact_email")
        if not to_email:
            raise HTTPException(422, "Account has no contact_email — add one before sending.")

        brand = await _active_brand()
        short = brand.get("short_name") or "Orisei"
        incentives = await _account_incentives(account_id)
        greeting = payload.note_override or _greeting(account, payload.sender_name, brand)
        pdf = _render_welcome_pdf(account, brand, greeting, incentives)
        subject = payload.subject_override or (
            f"Welcome to {short} Freight Solutions — a personal note & our onboarding kit"
        )
        # Resend email — MOCKED (same pattern as iter 55 dispatch offers).
        # Production JSON shape preserved so flipping to a live Resend key
        # doesn't need code changes.
        import base64
        delivery = {
            "id": f"em-mock-{uuid.uuid4().hex[:14]}",
            "provider": "resend-mock",
            "to": to_email,
            "cc": [str(e) for e in (payload.cc or [])],
            "from_": f"dispatch@{short.lower()}freight.com",
            "subject": subject,
            "status": "queued",
            "attachment": {
                "filename": f"orisei_welcome_{account_id}.pdf",
                "size_bytes": len(pdf),
                "content_b64_preview": base64.b64encode(pdf[:24]).decode() + "…",
            },
            "sent_at": _now(),
        }
        # Auto-log the outbound greeting as an activity note on the account
        activity = {
            "activity_id": f"ACT-{uuid.uuid4().hex[:10].upper()}",
            "account_id": account_id,
            "kind": "email",
            "summary": f"Welcome kit sent · Orisei-branded PDF ({len(pdf):,} bytes) → {to_email}",
            "outcome": "delivered_mock",
            "next_step": "Follow up in 2 business days",
            "email_subject": subject,
            "email_greeting": greeting,
            "delivery_receipt": delivery,
            "created_at": _now(),
            "created_by": _actor(user),
        }
        await db.shipper_activity_log.insert_one(dict(activity))
        # Also stash a lightweight record so future audits can find sent kits
        await db.shipper_welcome_kits.insert_one(dict({
            "kit_id": f"WK-{uuid.uuid4().hex[:10].upper()}",
            "account_id": account_id,
            "to_email": to_email,
            "subject": subject,
            "greeting": greeting,
            "pdf_bytes": len(pdf),
            "delivery": delivery,
            "sent_at": _now(),
            "sent_by": _actor(user),
        }))
        activity.pop("_id", None)
        return {
            "ok": True,
            "delivery": delivery,
            "greeting_preview": greeting[:220] + ("…" if len(greeting) > 220 else ""),
            "activity": activity,
            "pdf_bytes": len(pdf),
        }

    @router.get("/accounts/{account_id}/welcome-history")
    async def welcome_history(account_id: str, _=user_dep) -> Dict[str, Any]:
        rows = await db.shipper_welcome_kits.find(
            {"account_id": account_id}, {"_id": 0}).sort("sent_at", -1).to_list(50)
        return {"items": rows, "count": len(rows)}

    api_router.include_router(router)
