"""
Iter 22 — Orisei BOL / POD / QuickBooks OAuth regression suite.

Covers the new endpoints introduced in /app/backend/routes/brokerage.py:
  · GET  /api/brokerage/bookings
  · PUT  /api/brokerage/bookings/{id}/customer
  · GET  /api/brokerage/bookings/{id}/bol.pdf
  · GET  /api/brokerage/bookings/{id}/pod.pdf
  · POST /api/brokerage/bookings/{id}/pod/email  (dry_run + missing-creds path)
  · GET  /api/brokerage/bookings/{id}/pod-history
  · GET  /api/brokerage/quickbooks/oauth/start   (missing creds + with creds)

Plus regression on dashboard / boards / book / settle / margins / factoring /
investor-pitch / business-plan / cost-analysis.

Test admin token comes from /app/memory/test_credentials.md.
"""
import os
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else None
if not BASE_URL:
    # /app/frontend/.env is the source-of-truth for the preview URL
    with open("/app/frontend/.env") as fh:
        for line in fh:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().strip('"').rstrip("/")
                break

ADMIN_TOKEN = "test_session_admin_1"
HEADERS = {"Authorization": f"Bearer {ADMIN_TOKEN}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


@pytest.fixture(scope="module")
def booking_id(session):
    """Return an existing booked_id, or book a fresh one off the DAT board."""
    r = session.get(f"{BASE_URL}/api/brokerage/bookings", timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    bookings = data.get("bookings") or []
    if bookings:
        return bookings[0]["booked_id"]

    # No bookings yet — book one off DAT
    loads = session.get(f"{BASE_URL}/api/brokerage/boards/dat/loads", timeout=30).json().get("loads", [])
    assert loads, "Need at least one DAT load to book"
    payload = {
        "load_id": loads[0]["load_id"],
        "board_id": "dat",
        "carrier_name": "TEST_Carrier_Iter22",
        "carrier_mc": "MC-999999",
    }
    bk = session.post(f"{BASE_URL}/api/brokerage/loads/book", json=payload, timeout=30)
    assert bk.status_code == 200, bk.text
    return bk.json()["booked_id"]


# ============================ AUTH SANITY ============================
def test_auth_me_ok(session):
    r = session.get(f"{BASE_URL}/api/auth/me", timeout=15)
    assert r.status_code == 200, r.text
    assert r.json().get("role") == "admin"


# ============================ BOOKINGS LIST ============================
def test_list_bookings_shape(session):
    r = session.get(f"{BASE_URL}/api/brokerage/bookings", timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "bookings" in data
    assert "count" in data
    assert isinstance(data["bookings"], list)
    assert data["count"] == len(data["bookings"])
    if data["bookings"]:
        b = data["bookings"][0]
        for key in ("booked_id", "status", "carrier_name"):
            assert key in b, f"missing {key} on booking"
        # Mongo _id must NOT leak through
        assert "_id" not in b


# ============================ CUSTOMER ATTACH ============================
def test_set_booking_customer_persists(session, booking_id):
    payload = {
        "customer_name": "TEST_Acme Manufacturing",
        "customer_contact": "Ada Lovelace",
        "customer_email": "ops+test@acme-test.example.com",
        "customer_phone": "+1-612-555-0199",
        "consignee_address": "1 Acme Way, Bismarck, ND 58501",
        "shipper_name": "Orisei Freight Solutions LLC",
        "shipper_address": "Minneapolis HQ, 100 Riverside, Minneapolis, MN 55401",
    }
    r = session.put(f"{BASE_URL}/api/brokerage/bookings/{booking_id}/customer", json=payload, timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["customer_name"] == payload["customer_name"]
    assert body["customer_email"] == payload["customer_email"]
    assert body["consignee_address"] == payload["consignee_address"]
    assert "_id" not in body

    # Verify persistence via list (skip stale docs that pre-date the booked_id schema)
    bookings = session.get(f"{BASE_URL}/api/brokerage/bookings", timeout=15).json()["bookings"]
    match = [b for b in bookings if b.get("booked_id") == booking_id]
    assert match and match[0]["customer_name"] == payload["customer_name"]


def test_set_customer_404_for_unknown(session):
    r = session.put(
        f"{BASE_URL}/api/brokerage/bookings/BK-DOES-NOT-EXIST/customer",
        json={"customer_name": "x"},
        timeout=15,
    )
    assert r.status_code == 404


# ============================ BOL PDF ============================
def test_bol_pdf_valid(session, booking_id):
    r = session.get(f"{BASE_URL}/api/brokerage/bookings/{booking_id}/bol.pdf", timeout=30)
    assert r.status_code == 200, r.text[:500]
    assert r.headers.get("content-type", "").startswith("application/pdf")
    body = r.content
    assert body.startswith(b"%PDF"), "BOL response is not a PDF"
    assert 1000 < len(body) < 1_000_000, f"BOL size out of bounds: {len(body)} bytes"
    cd = r.headers.get("content-disposition", "")
    assert "ORI-BOL-" in cd


def test_bol_stamps_bol_no(session, booking_id):
    # After generating BOL, booking should have bol_no
    bookings = session.get(f"{BASE_URL}/api/brokerage/bookings", timeout=15).json()["bookings"]
    match = [b for b in bookings if b.get("booked_id") == booking_id]
    assert match
    assert match[0].get("bol_no", "").startswith("ORI-BOL-")


# ============================ POD PDF ============================
def test_pod_pdf_valid(session, booking_id):
    r = session.get(f"{BASE_URL}/api/brokerage/bookings/{booking_id}/pod.pdf", timeout=30)
    assert r.status_code == 200, r.text[:500]
    assert r.headers.get("content-type", "").startswith("application/pdf")
    body = r.content
    assert body.startswith(b"%PDF")
    assert 1000 < len(body) < 1_000_000


# ============================ POD EMAIL · DRY-RUN ============================
def test_pod_email_dry_run(session, booking_id):
    payload = {
        "to_email": "ops+test@acme-test.example.com",
        "to_name": "Ada Lovelace",
        "subject": "TEST_POD dry-run",
        "message": "Thanks for the freight.",
        "dry_run": True,
        "delivery": {
            "delivered_at": "2026-01-15 14:30 UTC",
            "received_by": "Ada Lovelace",
            "driver_name": "Sam Driver",
            "pieces_received": "22",
            "weight_received": "12,400 lbs",
            "condition": "Apparent good order, seal intact",
        },
    }
    r = session.post(
        f"{BASE_URL}/api/brokerage/bookings/{booking_id}/pod/email",
        json=payload,
        timeout=30,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["status"] == "dry_run"
    assert body["dry_run"] is True
    assert "html_preview" in body and "<html" in body["html_preview"].lower()
    assert isinstance(body["pdf_bytes"], int) and body["pdf_bytes"] > 1000
    assert body["to_email"] == payload["to_email"]
    assert body["subject"] == payload["subject"]
    assert "_id" not in body


def test_pod_email_dry_run_updates_status_and_delivery(session, booking_id):
    # After the dry-run above we wrote delivery + status='delivered'
    bookings = session.get(f"{BASE_URL}/api/brokerage/bookings", timeout=15).json()["bookings"]
    match = [b for b in bookings if b.get("booked_id") == booking_id]
    assert match
    b = match[0]
    assert b.get("status") == "delivered"
    delivery = b.get("delivery") or {}
    assert delivery.get("received_by") == "Ada Lovelace"
    assert delivery.get("driver_name") == "Sam Driver"
    assert delivery.get("pieces_received") == "22"
    assert delivery.get("weight_received") == "12,400 lbs"


def test_pod_history(session, booking_id):
    r = session.get(f"{BASE_URL}/api/brokerage/bookings/{booking_id}/pod-history", timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    assert isinstance(data.get("items"), list)
    assert data["count"] == len(data["items"])
    assert data["count"] >= 1  # we just sent a dry-run
    # Sorted desc by sent_at
    if len(data["items"]) >= 2:
        sent = [i.get("sent_at", "") for i in data["items"]]
        assert sent == sorted(sent, reverse=True)
    # Mongo _id excluded
    for i in data["items"]:
        assert "_id" not in i


# ============================ POD EMAIL · MISSING RESEND CREDS ============================
def _resend_configured(session) -> bool:
    """Return True if Connections vault has a Resend api_key configured."""
    try:
        r = session.get(f"{BASE_URL}/api/connections/resend", timeout=15)
        if r.status_code != 200:
            return False
        v = r.json() or {}
        # Connection vault returns the saved doc — api_key may be masked but boolean fields signal presence
        return bool(v.get("api_key")) or bool(v.get("configured")) or bool(v.get("has_api_key"))
    except Exception:
        return False


def test_pod_email_without_resend_creds_returns_400(session, booking_id):
    if _resend_configured(session):
        pytest.skip("Resend is configured in this env — cannot validate the missing-creds branch")
    payload = {
        "to_email": "ops+test@acme-test.example.com",
        "subject": "TEST_no_creds",
        "dry_run": False,
    }
    r = session.post(
        f"{BASE_URL}/api/brokerage/bookings/{booking_id}/pod/email",
        json=payload,
        timeout=30,
    )
    assert r.status_code == 400, r.text
    msg = (r.json().get("detail") or "").lower()
    assert "resend" in msg


# ============================ QUICKBOOKS OAUTH ============================
@pytest.fixture
def qb_creds_snapshot(session):
    """Snapshot the current QB connection so we can restore after the with-creds test."""
    r = session.get(f"{BASE_URL}/api/connections/quickbooks", timeout=15)
    snapshot = r.json() if r.status_code == 200 else None
    yield snapshot
    # Restore — if there was nothing, attempt to clear
    if snapshot:
        try:
            session.put(f"{BASE_URL}/api/connections/quickbooks", json=snapshot, timeout=15)
        except Exception:
            pass


def _qb_configured(session) -> bool:
    """Return True only if QB has *real* values (the GET endpoint shows set=True even
    for empty values due to a serialization quirk — so cross-check by calling oauth/start)."""
    r = session.get(f"{BASE_URL}/api/brokerage/quickbooks/oauth/start", timeout=10)
    return r.status_code == 200


def test_qb_oauth_start_missing_creds(session):
    if _qb_configured(session):
        pytest.skip("QuickBooks already configured — missing-creds branch not reachable without mutating vault")
    r = session.get(f"{BASE_URL}/api/brokerage/quickbooks/oauth/start", timeout=15)
    assert r.status_code == 400, r.text
    msg = (r.json().get("detail") or "").lower()
    assert "quickbooks" in msg and "client id" in msg


def test_qb_oauth_start_with_creds(session, qb_creds_snapshot):
    # Plant fake creds — Connections API expects { fields: {...}, enabled: bool }
    fake_fields = {
        "client_id": "TEST_qb_client_iter22",
        "client_secret": "TEST_qb_secret_iter22",
        "environment": "sandbox",
        "redirect_uri": f"{BASE_URL}/api/brokerage/quickbooks/oauth/callback",
    }
    put_r = session.put(
        f"{BASE_URL}/api/connections/quickbooks",
        json={"fields": fake_fields, "enabled": True},
        timeout=15,
    )
    assert put_r.status_code in (200, 201), put_r.text

    r = session.get(f"{BASE_URL}/api/brokerage/quickbooks/oauth/start", timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "authorize_url" in body
    assert "appcenter.intuit.com" in body["authorize_url"]
    assert "client_id=TEST_qb_client_iter22" in body["authorize_url"]
    assert "state=" in body["authorize_url"]
    assert body["state"] and isinstance(body["state"], str)
    assert body["environment"] == "sandbox"
    assert body["redirect_uri"] == fake_fields["redirect_uri"]


# ============================ REGRESSION (existing endpoints) ============================
@pytest.mark.parametrize("path", [
    "/api/brokerage/dashboard",
    "/api/brokerage/boards",
    "/api/brokerage/margins",
    "/api/brokerage/factoring/status",
    "/api/brokerage/business-plan",
    "/api/brokerage/cost-analysis",
])
def test_regression_get_endpoints(session, path):
    r = session.get(f"{BASE_URL}{path}", timeout=30)
    assert r.status_code == 200, f"{path} → {r.status_code} {r.text[:300]}"
    assert isinstance(r.json(), dict)


def test_regression_investor_pitch_preview(session):
    # POST with minimal recipient — dry-run is implicit for preview route
    r = session.post(
        f"{BASE_URL}/api/brokerage/investor-pitch/preview",
        json={"to_email": "investor+test@example.com"},
        timeout=30,
    )
    assert r.status_code == 200, r.text[:300]
    # Could be JSON or PDF — accept either
    ct = r.headers.get("content-type", "")
    assert ct.startswith("application/json") or ct.startswith("application/pdf") or ct.startswith("text/")


def test_regression_book_and_settle(session):
    # Book a fresh load
    loads = session.get(f"{BASE_URL}/api/brokerage/boards/dat/loads", timeout=30).json().get("loads", [])
    if not loads:
        pytest.skip("No DAT loads available for book/settle regression")
    load = loads[-1]
    bk = session.post(
        f"{BASE_URL}/api/brokerage/loads/book",
        json={"load_id": load["load_id"], "board_id": "dat",
              "carrier_name": "TEST_RegressionCarrier", "carrier_mc": "MC-111222"},
        timeout=30,
    )
    assert bk.status_code == 200, bk.text
    booked_id = bk.json()["booked_id"]

    # Settle it (requires both settled_rate_usd and settled_carrier_pay_usd per SettleLoadIn)
    rate = float(load.get("rate_usd") or 1500)
    pay = max(0.0, rate * 0.85)
    st = session.post(
        f"{BASE_URL}/api/brokerage/loads/settle",
        json={"booked_id": booked_id, "settled_rate_usd": rate,
              "settled_carrier_pay_usd": pay},
        timeout=30,
    )
    assert st.status_code == 200, st.text
    assert st.json().get("status") in {"settled", "delivered"}
