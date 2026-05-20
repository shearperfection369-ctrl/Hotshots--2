"""Iter31 — TMS Investor Invite Links (one-time-link gate) backend tests."""
import io
import os
import zipfile
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://clean-logistics-dash.preview.emergentagent.com").rstrip("/")
ADMIN_TOKEN = "test_session_admin_1"
ADMIN_HEADERS = {"Authorization": f"Bearer {ADMIN_TOKEN}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def created_token():
    """Create one invite link to be used across the suite."""
    r = requests.post(f"{BASE_URL}/api/investor/invite-links",
                      headers=ADMIN_HEADERS,
                      json={"firm_name": "Greylock Partners",
                            "contact_name": "Reid Hoffman",
                            "days_valid": 30, "max_visits": 50})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["firm_name"] == "Greylock Partners"
    assert data["visit_count"] == 0
    assert "token" in data and len(data["token"]) >= 16
    assert "share_url" in data and data["token"] in data["share_url"]
    assert "expires_at" in data and data["expires_at"]
    assert data["max_visits"] == 50
    assert data["download_counts"] == {"deck": 0, "one-pager": 0, "zip": 0}
    yield data["token"]
    # teardown
    try:
        requests.delete(f"{BASE_URL}/api/investor/invite-links/{data['token']}",
                        headers=ADMIN_HEADERS, timeout=10)
    except Exception:
        pass


# -------------------- ADMIN AUTH --------------------
class TestAdminAuth:
    def test_create_requires_admin(self):
        r = requests.post(f"{BASE_URL}/api/investor/invite-links",
                          json={"firm_name": "NoAuth"})
        assert r.status_code in (401, 403)

    def test_create_validation_empty_firm(self):
        r = requests.post(f"{BASE_URL}/api/investor/invite-links",
                          headers=ADMIN_HEADERS, json={"firm_name": ""})
        assert r.status_code == 422


# -------------------- LIST / DISABLE / DELETE --------------------
class TestAdminCrud:
    def test_list_invite_links(self, created_token):
        r = requests.get(f"{BASE_URL}/api/investor/invite-links",
                         headers=ADMIN_HEADERS)
        assert r.status_code == 200
        data = r.json()
        assert "items" in data and "count" in data
        assert data["count"] >= 1
        tokens = [it["token"] for it in data["items"]]
        assert created_token in tokens
        item = next(it for it in data["items"] if it["token"] == created_token)
        for k in ("share_url", "visit_count", "unique_ip_count",
                  "last_visit_at", "download_counts"):
            assert k in item

    def test_disable_and_delete(self):
        # create disposable link
        r = requests.post(f"{BASE_URL}/api/investor/invite-links",
                          headers=ADMIN_HEADERS,
                          json={"firm_name": "TEST_DisposableVC"})
        assert r.status_code == 200
        tok = r.json()["token"]
        # disable
        r2 = requests.post(f"{BASE_URL}/api/investor/invite-links/{tok}/disable",
                           headers=ADMIN_HEADERS)
        assert r2.status_code == 200
        assert r2.json()["status"] == "disabled"
        # public summary should now return 410
        r3 = requests.get(f"{BASE_URL}/api/public/tms-link/{tok}")
        assert r3.status_code == 410
        # delete
        r4 = requests.delete(f"{BASE_URL}/api/investor/invite-links/{tok}",
                             headers=ADMIN_HEADERS)
        assert r4.status_code == 200
        assert r4.json()["status"] == "deleted"
        # subsequent list excludes it
        r5 = requests.get(f"{BASE_URL}/api/investor/invite-links",
                          headers=ADMIN_HEADERS)
        toks = [it["token"] for it in r5.json()["items"]]
        assert tok not in toks


# -------------------- PUBLIC ENDPOINTS --------------------
class TestPublic:
    def test_summary_valid(self, created_token):
        r = requests.get(f"{BASE_URL}/api/public/tms-link/{created_token}")
        assert r.status_code == 200
        data = r.json()
        assert data["firm_name"] == "Greylock Partners"
        assert data["contact_name"] == "Reid Hoffman"
        assert data["status"] == "active"
        assert data["max_visits"] == 50
        assert "visits_used" in data

    def test_summary_invalid_404(self):
        r = requests.get(f"{BASE_URL}/api/public/tms-link/not_a_real_token_xyz")
        assert r.status_code == 404

    def test_log_visit_increments(self, created_token):
        r = requests.post(f"{BASE_URL}/api/public/tms-link/{created_token}/visit",
                          json={"event": "page_view"})
        assert r.status_code == 200
        assert r.json()["status"] == "logged"
        # verify visit_count incremented in admin list
        lst = requests.get(f"{BASE_URL}/api/investor/invite-links",
                           headers=ADMIN_HEADERS).json()
        item = next(it for it in lst["items"] if it["token"] == created_token)
        assert item["visit_count"] >= 1
        assert item["last_visit_at"]

    def test_deck_pdf_personalized(self, created_token):
        r = requests.get(f"{BASE_URL}/api/public/tms-link/{created_token}/deck.pdf")
        assert r.status_code == 200
        assert r.content[:4] == b"%PDF"
        cd = r.headers.get("Content-Disposition", "")
        assert "for_Greylock_Partners" in cd
        # download_counts.deck increments
        lst = requests.get(f"{BASE_URL}/api/investor/invite-links",
                           headers=ADMIN_HEADERS).json()
        item = next(it for it in lst["items"] if it["token"] == created_token)
        assert item["download_counts"]["deck"] >= 1

    def test_one_pager_pdf_personalized(self, created_token):
        r = requests.get(f"{BASE_URL}/api/public/tms-link/{created_token}/one-pager.pdf")
        assert r.status_code == 200
        assert r.content[:4] == b"%PDF"
        assert "for_Greylock_Partners" in r.headers.get("Content-Disposition", "")
        lst = requests.get(f"{BASE_URL}/api/investor/invite-links",
                           headers=ADMIN_HEADERS).json()
        item = next(it for it in lst["items"] if it["token"] == created_token)
        assert item["download_counts"]["one-pager"] >= 1

    def test_data_room_zip_personalized(self, created_token):
        r = requests.get(f"{BASE_URL}/api/public/tms-link/{created_token}/data-room.zip")
        assert r.status_code == 200
        assert "for_Greylock_Partners" in r.headers.get("Content-Disposition", "")
        zf = zipfile.ZipFile(io.BytesIO(r.content))
        names = zf.namelist()
        assert len(names) == 3
        assert any("01_Hot_Shot_TMS_Pitch_Deck_for_Greylock_Partners" in n for n in names)
        assert any("02_Hot_Shot_TMS_One_Pager_for_Greylock_Partners" in n for n in names)
        readme = zf.read("README.txt").decode("utf-8")
        assert "Prepared for: Greylock Partners" in readme
        assert f"Token: {created_token}" in readme
        assert "Plymouth, Minnesota" in readme


# -------------------- REGRESSION --------------------
class TestRegression:
    def test_non_personalized_summary_still_works(self):
        r = requests.get(f"{BASE_URL}/api/public/tms-pitch-summary")
        assert r.status_code == 200
        body = r.json()
        # brand is correct
        brand = body.get("brand") or {}
        assert "Hot Shot TMS" in (brand.get("company_name") or "")

    def test_non_personalized_pdfs(self):
        for path in ("/api/public/tms-deck.pdf",
                     "/api/public/tms-one-pager.pdf"):
            r = requests.get(f"{BASE_URL}{path}")
            assert r.status_code == 200, path
            assert r.content[:4] == b"%PDF", path

    def test_non_personalized_zip(self):
        r = requests.get(f"{BASE_URL}/api/public/tms-data-room.zip")
        assert r.status_code == 200
        zf = zipfile.ZipFile(io.BytesIO(r.content))
        assert len(zf.namelist()) >= 3

    def test_orisei_endpoints_intact(self):
        r = requests.get(f"{BASE_URL}/api/public/investor-summary")
        assert r.status_code == 200
        body = r.json()
        text = str(body).lower()
        assert "orisei" in text
        r2 = requests.get(f"{BASE_URL}/api/public/deck.pdf")
        assert r2.status_code == 200
        assert r2.content[:4] == b"%PDF"


# -------------------- CAP / EXPIRED LINK BEHAVIOUR --------------------
class TestCapHit:
    def test_max_visits_cap_returns_423(self):
        # create a link with max_visits=1
        r = requests.post(f"{BASE_URL}/api/investor/invite-links",
                          headers=ADMIN_HEADERS,
                          json={"firm_name": "TEST_CapHitVC", "max_visits": 1})
        tok = r.json()["token"]
        try:
            # 1st visit OK
            assert requests.post(f"{BASE_URL}/api/public/tms-link/{tok}/visit",
                                 json={"event": "page_view"}).status_code == 200
            # subsequent summary should now hit cap → 423
            r2 = requests.get(f"{BASE_URL}/api/public/tms-link/{tok}")
            assert r2.status_code == 423
        finally:
            requests.delete(f"{BASE_URL}/api/investor/invite-links/{tok}",
                            headers=ADMIN_HEADERS)
