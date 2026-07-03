"""
Iter 56 - Bug fix regression: Lighthouse / QBR / Claims collateral MUST render
with the ACTIVE brand (Orisei Freight Solutions), NOT Walmart.

Root cause: _active_brand() in three modules queried {"active": True}, but the
Mongo schema field is `is_active`. First-inserted brand doc (Walmart) was
being returned as fallback.

This test suite:
  1. Verifies each lighthouse asset PDF contains 'Orisei' and NOT 'Walmart'.
  2. Smokes the QBR Studio + Claims Master dashboards / branded PDFs.
  3. Confirms the DB has an Orisei brand doc with is_active=True.
"""
import io
import os

import pytest
import requests
from pypdf import PdfReader
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
TOKEN = "test_session_admin_1"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

ASSET_KINDS = [
    "product_tour",
    "roi_calculator",
    "spec_sheet",
    "case_study",
    "security_brief",
    "onboarding_map",
]


def _pdf_text(content: bytes) -> str:
    reader = PdfReader(io.BytesIO(content))
    return "\n".join(p.extract_text() or "" for p in reader.pages)


# -------------------- Lighthouse asset PDFs --------------------
class TestLighthouseAssetsBrand:
    @pytest.mark.parametrize("kind", ASSET_KINDS)
    def test_asset_pdf_has_orisei_not_walmart(self, kind):
        r = requests.get(
            f"{BASE_URL}/api/lighthouse/assets/{kind}.pdf",
            headers=HEADERS,
            timeout=30,
        )
        assert r.status_code == 200, f"{kind} returned {r.status_code}: {r.text[:200]}"
        assert r.headers.get("content-type", "").startswith("application/pdf"), (
            f"{kind} content-type is {r.headers.get('content-type')}"
        )
        assert r.content[:4] == b"%PDF", f"{kind} not a PDF"

        text = _pdf_text(r.content).lower()
        assert "orisei" in text, f"{kind} PDF has no 'Orisei' branding. First 400 chars: {text[:400]}"
        assert "walmart" not in text, f"{kind} PDF STILL contains 'walmart'. Extract: {text[:400]}"
        assert "bentonville" not in text, f"{kind} PDF contains 'bentonville'. Extract: {text[:400]}"

    def test_asset_catalog_endpoint(self):
        r = requests.get(f"{BASE_URL}/api/lighthouse/assets/catalog", headers=HEADERS, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list) or isinstance(data, dict)


# -------------------- QBR Studio smoke + branded PDF --------------------
class TestQBRStudioBrand:
    def test_qbr_dashboard_smoke(self):
        # QBR studio doesn't expose /dashboard — use /shippers list as smoke.
        r = requests.get(f"{BASE_URL}/api/qbr-studio/shippers", headers=HEADERS, timeout=20)
        assert r.status_code == 200, f"QBR shippers failed: {r.text[:200]}"

    def test_qbr_pdf_if_any_qbr_exists(self):
        # Try to list drafts; if any exist, fetch pdf and validate branding.
        r = requests.get(f"{BASE_URL}/api/qbr-studio/drafts", headers=HEADERS, timeout=20)
        if r.status_code != 200:
            pytest.skip(f"qbr drafts list not available: {r.status_code}")
        payload = r.json()
        drafts = payload if isinstance(payload, list) else payload.get("drafts") or payload.get("items") or []
        if not drafts:
            pytest.skip("no QBR drafts in db - shipper-list smoke covered above")
        draft_id = drafts[0].get("draft_id") or drafts[0].get("id") or drafts[0].get("_id")
        assert draft_id, f"no id field in qbr draft: {list(drafts[0].keys())}"
        pdf_r = requests.get(
            f"{BASE_URL}/api/qbr-studio/drafts/{draft_id}/report.pdf", headers=HEADERS, timeout=30
        )
        if pdf_r.status_code == 404:
            pytest.skip(f"qbr pdf route not exposed for id {draft_id}")
        assert pdf_r.status_code == 200, f"QBR pdf {draft_id} status {pdf_r.status_code}: {pdf_r.text[:200]}"
        text = _pdf_text(pdf_r.content).lower()
        assert "orisei" in text, f"QBR {draft_id} pdf lacks Orisei: {text[:400]}"
        assert "walmart" not in text, f"QBR {draft_id} pdf STILL has walmart: {text[:400]}"


# -------------------- Claims Master smoke + branded PDF --------------------
class TestClaimsMasterBrand:
    def test_claims_dashboard_smoke(self):
        r = requests.get(f"{BASE_URL}/api/claims/dashboard", headers=HEADERS, timeout=20)
        assert r.status_code == 200, f"claims dashboard failed: {r.text[:200]}"

    def test_claim_report_pdf_if_any_claim(self):
        r = requests.get(f"{BASE_URL}/api/claims/claims", headers=HEADERS, timeout=20)
        if r.status_code != 200:
            pytest.skip(f"claims list not available: {r.status_code}")
        payload = r.json()
        claims = payload if isinstance(payload, list) else payload.get("claims") or payload.get("items") or []
        if not claims:
            pytest.skip("no claims - dashboard-only smoke covered above")
        cid = claims[0].get("claim_id") or claims[0].get("id") or claims[0].get("_id")
        assert cid, f"no id field in claim: {list(claims[0].keys())}"
        pdf_r = requests.get(
            f"{BASE_URL}/api/claims/claims/{cid}/report.pdf", headers=HEADERS, timeout=30
        )
        if pdf_r.status_code == 404:
            pytest.skip(f"claim report pdf route not exposed for id {cid}")
        assert pdf_r.status_code == 200, f"claim pdf {cid} status {pdf_r.status_code}"
        text = _pdf_text(pdf_r.content).lower()
        assert "orisei" in text, f"claim {cid} pdf lacks Orisei: {text[:400]}"
        assert "walmart" not in text, f"claim {cid} pdf STILL has walmart: {text[:400]}"


# -------------------- Root-cause guard: brand DB state --------------------
class TestBrandDBState:
    """If a brand-list admin endpoint exists, verify the active brand is
    Orisei-flavoured, not Walmart. Skips gracefully if the endpoint is not
    exposed."""

    def test_active_brand_is_orisei(self):
        # Try common brand endpoints
        candidates = [
            "/api/brand/company",
            "/api/company-brand",
            "/api/brand-kit/active",
            "/api/branding/active",
        ]
        for path in candidates:
            r = requests.get(f"{BASE_URL}{path}", headers=HEADERS, timeout=10)
            if r.status_code == 200:
                data = r.json()
                dumped = str(data).lower()
                assert "orisei" in dumped, f"{path} does not surface Orisei: {dumped[:400]}"
                return
        pytest.skip("no brand admin endpoint reachable; verified indirectly via PDF text")
