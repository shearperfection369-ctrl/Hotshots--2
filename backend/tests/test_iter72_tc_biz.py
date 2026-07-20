"""Backend tests for Orisei Truck Cleaning module - vault, onboarding, invoicing, public pay."""
import io
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://clean-logistics-dash.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api/truck-cleaning"
HEADERS = {"Authorization": "Bearer test_session_admin_1"}


@pytest.fixture(scope="module")
def state():
    return {}


# ---------- VAULT ----------
class TestVault:
    def test_categories(self, state):
        r = requests.get(f"{API}/vault/categories", headers=HEADERS, timeout=20)
        assert r.status_code == 200
        cats = r.json().get("categories", [])
        assert "Insurance / COI" in cats
        assert "Other" in cats
        assert len(cats) >= 5

    def test_upload_file(self, state):
        files = {"file": ("test_iter72.txt", b"hello TEST_iter72 vault content", "text/plain")}
        data = {"category": "Other", "client_id": "", "notes": "TEST_iter72 upload"}
        r = requests.post(f"{API}/vault/upload", headers=HEADERS, files=files, data=data, timeout=30)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j.get("ok") is True
        assert j.get("file_id")
        state["file_id"] = j["file_id"]

    def test_list_files(self, state):
        r = requests.get(f"{API}/vault/files", headers=HEADERS, timeout=20)
        assert r.status_code == 200
        files = r.json().get("files", [])
        assert any(f.get("file_id") == state.get("file_id") for f in files)

    def test_list_files_category_filter(self, state):
        r = requests.get(f"{API}/vault/files?category=Other", headers=HEADERS, timeout=20)
        assert r.status_code == 200
        for f in r.json().get("files", []):
            assert f.get("category") == "Other"

    def test_download_file(self, state):
        r = requests.get(f"{API}/vault/files/{state['file_id']}/download", headers=HEADERS, timeout=20)
        assert r.status_code == 200
        assert b"TEST_iter72" in r.content

    def test_delete_file(self, state):
        r = requests.delete(f"{API}/vault/files/{state['file_id']}", headers=HEADERS, timeout=20)
        assert r.status_code == 200
        # Verify gone
        r2 = requests.get(f"{API}/vault/files/{state['file_id']}/download", headers=HEADERS, timeout=20)
        assert r2.status_code == 404


