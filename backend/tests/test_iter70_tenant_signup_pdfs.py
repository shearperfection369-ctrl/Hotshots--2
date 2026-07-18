"""iter70 — Hot Shot TMS: self-serve signup, welcome email, tenant load docs (PDFs).

Focuses on the 3 new features added in this iteration:
  1. Self-serve signup (public /api/hotshot/signup) — honeypot, rate limit, dup name, auto-login token.
  2. Welcome email — queued to db.tenant_emails when Resend key missing; returned in provision response.
  3. Tenant load documents — /ratecon.pdf and /invoices/{id}/pdf with tenant auth + cross-tenant 403.

Plus quick regressions: tenant login, dashboard KPIs, load+invoice create, stripe checkout URL.

NOTE: Rate-limit test is LAST because the counter is per-IP for 1h. All test tenants (except acme)
are deleted at teardown via DELETE /api/hotshot/tenants/{slug}.
"""
import os
import uuid
import time
from typing import Dict, Any, List

import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
ADMIN_HDR = {"Authorization": "Bearer test_session_admin_1"}

TENANT_A_SLUG = "acme-freight-co"
TENANT_A_EMAIL = "admin@acmefreight.com"
TENANT_A_PW = "AcmeDemo123!"

_created_slugs: List[str] = []


def _cleanup_slug(slug: str):
    try:
        requests.delete(f"{BASE_URL}/api/hotshot/tenants/{slug}", headers=ADMIN_HDR, timeout=30)
    except Exception:
        pass


@pytest.fixture(scope="module", autouse=True)
def _cleanup():
    yield
    for s in _created_slugs:
        _cleanup_slug(s)


