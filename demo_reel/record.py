"""Record real module usage clips with Playwright (1080p webm per segment)."""
import asyncio
import os
import shutil

from playwright.async_api import async_playwright

BASE = "https://clean-logistics-dash.preview.emergentagent.com"
OUT = "/app/demo_reel/raw"
VIEW = {"width": 1920, "height": 1080}


async def slow_scroll(page, px, steps=18, pause=70):
    for _ in range(steps):
        await page.mouse.wheel(0, px / steps)
        await page.wait_for_timeout(pause)


async def record(pw, name, path, actions, token_key="tms_session_token", token="test_session_admin_1"):
    browser = await pw.chromium.launch(args=["--force-device-scale-factor=1"])
    ctx = await browser.new_context(viewport=VIEW, record_video_dir=f"{OUT}/{name}", record_video_size=VIEW)
    page = await ctx.new_page()
    try:
        await page.goto(f"{BASE}/login", wait_until="domcontentloaded")
        await page.evaluate(f"localStorage.setItem('{token_key}','{token}')")
        await page.goto(f"{BASE}{path}", wait_until="networkidle", timeout=45000)
        await page.wait_for_timeout(2500)
        await actions(page)
    except Exception as e:  # keep whatever footage we got
        print(f"  ! {name}: {e}")
    video = page.video
    await ctx.close()
    await browser.close()
    src = await video.path()
    shutil.move(src, f"{OUT}/{name}.webm")
    print(f"OK {name}.webm")


async def hunter(page):
    try:
        await page.click("text=Load Hunter", timeout=6000)
    except Exception:
        pass
    await page.wait_for_timeout(3000)
    await slow_scroll(page, 500)
    try:
        card = page.locator("[data-testid^='hunter-winner-']").first
        await card.hover()
    except Exception:
        pass
    await page.wait_for_timeout(2500)
    await slow_scroll(page, 400)
    await page.wait_for_timeout(2000)


async def automatch(page):
    await page.wait_for_timeout(1500)
    try:
        await page.fill("[data-testid='auto-match-load-id']", "", timeout=5000)
    except Exception:
        pass
    try:
        btn = page.locator("[data-testid='auto-match-run']")
        await btn.hover()
        await page.wait_for_timeout(600)
        await btn.click(force=True)
        await page.wait_for_timeout(4500)
    except Exception:
        pass
    await slow_scroll(page, 450)
    await page.wait_for_timeout(2500)


async def liveops(page):
    await page.wait_for_timeout(5000)
    await page.mouse.move(960, 500)
    await slow_scroll(page, 300, steps=10)
    await page.wait_for_timeout(3000)
    await slow_scroll(page, -300, steps=10)
    await page.wait_for_timeout(2500)


async def routeopt(page):
    inputs = page.locator("input[placeholder='City, ST or full address']")
    try:
        await inputs.nth(0).click()
        await inputs.nth(0).type("Minneapolis, MN", delay=45)
        await page.wait_for_timeout(500)
        await inputs.nth(1).click()
        await inputs.nth(1).type("Dallas, TX", delay=45)
        await page.wait_for_timeout(600)
        await page.click("[data-testid='ro-route-btn']", force=True)
        await page.wait_for_timeout(9000)
        await slow_scroll(page, 450)
    except Exception as e:
        print("  routeopt inner:", e)
    await page.wait_for_timeout(3000)


async def sandbox(page):
    await page.wait_for_timeout(2000)
    try:
        launch = page.locator("[data-testid='sim-launch-btn']")
        if await launch.count() > 0:
            await launch.click(force=True)
            await page.wait_for_timeout(9000)
    except Exception:
        pass
    await slow_scroll(page, 600)
    await page.wait_for_timeout(3000)
    await slow_scroll(page, 500)
    await page.wait_for_timeout(2500)


async def whitelabel(page):
    await page.wait_for_timeout(3000)
    await slow_scroll(page, 350)
    await page.wait_for_timeout(1800)
    try:
        await page.click("[data-testid='tenant-nav-loads']", force=True)
        await page.wait_for_timeout(2800)
        await page.click("[data-testid='tenant-nav-settings']", force=True)
        await page.wait_for_timeout(3000)
    except Exception:
        pass
    await page.wait_for_timeout(1500)


async def main():
    os.makedirs(OUT, exist_ok=True)
    async with async_playwright() as pw:
        await record(pw, "hunter", "/brokerage", hunter)
        await record(pw, "automatch", "/margin-shield", automatch)
        await record(pw, "liveops", "/live-ops", liveops)
        await record(pw, "routeopt", "/route-optimizer", routeopt)
        await record(pw, "sandbox", "/sandbox", sandbox)
        await record(pw, "whitelabel", "/t/acme-freight-co/app", whitelabel,
                     token_key="hs_token_acme-freight-co", token=os.environ["ACME_TOKEN"])


asyncio.run(main())