# ---------- ONBOARDING ----------
class TestOnboarding:
    def test_create_invite(self, state):
        payload = {"company": "TEST_iter72 Fleet", "contact": "Test Contact", "email": "test72@example.com"}
        r = requests.post(f"{API}/onboarding", headers=HEADERS, json=payload, timeout=20)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["ok"] is True
        ob = j["onboarding"]
        assert ob["status"] == "invited"
        assert ob["onboard_id"].startswith("OB-TC-")
        assert j["link_path"].startswith("/tc/onboard/")
        state["onboard_id"] = ob["onboard_id"]
        state["token"] = ob["token"]

    def test_list_onboarding(self, state):
        r = requests.get(f"{API}/onboarding", headers=HEADERS, timeout=20)
        assert r.status_code == 200
        rows = r.json().get("onboardings", [])
        assert any(o["onboard_id"] == state["onboard_id"] for o in rows)

    def test_public_get_prefill(self, state):
        r = requests.get(f"{API}/onboard/{state['token']}", timeout=20)
        assert r.status_code == 200
        j = r.json()
        assert j["onboard_id"] == state["onboard_id"]
        assert j["status"] == "invited"
        assert j["prefill"]["company"] == "TEST_iter72 Fleet"

    def test_public_get_bad_token(self):
        r = requests.get(f"{API}/onboard/nonexistent_token_xyz", timeout=20)
        assert r.status_code == 404

    def test_submit_without_agreement_fails(self, state):
        payload = {"company": "TEST_iter72 Fleet", "contact": "Test Contact", "email": "test72@example.com",
                   "phone": "612-555-0000", "cabs": 3, "plan": "biweekly_sub",
                   "fleet_notes": "note", "yard_address": "1 Yard", "agreement_accepted": False}
        r = requests.post(f"{API}/onboard/{state['token']}/submit", json=payload, timeout=20)
        assert r.status_code == 400
        assert "agreement" in r.text.lower()

    def test_submit_invalid_plan_fails(self, state):
        payload = {"company": "TEST_iter72 Fleet", "contact": "Test Contact", "email": "test72@example.com",
                   "phone": "612-555-0000", "cabs": 3, "plan": "not_a_plan",
                   "fleet_notes": "note", "yard_address": "1 Yard", "agreement_accepted": True}
        r = requests.post(f"{API}/onboard/{state['token']}/submit", json=payload, timeout=20)
        assert r.status_code == 400

    def test_submit_success(self, state):
        payload = {"company": "TEST_iter72 Fleet", "contact": "Test Contact", "email": "test72@example.com",
                   "phone": "612-555-0000", "cabs": 3, "plan": "biweekly_sub",
                   "fleet_notes": "quarterly deep clean", "yard_address": "1 Yard Ln",
                   "agreement_accepted": True}
        r = requests.post(f"{API}/onboard/{state['token']}/submit", json=payload, timeout=20)
        assert r.status_code == 200, r.text
        # Verify status changed
        r2 = requests.get(f"{API}/onboard/{state['token']}", timeout=20)
        assert r2.json()["status"] == "submitted"

    def test_welcome_packet_pdf(self, state):
        r = requests.get(f"{API}/onboarding/{state['onboard_id']}/welcome-packet.pdf", headers=HEADERS, timeout=30)
        assert r.status_code == 200
        assert r.content[:4] == b"%PDF"

    def test_reject_from_submitted_ok(self, state):
        # Create a second onboarding to test reject
        payload = {"company": "TEST_iter72 Reject", "contact": "Xy", "email": "reject72@example.com"}
        r = requests.post(f"{API}/onboarding", headers=HEADERS, json=payload, timeout=20)
        tok = r.json()["onboarding"]["token"]
        ob_id = r.json()["onboarding"]["onboard_id"]
        sub = {"company": "TEST_iter72 Reject", "contact": "Xy", "email": "reject72@example.com",
               "phone": "", "cabs": 1, "plan": "one_time", "fleet_notes": "", "yard_address": "",
               "agreement_accepted": True}
        r2 = requests.post(f"{API}/onboard/{tok}/submit", json=sub, timeout=20)
        assert r2.status_code == 200
        r3 = requests.post(f"{API}/onboarding/{ob_id}/reject", headers=HEADERS, timeout=20)
        assert r3.status_code == 200
        # Reject a second time should 404 (no longer submitted)
        r4 = requests.post(f"{API}/onboarding/{ob_id}/reject", headers=HEADERS, timeout=20)
        assert r4.status_code == 404

    def test_approve_creates_client_with_correct_rate(self, state):
        r = requests.post(f"{API}/onboarding/{state['onboard_id']}/approve", headers=HEADERS, timeout=20)
        assert r.status_code == 200, r.text
        client = r.json()["client"]
        assert client["plan"] == "biweekly_sub"
        assert client["rate"] == 120.0
        assert client["company"] == "TEST_iter72 Fleet"
        state["client_id"] = client["client_id"]

    def test_approve_from_wrong_status_fails(self, state):
        # Try to approve again
        r = requests.post(f"{API}/onboarding/{state['onboard_id']}/approve", headers=HEADERS, timeout=20)
        assert r.status_code == 400


