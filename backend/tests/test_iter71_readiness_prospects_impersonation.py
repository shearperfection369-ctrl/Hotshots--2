"""iter71 — Platform Readiness self-test + Prospect hit list + View-as-client impersonation."""
import os
import time
import uuid
import urllib.parse

import pytest
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE}/api"
ADMIN = {"Authorization": "Bearer test_session_admin_1"}


# -------- helpers --------
def _dispatcher_headers():
    # Dispatcher on Orisei (not admin) — for 403 gating
    return {"Authorization": "Bearer test_session_dispatcher_1"}


# ================= 1) READINESS =================
class TestReadiness:
    @pytest.fixture(scope="class")
    def readiness_run(self):
        # ~5-15s; allow up to 60s
        r = requests.post(f"{API}/hotshot/readiness/run", headers=ADMIN, timeout=90)
        assert r.status_code == 200, r.text
        return r.json()

    def test_readiness_verdict_ready_to_sell(self, readiness_run):
        assert readiness_run["verdict"] == "READY_TO_SELL", f"got {readiness_run.get('verdict')}"
        assert readiness_run["metrics"]["failed"] == 0
        fp = readiness_run["metrics"]["functional_pass"]
        # e.g., "20/20"
        num, den = fp.split("/")
        assert num == den and int(den) >= 15, f"functional_pass {fp}"
        assert readiness_run["score"] >= 90
        assert "categories" in readiness_run and len(readiness_run["categories"]) >= 5

    def test_readiness_cleans_up_selftest_tenant(self, readiness_run):
        # No selftest-* tenants remain
        r = requests.get(f"{API}/hotshot/tenants", headers=ADMIN, timeout=30)
        assert r.status_code == 200, r.text
        slugs = [t["slug"] for t in r.json().get("tenants", [])]
        leftovers = [s for s in slugs if s.startswith("selftest-")]
        assert not leftovers, f"leftover selftest tenants: {leftovers}"

    def test_readiness_run_history(self, readiness_run):
        r = requests.get(f"{API}/hotshot/readiness/runs", headers=ADMIN, timeout=30)
        assert r.status_code == 200
        runs = r.json().get("runs", [])
        assert len(runs) >= 1
        assert runs[0].get("run_id") == readiness_run["run_id"]

    def test_readiness_latest(self, readiness_run):
        r = requests.get(f"{API}/hotshot/readiness/latest", headers=ADMIN, timeout=30)
        assert r.status_code == 200
        assert r.json().get("run", {}).get("run_id") == readiness_run["run_id"]

    def test_readiness_non_admin_blocked(self):
        r = requests.post(f"{API}/hotshot/readiness/run", headers=_dispatcher_headers(), timeout=30)
        assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code}"

        r2 = requests.post(f"{API}/hotshot/readiness/run", timeout=30)
        assert r2.status_code in (401, 403)


# ================= 2) PROSPECTS =================
class TestProspects:
    @pytest.fixture(scope="class")
    def seed_check(self):
        r = requests.get(f"{API}/hotshot/prospects", headers=ADMIN, timeout=30)
        assert r.status_code == 200, r.text
        return r.json()

    def test_seed_prospects_present(self, seed_check):
        rows = seed_check.get("prospects", [])
        assert len(rows) >= 12, f"expected >=12 seeded prospects, got {len(rows)}"
        assert "counts" in seed_check
        assert "statuses" in seed_check
        for r in rows:
            assert "email_draft" in r
            assert r["email_draft"]["subject"]
            assert r["email_draft"]["body"]

    def test_prospect_full_crud(self):
        # CREATE
        company = f"TEST_Prospect_{uuid.uuid4().hex[:6]}"
        c = requests.post(f"{API}/hotshot/prospects", headers=ADMIN,
                          json={"company": company, "contact": "Test Contact",
                                "email": "test@example.com", "city": "TestCity",
                                "size": "Broker", "notes": "unit test row"}, timeout=30)
        assert c.status_code == 200, c.text
        prospect = c.json()["prospect"]
        pid = prospect["prospect_id"]
        assert prospect["company"] == company
        assert prospect["status"] == "new"

        try:
            # GET verify persist
            g = requests.get(f"{API}/hotshot/prospects", headers=ADMIN, timeout=30)
            rows = g.json()["prospects"]
            match = [r for r in rows if r["prospect_id"] == pid]
            assert match and match[0]["company"] == company

            # PATCH status -> contacted (valid)
            u = requests.patch(f"{API}/hotshot/prospects/{pid}", headers=ADMIN,
                               json={"status": "contacted"}, timeout=30)
            assert u.status_code == 200, u.text

            # Verify status persistence
            g2 = requests.get(f"{API}/hotshot/prospects", headers=ADMIN, timeout=30)
            rows = g2.json()["prospects"]
            match = [r for r in rows if r["prospect_id"] == pid][0]
            assert match["status"] == "contacted"
            assert "contacted_at" in match

            # PATCH invalid status -> 400
            b = requests.patch(f"{API}/hotshot/prospects/{pid}", headers=ADMIN,
                               json={"status": "bogus_status"}, timeout=30)
            assert b.status_code == 400
        finally:
            # DELETE
            d = requests.delete(f"{API}/hotshot/prospects/{pid}", headers=ADMIN, timeout=30)
            assert d.status_code == 200

        # 404 verify
        d2 = requests.delete(f"{API}/hotshot/prospects/{pid}", headers=ADMIN, timeout=30)
        assert d2.status_code == 404

    def test_prospects_email_draft_personalized(self, seed_check):
        rows = seed_check.get("prospects", [])
        # Find one seed prospect
        seed = next((r for r in rows if r.get("is_sample")), None)
        assert seed is not None, "no sample seeded"
        draft = seed["email_draft"]
        assert seed["company"] in draft["subject"]
        first = seed.get("contact", "there").split(" ")[0]
        assert first in draft["body"]

    def test_prospects_unauthed(self):
        r = requests.get(f"{API}/hotshot/prospects", timeout=15)
        assert r.status_code in (401, 403)


