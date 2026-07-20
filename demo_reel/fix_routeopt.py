"""Fix: re-record routeopt only — clicks geocode candidates (root cause of the old timeout)."""
import asyncio
import shutil

from playwright.async_api import async_playwright

BASE = "https://clean-logistics-dash.preview.emergentagent.com"
OUT = "/app/demo_reel/raw"
VIEW = {"width": 1920, "height": 1080}


async def slow_scroll(page, px, steps=14, pause=70):
    for _ in range(steps):
        await page.mouse.wheel(0, px / steps)
        await page.wait_for_timeout(pause)


async def pick(page, prefix, text):
    inp = page.locator(f"[data-testid='{prefix}-input']")
    await inp.click()
    await inp.type(text, delay=45)
    await page.click(f"[data-testid='{prefix}-search-btn']", force=True)
    await page.wait_for_selector(f"[data-testid='{prefix}-candidate-0']", timeout=15000)
    await page.wait_for_timeout(900)
    await page.click(f"[data-testid='{prefix}-candidate-0']", force=True)
    await page.wait_for_timeout(1000)


async def routeopt(page):
    await pick(page, "ro-origin", "Minneapolis, MN")
    await pick(page, "ro-dest", "Dallas, TX")
    await page.click("[data-testid='ro-route-btn']", force=True)
    await page.wait_for_selector("[data-testid='ro-route-stats']", timeout=30000)
    await page.wait_for_timeout(3000)
    try:
        rate = page.locator("input[type='number']").first
        await rate.click()
        await rate.fill("2400")
        await page.wait_for_timeout(2500)
    except Exception as e:
        print("  rate fill:", e)
    await slow_scroll(page, 420)
    await page.wait_for_timeout(3000)
    await slow_scroll(page, -300, steps=10)
    await page.wait_for_timeout(2500)


async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(args=["--force-device-scale-factor=1"])
        ctx = await browser.new_context(viewport=VIEW, record_video_dir=f"{OUT}/routeopt", record_video_size=VIEW)
        page = await ctx.new_page()
        try:
            await page.goto(f"{BASE}/login", wait_until="domcontentloaded")
            await page.evaluate("localStorage.setItem('tms_session_token','test_session_admin_1')")
            await page.goto(f"{BASE}/route-optimizer", wait_until="networkidle", timeout=60000)
            await page.wait_for_timeout(2000)
            await routeopt(page)
            print("choreography complete")
        except Exception as e:
            print(f"  ! routeopt: {e}")
        video = page.video
        await ctx.close()
        await browser.close()
        shutil.move(await video.path(), f"{OUT}/routeopt.webm")
        print("OK routeopt.webm")


asyncio.run(main())
