"""Iteration 36 — Routing-rules engine + enterprise adapter framework.

Covers:
  · Routing rules wired into POST /api/enterprise-tms/dynamic-route
    (block / prefer_carrier / force_mode actions, audit trail)
  · 9 integration adapters + Freight Audit ML
  · adapter-status endpoint
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://clean-logistics-dash.preview.emergentagent.com").rstrip("/")
TOKEN = "test_session_admin_1"
HDRS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
PICKUP = "2026-02-15"

TMS = f"{BASE_URL}/api/enterprise-tms"
ADP = f"{BASE_URL}/api/enterprise-adapters"


# ---------- helpers --------------------------------------------------------
def _create_rule(payload):
    r = requests.post(f"{TMS}/routing-rules", json=payload, headers=HDRS, timeout=20)
    assert r.status_code in (200, 201), f"create rule failed {r.status_code}: {r.text[:200]}"
    return r.json()


def _delete_rule(rule_id):
    if rule_id:
        try:
            requests.delete(f"{TMS}/routing-rules/{rule_id}", headers=HDRS, timeout=10)
        except Exception:
            pass


# =================== ROUTING RULE ENGINE ===================================
class TestRoutingRulesEngine:
    def test_block_rule_hazmat_ca(self):
        rule = _create_rule({
            "name": "TEST_block_hazmat_CA",
            "priority": 10,
            "action": "block",
            "match_hazmat": True,
            "match_destination_region": "CA",
            "enabled": True,
        })
        rid = rule.get("rule_id") or rule.get("id") or rule.get("_id")
        try:
            r = requests.post(f"{TMS}/dynamic-route", json={
                "origin": "Newark, NJ",
                "destination": "Los Angeles, CA",
                "weight_lbs": 18000, "pickup_date": PICKUP,
                "hazmat_un": "UN1203",
            }, headers=HDRS, timeout=30)
            assert r.status_code == 200, r.text[:300]
            data = r.json()
            assert data.get("blocked") is True, f"expected blocked=true: {data}"
            assert isinstance(data.get("applied_rules"), list), "applied_rules missing"
            assert len(data["applied_rules"]) >= 1
            assert data.get("options") in ([], None) or data.get("options") == []
            assert data.get("recommendation") in (None, {}, [])
        finally:
            _delete_rule(rid)

    def test_normal_route_no_block(self):
        r = requests.post(f"{TMS}/dynamic-route", json={
            "origin": "Chicago, IL",
            "destination": "Dallas, TX",
            "weight_lbs": 22000, "pickup_date": PICKUP,
        }, headers=HDRS, timeout=30)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert data.get("blocked") in (False, None)
        assert isinstance(data.get("options"), list) and len(data["options"]) > 0
        rec = data.get("recommendation")
        assert rec, "recommendation missing"
        assert rec.get("mode")
        assert rec.get("rate_usd") is not None

    def test_routing_decisions_audit_trail(self):
        r = requests.get(f"{TMS}/routing-decisions", headers=HDRS, timeout=20)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        # Should be list or dict containing list
        items = body if isinstance(body, list) else (body.get("items") or body.get("decisions") or [])
        assert isinstance(items, list)

    def test_prefer_carrier_rule(self):
        rule = _create_rule({
            "name": "TEST_prefer_XPO",
            "priority": 20,
            "action": "prefer_carrier",
            "preferred_carrier_name": "XPO Logistics",
            "enabled": True,
        })
        rid = rule.get("rule_id") or rule.get("id") or rule.get("_id")
        try:
            r = requests.post(f"{TMS}/dynamic-route", json={
                "origin": "Atlanta, GA",
                "destination": "Memphis, TN",
                "weight_lbs": 15000, "pickup_date": PICKUP,
            }, headers=HDRS, timeout=30)
            assert r.status_code == 200, r.text[:300]
            data = r.json()
            opts = data.get("options") or []
            found = any("XPO Logistics" in (o.get("preferred_carriers") or []) for o in opts)
            assert found, f"XPO Logistics not in any preferred_carriers: {opts}"
        finally:
            _delete_rule(rid)

    def test_force_mode_rule(self):
        rule = _create_rule({
            "name": "TEST_force_intermodal_IL",
            "priority": 30,
            "action": "force_mode",
            "forced_mode": "Intermodal",
            "match_origin_region": "IL",
            "enabled": True,
        })
        rid = rule.get("rule_id") or rule.get("id") or rule.get("_id")
        try:
            r = requests.post(f"{TMS}/dynamic-route", json={
                "origin": "Chicago, IL",
                "destination": "Dallas, TX",
                "weight_lbs": 22000, "pickup_date": PICKUP,
            }, headers=HDRS, timeout=30)
            assert r.status_code == 200, r.text[:300]
            data = r.json()
            opts = data.get("options") or []
            # Acceptance: either all options Intermodal OR forced_mode field present
            modes = {(o.get("mode") or "").lower() for o in opts}
            forced = data.get("forced_mode") or data.get("recommendation", {}).get("mode")
            ok = (modes == {"intermodal"}) or (str(forced or "").lower() == "intermodal")
            assert ok, f"force_mode not honored. modes={modes}, forced={forced}"
        finally:
            _delete_rule(rid)


# =================== ADAPTERS ==============================================
class TestAdapters:
    def test_mileage_haversine(self):
        r = requests.post(f"{ADP}/mileage", json={
            "origin": "Chicago, IL", "destination": "Dallas, TX"
        }, headers=HDRS, timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d["source"] == "haversine_fallback"
        assert d["live"] is False
        assert 700 <= d["miles"] <= 1200, f"miles out of expected range: {d['miles']}"

    def test_parcel_rater_cheapest_badge(self):
        r = requests.post(f"{ADP}/parcel-rate", json={
            "origin_zip": "60601", "destination_zip": "75201", "weight_lbs": 12
        }, headers=HDRS, timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        rates = d.get("rates", [])
        assert len(rates) == 6, f"expected 6 rates, got {len(rates)}"
        assert "CHEAPEST" in (rates[0].get("badges") or [])

    def test_gps_tracking_graceful(self):
        r = requests.post(f"{ADP}/gps-track", json={
            "booking_id": "TEST-BOOKING-XYZ"
        }, headers=HDRS, timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d.get("source") in ("driver_pwa", "none", "project44", "fourkites")

    def test_edi_inbound_204_with_990_ack(self):
        r = requests.post(f"{ADP}/edi/inbound", json={
            "edi_type": "204",
            "sender_isa": "SHIPPER1",
            "receiver_isa": "TENNANT",
            "payload": {"shipment_id": "S-TEST-1", "items": []},
        }, headers=HDRS, timeout=20)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d["ok"] is True
        assert d["auto_ack_sent"] is True

        # Check log has both 204 inbound + 990 outbound
        r2 = requests.get(f"{ADP}/edi/log", headers=HDRS, timeout=20)
        assert r2.status_code == 200, r2.text[:300]
        items = r2.json().get("items", [])
        types_dirs = {(i.get("edi_type"), i.get("direction")) for i in items}
        assert ("204", "inbound") in types_dirs
        assert ("990", "outbound") in types_dirs

    def test_edi_invalid_type_400(self):
        r = requests.post(f"{ADP}/edi/inbound", json={
            "edi_type": "999",
            "sender_isa": "X", "receiver_isa": "Y", "payload": {}
        }, headers=HDRS, timeout=20)
        assert r.status_code == 400

    def test_wms_wave_release_and_list(self):
        r = requests.post(f"{ADP}/wms/wave", json={
            "facility": "TEST-FAC-1",
            "order_ids": ["O1", "O2", "O3"]
        }, headers=HDRS, timeout=20)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d.get("wave_id")
        assert d.get("live") is False
        assert d.get("pick_tasks_generated") == 3

        r2 = requests.get(f"{ADP}/wms/waves", headers=HDRS, timeout=20)
        assert r2.status_code == 200
        items = r2.json().get("items", [])
        assert any(w.get("wave_id") == d["wave_id"] for w in items)

    def test_dat_spot_fallback(self):
        r = requests.post(f"{ADP}/dat-spot", json={
            "origin": "Chicago, IL", "destination": "Dallas, TX",
            "equipment": "Dry Van"
        }, headers=HDRS, timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d.get("source") in ("historical_median", "none", "dat_one")

    def test_freight_audit_ml(self):
        r = requests.post(f"{ADP}/freight-audit-ml", json={
            "window_days": 180, "z_threshold": 2.0
        }, headers=HDRS, timeout=60)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        for key in ("bookings_audited", "lanes_modeled", "flags", "anomalies"):
            assert key in d, f"missing key: {key}"
        assert d.get("model") == "modified_z_score_mad"
        assert isinstance(d.get("anomalies"), list)

    def test_adapter_status(self):
        r = requests.get(f"{ADP}/adapter-status", headers=HDRS, timeout=20)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        ads = d.get("adapters", {})
        expected = {"pcmiler", "openrouteservice", "fedex", "ups", "project44",
                    "fourkites", "sps_commerce", "autostore", "dat_one", "freight_audit_ml"}
        assert set(ads.keys()) == expected, f"missing keys: {expected - set(ads.keys())}"
        assert ads["freight_audit_ml"] == "live"
        assert d.get("live_count") == 1
        assert d.get("total") == 10
        # Others should be absent
        for k in expected - {"freight_audit_ml"}:
            assert ads[k] == "absent", f"{k} expected absent but got {ads[k]}"
