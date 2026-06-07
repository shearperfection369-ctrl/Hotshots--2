"""Iter34 — Competitive TMS module (10-feature parity build)
Covers: accessorials CRUD+seed, FMCSA SAFER graceful degradation, lane analytics,
contract rates + rate-lookup, dock scheduling, mode-shift, freight audit,
spot quote requests (admin + public-portal), public RFP + bid, driver PWA 404.
"""
import os
import time
import requests
import pytest
from datetime import datetime, timezone, timedelta

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL")
            or "https://clean-logistics-dash.preview.emergentagent.com").rstrip("/")
ADMIN_TOKEN = "test_session_admin_1"
PORTAL_TOKEN = "HXACT0uXu-2TEYHG4G4otNGfLMU"
CUSTOMER_ID = "CUST-940030A27E"


@pytest.fixture(scope="session")
def s():
    sess = requests.Session()
    sess.headers.update({
        "Authorization": f"Bearer {ADMIN_TOKEN}",
        "Content-Type": "application/json",
    })
    return sess


@pytest.fixture(scope="session")
def pub():
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json"})
    return sess


# ========== B · ACCESSORIALS ==========
class TestAccessorials:
    def test_list_returns_seeded_defaults(self, s):
        r = s.get(f"{BASE_URL}/api/tms-competitive/accessorials")
        assert r.status_code == 200, r.text
        data = r.json()
        codes = {x["code"] for x in data["items"]}
        # spec says all 12 defaults
        expected = {"DET", "LMP", "LAY", "TONU", "DA", "STP",
                    "FSC", "TARP", "RES", "REWG", "INSIDE", "OVRDIM"}
        assert expected.issubset(codes), f"Missing: {expected - codes}"
        assert data["count"] >= 12

    def test_create_and_delete(self, s):
        code = f"TST{int(time.time())%100000}"
        r = s.post(f"{BASE_URL}/api/tms-competitive/accessorials",
                   json={"code": code, "label": "TEST_Acc", "rate_usd": 12.5})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["code"] == code and body["label"] == "TEST_Acc"
        acc_id = body["accessorial_id"]

        # Soft-delete
        rd = s.delete(f"{BASE_URL}/api/tms-competitive/accessorials/{acc_id}")
        assert rd.status_code == 200 and rd.json()["status"] == "deactivated"

        # Verify inactive (not in default active list)
        r2 = s.get(f"{BASE_URL}/api/tms-competitive/accessorials?active_only=true")
        assert acc_id not in [x["accessorial_id"] for x in r2.json()["items"]]


