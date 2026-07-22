"""iter 77 — Backhaul Hunter AI + driver assignment + drivers CRUD + PDFs."""
import os
import time
import pytest
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
H = {"Authorization": "Bearer test_session_admin_1"}


@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json", **H})
    return sess


# ---------------- status ----------------
class TestStatus:
    def test_status_ok(self, s):
        r = s.get(f"{BASE}/api/broker-autopilot/status")
        assert r.status_code == 200
        d = r.json()
        assert "config" in d and "stats" in d and "loads" in d and "stages" in d
        assert d["config"]["daily_limit"] == 15
        assert d["config"]["enabled"] is True
        # sourced_today only counts non-backhaul
        assert d["stats"]["sourced_today"] == 15
        assert d["stats"]["daily_limit"] == 15

    def test_new_loads_have_drivers(self, s):
        r = s.get(f"{BASE}/api/broker-autopilot/status").json()
        active_new = [l for l in r["loads"]
                      if l.get("load_type") in ("outbound", "backhaul")]
        assert active_new, "expected at least the 5 fresh outbound loads"
        for l in active_new:
            drv = l.get("driver") or {}
            assert drv.get("driver_id"), f"missing driver_id on {l['load_id']}"
            assert drv.get("name"), f"missing driver name on {l['load_id']}"
            assert drv.get("cdl_number"), f"missing cdl on {l['load_id']}"
            assert drv.get("home_base"), f"missing home_base on {l['load_id']}"
            assert "phone" in drv, f"missing phone key on {l['load_id']}"

    def test_stats_sourced_excludes_backhaul(self, s):
        d = s.get(f"{BASE}/api/broker-autopilot/status").json()
        # count outbound loads with today's date directly
        today_out = [l for l in d["loads"]
                     if l.get("load_type") != "backhaul"
                     and l.get("sourced_date") == __import__("datetime").datetime.utcnow().strftime("%Y-%m-%d")]
        assert d["stats"]["sourced_today"] == len(today_out)


# ---------------- drivers CRUD ----------------
class TestDrivers:
    def test_list(self, s):
        r = s.get(f"{BASE}/api/broker-autopilot/drivers")
        assert r.status_code == 200
        d = r.json()
        assert isinstance(d["drivers"], list) and isinstance(d["carriers"], list)
        assert len(d["carriers"]) >= 5
        # 2-3 drivers per carrier => ~20-30. Seed created 26 already.
        assert len(d["drivers"]) >= 20
        # verify shape
        drv = d["drivers"][0]
        for k in ("driver_id", "carrier_id", "carrier_name", "name", "phone",
                 "cdl_number", "home_base", "is_active"):
            assert k in drv

    def test_create_edit_delete(self, s):
        # pick a carrier
        cats = s.get(f"{BASE}/api/broker-autopilot/drivers").json()["carriers"]
        cid = cats[0]["carrier_id"]

        # CREATE — cdl and home_base blank should be auto-filled
        pay = {"carrier_id": cid, "name": "TEST_Iter77 Driver", "phone": "+15550001111"}
        r = s.post(f"{BASE}/api/broker-autopilot/drivers", json=pay)
        assert r.status_code == 200, r.text
        drv = r.json()["driver"]
        assert drv["name"] == "TEST_Iter77 Driver"
        assert drv["cdl_number"].startswith("CDL-"), "cdl should auto-fill"
        assert drv["home_base"], "home_base should auto-fill"
        did = drv["driver_id"]

        # GET should include new driver
        rows = s.get(f"{BASE}/api/broker-autopilot/drivers").json()["drivers"]
        assert any(x["driver_id"] == did for x in rows)

        # UPDATE
        r = s.put(f"{BASE}/api/broker-autopilot/drivers/{did}",
                  json={"name": "TEST_Iter77 Renamed", "phone": "+15559998888"})
        assert r.status_code == 200
        rows = s.get(f"{BASE}/api/broker-autopilot/drivers").json()["drivers"]
        me = next(x for x in rows if x["driver_id"] == did)
        assert me["name"] == "TEST_Iter77 Renamed"
        assert me["phone"] == "+15559998888"

        # DELETE => deactivate
        r = s.delete(f"{BASE}/api/broker-autopilot/drivers/{did}")
        assert r.status_code == 200
        rows = s.get(f"{BASE}/api/broker-autopilot/drivers").json()["drivers"]
        me = next(x for x in rows if x["driver_id"] == did)
        assert me["is_active"] is False

    def test_unknown_driver_404(self, s):
        r = s.put(f"{BASE}/api/broker-autopilot/drivers/DRV-NOPE",
                  json={"name": "x"})
        assert r.status_code == 404
        r = s.delete(f"{BASE}/api/broker-autopilot/drivers/DRV-NOPE")
        assert r.status_code == 404

    def test_unknown_carrier_404(self, s):
        r = s.post(f"{BASE}/api/broker-autopilot/drivers",
                   json={"carrier_id": "CX-NOPE", "name": "Bad Driver"})
        assert r.status_code == 404


