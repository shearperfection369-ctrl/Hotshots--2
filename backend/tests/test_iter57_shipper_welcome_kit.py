"""
Iter 57 — Shipper Relations Orisei Welcome Kit (PDF + mocked Resend send)

Tests:
  1) GET /api/shipper-relations/accounts/{id}/welcome.pdf — PDF, Orisei-branded, no Walmart/Bentonville.
  2) POST /api/shipper-relations/accounts/{id}/send-welcome — mock delivery, activity auto-log, kit history.
  3) Greeting personalization (first name parsed, company mentioned, Orisei mentioned, no HTML entities).
  4) Send-welcome without contact_email → 422.
  5) welcome-history sorted desc.
  6) ROI snapshot appears when annual_volume_loads>0.
  7) Regression smoke on dashboard/accounts/create/log-activity endpoints.
"""
import io
import os
import re
import uuid
import time

import pytest
import requests
from pypdf import PdfReader

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL", "https://clean-logistics-dash.preview.emergentagent.com"
).rstrip("/")
TOKEN = "test_session_admin_1"
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}


def _pdf_text(content: bytes) -> str:
    reader = PdfReader(io.BytesIO(content))
    return "\n".join(p.extract_text() or "" for p in reader.pages)


# ============================================================
# Fixtures — create two fresh accounts (with + without contact_email)
# ============================================================
@pytest.fixture(scope="module")
def account_with_email():
    unique = uuid.uuid4().hex[:8]
    payload = {
        "company_name": f"TEST_Acme Widgets {unique}",
        "industry": "manufacturing",
        "hq_city": "Denver",
        "hq_state": "CO",
        "contact_name": "Alex Buyer",
        "contact_email": f"alex.buyer.{unique}@example.com",
        "contact_phone": "303-555-0101",
        "annual_volume_loads": 120,
        "annual_revenue_usd": 500000,
        "primary_lanes": ["DEN-DFW", "DEN-LAX"],
        "equipment_needs": ["dry_van", "reefer"],
        "lifecycle": "qualified",
        "payment_terms": "net_30",
        "dedicated_am": "Jordan Ops",
        "notes": "created by iter57 test",
    }
    r = requests.post(f"{BASE_URL}/api/shipper-relations/accounts",
                      headers=HEADERS, json=payload, timeout=15)
    assert r.status_code in (200, 201), f"create with-email failed {r.status_code}: {r.text[:400]}"
    data = r.json()
    account_id = data.get("account_id") or data.get("id") or (data.get("account") or {}).get("account_id")
    assert account_id, f"no account_id in create response: {list(data.keys())}"
    yield {"account_id": account_id, "contact_email": payload["contact_email"],
           "company_name": payload["company_name"], "contact_name": payload["contact_name"]}
    # No teardown — we soft-delete via DELETE if desired but leaving TEST_ prefix for cleanup.


@pytest.fixture(scope="module")
def account_without_email():
    unique = uuid.uuid4().hex[:8]
    payload = {
        "company_name": f"TEST_NoEmail Co {unique}",
        "industry": "retail",
        "hq_city": "Atlanta",
        "hq_state": "GA",
        "contact_name": "Sam NoMail",
        "annual_volume_loads": 0,
        "lifecycle": "lead",
        "payment_terms": "net_45",
    }
    r = requests.post(f"{BASE_URL}/api/shipper-relations/accounts",
                      headers=HEADERS, json=payload, timeout=15)
    assert r.status_code in (200, 201), f"create no-email failed {r.status_code}: {r.text[:400]}"
    data = r.json()
    account_id = data.get("account_id") or data.get("id") or (data.get("account") or {}).get("account_id")
    assert account_id
    yield {"account_id": account_id, "company_name": payload["company_name"]}


