"""Iteration 83: Dynamic Pricing, Ops Truth, Match Playbook, Insurance Binders, Portal Live ETA."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://clean-logistics-dash.preview.emergentagent.com").rstrip("/")
ADMIN_TOKEN = "test_session_admin_1"
PORTAL_TOKEN = "HXACT0uXu-2TEYHG4G4otNGfLMU"

HDR = {"Authorization": f"Bearer {ADMIN_TOKEN}"}


# ----- Dynamic Pricing -----
def test_pricing_market():
    r = requests.get(f"{BASE_URL}/api/pricing/market", headers=HDR, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    hi = d.get("market_heat_index", d.get("heat_index"))
    assert hi is not None
    assert isinstance(d.get("lanes"), list) and len(d["lanes"]) >= 1
    first = d["lanes"][0]
    assert "ladder" in first or "price_ladder" in first or "best_day" in first
    print(f"heat_index={hi} lanes={len(d['lanes'])}")


def test_pricing_quote_suggest():
    r = requests.get(
        f"{BASE_URL}/api/pricing/quote-suggest",
        params={"origin": "Minneapolis, MN", "destination": "Chicago, IL"},
        headers=HDR,
        timeout=30,
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert "ladder" in d or "price_ladder" in d
    assert "shipper_pitch" in d


# ----- Ops Truth -----
def test_ops_truth_summary():
    r = requests.get(f"{BASE_URL}/api/ops-truth/summary", headers=HDR, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    funnel = d.get("funnel") or d
    # verify shape
    assert any(k in str(d) for k in ["scanned", "bids", "wins"])
    print(f"ops-truth keys={list(d.keys())}")


def test_ops_truth_match_playbook():
    r = requests.get(f"{BASE_URL}/api/ops-truth/match-playbook", headers=HDR, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    assert "pairs" in d or "recommendations" in d
    print(f"playbook keys={list(d.keys())}")


# ----- Insurance -----
def test_insurance_policies():
    r = requests.get(f"{BASE_URL}/api/insurance/policies", headers=HDR, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("dual_insured") is True
    policies = d.get("policies", [])
    assert len(policies) >= 3, f"Expected >=3 seeded policies, got {len(policies)}"


# ----- Portal Live ETA -----
@pytest.fixture(scope="module")
def temp_in_transit_booking():
    """Create in-transit booking directly in Mongo."""
    from pymongo import MongoClient
    from datetime import datetime, timezone, timedelta
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "test_database")
    client = MongoClient(mongo_url)
    db = client[db_name]
    booked_id = "BK-QATEST-ETA"
    doc = {
        "booked_id": booked_id,
        "customer_id": "CUST-940030A27E",
        "customer_name": "Acme Shipping Co",
        "status": "in_transit",
        "miles": 409,
        "is_sample": True,
        "booked_at": (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat(),
        "origin": "Chicago, IL",
        "destination": "Dallas, TX",
    }
    db.brokerage_bookings.update_one({"booked_id": booked_id}, {"$set": doc}, upsert=True)
    yield True
    db.brokerage_bookings.delete_one({"booked_id": booked_id})
    client.close()


def test_portal_live_eta(temp_in_transit_booking):
    r = requests.get(f"{BASE_URL}/api/public/customer-portal/{PORTAL_TOKEN}", timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    bookings = d.get("bookings", [])
    assert isinstance(bookings, list)
    live_found = False
    for b in bookings:
        live = (b.get("tracking") or {}).get("live") or {}
        if live.get("miles_out") is not None and live.get("eta_label") and live.get("progress_pct") is not None:
            live_found = True
            print(f"live ETA: {live.get('miles_out')} mi · {live.get('eta_label')} · {live.get('progress_pct')}%")
            break
    if not temp_in_transit_booking and not live_found:
        pytest.skip("Could not seed in-transit booking and no existing in-transit load — portal live ETA not verifiable")
    assert live_found, f"No booking with tracking.live shape found among {len(bookings)} bookings"
