"""
Iter50 — Load Aggregator + Shipper Relations + Claims Master.

Tests cover:
  - Load Aggregator: boards, feed, prefs, pin/pins, retention policy/audit/attest
  - Shipper Relations: dashboard, accounts CRUD + dedupe, tier/activity, incentives (seed idempotent),
    rate-cards, QBRs, TMS
  - Claims Master: dashboard, file→acknowledge→decision(fast_pay/dispute/shipper_fault)→close,
    photos (upload/get binary/delete), report.pdf validity, prevention checklist + audit scoring,
    carrier watchlist (cut_recommended flag), insurance COI (status derivation)
"""
import io
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://clean-logistics-dash.preview.emergentagent.com").rstrip("/")

ADMIN_TOKEN = "test_session_admin_1"
DISPATCHER_TOKEN = "test_session_dispatcher_1"


def _auth(token=ADMIN_TOKEN):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


# ===========================================================
#                LOAD AGGREGATOR
# ===========================================================
class TestLoadAggregator:
    def test_boards_returns_list_with_retention(self):
        r = _auth().get(f"{BASE_URL}/api/aggregator/boards")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "items" in data and "count" in data
        assert data["count"] >= 5, f"Expected >=5 boards, got {data['count']}"
        items = data["items"]
        # At least some boards should have retention info attached (dat + truckstop always overlap)
        with_retention = [b for b in items if "retention_months" in b]
        assert len(with_retention) >= 2, f"Expected >=2 boards w/ retention_months, got {len(with_retention)}"

    def test_feed_returns_scored_deduped_items(self):
        r = _auth().get(f"{BASE_URL}/api/aggregator/feed?limit=50")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "items" in data
        assert "boards_polled" in data
        assert isinstance(data["items"], list)
        if data["items"]:
            item = data["items"][0]
            for k in ("board_id", "board_name", "board_color", "score"):
                assert k in item, f"Missing {k} in feed item"
            assert 0 <= item["score"] <= 100

    def test_feed_filter_min_rate_per_mile(self):
        r = _auth().get(f"{BASE_URL}/api/aggregator/feed?min_rate_per_mile=2.0&limit=100")
        assert r.status_code == 200
        for it in r.json()["items"]:
            rpm = it.get("rate_per_mile") or 0
            assert rpm >= 2.0, f"Filter min_rate_per_mile broken; got rpm={rpm}"

    def test_feed_filter_boards_csv(self):
        r = _auth().get(f"{BASE_URL}/api/aggregator/feed?boards_csv=dat&limit=100")
        assert r.status_code == 200
        data = r.json()
        assert data["boards_polled"] == ["dat"]

    def test_prefs_roundtrip(self):
        c = _auth()
        payload = {"equipment": ["V", "R"], "min_rate_per_mile": 1.75, "exclude_hazmat": True}
        r = c.post(f"{BASE_URL}/api/aggregator/prefs", json=payload)
        assert r.status_code == 200
        r2 = c.get(f"{BASE_URL}/api/aggregator/prefs")
        assert r2.status_code == 200
        p = r2.json()
        assert p.get("min_rate_per_mile") == 1.75
        assert p.get("exclude_hazmat") is True
        assert "V" in p.get("equipment", [])

    def test_pin_lifecycle(self):
        c = _auth()
        pin = c.post(f"{BASE_URL}/api/aggregator/pin",
                     json={"load_id": f"L-{uuid.uuid4().hex[:6]}", "board_id": "dat", "reason": "TEST_pin"})
        assert pin.status_code == 200, pin.text
        pin_id = pin.json()["pin_id"]
        lst = c.get(f"{BASE_URL}/api/aggregator/pins")
        assert lst.status_code == 200
        assert any(p["pin_id"] == pin_id for p in lst.json()["items"])
        rm = c.delete(f"{BASE_URL}/api/aggregator/pins/{pin_id}")
        assert rm.status_code == 200
        lst2 = c.get(f"{BASE_URL}/api/aggregator/pins")
        assert not any(p["pin_id"] == pin_id for p in lst2.json()["items"])

    def test_retention_policy_has_6_boards(self):
        r = _auth().get(f"{BASE_URL}/api/aggregator/retention/policy")
        assert r.status_code == 200
        ids = {b["board_id"] for b in r.json()["items"]}
        for expected in ("dat", "truckstop", "direct_edi", "spot_rate", "smartway", "eld"):
            assert expected in ids, f"retention/policy missing {expected}"

    def test_retention_audit_and_attest(self):
        c = _auth()
        audit1 = c.get(f"{BASE_URL}/api/aggregator/retention/audit")
        assert audit1.status_code == 200
        # each item must have status field
        for it in audit1.json()["items"]:
            assert "status" in it
        # attest as admin
        att = c.post(f"{BASE_URL}/api/aggregator/retention/attest",
                     json={"board_id": "dat", "finding": "TEST_iter50 attest ok", "is_compliant": True,
                           "attester_name": "TEST_iter50"})
        assert att.status_code == 200, att.text
        # audit should now mark dat COMPLIANT
        audit2 = c.get(f"{BASE_URL}/api/aggregator/retention/audit")
        by_id = {i["board_id"]: i for i in audit2.json()["items"]}
        assert by_id["dat"]["status"] == "COMPLIANT"