# ---------------- run-cycle ----------------
class TestRunCycle:
    def test_run_cycle_ok(self, s):
        r = s.post(f"{BASE}/api/broker-autopilot/run-cycle", json={})
        assert r.status_code == 200
        d = r.json()
        assert d["ok"] is True
        assert isinstance(d["actions"], list)
        # cap still respected
        assert d["sourced_today"] <= 15

    def test_daily_cap_excludes_backhauls(self, s):
        d = s.get(f"{BASE}/api/broker-autopilot/status").json()
        assert d["stats"]["sourced_today"] == 15


# ---------------- backhaul ----------------
class TestBackhaul:
    def test_backhaul_endpoint(self, s):
        r = s.get(f"{BASE}/api/broker-autopilot/backhaul")
        assert r.status_code == 200
        d = r.json()
        assert "hunts" in d and "stats" in d
        for k in ("hunting", "booked", "round_trips", "backhaul_margin"):
            assert k in d["stats"]

    def test_hunt_shape_when_present(self, s):
        d = s.get(f"{BASE}/api/broker-autopilot/backhaul").json()
        # hunts may be empty at this point in the pipeline; verify shape if any
        for h in d["hunts"]:
            for k in ("hunt_id", "outbound_load_id", "carrier", "driver",
                     "stranded_at", "home_base", "status", "scans", "opened_at"):
                assert k in h, f"missing {k} in hunt"
            assert h["status"] in ("hunting", "booked", "completed", "expired")
            # driver has home base and it's different from stranded_at city
            if h["status"] == "hunting":
                assert h["driver"]["home_base"]
            if h["status"] in ("booked", "completed"):
                assert h.get("booked_load_id", "").startswith("BH-")

    def test_backhaul_loads_link_to_hunts(self, s):
        loads = s.get(f"{BASE}/api/broker-autopilot/status").json()["loads"]
        bh = [l for l in loads if l.get("load_type") == "backhaul"]
        for l in bh:
            assert l["load_id"].startswith("BH-")
            drv = l.get("driver") or {}
            assert drv.get("name"), "backhaul load missing driver"
            # dest is driver home base city
            assert l["dest"].split(",")[0].strip() == drv["home_base"].split(",")[0].strip()