# ============================================================
# 1) Welcome PDF endpoint
# ============================================================
class TestWelcomePdf:
    def test_pdf_is_orisei_branded(self, account_with_email):
        aid = account_with_email["account_id"]
        r = requests.get(f"{BASE_URL}/api/shipper-relations/accounts/{aid}/welcome.pdf",
                         headers=HEADERS, timeout=30)
        assert r.status_code == 200, f"welcome.pdf {aid} → {r.status_code}: {r.text[:300]}"
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:4] == b"%PDF"
        assert len(r.content) >= 40_000, f"PDF too small: {len(r.content)} bytes"

        text = _pdf_text(r.content)
        lower = text.lower()
        assert "orisei" in lower, f"'orisei' missing. Extract: {text[:400]}"
        assert "walmart" not in lower, f"'walmart' leaked. Extract: {text[:400]}"
        assert "bentonville" not in lower, f"'bentonville' leaked. Extract: {text[:400]}"
        # company_name present (may be broken across lines — check for the unique prefix)
        assert "TEST_Acme Widgets" in text or "TEST_Acme" in text, (
            f"company_name missing from PDF. Extract: {text[:800]}"
        )
        # Greeting section (auto-generated) — "welcome" OR "partnership" appear in the greeting body
        assert ("welcome" in lower) or ("partnership" in lower), (
            f"greeting keywords missing. Extract: {text[:800]}"
        )


# ============================================================
# 2) Send-welcome (mock email) endpoint
# ============================================================
class TestSendWelcome:
    def test_send_welcome_success(self, account_with_email):
        aid = account_with_email["account_id"]
        payload = {"sender_name": "Alex · Orisei Dispatch"}
        r = requests.post(f"{BASE_URL}/api/shipper-relations/accounts/{aid}/send-welcome",
                          headers=HEADERS, json=payload, timeout=30)
        assert r.status_code == 200, f"send-welcome failed {r.status_code}: {r.text[:400]}"
        data = r.json()

        assert data.get("ok") is True
        delivery = data.get("delivery")
        assert delivery, "delivery missing"
        assert delivery["provider"] == "resend-mock"
        assert delivery["id"].startswith("em-mock-"), f"id: {delivery['id']}"
        assert delivery["to"] == account_with_email["contact_email"]
        assert "Welcome to" in delivery["subject"], f"subject: {delivery['subject']}"
        assert delivery["status"] == "queued"

        att = delivery.get("attachment")
        assert att, "attachment missing"
        assert att["filename"].endswith(".pdf")
        assert att["size_bytes"] > 10_000, f"attachment size: {att['size_bytes']}"
        assert "content_b64_preview" in att

        assert isinstance(data.get("greeting_preview"), str) and len(data["greeting_preview"]) > 10

        activity = data.get("activity")
        assert activity, "activity missing"
        assert activity["kind"] == "email"
        assert "Welcome kit sent" in activity["summary"], activity["summary"]
        # _id must not leak
        assert "_id" not in activity

        assert data.get("pdf_bytes", 0) > 10_000

    def test_greeting_is_personalized(self, account_with_email):
        aid = account_with_email["account_id"]
        r = requests.post(f"{BASE_URL}/api/shipper-relations/accounts/{aid}/send-welcome",
                          headers=HEADERS, json={"sender_name": "Alex · Orisei Dispatch"}, timeout=30)
        assert r.status_code == 200
        # greeting_preview truncates at 220 chars — the full greeting lives in activity.email_greeting
        activity = r.json()["activity"]
        greeting = activity.get("email_greeting", "")
        assert greeting, "email_greeting missing on activity"

        # First name parsed from "Alex Buyer" → "Alex"
        assert re.search(r"\bHi\s+Alex\b", greeting), f"first-name not personalized: {greeting[:200]}"
        # Company mentioned
        assert account_with_email["company_name"].split(" ")[0] in greeting or "Acme" in greeting, greeting[:400]
        # Orisei brand mentioned
        assert "orisei" in greeting.lower(), greeting[:400]
        # No HTML entities leaked (real Unicode apostrophes)
        assert "&#39;" not in greeting, f"HTML entity leaked: {greeting[:400]}"
        assert "&amp;" not in greeting
        assert "&quot;" not in greeting

    def test_send_welcome_without_email_returns_422(self, account_without_email):
        aid = account_without_email["account_id"]
        r = requests.post(f"{BASE_URL}/api/shipper-relations/accounts/{aid}/send-welcome",
                          headers=HEADERS, json={"sender_name": "Alex"}, timeout=15)
        assert r.status_code == 422, f"expected 422, got {r.status_code}: {r.text[:300]}"
        detail = r.json().get("detail", "")
        assert "contact_email" in str(detail).lower() or "email" in str(detail).lower(), detail


