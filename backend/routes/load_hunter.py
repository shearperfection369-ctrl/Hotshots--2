"""routes.load_hunter — AI Load Hunter: autonomous load selection engine.

Most brokers work load boards reactively. The Hunter scans every configured
board in one pass, scores each load against a configurable weighted profile
(margin %, shipper reliability, lane profitability, fuel-corridor economics,
detention risk, driver/carrier match), auto-rejects high-risk shippers unless
margin justifies the override, pre-matches the best carrier from the dispatch
roster, and surfaces "winners" for one-click booking — or books them
autonomously under an operator-set dollar cap.

Compliance guardrail: scoring uses BUSINESS METRICS ONLY (payment history,
service performance, lane economics). No protected characteristics are ever
ingested or scored. Every decision is written to an audit trail.

Endpoints — /api/load-hunter/*
"""
from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger("orisei.load_hunter")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Weight presets — each sums to 1.0. "The secret sauce."
# ---------------------------------------------------------------------------
WEIGHT_PRESETS: Dict[str, Dict[str, float]] = {
    "balanced": {
        "margin_pct": 0.25, "shipper_reliability": 0.15, "lane_profitability": 0.15,
        "fuel_economics": 0.15, "detention_risk": 0.10, "driver_match": 0.20,
    },
    "high_margin": {
        "margin_pct": 0.40, "shipper_reliability": 0.15, "lane_profitability": 0.15,
        "fuel_economics": 0.10, "detention_risk": 0.10, "driver_match": 0.10,
    },
    "high_volume": {
        "margin_pct": 0.10, "shipper_reliability": 0.20, "lane_profitability": 0.20,
        "fuel_economics": 0.15, "detention_risk": 0.10, "driver_match": 0.25,
    },
}

PRESET_DESCRIPTIONS = {
    "balanced":    "Even blend — steady margins with consistent throughput. Default mode.",
    "high_margin": "Cash-flow builder — margin % dominates. Use when you're flush and selective.",
    "high_volume": "Scaling mode — throughput and driver utilization dominate. Use when growing the book.",
}

DEFAULT_CONFIG: Dict[str, Any] = {
    "mode": "balanced",
    "custom_weights": WEIGHT_PRESETS["balanced"],
    "min_score": 70,
    "scan_interval_sec": 45,
    "auto_book": {"enabled": False, "max_rate_usd": 2500.0, "min_score": 85, "max_per_day": 10},
    "risk": {"min_payment_score": 60, "override_margin_pct": 22.0},
    "alignment": {
        "weekly_volume_target": 20,        # anti cherry-picking floor
        "min_avg_margin_pct": 12.0,        # anti race-to-the-bottom floor
        "max_shipper_share_pct": 30.0,     # concentration guardrail
        "max_carrier_share_pct": 35.0,     # anti carrier-starvation guardrail
        "max_risk_override_share_pct": 15.0,
        "min_confidence_autobook": 70,     # Layer-3 gate: no low-confidence auto-books
    },
}

FUEL_COST_PER_MILE = {"Van": 0.58, "Reefer": 0.68, "Flatbed": 0.62, "Step Deck": 0.62, "Power Only": 0.52}
RPM_BENCHMARK = {"Van": 2.20, "Reefer": 2.65, "Flatbed": 2.50, "Step Deck": 2.55, "Power Only": 1.95}

# Seed registry — business-metric risk profiles for the shipper base.
RISK_SEED: List[Dict[str, Any]] = [
    {"shipper": "Walmart DC",  "payment_score": 92, "avg_days_to_pay": 32, "dispute_count": 1, "detention_incidents_90d": 4, "credit_flag": False, "blacklisted": False, "notes": "A credit. Slow docks at regional DCs — pad appointment windows."},
    {"shipper": "Target DC",   "payment_score": 90, "avg_days_to_pay": 35, "dispute_count": 0, "detention_incidents_90d": 2, "credit_flag": False, "blacklisted": False, "notes": "A credit, clean history."},
    {"shipper": "Amazon FBA",  "payment_score": 74, "avg_days_to_pay": 44, "dispute_count": 5, "detention_incidents_90d": 9, "credit_flag": False, "blacklisted": False, "notes": "Detention trap at FBA inbound — appointment discipline required."},
    {"shipper": "Costco DC",   "payment_score": 93, "avg_days_to_pay": 28, "dispute_count": 0, "detention_incidents_90d": 1, "credit_flag": False, "blacklisted": False, "notes": "Fast pay, well-run docks."},
    {"shipper": "Home Depot",  "payment_score": 85, "avg_days_to_pay": 38, "dispute_count": 2, "detention_incidents_90d": 3, "credit_flag": False, "blacklisted": False, "notes": ""},
    {"shipper": "Lowe's RDC",  "payment_score": 83, "avg_days_to_pay": 40, "dispute_count": 2, "detention_incidents_90d": 5, "credit_flag": False, "blacklisted": False, "notes": "RDC lumper fees — verify in rate con."},
    {"shipper": "Pepsi",       "payment_score": 88, "avg_days_to_pay": 34, "dispute_count": 1, "detention_incidents_90d": 2, "credit_flag": False, "blacklisted": False, "notes": ""},
    {"shipper": "Kraft Heinz", "payment_score": 55, "avg_days_to_pay": 61, "dispute_count": 7, "detention_incidents_90d": 8, "credit_flag": True, "blacklisted": False, "notes": "61-day average pay + open disputes. Only take at strong margin."},
]

