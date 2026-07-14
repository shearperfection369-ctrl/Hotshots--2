"""routes.live_ops — Real-time Live Ops Command: the production mirror of
Operation Sandbox. Same scoreboard, map, and feed — driven by REAL bookings,
shipments, and invoices (is_sample excluded). Read-only aggregation.

Endpoint — GET /api/live-ops/state
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List

from fastapi import APIRouter, Depends

logger = logging.getLogger("orisei.live_ops")
NOT_SAMPLE = {"is_sample": {"$ne": True}}


def build_live_ops_router(*, api_router: APIRouter, db,
                          get_current_user: Callable, require_role: Callable) -> None:
    router = APIRouter(prefix="/live-ops", tags=["live-ops"])

    @router.get("/state")
    async def state(_=Depends(get_current_user)) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        today = now.date().isoformat()
        week_cut = (now - timedelta(days=7)).isoformat()

        bookings = await db.brokerage_bookings.find(
            {**NOT_SAMPLE, "booked_at": {"$gte": week_cut}}, {"_id": 0}).to_list(2000)

        def _rev(b): return float(b.get("customer_rate_usd") or b.get("forecast_rate_usd") or 0)
        def _pay(b): return float(b.get("carrier_rate_usd") or b.get("forecast_carrier_pay_usd") or 0)

        daily_map: Dict[str, Dict[str, float]] = {}
        for i in range(7):
            daily_map[(now - timedelta(days=6 - i)).date().isoformat()] = {"loads": 0, "revenue": 0.0, "margin": 0.0}
        for b in bookings:
            day = (b.get("booked_at") or "")[:10]
            if day in daily_map:
                d = daily_map[day]
                d["loads"] += 1
                d["revenue"] += _rev(b)
                d["margin"] += _rev(b) - _pay(b)
        daily = [{"date": k, "loads": int(v["loads"]), "revenue": round(v["revenue"], 2),
                  "margin": round(v["margin"], 2)} for k, v in daily_map.items()]

        week_rev = sum(_rev(b) for b in bookings)
        week_margin = sum(_rev(b) - _pay(b) for b in bookings)
        today_rows = [b for b in bookings if (b.get("booked_at") or "").startswith(today)]

        transits = await db.shipments.find(
            {**NOT_SAMPLE, "status": {"$in": ["in_transit", "pending", "at_origin", "delayed"]}},
            {"_id": 0, "shipment_id": 1, "reference": 1, "carrier": 1, "status": 1,
             "origin": 1, "destination": 1, "current_location": 1, "progress": 1,
             "eta": 1, "customer_rate_usd": 1, "consignee": 1}).to_list(150)
        transits = [t for t in transits
                    if (t.get("current_location") or {}).get("lat") is not None]

        open_inv = await db.brokerage_invoices.find(
            {**NOT_SAMPLE, "status": {"$in": ["issued", "sent", "partial", "overdue"]}},
            {"_id": 0, "total_usd": 1, "due_at": 1, "customer_name": 1}).to_list(1000)
        ar_open = sum(float(i.get("total_usd") or 0) for i in open_inv)
        past_due = sum(float(i.get("total_usd") or 0) for i in open_inv
                       if (i.get("due_at") or "9999") < now.isoformat())
        paid_week = await db.brokerage_invoices.find(
            {**NOT_SAMPLE, "status": "paid", "paid_at": {"$gte": week_cut}},
            {"_id": 0, "total_usd": 1}).to_list(1000)

        # unified live feed: bookings + invoices + hunter decisions
        feed: List[Dict[str, Any]] = []
        for b in sorted(bookings, key=lambda x: x.get("booked_at") or "", reverse=True)[:12]:
            feed.append({"at": b.get("booked_at"), "type": "book",
                         "message": f"📦 {b.get('booked_id')} booked · {b.get('origin')} → {b.get('destination')} · ${_rev(b):,.0f} ({b.get('carrier_name')})"})
        async for i in db.brokerage_invoices.find(
                {**NOT_SAMPLE, "issued_at": {"$gte": week_cut}},
                {"_id": 0, "invoice_id": 1, "customer_name": 1, "total_usd": 1,
                 "issued_at": 1, "status": 1}).sort("issued_at", -1).limit(10):
            feed.append({"at": i.get("issued_at"), "type": "invoice",
                         "message": f"🧾 {i['invoice_id']} → {i.get('customer_name')} · ${float(i.get('total_usd') or 0):,.0f} · {i.get('status')}"})
        async for a in db.hunter_audit.find(
                {"action": {"$in": ["auto_book", "manual_book", "risk_reject", "weights_retrained"]}},
                {"_id": 0}).sort("at", -1).limit(10):
            icon = {"auto_book": "🤖", "manual_book": "✅", "risk_reject": "🛑",
                    "weights_retrained": "🧠"}.get(a["action"], "·")
            feed.append({"at": a.get("at"), "type": a["action"],
                         "message": f"{icon} Hunter {a['action'].replace('_', ' ')} · {a.get('lane') or ''} {a.get('shipper') or ''}".strip()})
        feed.sort(key=lambda x: x.get("at") or "", reverse=True)

        # triage: AR flags + open hunter risk info
        triage: List[Dict[str, Any]] = []
        cust_due: Dict[str, float] = {}
        for i in open_inv:
            if (i.get("due_at") or "9999") < now.isoformat():
                cust_due[i.get("customer_name") or "?"] = cust_due.get(i.get("customer_name") or "?", 0) + float(i.get("total_usd") or 0)
        for name, amt in sorted(cust_due.items(), key=lambda x: -x[1])[:6]:
            triage.append({"type": "past_due", "title": f"{name} past due ${amt:,.0f}",
                           "action": "Send reminder from Accounting → AR Engine, then Sync Risk Flags"})

        return {
            "as_of": now.isoformat(),
            "kpis": {
                "today_loads": len(today_rows),
                "today_revenue": round(sum(_rev(b) for b in today_rows), 2),
                "today_margin": round(sum(_rev(b) - _pay(b) for b in today_rows), 2),
                "week_loads": len(bookings),
                "week_revenue": round(week_rev, 2),
                "week_margin": round(week_margin, 2),
                "avg_daily_loads": round(len(bookings) / 7, 1),
                "in_transit": len(transits),
                "ar_outstanding": round(ar_open, 2),
                "ar_past_due": round(past_due, 2),
                "cash_collected_week": round(sum(float(p.get("total_usd") or 0) for p in paid_week), 2),
            },
            "daily": daily, "transits": transits,
            "feed": feed[:30], "triage": triage,
        }

    api_router.include_router(router)
    logger.info("Live Ops router registered (/api/live-ops)")
