"""Iteration 24 — Provider Outreach + BOL doc render via /api/documents/{id}/pdf.

Covers:
  - BOL document PDF goes through Orisei build_bol_pdf (Calafia/griffin)
  - Non-BOL doc types render successfully with brand-aware header
  - /provider-outreach/catalog returns >=14 providers with correct shape
  - POST /send dry_run=true persists, returns dry_run rows w/ html_preview
  - POST /send without Resend creds returns 400 with hint
  - to_email_overrides honored
  - admin-only enforcement (dispatcher 403)
  - /history sorted desc
  - PUT /{id}/status replied/closed/invalid/missing
"""
import os
import pytest
import requests

def _load_base():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if not v:
        # Fallback: read frontend/.env
        try:
            with open("/app/frontend/.env") as f:
                for line in f:
                    if line.startswith("REACT_APP_BACKEND_URL"):
                        v = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break
        except Exception:
            pass
    if not v:
        raise RuntimeError("REACT_APP_BACKEND_URL missing")
    return v.rstrip("/")

BASE = _load_base()
ADMIN_HDR = {"Authorization": "Bearer test_session_admin_1"}
DISP_HDR = {"Authorization": "Bearer test_disp_session"}


# ---------- Document PDF rendering ----------
class TestDocumentsBOL:
    def test_bol_pdf_via_documents_endpoint(self):
        r = requests.get(f"{BASE}/api/documents/DOC-FAA5C8A6/pdf", headers=ADMIN_HDR, timeout=30)
        assert r.status_code == 200, r.text[:300]
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content.startswith(b"%PDF")
        # Orisei BOL PDFs are sizeable (~150KB+) due to embedded griffin/logo
        assert len(r.content) > 50_000, f"BOL PDF suspiciously small: {len(r.content)}"

    @pytest.mark.parametrize("doc_id", ["DOC-D945D6AA", "DOC-E0C4541B", "DOC-E243799E", "DOC-F1C26490"])
    def test_non_bol_pdf_renders(self, doc_id):
        r = requests.get(f"{BASE}/api/documents/{doc_id}/pdf", headers=ADMIN_HDR, timeout=30)
        assert r.status_code == 200, f"{doc_id} -> {r.status_code} {r.text[:200]}"
        assert r.content.startswith(b"%PDF")


# ---------- Provider Outreach catalog ----------
class TestOutreachCatalog:
    def test_catalog_returns_14_providers(self):
        r = requests.get(f"{BASE}/api/provider-outreach/catalog", headers=ADMIN_HDR, timeout=15)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert body["count"] >= 14
        assert len(body["providers"]) >= 14
        required = {"id", "name", "category", "what_we_need", "default_email", "signup_url",
                    "has_credentials", "last_sent_at", "last_status"}
        for p in body["providers"]:
            assert required <= set(p.keys()), f"missing keys for {p.get('id')}: {required - set(p.keys())}"
            assert isinstance(p["has_credentials"], bool)
        ids = {p["id"] for p in body["providers"]}
        for must in ["dat", "truckstop", "convoy", "resend", "quickbooks", "fmcsa"]:
            assert must in ids, f"catalog missing {must}"

    def test_catalog_requires_auth(self):
        r = requests.get(f"{BASE}/api/provider-outreach/catalog", timeout=15)
        assert r.status_code in (401, 403)


