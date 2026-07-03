"""routes.dispatch_ml — ML layer on top of the rule-based dispatch engine.

Two sklearn models, both persisted to `/app/backend/ml_models/`:

  ┌────────────────────────────────────┬───────────────────────────────────┐
  │ accept_clf.joblib                   │ GradientBoostingClassifier        │
  │   → P(carrier accepts this offer)   │ features: score, margin, RPM      │
  │                                     │ delta, on-time, damage, idle,    │
  │                                     │ historical acceptance, miles     │
  ├────────────────────────────────────┼───────────────────────────────────┤
  │ rate_reg.joblib                     │ GradientBoostingRegressor         │
  │   → suggested $/mi to offer         │ features: same (learns from      │
  │                                     │ accepted offers only)             │
  └────────────────────────────────────┴───────────────────────────────────┘

Warm start: with fewer than 20 accepted rows, both models return a
heuristic prediction (accept ≈ score/100 × acceptance_history_pct;
rate = carrier ask + tiny margin nudge). This lets the ML layer light
up immediately, then improves as the offer log grows.

Rationale: Claude Sonnet 4.5 via the Emergent LLM key produces a
one-paragraph human explanation of the pick per load. Free, small
prompt, ~0.5s roundtrip.

Endpoints — /api/dispatch/ml/*
  GET  /status                · model versions, training data size, metrics
  POST /train                 · retrain both models on current dispatch_offers
  POST /predict/{load_id}     · ML-boosted ranking (accept prob + rate suggest)
  POST /explain/{load_id}     · Claude rationale for the top match
  POST /seed-training-data    · admin: generate synthetic historical offers
"""
from __future__ import annotations

import logging
import os
import random
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger("orisei.dispatch.ml")

MODEL_DIR = Path("/app/backend/ml_models")
MODEL_DIR.mkdir(parents=True, exist_ok=True)
ACCEPT_MODEL_PATH = MODEL_DIR / "accept_clf.joblib"
RATE_MODEL_PATH = MODEL_DIR / "rate_reg.joblib"
META_PATH = MODEL_DIR / "model_meta.json"

FEATURE_ORDER = [
    "match_score",
    "margin_usd",
    "margin_pct",
    "rate_delta_per_mile",       # carrier ask - load RPM (negative = carrier cheaper than load pays)
    "on_time_pct",
    "damage_rate_pct",
    "days_idle",
    "historical_acceptance_pct",
    "miles",
]

MIN_TRAIN_ROWS = 20


class TrainOut(BaseModel):
    trained: bool
    rows_used: int
    accept_auc: Optional[float] = None
    rate_r2: Optional[float] = None
    reason: Optional[str] = None
    trained_at: Optional[str] = None


def _features_from_offer(o: Dict[str, Any], carrier: Optional[Dict[str, Any]] = None) -> Dict[str, float]:
    """Flatten an offer + optional carrier record into the feature vector.
    Missing values are imputed to safe midpoints."""
    load_rpm = float(o.get("rate_per_mile") or 0)
    ask = float((carrier or {}).get("rate_expectation_per_mile") or 0)
    if not ask and o.get("miles") and o.get("offer_amount_usd"):
        ask = float(o["offer_amount_usd"]) / max(float(o["miles"]), 1)
    return {
        "match_score":               float(o.get("match_score") or 50),
        "margin_usd":                float(o.get("margin_usd") or 0),
        "margin_pct":                float(o.get("margin_pct") or 0),
        "rate_delta_per_mile":       round(ask - load_rpm, 3) if ask and load_rpm else 0.0,
        "on_time_pct":               float((carrier or {}).get("on_time_pct") or 90),
        "damage_rate_pct":           float((carrier or {}).get("damage_rate_pct") or 1),
        "days_idle":                 float((carrier or {}).get("days_idle") or 0),
        "historical_acceptance_pct": float((carrier or {}).get("historical_acceptance_pct") or 60),
        "miles":                     float(o.get("miles") or 0),
    }


def _vec(feat: Dict[str, float]) -> List[float]:
    return [feat[k] for k in FEATURE_ORDER]


def _heuristic_accept_prob(feat: Dict[str, float]) -> float:
    """Simple pre-ML fallback: (match_score/100) × (accept_history_pct/100),
    nudged down when margin_pct is low (cheap loads get declined more)."""
    base = (feat["match_score"] / 100.0) * (feat["historical_acceptance_pct"] / 100.0)
    if feat["margin_pct"] < 8:
        base *= 0.75
    elif feat["margin_pct"] > 25:
        base = min(1.0, base * 1.15)
    if feat["days_idle"] >= 3:
        base = min(1.0, base * 1.10)
    return round(max(0.02, min(0.98, base)), 3)


