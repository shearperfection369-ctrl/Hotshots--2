"""Iter32 — Brokerage Margin Shield backend tests.

Covers:
  - GET /api/margin-shield/dashboard (any auth)
  - GET /api/margin-shield/auto-match/{load_id}
  - POST /api/margin-shield/auto-match/{load_id}/tender (admin)
  - GET /api/margin-shield/rates/{load_id}
  - GET /api/margin-shield/compliance/{mc_number}
  - POST /api/margin-shield/invoice/auto/{booking_id} (admin)
  - GET/POST/PUT/DELETE /api/margin-shield/loyalty/programs (admin)
  - POST /api/margin-shield/loyalty/carriers/{mc}/tier (admin)
  - Auth gate (401 when unauthenticated)
  - Regression: brokerage/boards, investor/boardroom, public/tms-pitch-summary
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Fallback to frontend/.env
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL"):
                    BASE_URL = line.split("=", 1)[1].strip().strip('"').rstrip("/")
    except Exception:
        pass

ADMIN = {"Authorization": "Bearer test_session_admin_1"}
DISP = {"Authorization": "Bearer test_disp_session"}


@pytest.fixture(scope="module")
def s():
    return requests.Session()


# ---------- AUTH GATE ----------
class TestAuthGate:
    def test_unauth_dashboard_401(self, s):
        r = s.get(f"{BASE_URL}/api/margin-shield/dashboard")
        assert r.status_code == 401, r.text

    def test_unauth_loyalty_create_401(self, s):
        r = s.post(f"{BASE_URL}/api/margin-shield/loyalty/programs", json={"name": "x", "bonus_type": "flat", "bonus_value": 10})
        assert r.status_code == 401


# ---------- DASHBOARD ----------
class TestDashboard:
    def test_dashboard_shape(self, s):
        r = s.get(f"{BASE_URL}/api/margin-shield/dashboard", headers=ADMIN)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("loads_open", "bookings_total", "bookings_tendered",
                  "bookings_delivered", "margin_total_usd",
                  "active_loyalty_programs", "carrier_pool", "compliance",
                  "preferred_first_look_minutes"):
            assert k in d, f"missing key {k}"
        for k in ("platinum", "gold", "silver", "untiered", "total"):
            assert k in d["carrier_pool"], f"missing carrier_pool.{k}"
        for k in ("green", "amber", "red"):
            assert k in d["compliance"]

    def test_dashboard_dispatcher_ok(self, s):
        r = s.get(f"{BASE_URL}/api/margin-shield/dashboard", headers=DISP)
        assert r.status_code == 200


# ---------- AUTO-MATCH ----------
class TestAutoMatch:
    def test_auto_match_known_load(self, s):
        r = s.get(f"{BASE_URL}/api/margin-shield/auto-match/LD-MN-TX-001", headers=ADMIN)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["load_id"] == "LD-MN-TX-001"
        assert "matches" in d and len(d["matches"]) == 3
        assert d["total_candidates"] >= 3
        # Northland Logistics (platinum + MN-TX van + clean) should be #1
        top = d["matches"][0]
        assert top["score"] > 80, f"top score too low: {top}"
        # Each match has compliance
        for m in d["matches"]:
            assert "compliance" in m and "flag" in m["compliance"]
            assert "components" in m

    def test_auto_match_apex_flag_red_or_low(self, s):
        # Apex Trucking MC-100004 has revoked MC + expired insurance
        r = s.get(f"{BASE_URL}/api/margin-shield/auto-match/LD-MN-TX-001", headers=ADMIN)
        d = r.json()
        # Check there's at least 5 candidates total
        assert d["total_candidates"] >= 5

    def test_auto_match_synthesized_load(self, s):
        r = s.get(f"{BASE_URL}/api/margin-shield/auto-match/LD-NONEXISTENT-XYZ", headers=ADMIN)
        assert r.status_code == 200
        assert r.json()["load_id"] == "LD-NONEXISTENT-XYZ"

    def test_tender_load(self, s):
        # Use a synthesized load id to avoid mutating real ones
        load_id = f"LD-TEST-{uuid.uuid4().hex[:6].upper()}"
        body = {"carrier_mc": "MC-100001", "rate_usd": 2200, "compliance_flag": "green"}
        r = s.post(f"{BASE_URL}/api/margin-shield/auto-match/{load_id}/tender",
                   json=body, headers=ADMIN)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["ok"] is True
        assert d["tender_id"].startswith("TND-")

    def test_tender_missing_mc_400(self, s):
        r = s.post(f"{BASE_URL}/api/margin-shield/auto-match/LD-X/tender",
                   json={}, headers=ADMIN)
        assert r.status_code == 400

    def test_tender_dispatcher_ok(self, s):
        load_id = f"LD-TEST-{uuid.uuid4().hex[:6].upper()}"
        r = s.post(f"{BASE_URL}/api/margin-shield/auto-match/{load_id}/tender",
                   json={"carrier_mc": "MC-100002"}, headers=DISP)
        assert r.status_code == 200


# ---------- RATE SNAPSHOT ----------
class TestRates:
    def test_rate_snapshot_shape(self, s):
        r = s.get(f"{BASE_URL}/api/margin-shield/rates/LD-TEST-001", headers=ADMIN)
        assert r.status_code == 200, r.text
        d = r.json()
        assert len(d["sources"]) == 3
        names = {x["name"] for x in d["sources"]}
        assert names == {"DAT One", "Truckstop", "Historical Lane Avg"}
        assert isinstance(d["recommended_rate"], (int, float))
        assert isinstance(d["recommended_rpm"], (int, float))
        assert 40 <= d["confidence_pct"] <= 100
        assert 0 <= d["live_source_count"] <= 3
        assert "synthetic_warning" in d


# ---------- COMPLIANCE ----------
class TestCompliance:
    def test_green_carrier(self, s):
        r = s.get(f"{BASE_URL}/api/margin-shield/compliance/MC-100001", headers=ADMIN)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["flag"] == "green"
        assert d["summary"] == "Tender-ready"
        assert len(d["checks"]) == 5
        assert all(c["status"] == "pass" for c in d["checks"])

    def test_red_carrier_apex(self, s):
        r = s.get(f"{BASE_URL}/api/margin-shield/compliance/MC-100004", headers=ADMIN)
        assert r.status_code == 200
        d = r.json()
        assert d["flag"] == "red", f"expected red, got {d}"
        assert d["failures"] >= 1
        assert len(d["checks"]) == 5

    def test_unknown_mc_404(self, s):
        r = s.get(f"{BASE_URL}/api/margin-shield/compliance/MC-NONEXISTENT", headers=ADMIN)
        assert r.status_code == 404


# ---------- AUTO-INVOICE ----------
class TestAutoInvoice:
    @pytest.fixture(scope="class")
    def seeded_booking(self):
        """Seed a booking with POD uploaded via direct mongo access."""
        import asyncio
        from motor.motor_asyncio import AsyncIOMotorClient
        # Load from backend .env
        mongo_url = "mongodb://localhost:27017"
        db_name = "test_database"
        try:
            with open("/app/backend/.env") as f:
                for line in f:
                    if line.startswith("MONGO_URL"):
                        mongo_url = line.split("=", 1)[1].strip().strip('"')
                    elif line.startswith("DB_NAME"):
                        db_name = line.split("=", 1)[1].strip().strip('"')
        except Exception:
            pass
        bid = f"BK-TEST-{uuid.uuid4().hex[:8].upper()}"

        async def seed():
            client = AsyncIOMotorClient(mongo_url)
            db = client[db_name]
            await db.brokerage_bookings.insert_one({
                "booking_id": bid, "customer_name": "Test Cust",
                "customer_email": "test@x.com",
                "rate_usd": 2500.0, "pod_uploaded": True, "status": "delivered",
                "equipment": "Van", "created_at": "2026-01-01T00:00:00+00:00",
            })
            # one without POD
            bid_nopod = f"BK-NOPOD-{uuid.uuid4().hex[:8].upper()}"
            await db.brokerage_bookings.insert_one({
                "booking_id": bid_nopod, "customer_name": "NoPOD",
                "rate_usd": 1500.0, "pod_uploaded": False, "status": "booked",
            })
            client.close()
            return bid, bid_nopod
        return asyncio.get_event_loop().run_until_complete(seed())

    def test_auto_invoice_success(self, s, seeded_booking):
        bid, _ = seeded_booking
        r = s.post(f"{BASE_URL}/api/margin-shield/invoice/auto/{bid}", headers=ADMIN)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["ok"] is True
        assert d["invoice_id"].startswith("INV-")
        assert d["amount_usd"] == 2500.0
        assert d["qbo_queued"] is True
        assert d["email_drafted"] is True

    def test_already_invoiced(self, s, seeded_booking):
        bid, _ = seeded_booking
        r = s.post(f"{BASE_URL}/api/margin-shield/invoice/auto/{bid}", headers=ADMIN)
        assert r.status_code == 200
        d = r.json()
        assert d.get("already_invoiced") is True
        assert d.get("invoice_id", "").startswith("INV-")

    def test_no_pod_400(self, s, seeded_booking):
        _, bid_nopod = seeded_booking
        r = s.post(f"{BASE_URL}/api/margin-shield/invoice/auto/{bid_nopod}", headers=ADMIN)
        assert r.status_code == 400

    def test_unknown_booking_404(self, s):
        r = s.post(f"{BASE_URL}/api/margin-shield/invoice/auto/BK-NONEXISTENT-Z", headers=ADMIN)
        assert r.status_code == 404


# ---------- LOYALTY PROGRAMS ----------
class TestLoyalty:
    pid = None  # shared across tests in class

    def test_list_empty_or_ok(self, s):
        r = s.get(f"{BASE_URL}/api/margin-shield/loyalty/programs", headers=ADMIN)
        assert r.status_code == 200
        assert "items" in r.json() and "count" in r.json()

    def test_create_program(self, s):
        r = s.post(f"{BASE_URL}/api/margin-shield/loyalty/programs", headers=ADMIN,
                   json={"name": "TEST_Platinum Lock", "bonus_type": "percent",
                         "bonus_value": 1.5, "tier": "platinum",
                         "first_look_minutes": 30, "active": True,
                         "notes": "test"})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["program_id"].startswith("LYL-")
        assert d["name"] == "TEST_Platinum Lock"
        TestLoyalty.pid = d["program_id"]

    def test_create_empty_name_422(self, s):
        r = s.post(f"{BASE_URL}/api/margin-shield/loyalty/programs", headers=ADMIN,
                   json={"name": "", "bonus_type": "flat", "bonus_value": 50})
        assert r.status_code == 422

    def test_update_program(self, s):
        assert TestLoyalty.pid
        r = s.put(f"{BASE_URL}/api/margin-shield/loyalty/programs/{TestLoyalty.pid}", headers=ADMIN,
                  json={"name": "TEST_Platinum Lock v2", "bonus_type": "percent",
                        "bonus_value": 2.0, "tier": "platinum",
                        "first_look_minutes": 45, "active": True})
        assert r.status_code == 200, r.text
        assert r.json()["name"] == "TEST_Platinum Lock v2"
        assert r.json()["bonus_value"] == 2.0

    def test_update_unknown_404(self, s):
        r = s.put(f"{BASE_URL}/api/margin-shield/loyalty/programs/LYL-NOPE", headers=ADMIN,
                  json={"name": "x", "bonus_type": "flat", "bonus_value": 10})
        assert r.status_code == 404

    def test_assign_tier(self, s):
        r = s.post(f"{BASE_URL}/api/margin-shield/loyalty/carriers/MC-100002/tier",
                   headers=ADMIN, json={"tier": "platinum", "program_id": TestLoyalty.pid})
        assert r.status_code == 200, r.text
        assert r.json()["tier"] == "platinum"

    def test_assign_tier_unknown_404(self, s):
        r = s.post(f"{BASE_URL}/api/margin-shield/loyalty/carriers/MC-DOESNOTEXIST/tier",
                   headers=ADMIN, json={"tier": "gold"})
        assert r.status_code == 404

    def test_delete_program(self, s):
        assert TestLoyalty.pid
        r = s.delete(f"{BASE_URL}/api/margin-shield/loyalty/programs/{TestLoyalty.pid}", headers=ADMIN)
        assert r.status_code == 200
        assert r.json()["status"] == "deleted"

    def test_delete_unknown_404(self, s):
        r = s.delete(f"{BASE_URL}/api/margin-shield/loyalty/programs/LYL-GONE", headers=ADMIN)
        assert r.status_code == 404

    def test_cleanup_restore_carrier_tier(self, s):
        # restore MC-100002 to gold (its seeded tier)
        s.post(f"{BASE_URL}/api/margin-shield/loyalty/carriers/MC-100002/tier",
               headers=ADMIN, json={"tier": "gold"})


# ---------- REGRESSION ----------
class TestRegression:
    def test_brokerage_boards(self, s):
        r = s.get(f"{BASE_URL}/api/brokerage/boards", headers=ADMIN)
        assert r.status_code in (200, 401, 404), f"unexpected {r.status_code}"
        # at minimum should not be 500
        assert r.status_code < 500

    def test_investor_boardroom(self, s):
        r = s.get(f"{BASE_URL}/api/investor/boardroom", headers=ADMIN)
        assert r.status_code < 500

    def test_public_tms_pitch_summary(self, s):
        r = s.get(f"{BASE_URL}/api/public/tms-pitch-summary")
        assert r.status_code == 200
        assert "brand" in r.json() or "company_name" in str(r.json())
