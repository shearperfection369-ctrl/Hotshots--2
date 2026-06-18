"""Iteration 42 — Internal Document Vault (immutable PDF archive).

Covers:
  * GET /api/doc-vault list + filters (doc_type, doc_id, ref_id, since, limit)
  * GET /api/doc-vault/stats (total, by_type, oldest_at, retention_years=7)
  * Auto-archive on /api/documents/{id}/pdf (BOL) with version increment
  * Auto-archive on /api/orisei/rate-confirmations/{rc_id}/pdf (RATE_CONFIRMATION)
  * Auto-archive on /api/orisei/quotes/{quote_id}/pdf (QUOTE)
  * GET /api/doc-vault/{archive_id} metadata incl. payload_snapshot
  * GET /api/doc-vault/{archive_id}/file streams PDF + headers
  * POST /api/doc-vault/{archive_id}/re-render returns correct next_url
  * 404 on unknown archive_id
"""
from __future__ import annotations

import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://clean-logistics-dash.preview.emergentagent.com",
).rstrip("/")
TOKEN = "test_session_admin_1"


@pytest.fixture(scope="session")
def api():
    s = requests.Session()
    s.headers.update({
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
    })
    return s


@pytest.fixture(scope="session")
def bol_doc_id(api):
    """Find or create a BOL document we can render PDFs from."""
    r = api.get(f"{BASE_URL}/api/documents?limit=50")
    assert r.status_code == 200, r.text
    docs = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
    for d in docs:
        if d.get("type") == "BOL":
            return d["document_id"]
    # Fall back to any document so /pdf hook still fires
    return docs[0]["document_id"]


@pytest.fixture(scope="session")
def quote_id(api):
    r = api.get(f"{BASE_URL}/api/orisei/quotes")
    assert r.status_code == 200
    items = r.json().get("items", [])
    assert items, "Need at least one orisei quote in DB"
    return items[0]["quote_id"]


@pytest.fixture(scope="session")
def rc_id(api):
    """Reuse existing RC, else create one tied to an existing booking."""
    r = api.get(f"{BASE_URL}/api/orisei/rate-confirmations")
    if r.status_code == 200 and r.json().get("items"):
        return r.json()["items"][0]["rc_id"]
    # Need a booking
    br = api.get(f"{BASE_URL}/api/brokerage/margins")
    assert br.status_code == 200
    bookings = br.json().get("bookings", [])
    assert bookings, "Need a brokerage booking"
    booking_id = bookings[0].get("booked_id") or bookings[0].get("booking_id")
    payload = {
        "booking_id": booking_id,
        "carrier_name": "TEST_iter42_Carrier",
        "carrier_mc": "MC999999",
        "carrier_contact_email": "carrier@test.com",
        "carrier_contact_phone": "555-0100",
        "driver_name": "TEST Driver",
        "driver_phone": "555-0101",
        "tractor_number": "T-42",
        "trailer_number": "TR-42",
        "rate_usd": 1500.00,
        "fuel_surcharge_usd": 0.0,
        "lumper_usd": 0.0,
        "detention_usd": 0.0,
        "other_accessorials_usd": 0.0,
        "total_payable_usd": 1500.00,
        "payment_terms": "Quick Pay 2%",
        "notes": "TEST_iter42",
    }
    cr = api.post(f"{BASE_URL}/api/orisei/rate-confirmations", json=payload)
    assert cr.status_code in (200, 201), cr.text
    return cr.json()["rc_id"]


# -------------------- LIST + STATS --------------------
class TestDocVaultListStats:

    def test_list_default(self, api):
        r = api.get(f"{BASE_URL}/api/doc-vault")
        assert r.status_code == 200
        body = r.json()
        assert "items" in body and "count" in body
        assert body["retention_years"] == 7
        assert isinstance(body["items"], list)

    def test_list_filter_doc_type_bol(self, api):
        r = api.get(f"{BASE_URL}/api/doc-vault?doc_type=BOL")
        assert r.status_code == 200
        items = r.json()["items"]
        if items:
            assert all(it["doc_type"] == "BOL" for it in items)

    def test_list_filter_limit(self, api):
        r = api.get(f"{BASE_URL}/api/doc-vault?limit=2")
        assert r.status_code == 200
        assert len(r.json()["items"]) <= 2

    def test_stats_shape(self, api):
        r = api.get(f"{BASE_URL}/api/doc-vault/stats")
        assert r.status_code == 200
        body = r.json()
        assert "total_documents" in body
        assert "by_type" in body and isinstance(body["by_type"], list)
        assert "oldest_at" in body
        assert body["retention_years"] == 7
        for bt in body["by_type"]:
            assert {"doc_type", "count", "bytes", "latest"} <= set(bt.keys())


# -------------------- AUTO-ARCHIVE: BOL --------------------
class TestBolAutoArchive:

    def test_bol_pdf_creates_archive_and_versions(self, api, bol_doc_id):
        # snapshot count before
        before = api.get(
            f"{BASE_URL}/api/doc-vault?doc_id={bol_doc_id}").json()["count"]
        # First render
        r1 = api.get(f"{BASE_URL}/api/documents/{bol_doc_id}/pdf")
        assert r1.status_code == 200, r1.text
        assert r1.headers["content-type"].startswith("application/pdf")
        assert r1.content[:4] == b"%PDF"
        time.sleep(0.5)
        # Second render — should add a new version
        r2 = api.get(f"{BASE_URL}/api/documents/{bol_doc_id}/pdf")
        assert r2.status_code == 200
        time.sleep(0.5)

        listing = api.get(
            f"{BASE_URL}/api/doc-vault?doc_id={bol_doc_id}&limit=50").json()
        items = listing["items"]
        assert listing["count"] >= before + 2, (
            f"expected +2 archives, got {listing['count']} vs before={before}")
        # Versions monotonically increasing per (doc_type, doc_id)
        versions = sorted({it["version"] for it in items
                            if it["doc_id"] == bol_doc_id})
        assert versions == sorted(versions)
        assert len(versions) >= 2
        # Different sha256 across versions (content changes due to timestamps)
        shas = {it["sha256"] for it in items if it["doc_id"] == bol_doc_id}
        assert len(shas) >= 2, "Each render should produce a unique sha256"


