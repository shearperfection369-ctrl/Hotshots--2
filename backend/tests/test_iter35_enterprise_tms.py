"""Enterprise TMS module backend tests (iteration 35)."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://clean-logistics-dash.preview.emergentagent.com").rstrip("/")
ADMIN_TOKEN = "test_session_admin_1"
H = {"Authorization": f"Bearer {ADMIN_TOKEN}", "Content-Type": "application/json"}
PREFIX = f"{BASE_URL}/api/enterprise-tms"


def _ok(r, expected=200):
    assert r.status_code == expected, f"{r.status_code} → {r.text[:300]}"
    return r.json()


# ---------------- Coverage / Integration / Hazmat catalog ----------------
class TestCoverageAndCatalogs:
    def test_coverage(self):
        d = _ok(requests.get(f"{PREFIX}/coverage", headers=H))
        for k in ("total_requirements", "live", "partial", "stub", "coverage_pct", "items"):
            assert k in d
        assert d["total_requirements"] == len(d["items"]) > 0

    def test_integration_registry(self):
        d = _ok(requests.get(f"{PREFIX}/integration-registry", headers=H))
        assert d["total"] == 13, f"expected 13 connectors, got {d['total']}"
        assert len(d["items"]) == 13
        slugs = {i["slug"] for i in d["items"]}
        for must in ("sap_s4hana", "sap_ewm", "project44", "sps_commerce", "dat_one"):
            assert must in slugs

    def test_hazmat_catalog(self):
        d = _ok(requests.get(f"{PREFIX}/hazmat-catalog", headers=H))
        assert d["count"] >= 40, f"expected >=40 hazmat entries, got {d['count']}"
        un_set = {i["un_number"] for i in d["items"]}
        assert "UN1203" in un_set

    def test_hazmat_single_lookup(self):
        d = _ok(requests.get(f"{PREFIX}/hazmat/UN1203", headers=H))
        assert d["known"] is True
        assert d["proper_shipping_name"] == "Gasoline"
        assert d["hazard_class"] == "3"

    def test_hazmat_batch(self):
        d = _ok(requests.post(f"{PREFIX}/hazmat/batch", headers=H,
                              json={"un_numbers": ["UN1203", "UN9999"]}))
        assert len(d["items"]) == 2
        assert d["items"][0]["known"] is True
        assert d["items"][1]["known"] is False


# ---------------- Cartonize / Consolidate / Dynamic Route ----------------
class TestEngines:
    def test_cartonize_carton(self):
        d = _ok(requests.post(f"{PREFIX}/cartonize", headers=H, json={
            "items": [{"sku": "A", "qty": 2, "length_in": 10, "width_in": 8,
                       "height_in": 6, "weight_lbs": 10}]
        }))
        assert d["recommendation"] in ("CARTON", "PALLETIZE")

    def test_cartonize_palletize(self):
        d = _ok(requests.post(f"{PREFIX}/cartonize", headers=H, json={
            "items": [{"sku": "B", "qty": 20, "length_in": 24, "width_in": 18,
                       "height_in": 14, "weight_lbs": 30}]
        }))
        assert d["recommendation"] == "PALLETIZE"
        assert d["pallets_required"] >= 1

    def test_consolidate(self):
        payload = {"candidates": [
            {"origin": "Chicago, IL", "destination": "Dallas, TX",
             "pickup_date": "2026-02-01", "weight_lbs": 8000, "cube_ft": 600},
            {"origin": "Chicago, IL", "destination": "Dallas, TX",
             "pickup_date": "2026-02-01", "weight_lbs": 12000, "cube_ft": 900},
            {"origin": "Chicago, IL", "destination": "Dallas, TX",
             "pickup_date": "2026-02-02", "weight_lbs": 7000, "cube_ft": 500},
        ]}
        d = _ok(requests.post(f"{PREFIX}/consolidate", headers=H, json=payload))
        assert d["input_shipments"] == 3
        assert d["consolidated_loads"] == 1
        assert d["savings_pct"] > 60

    def test_dynamic_route(self):
        d = _ok(requests.post(f"{PREFIX}/dynamic-route", headers=H, json={
            "origin": "Chicago, IL", "destination": "Dallas, TX",
            "equipment": "Dry Van", "weight_lbs": 22000,
            "pickup_date": "2026-02-01"
        }))
        assert len(d["options"]) >= 1
        assert d["recommendation"] is not None
        assert "rate_usd" in d["recommendation"]

    def test_mode_rate_shop_with_badges(self):
        d = _ok(requests.post(f"{PREFIX}/mode-rate-shop", headers=H, json={
            "origin": "Los Angeles, CA", "destination": "Newark, NJ",
            "weight_lbs": 18000, "pieces": 4, "equipment": "Dry Van"
        }))
        assert len(d["options"]) >= 2
        modes = {o["mode"] for o in d["options"]}
        assert "Truckload" in modes
        badges_seen = {b for o in d["options"] for b in o.get("badges", [])}
        assert "CHEAPEST" in badges_seen


# ---------------- Rate benchmark / Global vis / Regional / KPIs ----------------
class TestVisibilityAndBenchmark:
    def test_rate_benchmark(self):
        r = requests.get(f"{PREFIX}/rate-benchmark", headers=H, params={
            "origin_state": "IL", "destination_state": "TX",
            "equipment": "Dry Van"
        })
        d = _ok(r)
        # Either has samples or returns 'note' for empty data
        if d.get("samples", 0) > 0:
            assert d["verdict"] in ("ALIGNED", "OVER", "UNDER")
        else:
            assert "note" in d

    def test_global_visibility(self):
        d = _ok(requests.get(f"{PREFIX}/global-visibility", headers=H))
        for region in ("NAM", "EMEA", "LATAM", "APAC"):
            assert region in d["by_region"]
        assert "total_active_shipments" in d

    def test_regional_network(self):
        d = _ok(requests.get(f"{PREFIX}/regional-network", headers=H))
        assert len(d["regions"]) == 4
        names = {r["region"] for r in d["regions"]}
        assert names == {"NAM", "EMEA", "LATAM", "APAC"}

    def test_global_kpis(self):
        d = _ok(requests.get(f"{PREFIX}/kpis/global", headers=H))
        for k in ("otif_pct", "on_time_pct", "cost_to_serve_pct"):
            assert k in d


# ---------------- Routing Rules CRUD ----------------
class TestRoutingRulesCRUD:
    rule_id = None

    def test_create_routing_rule(self):
        d = _ok(requests.post(f"{PREFIX}/routing-rules", headers=H, json={
            "name": "TEST_Rule_Iter35", "action": "prefer_carrier",
            "preferred_carrier_name": "XPO", "priority": 50
        }))
        assert d["name"] == "TEST_Rule_Iter35"
        assert d["rule_id"].startswith("RR-")
        TestRoutingRulesCRUD.rule_id = d["rule_id"]

    def test_list_routing_rules(self):
        d = _ok(requests.get(f"{PREFIX}/routing-rules", headers=H))
        ids = [r["rule_id"] for r in d["items"]]
        assert TestRoutingRulesCRUD.rule_id in ids

    def test_update_routing_rule(self):
        d = _ok(requests.put(f"{PREFIX}/routing-rules/{TestRoutingRulesCRUD.rule_id}",
                             headers=H, json={
            "name": "TEST_Rule_Iter35_v2", "action": "prefer_carrier",
            "preferred_carrier_name": "ODFL", "priority": 75
        }))
        assert d["name"] == "TEST_Rule_Iter35_v2"
        assert d["preferred_carrier_name"] == "ODFL"

    def test_delete_routing_rule(self):
        d = _ok(requests.delete(f"{PREFIX}/routing-rules/{TestRoutingRulesCRUD.rule_id}",
                                headers=H))
        assert d["status"] == "deactivated"


# ---------------- Consolidation Groups CRUD ----------------
class TestConsolidationGroupsCRUD:
    group_id = None

    def test_create(self):
        d = _ok(requests.post(f"{PREFIX}/consolidation-groups", headers=H, json={
            "name": "TEST_CG_Iter35", "lane_origin": "Chicago, IL",
            "lane_destination": "Dallas, TX", "pickup_window_days": ["Mon", "Wed"]
        }))
        assert d["group_id"].startswith("CG-")
        TestConsolidationGroupsCRUD.group_id = d["group_id"]

    def test_list(self):
        d = _ok(requests.get(f"{PREFIX}/consolidation-groups", headers=H))
        ids = [g["group_id"] for g in d["items"]]
        assert TestConsolidationGroupsCRUD.group_id in ids

    def test_delete(self):
        d = _ok(requests.delete(
            f"{PREFIX}/consolidation-groups/{TestConsolidationGroupsCRUD.group_id}",
            headers=H))
        assert d["status"] == "deactivated"


# ---------------- Hazmat Profiles CRUD ----------------
class TestHazmatProfilesCRUD:
    profile_id = None

    def test_create(self):
        d = _ok(requests.post(f"{PREFIX}/hazmat-profiles", headers=H, json={
            "customer_id": "TEST_CUST_IT35", "customer_name": "TEST_HZP",
            "un_numbers": ["UN1203", "UN1993"],
            "emergency_contact_name": "Ops Center",
            "emergency_contact_phone": "+1-800-555-0100"
        }))
        assert d["profile_id"].startswith("HZP-")
        assert d["compliance_score"] == 100.0
        assert len(d["validated_un_numbers"]) == 2
        TestHazmatProfilesCRUD.profile_id = d["profile_id"]

    def test_list(self):
        d = _ok(requests.get(f"{PREFIX}/hazmat-profiles", headers=H))
        ids = [p["profile_id"] for p in d["items"]]
        assert TestHazmatProfilesCRUD.profile_id in ids

    def test_delete(self):
        d = _ok(requests.delete(
            f"{PREFIX}/hazmat-profiles/{TestHazmatProfilesCRUD.profile_id}",
            headers=H))
        assert d["status"] == "deactivated"


# ---------------- Inbound CRUD + status ----------------
class TestInbound:
    inbound_id = None

    def test_create(self):
        d = _ok(requests.post(f"{PREFIX}/inbound", headers=H, json={
            "supplier_name": "TEST_Acme_Mfg", "destination_dc": "Atlanta DC",
            "expected_arrival": "2026-02-15", "mode": "TL",
            "weight_lbs": 14000, "carrier_name": "XPO"
        }))
        assert d["inbound_id"].startswith("INB-")
        assert d["status"] == "booked"
        TestInbound.inbound_id = d["inbound_id"]

    def test_list(self):
        d = _ok(requests.get(f"{PREFIX}/inbound", headers=H))
        ids = [i["inbound_id"] for i in d["items"]]
        assert TestInbound.inbound_id in ids

    def test_status_update(self):
        d = _ok(requests.post(
            f"{PREFIX}/inbound/{TestInbound.inbound_id}/status",
            headers=H, json={"status": "in_transit", "location": "Memphis, TN"}))
        assert d["status"] == "in_transit"


# ---------------- SAP IDoc ----------------
class TestSapIdoc:
    def test_idoc_inbound_delvry03(self):
        d = _ok(requests.post(f"{PREFIX}/sap/idoc/inbound", headers=H,
                              json={"idoc_type": "DELVRY03",
                                    "delivery_no": "TEST_8000000001"}))
        assert d["status"] == "queued"
        assert d["idoc_id"].startswith("IDOC-")

    def test_idoc_inbound_invalid(self):
        r = requests.post(f"{PREFIX}/sap/idoc/inbound", headers=H,
                          json={"idoc_type": "BOGUS"})
        assert r.status_code == 400

    def test_idoc_queue(self):
        d = _ok(requests.get(f"{PREFIX}/sap/idoc/queue", headers=H))
        assert "items" in d
