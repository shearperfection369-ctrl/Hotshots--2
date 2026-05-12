"""Iteration 15 — Massive feature batch (14 new features).

Covers:
  - GET /api/news (38+, body/published_at/time/minutes_ago, shuffles)
  - GET /api/traffic (25, severity/highway/lanes_closed/agency/source_url/eta_clear_min, ?severity=high)
  - GET /api/weather/alerts (4, alert_id/type/severity/headline/body/issued_at/expires_at)
  - GET /api/integrations/powerbi/config (6 reports, embed_url+view_url) + PUT admin-only
  - GET /api/integrations/sharepoint/config (5 sites + 8 recent_files)
  - GET /api/carriers/tracking-urls (35+) + /api/carriers/tracking-url (case-insens. + "XPO · XPOL")
  - GET /api/sap/link-config + /api/sap/deep-link?kind=invoice -> BillingDocument-display
  - GET /api/search/global?q=TN (mixed types) + /api/s4/search (deterministic per query)
  - GET /api/s4/invoices (50 mocked, vendor/amount_usd/status/s4_url)
  - GET/PUT /api/admin/settings (PUT admin-only)
  - GET /api/specialty-carriers (4 carriers w/ contact/specialty/modes/lanes/color/logo_initials/ytd_loads/on_time_pct/claim_rate_pct/since)
  - POST /api/machines (200; 409 on dup model)
  - GET /api/wellness/nudges (15 items w/ id/category/title/message/icon)
  - GET /api/workbook/truckload-bookings columns include up_charges_usd, up_charges_reason (with 'Detention'), notes (textarea); carrier still combo w/ 13+ options
"""

import subprocess
import requests


# ---------- /api/news ----------
class TestNews:
    def test_news_shape_and_volume(self, api_client, base_url):
        r = api_client.get(f"{base_url}/api/news")
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list) and len(data) >= 38, f"expected >=38, got {len(data)}"
        sample = data[0]
        for k in ("title", "body", "published_at", "time", "minutes_ago"):
            assert k in sample, f"news item missing '{k}': {list(sample)}"
        assert isinstance(sample["minutes_ago"], int)

    def test_news_minutes_ago_shuffles(self, api_client, base_url):
        # The live-feel shuffle changes minutes_ago between calls
        signatures = set()
        for _ in range(4):
            d = api_client.get(f"{base_url}/api/news").json()
            sig = tuple(item["minutes_ago"] for item in d[:6])
            signatures.add(sig)
        assert len(signatures) >= 2, f"minutes_ago appears static across 4 calls: {signatures}"


# ---------- /api/traffic ----------
class TestTraffic:
    def test_traffic_volume_and_fields(self, api_client, base_url):
        r = api_client.get(f"{base_url}/api/traffic")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list) and len(data) == 25, f"expected 25, got {len(data)}"
        s = data[0]
        for k in ("severity", "highway", "lanes_closed", "agency", "source_url", "eta_clear_min"):
            assert k in s, f"traffic item missing '{k}'"

    def test_traffic_severity_filter(self, api_client, base_url):
        all_ = api_client.get(f"{base_url}/api/traffic").json()
        high = api_client.get(f"{base_url}/api/traffic?severity=high").json()
        assert len(high) < len(all_)
        assert all(item["severity"] == "high" for item in high)


# ---------- /api/weather/alerts ----------
class TestWeatherAlerts:
    def test_alerts_shape(self, api_client, base_url):
        r = api_client.get(f"{base_url}/api/weather/alerts")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list) and len(data) == 4
        a = data[0]
        for k in ("alert_id", "type", "severity", "headline", "body", "issued_at", "expires_at"):
            assert k in a, f"alert missing '{k}'"


# ---------- /api/integrations/powerbi/config ----------
class TestPowerBIConfig:
    def test_get_powerbi_default_reports(self, api_client, base_url):
        r = api_client.get(f"{base_url}/api/integrations/powerbi/config")
        assert r.status_code == 200
        d = r.json()
        reports = d.get("reports", [])
        assert len(reports) == 6, f"expected 6 default reports, got {len(reports)}"
        for rep in reports:
            assert "embed_url" in rep and rep["embed_url"]
            assert "view_url" in rep and rep["view_url"]

    def test_put_powerbi_requires_admin(self, dispatcher_client, base_url):
        r = dispatcher_client.put(f"{base_url}/api/integrations/powerbi/config", json={"reports": []})
        assert r.status_code in (401, 403), r.status_code

    def test_put_powerbi_admin_ok(self, admin_client, base_url):
        # round-trip a minimal payload
        payload = {"reports": [{"id": "test", "name": "Test", "embed_url": "https://e", "view_url": "https://v"}], "tenant": "test"}
        r = admin_client.put(f"{base_url}/api/integrations/powerbi/config", json=payload)
        assert r.status_code == 200, r.text
        # restore defaults by clearing custom (best-effort)
        admin_client.put(f"{base_url}/api/integrations/powerbi/config", json={})


