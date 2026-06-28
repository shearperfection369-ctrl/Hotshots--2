"""Backend tests for iter48 — International export/import document suite."""
import io
import os
import pytest
import requests

def _load_url() -> str:
    u = os.environ.get("REACT_APP_BACKEND_URL")
    if not u:
        try:
            with open("/app/frontend/.env") as f:
                for line in f:
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        u = line.split("=", 1)[1].strip()
                        break
        except FileNotFoundError:
            pass
    if not u:
        raise RuntimeError("REACT_APP_BACKEND_URL not configured")
    return u.rstrip("/")

BASE_URL = _load_url()
INTL = f"{BASE_URL}/api/international"
AUTH = {"Authorization": "Bearer test_session_admin_1"}


@pytest.fixture(scope="module")
def booking_id():
    """Ensure at least one container booking exists; return its id."""
    r = requests.get(f"{INTL}/container-bookings", headers=AUTH, timeout=20)
    assert r.status_code == 200, r.text
    items = r.json().get("items") or []
    if items:
        return items[0]["booking_id"]
    # Create one
    payload = {
        "carrier_scac": "MAEU",
        "booking_number": "TEST-ITER48-001",
        "pol": "CNSHA",
        "pod": "USLAX",
        "container_size_type": "40HC",
        "container_count": 1,
        "commodity": "Fresh blueberries",
        "shipper_name": "TEST Orisei Exports",
        "consignee_name": "TEST Pacific Importers",
    }
    r = requests.post(f"{INTL}/container-bookings", json=payload,
                      headers=AUTH, timeout=20)
    assert r.status_code in (200, 201), r.text
    return r.json()["booking_id"]


