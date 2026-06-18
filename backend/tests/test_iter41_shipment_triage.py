"""Iter 41 — Shipment Triage / AI Exception Detection regression suite."""
import os
import time
import pytest
import requests

BASE_URL = "https://clean-logistics-dash.preview.emergentagent.com"
ADMIN = "test_session_admin_1"
H = {"Authorization": f"Bearer {ADMIN}", "Content-Type": "application/json"}

EXPECTED_TYPES = {
    "pickup_late", "delivery_late", "no_gps_checkin", "lost_load",
    "pod_missing", "margin_drift", "carrier_no_response", "off_route",
}


# ---------- catalog ----------
def test_exception_types():
    r = requests.get(f"{BASE_URL}/api/shipment-triage/exception-types", headers=H, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    items = data["items"]
    assert len(items) == 8
    ids = {i["id"] for i in items}
    assert ids == EXPECTED_TYPES
    for it in items:
        assert "label" in it and "icon" in it and "default_severity" in it
        assert isinstance(it["playbook"], list) and len(it["playbook"]) >= 1
    assert isinstance(data["is_after_hours"], bool)


# ---------- scan ----------
def test_scan_runs_and_detects():
    r = requests.post(f"{BASE_URL}/api/shipment-triage/scan", headers=H, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "scanned_bookings" in data
    assert "created_count" in data
    assert isinstance(data["created"], list)
    assert data["scanned_bookings"] >= 0
    for ex in data["created"]:
        assert ex["exception_id"].startswith("EX-")
        assert ex["exception_type"] in EXPECTED_TYPES
        assert ex["severity"] in ("low", "medium", "high", "critical")
        adv = ex["advice"]
        for k in ("root_cause", "playbook", "customer_message", "carrier_message", "escalation", "after_hours"):
            assert k in adv, f"advice missing {k}"
        assert isinstance(adv["playbook"], list) and len(adv["playbook"]) >= 1


# ---------- list ----------
def test_list_exceptions_sorted_with_summary():
    r = requests.get(f"{BASE_URL}/api/shipment-triage/exceptions", headers=H, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "items" in data and "summary" in data and "is_after_hours" in data
    summary = data["summary"]
    for k in ("open", "acknowledged", "in_progress", "resolved", "escalated", "critical", "high"):
        assert k in summary
    # severity sort: critical -> high -> medium -> low
    sev_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    items = data["items"]
    prev = -1
    for it in items:
        cur = sev_order.get(it.get("severity"), 9)
        assert cur >= prev, f"severity sort broken at {it.get('exception_id')}"
        prev = cur


def test_list_exceptions_filter_status():
    r = requests.get(f"{BASE_URL}/api/shipment-triage/exceptions?status=open", headers=H, timeout=20)
    assert r.status_code == 200
    for it in r.json()["items"]:
        assert it["status"] == "open"


# ---------- manual create + status + filter by booked_id ----------
@pytest.fixture(scope="module")
def a_booking_id():
    r = requests.get(f"{BASE_URL}/api/brokerage/margins", headers=H, timeout=20)
    assert r.status_code == 200
    body = r.json()
    items = body.get("bookings") or body.get("items") or []
    assert items, "no brokerage bookings to test against"
    bk = items[0]
    return bk.get("booked_id") or bk.get("id")


def test_manual_create_invalid_type(a_booking_id):
    r = requests.post(f"{BASE_URL}/api/shipment-triage/exceptions", headers=H,
                      json={"booked_id": a_booking_id, "exception_type": "bogus"}, timeout=20)
    assert r.status_code == 400


def test_manual_create_unknown_booking():
    r = requests.post(f"{BASE_URL}/api/shipment-triage/exceptions", headers=H,
                      json={"booked_id": "BK-DOES-NOT-EXIST", "exception_type": "pickup_late"}, timeout=20)
    assert r.status_code == 404


def test_manual_create_status_filter_resolve(a_booking_id):
    payload = {
        "booked_id": a_booking_id,
        "exception_type": "carrier_no_response",
        "severity": "high",
        "signal": "TEST_iter41 manual ping",
        "notes": "TEST_iter41 created from regression suite",
    }
    r = requests.post(f"{BASE_URL}/api/shipment-triage/exceptions", headers=H, json=payload, timeout=20)
    assert r.status_code == 200, r.text
    ex = r.json()
    eid = ex["exception_id"]
    assert ex["exception_type"] == "carrier_no_response"
    assert ex["severity"] == "high"
    assert ex["status"] == "open"
    assert ex["booked_id"] == a_booking_id
    assert "advice" in ex and "playbook" in ex["advice"]

    # Filter by booked_id
    r2 = requests.get(f"{BASE_URL}/api/shipment-triage/exceptions?booked_id={a_booking_id}", headers=H, timeout=20)
    assert r2.status_code == 200
    ids = [i["exception_id"] for i in r2.json()["items"]]
    assert eid in ids

    # Resolve
    r3 = requests.post(f"{BASE_URL}/api/shipment-triage/exceptions/{eid}/status", headers=H,
                       json={"status": "resolved", "resolution_notes": "TEST_iter41 fixed"}, timeout=20)
    assert r3.status_code == 200, r3.text
    updated = r3.json()
    assert updated["status"] == "resolved"
    assert updated.get("resolution_notes") == "TEST_iter41 fixed"
    assert updated.get("resolved_at")


def test_status_unknown_exception_404():
    r = requests.post(f"{BASE_URL}/api/shipment-triage/exceptions/EX-FAKEFAKE/status", headers=H,
                      json={"status": "resolved"}, timeout=20)
    assert r.status_code == 404


# ---------- dashboard ----------
def test_dashboard_shape():
    r = requests.get(f"{BASE_URL}/api/shipment-triage/dashboard", headers=H, timeout=20)
    assert r.status_code == 200, r.text
    d = r.json()
    for k in ("active_count", "critical_count", "high_count", "by_type", "by_severity",
              "mttr_hours", "resolved_total", "is_after_hours"):
        assert k in d, f"missing {k}"
    assert isinstance(d["active_count"], int)
    assert isinstance(d["resolved_total"], int)
    # mttr_hours can be None when no resolved (but we resolved one in test_manual_create_status_filter_resolve)
    if d["resolved_total"] > 0:
        # If recently resolved, MTTR should be a non-negative float
        assert d["mttr_hours"] is None or isinstance(d["mttr_hours"], (int, float))


# ---------- ai polish graceful ----------
def test_ai_polish_graceful(a_booking_id):
    # Create a fresh exception to polish
    payload = {"booked_id": a_booking_id, "exception_type": "off_route", "severity": "medium",
               "signal": "TEST_iter41 ai polish"}
    r = requests.post(f"{BASE_URL}/api/shipment-triage/exceptions", headers=H, json=payload, timeout=20)
    assert r.status_code == 200
    eid = r.json()["exception_id"]
    rp = requests.post(f"{BASE_URL}/api/shipment-triage/exceptions/{eid}/ai-polish",
                       headers=H, timeout=90)
    # Either AI succeeds or gracefully returns ai_polished False with reason — both are valid (no 5xx)
    assert rp.status_code == 200, rp.text
    body = rp.json()
    assert "exception_id" in body
    assert body["exception_id"] == eid
    # Should not raise — either polished true with text, or polished false with note/error
    if body.get("ai_polished"):
        assert isinstance(body.get("advice_ai_polished", ""), str) and body["advice_ai_polished"]
    else:
        assert "note" in body or "error" in body