# ---------- /api/integrations/sharepoint/config ----------
class TestSharePointConfig:
    def test_sharepoint_sites_and_files(self, api_client, base_url):
        d = api_client.get(f"{base_url}/api/integrations/sharepoint/config").json()
        assert len(d.get("sites", [])) == 5
        assert len(d.get("recent_files", [])) == 8


# ---------- /api/carriers/tracking-urls + tracking-url ----------
class TestCarrierTracking:
    def test_tracking_urls_volume(self, api_client, base_url):
        d = api_client.get(f"{base_url}/api/carriers/tracking-urls").json()
        carriers = d["carriers"]
        # Backend may return list or dict-of-name->cfg
        n = len(carriers) if not isinstance(carriers, dict) else len(carriers)
        assert n >= 35, f"expected >=35 carriers, got {n}"

    def test_tracking_url_xpo(self, api_client, base_url):
        r = api_client.get(f"{base_url}/api/carriers/tracking-url", params={"carrier": "XPO", "tracking": "ABC"})
        assert r.status_code == 200
        d = r.json()
        assert "xpo.com" in d["url"]
        assert "ABC" in d["url"]

    def test_tracking_url_case_insensitive(self, api_client, base_url):
        d = api_client.get(f"{base_url}/api/carriers/tracking-url", params={"carrier": "xpo", "tracking": "12345"}).json()
        assert "xpo.com" in d["url"]

    def test_tracking_url_dropdown_label_split(self, api_client, base_url):
        # "XPO · XPOL" dropdown label - should split on "·" and resolve XPO
        d = api_client.get(f"{base_url}/api/carriers/tracking-url", params={"carrier": "XPO · XPOL", "tracking": "12345"}).json()
        assert "xpo.com" in d["url"]
        assert "12345" in d["url"]


# ---------- /api/sap/link-config + deep-link ----------
class TestSAPLinks:
    def test_link_config(self, api_client, base_url):
        d = api_client.get(f"{base_url}/api/sap/link-config").json()
        for k in ("base", "patterns", "kinds"):
            assert k in d, f"missing '{k}'"

    def test_deep_link_invoice(self, api_client, base_url):
        d = api_client.get(f"{base_url}/api/sap/deep-link", params={"kind": "invoice", "value": "INV-12345"}).json()
        assert "BillingDocument-display" in d["url"], d["url"]
        assert "INV-12345" in d["url"]


# ---------- /api/search/global + /api/s4/search ----------
class TestGlobalSearch:
    def test_global_search_tn(self, api_client, base_url):
        d = api_client.get(f"{base_url}/api/search/global", params={"q": "TN"}).json()
        # Response is {"results":[...]} per current impl
        results = d.get("results", d if isinstance(d, list) else [])
        assert len(results) > 0, "expected at least one global result for 'TN'"
        for item in results[:3]:
            for k in ("type", "title", "link"):
                assert k in item, f"global-search item missing '{k}': {list(item)}"

    def test_s4_search_deterministic(self, api_client, base_url):
        a = api_client.get(f"{base_url}/api/s4/search", params={"q": "PO123"}).json()
        b = api_client.get(f"{base_url}/api/s4/search", params={"q": "PO123"}).json()
        assert a == b, "s4/search not deterministic per query"
        results = a.get("results", a if isinstance(a, list) else [])
        assert len(results) > 0


# ---------- /api/s4/invoices ----------
class TestS4Invoices:
    def test_invoices_shape(self, api_client, base_url):
        d = api_client.get(f"{base_url}/api/s4/invoices").json()
        invs = d.get("invoices", [])
        assert len(invs) == 50, f"expected 50 mocked invoices, got {len(invs)}"
        sample = invs[0]
        for k in ("vendor", "amount_usd", "status", "s4_url"):
            assert k in sample, f"invoice missing '{k}'"
        # s4_url should contain SAP S4 base
        assert "s4" in sample["s4_url"].lower() or "sap" in sample["s4_url"].lower()