# ---------- Reference endpoints ----------
class TestReference:
    def test_aes_help(self):
        r = requests.get(f"{INTL}/aes/help", headers=AUTH, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["filing_portal"] == "https://aesdirect.census.gov"
        keys = {f["key"] for f in d["fields"]}
        assert len(d["fields"]) == 20
        for required in ["usppi", "ultimate_consignee", "schedule_b_or_hts",
                         "value_usd", "port_of_export", "mode_of_transport",
                         "container_indicator", "ein"]:
            assert required in keys, f"missing {required}"

    def test_phyto_help(self):
        r = requests.get(f"{INTL}/phyto/help", headers=AUTH, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["filing_portal"] == "https://pcit.aphis.usda.gov"
        assert len(d["fields"]) == 12

    def test_document_types(self):
        r = requests.get(f"{INTL}/document-types", headers=AUTH, timeout=15)
        assert r.status_code == 200
        d = r.json()
        codes = {x["code"] for x in d["items"]}
        assert len(d["items"]) == 16
        for c in ["AES_WORKSHEET", "COMMERCIAL_INVOICE", "PACKING_LIST",
                  "CERTIFICATE_OF_ORIGIN", "PHYTOSANITARY_PREP",
                  "LETTER_OF_CREDIT", "ISF_10", "CBP_7501_PREP",
                  "BROKER_COVER_LETTER"]:
            assert c in codes


# ---------- PDF generators ----------
PDF_SLUGS = [
    "aes-worksheet", "commercial-invoice", "packing-list",
    "certificate-of-origin", "phyto-application", "letter-of-credit",
    "isf-10", "cbp-7501-prep", "broker-cover-letter", "sed",
]


class TestPdfGenerators:
    @pytest.mark.parametrize("slug", PDF_SLUGS)
    def test_pdf(self, booking_id, slug):
        r = requests.get(
            f"{INTL}/container-bookings/{booking_id}/pdf/{slug}",
            headers=AUTH, timeout=30)
        assert r.status_code == 200, f"{slug} -> {r.status_code} {r.text[:200]}"
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert len(r.content) > 100_000, f"{slug} pdf size {len(r.content)}"

    def test_unknown_slug(self, booking_id):
        r = requests.get(
            f"{INTL}/container-bookings/{booking_id}/pdf/unknown-slug",
            headers=AUTH, timeout=15)
        assert r.status_code == 400
        assert "No internal PDF generator" in r.text


# ---------- AES filing capture ----------
class TestAesFiling:
    def test_aes_filing_capture_and_itn_receipt(self, booking_id):
        itn = "X20260628000999"
        r = requests.post(
            f"{INTL}/container-bookings/{booking_id}/aes/filing",
            json={"itn": itn, "port_of_export": "2704",
                  "mode_of_transport": "10", "license_code": "C33"},
            headers=AUTH, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["ok"] is True
        assert d["aes_filing"]["itn"] == itn

        # verify ITN_RECEIPT doc was auto-added
        r2 = requests.get(
            f"{INTL}/container-bookings/{booking_id}/docs",
            headers=AUTH, timeout=15)
        assert r2.status_code == 200
        items = r2.json()["items"]
        match = [x for x in items if x.get("doc_type") == "ITN_RECEIPT"
                 and x.get("reference_number") == itn]
        assert match, f"no ITN_RECEIPT for {itn}: {items}"
        assert match[-1]["status"] == "FILED"

    def test_aes_filing_invalid_itn(self, booking_id):
        r = requests.post(
            f"{INTL}/container-bookings/{booking_id}/aes/filing",
            json={"itn": "X123"},  # too short
            headers=AUTH, timeout=15)
        assert r.status_code == 422


# ---------- Doc tracker CRUD ----------
class TestDocTracker:
    def test_doc_lifecycle(self, booking_id):
        # CREATE
        payload = {
            "doc_type": "LETTER_OF_CREDIT",
            "status": "DRAFT",
            "source": "INTERNAL_GEN",
            "reference_number": "LC-TEST-001",
            "counterparty": "HSBC HK",
            "filed_with_agency": "HSBC issuing bank",
        }
        r = requests.post(
            f"{INTL}/container-bookings/{booking_id}/docs",
            json=payload, headers=AUTH, timeout=15)
        assert r.status_code in (200, 201), r.text
        doc = r.json()
        assert doc["doc_id"].startswith("DOC-")
        doc_id = doc["doc_id"]

        # LIST
        r = requests.get(f"{INTL}/container-bookings/{booking_id}/docs",
                         headers=AUTH, timeout=15)
        assert r.status_code == 200
        ids = [x["doc_id"] for x in r.json()["items"]]
        assert doc_id in ids

        # UPDATE status -> READY
        r = requests.put(
            f"{INTL}/container-bookings/{booking_id}/docs/{doc_id}/status",
            json={"status": "READY"}, headers=AUTH, timeout=15)
        assert r.status_code == 200
        r = requests.get(f"{INTL}/container-bookings/{booking_id}/docs",
                         headers=AUTH, timeout=15)
        match = next(x for x in r.json()["items"] if x["doc_id"] == doc_id)
        assert match["status"] == "READY"

        # DELETE
        r = requests.delete(
            f"{INTL}/container-bookings/{booking_id}/docs/{doc_id}",
            headers=AUTH, timeout=15)
        assert r.status_code == 200
        r = requests.get(f"{INTL}/container-bookings/{booking_id}/docs",
                         headers=AUTH, timeout=15)
        ids = [x["doc_id"] for x in r.json()["items"]]
        assert doc_id not in ids

    def test_doc_upload_and_download(self, booking_id):
        # tiny PDF bytes
        pdf_bytes = b"%PDF-1.4\n%TEST_ITER48\n%%EOF"
        files = {"file": ("test_phyto.pdf", pdf_bytes, "application/pdf")}
        data = {"doc_type": "PHYTOSANITARY_CERT", "status": "RECEIVED",
                "reference_number": "USDA-CERT-2026-001"}
        r = requests.post(
            f"{INTL}/container-bookings/{booking_id}/docs/upload",
            files=files, data=data, headers=AUTH, timeout=30)
        assert r.status_code in (200, 201), r.text
        doc = r.json()
        assert doc["file_id"] is not None
        assert doc["source"] == "EXTERNAL_UPLOAD"
        assert doc["status"] == "RECEIVED"
        doc_id = doc["doc_id"]

        # download
        r = requests.get(
            f"{INTL}/container-bookings/{booking_id}/docs/{doc_id}/file",
            headers=AUTH, timeout=15)
        assert r.status_code == 200
        assert r.content == pdf_bytes

        # cleanup
        requests.delete(
            f"{INTL}/container-bookings/{booking_id}/docs/{doc_id}",
            headers=AUTH, timeout=15)
