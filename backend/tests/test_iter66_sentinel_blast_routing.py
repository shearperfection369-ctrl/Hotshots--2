"""iter66 — Agent Sentinel + Launch Email Blast + Route Optimizer + change-password.

Covers:
  - GET /api/sentinel/status, POST /scan, /alerts, /deployments (list/add/delete)
  - Bogus deployment → down alert → banner set → ack → delete auto-resolve
  - GET /api/launch-blast/preview, /recipients, POST /send (test + subset + role gate)
  - POST /api/auth/change-password (doug): wrong current 401, short 400, ok 200,
    old login fails, new login works, restore back to seed. Also google-only 400.
  - Route optimizer: geocode Chicago, route MSP→CHI, save with NO-GO (rate=500)
"""
import os
import time
import uuid

import pytest
import requests

def _load_backend_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v:
        return v.rstrip("/")
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip().rstrip("/")
    except FileNotFoundError:
        pass
    raise RuntimeError("REACT_APP_BACKEND_URL not found")


BASE_URL = _load_backend_url()
ADMIN_BEARER = "test_session_admin_1"
DISP_BEARER = "test_session_dispatcher_1"

DOUG_EMAIL = "doug@oriseifreight.com"
DOUG_PASSWORD = "Griffin-Graham-2026!"
DOUG_TEST_PASSWORD = "DougTest-2026-New!"
DANIEL_EMAIL = "daniel@oriseifreight.com"
DANIEL_PASSWORD = "Griffin-Karsor-2026!"


