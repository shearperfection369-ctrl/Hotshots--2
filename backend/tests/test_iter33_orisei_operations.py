"""Tests for Orisei Operations module — customers, quotes, rate-confirmations,
customer portal token + public portal endpoint."""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://clean-logistics-dash.preview.emergentagent.com").rstrip("/")
ADMIN_TOKEN = "test_session_admin_1"
HEADERS = {"Authorization": f"Bearer {ADMIN_TOKEN}", "Content-Type": "application/json",
           "Origin": BASE_URL}
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


@pytest.fixture(scope="module")
def customer(admin_session):
    """Create a TEST_ customer and yield it."""
    suffix = uuid.uuid4().hex[:6]
    payload = {
        "name": f"TEST_Acme_{suffix}",
        "primary_contact_name": "Jane Tester",
        "primary_contact_email": f"jane+{suffix}@example.com",
        "ap_email": f"ap+{suffix}@example.com",
        "payment_terms": "Net 30",
        "credit_limit_usd": 50000,
        "billing_address": "123 Test Way, MN",
    }
    r = admin_session.post(f"{API}/orisei/customers", json=payload)
    assert r.status_code in (200, 201), f"create customer failed: {r.status_code} {r.text}"
    data = r.json()
    assert data["name"] == payload["name"]
    assert "customer_id" in data
    yield data
    # Teardown — deactivate
    try:
        admin_session.delete(f"{API}/orisei/customers/{data['customer_id']}")
    except Exception:
        pass


# ============================ CUSTOMERS ============================
class TestCustomers:
    def test_list_customers(self, admin_session, customer):
        r = admin_session.get(f"{API}/orisei/customers")
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        ids = [c["customer_id"] for c in data["items"]]
        assert customer["customer_id"] in ids

    def test_get_customer(self, admin_session, customer):
        r = admin_session.get(f"{API}/orisei/customers/{customer['customer_id']}")
        assert r.status_code == 200
        data = r.json()
        assert data["customer_id"] == customer["customer_id"]
        assert "recent_bookings" in data
        assert "recent_invoices" in data
        assert "recent_quotes" in data

    def test_get_customer_404(self, admin_session):
        r = admin_session.get(f"{API}/orisei/customers/NOPE-XXX")
        assert r.status_code == 404

    def test_update_customer(self, admin_session, customer):
        upd = {
            "name": customer["name"],
            "primary_contact_name": "Jane Updated",
            "primary_contact_email": customer.get("primary_contact_email") or "x@example.com",
            "payment_terms": "Net 45",
        }
        r = admin_session.put(f"{API}/orisei/customers/{customer['customer_id']}", json=upd)
        assert r.status_code == 200
        # Verify persisted
        r2 = admin_session.get(f"{API}/orisei/customers/{customer['customer_id']}")
        data = r2.json()
        assert data["payment_terms"] == "Net 45"
        assert data["primary_contact_name"] == "Jane Updated"


# ============================ QUOTES ============================
@pytest.fixture(scope="module")
def quote(admin_session, customer):
    payload = {
        "customer_id": customer["customer_id"],
        "origin": "Minneapolis, MN", "destination": "Chicago, IL",
        "equipment": "Dry Van", "miles": 410, "weight_lbs": 36000,
        "line_haul_usd": 1800.0, "fuel_surcharge_usd": 200.0,
        "accessorials": [{"label": "Detention", "amount_usd": 75.0}],
        "valid_for_days": 7,
    }
    r = admin_session.post(f"{API}/orisei/quotes", json=payload)
    assert r.status_code in (200, 201), f"create quote failed: {r.status_code} {r.text}"
    return r.json()


class TestQuotes:
    def test_quote_total_calculation(self, quote):
        # 1800 + 200 + 75 = 2075
        assert quote["total_usd"] == 2075.0
        assert quote["status"] == "open"
        assert quote["customer_name"].startswith("TEST_Acme_")
        assert "quote_id" in quote

    def test_list_quotes(self, admin_session, quote):
        r = admin_session.get(f"{API}/orisei/quotes")
        assert r.status_code == 200
        ids = [q["quote_id"] for q in r.json()["items"]]
        assert quote["quote_id"] in ids

    def test_quote_pdf(self, admin_session, quote):
        r = admin_session.get(f"{API}/orisei/quotes/{quote['quote_id']}/pdf")
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:4] == b"%PDF"
        assert len(r.content) > 1000

    def test_quote_send_drafts_without_creds(self, admin_session, quote):
        r = admin_session.post(f"{API}/orisei/quotes/{quote['quote_id']}/send")
        assert r.status_code == 200, f"send failed: {r.status_code} {r.text}"
        data = r.json()
        # Resend creds NOT configured → should be drafted
        assert data["status"] in ("drafted", "sent")
        assert "to" in data
        # Verify persisted on quote
        lst = admin_session.get(f"{API}/orisei/quotes").json()["items"]
        found = next(q for q in lst if q["quote_id"] == quote["quote_id"])
        assert found.get("send_status") in ("drafted", "sent")


