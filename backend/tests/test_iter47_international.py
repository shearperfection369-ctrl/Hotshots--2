"""Iteration 47 — International (Ocean + Rail) module backend tests.

Validates reference data, container booking CRUD, lifecycle progression,
gate events, rail waybill attachment, and branded PDF generation (House BL + SLI).
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
TOKEN = "test_session_admin_1"
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
INTL = f"{BASE_URL}/api/international"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


# ---------------- REFERENCE ----------------
def test_reference_endpoint(session):
    r = session.get(f"{INTL}/reference", timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data["ocean_carriers"]) >= 18
    assert len(data["rail_carriers"]) >= 10
    assert len(data["rail_yards"]) >= 40
    assert len(data["container_types"]) >= 10
    assert len(data["container_statuses"]) == 8


def test_ocean_carriers_scac_values(session):
    r = session.get(f"{INTL}/ocean-carriers", timeout=20)
    assert r.status_code == 200
    items = r.json().get("items", r.json()) if isinstance(r.json(), dict) else r.json()
    by_scac = {c["scac"]: c["name"] for c in items}
    assert by_scac.get("MAEU") == "Maersk"
    assert by_scac.get("MSCU") == "MSC"


def test_rail_yards_filter_by_railroad(session):
    r = session.get(f"{INTL}/rail-yards", params={"railroad": "BNSF"}, timeout=20)
    assert r.status_code == 200
    items = r.json().get("items", r.json()) if isinstance(r.json(), dict) else r.json()
    assert len(items) > 0
    assert all(y["railroad"] == "BNSF" for y in items)


def test_rail_yards_filter_by_city_memphis(session):
    r = session.get(f"{INTL}/rail-yards", params={"city": "Memphis"}, timeout=20)
    assert r.status_code == 200
    items = r.json().get("items", r.json()) if isinstance(r.json(), dict) else r.json()
    assert len(items) >= 2
    railroads = {y["railroad"] for y in items}
    # Should span multiple Class-I railroads in Memphis
    assert len(railroads) >= 2


def test_container_types(session):
    r = session.get(f"{INTL}/container-types", timeout=20)
    assert r.status_code == 200
    items = r.json().get("items", r.json()) if isinstance(r.json(), dict) else r.json()
    codes = {c.get("code") or c.get("type") for c in items}
    # Standard codes
    assert any(c in codes for c in ["20DC", "40DC", "40HC"])


# ---------------- BOOKING LIFECYCLE ----------------
BOOKING_PAYLOAD = {
    "carrier_scac": "MAEU",
    "booking_number": "TEST_BK_47_001",
    "vessel_name": "Maersk Edinburgh",
    "voyage_number": "045E",
    "pol": "CNSHA",
    "pod": "USLAX",
    "commodity": "Electronics — TEST",
    "container_number": "MAEU1234567",
    "container_type": "40HC",
    "weight_kg": 18500,
    "shipper_name": "TEST Shanghai Exporters Co.",
    "consignee_name": "TEST LA Importers LLC",
    "hazmat": False,
}


@pytest.fixture(scope="module")
def created_booking(session):
    r = session.post(f"{INTL}/container-bookings", json=BOOKING_PAYLOAD, timeout=20)
    assert r.status_code in (200, 201), f"{r.status_code} {r.text}"
    data = r.json()
    assert data["booking_id"].startswith("INTL-"), data
    assert data["status"] == "BOOKED"
    assert isinstance(data.get("status_history"), list) and len(data["status_history"]) == 1
    yield data
    # cleanup: best-effort delete (no delete endpoint exists per code) — skip


def test_create_booking_shape(created_booking):
    bk = created_booking
    assert bk["carrier_scac"] == "MAEU"
    assert bk["booking_number"] == "TEST_BK_47_001"


def test_get_booking_persisted(session, created_booking):
    r = session.get(f"{INTL}/container-bookings/{created_booking['booking_id']}", timeout=20)
    assert r.status_code == 200
    assert r.json()["booking_id"] == created_booking["booking_id"]


def test_list_bookings_filter_carrier(session, created_booking):
    r = session.get(f"{INTL}/container-bookings", params={"carrier_scac": "MAEU"}, timeout=20)
    assert r.status_code == 200
    payload = r.json()
    items = payload.get("items", payload) if isinstance(payload, dict) else payload
    ids = [b["booking_id"] for b in items]
    assert created_booking["booking_id"] in ids


def test_gate_ingate_advances_status(session, created_booking):
    bid = created_booking["booking_id"]
    r = session.post(
        f"{INTL}/container-bookings/{bid}/gate",
        json={"event_type": "ingate", "terminal_code": "APM400", "location_unlocode": "USLAX"},
        timeout=20,
    )
    assert r.status_code in (200, 201), r.text
    data = r.json()
    # Re-fetch to confirm
    r2 = session.get(f"{INTL}/container-bookings/{bid}", timeout=20)
    bk = r2.json()
    assert bk["status"] == "GATE_IN_ORIGIN", bk
    assert len(bk["status_history"]) >= 2


def test_attach_waybill(session, created_booking):
    bid = created_booking["booking_id"]
    r = session.post(
        f"{INTL}/container-bookings/{bid}/waybill",
        json={
            "railroad_scac": "BNSF",
            "waybill_number": "TEST_WB_47_001",
            "origin_yard": "Los Angeles Hobart",
            "destination_yard": "Chicago Logistics Park",
            "equipment_initial": "BNSF",
            "equipment_number": "234567",
        },
        timeout=20,
    )
    assert r.status_code in (200, 201), r.text
    data = r.json()
    # check waybill id starts with WB-
    wb_id = data.get("waybill_id") or (data.get("waybill", {}) or {}).get("waybill_id")
    if not wb_id:
        # may be returned in updated booking
        wbs = data.get("rail_waybills") or []
        assert wbs, data
        wb_id = wbs[0].get("waybill_id")
    assert wb_id and wb_id.startswith("WB-"), data


def test_status_advance_valid(session, created_booking):
    bid = created_booking["booking_id"]
    # GATE_IN_ORIGIN → ON_VESSEL
    r = session.post(f"{INTL}/container-bookings/{bid}/status", json={"new_status": "ON_VESSEL"}, timeout=20)
    assert r.status_code in (200, 201), r.text
    bk = session.get(f"{INTL}/container-bookings/{bid}", timeout=20).json()
    assert bk["status"] == "ON_VESSEL"


def test_status_reject_invalid(session, created_booking):
    bid = created_booking["booking_id"]
    r = session.post(f"{INTL}/container-bookings/{bid}/status", json={"new_status": "NOT_A_REAL_STATUS"}, timeout=20)
    assert r.status_code in (400, 422), r.text


def test_house_bl_pdf(session, created_booking):
    bid = created_booking["booking_id"]
    r = session.get(f"{INTL}/container-bookings/{bid}/house-bl.pdf", timeout=60)
    assert r.status_code == 200, r.text[:300]
    assert r.headers.get("content-type", "").startswith("application/pdf")
    assert len(r.content) > 100 * 1024, f"PDF too small: {len(r.content)}"


def test_sli_pdf(session, created_booking):
    bid = created_booking["booking_id"]
    r = session.get(f"{INTL}/container-bookings/{bid}/sli.pdf", timeout=60)
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("application/pdf")
    assert len(r.content) > 100 * 1024


def test_invalid_carrier_scac_404(session):
    bad = dict(BOOKING_PAYLOAD)
    bad["carrier_scac"] = "XXXX"
    bad["booking_number"] = "TEST_BK_47_BAD"
    r = session.post(f"{INTL}/container-bookings", json=bad, timeout=20)
    assert r.status_code == 404, f"expected 404, got {r.status_code}: {r.text[:300]}"


def test_outgate_advances_to_outgated(session):
    # create a fresh booking and outgate it
    payload = dict(BOOKING_PAYLOAD)
    payload["booking_number"] = "TEST_BK_47_OUTGATE"
    payload["container_number"] = "MAEU7654321"
    r = session.post(f"{INTL}/container-bookings", json=payload, timeout=20)
    assert r.status_code in (200, 201), r.text
    bid = r.json()["booking_id"]
    g = session.post(
        f"{INTL}/container-bookings/{bid}/gate",
        json={"event_type": "outgate", "terminal_code": "BNSF_LPC"},
        timeout=20,
    )
    assert g.status_code in (200, 201), g.text
    bk = session.get(f"{INTL}/container-bookings/{bid}", timeout=20).json()
    assert bk["status"] == "OUTGATED", bk