# ---------- Provider Outreach send ----------
class TestOutreachSend:
    def test_dry_run_persists_and_returns_html_preview(self):
        payload = {"provider_ids": ["dat", "truckstop"], "dry_run": True,
                   "note_appendix": "TEST_iter24 dry run"}
        r = requests.post(f"{BASE}/api/provider-outreach/send", json=payload, headers=ADMIN_HDR, timeout=20)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert body["sent"] == 0
        assert body["dry_run_count"] == 2
        assert body["total"] == 2
        for rec in body["results"]:
            assert rec["status"] == "dry_run"
            assert "html_preview" in rec and rec["html_preview"].startswith("<!doctype html>")
            assert rec["id"].startswith("PO-")

    def test_send_without_resend_returns_400_with_hint(self):
        payload = {"provider_ids": ["dat"], "dry_run": False}
        r = requests.post(f"{BASE}/api/provider-outreach/send", json=payload, headers=ADMIN_HDR, timeout=20)
        assert r.status_code == 400, r.text[:300]
        detail = (r.json().get("detail") or "").lower()
        assert "resend" in detail and "connections" in detail

    def test_to_email_overrides_respected(self):
        payload = {"provider_ids": ["dat"], "dry_run": True,
                   "to_email_overrides": {"dat": "custom@example.com"}}
        r = requests.post(f"{BASE}/api/provider-outreach/send", json=payload, headers=ADMIN_HDR, timeout=20)
        assert r.status_code == 200, r.text[:300]
        results = r.json()["results"]
        assert results[0]["to_email"] == "custom@example.com"

    def test_send_admin_only(self):
        payload = {"provider_ids": ["dat"], "dry_run": True}
        r = requests.post(f"{BASE}/api/provider-outreach/send", json=payload, headers=DISP_HDR, timeout=20)
        assert r.status_code == 403, r.text[:300]

    def test_send_empty_or_invalid_ids_400(self):
        r = requests.post(f"{BASE}/api/provider-outreach/send",
                          json={"provider_ids": ["__not_a_real_provider__"], "dry_run": True},
                          headers=ADMIN_HDR, timeout=20)
        assert r.status_code == 400


# ---------- Provider Outreach history + status updates ----------
class TestOutreachHistoryAndStatus:
    def test_history_sorted_desc(self):
        r = requests.get(f"{BASE}/api/provider-outreach/history", headers=ADMIN_HDR, timeout=15)
        assert r.status_code == 200
        items = r.json()["items"]
        assert isinstance(items, list)
        if len(items) >= 2:
            assert items[0]["sent_at"] >= items[1]["sent_at"], "history must be desc by sent_at"

    def test_status_replied_then_closed(self):
        # Make a fresh dry-run row we can mutate
        send = requests.post(
            f"{BASE}/api/provider-outreach/send",
            json={"provider_ids": ["resend"], "dry_run": True, "note_appendix": "TEST_iter24 status"},
            headers=ADMIN_HDR, timeout=20,
        )
        assert send.status_code == 200
        oid = send.json()["results"][0]["id"]

        r1 = requests.put(f"{BASE}/api/provider-outreach/{oid}/status",
                          json={"status": "replied"}, headers=ADMIN_HDR, timeout=15)
        assert r1.status_code == 200
        assert r1.json()["status"] == "replied"

        r2 = requests.put(f"{BASE}/api/provider-outreach/{oid}/status",
                          json={"status": "closed"}, headers=ADMIN_HDR, timeout=15)
        assert r2.status_code == 200
        assert r2.json()["status"] == "closed"

    def test_status_invalid_400(self):
        r = requests.put(f"{BASE}/api/provider-outreach/PO-FAKEFAKE/status",
                         json={"status": "wat"}, headers=ADMIN_HDR, timeout=15)
        assert r.status_code == 400

    def test_status_missing_404(self):
        r = requests.put(f"{BASE}/api/provider-outreach/PO-DOESNOTEXIST/status",
                         json={"status": "replied"}, headers=ADMIN_HDR, timeout=15)
        assert r.status_code == 404


# ---------- Light regression ----------
class TestRegression:
    @pytest.mark.parametrize("path", [
        "/api/brokerage/settings",
        "/api/connections",
        "/api/documents?limit=5",
    ])
    def test_existing_endpoints_still_ok(self, path):
        r = requests.get(f"{BASE}{path}", headers=ADMIN_HDR, timeout=15)
        assert r.status_code == 200, f"{path} -> {r.status_code}"
