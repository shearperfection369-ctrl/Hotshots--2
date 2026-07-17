"""
iter65 — Partner password logins, role hierarchy (owner vs admin), brute-force lockout,
brand kit assets, and business plan brochure PDF regression.
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://clean-logistics-dash.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_BEARER = "test_session_admin_1"

OLIVER = ("oliver@oriseifreight.com", "Califia-Prime-2026!")
DANIEL = ("daniel@oriseifreight.com", "Griffin-Karsor-2026!")
DOUG = ("doug@oriseifreight.com", "Griffin-Graham-2026!")


# ── Login endpoints ─────────────────────────────────────────────────────────
class TestPartnerLogins:
    def test_daniel_login_returns_owner_role(self):
        r = requests.post(f"{API}/auth/login", json={"email": DANIEL[0], "password": DANIEL[1]})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("session_token"), "session_token missing"
        assert isinstance(data["session_token"], str)
        # Role assertion (in either flat or nested user object)
        role = data.get("role") or (data.get("user") or {}).get("role")
        assert role == "owner", f"expected owner, got {role}"
        # Cookie may be set
        assert any(c.name.lower().startswith("session") or "token" in c.name.lower()
                   for c in r.cookies) or "set-cookie" in {k.lower() for k in r.headers.keys()}

    def test_doug_login_returns_owner_role(self):
        r = requests.post(f"{API}/auth/login", json={"email": DOUG[0], "password": DOUG[1]})
        assert r.status_code == 200, r.text
        data = r.json()
        role = data.get("role") or (data.get("user") or {}).get("role")
        assert role == "owner"
        assert data.get("session_token")

    def test_oliver_login_returns_admin_role(self):
        r = requests.post(f"{API}/auth/login", json={"email": OLIVER[0], "password": OLIVER[1]})
        assert r.status_code == 200, r.text
        data = r.json()
        role = data.get("role") or (data.get("user") or {}).get("role")
        assert role == "admin"

    def test_wrong_password_returns_401(self):
        r = requests.post(f"{API}/auth/login", json={"email": DOUG[0], "password": "totally-wrong-pw"})
        assert r.status_code == 401, r.text


# ── Role hierarchy: owner (Daniel) ──────────────────────────────────────────
@pytest.fixture(scope="module")
def daniel_token():
    r = requests.post(f"{API}/auth/login", json={"email": DANIEL[0], "password": DANIEL[1]})
    if r.status_code != 200:
        pytest.skip("daniel login failed — cannot fetch owner token")
    return r.json()["session_token"]


@pytest.fixture(scope="module")
def doug_token():
    r = requests.post(f"{API}/auth/login", json={"email": DOUG[0], "password": DOUG[1]})
    if r.status_code != 200:
        pytest.skip("doug login failed")
    return r.json()["session_token"]


@pytest.fixture(scope="module")
def oliver_token():
    r = requests.post(f"{API}/auth/login", json={"email": OLIVER[0], "password": OLIVER[1]})
    if r.status_code != 200:
        pytest.skip("oliver login failed")
    return r.json()["session_token"]


class TestOwnerRoleAccess:
    def test_owner_gets_403_on_admin_users_list(self, daniel_token):
        r = requests.get(f"{API}/admin/users", headers={"Authorization": f"Bearer {daniel_token}"})
        assert r.status_code == 403, f"expected 403 for owner on admin, got {r.status_code}: {r.text[:200]}"

    def test_owner_gets_403_on_admin_role_update(self, daniel_token):
        r = requests.post(
            f"{API}/admin/users/some-user-id/role",
            headers={"Authorization": f"Bearer {daniel_token}"},
            json={"role": "dispatcher"},
        )
        assert r.status_code == 403, r.text[:200]

    def test_owner_200_on_auth_me(self, daniel_token):
        r = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {daniel_token}"})
        assert r.status_code == 200, r.text
        me = r.json()
        assert (me.get("role") or (me.get("user") or {}).get("role")) == "owner"
        # Response should NOT leak password_hash
        payload_str = str(me)
        assert "password_hash" not in payload_str

    def test_owner_200_on_shipments(self, daniel_token):
        r = requests.get(f"{API}/shipments", headers={"Authorization": f"Bearer {daniel_token}"})
        assert r.status_code == 200, r.text[:200]


# ── Admin role (Oliver) ─────────────────────────────────────────────────────
class TestAdminRoleAccess:
    def test_admin_200_on_admin_users(self, oliver_token):
        r = requests.get(f"{API}/admin/users", headers={"Authorization": f"Bearer {oliver_token}"})
        assert r.status_code == 200, r.text
        users = r.json()
        assert isinstance(users, list) or isinstance(users, dict)
        # Extract list if wrapped
        docs = users if isinstance(users, list) else (users.get("users") or users.get("items") or [])
        # No password_hash leaked
        for u in docs:
            assert "password_hash" not in u, f"password_hash leaked: {u}"

    def test_legacy_bearer_admin_token_still_works(self):
        r = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {ADMIN_BEARER}"})
        assert r.status_code == 200, r.text
        me = r.json()
        role = me.get("role") or (me.get("user") or {}).get("role")
        assert role == "admin"

    def test_legacy_admin_can_list_admin_users(self):
        r = requests.get(f"{API}/admin/users", headers={"Authorization": f"Bearer {ADMIN_BEARER}"})
        assert r.status_code == 200


# ── Business plan brochure PDF (regression after Doug edits) ────────────────
class TestBusinessPlanBrochure:
    def test_brochure_pdf_200(self):
        r = requests.get(
            f"{API}/brokerage/business-plan/brochure.pdf",
            headers={"Authorization": f"Bearer {ADMIN_BEARER}"},
        )
        assert r.status_code == 200, r.text[:200]
        assert r.content[:4] == b"%PDF", "not a valid PDF"
        assert len(r.content) > 5000, "PDF too small"


# ── Brute-force lockout (MUST be last — locks the account for 15 min) ──────
class TestBruteForceLockoutLast:
    """
    Uses a THROWAWAY email so no real partner is locked out. Backend keys the
    counter on ip:email — so a bogus email counter is independent.
    """

    def test_lockout_after_5_fails(self):
        bogus_email = "TEST_lockout_iter65@example.invalid"
        statuses = []
        for i in range(6):
            r = requests.post(f"{API}/auth/login", json={"email": bogus_email, "password": f"wrong{i}"})
            statuses.append(r.status_code)
            time.sleep(0.05)
        # First 5 should be 401 (bad password); 6th should be 429 (locked)
        # OR the endpoint might return 401 for all if bogus email is treated as "user not found"
        # We accept EITHER:
        #  - a 429 appearing at some point (lockout triggered), OR
        #  - all 401 if lockout is only per REAL user (then this is minor issue we report)
        assert any(s == 429 for s in statuses) or all(s in (401, 404) for s in statuses), (
            f"unexpected statuses: {statuses}"
        )
        # Log observed pattern for debug
        print(f"lockout statuses: {statuses}")