COMPLIANCE_POLICY = {
    "statement": (
        "The AI Load Hunter scores loads and carriers using business metrics only: "
        "posted rate, forecast margin, shipper payment history, dispute and detention "
        "records, lane economics, fuel-corridor cost, equipment fit, service-area fit, "
        "insurance coverage, and historical service performance (on-time %, damage rate, "
        "acceptance rate). It does not ingest, store, or score any protected "
        "characteristic (race, color, religion, sex, national origin, age, disability, "
        "or any other protected class) of any shipper contact, carrier, or driver."
    ),
    "metrics_used": [
        "margin_pct / margin_usd", "rate_per_mile vs lane benchmark",
        "shipper payment_score / avg_days_to_pay / dispute_count",
        "detention_incidents_90d", "fuel cost per mile by equipment",
        "carrier equipment fit / service area / insurance coverage",
        "carrier on_time_pct / damage_rate_pct / acceptance history",
    ],
    "audit": "Every surface / reject / auto-book decision is written to the hunter audit trail with the full score breakdown.",
}


class ConfigIn(BaseModel):
    mode: Optional[str] = Field(None, pattern="^(balanced|high_margin|high_volume|custom)$")
    custom_weights: Optional[Dict[str, float]] = None
    min_score: Optional[int] = Field(None, ge=0, le=100)
    scan_interval_sec: Optional[int] = Field(None, ge=15, le=600)
    auto_book_enabled: Optional[bool] = None
    auto_book_max_rate_usd: Optional[float] = Field(None, ge=0)
    auto_book_min_score: Optional[int] = Field(None, ge=0, le=100)
    auto_book_max_per_day: Optional[int] = Field(None, ge=0, le=100)
    risk_min_payment_score: Optional[int] = Field(None, ge=0, le=100)
    risk_override_margin_pct: Optional[float] = Field(None, ge=0, le=100)


class AlignmentIn(BaseModel):
    weekly_volume_target: Optional[int] = Field(None, ge=1, le=500)
    min_avg_margin_pct: Optional[float] = Field(None, ge=0, le=50)
    max_shipper_share_pct: Optional[float] = Field(None, ge=5, le=100)
    max_carrier_share_pct: Optional[float] = Field(None, ge=5, le=100)
    max_risk_override_share_pct: Optional[float] = Field(None, ge=0, le=100)
    min_confidence_autobook: Optional[int] = Field(None, ge=0, le=100)


def _reasoning_trace(comps: Dict[str, float], weights: Dict[str, float]) -> Dict[str, Any]:
    """Layer 2: inspectable 'why' — factor contributions sorted, top reason."""
    contribs = sorted(
        ({"factor": k, "score": comps[k], "weight": round(weights.get(k, 0), 3),
          "contribution": round(comps[k] * weights.get(k, 0), 1)} for k in comps),
        key=lambda x: -x["contribution"])
    top = contribs[0]
    weak = min(contribs, key=lambda x: x["score"])
    return {
        "contributions": contribs,
        "top_reason": f"Driven by {top['factor'].replace('_', ' ')} ({top['score']:.0f}/100 × w{top['weight']})",
        "weakest_signal": f"Weakest: {weak['factor'].replace('_', ' ')} at {weak['score']:.0f}/100",
    }


def _confidence(load: Dict[str, Any], risk: Optional[Dict[str, Any]],
                lane_known: bool, carrier_qualified: bool, override: bool) -> Dict[str, Any]:
    """Data-completeness confidence: the agent must know less ≠ act more."""
    c, notes = 100, []
    if not risk:
        c -= 20; notes.append("shipper not in risk registry (-20)")
    if not lane_known:
        c -= 10; notes.append("no lane history — RPM benchmark used (-10)")
    if not carrier_qualified:
        c -= 40; notes.append("no qualified carrier on roster (-40)")
    if override:
        c -= 25; notes.append("risk override in play (-25)")
    return {"confidence": max(0, c), "notes": notes}


class RiskIn(BaseModel):
    shipper: str = Field(..., max_length=120)
    payment_score: int = Field(..., ge=0, le=100)
    avg_days_to_pay: Optional[int] = Field(None, ge=0)
    dispute_count: int = 0
    detention_incidents_90d: int = 0
    credit_flag: bool = False
    blacklisted: bool = False
    notes: Optional[str] = Field(None, max_length=500)


def _weights_for(cfg: Dict[str, Any]) -> Dict[str, float]:
    mode = cfg.get("mode", "balanced")
    if mode == "custom":
        w = cfg.get("custom_weights") or WEIGHT_PRESETS["balanced"]
    else:
        w = WEIGHT_PRESETS.get(mode, WEIGHT_PRESETS["balanced"])
    total = sum(w.values()) or 1.0
    return {k: v / total for k, v in w.items()}


