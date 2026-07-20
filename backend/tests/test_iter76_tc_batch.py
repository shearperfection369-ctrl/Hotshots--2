"""Iter76 — Truck Cleaning batch: job/tech edit, 42-day sched, review engine, scent card, inventory."""
import os
import uuid
from datetime import datetime, timezone

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or "https://clean-logistics-dash.preview.emergentagent.com"
API = f"{BASE_URL}/api/truck-cleaning"
AUTH = {"Authorization": "Bearer test_session_admin_1"}


# ---------- fixtures ----------
@pytest.fixture(scope="module")
def s():
    ses = requests.Session()
    ses.headers.update(AUTH)
    return ses


@pytest.fixture(scope="module")
def client_id(s):
    r = s.get(f"{API}/clients")
    assert r.status_code == 200, r.text
    clients = r.json()["clients"]
    assert clients, "no seed clients"
    return clients[0]["client_id"]


@pytest.fixture
def fresh_job(s, client_id):
    r = s.post(f"{API}/jobs", json={"client_id": client_id, "date": "2026-02-15", "cabs": 2,
                                    "upsells": ["engine_bay"], "notes": "TEST_iter76"})
    assert r.status_code == 200, r.text
    return r.json()["job"]


# ---------- JOB EDIT / DELETE ----------
class TestJobEdit:
    def test_update_date_cabs_window_reprice(self, s, fresh_job, client_id):
        c = s.get(f"{API}/clients").json()["clients"]
        rate = next(x["rate"] for x in c if x["client_id"] == client_id)
        r = s.post(f"{API}/jobs/{fresh_job['job_id']}/update", json={
            "date": "2026-02-20", "cabs": 3, "window": "10:00-12:00",
            "upsells": ["engine_bay", "tire_dressing"]})
        assert r.status_code == 200, r.text
        job = r.json()["job"]
        assert job["date"] == "2026-02-20"
        assert job["cabs"] == 3
        assert job["window"] == "10:00-12:00"
        assert job["upsells"] == ["engine_bay", "tire_dressing"]
        assert job["price"] == round(3 * rate + 25 + 20, 2)
        # GET verify persistence
        got = next(j for j in s.get(f"{API}/jobs").json()["jobs"] if j["job_id"] == fresh_job["job_id"])
        assert got["date"] == "2026-02-20" and got["cabs"] == 3

    def test_update_status_valid(self, s, fresh_job):
        r = s.post(f"{API}/jobs/{fresh_job['job_id']}/update", json={"status": "completed"})
        assert r.status_code == 200
        assert r.json()["job"]["status"] == "completed"

    def test_update_status_invalid(self, s, fresh_job):
        r = s.post(f"{API}/jobs/{fresh_job['job_id']}/update", json={"status": "bogus"})
        assert r.status_code == 400
        assert "status must be" in r.json()["detail"]

    def test_update_tech_ids_filters_invalid(self, s, fresh_job):
        techs = s.get(f"{API}/techs").json()["techs"]
        tid = techs[0]["tech_id"]
        r = s.post(f"{API}/jobs/{fresh_job['job_id']}/update",
                   json={"tech_ids": [tid, "TECH-BOGUS"]})
        assert r.status_code == 200
        assert r.json()["job"]["tech_ids"] == [tid]

    def test_update_empty_payload_400(self, s, fresh_job):
        r = s.post(f"{API}/jobs/{fresh_job['job_id']}/update", json={})
        assert r.status_code == 400
        assert "Nothing to update" in r.json()["detail"]

    def test_delete_and_404(self, s, fresh_job):
        r = s.delete(f"{API}/jobs/{fresh_job['job_id']}")
        assert r.status_code == 200
        r2 = s.delete(f"{API}/jobs/{fresh_job['job_id']}")
        assert r2.status_code == 404


# ---------- TECH EDIT ----------
class TestTechEdit:
    def test_update_tech_fields(self, s):
        techs = s.get(f"{API}/techs").json()["techs"]
        tid = techs[0]["tech_id"]
        r = s.post(f"{API}/techs/{tid}/update",
                   json={"name": "TEST_UpdatedName", "role": "junior", "hourly_rate": 28})
        assert r.status_code == 200
        fresh = next(t for t in s.get(f"{API}/techs").json()["techs"] if t["tech_id"] == tid)
        assert fresh["name"] == "TEST_UpdatedName"
        assert fresh["role"] == "junior"
        assert fresh["hourly_rate"] == 28

    def test_update_tech_bad_role(self, s):
        techs = s.get(f"{API}/techs").json()["techs"]
        r = s.post(f"{API}/techs/{techs[0]['tech_id']}/update", json={"role": "manager"})
        assert r.status_code == 400

    def test_update_tech_404(self, s):
        r = s.post(f"{API}/techs/TECH-DOESNOTEXIST/update", json={"name": "Foo"})
        assert r.status_code == 404