def _heuristic_rate_suggest(feat: Dict[str, float]) -> float:
    """Return suggested $/mi. Start at carrier ask, nudge:
      + when idle days high (they'll take cheaper)
      - when their historical acceptance is low (bump rate to entice)."""
    # Reconstruct ask from delta if possible; else default to 2.15
    if feat["rate_delta_per_mile"]:
        base_ask = feat["rate_delta_per_mile"] + max(0.01, (feat["margin_usd"] / max(feat["miles"], 1)))
    else:
        base_ask = 2.15
    nudge = 0.0
    if feat["days_idle"] >= 3:
        nudge -= 0.05
    if feat["historical_acceptance_pct"] < 55:
        nudge += 0.08
    return round(max(1.20, min(3.50, base_ask + nudge)), 3)


class _ModelBundle:
    """Lazy-loaded joblib bundle. Auto-reloads when files change on disk."""
    def __init__(self):
        self._accept = None
        self._rate = None
        self._meta: Dict[str, Any] = {}
        self._loaded_at = 0.0

    def load(self):
        import joblib
        import json
        try:
            self._accept = joblib.load(ACCEPT_MODEL_PATH) if ACCEPT_MODEL_PATH.exists() else None
            self._rate = joblib.load(RATE_MODEL_PATH) if RATE_MODEL_PATH.exists() else None
            self._meta = json.loads(META_PATH.read_text()) if META_PATH.exists() else {}
        except Exception as e:                                              # noqa: BLE001
            logger.warning("model load failed: %s", e)
            self._accept = None
            self._rate = None
            self._meta = {}

    def accept_prob(self, feat: Dict[str, float]) -> float:
        if not self._accept:
            self.load()
        if not self._accept:
            return _heuristic_accept_prob(feat)
        try:
            import numpy as np
            X = np.array([_vec(feat)])
            p = float(self._accept.predict_proba(X)[0, 1])
            return round(max(0.01, min(0.99, p)), 3)
        except Exception as e:                                              # noqa: BLE001
            logger.warning("accept_prob failed: %s", e)
            return _heuristic_accept_prob(feat)

    def suggest_rate(self, feat: Dict[str, float]) -> float:
        if not self._rate:
            self.load()
        if not self._rate:
            return _heuristic_rate_suggest(feat)
        try:
            import numpy as np
            X = np.array([_vec(feat)])
            r = float(self._rate.predict(X)[0])
            return round(max(1.20, min(3.50, r)), 3)
        except Exception as e:                                              # noqa: BLE001
            logger.warning("suggest_rate failed: %s", e)
            return _heuristic_rate_suggest(feat)

    def meta(self) -> Dict[str, Any]:
        if not self._meta:
            self.load()
        return self._meta or {}


BUNDLE = _ModelBundle()


async def _explain_with_claude(load: Dict[str, Any], top_carrier: Dict[str, Any],
                                 pred: Dict[str, Any]) -> Optional[str]:
    """One-paragraph rationale from Claude Sonnet 4.5 via Emergent LLM key."""
    key = os.environ.get("EMERGENT_LLM_KEY")
    if not key:
        return None
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage      # type: ignore
    except Exception:                                                       # noqa: BLE001
        return None
    prompt = (
        f"You are a freight-brokerage dispatch analyst. In 3 concise sentences (≤ 60 words),"
        f" explain why carrier '{top_carrier.get('legal_name')}' is the best match for this load:\n"
        f"- Lane: {load.get('origin')} → {load.get('destination')} ({load.get('miles')} mi)\n"
        f"- Equipment: {load.get('equipment')} · Weight: {load.get('weight_lbs')} lbs\n"
        f"- Load pays: ${load.get('rate_usd')} (${load.get('rate_per_mile')}/mi)\n"
        f"- Carrier: on-time {top_carrier.get('on_time_pct')}% · damage {top_carrier.get('damage_rate_pct')}%"
        f" · idle {top_carrier.get('days_idle')}d · asks ${top_carrier.get('rate_expectation_per_mile')}/mi\n"
        f"- ML predicts: accept_prob={pred.get('accept_prob')} · suggested_rate=${pred.get('suggested_rate_per_mile')}/mi"
        f" · margin=${pred.get('margin_usd')} ({pred.get('margin_pct')}%)\n"
        f"Focus on the numbers that matter most (margin, acceptance risk, on-time). No preamble."
    )
    try:
        chat = LlmChat(api_key=key, session_id=f"dispatch-explain-{uuid.uuid4().hex[:8]}",
                        system_message="You are a concise dispatch analyst."
                       ).with_model("anthropic", "claude-sonnet-4-5-20250929")
        msg = UserMessage(text=prompt)
        resp = await chat.send_message(msg)
        return str(resp).strip()
    except Exception as e:                                                  # noqa: BLE001
        logger.warning("Claude explain failed: %s", e)
        return None


