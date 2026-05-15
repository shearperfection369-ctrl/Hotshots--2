"""Iteration 19 - Real NWS weather alerts + admin-managed alert locations.

Tests:
- GET/POST /api/weather/alert-locations (auth, schema, validation, cap, normalisation)
- GET /api/weather/alerts (seeding from brand, shape, live-or-mock, brand_swap)
- Regression: /api/branding/manual (promo_video_ids) and /api/admin/servers
"""

import os
import json
import requests
import pytest

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
ADMIN = {"Authorization": "Bearer test_session_admin_1", "Content-Type": "application/json"}


# ---------- helpers ----------
def _clear_locations():
    requests.post(f"{BASE_URL}/api/weather/alert-locations",
                  headers=ADMIN, json={"locations": []}, timeout=10)


@pytest.fixture(scope="module", autouse=True)
def _reset_after_module():
    _clear_locations()
    yield
    # Also clear at end so next iteration re-seeds from brand
    _clear_locations()


# ---------- /api/weather/alert-locations ----------
class TestAlertLocations:
    def test_get_empty_after_clear(self):
        # After autouse fixture clear, should be empty list
        r = requests.get(f"{BASE_URL}/api/weather/alert-locations",
                         headers=ADMIN, timeout=10)
        assert r.status_code == 200
        body = r.json()
        assert "locations" in body
        assert isinstance(body["locations"], list)
        assert body["locations"] == []

    def test_post_simple_save_and_persist(self):
        payload = {"locations": [
            {"label": "Denver, CO", "lat": 39.74, "lng": -104.99,
             "state": "CO", "country": "US"}
        ]}
        r = requests.post(f"{BASE_URL}/api/weather/alert-locations",
                          headers=ADMIN, json=payload, timeout=10)
        assert r.status_code == 200
        body = r.json()
        assert body.get("ok") is True
        locs = body.get("locations")
        assert isinstance(locs, list) and len(locs) == 1
        assert locs[0]["label"] == "Denver, CO"
        assert abs(locs[0]["lat"] - 39.74) < 1e-6
        assert abs(locs[0]["lng"] - (-104.99)) < 1e-6
        assert locs[0]["state"] == "CO"
        assert locs[0]["country"] == "US"

        # GET to confirm persistence
        g = requests.get(f"{BASE_URL}/api/weather/alert-locations",
                         headers=ADMIN, timeout=10)
        assert g.status_code == 200
        glocs = g.json()["locations"]
        assert len(glocs) == 1
        assert glocs[0]["label"] == "Denver, CO"

    def test_post_clears_when_empty_list(self):
        # Set then clear
        requests.post(f"{BASE_URL}/api/weather/alert-locations", headers=ADMIN,
                      json={"locations": [{"label": "X", "lat": 1.0, "lng": 2.0}]}, timeout=10)
        r = requests.post(f"{BASE_URL}/api/weather/alert-locations",
                          headers=ADMIN, json={"locations": []}, timeout=10)
        assert r.status_code == 200
        assert r.json()["locations"] == []
        g = requests.get(f"{BASE_URL}/api/weather/alert-locations",
                         headers=ADMIN, timeout=10)
        assert g.json()["locations"] == []

    def test_post_bad_body_non_list(self):
        r = requests.post(f"{BASE_URL}/api/weather/alert-locations",
                          headers=ADMIN, json={"locations": "nope"}, timeout=10)
        # Should not crash; expected 400
        assert r.status_code == 400

    def test_post_missing_locations_key(self):
        r = requests.post(f"{BASE_URL}/api/weather/alert-locations",
                          headers=ADMIN, json={"foo": 1}, timeout=10)
        assert r.status_code == 400

    def test_post_drops_rows_with_missing_lat_lng(self):
        payload = {"locations": [
            {"label": "Good", "lat": 39.0, "lng": -104.0, "state": "CO"},
            {"label": "MissingLat", "lng": -100.0},
            {"label": "MissingLng", "lat": 40.0},
            "not-a-dict",
            {"label": "BadTypes", "lat": "abc", "lng": "xyz"},
        ]}
        r = requests.post(f"{BASE_URL}/api/weather/alert-locations",
                          headers=ADMIN, json=payload, timeout=10)
        # Must not crash. Either 400 or drops bad rows leaving only the good one.
        assert r.status_code in (200, 400)
        if r.status_code == 200:
            locs = r.json()["locations"]
            labels = [l["label"] for l in locs]
            assert "Good" in labels
            assert "MissingLat" not in labels
            assert "MissingLng" not in labels
            assert "BadTypes" not in labels

    def test_post_caps_to_12(self):
        big = [{"label": f"Loc{i}", "lat": 30.0 + i * 0.1,
                "lng": -100.0 - i * 0.1, "state": "TX", "country": "US"}
               for i in range(20)]
        r = requests.post(f"{BASE_URL}/api/weather/alert-locations",
                          headers=ADMIN, json={"locations": big}, timeout=10)
        assert r.status_code == 200
        locs = r.json()["locations"]
        assert len(locs) == 12, f"Expected cap of 12, got {len(locs)}"

    def test_post_uppercases_state_country_and_trims_label(self):
        long_label = "A" * 200
        payload = {"locations": [
            {"label": long_label, "lat": 39.0, "lng": -104.0,
             "state": "co", "country": "us"}
        ]}
        r = requests.post(f"{BASE_URL}/api/weather/alert-locations",
                          headers=ADMIN, json=payload, timeout=10)
        assert r.status_code == 200
        loc = r.json()["locations"][0]
        assert loc["state"] == "CO"
        assert loc["country"] == "US"
        assert len(loc["label"]) <= 80, f"label not trimmed: {len(loc['label'])}"

    def test_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/weather/alert-locations", timeout=10)
        assert r.status_code in (401, 403)