# ---------- /api/admin/settings ----------
class TestAdminSettings:
    def test_get_settings_any_auth(self, dispatcher_client, base_url):
        r = dispatcher_client.get(f"{base_url}/api/admin/settings")
        assert r.status_code == 200
        assert isinstance(r.json(), dict)

    def test_put_settings_requires_admin(self, dispatcher_client, base_url):
        r = dispatcher_client.put(f"{base_url}/api/admin/settings", json={"x": 1})
        assert r.status_code in (401, 403), r.status_code

    def test_put_settings_admin_round_trip(self, admin_client, base_url):
        payload = {"notifications": {"email": True}, "v": "iter15-test"}
        r = admin_client.put(f"{base_url}/api/admin/settings", json=payload)
        assert r.status_code == 200, r.text
        # GET should now contain our value
        g = admin_client.get(f"{base_url}/api/admin/settings").json()
        assert g.get("v") == "iter15-test"


# ---------- /api/specialty-carriers ----------
class TestSpecialtyCarriers:
    def test_specialty_carriers(self, api_client, base_url):
        d = api_client.get(f"{base_url}/api/specialty-carriers").json()
        carriers = d.get("carriers", [])
        ids = sorted([c["id"] for c in carriers])
        assert ids == sorted(["logix", "arcbest-panther", "fastfrate", "ryan-transportation"]), ids
        c = carriers[0]
        for k in ("contact", "specialty", "modes", "lanes", "color", "logo_initials",
                  "ytd_loads", "on_time_pct", "claim_rate_pct", "since"):
            assert k in c, f"specialty carrier missing '{k}'"


# ---------- POST /api/machines ----------
class TestMachinesCreate:
    MODEL = None

    def test_create_machine(self, admin_client, base_url):
        import uuid as _u
        TestMachinesCreate.MODEL = f"TEST_M_{_u.uuid4().hex[:8]}"
        payload = {"model": TestMachinesCreate.MODEL, "family": "TestFam", "category": "scrubber"}
        r = admin_client.post(f"{base_url}/api/machines", json=payload)
        assert r.status_code == 200, r.text
        assert r.json()["model"] == TestMachinesCreate.MODEL

    def test_create_duplicate_409(self, admin_client, base_url):
        assert TestMachinesCreate.MODEL is not None
        payload = {"model": TestMachinesCreate.MODEL, "family": "TestFam", "category": "scrubber"}
        r = admin_client.post(f"{base_url}/api/machines", json=payload)
        assert r.status_code == 409, r.text

    @classmethod
    def teardown_class(cls):
        if cls.MODEL:
            try:
                subprocess.run(
                    ["mongosh", "--quiet", "--eval",
                     f"use('test_database'); db.machines.deleteOne({{model:'{cls.MODEL}'}})"],
                    capture_output=True, check=False
                )
            except Exception:
                pass


# ---------- /api/wellness/nudges ----------
class TestWellnessNudges:
    def test_nudges(self, api_client, base_url):
        d = api_client.get(f"{base_url}/api/wellness/nudges").json()
        assert isinstance(d, list) and len(d) == 15
        n = d[0]
        for k in ("id", "category", "title", "message", "icon"):
            assert k in n, f"nudge missing '{k}'"


# ---------- Truckload Booking Sheet columns (up_charges + notes) ----------
class TestTruckloadColumns:
    def test_new_columns(self, api_client, base_url):
        d = api_client.get(f"{base_url}/api/workbook/truckload-bookings").json()
        cols = d.get("columns", [])
        by_key = {c["key"]: c for c in cols}
        for k in ("up_charges_usd", "up_charges_reason", "notes"):
            assert k in by_key, f"missing column '{k}'"
        # up_charges_reason has select options including 'Detention'
        assert by_key["up_charges_reason"].get("type") == "select"
        opts = by_key["up_charges_reason"].get("options", [])
        assert "Detention" in opts, f"Detention not in {opts}"
        # notes is textarea
        assert by_key["notes"].get("type") == "textarea"
        # carrier still combo with 13+ options
        carrier = by_key.get("carrier")
        assert carrier is not None
        assert carrier.get("type") in ("combo", "select", "combobox")
        assert len(carrier.get("options", [])) >= 13
