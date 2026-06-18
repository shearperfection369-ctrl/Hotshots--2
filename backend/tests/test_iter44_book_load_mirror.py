"""
Iteration 44 — Book Load → Workflow cross-module mirror + Data Status backfill/wipe.

Tests verify:
  1. POST /api/shipments mirrors into brokerage_bookings (source='book_load',
     is_sample=False) and is visible via /api/brokerage/margins.
  2. The mirrored booked_id is immediately queryable via
     /api/orisei/workflow/checklist/{booked_id} with stage 'booked' completed.
  3. GET /api/data-status returns mode/total_real/total_sample/collections.
  4. POST /api/admin/backfill-sample-flags is idempotent.
  5. POST /api/admin/clear-sample-data?confirm=true requires confirm, is admin-only,
     and preserves rows with is_sample=False (real Book Load creations).
"""
import os
import time
import requests
import pytest

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://clean-logistics-dash.preview.emergentagent.com",
).rstrip("/")


# ---------- helpers ----------
def _book_load_payload(reference: str) -> dict:
    return {
        "reference":         reference,
        "mode":              "TL",
        "carrier":           "Schneider",
        "origin_city":       "Minneapolis, MN",
        "destination_city":  "Memphis, TN",
        "destination_lat":   35.1495,
        "destination_lng":   -90.049,
        "pickup_date":       "2026-02-01",
        "weight_lbs":        24000,
        "pieces":            12,
        "commodity":         "TEST_iter44 widgets",
        "value_usd":         3200.0,
    }


# ============================================================
# 1. Book Load mirror creates brokerage_bookings row
# ============================================================
class TestBookLoadMirror:
    def test_create_shipment_mirrors_to_brokerage_bookings(self, dispatcher_client):
        ref = f"TEST_iter44_{int(time.time())}"
        # POST a real shipment via Book Load endpoint
        r = dispatcher_client.post(f"{BASE_URL}/api/shipments",
                                   json=_book_load_payload(ref))
        assert r.status_code == 200, f"create_shipment failed: {r.status_code} {r.text}"
        shp = r.json()
        assert shp["reference"] == ref
        assert shp["shipment_id"].startswith("SHP-")
        # Persist for downstream tests
        pytest.iter44_shipment_id = shp["shipment_id"]
        pytest.iter44_reference   = ref

        # Verify the mirror landed in /api/brokerage/margins
        r2 = dispatcher_client.get(f"{BASE_URL}/api/brokerage/margins")
        assert r2.status_code == 200, f"margins failed: {r2.status_code}"
        data = r2.json()
        # endpoint can return either {bookings:[...]} or a bare list
        bookings = data.get("bookings", data) if isinstance(data, dict) else data
        assert isinstance(bookings, list), f"unexpected margins shape: {type(data)}"
        matches = [b for b in bookings if b.get("shipment_id") == shp["shipment_id"]]
        assert len(matches) == 1, (
            f"Expected exactly 1 mirrored booking for shipment "
            f"{shp['shipment_id']}, got {len(matches)}"
        )
        booking = matches[0]
        assert booking["source"] == "book_load"
        assert booking.get("is_sample") is False
        assert booking["booked_id"].startswith("BK-")
        assert booking["reference"] == ref
        assert booking["carrier_name"] == "Schneider"
        # forecast_rate_usd should equal value_usd from the create payload
        assert float(booking.get("forecast_rate_usd") or 0) == 3200.0
        pytest.iter44_booked_id = booking["booked_id"]

    def test_workflow_checklist_for_new_booking(self, dispatcher_client):
        booked_id = getattr(pytest, "iter44_booked_id", None)
        if not booked_id:
            pytest.skip("mirror test did not run / no booked_id captured")
        r = dispatcher_client.get(
            f"{BASE_URL}/api/orisei/workflow/checklist/{booked_id}"
        )
        assert r.status_code == 200, f"checklist failed: {r.status_code} {r.text}"
        body = r.json()
        # Some implementations wrap stages in a dict, some return a list
        stages = body.get("stages") if isinstance(body, dict) else body
        assert isinstance(stages, list), f"unexpected checklist shape: {type(body)}"
        assert len(stages) >= 8, f"expected >=8 stages, got {len(stages)}"
        # Stage 'booked' must exist and be auto-completed from booked_at
        booked_stage = next((s for s in stages if (s.get("id") or s.get("stage") or "").lower() == "booked"), None)
        assert booked_stage is not None, "no 'booked' stage in checklist"
        assert booked_stage.get("done") is True or booked_stage.get("completed") is True, \
            f"'booked' stage not auto-completed: {booked_stage}"


