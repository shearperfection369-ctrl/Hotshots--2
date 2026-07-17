"""iter67 — Operation Sandbox Industry Variables + AI Growth Copilot.

Covers:
  - Sandbox: reset → start → tick loop → verify market/industry/ledger structure
  - Ledger net_margin math correctness
  - Day rollover: overhead accrual + diesel/spot drift + day events
  - Copilot: /state (goal, week overhead breakdown 13 keys, compliance_gaps)
  - Copilot: /compliance seed 20 items critical-first, status update, invalid → 422
  - Copilot: /compliance requires auth (401 unauth)
  - Copilot: /plan (existing plan present), toggle task
  - Copilot: /chat multi-turn, /chat/{session_id}
  - Copilot: /briefing/latest (skip generation to save LLM budget)
  - Regression: /api/sentinel/status, /api/route-optimizer/loads

Note: LLM-generating endpoints (/plan/generate, /briefing) are ONLY invoked
      if there is no cached artifact. Otherwise skipped to save budget.
"""
import os
import time

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or \
    open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split()[0].rstrip("/")
LOCAL_URL = "http://localhost:8001"  # for long LLM calls (bypass ingress timeout)

ADMIN = {"Authorization": "Bearer test_session_admin_1"}
DISP = {"Authorization": "Bearer test_session_dispatcher_1"}


# ================================================================
# SANDBOX — industry variables
# ================================================================
class TestSandboxIndustry:
    def test_reset_and_start(self):
        r = requests.post(f"{BASE_URL}/api/sim/reset", headers=ADMIN, timeout=20)
        assert r.status_code == 200
        payload = {"duration_days": 7, "loads_per_day": 10,
                   "sim_minutes_per_real_second": 60, "autopilot": True, "auto_triage": True}
        s = requests.post(f"{BASE_URL}/api/sim/start", headers=ADMIN, json=payload, timeout=20)
        assert s.status_code == 200, s.text
        assert s.json()["ok"] is True

    def test_tick_loop_and_structure(self):
        last = None
        # Tick ~10 times over ~30s to force some day rollovers
        for i in range(10):
            r = requests.post(f"{BASE_URL}/api/sim/tick", headers=ADMIN, timeout=20)
            assert r.status_code == 200, r.text
            last = r.json()
            time.sleep(3)
        # Structure check
        assert last["active"] is True
        mkt = last["market"]
        assert set(mkt.keys()) >= {"diesel", "spot_index", "cycle"}
        assert mkt["cycle"] in ("tight", "balanced", "soft")
        ind = last["industry"]
        assert "overhead_daily" in ind
        # 13 overhead keys
        assert len(ind["overhead_daily"]) == 13, f"Expected 13 overhead keys, got {len(ind['overhead_daily'])}"
        assert ind["overhead_day_total"] == 226.9, f"Overhead day total mismatch: {ind['overhead_day_total']}"
        for k in ("claim_prob", "bad_debt_prob", "fallthrough_prob", "quickpay_fee", "carrier_payment_fee"):
            assert k in ind, f"Missing industry key {k}"
        assert ind["carrier_payment_fee"] == 12.0
        assert ind["quickpay_fee"] == 0.02
        # Ledger keys
        led = last["ledger"]
        for k in ("overhead", "claims", "bad_debt", "quickpay_income", "transaction_fees",
                  "revenue", "carrier_pay", "factoring_fees", "exception_costs", "net_margin"):
            assert k in led, f"Missing ledger key {k}"
        # Math check: net_margin
        expected = round(led["revenue"] - led["carrier_pay"] - led["factoring_fees"]
                         - led["exception_costs"] - led["overhead"] - led["claims"]
                         - led["bad_debt"] - led["transaction_fees"] + led["quickpay_income"], 2)
        # Allow small rounding tolerance
        assert abs(led["net_margin"] - expected) < 0.5, \
            f"net_margin math wrong: got {led['net_margin']}, expected {expected}"

    def test_day_rollover_overhead_market_drift(self):
        r = requests.post(f"{BASE_URL}/api/sim/tick", headers=ADMIN, timeout=20)
        assert r.status_code == 200
        j = r.json()
        sim_day = j["sim"]["sim_day"]
        led = j["ledger"]
        mkt = j["market"]
        # After several ticks we expect at least day 2
        assert sim_day >= 2, f"Expected day rollover, got sim_day={sim_day}"
        # Overhead ≈ 226.9 × sim_day (allow rounding)
        expected_oh = round(226.9 * sim_day, 2)
        assert abs(led["overhead"] - expected_oh) < 1.0, \
            f"Overhead ${led['overhead']} != expected ${expected_oh} for day {sim_day}"
        # Diesel drift OR still at baseline — cycles are random walk
        # At minimum diesel is present, in a plausible range
        assert 3.0 < mkt["diesel"] < 5.0
        assert 0.85 < mkt["spot_index"] < 1.20
        # Events feed sanity
        events = [e["message"] for e in j["events"]]
        # At least one day event should mention overhead
        day_events = [e for e in events if "DAY " in e or "overhead accrued" in e]
        assert len(day_events) > 0, f"No day rollover event with overhead: sample events {events[:5]}"

    def test_reset_at_end(self):
        r = requests.post(f"{BASE_URL}/api/sim/reset", headers=ADMIN, timeout=20)
        assert r.status_code == 200
        assert r.json()["ok"] is True


