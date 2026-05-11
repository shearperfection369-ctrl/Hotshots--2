"""Capture each TMS page using Playwright with the system Chromium binary
(playwright browsers aren't downloaded; we use the local /usr/bin/chromium).

Saves PNGs into /tmp/tms_promo_v2/shots/{slug}.png — same layout as
build_promo_with_screens.py expects.
"""
import os
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = "https://clean-logistics-dash.preview.emergentagent.com"
TOKEN = "test_session_admin_1"
OUT = Path("/tmp/tms_promo_v2/shots")
OUT.mkdir(parents=True, exist_ok=True)

SCENES = [
    ("/dashboard", "01_command"),
    ("/shipments", "02_shipments"),
    ("/workbook", "03_booking"),
    ("/documents", "04_documents"),
    ("/equipment", "05_equipment"),
    ("/trade-compliance", "06_trade"),
    ("/machines", "07_catalog"),
    ("/carrier-rates", "08_rates"),
]

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        executable_path="/usr/bin/chromium",
        args=["--no-sandbox", "--disable-dev-shm-usage"],
    )
    ctx = browser.new_context(viewport={"width": 1920, "height": 1080})
    ctx.add_cookies([{
        "name": "session_token", "value": TOKEN,
        "domain": ".preview.emergentagent.com",
        "path": "/", "secure": True, "sameSite": "None",
    }])
    page = ctx.new_page()
    # Warm-up navigation to make sure cookie is sent before first real load
    page.goto(f"{BASE}/api/auth/me", wait_until="domcontentloaded", timeout=15000)
    for path, slug in SCENES:
        out = OUT / f"{slug}.png"
        try:
            page.goto(f"{BASE}{path}", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(6000)  # let charts / leaflet settle
            page.screenshot(path=str(out), type="png", full_page=False)
            kb = os.path.getsize(out) // 1024
            print(f"  ✓ {slug:20s} {kb:>5} KB  ← {path}")
        except Exception as e:
            print(f"  ✗ {slug:20s} {e}")
    browser.close()

print("done")