# ================= 3) IMPERSONATION =================
class TestImpersonation:
    def test_impersonate_returns_token(self):
        r = requests.post(f"{API}/hotshot/tenants/acme-freight-co/impersonate",
                          headers=ADMIN, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("token")
        assert body.get("portal_path") == "/t/acme-freight-co/app"
        assert body.get("expires_in_hours") == 2

        # Use token
        token = body["token"]
        me = requests.get(f"{API}/t/acme-freight-co/auth/me",
                          headers={"Authorization": f"Bearer {token}"}, timeout=15)
        assert me.status_code == 200, me.text
        me_data = me.json()
        assert me_data.get("impersonated") is True
        assert me_data.get("role") == "admin"

    def test_impersonate_non_admin_blocked(self):
        r = requests.post(f"{API}/hotshot/tenants/acme-freight-co/impersonate",
                          headers=_dispatcher_headers(), timeout=15)
        assert r.status_code in (401, 403)

        r2 = requests.post(f"{API}/hotshot/tenants/acme-freight-co/impersonate", timeout=15)
        assert r2.status_code in (401, 403)

    def test_normal_tenant_login_no_impersonation_flag(self):
        # Log in as real tenant admin — verify NO impersonation flag
        lr = requests.post(f"{API}/t/acme-freight-co/auth/login",
                           json={"email": "admin@acmefreight.com", "password": "AcmeDemo123!"},
                           timeout=15)
        assert lr.status_code == 200, lr.text
        token = lr.json()["token"]

        me = requests.get(f"{API}/t/acme-freight-co/auth/me",
                          headers={"Authorization": f"Bearer {token}"}, timeout=15)
        assert me.status_code == 200
        assert not me.json().get("impersonated"), "regular login should NOT have impersonated flag"

    def test_impersonate_activity_logged(self):
        # Fire an impersonation
        requests.post(f"{API}/hotshot/tenants/acme-freight-co/impersonate", headers=ADMIN, timeout=15)
        r = requests.get(f"{API}/hotshot/tenants/acme-freight-co/activity",
                         headers=ADMIN, timeout=15)
        assert r.status_code == 200
        acts = r.json().get("activity", [])
        assert any(a.get("kind") == "impersonate" for a in acts), "no impersonate activity logged"


# ================= 4) MULTI-RUN READINESS HISTORY (for chart) =================
class TestReadinessHistory:
    def test_multiple_runs_history(self):
        # Just check the current stored history has >=2 runs after this file's other class ran once.
        # Trigger one more here to be safe.
        r = requests.post(f"{API}/hotshot/readiness/run", headers=ADMIN, timeout=90)
        assert r.status_code == 200
        h = requests.get(f"{API}/hotshot/readiness/runs", headers=ADMIN, timeout=30)
        runs = h.json().get("runs", [])
        assert len(runs) >= 2, f"expected >=2 history entries for chart, got {len(runs)}"
        # Each has metrics + score for chart
        for run in runs[:2]:
            assert "score" in run
            assert "started_at" in run
