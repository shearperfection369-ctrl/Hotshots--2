"""routes.ops_truth — real operational data, no vanity metrics.

Which loads actually book, which carriers convert, what margins hold
(forecast vs settled) — plus the shipper↔carrier match playbook that
gets smarter with every booked load.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List

from fastapi import APIRouter, Depends

DONE = ("delivered", "invoiced", "factored", "paid", "completed")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def build_ops_truth_router(*, db, get_current_user: Callable) -> APIRouter:
    router = APIRouter(prefix="/ops-truth", tags=["ops-truth"])

    @router.get("/summary")
    async def summary(window_days: int = 30, _=Depends(get_current_user)) -> Dict[str, Any]:
        since = (_now() - timedelta(days=window_days)).isoformat()

        outcomes = await db.hunter_bid_outcomes.find(
            {"at": {"$gte": since}}, {"_id": 0, "won": 1, "booked_id": 1}).to_list(4000)
        bids = len(outcomes)
        wins = sum(1 for o in outcomes if o.get("won"))
        auto_booked = sum(1 for o in outcomes if o.get("booked_id"))

        cycles = await db.fs_cycles.find({"at": {"$gte": since}}, {"_id": 0, "scanned": 1}).to_list(5000)
        scanned = sum(int(c.get("scanned") or 0) for c in cycles)

        bookings = await db.brokerage_bookings.find(
            {"booked_at": {"$gte": since}}, {"_id": 0}).to_list(3000)
        by_source: Dict[str, int] = defaultdict(int)
        for b in bookings:
            by_source[b.get("source") or "manual"] += 1

        # margins hold: forecast vs settled where settled exists
        settled = [b for b in bookings if b.get("settled_margin_usd") is not None]
        f_sum = sum(float(b.get("forecast_margin_usd") or 0) for b in settled)
        s_sum = sum(float(b.get("settled_margin_usd") or 0) for b in settled)
        hold_pct = round(s_sum / f_sum * 100, 1) if f_sum else None
        drifts = sorted(
            ({"booked_id": b.get("booked_id"), "lane": f"{b.get('origin')} → {b.get('destination')}",
              "carrier": b.get("carrier_name"),
              "forecast_usd": b.get("forecast_margin_usd"),
              "settled_usd": b.get("settled_margin_usd"),
              "drift_usd": round(float(b.get("settled_margin_usd") or 0)
                                 - float(b.get("forecast_margin_usd") or 0), 2)}
             for b in settled),
            key=lambda d: d["drift_usd"])[:6]

        # carrier conversion: assigned → completed, and margin held
        cmap: Dict[str, Dict[str, Any]] = {}
        for b in bookings:
            name = b.get("carrier_name") or "TBD"
            if name.startswith("TBD"):
                continue
            c = cmap.setdefault(name, {"carrier": name, "assigned": 0, "completed": 0,
                                       "forecast_margin": 0.0, "settled_margin": 0.0,
                                       "settled_n": 0})
            c["assigned"] += 1
            if (b.get("status") or "") in DONE:
                c["completed"] += 1
            c["forecast_margin"] += float(b.get("forecast_margin_usd") or 0)
            if b.get("settled_margin_usd") is not None:
                c["settled_margin"] += float(b.get("settled_margin_usd") or 0)
                c["settled_n"] += 1
        carriers = []
        for c in cmap.values():
            c["conversion_pct"] = round(c["completed"] / c["assigned"] * 100, 1) if c["assigned"] else 0
            c["margin_hold_pct"] = (round(c["settled_margin"] /
                                          max(c["forecast_margin"], 1) * 100, 1)
                                    if c["settled_n"] else None)
            c["forecast_margin"] = round(c["forecast_margin"], 2)
            c["settled_margin"] = round(c["settled_margin"], 2)
            carriers.append(c)
        carriers.sort(key=lambda c: -c["assigned"])

        return {
            "window_days": window_days,
            "funnel": {"scanned": scanned, "bids": bids, "wins": wins,
                       "auto_booked": auto_booked, "booked_total": len(bookings),
                       "win_rate_pct": round(wins / bids * 100, 1) if bids else 0.0,
                       "book_rate_pct": round(auto_booked / bids * 100, 1) if bids else 0.0},
            "bookings_by_source": dict(sorted(by_source.items(), key=lambda kv: -kv[1])),
            "margin_truth": {"settled_loads": len(settled),
                             "forecast_usd": round(f_sum, 2), "settled_usd": round(s_sum, 2),
                             "margin_hold_pct": hold_pct, "worst_drifts": drifts},
            "carriers": carriers[:12],
        }

    @router.get("/match-playbook")
    async def match_playbook(_=Depends(get_current_user)) -> Dict[str, Any]:
        bookings = await db.brokerage_bookings.find({}, {"_id": 0}).to_list(4000)
        pairs: Dict[tuple, Dict[str, Any]] = {}
        for b in bookings:
            shipper = b.get("customer_name") or ""
            carrier = b.get("carrier_name") or ""
            if not shipper or not carrier or carrier.startswith("TBD"):
                continue
            p = pairs.setdefault((shipper, carrier), {
                "shipper": shipper, "carrier": carrier, "loads": 0, "completed": 0,
                "revenue": 0.0, "margin": 0.0})
            p["loads"] += 1
            if (b.get("status") or "") in DONE:
                p["completed"] += 1
            rate = float(b.get("settled_rate_usd") or b.get("forecast_rate_usd") or 0)
            marg = float(b.get("settled_margin_usd") or b.get("forecast_margin_usd") or 0)
            p["revenue"] += rate
            p["margin"] += marg

        rows = []
        for p in pairs.values():
            comp = p["completed"] / p["loads"] if p["loads"] else 0
            mpct = p["margin"] / p["revenue"] * 100 if p["revenue"] else 0
            volume_bonus = min(p["loads"], 10) * 1.5
            p["completion_pct"] = round(comp * 100, 1)
            p["margin_pct"] = round(mpct, 1)
            p["match_score"] = round(min(100, comp * 45 + min(mpct, 20) / 20 * 40 + volume_bonus), 1)
            p["revenue"] = round(p["revenue"], 2)
            p["margin"] = round(p["margin"], 2)
            rows.append(p)
        rows.sort(key=lambda r: -r["match_score"])

        best_by_shipper: Dict[str, Dict[str, Any]] = {}
        for r in rows:
            if r["shipper"] not in best_by_shipper:
                best_by_shipper[r["shipper"]] = r
        recommendations = [
            {"shipper": s, "carrier": r["carrier"], "match_score": r["match_score"],
             "loads_learned_from": r["loads"], "margin_pct": r["margin_pct"],
             "note": f"Tender {s} freight to {r['carrier']} first — "
                     f"{r['completion_pct']}% completion at {r['margin_pct']}% margin over {r['loads']} loads."}
            for s, r in list(best_by_shipper.items())[:10]]

        return {"pairs_learned": len(rows), "loads_observed": sum(r["loads"] for r in rows),
                "pairs": rows[:25], "recommendations": recommendations,
                "learning_note": "Scores recompute from every settled load — the playbook sharpens automatically as volume grows."}

    return router