# ---------- SCHEDULE 42 DAYS ----------
class TestSchedule42:
    def test_42_day_bucket(self, s):
        r = s.get(f"{API}/schedule?start=2026-02-01&days=42")
        assert r.status_code == 200
        data = r.json()
        assert len(data["days"]) == 42
        assert data["days"][0]["date"] == "2026-02-01"

    def test_clamped_at_45(self, s):
        r = s.get(f"{API}/schedule?start=2026-02-01&days=100")
        assert r.status_code == 200
        assert len(r.json()["days"]) == 45


# ---------- REVIEW ENGINE ----------
class TestReviewEngine:
    def test_settings_roundtrip(self, s):
        r = s.post(f"{API}/settings", json={"google_review_url": "https://g.page/r/orisei-review-test"})
        assert r.status_code == 200
        g = s.get(f"{API}/settings")
        assert g.status_code == 200
        j = g.json()
        assert j["google_review_url"] == "https://g.page/r/orisei-review-test"
        assert "review_requests_sent" in j
        assert isinstance(j["review_requests_sent"], int)

    def test_review_request_no_phone_skipped(self, s, client_id):
        # ensure URL set
        s.post(f"{API}/settings", json={"google_review_url": "https://g.page/r/orisei-review"})
        # create a job on a client with no phone (seed clients have phone="")
        rj = s.post(f"{API}/jobs", json={"client_id": client_id, "date": "2026-02-16", "cabs": 1})
        job_id = rj.json()["job"]["job_id"]
        r = s.post(f"{API}/jobs/{job_id}/review-request")
        assert r.status_code == 200
        j = r.json()
        assert j["status"] == "skipped"
        assert "no phone" in j.get("note", "").lower()
        s.delete(f"{API}/jobs/{job_id}")

    def test_review_request_with_phone_sms_logged(self, s):
        # create client w/ phone
        cid = "TC-" + uuid.uuid4().hex[:6].upper()
        # go through official add_client
        rc = s.post(f"{API}/clients", json={"company": "TEST_ReviewCo", "phone": "+15555550100",
                                            "cabs": 1, "plan": "one_time", "rate": 150})
        assert rc.status_code == 200
        cid = rc.json()["client"]["client_id"]
        rj = s.post(f"{API}/jobs", json={"client_id": cid, "date": "2026-02-17", "cabs": 1})
        job_id = rj.json()["job"]["job_id"]
        s.post(f"{API}/settings", json={"google_review_url": "https://g.page/r/orisei-review"})
        r = s.post(f"{API}/jobs/{job_id}/review-request")
        assert r.status_code == 200
        # sms status can be queued or failed depending on twilio config
        assert r.json()["status"] in ("queued", "failed", "sent")
        # verify sms log has kind=review_request
        log = s.get(f"{API}/sms-log").json()["log"]
        assert any(row["kind"] == "review_request" and row["job_id"] == job_id for row in log)
        # verify job has review_requested_at
        jj = next(j for j in s.get(f"{API}/jobs").json()["jobs"] if j["job_id"] == job_id)
        assert jj.get("review_requested_at")
        # cleanup
        s.delete(f"{API}/jobs/{job_id}")
        s.delete(f"{API}/clients/{cid}")


