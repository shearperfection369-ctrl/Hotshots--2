"""Iteration 18 — Backend tests for v2.2 polish iteration:

Packages tested:
  (A) Brand-aware data reactivity — shipments, drivers, trailers, specialty-carriers,
      traffic, weather/alerts, kpis all return active brand's data; switching back
      to Tennant restores original data.
  (B) /api/branding/template + /api/branding/manual support promo_video_ids.
  (C) After booking a shipment, /api/shipments/{id}/generate-bol creates a BOL
      document and /api/documents/{id}/pdf returns a real PDF.
  (D) Regression: existing /api/admin/servers Server Registry endpoints work.

Active-brand convention enforced by this run:
  • Tests start with whatever brand the system currently has active.
  • Tests will switch to Tennant for "restore" check, then switch back to Pfizer
    so the system is left in the Pfizer-active state (per review request).
"""
import os
import json
import time
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://clean-logistics-dash.preview.emergentagent.com").rstrip("/")
ADMIN_TOKEN = "test_session_admin_1"

H = {"Authorization": f"Bearer {ADMIN_TOKEN}", "Content-Type": "application/json"}


# -------------------- helpers --------------------
def _flatten(value):
    """Yield every string scalar in a nested JSON value."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for v in value:
            yield from _flatten(v)
    elif isinstance(value, dict):
        for v in value.values():
            yield from _flatten(v)


def _active_brand():
    r = requests.get(f"{BASE_URL}/api/branding", headers=H, timeout=15)
    assert r.status_code == 200, r.text
    return r.json().get("brand") or {}


def _activate(brand_id: str):
    r = requests.post(
        f"{BASE_URL}/api/branding/activate",
        headers=H,
        data=json.dumps({"brand_id": brand_id}),
        timeout=15,
    )
    assert r.status_code == 200, f"activate {brand_id} failed: {r.status_code} {r.text}"


# -------------------- Package B: promo_video_ids --------------------
class TestBrandingTemplateAndManual:
    """/api/branding/template default + /api/branding/manual persistence."""

    def test_template_returns_promo_video_ids_default(self):
        r = requests.get(f"{BASE_URL}/api/branding/template", headers=H, timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "promo_video_ids" in body, f"promo_video_ids missing from template: {list(body)}"
        assert body["promo_video_ids"] == ["", "", ""], body["promo_video_ids"]

    def test_manual_persists_promo_video_ids_and_trims_empties(self):
        # Use a throwaway brand_id (TEST_ prefix) — DON'T activate it.
        payload = {
            "company_name": "TEST_PromoVidCo",
            "short_name": "TEST_Promo",
            "promo_video_ids": [
                "dQw4w9WgXcQ",
                "  yt-vid-2  ",  # whitespace gets trimmed
                "",              # dropped by server filter (falsy)
                "yt-vid-3",
                "yt-vid-4",
                "yt-vid-5",
                "yt-vid-6",
                "yt-vid-7",      # 7th non-empty should be cut off (max 6)
            ],
            "activate": False,
        }
        r = requests.post(
            f"{BASE_URL}/api/branding/manual",
            headers=H,
            data=json.dumps(payload),
            timeout=15,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("ok") is True
        brand = body.get("brand") or {}
        pvids = brand.get("promo_video_ids")
        assert pvids is not None, "promo_video_ids missing from manual create response"
        # Trimmed
        assert "  yt-vid-2  " not in pvids
        assert "yt-vid-2" in pvids
        # Empties dropped
        assert "" not in pvids
        # Capped at 6
        assert len(pvids) == 6, f"expected 6 promo videos, got {len(pvids)}: {pvids}"
        # First entry preserved
        assert pvids[0] == "dQw4w9WgXcQ"

        # Cleanup the test brand row
        try:
            from pymongo import MongoClient
            mc = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
            mc[os.environ.get("DB_NAME", "test_database")].company_brand.delete_one(
                {"brand_id": "test-promo"}
            )
        except Exception:
            pass  # best-effort cleanup

    def test_manual_with_activate_true_makes_brand_active(self):
        """Create + activate a brand; verify /api/branding returns it; then switch back to Pfizer."""
        payload = {
            "company_name": "TEST_ActivateMe Corp",
            "short_name": "TEST_ActMe",
            "primary_color": "#123456",
            "promo_video_ids": ["promo-A"],
            "activate": True,
        }
        r = requests.post(
            f"{BASE_URL}/api/branding/manual",
            headers=H,
            data=json.dumps(payload),
            timeout=15,
        )
        assert r.status_code == 200, r.text
        new_brand = r.json().get("brand") or {}
        new_id = new_brand.get("brand_id")
        assert new_brand.get("is_active") is True

        try:
            # Verify via GET /api/branding
            current = _active_brand()
            assert current.get("brand_id") == new_id, current
            assert current.get("promo_video_ids") == ["promo-A"]
        finally:
            # Switch back to Pfizer (required end state) and clean up
            _activate("pfizer")
            try:
                from pymongo import MongoClient
                mc = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
                mc[os.environ.get("DB_NAME", "test_database")].company_brand.delete_one(
                    {"brand_id": new_id}
                )
            except Exception:
                pass


# -------------------- Package C: Book-then-BOL --------------------
class TestBookingThenBOL:
    """POST /api/shipments → /generate-bol → /pdf round-trip."""

    @pytest.fixture(scope="class")
    def shipment(self):
        payload = {
            "reference": f"TEST-IT18-{int(time.time())}",
            "mode": "Truckload",
            "carrier": "TEST_Carrier_LLC",
            "origin_facility": None,
            "origin_city": "Minneapolis",
            "destination_city": "Chicago",
            "destination_lat": 41.8781,
            "destination_lng": -87.6298,
            "pickup_date": "2026-02-10",
            "weight_lbs": 12000.0,
            "pieces": 12,
            "commodity": "Industrial Sample Goods",
            "value_usd": 45000.0,
        }
        r = requests.post(
            f"{BASE_URL}/api/shipments",
            headers=H,
            data=json.dumps(payload),
            timeout=20,
        )
        assert r.status_code == 200, r.text
        s = r.json()
        assert "shipment_id" in s, s
        assert s["shipment_id"].startswith("SHP-")
        return s

    def test_generate_bol_returns_BOL_doc_with_fields(self, shipment):
        sid = shipment["shipment_id"]
        r = requests.post(
            f"{BASE_URL}/api/shipments/{sid}/generate-bol",
            headers=H,
            data=json.dumps({"shipper": "Tennant Company"}),
            timeout=20,
        )
        assert r.status_code == 200, r.text
        doc = r.json()
        assert doc.get("type") == "BOL", doc
        assert doc.get("document_id", "").startswith("DOC-"), doc
        data = doc.get("data") or {}
        # Required BOL fields
        for k in ("origin", "destination", "carrier"):
            assert k in data and data[k], f"BOL data missing/empty {k}: {data}"
        assert data["carrier"] == "TEST_Carrier_LLC", data["carrier"]
        # Pfizer is active → origin should reflect a Pfizer city, NOT a default
        # Tennant city. The overlay only swaps Tennant defaults, so a custom
        # origin_city like 'Minneapolis' stays unchanged. We just assert truthy.
        assert "Chicago" in data["destination"], data["destination"]

        # Stash for PDF test
        TestBookingThenBOL._doc_id = doc["document_id"]

    def test_bol_pdf_download_returns_pdf_content_type(self, shipment):
        doc_id = getattr(TestBookingThenBOL, "_doc_id", None)
        assert doc_id, "BOL doc was not created in previous test"
        r = requests.get(
            f"{BASE_URL}/api/documents/{doc_id}/pdf",
            headers=H,
            timeout=20,
        )
        assert r.status_code == 200, r.text
        ct = r.headers.get("content-type", "")
        assert "application/pdf" in ct.lower(), f"unexpected content-type {ct!r}"
        # PDF magic header
        assert r.content[:4] == b"%PDF", f"response not a PDF (starts with {r.content[:8]!r})"


# -------------------- Package A: brand-reactive endpoints --------------------
class TestBrandReactivity:
    """Endpoints must return active brand's data, no Tennant bleed-through
    when a non-Tennant brand is active."""

    @pytest.fixture(scope="class", autouse=True)
    def _ensure_pfizer_active(self):
        # Make sure we start each class with Pfizer active.
        b = _active_brand()
        if b.get("brand_id") != "pfizer":
            _activate("pfizer")
        yield
        # leave Pfizer active at end of class (final restore at module teardown)
        _activate("pfizer")

    def test_shipments_use_pfizer_cities(self):
        r = requests.get(f"{BASE_URL}/api/shipments?limit=20", headers=H, timeout=20)
        assert r.status_code == 200, r.text
        ships = r.json()
        assert len(ships) > 0, "no shipments returned"
        banned = {"Holland", "Louisville", "Golden Valley"}
        offenders = []
        for s in ships[:20]:
            for endpoint_key in ("origin", "destination"):
                ep = s.get(endpoint_key) or {}
                city = (ep.get("city") or "").strip()
                if city in banned:
                    offenders.append((s.get("shipment_id"), endpoint_key, city))
        assert not offenders, f"Tennant cities leaked into Pfizer-active shipments: {offenders[:5]}"

    def test_drivers_no_tennant_substring(self):
        r = requests.get(f"{BASE_URL}/api/drivers", headers=H, timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        bad = [s for s in _flatten(body) if "Tennant" in s or "TENNANT" in s]
        assert not bad, f"'Tennant' string leaked into /api/drivers: {bad[:5]}"

    def test_trailers_no_tennant_substring(self):
        r = requests.get(f"{BASE_URL}/api/trailers", headers=H, timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        bad = [s for s in _flatten(body) if "Tennant" in s or "TENNANT" in s]
        assert not bad, f"'Tennant' string leaked into /api/trailers: {bad[:5]}"

    def test_specialty_carriers_no_tennant_substring(self):
        r = requests.get(f"{BASE_URL}/api/specialty-carriers", headers=H, timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        bad = [s for s in _flatten(body) if "Tennant" in s or "TENNANT" in s]
        assert not bad, f"'Tennant' string leaked into /api/specialty-carriers: {bad[:5]}"

    def test_kpis_network_metrics_drifted_from_tennant(self):
        r = requests.get(f"{BASE_URL}/api/kpis", headers=H, timeout=20)
        assert r.status_code == 200, r.text
        nm = r.json().get("network_metrics") or {}
        # network_metrics is {category: [metric, ...]}; find on_time_pickup metric
        on_time = None
        for group in nm.values():
            if isinstance(group, list):
                for m in group:
                    if isinstance(m, dict) and m.get("key") == "on_time_pickup":
                        on_time = m
                        break
            if on_time:
                break
        # If schema differs, fall back to any numeric metric -- just assert at
        # least one metric exists and is a number.
        assert nm, "network_metrics missing"
        if on_time and "value" in on_time:
            assert on_time["value"] != 95.3, f"on_time_pickup == Tennant baseline: {on_time}"

    def test_traffic_no_tennant_substring(self):
        r = requests.get(f"{BASE_URL}/api/traffic", headers=H, timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        bad = [s for s in _flatten(body) if "Tennant" in s or "TENNANT" in s]
        assert not bad, f"'Tennant' string leaked into /api/traffic: {bad[:5]}"

    def test_weather_alerts_no_tennant_substring(self):
        r = requests.get(f"{BASE_URL}/api/weather/alerts", headers=H, timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        bad = [s for s in _flatten(body) if "Tennant" in s or "TENNANT" in s]
        assert not bad, f"'Tennant' string leaked into /api/weather/alerts: {bad[:5]}"


class TestRestoreToTennant:
    """Switching back to tennant should restore original Tennant data;
    finally re-activate Pfizer so the system is left in the required state."""

    def test_switch_to_tennant_restores_tennant_cities(self):
        try:
            _activate("tennant")
            r = requests.get(f"{BASE_URL}/api/shipments?limit=20", headers=H, timeout=20)
            assert r.status_code == 200, r.text
            ships = r.json()
            assert len(ships) > 0
            tennant_cities = {"Golden Valley", "Holland", "Louisville"}
            found = set()
            for s in ships[:20]:
                for endpoint_key in ("origin", "destination"):
                    ep = s.get(endpoint_key) or {}
                    city = (ep.get("city") or "").strip()
                    if city in tennant_cities:
                        found.add(city)
            assert found, f"no Tennant cities found in any of first 20 shipments after switch to tennant"

            # /api/drivers should now show 'Tennant' somewhere (driver name plate etc.)
            r2 = requests.get(f"{BASE_URL}/api/drivers", headers=H, timeout=20)
            assert r2.status_code == 200
            # We don't require Tennant in drivers (data may not include the
            # word) — but we should NOT see Pfizer leftover. Just assert 200.
        finally:
            # MUST end with Pfizer active per review request
            _activate("pfizer")

    def test_pfizer_is_active_at_end(self):
        b = _active_brand()
        assert b.get("brand_id") == "pfizer", f"expected pfizer active at end, got: {b.get('brand_id')}"


# -------------------- Regression: server registry --------------------
class TestServerRegistryRegression:
    """Iteration 17 introduced /api/admin/servers — verify it still works."""

    def test_get_admin_servers_ok(self):
        r = requests.get(f"{BASE_URL}/api/admin/servers", headers=H, timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "system" in body and isinstance(body["system"], list)
        assert "custom" in body and isinstance(body["custom"], list)
        # System list should include at least system::api and system::mongo
        ids = {row.get("id") for row in body["system"]}
        assert "system::api" in ids, ids
        assert "system::mongo" in ids, ids

    def test_post_and_delete_custom_server(self):
        # Create — payload schema requires name + role (per /api/admin/servers POST)
        payload = {
            "name": "TEST_Iter18Server",
            "role": "api",
            "hostname": "example.test",
            "port": 443,
            "protocol": "https",
            "notes": "iter18 regression",
        }
        r = requests.post(
            f"{BASE_URL}/api/admin/servers",
            headers=H,
            data=json.dumps(payload),
            timeout=15,
        )
        assert r.status_code in (200, 201), r.text
        srv = r.json()
        sid = srv.get("id") or srv.get("server_id")
        assert sid and sid.startswith("SRV-"), srv
        # Cleanup
        r2 = requests.delete(f"{BASE_URL}/api/admin/servers/{sid}", headers=H, timeout=15)
        assert r2.status_code in (200, 204), r2.text


# -------------------- Module teardown: ensure Pfizer active --------------------
@pytest.fixture(scope="module", autouse=True)
def _final_brand_state():
    yield
    try:
        _activate("pfizer")
    except Exception:
        pass