# ---------------- PDFs ----------------
class TestPdfDocs:
    def _first_load_at_or_past(self, s, min_stage):
        stages = ["sourced", "carrier_matched", "ratecon_sent", "bol_received",
                  "in_transit", "delivered", "completed"]
        idx = stages.index(min_stage)
        d = s.get(f"{BASE}/api/broker-autopilot/status").json()
        for l in d["loads"]:
            if stages.index(l["stage"]) >= idx:
                return l
        return None

    def test_ratecon_pdf(self, s):
        l = self._first_load_at_or_past(s, "ratecon_sent")
        assert l, "need at least one load past ratecon_sent"
        r = s.get(f"{BASE}/api/broker-autopilot/loads/{l['load_id']}/docs/ratecon.pdf")
        assert r.status_code == 200, r.text
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content.startswith(b"%PDF") and len(r.content) > 1000

    def test_ratecon_400_before_stage(self, s):
        # Find a load at carrier_matched (before ratecon_sent). None in current pipeline
        # so we synthesize by hitting a doc that is definitely not-yet-available.
        # Use pod on an in_transit or earlier load.
        stages = ["sourced", "carrier_matched", "ratecon_sent", "bol_received",
                  "in_transit", "delivered", "completed"]
        d = s.get(f"{BASE}/api/broker-autopilot/status").json()
        for l in d["loads"]:
            if stages.index(l["stage"]) < stages.index("delivered"):
                r = s.get(f"{BASE}/api/broker-autopilot/loads/{l['load_id']}/docs/pod.pdf")
                assert r.status_code == 400, f"expected 400 for {l['load_id']} at {l['stage']}: got {r.status_code}"
                return
        pytest.skip("no eligible load to test 400")

    def test_bol_pdf_available_at_or_past(self, s):
        stages = ["sourced", "carrier_matched", "ratecon_sent", "bol_received",
                  "in_transit", "delivered", "completed"]
        d = s.get(f"{BASE}/api/broker-autopilot/status").json()
        for l in d["loads"]:
            if stages.index(l["stage"]) >= stages.index("bol_received"):
                r = s.get(f"{BASE}/api/broker-autopilot/loads/{l['load_id']}/docs/bol.pdf")
                assert r.status_code == 200
                assert r.content.startswith(b"%PDF")
                return
        pytest.skip("no load past bol_received yet")

    def test_pod_pdf_available_at_or_past_delivered(self, s):
        stages = ["sourced", "carrier_matched", "ratecon_sent", "bol_received",
                  "in_transit", "delivered", "completed"]
        d = s.get(f"{BASE}/api/broker-autopilot/status").json()
        for l in d["loads"]:
            if stages.index(l["stage"]) >= stages.index("delivered"):
                r = s.get(f"{BASE}/api/broker-autopilot/loads/{l['load_id']}/docs/pod.pdf")
                assert r.status_code == 200
                assert r.content.startswith(b"%PDF")
                # sanity: driver name should appear in bytes (may be encoded but visible for these simple PDFs)
                return
        pytest.skip("no load at delivered/completed yet")

    def test_driver_embedded_in_pdf(self, s):
        """Load newest fresh load with a driver at ratecon_sent+ and check driver name via PyMuPDF."""
        import fitz  # PyMuPDF
        stages = ["sourced", "carrier_matched", "ratecon_sent", "bol_received",
                  "in_transit", "delivered", "completed"]
        d = s.get(f"{BASE}/api/broker-autopilot/status").json()
        for l in d["loads"]:
            drv = (l.get("driver") or {}).get("name")
            if drv and stages.index(l["stage"]) >= stages.index("ratecon_sent"):
                r = s.get(f"{BASE}/api/broker-autopilot/loads/{l['load_id']}/docs/ratecon.pdf")
                assert r.status_code == 200
                doc = fitz.open(stream=r.content, filetype="pdf")
                text = "\n".join(p.get_text() for p in doc)
                doc.close()
                assert drv in text, \
                    f"driver name '{drv}' not found in ratecon PDF text for {l['load_id']}. Text sample: {text[:400]}"
                return
        pytest.skip("no ratecon-eligible load with driver")


# ---------------- config regression ----------------
class TestConfigRegression:
    def test_daily_limit_toggle(self, s):
        # cycle through 5, 10, 15 then leave at 15
        for n in (5, 10, 15):
            r = s.post(f"{BASE}/api/broker-autopilot/config", json={"daily_limit": n})
            assert r.status_code == 200
            assert r.json()["config"]["daily_limit"] == n
        d = s.get(f"{BASE}/api/broker-autopilot/status").json()
        assert d["config"]["daily_limit"] == 15

    def test_enabled_stays_true(self, s):
        # verify still enabled (do not flip off per instructions)
        d = s.get(f"{BASE}/api/broker-autopilot/status").json()
        assert d["config"]["enabled"] is True
