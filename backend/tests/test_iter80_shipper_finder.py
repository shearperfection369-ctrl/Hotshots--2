"""Iter80 — Shipper Finder CRM + Playbook + Brochure + plan-review regression."""
import os
import time
import pytest
import requests

from dotenv import dotenv_values
_env = dotenv_values("/app/frontend/.env")
BASE = (os.environ.get("REACT_APP_BACKEND_URL") or _env.get("REACT_APP_BACKEND_URL")).rstrip("/")
HEADERS = {"Authorization": "Bearer test_session_admin_1", "Content-Type": "application/json"}


# ---------- Shipper Finder ----------
class TestShipperFinderSeed:
    def test_list_seeds_six_prospects_and_stage_counts(self):
        r = requests.get(f"{BASE}/api/shipper-finder/prospects", headers=HEADERS, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "prospects" in data and "counts" in data and "stages" in data
        assert len(data["prospects"]) >= 6
        # ensure required stage keys present
        for s in ["lead", "contacted", "meeting", "quoted", "trial", "contracted", "lost"]:
            assert s in data["counts"]
        assert isinstance(data.get("pipeline_loads_per_week"), int)
        assert data["pipeline_loads_per_week"] > 0

    def test_seed_is_idempotent(self):
        r1 = requests.get(f"{BASE}/api/shipper-finder/prospects", headers=HEADERS, timeout=30)
        c1 = len(r1.json()["prospects"])
        r2 = requests.get(f"{BASE}/api/shipper-finder/prospects", headers=HEADERS, timeout=30)
        c2 = len(r2.json()["prospects"])
        assert c1 == c2, f"Seed duplicated: {c1} -> {c2}"


class TestShipperFinderCRUD:
    def test_create_patch_touch_delete_flow(self):
        payload = {
            "company": "TEST_Acme Shipping",
            "contact_name": "Test Person",
            "city": "Minneapolis",
            "est_loads_per_week": 5,
            "stage": "lead",
        }
        r = requests.post(f"{BASE}/api/shipper-finder/prospects", headers=HEADERS, json=payload, timeout=30)
        assert r.status_code == 200, r.text
        prospect = r.json()["prospect"]
        pid = prospect["id"]
        assert prospect["company"] == "TEST_Acme Shipping"

        # verify persisted via GET
        list_r = requests.get(f"{BASE}/api/shipper-finder/prospects", headers=HEADERS, timeout=30)
        assert any(p["id"] == pid for p in list_r.json()["prospects"])

        # patch stage valid
        r = requests.patch(f"{BASE}/api/shipper-finder/prospects/{pid}",
                           headers=HEADERS, json={"stage": "contacted"}, timeout=30)
        assert r.status_code == 200
        assert r.json()["prospect"]["stage"] == "contacted"

        # patch stage invalid -> 400
        r = requests.patch(f"{BASE}/api/shipper-finder/prospects/{pid}",
                           headers=HEADERS, json={"stage": "nonsense"}, timeout=30)
        assert r.status_code == 400

        # touch
        r = requests.post(f"{BASE}/api/shipper-finder/prospects/{pid}/touch",
                          headers=HEADERS, json={"kind": "call", "note": "left vm"}, timeout=30)
        assert r.status_code == 200
        assert r.json()["touch"]["kind"] == "call"

        # delete
        r = requests.delete(f"{BASE}/api/shipper-finder/prospects/{pid}", headers=HEADERS, timeout=30)
        assert r.status_code == 200

        # verify gone
        r = requests.delete(f"{BASE}/api/shipper-finder/prospects/{pid}", headers=HEADERS, timeout=30)
        assert r.status_code == 404


class TestShipperFinderPlaybook:
    def test_playbook_shape(self):
        r = requests.get(f"{BASE}/api/shipper-finder/playbook", headers=HEADERS, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert len(d["competitive_advantages"]) == 7
        assert len(d["offer_stack"]) == 8
        assert len(d["sourcing_channels"]) == 10
        assert len(d["outreach_tips"]) == 12


class TestShipperFinderOutreach:
    def test_outreach_invalid_channel_returns_422(self):
        # pick any existing prospect
        r = requests.get(f"{BASE}/api/shipper-finder/prospects", headers=HEADERS, timeout=30)
        pid = r.json()["prospects"][0]["id"]
        r = requests.post(f"{BASE}/api/shipper-finder/prospects/{pid}/outreach",
                          headers=HEADERS, json={"channel": "carrier-pigeon"}, timeout=30)
        assert r.status_code == 422

    def test_outreach_email_generates_script(self):
        r = requests.get(f"{BASE}/api/shipper-finder/prospects", headers=HEADERS, timeout=30)
        pid = r.json()["prospects"][0]["id"]
        r = requests.post(f"{BASE}/api/shipper-finder/prospects/{pid}/outreach",
                          headers=HEADERS, json={"channel": "email"}, timeout=90)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        assert body["channel"] == "email"
        assert isinstance(body["script"], str) and len(body["script"]) > 40


class TestShipperBrochurePDF:
    def test_brochure_pdf_ok(self):
        r = requests.get(f"{BASE}/api/shipper-finder/brochure.pdf", headers=HEADERS, timeout=60)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:4] == b"%PDF"
        assert len(r.content) > 5000


# ---------- Plan review regression ----------
class TestPlanReviewRegression:
    def test_plan_review_shape(self):
        r = requests.get(f"{BASE}/api/brokerage/plan-review", headers=HEADERS, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        # salary
        assert d["salary"]["amount_monthly"] == 9167, d["salary"]
        # pnl is a list with 'metric','y1','y2','y3'
        pnl = d["pnl"]
        assert isinstance(pnl, list)
        gross = next((r for r in pnl if "gross revenue" in r["metric"].lower()), None)
        assert gross and gross["y1"] == 4000000, f"Y1 revenue mismatch: {gross}"
        salary_row = next((r for r in pnl if "operator salary" in r["metric"].lower()), None)
        assert salary_row and salary_row["y1"] == 110000, f"operator salary row: {salary_row}"
        # scenario_b mentions 'Plan Y1 exit (14/day)'
        sb = d.get("scenario_b", {})
        sb_txt = str(sb)
        assert "Plan Y1 exit" in sb_txt and "14/day" in sb_txt, sb_txt[:400]
        # working_capital P1 phase mentions '15-25 loads/wk'
        wc = d.get("working_capital", {})
        assert "15-25 loads/wk" in str(wc), str(wc)[:400]
        # industry_benchmarks and dso_playbook present
        assert "industry_benchmarks" in d
        assert "dso_playbook" in d

    def test_plan_vs_actual(self):
        r = requests.get(f"{BASE}/api/brokerage/plan-vs-actual", headers=HEADERS, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        loads_row = next((m for m in d["metrics"] if m["metric"] == "Loads / week"), None)
        net_row = next((m for m in d["metrics"] if "Est. net desk profit" in m["metric"]), None)
        assert loads_row and loads_row["plan"] == 70, loads_row
        assert net_row and net_row["plan"] == 6300, net_row


class TestExistingBrochures:
    def test_business_plan_brochure(self):
        r = requests.get(f"{BASE}/api/brokerage/business-plan/brochure.pdf", headers=HEADERS, timeout=60)
        assert r.status_code == 200
        assert r.content[:4] == b"%PDF"

    def test_partnership_agreement(self):
        r = requests.get(f"{BASE}/api/brokerage/partnership-agreement/pdf", headers=HEADERS, timeout=60)
        assert r.status_code == 200
        assert r.content[:4] == b"%PDF"