@pytest.fixture(scope="module")
def tenantA_token() -> str:
    r = requests.post(
        f"{BASE_URL}/api/t/{TENANT_A_SLUG}/auth/login",
        json={"email": TENANT_A_EMAIL, "password": TENANT_A_PW}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def tenantA_load(tenantA_token) -> Dict[str, Any]:
    h = {"Authorization": f"Bearer {tenantA_token}"}
    payload = {"origin": "TEST_ITER70_Dallas", "destination": "TEST_ITER70_Houston",
               "customer": "TEST_ITER70_Customer", "customer_rate": 1800, "carrier_rate": 1400,
               "equipment": "Reefer"}
    r = requests.post(f"{BASE_URL}/api/t/{TENANT_A_SLUG}/loads", headers=h, json=payload, timeout=30)
    assert r.status_code == 200, r.text
    load = r.json()["load"]
    yield load
    requests.delete(f"{BASE_URL}/api/t/{TENANT_A_SLUG}/loads/{load['load_id']}", headers=h, timeout=15)


@pytest.fixture(scope="module")
def tenantA_invoice(tenantA_token, tenantA_load) -> Dict[str, Any]:
    h = {"Authorization": f"Bearer {tenantA_token}"}
    r = requests.post(f"{BASE_URL}/api/t/{TENANT_A_SLUG}/loads/{tenantA_load['load_id']}/invoice",
                      headers=h, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["invoice"]


# ============================================================================
# 1. SELF-SERVE SIGNUP (public /api/hotshot/signup) — honeypot, dup, validation
# ============================================================================
class TestSelfServeSignup:
    def test_signup_success_returns_slug_and_token(self):
        marker = uuid.uuid4().hex[:6]
        payload = {
            "company_name": f"TEST_SS_{marker}",
            "name": "SS Test",
            "email": f"ss{marker}@testss.com",
            "password": "SelfServe123!",
            "origin_url": BASE_URL,
        }
        r = requests.post(f"{BASE_URL}/api/hotshot/signup", json=payload, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["ok"] is True
        assert "slug" in data and data["slug"]
        assert "token" in data and isinstance(data["token"], str) and len(data["token"]) > 20
        assert data["login_path"] == f"/t/{data['slug']}/login"
        _created_slugs.append(data["slug"])

        # verify tenant exists with source=self_serve
        rl = requests.get(f"{BASE_URL}/api/hotshot/tenants", headers=ADMIN_HDR, timeout=30)
        tenants = rl.json()["tenants"]
        me = next((t for t in tenants if t["slug"] == data["slug"]), None)
        assert me is not None
        assert me.get("source") == "self_serve"

        # token should log us in — verify via /auth/me
        rm = requests.get(f"{BASE_URL}/api/t/{data['slug']}/auth/me",
                          headers={"Authorization": f"Bearer {data['token']}"}, timeout=15)
        assert rm.status_code == 200
        assert rm.json()["email"] == payload["email"].lower()
        assert rm.json()["role"] == "admin"

    def test_signup_honeypot_returns_ok_but_no_tenant(self):
        marker = uuid.uuid4().hex[:6]
        payload = {
            "company_name": f"TEST_HONEY_{marker}",
            "name": "Bot", "email": f"bot{marker}@spam.com",
            "password": "BotPassword1!", "website": "http://evil.example.com"  # honeypot filled
        }
        r = requests.post(f"{BASE_URL}/api/hotshot/signup", json=payload, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        # should NOT create a tenant with this name
        rl = requests.get(f"{BASE_URL}/api/hotshot/tenants", headers=ADMIN_HDR, timeout=30)
        tenants = rl.json()["tenants"]
        assert not any(payload["company_name"].lower() in (t.get("company_name") or "").lower()
                       for t in tenants), "honeypot signup should have been silently dropped"

    def test_signup_duplicate_slug_returns_400(self):
        marker = uuid.uuid4().hex[:6]
        payload = {
            "company_name": f"TEST_DUP_{marker}",
            "name": "First", "email": f"dup1{marker}@x.com",
            "password": "Password12!", "origin_url": BASE_URL,
        }
        r1 = requests.post(f"{BASE_URL}/api/hotshot/signup", json=payload, timeout=30)
        assert r1.status_code == 200
        slug = r1.json()["slug"]
        _created_slugs.append(slug)
        # second signup with same company_name -> same slugified name -> 400
        payload2 = {**payload, "email": f"dup2{marker}@x.com"}
        r2 = requests.post(f"{BASE_URL}/api/hotshot/signup", json=payload2, timeout=30)
        assert r2.status_code == 400
        assert "taken" in r2.text.lower() or "already" in r2.text.lower()

    def test_signup_short_password_rejected(self):
        payload = {
            "company_name": "TEST_ShortPW", "name": "x", "email": "shortpw@x.com",
            "password": "abc12"  # <8
        }
        r = requests.post(f"{BASE_URL}/api/hotshot/signup", json=payload, timeout=15)
        # pydantic min_length=8 -> 422
        assert r.status_code == 422, r.text

    def test_signup_invalid_email_rejected(self):
        marker = uuid.uuid4().hex[:6]
        payload = {
            "company_name": f"TEST_BadEmail_{marker}", "name": "x",
            "email": "not-an-email", "password": "GoodPass123!",
        }
        r = requests.post(f"{BASE_URL}/api/hotshot/signup", json=payload, timeout=15)
        # Accepts 400 (custom EMAIL_RE) or 422 (pydantic) — both are valid rejections
        assert r.status_code in (400, 422), r.text


# ============================================================================
# 2. WELCOME EMAIL — queued when Resend key missing
# ============================================================================
class TestWelcomeEmail:
    def test_admin_provision_returns_welcome_email_queued(self):
        marker = uuid.uuid4().hex[:6]
        payload = {
            "company_name": f"TEST_WEL_{marker}",
            "slug": f"test-wel-{marker}",
            "plan": "growth",
            "admin_email": f"wel{marker}@testwel.com",
            "admin_password": "WelcomePW1!",
            "admin_name": "Wel Admin",
            "origin_url": BASE_URL,
        }
        r = requests.post(f"{BASE_URL}/api/hotshot/tenants", headers=ADMIN_HDR, json=payload, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        _created_slugs.append(d["tenant"]["slug"])
        # welcome_email should be a dict with status queued_no_resend (Resend key intentionally missing)
        we = d.get("welcome_email")
        assert we is not None, "welcome_email missing from response"
        assert we.get("status") == "queued_no_resend", f"expected queued_no_resend, got {we.get('status')}"
        assert "login_url" in we
        assert f"/t/{d['tenant']['slug']}/login" in we["login_url"]

    def test_signup_activity_contains_welcome_queued(self):
        """After a self-serve signup, activity feed should include a welcome-QUEUED entry."""
        marker = uuid.uuid4().hex[:6]
        payload = {
            "company_name": f"TEST_WACT_{marker}",
            "name": "WAct", "email": f"wact{marker}@testwact.com",
            "password": "WActPass123!", "origin_url": BASE_URL,
        }
        r = requests.post(f"{BASE_URL}/api/hotshot/signup", json=payload, timeout=30)
        assert r.status_code == 200
        slug = r.json()["slug"]
        _created_slugs.append(slug)

        ra = requests.get(f"{BASE_URL}/api/hotshot/activity", headers=ADMIN_HDR, timeout=15)
        assert ra.status_code == 200
        acts = ra.json()["activity"]
        my_acts = [a for a in acts if a.get("slug") == slug]
        assert my_acts, "no activity for newly-signed tenant"
        # look for welcome / QUEUED
        welcome_evts = [a for a in my_acts if "welcome" in a.get("message", "").lower()]
        assert welcome_evts, f"no welcome activity entry — got {[a.get('message') for a in my_acts]}"
        assert any("queue" in a["message"].lower() for a in welcome_evts), \
            "welcome activity should indicate QUEUED (Resend key intentionally missing)"


# ============================================================================
# 3. TENANT LOAD DOCS — Rate Con PDF + Invoice PDF, cross-tenant 403, unauth 401
# ============================================================================
class TestTenantPDFs:
    def test_ratecon_pdf_success(self, tenantA_token, tenantA_load):
        r = requests.get(
            f"{BASE_URL}/api/t/{TENANT_A_SLUG}/loads/{tenantA_load['load_id']}/ratecon.pdf",
            headers={"Authorization": f"Bearer {tenantA_token}"}, timeout=30)
        assert r.status_code == 200, r.text[:200]
        assert r.content[:4] == b"%PDF", f"not a PDF, first bytes: {r.content[:20]}"
        assert len(r.content) > 2000, f"PDF too small: {len(r.content)} bytes"
        assert "application/pdf" in r.headers.get("content-type", "").lower()

    def test_ratecon_pdf_no_auth_401(self, tenantA_load):
        r = requests.get(
            f"{BASE_URL}/api/t/{TENANT_A_SLUG}/loads/{tenantA_load['load_id']}/ratecon.pdf",
            timeout=15)
        assert r.status_code == 401

    def test_ratecon_pdf_cross_tenant_403(self, tenantA_load):
        # provision tenant B and try to fetch tenant A's rate con with B's token -> 403
        marker = uuid.uuid4().hex[:5]
        r = requests.post(f"{BASE_URL}/api/hotshot/tenants", headers=ADMIN_HDR, json={
            "company_name": f"TEST_PDF_B_{marker}", "slug": f"test-pdf-b-{marker}",
            "plan": "starter", "admin_email": f"b{marker}@testpdfb.com",
            "admin_password": "BPassword1!", "admin_name": "B Admin"}, timeout=30)
        assert r.status_code == 200
        b_slug = r.json()["tenant"]["slug"]
        _created_slugs.append(b_slug)
        rl = requests.post(f"{BASE_URL}/api/t/{b_slug}/auth/login",
                           json={"email": f"b{marker}@testpdfb.com", "password": "BPassword1!"}, timeout=15)
        assert rl.status_code == 200
        b_token = rl.json()["token"]
        # try to fetch A's PDF using B's token
        r_cross = requests.get(
            f"{BASE_URL}/api/t/{TENANT_A_SLUG}/loads/{tenantA_load['load_id']}/ratecon.pdf",
            headers={"Authorization": f"Bearer {b_token}"}, timeout=30)
        assert r_cross.status_code == 403, f"expected 403, got {r_cross.status_code}"

    def test_ratecon_pdf_missing_load_404(self, tenantA_token):
        r = requests.get(
            f"{BASE_URL}/api/t/{TENANT_A_SLUG}/loads/LD-DOES-NOT-EXIST/ratecon.pdf",
            headers={"Authorization": f"Bearer {tenantA_token}"}, timeout=15)
        assert r.status_code == 404

    def test_invoice_pdf_success(self, tenantA_token, tenantA_invoice):
        r = requests.get(
            f"{BASE_URL}/api/t/{TENANT_A_SLUG}/invoices/{tenantA_invoice['invoice_id']}/pdf",
            headers={"Authorization": f"Bearer {tenantA_token}"}, timeout=30)
        assert r.status_code == 200, r.text[:200]
        assert r.content[:4] == b"%PDF"
        assert len(r.content) > 2000
        assert "application/pdf" in r.headers.get("content-type", "").lower()

    def test_invoice_pdf_no_auth_401(self, tenantA_invoice):
        r = requests.get(
            f"{BASE_URL}/api/t/{TENANT_A_SLUG}/invoices/{tenantA_invoice['invoice_id']}/pdf",
            timeout=15)
        assert r.status_code == 401


# ============================================================================
# 4. REGRESSIONS: tenant login, dashboard KPIs, load create + invoice create,
#    stripe checkout URL (do not complete payment).
# ============================================================================
class TestRegressions:
    def test_tenant_login_still_works(self):
        r = requests.post(f"{BASE_URL}/api/t/{TENANT_A_SLUG}/auth/login",
                          json={"email": TENANT_A_EMAIL, "password": TENANT_A_PW}, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert "token" in d
        assert d["user"]["role"] == "admin"

    def test_dashboard_kpis(self, tenantA_token):
        r = requests.get(f"{BASE_URL}/api/t/{TENANT_A_SLUG}/dashboard",
                         headers={"Authorization": f"Bearer {tenantA_token}"}, timeout=15)
        assert r.status_code == 200
        for k in ("total_loads", "active_loads", "gross_revenue", "gross_margin", "open_ar"):
            assert k in r.json()["kpis"]

    def test_stripe_checkout_url(self, tenantA_token):
        r = requests.post(f"{BASE_URL}/api/t/{TENANT_A_SLUG}/billing/checkout",
                          headers={"Authorization": f"Bearer {tenantA_token}"},
                          json={"lookup_key": "hotshot_growth_monthly", "origin_url": BASE_URL},
                          timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "checkout_url" in d
        assert d["checkout_url"].startswith("https://checkout.stripe.com/")
        assert d["session_id"].startswith("cs_")


# ============================================================================
# 5. SELF-SERVE RATE LIMIT — LAST (per-IP hourly counter; 4th signup -> 429)
# ============================================================================
@pytest.mark.order(-1)
class TestRateLimit:
    def test_4th_self_serve_signup_within_hour_returns_429(self):
        """Rate limit: 3 signups per hour per client IP. Since previous tests also count,
        we just verify that at SOME point within 5 more signups we hit 429 (or that we're
        already at the limit)."""
        got_429_at = None
        for i in range(1, 6):
            marker = uuid.uuid4().hex[:6]
            payload = {
                "company_name": f"TEST_RL_{marker}",
                "name": f"RL {i}", "email": f"rl{marker}@testrl.com",
                "password": "RateLim1!Pass", "origin_url": BASE_URL,
            }
            r = requests.post(f"{BASE_URL}/api/hotshot/signup", json=payload, timeout=30)
            if r.status_code == 429:
                got_429_at = i
                assert "too many" in r.text.lower() or "signup" in r.text.lower()
                break
            elif r.status_code == 200:
                _created_slugs.append(r.json()["slug"])
            else:
                pytest.fail(f"unexpected status {r.status_code}: {r.text}")
        assert got_429_at is not None, "never got 429 rate-limit within 5 additional signups"
