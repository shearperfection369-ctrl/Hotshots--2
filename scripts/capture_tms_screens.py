"""Capture screenshots of every key TMS page in the preview environment, then
hand them off as ingredients for the next promo-video rebuild. Saves to
/tmp/tms_screens/*.png  (1920x1080 jpegs).
"""
import asyncio
import os
from pathlib import Path
from playwright.async_api import async_playwright

OUT = Path("/tmp/tms_screens")
OUT.mkdir(exist_ok=True)
BASE = "https://clean-logistics-dash.preview.emergentagent.com"
TOKEN = "test_session_admin_1"

# Pages worth showcasing in the promo cinematic. Each tuple is (path, slug).
PAGES = [
    ("/dashboard", "01_command"),
    ("/shipments", "02_shipments"),
    ("/workbook", "03_booking_sheet"),
    ("/documents", "04_documents"),
    ("/trade-compliance", "05_trade"),
    ("/equipment", "06_equipment"),
    ("/machines", "07_machines"),
    ("/carrier-rates", "08_carrier_rates"),
]


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": 1920, "height": 1080})
        # Pre-set the auth cookie at the apex domain so all subdomains see it
        await ctx.add_cookies([{
            "name": "session_token", "value": TOKEN,
            "domain": ".preview.emergentagent.com",
            "path": "/", "secure": True, "sameSite": "None",
        }])
        page = await ctx.new_page()
        for path, slug in PAGES:
            url = f"{BASE}{path}"
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(5000)  # let charts / leaflet settle
                out = OUT / f"{slug}.png"
                await page.screenshot(path=str(out), full_page=False, type="png")
                size = os.path.getsize(out)
                print(f"  ✓ {slug:20s}  {size//1024} KB  {path}")
            except Exception as e:
                print(f"  ✗ {slug:20s}  {e}")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
