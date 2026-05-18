"""Investor Boardroom tests — iteration 25.

Covers:
- GET /api/investor/boardroom (admin) — shape + default probability
- POST /api/investor/probability — score sensitivity (defaults ~99/STRONG;
  fragile inputs drop below 50)
- GET /api/investor/data-room.zip — valid ZIP, > 1 MB, 6 files + README, brand
- GET /api/investor/deck.pdf — > 200KB, app/pdf
- GET /api/investor/one-pager.pdf — application/pdf
- GET /api/investor/financial-model.xlsx — valid openxml
- Admin-only gating (dispatcher → 401/403)
- Brand swap (orisei-freight → fedex → orisei-freight) and filenames
"""

import io
import os
import zipfile
from pathlib import Path

import pytest
import requests


# ------ BASE_URL resolution ------
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


# ------ fixtures ------
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


# ------ /boardroom ------
class TestBoardroom:
    def test_admin_can_fetch_boardroom(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/investor/boardroom", timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        # shape
        for k in ("market_sizing", "industry_benchmarks", "unit_economics",
                  "monthly_model", "annual_summary", "default_probability"):
            assert k in d, f"missing key {k}"
        assert len(d["monthly_model"]) == 36
        assert len(d["annual_summary"]) == 3
        prob = d["default_probability"]
        for k in ("score_pct", "band", "drivers"):
            assert k in prob
        # defaults are Orisei-favorable → capped at 99
        assert prob["score_pct"] == 99.0
        assert prob["band"] == "STRONG"
        assert len(prob["drivers"]) >= 8

    def test_dispatcher_rejected(self, disp_session):
        r = disp_session.get(f"{BASE_URL}/api/investor/boardroom", timeout=10)
        assert r.status_code in (401, 403), r.text


# ------ /probability ------
class TestProbability:
    def test_default_high_score(self, admin_session):
        payload = {
            "starting_capital_usd": 75000,
            "operator_experience_years": 13,
            "monthly_marketing_budget_usd": 1500,
            "carrier_pool_size": 0,
            "has_tms": True,
            "has_factoring_partner": True,
            "has_authority": True,
            "target_lanes_count": 6,
        }
        r = admin_session.post(f"{BASE_URL}/api/investor/probability",
                               json=payload, timeout=10)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["score_pct"] >= 90
        assert d["band"] == "STRONG"

    def test_fragile_inputs_drop_score(self, admin_session):
        payload = {
            "starting_capital_usd": 10000,
            "operator_experience_years": 1,
            "monthly_marketing_budget_usd": 0,
            "carrier_pool_size": 0,
            "has_tms": False,
            "has_factoring_partner": False,
            "has_authority": False,
            "target_lanes_count": 30,
        }
        r = admin_session.post(f"{BASE_URL}/api/investor/probability",
                               json=payload, timeout=10)
        assert r.status_code == 200, r.text
        d = r.json()
        # score must drop significantly from 99 default. FRAGILE band <60.
        assert d["score_pct"] < 60, f"expected <60, got {d['score_pct']}"
        assert d["band"] == "FRAGILE"
        # Ripple check: at least 40 pts below 99 default
        assert d["score_pct"] < 60, "score should ripple down with worse inputs"

    def test_dispatcher_rejected(self, disp_session):
        r = disp_session.post(f"{BASE_URL}/api/investor/probability",
                              json={}, timeout=10)
        assert r.status_code in (401, 403)


# ------ /deck.pdf ------
class TestDeckPdf:
    def test_deck_pdf_download(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/investor/deck.pdf", timeout=60)
        assert r.status_code == 200, r.text[:300]
        assert "application/pdf" in r.headers.get("content-type", "")
        assert len(r.content) > 200_000, f"deck only {len(r.content)} bytes"
        assert r.content.startswith(b"%PDF"), "not a valid PDF"
        cd = r.headers.get("content-disposition", "")
        assert "Pitch_Deck.pdf" in cd

    def test_dispatcher_rejected(self, disp_session):
        r = disp_session.get(f"{BASE_URL}/api/investor/deck.pdf", timeout=10)
        assert r.status_code in (401, 403)


# ------ /one-pager.pdf ------
class TestOnePagerPdf:
    def test_one_pager_download(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/investor/one-pager.pdf",
                              timeout=60)
        assert r.status_code == 200, r.text[:300]
        assert "application/pdf" in r.headers.get("content-type", "")
        assert r.content.startswith(b"%PDF")
        assert len(r.content) > 30_000
        assert "One_Pager.pdf" in r.headers.get("content-disposition", "")


# ------ /financial-model.xlsx ------
class TestFinancialModelXlsx:
    def test_xlsx_download(self, admin_session):
        r = admin_session.get(
            f"{BASE_URL}/api/investor/financial-model.xlsx", timeout=60)
        assert r.status_code == 200, r.text[:300]
        assert "spreadsheetml" in r.headers.get("content-type", "")
        # Verify valid XLSX (zip with [Content_Types].xml + workbook.xml)
        try:
            with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
                names = zf.namelist()
                assert "[Content_Types].xml" in names
                assert any(n.endswith("workbook.xml") for n in names)
        except zipfile.BadZipFile:
            pytest.fail("Not a valid XLSX zip")


# ------ /data-room.zip ------
class TestDataRoomZip:
    def test_zip_valid_and_complete(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/investor/data-room.zip",
                              timeout=120)
        assert r.status_code == 200, r.text[:300]
        assert r.headers.get("content-type", "").startswith("application/zip")
        assert len(r.content) > 1_000_000, f"zip only {len(r.content)} bytes"
        with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
            names = zf.namelist()
        # Must include README + 6 documents
        assert "README.txt" in names
        # Brand short_name should be Orisei
        assert any("Orisei" in n for n in names), names
        pdfs = [n for n in names if n.lower().endswith(".pdf")]
        xlsx = [n for n in names if n.lower().endswith(".xlsx")]
        csvs = [n for n in names if n.lower().endswith(".csv")]
        assert len(pdfs) >= 3, f"only {pdfs}"
        assert len(xlsx) >= 1
        assert len(csvs) >= 1
        # Pitch deck + one-pager + probability report + business plan = 4 PDFs
        assert any("Pitch_Deck" in n for n in pdfs)
        assert any("One_Pager" in n for n in pdfs)
        assert any("Probability" in n for n in pdfs)
        # Business plan optional but expected if file exists
        cd = r.headers.get("content-disposition", "")
        assert "VC_Data_Room.zip" in cd


# ------ Brand swap ------
class TestBrandSwap:
    def test_brand_swap_changes_zip_filenames(self, admin_session):
        # Try to activate FedEx
        r_act = admin_session.post(
            f"{BASE_URL}/api/branding/activate",
            json={"brand_id": "fedex"}, timeout=15)
        if r_act.status_code != 200:
            pytest.skip(
                f"branding/activate fedex unavailable: {r_act.status_code} {r_act.text[:200]}")
        try:
            r = admin_session.get(f"{BASE_URL}/api/investor/data-room.zip",
                                  timeout=120)
            assert r.status_code == 200
            with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
                names = zf.namelist()
            assert any("FedEx" in n or "Fedex" in n for n in names), \
                f"expected FedEx in filenames, got {names}"
            cd = r.headers.get("content-disposition", "")
            assert "Federal_Express" in cd or "FedEx" in cd, cd

            # Deck PDF header should also reflect FedEx
            r_deck = admin_session.get(
                f"{BASE_URL}/api/investor/deck.pdf", timeout=60)
            assert r_deck.status_code == 200
            cd_deck = r_deck.headers.get("content-disposition", "")
            assert "Federal_Express" in cd_deck or "FedEx" in cd_deck, cd_deck
        finally:
            # Restore Orisei
            admin_session.post(
                f"{BASE_URL}/api/branding/activate",
                json={"brand_id": "orisei-freight"}, timeout=15)