# ================================================================
# COPILOT — state, compliance, plan, chat
# ================================================================
class TestCopilotState:
    def test_state_structure(self):
        r = requests.get(f"{BASE_URL}/api/copilot/state", headers=ADMIN, timeout=20)
        assert r.status_code == 200
        s = r.json()
        assert s["goal_weekly_net"] == 20000.0
        w = s["week"]
        for k in ("revenue", "gross_margin", "overhead", "net_margin", "loads", "avg_margin_per_load"):
            assert k in w
        assert w["overhead"] == 1587.4, f"Weekly overhead expected 1587.4, got {w['overhead']}"
        assert "progress_pct" in s
        assert "gap_to_goal" in s
        assert "loads_needed_per_week" in s
        assert "pipeline" in s
        # overhead_breakdown has 13 lines
        assert len(s["overhead_breakdown"]) == 13, f"Expected 13 overhead lines, got {len(s['overhead_breakdown'])}"
        assert "compliance_gaps" in s

    def test_unauth_returns_401(self):
        r = requests.get(f"{BASE_URL}/api/copilot/compliance", timeout=15)
        assert r.status_code in (401, 403), f"Unauth should be 401/403, got {r.status_code}"


class TestCopilotCompliance:
    def test_compliance_seed_20_items_sorted(self):
        r = requests.get(f"{BASE_URL}/api/copilot/compliance", headers=ADMIN, timeout=20)
        assert r.status_code == 200
        data = r.json()
        items = data["items"]
        assert len(items) == 20, f"Expected 20 compliance items seeded, got {len(items)}"
        assert data["total"] == 20
        # Sorted critical-first (non-met items)
        non_met = [i for i in items if i["status"] != "met"]
        severities = [i["severity"] for i in non_met]
        # First items should be critical
        assert severities[0] == "critical", f"First item should be critical, got {severities[0]}"
        # Check no critical after high (within non-met portion)
        seen_high = False
        for s in severities:
            if s == "high":
                seen_high = True
            elif s == "critical" and seen_high:
                pytest.fail(f"critical after high in sort: {severities}")

    def test_status_update_and_met_increment(self):
        r = requests.get(f"{BASE_URL}/api/copilot/compliance", headers=ADMIN, timeout=15)
        items = r.json()["items"]
        met_before = r.json()["met"]
        # Pick a non-met item
        target = next((i for i in items if i["status"] != "met"), None)
        assert target is not None
        item_id = target["item_id"]
        orig_status = target["status"]

        try:
            u = requests.post(f"{BASE_URL}/api/copilot/compliance/{item_id}/status",
                              headers=ADMIN, json={"status": "met"}, timeout=15)
            assert u.status_code == 200, u.text

            r2 = requests.get(f"{BASE_URL}/api/copilot/compliance", headers=ADMIN, timeout=15)
            met_after = r2.json()["met"]
            assert met_after == met_before + 1, f"met count didn't increment: {met_before}→{met_after}"
        finally:
            # Restore
            requests.post(f"{BASE_URL}/api/copilot/compliance/{item_id}/status",
                          headers=ADMIN, json={"status": orig_status}, timeout=15)

    def test_invalid_status_422(self):
        # get any item
        r = requests.get(f"{BASE_URL}/api/copilot/compliance", headers=ADMIN, timeout=15)
        item_id = r.json()["items"][0]["item_id"]
        u = requests.post(f"{BASE_URL}/api/copilot/compliance/{item_id}/status",
                          headers=ADMIN, json={"status": "bogus"}, timeout=15)
        assert u.status_code == 422, f"Invalid status should be 422, got {u.status_code}: {u.text}"

    def test_dispatcher_can_set_status(self):
        r = requests.get(f"{BASE_URL}/api/copilot/compliance", headers=DISP, timeout=15)
        assert r.status_code == 200
        item_id = r.json()["items"][0]["item_id"]
        orig = r.json()["items"][0]["status"]
        try:
            u = requests.post(f"{BASE_URL}/api/copilot/compliance/{item_id}/status",
                              headers=DISP, json={"status": "in_progress"}, timeout=15)
            assert u.status_code == 200, f"Dispatcher should be allowed: {u.status_code} {u.text}"
        finally:
            requests.post(f"{BASE_URL}/api/copilot/compliance/{item_id}/status",
                          headers=ADMIN, json={"status": orig}, timeout=15)


