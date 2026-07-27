"""Backend tests for the 6 new closing-focused Niche Markets features (iter 85)."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://clean-logistics-dash.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api/niche-markets"
H = {"Authorization": "Bearer test_session_admin_1", "Content-Type": "application/json"}

TORO_ID = "NM-9FB40580"
BOBCAT_ID = "NM-6FD05DD2"
BOBCAT_LINKED_CARRIER = "CN-49DE4F08"


def _get_target(tid):
    r = requests.get(f"{API}/targets", headers=H, timeout=15)
    assert r.status_code == 200, r.text
    for t in r.json()["targets"]:
        if t["id"] == tid:
            return t
    return None


class TestNewPatchFields:
    def test_patch_all_new_fields_persist(self):
        payload = {
            "intro_source": "TEST_LinkedIn warm intro",
            "warmth_score": 7,
            "current_carrier": "TEST_CH Robinson",
            "switch_angle": "TEST_service failures",
            "est_acquisition_cost": 12345.67,
            "sim_shipper_rate": 1800,
            "sim_carrier_cost": 1200,
        }
        r = requests.patch(f"{API}/targets/{TORO_ID}", json=payload, headers=H, timeout=15)
        assert r.status_code == 200, r.text
        t = r.json()["target"]
        for k, v in payload.items():
            assert t[k] == v, f"{k} not persisted: got {t.get(k)}"
        # verify via GET
        got = _get_target(TORO_ID)
        for k, v in payload.items():
            assert got[k] == v

    def test_warmth_score_upper_bound_rejected(self):
        r = requests.patch(f"{API}/targets/{TORO_ID}", json={"warmth_score": 11}, headers=H, timeout=15)
        assert r.status_code == 422, r.text

    def test_warmth_score_lower_bound_rejected(self):
        r = requests.patch(f"{API}/targets/{TORO_ID}", json={"warmth_score": 0}, headers=H, timeout=15)
        assert r.status_code == 422

    def test_negative_acq_cost_rejected(self):
        r = requests.patch(f"{API}/targets/{TORO_ID}", json={"est_acquisition_cost": -10}, headers=H, timeout=15)
        assert r.status_code == 422


class TestStageHistory:
    def test_stage_change_appends_history(self):
        # Toro is stage=meeting per context. Move to pilot_proposed then back to meeting.
        before = _get_target(TORO_ID)
        prev_hist = before.get("stage_history") or []
        prev_len = len(prev_hist)
        starting_stage = before["stage"]

        # move to different stage
        new_stage = "pilot_proposed" if starting_stage != "pilot_proposed" else "meeting"
        r = requests.patch(f"{API}/targets/{TORO_ID}", json={"stage": new_stage}, headers=H, timeout=15)
        assert r.status_code == 200
        after1 = r.json()["target"]
        hist1 = after1.get("stage_history") or []
        assert len(hist1) == prev_len + 1
        assert hist1[-1]["from"] == starting_stage
        assert hist1[-1]["to"] == new_stage
        assert "at" in hist1[-1]

        # same-stage patch does NOT append
        r2 = requests.patch(f"{API}/targets/{TORO_ID}", json={"stage": new_stage}, headers=H, timeout=15)
        assert r2.status_code == 200
        hist2 = r2.json()["target"].get("stage_history") or []
        assert len(hist2) == len(hist1), "same-stage patch must not append history"

        # restore
        requests.patch(f"{API}/targets/{TORO_ID}", json={"stage": starting_stage}, headers=H, timeout=15)


class TestLinkCarrierPatch:
    def test_patch_link_updates_rate_and_status(self):
        r = requests.patch(
            f"{API}/targets/{BOBCAT_ID}/link-carrier/{BOBCAT_LINKED_CARRIER}",
            json={"rate_usd": 1450, "status": "signed"}, headers=H, timeout=15)
        assert r.status_code == 200, r.text
        t = r.json()["target"]
        linked = [c for c in t.get("linked_carriers") or [] if c["id"] == BOBCAT_LINKED_CARRIER][0]
        assert linked["rate_usd"] == 1450
        assert linked["status"] == "signed"

        # restore to rate_agreed / 1400 per seed
        r2 = requests.patch(
            f"{API}/targets/{BOBCAT_ID}/link-carrier/{BOBCAT_LINKED_CARRIER}",
            json={"rate_usd": 1400, "status": "rate_agreed"}, headers=H, timeout=15)
        assert r2.status_code == 200

    def test_patch_link_invalid_status_rejected(self):
        r = requests.patch(
            f"{API}/targets/{BOBCAT_ID}/link-carrier/{BOBCAT_LINKED_CARRIER}",
            json={"status": "bogus"}, headers=H, timeout=15)
        assert r.status_code == 400

    def test_patch_link_unknown_pid_404(self):
        r = requests.patch(
            f"{API}/targets/{BOBCAT_ID}/link-carrier/CN-DOES-NOT-EXIST",
            json={"rate_usd": 100}, headers=H, timeout=15)
        assert r.status_code == 404

    def test_patch_link_empty_body_rejected(self):
        r = requests.patch(
            f"{API}/targets/{BOBCAT_ID}/link-carrier/{BOBCAT_LINKED_CARRIER}",
            json={}, headers=H, timeout=15)
        assert r.status_code == 400


class TestDashboardVelocity:
    def test_velocity_block_shape(self):
        r = requests.get(f"{API}/dashboard", headers=H, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert "velocity" in d
        v = d["velocity"]
        for key in ("closed_last_month", "closed_this_month", "closing_now", "projected_next",
                    "proposed_this_month"):
            assert key in v, f"missing velocity key: {key}"
            assert isinstance(v[key], int)

    def test_projected_next_counts_meeting_stage(self):
        r = requests.get(f"{API}/dashboard", headers=H, timeout=15)
        d = r.json()
        rows_r = requests.get(f"{API}/targets", headers=H, timeout=15).json()["targets"]
        expected = sum(1 for t in rows_r if t["stage"] == "meeting" and t.get("outcome") != "no")
        assert d["velocity"]["projected_next"] == expected
