"""iter64 — Revenue Stack + AI Sentinel + Sandbox market realism."""
import os
import time

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://clean-logistics-dash.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
TOK = "test_session_admin_1"
AUTH = {"Authorization": f"Bearer {TOK}", "Content-Type": "application/json"}
JSON = {"Content-Type": "application/json"}


# ---------------- Instant Quote Engine ----------------
class TestQuoteEngine:
    def test_headhaul_lane_LA_to_Detroit(self):
        r = requests.post(f"{API}/revenue/quotes", headers=AUTH, json={
            "origin": "Los Angeles, CA", "destination": "Detroit, MI",
            "equipment": "Van", "company": "TEST_HeadhaulCo", "email": "test@x.com",
        }, timeout=30)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["quote_id"].startswith("Q-")
        p = j["pricing"]
        assert p["lane_mult"] > 1.0, f"CA outbound should be headhaul >1 got {p['lane_mult']}"
        assert p["sell_usd"] > p["buy_usd"]
        assert p["margin_usd"] > 0
        assert "margin_pct" in p
        pytest.headhaul_qid = j["quote_id"]

    def test_backhaul_lane_Miami_to_Chicago(self):
        r = requests.post(f"{API}/revenue/quotes", headers=AUTH, json={
            "origin": "Miami, FL", "destination": "Chicago, IL",
            "equipment": "Van", "company": "TEST_BackhaulCo", "email": "b@x.com",
        }, timeout=30)
        assert r.status_code == 200, r.text
        p = r.json()["pricing"]
        assert p["headhaul"] == "backhaul", f"got {p['headhaul']}"
        assert p["lane_mult"] < 0.92, f"FL outbound should be discounted got {p['lane_mult']}"

    def test_email_parse_llm(self):
        r = requests.post(f"{API}/revenue/quotes/parse", headers=AUTH, json={
            "email_text": ("Hi, need a reefer Miami FL to Chicago IL next Tuesday, "
                           "38000 lbs frozen produce, quote please - Dana, Fresh Farms, dana@freshfarms.com")
        }, timeout=90)
        assert r.status_code == 200, r.text
        j = r.json()
        assert "parsed" in j and "quote" in j
        assert j["quote"]["pricing"]["equipment"] == "Reefer"
        pytest.email_qid = j["quote"]["quote_id"]

    def test_quote_pdf(self):
        qid = getattr(pytest, "headhaul_qid", None)
        assert qid
        r = requests.get(f"{API}/revenue/quotes/{qid}/pdf",
                         headers={"Authorization": f"Bearer {TOK}"}, timeout=30)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert len(r.content) > 10_000
        assert r.content[:4] == b"%PDF"

    def test_send_quote_queues(self):
        qid = getattr(pytest, "headhaul_qid", None)
        r = requests.post(f"{API}/revenue/quotes/{qid}/send", headers=AUTH, json={}, timeout=60)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["status"] == "queued_awaiting_key"
        # queue must show it
        q = requests.get(f"{API}/revenue/outreach/queue", headers=AUTH, timeout=15).json()
        assert any(i.get("ref") == qid for i in q["items"])

    def test_won_auto_posts_marketplace(self):
        qid = getattr(pytest, "headhaul_qid", None)
        r = requests.post(f"{API}/revenue/quotes/{qid}/status", headers=AUTH,
                          json={"status": "won"}, timeout=15)
        assert r.status_code == 200, r.text
        j = r.json()
        mkt = j.get("marketplace_load")
        assert mkt and mkt.get("mkt_id", "").startswith("ML-")
        pytest.mkt_id = mkt["mkt_id"]
        # visible in list
        ml = requests.get(f"{API}/revenue/marketplace/loads", headers=AUTH, timeout=15).json()
        assert any(x["mkt_id"] == pytest.mkt_id for x in ml["items"])