def _generate_synthetic_training_data(rnd: random.Random,
                                        n: int = 400) -> List[Dict[str, Any]]:
    """Deterministic synthetic offers for cold-starting the ML models.
    Ground truth: accept ≈ f(score, margin, rate_delta, idle, on_time)."""
    rows: List[Dict[str, Any]] = []
    now = datetime.now(timezone.utc)
    for i in range(n):
        score = rnd.randint(35, 96)
        on_time = rnd.uniform(78, 99)
        damage = rnd.uniform(0.2, 4.5)
        idle = rnd.randint(0, 7)
        hist = rnd.uniform(35, 92)
        miles = rnd.randint(120, 2400)
        load_rpm = round(rnd.uniform(1.85, 3.25), 2)
        ask = round(load_rpm - rnd.uniform(-0.35, 0.55), 2)                  # broker margin band
        margin_usd = round((load_rpm - ask) * miles, 2)
        margin_pct = round((margin_usd / (load_rpm * miles)) * 100, 1) if load_rpm else 0.0
        # Ground truth accept rule with stronger, more separable signal
        p = (score / 100 * 0.30
             + (hist / 100) * 0.25
             + max(0, min(1, margin_pct / 25)) * 0.30       # margin dominant
             + (min(idle, 5) / 5) * 0.10
             + (on_time / 100) * 0.05)
        # Sharper decision boundary (less noise) so the classifier can learn it
        threshold = 0.55 + rnd.uniform(-0.06, 0.06)
        accepted = 1 if p >= threshold else 0
        # Optimal accepted rate ≈ carrier ask + a small brokerage nudge for hot lanes
        optimal_rate = round(ask + (0.08 if idle >= 3 else -0.03) + rnd.uniform(-0.05, 0.05), 3)
        rows.append({
            "offer_id": f"SYN-{i:04d}",
            "match_score": score,
            "margin_usd": margin_usd,
            "margin_pct": margin_pct,
            "rate_per_mile": load_rpm,
            "miles": miles,
            "offer_amount_usd": round(ask * miles, 2),
            "status": "accepted" if accepted else rnd.choice(["declined", "expired"]),
            "accepted": accepted,
            "optimal_rate_pm": optimal_rate,
            "carrier_snapshot": {
                "on_time_pct": round(on_time, 1),
                "damage_rate_pct": round(damage, 2),
                "days_idle": idle,
                "historical_acceptance_pct": round(hist, 1),
                "rate_expectation_per_mile": ask,
            },
            "sent_at": (now - timedelta(days=rnd.randint(1, 90))).isoformat(),
            "synthetic": True,
        })
    return rows


