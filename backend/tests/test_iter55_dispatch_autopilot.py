"""Iteration 55 — Dispatch Autopilot + ML backend tests.

Coverage:
  - /api/dispatch/provider, /config, /carriers (CRUD + seed)
  - /api/dispatch/score/{load_id}, /auto-offer/{load_id}
  - /api/dispatch/offers (list + accept + decline + 409)
  - /api/dispatch/tick (autopilot cycle + dedupe + skipped path)
  - /api/dispatch/dashboard
  - /api/dispatch/ml/status, seed-training-data, train, predict/{id}, explain/{id}
  - Regression smoke: /aggregator/feed, /routing/provider, /telematics/provider,
    /parcel/provider, /edi/provider
"""
from __future__ import annotations

import os
import time
import pytest
import requests

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://clean-logistics-dash.preview.emergentagent.com",
).rstrip("/")
ADMIN_TOKEN = "test_session_admin_1"
HDR = {"Authorization": f"Bearer {ADMIN_TOKEN}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    sess.headers.update(HDR)
    return sess


@pytest.fixture(scope="module")
def real_load_id(s):
    # Use aggregator feed to grab a real load
    r = s.get(f"{BASE_URL}/api/aggregator/feed?limit=5", timeout=30)
    assert r.status_code == 200, r.text
    items = r.json().get("items") or r.json().get("loads") or []
    if not items:
        pytest.skip("aggregator returned no loads")
    # Persist that load into brokerage_loads via /tick so score/auto-offer works
    return items[0]["load_id"]


# ---------------- provider + config ----------------
class TestProviderAndConfig:
    def test_provider(self, s):
        r = s.get(f"{BASE_URL}/api/dispatch/provider", timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["sms"]["provider"] == "twilio" and d["sms"]["mode"] == "mock"
        assert d["email"]["provider"] == "resend" and d["email"]["mode"] == "mock"
        assert "ml" in d

    def test_config_defaults(self, s):
        r = s.get(f"{BASE_URL}/api/dispatch/config", timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("top_n_carriers_per_load", "min_margin_usd", "min_margin_pct",
                  "min_match_score", "offer_expiry_minutes", "autopilot_enabled",
                  "notify_sms", "notify_email"):
            assert k in d, f"missing config key {k}"

    def test_config_partial_update(self, s):
        # Baseline
        base = s.get(f"{BASE_URL}/api/dispatch/config", timeout=15).json()
        # Patch just min_match_score
        r = s.post(f"{BASE_URL}/api/dispatch/config",
                   json={"min_match_score": 60.0}, timeout=15)
        assert r.status_code == 200, r.text
        after = r.json()
        assert after["min_match_score"] == 60.0
        # Other defaults preserved
        assert after["top_n_carriers_per_load"] == base["top_n_carriers_per_load"]
        assert after["notify_sms"] == base["notify_sms"]
        # Restore
        s.post(f"{BASE_URL}/api/dispatch/config",
               json={"min_match_score": 55.0}, timeout=15)


# ---------------- carriers ----------------
class TestCarriers:
    def test_seed_carriers(self, s):
        r = s.post(f"{BASE_URL}/api/dispatch/carriers/seed", timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["ok"] is True
        assert "seeded" in d or "skipped" in d

    def test_seed_idempotent(self, s):
        r = s.post(f"{BASE_URL}/api/dispatch/carriers/seed", timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("skipped") is True

    def test_list_carriers(self, s):
        r = s.get(f"{BASE_URL}/api/dispatch/carriers", timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        items = d["items"]
        assert len(items) >= 10
        for c in items[:3]:
            for k in ("carrier_id", "legal_name", "mc_number", "equipment_types",
                      "service_states", "insurance_covers_hazmat",
                      "rate_expectation_per_mile", "on_time_pct",
                      "damage_rate_pct", "days_idle"):
                assert k in c, f"missing key {k} in carrier {c.get('carrier_id')}"

    def test_upsert_carrier_and_retire(self, s):
        payload = {
            "legal_name": "TEST_CarrierA",
            "contact_email": "test@example.com",
            "equipment_types": ["Van"],
            "service_states": ["CA", "NV"],
        }
        r = s.post(f"{BASE_URL}/api/dispatch/carriers", json=payload, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["carrier_id"].startswith("CX-")
        cid = d["carrier_id"]
        # Re-post updates
        payload["carrier_id"] = cid
        payload["on_time_pct"] = 88.5
        r2 = s.post(f"{BASE_URL}/api/dispatch/carriers", json=payload, timeout=15)
        assert r2.status_code == 200
        assert r2.json()["on_time_pct"] == 88.5

        # Retire
        r3 = s.delete(f"{BASE_URL}/api/dispatch/carriers/{cid}", timeout=15)
        assert r3.status_code == 200

        # Should not appear in active_only=true
        r4 = s.get(f"{BASE_URL}/api/dispatch/carriers?active_only=true", timeout=15)
        assert r4.status_code == 200
        ids = [c["carrier_id"] for c in r4.json()["items"]]
        assert cid not in ids


# ---------------- scoring + offers ----------------
class TestScoreAndOffers:
    def test_tick_persists_loads(self, s):
        # First ensure autopilot_enabled=true
        s.post(f"{BASE_URL}/api/dispatch/config",
               json={"autopilot_enabled": True}, timeout=15)
        r = s.post(f"{BASE_URL}/api/dispatch/tick", timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("loads_scanned", "loads_fresh", "loads_touched",
                  "offers_sent", "cfg_snapshot"):
            assert k in d, f"missing tick key {k}"

    def test_tick_dedupes(self, s):
        r1 = s.post(f"{BASE_URL}/api/dispatch/tick", timeout=60)
        assert r1.status_code == 200
        d1 = r1.json()
        r2 = s.post(f"{BASE_URL}/api/dispatch/tick", timeout=60)
        assert r2.status_code == 200
        d2 = r2.json()
        # Second run within 2hrs should see loads_fresh ≤ first run
        assert d2.get("loads_fresh", 0) <= d1.get("loads_fresh", 999)

    def test_score_returns_qualified_shape(self, s):
        # Pull one persisted load
        r = s.get(f"{BASE_URL}/api/dispatch/offers?limit=1", timeout=15)
        assert r.status_code == 200
        offers = r.json()["items"]
        if not offers:
            pytest.skip("no offers exist after tick")
        load_id = offers[0]["load_id"]
        r2 = s.post(f"{BASE_URL}/api/dispatch/score/{load_id}", timeout=30)
        assert r2.status_code == 200, r2.text
        d = r2.json()
        assert "qualified" in d and "disqualified" in d
        assert set(d["counts"].keys()) >= {"qualified", "disqualified", "total"}
        for row in d["qualified"][:2]:
            assert 0 <= row["score"] <= 100
            assert "breakdown" in row
            for bkey in ("on_time", "low_damage", "rate_align",
                         "accept_history", "idle_boost", "shipper_pref"):
                assert bkey in row["breakdown"], f"missing breakdown {bkey}"
            for mkey in ("margin_usd", "margin_pct", "carrier_ask_usd", "load_rate_usd"):
                assert mkey in row, f"missing margin {mkey}"
        # Descending by score
        scores = [r["score"] for r in d["qualified"]]
        assert scores == sorted(scores, reverse=True)

    def test_auto_offer(self, s):
        r = s.get(f"{BASE_URL}/api/dispatch/offers?limit=1", timeout=15)
        offers = r.json()["items"]
        if not offers:
            pytest.skip("no offers to derive a load_id from")
        load_id = offers[0]["load_id"]
        r2 = s.post(f"{BASE_URL}/api/dispatch/auto-offer/{load_id}", timeout=30)
        assert r2.status_code == 200, r2.text
        d = r2.json()
        assert "offers_sent" in d
        for o in d.get("offers", [])[:2]:
            assert o["offer_id"].startswith("OF-")
            assert o["accept_url"].endswith("/accept")
            assert o["decline_url"].endswith("/decline")
            assert "expires_at" in o
            # Mocked deliveries
            if o.get("deliveries", {}).get("sms"):
                assert o["deliveries"]["sms"]["sid"].startswith("SM-mock-")
                assert o["deliveries"]["sms"]["provider"] == "twilio-mock"
            if o.get("deliveries", {}).get("email"):
                assert o["deliveries"]["email"]["id"].startswith("em-mock-")
                assert o["deliveries"]["email"]["provider"] == "resend-mock"

    def test_offers_list_and_counts(self, s):
        r = s.get(f"{BASE_URL}/api/dispatch/offers?limit=200", timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert "items" in d and "counts_by_status" in d
        for k in ("pending", "accepted", "declined", "expired"):
            assert k in d["counts_by_status"]
        # sorted desc by sent_at
        items = d["items"]
        if len(items) >= 2:
            assert items[0]["sent_at"] >= items[1]["sent_at"]

    def test_accept_and_expire_siblings(self, s):
        r = s.get(f"{BASE_URL}/api/dispatch/offers?status=pending&limit=100", timeout=20)
        pend = r.json()["items"]
        if not pend:
            pytest.skip("no pending offers to accept")
        # Find a load with multiple pending offers so we can verify sibling expiry
        by_load: dict = {}
        for o in pend:
            by_load.setdefault(o["load_id"], []).append(o)
        target = None
        for lid, olist in by_load.items():
            if len(olist) >= 2:
                target = olist
                break
        if not target:
            target = [pend[0]]
        oid = target[0]["offer_id"]
        r2 = s.post(f"{BASE_URL}/api/dispatch/offers/{oid}/accept", timeout=15)
        assert r2.status_code == 200, r2.text
        assert r2.json()["status"] == "accepted"
        # 409 on re-accept
        r3 = s.post(f"{BASE_URL}/api/dispatch/offers/{oid}/accept", timeout=15)
        assert r3.status_code == 409
        # siblings should now be expired
        if len(target) >= 2:
            for sib in target[1:]:
                rs = s.get(f"{BASE_URL}/api/dispatch/offers?limit=500", timeout=20)
                items = {o["offer_id"]: o for o in rs.json()["items"]}
                assert items[sib["offer_id"]]["status"] in ("expired", "accepted", "declined"), \
                    f"sibling {sib['offer_id']} not auto-expired"

    def test_decline_and_409(self, s):
        # Find any pending offer
        r = s.get(f"{BASE_URL}/api/dispatch/offers?status=pending&limit=50", timeout=20)
        pend = r.json()["items"]
        if not pend:
            pytest.skip("no pending offer to decline")
        oid = pend[0]["offer_id"]
        r2 = s.post(f"{BASE_URL}/api/dispatch/offers/{oid}/decline", timeout=15)
        assert r2.status_code == 200
        assert r2.json()["status"] == "declined"
        r3 = s.post(f"{BASE_URL}/api/dispatch/offers/{oid}/decline", timeout=15)
        assert r3.status_code == 409

    def test_dashboard(self, s):
        r = s.get(f"{BASE_URL}/api/dispatch/dashboard", timeout=20)
        assert r.status_code == 200
        d = r.json()
        for k in ("carriers_active", "offers_total", "offers_by_status",
                  "acceptance_rate_pct", "avg_time_to_book_sec",
                  "margin_captured_usd", "offers_last_hour", "config"):
            assert k in d, f"missing dashboard key {k}"
        for k in ("pending", "accepted", "declined", "expired"):
            assert k in d["offers_by_status"]

    def test_autopilot_disabled_skips(self, s):
        s.post(f"{BASE_URL}/api/dispatch/config",
               json={"autopilot_enabled": False}, timeout=15)
        r = s.post(f"{BASE_URL}/api/dispatch/tick", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d.get("skipped") is True
        # Restore
        s.post(f"{BASE_URL}/api/dispatch/config",
               json={"autopilot_enabled": True}, timeout=15)


# ---------------- ML ----------------
class TestML:
    def test_ml_status_shape(self, s):
        r = s.get(f"{BASE_URL}/api/dispatch/ml/status", timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("models_loaded", "training_rows_available",
                  "min_rows_to_train", "features"):
            assert k in d, f"missing ml/status key {k}"
        assert d["min_rows_to_train"] == 20
        assert len(d["features"]) == 9

    def test_ml_seed_training(self, s):
        r = s.post(f"{BASE_URL}/api/dispatch/ml/seed-training-data", timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["ok"] is True
        assert d["seeded"] == 400

    def test_ml_train(self, s):
        r = s.post(f"{BASE_URL}/api/dispatch/ml/train", timeout=90)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["trained"] is True
        assert d["rows_used"] >= 400
        assert d.get("accept_auc") is not None
        assert d["accept_auc"] >= 0.70, f"AUC too low: {d['accept_auc']}"
        assert d.get("trained_at")
        # Status now shows models_loaded=true
        r2 = s.get(f"{BASE_URL}/api/dispatch/ml/status", timeout=20)
        s2 = r2.json()
        assert s2["models_loaded"] is True
        assert s2.get("meta", {}).get("trained_at")

    def test_ml_predict(self, s):
        # Grab a load id from any offer or from aggregator
        rr = s.get(f"{BASE_URL}/api/dispatch/offers?limit=1", timeout=15)
        items = rr.json()["items"]
        if items:
            load_id = items[0]["load_id"]
        else:
            fr = s.get(f"{BASE_URL}/api/aggregator/feed?limit=1", timeout=20)
            lst = fr.json().get("items") or fr.json().get("loads") or []
            if not lst:
                pytest.skip("no loads for ML predict")
            load_id = lst[0]["load_id"]
        r = s.post(f"{BASE_URL}/api/dispatch/ml/predict/{load_id}", timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["ml_active"] is True
        assert "load" in d
        assert "ranked" in d
        assert "disqualified_count" in d
        for row in d["ranked"][:3]:
            for k in ("ml_accept_prob", "ml_suggested_rpm",
                      "ml_suggested_offer_usd", "ml_expected_margin_usd",
                      "ml_expected_value_usd"):
                assert k in row, f"missing ML row key {k}"
            assert 0.0 <= row["ml_accept_prob"] <= 1.0
        # Descending by expected value
        evs = [r["ml_expected_value_usd"] for r in d["ranked"]]
        assert evs == sorted(evs, reverse=True)

    def test_ml_explain(self, s):
        rr = s.get(f"{BASE_URL}/api/dispatch/offers?limit=1", timeout=15)
        items = rr.json()["items"]
        if items:
            load_id = items[0]["load_id"]
        else:
            fr = s.get(f"{BASE_URL}/api/aggregator/feed?limit=1", timeout=20)
            lst = fr.json().get("items") or fr.json().get("loads") or []
            load_id = lst[0]["load_id"]
        r = s.post(f"{BASE_URL}/api/dispatch/ml/explain/{load_id}", timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "used_llm" in d
        assert "rationale" in d
        assert isinstance(d["rationale"], str)
        assert 0 < len(d["rationale"]) <= 800
        assert "carrier_name" in d
        assert "top_match" in d

    def test_ml_explain_pinned_carrier(self, s):
        # Get a carrier from active list
        rc = s.get(f"{BASE_URL}/api/dispatch/carriers?active_only=true", timeout=15)
        carriers = rc.json()["items"]
        assert carriers, "no carriers"
        cid = carriers[0]["carrier_id"]
        # Pick a load
        fr = s.get(f"{BASE_URL}/api/aggregator/feed?limit=1", timeout=20)
        lst = fr.json().get("items") or fr.json().get("loads") or []
        if not lst:
            pytest.skip("no load")
        load_id = lst[0]["load_id"]
        # Ensure load persisted via tick
        s.post(f"{BASE_URL}/api/dispatch/tick", timeout=60)
        r = s.post(f"{BASE_URL}/api/dispatch/ml/explain/{load_id}?carrier_id={cid}", timeout=60)
        # Could be 200 (if carrier qualifies) or 422 (if not qualified)
        assert r.status_code in (200, 422), r.text
        if r.status_code == 200:
            d = r.json()
            # If explicitly pinned, top_match should match that carrier when qualified
            assert isinstance(d["rationale"], str) and d["rationale"]


# ---------------- Regression smoke ----------------
class TestRegressionSmoke:
    def test_aggregator_feed(self, s):
        r = s.get(f"{BASE_URL}/api/aggregator/feed?limit=3", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert "margin_summary" in d or "items" in d or "loads" in d

    def test_routing_provider(self, s):
        r = s.get(f"{BASE_URL}/api/routing/provider", timeout=15)
        assert r.status_code == 200

    def test_telematics_provider(self, s):
        r = s.get(f"{BASE_URL}/api/telematics/provider", timeout=15)
        assert r.status_code == 200

    def test_parcel_provider(self, s):
        r = s.get(f"{BASE_URL}/api/parcel/provider", timeout=15)
        assert r.status_code == 200

    def test_edi_provider(self, s):
        r = s.get(f"{BASE_URL}/api/edi/provider", timeout=15)
        assert r.status_code == 200