# ---------------- Public loadboard ----------------
class TestPublicMarketplace:
    def test_public_loadboard_hides_margin(self):
        r = requests.get(f"{API}/public/revenue/loadboard", timeout=15)
        assert r.status_code == 200
        items = r.json()["items"]
        assert items, "expected at least one open load"
        for i in items:
            assert "sell_usd" not in i
            assert "margin_usd" not in i
            assert "book_now_usd" in i

    def test_public_book_flow(self):
        # find an open load
        board = requests.get(f"{API}/public/revenue/loadboard", timeout=15).json()["items"]
        mkt_id = getattr(pytest, "mkt_id", None) or board[0]["mkt_id"]
        pytest.book_mkt_id = mkt_id
        r = requests.post(f"{API}/public/revenue/loadboard/{mkt_id}/book",
                          headers=JSON, json={
                              "mc_number": "123456", "company": "TEST_Carrier LLC",
                              "contact": "Joe", "email": "joe@carrier.com",
                          }, timeout=15)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j.get("confirm_code") and j.get("ratecon_url")
        pytest.confirm_code = j["confirm_code"]
        pytest.mb_id = j["mb_id"]
        pytest.ratecon_url = j["ratecon_url"]

    def test_ratecon_pdf_ok_and_wrong_code(self):
        mb = pytest.mb_id
        # good code
        r = requests.get(f"{BASE_URL}/api/public/revenue/bookings/{mb}/ratecon.pdf?code={pytest.confirm_code}", timeout=30)
        assert r.status_code == 200
        assert r.content[:4] == b"%PDF"
        # bad code
        r2 = requests.get(f"{BASE_URL}/api/public/revenue/bookings/{mb}/ratecon.pdf?code=WRONG123", timeout=15)
        assert r2.status_code == 403

    def test_brokerage_booking_row_created(self):
        # verify via quickpay eligible or list. We'll check quickpay/program eligible bookings
        r = requests.get(f"{API}/revenue/quickpay/program", headers=AUTH, timeout=15)
        assert r.status_code == 200
        elig = r.json()["eligible_bookings"]
        # at least one booking with source marketplace-esque naming
        found = [b for b in elig if b["booked_id"].startswith("BK-MKT")]
        assert found, "expected a booking with BK-MKT prefix from marketplace book"
        pytest.qp_booked_id = found[0]["booked_id"]
        pytest.qp_carrier_rate = float(found[0]["carrier_rate_usd"])

    def test_public_shipper_quote(self):
        r = requests.post(f"{API}/public/revenue/quote", headers=JSON, json={
            "company": "TEST_Shipper", "contact": "Sam", "email": "sam@x.com",
            "origin": "Dallas, TX", "destination": "Atlanta, GA", "equipment": "Van",
        }, timeout=30)
        assert r.status_code == 200
        j = r.json()
        assert j["all_in_rate_usd"] > 0 and j["quote_id"] and j["valid_until"]

    def test_public_quote_invalid_city_returns_422(self):
        r = requests.post(f"{API}/public/revenue/quote", headers=JSON, json={
            "company": "TEST", "contact": "x", "email": "x@x.com",
            "origin": "Nowhere", "destination": "Atlanta, GA",
        }, timeout=15)
        assert r.status_code == 422, r.text


# ---------------- Prospects ----------------
class TestProspects:
    def test_manual_add(self):
        r = requests.post(f"{API}/revenue/prospects", headers=AUTH, json={
            "company": "TEST_Acme Manual", "contact_name": "Bob",
            "email": "bob@testacme.com", "est_loads_week": 4,
        }, timeout=15)
        assert r.status_code == 200
        j = r.json()
        assert j["prospect_id"].startswith("P-")
        pytest.prospect_id = j["prospect_id"]

    def test_csv_import(self):
        r = requests.post(f"{API}/revenue/prospects/import", headers=AUTH, json={
            "csv_text": "company,contact_name,email\nTEST_Acme Foods,Bob,bob@acme.com"
        }, timeout=15)
        assert r.status_code == 200
        assert r.json()["imported"] == 1

    def test_sequence_llm(self):
        pid = pytest.prospect_id
        r = requests.post(f"{API}/revenue/prospects/{pid}/sequence", headers=AUTH, timeout=90)
        assert r.status_code == 200, r.text
        j = r.json()
        seq = j["sequence"]
        assert len(seq) == 3
        # first touch queued (email present)
        assert seq[0]["status"] in ("queued_awaiting_key", "sent", "scheduled")

    def test_ai_generate_prospects(self):
        r = requests.post(f"{API}/revenue/prospects/generate", headers=AUTH,
                          json={"region": "Midwest", "industry": "food", "count": 3}, timeout=90)
        assert r.status_code == 200, r.text
        assert len(r.json()["created"]) >= 1