# ========== C · FMCSA ==========
class TestFmcsa:
    def test_fmcsa_graceful_on_free_webkey(self, s):
        r = s.get(f"{BASE_URL}/api/tms-competitive/fmcsa/MC-111180", timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        # FREE webKey → expect graceful error or a valid carrier result, never crash
        assert ("error" in data) or ("verdict" in data)

    def test_fmcsa_bad_mc(self, s):
        r = s.get(f"{BASE_URL}/api/tms-competitive/fmcsa/999999999", timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert ("error" in data) or ("verdict" in data)


# ========== D · LANE ANALYTICS ==========
class TestLaneAnalytics:
    def test_returns_aggregated(self, s):
        r = s.get(f"{BASE_URL}/api/tms-competitive/lane-analytics?window_days=180")
        assert r.status_code == 200, r.text
        d = r.json()
        assert "lanes" in d
        assert "network_avg_rpm" in d
        assert "total_loads" in d
        assert d["window_days"] == 180
        # Tightness in expected set
        for L in d["lanes"]:
            assert L["capacity_tightness"] in ("low", "medium", "high")
        # Sorted by loads desc
        loads = [L["loads"] for L in d["lanes"]]
        assert loads == sorted(loads, reverse=True)


# ========== E · CONTRACT RATES + LOOKUP ==========
class TestContractRates:
    def test_create_contract_and_lookup_prefers_contract(self, s):
        today = datetime.now(timezone.utc).date()
        payload = {
            "customer_id": CUSTOMER_ID,
            "origin_state": "MN",
            "destination_state": "TX",
            "equipment": "Dry Van",
            "line_haul_usd": 2750,
            "fuel_surcharge_usd": 425,
            "effective_from": (today - timedelta(days=1)).isoformat(),
            "effective_to": (today + timedelta(days=365)).isoformat(),
            "min_commit_loads": 5,
        }
        r = s.post(f"{BASE_URL}/api/tms-competitive/contract-rates", json=payload)
        assert r.status_code == 200, r.text
        ctr = r.json()
        assert ctr["customer_id"] == CUSTOMER_ID
        assert ctr["line_haul_usd"] == 2750
        ctr_id = ctr["contract_rate_id"]

        # Lookup with customer → contract
        r2 = s.get(
            f"{BASE_URL}/api/tms-competitive/rate-lookup",
            params={"origin_state": "MN", "destination_state": "TX",
                    "customer_id": CUSTOMER_ID})
        assert r2.status_code == 200
        assert r2.json()["source"] == "contract"

        # Lookup with unknown customer → spot
        r3 = s.get(
            f"{BASE_URL}/api/tms-competitive/rate-lookup",
            params={"origin_state": "MN", "destination_state": "TX",
                    "customer_id": "CUST-NOTEXIST-XYZ"})
        assert r3.status_code == 200
        assert r3.json()["source"] == "spot"

        # cleanup
        s.delete(f"{BASE_URL}/api/tms-competitive/contract-rates/{ctr_id}")


# ========== F · DOCK SCHEDULING ==========
class TestDock:
    def test_create_list_cancel(self, s):
        payload = {
            "facility_name": "TEST_Facility",
            "facility_address": "1 Test Ln",
            "scheduled_at": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
            "duration_minutes": 60,
            "appointment_type": "pickup",
        }
        r = s.post(f"{BASE_URL}/api/tms-competitive/dock-appointments", json=payload)
        assert r.status_code == 200, r.text
        appt_id = r.json()["appt_id"]

        rl = s.get(f"{BASE_URL}/api/tms-competitive/dock-appointments")
        assert rl.status_code == 200
        assert appt_id in [x["appt_id"] for x in rl.json()["items"]]

        rd = s.delete(f"{BASE_URL}/api/tms-competitive/dock-appointments/{appt_id}")
        assert rd.status_code == 200 and rd.json()["status"] == "cancelled"


# ========== G · MODE-SHIFT ==========
class TestModeShift:
    def test_intermodal_recommended_long_haul(self, s):
        r = s.post(f"{BASE_URL}/api/tms-competitive/mode-shift", json={
            "origin": "MSP", "destination": "DAL",
            "miles": 1900, "weight_lbs": 42000,
            "equipment": "Dry Van", "current_rate_usd": 4800,
        })
        assert r.status_code == 200, r.text
        d = r.json()
        modes = [o["mode"] for o in d["options"]]
        assert any("Intermodal" in m for m in modes)
        intermodal = next(o for o in d["options"] if "Intermodal" in o["mode"])
        assert intermodal["savings_usd"] > 0
        assert intermodal["added_days"] == 3


# ========== I · FREIGHT AUDIT ==========
class TestFreightAudit:
    def _create_booking(self, s, rate_con: float):
        """Create a real brokerage booking with carrier_rate_usd set."""
        # Use the existing brokerage endpoint. Need to know shape — fall back to direct.
        # Try a common endpoint and skip if not available
        payload = {
            "customer_id": CUSTOMER_ID,
            "customer_name": "TEST_Cust_Audit",
            "origin": "Minneapolis, MN",
            "destination": "Dallas, TX",
            "carrier_name": "TEST_Carrier",
            "carrier_rate_usd": rate_con,
            "customer_rate_usd": rate_con + 400,
            "miles": 940,
            "equipment": "Dry Van",
        }
        for path in ("/api/brokerage/bookings",
                     "/api/orisei/bookings",
                     "/api/bookings"):
            r = s.post(f"{BASE_URL}{path}", json=payload)
            if r.status_code in (200, 201):
                j = r.json()
                return j.get("booked_id") or j.get("booking_id") or j.get("id")
        return None

    def test_audit_red_when_over_billed(self, s):
        bid = self._create_booking(s, rate_con=2000)
        if not bid:
            pytest.skip("No way to create brokerage booking in this env to test audit")
        r = s.post(f"{BASE_URL}/api/tms-competitive/freight-audit", json={
            "booking_id": bid,
            "carrier_invoice_usd": 3500,
        })
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["verdict"] == "RED"
        assert d["diff_usd"] == 1500
        assert any(f["code"] == "OVER_BILL" for f in d["flags"])


# ========== A · SPOT-QUOTE PUBLIC + ADMIN ==========
class TestSpotQuote:
    def test_public_submit_then_admin_list_and_quote(self, s, pub):
        # Public submit (no auth)
        payload = {
            "origin": "Chicago, IL",
            "destination": "Houston, TX",
            "equipment": "Dry Van",
            "weight_lbs": 38000,
        }
        r = pub.post(
            f"{BASE_URL}/api/public/customer-portal/{PORTAL_TOKEN}/spot-quote-request",
            json=payload,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        assert body["expected_response_time_hours"] == 4
        req_id = body["request_id"]

        # Admin list
        rl = s.get(f"{BASE_URL}/api/tms-competitive/spot-quote-requests")
        assert rl.status_code == 200
        ids = [x["request_id"] for x in rl.json()["items"]]
        assert req_id in ids

        # Quote
        rq = s.post(
            f"{BASE_URL}/api/tms-competitive/spot-quote-requests/{req_id}/quote")
        assert rq.status_code == 200 and rq.json()["status"] == "quoted"

    def test_public_bad_portal_token(self, pub):
        r = pub.post(
            f"{BASE_URL}/api/public/customer-portal/INVALID-TOKEN/spot-quote-request",
            json={"origin": "A", "destination": "B"},
        )
        assert r.status_code == 404


# ========== J · RFP / RFQ ==========
class TestRfp:
    def test_create_admin_then_public_list_and_bid(self, s, pub):
        payload = {
            "shipper_name": "TEST_Shipper",
            "title": "TEST_RFP_Iter34",
            "description": "Auto-generated test RFP",
            "lanes": [
                {"origin": "Minneapolis, MN", "destination": "Dallas, TX",
                 "equipment": "Dry Van", "est_volume_per_week": 5},
                {"origin": "Chicago, IL", "destination": "Atlanta, GA",
                 "equipment": "Dry Van", "est_volume_per_week": 3},
            ],
            "submission_deadline": (datetime.now(timezone.utc)
                                    + timedelta(days=14)).isoformat(),
            "is_public": True,
        }
        r = s.post(f"{BASE_URL}/api/tms-competitive/rfps", json=payload)
        assert r.status_code == 200, r.text
        rfp = r.json()
        rfp_id = rfp["rfp_id"]
        assert rfp["status"] == "open"
        assert rfp["bid_count"] == 0

        # Public list — no auth
        rp = pub.get(f"{BASE_URL}/api/public/rfps")
        assert rp.status_code == 200
        public_ids = [x["rfp_id"] for x in rp.json()["items"]]
        assert rfp_id in public_ids

        # Public get one
        rg = pub.get(f"{BASE_URL}/api/public/rfps/{rfp_id}")
        assert rg.status_code == 200
        assert rg.json()["rfp_id"] == rfp_id

        # Public submit bid — no auth
        bid_payload = {
            "bidder_name": "TEST_Carrier_A",
            "bidder_email": "carrier@example.com",
            "bidder_mc": "MC-123456",
            "lane_rates": [
                {"lane_index": 0, "rate_per_load": 2850},
                {"lane_index": 1, "rate_per_load": 2200},
            ],
        }
        rb = pub.post(f"{BASE_URL}/api/public/rfps/{rfp_id}/bid", json=bid_payload)
        assert rb.status_code == 200, rb.text
        assert rb.json()["ok"] is True

        # bid_count incremented on rfp doc
        rget = pub.get(f"{BASE_URL}/api/public/rfps/{rfp_id}")
        assert rget.json()["bid_count"] >= 1


# ========== H · DRIVER PWA (negative only) ==========
class TestDriverPwa:
    def test_invalid_booking_or_pin_404(self, pub):
        r = pub.get(
            f"{BASE_URL}/api/driver-pwa/booking/BK-DOES-NOT-EXIST",
            params={"pin": "0000"})
        assert r.status_code == 404
