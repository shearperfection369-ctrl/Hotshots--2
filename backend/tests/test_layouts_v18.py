"""
Iteration 18 — User Layouts + regression for /api/kpis, /api/shipments,
/api/equipment/analytics, /api/equipment/reports.

Layout endpoints (/api/user/layouts/{page_key}):
  - GET returns {order: []} for fresh user
  - PUT saves an order, GET returns saved value
  - PUT empty -> 400, PUT >200 ids -> 400
  - DELETE resets it
  - Cross-user isolation: admin & dispatcher independent layouts
  - Page-key agnostic (dashboard / trade-compliance / equipment)
"""
import os
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://clean-logistics-dash.preview.emergentagent.com").rstrip("/")
ADMIN_TOKEN = "test_session_admin_1"
DISP_TOKEN = "test_disp_session"


def _hdr(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


PAGES = ["dashboard", "trade-compliance", "equipment"]


@pytest.fixture(scope="module", autouse=True)
def _cleanup():
    # Clean any prior saved layouts so tests start from a fresh state
    for tok in (ADMIN_TOKEN, DISP_TOKEN):
        for p in PAGES:
            requests.delete(f"{BASE_URL}/api/user/layouts/{p}", headers=_hdr(tok))
    yield
    for tok in (ADMIN_TOKEN, DISP_TOKEN):
        for p in PAGES:
            requests.delete(f"{BASE_URL}/api/user/layouts/{p}", headers=_hdr(tok))


class TestAuthSanity:
    def test_admin_token_valid(self):
        r = requests.get(f"{BASE_URL}/api/auth/me", headers=_hdr(ADMIN_TOKEN))
        assert r.status_code == 200, r.text
        assert r.json()["role"] == "admin"

    def test_dispatcher_token_valid(self):
        r = requests.get(f"{BASE_URL}/api/auth/me", headers=_hdr(DISP_TOKEN))
        assert r.status_code == 200, r.text
        assert r.json()["role"] == "dispatcher"

    def test_unauth_get_returns_401(self):
        r = requests.get(f"{BASE_URL}/api/user/layouts/dashboard")
        assert r.status_code == 401


class TestLayoutCRUD:
    @pytest.mark.parametrize("page_key", PAGES)
    def test_get_empty_for_fresh_user(self, page_key):
        r = requests.get(f"{BASE_URL}/api/user/layouts/{page_key}", headers=_hdr(ADMIN_TOKEN))
        assert r.status_code == 200, r.text
        body = r.json()
        assert "order" in body
        assert isinstance(body["order"], list)
        assert body["order"] == []

    @pytest.mark.parametrize("page_key,order", [
        ("dashboard", ["main-grid", "kpis", "sap-quick", "news-ticker", "video-row"]),
        ("trade-compliance", ["summary", "incoterms", "tariffs", "hs-codes"]),
        ("equipment", ["kpis", "charts-top", "charts-bottom", "tables", "history"]),
    ])
    def test_put_saves_and_get_returns_same(self, page_key, order):
        r = requests.put(
            f"{BASE_URL}/api/user/layouts/{page_key}",
            json={"order": order},
            headers=_hdr(ADMIN_TOKEN),
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        assert body["order"] == order

        # Verify persistence
        g = requests.get(f"{BASE_URL}/api/user/layouts/{page_key}", headers=_hdr(ADMIN_TOKEN))
        assert g.status_code == 200
        assert g.json()["order"] == order

    def test_put_empty_order_returns_400(self):
        r = requests.put(
            f"{BASE_URL}/api/user/layouts/dashboard",
            json={"order": []},
            headers=_hdr(ADMIN_TOKEN),
        )
        assert r.status_code == 400, r.text

    def test_put_too_many_ids_returns_400(self):
        big = [f"t{i}" for i in range(201)]
        r = requests.put(
            f"{BASE_URL}/api/user/layouts/dashboard",
            json={"order": big},
            headers=_hdr(ADMIN_TOKEN),
        )
        assert r.status_code == 400, r.text

    def test_delete_resets_layout(self):
        # Seed
        order = ["a", "b", "c"]
        requests.put(
            f"{BASE_URL}/api/user/layouts/dashboard",
            json={"order": order},
            headers=_hdr(ADMIN_TOKEN),
        )
        # Delete
        r = requests.delete(f"{BASE_URL}/api/user/layouts/dashboard", headers=_hdr(ADMIN_TOKEN))
        assert r.status_code == 200, r.text
        assert r.json()["ok"] is True
        # Verify cleared
        g = requests.get(f"{BASE_URL}/api/user/layouts/dashboard", headers=_hdr(ADMIN_TOKEN))
        assert g.status_code == 200
        assert g.json()["order"] == []


class TestCrossUserIsolation:
    def test_admin_and_dispatcher_have_independent_layouts(self):
        admin_order = ["main-grid", "kpis", "sap-quick"]
        disp_order = ["kpis", "main-grid", "news-ticker"]
        # Admin saves its order
        r1 = requests.put(
            f"{BASE_URL}/api/user/layouts/dashboard",
            json={"order": admin_order},
            headers=_hdr(ADMIN_TOKEN),
        )
        assert r1.status_code == 200
        # Dispatcher saves a different order
        r2 = requests.put(
            f"{BASE_URL}/api/user/layouts/dashboard",
            json={"order": disp_order},
            headers=_hdr(DISP_TOKEN),
        )
        assert r2.status_code == 200
        # Each user retrieves their own
        ga = requests.get(f"{BASE_URL}/api/user/layouts/dashboard", headers=_hdr(ADMIN_TOKEN))
        gd = requests.get(f"{BASE_URL}/api/user/layouts/dashboard", headers=_hdr(DISP_TOKEN))
        assert ga.json()["order"] == admin_order
        assert gd.json()["order"] == disp_order
        assert ga.json()["order"] != gd.json()["order"]


# Regression for primary endpoints
class TestRegression:
    def test_kpis(self):
        r = requests.get(f"{BASE_URL}/api/kpis", headers=_hdr(ADMIN_TOKEN))
        assert r.status_code == 200
        body = r.json()
        assert "totals" in body
        assert "by_mode" in body

    def test_shipments(self):
        r = requests.get(f"{BASE_URL}/api/shipments", headers=_hdr(ADMIN_TOKEN))
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_equipment_analytics(self):
        r = requests.get(f"{BASE_URL}/api/equipment/analytics", headers=_hdr(ADMIN_TOKEN))
        assert r.status_code == 200

    def test_equipment_reports(self):
        r = requests.get(f"{BASE_URL}/api/equipment/reports", headers=_hdr(ADMIN_TOKEN))
        assert r.status_code == 200


class TestPromoAsset:
    def test_promo_mp4_head(self):
        r = requests.head(f"{BASE_URL}/promo.mp4", allow_redirects=True)
        assert r.status_code == 200, r.text
        ct = r.headers.get("content-type", "")
        assert "video/mp4" in ct, ct
        size = int(r.headers.get("content-length", 0))
        assert 1_000_000 <= size <= 5_500_000, f"size={size}"

    def test_promo_mp4_ftyp_header(self):
        # Range request first 16 bytes — should contain 'ftyp' in bytes 4-8
        r = requests.get(
            f"{BASE_URL}/promo.mp4",
            headers={"Range": "bytes=0-15"},
            stream=True,
        )
        assert r.status_code in (200, 206)
        head = r.content[:16]
        assert b"ftyp" in head, f"head={head!r}"
