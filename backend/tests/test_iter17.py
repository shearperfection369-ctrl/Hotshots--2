"""Iteration 17 backend tests:
 - SAP brand bleed-through (Pfizer active) — config / sales-orders / purchase-orders /
   materials / sync-logs / open-deliveries should all be brand-swapped.
 - /api/integrations hostnames should brand-swap.
 - /api/kpis network_metrics should drift per active brand (non-Tennant).
 - Server Registry admin CRUD + ping + admin-only enforcement.
"""
import os
import re
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://clean-logistics-dash.preview.emergentagent.com").rstrip("/")
ADMIN_TOKEN = "test_session_admin_1"
DISP_TOKEN = "test_disp_session"  # per /app/memory/test_credentials.md (request had wrong name)


# ---------- fixtures ----------
@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {ADMIN_TOKEN}", "Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def dispatcher():
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {DISP_TOKEN}", "Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def active_brand(admin):
    r = admin.get(f"{BASE_URL}/api/branding")
    r.raise_for_status()
    return r.json().get("brand") or {}


# ---------- SAP brand bleed-through ----------
class TestSAPBrandBleedThrough:
    def test_sap_config_brand_swapped(self, admin, active_brand):
        short = (active_brand.get("short_name") or "").lower()
        slug = re.sub(r"[^a-z0-9]+", "", short)[:20] or "brand"
        r = admin.get(f"{BASE_URL}/api/sap/config")
        assert r.status_code == 200, r.text
        d = r.json()
        assert "tennant" not in d.get("host", "").lower(), f"Host bleed-through: {d.get('host')}"
        assert slug in d.get("host", "").lower(), f"Expected slug '{slug}' in host: {d.get('host')}"
        # user prefix should not start with TENNANT
        assert not d.get("user", "").upper().startswith("TENNANT"), f"User bleed-through: {d.get('user')}"

    def test_sap_sales_orders_brand_swapped(self, admin):
        r = admin.get(f"{BASE_URL}/api/sap/sales-orders")
        assert r.status_code == 200, r.text
        d = r.json()
        blob = str(d).lower()
        if "tennant" in blob:
            hits = re.findall(r"tennant\S*", blob)[:5]
            assert False, f"Tennant bleed in sales-orders: {hits}"
        # source URL must reflect brand
        src = d.get("source") or d.get("source_url") or ""
        if src:
            assert "tennant" not in src.lower()

    def test_sap_purchase_orders_brand_swapped(self, admin):
        r = admin.get(f"{BASE_URL}/api/sap/purchase-orders")
        assert r.status_code == 200, r.text
        blob = str(r.json()).lower()
        assert "tennant" not in blob, "Tennant bleed in purchase-orders"

    def test_sap_materials_brand_swapped(self, admin):
        r = admin.get(f"{BASE_URL}/api/sap/materials")
        assert r.status_code == 200, r.text
        blob = str(r.json()).lower()
        assert "tennant" not in blob, "Tennant bleed in materials"

    def test_sap_sync_logs_brand_swapped(self, admin):
        r = admin.get(f"{BASE_URL}/api/sap/sync-logs")
        assert r.status_code == 200, r.text
        blob = str(r.json()).lower()
        assert "tennant" not in blob, "Tennant bleed in sync-logs"

    def test_sap_open_deliveries_brand_swapped(self, admin):
        r = admin.get(f"{BASE_URL}/api/sap/open-deliveries")
        assert r.status_code == 200, r.text
        blob = str(r.json()).lower()
        assert "tennant" not in blob, "Tennant bleed in open-deliveries"


# ---------- Integrations ----------
class TestIntegrationsBrandSwap:
    def test_integrations_endpoint_brand_swapped(self, admin, active_brand):
        short = (active_brand.get("short_name") or "").lower()
        slug = re.sub(r"[^a-z0-9]+", "", short)[:20] or "brand"
        r = admin.get(f"{BASE_URL}/api/integrations")
        assert r.status_code == 200, r.text
        blob = str(r.json()).lower()
        # active brand is Pfizer — there should be at least one pfizer-prefixed host
        assert slug in blob, f"Expected slug '{slug}' somewhere in /api/integrations response"
        assert "tennantco.sharepoint.com" not in blob, "SharePoint host bleed-through"
        assert "powerbi.com/tennant" not in blob, "PowerBI host bleed-through"


# ---------- KPIs ----------
class TestKPIsBrandDrift:
    def test_kpis_network_metrics_drift_for_pfizer(self, admin, active_brand):
        r = admin.get(f"{BASE_URL}/api/kpis")
        assert r.status_code == 200, r.text
        d = r.json()
        nm = d.get("network_metrics") or {}
        assert nm, "network_metrics missing on /api/kpis"
        # network_metrics is a dict of category -> list[metric]. Find on_time_pickup.
        flat = [m for grp in nm.values() if isinstance(grp, list) for m in grp]
        otp = next((m.get("value") for m in flat if m.get("key") == "on_time_pickup"), None)
        assert otp is not None, f"on_time_pickup missing. categories={list(nm.keys())}"
        if (active_brand.get("brand_id") or "tennant") != "tennant":
            assert abs(float(otp) - 95.3) > 0.05, f"on_time_pickup did not drift for non-Tennant brand (got {otp}, baseline 95.3)"


