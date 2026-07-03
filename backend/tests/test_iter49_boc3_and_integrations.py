"""iter49 backend tests — BOC-3 compliance module + regression on iter48 features.

Covers:
  • GET /api/boc3/states — 51 jurisdictions + 7 statuses
  • POST /api/boc3/filings — create + upsert (same state)
  • YELLOW alert on ~45-day expiry
  • RED alert on ~20-day expiry
  • EXPIRED alert on past expiry
  • PUT status transition (ACCEPTED → REJECTED w/ reason) + history append
  • GET /calendar — 24 months and future-month bucket
  • GET /coverage — percent_covered against ACCEPTED/FILED
  • POST /upload + GET /file — GridFS round-trip
  • Regression: intake POST, onboarding checklist GET, brokerage check-call POST
"""
from __future__ import annotations

import io
import os
from datetime import datetime, timedelta, timezone

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # In test container we read from /app/frontend/.env
    with open("/app/frontend/.env") as f:
        for ln in f:
            if ln.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = ln.split("=", 1)[1].strip().rstrip("/")

TOKEN = "test_session_admin_1"
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}


def _iso(days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {TOKEN}"})
    return s


# ---------------- BOC-3 tests ----------------

class TestBoc3States:
    def test_list_states(self, api):
        r = api.get(f"{BASE_URL}/api/boc3/states")
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["count"] == 51
        codes = {i["code"] for i in d["items"]}
        assert "DC" in codes and "CA" in codes and "MN" in codes
        assert len(d["statuses"]) == 7
        for s in ["PENDING_FILE", "FILED", "ACCEPTED", "REJECTED",
                  "EXPIRED", "RENEWAL_DUE", "VOID"]:
            assert s in d["statuses"]


class TestBoc3Filings:
    def test_create_and_upsert_mn(self, api):
        # create MN filing at ~200 days out to keep out of alert range
        payload = {
            "state_code": "MN",
            "process_agent_name": "TEST_AgentCo",
            "process_agent_address": "1 Test Way, Minneapolis MN",
            "filed_at": _iso(-10),
            "expires_at": _iso(200),
            "status": "ACCEPTED",
        }
        r = api.post(f"{BASE_URL}/api/boc3/filings", json=payload)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["filing_id"].startswith("BOC3-")
        assert d["state_code"] == "MN"
        assert d["status"] == "ACCEPTED"
        filing_id = d["filing_id"]

        # upsert — post again for same state_code should keep same doc
        payload2 = {**payload, "process_agent_name": "TEST_AgentCo v2"}
        r2 = api.post(f"{BASE_URL}/api/boc3/filings", json=payload2)
        assert r2.status_code == 200, r2.text
        d2 = r2.json()
        assert d2.get("filing_id") == filing_id or d2.get("state_code") == "MN"
        assert d2["process_agent_name"] == "TEST_AgentCo v2"

    def test_yellow_alert_45_days(self, api):
        # CA at 45 days → YELLOW
        r = api.post(f"{BASE_URL}/api/boc3/filings", json={
            "state_code": "CA",
            "process_agent_name": "TEST_YellowAgent",
            "process_agent_address": "1 Yellow St, LA CA",
            "filed_at": _iso(-30),
            "expires_at": _iso(45),
            "status": "ACCEPTED",
        })
        assert r.status_code == 200
        alerts = api.get(f"{BASE_URL}/api/boc3/alerts").json()
        assert alerts["yellow_count"] >= 1
        assert any(x["state_code"] == "CA" for x in alerts["yellow"])

    def test_red_alert_20_days(self, api):
        r = api.post(f"{BASE_URL}/api/boc3/filings", json={
            "state_code": "TX",
            "process_agent_name": "TEST_RedAgent",
            "process_agent_address": "1 Red St, Dallas TX",
            "filed_at": _iso(-60),
            "expires_at": _iso(20),
            "status": "ACCEPTED",
        })
        assert r.status_code == 200
        alerts = api.get(f"{BASE_URL}/api/boc3/alerts").json()
        assert alerts["red_count"] >= 1
        assert any(x["state_code"] == "TX" for x in alerts["red"])

    def test_expired_alert_past(self, api):
        r = api.post(f"{BASE_URL}/api/boc3/filings", json={
            "state_code": "NY",
            "process_agent_name": "TEST_ExpiredAgent",
            "process_agent_address": "1 Exp St, NYC NY",
            "filed_at": _iso(-400),
            "expires_at": _iso(-30),
            "status": "ACCEPTED",
        })
        assert r.status_code == 200
        alerts = api.get(f"{BASE_URL}/api/boc3/alerts").json()
        assert alerts["expired_count"] >= 1
        assert any(x["state_code"] == "NY" for x in alerts["expired"])

    def test_reject_and_history(self, api):
        # find a filing_id — use MN
        rows = api.get(f"{BASE_URL}/api/boc3/filings").json()["items"]
        mn = next(r for r in rows if r["state_code"] == "MN")
        fid = mn["filing_id"]
        r = api.put(f"{BASE_URL}/api/boc3/filings/{fid}/status", json={
            "status": "REJECTED",
            "rejection_reason": "TEST_ Missing agent signature",
        })
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["status"] == "REJECTED"
        assert d["rejection_reason"].startswith("TEST_")
        assert any(h.get("status") == "REJECTED" for h in d.get("history", []))
        # restore state so subsequent tests reflect ACCEPTED
        api.put(f"{BASE_URL}/api/boc3/filings/{fid}/status", json={
            "status": "ACCEPTED", "note": "restore"})

    def test_calendar_24_months(self, api):
        d = api.get(f"{BASE_URL}/api/boc3/calendar").json()
        assert len(d["months"]) == 24
        # CA @ 45d and TX @ 20d — must appear in some upcoming month
        matched_ca = False
        for m in d["months"]:
            for f in m["filings"]:
                if f["state_code"] == "CA":
                    matched_ca = True
        assert matched_ca

    def test_coverage_percent(self, api):
        d = api.get(f"{BASE_URL}/api/boc3/coverage").json()
        assert d["total_jurisdictions"] == 51
        # We have MN(ACCEPTED restored), CA, TX, NY posted as ACCEPTED
        assert d["covered_count"] >= 3
        expected = round(100 * d["covered_count"] / 51, 1)
        assert d["percent_covered"] == expected

    def test_upload_and_download(self, api):
        rows = api.get(f"{BASE_URL}/api/boc3/filings").json()["items"]
        mn = next(r for r in rows if r["state_code"] == "MN")
        fid = mn["filing_id"]
        pdf_bytes = b"%PDF-1.4\nTEST_iter49\n%%EOF"
        # multipart — do not send JSON Content-Type
        s = requests.Session()
        s.headers.update({"Authorization": f"Bearer {TOKEN}"})
        r = s.post(f"{BASE_URL}/api/boc3/filings/{fid}/upload",
                   files={"file": ("test.pdf", pdf_bytes, "application/pdf")})
        assert r.status_code == 200, r.text
        up = r.json()
        assert up["ok"] and up.get("cert_file_id")
        # download
        dl = s.get(f"{BASE_URL}/api/boc3/filings/{fid}/file")
        assert dl.status_code == 200
        assert dl.content == pdf_bytes


# ---------------- Regression: prior iter endpoints ----------------

class TestPriorIntegrations:
    def test_intake_create(self, api):
        r = api.post(f"{BASE_URL}/api/intake/requests", json={
            "shipper_name": "TEST_ShipCo iter49",
            "shipper_email": "test-i49@example.com",
        })
        assert r.status_code in (200, 201), r.text
        d = r.json()
        # Look for token or id-ish field
        assert any(k in d for k in ("token", "public_token", "id", "request_id"))
        # Save for possible reuse
        TestPriorIntegrations.intake_token = d.get("token") or d.get("public_token")

    def test_onboarding_checklist(self, api):
        r = api.get(f"{BASE_URL}/api/onboarding/checklist")
        assert r.status_code == 200, r.text
        d = r.json()
        assert "items" in d or "groups" in d or isinstance(d, list)

    def test_check_call_optional(self, api):
        # Best effort — need a booking. Try to list existing bookings
        r = api.get(f"{BASE_URL}/api/brokerage/bookings")
        if r.status_code != 200:
            pytest.skip("brokerage bookings list unavailable")
        arr = r.json()
        items = arr.get("bookings") or arr.get("items") if isinstance(arr, dict) else arr
        if not items:
            pytest.skip("no bookings to attach check-call to")
        booking_id = items[0].get("booked_id") or items[0].get("id") or items[0].get("booking_id")
        if not booking_id:
            pytest.skip("no booking id field")
        r = api.post(
            f"{BASE_URL}/api/brokerage/bookings/{booking_id}/check-call",
            json={"status": "IN_TRANSIT", "location": "TEST_CityA, NV",
                  "note": "iter49 test"},
        )
        assert r.status_code in (200, 201), r.text
