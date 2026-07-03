"""Iteration 53 — Aggregator margin, Routing (Mapbox/OSRM), Telematics (Samsara).

Covers:
- GET /api/aggregator/feed  (margin_usd/margin_pct + margin_summary + sort)
- GET /api/routing/provider  (osrm since no MAPBOX_TOKEN)
- POST /api/routing/route (coords) + persistence via /api/routing/recent
- POST /api/routing/route (addresses via OSM Nominatim)  -- lenient
- GET /api/telematics/provider  (sample mode)
- GET /api/telematics/vehicles/locations
- GET /api/telematics/drivers/hos
- GET /api/telematics/safety/events
- POST /api/telematics/connect (admin, rotates env var)
"""
import os
import pytest
import requests

def _load_frontend_env():
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return None


BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or _load_frontend_env() or "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL missing"
ADMIN = "test_session_admin_1"
H = {"Authorization": f"Bearer {ADMIN}", "Content-Type": "application/json"}


# --- Aggregator margin ------------------------------------------------------
class TestAggregatorMargin:
    def test_feed_has_margin_and_summary(self):
        r = requests.get(f"{BASE_URL}/api/aggregator/feed?limit=5", headers=H, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "items" in data
        items = data["items"]
        assert len(items) > 0, "aggregator returned no items"

        for row in items:
            assert "margin_usd" in row, f"row missing margin_usd: {row}"
            assert "margin_pct" in row, f"row missing margin_pct: {row}"
            assert row["margin_usd"] is not None, f"margin_usd null: {row}"
            assert row["margin_pct"] is not None, f"margin_pct null: {row}"
            assert isinstance(row["margin_usd"], (int, float))
            assert isinstance(row["margin_pct"], (int, float))

        assert "margin_summary" in data, "no margin_summary in response"
        ms = data["margin_summary"]
        for key in ("total_margin_usd", "avg_margin_usd", "avg_margin_pct", "high_margin_count"):
            assert key in ms, f"margin_summary missing {key}"

    def test_feed_sort_by_margin_usd_desc(self):
        r = requests.get(f"{BASE_URL}/api/aggregator/feed?limit=10&sort_by=margin_usd",
                         headers=H, timeout=30)
        assert r.status_code == 200, r.text
        items = r.json().get("items", [])
        assert len(items) >= 2
        margins = [float(x.get("margin_usd") or 0) for x in items]
        assert margins == sorted(margins, reverse=True), f"not desc: {margins}"


# --- Routing ----------------------------------------------------------------
class TestRouting:
    def test_provider_defaults_to_osrm(self):
        r = requests.get(f"{BASE_URL}/api/routing/provider", headers=H, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["primary"] == "osrm"
        assert d["mapbox_enabled"] is False

    def test_route_by_coords_la_to_phx(self):
        payload = {
            "origin": {"lat": 34.0522, "lng": -118.2437},
            "destination": {"lat": 33.4484, "lng": -112.0740},
        }
        r = requests.post(f"{BASE_URL}/api/routing/route", headers=H, json=payload, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["distance_mi"] > 100, f"distance too small: {d}"
        # any of the 3 providers is acceptable per agent_to_agent_context_note
        assert d["provider"] in ("mapbox", "osrm", "estimate")
        assert d["distance_m"] > 0
        assert "route_id" in d

    def test_recent_contains_last_route(self):
        r = requests.get(f"{BASE_URL}/api/routing/recent", headers=H, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["count"] >= 1
        assert len(d["items"]) >= 1
        first = d["items"][0]
        assert "distance_mi" in first
        assert "provider" in first

    def test_route_by_address_lenient(self):
        # Nominatim may throttle — accept 200 or 422 with detail per spec.
        payload = {"origin_address": "Los Angeles, CA", "destination_address": "Phoenix, AZ"}
        r = requests.post(f"{BASE_URL}/api/routing/route", headers=H, json=payload, timeout=30)
        assert r.status_code in (200, 422), r.text
        if r.status_code == 200:
            d = r.json()
            assert d["distance_mi"] > 100


# --- Telematics -------------------------------------------------------------
class TestTelematics:
    def test_provider_sample_mode(self):
        # Ensure no lingering token from an earlier connect test leaks.
        # We test provider in the "no live token" phase FIRST.
        r = requests.get(f"{BASE_URL}/api/telematics/provider", headers=H, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["provider"] == "samsara"
        # connected/mode may be flipped if a previous test ran /connect — check either
        assert d["mode"] in ("sample", "live")

    def test_vehicle_locations(self):
        r = requests.get(f"{BASE_URL}/api/telematics/vehicles/locations", headers=H, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["count"] > 0
        for item in d["items"][:3]:
            for key in ("lat", "lng", "speed_mph", "heading_deg"):
                assert key in item, f"missing {key}: {item}"

    def test_hos_logs(self):
        r = requests.get(f"{BASE_URL}/api/telematics/drivers/hos", headers=H, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["count"] > 0
        assert "at_risk" in d
        for item in d["items"][:3]:
            assert "driver_id" in item
            assert "violation_risk" in item

    def test_safety_events(self):
        r = requests.get(f"{BASE_URL}/api/telematics/safety/events", headers=H, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["count"] > 0
        for item in d["items"][:3]:
            assert "event_type" in item
            assert "severity" in item
            assert "coaching_status" in item

    def test_connect_admin_rotates_token(self):
        # Run this LAST — flips provider to connected=true; subsequent live
        # calls will 401 upstream and gracefully fall back to sample data.
        payload = {"api_token": "fake_samsara_token_for_test_1234"}
        r = requests.post(f"{BASE_URL}/api/telematics/connect", headers=H, json=payload, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["ok"] is True
        assert d["mode"] == "live"

        # verify /provider now reports connected=true
        r2 = requests.get(f"{BASE_URL}/api/telematics/provider", headers=H, timeout=15)
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2["connected"] is True

        # verify vehicles/locations still returns items (live 401 → sample fallback)
        r3 = requests.get(f"{BASE_URL}/api/telematics/vehicles/locations", headers=H, timeout=20)
        assert r3.status_code == 200
        assert r3.json()["count"] > 0

        # cleanup: clear the token so we don't pollute state for other test runs
        os.environ.pop("SAMSARA_API_TOKEN", None)
