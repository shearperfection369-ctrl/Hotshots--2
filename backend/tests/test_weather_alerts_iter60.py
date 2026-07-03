"""Weather alerts endpoint — verifies mock removal & real NWS integration.

Focused on iter60 review request:
- ?lat&lng from browser geolocation drives live NWS lookup
- No mock strings (Tennant, Walmart, Golden Valley) leak into payload
- 60s cache holds identical calls
- needs_location:true when no lat/lng and no saved locations
"""
import json
import os
import time

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://clean-logistics-dash.preview.emergentagent.com").rstrip("/")
ADMIN_TOKEN = "test_session_admin_1"

MOCK_STRINGS = ["Tennant", "TENNANT", "Walmart", "Golden Valley", "GOLDEN VALLEY",
                "HOLLAND MI", "LOUISVILLE KY"]


@pytest.fixture(scope="module")
def api_client():
    s = requests.Session()
    s.headers.update({
        "Authorization": f"Bearer {ADMIN_TOKEN}",
        "Content-Type": "application/json",
    })
    return s


class TestWeatherAlertsBrowserGeo:
    """?lat&lng path — the new real-NWS mode."""

    def test_denver_returns_real_nws_no_mock(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/weather/alerts",
                           params={"lat": 39.7392, "lng": -104.9903})
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, dict)
        assert "items" in data
        assert isinstance(data["items"], list)
        assert data["resolved_from"] == "browser_geolocation"
        assert data["needs_location"] is False
        assert data["count"] == len(data["items"])
        assert data["no_active_alerts"] == (len(data["items"]) == 0)

        # No mock strings anywhere in the payload
        payload_str = json.dumps(data)
        for mock in MOCK_STRINGS:
            assert mock not in payload_str, f"Mock string '{mock}' leaked into Denver response: {payload_str[:500]}"

        # Any returned alerts must be from NWS
        for item in data["items"]:
            src = item.get("source") or ""
            assert src.startswith("NWS") or "National Weather Service" in src, \
                f"Alert source '{src}' is not from NWS"
            assert item.get("live") is True
            # affected_facility must NOT be a mock facility
            aff = (item.get("affected_facility") or "")
            for mock in MOCK_STRINGS:
                assert mock not in aff, f"affected_facility contains mock string: {aff}"

    def test_miami_no_active_alerts_no_mock(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/weather/alerts",
                           params={"lat": 25.7743, "lng": -80.1937})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["resolved_from"] == "browser_geolocation"
        assert data["needs_location"] is False
        # count may be 0 or >0 depending on actual weather right now.
        assert isinstance(data["items"], list)
        payload_str = json.dumps(data)
        for mock in MOCK_STRINGS:
            assert mock not in payload_str, f"Mock string '{mock}' in Miami response"

    def test_cache_hit_same_coord(self, api_client):
        # Two identical calls within 1s should return identical items list
        r1 = api_client.get(f"{BASE_URL}/api/weather/alerts",
                            params={"lat": 39.7392, "lng": -104.9903})
        r2 = api_client.get(f"{BASE_URL}/api/weather/alerts",
                            params={"lat": 39.7392, "lng": -104.9903})
        assert r1.status_code == 200 and r2.status_code == 200
        # Soft assertion — content should be stable within cache window
        ids1 = sorted(a.get("alert_id") for a in r1.json().get("items", []))
        ids2 = sorted(a.get("alert_id") for a in r2.json().get("items", []))
        assert ids1 == ids2, "Cache miss on second identical call"

    def test_rounded_coord_hits_same_cache(self, api_client):
        # 3-decimal rounding: 39.7392 and 39.7393 → same key
        r1 = api_client.get(f"{BASE_URL}/api/weather/alerts",
                            params={"lat": 39.7392, "lng": -104.9903})
        r2 = api_client.get(f"{BASE_URL}/api/weather/alerts",
                            params={"lat": 39.7393, "lng": -104.9903})
        assert r1.status_code == 200 and r2.status_code == 200
        ids1 = sorted(a.get("alert_id") for a in r1.json().get("items", []))
        ids2 = sorted(a.get("alert_id") for a in r2.json().get("items", []))
        assert ids1 == ids2


class TestWeatherAlertsNoLocation:
    """No lat/lng and no saved locations → needs_location:true."""

    @pytest.fixture(autouse=True)
    def clear_locations(self, api_client):
        # Reset any saved locations to empty
        api_client.post(f"{BASE_URL}/api/weather/alert-locations",
                        json={"locations": []})
        yield

    def test_needs_location_when_no_coords_no_saved(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/weather/alerts")
        assert r.status_code == 200
        data = r.json()
        assert data["needs_location"] is True
        assert data["count"] == 0
        assert data["items"] == []
        assert data["resolved_from"] is None
        # Still no mock strings
        for mock in MOCK_STRINGS:
            assert mock not in json.dumps(data)


class TestWeatherAlertLocationsRegression:
    """Regression: GET/POST /weather/alert-locations still work."""

    def test_post_and_get_locations(self, api_client):
        payload = {"locations": [
            {"label": "TEST_Denver", "lat": 39.7392, "lng": -104.9903, "state": "CO", "country": "US"},
        ]}
        r = api_client.post(f"{BASE_URL}/api/weather/alert-locations", json=payload)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["ok"] is True
        assert len(data["locations"]) == 1
        assert data["locations"][0]["label"] == "TEST_Denver"

        # GET back
        r2 = api_client.get(f"{BASE_URL}/api/weather/alert-locations")
        assert r2.status_code == 200
        assert len(r2.json()["locations"]) == 1

        # cleanup
        api_client.post(f"{BASE_URL}/api/weather/alert-locations",
                        json={"locations": []})

    def test_saved_locations_path_returns_no_mock(self, api_client):
        # save a location then hit /alerts with no query
        api_client.post(f"{BASE_URL}/api/weather/alert-locations", json={
            "locations": [{"label": "TEST_Miami", "lat": 25.7743, "lng": -80.1937, "state": "FL", "country": "US"}]
        })
        r = api_client.get(f"{BASE_URL}/api/weather/alerts")
        assert r.status_code == 200
        data = r.json()
        assert data["resolved_from"] == "saved_locations"
        assert data["needs_location"] is False
        for mock in MOCK_STRINGS:
            assert mock not in json.dumps(data)
        # cleanup
        api_client.post(f"{BASE_URL}/api/weather/alert-locations", json={"locations": []})
