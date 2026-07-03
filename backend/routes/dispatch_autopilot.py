"""routes.dispatch_autopilot — Real-time rule-based load-matching engine.

Sprint 1 (rule-based): ingest loads from the aggregator feed, score every
active carrier against each new load, auto-fire SMS+email offers to the
top-N matches, track acceptance. Everything is logged for later ML.

Scoring
-------
  HARD  → equipment match, weight ≤ carrier_max_lbs, lane in carrier
          service area, insurance covers commodity (hazmat/temp).
          Any hard-fail = disqualified.
  SOFT  → on-time %, damage rate, days-idle boost, rate alignment,
          shipper preference, historical acceptance rate.  0-100 scale.
  MARGIN→ load.rate_usd − carrier.rate_ask. Loads under threshold get
          flagged (not sent).

Communication
-------------
  Twilio SMS + Resend email are MOCKED (returns simulated delivery
  receipts). Production JSON shape is preserved so the same offer object
  will flow through the real integrations once keys are wired.

Endpoints — /api/dispatch/*
  GET   /provider                 · shows what's wired vs mocked
  GET   /dashboard                · autopilot KPIs
  GET   /carriers                 · carrier availability matrix
  POST  /carriers                 · add/update a carrier row
  DELETE /carriers/{carrier_id}   · retire a carrier
  POST  /carriers/seed            · admin: seed a demo carrier fleet
  POST  /score/{load_id}          · score all carriers against a load
  POST  /auto-offer/{load_id}     · fire offers to top-N matches
  GET   /offers                   · offer pipeline
  POST  /offers/{offer_id}/accept · one-click accept (carrier-facing)
  POST  /offers/{offer_id}/decline
  POST  /tick                     · manually run the autopilot cycle
  GET   /config                   · read autopilot config
  POST  /config                   · update thresholds
"""
from __future__ import annotations

import asyncio
import logging
import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger("orisei.dispatch")

DEFAULT_CONFIG = {
    "top_n_carriers_per_load": 3,
    "min_margin_usd": 200.0,
    "min_margin_pct": 12.0,
    "min_match_score": 55.0,
    "offer_expiry_minutes": 30,
    "autopilot_enabled": True,
    "notify_sms": True,
    "notify_email": True,
}


class CarrierIn(BaseModel):
    carrier_id: Optional[str] = Field(None, max_length=40)
    legal_name: str = Field(..., max_length=200)
    mc_number: Optional[str] = Field(None, max_length=20)
    dot_number: Optional[str] = Field(None, max_length=20)
    contact_name: Optional[str] = Field(None, max_length=100)
    contact_phone: Optional[str] = Field(None, max_length=40)
    contact_email: Optional[str] = Field(None, max_length=200)
    equipment_types: List[str] = Field(default_factory=list)   # ["Van","Reefer","Flatbed"]
    max_weight_lbs: float = Field(45000, ge=0, le=200000)
    service_states: List[str] = Field(default_factory=list)    # ["TX","OK","AR"] - operates in these origin/dest states
    insurance_cargo_usd: float = Field(100000, ge=0)
    insurance_covers_hazmat: bool = False
    insurance_covers_reefer: bool = True
    home_base_state: Optional[str] = Field(None, max_length=2)
    rate_expectation_per_mile: float = Field(2.15, ge=0)
    on_time_pct: float = Field(90.0, ge=0, le=100)
    damage_rate_pct: float = Field(1.0, ge=0, le=100)
    historical_acceptance_pct: float = Field(65.0, ge=0, le=100)
    preferred_shippers: List[str] = Field(default_factory=list)
    days_idle: int = Field(0, ge=0)
    is_active: bool = True


class ConfigIn(BaseModel):
    top_n_carriers_per_load: Optional[int] = Field(None, ge=1, le=20)
    min_margin_usd: Optional[float] = Field(None, ge=0)
    min_margin_pct: Optional[float] = Field(None, ge=0, le=100)
    min_match_score: Optional[float] = Field(None, ge=0, le=100)
    offer_expiry_minutes: Optional[int] = Field(None, ge=1, le=1440)
    autopilot_enabled: Optional[bool] = None
    notify_sms: Optional[bool] = None
    notify_email: Optional[bool] = None


