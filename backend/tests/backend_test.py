"""
Tennant TMS — Comprehensive backend test suite
Covers: health, auth, facilities, shipments, KPIs, weather/news/traffic,
integrations, trailers, HS lookup, links, chat, freight bills,
carrier onboarding, driver mobile (auth-free), and admin seed.
"""
import os
import json
import time
import asyncio
import pytest
import requests
import websockets

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://clean-logistics-dash.preview.emergentagent.com").rstrip("/")


# ---------- Health & Root ----------
class TestHealth:
    def test_root(self):
        r = requests.get(f"{BASE_URL}/api/")
        assert r.status_code == 200
        d = r.json()
        assert d.get("status") == "ok"
        assert "Tennant" in d.get("service", "")


# ---------- Auth ----------
class TestAuth:
    def test_me_unauthenticated(self):
        r = requests.get(f"{BASE_URL}/api/auth/me")
        assert r.status_code == 401

    def test_me_authenticated(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/auth/me")
        assert r.status_code == 200
        d = r.json()
        assert "user_id" in d and "email" in d and "name" in d
        assert d["role"] == "dispatcher"

    def test_invalid_token(self):
        r = requests.get(f"{BASE_URL}/api/auth/me", headers={"Authorization": "Bearer invalid_token_xyz"})
        assert r.status_code == 401


# ---------- Admin Seed ----------
class TestSeed:
    def test_seed_force(self, api_client):
        r = api_client.post(f"{BASE_URL}/api/admin/seed?force=true")
        assert r.status_code == 200
        d = r.json()
        assert d.get("ok") is True
        # When force=True the route returns shipments/bills/onboardings counts
        assert d.get("shipments", 0) >= 1
        assert d.get("bills", 0) >= 1
        assert d.get("onboardings", 0) >= 1


# ---------- Facilities ----------
class TestFacilities:
    def test_list(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/facilities")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list) and len(data) == 3
        ids = {x["id"] for x in data}
        assert ids == {"GVM", "HOM", "LVK"}

    def test_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/facilities")
        assert r.status_code == 401


# ---------- Shipments ----------
class TestShipments:
    def test_list(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/shipments")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list) and len(data) >= 1
        s = data[0]
        for k in ("shipment_id", "mode", "carrier", "status", "origin", "destination"):
            assert k in s

    def test_filter_mode(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/shipments?mode=TL")
        assert r.status_code == 200
        data = r.json()
        for s in data:
            assert s["mode"] == "TL"

    def test_filter_status(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/shipments?status=delivered")
        assert r.status_code == 200
        for s in r.json():
            assert s["status"] == "delivered"

    def test_get_specific(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/shipments")
        sid = r.json()[0]["shipment_id"]
        r2 = api_client.get(f"{BASE_URL}/api/shipments/{sid}")
        assert r2.status_code == 200
        assert r2.json()["shipment_id"] == sid

    def test_get_notfound(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/shipments/SHP-NOTREAL")
        assert r.status_code == 404

    def test_create_shipment(self, api_client):
        payload = {
            "reference": "TEST-PYTEST-001",
            "mode": "TL",
            "carrier": "XPO Logistics",
            "origin_facility": "GVM",
            "destination_city": "Dallas, TX",
            "destination_lat": 32.7767,
            "destination_lng": -96.7970,
            "pickup_date": "2026-01-15",
            "weight_lbs": 12500,
            "pieces": 5,
            "commodity": "Floor scrubbers (T16AMR)",
            "value_usd": 45000,
        }
        r = api_client.post(f"{BASE_URL}/api/shipments", json=payload)
        assert r.status_code == 200, r.text
        s = r.json()
        assert s["mode"] == "TL"
        assert s["carrier"] == "XPO Logistics"
        assert s["status"] == "pending"
        assert s["origin"].get("facility") == "GVM"
        # Verify persistence
        r2 = api_client.get(f"{BASE_URL}/api/shipments/{s['shipment_id']}")
        assert r2.status_code == 200
        assert r2.json()["reference"] == "TEST-PYTEST-001"


# ---------- KPIs ----------
class TestKPIs:
    def test_kpis(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/kpis")
        assert r.status_code == 200
        d = r.json()
        assert "totals" in d and "by_mode" in d and "by_carrier" in d and "trend" in d
        assert d["totals"]["total"] >= 1
        assert len(d["trend"]) == 14


# ---------- Live feeds ----------
class TestFeeds:
    def test_weather(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/weather")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 3
        # Real Open-Meteo: at least one should return temperature
        with_temp = [d for d in data if d.get("temperature_f") is not None]
        assert len(with_temp) >= 1, f"No real weather data returned: {data}"

    def test_news(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/news")
        assert r.status_code == 200
        assert len(r.json()) >= 5

    def test_traffic(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/traffic")
        assert r.status_code == 200
        assert len(r.json()) >= 3

    def test_integrations(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/integrations")
        assert r.status_code == 200
        data = r.json()
        ids = {x["id"] for x in data}
        for needed in ("sap_s4hana", "powerbi", "ups", "fedex", "dhl", "xpo", "saia", "arcbest", "rl", "fastfrate", "kuehne"):
            assert needed in ids


# ---------- Trailers / HS / Links ----------
class TestRef:
    def test_trailers(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/trailers")
        assert r.status_code == 200
        assert len(r.json()) == 8

    def test_hs_lookup_search(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/hs-lookup", params={"q": "scrubber"})
        assert r.status_code == 200
        results = r.json()
        assert len(results) >= 1
        assert any("scrub" in c["description"].lower() for c in results)

    def test_hs_lookup_all(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/hs-lookup")
        assert r.status_code == 200
        assert len(r.json()) >= 10

    def test_links(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/links")
        assert r.status_code == 200
        assert len(r.json()) >= 8


# ---------- Chat ----------
class TestChat:
    def test_channels(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/chat/channels")
        assert r.status_code == 200
        assert len(r.json()) == 7

    def test_messages(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/chat/messages", params={"channel": "general"})
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_websocket(self, session_token):
        """WS auth via token query, send a message and receive broadcast."""
        ws_url = BASE_URL.replace("https://", "wss://").replace("http://", "ws://") + f"/api/ws/chat?token={session_token}"

        async def _run():
            async with websockets.connect(ws_url, open_timeout=10) as ws:
                await ws.send(json.dumps({"channel": "general", "text": "pytest hello"}))
                msg = await asyncio.wait_for(ws.recv(), timeout=8)
                d = json.loads(msg)
                assert d.get("type") == "message"
                assert d["data"]["text"] == "pytest hello"

        asyncio.run(_run())


# ---------- Freight Audit & Pay ----------
class TestFreightBills:
    def test_list(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/freight-bills")
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 1
        assert "bill_id" in data[0]

    def test_summary(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/freight-bills/summary")
        assert r.status_code == 200
        d = r.json()
        for k in ("total_billed", "paid", "pending", "disputed", "overcharges_detected", "count"):
            assert k in d

    def test_filter(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/freight-bills", params={"status": "paid"})
        assert r.status_code == 200
        for b in r.json():
            assert b["status"] == "paid"

    def test_approve_pay_dispute(self, auditor_client, api_client):
        """Freight ops require auditor or admin since iter 2 RBAC change."""
        bills = auditor_client.get(f"{BASE_URL}/api/freight-bills").json()
        # Dispatcher should be forbidden
        b0 = bills[0]["bill_id"]
        r_forbid = api_client.post(f"{BASE_URL}/api/freight-bills/{b0}/approve")
        assert r_forbid.status_code == 403
        # Auditor can approve
        b1 = bills[0]["bill_id"]
        r = auditor_client.post(f"{BASE_URL}/api/freight-bills/{b1}/approve")
        assert r.status_code == 200
        # Pay
        b2 = bills[1]["bill_id"] if len(bills) > 1 else b1
        r = auditor_client.post(f"{BASE_URL}/api/freight-bills/{b2}/pay")
        assert r.status_code == 200
        all_bills = auditor_client.get(f"{BASE_URL}/api/freight-bills").json()
        paid = next((b for b in all_bills if b["bill_id"] == b2), None)
        assert paid is not None and paid["status"] == "paid"
        # Dispute
        b3 = bills[2]["bill_id"] if len(bills) > 2 else b1
        r = auditor_client.post(f"{BASE_URL}/api/freight-bills/{b3}/dispute", json={"reason": "Test overcharge"})
        assert r.status_code == 200

    def test_freight_404_on_missing(self, auditor_client):
        for action in ("approve", "pay", "dispute"):
            r = auditor_client.post(f"{BASE_URL}/api/freight-bills/BILL-NOTREAL/{action}", json={"reason": "x"})
            assert r.status_code == 404


# ---------- Carrier Onboarding ----------
class TestCarrierOnboarding:
    def test_list(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/carriers/onboarding")
        assert r.status_code == 200
        assert len(r.json()) >= 1

    def test_create_and_decide(self, api_client, admin_client):
        payload = {
            "legal_name": "TEST_Pytest Carrier LLC",
            "dba": "TestPytest",
            "mc_number": "MC-999999",
            "dot_number": "9999999",
            "scac": "TPTC",
            "mode": "TL",
            "contact_name": "QA Bot",
            "contact_email": "qa@test.com",
            "contact_phone": "+1-555-555-5555",
            "insurance_amount": 1000000,
            "insurance_expiry": "2026-12-31",
            "safety_rating": "Satisfactory",
            "csa_score": 40,
            "notes": "pytest",
        }
        r = api_client.post(f"{BASE_URL}/api/carriers/onboarding", json=payload)
        assert r.status_code == 200, r.text
        d = r.json()
        oid = d["onboarding_id"]
        assert d["status"] == "in_review"

        # Toggle document fields
        for f in ("w9_received", "coi_received", "contract_signed"):
            r2 = api_client.post(f"{BASE_URL}/api/carriers/onboarding/{oid}/toggle", json={"field": f})
            assert r2.status_code == 200

        # Decision now requires admin per iter 2; dispatcher should get 403
        r_forbid = api_client.post(f"{BASE_URL}/api/carriers/onboarding/{oid}/decision", json={"decision": "approved"})
        assert r_forbid.status_code == 403

        # Admin can decide
        r3 = admin_client.post(f"{BASE_URL}/api/carriers/onboarding/{oid}/decision", json={"decision": "approved", "notes": "ok"})
        assert r3.status_code == 200

        # Invalid decision
        r4 = admin_client.post(f"{BASE_URL}/api/carriers/onboarding/{oid}/decision", json={"decision": "maybe"})
        assert r4.status_code == 400

        # Invalid toggle field
        r5 = api_client.post(f"{BASE_URL}/api/carriers/onboarding/{oid}/toggle", json={"field": "fake_field"})
        assert r5.status_code == 400


# ---------- Driver Mobile (auth-free) ----------
class TestDriver:
    def test_get_shipment_no_auth(self, api_client):
        sid = api_client.get(f"{BASE_URL}/api/shipments").json()[0]["shipment_id"]
        # auth-free request
        r = requests.get(f"{BASE_URL}/api/driver/shipment/{sid}")
        assert r.status_code == 200
        d = r.json()
        assert "shipment" in d and "checkins" in d

    def test_get_shipment_notfound(self):
        r = requests.get(f"{BASE_URL}/api/driver/shipment/SHP-DOESNOTEXIST")
        assert r.status_code == 404

    def test_checkin_no_auth_updates_shipment(self, api_client):
        sid = api_client.get(f"{BASE_URL}/api/shipments").json()[0]["shipment_id"]
        payload = {
            "shipment_id": sid,
            "driver_name": "Test Driver",
            "driver_phone": "+1-555-000-0001",
            "status": "en_route",
            "lat": 39.0,
            "lng": -90.0,
            "location_text": "St Louis",
            "note": "pytest",
            "fuel_pct": 75,
        }
        r = requests.post(f"{BASE_URL}/api/driver/checkin", json=payload)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("ok") is True and d.get("shipment_status") == "in_transit"

        # Verify shipment updated
        s = api_client.get(f"{BASE_URL}/api/shipments/{sid}").json()
        assert s["status"] == "in_transit"
        assert s["current_location"]["city"] == "St Louis"

    def test_checkin_invalid_shipment(self):
        payload = {
            "shipment_id": "SHP-NOTREAL",
            "driver_name": "X",
            "driver_phone": "+1",
            "status": "en_route",
        }
        r = requests.post(f"{BASE_URL}/api/driver/checkin", json=payload)
        assert r.status_code == 404

    def test_list_checkins_requires_auth(self, api_client):
        r = requests.get(f"{BASE_URL}/api/driver/checkins")
        assert r.status_code == 401
        r2 = api_client.get(f"{BASE_URL}/api/driver/checkins")
        assert r2.status_code == 200
        assert isinstance(r2.json(), list)


# ---------- Logout ----------
class TestLogout:
    def test_logout_ok(self, api_client):
        # Logout without a cookie still returns ok (token in header is not deleted, but endpoint is idempotent)
        r = api_client.post(f"{BASE_URL}/api/auth/logout")
        assert r.status_code == 200
        assert r.json().get("ok") is True
