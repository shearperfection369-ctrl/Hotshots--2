"""Iter29 — Personalized investor PDF/ZIP endpoints.

Covers:
- POST /api/investor/personalized-deck.pdf
- POST /api/investor/personalized-one-pager.pdf
- POST /api/investor/personalized-data-room.zip
- GET  /api/investor/personalized-outreach (history)
- Regression: GET /api/investor/deck.pdf (non-personalized)
- Regression: GET /api/investor/data-room.zip (non-personalized)
- Auth + validation edge cases
"""
import io
import os
import zipfile

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://clean-logistics-dash.preview.emergentagent.com").rstrip("/")
ADMIN_TOKEN = "test_session_admin_1"
AUTH_HEADERS = {"Authorization": f"Bearer {ADMIN_TOKEN}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update(AUTH_HEADERS)
    return s


# -------------------- Personalized PDFs --------------------
class TestPersonalizedDeck:
    def test_personalized_deck_greylock(self, session):
        r = session.post(f"{BASE_URL}/api/investor/personalized-deck.pdf",
                         json={"firm_name": "Greylock Partners", "contact_name": "Reid Hoffman"})
        assert r.status_code == 200, r.text
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:4] == b"%PDF", "Not a valid PDF magic bytes"
        assert len(r.content) > 100_000, f"PDF too small: {len(r.content)} bytes"
        cd = r.headers.get("content-disposition", "")
        assert "for_Greylock_Partners" in cd, f"Filename missing firm slug: {cd}"

    def test_personalized_deck_empty_firm_returns_422(self, session):
        r = session.post(f"{BASE_URL}/api/investor/personalized-deck.pdf",
                         json={"firm_name": ""})
        assert r.status_code == 422, f"Expected 422 got {r.status_code}: {r.text}"

    def test_personalized_deck_unauth_returns_401_or_403(self):
        r = requests.post(f"{BASE_URL}/api/investor/personalized-deck.pdf",
                          json={"firm_name": "AnonVC"},
                          headers={"Content-Type": "application/json"})
        assert r.status_code in (401, 403), f"Expected 401/403 got {r.status_code}"


class TestPersonalizedOnePager:
    def test_personalized_one_pager_sequoia(self, session):
        r = session.post(f"{BASE_URL}/api/investor/personalized-one-pager.pdf",
                         json={"firm_name": "Sequoia Capital"})
        assert r.status_code == 200, r.text
        assert r.content[:4] == b"%PDF"
        assert len(r.content) > 20_000
        assert "for_Sequoia_Capital" in r.headers.get("content-disposition", "")


# -------------------- Personalized ZIP --------------------
class TestPersonalizedDataRoom:
    def test_personalized_zip_a16z(self, session):
        r = session.post(f"{BASE_URL}/api/investor/personalized-data-room.zip",
                         json={"firm_name": "Andreessen Horowitz"})
        assert r.status_code == 200, r.text
        assert r.headers.get("content-type", "").startswith("application/zip")
        assert "for_Andreessen_Horowitz" in r.headers.get("content-disposition", "")

        zf = zipfile.ZipFile(io.BytesIO(r.content))
        names = zf.namelist()
        # README always present
        assert "README.txt" in names
        readme = zf.read("README.txt").decode("utf-8")
        assert "Prepared for: Andreessen Horowitz" in readme

        # Personalized PDFs
        pdf_names = [n for n in names if n.endswith(".pdf")]
        assert len(pdf_names) >= 3, f"Need >=3 personalized PDFs, got {pdf_names}"
        for pdf_name in pdf_names:
            assert "for_Andreessen_Horowitz" in pdf_name, f"PDF missing firm slug: {pdf_name}"

        # XLSX + CSV — clean (no firm slug in name)
        xlsx = [n for n in names if n.endswith(".xlsx")]
        csv = [n for n in names if n.endswith(".csv")]
        assert len(xlsx) == 1 and "for_" not in xlsx[0], f"XLSX should be clean: {xlsx}"
        assert len(csv) == 1 and "for_" not in csv[0], f"CSV should be clean: {csv}"

        # Total entries — expected 7 (4 PDFs + xlsx + csv + readme) but business plan PDF is conditional
        assert len(names) >= 6, f"Expected at least 6 entries, got {len(names)}: {names}"


# -------------------- History endpoint --------------------
class TestPersonalizedOutreachHistory:
    def test_history_admin_returns_recent(self, session):
        r = session.get(f"{BASE_URL}/api/investor/personalized-outreach")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "items" in data and "count" in data
        assert isinstance(data["items"], list)
        assert data["count"] == len(data["items"])
        # Should contain the 3 firms we generated above
        firms = {item.get("firm_name") for item in data["items"]}
        assert "Greylock Partners" in firms
        assert "Sequoia Capital" in firms
        assert "Andreessen Horowitz" in firms
        # doc_type fields present
        for item in data["items"]:
            assert "doc_type" in item
            assert "firm_name" in item
            assert "generated_at" in item
            assert "_id" not in item  # MongoDB _id must be excluded
        # Most-recent-first ordering
        ts = [item["generated_at"] for item in data["items"]]
        assert ts == sorted(ts, reverse=True), "Items not sorted by generated_at DESC"

    def test_history_unauth(self):
        r = requests.get(f"{BASE_URL}/api/investor/personalized-outreach")
        assert r.status_code in (401, 403)


# -------------------- Regression --------------------
class TestRegression:
    def test_nonpersonalized_deck_still_works(self, session):
        r = session.get(f"{BASE_URL}/api/investor/deck.pdf")
        assert r.status_code == 200
        assert r.content[:4] == b"%PDF"
        assert len(r.content) > 100_000
        cd = r.headers.get("content-disposition", "")
        # No "for_" personalization slug
        assert "for_" not in cd, f"Non-personalized deck has personalization in filename: {cd}"

    def test_nonpersonalized_data_room_still_works(self, session):
        r = session.get(f"{BASE_URL}/api/investor/data-room.zip")
        assert r.status_code == 200
        zf = zipfile.ZipFile(io.BytesIO(r.content))
        names = zf.namelist()
        # Original 10-doc bundle includes README + at least 6+ artifacts
        assert "README.txt" in names
        assert len(names) >= 7, f"Expected >=7 entries in original data room, got {len(names)}: {names}"
        # None of the PDFs/XLSX/CSV should be personalized
        for n in names:
            assert "for_" not in n, f"Non-personalized zip contains personalized file: {n}"
