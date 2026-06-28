"""Iter 46 — NMFC expansion, Tennant removal, branded non-BOL PDFs, post-book routing.

Tests:
1. /api/nmfc/codes returns >=80 codes spanning many categories (Food, Electronics,
   Pharma, Furniture, Building, Machinery, Hazmat, Automotive, FAK), includes
   nmfc=73130 and nmfc=FAK-85 — proving the catalog is generic, not Tennant.
2. /api/documents/{id}/pdf for non-BOL docs (PACKING_SLIP, COMMERCIAL_INVOICE,
   WEIGHT_CERT, COO) returns a sizable branded PDF (>20KB heraldic engine).
3. BOL PDF still works (no regression on /shipments/{id}/generate-bol path).
4. /api/brokerage/loads/book returns 200 with booked_id starting BK-.
"""

import os
import time
import uuid
import requests
import pytest

def _resolve_base_url() -> str:
    url = os.environ.get("REACT_APP_BACKEND_URL")
    if url:
        return url.rstrip("/")
    # Read from frontend/.env so pytest can run from CLI without env exported
    env_path = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", ".env")
    with open(env_path) as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip().strip('"').rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL not set")


BASE_URL = _resolve_base_url()
AUTH = {"Authorization": "Bearer test_session_admin_1"}