# ---------- INVOICING ----------
class TestInvoicing:
    def test_create_invoice_needs_items(self, state):
        r = requests.post(f"{API}/invoices", headers=HEADERS,
                          json={"client_id": state["client_id"], "job_ids": [], "custom_items": []},
                          timeout=20)
        assert r.status_code == 400

    def test_create_invoice_with_custom_items(self, state):
        payload = {"client_id": state["client_id"], "job_ids": [],
                   "custom_items": [{"desc": "TEST_iter72 detail", "amount": 250.0},
                                    {"desc": "TEST_iter72 upsell", "amount": 45.5}],
                   "due_days": 15, "notes": "TEST invoice iter72"}
        r = requests.post(f"{API}/invoices", headers=HEADERS, json=payload, timeout=20)
        assert r.status_code == 200, r.text
        inv = r.json()["invoice"]
        assert inv["total"] == 295.5
        assert len(inv["line_items"]) == 2
        assert inv["status"] == "draft"
        state["invoice_id"] = inv["invoice_id"]

    def test_list_invoices(self, state):
        r = requests.get(f"{API}/invoices", headers=HEADERS, timeout=20)
        assert r.status_code == 200
        invs = r.json().get("invoices", [])
        assert any(i["invoice_id"] == state["invoice_id"] for i in invs)

    def test_invoice_pdf(self, state):
        r = requests.get(f"{API}/invoices/{state['invoice_id']}/pdf", headers=HEADERS, timeout=30)
        assert r.status_code == 200
        assert r.content[:4] == b"%PDF"

    def test_invoice_email_resend_not_configured(self, state):
        # Resend intentionally not configured; expect 400 with helpful message
        r = requests.post(f"{API}/invoices/{state['invoice_id']}/email", headers=HEADERS,
                          json={"to_email": "test72@example.com", "message": "hi"}, timeout=20)
        assert r.status_code == 400
        assert "resend" in r.text.lower() or "connections" in r.text.lower()

    def test_public_pay_info(self, state):
        r = requests.get(f"{API}/pay/{state['invoice_id']}", timeout=20)
        assert r.status_code == 200
        j = r.json()
        assert j["invoice_id"] == state["invoice_id"]
        assert j["total"] == 295.5
        assert j["status"] == "draft"
        # ensure sensitive fields not leaked
        assert "stripe_session_id" not in j

    def test_public_pay_pdf(self, state):
        r = requests.get(f"{API}/pay/{state['invoice_id']}/pdf", timeout=30)
        assert r.status_code == 200
        assert r.content[:4] == b"%PDF"

    def test_public_checkout_returns_stripe_url(self, state):
        r = requests.post(f"{API}/pay/{state['invoice_id']}/checkout",
                          json={"origin_url": BASE_URL}, timeout=30)
        assert r.status_code == 200, r.text
        j = r.json()
        assert "checkout_url" in j
        assert j["checkout_url"].startswith("https://checkout.stripe.com") or "stripe.com" in j["checkout_url"]
        assert j["session_id"].startswith("cs_test_")

    def test_public_pay_status(self, state):
        r = requests.get(f"{API}/pay/{state['invoice_id']}/status", timeout=20)
        assert r.status_code == 200
        assert r.json()["status"] in ("draft", "sent", "overdue")

    def test_mark_paid_and_status_updates(self, state):
        r = requests.post(f"{API}/invoices/{state['invoice_id']}/mark-paid", headers=HEADERS, timeout=20)
        assert r.status_code == 200
        # verify status
        r2 = requests.get(f"{API}/pay/{state['invoice_id']}", timeout=20)
        assert r2.json()["status"] == "paid"

    def test_checkout_after_paid_returns_400(self, state):
        r = requests.post(f"{API}/pay/{state['invoice_id']}/checkout",
                          json={"origin_url": BASE_URL}, timeout=20)
        assert r.status_code == 400


# ---------- REGRESSION: existing tabs ----------
class TestRegression:
    def test_clients_list(self):
        r = requests.get(f"{BASE_URL}/api/truck-cleaning/clients", headers=HEADERS, timeout=20)
        assert r.status_code == 200

    def test_jobs_list(self):
        r = requests.get(f"{BASE_URL}/api/truck-cleaning/jobs", headers=HEADERS, timeout=20)
        assert r.status_code == 200

    def test_metrics(self):
        r = requests.get(f"{BASE_URL}/api/truck-cleaning/metrics", headers=HEADERS, timeout=20)
        assert r.status_code == 200