# ===========================================================
#                SHIPPER RELATIONS
# ===========================================================
@pytest.fixture(scope="module")
def sr_account_id():
    """Create a unique shipper account for downstream tests."""
    c = _auth()
    unique = f"TEST_Shipper_{uuid.uuid4().hex[:8]}"
    r = c.post(f"{BASE_URL}/api/shipper-relations/accounts", json={
        "company_name": unique, "industry": "Retail", "hq_state": "TX",
        "contact_email": "test@example.com", "annual_volume_loads": 200,
        "annual_revenue_usd": 750000, "lifecycle": "qualified",
    })
    assert r.status_code == 200, r.text
    aid = r.json()["account_id"]
    yield aid


class TestShipperRelations:
    def test_dashboard(self):
        r = _auth().get(f"{BASE_URL}/api/shipper-relations/dashboard")
        assert r.status_code == 200
        d = r.json()
        assert "totals" in d and "pipeline" in d and "portfolio" in d
        for k in ("accounts", "rate_cards", "incentive_programs", "qbrs", "tms_integrations"):
            assert k in d["totals"]

    def test_create_dedupe(self, sr_account_id):
        # Fetch the account to get the exact company_name (already unique)
        r = _auth().get(f"{BASE_URL}/api/shipper-relations/accounts")
        name = None
        for a in r.json()["items"]:
            if a["account_id"] == sr_account_id:
                name = a["company_name"]
                break
        assert name
        dup = _auth().post(f"{BASE_URL}/api/shipper-relations/accounts",
                           json={"company_name": name, "lifecycle": "lead"})
        assert dup.status_code == 409, f"Expected 409 dedupe, got {dup.status_code} {dup.text}"

    def test_patch_account(self, sr_account_id):
        r = _auth().patch(f"{BASE_URL}/api/shipper-relations/accounts/{sr_account_id}",
                          json={"contact_phone": "555-1234", "notes": "TEST_iter50 patch"})
        assert r.status_code == 200
        # patch endpoint returns 360 payload with 'account' key
        acct = r.json().get("account") or r.json()
        assert acct.get("contact_phone") == "555-1234"

    def test_tier_and_activity(self, sr_account_id):
        c = _auth()
        r1 = c.post(f"{BASE_URL}/api/shipper-relations/accounts/{sr_account_id}/tier",
                    json={"lifecycle": "active", "reason": "TEST_iter50 promotion"})
        assert r1.status_code == 200
        r2 = c.post(f"{BASE_URL}/api/shipper-relations/accounts/{sr_account_id}/activity",
                    json={"kind": "call", "summary": "TEST_iter50 discovery call",
                          "outcome": "positive", "next_step": "send proposal"})
        assert r2.status_code == 200
        # 360 view has activity entries
        r3 = c.get(f"{BASE_URL}/api/shipper-relations/accounts/{sr_account_id}")
        assert r3.status_code == 200
        v = r3.json()
        assert v["account"]["lifecycle"] == "active"
        assert any(a["summary"].startswith("TEST_iter50") for a in v["activity"])

    def test_seed_incentive_catalog_idempotent(self):
        c = _auth()
        r1 = c.post(f"{BASE_URL}/api/shipper-relations/seed-incentive-catalog")
        assert r1.status_code == 200
        # 2nd call must insert 0
        r2 = c.post(f"{BASE_URL}/api/shipper-relations/seed-incentive-catalog")
        assert r2.status_code == 200
        assert r2.json()["inserted"] == 0

    def test_incentive_crud_and_assign(self, sr_account_id):
        c = _auth()
        # Create new incentive
        r = c.post(f"{BASE_URL}/api/shipper-relations/incentives", json={
            "name": f"TEST_iter50 Bonus {uuid.uuid4().hex[:6]}",
            "kind": "volume_rebate", "threshold_loads": 50,
            "reward_type": "rebate_pct", "reward_value": 1.5, "frequency": "quarterly",
        })
        assert r.status_code == 200
        inc_id = r.json()["incentive_id"]
        # Assign
        a = c.post(f"{BASE_URL}/api/shipper-relations/accounts/{sr_account_id}/assign-incentive",
                   json={"incentive_id": inc_id})
        assert a.status_code == 200
        v = c.get(f"{BASE_URL}/api/shipper-relations/accounts/{sr_account_id}").json()
        assert any(i["incentive_id"] == inc_id for i in v["incentives"])
        # Unassign
        u = c.delete(f"{BASE_URL}/api/shipper-relations/accounts/{sr_account_id}/incentives/{inc_id}")
        assert u.status_code == 200
        # Delete incentive
        d = c.delete(f"{BASE_URL}/api/shipper-relations/incentives/{inc_id}")
        assert d.status_code == 200

    def test_rate_card_crud(self):
        c = _auth()
        r = c.post(f"{BASE_URL}/api/shipper-relations/rate-cards", json={
            "name": f"TEST_iter50 RateCard {uuid.uuid4().hex[:6]}",
            "equipment": "V", "base_rpm": 2.15, "fuel_surcharge_pct": 12,
            "valid_from": "2026-01-01",
            "tiers": [
                {"min_loads_per_month": 25, "discount_pct": 2},
                {"min_loads_per_month": 100, "discount_pct": 5},
            ],
        })
        assert r.status_code == 200, r.text
        rc_id = r.json()["rate_card_id"]
        # Delete cleanup
        d = c.delete(f"{BASE_URL}/api/shipper-relations/rate-cards/{rc_id}")
        assert d.status_code == 200

    def test_qbr_creation(self, sr_account_id):
        c = _auth()
        r = c.post(f"{BASE_URL}/api/shipper-relations/accounts/{sr_account_id}/qbr", json={
            "period": "Q1 2026", "otd_pct": 97.5, "otp_pct": 96.0,
            "damage_free_pct": 99.1, "volume_loads": 42, "revenue_usd": 90000, "nps_score": 60,
            "strengths": "TEST_iter50 strengths", "gaps": "TEST_iter50 gaps",
            "action_items": ["Improve OTP"],
        })
        assert r.status_code == 200
        lst = c.get(f"{BASE_URL}/api/shipper-relations/accounts/{sr_account_id}/qbrs")
        assert lst.status_code == 200
        assert lst.json()["count"] >= 1

    def test_tms_integration_lifecycle(self, sr_account_id):
        c = _auth()
        r = c.post(f"{BASE_URL}/api/shipper-relations/accounts/{sr_account_id}/tms", json={
            "system": "MercuryGate", "method": "api", "status": "planned",
            "notes": "TEST_iter50",
        })
        assert r.status_code == 200
        tms_id = r.json()["tms_id"]
        lst = c.get(f"{BASE_URL}/api/shipper-relations/accounts/{sr_account_id}/tms")
        assert any(t["tms_id"] == tms_id for t in lst.json()["items"])
        rm = c.delete(f"{BASE_URL}/api/shipper-relations/accounts/{sr_account_id}/tms/{tms_id}")
        assert rm.status_code == 200