# ============================================================
# 3) Activity auto-log visible on account 360° view
# ============================================================
class TestActivityAutoLog:
    def test_activity_shows_on_account_detail(self, account_with_email):
        aid = account_with_email["account_id"]
        # ensure at least one send happened
        s = requests.post(f"{BASE_URL}/api/shipper-relations/accounts/{aid}/send-welcome",
                          headers=HEADERS, json={"sender_name": "Alex · Orisei Dispatch"}, timeout=30)
        assert s.status_code == 200

        r = requests.get(f"{BASE_URL}/api/shipper-relations/accounts/{aid}",
                         headers=HEADERS, timeout=15)
        assert r.status_code == 200, f"get account failed: {r.text[:300]}"
        data = r.json()
        activities = data.get("activities") or data.get("activity") or []
        assert activities, f"no activities on account. keys={list(data.keys())}"
        found = any(
            a.get("kind") == "email" and "Welcome kit sent" in a.get("summary", "")
            for a in activities
        )
        assert found, f"welcome-kit activity not found. activities: {activities[:3]}"


# ============================================================
# 4) Welcome-history endpoint (most recent first)
# ============================================================
class TestWelcomeHistory:
    def test_history_sorted_desc(self, account_with_email):
        aid = account_with_email["account_id"]
        # ensure at least 2 sends
        for _ in range(2):
            r = requests.post(f"{BASE_URL}/api/shipper-relations/accounts/{aid}/send-welcome",
                              headers=HEADERS, json={"sender_name": "Alex · Orisei Dispatch"}, timeout=30)
            assert r.status_code == 200
            time.sleep(0.5)

        h = requests.get(f"{BASE_URL}/api/shipper-relations/accounts/{aid}/welcome-history",
                         headers=HEADERS, timeout=15)
        assert h.status_code == 200
        payload = h.json()
        items = payload.get("items", [])
        assert len(items) >= 2, f"expected ≥2 kits, got {len(items)}"

        top = items[0]
        assert top["kit_id"].startswith("WK-"), top["kit_id"]
        for field in ("sent_at", "subject", "to_email", "greeting", "pdf_bytes"):
            assert field in top, f"missing field {field} in kit: {list(top.keys())}"

        # ordering — sent_at desc
        sent_ats = [i["sent_at"] for i in items]
        assert sent_ats == sorted(sent_ats, reverse=True), f"not sorted desc: {sent_ats}"


# ============================================================
# 5) ROI snapshot present when annual_volume_loads > 0
# ============================================================
class TestRoiSnapshot:
    def test_roi_section_appears_after_patch(self, account_with_email):
        aid = account_with_email["account_id"]
        # patch account to set annual_volume_loads=250
        p = requests.patch(f"{BASE_URL}/api/shipper-relations/accounts/{aid}",
                           headers=HEADERS,
                           json={"annual_volume_loads": 250}, timeout=15)
        assert p.status_code == 200, f"patch failed: {p.text[:200]}"

        r = requests.get(f"{BASE_URL}/api/shipper-relations/accounts/{aid}/welcome.pdf",
                         headers=HEADERS, timeout=30)
        assert r.status_code == 200
        text = _pdf_text(r.content).lower()
        assert "roi" in text, f"ROI section missing from PDF. Extract: {text[:600]}"


# ============================================================
# 6) Regression smoke — existing shipper-relations endpoints
# ============================================================
class TestRegression:
    def test_dashboard(self):
        r = requests.get(f"{BASE_URL}/api/shipper-relations/dashboard",
                         headers=HEADERS, timeout=15)
        assert r.status_code == 200, r.text[:200]
        assert "totals" in r.json()

    def test_list_accounts(self):
        r = requests.get(f"{BASE_URL}/api/shipper-relations/accounts",
                         headers=HEADERS, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list) or isinstance(data.get("accounts"), list) or isinstance(data.get("items"), list)

    def test_create_account_smoke(self):
        unique = uuid.uuid4().hex[:8]
        payload = {
            "company_name": f"TEST_Smoke {unique}",
            "lifecycle": "lead",
            "payment_terms": "net_30",
        }
        r = requests.post(f"{BASE_URL}/api/shipper-relations/accounts",
                          headers=HEADERS, json=payload, timeout=15)
        assert r.status_code in (200, 201), r.text[:200]

    def test_log_activity(self, account_with_email):
        aid = account_with_email["account_id"]
        r = requests.post(f"{BASE_URL}/api/shipper-relations/accounts/{aid}/activity",
                          headers=HEADERS,
                          json={"kind": "note", "summary": "TEST_iter57 manual activity"},
                          timeout=15)
        assert r.status_code in (200, 201), r.text[:200]