# ============================================================
# 2. /api/data-status
# ============================================================
class TestDataStatus:
    def test_data_status_shape(self, dispatcher_client):
        r = dispatcher_client.get(f"{BASE_URL}/api/data-status")
        assert r.status_code == 200, f"data-status failed: {r.status_code} {r.text}"
        d = r.json()
        assert d["mode"] in ("live", "mostly_live", "sample_heavy",
                             "sample_only", "empty", "mixed")
        assert isinstance(d["total_real"], int)
        assert isinstance(d["total_sample"], int)
        assert isinstance(d["collections"], list)
        names = {c["collection"] for c in d["collections"]}
        for required in ("shipments", "brokerage_bookings", "orisei_customers"):
            assert required in names, f"missing {required} in collections breakdown"
        for c in d["collections"]:
            assert c["total"] == c["real"] + c["sample"]


# ============================================================
# 3. backfill is idempotent
# ============================================================
class TestBackfillSampleFlags:
    def test_backfill_is_idempotent(self, admin_client):
        # first call: may stamp some rows
        r1 = admin_client.post(f"{BASE_URL}/api/admin/backfill-sample-flags")
        assert r1.status_code == 200, f"backfill 1 failed: {r1.status_code} {r1.text}"
        first = r1.json()
        assert first["ok"] is True
        # second call: every row should already have is_sample, so 0 modifications
        r2 = admin_client.post(f"{BASE_URL}/api/admin/backfill-sample-flags")
        assert r2.status_code == 200
        second = r2.json()
        total_second = sum(c["stamped_as_sample"] for c in second["collections"])
        assert total_second == 0, (
            f"backfill not idempotent — second call stamped {total_second} rows"
        )

    def test_backfill_admin_only(self, dispatcher_client):
        r = dispatcher_client.post(f"{BASE_URL}/api/admin/backfill-sample-flags")
        assert r.status_code in (401, 403), \
            f"non-admin should be blocked, got {r.status_code}"


# ============================================================
# 4. clear-sample-data
# ============================================================
class TestClearSampleData:
    def test_clear_requires_confirm(self, admin_client):
        r = admin_client.post(f"{BASE_URL}/api/admin/clear-sample-data")
        assert r.status_code == 400, \
            f"missing ?confirm should 400, got {r.status_code}"

    def test_clear_admin_only(self, dispatcher_client):
        r = dispatcher_client.post(
            f"{BASE_URL}/api/admin/clear-sample-data?confirm=true"
        )
        assert r.status_code in (401, 403), \
            f"non-admin should be blocked, got {r.status_code}"

    def test_clear_preserves_real_book_load_rows(self, admin_client, dispatcher_client):
        """Create a real Book Load row, run clear, confirm it survives."""
        ref = f"TEST_iter44_preserve_{int(time.time())}"
        r = dispatcher_client.post(f"{BASE_URL}/api/shipments",
                                   json=_book_load_payload(ref))
        assert r.status_code == 200
        sid = r.json()["shipment_id"]

        # Run clear
        clr = admin_client.post(
            f"{BASE_URL}/api/admin/clear-sample-data?confirm=true"
        )
        assert clr.status_code == 200, f"clear failed: {clr.status_code} {clr.text}"
        assert clr.json()["ok"] is True

        # Real shipment still exists
        g = dispatcher_client.get(f"{BASE_URL}/api/shipments/{sid}")
        assert g.status_code == 200, (
            f"real shipment {sid} was wiped by clear-sample-data!"
        )
        body = g.json()
        assert body.get("is_sample") is False or body.get("is_sample") is None

        # And its mirrored booking still exists
        m = dispatcher_client.get(f"{BASE_URL}/api/brokerage/margins")
        assert m.status_code == 200
        bdata = m.json()
        bookings = bdata.get("bookings", bdata) if isinstance(bdata, dict) else bdata
        assert any(b.get("shipment_id") == sid for b in bookings), \
            f"mirror for {sid} was wiped — real loads must survive clear-sample-data"
