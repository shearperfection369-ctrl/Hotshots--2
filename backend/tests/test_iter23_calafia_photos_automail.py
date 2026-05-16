"""
Iter 23 — Orisei Calafia / POD Photos / Auto-mail / Mark-Delivered / Live-board adapter.

New endpoints exercised:
  · GET  /api/brokerage/settings (defaults + persistence)
  · PUT  /api/brokerage/settings (admin only, allowlist filter)
  · POST /api/brokerage/bookings/{id}/pod/photos (multipart, max 3)
  · GET  /api/brokerage/bookings/{id}/pod/photos (list, no binary)
  · GET  /api/brokerage/bookings/{id}/pod/photos/{photo_id} (image/jpeg)
  · DELETE /api/brokerage/bookings/{id}/pod/photos/{photo_id} (+ 404 on retry)
  · GET  /api/brokerage/bookings/{id}/pod.pdf (larger with photos)
  · POST /api/brokerage/bookings/{id}/mark-delivered (auto-mail hint)
  · PUT  /api/brokerage/bookings/{id}/customer (auto_email_bol_on_book hint)
  · GET  /api/brokerage/boards/{id}/loads (`source: synthetic`)
Plus a focused regression on dashboard / book / settle / margins / bol / pod / pod-history /
pod-email (dry-run) / quickbooks/oauth/start (no creds).
"""
import io
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    with open("/app/frontend/.env") as fh:
        for line in fh:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().strip('"')
                break
BASE_URL = BASE_URL.rstrip("/")

ADMIN_TOKEN = "test_session_admin_1"
DISP_TOKEN  = "test_disp_session"


# --------------------------- fixtures ---------------------------
@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {ADMIN_TOKEN}"})
    return s


@pytest.fixture(scope="module")
def disp_session():
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {DISP_TOKEN}"})
    return s


@pytest.fixture(scope="module")
def fresh_booking(session):
    """Book a fresh load from the DAT board for tests that mutate state."""
    loads = session.get(f"{BASE_URL}/api/brokerage/boards/dat/loads", timeout=30).json().get("loads", [])
    assert loads, "Need at least one DAT load"
    payload = {"load_id": loads[0]["load_id"], "board_id": "dat",
               "carrier_name": "TEST_Iter23_Carrier", "carrier_mc": "MC-232323"}
    r = session.post(f"{BASE_URL}/api/brokerage/loads/book", json=payload, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["booked_id"]


@pytest.fixture
def tiny_jpeg_bytes():
    """Generate a real JPEG with PIL so the server-side downsample path runs."""
    from PIL import Image
    im = Image.new("RGB", (1600, 1200), color=(214, 169, 88))
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=80)
    return buf.getvalue()


# --------------------------- auth sanity ---------------------------
def test_auth_admin_ok(session):
    r = session.get(f"{BASE_URL}/api/auth/me", timeout=15)
    assert r.status_code == 200, r.text
    assert r.json().get("role") == "admin"


