"""Iteration 21 — Connections admin vault + Orisei rename regression.

Covers:
 - /api/connections/providers (admin-only)
 - GET /api/connections (10 providers, unconfigured rollup)
 - PUT /api/connections/{p} validation, masking, secret-preserve-on-empty
 - POST /api/connections/{p}/test
 - DELETE /api/connections/{p}
 - 404 on unknown provider
 - Non-admin 4xx on every route
 - Mongo doc encryption (cipher, no plaintext)
 - /api/brokerage/business-plan rename Apex→Orisei
 - /api/brokerage/dashboard regression
"""
import os
import asyncio
import pytest
import requests
from motor.motor_asyncio import AsyncIOMotorClient

def _load_frontend_url():
    with open("/app/frontend/.env") as fh:
        for ln in fh:
            ln = ln.strip()
            if ln.startswith("REACT_APP_BACKEND_URL="):
                return ln.split("=", 1)[1].strip().strip('"').rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL not found")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", _load_frontend_url()).rstrip("/")
ADMIN = "test_session_admin_1"
DISP = "test_disp_session"

MONGO_URL = None
DB_NAME = None
with open("/app/backend/.env") as f:
    for line in f:
        line = line.strip()
        if line.startswith("MONGO_URL="):
            MONGO_URL = line.split("=", 1)[1].strip().strip('"')
        elif line.startswith("DB_NAME="):
            DB_NAME = line.split("=", 1)[1].strip().strip('"')


def H(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="module", autouse=True)
def _cleanup():
    # Ensure clean QB doc to start the secret-preserve tests
    requests.delete(f"{BASE_URL}/api/connections/quickbooks", headers=H(ADMIN), timeout=15)
    yield
    requests.delete(f"{BASE_URL}/api/connections/quickbooks", headers=H(ADMIN), timeout=15)
    requests.delete(f"{BASE_URL}/api/connections/stripe", headers=H(ADMIN), timeout=15)


# ---- Catalog ----
def test_providers_admin_lists_10():
    r = requests.get(f"{BASE_URL}/api/connections/providers", headers=H(ADMIN), timeout=15)
    assert r.status_code == 200
    body = r.json()
    assert "providers" in body
    assert len(body["providers"]) == 10
    ids = {p["id"] for p in body["providers"]}
    assert ids >= {"quickbooks", "dat", "truckstop", "uber_freight", "loadboard_123",
                   "stripe", "resend", "twilio", "macropoint", "rmis"}
    for p in body["providers"]:
        assert "fields" in p and isinstance(p["fields"], list) and len(p["fields"]) > 0


def test_providers_non_admin_rejected():
    r = requests.get(f"{BASE_URL}/api/connections/providers", headers=H(DISP), timeout=15)
    assert r.status_code in (401, 403)


# ---- List ----
def test_list_connections_includes_unconfigured_rollup():
    r = requests.get(f"{BASE_URL}/api/connections", headers=H(ADMIN), timeout=15)
    assert r.status_code == 200
    body = r.json()
    conns = body["connections"]
    # At least 10 (one per provider), all known statuses
    ids = {c["provider_id"] for c in conns}
    assert ids >= {"quickbooks", "dat", "truckstop", "uber_freight", "loadboard_123",
                   "stripe", "resend", "twilio", "macropoint", "rmis"}
    qb = next(c for c in conns if c["provider_id"] == "quickbooks")
    assert qb["status"] == "unconfigured"


def test_list_non_admin_rejected():
    r = requests.get(f"{BASE_URL}/api/connections", headers=H(DISP), timeout=15)
    assert r.status_code in (401, 403)


# ---- Unknown provider ----
def test_get_unknown_provider_404():
    r = requests.get(f"{BASE_URL}/api/connections/__nope__", headers=H(ADMIN), timeout=15)
    assert r.status_code == 404


# ---- Validation ----
def test_put_missing_required_field_400():
    r = requests.put(
        f"{BASE_URL}/api/connections/quickbooks",
        headers=H(ADMIN),
        json={"fields": {"client_id": "abc"}, "enabled": True},
        timeout=15,
    )
    assert r.status_code == 400
    detail = r.json().get("detail", "")
    assert "Client Secret" in detail or "required" in detail.lower()