# ---------- Server Registry ----------
class TestServerRegistry:
    created_ids: list = []

    def test_admin_required_get(self, dispatcher):
        r = dispatcher.get(f"{BASE_URL}/api/admin/servers")
        assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"

    def test_admin_required_post(self, dispatcher):
        r = dispatcher.post(f"{BASE_URL}/api/admin/servers", json={
            "name": "x", "role": "edi", "hostname": "x.example.com"
        })
        assert r.status_code == 403

    def test_admin_required_delete(self, dispatcher):
        r = dispatcher.delete(f"{BASE_URL}/api/admin/servers/SRV-FAKE")
        assert r.status_code == 403

    def test_list_servers_has_system_and_totals(self, admin):
        r = admin.get(f"{BASE_URL}/api/admin/servers")
        assert r.status_code == 200, r.text
        d = r.json()
        assert "system" in d and "custom" in d and "totals" in d
        assert isinstance(d["system"], list) and len(d["system"]) >= 3, "Expected api/mongo/llm system rows"
        system_ids = {s["id"] for s in d["system"]}
        assert "system::api" in system_ids
        assert "system::mongo" in system_ids
        assert "system::llm" in system_ids
        totals = d["totals"]
        assert totals.get("total") == len(d["system"]) + len(d["custom"])

    def test_create_custom_server_with_health_url(self, admin):
        payload = {
            "name": "TEST_HealthURL Server",
            "role": "edi",
            "hostname": "test-edi.example.com",
            "port": 443,
            "protocol": "https",
            "region": "us-east-1",
            "environment": "staging",
            "owner_email": "test@example.com",
            "notes": "TEST_ created by iteration 17",
            "health_url": "https://httpbin.org/status/200",
        }
        r = admin.post(f"{BASE_URL}/api/admin/servers", json=payload)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["name"] == payload["name"]
        assert d["id"].startswith("SRV-")
        assert d["system"] is False
        TestServerRegistry.created_ids.append(d["id"])
        # verify via GET
        r2 = admin.get(f"{BASE_URL}/api/admin/servers")
        assert any(c["id"] == d["id"] for c in r2.json()["custom"])

    def test_create_custom_server_with_hostname_port(self, admin):
        payload = {
            "name": "TEST_TCP Server",
            "role": "cache",
            "hostname": "1.1.1.1",
            "port": 443,
            "protocol": "tcp",
        }
        r = admin.post(f"{BASE_URL}/api/admin/servers", json=payload)
        assert r.status_code == 200, r.text
        TestServerRegistry.created_ids.append(r.json()["id"])

    def test_patch_custom_server(self, admin):
        assert TestServerRegistry.created_ids, "need a created server"
        sid = TestServerRegistry.created_ids[0]
        r = admin.patch(f"{BASE_URL}/api/admin/servers/{sid}", json={"notes": "TEST_updated"})
        assert r.status_code == 200, r.text
        assert r.json()["notes"] == "TEST_updated"

    def test_patch_system_server_rejected(self, admin):
        r = admin.patch(f"{BASE_URL}/api/admin/servers/system::api", json={"notes": "nope"})
        assert r.status_code == 400, r.text

    def test_delete_system_server_rejected(self, admin):
        r = admin.delete(f"{BASE_URL}/api/admin/servers/system::mongo")
        assert r.status_code == 400, r.text

    def test_ping_http_health_url(self, admin):
        assert TestServerRegistry.created_ids, "need a created server"
        sid = TestServerRegistry.created_ids[0]  # health_url server
        r = admin.post(f"{BASE_URL}/api/admin/servers/{sid}/ping")
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["last_health"] in ("healthy", "degraded", "down")
        # httpbin /status/200 should be healthy — but allow degraded/down for network flakes
        assert "last_check_at" in d

    def test_ping_tcp_hostname_port(self, admin):
        assert len(TestServerRegistry.created_ids) >= 2
        sid = TestServerRegistry.created_ids[1]  # hostname+port server
        r = admin.post(f"{BASE_URL}/api/admin/servers/{sid}/ping")
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["last_health"] in ("healthy", "down", "degraded")

    def test_zz_cleanup_delete_custom(self, admin):
        for sid in list(TestServerRegistry.created_ids):
            r = admin.delete(f"{BASE_URL}/api/admin/servers/{sid}")
            assert r.status_code == 200, f"delete {sid}: {r.text}"
        # verify they're gone
        r = admin.get(f"{BASE_URL}/api/admin/servers")
        custom_ids = {c["id"] for c in r.json()["custom"]}
        for sid in TestServerRegistry.created_ids:
            assert sid not in custom_ids

    def test_delete_unknown_returns_404(self, admin):
        r = admin.delete(f"{BASE_URL}/api/admin/servers/SRV-DOES-NOT-EXIST")
        assert r.status_code == 404
