import os
import time
import pytest
import requests
import subprocess

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://clean-logistics-dash.preview.emergentagent.com").rstrip("/")


def _create_session_via_mongo(role: str = "dispatcher", label: str = "user"):
    """Create a user + session directly in MongoDB (Emergent auth mocking per /app/auth_testing.md)."""
    ts = int(time.time() * 1000)
    # add small extra digits so multiple fixtures don't collide in the same ms
    import random as _r
    suffix = _r.randint(1000, 9999)
    user_id = f"test-{label}-{ts}-{suffix}"
    token = f"test_session_{label}_{ts}_{suffix}"
    js = f"""
    use('test_database');
    db.users.insertOne({{
      user_id: '{user_id}',
      email: 'test.{label}.{ts}{suffix}@tennantco.com',
      name: 'Test {label.title()}',
      picture: 'https://via.placeholder.com/150',
      role: '{role}',
      created_at: new Date().toISOString()
    }});
    db.user_sessions.insertOne({{
      user_id: '{user_id}',
      session_token: '{token}',
      expires_at: new Date(Date.now() + 7*24*60*60*1000).toISOString(),
      created_at: new Date().toISOString()
    }});
    """
    subprocess.run(["mongosh", "--quiet", "--eval", js], check=True, capture_output=True)
    return token, user_id


def _make_client(token: str) -> requests.Session:
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json", "Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="session")
def session_token():
    token, _ = _create_session_via_mongo("dispatcher", "dispatcher")
    return token


@pytest.fixture(scope="session")
def api_client(session_token):
    # Default api_client is a dispatcher (backwards-compat with iteration 1 tests)
    return _make_client(session_token)


@pytest.fixture(scope="session")
def admin_session():
    token, user_id = _create_session_via_mongo("admin", "admin")
    return {"token": token, "user_id": user_id}


@pytest.fixture(scope="session")
def admin_client(admin_session):
    return _make_client(admin_session["token"])


@pytest.fixture(scope="session")
def auditor_session():
    token, user_id = _create_session_via_mongo("auditor", "auditor")
    return {"token": token, "user_id": user_id}


@pytest.fixture(scope="session")
def auditor_client(auditor_session):
    return _make_client(auditor_session["token"])


@pytest.fixture(scope="session")
def dispatcher_session(session_token):
    return {"token": session_token}


@pytest.fixture(scope="session")
def dispatcher_client(api_client):
    return api_client


@pytest.fixture(scope="session")
def base_url():
    return BASE_URL