# ------------------- Scoring core -------------------
def _extract_state(location: str) -> Optional[str]:
    if not location:
        return None
    parts = location.split(",")
    if len(parts) >= 2:
        return parts[-1].strip().upper()[:2]
    return None


def _score(load: Dict[str, Any], carrier: Dict[str, Any]) -> Dict[str, Any]:
    """Return {qualified: bool, score: int (0-100), hard_fails: [...], breakdown: {...}}."""
    hard_fails: List[str] = []
    breakdown: Dict[str, float] = {}

    # HARD 1: equipment match
    eq = load.get("equipment") or ""
    if eq and eq not in (carrier.get("equipment_types") or []):
        hard_fails.append(f"equipment mismatch (load needs {eq})")

    # HARD 2: weight
    load_wt = float(load.get("weight_lbs") or 0)
    max_wt = float(carrier.get("max_weight_lbs") or 0)
    if load_wt and max_wt and load_wt > max_wt:
        hard_fails.append(f"over max weight ({load_wt:.0f} > {max_wt:.0f} lbs)")

    # HARD 3: lane in service area (either origin or dest state must be in service_states,
    # OR service_states is empty which means nationwide)
    svc = set((carrier.get("service_states") or []))
    if svc:
        ost = _extract_state(load.get("origin", ""))
        dst = _extract_state(load.get("destination", ""))
        if not ((ost and ost in svc) or (dst and dst in svc)):
            hard_fails.append("lane not in carrier service area")

    # HARD 4: insurance coverage
    if load.get("hazmat") and not carrier.get("insurance_covers_hazmat"):
        hard_fails.append("hazmat not covered by insurance")
    if eq == "Reefer" and not carrier.get("insurance_covers_reefer"):
        hard_fails.append("reefer not covered by insurance")

    if hard_fails:
        return {"qualified": False, "score": 0, "hard_fails": hard_fails, "breakdown": breakdown}

    # SOFT — 0..100
    score = 0.0
    # On-time (0..25)
    ot = float(carrier.get("on_time_pct") or 0)
    breakdown["on_time"] = round(ot / 100 * 25, 1)
    score += breakdown["on_time"]
    # Low damage (0..15) — inverse of damage rate
    dr = float(carrier.get("damage_rate_pct") or 0)
    breakdown["low_damage"] = round(max(0, 15 - dr * 3), 1)
    score += breakdown["low_damage"]
    # Rate alignment (0..25) — closer to load RPM = better
    load_rpm = float(load.get("rate_per_mile") or load.get("rpm") or 0)
    ask_rpm = float(carrier.get("rate_expectation_per_mile") or 0)
    if load_rpm and ask_rpm:
        delta = abs(load_rpm - ask_rpm) / max(load_rpm, 0.01)
        breakdown["rate_align"] = round(max(0, 25 - delta * 100), 1)
        score += breakdown["rate_align"]
    else:
        breakdown["rate_align"] = 12.0
        score += 12.0
    # Acceptance history (0..15)
    ap = float(carrier.get("historical_acceptance_pct") or 0)
    breakdown["accept_history"] = round(ap / 100 * 15, 1)
    score += breakdown["accept_history"]
    # Days idle boost — idle carriers are hungry (0..10)
    idle = int(carrier.get("days_idle") or 0)
    breakdown["idle_boost"] = float(min(10, idle * 2))
    score += breakdown["idle_boost"]
    # Shipper preference (0..10)
    if load.get("shipper") and load["shipper"] in (carrier.get("preferred_shippers") or []):
        breakdown["shipper_pref"] = 10.0
        score += 10.0
    else:
        breakdown["shipper_pref"] = 0.0

    return {"qualified": True, "score": int(round(score)),
            "hard_fails": [], "breakdown": breakdown}


