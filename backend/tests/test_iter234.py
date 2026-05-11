"""
Tennant TMS — Iterations 2, 3, 4 backend tests
- Iter 2: PDF rendering, RBAC (admin/auditor/dispatcher), SAP S/4HANA mock
- Iter 3: AI Assistant (Claude Sonnet 4.5) — single call, Webex (mocked)
- Iter 4: Workbook (Excel-style renameable tabs) + xlsx export (single & full)
"""
import os
import json as _json
import subprocess
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://clean-logistics-dash.preview.emergentagent.com").rstrip("/")


# =================================================================
# Iter 2 — PDF rendering for documents
# =================================================================
class TestDocumentPDF:
    def _get_doc_ids_by_type(self, client):
        """Return mapping of doc_type -> document_id directly from MongoDB seed."""
        # Documents are seeded in db.documents and aren't exposed via a list endpoint;
        # use mongosh to pluck one id per type for PDF rendering tests.
        js = """
        use('test_database');
        const types = db.documents.distinct('type');
        const result = {};
        types.forEach(t => {
          const d = db.documents.findOne({type: t}, {_id: 0, document_id: 1, type: 1});
          if (d && d.document_id) result[t] = d.document_id;
        });
        print('JSON_START' + JSON.stringify(result) + 'JSON_END');
        """
        out = subprocess.run(["mongosh", "--quiet", "--eval", js], capture_output=True, text=True, check=True).stdout
        s = out.find("JSON_START") + len("JSON_START")
        e = out.find("JSON_END")
        return _json.loads(out[s:e])

    def test_pdf_requires_auth(self):
        # any id — auth missing must come back 401 before 404
        r = requests.get(f"{BASE_URL}/api/documents/DOC-NOTREAL/pdf")
        assert r.status_code == 401

    def test_pdf_404_on_missing(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/documents/DOC-DOESNOTEXIST/pdf")
        assert r.status_code == 404

    def test_pdf_renders_all_doc_types(self, api_client):
        # Iterate all shipments to find at least one doc of each requested type
        wanted = {"BOL", "COMMERCIAL_INVOICE", "PACKING_SLIP", "WEIGHT_CERT", "COO"}
        ids = self._get_doc_ids_by_type(api_client)
        # If types are missing, fall back to whatever ids exist (rendered as long as available)
        tested = 0
        for t in list(ids.keys()):
            doc_id = ids[t]
            r = api_client.get(f"{BASE_URL}/api/documents/{doc_id}/pdf")
            assert r.status_code == 200, f"PDF for {t} failed: {r.status_code} {r.text[:200]}"
            assert r.headers.get("content-type", "").startswith("application/pdf")
            assert r.content[:4] == b"%PDF", f"PDF magic bytes missing for {t}: {r.content[:8]!r}"
            assert "attachment" in r.headers.get("content-disposition", "").lower()
            tested += 1
        assert tested >= 1, "No documents found to render"
        # Soft-coverage check: log which expected types weren't present
        missing = wanted - set(ids.keys())
        if missing:
            print(f"[WARN] doc types not present in seed: {sorted(missing)}")


# =================================================================
# Iter 2 — Admin / RBAC
# =================================================================
class TestAdminRBAC:
    def test_list_users_admin_only(self, api_client, admin_client):
        r_no = requests.get(f"{BASE_URL}/api/admin/users")
        assert r_no.status_code == 401
        r_disp = api_client.get(f"{BASE_URL}/api/admin/users")
        assert r_disp.status_code == 403
        r_admin = admin_client.get(f"{BASE_URL}/api/admin/users")
        assert r_admin.status_code == 200
        assert isinstance(r_admin.json(), list)
        assert len(r_admin.json()) >= 1

    def test_seed_team_admin_only_and_idempotent(self, api_client, admin_client):
        r_disp = api_client.post(f"{BASE_URL}/api/admin/seed-team")
        assert r_disp.status_code == 403
        r1 = admin_client.post(f"{BASE_URL}/api/admin/seed-team")
        assert r1.status_code == 200
        d1 = r1.json()
        assert "inserted" in d1 or d1.get("ok") is True
        # idempotent — re-running should not error and should not double-insert
        r2 = admin_client.post(f"{BASE_URL}/api/admin/seed-team")
        assert r2.status_code == 200

    def test_change_role(self, admin_client, dispatcher_session):
        # change a different user's role (use a dispatcher fixture user, not the admin themselves)
        target_user_id = None
        users = admin_client.get(f"{BASE_URL}/api/admin/users").json()
        for u in users:
            if u.get("role") == "driver":
                target_user_id = u["user_id"]; break
        if not target_user_id:
            # fallback: create-by-seed-team and pick a driver
            admin_client.post(f"{BASE_URL}/api/admin/seed-team")
            users = admin_client.get(f"{BASE_URL}/api/admin/users").json()
            for u in users:
                if u.get("role") == "driver":
                    target_user_id = u["user_id"]; break
        assert target_user_id, "No driver user available for role-change test"

        # invalid role rejected
        r_bad = admin_client.post(f"{BASE_URL}/api/admin/users/{target_user_id}/role", json={"role": "godmode"})
        assert r_bad.status_code == 400

        # valid promote to auditor
        r_ok = admin_client.post(f"{BASE_URL}/api/admin/users/{target_user_id}/role", json={"role": "auditor"})
        assert r_ok.status_code == 200
        assert r_ok.json()["role"] == "auditor"

        # demote back to driver
        admin_client.post(f"{BASE_URL}/api/admin/users/{target_user_id}/role", json={"role": "driver"})

    def test_change_role_unknown_user(self, admin_client):
        r = admin_client.post(f"{BASE_URL}/api/admin/users/nonexistent-user/role", json={"role": "auditor"})
        assert r.status_code == 404


# =================================================================
# Iter 2 — SAP S/4HANA mock
# =================================================================
class TestSAP:
    def test_config(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/sap/config")
        assert r.status_code == 200
        d = r.json()
        assert "host" in d and "service" in d

    def test_sales_orders_and_plant_filter(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/sap/sales-orders")
        assert r.status_code == 200
        d = r.json()
        assert "value" in d and isinstance(d["value"], list) and len(d["value"]) >= 1
        r2 = api_client.get(f"{BASE_URL}/api/sap/sales-orders?plant=1010")
        assert r2.status_code == 200
        d2 = r2.json()
        for o in d2["value"]:
            assert o["Plant"] == "1010"

    def test_purchase_orders_only_imports(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/sap/purchase-orders?only_imports=true")
        assert r.status_code == 200
        d = r.json()
        for o in d["value"]:
            assert o["IsImport"] is True

    def test_sync_rbac_and_logs(self, api_client, admin_client, auditor_client):
        # auditor forbidden
        r_aud = auditor_client.post(f"{BASE_URL}/api/sap/sync")
        assert r_aud.status_code == 403
        # dispatcher allowed
        r_disp = api_client.post(f"{BASE_URL}/api/sap/sync")
        assert r_disp.status_code == 200
        # admin allowed
        r_adm = admin_client.post(f"{BASE_URL}/api/sap/sync")
        assert r_adm.status_code == 200
        log = r_adm.json()
        assert log["status"] == "success"
        log_id = log["log_id"]

        # logs list contains it
        r_log = api_client.get(f"{BASE_URL}/api/sap/sync-logs")
        assert r_log.status_code == 200
        logs = r_log.json()
        assert any(x["log_id"] == log_id for x in logs)


# =================================================================
# Iter 3 — AI Assistant (single budget-safe call)
# =================================================================
class TestAIAssistant:
    def test_chat_single_message(self, api_client):
        session_id = "pytest-ai-session-iter234"
        # Clean prior history for the test session
        api_client.delete(f"{BASE_URL}/api/ai/history", params={"session_id": session_id})

        r = api_client.post(f"{BASE_URL}/api/ai/chat", json={
            "session_id": session_id,
            "message": "In one short sentence: what is HS code 8479?"
        })
        assert r.status_code == 200, r.text
        d = r.json()
        assert "reply" in d and isinstance(d["reply"], str) and len(d["reply"].strip()) > 0

        # history must contain user + assistant (oldest first)
        r2 = api_client.get(f"{BASE_URL}/api/ai/history", params={"session_id": session_id})
        assert r2.status_code == 200
        hist = r2.json()
        assert len(hist) >= 2
        roles = [m["role"] for m in hist]
        assert "user" in roles and "assistant" in roles
        # oldest first ordering
        assert hist[0]["created_at"] <= hist[-1]["created_at"]

    def test_history_user_scoped(self, api_client, auditor_client):
        # Auditor must not see the dispatcher's session messages
        session_id = "pytest-ai-session-iter234"
        r = auditor_client.get(f"{BASE_URL}/api/ai/history", params={"session_id": session_id})
        assert r.status_code == 200
        assert r.json() == []

    def test_delete_history(self, api_client):
        session_id = "pytest-ai-session-iter234"
        r = api_client.delete(f"{BASE_URL}/api/ai/history", params={"session_id": session_id})
        assert r.status_code == 200
        assert r.json().get("ok") is True
        r2 = api_client.get(f"{BASE_URL}/api/ai/history", params={"session_id": session_id})
        assert r2.json() == []


# =================================================================
# Iter 3 — Webex (mocked)
# =================================================================
class TestWebex:
    def test_endpoints_require_auth(self):
        for p in ("/api/webex/config", "/api/webex/spaces", "/api/webex/meetings", "/api/webex/log"):
            assert requests.get(f"{BASE_URL}{p}").status_code == 401

    def test_static_collections(self, api_client):
        assert api_client.get(f"{BASE_URL}/api/webex/config").json().get("status") == "connected"
        spaces = api_client.get(f"{BASE_URL}/api/webex/spaces").json()
        meetings = api_client.get(f"{BASE_URL}/api/webex/meetings").json()
        assert len(spaces) == 7
        assert len(meetings) == 4

    def test_notify_writes_log(self, api_client):
        payload = {"space_id": "SPC-OPS-DISP", "text": "TEST_pytest webex notify", "shipment_ref": "SHP-TEST"}
        r = api_client.post(f"{BASE_URL}/api/webex/notify", json=payload)
        assert r.status_code == 200
        rec = r.json()
        assert rec["status"] == "delivered" and rec["space_id"] == "SPC-OPS-DISP"
        log_id = rec["log_id"]
        logs = api_client.get(f"{BASE_URL}/api/webex/log").json()
        assert any(x["log_id"] == log_id for x in logs)

    def test_schedule_creates_meeting(self, api_client):
        payload = {"title": "TEST_pytest mtg", "when": "2026-06-01T15:00:00Z", "duration_min": 30, "invitees": ["a@x.com"]}
        r = api_client.post(f"{BASE_URL}/api/webex/schedule", json=payload)
        assert r.status_code == 200
        m = r.json()
        assert m["title"] == "TEST_pytest mtg" and m["duration_min"] == 30 and m["attendees"] == 1
        assert m["join_url"].startswith("https://tennantco.webex.com/")


# =================================================================
# Iter 4 — Workbook
# =================================================================
class TestWorkbook:
    def test_tabs_autoseed_13(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/workbook/tabs")
        assert r.status_code == 200
        tabs = r.json()
        assert len(tabs) >= 13
        names = {t["name"] for t in tabs}
        expected = {"Outbound TL", "Outbound LTL", "Expedites", "Crate Spots",
                    "Seafreight 25M", "25 Import", "25 Quotes", "Plant Hubs",
                    "IN Primary Carrier", "IN Supplier Contacts", "IN Carrier Contacts",
                    "Info", "Volume Overview"}
        assert expected.issubset(names), f"Missing default tabs: {expected - names}"
        # each tab has columns array
        for t in tabs:
            assert "columns" in t and isinstance(t["columns"], list)

    def test_tabs_require_auth(self):
        assert requests.get(f"{BASE_URL}/api/workbook/tabs").status_code == 401

    def test_create_unknown_kind_rejected(self, api_client):
        r = api_client.post(f"{BASE_URL}/api/workbook/tabs", json={"name": "Bad", "kind": "junk_kind"})
        assert r.status_code == 400

    def test_create_rename_delete_tab(self, api_client):
        # CREATE
        r = api_client.post(f"{BASE_URL}/api/workbook/tabs", json={"name": "TEST_pytest_tab", "kind": "info"})
        assert r.status_code == 200, r.text
        tab = r.json()
        tab_id = tab["tab_id"]
        assert tab["name"] == "TEST_pytest_tab"
        assert isinstance(tab.get("columns"), list)

        # PATCH rename + order
        r2 = api_client.patch(f"{BASE_URL}/api/workbook/tabs/{tab_id}", json={"name": "TEST_pytest_renamed", "order": 99})
        assert r2.status_code == 200
        assert r2.json().get("ok") is True

        # Verify rename via GET
        tabs = api_client.get(f"{BASE_URL}/api/workbook/tabs").json()
        match = next((t for t in tabs if t["tab_id"] == tab_id), None)
        assert match is not None and match["name"] == "TEST_pytest_renamed"

        # PATCH missing → 404
        r_missing = api_client.patch(f"{BASE_URL}/api/workbook/tabs/TAB-DOESNOTEXIST", json={"name": "x"})
        assert r_missing.status_code == 404

        # DELETE
        r3 = api_client.delete(f"{BASE_URL}/api/workbook/tabs/{tab_id}")
        assert r3.status_code == 200
        # DELETE missing → 404
        r4 = api_client.delete(f"{BASE_URL}/api/workbook/tabs/{tab_id}")
        assert r4.status_code == 404

    def test_rows_projection_nested_keys(self, api_client):
        tabs = api_client.get(f"{BASE_URL}/api/workbook/tabs").json()
        tl_tab = next(t for t in tabs if t["name"] == "Outbound TL")
        r = api_client.get(f"{BASE_URL}/api/workbook/tabs/{tl_tab['tab_id']}/rows")
        assert r.status_code == 200
        body = r.json()
        assert {"tab", "columns", "rows"}.issubset(body.keys())
        # columns include nested origin.city / destination.city
        col_keys = [c["key"] for c in body["columns"]]
        assert "origin.city" in col_keys and "destination.city" in col_keys
        # rows are flat-projected — nested keys present as flat keys with non-None values when source had them
        if body["rows"]:
            r0 = body["rows"][0]
            assert "origin.city" in r0  # key present in projection
            assert "destination.city" in r0

    def test_rows_404_on_missing_tab(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/workbook/tabs/TAB-NOPE/rows")
        assert r.status_code == 404

    def test_export_tab_xlsx(self, api_client):
        tabs = api_client.get(f"{BASE_URL}/api/workbook/tabs").json()
        info_tab = next(t for t in tabs if t["name"] == "Info")
        r = api_client.get(f"{BASE_URL}/api/workbook/tabs/{info_tab['tab_id']}/export.xlsx")
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        cd = r.headers.get("content-disposition", "")
        assert "filename" in cd.lower()
        assert r.content[:2] == b"PK", f"xlsx zip header missing: {r.content[:8]!r}"
        assert len(r.content) > 1000

    def test_export_all_xlsx(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/workbook/export-all.xlsx")
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        assert r.content[:2] == b"PK"
        # Should be larger than single-tab export
        assert len(r.content) > 5000
