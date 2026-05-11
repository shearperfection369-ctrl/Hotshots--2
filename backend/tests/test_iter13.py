"""Iteration 13 — Routing Guide, Truckload Carrier Combo, Copilot regression."""
import os
import io
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://clean-logistics-dash.preview.emergentagent.com").rstrip("/")
ADMIN_TOKEN = "test_session_admin_1"
DISP_TOKEN = "test_disp_session"


@pytest.fixture
def admin():
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {ADMIN_TOKEN}", "Content-Type": "application/json"})
    return s


@pytest.fixture
def disp():
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {DISP_TOKEN}", "Content-Type": "application/json"})
    return s


@pytest.fixture
def anon():
    return requests.Session()


# ---------------- Routing Guide ----------------
class TestRoutingGuide:
    def test_pdf_is_public_no_auth(self, anon):
        r = anon.get(f"{BASE_URL}/api/routing-guide/pdf", allow_redirects=True)
        assert r.status_code == 200, r.status_code
        assert r.headers.get("Content-Type", "").startswith("application/pdf")
        assert 400_000 <= len(r.content) <= 600_000, f"size={len(r.content)}"
        assert r.content[:4] == b"%PDF"

    def test_pdf_public_explicit_no_auth_header(self):
        # raw call ensures no auth header is set
        r = requests.get(f"{BASE_URL}/api/routing-guide/pdf")
        assert r.status_code == 200
        assert r.headers.get("Content-Type", "").startswith("application/pdf")

    def test_info_admin(self, admin):
        r = admin.get(f"{BASE_URL}/api/routing-guide/info")
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("title")
        assert d.get("revision") == "Revision 29"
        assert d.get("effective_date") == "2026-01-09"
        assert isinstance(d.get("size_bytes"), int) and d["size_bytes"] > 0
        assert d.get("pdf_url") == "/api/routing-guide/pdf"
        assert "notes" in d

    def test_email_template(self, admin):
        r = admin.get(
            f"{BASE_URL}/api/routing-guide/email-template",
            params={"to": "foo@bar.com", "cc": "ops@tennantco.com"},
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("subject")
        body = d.get("body", "")
        assert "Revision 29" in body
        assert "Effective Date: 2026-01-09" in body
        mailto = d.get("mailto", "")
        assert mailto.startswith("mailto:foo%40bar.com"), mailto[:80]
        assert "pdf_url" in d or "/api/routing-guide/pdf" in body or "/api/routing-guide/pdf" in mailto
        # pdf url should appear somewhere in the response
        flat = (body + mailto + d.get("pdf_url", "")).lower()
        assert "/api/routing-guide/pdf" in flat or "routing-guide%2fpdf" in flat

    def test_versions_list(self, admin):
        r = admin.get(f"{BASE_URL}/api/routing-guide/versions")
        assert r.status_code == 200, r.text
        data = r.json()
        # accept either list or dict with "versions"
        if isinstance(data, dict):
            data = data.get("versions") or data.get("items") or []
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_upload_new_revision(self, admin):
        # Get current count
        r1 = admin.get(f"{BASE_URL}/api/routing-guide/versions")
        before = r1.json()
        if isinstance(before, dict):
            before = before.get("versions") or before.get("items") or []
        before_n = len(before)

        # Build a tiny valid PDF
        fake_pdf = (
            b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
            b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj\n"
            b"xref\n0 4\n0000000000 65535 f\n0000000010 00000 n\n0000000053 00000 n\n0000000100 00000 n\ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n160\n%%EOF"
        )
        files = {"file": ("test_revision_30.pdf", io.BytesIO(fake_pdf), "application/pdf")}
        # multipart needs a session WITHOUT Content-Type: application/json
        s = requests.Session()
        s.headers.update({"Authorization": f"Bearer {ADMIN_TOKEN}"})
        r2 = s.post(f"{BASE_URL}/api/routing-guide/upload", files=files)
        assert r2.status_code in (200, 201), r2.text
        created_id = (r2.json() or {}).get("file_id") or (r2.json() or {}).get("id")

        r3 = admin.get(f"{BASE_URL}/api/routing-guide/versions")
        after = r3.json()
        if isinstance(after, dict):
            after = after.get("versions") or after.get("items") or []
        try:
            assert len(after) >= before_n + 1, f"versions before={before_n} after={len(after)}"
        finally:
            # CLEANUP — delete the test-uploaded fake PDF so the active
            # revision rolls back to the real "Revision 29" seeded PDF.
            if not created_id:
                # find by filename
                cand = next((v for v in after if v.get("filename") == "test_revision_30.pdf"), None)
                created_id = cand and (cand.get("file_id") or cand.get("id"))
            if created_id:
                admin.delete(f"{BASE_URL}/api/routing-guide/versions/{created_id}")


# ---------------- Truckload Booking Sheet carrier combo ----------------
class TestTruckloadCarrierCombo:
    def test_columns_have_carrier_combo(self, admin):
        r = admin.get(f"{BASE_URL}/api/workbook/truckload-bookings")
        assert r.status_code == 200, r.text
        d = r.json()
        cols = d.get("columns")
        assert isinstance(cols, list) and len(cols) > 0
        carrier_col = next((c for c in cols if c.get("key") == "carrier" or c.get("id") == "carrier" or c.get("name") == "carrier"), None)
        assert carrier_col, f"no carrier col in {[c.get('key') or c.get('id') or c.get('name') for c in cols]}"
        assert carrier_col.get("type") == "combo", carrier_col
        opts = carrier_col.get("options") or []
        assert len(opts) >= 13, f"only {len(opts)} options: {opts}"
        # check a few well-known
        joined = " ".join(opts).lower()
        for nm in ["xpo", "odfl", "saia", "estes", "knight", "schneider", "werner"]:
            assert nm in joined, f"missing {nm} in {opts}"

    def test_top_level_carrier_options(self, admin):
        r = admin.get(f"{BASE_URL}/api/workbook/truckload-bookings")
        d = r.json()
        co = d.get("carrier_options")
        assert isinstance(co, list) and len(co) >= 13


# ---------------- Regression ----------------
class TestRegression:
    def test_truckload_post_patch_version(self, admin):
        # version
        rv = admin.get(f"{BASE_URL}/api/workbook/truckload-bookings/version")
        assert rv.status_code == 200, rv.text
        v0 = rv.json().get("version", 0)

        # post a row
        row = {"origin": "TEST_ORIG", "destination": "TEST_DEST", "carrier": "TEST_CARRIER"}
        rp = admin.post(f"{BASE_URL}/api/workbook/truckload-bookings", json=row)
        assert rp.status_code in (200, 201), rp.text
        created = rp.json()
        rid = created.get("id") or created.get("_id") or (created.get("row") or {}).get("id")
        assert rid, created

        # patch
        rpatch = admin.patch(
            f"{BASE_URL}/api/workbook/truckload-bookings/{rid}",
            json={"carrier": "TEST_CARRIER_UPDATED"},
        )
        assert rpatch.status_code in (200, 204), rpatch.text

        # version should increase
        rv2 = admin.get(f"{BASE_URL}/api/workbook/truckload-bookings/version")
        assert rv2.status_code == 200
        v1 = rv2.json().get("version", 0)
        assert v1 > v0

        # cleanup
        admin.delete(f"{BASE_URL}/api/workbook/truckload-bookings/{rid}")

    def test_approved_carriers(self, admin):
        r = admin.get(f"{BASE_URL}/api/carriers/onboarding", params={"status": "approved"})
        assert r.status_code == 200, r.text
        data = r.json()
        if isinstance(data, dict):
            data = data.get("items") or data.get("carriers") or []
        # filter to approved client-side just in case
        approved = [c for c in data if (c.get("status") or "").lower() == "approved"] or data
        assert len(approved) >= 12, f"only {len(approved)} approved"
