"""Re-record hunter, automatch, routeopt with improved choreography."""
import asyncio
import os
import shutil

from playwright.async_api import async_playwright

BASE = "https://clean-logistics-dash.preview.emergentagent.com"
OUT = "/app/demo_reel/raw"
VIEW = {"width": 1920, "height": 1080}


async def slow_scroll(page, px, steps=14, pause=70):
    for _ in range(steps):
        await page.mouse.wheel(0, px / steps)
        await page.wait_for_timeout(pause)


async def record(pw, name, path, actions):
    browser = await pw.chromium.launch(args=["--force-device-scale-factor=1"])
    ctx = await browser.new_context(viewport=VIEW, record_video_dir=f"{OUT}/{name}", record_video_size=VIEW)
    page = await ctx.new_page()
    try:
        await page.goto(f"{BASE}/login", wait_until="domcontentloaded")
        await page.evaluate("localStorage.setItem('tms_session_token','test_session_admin_1')")
        await page.goto(f"{BASE}{path}", wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(1500)
        await actions(page)
    except Exception as e:
        print(f"  ! {name}: {e}")
    video = page.video
    await ctx.close()
    await browser.close()
    shutil.move(await video.path(), f"{OUT}/{name}.webm")
    print(f"OK {name}.webm")


async def hunter(page):
    try:
        await page.click("text=Load Hunter", timeout=6000)
    except Exception:
        pass
    await page.wait_for_timeout(4000)
    try:
        cards = page.locator("[data-testid^='hunter-winner-']")
        if await cards.count() > 0:
            await cards.first.hover()
    except Exception:
        pass
    await page.wait_for_timeout(2500)
    await slow_scroll(page, 380)
    await page.wait_for_timeout(2500)
    await slow_scroll(page, 320)
    await page.wait_for_timeout(2500)


async def automatch(page):
    await page.wait_for_timeout(2500)
    for label in ["RATE SNAPSHOT", "COMPLIANCE", "LOYALTY", "AUTO-MATCH"]:
        try:
            await page.click(f"text={label}", timeout=4000)
            await page.wait_for_timeout(2600)
        except Exception:
            pass
    await page.wait_for_timeout(1500)


async def routeopt(page):
    inputs = page.locator("input[placeholder='City, ST or full address']")
    finds = page.locator("button:has-text('Find')")
    try:
        await inputs.nth(0).click()
        await inputs.nth(0).type("Minneapolis, MN", delay=40)
        await finds.nth(0).click(force=True)
        await page.wait_for_timeout(2500)
        await inputs.nth(1).click()
        await inputs.nth(1).type("Dallas, TX", delay=40)
        await finds.nth(1).click(force=True)
        await page.wait_for_timeout(2500)
        await page.click("[data-testid='ro-route-btn']", force=True)
        await page.wait_for_selector("[data-testid='ro-route-stats']", timeout=20000)
        await page.wait_for_timeout(2500)
        try:
            await page.fill("input[type='number'] >> nth=0", "2400")
        except Exception:
            pass
        await page.wait_for_timeout(3000)
    except Exception as e:
        print("  routeopt inner:", e)
    await page.wait_for_timeout(2500)


async def main():
    async with async_playwright() as pw:
        await record(pw, "hunter", "/brokerage", hunter)
        await record(pw, "automatch", "/margin-shield", automatch)
        await record(pw, "routeopt", "/route-optimizer", routeopt)


asyncio.run(main())