def _component_scores(load: Dict[str, Any], risk: Optional[Dict[str, Any]],
                      lane_hist: Dict[str, float],
                      best_carrier_score: int) -> Dict[str, float]:
    """Each component normalized 0..100."""
    eq = load.get("equipment") or "Van"
    rpm = float(load.get("rate_per_mile") or load.get("rpm") or 0)
    margin_pct = float(load.get("margin_pct") or 0)

    # Margin: 25%+ margin = 100
    c_margin = min(100.0, margin_pct / 25.0 * 100.0)

    # Shipper reliability: registry payment score; unknown shippers get 65
    c_shipper = float(risk["payment_score"]) if risk else 65.0

    # Lane profitability: historical avg margin% on this state-pair, else RPM vs benchmark
    ost = (load.get("origin") or "")[-2:].upper()
    dst = (load.get("destination") or "")[-2:].upper()
    hist = lane_hist.get(f"{ost}-{dst}")
    if hist is not None:
        c_lane = min(100.0, hist / 22.0 * 100.0)
    else:
        bench = RPM_BENCHMARK.get(eq, 2.2)
        c_lane = min(100.0, (rpm / bench) * 70.0) if rpm else 50.0

    # Fuel-corridor economics: net RPM after fuel
    fuel = FUEL_COST_PER_MILE.get(eq, 0.58)
    c_fuel = min(100.0, max(0.0, (rpm - fuel) / max(rpm, 0.01) * 135.0)) if rpm else 40.0

    # Detention risk (higher = safer)
    det = int(risk["detention_incidents_90d"]) if risk else 3
    c_det = max(0.0, 100.0 - det * 9.0)

    # Driver/carrier match: best qualified carrier score from the dispatch roster
    c_driver = float(best_carrier_score)

    return {
        "margin_pct": round(c_margin, 1),
        "shipper_reliability": round(c_shipper, 1),
        "lane_profitability": round(c_lane, 1),
        "fuel_economics": round(c_fuel, 1),
        "detention_risk": round(c_det, 1),
        "driver_match": round(c_driver, 1),
    }


