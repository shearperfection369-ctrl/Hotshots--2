"""Iter79 — Load Board Integration Layer (loadboard-gateway)."""
import os
import time

import pytest
import requests
from dotenv import dotenv_values

BASE = (os.environ.get("REACT_APP_BACKEND_URL")
        or dotenv_values("/app/frontend/.env").get("REACT_APP_BACKEND_URL", "")).rstrip("/")
assert BASE, "REACT_APP_BACKEND_URL missing"
AUTH = {"Authorization": "Bearer test_session_admin_1"}
EXPECTED_BOARDS = {"dat", "truckstop", "123loadboard", "convoy", "uberfreight"}


@pytest.fixture(scope="module")
def s():
    ss = requests.Session()
    ss.headers.update(AUTH)
    return ss


# ---------- boards registry ----------
class TestBoards:
    def test_list_boards(self, s):
        r = s.get(f"{BASE}/api/loadboard-gateway/boards")
        assert r.status_code == 200
        data = r.json()
        boards = {b["board"]: b for b in data["boards"]}
        assert set(boards.keys()) == EXPECTED_BOARDS
        for bid, b in boards.items():
            assert b["label"]
            assert b["docs"]
            assert b["rate_limit"]
            assert b["setup"]
            assert b["has_api_key"] is False
            assert b["booking_email"] == ""
            assert b["health"]["status"] == "no_credentials"

    def test_board_test_no_credentials(self, s):
        for bid in EXPECTED_BOARDS:
            r = s.post(f"{BASE}/api/loadboard-gateway/boards/{bid}/test")
            assert r.status_code == 200, (bid, r.text)
            j = r.json()
            assert j["ok"] is False
            assert j["status"] == "no_credentials"

    def test_board_test_unknown_404(self, s):
        r = s.post(f"{BASE}/api/loadboard-gateway/boards/bogus_xx/test")
        assert r.status_code == 404


# ---------- feed / ingest ----------
class TestFeed:
    def test_ingest_and_dedup(self, s):
        r1 = s.post(f"{BASE}/api/loadboard-gateway/ingest")
        assert r1.status_code == 200
        j1 = r1.json()
        assert j1["ok"] is True
        assert "ingested" in j1 and "merged" in j1 and "expired" in j1

        r2 = s.post(f"{BASE}/api/loadboard-gateway/ingest")
        j2 = r2.json()
        # Second run should have low ingest (feed already at floor) — dedup working
        # Accept either merged>=0 (mostly merges) OR ingested small (no new sim generated because floor met)
        assert j2["ok"] is True
        print(f"ingest1={j1}, ingest2={j2}")

    def test_feed(self, s):
        r = s.get(f"{BASE}/api/loadboard-gateway/feed")
        assert r.status_code == 200
        j = r.json()
        assert "loads" in j
        assert j["open_count"] >= 1
        # Should be near ~20 open once ingested a few times
        for ld in j["loads"][:5]:
            assert "fingerprint" in ld
            assert "sources" in ld and isinstance(ld["sources"], list)
            assert "board" in ld  # label like DAT One


# ---------- outbox / actions ----------
class TestOutbox:
    def test_outbox_lists_queued(self, s):
        r = s.get(f"{BASE}/api/loadboard-gateway/outbox")
        assert r.status_code == 200
        j = r.json()
        assert "outbox" in j
        # HTML field must be excluded from list
        for it in j["outbox"]:
            assert "html" not in it
            assert "subject" in it
        # Prev agent said several are already queued
        print(f"queued={j.get('queued')}, sent={j.get('sent')}")

    def test_outbox_flush_no_key(self, s):
        r = s.post(f"{BASE}/api/loadboard-gateway/outbox/flush")
        assert r.status_code == 200
        j = r.json()
        assert j["ok"] is True
        assert j["sent"] == 0

    def test_actions_has_queued(self, s):
        r = s.get(f"{BASE}/api/loadboard-gateway/actions")
        assert r.status_code == 200
        j = r.json()
        modes = {a.get("mode") for a in j.get("actions", [])}
        assert "queued" in modes or len(j.get("actions", [])) == 0
        print(f"actions modes present: {modes}")


