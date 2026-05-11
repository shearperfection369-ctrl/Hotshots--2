import os
import time
import pytest
import requests
import subprocess

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://clean-logistics-dash.preview.emergentagent.com").rstrip("/")


def _create_session_via_mongo():
    """Create a user + session directly in MongoDB (Emergent auth mocking per /app/auth_testing.md)."""
    ts = int(time.time() * 1000)
    user_id = f"test-user-{ts}"
    token = f"test_session_{ts}"
    js = f"""
    use('test_database');
    db.users.insertOne({{
      user_id: '{user_id}',
      email: 'test.user.{ts}@tennantco.com',
      name: 'Test Dispatcher',
      picture: 'https://via.placeholder.com/150',
      role: 'dispatcher',
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


@pytest.fixture(scope="session")
def session_token():
    token, _ = _create_session_via_mongo()
    return token


@pytest.fixture(scope="session")
def api_client(session_token):
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json", "Authorization": f"Bearer {session_token}"})
    return s


@pytest.fixture(scope="session")
def base_url():
    return BASE_URL