# ---------------- QuickPay ----------------
class TestQuickPay:
    def test_quickpay_program(self):
        r = requests.get(f"{API}/revenue/quickpay/program", headers=AUTH, timeout=15)
        assert r.status_code == 200
        assert "eligible_bookings" in r.json()

    def test_quickpay_request_and_fee(self):
        bid = getattr(pytest, "qp_booked_id", None)
        assert bid, "no marketplace booking id"
        r = requests.post(f"{API}/revenue/quickpay/request", headers=AUTH,
                          json={"booked_id": bid, "tier": "same_day"}, timeout=15)
        assert r.status_code == 200, r.text
        j = r.json()
        expected_fee = round(pytest.qp_carrier_rate * 0.035, 2)
        assert abs(j["fee_usd"] - expected_fee) < 0.05
        pytest.qp_id = j["qp_id"]

    def test_quickpay_duplicate_409(self):
        bid = pytest.qp_booked_id
        r = requests.post(f"{API}/revenue/quickpay/request", headers=AUTH,
                          json={"booked_id": bid, "tier": "same_day"}, timeout=15)
        assert r.status_code == 409

    def test_quickpay_mark_paid(self):
        r = requests.post(f"{API}/revenue/quickpay/{pytest.qp_id}/mark-paid",
                          headers=AUTH, json={}, timeout=15)
        assert r.status_code == 200


# ---------------- Dashboard ----------------
class TestRevenueDashboard:
    def test_dashboard_aggregation(self):
        r = requests.get(f"{API}/revenue/dashboard", headers=AUTH, timeout=15)
        assert r.status_code == 200
        j = r.json()
        for k in ("quotes", "prospects", "marketplace", "quickpay"):
            assert k in j
        assert "win_rate" in j["quotes"]
        assert "by_stage" in j["prospects"]
        assert "spread_earned" in j["quickpay"]


# ---------------- Sentinel ----------------
class TestSentinel:
    def test_fire_test_alert(self):
        r = requests.post(f"{API}/alerts/test", headers=AUTH, timeout=90)
        assert r.status_code == 200, r.text
        a = r.json()["alert"]
        assert a["alert_id"].startswith("AL-")
        assert a["severity"] == "critical"
        assert "ai_brief" in a and a["ai_brief"]
        pytest.alert_id = a["alert_id"]

    def test_scan_returns_open(self):
        r = requests.post(f"{API}/alerts/scan", headers=AUTH, timeout=30)
        assert r.status_code == 200
        j = r.json()
        assert "open_alerts" in j
        assert any(a["alert_id"] == pytest.alert_id for a in j["open_alerts"])

    def test_ack_then_resolve(self):
        aid = pytest.alert_id
        r1 = requests.post(f"{API}/alerts/{aid}/ack", headers=AUTH, json={}, timeout=15)
        assert r1.status_code == 200
        r2 = requests.post(f"{API}/alerts/{aid}/resolve", headers=AUTH, json={}, timeout=15)
        assert r2.status_code == 200

    def test_settings_roundtrip(self):
        payload = {"email": "test-alerts@x.com", "phone": "+15551230000", "min_severity": "medium"}
        r = requests.post(f"{API}/alerts/settings", headers=AUTH, json=payload, timeout=15)
        assert r.status_code == 200
        g = requests.get(f"{API}/alerts/settings", headers=AUTH, timeout=15).json()
        assert g["email"] == payload["email"]
        assert g["phone"] == payload["phone"]
        assert g["min_severity"] == "medium"
        # restore
        requests.post(f"{API}/alerts/settings", headers=AUTH,
                      json={"email": "", "phone": "", "min_severity": "high"}, timeout=15)


# ---------------- Sandbox market realism ----------------
class TestSandboxMarket:
    def test_sim_market_object_on_loads(self):
        # reset + start
        r = requests.post(f"{API}/sim/reset", headers=AUTH, timeout=15)
        assert r.status_code == 200, r.text
        r = requests.post(f"{API}/sim/start", headers=AUTH, json={}, timeout=15)
        assert r.status_code == 200, r.text
        for _ in range(3):
            requests.post(f"{API}/sim/tick", headers=AUTH, json={}, timeout=15)
            time.sleep(0.2)
        state = requests.get(f"{API}/sim/state", headers=AUTH, timeout=15).json()
        loads = state.get("loads") or state.get("open_loads") or []
        assert loads, f"no loads present in state keys={list(state.keys())}"
        with_market = [l for l in loads if isinstance(l.get("market"), dict)]
        assert with_market, "expected loads to have 'market' object"
        m = with_market[0]["market"]
        for k in ("lane_mult", "seasonal_mult", "headhaul"):
            assert k in m
        assert m["headhaul"] in ("headhaul", "backhaul", "balanced")
