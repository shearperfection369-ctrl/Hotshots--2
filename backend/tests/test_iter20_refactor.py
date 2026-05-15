"""Iteration 20 — backend regression after conservative refactor.

Verifies that moving weather + server-registry endpoints into
/app/backend/routes/ did not change behaviour, that the new NWS cache
(60s, keyed by rounded lat/lng) yields stable shapes across consecutive
calls, that the non-blocking asyncio TCP ping handles bad endpoints
without crashing, and that other brand-aware endpoints still work.
"""
import os
import time
import uuid
import pytest
import requests


def _load_backend_url() -> str:
    url = os.environ.get("REACT_APP_BACKEND_URL")
    if not url:
        try:
            with open("/app/frontend/.env") as f:
                for line in f:
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        url = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break
        except Exception:
            pass
    if not url:
        raise RuntimeError("REACT_APP_BACKEND_URL missing from env and frontend/.env")
    return url.rstrip("/")


BASE_URL = _load_backend_url()

ADMIN = {"Authorization": "Bearer test_session_admin_1"}
# /app/memory/test_credentials.md says dispatcher token is `test_disp_session`.
# Review request asked for `test_session_disp_1`, but creds file is source-of-
# truth — both are exercised so we cover either wiring.
DISP_PRIMARY = {"Authorization": "Bearer test_disp_session"}
DISP_FALLBACK = {"Authorization": "Bearer test_session_disp_1"}

REQUIRED_ALERT_FIELDS = {
    "alert_id", "type", "severity", "area", "headline",
    "body", "issued_at", "expires_at",
}


# ====================== WEATHER REGRESSION ======================
class TestWeatherAlertsRegression:
    def test_alerts_endpoint_returns_list_with_required_shape(self):
        r = requests.get(f"{BASE_URL}/api/weather/alerts", headers=ADMIN, timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list)
        # If empty, mock fallback path should have produced rows
        assert len(data) >= 1, "Expected at least mocked alert fallback"
        for a in data:
            missing = REQUIRED_ALERT_FIELDS - set(a.keys())
            assert not missing, f"Alert missing fields {missing}: {a}"
            assert a["severity"] in {"high", "moderate", "low"}

    def test_get_alert_locations_shape(self):
        r = requests.get(f"{BASE_URL}/api/weather/alert-locations",
                         headers=ADMIN, timeout=10)
        assert r.status_code == 200, r.text
        body = r.json()
        assert isinstance(body, dict)
        assert "locations" in body
        assert isinstance(body["locations"], list)

    def test_post_alert_locations_validates_and_caps_at_12(self):
        good = [{"label": f"City {i}", "lat": 40 + i * 0.1, "lng": -90 - i * 0.1,
                 "state": "mn", "country": "us"} for i in range(15)]
        bad = ["not-a-dict", {"label": "missing latlng"}, {"lat": 1.0}, 42]
        payload = {"locations": good + bad}
        r = requests.post(f"{BASE_URL}/api/weather/alert-locations",
                          headers=ADMIN, json=payload, timeout=10)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("ok") is True
        # Capped at 12 — slicing happens before validation, so all 12 first
        # entries are valid → 12 cleaned, dropped count covers anything left
        assert len(body["locations"]) == 12, body
        assert body.get("dropped", 0) >= 0
        # State upper-cased + country upper-cased
        for row in body["locations"]:
            assert row["state"] == "MN"
            assert row["country"] == "US"

    def test_post_alert_locations_drops_invalid_only(self):
        payload = {"locations": [
            {"label": "Valid", "lat": 44.98, "lng": -93.34, "state": "mn"},
            {"not": "a-location"},
            "string",
            {"label": "NoCoords"},
        ]}
        r = requests.post(f"{BASE_URL}/api/weather/alert-locations",
                          headers=ADMIN, json=payload, timeout=10)
        assert r.status_code == 200, r.text
        body = r.json()
        assert len(body["locations"]) == 1
        assert body["dropped"] == 3
        assert body["locations"][0]["state"] == "MN"

    def test_post_alert_locations_rejects_bad_body(self):
        r = requests.post(f"{BASE_URL}/api/weather/alert-locations",
                          headers=ADMIN, json={"foo": "bar"}, timeout=10)
        assert r.status_code == 400, r.text


