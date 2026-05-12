"""Iteration 16 tests:
- Suppliers (list / POST custom / DELETE custom + seed protection)
- Drivers (list / POST)
- Trailers (list / POST)
- Manual content v2.0 cover + new slides
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://clean-logistics-dash.preview.emergentagent.com").rstrip("/")
ADMIN_TOKEN = "test_session_admin_1"


@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    s.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {ADMIN_TOKEN}",
    })
    return s


# ---------- Suppliers ----------
class TestSuppliers:
    def test_list_suppliers_seed(self, admin):
        r = admin.get(f"{BASE_URL}/api/suppliers")
        assert r.status_code == 200, r.text
        body = r.json()
        # endpoint may return list or {suppliers,...}
        suppliers = body if isinstance(body, list) else body.get("suppliers", [])
        assert isinstance(suppliers, list) and len(suppliers) > 0
        ids = {s.get("id") or s.get("supplier_id") for s in suppliers}
        assert "SUP-001" in ids, f"expected seeded SUP-001 in {ids}"

    def test_create_and_delete_custom_supplier(self, admin):
        name = f"TEST_Supplier_{int(time.time())}"
        payload = {"name": name, "category": "Misc", "contact_email": "x@y.com"}
        r = admin.post(f"{BASE_URL}/api/suppliers", json=payload)
        assert r.status_code in (200, 201), r.text
        body = r.json()
        # response shape: {ok: true, supplier: {...}}
        created = body.get("supplier") if isinstance(body, dict) and "supplier" in body else body
        sid = created.get("supplier_id") or created.get("id")
        assert sid and sid.startswith("SUP-C"), f"unexpected id {sid}"
        assert created.get("name") == name

        # verify it appears in GET
        r2 = admin.get(f"{BASE_URL}/api/suppliers")
        body = r2.json()
        suppliers = body if isinstance(body, list) else body.get("suppliers", [])
        found = next((s for s in suppliers if (s.get("id") or s.get("supplier_id")) == sid), None)
        assert found is not None, f"created supplier {sid} not in list"

        # delete
        rd = admin.delete(f"{BASE_URL}/api/suppliers/{sid}")
        assert rd.status_code in (200, 204), rd.text

        # confirm gone
        r3 = admin.get(f"{BASE_URL}/api/suppliers")
        body3 = r3.json()
        suppliers3 = body3 if isinstance(body3, list) else body3.get("suppliers", [])
        ids = {s.get("id") or s.get("supplier_id") for s in suppliers3}
        assert sid not in ids

    def test_create_supplier_requires_name(self, admin):
        r = admin.post(f"{BASE_URL}/api/suppliers", json={"category": "Misc"})
        assert r.status_code in (400, 422), f"expected validation error, got {r.status_code}: {r.text}"

    def test_delete_seed_supplier_returns_404(self, admin):
        r = admin.delete(f"{BASE_URL}/api/suppliers/SUP-001")
        assert r.status_code == 404, f"expected 404 on seed delete, got {r.status_code}: {r.text}"


# ---------- Drivers ----------
class TestDrivers:
    def test_list_drivers(self, admin):
        r = admin.get(f"{BASE_URL}/api/drivers")
        assert r.status_code == 200, r.text
        body = r.json()
        drivers = body if isinstance(body, list) else body.get("drivers", [])
        assert isinstance(drivers, list)

    def test_create_driver(self, admin):
        name = f"TEST_Driver_{int(time.time())}"
        r = admin.post(f"{BASE_URL}/api/drivers", json={"name": name})
        assert r.status_code in (200, 201), r.text
        created = r.json()
        assert created.get("name") == name
        # verify via list
        rl = admin.get(f"{BASE_URL}/api/drivers")
        drivers = rl.json() if isinstance(rl.json(), list) else rl.json().get("drivers", [])
        assert any(d.get("name") == name for d in drivers)


# ---------- Trailers ----------
class TestTrailers:
    def test_list_trailers(self, admin):
        r = admin.get(f"{BASE_URL}/api/trailers")
        assert r.status_code == 200, r.text
        body = r.json()
        trailers = body if isinstance(body, list) else body.get("trailers", [])
        assert isinstance(trailers, list)

    def test_create_trailer(self, admin):
        unit = f"TEST-TRL-{int(time.time())}"
        r = admin.post(f"{BASE_URL}/api/trailers", json={"trailer_no": unit, "type": "Dry Van 53'", "carrier": "TEST_Carrier"})
        assert r.status_code in (200, 201), r.text


# ---------- Manual v2 ----------
class TestManualV2:
    def test_manual_cover_v2(self, admin):
        r = admin.get(f"{BASE_URL}/api/manual/content")
        assert r.status_code == 200, r.text
        body = r.json()
        # Find title across possible shapes
        text_blob = str(body).lower()
        assert "v2.0" in text_blob or "v2" in text_blob, "expected v2 marker in manual content"

    def test_manual_has_new_feature_slides(self, admin):
        r = admin.get(f"{BASE_URL}/api/manual/content")
        body = r.json()
        blob = str(body).lower()
        expected_terms = [
            "copilot",
            "power bi",
            "sharepoint",
            "specialty",
            "driver",
            "trailer",
            "chess",
            "theme",
            "routing",
            "promo",
        ]
        missing = [t for t in expected_terms if t not in blob]
        assert not missing, f"missing terms in manual: {missing}"
