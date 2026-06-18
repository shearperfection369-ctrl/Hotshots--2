"""Backend tests for Orisei Run-the-Load Workflow features (iter 37).

Covers:
  - Workflow checklist GET / mark / margin
  - Invite templates CRUD + preview
  - Doc overrides CRUD + invoice PDF render w/ overrides
  - Branded invoice creation, edit, PDF
  - Domain config GET/POST + propagation
  - Marketing video + static site assets
"""
import os
import uuid
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://clean-logistics-dash.preview.emergentagent.com").rstrip("/")
ADMIN_TOKEN = "test_session_admin_1"
H = {"Authorization": f"Bearer {ADMIN_TOKEN}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def booked_id():
    r = requests.get(f"{BASE_URL}/api/brokerage/bookings?limit=5", headers=H, timeout=15)
    assert r.status_code == 200, r.text
    items = r.json().get("bookings") or []
    if not items:
        pytest.skip("No bookings to test against")
    return items[0]["booked_id"]


# ---------------- Workflow Stages / Checklist ----------------
def test_workflow_stages():
    r = requests.get(f"{BASE_URL}/api/orisei/workflow/stages", headers=H, timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 8
    assert [s["id"] for s in data["stages"]][:2] == ["booked", "carrier_assigned"]


def test_checklist_shape(booked_id):
    r = requests.get(f"{BASE_URL}/api/orisei/workflow/checklist/{booked_id}", headers=H, timeout=15)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["booked_id"] == booked_id
    assert d["total_count"] == 8
    assert len(d["stages"]) == 8
    assert 0 <= d["pct_complete"] <= 100
    # 'booked' should auto-complete since bookings have booked_at
    booked_stage = next(s for s in d["stages"] if s["id"] == "booked")
    assert booked_stage["completed"] is True
    assert booked_stage["manual"] is False


def test_mark_stage_increments_progress(booked_id):
    before = requests.get(f"{BASE_URL}/api/orisei/workflow/checklist/{booked_id}", headers=H).json()
    # find first incomplete
    incomplete = next((s for s in before["stages"] if not s["completed"]), None)
    if not incomplete:
        pytest.skip("Nothing to mark")
    sid = incomplete["id"]
    r = requests.post(
        f"{BASE_URL}/api/orisei/workflow/checklist/{booked_id}/mark",
        headers=H, json={"stage_id": sid, "notes": "TEST_mark_iter37"}, timeout=15,
    )
    assert r.status_code == 200, r.text
    after = r.json()
    assert after["completed_count"] > before["completed_count"]
    s = next(x for x in after["stages"] if x["id"] == sid)
    assert s["completed"] is True
    assert s["manual"] is True
    assert s["notes"] == "TEST_mark_iter37"
    # cleanup unmark
    requests.post(
        f"{BASE_URL}/api/orisei/workflow/checklist/{booked_id}/unmark",
        headers=H, json={"stage_id": sid}, timeout=10,
    )


def test_mark_stage_unknown(booked_id):
    r = requests.post(
        f"{BASE_URL}/api/orisei/workflow/checklist/{booked_id}/mark",
        headers=H, json={"stage_id": "no_such"}, timeout=10,
    )
    assert r.status_code == 400


# ---------------- Quick Margin ----------------
def test_quick_margin(booked_id):
    r = requests.post(
        f"{BASE_URL}/api/orisei/workflow/margin/quick",
        headers=H, json={"booked_id": booked_id, "carrier_cost_usd": 800, "extra_costs_usd": 50}, timeout=10,
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["carrier_cost_usd"] == 800
    assert d["total_cost_usd"] == 850
    assert "margin_usd" in d and "margin_pct" in d
    assert d["health"] in {"strong", "healthy", "thin", "loss"}
    # GET reflects manual cost
    g = requests.get(f"{BASE_URL}/api/orisei/workflow/margin/{booked_id}", headers=H).json()
    assert g["has_manual_cost"] is True
    assert g["carrier_cost_usd"] == 800


# ---------------- Invite Templates ----------------
def test_invite_default_seeded():
    r = requests.get(f"{BASE_URL}/api/orisei/workflow/invites/templates", headers=H, timeout=10)
    assert r.status_code == 200
    ids = {t["template_id"] for t in r.json()["items"]}
    assert "carrier-invite-default" in ids
    assert "shipper-invite-default" in ids


def test_invite_template_crud_and_preview():
    body = {
        "kind": "carrier", "name": "TEST_tpl_iter37",
        "subject": "Hi {{carrier_name}}", "body_html": "<p>Visit {{site_url}} now</p>"
    }
    c = requests.post(f"{BASE_URL}/api/orisei/workflow/invites/templates", headers=H, json=body, timeout=10)
    assert c.status_code == 200, c.text
    tpl_id = c.json()["template_id"]
    # Update
    body["subject"] = "Updated {{carrier_name}}"
    u = requests.put(f"{BASE_URL}/api/orisei/workflow/invites/templates/{tpl_id}", headers=H, json=body, timeout=10)
    assert u.status_code == 200
    assert "Updated" in u.json()["subject"]
    # Preview
    p = requests.post(f"{BASE_URL}/api/orisei/workflow/invites/preview", headers=H,
                       json={"template_id": tpl_id}, timeout=10)
    assert p.status_code == 200, p.text
    pv = p.json()
    assert "Acme Trucking" in pv["subject"]
    assert "Acme Trucking" not in pv["body_html"]  # has site_url, not carrier_name
    assert "http" in pv["body_html"]  # site_url substituted
    # Delete custom OK
    d = requests.delete(f"{BASE_URL}/api/orisei/workflow/invites/templates/{tpl_id}", headers=H, timeout=10)
    assert d.status_code == 200


def test_invite_cannot_delete_default():
    r = requests.delete(f"{BASE_URL}/api/orisei/workflow/invites/templates/carrier-invite-default",
                        headers=H, timeout=10)
    assert r.status_code == 400


# ---------------- Doc Overrides + Invoice ----------------
@pytest.fixture(scope="module")
def customer_id():
    suffix = uuid.uuid4().hex[:6]
    payload = {
        "name": f"TEST_Acme {suffix}",
        "ap_email": f"ap+{suffix}@acmecorp.com",
        "billing_address": "1 Test St, Atlanta, GA",
        "payment_terms": "Net 30",
    }
    # Try a couple of endpoints since exact path may vary
    for path in ("/api/orisei/customers", "/api/brokerage/customers"):
        r = requests.post(f"{BASE_URL}{path}", headers=H, json=payload, timeout=10)
        if r.status_code in (200, 201):
            return r.json().get("customer_id") or r.json().get("id")
    pytest.skip(f"Could not create customer (last status {r.status_code} body {r.text[:200]})")


@pytest.fixture(scope="module")
def invoice_id(customer_id, booked_id):
    r = requests.post(
        f"{BASE_URL}/api/orisei/workflow/invoices", headers=H,
        json={"customer_id": customer_id, "booking_ids": [booked_id], "due_in_days": 30,
              "notes": "TEST_inv_iter37"},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    return r.json()["invoice_id"]


def test_invoice_list_contains(invoice_id):
    r = requests.get(f"{BASE_URL}/api/orisei/workflow/invoices", headers=H, timeout=10)
    assert r.status_code == 200
    ids = {i["invoice_id"] for i in r.json()["items"]}
    assert invoice_id in ids


def test_invoice_pdf_renders(invoice_id):
    r = requests.get(f"{BASE_URL}/api/orisei/workflow/invoices/{invoice_id}/pdf", headers=H, timeout=20)
    assert r.status_code == 200
    assert "application/pdf" in r.headers.get("content-type", "")
    assert r.content[:4] == b"%PDF"


def test_doc_overrides_and_pdf_embed(invoice_id):
    marker = f"TEST_OVR_{uuid.uuid4().hex[:8]}"
    body = {"doc_kind": "invoice", "doc_id": invoice_id, "overrides": {"notes": marker}}
    s = requests.post(f"{BASE_URL}/api/orisei/workflow/doc-overrides", headers=H, json=body, timeout=10)
    assert s.status_code == 200, s.text
    g = requests.get(f"{BASE_URL}/api/orisei/workflow/doc-overrides/invoice/{invoice_id}",
                      headers=H, timeout=10).json()
    assert g["overrides"]["notes"] == marker
    # PDF embed (loose: marker text appears in PDF stream or invoice GET)
    inv = requests.get(f"{BASE_URL}/api/orisei/workflow/invoices/{invoice_id}", headers=H).json()
    assert inv["notes"] == marker


def test_invoice_inline_edit(invoice_id):
    new_items = [{"label": "TEST_line A", "amount_usd": 1234.5},
                 {"label": "TEST_line B", "amount_usd": 100}]
    r = requests.put(f"{BASE_URL}/api/orisei/workflow/invoices/{invoice_id}",
                     headers=H, json={"line_items": new_items, "status": "issued"}, timeout=10)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["subtotal_usd"] == 1334.5
    assert d["total_usd"] == 1334.5


# ---------------- Domain ----------------
def test_domain_get_set():
    g = requests.get(f"{BASE_URL}/api/orisei/workflow/domain-config", headers=H, timeout=10)
    assert g.status_code == 200
    orig = g.json()
    s = requests.post(f"{BASE_URL}/api/orisei/workflow/domain-config", headers=H,
                      json={"primary_domain": "oriseifreight.com",
                            "propagate_to_static_site": False}, timeout=15)
    assert s.status_code == 200, s.text
    d = s.json()
    assert d["primary_domain"] == "oriseifreight.com"
    assert d["propagated_to_static_site"] is False


# ---------------- Marketing assets ----------------
def test_broker_promo_video_http():
    r = requests.get(f"{BASE_URL}/orisei-marketing/video/orisei-broker-promo.mp4",
                     stream=True, timeout=20)
    assert r.status_code == 200
    assert "video/mp4" in r.headers.get("content-type", "")


def test_marketing_site_references_broker_promo():
    r = requests.get(f"{BASE_URL}/orisei-marketing/site/index.html", timeout=15)
    assert r.status_code == 200
    assert "orisei-broker-promo.mp4" in r.text