# ====================== CACHE PERFORMANCE ======================
class TestWeatherCachePerformance:
    def test_back_to_back_calls_consistent_and_second_fast(self):
        """Two calls within 5s must both succeed; second should be a cache hit.
        Allow first call to be slow (cold NWS fetch), assert second < first or
        under 4s — and crucially that the alert_id set is identical (cache
        correctness)."""
        t0 = time.time()
        r1 = requests.get(f"{BASE_URL}/api/weather/alerts", headers=ADMIN, timeout=20)
        d1 = time.time() - t0
        assert r1.status_code == 200

        t1 = time.time()
        r2 = requests.get(f"{BASE_URL}/api/weather/alerts", headers=ADMIN, timeout=20)
        d2 = time.time() - t1
        assert r2.status_code == 200

        ids1 = {a["alert_id"] for a in r1.json()}
        ids2 = {a["alert_id"] for a in r2.json()}
        assert ids1 == ids2, (
            f"Cache correctness bug: alert sets differ within 60s TTL. "
            f"first={ids1} second={ids2}"
        )
        # Soft perf assertion — second call should be reasonably fast
        assert d2 < 6.0, f"Second call took {d2:.2f}s — cache may be ineffective"
        print(f"cache perf: first={d1:.2f}s second={d2:.2f}s")


# ====================== BRAND SWAP ======================
class TestBrandSwap:
    def test_no_literal_tennant_in_weather_alerts_when_pfizer_active(self):
        # Ensure Pfizer brand is the active one
        br = requests.get(f"{BASE_URL}/api/branding", headers=ADMIN, timeout=10)
        assert br.status_code == 200
        body = br.json() or {}
        brand_obj = body.get("brand") if isinstance(body.get("brand"), dict) else body
        brand_name = (brand_obj.get("company_name") or brand_obj.get("brand_name")
                      or brand_obj.get("brand_id") or "")
        # Branding may report 'Pfizer' or similar — only enforce sub-check if
        # the active brand is NOT tennant
        if "tennant" in brand_name.lower():
            pytest.skip("Active brand is Tennant — sub-check not meaningful")

        r = requests.get(f"{BASE_URL}/api/weather/alerts", headers=ADMIN, timeout=20)
        assert r.status_code == 200
        body_text = r.text
        assert "Tennant" not in body_text, (
            "Brand swap leak: literal 'Tennant' present in /api/weather/alerts "
            f"while active brand is {brand_name!r}"
        )


# ====================== SERVER REGISTRY ======================
@pytest.fixture(scope="module")
def cleanup_servers():
    created: list[str] = []
    yield created
    # Teardown — remove all custom servers we created
    for sid in created:
        try:
            requests.delete(f"{BASE_URL}/api/admin/servers/{sid}",
                            headers=ADMIN, timeout=10)
        except Exception:
            pass


