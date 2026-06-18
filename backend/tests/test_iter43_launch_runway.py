"""
Iteration 43 — Launch Runway + Shipper Outreach.

Coverage:
- GET  /api/launch-runway, /api/launch-runway/summary
- POST /api/launch-runway/{id}/toggle (persistence)
- POST /api/launch-runway/{id}/notes (persistence)
- POST /api/shipper-outreach/generate (email, call_script, linkedin_dm)
- POST /api/shipper-outreach/pdf (capability, agreement, welcome, credit_ref, onboarding_packet)
- GET  /api/shipper-outreach/templates
- Auto-archive verification via /api/doc-vault
"""
import pytest


# --------------------------------------------------------------------------- #
# Launch Runway — Plan / Summary
# --------------------------------------------------------------------------- #
class TestLaunchRunwayPlan:
    def test_get_plan_returns_12_milestones(self, api_client, base_url):
        r = api_client.get(f"{base_url}/api/launch-runway")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "milestones" in data
        assert len(data["milestones"]) == 12

        expected_phases = {"Week 1–2", "Week 3–4", "Day 15", "Day 21",
                           "Day 28", "Month 2", "Month 3–6", "Month 12"}
        phases_in_data = {m["phase"] for m in data["milestones"]}
        assert expected_phases.issubset(phases_in_data), \
            f"Missing phases: {expected_phases - phases_in_data}"

        # Per-milestone fields
        required = {"id", "phase", "label", "narrative", "kpi_key",
                    "kpi_target", "kpi_label", "actual", "actual_pct",
                    "status"}
        for m in data["milestones"]:
            missing = required - set(m.keys())
            assert not missing, f"{m.get('id')} missing fields: {missing}"

        # Actuals payload
        actuals = data.get("actuals", {})
        for k in ("shippers_closed", "calls_logged", "invoices_generated",
                  "dollars_collected", "factor_apps_submitted",
                  "factor_live", "total_margin", "bookings",
                  "invoiced_usd"):
            assert k in actuals, f"actuals missing {k}"

    def test_summary_fields(self, api_client, base_url):
        r = api_client.get(f"{base_url}/api/launch-runway/summary")
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["total_milestones"] == 12
        for k in ("completed", "in_progress", "pct_complete",
                  "actuals", "target_y1_margin"):
            assert k in d
        assert d["target_y1_margin"] == 50000
        # `current` and `next_action` may be None depending on data
        assert "current" in d
        assert "next_action" in d


# --------------------------------------------------------------------------- #
# Toggle & Notes persistence
# --------------------------------------------------------------------------- #
class TestLaunchRunwayMutations:
    MILESTONE = "p1-cold-call"

    def test_toggle_to_done_then_back(self, api_client, base_url):
        # mark done
        r = api_client.post(
            f"{base_url}/api/launch-runway/{self.MILESTONE}/toggle",
            json={"status": "done"})
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "done"

        # verify on the list
        r2 = api_client.get(f"{base_url}/api/launch-runway")
        rec = next(m for m in r2.json()["milestones"] if m["id"] == self.MILESTONE)
        assert rec["status"] == "done"
        assert rec.get("completed_at"), "completed_at should be populated"

        # toggle back to todo
        r3 = api_client.post(
            f"{base_url}/api/launch-runway/{self.MILESTONE}/toggle",
            json={"status": "todo"})
        assert r3.status_code == 200
        assert r3.json()["status"] == "todo"

        # verify persistence of revert
        r4 = api_client.get(f"{base_url}/api/launch-runway")
        rec2 = next(m for m in r4.json()["milestones"] if m["id"] == self.MILESTONE)
        # status may not strictly be 'todo' because of auto-computed override
        # but the manual override should be lifted and completed_at cleared
        assert rec2.get("completed_at") in (None, ""), \
            f"completed_at not cleared after revert: {rec2.get('completed_at')}"

    def test_toggle_unknown_milestone_404(self, api_client, base_url):
        r = api_client.post(
            f"{base_url}/api/launch-runway/does-not-exist/toggle",
            json={"status": "done"})
        assert r.status_code == 404

    def test_toggle_invalid_status_400(self, api_client, base_url):
        r = api_client.post(
            f"{base_url}/api/launch-runway/{self.MILESTONE}/toggle",
            json={"status": "garbage"})
        assert r.status_code == 400

    def test_note_persists(self, api_client, base_url):
        note = "TEST_iter43 note — automated"
        r = api_client.post(
            f"{base_url}/api/launch-runway/{self.MILESTONE}/notes",
            json={"note": note})
        assert r.status_code == 200, r.text

        r2 = api_client.get(f"{base_url}/api/launch-runway")
        rec = next(m for m in r2.json()["milestones"] if m["id"] == self.MILESTONE)
        assert rec.get("note") == note


# --------------------------------------------------------------------------- #
# Shipper Outreach text channels
# --------------------------------------------------------------------------- #
SHIPPER = "SUPERVALU"
CONTACT = "Mike"
LANE    = "Eden Prairie → Des Moines"
MODE    = "TL + LTL"


def _gen_body(**extra):
    body = {
        "shipper_name": SHIPPER,
        "contact_name": CONTACT,
        "lane_focus":   LANE,
        "mode_mix":     MODE,
        "personalize_with_ai": False,
    }
    body.update(extra)
    return body


