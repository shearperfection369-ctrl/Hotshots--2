"""Iter92: TC Booking Map, Ad Tracker, Detail Tiers, FMCSA Carrier Search."""
import os
import time
import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/dev-session", timeout=15)
    assert r.status_code == 200, f"dev-session failed: {r.status_code} {r.text}"
    return r.json()["session_token"]


@pytest.fixture(scope="module")
def auth(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ========== FMCSA Carrier Search ==========
class TestCarrierSearch:
    def test_search_by_name(self, auth):
        r = requests.get(f"{BASE_URL}/api/carrier-search",
                         params={"q": "dart transit", "state": "MN"}, headers=auth, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "results" in data and data["count"] > 0, data
        top = data["results"][0]
        for k in ("legal_name", "phone", "address", "power_units", "dot_number"):
            assert k in top, f"missing {k}"

    def test_search_by_dot(self, auth):
        r = requests.get(f"{BASE_URL}/api/carrier-search",
                         params={"q": "44110", "by": "dot"}, headers=auth, timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert data["count"] >= 1
        name = (data["results"][0].get("legal_name") or "").lower()
        assert "greyhound" in name, f"expected greyhound, got {name}"

    def test_add_prospect_and_duplicate(self, auth):
        payload = {"legal_name": "TEST Iter92 Carrier",
                   "dot_number": "TESTITER92DOT", "power_units": 25,
                   "city": "Minneapolis", "state": "MN",
                   "address": "123 Test St", "phone": "555-0100",
                   "operation": "Interstate", "cargo": ["General Freight"]}
        r1 = requests.post(f"{BASE_URL}/api/carrier-search/add-prospect",
                           json=payload, headers=auth, timeout=15)
        assert r1.status_code == 200, r1.text
        d1 = r1.json()
        assert d1["ok"] and d1["prospect_id"].startswith("YP-")
        pid = d1["prospect_id"]
        r2 = requests.post(f"{BASE_URL}/api/carrier-search/add-prospect",
                           json=payload, headers=auth, timeout=15)
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2.get("duplicate") is True
        assert d2["prospect_id"] == pid
        # cleanup
        from pymongo import MongoClient
        MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]].tc_yard_prospects.delete_one(
            {"prospect_id": pid})

    def test_enrichment_status_not_configured(self, auth):
        r = requests.get(f"{BASE_URL}/api/carrier-search/enrichment-status",
                         headers=auth, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["configured"] is False
        assert "not yet connected" in d["message"].lower() or "not configured" in d["message"].lower()

    def test_search_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/carrier-search", params={"q": "dart"}, timeout=15)
        assert r.status_code in (401, 403)


# ========== Public Booking: Detail Tiers + Ad Tracker + Jobs Map ==========
class TestBookingTiersAndMap:
    _gold_booking_id = None
    _plat_booking_id = None
    _gold_job_id = None
    _plat_job_id = None

    def test_gold_tier_booking_with_ceramic_addon(self, auth):
        payload = {
            "company": "TEST Iter92 Gold Co", "contact": "Test Gold",
            "phone": "612-555-0101", "email": "test.gold@example.com",
            "cabs": 1, "plan": "car_detail", "tier": "gold",
            "heard_from": "Facebook",
            "services": ["ceramic_spray"],
            "address": "301 Chicago Ave, Minneapolis, MN 55415",
            "notes": "TEST iter92 gold",
        }
        r = requests.post(f"{BASE_URL}/api/truck-cleaning/public/booking",
                          json=payload, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["ok"] and d["booking_id"].startswith("BOOK-")
        TestBookingTiersAndMap._gold_booking_id = d["booking_id"]
        assert d.get("scheduled_date"), "should have scheduled date"

        # verify via /bookings
        rb = requests.get(f"{BASE_URL}/api/truck-cleaning/bookings", headers=auth, timeout=15)
        assert rb.status_code == 200
        booking = next(b for b in rb.json()["bookings"] if b["booking_id"] == d["booking_id"])
        assert booking["tier"] == "gold"
        assert booking["heard_from"] == "Facebook"
        assert booking.get("job_id")
        TestBookingTiersAndMap._gold_job_id = booking["job_id"]

        # verify job price = 220 (gold) + 75 (ceramic_spray) = 295
        from pymongo import MongoClient
        job = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]].tc_jobs.find_one(
            {"job_id": booking["job_id"]}, {"_id": 0})
        assert job is not None
        assert job["price"] == 295.0, f"expected 295, got {job['price']}"

    def test_platinum_tier_no_double_charge(self, auth):
        time.sleep(3)  # rate limit spacing
        payload = {
            "company": "TEST Iter92 Plat Co", "contact": "Test Plat",
            "phone": "612-555-0102", "email": "test.plat@example.com",
            "cabs": 1, "plan": "car_detail", "tier": "platinum",
            "heard_from": "Referral",
            "services": ["shampoo_seats"],  # included in platinum
            "address": "301 Chicago Ave, Minneapolis, MN 55415",
            "notes": "TEST iter92 plat",
        }
        r = requests.post(f"{BASE_URL}/api/truck-cleaning/public/booking",
                          json=payload, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        TestBookingTiersAndMap._plat_booking_id = d["booking_id"]

        rb = requests.get(f"{BASE_URL}/api/truck-cleaning/bookings", headers=auth, timeout=15)
        booking = next(b for b in rb.json()["bookings"] if b["booking_id"] == d["booking_id"])
        assert booking["tier"] == "platinum"
        TestBookingTiersAndMap._plat_job_id = booking.get("job_id")

        from pymongo import MongoClient
        job = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]].tc_jobs.find_one(
            {"job_id": booking["job_id"]}, {"_id": 0})
        assert job["price"] == 300.0, f"platinum should be 300 flat, got {job['price']}"
        assert "shampoo_seats" not in job.get("upsells", []), "included add-on should be stripped"

    def test_jobs_map(self, auth):
        r = requests.get(f"{BASE_URL}/api/truck-cleaning/jobs-map", headers=auth, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert "pins" in d and "total_jobs" in d
        # allow retry for geocoding
        if len(d["pins"]) == 0:
            time.sleep(2)
            r = requests.get(f"{BASE_URL}/api/truck-cleaning/jobs-map", headers=auth, timeout=30)
            d = r.json()
        for pin in d["pins"]:
            assert "lat" in pin and "lng" in pin and pin["lat"] is not None

    def test_jobs_map_date_filter(self, auth):
        r = requests.get(f"{BASE_URL}/api/truck-cleaning/jobs-map",
                         params={"date": "1999-01-01"}, headers=auth, timeout=15)
        assert r.status_code == 200
        assert r.json()["total_jobs"] == 0

    def test_cleanup(self, auth):
        from pymongo import MongoClient
        db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
        for bid in (self._gold_booking_id, self._plat_booking_id):
            if bid:
                db.tc_bookings.delete_many({"booking_id": bid})
        for jid in (self._gold_job_id, self._plat_job_id):
            if jid:
                db.tc_jobs.delete_many({"job_id": jid})
        db.tc_clients.delete_many({"company": {"$regex": "^TEST Iter92"}})


# ========== Regression on other plans ==========
class TestRegression:
    def test_one_time_booking(self, auth):
        time.sleep(3)
        payload = {"company": "TEST Iter92 OneTime", "contact": "Reg Test",
                   "phone": "612-555-0103", "cabs": 2, "plan": "one_time",
                   "heard_from": "Google"}
        r = requests.post(f"{BASE_URL}/api/truck-cleaning/public/booking",
                          json=payload, timeout=30)
        assert r.status_code == 200
        bid = r.json()["booking_id"]
        rb = requests.get(f"{BASE_URL}/api/truck-cleaning/bookings", headers=auth, timeout=15)
        booking = next(b for b in rb.json()["bookings"] if b["booking_id"] == bid)
        from pymongo import MongoClient
        db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
        job = db.tc_jobs.find_one({"job_id": booking["job_id"]}, {"_id": 0})
        assert job["price"] == 350.0  # 2 cabs * 175
        # cleanup
        db.tc_bookings.delete_many({"booking_id": bid})
        db.tc_jobs.delete_many({"job_id": booking["job_id"]})
        db.tc_clients.delete_many({"company": "TEST Iter92 OneTime"})
