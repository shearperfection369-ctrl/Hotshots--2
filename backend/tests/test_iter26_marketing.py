"""Marketing Pack tests — iteration 26.

Covers:
- GET /api/marketing/carrier-sell-sheet.pdf (admin) — brand-aware PDF, >150KB
- GET /api/marketing/shipper-sell-sheet.pdf
- GET /api/marketing/press-release.pdf
- GET /api/marketing/linkedin-posts → JSON 3 posts w/ id, title, audience, body, hashtags, cta
- GET /api/marketing/cold-emails → JSON 3 emails w/ id, subject, audience, body, merge_tokens, follow_up_days, follow_up_body
- GET /api/marketing/pack.zip — bundles >=7 entries + README, brand-prefixed
- Updated /api/investor/data-room.zip now includes 3 marketing PDFs, >1.5 MB
- Admin gating (dispatcher → 401/403)
- Brand swap orisei → fedex → orisei
"""

import io
import os
import zipfile
from pathlib import Path

import pytest
import requests


def _resolve_base_url() -> str:
    env = os.environ.get("REACT_APP_BACKEND_URL")
    if env:
        return env.rstrip("/")
    fe_env = Path("/app/frontend/.env")
    if fe_env.exists():
        for line in fe_env.read_text().splitlines():
            if line.startswith("REACT_APP_BACKEND_URL"):
                return line.split("=", 1)[1].strip().strip('"').rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL not configured")


BASE_URL = _resolve_base_url()
ADMIN_TOKEN = "test_session_admin_1"
DISP_TOKEN = "test_disp_session"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {ADMIN_TOKEN}"})
    return s


@pytest.fixture(scope="module")
def disp_session():
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {DISP_TOKEN}"})
    return s