# ---------- /api/weather/alerts ----------
class TestWeatherAlerts:
    SEV = {"high", "moderate", "low"}
    REQUIRED = {"alert_id", "type", "severity", "area", "headline",
                "body", "issued_at", "expires_at"}

    def test_alerts_seed_from_brand_when_empty(self):
        # Ensure empty first
        _clear_locations()
        r = requests.get(f"{BASE_URL}/api/weather/alerts",
                         headers=ADMIN, timeout=30)
        assert r.status_code == 200
        alerts = r.json()
        assert isinstance(alerts, list)
        # Should have triggered a seed; verify locations were stored
        g = requests.get(f"{BASE_URL}/api/weather/alert-locations",
                         headers=ADMIN, timeout=10)
        glocs = g.json()["locations"]
        assert len(glocs) > 0, "Expected /alerts to seed locations from active brand"

    def test_alert_shape(self):
        r = requests.get(f"{BASE_URL}/api/weather/alerts",
                         headers=ADMIN, timeout=30)
        assert r.status_code == 200
        alerts = r.json()
        assert isinstance(alerts, list) and len(alerts) > 0, \
            "Expected at least mock alerts when seeded"
        for a in alerts:
            missing = self.REQUIRED - set(a.keys())
            assert not missing, f"alert missing keys: {missing} | alert={a}"
            assert a["severity"] in self.SEV, \
                f"bad severity {a['severity']}"

    def test_denver_does_not_crash_and_shape_ok(self):
        # Override locations with Denver, CO and confirm /alerts still 200
        requests.post(f"{BASE_URL}/api/weather/alert-locations", headers=ADMIN,
                      json={"locations": [{"label": "Denver, CO",
                                           "lat": 39.74, "lng": -104.99,
                                           "state": "CO", "country": "US"}]},
                      timeout=10)
        r = requests.get(f"{BASE_URL}/api/weather/alerts",
                         headers=ADMIN, timeout=30)
        assert r.status_code == 200
        alerts = r.json()
        assert isinstance(alerts, list)
        # If NWS returned anything live, source should mention NWS / National Weather Service
        live_alerts = [a for a in alerts if a.get("live") is True]
        if live_alerts:
            for a in live_alerts:
                src = (a.get("source") or "") + " " + (a.get("source_url") or "")
                assert "NWS" in src or "National Weather Service" in src or "weather.gov" in src, \
                    f"live alert source unexpected: {a.get('source')} / {a.get('source_url')}"
        # else: NWS may be quiet — assertion skipped per spec

    def test_brand_swap_no_tennant_when_pfizer_active(self):
        # Verify active brand is Pfizer first
        ab = requests.get(f"{BASE_URL}/api/branding", timeout=10, headers=ADMIN)
        if ab.status_code == 200:
            brand = (ab.json() or {}).get("brand") or {}
            brand_name = (brand.get("display_name") or brand.get("brand_id") or "")
            if "pfizer" not in brand_name.lower():
                pytest.skip(f"Active brand is not Pfizer ({brand_name}), skipping brand_swap check")
        r = requests.get(f"{BASE_URL}/api/weather/alerts",
                         headers=ADMIN, timeout=30)
        assert r.status_code == 200
        raw = json.dumps(r.json())
        assert "Tennant" not in raw, \
            "Serialized /weather/alerts contains literal 'Tennant' substring " \
            "while Pfizer brand is active — brand_swap wrapper broken"

    def test_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/weather/alerts", timeout=10)
        assert r.status_code in (401, 403)


# ---------- Regression: iter18 endpoints ----------
class TestIter18Regression:
    def test_branding_manual_saves_promo_video_ids(self):
        # Use a throw-away company_name with activate=False so we don't disturb
        # the currently-active Pfizer brand for the next test iteration.
        payload = {
            "company_name": "TEST PromoCo Iter19",
            "short_name": "TestPromo19",
            "promo_video_ids": ["dQw4w9WgXcQ", "abc123"],
            "activate": False,
        }
        r = requests.post(f"{BASE_URL}/api/branding/manual",
                          headers=ADMIN, json=payload, timeout=15)
        assert r.status_code == 200, f"branding/manual failed: {r.status_code} {r.text[:200]}"
        body = r.json()
        ids = body.get("promo_video_ids") or (body.get("brand") or {}).get("promo_video_ids")
        assert ids is not None, f"promo_video_ids missing from response: {body}"
        assert "dQw4w9WgXcQ" in ids
        assert "abc123" in ids

    def test_admin_servers_returns_totals(self):
        r = requests.get(f"{BASE_URL}/api/admin/servers", headers=ADMIN, timeout=15)
        assert r.status_code == 200
        body = r.json()
        # Either a list or {servers:[...], totals:{}}
        assert isinstance(body, (dict, list))
        if isinstance(body, dict):
            # totals key expected
            assert "totals" in body or "servers" in body, f"unexpected shape: {list(body.keys())}"
