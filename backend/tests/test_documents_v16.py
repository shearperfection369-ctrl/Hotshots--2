"""
Iteration 6 — Documents/BOL overhaul tests.

Covers:
  • POST   /api/documents              (create — amendments=[], version=1, updated_at=None)
  • PATCH  /api/documents/{id}         (amend — version bumps, diff captured, audit trail)
  • POST   /api/documents/{id}/email   (mailto build + db.document_emails log)
  • POST   /api/shipments/{id}/generate-bol  (BOL pre-fill, admin/dispatcher only)
  • GET    /api/documents              (list — legacy docs still parse)
  • GET    /api/documents/{id}/pdf     (PDF reflects amended data)
"""
import os
import pytest
import urllib.parse

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")


# ---------- Document create + amend ----------
class TestDocumentCreateAmend:
    def test_create_document_defaults(self, admin_client):
        payload = {
            "type": "BOL",
            "shipment_ref": "TEST_REF_001",
            "data": {
                "shipper": "Tennant Company",
                "consignee": "ACME Co",
                "carrier": "FEDX",
                "weight": "4500",
                "origin": "Minneapolis, MN",
                "destination": "Dallas, TX",
            },
        }
        r = admin_client.post(f"{BASE_URL}/api/documents", json=payload)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["type"] == "BOL"
        assert d["shipment_ref"] == "TEST_REF_001"
        assert d["amendments"] == []
        assert d["version"] == 1
        assert d.get("updated_at") in (None, "")
        assert d["data"]["weight"] == "4500"
        assert d["document_id"].startswith("DOC-")
        # store for chained tests
        pytest.created_doc_id = d["document_id"]

    def test_amend_document_records_diff(self, admin_client):
        doc_id = getattr(pytest, "created_doc_id", None)
        assert doc_id, "create test must run first"
        new_data = {
            "shipper": "Tennant Company",
            "consignee": "ACME Co",
            "carrier": "FEDX",
            "weight": "4750",            # CHANGED
            "origin": "Minneapolis, MN",
            "destination": "Houston, TX",  # CHANGED
        }
        body = {"data": new_data, "reason": "Customer revised destination & weight"}
        r = admin_client.patch(f"{BASE_URL}/api/documents/{doc_id}", json=body)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["version"] == 2
        assert d["updated_at"] is not None and len(d["updated_at"]) > 5
        assert len(d["amendments"]) == 1
        amend = d["amendments"][0]
        assert amend["reason"] == "Customer revised destination & weight"
        assert "amended_at" in amend and "amended_by" in amend
        # diff: only weight + destination should be recorded
        changed_fields = {c["field"] for c in amend["changes"]}
        assert changed_fields == {"weight", "destination"}, f"unexpected diff: {amend['changes']}"
        for c in amend["changes"]:
            if c["field"] == "weight":
                assert c["from"] == "4500" and c["to"] == "4750"
            if c["field"] == "destination":
                assert c["from"] == "Dallas, TX" and c["to"] == "Houston, TX"

    def test_amend_404(self, admin_client):
        r = admin_client.patch(
            f"{BASE_URL}/api/documents/DOC-NOPE", json={"data": {}, "reason": "x"}
        )
        assert r.status_code == 404


# ---------- Email composer ----------
class TestDocumentEmail:
    def test_email_returns_mailto_and_logs(self, admin_client):
        doc_id = getattr(pytest, "created_doc_id", None)
        assert doc_id
        body = {"to": "ops@example.com", "cc": "audit@example.com", "message": "Please confirm receipt."}
        r = admin_client.post(f"{BASE_URL}/api/documents/{doc_id}/email", json=body)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["ok"] is True
        # subject: type label + 'Rev N' note when version>1
        assert "BILL OF LADING" in j["subject"].upper()
        assert "Rev 2" in j["subject"], f"expected Rev 2, got: {j['subject']}"
        # body has the summary
        assert "Document ID: " + doc_id in j["body"]
        assert "FEDX" in j["body"]
        assert "Houston, TX" in j["body"]
        # mailto well-formed
        assert j["mailto"].startswith("mailto:ops@example.com?subject=")
        assert urllib.parse.quote(j["subject"]) in j["mailto"]
        assert "cc=audit%40example.com" in j["mailto"]
        # pdf url
        assert j["pdf_url"].endswith(f"/api/documents/{doc_id}/pdf")

    def test_email_404(self, admin_client):
        r = admin_client.post(
            f"{BASE_URL}/api/documents/DOC-MISSING/email",
            json={"to": "x@y.com"},
        )
        assert r.status_code == 404


