"""Iter 54 backend tests — Parcel Rating (FedEx+UPS) + SPS Commerce EDI.

Sample-mode is expected: FEDEX_/UPS_/SPS_ env vars are absent. All endpoints
must fall back to synthetic data deterministically.
"""
import os
import pytest
import requests
from pathlib import Path


def _load_frontend_env():
    env_path = Path("/app/frontend/.env")
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip().strip('"')
    return os.environ.get("REACT_APP_BACKEND_URL", "")


BASE_URL = _load_frontend_env().rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL required"
ADMIN_TOKEN = "test_session_admin_1"


@pytest.fixture(scope="module")
def admin_client():
    s = requests.Session()
    s.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {ADMIN_TOKEN}",
    })
    return s


# ============================================================
# Parcel Rating (FedEx + UPS)
# ============================================================
class TestParcelProvider:
    def test_provider_returns_sample_shape(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/parcel/provider")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "fedex" in data and "ups" in data and "sample_mode" in data
        # Absence of live creds -> connected must be False and sample_mode True
        assert data["fedex"]["connected"] is False
        assert data["ups"]["connected"] is False
        assert data["sample_mode"] is True


class TestParcelQuote:
    payload_std = {
        "origin_zip": "30301",
        "destination_zip": "85001",
        "weight_lbs": 25,
        "length_in": 18,
        "width_in": 12,
        "height_in": 10,
        "package_count": 2,
        "residential": False,
    }

    def test_quote_returns_10_rates_sorted(self, admin_client):
        r = admin_client.post(f"{BASE_URL}/api/parcel/quote", json=self.payload_std)
        assert r.status_code == 200, r.text
        data = r.json()
        items = data["items"]
        assert len(items) >= 10, f"expected >=10 rates, got {len(items)}"
        # count per carrier
        fedex = [i for i in items if i["carrier"] == "FEDEX"]
        ups = [i for i in items if i["carrier"] == "UPS"]
        assert len(fedex) >= 5 and len(ups) >= 5
        # distance
        assert data["distance_mi"] > 1000, data["distance_mi"]
        # cheapest & fastest present
        assert data["cheapest"] and data["fastest"]
        # modes are sample (no keys)
        assert data["fedex_mode"] == "sample"
        assert data["ups_mode"] == "sample"
        # sorted ascending
        charges = [i["total_charge"] for i in items]
        assert charges == sorted(charges), "items must be ascending by total_charge"
        # each item shape
        for it in items:
            assert it["carrier"] in ("FEDEX", "UPS")
            assert it["service_code"] and it["service_name"]
            assert it["total_charge"] > 0
            assert it["currency"] == "USD"
            assert isinstance(it["transit_days"], int)

    def test_residential_surcharge_15pct(self, admin_client):
        r1 = admin_client.post(f"{BASE_URL}/api/parcel/quote", json=self.payload_std)
        p2 = dict(self.payload_std, residential=True)
        r2 = admin_client.post(f"{BASE_URL}/api/parcel/quote", json=p2)
        assert r1.status_code == 200 and r2.status_code == 200
        c1 = r1.json()["cheapest"]["total_charge"]
        c2 = r2.json()["cheapest"]["total_charge"]
        # ~15% higher
        assert c2 > c1
        ratio = c2 / c1
        assert 1.10 <= ratio <= 1.20, f"expected ~1.15x, got {ratio:.3f}"


class TestParcelConnect:
    def test_connect_fedex_flips_connected(self, admin_client):
        payload = {
            "client_id": "test_fedex_id_1234567",
            "client_secret": "test_fedex_secret_abcdef",
            "account_number": "999888777",
        }
        r = admin_client.post(f"{BASE_URL}/api/parcel/connect/fedex", json=payload)
        assert r.status_code == 200, r.text
        assert r.json()["ok"] is True
        p = admin_client.get(f"{BASE_URL}/api/parcel/provider").json()
        assert p["fedex"]["connected"] is True
        # sample_mode may still be True if UPS unconfigured (that's fine)
        # Now quote still falls back to sample because upstream 401s
        q = admin_client.post(f"{BASE_URL}/api/parcel/quote", json=TestParcelQuote.payload_std).json()
        assert q["fedex_mode"] == "sample"  # 401 fallback


# ============================================================
# SPS Commerce EDI
# ============================================================
class TestEdiProvider:
    def test_provider(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/edi/provider")
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["provider"] == "sps_commerce"
        assert d["connected"] is False
        assert d["mode"] == "sample"
        assert set(d["supported_docs"]) == {"204", "990", "214", "210", "856"}


class TestEdiInbound:
    def test_204_auto_seed(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/edi/inbound/204")
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["mode"] == "sample"
        assert d["count"] >= 1
        t = d["items"][0]
        for k in ("tender_id", "shipper", "origin", "destination", "commodity",
                 "tender_amount_usd", "status"):
            assert k in t, f"missing {k}"
        for k in ("city", "state", "postal_code"):
            assert k in t["origin"]
            assert k in t["destination"]

    def test_856_asn(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/edi/inbound/856")
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["mode"] == "sample"
        assert d["count"] >= 1
        a = d["items"][0]
        for k in ("pallet_count", "carton_count", "sscc"):
            assert k in a


class TestEdiOutbound:
    def test_990_accept_updates_tender(self, admin_client):
        # get a 'new' tender
        tenders = admin_client.get(f"{BASE_URL}/api/edi/inbound/204").json()["items"]
        new_tenders = [t for t in tenders if t.get("status") == "new"]
        assert new_tenders, "expected at least one 'new' tender to test 990 flow"
        tid = new_tenders[0]["tender_id"]

        r = admin_client.post(f"{BASE_URL}/api/edi/outbound/990",
                              json={"tender_id": tid, "decision": "accept", "notes": "test"})
        assert r.status_code == 200, r.text
        rec = r.json()
        assert rec["doc_id"].startswith("990-")
        assert rec["mode"] == "sample"
        assert rec["kind"] == "990"

        # verify tender status changed
        tenders2 = admin_client.get(f"{BASE_URL}/api/edi/inbound/204").json()["items"]
        after = next((t for t in tenders2 if t["tender_id"] == tid), None)
        assert after and after["status"] == "accepted"

    def test_214_auto_status_time(self, admin_client):
        r = admin_client.post(f"{BASE_URL}/api/edi/outbound/214",
                              json={"shipment_id": "SHP-123", "status_code": "in_transit"})
        assert r.status_code == 200, r.text
        rec = r.json()
        assert rec["doc_id"].startswith("214-")
        assert rec["kind"] == "214"
        # status_time auto-populated on persisted payload
        assert rec["payload"].get("status_time"), "status_time should be auto-populated"

    def test_210_invoice(self, admin_client):
        r = admin_client.post(f"{BASE_URL}/api/edi/outbound/210",
                              json={"invoice_number": "INV-9001", "amount": 1250.50})
        assert r.status_code == 200, r.text
        rec = r.json()
        assert rec["doc_id"].startswith("210-")
        assert rec["kind"] == "210"


class TestEdiHistory:
    def test_history_sorted_and_by_kind(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/edi/outbound/history")
        assert r.status_code == 200, r.text
        d = r.json()
        assert "items" in d and "by_kind" in d
        for k in ("990", "214", "210"):
            assert k in d["by_kind"]
        # each kind should have at least 1 (from previous tests)
        assert d["by_kind"]["990"] >= 1
        assert d["by_kind"]["214"] >= 1
        assert d["by_kind"]["210"] >= 1
        # sorted desc by sent_at
        sents = [r["sent_at"] for r in d["items"]]
        assert sents == sorted(sents, reverse=True)


class TestEdiConnect:
    def test_connect_admin_ok(self, admin_client):
        r = admin_client.post(f"{BASE_URL}/api/edi/connect", json={
            "auth0_domain": "orisei-test.us.auth0.com",
            "client_id": "fake_sps_client_id",
            "client_secret": "fake_sps_client_secret_xyz",
        })
        assert r.status_code == 200, r.text
        assert r.json()["ok"] is True
        # After connect, live upstream calls will 401 → fall back to sample
        d = admin_client.get(f"{BASE_URL}/api/edi/inbound/204").json()
        assert d["mode"] == "sample"

    def test_seed_samples_admin(self, admin_client):
        r = admin_client.post(f"{BASE_URL}/api/edi/seed-samples")
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["ok"] is True
        assert d["inbound_204"] >= 1
        assert d["inbound_856"] >= 1
