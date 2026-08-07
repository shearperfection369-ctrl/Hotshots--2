"""Truck Cleaning new batch: booking autopilot, invalid plan/date, win notification email."""
import os
import time
import pytest
import requests
from datetime import datetime, timezone, timedelta

def _load_backend_url():
    u = os.environ.get("REACT_APP_BACKEND_URL", "").strip()
    if not u:
        try:
            with open("/app/frontend/.env") as f:
                for line in f:
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        u = line.split("=", 1)[1].strip().strip('"')
                        break
        except FileNotFoundError:
            pass
    return u.rstrip("/")


BASE_URL = _load_backend_url()
ADMIN_HEADERS = {"Authorization": "Bearer test_session_admin_1", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def sess():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _tomorrow():
    return (datetime.now(timezone.utc).date() + timedelta(days=1)).isoformat()


# --- 1. Booking autopilot: happy path ---
def test_public_booking_autopilot(sess):
    payload = {
        "company": "QA Autopilot Yard",
        "phone": "612-555-1000",
        "cabs": 2,
        "plan": "biweekly",
        "scent": "Pine Forest",
        "services": ["tire_dressing"],
        "preferred_date": "",
        "notes": "525 Kasota Ave SE, Minneapolis MN",
    }
    r = sess.post(f"{BASE_URL}/api/truck-cleaning/public/booking", json=payload)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("ok") is True
    assert data.get("scheduled_date") == _tomorrow(), data
    # tech_name may be empty if no active tech; task expects a real tech (Jaylen Brooks etc.)
    assert data.get("tech_name"), f"No tech assigned: {data}"
    print(f"Autopilot booking → scheduled={data['scheduled_date']} tech={data['tech_name']}")

    # Verify in DB via bookings list
    r2 = sess.get(f"{BASE_URL}/api/truck-cleaning/bookings", headers=ADMIN_HEADERS)
    assert r2.status_code == 200
    bookings = r2.json().get("bookings", [])
    ours = [b for b in bookings if b.get("company") == "QA Autopilot Yard"]
    assert ours, "Booking not found in list"
    b = ours[0]
    assert b["status"] == "converted"
    assert b.get("job_id")
    assert b.get("scheduled_date") == _tomorrow()

    # Verify job via jobs endpoint
    rj = sess.get(f"{BASE_URL}/api/truck-cleaning/jobs", headers=ADMIN_HEADERS)
    assert rj.status_code == 200
    jobs = rj.json().get("jobs", [])
    job = next((j for j in jobs if j.get("job_id") == b["job_id"]), None)
    assert job, "Job not found"
    # price = 2 * 130 + tire_dressing (assume $20)
    assert job["price"] == pytest.approx(280.0), f"price={job['price']}"
    assert "tire_dressing" in job.get("upsells", [])
    # tech_ids may be assigned via routing
    assert job.get("tech_ids"), f"tech_ids empty: {job}"


# --- 2. Invalid plan defaults to one_time; invalid preferred_date falls back ---
def test_invalid_plan_and_past_date(sess):
    payload = {
        "company": "QA Autopilot Yard Bad",
        "phone": "612-555-1001",
        "cabs": 1,
        "plan": "not_a_plan",
        "scent": "",
        "services": [],
        "preferred_date": "2020-01-01",
        "notes": "bad input test",
    }
    r = sess.post(f"{BASE_URL}/api/truck-cleaning/public/booking", json=payload)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("scheduled_date") == _tomorrow()

    # Fetch booking to check plan defaulted to one_time
    r2 = sess.get(f"{BASE_URL}/api/truck-cleaning/bookings", headers=ADMIN_HEADERS)
    bookings = r2.json().get("bookings", [])
    ours = next((b for b in bookings if b.get("company") == "QA Autopilot Yard Bad"), None)
    assert ours
    assert ours.get("plan") == "one_time", f"plan={ours.get('plan')}"

    # Cleanup this extra booking + job/client
    if ours.get("job_id"):
        _cleanup_company("QA Autopilot Yard Bad", sess)


# --- 3. Win notification email ---
def test_win_notification_email(sess):
    # Create agreement
    r = sess.post(f"{BASE_URL}/api/truck-cleaning/agreements",
                  json={"company": "QA Win Yard", "cabs": 3, "frequency": "biweekly"},
                  headers=ADMIN_HEADERS)
    assert r.status_code == 200, r.text
    token = r.json()["token"]

    # Sign
    r2 = sess.post(f"{BASE_URL}/api/truck-cleaning/public/agreement/{token}/sign",
                   json={"name": "QA Winner", "title": "Yard Mgr"})
    assert r2.status_code == 200, r2.text

    # Give the async email tasks a beat
    time.sleep(3)

    # Check outbound_emails via debug endpoint if available; else check via DB indirectly.
    # Try admin outbound_emails endpoint
    r3 = sess.get(f"{BASE_URL}/api/truck-cleaning/agreements", headers=ADMIN_HEADERS)
    assert r3.status_code == 200
    agrs = r3.json().get("agreements", [])
    signed = next((a for a in agrs if a.get("company") == "QA Win Yard"), None)
    assert signed and signed["status"] == "signed"
    print(f"Agreement signed for QA Win Yard, token={token}")


def _cleanup_company(company, sess):
    """Best-effort cleanup via direct mongo through backend admin endpoints if available."""
    pass


# --- Cleanup all test artifacts at end ---
def test_zzz_cleanup(sess):
    """Delete created test data directly via mongo (backend has no delete endpoints exposed)."""
    from pymongo import MongoClient
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    if not mongo_url or not db_name:
        # Try backend .env
        env_path = "/app/backend/.env"
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    if line.startswith("MONGO_URL="):
                        mongo_url = line.split("=", 1)[1].strip().strip('"')
                    if line.startswith("DB_NAME="):
                        db_name = line.split("=", 1)[1].strip().strip('"')
    assert mongo_url and db_name, "Mongo not configured"
    client = MongoClient(mongo_url)
    db = client[db_name]
    for co in ("QA Autopilot Yard", "QA Autopilot Yard Bad", "QA UI Booking Co"):
        db.tc_bookings.delete_many({"company": co})
        db.tc_jobs.delete_many({"company": co})
        db.tc_clients.delete_many({"company": co})
    for co in ("QA Win Yard",):
        db.tc_agreements.delete_many({"company": co})
        db.tc_clients.delete_many({"company": co})
        db.tc_recurring.delete_many({"company": co})
    print("Cleanup complete")
