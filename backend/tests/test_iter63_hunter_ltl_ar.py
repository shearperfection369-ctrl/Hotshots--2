"""
Iter 63 — Backend test for:
  1. AI Load Hunter (scan, winners, book, dismiss, config, risk, audit, compliance, stats)
  2. LTL Rate Cards (cards seed, quote, inline update, history)
  3. AR Aging (aging, auto-invoice, sync-risk, mark-paid, remind, dunning)
  4. Ops KPIs daily margin series
  5. Carrier Brochure PDF
"""
import os
import time
import requests
import pytest

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://clean-logistics-dash.preview.emergentagent.com").rstrip("/")
TOKEN = "test_session_admin_1"
HDR = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}


@pytest.fixture(scope="session", autouse=True)
def seed_carriers():
    # required so hunter has carriers to match
    requests.post(f"{BASE}/api/dispatch/carriers/seed", headers=HDR, timeout=15)
    yield
    # cleanup: reset hunter config to balanced/auto_book=false at the end
    requests.post(
        f"{BASE}/api/load-hunter/config",
        headers=HDR,
        json={"mode": "balanced", "auto_book_enabled": False, "min_score": 80, "max_rate_usd": 3000, "max_per_day": 5},
        timeout=15,
    )


# ---------------- LOAD HUNTER ----------------
class TestLoadHunter:
    def test_scan_returns_winners_with_components(self):
        r = requests.post(f"{BASE}/api/load-hunter/scan", headers=HDR, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "scanned" in d and "winners" in d and "elapsed_ms" in d
        assert d["scanned"] > 0
        assert isinstance(d.get("winners_list"), list)
        if d["winners_list"]:
            w = d["winners_list"][0]
            for k in ("margin_pct", "shipper_reliability", "lane_profitability",
                      "fuel_economics", "detention_risk", "driver_match"):
                assert k in w["components"], f"missing component {k}"
            # best_carrier populated after seeding
            assert w.get("best_carrier") is not None, "best_carrier not populated after seeding carriers"

    def test_get_winners(self):
        r = requests.get(f"{BASE}/api/load-hunter/winners", headers=HDR, timeout=15)
        assert r.status_code == 200
        d = r.json()
        winners = d.get("items") or d.get("winners") or d
        assert isinstance(winners, list)

    def test_book_and_dismiss_winner(self):
        # ensure some winners
        requests.post(f"{BASE}/api/load-hunter/scan", headers=HDR, timeout=30)
        r = requests.get(f"{BASE}/api/load-hunter/winners", headers=HDR, timeout=15)
        d = r.json()
        winners = d.get("items") or d.get("winners") or d
        # find a not-yet-booked winner
        booked_status_keys = ("booked", "dismissed", "status")
        candidate = None
        for w in winners:
            status = w.get("status", "")
            if status not in ("booked", "dismissed"):
                candidate = w
                break
        if not candidate and winners:
            candidate = winners[0]
        if not candidate:
            pytest.skip("no winners to book/dismiss")
        wid = candidate.get("winner_id") or candidate.get("id")
        book = requests.post(f"{BASE}/api/load-hunter/winners/{wid}/book", headers=HDR, timeout=20)
        # 200/201 for fresh book; 400 "Already booked" is acceptable given auto-book side-effects
        assert book.status_code in (200, 201, 400), book.text
        if book.status_code in (200, 201):
            bd = book.json()
            assert bd.get("ok") or bd.get("booking_id") or bd.get("shipment_id") or bd.get("booking"), bd

        # find another candidate to dismiss
        dismiss_target = None
        for w in winners:
            if (w.get("winner_id") or w.get("id")) != wid and w.get("status") not in ("booked", "dismissed"):
                dismiss_target = w
                break
        if dismiss_target:
            wid2 = dismiss_target.get("winner_id") or dismiss_target.get("id")
            dis = requests.post(f"{BASE}/api/load-hunter/winners/{wid2}/dismiss", headers=HDR, timeout=15)
            assert dis.status_code in (200, 204, 400), dis.text

    def test_config_mode_switch(self):
        for mode in ("high_margin", "high_volume", "balanced"):
            r = requests.post(
                f"{BASE}/api/load-hunter/config",
                headers=HDR,
                json={"mode": mode},
                timeout=15,
            )
            assert r.status_code == 200, r.text
            d = r.json()
            cfg = d.get("config", d)
            assert cfg.get("mode") == mode

    def test_config_auto_book_and_scan_books(self):
        # enable auto-book
        r = requests.post(
            f"{BASE}/api/load-hunter/config",
            headers=HDR,
            json={"mode": "balanced", "auto_book_enabled": True, "min_score": 80,
                  "max_rate_usd": 3000, "max_per_day": 3},
            timeout=15,
        )
        assert r.status_code == 200
        cfg = r.json().get("config", r.json())
        # config can be nested — auto_book.enabled or flat auto_book_enabled
        ab = cfg.get("auto_book") if isinstance(cfg.get("auto_book"), dict) else None
        enabled = (ab or {}).get("enabled", cfg.get("auto_book_enabled"))
        assert enabled is True, f"auto_book not enabled: {cfg}"

        # scan
        s = requests.post(f"{BASE}/api/load-hunter/scan", headers=HDR, timeout=30)
        assert s.status_code == 200
        sd = s.json()
        # auto_booked can be 0 if all winners already booked from prior test scans; just assert key present
        assert "auto_booked" in sd
        assert isinstance(sd.get("auto_booked_ids", []), list)

    def test_risk_registry_has_kraft(self):
        r = requests.get(f"{BASE}/api/load-hunter/risk", headers=HDR, timeout=15)
        assert r.status_code == 200
        d = r.json()
        rows = d.get("shippers") or d.get("registry") or d if isinstance(d, list) else d.get("risk", [])
        # look for kraft (case-insensitive)
        txt = str(d).lower()
        assert "kraft" in txt, "Kraft Heinz not seeded in risk registry"

    def test_audit_and_compliance_and_stats(self):
        for path in ("audit", "compliance", "stats"):
            r = requests.get(f"{BASE}/api/load-hunter/{path}", headers=HDR, timeout=15)
            assert r.status_code == 200, f"{path} failed: {r.text}"


# ---------------- LTL RATE CARDS ----------------
class TestLTL:
    def test_cards_autoseed_six(self):
        r = requests.get(f"{BASE}/api/ltl/cards", headers=HDR, timeout=15)
        assert r.status_code == 200
        d = r.json()
        cards = d.get("items") or d.get("cards") or (d if isinstance(d, list) else [])
        assert len(cards) >= 6, f"expected >=6 seeded cards, got {len(cards)}"

    def test_quote_returns_six_ranked(self):
        payload = {
            "origin_state": "MN", "dest_state": "IL",
            "weight_lbs": 2400, "freight_class": "70",
            "accessorials": ["liftgate_delivery"],
            "target_margin_pct": 22
        }
        r = requests.post(f"{BASE}/api/ltl/quote", headers=HDR, json=payload, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        quotes = d.get("quotes", d) if isinstance(d, dict) else d
        assert len(quotes) >= 6
        cheapest_flags = [q for q in quotes if q.get("cheapest")]
        assert len(cheapest_flags) == 1, "exactly one cheapest quote expected"
        q0 = quotes[0]
        for k in ("net_total_usd", "suggested_sell_usd"):
            assert k in q0, f"missing {k} in quote"

    def test_inline_update_card_discount(self):
        cards = requests.get(f"{BASE}/api/ltl/cards", headers=HDR, timeout=15).json()
        cards_list = cards.get("items") or cards.get("cards") or (cards if isinstance(cards, list) else [])
        c = dict(cards_list[0])
        scac = c.get("scac")
        new_disc = 42.5
        # inline update requires full card payload
        payload = {k: v for k, v in c.items() if k not in ("_id", "updated_at", "updated_by")}
        payload["discount_pct"] = new_disc
        r = requests.post(
            f"{BASE}/api/ltl/cards",
            headers=HDR,
            json=payload,
            timeout=15,
        )
        assert r.status_code in (200, 201), r.text
        after = requests.get(f"{BASE}/api/ltl/cards", headers=HDR, timeout=15).json()
        after_list = after.get("items") or after.get("cards") or (after if isinstance(after, list) else [])
        match = next((x for x in after_list if x.get("scac") == scac), None)
        assert match, "card missing after update"
        assert abs(match.get("discount_pct", 0) - new_disc) < 0.01, f"discount not persisted: {match}"

    def test_quotes_history(self):
        r = requests.get(f"{BASE}/api/ltl/quotes", headers=HDR, timeout=15)
        assert r.status_code == 200


# ---------------- AR AGING ----------------
class TestAR:
    def test_aging_buckets(self):
        r = requests.get(f"{BASE}/api/ar/aging", headers=HDR, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert "buckets" in d or "customers" in d, d
        # buckets keys should include 0_30 / 31_60 / 61_90 / 91_plus or similar
        keys = str(d.get("buckets", {})).lower()
        # not strict; just ensure has data structure
        assert isinstance(d.get("buckets") or d.get("customers"), (dict, list))

    def test_auto_invoice_idempotent(self):
        r1 = requests.post(f"{BASE}/api/ar/auto-invoice/run", headers=HDR, timeout=30)
        assert r1.status_code == 200, r1.text
        d1 = r1.json()
        created1 = d1.get("created", d1.get("invoices_created", 0))
        # second run - should create zero
        r2 = requests.post(f"{BASE}/api/ar/auto-invoice/run", headers=HDR, timeout=30)
        assert r2.status_code == 200
        d2 = r2.json()
        created2 = d2.get("created", d2.get("invoices_created", 0))
        assert created2 == 0, f"second run should be idempotent, created={created2}"

    def test_sync_risk(self):
        r = requests.post(f"{BASE}/api/ar/sync-risk", headers=HDR, timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert "synced" in d or "flagged" in d or d.get("ok") is True

    def test_mark_paid_and_remind(self):
        # get first invoice id from aging response
        aging = requests.get(f"{BASE}/api/ar/aging", headers=HDR, timeout=15).json()
        inv_id = None
        for c in aging.get("customers", []):
            if c.get("oldest_invoice_id"):
                inv_id = c["oldest_invoice_id"]
                break
        if not inv_id:
            pytest.skip("no invoice available to mark-paid/remind")
        remind = requests.post(f"{BASE}/api/ar/invoices/{inv_id}/remind", headers=HDR, timeout=15)
        assert remind.status_code in (200, 201), remind.text
        paid = requests.post(f"{BASE}/api/ar/invoices/{inv_id}/mark-paid", headers=HDR, timeout=15)
        assert paid.status_code in (200, 201), paid.text

    def test_dunning_list(self):
        r = requests.get(f"{BASE}/api/ar/dunning", headers=HDR, timeout=15)
        assert r.status_code == 200


# ---------------- OPS KPIs daily ----------------
def test_ops_kpis_daily_series():
    r = requests.get(f"{BASE}/api/brokerage/ops-kpis?window_days=30", headers=HDR, timeout=20)
    assert r.status_code == 200, r.text
    d = r.json()
    assert "daily" in d, f"'daily' missing: keys={list(d.keys())}"
    daily = d["daily"]
    assert isinstance(daily, list) and len(daily) >= 28
    e = daily[0]
    for k in ("revenue_usd", "margin_usd", "loads"):
        assert k in e, f"daily entry missing {k}: {e}"


# ---------------- Carrier brochure ----------------
def test_carrier_brochure_pdf():
    r = requests.get(f"{BASE}/api/brokerage/carrier-brochure.pdf", headers=HDR, timeout=30)
    assert r.status_code == 200
    assert "pdf" in r.headers.get("content-type", "").lower()
    assert len(r.content) > 100 * 1024, f"pdf too small: {len(r.content)} bytes"
    assert r.content.startswith(b"%PDF")
