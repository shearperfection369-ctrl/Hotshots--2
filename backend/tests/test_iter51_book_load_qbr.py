"""Iter51 — Test the /brokerage/loads/book (with shipment mirror + overrides),
/api/data-status new modules, and full QBR Studio.

Auth: Bearer test_session_admin_1 (see /app/memory/test_credentials.md)
"""
import os
import time
import uuid

import pytest
import requests

def _load_env_url():
    # Prefer OS env, else fall back to /app/frontend/.env
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v:
        return v.rstrip("/")
    try:
        with open("/app/frontend/.env") as f:
            for ln in f:
                if ln.startswith("REACT_APP_BACKEND_URL="):
                    return ln.split("=", 1)[1].strip().rstrip("/")
    except OSError:
        pass
    raise RuntimeError("REACT_APP_BACKEND_URL is not set")


BASE_URL = _load_env_url()
API = f"{BASE_URL}/api"
HEADERS = {"Authorization": "Bearer test_session_admin_1",
           "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


# ============================================================
#     PART 1 · /brokerage/loads/book — synthetic + shipment mirror
# ============================================================
class TestBookLoadSynthetic:
    """Book a load that exists on the synthetic feed → verify booking + shipment atomic write."""

    _shared = {}

    def test_pick_load_from_feed(self, session):
        r = session.get(f"{API}/brokerage/boards/dat/loads")
        assert r.status_code == 200, r.text
        loads = r.json().get("loads", [])
        assert len(loads) > 0, "No DAT loads returned"
        self._shared["load"] = loads[0]

    def test_book_synthetic(self, session):
        load = self._shared["load"]
        payload = {
            "load_id": load["load_id"],
            "board_id": load["board_id"],
            "carrier_name": f"TEST_Carrier_{uuid.uuid4().hex[:6]}",
            "customer_name": "E2E Test Shipper Co",
        }
        r = session.post(f"{API}/brokerage/loads/book", json=payload)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["booked_id"].startswith("BK-")
        assert d["shipment_id"].startswith("SH-")
        assert d["is_sample"] is False
        assert d["shipment_created"] is True
        self._shared["booked"] = d

    def test_shipment_appears_in_tracking(self, session):
        booked = self._shared["booked"]
        r = session.get(f"{API}/shipments")
        assert r.status_code == 200, f"/api/shipments broke: {r.status_code} {r.text[:400]}"
        # Response may be list or {items:[...]}
        items = r.json() if isinstance(r.json(), list) else r.json().get("items", r.json().get("shipments", []))
        found = [s for s in items if s.get("shipment_id") == booked["shipment_id"]]
        assert found, f"Shipment {booked['shipment_id']} not found in /api/shipments"
        s = found[0]
        assert s.get("booking_number") == booked["booked_id"]
        assert s.get("status") == "pending"
        # Required fields for /tracking not to 500
        for k in ["current_location", "pieces", "eta", "weight_lbs", "commodity", "value_usd"]:
            assert k in s, f"missing required field {k} in shipment row"

    def test_workflow_checklist_finds_booking(self, session):
        booked = self._shared["booked"]
        r = session.get(f"{API}/orisei/workflow/checklist/{booked['booked_id']}")
        assert r.status_code == 200, r.text
        data = r.json()
        # Should have stages and 'booked' completed
        stages = data.get("stages") or data.get("checklist") or []
        assert stages, f"no stages returned: {data}"
        # Find booked stage
        booked_stage = next((s for s in stages if (s.get("id") or s.get("key") or "").lower() == "booked"), None)
        # Fallback: 'booked' status attribute
        if booked_stage is None:
            # look for any completed stage
            completed = [s for s in stages if s.get("completed") or s.get("done") or s.get("status") == "completed"]
            assert completed, f"expected at least one completed stage, got {stages}"
        else:
            assert booked_stage.get("completed") or booked_stage.get("done") or booked_stage.get("status") == "completed"


class TestBookLoadWithOverrides:
    """Book a REAL (non-synthetic) load using override_* fields."""

    def test_book_with_overrides(self, session):
        fake_load_id = f"REAL-{uuid.uuid4().hex[:8].upper()}"
        payload = {
            "load_id": fake_load_id,
            "board_id": "dat",
            "carrier_name": f"TEST_RealCarrier_{uuid.uuid4().hex[:6]}",
            "customer_name": "Acme Retail Inc",
            "override_origin": "Dallas, TX",
            "override_destination": "Atlanta, GA",
            "override_miles": 782,
            "override_equipment": "Reefer",
            "override_rate_usd": 3200,
            "override_carrier_pay_usd": 2400,
            "override_pickup_date": "2026-02-01",
            "override_delivery_date": "2026-02-03",
        }
        r = session.post(f"{API}/brokerage/loads/book", json=payload)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["origin"] == "Dallas, TX"
        assert d["destination"] == "Atlanta, GA"
        assert d["miles"] == 782
        assert d["equipment"] == "Reefer"
        assert d["forecast_rate_usd"] == 3200
        assert d["forecast_carrier_pay_usd"] == 2400
        assert d["forecast_margin_usd"] == 800.0
        assert d["is_sample"] is False
        assert d["shipment_created"] is True

    def test_book_missing_synthetic_no_overrides_404(self, session):
        payload = {
            "load_id": f"NOPE-{uuid.uuid4().hex[:8]}",
            "board_id": "dat",
            "carrier_name": "TEST_ShouldFail",
        }
        r = session.post(f"{API}/brokerage/loads/book", json=payload)
        assert r.status_code == 404, r.text


# ============================================================
#     PART 2 · /api/data-status — new modules + real vs sample
# ============================================================
class TestDataStatus:
    def test_data_status_contains_new_modules(self, session):
        r = session.get(f"{API}/data-status")
        assert r.status_code == 200, r.text
        d = r.json()
        cols = {c["collection"]: c for c in d["collections"]}
        for expected in ["claims_master", "shipper_accounts", "aggregator_prefs",
                          "brokerage_bookings", "shipments"]:
            assert expected in cols, f"expected collection {expected}"
        # Real is total - sample. Records without is_sample flag → real.
        # Verify brokerage_bookings has at least the ones we just booked as real
        bb = cols["brokerage_bookings"]
        assert bb["real"] >= 2, f"expected our bookings to count as real, got {bb}"


# ============================================================
#     PART 3 · QBR Studio — full CRUD + PDF + distribute
# ============================================================
class TestQbrStudio:
    _shared = {}

    def test_list_shippers(self, session):
        r = session.get(f"{API}/qbr-studio/shippers")
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["count"] > 0
        assert isinstance(d["items"], list)
        # Each item has name + source
        for item in d["items"]:
            assert "name" in item and "source" in item
        names_lower = {i["name"].lower() for i in d["items"]}
        # Should include E2E Test Shipper Co from our bookings
        assert any("e2e test shipper" in n for n in names_lower) or any("acme retail" in n for n in names_lower)

    def test_compute_period_valid(self, session):
        r = session.get(f"{API}/qbr-studio/period/Q1%202026/E2E%20Test%20Shipper%20Co")
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["period"] == "Q1 2026"
        assert d["prior_period"] == "Q4 2025"
        # metrics + prior_metrics + deltas structure
        for k in ["metrics", "prior_metrics", "deltas"]:
            assert k in d, f"missing {k}"
        m = d["metrics"]
        for sub in ["loads", "shipments", "claims", "account", "lanes", "equipment"]:
            assert sub in m, f"metrics missing {sub}"
        # Deltas keys expected
        for k in ["loads_total", "revenue_usd", "margin_pct", "otd_pct",
                  "damage_free_pct", "claims_count", "claims_amount_usd"]:
            assert k in d["deltas"], f"missing delta {k}"

    def test_compute_period_invalid_400(self, session):
        r = session.get(f"{API}/qbr-studio/period/BOGUS%20PERIOD/Acme%20Retail%20Inc")
        assert r.status_code == 400, r.text

    def test_generate_draft(self, session):
        payload = {
            "period": "Q1 2026",
            "shipper_name": "E2E Test Shipper Co",
            "executive_summary": "TEST_ summary for iter51",
            "strengths": "Fast pay, good OTD",
            "gaps": "Damage rate creeping",
            "action_items": ["Improve claims SLA", "Add reefer dedicated lane"],
            "next_review_date": "2026-04-15",
        }
        r = session.post(f"{API}/qbr-studio/generate", json=payload)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["draft_id"].startswith("QBR-")
        assert d["status"] == "draft"
        assert d["executive_summary"] == "TEST_ summary for iter51"
        assert d["action_items"] == ["Improve claims SLA", "Add reefer dedicated lane"]
        assert "metrics" in d
        self._shared["draft_id"] = d["draft_id"]

    def test_list_drafts(self, session):
        r = session.get(f"{API}/qbr-studio/drafts")
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["count"] >= 1
        ids = {row["draft_id"] for row in d["items"]}
        assert self._shared["draft_id"] in ids

    def test_get_draft(self, session):
        did = self._shared["draft_id"]
        r = session.get(f"{API}/qbr-studio/drafts/{did}")
        assert r.status_code == 200, r.text
        assert r.json()["draft_id"] == did

    def test_patch_draft(self, session):
        did = self._shared["draft_id"]
        r = session.patch(f"{API}/qbr-studio/drafts/{did}",
                          json={"strengths": "UPDATED strengths iter51"})
        assert r.status_code == 200, r.text
        assert r.json()["strengths"] == "UPDATED strengths iter51"

    def test_pdf_report(self, session):
        did = self._shared["draft_id"]
        r = session.get(f"{API}/qbr-studio/drafts/{did}/report.pdf")
        assert r.status_code == 200, r.text[:400]
        assert r.headers.get("content-type", "").startswith("application/pdf")
        body = r.content
        assert body.startswith(b"%PDF"), "not a valid PDF (missing %PDF magic)"
        assert len(body) > 5000, f"PDF too small ({len(body)} bytes)"

    def test_distribute_defaults(self, session):
        did = self._shared["draft_id"]
        # No cc/subject/message → server should fill defaults
        r = session.post(f"{API}/qbr-studio/drafts/{did}/distribute",
                          json={"to_email": "test.customer@example.com"})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["ok"] is True
        email = d["email"]
        assert email["to"] == "test.customer@example.com"
        assert email["subject"], "default subject missing"
        assert email["body"], "default body missing"
        assert email["attachment_url"].endswith("/report.pdf")
        # draft status should now be distributed
        r2 = session.get(f"{API}/qbr-studio/drafts/{did}")
        assert r2.json()["status"] == "distributed"

    def test_delete_draft(self, session):
        did = self._shared["draft_id"]
        r = session.delete(f"{API}/qbr-studio/drafts/{did}")
        assert r.status_code == 200, r.text
        # GET should now 404
        r2 = session.get(f"{API}/qbr-studio/drafts/{did}")
        assert r2.status_code == 404

    def test_preserve_existing_draft(self, session):
        """Do NOT delete draft QBR-70CD2DE972 per test brief."""
        r = session.get(f"{API}/qbr-studio/drafts/QBR-70CD2DE972")
        # Either exists or doesn't — but we do NOT delete it. Just verify GET is stable.
        assert r.status_code in (200, 404)


# ============================================================
#     PART 4 · Regression — brokerage/loads/book (previous consumers)
# ============================================================
class TestBookLoadRegression:
    """Make sure previous consumers of book_load (no override, no customer) still work."""

    def test_minimal_book_still_works(self, session):
        r = session.get(f"{API}/brokerage/boards/truckstop/loads")
        assert r.status_code == 200
        loads = r.json().get("loads", [])
        assert loads, "no truckstop loads"
        payload = {
            "load_id": loads[0]["load_id"],
            "board_id": loads[0]["board_id"],
            "carrier_name": "TEST_MinimalCarrier",
        }
        r = session.post(f"{API}/brokerage/loads/book", json=payload)
        assert r.status_code == 200, r.text
        d = r.json()
        # even without customer_name, response should contain booked_id + shipment_created
        assert d["booked_id"].startswith("BK-")
        assert d["shipment_created"] is True
