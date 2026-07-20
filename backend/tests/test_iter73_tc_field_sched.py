"""Backend tests for iter73 Orisei Truck Cleaning field ops:
SMS reminders + public reschedule, before/after photo proof + public gallery,
scheduler/techs/assignment, and the cleaning guide."""
import io
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from PIL import Image

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://clean-logistics-dash.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api/truck-cleaning"
HEADERS = {"Authorization": "Bearer test_session_admin_1"}


def _tomorrow():
    return (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")


def _future(days=5):
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%d")


def _yesterday():
    return (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")


def _make_png_bytes(color=(200, 40, 40)):
    buf = io.BytesIO()
    Image.new("RGB", (200, 150), color=color).save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture(scope="module")
def state():
    return {}


@pytest.fixture(scope="module", autouse=True)
def bootstrap(state):
    """Create a client with phone + a scheduled job dated tomorrow (fresh)."""
    marker = uuid.uuid4().hex[:6]
    # Client with phone
    r = requests.post(f"{API}/clients", headers=HEADERS, json={
        "company": f"TEST_iter73 Fleet {marker}", "contact": "T Test", "phone": "+16125550199",
        "email": "iter73@example.com", "cabs": 2, "plan": "one_time", "rate": 150,
        "source": "test", "notes": ""}, timeout=20)
    assert r.status_code == 200, r.text
    state["client_id"] = r.json()["client"]["client_id"]
    # Client WITHOUT phone
    r2 = requests.post(f"{API}/clients", headers=HEADERS, json={
        "company": f"TEST_iter73 NoPhone {marker}", "contact": "NP", "phone": "",
        "email": "np@example.com", "cabs": 1, "plan": "one_time", "rate": 150,
        "source": "test", "notes": ""}, timeout=20)
    assert r2.status_code == 200
    state["client_no_phone"] = r2.json()["client"]["client_id"]

    # Job for tomorrow
    r3 = requests.post(f"{API}/jobs", headers=HEADERS, json={
        "client_id": state["client_id"], "date": _tomorrow(), "cabs": 2, "upsells": []}, timeout=20)
    assert r3.status_code == 200, r3.text
    state["job_id"] = r3.json()["job"]["job_id"]
    # Job for no-phone client (used for skip test)
    r4 = requests.post(f"{API}/jobs", headers=HEADERS, json={
        "client_id": state["client_no_phone"], "date": _future(3), "cabs": 1, "upsells": []}, timeout=20)
    assert r4.status_code == 200
    state["job_no_phone"] = r4.json()["job"]["job_id"]

    # Third job dated further-future for photo-proof tests (so remind autorun doesn't touch it)
    r5 = requests.post(f"{API}/jobs", headers=HEADERS, json={
        "client_id": state["client_id"], "date": _future(4), "cabs": 1, "upsells": []}, timeout=20)
    assert r5.status_code == 200
    state["photo_job_id"] = r5.json()["job"]["job_id"]
    yield


# ================= SMS REMINDERS =================
class TestSmsReminders:
    def test_remind_job_with_phone(self, state):
        r = requests.post(f"{API}/jobs/{state['job_id']}/remind", headers=HEADERS, timeout=25)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["job_id"] == state["job_id"]
        # Dummy creds → failed; no creds → queued; real → sent
        assert j["status"] in ("sent", "queued", "failed"), j
        state["last_remind_status"] = j["status"]

    def test_remind_sets_token_and_logs_link(self, state):
        # After remind, job should have a reschedule_token
        r = requests.get(f"{API}/jobs", headers=HEADERS, timeout=20)
        assert r.status_code == 200
        job = next((j for j in r.json()["jobs"] if j["job_id"] == state["job_id"]), None)
        assert job is not None
        token = job.get("reschedule_token")
        assert token, "reschedule_token not set on job after remind"
        state["reschedule_token"] = token

        # SMS log must contain a row for this job with absolute https link
        r2 = requests.get(f"{API}/sms-log", headers=HEADERS, timeout=20)
        assert r2.status_code == 200
        rows = r2.json().get("log", [])
        mine = [row for row in rows if row.get("job_id") == state["job_id"] and row.get("kind") == "reminder"]
        assert mine, "no reminder SMS log row for job"
        body = mine[0]["body"]
        assert "https://" in body
        assert f"/tc/reschedule/{token}" in body

    def test_remind_skipped_when_no_phone(self, state):
        r = requests.post(f"{API}/jobs/{state['job_no_phone']}/remind", headers=HEADERS, timeout=20)
        assert r.status_code == 200
        assert r.json()["status"] == "skipped"

    def test_reminders_run_idempotent(self, state):
        # First run — may or may not process (autorun loop may have already fired)
        r1 = requests.post(f"{API}/reminders/run", headers=HEADERS, timeout=30)
        assert r1.status_code == 200, r1.text
        d1 = r1.json()
        assert d1["target_date"] == _tomorrow()
        # Second run — must be idempotent per date → processes 0
        r2 = requests.post(f"{API}/reminders/run", headers=HEADERS, timeout=30)
        assert r2.status_code == 200
        d2 = r2.json()
        assert len(d2["processed"]) == 0, f"second run should be idempotent, got {d2}"


# ================= PUBLIC RESCHEDULE =================
class TestReschedule:
    def test_get_reschedule_info(self, state):
        tok = state["reschedule_token"]
        r = requests.get(f"{API}/reschedule/{tok}", timeout=20)  # no auth
        assert r.status_code == 200
        j = r.json()
        assert j["job_id"] == state["job_id"]
        assert j["status"] == "scheduled"
        assert j["date"] == _tomorrow()

    def test_get_reschedule_bad_token(self):
        r = requests.get(f"{API}/reschedule/badtoken_xyz_123", timeout=20)
        assert r.status_code == 404

    def test_reschedule_past_date_400(self, state):
        r = requests.post(f"{API}/reschedule/{state['reschedule_token']}",
                          json={"new_date": _yesterday()}, timeout=20)
        assert r.status_code == 400

    def test_reschedule_future_ok_and_logs_confirm(self, state):
        new_date = _future(6)
        r = requests.post(f"{API}/reschedule/{state['reschedule_token']}",
                          json={"new_date": new_date}, timeout=25)
        assert r.status_code == 200, r.text
        assert r.json()["new_date"] == new_date

        # Verify job.date updated
        rj = requests.get(f"{API}/jobs", headers=HEADERS, timeout=20)
        job = next((j for j in rj.json()["jobs"] if j["job_id"] == state["job_id"]), None)
        assert job and job["date"] == new_date
        # reschedule_confirm SMS logged
        rl = requests.get(f"{API}/sms-log", headers=HEADERS, timeout=20)
        confirms = [x for x in rl.json()["log"]
                    if x.get("job_id") == state["job_id"] and x.get("kind") == "reschedule_confirm"]
        assert confirms, "no reschedule_confirm SMS logged"

    def test_reschedule_bad_token_post(self):
        r = requests.post(f"{API}/reschedule/does_not_exist_token",
                          json={"new_date": _future(3)}, timeout=20)
        assert r.status_code == 404

    def test_reschedule_completed_job_400(self, state):
        # Mark the job completed
        r = requests.post(f"{API}/jobs/{state['job_id']}/status", headers=HEADERS,
                         json={"status": "completed"}, timeout=20)
        assert r.status_code == 200
        # Now try reschedule → 400
        r2 = requests.post(f"{API}/reschedule/{state['reschedule_token']}",
                           json={"new_date": _future(9)}, timeout=20)
        assert r2.status_code == 400


# ================= PHOTO PROOF =================
class TestPhotos:
    def test_upload_before_and_after(self, state):
        job_id = state["photo_job_id"]
        # before
        files = {"file": ("before.png", _make_png_bytes(color=(220, 40, 40)), "image/png")}
        r1 = requests.post(f"{API}/jobs/{job_id}/photos", headers=HEADERS,
                           files=files, data={"kind": "before", "caption": "TEST_iter73 before"}, timeout=30)
        assert r1.status_code == 200, r1.text
        j1 = r1.json()
        assert j1["ok"] and j1["kind"] == "before" and j1["proof_token"]
        state["proof_token"] = j1["proof_token"]
        state["photo_ids"] = [j1["photo_id"]]
        # after
        files = {"file": ("after.png", _make_png_bytes(color=(40, 200, 40)), "image/png")}
        r2 = requests.post(f"{API}/jobs/{job_id}/photos", headers=HEADERS,
                           files=files, data={"kind": "after"}, timeout=30)
        assert r2.status_code == 200
        state["photo_ids"].append(r2.json()["photo_id"])

    def test_upload_invalid_kind_400(self, state):
        files = {"file": ("x.png", _make_png_bytes(), "image/png")}
        r = requests.post(f"{API}/jobs/{state['photo_job_id']}/photos", headers=HEADERS,
                          files=files, data={"kind": "sideways"}, timeout=20)
        assert r.status_code == 400
        assert "before" in r.text.lower()

    def test_upload_non_image_400(self, state):
        files = {"file": ("x.txt", b"not an image", "text/plain")}
        r = requests.post(f"{API}/jobs/{state['photo_job_id']}/photos", headers=HEADERS,
                          files=files, data={"kind": "before"}, timeout=20)
        assert r.status_code == 400
        assert "image" in r.text.lower()

    def test_list_photos(self, state):
        r = requests.get(f"{API}/jobs/{state['photo_job_id']}/photos", headers=HEADERS, timeout=20)
        assert r.status_code == 200
        data = r.json()
        assert data["proof_token"] == state["proof_token"]
        assert len(data["photos"]) >= 2
        assert {p["kind"] for p in data["photos"]} >= {"before", "after"}

    def test_max_8_photos(self, state):
        job_id = state["photo_job_id"]
        # We already have 2, upload 6 more to reach 8 total
        for i in range(6):
            files = {"file": (f"p{i}.png", _make_png_bytes(color=(i * 30 % 255, 128, 40)), "image/png")}
            r = requests.post(f"{API}/jobs/{job_id}/photos", headers=HEADERS,
                              files=files, data={"kind": "before"}, timeout=25)
            assert r.status_code == 200, f"fill {i}: {r.text}"
        # 9th upload → 400
        files = {"file": ("nope.png", _make_png_bytes(), "image/png")}
        r = requests.post(f"{API}/jobs/{job_id}/photos", headers=HEADERS,
                          files=files, data={"kind": "after"}, timeout=20)
        assert r.status_code == 400
        assert "8" in r.text or "max" in r.text.lower()

    def test_public_proof_gallery(self, state):
        r = requests.get(f"{API}/proof/{state['proof_token']}", timeout=20)
        assert r.status_code == 200
        j = r.json()
        assert j["company"].startswith("TEST_iter73")
        assert j["date"]
        assert j["cabs"] == 1
        assert len(j["photos"]) >= 2

    def test_public_proof_bad_token(self):
        r = requests.get(f"{API}/proof/badproof_token_xyz", timeout=20)
        assert r.status_code == 404

    def test_public_proof_photo_bytes(self, state):
        photo_id = state["photo_ids"][0]
        r = requests.get(f"{API}/proof/{state['proof_token']}/photo/{photo_id}", timeout=25)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("image/jpeg")
        # JPEG magic bytes
        assert r.content[:3] == b"\xff\xd8\xff"

    def test_public_proof_photo_wrong_token_404(self, state):
        """Photo from another job accessed via wrong proof_token → 404."""
        # Create another job + upload a photo → different proof_token
        rj = requests.post(f"{API}/jobs", headers=HEADERS, json={
            "client_id": state["client_id"], "date": _future(8), "cabs": 1, "upsells": []}, timeout=20)
        other_job = rj.json()["job"]["job_id"]
        files = {"file": ("o.png", _make_png_bytes(color=(0, 0, 200)), "image/png")}
        rup = requests.post(f"{API}/jobs/{other_job}/photos", headers=HEADERS,
                            files=files, data={"kind": "before"}, timeout=25)
        other_photo = rup.json()["photo_id"]
        # Access other_photo via the FIRST proof_token → must 404
        r = requests.get(f"{API}/proof/{state['proof_token']}/photo/{other_photo}", timeout=20)
        assert r.status_code == 404

    def test_delete_photo(self, state):
        # Get current list, delete last one
        r = requests.get(f"{API}/jobs/{state['photo_job_id']}/photos", headers=HEADERS, timeout=20)
        pid = r.json()["photos"][-1]["photo_id"]
        rd = requests.delete(f"{API}/photos/{pid}", headers=HEADERS, timeout=20)
        assert rd.status_code == 200
        # Verify gone from list
        r2 = requests.get(f"{API}/jobs/{state['photo_job_id']}/photos", headers=HEADERS, timeout=20)
        pids = {p["photo_id"] for p in r2.json()["photos"]}
        assert pid not in pids

    def test_proof_send_resend_not_configured(self, state):
        r = requests.post(f"{API}/jobs/{state['photo_job_id']}/proof/send", headers=HEADERS,
                          json={"to_email": "iter73@example.com", "message": "hi"}, timeout=25)
        assert r.status_code == 400
        low = r.text.lower()
        assert "resend" in low
        assert f"/tc/proof/{state['proof_token']}" in r.text


# ================= SCHEDULER / TECHS =================
class TestScheduler:
    def test_techs_seeds_and_lists(self, state):
        r = requests.get(f"{API}/techs", headers=HEADERS, timeout=25)
        assert r.status_code == 200, r.text
        techs = r.json()["techs"]
        assert len(techs) >= 3
        for t in techs:
            assert "jobs_today" in t and "status_today" in t
            assert t["status_today"] in ("on_job", "available")
        state["sample_tech_id"] = techs[0]["tech_id"]

    def test_add_tech_bad_role_400(self):
        r = requests.post(f"{API}/techs", headers=HEADERS, json={
            "name": "TEST_iter73 Tech Bad", "phone": "", "role": "supervisor",
            "hourly_rate": 30, "skills": []}, timeout=20)
        assert r.status_code == 400

    def test_add_tech_ok(self, state):
        r = requests.post(f"{API}/techs", headers=HEADERS, json={
            "name": "TEST_iter73 New Tech", "phone": "+15555550000", "role": "junior",
            "hourly_rate": 25, "skills": ["glass"]}, timeout=20)
        assert r.status_code == 200
        t = r.json()["tech"]
        assert t["tech_id"].startswith("TECH-")
        assert t["role"] == "junior"
        state["new_tech_id"] = t["tech_id"]

    def test_assign_tech_to_job(self, state):
        # Fresh scheduled job
        rj = requests.post(f"{API}/jobs", headers=HEADERS, json={
            "client_id": state["client_id"], "date": _future(2), "cabs": 1, "upsells": []}, timeout=20)
        assign_job = rj.json()["job"]["job_id"]
        state["assign_job_id"] = assign_job
        payload = {"tech_ids": [state["new_tech_id"], "TECH-DOES-NOT-EXIST"], "window": "08:00-10:00"}
        r = requests.post(f"{API}/jobs/{assign_job}/assign", headers=HEADERS, json=payload, timeout=20)
        assert r.status_code == 200, r.text
        # Only valid tech_id stored
        assert r.json()["tech_ids"] == [state["new_tech_id"]]
        assert r.json()["window"] == "08:00-10:00"

    def test_schedule_board_7_days(self, state):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        r = requests.get(f"{API}/schedule?start={today}&days=7", headers=HEADERS, timeout=25)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["start"] == today
        assert len(j["days"]) == 7
        for d in j["days"]:
            assert set(d.keys()) >= {"date", "jobs", "cabs", "revenue", "unassigned"}
            for job in d["jobs"]:
                assert "tech_names" in job  # resolved
        s = j["summary"]
        for k in ("jobs", "cabs", "revenue", "crew_hours_needed"):
            assert k in s
        # our assign_job should appear in one of the day buckets with the tech's NAME resolved
        found = False
        for d in j["days"]:
            for jb in d["jobs"]:
                if jb["job_id"] == state["assign_job_id"]:
                    assert "TEST_iter73 New Tech" in jb["tech_names"]
                    found = True
        assert found, "assigned job not present in schedule board"

    def test_schedule_bad_start_400(self):
        r = requests.get(f"{API}/schedule?start=not-a-date&days=3", headers=HEADERS, timeout=20)
        assert r.status_code == 400

    def test_delete_tech_soft_deactivates_and_pulls(self, state):
        # Delete newly-added tech
        r = requests.delete(f"{API}/techs/{state['new_tech_id']}", headers=HEADERS, timeout=20)
        assert r.status_code == 200
        # Not in active list
        r2 = requests.get(f"{API}/techs", headers=HEADERS, timeout=20)
        ids = [t["tech_id"] for t in r2.json()["techs"]]
        assert state["new_tech_id"] not in ids
        # Pulled from scheduled jobs
        rj = requests.get(f"{API}/jobs", headers=HEADERS, timeout=20)
        job = next((j for j in rj.json()["jobs"] if j["job_id"] == state["assign_job_id"]), None)
        assert job is not None
        assert state["new_tech_id"] not in (job.get("tech_ids") or [])

    def test_delete_missing_tech_404(self):
        r = requests.delete(f"{API}/techs/TECH-NOPE-XYZ", headers=HEADERS, timeout=20)
        assert r.status_code == 404


# ================= CLEANING GUIDE =================
class TestGuide:
    def test_guide_requires_auth(self):
        r = requests.get(f"{API}/guide", timeout=20)
        assert r.status_code in (401, 403)

    def test_guide_structure(self):
        r = requests.get(f"{API}/guide", headers=HEADERS, timeout=20)
        assert r.status_code == 200, r.text
        g = r.json()
        assert isinstance(g.get("phases"), list) and len(g["phases"]) == 9
        assert g.get("supply_kit") and len(g["supply_kit"]) >= 5
        assert len(g.get("upsells", [])) >= 3
        assert g.get("safety") and g.get("quality_bar")
        for ph in g["phases"]:
            assert "phase" in ph and "steps" in ph and "minutes" in ph
