"""Iter 45 — Autocomplete directory + branded PDF tests.

Covers:
* GET /api/autocomplete/carriers/directory (rich items shape + curated names + q filter)
* GET /api/autocomplete/customers/directory (rich items shape)
* GET /api/autocomplete/carriers (simple still works)
* Branded markdown PDF: create quote → fetch /pdf → size > 50KB
"""
import os
import time
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN = "test_session_admin_1"
H = {"Authorization": f"Bearer {ADMIN}", "Content-Type": "application/json"}


# -------- Autocomplete carriers directory --------
class TestCarriersDirectory:
    def test_returns_200_with_items_shape(self):
        r = requests.get(f"{BASE_URL}/api/autocomplete/carriers/directory", headers=H, timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "items" in data and isinstance(data["items"], list)
        assert len(data["items"]) > 0, "expected at least one carrier item"
        sample = data["items"][0]
        for f in ("name", "mc", "dot", "contact_email", "contact_phone", "use_count", "source"):
            assert f in sample, f"missing field {f} in item: {sample}"

    def test_includes_curated_carrier_names(self):
        r = requests.get(f"{BASE_URL}/api/autocomplete/carriers/directory?limit=200", headers=H, timeout=20)
        assert r.status_code == 200
        names = {(c.get("name") or "").lower() for c in r.json()["items"]}
        assert "xpo logistics" in names, names
        assert "schneider national" in names, names

    def test_filter_by_q_sch(self):
        r = requests.get(f"{BASE_URL}/api/autocomplete/carriers/directory?q=Sch", headers=H, timeout=20)
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) > 0
        assert all("sch" in (it.get("name") or "").lower() or "sch" in (it.get("mc") or "").lower() for it in items)


# -------- Autocomplete customers directory --------
class TestCustomersDirectory:
    def test_returns_200_with_items(self):
        r = requests.get(f"{BASE_URL}/api/autocomplete/customers/directory", headers=H, timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "items" in data and isinstance(data["items"], list)
        # may be empty if no customers yet; create one and re-check
        if len(data["items"]) == 0:
            pytest.skip("no customers seeded yet — sub-test for shape skipped")
        sample = data["items"][0]
        for f in ("customer_id", "name", "primary_contact_email", "payment_terms"):
            assert f in sample, f"missing field {f}"


# -------- Simple autocomplete still works --------
class TestSimpleCarriers:
    def test_simple_carriers(self):
        r = requests.get(f"{BASE_URL}/api/autocomplete/carriers", headers=H, timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("kind") == "carriers"
        assert isinstance(data.get("suggestions"), list)
        assert len(data["suggestions"]) > 0


# -------- Branded quote PDF --------
class TestBrandedQuotePDF:
    def test_quote_pdf_is_branded_and_sized(self):
        # Create a customer
        cust_payload = {
            "name": f"TEST_BrandCust_{int(time.time())}",
            "primary_contact_email": "ap@testbrand.com",
            "primary_contact_name": "AP Lead",
            "payment_terms": "Net 30",
            "billing_address": "100 Test Ave, Minneapolis MN",
        }
        rc = requests.post(f"{BASE_URL}/api/orisei/customers", headers=H, json=cust_payload, timeout=20)
        assert rc.status_code in (200, 201), f"cust create failed {rc.status_code}: {rc.text}"
        customer_id = rc.json().get("customer_id") or rc.json().get("id")
        assert customer_id

        # Create a quote
        quote_payload = {
            "customer_id": customer_id,
            "origin": "Minneapolis, MN",
            "destination": "Chicago, IL",
            "equipment": "Dry Van 53'",
            "commodity": "Paper products",
            "weight_lbs": 38000,
            "pickup_date": "2026-02-15",
            "delivery_date": "2026-02-16",
            "miles": 410,
            "rate_usd": 1850.00,
            "line_haul_usd": 1700.00,
            "fuel_surcharge_usd": 150.00,
        }
        rq = requests.post(f"{BASE_URL}/api/orisei/quotes", headers=H, json=quote_payload, timeout=30)
        assert rq.status_code in (200, 201), f"quote create failed {rq.status_code}: {rq.text}"
        qd = rq.json()
        qid = qd.get("quote_id") or qd.get("id")
        assert qid

        # Fetch PDF
        rp = requests.get(f"{BASE_URL}/api/orisei/quotes/{qid}/pdf", headers=H, timeout=60)
        assert rp.status_code == 200, f"pdf fetch failed {rp.status_code}: {rp.text[:300]}"
        body = rp.content
        # Save for inspection
        with open("/tmp/iter45_quote.pdf", "wb") as f:
            f.write(body)
        assert body[:4] == b"%PDF", "response is not a PDF"
        size = len(body)
        # Branded PDF (logo + tables + gold banner) should be much bigger than a plain text PDF
        assert size > 50_000, f"PDF size too small ({size} bytes); branded assets missing?"
