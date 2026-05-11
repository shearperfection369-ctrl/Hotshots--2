"""
Iteration 14 — P2 features for Tennant TMS:
- P2.1: Auto-create carrier_onboarding stub from Truckload Booking Sheet
- P2.2: GET /api/calendar/events (range-validated)
- P2.3: MOCKED email integration: /api/email/send, /api/email/log,
        /api/routing-guide/send-email
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://clean-logistics-dash.preview.emergentagent.com").rstrip("/")

ADMIN_TOKEN = "test_session_admin_1"
DISP_TOKEN = "test_disp_session"


def _h(token=ADMIN_TOKEN):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def admin():
    return _h(ADMIN_TOKEN)


@pytest.fixture(scope="module")
def disp():
    return _h(DISP_TOKEN)


# ===================== P2.1 auto-onboarding =====================
class TestAutoOnboarding:
    """P2.1 — typing a new carrier in the Truckload Booking Sheet creates a
    carrier_onboarding stub with status=in_review and auto_created=True."""

    def test_new_carrier_creates_stub(self, admin):
        unique = f"BrandNewCarrier_{uuid.uuid4().hex[:8]}"
        r = requests.post(
            f"{BASE_URL}/api/workbook/truckload-bookings",
            headers=admin,
            json={"data": {"carrier": unique}},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        ob_id = body.get("auto_onboarding_id")
        assert ob_id and ob_id.startswith("OB-"), f"Expected OB- prefix, got {ob_id!r}"
        # Verify in /carriers/onboarding?status=in_review
        time.sleep(0.5)
        lst = requests.get(
            f"{BASE_URL}/api/carriers/onboarding?status=in_review", headers=admin
        )
        assert lst.status_code == 200
        rows = lst.json() if isinstance(lst.json(), list) else lst.json().get("items", [])
        match = [r for r in rows if r.get("onboarding_id") == ob_id]
        assert match, f"OB id {ob_id} not found in in_review list"
        rec = match[0]
        assert rec.get("auto_created") is True
        assert rec.get("status") == "in_review"
        assert rec.get("legal_name", "").lower() == unique.lower()
        assert rec.get("submitted_by") == "Test Admin"
        # cleanup
        requests.delete(f"{BASE_URL}/api/workbook/truckload-bookings/{body['row']['id']}", headers=admin)

    def test_same_carrier_dedupes(self, admin):
        unique = f"DedupeCarrier_{uuid.uuid4().hex[:8]}"
        # 1st creates
        r1 = requests.post(
            f"{BASE_URL}/api/workbook/truckload-bookings", headers=admin,
            json={"data": {"carrier": unique}},
        )
        assert r1.json().get("auto_onboarding_id", "").startswith("OB-")
        # 2nd → null
        r2 = requests.post(
            f"{BASE_URL}/api/workbook/truckload-bookings", headers=admin,
            json={"data": {"carrier": unique}},
        )
        assert r2.status_code == 200
        assert r2.json().get("auto_onboarding_id") is None
        # case-insensitive
        r3 = requests.post(
            f"{BASE_URL}/api/workbook/truckload-bookings", headers=admin,
            json={"data": {"carrier": unique.upper()}},
        )
        assert r3.json().get("auto_onboarding_id") is None
        # cleanup
        for r in (r1, r2, r3):
            rid = (r.json().get("row") or {}).get("id")
            if rid:
                requests.delete(f"{BASE_URL}/api/workbook/truckload-bookings/{rid}", headers=admin)

    def test_patch_to_new_carrier_creates_stub(self, admin):
        # Create with a known existing carrier first
        r = requests.post(
            f"{BASE_URL}/api/workbook/truckload-bookings", headers=admin,
            json={"data": {"carrier": "XPO"}},
        )
        assert r.status_code == 200
        rid = r.json()["row"]["id"]
        # PATCH to brand new name
        new_name = f"PatchedCarrier_{uuid.uuid4().hex[:8]}"
        r2 = requests.patch(
            f"{BASE_URL}/api/workbook/truckload-bookings/{rid}", headers=admin,
            json={"data": {"carrier": new_name}},
        )
        assert r2.status_code == 200
        ob_id = r2.json().get("auto_onboarding_id")
        assert ob_id and ob_id.startswith("OB-"), f"Expected OB- prefix, got {ob_id!r}"
        # cleanup
        requests.delete(f"{BASE_URL}/api/workbook/truckload-bookings/{rid}", headers=admin)

    def test_existing_xpo_label_no_create(self, admin):
        """'XPO · XPOL' dropdown label should NOT auto-create — existing
        'XPO Logistics LLC' should match via dba='XPO'."""
        for label in ("XPO · XPOL", "xpo", "XPO LOGISTICS LLC"):
            r = requests.post(
                f"{BASE_URL}/api/workbook/truckload-bookings", headers=admin,
                json={"data": {"carrier": label}},
            )
            assert r.status_code == 200, r.text
            assert r.json().get("auto_onboarding_id") is None, (
                f"Label {label!r} should NOT create a new stub"
            )
            rid = r.json()["row"]["id"]
            requests.delete(f"{BASE_URL}/api/workbook/truckload-bookings/{rid}", headers=admin)


# ===================== P2.2 calendar =====================
class TestCalendarEvents:
    """P2.2 — /api/calendar/events range-validated, returns shape with
    events / counts_by_date / start / end."""

    def test_happy_path(self, admin):
        r = requests.get(
            f"{BASE_URL}/api/calendar/events?start=2026-05-01&end=2026-05-31",
            headers=admin,
        )
        assert r.status_code == 200, r.text
        b = r.json()
        assert set(["events", "counts_by_date", "start", "end"]).issubset(b.keys())
        assert b["start"] == "2026-05-01"
        assert b["end"] == "2026-05-31"
        assert isinstance(b["events"], list)
        assert isinstance(b["counts_by_date"], dict)
        # Each event has required keys (when any)
        for e in b["events"]:
            for k in ("date", "kind", "type", "label", "ref", "link"):
                assert k in e, f"Missing {k} in event {e}"
            assert e["kind"] in ("shipment", "booking")
            assert e["type"] in ("pickup", "delivery", "eta", "bol_deadline")

    def test_range_too_large(self, admin):
        r = requests.get(
            f"{BASE_URL}/api/calendar/events?start=2026-01-01&end=2026-06-01",
            headers=admin,
        )
        assert r.status_code == 400

    def test_bad_dates(self, admin):
        r = requests.get(
            f"{BASE_URL}/api/calendar/events?start=not-a-date&end=2026-05-31",
            headers=admin,
        )
        assert r.status_code == 400


class TestCalendarRegression:
    def test_shipments_still_200(self, admin):
        r = requests.get(f"{BASE_URL}/api/shipments", headers=admin)
        assert r.status_code == 200

    def test_truckload_bookings_still_200(self, admin):
        r = requests.get(f"{BASE_URL}/api/workbook/truckload-bookings", headers=admin)
        assert r.status_code == 200


# ===================== P2.3 mocked email =====================
class TestEmailMocked:
    def test_email_send_returns_mock_receipt(self, admin):
        r = requests.post(
            f"{BASE_URL}/api/email/send", headers=admin,
            json={
                "to": "vendor_test@example.com",
                "cc": "",
                "subject": "TEST_ITER14 Subject",
                "body_text": "TEST_ITER14 body",
                "kind": "test",
                "ref": "TEST_REF",
            },
        )
        assert r.status_code == 200, r.text
        b = r.json()
        assert b.get("ok") is True
        assert b.get("status") == "mocked"
        assert b.get("from") == "transportation@tennantco.com"
        mid = b.get("message_id", "")
        assert mid.startswith("mock_"), f"Expected mock_ prefix, got {mid!r}"
        # verify in /email/log
        time.sleep(0.3)
        lr = requests.get(f"{BASE_URL}/api/email/log?limit=50", headers=admin)
        assert lr.status_code == 200
        lb = lr.json()
        assert lb.get("provider") == "mock"
        assert lb.get("from") == "transportation@tennantco.com"
        found = [e for e in lb.get("log", []) if e.get("message_id") == mid]
        assert found, "Sent email not found in /email/log"
        entry = found[0]
        assert entry.get("subject") == "TEST_ITER14 Subject"
        assert entry.get("to") == "vendor_test@example.com"
        assert entry.get("status") == "mocked"

    def test_routing_guide_send_email_auto_builds_subject_body(self, admin):
        r = requests.post(
            f"{BASE_URL}/api/routing-guide/send-email", headers=admin,
            json={"to": "test_vendor@example.com", "cc": "ops@tennantco.com",
                  "subject": "", "body_text": ""},
        )
        assert r.status_code == 200, r.text
        b = r.json()
        assert b.get("ok") is True
        assert b.get("status") == "mocked"
        assert "Tennant Inbound Routing Guide" in (b.get("subject") or "")
        # check log entry has kind=routing_guide
        time.sleep(0.3)
        lr = requests.get(f"{BASE_URL}/api/email/log?kind=routing_guide&limit=10", headers=admin)
        assert lr.status_code == 200
        log = lr.json().get("log", [])
        assert any(e.get("message_id") == b.get("message_id") for e in log)
        rg = next(e for e in log if e.get("message_id") == b.get("message_id"))
        assert rg.get("kind") == "routing_guide"
        assert "Routing Guide" in rg.get("subject", "")
        assert rg.get("to") == "test_vendor@example.com"
        assert rg.get("cc") == "ops@tennantco.com"
        # body auto-built
        assert "Revision" in (rg.get("body_text") or "")

    def test_dispatcher_can_send(self, disp):
        r = requests.post(
            f"{BASE_URL}/api/email/send", headers=disp,
            json={"to": "x@y.com", "subject": "disp test", "body_text": "ok"},
        )
        assert r.status_code == 200, r.text

    def test_no_auth_returns_401_or_403(self):
        r = requests.post(
            f"{BASE_URL}/api/email/send",
            headers={"Content-Type": "application/json"},
            json={"to": "x@y.com", "subject": "s", "body_text": "b"},
        )
        assert r.status_code in (401, 403), f"Expected 401/403, got {r.status_code}"

        r2 = requests.post(
            f"{BASE_URL}/api/routing-guide/send-email",
            headers={"Content-Type": "application/json"},
            json={"to": "x@y.com"},
        )
        assert r2.status_code in (401, 403)