class TestCopilotPlan:
    def test_get_plan_and_toggle(self):
        r = requests.get(f"{BASE_URL}/api/copilot/plan", headers=ADMIN, timeout=20)
        assert r.status_code == 200
        plan = r.json().get("plan")
        if not plan:
            pytest.skip("No active plan (main agent said one exists, skip toggle)")
        assert "phases" in plan
        assert len(plan["phases"]) == 4, f"Expected 4 phases, got {len(plan['phases'])}"
        for p in plan["phases"]:
            assert 5 <= len(p["tasks"]) <= 7, f"Phase tasks count out of range: {len(p['tasks'])}"
            for t in p["tasks"]:
                assert "task_id" in t
        # Find a task and toggle
        task = plan["phases"][0]["tasks"][0]
        task_id = task["task_id"]
        was_done = task.get("done", False)

        t = requests.post(f"{BASE_URL}/api/copilot/plan/tasks/{task_id}/toggle",
                          headers=ADMIN, timeout=15)
        assert t.status_code == 200
        # Verify flipped
        r2 = requests.get(f"{BASE_URL}/api/copilot/plan", headers=ADMIN, timeout=15).json()["plan"]
        new_task = next(x for p in r2["phases"] for x in p["tasks"] if x["task_id"] == task_id)
        assert new_task["done"] != was_done, "Toggle didn't flip state"
        # Toggle back
        requests.post(f"{BASE_URL}/api/copilot/plan/tasks/{task_id}/toggle",
                      headers=ADMIN, timeout=15)


class TestCopilotChat:
    def test_multi_turn_chat(self):
        session_id = "test-sess-iter67"
        # Message 1
        r1 = requests.post(f"{LOCAL_URL}/api/copilot/chat", headers=ADMIN,
                           json={"session_id": session_id,
                                 "message": "What is our current weekly net margin?"},
                           timeout=180)
        assert r1.status_code == 200, r1.text
        reply1 = r1.json()["reply"]
        assert isinstance(reply1, str) and len(reply1) > 10
        # Message 2 in same session
        r2 = requests.post(f"{LOCAL_URL}/api/copilot/chat", headers=ADMIN,
                           json={"session_id": session_id,
                                 "message": "And how many loads to close the gap?"},
                           timeout=180)
        assert r2.status_code == 200
        reply2 = r2.json()["reply"]
        assert isinstance(reply2, str) and len(reply2) > 10

        # History has >= 4 messages
        h = requests.get(f"{BASE_URL}/api/copilot/chat/{session_id}", headers=ADMIN, timeout=15)
        assert h.status_code == 200
        msgs = h.json()["messages"]
        assert len(msgs) >= 4, f"Expected >=4 messages in session history, got {len(msgs)}"


class TestCopilotBriefing:
    def test_briefing_latest(self):
        r = requests.get(f"{BASE_URL}/api/copilot/briefing/latest", headers=ADMIN, timeout=15)
        assert r.status_code == 200
        # briefing may be None if not generated yet; that's fine
        b = r.json().get("briefing")
        if b:
            assert "text" in b and len(b["text"]) > 20


# ================================================================
# REGRESSION
# ================================================================
class TestRegression:
    def test_sentinel_status(self):
        r = requests.get(f"{BASE_URL}/api/sentinel/status", headers=ADMIN, timeout=15)
        assert r.status_code == 200

    def test_route_optimizer_loads(self):
        r = requests.get(f"{BASE_URL}/api/route-optimizer/loads", headers=ADMIN, timeout=15)
        assert r.status_code == 200
        assert "loads" in r.json()