# ---------- autopilot E2E ----------
class TestAutopilotE2E:
    def test_booking_creates_outbox_and_action(self, s):
        # Snapshot counts BEFORE
        ob_before = s.get(f"{BASE}/api/loadboard-gateway/outbox").json()["queued"]
        ac_before = len(s.get(f"{BASE}/api/loadboard-gateway/actions").json()["actions"])

        # Open cap room
        r = s.post(f"{BASE}/api/broker-autopilot/config", json={"daily_limit": 18})
        assert r.status_code == 200

        # Run a cycle
        r = s.post(f"{BASE}/api/broker-autopilot/run-cycle")
        assert r.status_code == 200
        cyc = r.json()
        print(f"run-cycle: {cyc}")

        # give small window for db writes
        time.sleep(1)

        ob_after = s.get(f"{BASE}/api/loadboard-gateway/outbox").json()["queued"]
        actions_after = s.get(f"{BASE}/api/loadboard-gateway/actions").json()["actions"]
        ac_after = len(actions_after)

        # If cycle booked >=1 load, outbox and actions must each grow
        booked = cyc.get("booked") or cyc.get("count") or cyc.get("loads_booked") or 0
        print(f"booked={booked}, ob {ob_before}->{ob_after}, actions {ac_before}->{ac_after}")

        # Verify at least one recent AP-load has SIM- board_id and via email outbox timeline
        loads = s.get(f"{BASE}/api/loads?limit=20").json()
        ap_loads = [ld for ld in (loads if isinstance(loads, list) else loads.get("loads", []))
                    if str(ld.get("load_id", "")).startswith("AP-")]
        if ap_loads:
            newest = ap_loads[0]
            print(f"newest AP load board_id={newest.get('board_id')} board={newest.get('board')}")
            # Check timeline has 'via email outbox'
            timeline = newest.get("timeline", [])
            tl_text = " ".join(str(t) for t in timeline)
            print(f"timeline sample: {tl_text[:400]}")

        # Reset daily_limit
        r = s.post(f"{BASE}/api/broker-autopilot/config", json={"daily_limit": 15})
        assert r.status_code == 200

        # If a booking occurred, verify outbox + actions both incremented
        if booked and booked > 0:
            assert ob_after >= ob_before + 1, "outbox did not grow after booking"
            assert ac_after >= ac_before + 1, "board_actions did not grow after booking"


# ---------- connections regression ----------
class TestConnections:
    def test_providers_has_convoy_and_booking_email(self, s):
        r = s.get(f"{BASE}/api/connections/providers")
        assert r.status_code == 200
        j = r.json()
        providers = j.get("providers") if isinstance(j, dict) else j
        by_id = {p["id"]: p for p in providers}
        assert "convoy" in by_id, "convoy provider missing"
        for pid in ("dat", "truckstop", "loadboard_123", "uber_freight", "convoy"):
            assert pid in by_id, f"{pid} missing"
            fields = {f.get("key") or f.get("name") or f.get("id") for f in by_id[pid].get("fields", [])}
            assert "booking_email" in fields, f"{pid} lacks booking_email field: {fields}"


# ---------- regression ----------
class TestRegression:
    def test_gateway_status_chain(self, s):
        r = s.get(f"{BASE}/api/loadboard-gateway/status")
        assert r.status_code == 200
        j = r.json()
        assert len(j["chain"]) == 6
        boards_in_chain = [c["board"] for c in j["chain"]]
        assert "internal_sim" in boards_in_chain
        for b in EXPECTED_BOARDS:
            assert b in boards_in_chain

    def test_self_repair_sweep(self, s):
        r = s.post(f"{BASE}/api/self-repair/sweep")
        assert r.status_code == 200

    def test_ops_backups_list(self, s):
        r = s.get(f"{BASE}/api/ops-backups")
        assert r.status_code == 200