# ---------- SCENT CARD ----------
class TestScentCard:
    def _setup_job(self, s, client_id, date="2026-02-18"):
        rj = s.post(f"{API}/jobs", json={"client_id": client_id, "date": date, "cabs": 2})
        return rj.json()["job"]

    def test_create_scent_card_link(self, s, client_id):
        job = self._setup_job(s, client_id)
        r = s.post(f"{API}/jobs/{job['job_id']}/scent-card")
        assert r.status_code == 200
        assert r.json()["link_path"].startswith("/tc/scent/")
        s.delete(f"{API}/jobs/{job['job_id']}")

    def test_public_get_scent_menu(self, s, client_id):
        job = self._setup_job(s, client_id)
        r = s.post(f"{API}/jobs/{job['job_id']}/scent-card")
        token = r.json()["link_path"].rsplit("/", 1)[-1]
        # public no auth
        p = requests.get(f"{API}/scent/{token}")
        assert p.status_code == 200
        d = p.json()
        assert len(d["scents"]) == 8
        assert len(d["upgrades"]) == 10  # 4 freshener + 6 bedding
        cats = {u["category"] for u in d["upgrades"]}
        assert cats == {"freshener", "bedding"}
        fcount = sum(1 for u in d["upgrades"] if u["category"] == "freshener")
        bcount = sum(1 for u in d["upgrades"] if u["category"] == "bedding")
        assert fcount == 4 and bcount == 6
        assert d["locked"] is False
        s.delete(f"{API}/jobs/{job['job_id']}")

    def test_public_submit_reprice_and_added_total(self, s, client_id):
        # get client rate
        clients = s.get(f"{API}/clients").json()["clients"]
        rate = next(c["rate"] for c in clients if c["client_id"] == client_id)
        job = self._setup_job(s, client_id, date="2026-02-19")
        token = s.post(f"{API}/jobs/{job['job_id']}/scent-card").json()["link_path"].rsplit("/", 1)[-1]
        p = requests.post(f"{API}/scent/{token}",
                          json={"scent": "Black Ice",
                                "upsell_ids": ["bedding_premium", "pillow_cooling"]})
        assert p.status_code == 200, p.text
        d = p.json()
        assert d["added_total"] == 138  # 99 + 39
        # verify job repriced (cabs=2, no prior upsells)
        jj = next(j for j in s.get(f"{API}/jobs").json()["jobs"] if j["job_id"] == job["job_id"])
        assert jj["price"] == round(2 * rate + 99 + 39, 2)
        assert set(jj["upsells"]) == {"bedding_premium", "pillow_cooling"}
        s.delete(f"{API}/jobs/{job['job_id']}")

    def test_public_submit_invalid_scent(self, s, client_id):
        job = self._setup_job(s, client_id, date="2026-02-20")
        token = s.post(f"{API}/jobs/{job['job_id']}/scent-card").json()["link_path"].rsplit("/", 1)[-1]
        p = requests.post(f"{API}/scent/{token}", json={"scent": "Not a Real Scent", "upsell_ids": []})
        assert p.status_code == 400
        s.delete(f"{API}/jobs/{job['job_id']}")

    def test_public_locked_when_completed(self, s, client_id):
        job = self._setup_job(s, client_id, date="2026-02-21")
        token = s.post(f"{API}/jobs/{job['job_id']}/scent-card").json()["link_path"].rsplit("/", 1)[-1]
        s.post(f"{API}/jobs/{job['job_id']}/update", json={"status": "completed"})
        p = requests.post(f"{API}/scent/{token}", json={"scent": "Black Ice", "upsell_ids": []})
        assert p.status_code == 400
        # public GET still works and shows locked=True
        g = requests.get(f"{API}/scent/{token}")
        assert g.status_code == 200
        assert g.json()["locked"] is True
        s.delete(f"{API}/jobs/{job['job_id']}")

    def test_bad_token_404(self):
        r = requests.get(f"{API}/scent/deadbeef-not-a-real-token-xyz")
        assert r.status_code == 404


# ---------- REMINDER SMS body contains both links ----------
class TestReminderBothLinks:
    def test_reminder_body_has_reschedule_and_scent(self, s):
        rc = s.post(f"{API}/clients", json={"company": "TEST_ReminderCo", "phone": "+15555550101",
                                            "cabs": 1, "plan": "one_time", "rate": 150})
        cid = rc.json()["client"]["client_id"]
        rj = s.post(f"{API}/jobs", json={"client_id": cid, "date": "2026-03-01", "cabs": 1})
        job_id = rj.json()["job"]["job_id"]
        r = s.post(f"{API}/jobs/{job_id}/remind")
        assert r.status_code == 200
        # find reminder log
        log = s.get(f"{API}/sms-log").json()["log"]
        row = next(x for x in log if x["job_id"] == job_id and x["kind"] == "reminder")
        assert "/tc/reschedule/" in row["body"]
        assert "/tc/scent/" in row["body"]
        s.delete(f"{API}/jobs/{job_id}")
        s.delete(f"{API}/clients/{cid}")