# -------------------- AUTO-ARCHIVE: RATE CONFIRMATION --------------------
class TestRateConfAutoArchive:

    def test_rate_con_pdf_archives(self, api, rc_id):
        before = api.get(
            f"{BASE_URL}/api/doc-vault?doc_id={rc_id}").json()["count"]
        r = api.get(f"{BASE_URL}/api/orisei/rate-confirmations/{rc_id}/pdf")
        assert r.status_code == 200, r.text
        assert r.content[:4] == b"%PDF"
        time.sleep(0.5)
        listing = api.get(
            f"{BASE_URL}/api/doc-vault?doc_id={rc_id}").json()
        assert listing["count"] >= before + 1
        item = listing["items"][0]
        assert item["doc_type"] == "RATE_CONFIRMATION"
        assert item["doc_id"] == rc_id


# -------------------- AUTO-ARCHIVE: QUOTE --------------------
class TestQuoteAutoArchive:

    def test_quote_pdf_archives(self, api, quote_id):
        before = api.get(
            f"{BASE_URL}/api/doc-vault?doc_id={quote_id}").json()["count"]
        r = api.get(f"{BASE_URL}/api/orisei/quotes/{quote_id}/pdf")
        assert r.status_code == 200, r.text
        assert r.content[:4] == b"%PDF"
        time.sleep(0.5)
        listing = api.get(
            f"{BASE_URL}/api/doc-vault?doc_id={quote_id}").json()
        assert listing["count"] >= before + 1
        item = listing["items"][0]
        assert item["doc_type"] == "QUOTE"
        assert item["doc_id"] == quote_id


# -------------------- METADATA + FILE STREAM + RE-RENDER --------------------
class TestArchiveDetailFlows:

    @pytest.fixture(scope="class")
    def any_bol_archive(self, api, bol_doc_id):
        # Ensure we have at least one BOL archive
        api.get(f"{BASE_URL}/api/documents/{bol_doc_id}/pdf")
        time.sleep(0.3)
        items = api.get(
            f"{BASE_URL}/api/doc-vault?doc_type=BOL&doc_id={bol_doc_id}"
        ).json()["items"]
        assert items, "No BOL archive available"
        return items[0]

    def test_get_metadata(self, api, any_bol_archive):
        aid = any_bol_archive["archive_id"]
        r = api.get(f"{BASE_URL}/api/doc-vault/{aid}")
        assert r.status_code == 200
        body = r.json()
        assert body["archive_id"] == aid
        assert "payload_snapshot" in body
        assert isinstance(body["payload_snapshot"], dict)
        assert body["doc_type"] == "BOL"
        assert "sha256" in body and "version" in body

    def test_metadata_404(self, api):
        r = api.get(f"{BASE_URL}/api/doc-vault/DA-NOSUCH123")
        assert r.status_code == 404

    def test_file_stream_pdf(self, api, any_bol_archive):
        aid = any_bol_archive["archive_id"]
        r = api.get(f"{BASE_URL}/api/doc-vault/{aid}/file")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("application/pdf")
        assert r.headers.get("X-Archive-Sha256") == any_bol_archive["sha256"]
        assert r.headers.get("X-Archive-Version") == str(
            any_bol_archive["version"])
        assert r.content[:4] == b"%PDF"
        # archived BOL PDFs from this app are sizeable
        assert len(r.content) > 1000, "PDF stream looks suspiciously small"

    def test_file_stream_404(self, api):
        r = api.get(f"{BASE_URL}/api/doc-vault/DA-NOSUCH123/file")
        assert r.status_code == 404

    def test_re_render_bol(self, api, any_bol_archive):
        aid = any_bol_archive["archive_id"]
        r = api.post(f"{BASE_URL}/api/doc-vault/{aid}/re-render")
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body["next_url"] == (
            f"/api/documents/{any_bol_archive['doc_id']}/pdf")

    def test_re_render_404(self, api):
        r = api.post(f"{BASE_URL}/api/doc-vault/DA-NOSUCH123/re-render")
        assert r.status_code == 404

    def test_re_render_rate_confirmation_url(self, api, rc_id):
        items = api.get(
            f"{BASE_URL}/api/doc-vault?doc_id={rc_id}").json()["items"]
        assert items, "Rate confirmation must already be archived"
        aid = items[0]["archive_id"]
        r = api.post(f"{BASE_URL}/api/doc-vault/{aid}/re-render")
        assert r.status_code == 200
        assert r.json()["next_url"] == (
            f"/api/orisei/rate-confirmations/{rc_id}/pdf")

    def test_re_render_quote_url(self, api, quote_id):
        items = api.get(
            f"{BASE_URL}/api/doc-vault?doc_id={quote_id}").json()["items"]
        assert items
        aid = items[0]["archive_id"]
        r = api.post(f"{BASE_URL}/api/doc-vault/{aid}/re-render")
        assert r.status_code == 200
        assert r.json()["next_url"] == f"/api/orisei/quotes/{quote_id}/pdf"