def _risk_gate(load: Dict[str, Any], risk: Optional[Dict[str, Any]],
               cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Returns {passed, override, reasons}."""
    if not risk:
        return {"passed": True, "override": False, "reasons": []}
    reasons: List[str] = []
    r = cfg.get("risk", DEFAULT_CONFIG["risk"])
    if risk.get("blacklisted"):
        return {"passed": False, "override": False,
                "reasons": [f"{risk['shipper']} is blacklisted"]}
    if risk.get("credit_flag"):
        reasons.append("active credit flag")
    if int(risk.get("payment_score") or 100) < int(r.get("min_payment_score", 60)):
        reasons.append(f"payment score {risk.get('payment_score')} below floor {r.get('min_payment_score')}")
    if int(risk.get("dispute_count") or 0) >= 6:
        reasons.append(f"{risk['dispute_count']} open/recent disputes")
    if not reasons:
        return {"passed": True, "override": False, "reasons": []}
    margin_pct = float(load.get("margin_pct") or 0)
    if margin_pct >= float(r.get("override_margin_pct", 22.0)):
        return {"passed": True, "override": True,
                "reasons": [f"risk override: {margin_pct:.1f}% margin ≥ {r.get('override_margin_pct')}% threshold"] + reasons}
    return {"passed": False, "override": False, "reasons": reasons}


def build_load_hunter_router(
    *, api_router: APIRouter, db,
    get_current_user: Callable, require_role: Callable,
) -> None:
    router = APIRouter(prefix="/load-hunter", tags=["load-hunter"])

    async def _config() -> Dict[str, Any]:
        row = await db.hunter_config.find_one({"_id": "default"}, {"_id": 0})
        cfg = {**DEFAULT_CONFIG, **(row or {})}
        cfg["auto_book"] = {**DEFAULT_CONFIG["auto_book"], **(cfg.get("auto_book") or {})}
        cfg["risk"] = {**DEFAULT_CONFIG["risk"], **(cfg.get("risk") or {})}
        return cfg

    async def _risk_map() -> Dict[str, Dict[str, Any]]:
        rows = await db.shipper_risk.find({}, {"_id": 0}).to_list(500)
        if not rows:
            await db.shipper_risk.insert_many([dict(x) for x in RISK_SEED])
            rows = [dict(x) for x in RISK_SEED]
        return {r["shipper"]: r for r in rows}

    async def _lane_history() -> Dict[str, float]:
        """Avg settled/forecast margin% per origin/dest state pair from real bookings."""
        rows = await db.brokerage_bookings.find(
            {}, {"_id": 0, "origin": 1, "destination": 1,
                 "forecast_rate_usd": 1, "forecast_margin_usd": 1}).to_list(2000)
        agg: Dict[str, List[float]] = {}
        for b in rows:
            rate = float(b.get("forecast_rate_usd") or 0)
            m = float(b.get("forecast_margin_usd") or 0)
            if rate <= 0:
                continue
            key = f"{(b.get('origin') or '')[-2:].upper()}-{(b.get('destination') or '')[-2:].upper()}"
            agg.setdefault(key, []).append(m / rate * 100.0)
        return {k: sum(v) / len(v) for k, v in agg.items() if v}

    async def _all_loads() -> List[Dict[str, Any]]:
        from routes.brokerage import LOAD_BOARDS, _gen_loads_for_board  # type: ignore
        out: List[Dict[str, Any]] = []
        for b in LOAD_BOARDS:
            rows = await db.brokerage_loads.find(
                {"board_id": b["id"]}, {"_id": 0}).to_list(50)
            if not rows:
                rows = _gen_loads_for_board(b["id"], count=14)
            for r in rows:
                r = dict(r)
                r["board_id"] = b["id"]
                rate = float(r.get("rate_usd") or 0)
                cpay = float(r.get("carrier_pay_usd") or 0)
                if not r.get("margin_usd") and rate and cpay:
                    r["margin_usd"] = round(rate - cpay, 2)
                if not r.get("margin_pct") and rate:
                    r["margin_pct"] = round(float(r.get("margin_usd") or 0) / rate * 100, 1)
                if not r.get("rate_per_mile"):
                    r["rate_per_mile"] = r.get("rpm")
                out.append(r)
        return out

    async def _best_carrier(load: Dict[str, Any],
                            carriers: List[Dict[str, Any]]) -> Dict[str, Any]:
        from routes.dispatch_autopilot import _score as carrier_score  # type: ignore
        best, best_res = None, {"qualified": False, "score": 0}
        for c in carriers:
            res = carrier_score(load, c)
            if res["qualified"] and res["score"] > best_res["score"]:
                best, best_res = c, res
        if not best:
            return {"carrier_name": None, "score": 0, "qualified": False}
        return {"carrier_name": best.get("legal_name") or best.get("name"),
                "carrier_mc": best.get("mc_number"),
                "carrier_id": best.get("carrier_id"), "score": best_res["score"],
                "qualified": True}

    async def _audit(action: str, load: Dict[str, Any], detail: Dict[str, Any]):
        await db.hunter_audit.insert_one({
            "id": str(uuid.uuid4()), "at": _now_iso(), "action": action,
            "load_id": load.get("load_id"), "board_id": load.get("board_id"),
            "shipper": load.get("shipper"), "lane": f"{load.get('origin')} → {load.get('destination')}",
            **detail,
        })

    async def _book_winner(winner: Dict[str, Any], user_id: str, auto: bool) -> Dict[str, Any]:
        """Create a brokerage booking + shipment row from a hunter winner."""
        load = winner["load"]
        now = _now_iso()
        booked_id = f"BK-{uuid.uuid4().hex[:10].upper()}"
        shipment_id = f"SH-{uuid.uuid4().hex[:10].upper()}"
        rate = float(load.get("rate_usd") or 0)
        cpay = float(load.get("carrier_pay_usd") or 0)
        doc = {
            "booked_id": booked_id, "load_id": load.get("load_id"),
            "board_id": load.get("board_id"),
            "carrier_name": winner.get("best_carrier", {}).get("carrier_name") or "TBD — assign carrier",
            "carrier_mc": winner.get("best_carrier", {}).get("carrier_mc"),
            "customer_name": load.get("shipper"), "customer_email": None,
            "origin": load.get("origin"), "destination": load.get("destination"),
            "miles": load.get("miles"), "equipment": load.get("equipment"),
            "forecast_rate_usd": rate, "forecast_carrier_pay_usd": cpay,
            "forecast_margin_usd": round(rate - cpay, 2),
            "settled_rate_usd": None, "settled_carrier_pay_usd": None, "settled_margin_usd": None,
            "pickup_date": load.get("pickup_date"), "delivery_date": load.get("delivery_date"),
            "status": "booked", "booked_at": now, "booked_by": user_id,
            "notes": f"{'AUTO-BOOKED' if auto else 'Booked'} by AI Load Hunter · score {winner['score']}",
            "is_sample": False, "shipment_id": shipment_id,
            "source": "ai_load_hunter", "hunter_auto": auto,
        }
        await db.brokerage_bookings.insert_one(dict(doc))

        def _split(loc: str) -> Dict[str, str]:
            if not loc or "," not in loc:
                return {"city": loc or "—", "state": "", "name": loc or "—"}
            city, _, state = loc.partition(",")
            return {"city": city.strip(), "state": state.strip()[:4], "name": loc}

        try:
            await db.shipments.insert_one({
                "shipment_id": shipment_id, "reference": load.get("load_id"),
                "booking_number": booked_id, "carrier": doc["carrier_name"],
                "carrier_mc": doc["carrier_mc"], "mode": "TL", "status": "pending",
                "origin": _split(load.get("origin") or ""),
                "destination": _split(load.get("destination") or ""),
                "current_location": _split(load.get("origin") or ""),
                "eta": load.get("delivery_date"), "pickup_date": load.get("pickup_date"),
                "delivery_date": load.get("delivery_date"),
                "weight_lbs": float(load.get("weight_lbs") or 0), "pieces": 1,
                "commodity": load.get("commodity") or load.get("equipment") or "General freight",
                "value_usd": rate, "consignee": load.get("shipper"), "supplier": load.get("shipper"),
                "customer_rate_usd": rate, "carrier_rate_usd": cpay,
                "miles": load.get("miles"), "progress": 0.0, "direction": "outbound",
                "hazmat": bool(load.get("hazmat")), "notes": doc["notes"],
                "created_at": now, "updated_at": now, "created_by": user_id,
                "is_sample": False, "_from_brokerage": True,
            })
        except Exception as e:                                     # noqa: BLE001
            logger.warning("Hunter shipment row failed for %s: %s", booked_id, e)
        return doc

    # ------------------------------------------------------------------ scan
    @router.post("/scan")
    async def scan(user=Depends(get_current_user)) -> Dict[str, Any]:
        """Full hunt cycle: fetch all boards → score → risk-filter →
        pre-match carriers → surface winners → optional auto-book."""
        t0 = time.perf_counter()
        cfg = await _config()
        weights = _weights_for(cfg)
        risk_map = await _risk_map()
        lane_hist = await _lane_history()
        carriers = await db.dispatch_carriers.find({"is_active": True}, {"_id": 0}).to_list(500)
        loads = await _all_loads()

        seen_row = await db.hunter_seen.find_one({"_id": "seen"}) or {}
        seen_ids = set(seen_row.get("ids") or [])

        winners: List[Dict[str, Any]] = []
        rejected_risk = 0
        today = datetime.now(timezone.utc).date().isoformat()
        auto_booked_today = await db.brokerage_bookings.count_documents(
            {"hunter_auto": True, "booked_at": {"$gte": today}})
        auto_booked_now: List[str] = []

        for load in loads:
            risk = risk_map.get(load.get("shipper") or "")
            gate = _risk_gate(load, risk, cfg)
            if not gate["passed"]:
                rejected_risk += 1
                await _audit("risk_reject", load, {"reasons": gate["reasons"],
                                                    "margin_pct": load.get("margin_pct")})
                continue
            best = await _best_carrier(load, carriers)
            comps = _component_scores(load, risk, lane_hist, best["score"])
            score = int(round(sum(comps[k] * weights.get(k, 0) for k in comps)))
            if score < int(cfg.get("min_score", 70)):
                continue
            ost = (load.get("origin") or "")[-2:].upper()
            dst = (load.get("destination") or "")[-2:].upper()
            conf = _confidence(load, risk, f"{ost}-{dst}" in lane_hist,
                               best["qualified"], gate["override"])
            winner = {
                "winner_id": f"HW-{uuid.uuid4().hex[:8].upper()}",
                "load_id": load.get("load_id"), "board_id": load.get("board_id"),
                "score": score, "components": comps, "weights": weights,
                "reasoning": _reasoning_trace(comps, weights),
                "confidence": conf["confidence"], "confidence_notes": conf["notes"],
                "risk_override": gate["override"], "risk_reasons": gate["reasons"],
                "best_carrier": best, "load": load,
                "is_new": load.get("load_id") not in seen_ids,
                "status": "surfaced", "surfaced_at": _now_iso(),
            }
            # Auto-book path — Layer 3 gate: score + $ cap + clean risk + confidence
            ab = cfg["auto_book"]
            align = cfg.get("alignment", DEFAULT_CONFIG["alignment"])
            if (ab.get("enabled") and score >= int(ab.get("min_score", 85))
                    and float(load.get("rate_usd") or 0) <= float(ab.get("max_rate_usd", 0))
                    and best["qualified"] and not gate["override"]
                    and conf["confidence"] >= int(align.get("min_confidence_autobook", 70))
                    and auto_booked_today + len(auto_booked_now) < int(ab.get("max_per_day", 10))):
                booking = await _book_winner(winner, getattr(user, "user_id", "hunter"), auto=True)
                winner["status"] = "auto_booked"
                winner["booked_id"] = booking["booked_id"]
                auto_booked_now.append(booking["booked_id"])
                await _audit("auto_book", load, {"score": score, "booked_id": booking["booked_id"],
                                                  "carrier": best.get("carrier_name"),
                                                  "components": comps})
            else:
                await _audit("surface", load, {"score": score, "components": comps,
                                                "risk_override": gate["override"],
                                                "carrier": best.get("carrier_name")})
            winners.append(winner)

        # Persist winners queue (replace surfaced set; keep booked/dismissed history)
        await db.hunter_winners.delete_many({"status": "surfaced"})
        if winners:
            await db.hunter_winners.insert_many([dict(w) for w in winners])
        await db.hunter_seen.update_one(
            {"_id": "seen"},
            {"$set": {"ids": list(seen_ids | {l.get("load_id") for l in loads})[-3000:],
                      "at": _now_iso()}}, upsert=True)

        elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
        summary = {
            "scanned": len(loads), "boards": len({l.get("board_id") for l in loads}),
            "winners": len(winners), "new_winners": sum(1 for w in winners if w["is_new"]),
            "risk_rejected": rejected_risk,
            "auto_booked": len(auto_booked_now), "auto_booked_ids": auto_booked_now,
            "elapsed_ms": elapsed_ms, "mode": cfg["mode"], "at": _now_iso(),
        }
        await db.hunter_scans.insert_one(dict(summary))
        summary["winners_list"] = winners
        return summary

    # ----------------------------------------------------------------- queue
    @router.get("/winners")
    async def get_winners(status: Optional[str] = None,
                          _=Depends(get_current_user)) -> Dict[str, Any]:
        q = {"status": status} if status else {"status": {"$in": ["surfaced", "auto_booked"]}}
        rows = await db.hunter_winners.find(q, {"_id": 0}).sort("score", -1).to_list(100)
        return {"items": rows, "count": len(rows)}

    @router.post("/winners/{winner_id}/book")
    async def book_winner(winner_id: str, user=Depends(get_current_user)) -> Dict[str, Any]:
        w = await db.hunter_winners.find_one({"winner_id": winner_id}, {"_id": 0})
        if not w:
            raise HTTPException(404, "Winner not found — it may have expired on rescan")
        if w.get("status") in ("booked", "auto_booked"):
            raise HTTPException(400, "Already booked")
        booking = await _book_winner(w, getattr(user, "user_id", "user"), auto=False)
        await db.hunter_winners.update_one(
            {"winner_id": winner_id},
            {"$set": {"status": "booked", "booked_id": booking["booked_id"],
                      "booked_at": _now_iso()}})
        await _audit("manual_book", w["load"], {"score": w["score"],
                                                 "booked_id": booking["booked_id"]})
        return {"ok": True, "booked_id": booking["booked_id"],
                "shipment_id": booking["shipment_id"]}

    @router.post("/winners/{winner_id}/dismiss")
    async def dismiss_winner(winner_id: str, _=Depends(get_current_user)) -> Dict[str, Any]:
        r = await db.hunter_winners.update_one(
            {"winner_id": winner_id}, {"$set": {"status": "dismissed",
                                                 "dismissed_at": _now_iso()}})
        if not r.matched_count:
            raise HTTPException(404, "Winner not found")
        return {"ok": True}

    # ---------------------------------------------------------------- config
    @router.get("/config")
    async def get_config(_=Depends(get_current_user)) -> Dict[str, Any]:
        cfg = await _config()
        return {**cfg, "presets": WEIGHT_PRESETS,
                "preset_descriptions": PRESET_DESCRIPTIONS,
                "active_weights": _weights_for(cfg)}

    @router.post("/config")
    async def set_config(payload: ConfigIn,
                         user=Depends(require_role("admin", "dispatcher"))) -> Dict[str, Any]:
        cfg = await _config()
        if payload.mode is not None:
            cfg["mode"] = payload.mode
        if payload.custom_weights is not None:
            allowed = set(WEIGHT_PRESETS["balanced"])
            cfg["custom_weights"] = {k: max(0.0, float(v))
                                     for k, v in payload.custom_weights.items() if k in allowed}
        if payload.min_score is not None:
            cfg["min_score"] = payload.min_score
        if payload.scan_interval_sec is not None:
            cfg["scan_interval_sec"] = payload.scan_interval_sec
        ab = cfg["auto_book"]
        if payload.auto_book_enabled is not None:
            ab["enabled"] = payload.auto_book_enabled
        if payload.auto_book_max_rate_usd is not None:
            ab["max_rate_usd"] = payload.auto_book_max_rate_usd
        if payload.auto_book_min_score is not None:
            ab["min_score"] = payload.auto_book_min_score
        if payload.auto_book_max_per_day is not None:
            ab["max_per_day"] = payload.auto_book_max_per_day
        rk = cfg["risk"]
        if payload.risk_min_payment_score is not None:
            rk["min_payment_score"] = payload.risk_min_payment_score
        if payload.risk_override_margin_pct is not None:
            rk["override_margin_pct"] = payload.risk_override_margin_pct
        cfg["updated_at"] = _now_iso()
        cfg["updated_by"] = getattr(user, "user_id", None)
        await db.hunter_config.update_one({"_id": "default"}, {"$set": cfg}, upsert=True)
        return {"ok": True, **cfg, "active_weights": _weights_for(cfg)}

    # ------------------------------------------------------------------ risk
    @router.get("/risk")
    async def risk_registry(_=Depends(get_current_user)) -> Dict[str, Any]:
        m = await _risk_map()
        return {"items": sorted(m.values(), key=lambda x: x["payment_score"]),
                "count": len(m)}

    @router.post("/risk")
    async def upsert_risk(payload: RiskIn,
                          user=Depends(require_role("admin", "dispatcher"))) -> Dict[str, Any]:
        doc = payload.model_dump()
        doc["updated_at"] = _now_iso()
        doc["updated_by"] = getattr(user, "user_id", None)
        await db.shipper_risk.update_one({"shipper": payload.shipper},
                                         {"$set": doc}, upsert=True)
        return {"ok": True, **doc}

    # ------------------------------------------------------------- audit etc
    @router.get("/audit")
    async def audit_trail(limit: int = 60, _=Depends(get_current_user)) -> Dict[str, Any]:
        rows = await db.hunter_audit.find({}, {"_id": 0}).sort("at", -1).to_list(min(limit, 200))
        return {"items": rows, "count": len(rows)}

    @router.get("/compliance")
    async def compliance(_=Depends(get_current_user)) -> Dict[str, Any]:
        return COMPLIANCE_POLICY

    @router.get("/stats")
    async def stats(_=Depends(get_current_user)) -> Dict[str, Any]:
        scans = await db.hunter_scans.find({}, {"_id": 0}).sort("at", -1).to_list(50)
        booked = await db.hunter_winners.count_documents({"status": {"$in": ["booked", "auto_booked"]}})
        auto = await db.brokerage_bookings.count_documents({"hunter_auto": True})
        winners = await db.hunter_winners.find(
            {"status": {"$in": ["surfaced", "auto_booked"]}},
            {"_id": 0, "load.margin_usd": 1, "score": 1}).to_list(200)
        margins = [float((w.get("load") or {}).get("margin_usd") or 0) for w in winners]
        return {
            "total_scans": await db.hunter_scans.count_documents({}),
            "last_scan": scans[0] if scans else None,
            "avg_scan_ms": round(sum(s.get("elapsed_ms", 0) for s in scans) / len(scans), 1) if scans else None,
            "winners_active": len(winners),
            "winners_booked": booked, "auto_booked_total": auto,
            "avg_winner_margin_usd": round(sum(margins) / len(margins), 2) if margins else 0,
            "pipeline_margin_usd": round(sum(margins), 2),
        }

    # -------------------------------------------------- alignment guardian
    @router.get("/alignment")
    async def alignment(_=Depends(get_current_user)) -> Dict[str, Any]:
        """Misalignment monitors over the last 7 days of hunter bookings:
        cherry-picking, carrier starvation, shipper concentration, risk drift."""
        cfg = await _config()
        a = cfg.get("alignment", DEFAULT_CONFIG["alignment"])
        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        rows = await db.brokerage_bookings.find(
            {"source": "ai_load_hunter", "booked_at": {"$gte": cutoff}},
            {"_id": 0}).to_list(1000)
        n = len(rows)
        rev = sum(float(b.get("forecast_rate_usd") or 0) for b in rows)
        margin = sum(float(b.get("forecast_margin_usd") or 0) for b in rows)
        avg_margin_pct = round(margin / rev * 100, 1) if rev else 0.0
        ship_rev: Dict[str, float] = {}
        carr_ct: Dict[str, int] = {}
        overrides = 0
        for b in rows:
            ship_rev[b.get("customer_name") or "?"] = ship_rev.get(b.get("customer_name") or "?", 0) + float(b.get("forecast_rate_usd") or 0)
            carr_ct[b.get("carrier_name") or "?"] = carr_ct.get(b.get("carrier_name") or "?", 0) + 1
            if "risk" in (b.get("notes") or "").lower() and "override" in (b.get("notes") or "").lower():
                overrides += 1
        top_ship = max(ship_rev.items(), key=lambda x: x[1]) if ship_rev else (None, 0)
        top_carr = max(carr_ct.items(), key=lambda x: x[1]) if carr_ct else (None, 0)
        ship_share = round(top_ship[1] / rev * 100, 1) if rev else 0.0
        carr_share = round(top_carr[1] / n * 100, 1) if n else 0.0
        override_share = round(overrides / n * 100, 1) if n else 0.0

        alerts: List[Dict[str, Any]] = []
        if n < int(a["weekly_volume_target"]) and avg_margin_pct > float(a["min_avg_margin_pct"]) + 6:
            alerts.append({"type": "cherry_picking", "severity": "warn",
                           "message": f"Volume {n}/{a['weekly_volume_target']} this week while avg margin runs hot ({avg_margin_pct}%) — the agent may be cherry-picking margin and starving throughput.",
                           "recommendation": "Switch to High-Volume mode or lower min_score to protect carrier relationships and weekly cash."})
        if rev and avg_margin_pct < float(a["min_avg_margin_pct"]):
            alerts.append({"type": "margin_erosion", "severity": "error",
                           "message": f"Avg booked margin {avg_margin_pct}% is below the {a['min_avg_margin_pct']}% floor — the agent is chasing volume at the expense of profit.",
                           "recommendation": "Switch to High-Margin mode or raise min_score."})
        if ship_share > float(a["max_shipper_share_pct"]):
            alerts.append({"type": "shipper_concentration", "severity": "warn",
                           "message": f"{top_ship[0]} is {ship_share}% of booked revenue (cap {a['max_shipper_share_pct']}%) — one dispute or credit hold now threatens the whole book.",
                           "recommendation": "Diversify: temporarily deprioritize this shipper's loads."})
        if n >= 5 and carr_share > float(a["max_carrier_share_pct"]):
            alerts.append({"type": "carrier_starvation", "severity": "warn",
                           "message": f"{top_carr[0]} is taking {carr_share}% of loads (cap {a['max_carrier_share_pct']}%) — the rest of the roster is being starved and will stop answering.",
                           "recommendation": "Spread freight: the driver_match component will re-rank once relationship scores update via the feedback loop."})
        if override_share > float(a["max_risk_override_share_pct"]):
            alerts.append({"type": "risk_drift", "severity": "error",
                           "message": f"{override_share}% of bookings used a risk override (cap {a['max_risk_override_share_pct']}%) — margin targets are pulling the agent toward sketchy shippers.",
                           "recommendation": "Raise override_margin_pct or lower margin weight — chargebacks eat those margins."})
        return {
            "layers": [
                {"layer": 1, "name": "Perception", "status": "active", "detail": "Boards normalized into one schema · component scores stored with every decision."},
                {"layer": 2, "name": "Reasoning", "status": "active", "detail": "Weighted preference function · full reasoning trace + confidence on every winner."},
                {"layer": 3, "name": "Action", "status": "active", "detail": f"Human-in-the-loop queue · auto-book gated by score, $ cap, clean risk AND confidence ≥ {a['min_confidence_autobook']}."},
                {"layer": 4, "name": "Feedback", "status": "active", "detail": "Outcome loop: actual vs forecast margin, payment behavior, carrier performance → human-approved weight retraining."},
            ],
            "window_days": 7, "bookings": n, "revenue_usd": round(rev, 2),
            "avg_margin_pct": avg_margin_pct,
            "top_shipper": {"name": top_ship[0], "share_pct": ship_share},
            "top_carrier": {"name": top_carr[0], "share_pct": carr_share},
            "risk_override_share_pct": override_share,
            "targets": a, "alerts": alerts, "aligned": len(alerts) == 0,
        }

    @router.post("/alignment/config")
    async def set_alignment(payload: AlignmentIn,
                            user=Depends(require_role("admin", "dispatcher"))) -> Dict[str, Any]:
        cfg = await _config()
        a = cfg.get("alignment", dict(DEFAULT_CONFIG["alignment"]))
        for k, v in payload.model_dump().items():
            if v is not None:
                a[k] = v
        await db.hunter_config.update_one({"_id": "default"},
                                          {"$set": {"alignment": a, "updated_at": _now_iso()}},
                                          upsert=True)
        return {"ok": True, "alignment": a}

    @router.post("/feedback/run")
    async def feedback_run(user=Depends(require_role("admin", "dispatcher"))) -> Dict[str, Any]:
        """Layer 4: learn from outcomes. Compares forecast vs settled margin,
        reads invoice payment behavior, scores carrier performance — then
        proposes (never silently applies) weight adjustments."""
        bookings = await db.brokerage_bookings.find(
            {"status": {"$in": ["delivered", "settled"]}}, {"_id": 0}).to_list(2000)
        inv_status: Dict[str, str] = {}
        async for inv in db.brokerage_invoices.find({}, {"_id": 0, "customer_name": 1, "status": 1, "due_at": 1, "paid_at": 1}):
            cust = inv.get("customer_name") or "?"
            late = (inv.get("status") != "paid" and inv.get("due_at") and inv["due_at"] < _now_iso())
            if late:
                inv_status[cust] = "late"
            elif cust not in inv_status:
                inv_status[cust] = inv.get("status") or "issued"
        carr: Dict[str, Dict[str, Any]] = {}
        variances: List[float] = []
        late_shippers: set = set()
        for b in bookings:
            f = float(b.get("forecast_margin_usd") or 0)
            s = b.get("settled_margin_usd")
            if s is not None and f:
                variances.append((float(s) - f) / abs(f) * 100)
            cust = b.get("customer_name") or "?"
            if inv_status.get(cust) == "late":
                late_shippers.add(cust)
            name = b.get("carrier_name") or "?"
            c = carr.setdefault(name, {"carrier_name": name, "loads": 0, "margin_usd": 0.0})
            c["loads"] += 1
            c["margin_usd"] += float(b.get("settled_margin_usd") or b.get("forecast_margin_usd") or 0)
        for name, c in carr.items():
            score = min(100, 55 + c["loads"] * 5 + (10 if c["margin_usd"] > 0 else -15))
            c["relationship_score"] = score
            await db.carrier_relationship.update_one(
                {"carrier_name": name},
                {"$set": {**c, "updated_at": _now_iso()}}, upsert=True)
        avg_var = round(sum(variances) / len(variances), 1) if variances else None
        suggestions: List[Dict[str, Any]] = []
        cfg = await _config()
        w = _weights_for(cfg)
        if late_shippers:
            suggestions.append({
                "id": "up_shipper_reliability",
                "reason": f"{len(late_shippers)} shipper(s) paying late ({', '.join(list(late_shippers)[:3])}) — the agent under-weights payment behavior.",
                "change": "shipper_reliability weight +0.05 (margin −0.05)",
                "weights": {**w, "shipper_reliability": round(w.get("shipper_reliability", .15) + .05, 3),
                            "margin_pct": round(max(0.05, w.get("margin_pct", .25) - .05), 3)}})
        if avg_var is not None and avg_var < -8:
            suggestions.append({
                "id": "up_detention_risk",
                "reason": f"Settled margins run {avg_var}% below forecast — hidden costs (detention, lumpers) are eating the plan.",
                "change": "detention_risk weight +0.05 (fuel −0.05)",
                "weights": {**w, "detention_risk": round(w.get("detention_risk", .10) + .05, 3),
                            "fuel_economics": round(max(0.05, w.get("fuel_economics", .15) - .05), 3)}})
        result = {"ok": True, "bookings_analyzed": len(bookings),
                  "carriers_scored": len(carr), "late_paying_shippers": sorted(late_shippers),
                  "avg_margin_variance_pct": avg_var, "suggestions": suggestions,
                  "note": "Suggestions are NEVER auto-applied — approve one to retrain the weights.",
                  "ran_at": _now_iso(), "ran_by": getattr(user, "user_id", None)}
        await db.hunter_feedback_runs.insert_one(dict(result))
        return result

    @router.post("/feedback/apply")
    async def feedback_apply(payload: Dict[str, Any],
                             user=Depends(require_role("admin", "dispatcher"))) -> Dict[str, Any]:
        """Human approves a suggestion → weights become the new custom profile."""
        weights = payload.get("weights") or {}
        allowed = set(WEIGHT_PRESETS["balanced"])
        clean = {k: max(0.0, float(v)) for k, v in weights.items() if k in allowed}
        if len(clean) != len(allowed):
            raise HTTPException(400, "Suggestion must include all six weight components")
        await db.hunter_config.update_one(
            {"_id": "default"},
            {"$set": {"mode": "custom", "custom_weights": clean,
                      "updated_at": _now_iso(), "updated_by": getattr(user, "user_id", None)}},
            upsert=True)
        await db.hunter_audit.insert_one({
            "id": str(uuid.uuid4()), "at": _now_iso(), "action": "weights_retrained",
            "load_id": None, "shipper": None, "lane": None,
            "weights": clean, "approved_by": getattr(user, "user_id", None)})
        return {"ok": True, "mode": "custom", "custom_weights": clean}

    api_router.include_router(router)
    logger.info("AI Load Hunter router registered (/api/load-hunter)")