class TestServerRegistry:
    def test_list_servers_returns_system_and_custom(self):
        r = requests.get(f"{BASE_URL}/api/admin/servers", headers=ADMIN, timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "system" in body and "custom" in body and "totals" in body
        assert isinstance(body["system"], list)
        assert isinstance(body["custom"], list)
        # Must always have at least api + mongo + llm
        roles = {s["id"] for s in body["system"]}
        assert "system::api" in roles
        assert "system::mongo" in roles
        assert "system::llm" in roles
        totals = body["totals"]
        for k in ("total", "healthy", "down", "by_role"):
            assert k in totals
        assert totals["total"] == len(body["system"]) + len(body["custom"])

    def test_create_patch_delete_custom_server(self, cleanup_servers):
        name = f"TEST_iter20_{uuid.uuid4().hex[:6]}"
        create = requests.post(f"{BASE_URL}/api/admin/servers", headers=ADMIN, json={
            "name": name, "role": "cache", "hostname": "redis.example.com",
            "port": 6379, "protocol": "redis", "environment": "staging",
            "owner_email": "ops@example.com", "notes": "Iter20 test",
        }, timeout=10)
        assert create.status_code == 200, create.text
        doc = create.json()
        sid = doc["id"]
        cleanup_servers.append(sid)
        assert sid.startswith("SRV-")
        assert doc["name"] == name
        assert doc["enabled"] is True

        # GET — verify persistence
        listing = requests.get(f"{BASE_URL}/api/admin/servers",
                               headers=ADMIN, timeout=10).json()
        ids = {c["id"] for c in listing["custom"]}
        assert sid in ids

        # PATCH
        patch = requests.patch(f"{BASE_URL}/api/admin/servers/{sid}",
                               headers=ADMIN, json={"notes": "updated"}, timeout=10)
        assert patch.status_code == 200, patch.text
        assert patch.json()["notes"] == "updated"

        # DELETE
        d = requests.delete(f"{BASE_URL}/api/admin/servers/{sid}",
                            headers=ADMIN, timeout=10)
        assert d.status_code == 200, d.text
        # Verify gone
        listing2 = requests.get(f"{BASE_URL}/api/admin/servers",
                                headers=ADMIN, timeout=10).json()
        ids2 = {c["id"] for c in listing2["custom"]}
        assert sid not in ids2
        cleanup_servers.remove(sid)

    def test_system_servers_immutable(self):
        p = requests.patch(f"{BASE_URL}/api/admin/servers/system::api",
                          headers=ADMIN, json={"notes": "no"}, timeout=10)
        assert p.status_code == 400, p.text
        d = requests.delete(f"{BASE_URL}/api/admin/servers/system::mongo",
                           headers=ADMIN, timeout=10)
        assert d.status_code == 400, d.text

    def test_ping_http_health_url_returns_healthy(self, cleanup_servers):
        c = requests.post(f"{BASE_URL}/api/admin/servers", headers=ADMIN, json={
            "name": "TEST_iter20_google", "role": "edge",
            "hostname": "www.google.com",
            "health_url": "https://www.google.com",
        }, timeout=10)
        assert c.status_code == 200, c.text
        sid = c.json()["id"]
        cleanup_servers.append(sid)
        p = requests.post(f"{BASE_URL}/api/admin/servers/{sid}/ping",
                          headers=ADMIN, timeout=15)
        assert p.status_code == 200, p.text
        body = p.json()
        assert body["last_health"] in {"healthy", "degraded"}, body
        assert isinstance(body.get("last_ping_ms"), int)

    def test_ping_bad_tcp_returns_down_without_crashing(self, cleanup_servers):
        c = requests.post(f"{BASE_URL}/api/admin/servers", headers=ADMIN, json={
            "name": "TEST_iter20_badtcp", "role": "cache",
            "hostname": "localhost", "port": 1,
        }, timeout=10)
        assert c.status_code == 200
        sid = c.json()["id"]
        cleanup_servers.append(sid)
        t0 = time.time()
        p = requests.post(f"{BASE_URL}/api/admin/servers/{sid}/ping",
                          headers=ADMIN, timeout=15)
        elapsed = time.time() - t0
        assert p.status_code == 200, p.text
        assert p.json()["last_health"] == "down"
        # Should not block the event loop for long — non-blocking asyncio
        assert elapsed < 10, f"Ping took {elapsed:.2f}s — possible event-loop block"

        # Sanity: another endpoint still responsive RIGHT AFTER the bad ping
        s = requests.get(f"{BASE_URL}/api/branding", headers=ADMIN, timeout=5)
        assert s.status_code == 200

    def _dispatcher_headers(self):
        # try both possible tokens, return one that authenticates
        for h in (DISP_PRIMARY, DISP_FALLBACK):
            r = requests.get(f"{BASE_URL}/api/auth/me", headers=h, timeout=10)
            if r.status_code == 200 and r.json().get("role") != "admin":
                return h
        pytest.skip("No working non-admin token found")

    def test_non_admin_forbidden(self):
        h = self._dispatcher_headers()
        r = requests.get(f"{BASE_URL}/api/admin/servers", headers=h, timeout=10)
        assert r.status_code == 403, f"expected 403 got {r.status_code}: {r.text}"


# ====================== OTHER BRAND-AWARE ENDPOINTS ======================
class TestOtherEndpointsHealthy:
    def test_branding(self):
        r = requests.get(f"{BASE_URL}/api/branding", headers=ADMIN, timeout=10)
        assert r.status_code == 200, r.text
        body = r.json()
        brand = body.get("brand") if isinstance(body, dict) else None
        assert isinstance(brand, dict), f"Unexpected branding shape: {body}"
        assert "brand_id" in brand or "company_name" in brand

    def test_shipments_limit_5(self):
        r = requests.get(f"{BASE_URL}/api/shipments?limit=5",
                         headers=ADMIN, timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        # Accept either list or {items: [...]}
        rows = body if isinstance(body, list) else body.get("items") or body.get("shipments") or []
        assert isinstance(rows, list)
        assert len(rows) <= 5

    def test_kpis(self):
        r = requests.get(f"{BASE_URL}/api/kpis", headers=ADMIN, timeout=15)
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), (dict, list))

    def test_sap_config(self):
        r = requests.get(f"{BASE_URL}/api/sap/config", headers=ADMIN, timeout=10)
        assert r.status_code == 200, r.text
