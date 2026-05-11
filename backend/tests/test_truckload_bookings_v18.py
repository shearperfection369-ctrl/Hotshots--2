"""
Truckload Booking Sheet — v1.8 backend tests
Covers: list/version/POST/PATCH/DELETE + workbook/tabs idempotent seed.
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://clean-logistics-dash.preview.emergentagent.com").rstrip("/")
ADMIN = {"Authorization": "Bearer test_session_admin_1", "Content-Type": "application/json"}

EXPECTED_COL_KEYS = {
    "date", "bol_no", "po_no", "carrier", "origin", "destination", "pieces",
    "weight_lbs", "pallets", "lift_gate", "freight_class", "nmfc_code",
    "equipment", "pickup_date", "delivery_date", "rate_usd", "status", "notes",
}


# ------------------- TABS / SEED -------------------
class TestTabsSeed:
    def test_tabs_include_truckload_bookings_at_order_zero(self):
        r = requests.get(f"{BASE_URL}/api/workbook/tabs", headers=ADMIN, timeout=15)
        assert r.status_code == 200, r.text
        tabs = r.json()
        assert isinstance(tabs, list) and len(tabs) > 0
        kinds = [t["kind"] for t in tabs]
        assert "truckload_bookings" in kinds, f"truckload_bookings not seeded: {kinds}"
        # First tab should be the editable one
        assert tabs[0]["kind"] == "truckload_bookings", f"first tab is {tabs[0]['kind']}"
        # columns attached
        cols = tabs[0]["columns"]
        keys = {c["key"] for c in cols}
        assert keys == EXPECTED_COL_KEYS, f"missing keys: {EXPECTED_COL_KEYS - keys}"

    def test_seed_is_idempotent(self):
        r1 = requests.get(f"{BASE_URL}/api/workbook/tabs", headers=ADMIN, timeout=15).json()
        r2 = requests.get(f"{BASE_URL}/api/workbook/tabs", headers=ADMIN, timeout=15).json()
        kinds1 = [t["kind"] for t in r1]
        kinds2 = [t["kind"] for t in r2]
        assert kinds1.count("truckload_bookings") == 1
        assert kinds2.count("truckload_bookings") == 1
        assert len(r1) == len(r2)


# ------------------- LIST -------------------
class TestList:
    def test_list_returns_rows_columns_version(self):
        r = requests.get(f"{BASE_URL}/api/workbook/truckload-bookings", headers=ADMIN, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "rows" in data and isinstance(data["rows"], list)
        assert "columns" in data and len(data["columns"]) == 18
        assert "version" in data
        keys = {c["key"] for c in data["columns"]}
        assert keys == EXPECTED_COL_KEYS
        # Each select column has options
        for c in data["columns"]:
            if c["type"] == "select":
                assert isinstance(c.get("options"), list) and len(c["options"]) > 0


# ------------------- VERSION -------------------
class TestVersionPoll:
    def test_version_endpoint_shape(self):
        r = requests.get(f"{BASE_URL}/api/workbook/truckload-bookings/version", headers=ADMIN, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert "version" in d
        assert "updated_at" in d
        assert "last_editor" in d


# ------------------- CRUD -------------------
class TestCRUD:
    created_id = None

    def test_01_create_row(self):
        v_before = requests.get(f"{BASE_URL}/api/workbook/truckload-bookings/version", headers=ADMIN).json().get("version", 0)
        payload = {"data": {"carrier": "TEST_XPO", "origin": "Minneapolis, MN", "pieces": 12, "status": "Quoted"}}
        r = requests.post(f"{BASE_URL}/api/workbook/truckload-bookings", headers=ADMIN, json=payload, timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "row" in body and "version" in body
        row = body["row"]
        assert row["id"].startswith("TLB-")
        assert row["carrier"] == "TEST_XPO"
        assert row["pieces"] == 12
        assert row["status"] == "Quoted"
        assert row["created_by"] and row["updated_by"]
        # All 18 columns present (None where not provided)
        for k in EXPECTED_COL_KEYS:
            assert k in row, f"missing column {k}"
        assert row["destination"] is None  # not supplied
        assert body["version"] > v_before
        TestCRUD.created_id = row["id"]

    def test_02_patch_only_passed_keys_and_drops_unknown(self):
        rid = TestCRUD.created_id
        assert rid, "create test must run first"
        v_before = requests.get(f"{BASE_URL}/api/workbook/truckload-bookings/version", headers=ADMIN).json()["version"]
        # send one known + one unknown key
        payload = {"data": {"pieces": 99, "totally_made_up_key": "ignore_me"}}
        r = requests.patch(f"{BASE_URL}/api/workbook/truckload-bookings/{rid}", headers=ADMIN, json=payload, timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        row = body["row"]
        assert row["pieces"] == 99
        assert row["carrier"] == "TEST_XPO"  # unchanged
        assert "totally_made_up_key" not in row
        assert body["version"] > v_before

        # GET to verify persistence
        rows = requests.get(f"{BASE_URL}/api/workbook/truckload-bookings", headers=ADMIN).json()["rows"]
        match = [x for x in rows if x["id"] == rid][0]
        assert match["pieces"] == 99
        assert match["carrier"] == "TEST_XPO"

    def test_03_patch_status_select(self):
        rid = TestCRUD.created_id
        r = requests.patch(f"{BASE_URL}/api/workbook/truckload-bookings/{rid}",
                           headers=ADMIN, json={"data": {"status": "Booked"}}, timeout=15)
        assert r.status_code == 200
        assert r.json()["row"]["status"] == "Booked"

    def test_04_version_bumps_per_edit(self):
        v1 = requests.get(f"{BASE_URL}/api/workbook/truckload-bookings/version", headers=ADMIN).json()["version"]
        rid = TestCRUD.created_id
        requests.patch(f"{BASE_URL}/api/workbook/truckload-bookings/{rid}",
                       headers=ADMIN, json={"data": {"notes": "ping1"}}, timeout=15)
        v2 = requests.get(f"{BASE_URL}/api/workbook/truckload-bookings/version", headers=ADMIN).json()["version"]
        assert v2 == v1 + 1
        # last_editor stamped
        meta = requests.get(f"{BASE_URL}/api/workbook/truckload-bookings/version", headers=ADMIN).json()
        assert meta.get("last_editor")

    def test_05_delete_row(self):
        rid = TestCRUD.created_id
        v_before = requests.get(f"{BASE_URL}/api/workbook/truckload-bookings/version", headers=ADMIN).json()["version"]
        r = requests.delete(f"{BASE_URL}/api/workbook/truckload-bookings/{rid}", headers=ADMIN, timeout=15)
        assert r.status_code in (200, 204), r.text
        v_after = requests.get(f"{BASE_URL}/api/workbook/truckload-bookings/version", headers=ADMIN).json()["version"]
        assert v_after > v_before
        # GET to verify removal
        rows = requests.get(f"{BASE_URL}/api/workbook/truckload-bookings", headers=ADMIN).json()["rows"]
        assert not [x for x in rows if x["id"] == rid]

    def test_06_patch_404_for_missing(self):
        r = requests.patch(f"{BASE_URL}/api/workbook/truckload-bookings/TLB-NOPE0000",
                           headers=ADMIN, json={"data": {"carrier": "x"}}, timeout=15)
        assert r.status_code == 404

    def test_07_delete_404_for_missing(self):
        r = requests.delete(f"{BASE_URL}/api/workbook/truckload-bookings/TLB-GONE0000", headers=ADMIN, timeout=15)
        assert r.status_code == 404


# ------------------- AUTHZ -------------------
class TestAuthz:
    def test_unauthenticated_blocked(self):
        r = requests.get(f"{BASE_URL}/api/workbook/truckload-bookings", timeout=15)
        assert r.status_code in (401, 403)