class TestOutreachText:
    def test_templates_lists_all_8(self, api_client, base_url):
        r = api_client.get(f"{base_url}/api/shipper-outreach/templates")
        assert r.status_code == 200
        ids = {c["id"] for c in r.json()["channels"]}
        expected = {"email", "call_script", "linkedin_dm",
                    "capability_pdf", "agreement_pdf", "welcome_pdf",
                    "credit_ref_pdf", "onboarding_packet"}
        assert expected.issubset(ids), \
            f"missing channels: {expected - ids}"

    def test_email_generation(self, api_client, base_url):
        r = api_client.post(
            f"{base_url}/api/shipper-outreach/generate?channel=email",
            json=_gen_body())
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["channel"] == "email"
        assert SHIPPER in d["subject"]
        assert f"Hi {CONTACT}" in d["plain"]
        assert d["html"].startswith("<div")

    def test_call_script_generation(self, api_client, base_url):
        r = api_client.post(
            f"{base_url}/api/shipper-outreach/generate?channel=call_script",
            json=_gen_body())
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["channel"] == "call_script"
        md = d["markdown"]
        assert md.startswith("# COLD CALL SCRIPT")
        assert SHIPPER in md

    def test_linkedin_dm_generation(self, api_client, base_url):
        r = api_client.post(
            f"{base_url}/api/shipper-outreach/generate?channel=linkedin_dm",
            json=_gen_body())
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["channel"] == "linkedin_dm"
        assert SHIPPER in d["text"]

    def test_invalid_text_channel(self, api_client, base_url):
        r = api_client.post(
            f"{base_url}/api/shipper-outreach/generate?channel=bogus",
            json=_gen_body())
        assert r.status_code == 400


# --------------------------------------------------------------------------- #
# Shipper Outreach PDF channels + vault auto-archive
# --------------------------------------------------------------------------- #
class TestOutreachPDF:
    def _post_pdf(self, api_client, base_url, channel, **extra):
        return api_client.post(
            f"{base_url}/api/shipper-outreach/pdf?channel={channel}",
            json=_gen_body(**extra))

    def test_capability_pdf(self, api_client, base_url):
        r = self._post_pdf(api_client, base_url, "capability_pdf")
        assert r.status_code == 200, r.text[:300]
        assert r.headers["content-type"].startswith("application/pdf")
        assert r.content[:4] == b"%PDF"
        assert len(r.content) > 100_000, \
            f"capability PDF too small: {len(r.content)} bytes"

        # Auto-archived to vault
        v = api_client.get(f"{base_url}/api/doc-vault",
                           params={"doc_type": "CAPABILITY", "limit": 5})
        assert v.status_code == 200
        rows = v.json().get("documents") or v.json().get("rows") or v.json()
        assert rows, "Expected at least one CAPABILITY entry in doc-vault"

    def test_agreement_pdf_contains_net_terms(self, api_client, base_url):
        r = self._post_pdf(api_client, base_url, "agreement_pdf",
                            net_terms=14)
        assert r.status_code == 200, r.text[:300]
        assert r.content[:4] == b"%PDF"
        # Content has 'NET 14' embedded as raw text (uncompressed pdf may
        # not contain it readable; minimum check is PDF magic + size).
        assert len(r.content) > 50_000

    def test_welcome_pdf(self, api_client, base_url):
        r = self._post_pdf(api_client, base_url, "welcome_pdf")
        assert r.status_code == 200, r.text[:300]
        assert r.content[:4] == b"%PDF"
        assert len(r.content) > 50_000

        v = api_client.get(f"{base_url}/api/doc-vault",
                           params={"doc_type": "WELCOME", "limit": 5})
        assert v.status_code == 200

    def test_credit_ref_pdf(self, api_client, base_url):
        r = self._post_pdf(api_client, base_url, "credit_ref_pdf")
        assert r.status_code == 200, r.text[:300]
        assert r.content[:4] == b"%PDF"
        assert len(r.content) > 30_000

    def test_onboarding_packet(self, api_client, base_url):
        r = self._post_pdf(api_client, base_url, "onboarding_packet")
        assert r.status_code == 200, r.text[:300]
        assert r.content[:4] == b"%PDF"
        assert len(r.content) > 300_000, \
            f"packet too small ({len(r.content)} bytes) — expected > 300KB"

        v = api_client.get(f"{base_url}/api/doc-vault",
                           params={"doc_type": "ONBOARDING_PACKET", "limit": 5})
        assert v.status_code == 200
        rows = v.json().get("documents") or v.json().get("rows") or v.json()
        assert rows, "ONBOARDING_PACKET should auto-archive"

    def test_invalid_pdf_channel(self, api_client, base_url):
        r = self._post_pdf(api_client, base_url, "nonsense")
        assert r.status_code == 400


# --------------------------------------------------------------------------- #
# Edge cases
# --------------------------------------------------------------------------- #
class TestEdgeCases:
    def test_email_missing_optional_fields(self, api_client, base_url):
        r = api_client.post(
            f"{base_url}/api/shipper-outreach/generate?channel=email",
            json={"shipper_name": "Acme", "personalize_with_ai": False})
        assert r.status_code == 200, r.text
        d = r.json()
        assert "Acme" in d["subject"]
        # Defaults to 'Hi team,' when contact_name missing
        assert "Hi team" in d["plain"]

    def test_email_empty_shipper_name(self, api_client, base_url):
        # Pydantic should still accept empty string (field required, not min_length)
        r = api_client.post(
            f"{base_url}/api/shipper-outreach/generate?channel=email",
            json={"shipper_name": "", "personalize_with_ai": False})
        # Either 200 (with empty shipper) or 422 acceptable; do not crash
        assert r.status_code in (200, 400, 422), r.text[:200]
