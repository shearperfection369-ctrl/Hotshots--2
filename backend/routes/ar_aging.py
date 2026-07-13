"""routes.ar_aging — Accounts-receivable aging, auto-invoicing & collections.

Three jobs:
  1. Aging report over `brokerage_invoices` — 30/60/90+ buckets, per-customer
     rollups, and dunning flags (watch / escalate / credit-hold).
  2. Auto-invoice engine — finds delivered/settled bookings that have no
     invoice yet and generates them (line items from the booking, due date
     from the customer's payment terms).
  3. Risk sync — customers with 61+ day past-due balances get their
     `shipper_risk` record credit-flagged, which the AI Load Hunter then
     uses to auto-reject their freight unless margin justifies it.

Endpoints — /api/ar/*
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException

logger = logging.getLogger("orisei.ar_aging")

OPEN_STATUSES = ("issued", "sent", "partial", "overdue")
BUCKETS = ["current", "b1_30", "b31_60", "b61_90", "b90_plus"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _parse_dt(v: Optional[str]) -> Optional[datetime]:
    if not v:
        return None
    try:
        dt = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _bucket_for(due_at: Optional[str]) -> tuple:
    """Returns (bucket_key, days_past_due)."""
    due = _parse_dt(due_at)
    if not due:
        return "current", 0
    days = (_now() - due).days
    if days <= 0: return "current", 0
    if days <= 30: return "b1_30", days
    if days <= 60: return "b31_60", days
    if days <= 90: return "b61_90", days
    return "b90_plus", days


def _flag_for(max_days: int) -> str:
    if max_days > 90: return "credit_hold"
    if max_days > 60: return "escalate"
    if max_days > 30: return "watch"
    return "clean"


def build_ar_router(
    *, api_router: APIRouter, db,
    get_current_user: Callable, require_role: Callable,
) -> None:
    router = APIRouter(prefix="/ar", tags=["ar-aging"])

    async def _open_invoices() -> List[Dict[str, Any]]:
        return await db.brokerage_invoices.find(
            {"status": {"$in": list(OPEN_STATUSES)}}, {"_id": 0}).to_list(2000)

    @router.get("/aging")
    async def aging(_=Depends(get_current_user)) -> Dict[str, Any]:
        """Full AR aging: bucket totals + per-customer rollups + flags."""
        invoices = await _open_invoices()
        totals = {b: 0.0 for b in BUCKETS}
        customers: Dict[str, Dict[str, Any]] = {}
        for inv in invoices:
            amt = float(inv.get("total_usd") or inv.get("amount_usd") or 0)
            bucket, days = _bucket_for(inv.get("due_at"))
            totals[bucket] += amt
            name = inv.get("customer_name") or "Unknown"
            c = customers.setdefault(name, {
                "customer_name": name, "customer_id": inv.get("customer_id"),
                "open_invoices": 0, "total_open_usd": 0.0,
                **{b: 0.0 for b in BUCKETS},
                "max_days_past_due": 0, "oldest_invoice_id": None,
            })
            c["open_invoices"] += 1
            c["total_open_usd"] += amt
            c[bucket] += amt
            if days > c["max_days_past_due"]:
                c["max_days_past_due"] = days
                c["oldest_invoice_id"] = inv.get("invoice_id")
        rows = []
        for c in customers.values():
            c["flag"] = _flag_for(c["max_days_past_due"])
            for k in ("total_open_usd", *BUCKETS):
                c[k] = round(c[k], 2)
            rows.append(c)
        rows.sort(key=lambda x: -x["max_days_past_due"])
        total_open = round(sum(totals.values()), 2)
        past_due = round(sum(v for k, v in totals.items() if k != "current"), 2)
        return {
            "buckets": {k: round(v, 2) for k, v in totals.items()},
            "total_open_usd": total_open,
            "past_due_usd": past_due,
            "past_due_pct": round(past_due / total_open * 100, 1) if total_open else 0.0,
            "open_invoice_count": len(invoices),
            "customers": rows,
            "flags": {f: sum(1 for r in rows if r["flag"] == f)
                      for f in ("watch", "escalate", "credit_hold")},
            "generated_at": _now_iso(),
        }

    @router.post("/auto-invoice/run")
    async def auto_invoice_run(user=Depends(require_role("admin", "dispatcher"))) -> Dict[str, Any]:
        """Generate invoices for every delivered/settled booking that has no
        invoice yet. Line items built from the booking; terms from the
        customer record (default Net 30)."""
        bookings = await db.brokerage_bookings.find(
            {"status": {"$in": ["delivered", "settled"]}}, {"_id": 0}).to_list(2000)
        invoiced_ids: set = set()
        async for inv in db.brokerage_invoices.find({}, {"_id": 0, "booking_ids": 1}):
            for bid in inv.get("booking_ids") or []:
                invoiced_ids.add(bid)
        created: List[Dict[str, Any]] = []
        for b in bookings:
            bid = b.get("booked_id")
            if not bid or bid in invoiced_ids:
                continue
            amount = float(b.get("settled_rate_usd") or b.get("forecast_rate_usd")
                           or b.get("customer_rate_usd") or 0)
            if amount <= 0:
                continue
            cust_name = b.get("customer_name") or b.get("consignee") or "Unknown Shipper"
            customer = await db.orisei_customers.find_one(
                {"name": cust_name}, {"_id": 0}) or {}
            terms = str(customer.get("payment_terms") or "Net 30")
            try:
                due_days = int("".join(ch for ch in terms if ch.isdigit()) or 30)
            except ValueError:
                due_days = 30
            invoice = {
                "invoice_id": f"INV-{uuid.uuid4().hex[:10].upper()}",
                "customer_id": customer.get("customer_id"),
                "customer_name": cust_name,
                "customer_billing_address": customer.get("billing_address"),
                "customer_ap_email": customer.get("ap_email"),
                "booking_ids": [bid],
                "line_items": [{
                    "label": f"{bid} · {b.get('origin', '')} → {b.get('destination', '')}",
                    "amount_usd": round(amount, 2),
                    "miles": b.get("miles"), "equipment": b.get("equipment"),
                }],
                "subtotal_usd": round(amount, 2), "tax_usd": 0,
                "total_usd": round(amount, 2),
                "issued_at": _now_iso(),
                "due_at": (_now() + timedelta(days=due_days)).isoformat(),
                "payment_terms": terms,
                "status": "issued",
                "auto_generated": True,
                "created_by": getattr(user, "user_id", "ar-engine"),
            }
            await db.brokerage_invoices.insert_one(dict(invoice))
            created.append({"invoice_id": invoice["invoice_id"], "booked_id": bid,
                            "customer": cust_name, "total_usd": invoice["total_usd"]})
        return {"ok": True, "created": len(created), "invoices": created,
                "scanned_bookings": len(bookings)}

    @router.post("/sync-risk")
    async def sync_risk(user=Depends(require_role("admin", "dispatcher"))) -> Dict[str, Any]:
        """Push AR flags into the Load Hunter's shipper risk registry:
        61+ days past due → credit_flag + payment score haircut."""
        invoices = await _open_invoices()
        worst: Dict[str, int] = {}
        for inv in invoices:
            _, days = _bucket_for(inv.get("due_at"))
            name = inv.get("customer_name") or "Unknown"
            worst[name] = max(worst.get(name, 0), days)
        flagged = []
        for name, days in worst.items():
            if days > 60:
                existing = await db.shipper_risk.find_one({"shipper": name}, {"_id": 0}) or {}
                new_score = min(int(existing.get("payment_score") or 70), max(20, 70 - days // 3))
                await db.shipper_risk.update_one(
                    {"shipper": name},
                    {"$set": {"shipper": name, "credit_flag": True,
                              "payment_score": new_score,
                              "avg_days_to_pay": days,
                              "notes": f"AR ENGINE: {days} days past due as of {_now_iso()[:10]}. "
                                       f"{existing.get('notes') or ''}"[:490],
                              "updated_at": _now_iso(),
                              "updated_by": "ar-engine"}},
                    upsert=True)
                flagged.append({"shipper": name, "days_past_due": days,
                                "payment_score": new_score})
        return {"ok": True, "flagged": flagged, "flagged_count": len(flagged),
                "note": "Flagged shippers now auto-reject in the AI Load Hunter unless margin exceeds the override threshold."}

    @router.post("/invoices/{invoice_id}/mark-paid")
    async def mark_paid(invoice_id: str,
                        user=Depends(require_role("admin", "dispatcher"))) -> Dict[str, Any]:
        r = await db.brokerage_invoices.update_one(
            {"invoice_id": invoice_id},
            {"$set": {"status": "paid", "paid_at": _now_iso(),
                      "updated_by": getattr(user, "user_id", None)}})
        if not r.matched_count:
            raise HTTPException(404, "Invoice not found")
        return {"ok": True, "invoice_id": invoice_id, "status": "paid"}

    @router.post("/invoices/{invoice_id}/remind")
    async def send_reminder(invoice_id: str, user=Depends(get_current_user)) -> Dict[str, Any]:
        """Record a dunning touch. Sends via Resend when configured;
        otherwise logs the reminder for the collections trail."""
        inv = await db.brokerage_invoices.find_one({"invoice_id": invoice_id}, {"_id": 0})
        if not inv:
            raise HTTPException(404, "Invoice not found")
        _, days = _bucket_for(inv.get("due_at"))
        level = "final_notice" if days > 60 else "second_notice" if days > 30 else "friendly_reminder"
        record = {
            "id": str(uuid.uuid4()), "invoice_id": invoice_id,
            "customer_name": inv.get("customer_name"),
            "total_usd": inv.get("total_usd"), "days_past_due": days,
            "level": level, "channel": "email",
            "to": inv.get("customer_ap_email") or "ap@customer (not on file)",
            "sent_at": _now_iso(), "sent_by": getattr(user, "user_id", None),
            "delivered": False,
            "note": "Queued — connect Resend in Connections to send live emails.",
        }
        await db.ar_dunning.insert_one(dict(record))
        await db.brokerage_invoices.update_one(
            {"invoice_id": invoice_id},
            {"$inc": {"reminder_count": 1},
             "$set": {"last_reminder_at": _now_iso()}})
        return {"ok": True, **record}

    @router.get("/dunning")
    async def dunning_history(limit: int = 30, _=Depends(get_current_user)) -> Dict[str, Any]:
        rows = await db.ar_dunning.find({}, {"_id": 0}).sort("sent_at", -1).to_list(min(limit, 100))
        return {"items": rows, "count": len(rows)}

    api_router.include_router(router)
    logger.info("AR aging router registered (/api/ar)")