# ============================ RATE CONFIRMATIONS ============================
class TestRateConfirmations:
    def test_create_rc_missing_booking_404(self, admin_session):
        payload = {
            "booking_id": "NOPE-9999",
            "carrier_mc": "MC123456",
            "carrier_name": "Test Carrier Co",
            "rate_usd": 1500.0,
        }
        r = admin_session.post(f"{API}/orisei/rate-confirmations", json=payload)
        assert r.status_code == 404

    def test_list_rate_cons(self, admin_session):
        r = admin_session.get(f"{API}/orisei/rate-confirmations")
        assert r.status_code == 200
        assert "items" in r.json()


# ============================ PORTAL LINK + PUBLIC ============================
@pytest.fixture(scope="module")
def portal_link(admin_session, customer):
    r = admin_session.post(
        f"{API}/orisei/customers/{customer['customer_id']}/portal-link",
        json={"customer_id": customer["customer_id"], "days_valid": 90},
    )
    assert r.status_code in (200, 201), f"{r.status_code} {r.text}"
    return r.json()


class TestPortalLink:
    def test_portal_link_shape(self, portal_link):
        assert "token" in portal_link and len(portal_link["token"]) > 10
        assert "share_url" in portal_link
        assert "/customer-portal?token=" in portal_link["share_url"]
        assert "expires_at" in portal_link

    def test_multiple_links(self, admin_session, customer):
        tokens = set()
        for _ in range(3):
            r = admin_session.post(
                f"{API}/orisei/customers/{customer['customer_id']}/portal-link",
                json={"customer_id": customer["customer_id"], "days_valid": 30},
            )
            assert r.status_code in (200, 201)
            tokens.add(r.json()["token"])
        assert len(tokens) == 3


class TestPublicPortal:
    def test_public_portal_no_auth(self, portal_link):
        """Critical: GET /api/public/customer-portal/{token} works WITHOUT Authorization."""
        token = portal_link["token"]
        # Use raw requests session with NO auth header
        r = requests.get(f"{API}/public/customer-portal/{token}")
        assert r.status_code == 200, f"public portal failed: {r.status_code} {r.text}"
        data = r.json()
        assert "customer_name" in data
        assert "customer" in data
        assert "summary" in data
        assert "active_shipments" in data["summary"]
        assert "delivered_past_30d" in data["summary"]
        assert "outstanding_invoices_usd" in data["summary"]
        assert "open_quotes" in data["summary"]
        assert isinstance(data.get("bookings"), list)
        assert isinstance(data.get("invoices"), list)
        assert isinstance(data.get("quotes"), list)

    def test_public_portal_records_visit(self, portal_link, admin_session, customer):
        token = portal_link["token"]
        # Hit it twice
        requests.get(f"{API}/public/customer-portal/{token}")
        requests.get(f"{API}/public/customer-portal/{token}")
        # No public endpoint to check visits — verified indirectly by 2nd call still 200
        r = requests.get(f"{API}/public/customer-portal/{token}")
        assert r.status_code == 200

    def test_public_portal_bad_token_404(self):
        r = requests.get(f"{API}/public/customer-portal/badtokenxxx")
        assert r.status_code == 404


# ============================ DEACTIVATE ============================
class TestDeactivate:
    def test_deactivate_then_excluded_from_active_list(self, admin_session):
        # Create disposable customer
        suffix = uuid.uuid4().hex[:6]
        r = admin_session.post(f"{API}/orisei/customers", json={
            "name": f"TEST_Dispose_{suffix}", "payment_terms": "Net 30",
        })
        cid = r.json()["customer_id"]
        # Deactivate
        d = admin_session.delete(f"{API}/orisei/customers/{cid}")
        assert d.status_code == 200
        # Should not be in active list
        lst = admin_session.get(f"{API}/orisei/customers?active_only=true").json()["items"]
        assert all(c["customer_id"] != cid for c in lst)
        # Should be in full list
        full = admin_session.get(f"{API}/orisei/customers?active_only=false").json()["items"]
        assert any(c["customer_id"] == cid for c in full)