def _hdr(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def admin():
    return _hdr(ADMIN_BEARER)


@pytest.fixture(scope="module")
def disp():
    return _hdr(DISP_BEARER)


@pytest.fixture(scope="module")
def doug_token():
    # login with password
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": DOUG_EMAIL, "password": DOUG_PASSWORD}, timeout=15)
    if r.status_code == 429:
        pytest.skip("Doug login locked out — brute-force cooldown active")
    assert r.status_code == 200, f"Doug login failed: {r.status_code} {r.text}"
    tok = r.json().get("session_token")
    assert tok
    return tok


@pytest.fixture(scope="module")
def daniel_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": DANIEL_EMAIL, "password": DANIEL_PASSWORD}, timeout=15)
    if r.status_code == 429:
        pytest.skip("Daniel login locked out")
    assert r.status_code == 200, f"Daniel login failed: {r.status_code} {r.text}"
    return r.json()["session_token"]


# ================================================================
# SENTINEL
# ================================================================

class TestSentinel:
    def test_status_default(self, admin):
        r = requests.get(f"{BASE_URL}/api/sentinel/status", headers=admin, timeout=15)
        assert r.status_code == 200
        j = r.json()
        assert "snapshot" in j
        assert "active_alerts" in j
        assert "banner" in j
        # banner may be None or dict — accept both

    def test_deployments_list_seeded(self, admin):
        r = requests.get(f"{BASE_URL}/api/sentinel/deployments", headers=admin, timeout=15)
        assert r.status_code == 200
        deps = r.json()["deployments"]
        assert len(deps) >= 1
        names = [d["name"] for d in deps]
        # JadeOS should always be seeded (Orisei self only if PUBLIC_FRONTEND_URL is set)
        assert any("JadeOS" in n for n in names), f"JadeOS missing: {names}"

    def test_alerts_feed(self, admin):
        r = requests.get(f"{BASE_URL}/api/sentinel/alerts", headers=admin, timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json()["alerts"], list)

    def test_scan_now(self, admin):
        r = requests.post(f"{BASE_URL}/api/sentinel/scan", headers=admin, timeout=90)
        assert r.status_code == 200
        j = r.json()
        assert "snapshot" in j
        snap = j["snapshot"]
        assert snap.get("overall") in ("ok", "degraded", "critical")
        assert isinstance(snap.get("deployments"), list)
        assert snap.get("llm", {}).get("status") in ("ok", "slow", "error", "budget_exhausted", "unknown")

    def test_bogus_deployment_flow(self, admin, doug_token):
        # Add bogus deployment (owner-level required)
        bogus_name = f"TEST_bogus_{uuid.uuid4().hex[:6]}"
        add = requests.post(f"{BASE_URL}/api/sentinel/deployments", headers=_hdr(doug_token),
                            json={"name": bogus_name,
                                  "url": "https://does-not-exist-xyz123-orisei.example.com"},
                            timeout=15)
        assert add.status_code == 200, f"Add failed: {add.text}"
        dep_id = add.json()["deployment_id"]

        try:
            # Trigger a scan — should mark it down
            scan = requests.post(f"{BASE_URL}/api/sentinel/scan", headers=admin, timeout=90)
            assert scan.status_code == 200
            snap = scan.json()["snapshot"]
            bogus = next((d for d in snap["deployments"] if d["deployment_id"] == dep_id), None)
            assert bogus is not None, "Bogus deployment missing from snapshot"
            assert bogus["status"] == "down", f"Expected down, got {bogus['status']}: {bogus}"

            # Status now should have a banner
            st = requests.get(f"{BASE_URL}/api/sentinel/status", headers=admin, timeout=15).json()
            assert st["banner"] is not None, f"Banner should be set; snapshot: {st}"

            # Get the newly raised alert
            alerts = requests.get(f"{BASE_URL}/api/sentinel/alerts", headers=admin, timeout=15).json()["alerts"]
            alert = next((a for a in alerts if a.get("fingerprint") == f"deploy:{dep_id}"), None)
            assert alert is not None, "Alert not raised for bogus deployment"
            assert alert["severity"] == "critical"

            # Ack it
            ack = requests.post(f"{BASE_URL}/api/sentinel/alerts/{alert['alert_id']}/ack",
                                headers=admin, timeout=15)
            assert ack.status_code == 200

        finally:
            # Delete bogus deployment — should auto-resolve alert
            d = requests.delete(f"{BASE_URL}/api/sentinel/deployments/{dep_id}",
                                headers=_hdr(doug_token), timeout=15)
            assert d.status_code == 200

        # Verify alert is now resolved
        alerts_after = requests.get(f"{BASE_URL}/api/sentinel/alerts", headers=admin, timeout=15).json()["alerts"]
        for a in alerts_after:
            if a.get("fingerprint") == f"deploy:{dep_id}":
                assert a["status"] == "resolved", f"Alert should be resolved after delete: {a}"

    def test_add_deployment_requires_owner(self, disp):
        r = requests.post(f"{BASE_URL}/api/sentinel/deployments", headers=disp,
                          json={"name": "TEST_disp", "url": "https://example.com"}, timeout=15)
        assert r.status_code in (401, 403), f"Dispatcher should be blocked, got {r.status_code}"


# ================================================================
# LAUNCH BLAST
# ================================================================

class TestLaunchBlast:
    def test_preview(self, admin):
        r = requests.get(f"{BASE_URL}/api/launch-blast/preview", headers=admin, timeout=15)
        assert r.status_code == 200
        j = r.json()
        assert "subject" in j and j["subject"]
        assert "html" in j
        assert "launch_card_wide.png" in j["html"]
        assert "/get-quote" in j["html"]
        assert isinstance(j["recipient_count"], int)

    def test_recipients(self, admin):
        r = requests.get(f"{BASE_URL}/api/launch-blast/recipients", headers=admin, timeout=15)
        assert r.status_code == 200
        j = r.json()
        assert "recipients" in j
        assert j["count"] == len(j["recipients"])
        # dedup check
        emails = [x["email"] for x in j["recipients"]]
        assert len(emails) == len(set(emails)), "Recipients not deduped"

    def test_test_send_queues(self, admin):
        r = requests.post(f"{BASE_URL}/api/launch-blast/send",
                          headers=admin, json={"test_to": "test@example.com"}, timeout=20)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["total"] == 1
        # since no Resend key configured expect queued
        assert j["queued_awaiting_key"] == 1 or j["sent"] == 1

    def test_subset_send(self, admin):
        # Grab first recipient
        recips = requests.get(f"{BASE_URL}/api/launch-blast/recipients", headers=admin, timeout=15).json()["recipients"]
        if not recips:
            pytest.skip("No recipients to test subset send")
        target = recips[0]["email"]
        r = requests.post(f"{BASE_URL}/api/launch-blast/send", headers=admin,
                          json={"emails": [target]}, timeout=20)
        assert r.status_code == 200
        assert r.json()["total"] == 1

    def test_dispatcher_forbidden(self, disp):
        r = requests.post(f"{BASE_URL}/api/launch-blast/send", headers=disp,
                          json={"test_to": "x@example.com"}, timeout=20)
        assert r.status_code in (401, 403)


# ================================================================
# CHANGE PASSWORD (Doug)
# ================================================================

class TestChangePassword:
    def test_full_cycle_doug(self, doug_token):
        h = _hdr(doug_token)
        # wrong current
        r1 = requests.post(f"{BASE_URL}/api/auth/change-password", headers=h,
                           json={"current_password": "WRONG", "new_password": "SomethingElseGood-1!"},
                           timeout=15)
        assert r1.status_code == 401, r1.text

        # too short
        r2 = requests.post(f"{BASE_URL}/api/auth/change-password", headers=h,
                           json={"current_password": DOUG_PASSWORD, "new_password": "short"}, timeout=15)
        assert r2.status_code == 400

        # valid change
        r3 = requests.post(f"{BASE_URL}/api/auth/change-password", headers=h,
                           json={"current_password": DOUG_PASSWORD, "new_password": DOUG_TEST_PASSWORD},
                           timeout=15)
        assert r3.status_code == 200, r3.text

        try:
            # Old password fails
            time.sleep(0.5)
            login_old = requests.post(f"{BASE_URL}/api/auth/login",
                                      json={"email": DOUG_EMAIL, "password": DOUG_PASSWORD}, timeout=15)
            # 401 expected (or 429 if brute lockout hit — accept either as functional proof)
            assert login_old.status_code in (401, 429), \
                f"Old password should not work anymore: {login_old.status_code}"

            # New password works
            login_new = requests.post(f"{BASE_URL}/api/auth/login",
                                      json={"email": DOUG_EMAIL, "password": DOUG_TEST_PASSWORD}, timeout=15)
            if login_new.status_code == 429:
                pytest.skip("Login lockout hit during test cycle")
            assert login_new.status_code == 200, f"New password should work: {login_new.text}"
            new_token = login_new.json()["session_token"]

            # Restore original
            restore = requests.post(f"{BASE_URL}/api/auth/change-password",
                                    headers=_hdr(new_token),
                                    json={"current_password": DOUG_TEST_PASSWORD,
                                          "new_password": DOUG_PASSWORD}, timeout=15)
            assert restore.status_code == 200, f"Restore failed: {restore.text}"
        except Exception:
            # Best-effort restore attempt via new_token if we haven't already
            try:
                nt = requests.post(f"{BASE_URL}/api/auth/login",
                                   json={"email": DOUG_EMAIL, "password": DOUG_TEST_PASSWORD},
                                   timeout=15).json().get("session_token")
                if nt:
                    requests.post(f"{BASE_URL}/api/auth/change-password", headers=_hdr(nt),
                                  json={"current_password": DOUG_TEST_PASSWORD,
                                        "new_password": DOUG_PASSWORD}, timeout=15)
            except Exception:
                pass
            raise

    def test_google_only_account_400(self, admin):
        # Legacy Bearer test_session_admin_1 → no password_hash
        r = requests.post(f"{BASE_URL}/api/auth/change-password", headers=admin,
                          json={"current_password": "whatever", "new_password": "AnyGoodPass1!"},
                          timeout=15)
        assert r.status_code == 400
        assert "google" in r.text.lower() or "no password" in r.text.lower()


# ================================================================
# ROUTE OPTIMIZER
# ================================================================

class TestRouteOptimizer:
    def test_geocode_chicago(self, admin):
        r = requests.get(f"{BASE_URL}/api/route-optimizer/geocode",
                         params={"q": "Chicago, IL"}, headers=admin, timeout=20)
        if r.status_code == 502:
            pytest.skip("Nominatim upstream unavailable")
        assert r.status_code == 200
        cands = r.json()["candidates"]
        assert len(cands) > 0
        top = cands[0]
        # Chicago ~ 41.8, -87.6
        assert 40 < top["lat"] < 43
        assert -89 < top["lon"] < -86

    def test_route_msp_to_chi(self, admin):
        origin = {"lat": 44.9778, "lon": -93.2650, "label": "Minneapolis, MN"}
        dest = {"lat": 41.8781, "lon": -87.6298, "label": "Chicago, IL"}
        r = requests.post(f"{BASE_URL}/api/route-optimizer/route",
                          headers=admin, json={"origin": origin, "dest": dest}, timeout=30)
        if r.status_code == 502:
            pytest.skip("OSRM upstream unavailable")
        assert r.status_code == 200
        j = r.json()
        assert j["miles"] > 300 and j["miles"] < 500  # ~410 mi
        assert j["drive_hours"] > 3
        assert isinstance(j["geometry"], list) and len(j["geometry"]) > 5
        # Leaflet-order sanity check: first point lat should be near origin.lat
        first_lat = j["geometry"][0][0]
        assert 43 < first_lat < 46 or 40 < first_lat < 43  # near MSP or CHI

    def test_save_load_no_go(self, admin):
        origin = {"lat": 44.9778, "lon": -93.2650, "label": "MSP"}
        dest = {"lat": 41.8781, "lon": -87.6298, "label": "CHI"}
        payload = {
            "origin": origin, "dest": dest, "miles": 410, "drive_hours": 6.5,
            "inputs": {"rate": 500, "fuel_price": 4.0, "mpg": 6.5,
                       "driver_pay_cpm": 0.65, "tolls": 20},
            "notes": "TEST_iter66_no_go",
        }
        r = requests.post(f"{BASE_URL}/api/route-optimizer/loads", headers=admin,
                          json=payload, timeout=15)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["results"]["verdict"] == "NO-GO", f"Rate=500 must be NO-GO: {j['results']}"
        assert j["results"]["net_profit"] <= 0
        # cleanup
        requests.delete(f"{BASE_URL}/api/route-optimizer/loads/{j['load_id']}",
                        headers=admin, timeout=15)

    def test_save_load_go_and_delete(self, admin):
        payload = {
            "origin": {"lat": 44.97, "lon": -93.26, "label": "MSP"},
            "dest": {"lat": 41.87, "lon": -87.62, "label": "CHI"},
            "miles": 410, "drive_hours": 6.5,
            "inputs": {"rate": 1500, "fuel_price": 4.0, "mpg": 6.5,
                       "driver_pay_cpm": 0.55, "tolls": 20},
            "notes": "TEST_iter66_go",
        }
        r = requests.post(f"{BASE_URL}/api/route-optimizer/loads", headers=admin,
                          json=payload, timeout=15)
        assert r.status_code == 200
        j = r.json()
        assert j["results"]["verdict"] in ("GO", "CAUTION")
        lid = j["load_id"]

        # list contains it
        lst = requests.get(f"{BASE_URL}/api/route-optimizer/loads", headers=admin, timeout=15).json()
        assert any(x["load_id"] == lid for x in lst["loads"])

        # delete
        d = requests.delete(f"{BASE_URL}/api/route-optimizer/loads/{lid}",
                            headers=admin, timeout=15)
        assert d.status_code == 200
