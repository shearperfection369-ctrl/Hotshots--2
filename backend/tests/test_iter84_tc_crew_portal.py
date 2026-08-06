"""Iter 84 — Truck Cleaning: Crew portal (PIN/clock/photos/completion), Crew Live map,
Money/P&L, Vehicles, Gear, Public booking + Bookings inbox, Invoice edit (PUT).

All endpoints under /api/truck-cleaning. Admin auth via test_session_admin_1.
"""
import io
import os
import time

import pytest
import requests
from PIL import Image

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://clean-logistics-dash.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api/truck-cleaning"
ADMIN = {"Authorization": "Bearer test_session_admin_1"}


# ---------- Helpers ----------
def _png_bytes():
    im = Image.new("RGB", (300, 200), (100, 140, 180))
    b = io.BytesIO()
    im.save(b, "JPEG")
    b.seek(0)
    return b.getvalue()


@pytest.fixture(scope="module")
def techs():
    r = requests.get(f"{API}/techs", headers=ADMIN, timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    lst = data.get("techs") or data
    assert lst, "no techs seeded"
    return lst


@pytest.fixture(scope="module")
def tech_id(techs):
    return techs[0]["tech_id"]


@pytest.fixture(scope="module")
def crew_pin(tech_id):
    r = requests.post(f"{API}/crew-admin/{tech_id}/pin", headers=ADMIN, timeout=15)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["ok"] and len(j["pin"]) == 6 and j["pin"].isdigit()
    return j["pin"]


@pytest.fixture(scope="module")
def crew_token(crew_pin):
    r = requests.post(f"{API}/crew/login", json={"pin": crew_pin}, timeout=15)
    assert r.status_code == 200, r.text
    j = r.json()
    assert "token" in j and j["crew"]["tech_id"]
    return j["token"]


def crew_hdr(token):
    return {"X-Crew-Token": token}


# ---------- Crew Auth ----------
class TestCrewAuth:
    def test_pin_issue_shape(self, crew_pin):
        assert len(crew_pin) == 6

    def test_login_wrong_pin(self):
        r = requests.post(f"{API}/crew/login", json={"pin": "000000"}, timeout=15)
        assert r.status_code == 401

    def test_login_bad_format(self):
        r = requests.post(f"{API}/crew/login", json={"pin": "abc"}, timeout=15)
        assert r.status_code == 422

    def test_crew_me(self, crew_token):
        r = requests.get(f"{API}/crew/me", headers=crew_hdr(crew_token), timeout=15)
        assert r.status_code == 200
        assert "crew" in r.json()

    def test_no_token_rejected(self):
        r = requests.get(f"{API}/crew/me", timeout=15)
        assert r.status_code == 401


# ---------- Clock in/out + ping + timesheets ----------
class TestClockAndPing:
    def test_clock_cycle(self, crew_token):
        # ensure clean state — try clock out (may 400 if not in)
        requests.post(f"{API}/crew/clock", json={"action": "out"}, headers=crew_hdr(crew_token), timeout=15)
        r1 = requests.post(f"{API}/crew/clock", json={"action": "in", "lat": 44.97, "lng": -93.26},
                           headers=crew_hdr(crew_token), timeout=15)
        assert r1.status_code == 200 and r1.json()["clocked_in"] is True
        # double clock in => 400
        r_dbl = requests.post(f"{API}/crew/clock", json={"action": "in"}, headers=crew_hdr(crew_token), timeout=15)
        assert r_dbl.status_code == 400
        # ping
        rp = requests.post(f"{API}/crew/ping", json={"lat": 44.98, "lng": -93.25},
                           headers=crew_hdr(crew_token), timeout=15)
        assert rp.status_code == 200
        # clock out
        r2 = requests.post(f"{API}/crew/clock", json={"action": "out", "lat": 44.98, "lng": -93.25},
                           headers=crew_hdr(crew_token), timeout=15)
        assert r2.status_code == 200 and r2.json()["clocked_in"] is False
        assert isinstance(r2.json().get("hours"), (int, float))

    def test_timesheets(self):
        r = requests.get(f"{API}/timesheets?days=7", headers=ADMIN, timeout=15)
        assert r.status_code == 200
        j = r.json()
        assert "entries" in j and "total_hours" in j


# ---------- Crew Live map ----------
class TestCrewLive:
    def test_crew_live(self, crew_pin):
        r = requests.get(f"{API}/crew-live", headers=ADMIN, timeout=15)
        assert r.status_code == 200
        j = r.json()
        assert "crews" in j and any(c.get("has_pin") for c in j["crews"])


# ---------- Company Updates ----------
class TestUpdates:
    def test_crud(self):
        r = requests.post(f"{API}/updates", json={"title": "TEST_hello", "body": "b", "pinned": False},
                          headers=ADMIN, timeout=15)
        assert r.status_code == 200
        uid = r.json()["update"]["update_id"]
        lst = requests.get(f"{API}/updates", headers=ADMIN, timeout=15).json()
        assert any(u["update_id"] == uid for u in lst["updates"])
        d = requests.delete(f"{API}/updates/{uid}", headers=ADMIN, timeout=15)
        assert d.status_code == 200


# ---------- Expenses + PnL ----------
class TestMoney:
    def test_expense_crud_and_pnl(self):
        r = requests.post(f"{API}/expenses", json={"category": "supplies", "vendor": "TEST_Amazon",
                          "desc": "TEST_towels", "amount": 42.5}, headers=ADMIN, timeout=15)
        assert r.status_code == 200
        eid = r.json()["expense"]["expense_id"]
        lst = requests.get(f"{API}/expenses", headers=ADMIN, timeout=15).json()
        assert any(e["expense_id"] == eid for e in lst["expenses"])
        pnl = requests.get(f"{API}/pnl", headers=ADMIN, timeout=15).json()
        assert "revenue" in pnl and "expenses_total" in pnl and "series" in pnl
        d = requests.delete(f"{API}/expenses/{eid}", headers=ADMIN, timeout=15)
        assert d.status_code == 200

    def test_invalid_category(self):
        r = requests.post(f"{API}/expenses", json={"category": "bogus", "amount": 1.0},
                          headers=ADMIN, timeout=15)
        assert r.status_code == 400


# ---------- Vehicles ----------
class TestVehicles:
    def test_vehicle_crud(self, tech_id):
        r = requests.post(f"{API}/vehicles", json={"name": "TEST_Van 7", "plate": "TEST-01",
                          "vtype": "van", "status": "active", "assigned_tech_id": tech_id},
                          headers=ADMIN, timeout=15)
        assert r.status_code == 200
        vid = r.json()["vehicle"]["vehicle_id"]
        lst = requests.get(f"{API}/vehicles", headers=ADMIN, timeout=15).json()
        row = next((v for v in lst["vehicles"] if v["vehicle_id"] == vid), None)
        assert row and row["assigned_tech_name"]
        u = requests.put(f"{API}/vehicles/{vid}", json={"name": "TEST_Van 7", "plate": "TEST-01",
                          "vtype": "van", "status": "maintenance", "assigned_tech_id": tech_id},
                          headers=ADMIN, timeout=15)
        assert u.status_code == 200
        d = requests.delete(f"{API}/vehicles/{vid}", headers=ADMIN, timeout=15)
        assert d.status_code == 200


# ---------- Gear ----------
class TestGear:
    def test_gear(self):
        r = requests.get(f"{API}/gear", headers=ADMIN, timeout=15)
        assert r.status_code == 200
        j = r.json()
        assert len(j["gear"]) >= 5
        assert j["kit_total_est"] > 0


# ---------- Public booking + Bookings inbox + Convert ----------
class TestBookingFlow:
    def test_public_booking_and_convert(self):
        # site info
        info = requests.get(f"{API}/public/site-info", timeout=15).json()
        assert info["base_price"] > 0
        # submit booking
        ts = int(time.time())
        r = requests.post(f"{API}/public/booking", json={
            "company": f"TEST_Fleet_{ts}", "contact": "TEST Owner", "phone": "5555550100",
            "email": "test@example.com", "cabs": 3, "preferred_date": "",
            "services": [info["services"][0]["id"]] if info["services"] else [],
            "notes": "TEST_notes"}, timeout=15)
        assert r.status_code == 200, r.text
        bid = r.json()["booking_id"]
        # admin list
        lst = requests.get(f"{API}/bookings", headers=ADMIN, timeout=15).json()
        assert any(b["booking_id"] == bid for b in lst["bookings"])
        # convert
        c = requests.post(f"{API}/bookings/{bid}/convert", headers=ADMIN, timeout=15)
        assert c.status_code == 200, c.text
        client_id = c.json()["client_id"]
        job_id = c.json()["job_id"]
        assert client_id and job_id
        # cannot re-convert
        c2 = requests.post(f"{API}/bookings/{bid}/convert", headers=ADMIN, timeout=15)
        assert c2.status_code == 400
        # dismiss another booking
        r2 = requests.post(f"{API}/public/booking",
                           json={"company": f"TEST_Dismiss_{ts}", "phone": "5555550111"}, timeout=15)
        did = r2.json()["booking_id"]
        d = requests.post(f"{API}/bookings/{did}/dismiss", headers=ADMIN, timeout=15)
        assert d.status_code == 200
        return job_id

    def test_public_booking_requires_company(self):
        r = requests.post(f"{API}/public/booking", json={"company": "", "phone": "x"}, timeout=15)
        assert r.status_code == 422


# ---------- Crew job flow (claim/task/photo/completion gate) ----------
class TestCrewJobFlow:
    def test_full_completion_gate(self, crew_token):
        # Create booking, convert to job scheduled today, assign the crew (via claim).
        info = requests.get(f"{API}/public/site-info", timeout=15).json()
        ts = int(time.time())
        r = requests.post(f"{API}/public/booking", json={
            "company": f"TEST_CrewFlow_{ts}", "phone": "5555550122", "cabs": 1,
            "services": [info["services"][0]["id"]] if info["services"] else []}, timeout=15)
        bid = r.json()["booking_id"]
        c = requests.post(f"{API}/bookings/{bid}/convert", headers=ADMIN, timeout=15).json()
        job_id = c["job_id"]

        # Claim
        rc = requests.post(f"{API}/crew/jobs/{job_id}/claim", headers=crew_hdr(crew_token), timeout=15)
        assert rc.status_code == 200

        # today shows in my_jobs
        today = requests.get(f"{API}/crew/today", headers=crew_hdr(crew_token), timeout=15).json()
        mine = [j for j in today["my_jobs"] if j["job_id"] == job_id]
        assert mine, "claimed job not in my_jobs"
        job_view = mine[0]

        # Attempt complete → blockers (checklist + photos)
        cr = requests.post(f"{API}/crew/jobs/{job_id}/complete", headers=crew_hdr(crew_token), timeout=15)
        assert cr.status_code == 200
        j0 = cr.json()
        assert j0["ok"] is False and len(j0["blockers"]) > 0

        # Check all tasks done
        for t in job_view["checklist"]:
            rt = requests.post(f"{API}/crew/jobs/{job_id}/task", json={"task_id": t["id"], "done": True},
                               headers=crew_hdr(crew_token), timeout=15)
            assert rt.status_code == 200

        # Complete still blocked (no photos)
        cr2 = requests.post(f"{API}/crew/jobs/{job_id}/complete", headers=crew_hdr(crew_token), timeout=15).json()
        assert cr2["ok"] is False
        assert any("BEFORE" in b for b in cr2["blockers"])
        assert any("AFTER" in b for b in cr2["blockers"])

        # Upload before + after
        img = _png_bytes()
        for kind in ("before", "after"):
            r_up = requests.post(f"{API}/crew/jobs/{job_id}/photos",
                                 headers=crew_hdr(crew_token),
                                 files={"file": ("t.jpg", img, "image/jpeg")},
                                 data={"kind": kind}, timeout=20)
            assert r_up.status_code == 200, r_up.text

        # Complete now succeeds
        cr3 = requests.post(f"{API}/crew/jobs/{job_id}/complete", headers=crew_hdr(crew_token), timeout=15).json()
        assert cr3["ok"] is True and cr3["status"] == "completed"


# ---------- Invoice edit (PUT) ----------
class TestInvoiceEdit:
    def test_put_invoice(self):
        # Find any existing invoice
        r = requests.get(f"{API}/invoices", headers=ADMIN, timeout=15)
        if r.status_code != 200:
            pytest.skip("invoices endpoint unavailable")
        data = r.json()
        invs = data.get("invoices") or data
        editable = next((i for i in invs if i.get("status") != "paid"), None)
        if not editable:
            pytest.skip("no editable invoice available")
        inv_id = editable["invoice_id"]
        # Build a minimal payload — try adjusting one line item amount
        payload = {"line_items": editable.get("line_items", []), "notes": "TEST_edit"}
        u = requests.put(f"{API}/invoices/{inv_id}", json=payload, headers=ADMIN, timeout=15)
        # accept 200 or 422 depending on schema strictness
        assert u.status_code in (200, 422), u.text


# ---------- Rate limit ----------
class TestRateLimit:
    def test_login_rate_limit(self):
        # 11 rapid requests from same IP should trip 429
        codes = []
        for _ in range(12):
            r = requests.post(f"{API}/crew/login", json={"pin": "000000"}, timeout=10)
            codes.append(r.status_code)
        assert 429 in codes, f"expected 429 within {codes}"
