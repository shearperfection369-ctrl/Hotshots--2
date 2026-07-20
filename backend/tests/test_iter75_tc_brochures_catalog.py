"""Iter75 — Truck cleaning catalog expansion + full-color brochure PDFs + legacy docs still valid."""
import os
import re
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://clean-logistics-dash.preview.emergentagent.com").rstrip("/")
HEADERS = {"Authorization": "Bearer test_session_admin_1", "Content-Type": "application/json"}


# ---------- CATALOG ----------
class TestCatalog:
    def test_catalog_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/truck-cleaning/catalog", timeout=15)
        assert r.status_code in (401, 403)

    def test_catalog_shape(self):
        r = requests.get(f"{BASE_URL}/api/truck-cleaning/catalog", headers=HEADERS, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert "upsells" in data and "scents" in data
        upsells = data["upsells"]
        scents = data["scents"]
        assert isinstance(upsells, list) and isinstance(scents, list)
        assert len(upsells) >= 13, f"expected >=13 upsells, got {len(upsells)}"
        assert len(scents) == 8, f"expected 8 scents, got {len(scents)}"
        add_ons = [u for u in upsells if u["category"] == "add_on"]
        fresheners = [u for u in upsells if u["category"] == "freshener"]
        assert len(add_ons) == 9, f"expected 9 add_ons, got {len(add_ons)}"
        assert len(fresheners) == 4, f"expected 4 fresheners, got {len(fresheners)}"
        for u in upsells:
            assert set(u.keys()) >= {"id", "label", "price", "category", "desc"}
            assert u["category"] in ("add_on", "freshener", "bedding")
            assert isinstance(u["price"], (int, float))
        ids = {u["id"] for u in upsells}
        for required in ("engine_bay", "odor_bomb", "exterior_wash", "scent_single", "vent_diffuser"):
            assert required in ids, f"missing upsell id {required}"


# ---------- JOB PRICING with new upsells ----------
class TestJobPricingNewUpsells:
    def _seed_client(self):
        # Ensure clients exist and pick one
        r = requests.get(f"{BASE_URL}/api/truck-cleaning/clients", headers=HEADERS, timeout=15)
        assert r.status_code == 200
        clients = r.json()["clients"]
        assert clients, "seed clients missing"
        return clients[0]

    def test_job_pricing_new_upsells(self):
        client = self._seed_client()
        payload = {
            "client_id": client["client_id"],
            "date": "2026-01-15",
            "cabs": 1,
            "upsells": ["odor_bomb", "vent_diffuser", "scent_single", "totally_unknown_id"],
            "notes": "TEST_iter75",
        }
        r = requests.post(f"{BASE_URL}/api/truck-cleaning/jobs", headers=HEADERS, json=payload, timeout=15)
        assert r.status_code == 200, r.text
        job = r.json()["job"]
        # unknown id must be silently dropped
        assert "totally_unknown_id" not in job["upsells"]
        assert set(job["upsells"]) == {"odor_bomb", "vent_diffuser", "scent_single"}
        expected = round(1 * client["rate"] + 35 + 12 + 5, 2)
        assert job["price"] == expected, f"expected {expected}, got {job['price']}"


# ---------- BROCHURES ----------
class TestBrochures:
    def test_brochures_require_auth(self):
        r = requests.get(f"{BASE_URL}/api/truck-cleaning/brochures/services.pdf", timeout=30)
        assert r.status_code in (401, 403)

    def test_services_brochure_pdf(self):
        r = requests.get(f"{BASE_URL}/api/truck-cleaning/brochures/services.pdf", headers=HEADERS, timeout=45)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content.startswith(b"%PDF")
        assert len(r.content) > 3000

    def test_cleaning_guide_brochure_multipage(self):
        r = requests.get(f"{BASE_URL}/api/truck-cleaning/brochures/cleaning-guide.pdf", headers=HEADERS, timeout=45)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content.startswith(b"%PDF")
        # Count pages via /Type /Page markers (not /Pages)
        pages = len(re.findall(rb"/Type\s*/Page[^s]", r.content))
        assert pages >= 2, f"expected 2+ pages, got {pages}"

    def test_unknown_brochure_404(self):
        r = requests.get(f"{BASE_URL}/api/truck-cleaning/brochures/notreal.pdf", headers=HEADERS, timeout=15)
        assert r.status_code == 404


# ---------- LEGACY docs still work ----------
class TestLegacyDocs:
    def test_proposal_pdf(self):
        r = requests.get(f"{BASE_URL}/api/truck-cleaning/docs/proposal.pdf", headers=HEADERS, timeout=30)
        assert r.status_code == 200
        assert r.content.startswith(b"%PDF")

    def test_agreement_pdf(self):
        r = requests.get(f"{BASE_URL}/api/truck-cleaning/docs/agreement.pdf", headers=HEADERS, timeout=30)
        assert r.status_code == 200
        assert r.content.startswith(b"%PDF")

    def test_report_card_pdf(self):
        r = requests.get(f"{BASE_URL}/api/truck-cleaning/docs/report-card.pdf", headers=HEADERS, timeout=30)
        assert r.status_code == 200
        assert r.content.startswith(b"%PDF")

    def test_unknown_legacy_doc_404(self):
        r = requests.get(f"{BASE_URL}/api/truck-cleaning/docs/notreal.pdf", headers=HEADERS, timeout=15)
        assert r.status_code == 404
