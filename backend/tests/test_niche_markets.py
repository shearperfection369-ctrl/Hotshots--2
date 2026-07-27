"""Backend tests for Niche Markets module (iteration 84)."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or "https://clean-logistics-dash.preview.emergentagent.com"
HEADERS = {"Authorization": "Bearer test_session_admin_1", "Content-Type": "application/json"}
API = f"{BASE_URL}/api/niche-markets"


def test_playbook():
    r = requests.get(f"{API}/playbook", headers=HEADERS, timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert len(d["verticals"]) == 10
    assert len(d["stages"]) == 6
    assert len(d["phase_plan"]) == 3
    assert d["goals"]["loads_per_month"] == 765
    assert d["goals"]["y1_revenue"] == 4_500_000
    keys = {v["key"] for v in d["verticals"]}
    assert "craft_beverage" in keys and "medical_devices" in keys


def test_targets_list_and_filter():
    r = requests.get(f"{API}/targets", headers=HEADERS, timeout=30)
    assert r.status_code == 200
    all_targets = r.json()["targets"]
    assert len(all_targets) >= 44
    assert all("y1_potential" in t for t in all_targets)

    r2 = requests.get(f"{API}/targets?vertical=craft_beverage", headers=HEADERS, timeout=30)
    assert r2.status_code == 200
    cb = r2.json()["targets"]
    assert len(cb) >= 4
    assert all(t["vertical"] == "craft_beverage" for t in cb)

    r3 = requests.get(f"{API}/targets?phase=1", headers=HEADERS, timeout=30)
    assert r3.status_code == 200
    p1 = r3.json()["targets"]
    assert len(p1) >= 3
    assert all(t["phase"] == 1 for t in p1)


def test_create_patch_delete_target():
    payload = {"name": "TEST_QA Co", "vertical": "craft_beverage", "city": "Duluth, MN",
               "phase": 1, "est_loads_month": 12, "margin_per_load_est": 900}
    r = requests.post(f"{API}/targets", json=payload, headers=HEADERS, timeout=30)
    assert r.status_code == 200
    tid = r.json()["target"]["id"]
    assert r.json()["target"]["stage"] == "target"
    assert r.json()["target"]["y1_potential"] == 12 * 900 * 12

    # bad vertical
    bad = requests.post(f"{API}/targets", json={**payload, "vertical": "junk"}, headers=HEADERS, timeout=30)
    assert bad.status_code == 400

    # patch stage
    pr = requests.patch(f"{API}/targets/{tid}", json={"stage": "meeting"}, headers=HEADERS, timeout=30)
    assert pr.status_code == 200
    assert pr.json()["target"]["stage"] == "meeting"

    # invalid stage
    bs = requests.patch(f"{API}/targets/{tid}", json={"stage": "bogus"}, headers=HEADERS, timeout=30)
    assert bs.status_code == 400

    # persist check
    ck = requests.get(f"{API}/targets", headers=HEADERS, timeout=30).json()["targets"]
    found = [t for t in ck if t["id"] == tid][0]
    assert found["stage"] == "meeting"

    # delete
    dr = requests.delete(f"{API}/targets/{tid}", headers=HEADERS, timeout=30)
    assert dr.status_code == 200
    d2 = requests.delete(f"{API}/targets/{tid}", headers=HEADERS, timeout=30)
    assert d2.status_code == 404


def test_dashboard():
    r = requests.get(f"{API}/dashboard", headers=HEADERS, timeout=30)
    assert r.status_code == 200
    d = r.json()
    for k in ["targets_total", "weighted_pipeline_y1", "contracted_loads_month", "loads_pct_of_goal"]:
        assert k in d["stats"]
    assert d["stats"]["targets_total"] >= 44
    assert len(d["verticals"]) == 10
    assert len(d["phases"]) == 3
    assert all("loads_committed" in p for p in d["phases"])
    # verticals sorted by tier
    tiers = [v["tier"] for v in d["verticals"]]
    assert tiers == sorted(tiers)
    # stage_counts includes all stages
    assert set(d["stage_counts"].keys()) == {"target", "researched", "contacted", "meeting", "pilot", "contracted"}


def test_battle_card_ai():
    # get a target
    ts = requests.get(f"{API}/targets?phase=1", headers=HEADERS, timeout=30).json()["targets"]
    tid = ts[0]["id"]
    r = requests.post(f"{API}/targets/{tid}/battle-card", headers=HEADERS, timeout=120)
    assert r.status_code == 200, r.text
    card = r.json()["battle_card"]
    for k in ["what_they_ship", "likely_lanes", "decision_makers", "objections", "hook", "compliance_notes"]:
        assert k in card, f"missing {k}"
    assert isinstance(card["likely_lanes"], list) and len(card["likely_lanes"]) >= 1
    assert isinstance(card["objections"], list) and len(card["objections"]) >= 1


def test_pitch_preview_and_send_recorded():
    ts = requests.get(f"{API}/targets?phase=1", headers=HEADERS, timeout=30).json()["targets"]
    tid = ts[0]["id"]
    # preview
    r = requests.post(f"{API}/targets/{tid}/pitch", json={"send": False}, headers=HEADERS, timeout=120)
    assert r.status_code == 200, r.text
    p = r.json()["pitch"]
    assert p["subject"] and p["body_text"]
    assert p["sent"] is False

    # send (no Resend key configured → recorded_no_key)
    r2 = requests.post(f"{API}/targets/{tid}/pitch",
                       json={"send": True, "email": "qa@example.com"},
                       headers=HEADERS, timeout=120)
    assert r2.status_code == 200, r2.text
    p2 = r2.json()["pitch"]
    assert p2.get("send_status") in ("recorded_no_key", "sent")
    # stage should be at least contacted (Toro is pilot already — don't downgrade check)
    tt = [t for t in requests.get(f"{API}/targets", headers=HEADERS, timeout=30).json()["targets"] if t["id"] == tid][0]
    assert tt["stage"] in ("contacted", "meeting", "pilot", "contracted")


def test_regression_autopilot_and_brochure():
    r = requests.get(f"{BASE_URL}/api/broker-autopilot/status", headers=HEADERS, timeout=30)
    assert r.status_code == 200
    body = r.json()
    # stat should still exist somewhere
    txt = str(body)
    assert "playbook_tenders" in txt

    r2 = requests.get(f"{BASE_URL}/api/brokerage/business-plan/brochure.pdf", headers=HEADERS, timeout=60)
    assert r2.status_code == 200
    assert r2.headers.get("content-type", "").startswith("application/pdf")
    assert len(r2.content) > 1000