# -------------------- 1. NMFC catalog --------------------
class TestNmfcCatalog:
    def test_nmfc_catalog_is_generic_and_broad(self):
        r = requests.get(f"{BASE_URL}/api/nmfc/codes", headers=AUTH, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        codes = data.get("codes", [])
        assert isinstance(codes, list)
        assert len(codes) >= 80, f"only {len(codes)} codes"

        cats = {c.get("category", "") for c in codes}
        # Must span multiple verticals, not just Tennant scrubber/battery
        required_substrings = [
            "Food", "Electronics", "Pharmaceuticals", "Furniture",
            "Building", "Machinery", "Hazmat", "Automotive", "FAK",
        ]
        for sub in required_substrings:
            assert any(sub in c for c in cats), f"missing category like '{sub}' in {cats}"

        nmfcs = {c.get("nmfc") for c in codes}
        assert "73130" in nmfcs, "expected canned-foodstuffs NMFC 73130"
        assert "FAK-85" in nmfcs, "expected FAK-85 catch-all"

        # No Tennant-branded product entries
        bad = [c for c in codes if "tennant" in (c.get("description") or "").lower()
               or "t16amr" in (c.get("description") or "").lower()]
        assert not bad, f"found tennant-branded NMFC entries: {bad}"

    def test_nmfc_response_includes_freight_classes(self):
        r = requests.get(f"{BASE_URL}/api/nmfc/codes", headers=AUTH, timeout=10)
        data = r.json()
        assert "freight_classes" in data
        assert isinstance(data["freight_classes"], list)
        assert len(data["freight_classes"]) > 0


# -------------------- 2 + 3. Branded PDF generation --------------------
@pytest.fixture(scope="module")
def shipment_id():
    """Create a real shipment for downstream BOL + document tests."""
    payload = {
        "reference": f"TEST-SHIP-{uuid.uuid4().hex[:6].upper()}",
        "mode": "LTL",
        "carrier": "TEST_Carrier",
        "origin_city": "Minneapolis, MN",
        "destination_city": "Dallas, TX",
        "destination_lat": 32.7767,
        "destination_lng": -96.7970,
        "pickup_date": "2026-02-01",
        "weight_lbs": 12500,
        "pieces": 10,
        "commodity": "Foodstuffs, canned",
        "value_usd": 5000,
    }
    r = requests.post(f"{BASE_URL}/api/shipments", headers={**AUTH,
                      "Content-Type": "application/json"}, json=payload, timeout=15)
    assert r.status_code in (200, 201), r.text
    sid = r.json().get("shipment_id") or r.json().get("id")
    assert sid, f"no shipment id in {r.json()}"
    return sid


class TestBolPdfNoRegression:
    def test_generate_bol_and_fetch_pdf(self, shipment_id):
        r = requests.post(
            f"{BASE_URL}/api/shipments/{shipment_id}/generate-bol",
            headers={**AUTH, "Content-Type": "application/json"},
            json={"shipper": "Orisei Freight Solutions"},
            timeout=20,
        )
        assert r.status_code in (200, 201), r.text
        doc = r.json()
        doc_id = doc.get("document_id")
        assert doc_id, f"no document id in {doc}"

        pdf = requests.get(f"{BASE_URL}/api/documents/{doc_id}/pdf",
                           headers=AUTH, timeout=30)
        assert pdf.status_code == 200, pdf.text[:300]
        assert pdf.headers.get("content-type", "").startswith("application/pdf")
        size = len(pdf.content)
        assert size > 20_000, f"BOL pdf only {size} bytes"
        with open(f"/tmp/iter46_bol_{doc_id}.pdf", "wb") as f:
            f.write(pdf.content)


class TestBrandedNonBolDocs:
    """Each non-BOL doc must render via build_branded_markdown_pdf (heraldic)."""

    @pytest.mark.parametrize("doc_type", [
        "PACKING_SLIP", "COMMERCIAL_INVOICE", "WEIGHT_CERT", "COO",
    ])
    def test_doc_type_renders_branded_pdf(self, shipment_id, doc_type):
        # Create the doc via /api/documents
        payload = {
            "type": doc_type,
            "shipment_ref": shipment_id,
            "data": {
                "shipper": "Orisei Freight Solutions",
                "consignee": "TEST_Consignee Co.",
                "carrier": "TEST_Carrier",
                "origin": "Minneapolis, MN",
                "destination": "Dallas, TX",
                "commodity": "Foodstuffs, canned",
                "pieces": 10,
                "weight": 12500,
                "items": [
                    {"description": "Foodstuffs, canned", "qty": 10,
                     "weight_lbs": 1250, "value_usd": 5000},
                ],
                "total_usd": 5000,
                "total_weight_lbs": 12500,
            },
        }
        r = requests.post(f"{BASE_URL}/api/documents",
                          headers={**AUTH, "Content-Type": "application/json"},
                          json=payload, timeout=15)
        assert r.status_code in (200, 201), f"{doc_type}: {r.status_code} {r.text[:300]}"
        doc = r.json()
        doc_id = doc.get("document_id")
        assert doc_id, f"no id for {doc_type}: {doc}"

        # Fetch PDF — must go through branded engine
        pdf = requests.get(f"{BASE_URL}/api/documents/{doc_id}/pdf",
                           headers=AUTH, timeout=30)
        assert pdf.status_code == 200, f"{doc_type}: {pdf.status_code} {pdf.text[:300]}"
        ctype = pdf.headers.get("content-type", "")
        assert ctype.startswith("application/pdf"), f"{doc_type}: ctype={ctype}"
        size = len(pdf.content)
        # Branded engine output is typically >100KB due to embedded fonts/borders;
        # accept >=50KB as a safe floor that still excludes the plain `_build_pdf`
        # 4-8KB output.
        assert size > 50_000, f"{doc_type} pdf only {size} bytes — likely not branded"
        out = f"/tmp/iter46_{doc_type}_{doc_id}.pdf"
        with open(out, "wb") as f:
            f.write(pdf.content)
        # Sanity: PDF magic
        assert pdf.content[:4] == b"%PDF", f"{doc_type} not a PDF"


# -------------------- 4. brokerage loads book --------------------
class TestBrokerageBookLoad:
    def test_book_load_returns_booked_id(self):
        # Pull a real load_id off the board first
        boards = requests.get(f"{BASE_URL}/api/brokerage/boards",
                              headers=AUTH, timeout=10)
        assert boards.status_code == 200, boards.text
        board_id = boards.json()["boards"][0]["id"]

        loads = requests.get(f"{BASE_URL}/api/brokerage/boards/{board_id}/loads",
                             headers=AUTH, timeout=15)
        assert loads.status_code == 200, loads.text
        load_id = loads.json()["loads"][0]["load_id"]

        r = requests.post(
            f"{BASE_URL}/api/brokerage/loads/book",
            headers={**AUTH, "Content-Type": "application/json"},
            json={
                "load_id": load_id,
                "board_id": board_id,
                "carrier_name": "TEST_XPO Logistics",
                "carrier_mc": "MC-TEST-001",
                "notes": "iter46 routing test",
            },
            timeout=15,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "booked_id" in data
        assert data["booked_id"].startswith("BK-"), data["booked_id"]
        assert data["status"] == "booked"