# ---------- INVENTORY ----------
class TestInventory:
    def test_inventory_seed_9_items(self, s):
        r = s.get(f"{API}/inventory")
        assert r.status_code == 200
        d = r.json()
        assert len(d["items"]) == 9
        # verify bed_change is NOT there
        ids = {i["item_id"] for i in d["items"]}
        assert "bed_change" not in ids
        # 4 freshener + 5 bedding (6 bedding minus bed_change)
        cats = {}
        for i in d["items"]:
            cats.setdefault(i["category"], 0)
            cats[i["category"]] += 1
        assert cats == {"freshener": 4, "bedding": 5}
        # each item has required fields
        for it in d["items"]:
            for k in ("stock", "committed", "available", "low", "unit_price"):
                assert k in it
        assert "low_count" in d and "retail_value" in d

    def test_adjust_positive_and_negative(self, s):
        items = s.get(f"{API}/inventory").json()["items"]
        item = items[0]
        base = item["stock"]
        r = s.post(f"{API}/inventory/{item['item_id']}/adjust", json={"delta": 5})
        assert r.status_code == 200
        assert r.json()["stock"] == base + 5
        r2 = s.post(f"{API}/inventory/{item['item_id']}/adjust", json={"delta": -3})
        assert r2.status_code == 200
        assert r2.json()["stock"] == base + 2

    def test_adjust_zero_400(self, s):
        items = s.get(f"{API}/inventory").json()["items"]
        r = s.post(f"{API}/inventory/{items[0]['item_id']}/adjust", json={"delta": 0})
        assert r.status_code == 400

    def test_adjust_over_500_400(self, s):
        items = s.get(f"{API}/inventory").json()["items"]
        r = s.post(f"{API}/inventory/{items[0]['item_id']}/adjust", json={"delta": 501})
        assert r.status_code == 400

    def test_adjust_floors_at_zero(self, s):
        items = s.get(f"{API}/inventory").json()["items"]
        it = items[0]
        # push stock down massively — should floor at 0 not go negative
        s.post(f"{API}/inventory/{it['item_id']}/adjust", json={"delta": -500})
        r = s.get(f"{API}/inventory").json()
        found = next(x for x in r["items"] if x["item_id"] == it["item_id"])
        assert found["stock"] >= 0
        # restore some stock
        s.post(f"{API}/inventory/{it['item_id']}/adjust", json={"delta": 50})

    def test_consume_once_on_completion(self, s, client_id):
        # snapshot stock for pillow_cooling
        before = next(x for x in s.get(f"{API}/inventory").json()["items"] if x["item_id"] == "pillow_cooling")
        base_stock = before["stock"]
        rj = s.post(f"{API}/jobs", json={"client_id": client_id, "date": "2026-02-22", "cabs": 1,
                                         "upsells": ["pillow_cooling"]})
        job_id = rj.json()["job"]["job_id"]
        # mark completed via /status
        r = s.post(f"{API}/jobs/{job_id}/status", json={"status": "completed"})
        assert r.status_code == 200
        after = next(x for x in s.get(f"{API}/inventory").json()["items"] if x["item_id"] == "pillow_cooling")
        assert after["stock"] == base_stock - 1
        # flip to paid — should NOT double-deduct
        s.post(f"{API}/jobs/{job_id}/status", json={"status": "paid"})
        after2 = next(x for x in s.get(f"{API}/inventory").json()["items"] if x["item_id"] == "pillow_cooling")
        assert after2["stock"] == base_stock - 1
        # flip back to completed — still idempotent
        s.post(f"{API}/jobs/{job_id}/status", json={"status": "completed"})
        after3 = next(x for x in s.get(f"{API}/inventory").json()["items"] if x["item_id"] == "pillow_cooling")
        assert after3["stock"] == base_stock - 1
        s.delete(f"{API}/jobs/{job_id}")


# ---------- 404s ----------
def test_delete_job_missing_404(s):
    r = s.delete(f"{API}/jobs/TJ-DOESNOTEXIST")
    assert r.status_code == 404


def test_scent_card_job_missing_404(s):
    r = s.post(f"{API}/jobs/TJ-DOESNOTEXIST/scent-card")
    assert r.status_code == 404
