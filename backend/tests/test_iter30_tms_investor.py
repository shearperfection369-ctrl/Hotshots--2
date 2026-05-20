"""Iter30 — Hot Shot TMS public investor pitch endpoints."""
import io
import os
import zipfile

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://clean-logistics-dash.preview.emergentagent.com").rstrip("/")


# ─── /api/public/tms-pitch-summary ──────────────────────────────────────────
class TestTmsPitchSummary:
    def test_pitch_summary_returns_hot_shot_brand(self):
        r = requests.get(f"{BASE_URL}/api/public/tms-pitch-summary", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()

        # Brand
        assert data["brand"]["company_name"] == "Hot Shot TMS"

        # Founder
        f = data["founder"]
        assert f["name"] == "Oliver Cummins"
        assert f["location"] == "Plymouth, Minnesota"
        assert f["tenure_years"] == 13

        # Platform stats
        ps = data["platform_stats"]
        assert ps["modules"] == 50
        assert ps["api_endpoints"] == 200
        assert ps["erp_connectors"] == 9
        assert ps["launch_day_integrations"] == 14
        assert ps["visual_themes"] == 16
        assert ps["brand_directory"] == 77
        assert ps["scorecard_metrics"] == 45

        # Plug & Play
        pp = data["plug_and_play"]
        assert len(pp["erp_connectors"]) == 9
        assert len(pp["launch_day_providers"]) == 14

        # Rebranding
        assert len(data["rebranding"]["brand_reel"]) == 10

        # Ask
        a = data["ask"]
        assert a["amount_usd"] == 1_500_000
        assert a["valuation_cap_usd"] == 8_000_000

    def test_no_auth_required(self):
        # No headers
        r = requests.get(f"{BASE_URL}/api/public/tms-pitch-summary", timeout=10)
        assert r.status_code == 200


# ─── /api/public/tms-deck.pdf ───────────────────────────────────────────────
class TestTmsDeckPdf:
    def test_returns_valid_pdf(self):
        r = requests.get(f"{BASE_URL}/api/public/tms-deck.pdf", timeout=30)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert "inline" in r.headers.get("content-disposition", "").lower()
        assert r.content[:4] == b"%PDF"
        assert len(r.content) > 100_000, f"PDF too small: {len(r.content)} bytes"


# ─── /api/public/tms-one-pager.pdf ──────────────────────────────────────────
class TestTmsOnePagerPdf:
    def test_returns_valid_pdf(self):
        r = requests.get(f"{BASE_URL}/api/public/tms-one-pager.pdf", timeout=30)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:4] == b"%PDF"
        assert len(r.content) > 10_000


# ─── /api/public/tms-data-room.zip ──────────────────────────────────────────
class TestTmsDataRoomZip:
    def test_returns_valid_zip_with_three_entries(self):
        r = requests.get(f"{BASE_URL}/api/public/tms-data-room.zip", timeout=45)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/zip")

        zf = zipfile.ZipFile(io.BytesIO(r.content))
        names = zf.namelist()
        assert "01_Hot_Shot_TMS_Pitch_Deck.pdf" in names
        assert "02_Hot_Shot_TMS_One_Pager.pdf" in names
        assert "README.txt" in names

        readme = zf.read("README.txt").decode()
        assert "Plymouth, Minnesota" in readme
        assert "Oliver Cummins" in readme


# ─── Regression: Orisei brokerage endpoints unchanged ───────────────────────
class TestOriseiRegression:
    def test_investor_summary_still_works(self):
        r = requests.get(f"{BASE_URL}/api/public/investor-summary", timeout=15)
        assert r.status_code == 200
        data = r.json()
        # Should not be Hot Shot TMS — must still be Orisei-branded
        brand_name = (data.get("brand") or {}).get("company_name", "") or data.get("company_name", "")
        assert "Hot Shot TMS" not in str(data)[:2000] or "Orisei" in str(data), \
            f"Orisei summary leaked into Hot Shot TMS branding: {brand_name}"

    def test_orisei_deck_pdf_still_works(self):
        r = requests.get(f"{BASE_URL}/api/public/deck.pdf", timeout=30)
        assert r.status_code == 200
        assert r.content[:4] == b"%PDF"
        # Orisei deck should not have Hot Shot TMS in filename
        cd = r.headers.get("content-disposition", "")
        assert "Hot_Shot_TMS" not in cd

    def test_orisei_one_pager_pdf_still_works(self):
        r = requests.get(f"{BASE_URL}/api/public/one-pager.pdf", timeout=30)
        assert r.status_code == 200
        assert r.content[:4] == b"%PDF"
        cd = r.headers.get("content-disposition", "")
        assert "Hot_Shot_TMS" not in cd


# ─── Investor intro form (brand-agnostic shared endpoint) ────────────────────
class TestInvestorIntroForm:
    def test_intro_accepts_hot_shot_tms_prefix(self):
        payload = {
            "name": "Test VC",
            "email": "test@vc.com",
            "firm": "Acme Capital",
            "message": "[Hot Shot TMS pitch] Interested in connecting about the seed round.",
        }
        r = requests.post(
            f"{BASE_URL}/api/public/investor-intro",
            json=payload,
            timeout=15,
        )
        assert r.status_code in (200, 201), r.text


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
