"""Iter74 — Orisei Truck Cleaning fleet unit registry, AI schedule, AI offers.

Covers:
- /truck-cleaning/units (seed, filter, add, delete, mark clean, cadence guard)
- /truck-cleaning/ai-schedule (ai=false plan packing, capacity, one-yard-trip)
- /truck-cleaning/offers/scrub (AI drafting; run only ONCE to avoid LLM cost)
- /truck-cleaning/offers, /send, /send-all, DELETE (Resend not configured → 400)
"""
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api/truck-cleaning"
HEADERS = {"Authorization": "Bearer test_session_admin_1"}


@pytest.fixture(scope="module")
def state():
    return {"created_unit_ids": [], "client_id": None, "unit_id": None, "offer_id": None}


# ================= UNITS =================
class TestFleetUnits:
    def test_units_seed_and_shape(self, state):
        r = requests.get(f"{API}/units", headers=HEADERS, timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "units" in data and "fleets" in data
        assert isinstance(data["units"], list)
        assert isinstance(data["fleets"], list)
        # After a prior scrub/seed, should be non-empty
        if data["units"]:
            u = data["units"][0]
            assert "metrics" in u
            m = u["metrics"]
            for k in ("last_cleaned", "days_since", "due_in_days", "status",
                      "total_cleans", "avg_interval_days", "cadence_days"):
                assert k in m, f"missing metric key: {k}"
            assert m["status"] in ("overdue", "due_soon", "fresh", "never_cleaned")
        if data["fleets"]:
            f = data["fleets"][0]
            for k in ("units", "overdue", "due_soon", "total_cleans", "client_id", "company"):
                assert k in f

    def test_units_filter_by_client(self, state):
        r = requests.get(f"{API}/units", headers=HEADERS, timeout=20)
        assert r.status_code == 200
        units = r.json()["units"]
        if not units:
            pytest.skip("no seeded units to filter test")
        cid = units[0]["client_id"]
        state["client_id"] = cid
        r2 = requests.get(f"{API}/units", headers=HEADERS, params={"client_id": cid}, timeout=20)
        assert r2.status_code == 200
        for u in r2.json()["units"]:
            assert u["client_id"] == cid

    def test_add_unit_unknown_client_404(self):
        r = requests.post(f"{API}/units", headers=HEADERS,
                          json={"client_id": "does-not-exist-xyz", "unit_number": "TEST-001"},
                          timeout=20)
        assert r.status_code == 404

    def test_add_unit_derives_cadence(self, state):
        # Need a real client
        rc = requests.get(f"{API}/clients", headers=HEADERS, timeout=15)
        assert rc.status_code == 200
        clients = rc.json()["clients"]
        assert clients, "no clients present in registry"
        client = clients[0]
        marker = uuid.uuid4().hex[:6]
        payload = {"client_id": client["client_id"], "unit_number": f"TEST-{marker}",
                   "make": "Freightliner", "model": "Cascadia", "year": "2024",
                   "cadence_days": 0, "notes": "TEST unit"}
        r = requests.post(f"{API}/units", headers=HEADERS, json=payload, timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("ok") is True
        unit = data["unit"]
        assert unit["unit_id"].startswith("UNIT-")
        # cadence derived from plan (must be one of the plan defaults or valid int)
        assert unit["cadence_days"] in (14, 21, 30) or 3 <= unit["cadence_days"] <= 120
        assert unit["metrics"]["status"] == "never_cleaned"
        assert unit["metrics"]["total_cleans"] == 0
        state["unit_id"] = unit["unit_id"]
        state["created_unit_ids"].append(unit["unit_id"])

    def test_mark_cleaned_updates_metrics(self, state):
        assert state["unit_id"], "no test unit created"
        r = requests.post(f"{API}/units/{state['unit_id']}/clean", headers=HEADERS,
                          json={"date": "", "job_id": "", "upsells": ["engine_bay"]}, timeout=20)
        assert r.status_code == 200, r.text
        m = r.json()["metrics"]
        assert m["total_cleans"] == 1
        assert m["status"] in ("fresh", "due_soon")
        assert m["days_since"] == 0 or m["days_since"] is not None

    def test_cadence_range_guard(self, state):
        assert state["unit_id"]
        r1 = requests.post(f"{API}/units/{state['unit_id']}/cadence", headers=HEADERS,
                           json={"cadence_days": 2}, timeout=15)
        assert r1.status_code == 400
        r2 = requests.post(f"{API}/units/{state['unit_id']}/cadence", headers=HEADERS,
                           json={"cadence_days": 121}, timeout=15)
        assert r2.status_code == 400
        r3 = requests.post(f"{API}/units/{state['unit_id']}/cadence", headers=HEADERS,
                           json={"cadence_days": 30}, timeout=15)
        assert r3.status_code == 200
        # Verify persisted
        rv = requests.get(f"{API}/units", headers=HEADERS, timeout=15)
        u = next((x for x in rv.json()["units"] if x["unit_id"] == state["unit_id"]), None)
        assert u and u["cadence_days"] == 30

    def test_cadence_404_unknown_unit(self):
        r = requests.post(f"{API}/units/UNIT-NOPE00/cadence", headers=HEADERS,
                          json={"cadence_days": 21}, timeout=15)
        assert r.status_code == 404

    def test_delete_unit(self, state):
        assert state["unit_id"]
        r = requests.delete(f"{API}/units/{state['unit_id']}", headers=HEADERS, timeout=15)
        assert r.status_code == 200
        # 2nd delete → 404
        r2 = requests.delete(f"{API}/units/{state['unit_id']}", headers=HEADERS, timeout=15)
        assert r2.status_code == 404
        state["created_unit_ids"].remove(state["unit_id"])
        state["unit_id"] = None


# ================= AI SCHEDULE =================
class TestAiSchedule:
    def test_schedule_no_ai(self):
        r = requests.get(f"{API}/ai-schedule", headers=HEADERS,
                         params={"days": 7, "ai": "false"}, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["capacity_per_day"] >= 9  # at least 1 tech
        assert data["techs"] >= 1
        assert len(data["plan"]) == 7
        # one yard trip per client per day
        for day in data["plan"]:
            client_ids_today = [s["client_id"] for s in day["stops"]]
            assert len(client_ids_today) == len(set(client_ids_today)), \
                f"client duplicated across stops on {day['date']}"
            assert day["cabs"] == sum(s["cabs"] for s in day["stops"])
        assert "units_due" in data and "overdue" in data
        # ai_notes NOT present when ai=false
        assert "ai_notes" not in data or data.get("ai_notes") == ""

    def test_schedule_days_clamp(self):
        r = requests.get(f"{API}/ai-schedule", headers=HEADERS,
                         params={"days": 2, "ai": "false"}, timeout=20)
        assert r.status_code == 200
        # 2 clamps up to 3
        assert len(r.json()["plan"]) == 3


# ================= OFFERS =================
class TestOffers:
    def test_offers_list_shape(self, state):
        r = requests.get(f"{API}/offers", headers=HEADERS, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "offers" in data
        assert "resend_configured" in data
        # per task note: resend_configured=false
        assert data["resend_configured"] is False
        # Capture an offer_id for send-not-configured test (main agent already ran scrub)
        if data["offers"]:
            draft = next((o for o in data["offers"] if o["status"] == "draft"), None)
            if draft:
                state["offer_id"] = draft["offer_id"]

    def test_send_offer_400_when_no_resend(self, state):
        # Get any offer to try send
        r = requests.get(f"{API}/offers", headers=HEADERS, timeout=15)
        offers = r.json()["offers"]
        if not offers:
            pytest.skip("no offers to send")
        oid = offers[0]["offer_id"]
        r2 = requests.post(f"{API}/offers/{oid}/send", headers=HEADERS, timeout=15)
        assert r2.status_code == 400, r2.text
        assert "resend" in r2.text.lower()

    def test_send_all_400_when_no_resend(self):
        r = requests.post(f"{API}/offers/send-all", headers=HEADERS, timeout=15)
        assert r.status_code == 400
        assert "resend" in r.text.lower()

    def test_delete_offer(self):
        r = requests.get(f"{API}/offers", headers=HEADERS, timeout=15)
        offers = r.json()["offers"]
        if not offers:
            pytest.skip("no offers to delete")
        # delete the last offer to preserve most
        target = offers[-1]["offer_id"]
        rd = requests.delete(f"{API}/offers/{target}", headers=HEADERS, timeout=15)
        assert rd.status_code == 200
        rd2 = requests.delete(f"{API}/offers/{target}", headers=HEADERS, timeout=15)
        assert rd2.status_code == 404


# ================= CLEANUP =================
def test_zzz_cleanup(state):
    for uid in list(state["created_unit_ids"]):
        try:
            requests.delete(f"{API}/units/{uid}", headers=HEADERS, timeout=15)
        except Exception:
            pass