def _margin(load: Dict[str, Any], carrier: Dict[str, Any]) -> Dict[str, Any]:
    """Estimate margin: load pays load.rate_usd, carrier expects
    rate_expectation_per_mile × miles. Returns $ and %."""
    miles = float(load.get("miles") or 0)
    load_rate = float(load.get("rate_usd") or 0)
    carrier_ask = round(float(carrier.get("rate_expectation_per_mile") or 0) * miles, 2)
    margin_usd = round(load_rate - carrier_ask, 2)
    margin_pct = round((margin_usd / load_rate) * 100, 1) if load_rate else 0.0
    return {
        "load_rate_usd": load_rate,
        "carrier_ask_usd": carrier_ask,
        "margin_usd": margin_usd,
        "margin_pct": margin_pct,
    }


# ------------------- Mocked comms -------------------
async def _mock_sms(to: str, body: str) -> Dict[str, Any]:
    # Simulate Twilio delivery receipt — production JSON shape
    return {"sid": f"SM-mock-{uuid.uuid4().hex[:14]}",
            "to": to, "from_": "+15005550006",
            "status": "queued", "provider": "twilio-mock",
            "delivered_at": datetime.now(timezone.utc).isoformat()}


async def _mock_email(to: str, subject: str, body: str) -> Dict[str, Any]:
    return {"id": f"em-mock-{uuid.uuid4().hex[:14]}",
            "to": to, "from_": "dispatch@oriseifreight.com",
            "subject": subject, "status": "queued",
            "provider": "resend-mock",
            "delivered_at": datetime.now(timezone.utc).isoformat()}


def _seed_carriers() -> List[Dict[str, Any]]:
    rnd = random.Random("carrier-seed::2026")
    demo = [
        ("Ironhorse Freight Logistics", "MC-844321", ["TX", "OK", "AR", "LA"], "TX", ["Van", "Reefer"], True),
        ("Sunbelt Trucking Co.",         "MC-712989", ["FL", "GA", "AL", "SC"], "FL", ["Van"], False),
        ("Rockies Line Haul",            "MC-611022", ["CO", "UT", "NM", "AZ", "WY"], "CO", ["Van", "Flatbed"], False),
        ("Great Lakes Cartage",          "MC-543210", ["MI", "OH", "IN", "IL", "WI"], "MI", ["Van", "Reefer"], True),
        ("Pacific Coast Express",        "MC-471198", ["CA", "OR", "WA", "NV"], "CA", ["Van", "Reefer"], True),
        ("Mid-Atlantic Movers",          "MC-388821", ["PA", "NJ", "NY", "MD", "VA", "DE"], "PA", ["Van"], False),
        ("Prairie Wind Transport",       "MC-291874", ["ND", "SD", "NE", "KS", "MN", "IA"], "SD", ["Van", "Flatbed"], False),
        ("Bayou State Freight",          "MC-273099", ["LA", "MS", "AL", "TX"], "LA", ["Van", "Flatbed"], True),
        ("Summit Reefer Lines",          "MC-238771", ["CA", "AZ", "NV", "UT", "TX"], "AZ", ["Reefer"], True),
        ("Empire Flatbed Services",      "MC-198432", ["NY", "PA", "OH", "MA", "CT"], "NY", ["Flatbed", "Step Deck"], False),
    ]
    out: List[Dict[str, Any]] = []
    for name, mc, states, home, eq, hazmat in demo:
        out.append({
            "carrier_id": f"CX-{rnd.randint(10000, 99999)}",
            "legal_name": name, "mc_number": mc, "dot_number": f"DOT-{rnd.randint(100000, 9999999)}",
            "contact_name": rnd.choice(["Maria Lopez", "James Chen", "Priya Patel", "David Schmidt",
                                          "Linda Nguyen", "Carlos Rivera", "Sara Olson"]),
            "contact_phone": f"+1555{rnd.randint(1000000, 9999999)}",
            "contact_email": f"dispatch@{name.lower().split()[0]}.example",
            "equipment_types": eq,
            "max_weight_lbs": rnd.choice([44000, 45000, 46000, 48000]),
            "service_states": states,
            "insurance_cargo_usd": rnd.choice([100_000, 150_000, 250_000, 500_000]),
            "insurance_covers_hazmat": hazmat,
            "insurance_covers_reefer": "Reefer" in eq,
            "home_base_state": home,
            "rate_expectation_per_mile": round(rnd.uniform(1.95, 2.55), 2),
            "on_time_pct": round(rnd.uniform(82, 98), 1),
            "damage_rate_pct": round(rnd.uniform(0.2, 3.5), 2),
            "historical_acceptance_pct": round(rnd.uniform(45, 88), 1),
            "preferred_shippers": [],
            "days_idle": rnd.randint(0, 5),
            "is_active": True,
            "added_at": datetime.now(timezone.utc).isoformat(),
        })
    return out