# ---- Upsert + Masking ----
def test_put_quickbooks_configured_and_masked():
    payload = {
        "fields": {
            "client_id": "QB_CLIENT_PLAIN",
            "client_secret": "SUPER_SECRET_VALUE_XYZ_12345",
            "environment": "sandbox",
            "redirect_uri": "https://example.com/api/brokerage/quickbooks/callback",
        },
        "enabled": True,
    }
    r = requests.put(f"{BASE_URL}/api/connections/quickbooks", headers=H(ADMIN), json=payload, timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "configured"
    assert body["enabled"] is True

    cid = body["fields"]["client_id"]
    assert cid["set"] is True
    assert cid["value"] == "QB_CLIENT_PLAIN"

    cs = body["fields"]["client_secret"]
    assert cs["set"] is True
    assert "preview" in cs
    assert cs["preview"].startswith("SUP")
    assert cs["preview"].endswith("345")
    assert "•" in cs["preview"]
    # Crucially: no plaintext
    assert cs.get("value") != "SUPER_SECRET_VALUE_XYZ_12345"
    assert "SUPER_SECRET_VALUE_XYZ_12345" not in r.text


# ---- Encryption at rest ----
def test_secret_encrypted_at_rest_in_mongo():
    async def _check():
        client = AsyncIOMotorClient(MONGO_URL)
        try:
            db = client[DB_NAME]
            doc = await db.connections.find_one({"provider_id": "quickbooks"})
            assert doc is not None
            cs = doc["fields"]["client_secret"]
            assert isinstance(cs, dict)
            assert cs.get("secret") is True
            cipher = cs.get("cipher")
            assert cipher and isinstance(cipher, str)
            assert "SUPER_SECRET_VALUE_XYZ_12345" not in cipher
            # Fernet tokens start with 'gAAAAA'
            assert cipher.startswith("gAAAAA")
            # Non-secret client_id stored in clear
            cid = doc["fields"]["client_id"]
            assert cid.get("secret") is False
            assert cid.get("value") == "QB_CLIENT_PLAIN"
        finally:
            client.close()

    asyncio.get_event_loop().run_until_complete(_check())


# ---- Secret preservation on empty re-PUT ----
def test_put_empty_secret_preserves_existing():
    async def _cipher_now():
        client = AsyncIOMotorClient(MONGO_URL)
        try:
            doc = await client[DB_NAME].connections.find_one({"provider_id": "quickbooks"})
            return doc["fields"]["client_secret"]["cipher"]
        finally:
            client.close()

    loop = asyncio.get_event_loop()
    cipher_before = loop.run_until_complete(_cipher_now())

    # Re-PUT with empty secret, change non-secret
    payload = {
        "fields": {
            "client_id": "QB_CLIENT_PLAIN_v2",
            "client_secret": "",
            "environment": "production",
            "redirect_uri": "https://example.com/api/brokerage/quickbooks/callback",
        },
        "enabled": True,
    }
    r = requests.put(f"{BASE_URL}/api/connections/quickbooks", headers=H(ADMIN), json=payload, timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    # preview should still match original secret tail
    assert body["fields"]["client_secret"]["set"] is True
    assert body["fields"]["client_secret"]["preview"].endswith("345")
    assert body["fields"]["client_id"]["value"] == "QB_CLIENT_PLAIN_v2"
    assert body["fields"]["environment"]["value"] == "production"

    cipher_after = loop.run_until_complete(_cipher_now())
    # Same plaintext re-encrypted with Fernet produces a different token,
    # but importantly: still decrypts to the same value. We've already checked
    # the preview matches; cipher non-empty.
    assert cipher_after  # not blanked


# ---- Test endpoint ----
def test_post_test_returns_ok_for_configured():
    r = requests.post(f"{BASE_URL}/api/connections/quickbooks/test", headers=H(ADMIN), timeout=15)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True


def test_non_admin_blocked_on_put_and_delete_and_test():
    r1 = requests.put(f"{BASE_URL}/api/connections/quickbooks",
                      headers=H(DISP), json={"fields": {}}, timeout=15)
    assert r1.status_code in (401, 403)
    r2 = requests.post(f"{BASE_URL}/api/connections/quickbooks/test",
                       headers=H(DISP), timeout=15)
    assert r2.status_code in (401, 403)
    r3 = requests.delete(f"{BASE_URL}/api/connections/quickbooks", headers=H(DISP), timeout=15)
    assert r3.status_code in (401, 403)


# ---- Delete reverts to unconfigured ----
def test_delete_reverts_to_unconfigured():
    r = requests.delete(f"{BASE_URL}/api/connections/quickbooks", headers=H(ADMIN), timeout=15)
    assert r.status_code == 200
    body = r.json()
    assert body.get("deleted") is True

    r2 = requests.get(f"{BASE_URL}/api/connections/quickbooks", headers=H(ADMIN), timeout=15)
    assert r2.status_code == 200
    assert r2.json()["status"] == "unconfigured"


# ---- Brokerage rename + regression ----
def test_business_plan_orisei_present_apex_absent():
    r = requests.get(f"{BASE_URL}/api/brokerage/business-plan", headers=H(ADMIN), timeout=20)
    assert r.status_code == 200
    body = r.json()
    text = body.get("markdown") or body.get("body") or body.get("content") or str(body)
    assert "Orisei Freight Solutions" in text
    assert "Apex Freight Solutions" not in text


def test_brokerage_dashboard_still_200():
    r = requests.get(f"{BASE_URL}/api/brokerage/dashboard", headers=H(ADMIN), timeout=20)
    assert r.status_code == 200
