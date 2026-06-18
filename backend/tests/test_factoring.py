"""Backend regression tests for /api/factoring/* (Freight Factoring + ABL)."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL") or os.environ.get("EXTERNAL_URL")
if not BASE_URL:
    # Read from frontend env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().strip('"')
                break
BASE_URL = BASE_URL.rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_TOKEN = "test_session_admin_1"
H = {"Authorization": f"Bearer {ADMIN_TOKEN}", "Content-Type": "application/json"}


# ============== CATALOG ==============
def test_list_factors_returns_8():
    r = requests.get(f"{API}/factoring/factors", headers=H, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["count"] == 8
    items = data["items"]
    names = {f["name"] for f in items}
    expected = {
        "Truckstop Capital", "On The Spot Capital", "BlueChip Financial",
        "Apex Capital", "Coyote / RXO Financial", "Rapid Finance",
        "Factor Network", "Republic Business Credit"
    }
    assert names == expected
    # Midwest tagging
    midwest = {f["name"] for f in items if f.get("midwest")}
    assert midwest == {"Truckstop Capital", "On The Spot Capital", "BlueChip Financial"}
    # Fee ranges
    by = {f["factor_id"]: f for f in items}
    assert by["truckstop-capital"]["fee_pct_min"] == 2.5 and by["truckstop-capital"]["fee_pct_max"] == 3.5
    assert by["on-the-spot"]["fee_pct_min"] == 2.5 and by["on-the-spot"]["fee_pct_max"] == 3.0
    assert by["apex-capital"]["fee_pct_max"] == 4.0
    assert by["coyote-rxo"]["fee_pct_min"] == 2.0
    assert by["rapid-finance"]["fee_pct_min"] == 3.0
    assert by["republic-business-credit"]["fee_pct_min"] == 2.0


def test_get_factor_detail_and_404():
    r = requests.get(f"{API}/factoring/factors/on-the-spot", headers=H, timeout=10)
    assert r.status_code == 200
    assert r.json()["name"] == "On The Spot Capital"
    r2 = requests.get(f"{API}/factoring/factors/does-not-exist", headers=H, timeout=10)
    assert r2.status_code == 404


# ============== STAGES ==============
def test_list_stages_returns_5():
    r = requests.get(f"{API}/factoring/stages", headers=H, timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert data["count"] == 5
    stages = data["stages"]
    fees = [s["fee_pct"] for s in stages]
    assert fees == [3.5, 3.0, 2.75, 2.5, 2.0]
    ranges = [s["month_range"] for s in stages]
    assert ranges[0].startswith("Month 1")
    assert "12" in ranges[-1]


def test_recommend_stage_stage1_midwest_priority():
    r = requests.post(f"{API}/factoring/recommend-stage", headers=H,
                       json={"monthly_loads": 40}, timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert body["stage"]["label"].startswith("Stage 1")
    assert body["recommended_factors"], "expected recommended factors"
    # Midwest-priority sort
    first = body["recommended_factors"][0]
    assert first.get("midwest") is True, f"expected first recommendation to be Midwest, got {first['name']}"


# ============== COMPARE COST ==============
def test_compare_cost_abl_lowest():
    r = requests.post(f"{API}/factoring/compare-cost", headers=H,
                       json={"monthly_loads": 80, "avg_invoice_usd": 1320,
                             "avg_margin_usd_per_load": 220, "payment_terms_days": 14},
                       timeout=10)
    assert r.status_code == 200
    data = r.json()
    rows = data["rows"]
    assert len(rows) == 4
    kinds = [r["kind"] for r in rows]
    assert set(kinds) == {"spot", "recourse", "non-recourse", "abl"}
    assert data["recommended_kind"] == "abl"
    # ABL is_interest flag
    abl = next(r for r in rows if r["kind"] == "abl")
    assert abl["is_interest"] is True
    assert abl["is_best"] is True


# ============== STRATEGIES ==============
def test_list_strategies_returns_4():
    r = requests.get(f"{API}/factoring/strategies", headers=H, timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert data["count"] == 4
    titles = {s["title"] for s in data["strategies"]}
    assert titles == {
        "Multi-Factor Redundancy",
        "Shipper Payment Term Compression",
        "Reserve Release Negotiation",
        "Shipper Concentration Control",
    }
    for s in data["strategies"]:
        assert len(s["implementation"]) >= 4


# ============== OUTREACH ==============
BROKER_NAME = "TEST_OriseiPytest LLC"

def test_outreach_generate_contains_personal_data():
    payload = {
        "factor_id": "on-the-spot",
        "broker_name": BROKER_NAME,
        "contact_name": "Test Contact",
        "current_loads_per_month": 25,
        "projected_3mo_loads": 80,
        "projected_6mo_loads": 250,
        "top_shippers": ["SUPERVALU", "Target", "3M"],
        "lanes": ["MPLS -> Chicago", "MPLS -> Milwaukee"],
    }
    r = requests.post(f"{API}/factoring/outreach/generate", headers=H, json=payload, timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "subject" in data and "body" in data and "mailto" in data
    assert BROKER_NAME in data["subject"]
    assert BROKER_NAME in data["body"]
    assert "On The Spot Capital" in data["body"]
    assert "SUPERVALU" in data["body"]
    assert "MPLS -> Chicago" in data["body"]


def test_outreach_ai_polish_graceful():
    payload = {
        "factor_id": "apex-capital",
        "broker_name": BROKER_NAME,
        "contact_name": "Test Contact",
        "current_loads_per_month": 10,
        "projected_3mo_loads": 30,
        "projected_6mo_loads": 90,
        "top_shippers": ["Target"],
        "lanes": ["MPLS -> Chicago"],
    }
    r = requests.post(f"{API}/factoring/outreach/ai-polish", headers=H, json=payload, timeout=60)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "body" in data and "subject" in data
    assert "ai_polished" in data
    assert isinstance(data["body"], str) and len(data["body"]) > 50


# ============== APPLICATIONS ==============
created_app_id = None

def test_create_application_and_list():
    global created_app_id
    payload = {
        "factor_id": "bluechip-financial",
        "contact_name": "Test Person",
        "contact_email": "test@acmecorp.com",
        "status": "preparing",
        "notes": "TEST application from pytest",
        "monthly_volume_target_usd": 50000,
    }
    r = requests.post(f"{API}/factoring/applications", headers=H, json=payload, timeout=15)
    assert r.status_code == 200, r.text
    doc = r.json()
    assert doc["application_id"].startswith("FAPP-")
    assert doc["factor_id"] == "bluechip-financial"
    created_app_id = doc["application_id"]

    r2 = requests.get(f"{API}/factoring/applications", headers=H, timeout=10)
    assert r2.status_code == 200
    apps = r2.json()["items"]
    found = next((a for a in apps if a["application_id"] == created_app_id), None)
    assert found, "newly created application missing in list"
    assert found.get("factor_name") == "BlueChip Financial"


def test_update_and_delete_application():
    assert created_app_id, "create test must run first"
    upd = {
        "factor_id": "bluechip-financial",
        "status": "sent",
        "notes": "TEST update",
    }
    r = requests.put(f"{API}/factoring/applications/{created_app_id}", headers=H, json=upd, timeout=10)
    assert r.status_code == 200
    assert r.json()["status"] == "sent"
    rd = requests.delete(f"{API}/factoring/applications/{created_app_id}", headers=H, timeout=10)
    assert rd.status_code == 200


# ============== SUBMISSIONS ==============
created_sub_id = None

def test_create_submission_with_calc():
    global created_sub_id
    payload = {
        "factor_id": "on-the-spot",
        "invoice_id": f"TEST-INV-{int(time.time())}",
        "customer_name": "TEST Customer",
        "invoice_usd": 1320.00,
        "carrier_cost_usd": 1000.00,
        "payment_terms_days": 14,
    }
    r = requests.post(f"{API}/factoring/submissions", headers=H, json=payload, timeout=15)
    assert r.status_code == 200, r.text
    doc = r.json()
    assert doc["submission_id"].startswith("FSUB-")
    # fee_pct = avg(2.5,3.0) = 2.75 → fee = 1320*0.0275 = 36.3
    assert abs(doc["fee_usd"] - 36.3) < 0.05
    # advance = 1320*.85 = 1122.0
    assert abs(doc["advance_usd"] - 1122.0) < 0.05
    # reserve = 1320 - 1122 = 198.0
    assert abs(doc["reserve_usd"] - 198.0) < 0.05
    # broker take home = 1122 - 1000 = 122
    assert abs(doc["broker_take_home_usd"] - 122.0) < 0.05
    created_sub_id = doc["submission_id"]


def test_update_submission_status_and_list():
    assert created_sub_id
    r = requests.post(f"{API}/factoring/submissions/{created_sub_id}/status",
                       headers=H, json={"status": "funded"}, timeout=10)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "funded"

    rl = requests.get(f"{API}/factoring/submissions", headers=H, timeout=10)
    assert rl.status_code == 200
    items = rl.json()["items"]
    found = next((s for s in items if s["submission_id"] == created_sub_id), None)
    assert found is not None
    assert found["status"] == "funded"
    assert found.get("factor_name") == "On The Spot Capital"


def test_invalid_status_rejected():
    assert created_sub_id
    r = requests.post(f"{API}/factoring/submissions/{created_sub_id}/status",
                       headers=H, json={"status": "garbage"}, timeout=10)
    assert r.status_code == 400


def test_delete_submission_cleanup():
    assert created_sub_id
    r = requests.delete(f"{API}/factoring/submissions/{created_sub_id}", headers=H, timeout=10)
    assert r.status_code == 200


# ============== DASHBOARD ==============
def test_dashboard_aggregates():
    r = requests.get(f"{API}/factoring/dashboard", headers=H, timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert "totals_90d" in data
    assert "stage" in data
    assert "applications_summary" in data
    assert "by_factor" in data
    assert isinstance(data["totals_90d"]["submissions"], int)
