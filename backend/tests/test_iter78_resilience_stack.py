"""Iteration 78 — Resilience Stack backend tests.

Covers:
- Orisei Sentinel (self-repair) — status, sweep, and injected anomaly auto-patch verification
- Load Board Gateway — status chain (4 boards) + failover fetch (falls to internal_sim)
- Decision Engine — info + match ranking + validation
- Ops Runbook — markdown + branded PDF + printable load-sheets PDF
- Ops Backups — list, run, download (path-traversal guard), prune
- Regression — broker autopilot run-cycle still 200 + status ok
"""
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
ADMIN_TOKEN = "test_session_admin_1"
HEADERS = {"Authorization": f"Bearer {ADMIN_TOKEN}", "Content-Type": "application/json"}

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")


@pytest.fixture(scope="module")
def db():
    client = MongoClient(MONGO_URL)
    yield client[DB_NAME]
    client.close()


# -------------------- Sentinel --------------------
class TestSentinel:
    def test_status(self):
        r = requests.get(f"{BASE_URL}/api/self-repair/status", headers=HEADERS, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "state" in data and "repair_log" in data and "thresholds" in data
        assert set(data["thresholds"].keys()) == {"stall_minutes", "hunt_dead_minutes", "heartbeat_minutes"}

    def test_sweep_baseline(self):
        r = requests.post(f"{BASE_URL}/api/self-repair/sweep", headers=HEADERS, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("ok") is True
        checks = data["checks"]
        assert len(checks) == 6
        names = {c["check"] for c in checks}
        assert names == {"stalled_loads", "driverless_loads", "dead_hunts",
                         "config_drift", "loop_heartbeat", "orphan_hunts"}

    def test_sweep_autopatches_injected_anomalies(self, db):
        """Inject: stalled load, driverless load, stale heartbeat. Verify auto-patch."""
        now = datetime.now(timezone.utc)
        two_hours_ago = (now - timedelta(hours=2)).isoformat()

        stalled_id = f"TEST_STALL_{uuid.uuid4().hex[:6]}"
        driverless_id = f"TEST_NODRV_{uuid.uuid4().hex[:6]}"
        injected_ids = [stalled_id, driverless_id]

        try:
            # (a) Stalled load
            db.autopilot_loads.insert_one({
                "load_id": stalled_id, "stage": "in_transit", "stage_at": two_hours_ago,
                "created_at": two_hours_ago, "origin": "Test, MN", "dest": "Test, IL",
                "miles": 400, "equipment": "Dry Van", "carrier_rate": 1000,
                "carrier": {"name": "TEST", "mc_number": "MC000"}, "driver": {"name": "TestDrv", "cdl_number": "X"},
                "timeline": []
            })

            # (b) Driverless load (no 'driver' field)
            db.autopilot_loads.insert_one({
                "load_id": driverless_id, "stage": "booked", "stage_at": now.isoformat(),
                "created_at": now.isoformat(), "origin": "Test, MN", "dest": "Test, IL",
                "miles": 400, "equipment": "Dry Van", "carrier_rate": 1000,
                "carrier": {"name": "TEST", "mc_number": "MC000"},
                "timeline": []
            })

            # (c) Stale autopilot heartbeat
            db.sentinel_heartbeats.update_one(
                {"_id": "autopilot_loop"},
                {"$set": {"at": two_hours_ago}},
                upsert=True,
            )

            # Trigger sweep
            r = requests.post(f"{BASE_URL}/api/self-repair/sweep", headers=HEADERS, timeout=90)
            assert r.status_code == 200, r.text
            data = r.json()
            by = {c["check"]: c for c in data["checks"]}

            # Stalled -> found >=1 patched >=1
            assert by["stalled_loads"]["found"] >= 1, by["stalled_loads"]
            assert by["stalled_loads"]["patched"] >= 1

            # Driverless -> found >=1 patched >=1
            assert by["driverless_loads"]["found"] >= 1, by["driverless_loads"]
            assert by["driverless_loads"]["patched"] >= 1

            # Heartbeat check triggered
            assert by["loop_heartbeat"]["found"] >= 1, by["loop_heartbeat"]

            # Verify driverless load got a driver assigned
            drv_load = db.autopilot_loads.find_one({"load_id": driverless_id})
            assert drv_load.get("driver") and drv_load["driver"].get("name")

            # Verify stalled timer re-armed (timeline note present — stage_at
            # may already have been re-advanced by the background autopilot loop)
            stalled = db.autopilot_loads.find_one({"load_id": stalled_id})
            timeline_notes = " ".join(t.get("note", "") for t in stalled.get("timeline", []))
            assert "Sentinel: stage stalled" in timeline_notes, timeline_notes

            # Verify repairs were logged
            repair_checks = {r["check"] for r in data.get("repairs", [])}
            assert "stalled_loads" in repair_checks
            assert "driverless_loads" in repair_checks
            assert "loop_heartbeat" in repair_checks

        finally:
            db.autopilot_loads.delete_many({"load_id": {"$in": injected_ids}})


# -------------------- Loadboard Gateway --------------------
class TestGateway:
    def test_status_chain(self):
        r = requests.get(f"{BASE_URL}/api/loadboard-gateway/status", headers=HEADERS, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["failover_order"] == ["dat", "truckstop", "convoy", "internal_sim"]
        assert len(data["chain"]) == 4
        by_board = {c["board"]: c for c in data["chain"]}
        # internal_sim should be healthy
        assert by_board["internal_sim"]["status"] == "healthy"

    def test_fetch_falls_to_sim(self):
        r = requests.post(f"{BASE_URL}/api/loadboard-gateway/fetch", headers=HEADERS, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["ok"] is True
        assert data["source"] == "internal_sim"
        assert data["count"] >= 10
        sample = data["sample"]
        assert len(sample) > 0
        for ld in sample:
            assert "board_id" in ld and "origin" in ld and "dest" in ld and "shipper_rate" in ld

        # After fetch, confirm dat/truckstop/convoy are NOT healthy (either
        # 'no_credentials' when Connections is empty, or an 'error: *' status
        # when leftover encrypted-but-invalid creds exist from prior iter tests).
        r2 = requests.get(f"{BASE_URL}/api/loadboard-gateway/status", headers=HEADERS, timeout=30)
        by_board = {c["board"]: c for c in r2.json()["chain"]}
        for b in ("dat", "truckstop", "convoy"):
            assert by_board[b]["status"] != "healthy", by_board[b]
            assert by_board[b]["status"] != "connected", by_board[b]


# -------------------- Decision Engine --------------------
class TestDecisionEngine:
    def test_info(self):
        r = requests.get(f"{BASE_URL}/api/decision-engine/info", headers=HEADERS, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["standalone"] is True
        assert "weights" in data and "engine" in data

    def test_match_returns_ranked(self):
        payload = {"origin": "Minneapolis, MN", "dest": "Chicago, IL", "equipment": "Dry Van",
                   "weight_lbs": 30000, "miles": 408, "shipper_rate": 1100}
        r = requests.post(f"{BASE_URL}/api/decision-engine/match", headers=HEADERS,
                          json=payload, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "ranked" in data and len(data["ranked"]) > 0
        rec = data["recommended"]
        assert rec is not None
        assert "score" in rec and "components" in rec and "drivers_available" in rec
        assert "est_margin" in rec

    def test_match_weight_validation(self):
        payload = {"origin": "Minneapolis, MN", "dest": "Chicago, IL", "equipment": "Dry Van",
                   "weight_lbs": 100000, "miles": 408, "shipper_rate": 1100}
        r = requests.post(f"{BASE_URL}/api/decision-engine/match", headers=HEADERS,
                          json=payload, timeout=30)
        assert r.status_code == 422


# -------------------- Runbook --------------------
class TestRunbook:
    def test_runbook_markdown(self):
        r = requests.get(f"{BASE_URL}/api/ops-runbook", headers=HEADERS, timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert "markdown" in data
        assert "Orisei" in data["markdown"]

    def test_runbook_pdf(self):
        r = requests.get(f"{BASE_URL}/api/ops-runbook/pdf", headers=HEADERS, timeout=60)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:4] == b"%PDF"
        assert len(r.content) > 10000

    def test_load_sheets_pdf(self):
        r = requests.get(f"{BASE_URL}/api/ops-runbook/load-sheets.pdf", headers=HEADERS, timeout=60)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:4] == b"%PDF"


# -------------------- Backups --------------------
class TestBackups:
    def test_list(self):
        r = requests.get(f"{BASE_URL}/api/ops-backups", headers=HEADERS, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "backups" in data and len(data["backups"]) >= 1
        assert "log_caps" in data and "keep" in data
        # existing seed backup
        names = {b["name"] for b in data["backups"]}
        assert any("orisei_backup_" in n for n in names)

    def test_download_head(self):
        # get list, take first
        r = requests.get(f"{BASE_URL}/api/ops-backups", headers=HEADERS, timeout=30)
        name = r.json()["backups"][0]["name"]
        # Stream a small chunk
        with requests.get(f"{BASE_URL}/api/ops-backups/{name}/download",
                          headers=HEADERS, stream=True, timeout=60) as resp:
            assert resp.status_code == 200
            ct = resp.headers.get("content-type", "")
            assert "gzip" in ct or "octet-stream" in ct
            first = next(resp.iter_content(chunk_size=64))
            # gzip magic
            assert first[:2] == b"\x1f\x8b"
            resp.close()

    def test_download_path_traversal_blocked(self):
        r = requests.get(f"{BASE_URL}/api/ops-backups/..%2Fserver.py/download",
                         headers=HEADERS, timeout=30, allow_redirects=False)
        assert r.status_code in (400, 404), f"got {r.status_code}"

    def test_prune(self):
        r = requests.post(f"{BASE_URL}/api/ops-backups/prune", headers=HEADERS, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "pruned" in data and isinstance(data["pruned"], dict)

    def test_run_backup(self):
        r = requests.post(f"{BASE_URL}/api/ops-backups/run", headers=HEADERS, timeout=180)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("ok") is True
        assert data["backup"]["name"].startswith("orisei_backup_")
        assert data["backup"]["size_bytes"] > 0


# -------------------- Regression --------------------
class TestRegression:
    def test_broker_autopilot_status(self):
        r = requests.get(f"{BASE_URL}/api/broker-autopilot/status", headers=HEADERS, timeout=30)
        assert r.status_code == 200, r.text

    def test_broker_autopilot_run_cycle(self):
        r = requests.post(f"{BASE_URL}/api/broker-autopilot/run-cycle", headers=HEADERS, timeout=90)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "actions" in data or "ok" in data or "sourced" in data
