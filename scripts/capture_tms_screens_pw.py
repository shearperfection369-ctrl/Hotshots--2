"""Capture each TMS page using Playwright with the system Chromium binary
(playwright browsers aren't downloaded; we use the local /usr/bin/chromium).

Saves PNGs into /tmp/tms_promo_v2/shots/{slug}.png — same layout as
build_promo_with_screens.py expects.

UPDATED v2: now captures every flagship page added in the v2 launch wave —
PowerBI, SharePoint, Specialty Carriers, Routing Guide, Microsoft Copilot,
Driver Registry, Trade Compliance, Supplier Sourcing, Arcade and more.
"""
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = os.environ.get("PROMO_BASE_URL", "https://clean-logistics-dash.preview.emergentagent.com")
TOKEN = os.environ.get("PROMO_SESSION_TOKEN", "test_session_admin_1")
OUT = Path("/tmp/tms_promo_v2/shots")
OUT.mkdir(parents=True, exist_ok=True)

# (URL path, slug) — slug is referenced by SCENES in build_promo_with_screens.py
SCENES = [
    ("/dashboard", "01_command"),
    ("/workbook", "02_booking"),
    ("/shipments", "03_shipments"),
    ("/tracking", "04_tracking"),
    ("/equipment", "05_equipment"),
    ("/carrier-rates", "06_rates"),
    ("/specialty-carriers", "07_specialty"),
    ("/routing-guide", "08_routing"),
    ("/documents", "09_documents"),
    ("/trade-compliance", "10_trade"),
    ("/suppliers", "11_suppliers"),
    ("/machines", "12_catalog"),
    ("/powerbi", "13_powerbi"),
    ("/sharepoint", "14_sharepoint"),
    ("/copilot", "15_copilot"),
    ("/reports", "16_reports"),
    ("/driver-registry", "17_driver_registry"),
    ("/arcade", "18_arcade"),
]


def main():
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
        # Warm-up navigation so cookie is sent before the first real load.
        try:
            page.goto(f"{BASE}/api/auth/me", wait_until="domcontentloaded", timeout=15000)
        except Exception:
            pass
        for path, slug in SCENES:
            out = OUT / f"{slug}.png"
            try:
                page.goto(f"{BASE}{path}", wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(6000)  # let charts / leaflet settle
                page.screenshot(path=str(out), type="png", full_page=False)
                kb = os.path.getsize(out) // 1024
                print(f"  OK {slug:25s} {kb:>5} KB  <- {path}")
            except Exception as e:
                print(f"  FAIL {slug:25s} {e}")
        browser.close()
    print("done")


if __name__ == "__main__":
    main()
