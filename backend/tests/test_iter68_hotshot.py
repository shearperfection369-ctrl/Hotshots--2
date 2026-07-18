"""iter68 — HOT SHOT TMS: lead capture, auth, admin list access, PDF, validation.

Verifies:
  - POST /api/hotshot/leads (public) with valid + invalid email
  - GET  /api/hotshot/leads with admin bearer token
  - POST /api/hotshot/leads/{id}/status persistence
  - GET  /api/hotshot/one-pager.pdf 200 with %PDF magic bytes
"""
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else "https://clean-logistics-dash.preview.emergentagent.com"
ADMIN_TOKEN = "test_session_admin_1"
HDR = {"Authorization": f"Bearer {ADMIN_TOKEN}"}


@pytest.fixture(scope="module")
def created_lead_id():
    marker = f"TEST_iter68_{int(time.time())}_{uuid.uuid4().hex[:4]}"
    payload = {
        "name": f"Pytest {marker}",
        "email": f"pytest.{marker.lower()}@example.com",
        "company": f"HotShotPytest {marker}",
        "fleet_or_volume": "8 trucks",
        "tier_interest": "Growth",
        "message": "iter68 automated regression"
    }
    r = requests.post(f"{BASE_URL}/api/hotshot/leads", json=payload, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("ok") is True
    # find the lead we just created via list endpoint
    lst = requests.get(f"{BASE_URL}/api/hotshot/leads", headers=HDR, timeout=30)
    assert lst.status_code == 200, lst.text
    leads = lst.json().get("leads", [])
    mine = [ld for ld in leads if ld["email"] == payload["email"]]
    assert mine, "created lead not found in list"
    return mine[0]["lead_id"]


# ---- public lead creation ----
def test_create_lead_ok():
    marker = uuid.uuid4().hex[:8]
    payload = {"name": f"TEST_{marker}", "email": f"a{marker}@t.com", "company": "TC"}
    r = requests.post(f"{BASE_URL}/api/hotshot/leads", json=payload, timeout=30)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert "message" in body


def test_create_lead_invalid_email_returns_400():
    r = requests.post(f"{BASE_URL}/api/hotshot/leads",
                      json={"name": "Bad Email", "email": "notanemail", "company": "X"},
                      timeout=30)
    assert r.status_code == 400, r.text
    assert "valid email" in r.text.lower()


def test_create_lead_missing_name_returns_422():
    r = requests.post(f"{BASE_URL}/api/hotshot/leads",
                      json={"email": "x@y.com"},
                      timeout=30)
    assert r.status_code in (400, 422)


# ---- admin list access ----
def test_list_leads_admin_200(created_lead_id):
    r = requests.get(f"{BASE_URL}/api/hotshot/leads", headers=HDR, timeout=30)
    assert r.status_code == 200, f"admin must be permitted to list leads: {r.status_code} {r.text[:400]}"
    data = r.json()
    assert "leads" in data and isinstance(data["leads"], list)
    ids = [ld["lead_id"] for ld in data["leads"]]
    assert created_lead_id in ids


def test_list_leads_unauth_401():
    r = requests.get(f"{BASE_URL}/api/hotshot/leads", timeout=30)
    assert r.status_code in (401, 403)


# ---- status transitions persist ----
def test_status_change_persists(created_lead_id):
    r = requests.post(f"{BASE_URL}/api/hotshot/leads/{created_lead_id}/status",
                      headers=HDR, json={"status": "contacted"}, timeout=30)
    assert r.status_code == 200
    # verify via GET
    lst = requests.get(f"{BASE_URL}/api/hotshot/leads", headers=HDR, timeout=30).json()["leads"]
    match = [ld for ld in lst if ld["lead_id"] == created_lead_id]
    assert match and match[0]["status"] == "contacted"


def test_status_invalid_returns_400(created_lead_id):
    r = requests.post(f"{BASE_URL}/api/hotshot/leads/{created_lead_id}/status",
                      headers=HDR, json={"status": "bogus"}, timeout=30)
    assert r.status_code == 400


def test_status_not_found_404():
    r = requests.post(f"{BASE_URL}/api/hotshot/leads/HSL-DOES-NOT-EXIST/status",
                      headers=HDR, json={"status": "new"}, timeout=30)
    assert r.status_code == 404


# ---- one-pager pdf ----
def test_one_pager_pdf():
    r = requests.get(f"{BASE_URL}/api/hotshot/one-pager.pdf", timeout=30)
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("application/pdf")
    assert r.content[:4] == b"%PDF"
    assert len(r.content) > 1000
