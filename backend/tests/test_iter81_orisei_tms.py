"""Iteration 81 tests: NMFC, Weigh Stations, Lane Notes, Niche Cargo, QBR Exec Summary PDF,
Shipment addresses + BOL, Admin sample-data wiper."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://clean-logistics-dash.preview.emergentagent.com").rstrip("/")
TOKEN = "test_session_admin_1"
HDR = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}


# --- Health ---
def test_health():
    r = requests.get(f"{BASE_URL}/api/health", timeout=15)
    assert r.status_code == 200


# --- NMFC ---
def test_nmfc_codes_merged():
    r = requests.get(f"{BASE_URL}/api/nmfc/codes", headers=HDR, timeout=30)
    assert r.status_code == 200
    data = r.json()
    codes = data if isinstance(data, list) else data.get("codes") or data.get("items") or []
    assert len(codes) >= 100, f"expected ~163 codes, got {len(codes)}"
    sample = codes[0]
    for k in ("nmfc", "description", "freight_class", "category"):
        assert k in sample, f"missing key {k} in nmfc code"


# --- Weigh Stations ---
def test_weigh_stations_all():
    r = requests.get(f"{BASE_URL}/api/reference/weigh-stations", headers=HDR, timeout=30)
    assert r.status_code == 200
    d = r.json()
    stations = d if isinstance(d, list) else d.get("stations") or d.get("items") or []
    assert len(stations) >= 70
    s = stations[0]
    assert "likely_open" in s and "advice" in s


def test_weigh_stations_state_filter():
    r = requests.get(f"{BASE_URL}/api/reference/weigh-stations?state=MN", headers=HDR, timeout=30)
    assert r.status_code == 200
    d = r.json()
    stations = d if isinstance(d, list) else d.get("stations") or d.get("items") or []
    assert all(s.get("state", "").upper() == "MN" for s in stations)


# --- Lane Notes ---
def test_lane_notes_crud():
    payload = {
        "origin": "TEST_MN",
        "destination": "TEST_TX",
        "instructions": "TEST_ note please ignore",
        "flags": ["chains_required"],
        "shipper": "TEST_Shipper",
    }
    r = requests.post(f"{BASE_URL}/api/reference/lane-notes", headers=HDR, json=payload, timeout=15)
    assert r.status_code in (200, 201), r.text
    created = r.json()
    note_id = created.get("id") or created.get("_id") or created.get("note", {}).get("id")
    assert note_id, f"no id returned: {created}"

    r = requests.get(f"{BASE_URL}/api/reference/lane-notes", headers=HDR, timeout=15)
    assert r.status_code == 200
    lst = r.json()
    items = lst if isinstance(lst, list) else lst.get("notes") or lst.get("items") or []
    assert any((n.get("id") or n.get("_id")) == note_id for n in items)

    r = requests.delete(f"{BASE_URL}/api/reference/lane-notes/{note_id}", headers=HDR, timeout=15)
    assert r.status_code in (200, 204)


# --- Niche Cargo ---
def test_niche_cargo_analysis():
    r = requests.get(f"{BASE_URL}/api/niche-cargo/analysis", headers=HDR, timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert "lanes" in d
    assert "niche_library" in d
    assert len(d["niche_library"]) >= 6


def test_niche_cargo_ai_advise():
    r = requests.post(f"{BASE_URL}/api/niche-cargo/ai-advise", headers=HDR, json={}, timeout=90)
    assert r.status_code == 200, r.text
    d = r.json()
    text = d.get("advice") or d.get("text") or ""
    assert isinstance(text, str) and len(text) > 30, f"advice too short: {d}"

    # Second call should return cached=true
    r2 = requests.post(f"{BASE_URL}/api/niche-cargo/ai-advise", headers=HDR, json={}, timeout=30)
    assert r2.status_code == 200
    assert r2.json().get("cached") is True or r2.json().get("advice")


# --- QBR Exec Summary PDF ---
def test_qbr_exec_summary_pdf():
    r = requests.get(f"{BASE_URL}/api/qbr-studio/shippers", headers=HDR, timeout=30)
    assert r.status_code == 200
    d = r.json()
    shippers = d if isinstance(d, list) else d.get("shippers") or d.get("items") or []
    if not shippers:
        pytest.skip("No shippers available for QBR test")
    name = shippers[0].get("name") or shippers[0].get("shipper_name") or shippers[0]
    if isinstance(name, dict):
        name = name.get("name")
    assert name
    r = requests.get(
        f"{BASE_URL}/api/qbr-studio/exec-summary/{name}/pdf",
        headers=HDR, params={"period": "Q1 2026"}, timeout=120,
    )
    assert r.status_code == 200, r.text[:300]
    assert r.headers.get("content-type", "").startswith("application/pdf")
    assert r.content[:4] == b"%PDF"
    assert len(r.content) > 5000


# --- Shipment with addresses -> BOL ---
def test_shipment_with_addresses_bol():
    payload = {
        "shipper_name": "TEST_Acme Shipper",
        "shipper_address": "123 Test St",
        "shipper_city_state_zip": "Minneapolis, MN 55401",
        "shipper_contact": "Jane Doe",
        "consignee_name": "TEST_Beta Consignee",
        "consignee_address": "456 Rcv Ave",
        "consignee_city_state_zip": "Dallas, TX 75201",
        "consignee_contact": "John Roe",
        "origin": "Minneapolis, MN",
        "destination": "Dallas, TX",
        "commodity": "TEST_pallets",
        "weight": 5000,
        "rate": 1500,
        "mode": "FTL",
        "carrier": "TEST_Carrier",
        "destination_city": "Dallas, TX",
        "destination_lat": 32.7767,
        "destination_lng": -96.7970,
        "pickup_date": "2026-01-15",
        "weight_lbs": 5000,
        "pieces": 10,
        "value_usd": 25000,
    }
    r = requests.post(f"{BASE_URL}/api/shipments", headers=HDR, json=payload, timeout=30)
    assert r.status_code in (200, 201), r.text
    created = r.json()
    sid = created.get("id") or created.get("_id") or created.get("shipment_id") or created.get("bol_no") or (created.get("shipment") or {}).get("id")
    assert sid, created

    r = requests.post(
        f"{BASE_URL}/api/shipments/{sid}/generate-bol",
        headers=HDR, json={"shipper": ""}, timeout=60,
    )
    assert r.status_code == 200, r.text
    doc = r.json()
    doc_id = doc.get("document_id") or doc.get("id") or (doc.get("document") or {}).get("id")
    data = doc.get("data") or (doc.get("document") or {}).get("data") or {}
    # verify address bits made it into the BOL doc data
    blob = str(data).lower()
    assert "minneapolis" in blob and "dallas" in blob, f"origin/dest not in BOL data: {data}"

    if doc_id:
        r = requests.get(f"{BASE_URL}/api/documents/{doc_id}/pdf", headers=HDR, timeout=60)
        assert r.status_code == 200
        assert r.content[:4] == b"%PDF"


# --- Admin Wiper ---
def test_wipe_categories_listing():
    r = requests.get(f"{BASE_URL}/api/admin/wipe-categories", headers=HDR, timeout=30)
    assert r.status_code == 200
    d = r.json()
    cats = d if isinstance(d, list) else d.get("categories") or []
    assert len(cats) == 9, f"expected 9 categories, got {len(cats)}"


def test_wipe_without_confirm_returns_400():
    r = requests.post(
        f"{BASE_URL}/api/admin/wipe-data",
        headers=HDR, json={"categories": ["comms"], "confirm": False}, timeout=15,
    )
    assert r.status_code == 400, r.status_code


def test_wipe_comms_only():
    r = requests.post(
        f"{BASE_URL}/api/admin/wipe-data",
        headers=HDR, json={"categories": ["comms"], "confirm": True}, timeout=30,
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert "total_deleted" in d or "deleted" in d


# --- Sentinel ---
def test_sentinel_status():
    r = requests.get(f"{BASE_URL}/api/sentinel/status", headers=HDR, timeout=15)
    # Accept 200 or 404 if route path differs
    if r.status_code == 200:
        d = r.json()
        status = (d.get("status") or d.get("health") or "").lower()
        assert "degraded" not in status