# ===========================================================
#                CLAIMS MASTER
# ===========================================================
@pytest.fixture(scope="module")
def claim_id():
    r = _auth().post(f"{BASE_URL}/api/claims/claims", json={
        "shipper_name": f"TEST_Shipper_{uuid.uuid4().hex[:6]}",
        "carrier_mc": "MC-TEST-50", "carrier_name": "TEST_Carrier_50",
        "kind": "damage", "claim_amount_usd": 2500,
        "description": "TEST_iter50 · pallet damaged in transit",
        "origin": "Dallas, TX", "destination": "Atlanta, GA",
    })
    assert r.status_code == 200, r.text
    cid = r.json()["claim_id"]
    yield cid


class TestClaimsMaster:
    def test_dashboard(self):
        r = _auth().get(f"{BASE_URL}/api/claims/dashboard")
        assert r.status_code == 200
        d = r.json()
        for k in ("totals", "by_status", "by_kind", "top_shippers", "carrier_watchlist", "reserve"):
            assert k in d, f"Missing dashboard field {k}"

    def test_file_claim_has_sla_deadline(self, claim_id):
        r = _auth().get(f"{BASE_URL}/api/claims/claims/{claim_id}")
        assert r.status_code == 200
        c = r.json()["claim"]
        assert "sla_deadline_at" in c
        assert c["sla_hours_remaining"] is not None
        # Freshly filed → ~24h remaining (allow a couple of hours slack)
        assert 20 <= c["sla_hours_remaining"] <= 25, f"sla_hours_remaining={c['sla_hours_remaining']}"

    def test_acknowledge_stops_timer(self, claim_id):
        c = _auth()
        r = c.post(f"{BASE_URL}/api/claims/claims/{claim_id}/acknowledge",
                   json={"ack_note": "TEST_iter50 ack"})
        assert r.status_code == 200
        info = c.get(f"{BASE_URL}/api/claims/claims/{claim_id}").json()["claim"]
        assert info.get("acknowledged_at")
        assert info["sla_hours_remaining"] is None

    def test_decision_dispute_moves_to_investigating(self):
        c = _auth()
        f = c.post(f"{BASE_URL}/api/claims/claims", json={
            "shipper_name": f"TEST_Dispute_{uuid.uuid4().hex[:6]}",
            "carrier_mc": "MC-DIS-50", "kind": "shortage", "claim_amount_usd": 800,
            "description": "TEST_iter50 dispute",
        })
        cid = f.json()["claim_id"]
        d = c.post(f"{BASE_URL}/api/claims/claims/{cid}/decision",
                   json={"outcome": "dispute", "payout_usd": 0,
                         "reasoning": "TEST_iter50 evidence unclear"})
        assert d.status_code == 200
        assert d.json()["status"] == "investigating"

    def test_decision_shipper_fault_denies(self):
        c = _auth()
        f = c.post(f"{BASE_URL}/api/claims/claims", json={
            "shipper_name": f"TEST_ShipFault_{uuid.uuid4().hex[:6]}",
            "carrier_mc": "MC-SF-50", "kind": "damage", "claim_amount_usd": 300,
            "description": "TEST_iter50 shipper caused",
        })
        cid = f.json()["claim_id"]
        d = c.post(f"{BASE_URL}/api/claims/claims/{cid}/decision",
                   json={"outcome": "shipper_fault", "payout_usd": 0,
                         "reasoning": "TEST_iter50 shipper loaded improperly"})
        assert d.status_code == 200
        assert d.json()["status"] == "denied"

    def test_decision_fast_pay_marks_paid(self, claim_id):
        r = _auth().post(f"{BASE_URL}/api/claims/claims/{claim_id}/decision",
                         json={"outcome": "fast_pay", "payout_usd": 500,
                               "reasoning": "TEST_iter50 carrier liable, fast pay"})
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "paid"

    def test_comm_logged(self, claim_id):
        r = _auth().post(f"{BASE_URL}/api/claims/claims/{claim_id}/comms",
                         json={"channel": "email", "direction": "outbound",
                               "with_party": "shipper", "summary": "TEST_iter50 email to shipper"})
        assert r.status_code == 200
        assert r.json()["channel"] == "email"

    def test_photo_lifecycle(self, claim_id):
        # Create small JPEG in-memory (1x1 red pixel)
        from PIL import Image
        buf = io.BytesIO()
        Image.new("RGB", (10, 10), (255, 0, 0)).save(buf, "JPEG")
        buf.seek(0)
        c = _auth()
        up = c.post(
            f"{BASE_URL}/api/claims/claims/{claim_id}/photos",
            files={"file": ("t.jpg", buf, "image/jpeg")},
            data={"caption": "TEST_iter50 photo", "kind": "damage"},
        )
        assert up.status_code == 200, up.text
        pid = up.json()["photo_id"]
        lst = c.get(f"{BASE_URL}/api/claims/claims/{claim_id}/photos")
        assert any(p["photo_id"] == pid for p in lst.json()["items"])
        # Binary fetch
        b = c.get(f"{BASE_URL}/api/claims/claims/{claim_id}/photos/{pid}")
        assert b.status_code == 200
        assert b.headers.get("content-type", "").startswith("image/jpeg")
        assert len(b.content) > 100
        rm = c.delete(f"{BASE_URL}/api/claims/claims/{claim_id}/photos/{pid}")
        assert rm.status_code == 200

    def test_report_pdf_generation(self, claim_id):
        r = _auth().get(f"{BASE_URL}/api/claims/claims/{claim_id}/report.pdf")
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:5] == b"%PDF-", "PDF magic bytes missing"
        assert len(r.content) > 5000, f"PDF suspiciously small: {len(r.content)}"

    def test_close_claim(self):
        c = _auth()
        f = c.post(f"{BASE_URL}/api/claims/claims", json={
            "shipper_name": f"TEST_Close_{uuid.uuid4().hex[:6]}",
            "carrier_mc": "MC-CLS-50", "kind": "delay", "claim_amount_usd": 100,
            "description": "TEST_iter50 close flow",
        })
        cid = f.json()["claim_id"]
        r = c.post(f"{BASE_URL}/api/claims/claims/{cid}/close",
                   json={"resolution": "TEST_iter50 resolved amicably", "final_payout_usd": 75})
        assert r.status_code == 200
        info = c.get(f"{BASE_URL}/api/claims/claims/{cid}").json()["claim"]
        assert info["status"] == "closed"
        assert info["final_payout_usd"] == 75
        assert info.get("closed_at")

    def test_prevention_checklist_and_audit(self):
        c = _auth()
        r = c.get(f"{BASE_URL}/api/claims/prevention/checklist")
        assert r.status_code == 200
        checklist = r.json()["checklist"]
        assert len(checklist) == 8
        keys = {i["key"] for i in checklist}
        assert "load_agreement_signed" in keys and "seal_intact_verified" in keys

        # Score 100% audit
        load_id = f"L-TEST-{uuid.uuid4().hex[:6]}"
        a = c.post(f"{BASE_URL}/api/claims/prevention/audits", json={
            "load_id": load_id,
            "load_agreement_signed": True, "windows_documented": True,
            "equipment_condition_ok": True, "load_securement_ok": True,
            "pickup_photos_taken": True, "delivery_photos_taken": True,
            "carrier_coi_current": True, "seal_intact_verified": True,
        })
        assert a.status_code == 200
        assert a.json()["score_pct"] == 100.0
        assert a.json()["passed_count"] == 8

    def test_carrier_watchlist_cut_recommended(self):
        # Ensure at least 2 claims exist for a specific carrier MC
        c = _auth()
        mc = f"MC-WATCH-{uuid.uuid4().hex[:4]}"
        for i in range(2):
            c.post(f"{BASE_URL}/api/claims/claims", json={
                "shipper_name": f"TEST_watch_shipper_{i}",
                "carrier_mc": mc, "kind": "damage", "claim_amount_usd": 100,
                "description": f"TEST_iter50 watchlist #{i}",
            })
        w = c.get(f"{BASE_URL}/api/claims/carriers/watchlist")
        assert w.status_code == 200
        row = next((r for r in w.json()["items"] if r["carrier_mc"] == mc), None)
        assert row is not None, "Test carrier missing from watchlist"
        assert row["cut_recommended"] is True

    def test_insurance_coi_status(self):
        from datetime import datetime, timezone, timedelta
        c = _auth()
        # Expired
        r1 = c.post(f"{BASE_URL}/api/claims/insurance/verifications", json={
            "carrier_mc": f"MC-COI-EXP-{uuid.uuid4().hex[:4]}",
            "coverage_usd": 1_000_000,
            "effective_date": "2020-01-01",
            "expiration_date": (datetime.now(timezone.utc) - timedelta(days=10)).date().isoformat(),
        })
        assert r1.status_code == 200
        # Current
        r2 = c.post(f"{BASE_URL}/api/claims/insurance/verifications", json={
            "carrier_mc": f"MC-COI-CUR-{uuid.uuid4().hex[:4]}",
            "coverage_usd": 1_000_000,
            "effective_date": "2025-01-01",
            "expiration_date": (datetime.now(timezone.utc) + timedelta(days=90)).date().isoformat(),
        })
        assert r2.status_code == 200
        lst = c.get(f"{BASE_URL}/api/claims/insurance/verifications")
        assert lst.status_code == 200
        # Ensure statuses computed
        statuses = {r["status"] for r in lst.json()["items"] if "status" in r}
        assert "expired" in statuses
        assert "current" in statuses