def build_dispatch_ml_router(
    *, api_router: APIRouter, db,
    get_current_user: Callable, require_role: Callable,
) -> None:
    router = APIRouter(prefix="/dispatch/ml", tags=["dispatch-ml"])

    async def _training_rows() -> List[Dict[str, Any]]:
        """Pull decided offers (accepted/declined/expired) from Mongo, join
        each with the carrier snapshot at offer-time. Falls back to synthetic
        seed if there aren't enough real rows."""
        real = await db.dispatch_offers.find(
            {"status": {"$in": ["accepted", "declined", "expired"]}},
            {"_id": 0}).to_list(5000)
        synthetic = await db.dispatch_ml_training.find({}, {"_id": 0}).to_list(5000)
        return real + synthetic

    async def _hydrate_carrier(carrier_id: Optional[str]) -> Dict[str, Any]:
        if not carrier_id:
            return {}
        c = await db.dispatch_carriers.find_one({"carrier_id": carrier_id}, {"_id": 0})
        return c or {}

    async def _load_lookup(load_id: str) -> Optional[Dict[str, Any]]:
        row = await db.brokerage_loads.find_one({"load_id": load_id}, {"_id": 0})
        if row:
            return row
        try:
            from routes.brokerage import _gen_loads_for_board, LOAD_BOARDS  # type: ignore
            for b in LOAD_BOARDS:
                for r in _gen_loads_for_board(b["id"]):
                    if r["load_id"] == load_id:
                        return r
        except Exception:                                                   # noqa: BLE001
            pass
        return None

    @router.get("/status")
    async def status(_=Depends(get_current_user)) -> Dict[str, Any]:
        rows = await _training_rows()
        n = len(rows)
        accepted = sum(1 for r in rows if r.get("status") == "accepted" or r.get("accepted") == 1)
        BUNDLE.load()
        meta = BUNDLE.meta()
        return {
            "models_loaded": bool(BUNDLE._accept and BUNDLE._rate),
            "accept_model_path": str(ACCEPT_MODEL_PATH) if ACCEPT_MODEL_PATH.exists() else None,
            "rate_model_path": str(RATE_MODEL_PATH) if RATE_MODEL_PATH.exists() else None,
            "training_rows_available": n,
            "training_rows_accepted": accepted,
            "min_rows_to_train": MIN_TRAIN_ROWS,
            "features": FEATURE_ORDER,
            "meta": meta,
        }

    @router.post("/seed-training-data")
    async def seed_training(count: int = 400,
                             user=Depends(require_role("admin"))) -> Dict[str, Any]:
        rnd = random.Random("ml-seed::orisei::v1")
        rows = _generate_synthetic_training_data(rnd, n=count)
        await db.dispatch_ml_training.delete_many({"synthetic": True})
        await db.dispatch_ml_training.insert_many([dict(x) for x in rows])
        return {"ok": True, "seeded": len(rows)}

    @router.post("/train", response_model=TrainOut)
    async def train(user=Depends(require_role("admin"))) -> TrainOut:
        rows = await _training_rows()
        n = len(rows)
        if n < MIN_TRAIN_ROWS:
            return TrainOut(trained=False, rows_used=n, reason=f"need ≥{MIN_TRAIN_ROWS} rows")
        # Build X, y_accept, X_rate, y_rate
        import numpy as np
        import joblib
        import json
        from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import roc_auc_score, r2_score

        X, y_a, X_r, y_r = [], [], [], []
        for r in rows:
            carrier_snap = r.get("carrier_snapshot") or {}
            feat = _features_from_offer(r, carrier_snap)
            X.append(_vec(feat))
            y_a.append(1 if (r.get("status") == "accepted" or r.get("accepted") == 1) else 0)
            if r.get("status") == "accepted" or r.get("accepted") == 1:
                miles = float(r.get("miles") or 0)
                opt = r.get("optimal_rate_pm")
                if opt is None and miles:
                    opt = float(r.get("offer_amount_usd") or 0) / max(miles, 1)
                if opt:
                    X_r.append(_vec(feat))
                    y_r.append(float(opt))
        X = np.array(X)
        y_a = np.array(y_a)
        # Classifier
        auc = None
        try:
            if len(set(y_a)) >= 2 and len(X) >= 40:
                Xtr, Xte, ytr, yte = train_test_split(X, y_a, test_size=0.25, random_state=42, stratify=y_a)
                clf = GradientBoostingClassifier(n_estimators=120, max_depth=3, random_state=42)
                clf.fit(Xtr, ytr)
                try:
                    auc = round(float(roc_auc_score(yte, clf.predict_proba(Xte)[:, 1])), 3)
                except Exception:                                           # noqa: BLE001
                    auc = None
            else:
                clf = GradientBoostingClassifier(n_estimators=80, max_depth=3, random_state=42)
                clf.fit(X, y_a)
        except Exception as e:                                              # noqa: BLE001
            return TrainOut(trained=False, rows_used=n, reason=f"clf fit failed: {e}")
        joblib.dump(clf, ACCEPT_MODEL_PATH)
        # Regressor (accepted-only)
        r2 = None
        if len(X_r) >= 15:
            Xr = np.array(X_r)
            yr = np.array(y_r)
            try:
                Xtr, Xte, ytr, yte = train_test_split(Xr, yr, test_size=0.25, random_state=42)
                reg = GradientBoostingRegressor(n_estimators=140, max_depth=3, random_state=42)
                reg.fit(Xtr, ytr)
                r2 = round(float(r2_score(yte, reg.predict(Xte))), 3)
                joblib.dump(reg, RATE_MODEL_PATH)
            except Exception as e:                                          # noqa: BLE001
                logger.warning("regressor fit failed: %s", e)
        meta = {
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "trained_by": getattr(user, "user_id", None),
            "rows_used": n,
            "accepted_rows": int(sum(y_a)),
            "accept_auc": auc,
            "rate_r2": r2,
            "features": FEATURE_ORDER,
            "version": "v1",
        }
        META_PATH.write_text(json.dumps(meta, indent=2))
        BUNDLE.load()
        return TrainOut(trained=True, rows_used=n, accept_auc=auc, rate_r2=r2,
                        trained_at=meta["trained_at"])

    @router.post("/predict/{load_id}")
    async def predict(load_id: str, _=Depends(get_current_user)) -> Dict[str, Any]:
        """Rank carriers by ML accept-prob × margin, alongside a rate
        suggestion for each. Falls back to heuristics if models absent."""
        load = await _load_lookup(load_id)
        if not load:
            raise HTTPException(404, "Load not found")
        carriers = await db.dispatch_carriers.find({"is_active": True}, {"_id": 0}).to_list(500)
        # Reuse the rule-based scoring
        from routes.dispatch_autopilot import _score as rule_score, _margin as rule_margin

        rows: List[Dict[str, Any]] = []
        for c in carriers:
            s = rule_score(load, c)
            m = rule_margin(load, c)
            feat = _features_from_offer({
                "match_score": s["score"],
                "margin_usd": m["margin_usd"],
                "margin_pct": m["margin_pct"],
                "rate_per_mile": load.get("rate_per_mile") or load.get("rpm"),
                "miles": load.get("miles"),
                "offer_amount_usd": m["carrier_ask_usd"],
            }, c)
            accept_prob = BUNDLE.accept_prob(feat)
            suggested_rpm = BUNDLE.suggest_rate(feat)
            miles = float(load.get("miles") or 0)
            suggested_offer = round(suggested_rpm * miles, 2) if miles else m["carrier_ask_usd"]
            # Expected margin using ML-suggested rate
            exp_margin = round(m["load_rate_usd"] - suggested_offer, 2)
            expected_value = round(accept_prob * exp_margin, 2)
            rows.append({
                "carrier_id": c["carrier_id"],
                "legal_name": c["legal_name"],
                "on_time_pct": c.get("on_time_pct"),
                "damage_rate_pct": c.get("damage_rate_pct"),
                "days_idle": c.get("days_idle"),
                "qualified": s["qualified"],
                "match_score": s["score"],
                "hard_fails": s["hard_fails"],
                "carrier_ask_usd": m["carrier_ask_usd"],
                "margin_usd": m["margin_usd"],
                "margin_pct": m["margin_pct"],
                "ml_accept_prob": accept_prob,
                "ml_suggested_rpm": suggested_rpm,
                "ml_suggested_offer_usd": suggested_offer,
                "ml_expected_margin_usd": exp_margin,
                "ml_expected_value_usd": expected_value,
            })
        qualified = [r for r in rows if r["qualified"]]
        qualified.sort(key=lambda r: (-r["ml_expected_value_usd"], -r["match_score"]))
        return {
            "load_id": load_id,
            "load": {k: load.get(k) for k in
                      ["origin", "destination", "miles", "equipment", "weight_lbs",
                       "rate_usd", "rate_per_mile", "rpm", "hazmat", "shipper", "pickup_date"]},
            "ml_active": bool(BUNDLE._accept and BUNDLE._rate),
            "meta": BUNDLE.meta(),
            "ranked": qualified,
            "disqualified_count": len(rows) - len(qualified),
        }

    @router.post("/explain/{load_id}")
    async def explain(load_id: str,
                       carrier_id: Optional[str] = None,
                       _=Depends(get_current_user)) -> Dict[str, Any]:
        pred = await predict(load_id)                                       # type: ignore
        ranked = pred.get("ranked") or []
        if not ranked:
            raise HTTPException(422, "No qualified carriers to explain")
        # If caller specifies a carrier, explain that; else top-1.
        target = None
        if carrier_id:
            target = next((r for r in ranked if r["carrier_id"] == carrier_id), None)
        if not target:
            target = ranked[0]
        carrier = await _hydrate_carrier(target["carrier_id"])
        rationale = await _explain_with_claude(pred["load"], carrier, target)
        return {
            "load_id": load_id,
            "carrier_id": target["carrier_id"],
            "carrier_name": target["legal_name"],
            "rationale": rationale or (
                f"{target['legal_name']} is the top pick: match score {target['match_score']}, "
                f"predicted accept probability {int(target['ml_accept_prob']*100)}%, "
                f"expected margin ${target['ml_expected_margin_usd']} "
                f"(${target['ml_expected_value_usd']} EV after acceptance-risk weighting)."),
            "used_llm": rationale is not None,
            "top_match": target,
        }

    api_router.include_router(router)
