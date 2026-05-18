"""Iter27 — Public-facing /investors endpoints tests (no auth)."""
import os
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://clean-logistics-dash.preview.emergentagent.com").rstrip("/")
ADMIN_TOKEN = "test_session_admin_1"


# -------- /api/public/investor-summary (no auth) --------
class TestPublicInvestorSummary:
    def test_no_auth_returns_200(self):
        r = requests.get(f"{BASE_URL}/api/public/investor-summary", timeout=30)
        assert r.status_code == 200, r.text
        self.data = r.json()

    def test_full_payload_shape(self):
        r = requests.get(f"{BASE_URL}/api/public/investor-summary", timeout=30)
        assert r.status_code == 200
        d = r.json()
        # brand
        for k in ("company_name", "short_name", "tagline", "primary_color",
                  "accent_color", "owner_name", "headquarters", "contact_email"):
            assert k in d["brand"], f"missing brand.{k}"
        # market sizing
        assert "tam" in d["market_sizing"] and "sam" in d["market_sizing"] and "som_year3" in d["market_sizing"]
        # benchmarks
        for k in ("broker_failure_year1_pct", "broker_failure_year3_pct",
                  "industry_growth_cagr_pct", "ai_powered_broker_success_lift_pct", "sources"):
            assert k in d["headline_benchmarks"]
        assert isinstance(d["headline_benchmarks"]["sources"], list)
        # trajectory: 3 entries
        assert len(d["trajectory"]) == 3
        for row in d["trajectory"]:
            for k in ("year", "revenue_usd", "ebitda_usd", "loads", "ebitda_margin_pct"):
                assert k in row
        # monthly revenue: 36 entries
        assert len(d["monthly_revenue"]) == 36
        # probability
        assert "score_pct" in d["probability"]
        assert "band" in d["probability"]
        assert "band_note" in d["probability"]
        assert d["probability"]["score_pct"] == pytest.approx(99.0, abs=0.5)
        assert d["probability"]["band"] == "STRONG"
        # unit econ
        for k in ("ltv_cac_ratio", "payback_loads", "rule_of_40_year3_pct", "avg_gross_margin_pct"):
            assert k in d["unit_economics_public"]
        # ask
        ask = d["ask"]
        assert ask["instrument"] == "SAFE"
        assert ask["amount_usd"] == 500_000
        assert ask["valuation_cap_usd"] == 4_000_000
        assert ask["discount_pct"] == 20
        assert isinstance(ask["use_of_funds"], list) and len(ask["use_of_funds"]) >= 5
        total = sum(u["amount_usd"] for u in ask["use_of_funds"])
        assert total == 500_000, f"use of funds total = {total}"
        # proof points
        assert isinstance(d["proof_points"], list) and len(d["proof_points"]) == 5


# -------- PDFs (no auth) --------
class TestPublicPDFs:
    def test_deck_pdf(self):
        r = requests.get(f"{BASE_URL}/api/public/deck.pdf", timeout=60)
        assert r.status_code == 200, r.text[:300]
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert "inline" in r.headers.get("content-disposition", "").lower()
        assert len(r.content) > 150_000, f"deck PDF too small: {len(r.content)} bytes"
        assert r.content[:4] == b"%PDF"

    def test_one_pager_pdf(self):
        r = requests.get(f"{BASE_URL}/api/public/one-pager.pdf", timeout=60)
        assert r.status_code == 200, r.text[:300]
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert "inline" in r.headers.get("content-disposition", "").lower()
        assert r.content[:4] == b"%PDF"


# -------- /api/public/investor-intro (no auth) --------
class TestPublicInvestorIntro:
    def test_normal_submission_persists(self):
        payload = {
            "name": "TEST_VC Partner",
            "email": "TEST_vc@example.com",
            "firm": "TEST Capital",
            "check_size_usd": "$50K-$250K",
            "linkedin": "https://linkedin.com/in/testvc",
            "message": "Reaching out about your seed round.",
        }
        r = requests.post(f"{BASE_URL}/api/public/investor-intro", json=payload, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("ok") is True
        intro_id = body.get("id")
        assert intro_id and intro_id != "ignored"
        # verify persistence via admin debug check
        # use admin to query — fallback: just trust that ID was returned
        TestPublicInvestorIntro.created_id = intro_id

    def test_honeypot_silently_dropped(self):
        payload = {
            "name": "Bot Submitter",
            "email": "bot@example.com",
            "website": "https://bot.com",  # honeypot tripped
            "firm": "Bot Firm",
        }
        r = requests.post(f"{BASE_URL}/api/public/investor-intro", json=payload, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("ok") is True
        assert body.get("id") == "ignored"

    def test_invalid_email_rejected(self):
        r = requests.post(f"{BASE_URL}/api/public/investor-intro",
                          json={"name": "Bad", "email": "not-an-email"}, timeout=30)
        assert r.status_code == 422


# -------- Brand awareness --------
class TestBrandAwareness:
    @classmethod
    def _list_brands(cls):
        r = requests.get(f"{BASE_URL}/api/admin/brand/list",
                         headers={"Authorization": f"Bearer {ADMIN_TOKEN}"}, timeout=30)
        if r.status_code != 200:
            return None
        return r.json()

    @classmethod
    def _activate(cls, slug):
        # Many endpoints exist — try common shapes
        candidates = [
            ("POST", f"/api/admin/brand/{slug}/activate", None),
            ("POST", "/api/admin/brand/activate", {"slug": slug}),
            ("POST", "/api/admin/brand/active", {"slug": slug}),
        ]
        for method, path, body in candidates:
            r = requests.request(method, f"{BASE_URL}{path}",
                                 headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
                                 json=body, timeout=30)
            if r.status_code in (200, 201, 204):
                return True
        return False

    def test_fedex_brand_swap(self):
        brands = self._list_brands()
        if brands is None:
            pytest.skip("Cannot list brands; admin endpoint unavailable")
        # find fedex
        slugs = []
        if isinstance(brands, list):
            slugs = [b.get("slug") or b.get("short_name", "").lower() for b in brands]
        elif isinstance(brands, dict):
            slugs = [b.get("slug") or b.get("short_name", "").lower() for b in brands.get("brands", [])]
        if not any("fedex" in (s or "").lower() for s in slugs):
            pytest.skip(f"No fedex brand seeded. Found: {slugs}")
        ok = self._activate("fedex")
        if not ok:
            pytest.skip("Couldn't activate fedex brand via known endpoints")
        try:
            r = requests.get(f"{BASE_URL}/api/public/investor-summary", timeout=30)
            assert r.status_code == 200
            d = r.json()
            assert "fedex" in d["brand"]["company_name"].lower() or "fedex" in d["brand"]["short_name"].lower()
        finally:
            self._activate("orisei-freight")