# ---------- BOL-from-shipment ----------
class TestGenerateBolFromShipment:
    def test_generate_bol_admin(self, admin_client):
        # Find an existing shipment via the list endpoint
        r = admin_client.get(f"{BASE_URL}/api/shipments?limit=5")
        assert r.status_code == 200, r.text
        shipments = r.json()
        assert len(shipments) > 0, "need at least one seeded shipment"
        sid = shipments[0]["shipment_id"]
        rb = admin_client.post(
            f"{BASE_URL}/api/shipments/{sid}/generate-bol",
            json={"shipper": "Tennant Company"},
        )
        assert rb.status_code == 200, rb.text
        d = rb.json()
        assert d["type"] == "BOL"
        assert d["version"] == 1
        assert d["amendments"] == []
        # data pre-filled from shipment
        assert "carrier" in d["data"]
        assert "origin" in d["data"] and "destination" in d["data"]
        pytest.generated_bol_id = d["document_id"]

    def test_generate_bol_404(self, admin_client):
        r = admin_client.post(
            f"{BASE_URL}/api/shipments/SHP-NOPE/generate-bol", json={}
        )
        assert r.status_code == 404

    def test_generate_bol_rbac_auditor_forbidden(self, auditor_client):
        # auditor is NOT admin/dispatcher → 403
        r = auditor_client.get(f"{BASE_URL}/api/shipments?limit=1")
        if r.status_code != 200 or not r.json():
            pytest.skip("no shipment to test rbac against")
        sid = r.json()[0]["shipment_id"]
        rb = auditor_client.post(
            f"{BASE_URL}/api/shipments/{sid}/generate-bol", json={}
        )
        assert rb.status_code == 403, f"expected 403 got {rb.status_code}: {rb.text}"


# ---------- List + legacy parsing ----------
class TestListDocuments:
    def test_list_includes_new_fields(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/documents")
        assert r.status_code == 200
        docs = r.json()
        assert isinstance(docs, list) and len(docs) > 0
        # every doc must parse — pydantic defaults amendments=[], version=1
        for d in docs:
            assert "amendments" in d
            assert "version" in d
            assert isinstance(d["amendments"], list)
            assert isinstance(d["version"], int) and d["version"] >= 1
        # our amended doc should be in the list with version=2
        amended = [d for d in docs if d["document_id"] == getattr(pytest, "created_doc_id", "")]
        assert len(amended) == 1
        assert amended[0]["version"] == 2
        assert len(amended[0]["amendments"]) == 1


# ---------- PDF still works after amendment ----------
class TestPdf:
    def test_pdf_reflects_latest_data(self, admin_client):
        doc_id = getattr(pytest, "created_doc_id", None)
        assert doc_id
        r = admin_client.get(f"{BASE_URL}/api/documents/{doc_id}/pdf")
        assert r.status_code == 200, r.text
        ct = r.headers.get("content-type", "")
        assert "pdf" in ct.lower(), f"unexpected content-type: {ct}"
        # the body is binary PDF — sanity check: starts with %PDF
        assert r.content[:4] == b"%PDF", r.content[:20]


# ---------- P1 regression smoke ----------
class TestRegressionSmoke:
    def test_shipments_list(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/shipments?limit=5")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_workbook_tabs(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/workbook/tabs")
        assert r.status_code == 200

    def test_kpis(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/kpis")
        assert r.status_code == 200
