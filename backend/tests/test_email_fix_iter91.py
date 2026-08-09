"""Iteration 91 — verify Resend env-var fallback fixes tc_booking_alert emails.

Covers:
  1) Env fallback logic in routes.orisei_auto_digest._resend_creds
  2) POST /api/truck-cleaning/public/booking triggers status='sent' in outbound_emails
  3) Autopilot conversion works (tc_bookings.status='converted' + job_id + scheduled_date)
  4) Code inspection (import os present; DB creds preferred)
"""
import os
import sys
import asyncio
import pytest
import requests
from pathlib import Path

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL") or open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split()[0]
BASE_URL = BASE_URL.rstrip("/")

# Load backend env vars so tests see RESEND_*
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")

sys.path.insert(0, "/app/backend")


# -------------------- 1. Env fallback logic --------------------
def test_resend_creds_env_fallback():
    """When DB has no resend creds, _resend_creds must fall back to env vars."""
    from routes.orisei_auto_digest import _resend_creds

    class DummyDB:
        # get_connection_credentials will try to access db.connections; make it fail
        def __getattr__(self, item):
            raise RuntimeError("no db")

    creds = asyncio.get_event_loop().run_until_complete(_resend_creds(DummyDB()))
    assert creds is not None, "Expected env fallback creds, got None"
    assert creds.get("api_key", "").startswith("re_"), f"api_key not from Resend env: {creds.get('api_key','')[:6]}"
    assert creds.get("from_email") == "bookings@oriseifreightsolutions.com", \
        f"from_email mismatch: {creds.get('from_email')}"
    assert creds.get("from_name"), "from_name missing"


# -------------------- 4. Code inspection --------------------
def test_orisei_auto_digest_code_shape():
    src = Path("/app/backend/routes/orisei_auto_digest.py").read_text()
    assert "\nimport os\n" in src, "import os missing"
    # DB creds preferred (returns them if api_key set) before env fallback
    idx_db = src.find('if creds and creds.get("api_key"):')
    idx_env = src.find('env_key = os.environ.get("RESEND_API_KEY"')
    assert idx_db != -1 and idx_env != -1 and idx_db < idx_env, \
        "DB creds must be checked BEFORE env fallback"


# -------------------- 2 & 3. End-to-end public booking --------------------
@pytest.fixture(scope="module")
def mongo_db():
    from pymongo import MongoClient
    client = MongoClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    yield db
    client.close()


@pytest.fixture(scope="module")
def booking_response():
    """Fires the REAL booking exactly ONCE (module-scoped)."""
    payload = {
        "company": "QA EmailFix Yard",
        "phone": "612-555-0303",
        "cabs": 1,
        "plan": "one_time",
        "services": [],
    }
    r = requests.post(f"{BASE_URL}/api/truck-cleaning/public/booking",
                       json=payload, timeout=45)
    return r


def test_booking_returns_200(booking_response):
    assert booking_response.status_code == 200, \
        f"Expected 200, got {booking_response.status_code}: {booking_response.text[:400]}"
    data = booking_response.json()
    assert data.get("ok") is True or data.get("booking_id"), \
        f"Unexpected response: {data}"


def test_outbound_emails_sent(booking_response, mongo_db):
    """Two newest tc_booking_alert docs must have status='sent' and error=None."""
    # Emails are inserted synchronously in the same request, but allow a small buffer
    import time
    time.sleep(2)
    rows = list(mongo_db.outbound_emails
                .find({"kind": "tc_booking_alert"})
                .sort("at", -1).limit(2))
    assert len(rows) == 2, f"Expected 2 recent booking alerts, got {len(rows)}"

    tos = {r["to"] for r in rows}
    assert tos == {"oliver@oriseifreightsolutions.com",
                    "shearperfection369@gmail.com"}, f"Wrong recipients: {tos}"

    for r in rows:
        assert r["status"] == "sent", \
            f"Email to {r['to']} status={r['status']} error={r.get('error')}"
        assert r.get("error") in (None, ""), \
            f"Email to {r['to']} has error: {r.get('error')}"


def test_booking_autopilot_converted(booking_response, mongo_db):
    """Booking must be status='converted' with job_id + scheduled_date."""
    import time
    time.sleep(1)
    b = mongo_db.tc_bookings.find_one({"company": "QA EmailFix Yard"},
                                       sort=[("created_at", -1)])
    assert b is not None, "Booking not persisted"
    assert b.get("status") == "converted", f"Booking status={b.get('status')}"
    assert b.get("job_id"), "Missing job_id on converted booking"
    assert b.get("scheduled_date"), "Missing scheduled_date"


# -------------------- Cleanup --------------------
def test_cleanup_qa_records(mongo_db):
    """Delete tc_bookings/tc_jobs/tc_clients for QA EmailFix Yard."""
    d1 = mongo_db.tc_bookings.delete_many({"company": "QA EmailFix Yard"}).deleted_count
    d2 = mongo_db.tc_jobs.delete_many({"company": "QA EmailFix Yard"}).deleted_count
    d3 = mongo_db.tc_clients.delete_many({"company": "QA EmailFix Yard"}).deleted_count
    print(f"cleanup: bookings={d1} jobs={d2} clients={d3}")
    # Also remove the outbound_emails rows we created to keep collection clean
    # (Do NOT delete other alerts.)
    # Identify by booking_id we just wrote — but simpler: leave them for audit.
    assert True
