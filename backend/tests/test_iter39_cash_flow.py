"""Iteration 39 — Cash Flow Command Center + Workflow auto-route hook.

Tests for /api/cash-flow/* and the carrier_assigned auto-route into
cash_flow_factor_proposals via /api/orisei/workflow/checklist/{id}/mark.
"""
import os
import time
import requests

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://clean-logistics-dash.preview.emergentagent.com",
).rstrip("/")


# ---------- position + bank balance ----------
def test_position_returns_required_fields(admin_client):
    r = admin_client.get(f"{BASE_URL}/api/cash-flow/position")
    assert r.status_code == 200, r.text
    d = r.json()
    for f in ("bank_balance_usd", "accounts_receivable_usd",
              "accounts_payable_usd", "available_to_deploy_usd",
              "loads_can_take", "health"):
        assert f in d, f"missing {f}"
    assert d["health"] in {"strong", "healthy", "tight", "critical"}
    assert isinstance(d["loads_can_take"], int)


def test_bank_balance_persists(admin_client):
    # Set to a known value
    r = admin_client.post(f"{BASE_URL}/api/cash-flow/bank-balance",
                          json={"balance_usd": 8000.0, "source": "manual"})
    assert r.status_code == 200, r.text
    assert r.json()["bank_balance_usd"] == 8000.0
    # GET reflects it
    r2 = admin_client.get(f"{BASE_URL}/api/cash-flow/position")
    assert r2.status_code == 200
    assert r2.json()["bank_balance_usd"] == 8000.0


# ---------- qualify-load ----------
def test_qualify_load_target(admin_client):
    r = admin_client.post(f"{BASE_URL}/api/cash-flow/qualify-load",
                          json={"customer_rate_usd": 1500,
                                "carrier_cost_usd": 1050,
                                "payment_terms_days": 14,
                                "shipper_name": "Target"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["forecast_margin_usd"] == 450.0
    assert d["forecast_margin_pct"] == 30.0
    assert d["shipper_credit"]["tier"] in {"A+", "A"}
    # Tier-1 bonus signal expected in factors
    assert any("Tier-1" in f for f in d["shipper_credit"]["factors"])
    assert isinstance(d["can_self_fund"], bool)
    assert isinstance(d["needs_factoring"], bool)
    assert isinstance(d["actions"], list) and len(d["actions"]) > 0


# ---------- auto-route factor ----------
def test_auto_route_factor(admin_client):
    r = admin_client.post(f"{BASE_URL}/api/cash-flow/auto-route-factor",
                          json={"invoice_usd": 1500, "carrier_cost_usd": 1050,
                                "payment_terms_days": 14,
                                "shipper_credit_score": 85})
    assert r.status_code == 200, r.text
    d = r.json()
    best = d["best"]
    assert best is not None
    for f in ("factor_id", "name", "fee_pct", "advance_usd"):
        assert f in best
    assert "broker_take_home_usd" in d
    assert "covers_carrier_cost" in d


# ---------- dynamic discount ----------
def test_dynamic_discount_math(admin_client):
    r = admin_client.post(f"{BASE_URL}/api/cash-flow/dynamic-discount",
                          json={"waiting_carriers_usd": 15000,
                                "available_cash_usd": 10000,
                                "proposed_discount_pct": 5})
    assert r.status_code == 200, r.text
    d = r.json()
    # 5% of 15000 = 750
    assert d["total_discount_savings_usd"] == 750.0
    assert "expected_cash_outlay_usd" in d
    assert "coverage_ratio" in d
    assert isinstance(d["carrier_pitch"], str) and d["carrier_pitch"]


# ---------- scenario ----------
def test_scenario_planner(admin_client):
    r = admin_client.post(f"{BASE_URL}/api/cash-flow/scenario",
                          json={"target_loads_per_week": 200,
                                "avg_invoice_usd": 1280,
                                "avg_margin_usd_per_load": 230,
                                "payment_terms_days": 14,
                                "hire_dispatcher": True})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["monthly_loads"] == int(200 * 4.33)  # 866
    assert "gross_margin_usd_monthly" in d
    assert "working_capital_required_usd" in d
    assert d["best_funding_method"] == "ABL (interest)"
    assert "net_margin_after_funding_usd" in d


# ---------- shipper term analysis ----------
def test_shipper_term_analysis(admin_client):
    r = admin_client.get(f"{BASE_URL}/api/cash-flow/shipper-term-analysis")
    assert r.status_code == 200, r.text
    d = r.json()
    assert "candidates" in d and isinstance(d["candidates"], list)
    assert "total_potential_savings_usd" in d
    assert "candidate_count" in d
    # ranked descending by potential_savings_usd
    savings = [c["potential_savings_usd"] for c in d["candidates"]]
    assert savings == sorted(savings, reverse=True)


# ---------- shipper credit by customer ----------
def test_shipper_credit_for_real_customer(admin_client):
    custs = admin_client.get(f"{BASE_URL}/api/orisei/customers").json()
    rows = custs if isinstance(custs, list) else custs.get("items", [])
    if not rows:
        # Create a TEST customer
        cr = admin_client.post(f"{BASE_URL}/api/orisei/customers",
                               json={"name": "TEST_Target Stores",
                                     "email": "ap@acmecorp.com",
                                     "payment_terms": "Net 30"})
        assert cr.status_code in (200, 201), cr.text
        cid = cr.json()["customer_id"]
    else:
        cid = rows[0]["customer_id"]
    r = admin_client.get(f"{BASE_URL}/api/cash-flow/shipper-credit/{cid}")
    assert r.status_code == 200, r.text
    d = r.json()
    assert "score" in d
    assert d["tier"] in {"A+", "A", "B", "C", "D", "F", "unknown"}
    assert "risk" in d and "factors" in d and "recommendation" in d


# ---------- workflow hook → factor proposal ----------
def test_workflow_carrier_assigned_creates_proposal(admin_client):
    # Find any existing booking
    bks = admin_client.get(f"{BASE_URL}/api/brokerage/bookings").json()
    rows = bks if isinstance(bks, list) else bks.get("items", bks.get("rows", bks.get("bookings", [])))
    booked_id = None
    if rows:
        booked_id = rows[0].get("booked_id")
    if not booked_id:
        # Book a load through the /loads/book endpoint as fallback
        loads = admin_client.get(f"{BASE_URL}/api/brokerage/boards/dat/loads").json()
        cands = loads if isinstance(loads, list) else loads.get("items", [])
        assert cands, "no boards loads available to book"
        ld = cands[0]
        br = admin_client.post(f"{BASE_URL}/api/brokerage/loads/book",
                                json={"board_id": "dat", "load_id": ld["load_id"]})
        assert br.status_code in (200, 201), br.text
        booked_id = br.json().get("booked_id") or br.json().get("id")
    assert booked_id, "could not get a booked_id"
    _ = time.time()  # silence unused

    # Mark carrier_assigned
    mk = admin_client.post(
        f"{BASE_URL}/api/orisei/workflow/checklist/{booked_id}/mark",
        json={"stage_id": "carrier_assigned"})
    assert mk.status_code == 200, mk.text

    # Should appear in factor-proposals
    fp = admin_client.get(f"{BASE_URL}/api/cash-flow/factor-proposals")
    assert fp.status_code == 200, fp.text
    items = fp.json()["items"]
    match = [p for p in items if p.get("booked_id") == booked_id]
    assert match, f"no proposal for {booked_id}"
    prop = match[0]
    assert prop.get("best_factor") is not None
    assert "factor_id" in prop["best_factor"]