# ============ SETTINGS ============
def test_settings_defaults(session):
    # Reset to defaults first (admin can set both to false + empty templates)
    session.put(f"{BASE_URL}/api/brokerage/settings",
                json={"auto_email_bol_on_book": False,
                      "auto_email_pod_on_delivery": False,
                      "bol_message_template": "",
                      "pod_message_template": ""}, timeout=15)
    r = session.get(f"{BASE_URL}/api/brokerage/settings", timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("auto_email_bol_on_book") is False
    assert data.get("auto_email_pod_on_delivery") is False
    # template keys present (empty)
    assert "bol_message_template" in data
    assert "pod_message_template" in data


def test_settings_put_persists_and_rejects_unknown(session):
    payload = {"auto_email_bol_on_book": True,
               "auto_email_pod_on_delivery": True,
               "bol_message_template": "TEST_bol_tpl",
               "pod_message_template": "TEST_pod_tpl",
               "danger_key": "should_be_ignored"}
    r = session.put(f"{BASE_URL}/api/brokerage/settings", json=payload, timeout=15)
    assert r.status_code == 200, r.text
    doc = r.json()
    assert doc["auto_email_bol_on_book"] is True
    assert doc["auto_email_pod_on_delivery"] is True
    assert doc["bol_message_template"] == "TEST_bol_tpl"
    assert "danger_key" not in doc
    # Persistence via GET
    r = session.get(f"{BASE_URL}/api/brokerage/settings", timeout=15)
    assert r.json()["auto_email_bol_on_book"] is True


def test_settings_put_requires_admin(disp_session):
    r = disp_session.put(f"{BASE_URL}/api/brokerage/settings",
                         json={"auto_email_bol_on_book": False}, timeout=15)
    assert r.status_code in (401, 403), r.text


def test_settings_put_empty_payload_rejected(session):
    r = session.put(f"{BASE_URL}/api/brokerage/settings", json={}, timeout=15)
    assert r.status_code == 400


# ============ AUTO-MAIL BOL HINT ON /customer ============
def test_auto_bol_email_hint_when_resend_missing(session, fresh_booking, tiny_jpeg_bytes):
    # Ensure auto_email_bol_on_book is ON (it was set true in previous test)
    session.put(f"{BASE_URL}/api/brokerage/settings",
                json={"auto_email_bol_on_book": True}, timeout=15)

    payload = {"customer_name": "TEST_AutoMailCo",
               "customer_email": f"ops+iter23-{int(time.time())}@example.com",
               "consignee_address": "100 Test Ave, Fargo, ND 58102"}
    r = session.put(f"{BASE_URL}/api/brokerage/bookings/{fresh_booking}/customer",
                    json=payload, timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    # Hook only fires when transitioning empty→has email; for a fresh booking it must fire.
    assert "_auto_bol" in body, f"Expected _auto_bol hook to attach, got: {list(body.keys())}"
    auto = body["_auto_bol"]
    assert "auto_email_error" in auto, f"Expected Resend missing-creds error: {auto}"
    assert "Resend" in (auto.get("auto_email_error") or "")


# ============ POD PHOTOS ============
def test_pod_photo_upload_and_list(session, fresh_booking, tiny_jpeg_bytes):
    # Upload 1st photo (multipart)
    r = session.post(
        f"{BASE_URL}/api/brokerage/bookings/{fresh_booking}/pod/photos",
        files={"file": ("dock1.jpg", tiny_jpeg_bytes, "image/jpeg")},
        data={"caption": "TEST_dock_1"},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["photo_id"].startswith("PHO-")
    # Should be downsampled smaller than the 1600x1200 source
    assert data["size_bytes"] > 0
    assert data["size_bytes"] < len(tiny_jpeg_bytes)

    # List
    r = session.get(f"{BASE_URL}/api/brokerage/bookings/{fresh_booking}/pod/photos",
                    timeout=15)
    assert r.status_code == 200, r.text
    lst = r.json()
    assert lst["count"] >= 1
    sample = lst["photos"][0]
    assert "data" not in sample, "Binary data must NOT be returned on list endpoint"
    assert "photo_id" in sample and "size_bytes" in sample


def test_pod_photo_fetch_returns_jpeg(session, fresh_booking, tiny_jpeg_bytes):
    # Make sure at least one photo exists
    photos = session.get(f"{BASE_URL}/api/brokerage/bookings/{fresh_booking}/pod/photos",
                        timeout=15).json()["photos"]
    if not photos:
        r0 = session.post(
            f"{BASE_URL}/api/brokerage/bookings/{fresh_booking}/pod/photos",
            files={"file": ("dock_fetch.jpg", tiny_jpeg_bytes, "image/jpeg")},
            data={"caption": "TEST_dock_fetch"}, timeout=30,
        )
        assert r0.status_code == 200
        pid = r0.json()["photo_id"]
    else:
        pid = photos[0]["photo_id"]

    r = session.get(f"{BASE_URL}/api/brokerage/bookings/{fresh_booking}/pod/photos/{pid}",
                    timeout=15)
    assert r.status_code == 200, r.text
    assert r.headers.get("content-type", "").startswith("image/jpeg")
    assert len(r.content) > 100


def test_pod_photo_max_3_enforced(session, fresh_booking, tiny_jpeg_bytes):
    # Top up to exactly 3 photos
    existing = session.get(
        f"{BASE_URL}/api/brokerage/bookings/{fresh_booking}/pod/photos", timeout=15
    ).json()["count"]
    for i in range(3 - existing):
        rr = session.post(
            f"{BASE_URL}/api/brokerage/bookings/{fresh_booking}/pod/photos",
            files={"file": (f"dock_extra_{i}.jpg", tiny_jpeg_bytes, "image/jpeg")},
            data={"caption": f"TEST_dock_extra_{i}"}, timeout=30,
        )
        assert rr.status_code == 200, rr.text

    # 4th attempt MUST 400
    r4 = session.post(
        f"{BASE_URL}/api/brokerage/bookings/{fresh_booking}/pod/photos",
        files={"file": ("dock_4.jpg", tiny_jpeg_bytes, "image/jpeg")},
        data={"caption": "TEST_dock_4"}, timeout=30,
    )
    assert r4.status_code == 400, r4.text
    assert "3" in r4.text


def test_pod_pdf_grows_when_photos_attached(session, fresh_booking):
    """POD pdf MUST be larger when photos are attached vs an empty-photos booking."""
    # Baseline POD bytes for fresh_booking (has photos)
    r_with = session.get(f"{BASE_URL}/api/brokerage/bookings/{fresh_booking}/pod.pdf",
                         timeout=30)
    assert r_with.status_code == 200, r_with.text
    assert r_with.headers.get("content-type", "").startswith("application/pdf")
    with_size = len(r_with.content)

    # Find another booking without photos OR book a brand new one with no photos
    bks = session.get(f"{BASE_URL}/api/brokerage/bookings", timeout=15).json()["bookings"]
    no_photo_bk = None
    for b in bks:
        bid = b.get("booked_id")
        if not bid or bid == fresh_booking:
            continue
        cnt = session.get(f"{BASE_URL}/api/brokerage/bookings/{bid}/pod/photos",
                          timeout=15).json().get("count", 0)
        if cnt == 0:
            no_photo_bk = bid
            break
    if not no_photo_bk:
        loads = session.get(f"{BASE_URL}/api/brokerage/boards/dat/loads",
                            timeout=15).json()["loads"]
        bk = session.post(f"{BASE_URL}/api/brokerage/loads/book",
                          json={"load_id": loads[1]["load_id"], "board_id": "dat",
                                "carrier_name": "TEST_PodSizeBaseline",
                                "carrier_mc": "MC-555000"}, timeout=30).json()
        no_photo_bk = bk["booked_id"]

    r_wo = session.get(f"{BASE_URL}/api/brokerage/bookings/{no_photo_bk}/pod.pdf",
                       timeout=30)
    assert r_wo.status_code == 200
    assert with_size > len(r_wo.content), \
        f"PDF with photos ({with_size}) should be > without ({len(r_wo.content)})"


def test_pod_photo_delete_and_404(session, fresh_booking, tiny_jpeg_bytes):
    # Upload one (we may already be at cap, so clear if needed)
    photos = session.get(f"{BASE_URL}/api/brokerage/bookings/{fresh_booking}/pod/photos",
                        timeout=15).json()["photos"]
    if photos:
        pid = photos[-1]["photo_id"]
    else:
        r0 = session.post(
            f"{BASE_URL}/api/brokerage/bookings/{fresh_booking}/pod/photos",
            files={"file": ("d.jpg", tiny_jpeg_bytes, "image/jpeg")},
            data={"caption": "x"}, timeout=30,
        )
        pid = r0.json()["photo_id"]

    r = session.delete(f"{BASE_URL}/api/brokerage/bookings/{fresh_booking}/pod/photos/{pid}",
                       timeout=15)
    assert r.status_code == 200, r.text
    assert r.json().get("deleted") is True

    # Retry → 404
    r2 = session.delete(f"{BASE_URL}/api/brokerage/bookings/{fresh_booking}/pod/photos/{pid}",
                        timeout=15)
    assert r2.status_code == 404


# ============ MARK DELIVERED ============
def test_mark_delivered_auto_pod_hint(session, fresh_booking):
    # Ensure auto POD on delivery is ON
    session.put(f"{BASE_URL}/api/brokerage/settings",
                json={"auto_email_pod_on_delivery": True,
                      "pod_message_template": "Thank you!"}, timeout=15)

    payload = {"received_by": "TEST_J. Receiver",
               "driver_name": "TEST_Driver",
               "pieces_received": "12", "weight_received": "24000",
               "notes": "iter23 mark-delivered"}
    r = session.post(f"{BASE_URL}/api/brokerage/bookings/{fresh_booking}/mark-delivered",
                     json=payload, timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("ok") is True
    # We set customer_email earlier — so an auto-mail attempt should occur and produce a Resend hint.
    assert "auto_email_error" in body, body
    assert "Resend" in (body.get("auto_email_error") or "")

    # Status flipped to delivered
    bks = session.get(f"{BASE_URL}/api/brokerage/bookings", timeout=15).json()["bookings"]
    me = next(b for b in bks if b.get("booked_id") == fresh_booking)
    assert me["status"] == "delivered"
    assert (me.get("delivery") or {}).get("received_by") == "TEST_J. Receiver"


def test_mark_delivered_silent_when_no_customer_email(session, tiny_jpeg_bytes):
    # Book new + don't attach email
    loads = session.get(f"{BASE_URL}/api/brokerage/boards/truckstop/loads",
                        timeout=15).json()["loads"]
    bk = session.post(f"{BASE_URL}/api/brokerage/loads/book",
                      json={"load_id": loads[0]["load_id"], "board_id": "truckstop",
                            "carrier_name": "TEST_NoEmail_Carrier",
                            "carrier_mc": "MC-001"}, timeout=30).json()
    bid = bk["booked_id"]

    # Auto-pod toggle ON, but no customer_email
    session.put(f"{BASE_URL}/api/brokerage/settings",
                json={"auto_email_pod_on_delivery": True}, timeout=15)

    r = session.post(f"{BASE_URL}/api/brokerage/bookings/{bid}/mark-delivered",
                     json={"received_by": "T_R"}, timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("ok") is True
    assert body.get("auto_email_sent") is False
    assert "auto_email_error" not in body, f"Should silently skip, got: {body}"


# ============ BOARD SOURCE (synthetic vs live) ============
@pytest.mark.parametrize("board", ["dat", "truckstop", "convoy"])
def test_board_loads_source_synthetic_fallback(session, board):
    r = session.get(f"{BASE_URL}/api/brokerage/boards/{board}/loads", timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "source" in data, f"`source` field MUST be present on board response, got: {list(data.keys())}"
    assert data["source"] in ("synthetic", "live"), data["source"]
    # No creds in this env → must be synthetic
    assert data["source"] == "synthetic", f"Expected synthetic, got {data['source']}"
    assert data["count"] == len(data["loads"]) > 0


# ============ REGRESSION ============
def test_dashboard_ok(session):
    r = session.get(f"{BASE_URL}/api/brokerage/dashboard", timeout=15)
    assert r.status_code == 200, r.text


def test_bookings_list_no_id_leak(session):
    r = session.get(f"{BASE_URL}/api/brokerage/bookings", timeout=15)
    assert r.status_code == 200
    for b in r.json()["bookings"]:
        assert "_id" not in b


def test_bol_pdf_regression(session, fresh_booking):
    r = session.get(f"{BASE_URL}/api/brokerage/bookings/{fresh_booking}/bol.pdf", timeout=30)
    assert r.status_code == 200, r.text
    assert r.headers.get("content-type", "").startswith("application/pdf")
    assert r.content.startswith(b"%PDF")


def test_pod_email_dry_run(session, fresh_booking):
    payload = {"to_email": "dry@example.com",
               "to_name": "DryRun",
               "subject": "TEST_subject",
               "message": "TEST_msg",
               "delivery": {"received_by": "TEST_R"},
               "dry_run": True}
    r = session.post(f"{BASE_URL}/api/brokerage/bookings/{fresh_booking}/pod/email",
                     json=payload, timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("status") == "dry_run"
    assert "html_preview" in body


def test_pod_history(session, fresh_booking):
    r = session.get(f"{BASE_URL}/api/brokerage/bookings/{fresh_booking}/pod-history",
                    timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "items" in body and isinstance(body["items"], list)


def test_qb_oauth_start_400_without_creds(session):
    r = session.get(f"{BASE_URL}/api/brokerage/quickbooks/oauth/start", timeout=15)
    # Either 400 (no creds — the documented path) or 200 if local fixture has set them.
    assert r.status_code in (200, 400), r.text
    if r.status_code == 400:
        assert "QuickBooks" in r.text or "Client" in r.text


def test_loads_book_and_margins(session):
    loads = session.get(f"{BASE_URL}/api/brokerage/boards/dat/loads",
                        timeout=15).json()["loads"]
    r = session.post(f"{BASE_URL}/api/brokerage/loads/book",
                     json={"load_id": loads[-1]["load_id"], "board_id": "dat",
                           "carrier_name": "TEST_Regression_Carrier",
                           "carrier_mc": "MC-444555"}, timeout=20)
    assert r.status_code == 200, r.text
    r2 = session.get(f"{BASE_URL}/api/brokerage/margins", timeout=15)
    assert r2.status_code == 200


# ---- cleanup -----------
def test_zz_reset_settings(session):
    session.put(f"{BASE_URL}/api/brokerage/settings",
                json={"auto_email_bol_on_book": False,
                      "auto_email_pod_on_delivery": False,
                      "bol_message_template": "",
                      "pod_message_template": ""}, timeout=15)
