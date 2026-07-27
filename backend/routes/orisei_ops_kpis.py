"""routes.orisei_ops_kpis — The 4 KPIs every shipper and carrier asks for.

  • Cost per mile by lane (origin-dest pairs, weighted by volume)
  • Margin % (gross + net, period over period)
  • Fill rate (booked / available, by week)
  • On-time % (delivered on or before promised date)

Plus per-carrier performance scorecards and per-lane drill-downs.

This is the dashboard a shipper relationship manager pulls up on a Monday
morning. Engineered for both Orisei (internal ops) and shipper-facing
weekly reports.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Depends, Query

logger = logging.getLogger("tennant_tms.orisei_ops_kpis")


def _lane_key(origin: str, destination: str) -> str:
    o = (origin or "?")[:30].strip().upper()
    d = (destination or "?")[:30].strip().upper()
    return f"{o} → {d}"


def _safe_dt(val: Any) -> Optional[datetime]:
    if not val:
        return None
    try:
        if isinstance(val, datetime):
            return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
        s = str(val).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def build_orisei_ops_router(
    api_router: APIRouter, *, db,
    get_current_user: Callable, require_role: Callable,
) -> None:
    """Wire ops-KPI endpoints into the main api_router."""
    router = APIRouter(prefix="/brokerage", tags=["ops-kpis"])
    user_dep = Depends(get_current_user)

    @router.get("/ops-kpis")
    async def ops_kpis(window_days: int = Query(30, ge=7, le=365),
                       _: Any = user_dep) -> Dict[str, Any]:
        """Single endpoint returning the 4 KPIs every shipper asks for,
        plus lane breakdown + carrier performance for the given window.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)

        bookings = await db.brokerage_bookings.find({}, {"_id": 0}).to_list(2000)
        # Filter to the window
        recent: List[Dict[str, Any]] = []
        for b in bookings:
            dt = _safe_dt(b.get("created_at") or b.get("booked_at"))
            if dt and dt >= cutoff:
                recent.append(b)

        # ---------------- HEADLINE KPIs ----------------
        total_loads = len(recent)
        delivered = [b for b in recent if b.get("status") == "delivered"]
        booked = [b for b in recent if b.get("status") in ("booked", "tendered", "delivered", "invoiced")]
        revenue = sum(float(b.get("customer_rate_usd") or b.get("rate_usd") or 0)
                       for b in recent)
        carrier_cost = sum(float(b.get("carrier_rate_usd") or 0) for b in recent)
        gross_margin = revenue - carrier_cost
        gross_margin_pct = (gross_margin / revenue * 100) if revenue else 0.0
        total_miles = sum(float(b.get("miles") or 0) for b in recent)
        cost_per_mile = (carrier_cost / total_miles) if total_miles else 0.0
        revenue_per_mile = (revenue / total_miles) if total_miles else 0.0

        # Fill rate = booked loads / total available loads in same window
        open_loads = await db.brokerage_loads.count_documents(
            {"created_at": {"$gte": cutoff.isoformat()}})
        denom = max(open_loads + len(booked), 1)
        fill_rate = (len(booked) / denom) * 100

        # On-time % from delivered loads
        on_time_count = 0
        late_count = 0
        for b in delivered:
            promised = _safe_dt(b.get("promised_delivery_at") or b.get("scheduled_delivery_at"))
            actual = _safe_dt(b.get("delivered_at") or b.get("pod_uploaded_at"))
            if promised and actual:
                if actual <= promised + timedelta(hours=1):  # 1-hour grace
                    on_time_count += 1
                else:
                    late_count += 1
        otp_total = on_time_count + late_count
        on_time_pct = (on_time_count / otp_total * 100) if otp_total else 100.0

        # ---------------- LANE BREAKDOWN ----------------
        lanes: Dict[str, Dict[str, float]] = defaultdict(
            lambda: {"loads": 0.0, "miles": 0.0, "revenue": 0.0,
                     "carrier_cost": 0.0, "on_time": 0.0, "late": 0.0})
        for b in recent:
            key = _lane_key(b.get("origin"), b.get("destination"))
            agg = lanes[key]
            agg["loads"] += 1
            agg["miles"] += float(b.get("miles") or 0)
            agg["revenue"] += float(b.get("customer_rate_usd") or b.get("rate_usd") or 0)
            agg["carrier_cost"] += float(b.get("carrier_rate_usd") or 0)
            if b.get("status") == "delivered":
                promised = _safe_dt(b.get("promised_delivery_at"))
                actual = _safe_dt(b.get("delivered_at"))
                if promised and actual:
                    if actual <= promised + timedelta(hours=1):
                        agg["on_time"] += 1
                    else:
                        agg["late"] += 1
        lane_rows: List[Dict[str, Any]] = []
        for key, agg in lanes.items():
            cpm = (agg["carrier_cost"] / agg["miles"]) if agg["miles"] else 0.0
            rpm = (agg["revenue"] / agg["miles"]) if agg["miles"] else 0.0
            margin = agg["revenue"] - agg["carrier_cost"]
            margin_pct = (margin / agg["revenue"] * 100) if agg["revenue"] else 0.0
            otp_total_l = agg["on_time"] + agg["late"]
            otp_pct = (agg["on_time"] / otp_total_l * 100) if otp_total_l else None
            lane_rows.append({
                "lane": key, "loads": int(agg["loads"]),
                "miles": round(agg["miles"]),
                "revenue_usd": round(agg["revenue"], 2),
                "carrier_cost_usd": round(agg["carrier_cost"], 2),
                "margin_usd": round(margin, 2),
                "margin_pct": round(margin_pct, 1),
                "cost_per_mile": round(cpm, 2),
                "revenue_per_mile": round(rpm, 2),
                "on_time_pct": round(otp_pct, 1) if otp_pct is not None else None,
            })
        lane_rows.sort(key=lambda r: r["loads"], reverse=True)

        # ---------------- DAILY MARGIN TREND ----------------
        daily_map: Dict[str, Dict[str, float]] = defaultdict(
            lambda: {"loads": 0.0, "revenue": 0.0, "carrier_cost": 0.0})
        for b in recent:
            dt = _safe_dt(b.get("created_at") or b.get("booked_at"))
            if not dt:
                continue
            day = dt.date().isoformat()
            agg = daily_map[day]
            agg["loads"] += 1
            agg["revenue"] += float(b.get("customer_rate_usd") or b.get("forecast_rate_usd")
                                    or b.get("rate_usd") or 0)
            agg["carrier_cost"] += float(b.get("carrier_rate_usd")
                                         or b.get("forecast_carrier_pay_usd") or 0)
        daily_rows: List[Dict[str, Any]] = []
        day_cursor = cutoff.date()
        end_day = datetime.now(timezone.utc).date()
        while day_cursor <= end_day:
            key = day_cursor.isoformat()
            agg = daily_map.get(key, {"loads": 0, "revenue": 0.0, "carrier_cost": 0.0})
            margin = agg["revenue"] - agg["carrier_cost"]
            daily_rows.append({
                "date": key, "loads": int(agg["loads"]),
                "revenue_usd": round(agg["revenue"], 2),
                "margin_usd": round(margin, 2),
                "margin_pct": round(margin / agg["revenue"] * 100, 1) if agg["revenue"] else 0.0,
            })
            day_cursor += timedelta(days=1)

        # ---------------- CARRIER SCORECARD ----------------
        cmap: Dict[str, Dict[str, float]] = defaultdict(
            lambda: {"loads": 0.0, "revenue": 0.0, "carrier_cost": 0.0,
                     "on_time": 0.0, "late": 0.0, "miles": 0.0})
        for b in recent:
            mc = b.get("carrier_mc") or b.get("carrier_id") or "Unassigned"
            agg = cmap[mc]
            agg["loads"] += 1
            agg["miles"] += float(b.get("miles") or 0)
            agg["revenue"] += float(b.get("customer_rate_usd") or b.get("rate_usd") or 0)
            agg["carrier_cost"] += float(b.get("carrier_rate_usd") or 0)
            if b.get("status") == "delivered":
                promised = _safe_dt(b.get("promised_delivery_at"))
                actual = _safe_dt(b.get("delivered_at"))
                if promised and actual:
                    if actual <= promised + timedelta(hours=1):
                        agg["on_time"] += 1
                    else:
                        agg["late"] += 1
        carriers = await db.carriers.find({}, {"_id": 0}).to_list(500)
        cname = {(c.get("mc_number") or c.get("dot_number")): c.get("name") for c in carriers}
        for c in await db.dispatch_carriers.find({}, {"_id": 0}).to_list(500):
            key = c.get("mc_number") or c.get("carrier_id") or c.get("id")
            if key and key not in cname:
                cname[key] = c.get("name") or c.get("carrier_name")
        booked_names = {}
        for b in recent:
            key = b.get("carrier_mc") or b.get("carrier_id") or "Unassigned"
            nm = b.get("carrier_name") or b.get("carrier")
            if nm and key not in booked_names:
                booked_names[key] = nm
        carrier_rows: List[Dict[str, Any]] = []
        for mc, agg in cmap.items():
            otp_total_c = agg["on_time"] + agg["late"]
            otp_pct = (agg["on_time"] / otp_total_c * 100) if otp_total_c else None
            margin = agg["revenue"] - agg["carrier_cost"]
            carrier_rows.append({
                "carrier_mc": mc,
                "carrier_name": cname.get(mc) or booked_names.get(mc) or mc,
                "loads": int(agg["loads"]),
                "miles": round(agg["miles"]),
                "carrier_cost_usd": round(agg["carrier_cost"], 2),
                "margin_usd": round(margin, 2),
                "avg_cost_per_mile": round(agg["carrier_cost"] / agg["miles"], 2) if agg["miles"] else 0.0,
                "on_time_pct": round(otp_pct, 1) if otp_pct is not None else None,
            })
        carrier_rows.sort(key=lambda r: r["loads"], reverse=True)

        return {
            "window_days": window_days,
            "headline": {
                "total_loads": total_loads,
                "delivered_loads": len(delivered),
                "revenue_usd": round(revenue, 2),
                "carrier_cost_usd": round(carrier_cost, 2),
                "gross_margin_usd": round(gross_margin, 2),
                "gross_margin_pct": round(gross_margin_pct, 1),
                "total_miles": round(total_miles),
                "cost_per_mile": round(cost_per_mile, 2),
                "revenue_per_mile": round(revenue_per_mile, 2),
                "fill_rate_pct": round(fill_rate, 1),
                "on_time_pct": round(on_time_pct, 1),
                "open_loads_available": open_loads,
            },
            "lanes": lane_rows[:25],
            "carriers": carrier_rows[:25],
            "daily": daily_rows,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    @router.get("/ops-kpis/shipper-report/{shipper_name}")
    async def shipper_report(shipper_name: str, window_days: int = 7,
                              _: Any = user_dep) -> Dict[str, Any]:
        """Shipper-scoped weekly report — same KPIs filtered to one customer."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
        bookings = await db.brokerage_bookings.find(
            {"customer_name": {"$regex": f"^{shipper_name}$", "$options": "i"}},
            {"_id": 0}).to_list(1000)
        recent = [b for b in bookings
                   if _safe_dt(b.get("created_at") or b.get("booked_at"))
                   and _safe_dt(b.get("created_at") or b.get("booked_at")) >= cutoff]
        # Mini KPI
        revenue = sum(float(b.get("customer_rate_usd") or b.get("rate_usd") or 0) for b in recent)
        miles = sum(float(b.get("miles") or 0) for b in recent)
        carrier_cost = sum(float(b.get("carrier_rate_usd") or 0) for b in recent)
        delivered = [b for b in recent if b.get("status") == "delivered"]
        return {
            "shipper": shipper_name,
            "window_days": window_days,
            "loads_total": len(recent),
            "loads_delivered": len(delivered),
            "revenue_usd": round(revenue, 2),
            "miles": round(miles),
            "carrier_cost_usd": round(carrier_cost, 2),
            "avg_cost_per_mile": round(carrier_cost / miles, 2) if miles else 0.0,
            "avg_rate_per_load": round(revenue / max(len(recent), 1), 2),
            "loads": recent[:50],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    api_router.include_router(router)