# ---------- PDFs ----------
class TestCarrierSellSheetPdf:
    def test_admin_download(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/marketing/carrier-sell-sheet.pdf", timeout=60)
        assert r.status_code == 200, r.text[:300]
        assert "application/pdf" in r.headers.get("content-type", "")
        assert r.content.startswith(b"%PDF")
        assert len(r.content) > 150_000, f"only {len(r.content)} bytes"
        cd = r.headers.get("content-disposition", "")
        assert "Carrier_Sell_Sheet.pdf" in cd

    def test_dispatcher_rejected(self, disp_session):
        r = disp_session.get(f"{BASE_URL}/api/marketing/carrier-sell-sheet.pdf", timeout=10)
        assert r.status_code in (401, 403)


class TestShipperSellSheetPdf:
    def test_admin_download(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/marketing/shipper-sell-sheet.pdf", timeout=60)
        assert r.status_code == 200, r.text[:300]
        assert "application/pdf" in r.headers.get("content-type", "")
        assert r.content.startswith(b"%PDF")
        assert len(r.content) > 150_000
        assert "Shipper_Sell_Sheet.pdf" in r.headers.get("content-disposition", "")


class TestPressReleasePdf:
    def test_admin_download(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/marketing/press-release.pdf", timeout=60)
        assert r.status_code == 200, r.text[:300]
        assert "application/pdf" in r.headers.get("content-type", "")
        assert r.content.startswith(b"%PDF")
        assert len(r.content) > 150_000
        assert "Press_Release.pdf" in r.headers.get("content-disposition", "")


# ---------- LinkedIn posts ----------
class TestLinkedInPosts:
    def test_shape(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/marketing/linkedin-posts", timeout=15)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert "posts" in d
        posts = d["posts"]
        assert len(posts) == 3
        ids = {p["id"] for p in posts}
        assert ids == {"founder_story", "operator_insight", "direct_gtm_ask"}
        required = {"id", "title", "audience", "body", "hashtags", "cta"}
        for p in posts:
            assert required.issubset(p.keys()), f"missing keys in {p.get('id')}"
            assert isinstance(p["hashtags"], list)
            assert len(p["hashtags"]) > 0
            assert isinstance(p["body"], str) and len(p["body"]) > 100
            assert isinstance(p["cta"], str) and len(p["cta"]) > 0

    def test_dispatcher_rejected(self, disp_session):
        r = disp_session.get(f"{BASE_URL}/api/marketing/linkedin-posts", timeout=10)
        assert r.status_code in (401, 403)


# ---------- Cold emails ----------
class TestColdEmails:
    def test_shape(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/marketing/cold-emails", timeout=15)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert "emails" in d
        emails = d["emails"]
        assert len(emails) == 3
        ids = {e["id"] for e in emails}
        assert ids == {"shipper_cold", "carrier_cold", "investor_followup"}
        required = {"id", "subject", "audience", "body", "merge_tokens",
                    "follow_up_days", "follow_up_body"}
        for e in emails:
            assert required.issubset(e.keys()), f"missing keys in {e.get('id')}"
            assert isinstance(e["merge_tokens"], list)
            assert len(e["merge_tokens"]) > 0
            assert isinstance(e["follow_up_days"], int) and e["follow_up_days"] > 0
            assert isinstance(e["body"], str) and len(e["body"]) > 100
            assert isinstance(e["follow_up_body"], str) and len(e["follow_up_body"]) > 0

    def test_dispatcher_rejected(self, disp_session):
        r = disp_session.get(f"{BASE_URL}/api/marketing/cold-emails", timeout=10)
        assert r.status_code in (401, 403)


# ---------- Pack ZIP ----------
class TestPackZip:
    def test_pack_zip_complete(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/marketing/pack.zip", timeout=120)
        assert r.status_code == 200, r.text[:300]
        assert r.headers.get("content-type", "").startswith("application/zip")
        assert len(r.content) > 500_000, f"zip only {len(r.content)} bytes"
        with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
            names = zf.namelist()
        # README + 7 content entries (3 sell-sheet PDFs + LinkedIn .md + .pdf + cold-email .md + .pdf)
        assert "README.txt" in names
        content = [n for n in names if n != "README.txt"]
        assert len(content) >= 7, f"expected >=7 content entries, got {content}"
        # brand prefix
        assert any("Orisei" in n for n in content), names
        assert any("Carrier_Sell_Sheet.pdf" in n for n in names)
        assert any("Shipper_Sell_Sheet.pdf" in n for n in names)
        assert any("Press_Release.pdf" in n for n in names)
        assert any("LinkedIn_Posts.pdf" in n for n in names)
        assert any("LinkedIn_Posts.md" in n for n in names)
        assert any("Cold_Email_Templates.pdf" in n for n in names)
        assert any("Cold_Email_Templates.md" in n for n in names)
        cd = r.headers.get("content-disposition", "")
        assert "Marketing_Pack.zip" in cd

    def test_dispatcher_rejected(self, disp_session):
        r = disp_session.get(f"{BASE_URL}/api/marketing/pack.zip", timeout=30)
        assert r.status_code in (401, 403)


# ---------- Updated investor data-room with marketing PDFs ----------
class TestInvestorDataRoomWithMarketing:
    def test_zip_includes_marketing_pdfs(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/investor/data-room.zip", timeout=180)
        assert r.status_code == 200, r.text[:300]
        # > 1.5 MB after adding marketing PDFs
        assert len(r.content) > 1_500_000, f"zip only {len(r.content)} bytes"
        with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
            names = zf.namelist()
        assert any("07_" in n and "Carrier_Sell_Sheet" in n for n in names), names
        assert any("08_" in n and "Shipper_Sell_Sheet" in n for n in names), names
        assert any("09_" in n and "Press_Release" in n for n in names), names


# ---------- Brand swap ----------
class TestBrandSwap:
    def test_fedex_brand_renames_pdfs(self, admin_session):
        r_act = admin_session.post(
            f"{BASE_URL}/api/branding/activate",
            json={"brand_id": "fedex"}, timeout=15)
        if r_act.status_code != 200:
            pytest.skip(f"branding/activate fedex unavailable: {r_act.status_code} {r_act.text[:200]}")
        try:
            # Carrier sheet should now have FedEx in CD and content
            r = admin_session.get(f"{BASE_URL}/api/marketing/carrier-sell-sheet.pdf", timeout=60)
            assert r.status_code == 200
            cd = r.headers.get("content-disposition", "")
            assert "Federal_Express" in cd or "FedEx" in cd, cd
            # Pack ZIP should rename to FedEx prefix
            rz = admin_session.get(f"{BASE_URL}/api/marketing/pack.zip", timeout=120)
            assert rz.status_code == 200
            with zipfile.ZipFile(io.BytesIO(rz.content)) as zf:
                names = zf.namelist()
            assert any("FedEx" in n or "Fedex" in n for n in names), names
        finally:
            admin_session.post(
                f"{BASE_URL}/api/branding/activate",
                json={"brand_id": "orisei-freight"}, timeout=15)