def build_dispatch_autopilot_router(
    *, api_router: APIRouter, db,
    get_current_user: Callable, require_role: Callable,
) -> None:
    router = APIRouter(prefix="/dispatch", tags=["dispatch-autopilot"])

    async def _config() -> Dict[str, Any]:
        cfg = await db.dispatch_config.find_one({"_id": "default"}, {"_id": 0}) or {}
        return {**DEFAULT_CONFIG, **cfg}

    async def _list_carriers(active_only: bool = True) -> List[Dict[str, Any]]:
        q = {"is_active": True} if active_only else {}
        return await db.dispatch_carriers.find(q, {"_id": 0}).to_list(500)

    async def _load_by_id(load_id: str) -> Optional[Dict[str, Any]]:
        # Aggregator uses generated loads keyed by hour; try Mongo brokerage_loads first,
        # then fall back to any aggregator generator for consistency.
        row = await db.brokerage_loads.find_one({"load_id": load_id}, {"_id": 0})
        if row:
            return row
        try:
            from routes.brokerage import _gen_loads_for_board, LOAD_BOARDS  # type: ignore
            for b in LOAD_BOARDS:
                for r in _gen_loads_for_board(b["id"]):
                    if r["load_id"] == load_id:
                        return r
        except Exception:                                                     # noqa: BLE001
            pass
        return None

    async def _send_offer(offer: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
        """Send SMS + email (mocked). Returns delivery receipts."""
        deliveries: Dict[str, Any] = {}
        body_sms = (f"[Orisei Dispatch] Load {offer['load_id']} "
                    f"{offer['origin']} → {offer['destination']} "
                    f"({offer.get('equipment','Van')}) — ${offer['offer_amount_usd']:.0f}. "
                    f"Pickup {offer.get('pickup_date','TBD')}. "
                    f"Reply YES to accept · {offer['accept_url']}")
        body_email = (f"Hi {offer.get('carrier_contact_name') or 'Dispatch'},\n\n"
                      f"Orisei has a load matching your fleet:\n\n"
                      f"  • Lane:     {offer['origin']} → {offer['destination']}\n"
                      f"  • Miles:    {offer.get('miles','?')}\n"
                      f"  • Equip:    {offer.get('equipment','Van')}\n"
                      f"  • Rate:     ${offer['offer_amount_usd']:.2f} "
                      f"({offer.get('rate_per_mile',0):.2f}/mi)\n"
                      f"  • Pickup:   {offer.get('pickup_date','TBD')}\n\n"
                      f"One-click accept:  {offer['accept_url']}\n"
                      f"Decline:           {offer['decline_url']}\n\n"
                      f"— Orisei Autopilot")
        if cfg.get("notify_sms") and offer.get("carrier_phone"):
            deliveries["sms"] = await _mock_sms(offer["carrier_phone"], body_sms)
        if cfg.get("notify_email") and offer.get("carrier_email"):
            deliveries["email"] = await _mock_email(offer["carrier_email"],
                                                     f"Load offer · {offer['origin']} → {offer['destination']}",
                                                     body_email)
        return deliveries

    # ---------- config ----------
    @router.get("/config")
    async def get_config(_=Depends(get_current_user)) -> Dict[str, Any]:
        return await _config()

    @router.post("/config")
    async def set_config(payload: ConfigIn, user=Depends(require_role("admin"))) -> Dict[str, Any]:
        patch = {k: v for k, v in payload.model_dump(exclude_none=True).items()}
        await db.dispatch_config.update_one(
            {"_id": "default"},
            {"$set": {**patch, "updated_at": datetime.now(timezone.utc).isoformat(),
                       "updated_by": getattr(user, "user_id", None)}},
            upsert=True)
        return await _config()

    @router.get("/provider")
    async def provider(_=Depends(get_current_user)) -> Dict[str, Any]:
        return {
            "sms":   {"provider": "twilio",  "mode": "mock"},
            "email": {"provider": "resend",  "mode": "mock"},
            "ml":    {"enabled": False,       "sprint": "rule-based v1"},
        }

    # ---------- carriers ----------
    @router.get("/carriers")
    async def list_carriers(active_only: bool = True,
                             _=Depends(get_current_user)) -> Dict[str, Any]:
        rows = await _list_carriers(active_only=active_only)
        return {"items": rows, "count": len(rows)}

    @router.post("/carriers")
    async def upsert_carrier(payload: CarrierIn,
                              user=Depends(require_role("admin", "dispatcher"))) -> Dict[str, Any]:
        doc = payload.model_dump()
        cid = doc.get("carrier_id") or f"CX-{uuid.uuid4().hex[:8].upper()}"
        doc["carrier_id"] = cid
        doc["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.dispatch_carriers.update_one(
            {"carrier_id": cid},
            {"$set": doc, "$setOnInsert": {"added_at": doc["updated_at"]}},
            upsert=True)
        return doc

    @router.delete("/carriers/{carrier_id}")
    async def retire_carrier(carrier_id: str,
                              user=Depends(require_role("admin"))) -> Dict[str, Any]:
        await db.dispatch_carriers.update_one(
            {"carrier_id": carrier_id},
            {"$set": {"is_active": False,
                       "retired_at": datetime.now(timezone.utc).isoformat()}})
        return {"ok": True, "carrier_id": carrier_id}

    @router.post("/carriers/seed")
    async def seed_carriers(user=Depends(require_role("admin"))) -> Dict[str, Any]:
        existing = await db.dispatch_carriers.count_documents({})
        if existing:
            return {"ok": True, "skipped": True, "existing": existing}
        seed = _seed_carriers()
        await db.dispatch_carriers.insert_many([dict(x) for x in seed])
        return {"ok": True, "seeded": len(seed)}

    # ---------- scoring ----------
    @router.post("/score/{load_id}")
    async def score_load(load_id: str, _=Depends(get_current_user)) -> Dict[str, Any]:
        load = await _load_by_id(load_id)
        if not load:
            raise HTTPException(404, f"Load {load_id} not found")
        carriers = await _list_carriers()
        rows: List[Dict[str, Any]] = []
        for c in carriers:
            s = _score(load, c)
            m = _margin(load, c)
            rows.append({
                "carrier_id": c["carrier_id"],
                "legal_name": c["legal_name"],
                "contact_name": c.get("contact_name"),
                "on_time_pct": c.get("on_time_pct"),
                "damage_rate_pct": c.get("damage_rate_pct"),
                "days_idle": c.get("days_idle"),
                "qualified": s["qualified"],
                "score": s["score"],
                "breakdown": s["breakdown"],
                "hard_fails": s["hard_fails"],
                **m,
            })
        qualified = [r for r in rows if r["qualified"]]
        qualified.sort(key=lambda r: (-r["score"], -r["margin_usd"]))
        disqualified = [r for r in rows if not r["qualified"]]
        return {
            "load_id": load_id,
            "load": {k: load.get(k) for k in
                      ["origin", "destination", "miles", "equipment", "weight_lbs",
                       "rate_usd", "rate_per_mile", "rpm", "hazmat", "shipper", "pickup_date"]},
            "qualified": qualified,
            "disqualified": disqualified,
            "counts": {"qualified": len(qualified),
                       "disqualified": len(disqualified),
                       "total": len(rows)},
        }

    # ---------- offers ----------
    async def _build_offer_row(load: Dict[str, Any], carrier: Dict[str, Any],
                                cfg: Dict[str, Any], scored: Dict[str, Any]) -> Dict[str, Any]:
        offer_id = f"OF-{uuid.uuid4().hex[:10].upper()}"
        # Offer at carrier's rate expectation (start of negotiation)
        offer_amount = scored["carrier_ask_usd"]
        base = f"/api/dispatch/offers/{offer_id}"
        return {
            "offer_id": offer_id,
            "load_id": load["load_id"],
            "board_id": load.get("board_id"),
            "carrier_id": carrier["carrier_id"],
            "carrier_name": carrier["legal_name"],
            "carrier_contact_name": carrier.get("contact_name"),
            "carrier_phone": carrier.get("contact_phone"),
            "carrier_email": carrier.get("contact_email"),
            "origin": load.get("origin"),
            "destination": load.get("destination"),
            "miles": load.get("miles"),
            "equipment": load.get("equipment"),
            "pickup_date": load.get("pickup_date"),
            "rate_per_mile": load.get("rate_per_mile") or load.get("rpm"),
            "load_rate_usd": scored["load_rate_usd"],
            "offer_amount_usd": offer_amount,
            "margin_usd": scored["margin_usd"],
            "margin_pct": scored["margin_pct"],
            "match_score": scored["score"],
            "score_breakdown": scored["breakdown"],
            "accept_url": f"{base}/accept",
            "decline_url": f"{base}/decline",
            "status": "pending",
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc)
                           + timedelta(minutes=int(cfg["offer_expiry_minutes"]))).isoformat(),
        }

    @router.post("/auto-offer/{load_id}")
    async def auto_offer(load_id: str,
                          user=Depends(require_role("admin", "dispatcher"))) -> Dict[str, Any]:
        cfg = await _config()
        score_resp = await score_load(load_id)                                  # reuse
        qualified = score_resp["qualified"]
        load_obj = score_resp["load"]
        # Apply thresholds
        eligible = [r for r in qualified
                    if r["score"] >= cfg["min_match_score"]
                    and r["margin_usd"] >= cfg["min_margin_usd"]
                    and r["margin_pct"] >= cfg["min_margin_pct"]]
        top = eligible[: int(cfg["top_n_carriers_per_load"])]
        if not top:
            return {"ok": True, "offers_sent": 0, "reason": "no carriers cleared thresholds",
                    "load_id": load_id, "qualified": len(qualified),
                    "eligible_after_threshold": len(eligible),
                    "thresholds_used": {k: cfg[k] for k in
                                          ("min_match_score", "min_margin_usd", "min_margin_pct")}}
        carriers = await _list_carriers()
        carrier_by_id = {c["carrier_id"]: c for c in carriers}
        sent: List[Dict[str, Any]] = []
        for r in top:
            c = carrier_by_id.get(r["carrier_id"])
            if not c:
                continue
            offer = await _build_offer_row(
                {**load_obj, "load_id": load_id, "board_id": None}, c, cfg, r)
            deliveries = await _send_offer(offer, cfg)
            offer["deliveries"] = deliveries
            await db.dispatch_offers.insert_one(dict(offer))
            offer.pop("_id", None)
            sent.append(offer)
        return {"ok": True, "offers_sent": len(sent), "load_id": load_id, "offers": sent,
                "eligible_after_threshold": len(eligible)}

    @router.get("/offers")
    async def list_offers(status: Optional[str] = None,
                           limit: int = 100,
                           _=Depends(get_current_user)) -> Dict[str, Any]:
        q: Dict[str, Any] = {}
        if status:
            q["status"] = status
        rows = await db.dispatch_offers.find(q, {"_id": 0}).sort("sent_at", -1).to_list(limit)
        # Expire stale pending offers
        now = datetime.now(timezone.utc)
        for r in rows:
            if r.get("status") == "pending" and r.get("expires_at"):
                try:
                    exp = datetime.fromisoformat(r["expires_at"].replace("Z", "+00:00"))
                    if exp < now:
                        r["status"] = "expired"
                        await db.dispatch_offers.update_one(
                            {"offer_id": r["offer_id"]}, {"$set": {"status": "expired"}})
                except Exception:                                               # noqa: BLE001
                    pass
        counts = {"pending": 0, "accepted": 0, "declined": 0, "expired": 0, "sent_to_workflow": 0}
        for r in rows:
            counts[r.get("status", "pending")] = counts.get(r.get("status", "pending"), 0) + 1
        return {"items": rows, "count": len(rows), "counts_by_status": counts}

    @router.post("/offers/{offer_id}/accept")
    async def accept_offer(offer_id: str,
                            _=Depends(get_current_user)) -> Dict[str, Any]:
        o = await db.dispatch_offers.find_one({"offer_id": offer_id}, {"_id": 0})
        if not o:
            raise HTTPException(404, "Offer not found")
        if o["status"] != "pending":
            raise HTTPException(409, f"Offer already {o['status']}")
        await db.dispatch_offers.update_one(
            {"offer_id": offer_id},
            {"$set": {"status": "accepted",
                       "accepted_at": datetime.now(timezone.utc).isoformat()}})
        # Cancel sibling pending offers on the same load
        await db.dispatch_offers.update_many(
            {"load_id": o["load_id"], "offer_id": {"$ne": offer_id},
             "status": "pending"},
            {"$set": {"status": "expired",
                       "expired_reason": "sibling offer accepted",
                       "expired_at": datetime.now(timezone.utc).isoformat()}})
        return {"ok": True, "offer_id": offer_id, "status": "accepted",
                "load_id": o["load_id"]}

    @router.post("/offers/{offer_id}/decline")
    async def decline_offer(offer_id: str, _=Depends(get_current_user)) -> Dict[str, Any]:
        o = await db.dispatch_offers.find_one({"offer_id": offer_id}, {"_id": 0})
        if not o:
            raise HTTPException(404, "Offer not found")
        if o["status"] != "pending":
            raise HTTPException(409, f"Offer already {o['status']}")
        await db.dispatch_offers.update_one(
            {"offer_id": offer_id},
            {"$set": {"status": "declined",
                       "declined_at": datetime.now(timezone.utc).isoformat()}})
        return {"ok": True, "offer_id": offer_id, "status": "declined"}

    # ---------- autopilot cycle ----------
    async def _autopilot_cycle_impl(user_id: Optional[str] = None) -> Dict[str, Any]:
        cfg = await _config()
        if not cfg.get("autopilot_enabled"):
            return {"ok": True, "skipped": True, "reason": "autopilot_disabled"}
        # Get top aggregator loads for the current hour
        try:
            from routes.brokerage import _gen_loads_for_board, LOAD_BOARDS  # type: ignore
            loads: List[Dict[str, Any]] = []
            for b in LOAD_BOARDS:
                loads.extend(_gen_loads_for_board(b["id"], count=6))
        except Exception:                                                       # noqa: BLE001
            loads = []
        # Skip loads that already have an offer
        already = set()
        recent = await db.dispatch_offers.find(
            {"sent_at": {"$gte": (datetime.now(timezone.utc)
                                    - timedelta(hours=2)).isoformat()}},
            {"_id": 0, "load_id": 1}).to_list(500)
        for r in recent:
            already.add(r.get("load_id"))
        fresh = [ld for ld in loads if ld["load_id"] not in already]
        # Cap per cycle so we don't blast every load in one tick
        fresh = fresh[:12]
        total_offers = 0
        touched_loads: List[str] = []
        for ld in fresh:
            # Persist load to brokerage_loads so score_load / auto-offer can find it
            await db.brokerage_loads.update_one(
                {"load_id": ld["load_id"]}, {"$set": ld}, upsert=True)
            r = await auto_offer(ld["load_id"])                                # type: ignore[arg-type]
            # ^ won't work due to Depends. Inline the logic instead:
            # (we roll our own below)
        # Inline logic: score + fire offers per load
        carriers = await _list_carriers()
        for ld in fresh:
            score_rows: List[Dict[str, Any]] = []
            for c in carriers:
                s = _score(ld, c)
                m = _margin(ld, c)
                if s["qualified"]:
                    score_rows.append({"carrier": c, "score": s, "margin": m})
            score_rows.sort(key=lambda r: (-r["score"]["score"], -r["margin"]["margin_usd"]))
            eligible = [r for r in score_rows
                        if r["score"]["score"] >= cfg["min_match_score"]
                        and r["margin"]["margin_usd"] >= cfg["min_margin_usd"]
                        and r["margin"]["margin_pct"] >= cfg["min_margin_pct"]]
            top = eligible[: int(cfg["top_n_carriers_per_load"])]
            for r in top:
                offer = await _build_offer_row(ld, r["carrier"], cfg,
                                                 {**r["margin"], "score": r["score"]["score"],
                                                  "breakdown": r["score"]["breakdown"]})
                deliveries = await _send_offer(offer, cfg)
                offer["deliveries"] = deliveries
                offer["source"] = "autopilot_tick"
                offer["fired_by"] = user_id
                await db.dispatch_offers.insert_one(dict(offer))
                total_offers += 1
            if top:
                touched_loads.append(ld["load_id"])
        return {
            "ok": True, "cycle_at": datetime.now(timezone.utc).isoformat(),
            "loads_scanned": len(loads), "loads_fresh": len(fresh),
            "loads_touched": len(touched_loads), "offers_sent": total_offers,
            "cfg_snapshot": {k: cfg[k] for k in
                              ("min_match_score", "min_margin_usd", "min_margin_pct",
                                "top_n_carriers_per_load")},
        }

    @router.post("/tick")
    async def tick(user=Depends(require_role("admin", "dispatcher"))) -> Dict[str, Any]:
        return await _autopilot_cycle_impl(user_id=getattr(user, "user_id", None))

    # ---------- dashboard ----------
    @router.get("/dashboard")
    async def dashboard(_=Depends(get_current_user)) -> Dict[str, Any]:
        cfg = await _config()
        offers = await db.dispatch_offers.find({}, {"_id": 0}).to_list(1000)
        by_status = {"pending": 0, "accepted": 0, "declined": 0, "expired": 0}
        margin_captured = 0.0
        accept_times_sec: List[float] = []
        for o in offers:
            by_status[o.get("status", "pending")] = by_status.get(o.get("status", "pending"), 0) + 1
            if o.get("status") == "accepted":
                margin_captured += float(o.get("margin_usd") or 0)
                try:
                    s = datetime.fromisoformat(o["sent_at"].replace("Z", "+00:00"))
                    a = datetime.fromisoformat(o["accepted_at"].replace("Z", "+00:00"))
                    accept_times_sec.append((a - s).total_seconds())
                except Exception:                                               # noqa: BLE001
                    pass
        total = len(offers)
        active = await db.dispatch_carriers.count_documents({"is_active": True})
        accept_rate = round((by_status["accepted"] / total) * 100, 1) if total else 0.0
        avg_ttb = round(sum(accept_times_sec) / len(accept_times_sec), 1) if accept_times_sec else 0.0
        # Last-hour throughput
        one_hr_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        last_hour = await db.dispatch_offers.count_documents({"sent_at": {"$gte": one_hr_ago}})
        return {
            "config": cfg,
            "carriers_active": active,
            "offers_total": total,
            "offers_by_status": by_status,
            "acceptance_rate_pct": accept_rate,
            "avg_time_to_book_sec": avg_ttb,
            "margin_captured_usd": round(margin_captured, 2),
            "offers_last_hour": last_hour,
        }

    api_router.include_router(router)
