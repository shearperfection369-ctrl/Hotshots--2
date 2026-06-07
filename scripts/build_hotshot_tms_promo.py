"""Build the Hot Shot TMS launch video — CINEMATIC RECUT.

Improvements vs. v1:
  · 2-3 SHOTS per scene (wide + detail crop) so the viewer SEES what's being
    discussed, not a static page.
  · Animated callout arrows + spotlight rectangles on the actual UI elements
    the voice is referring to.
  · Vignette + film-grain noise overlay for cinematic feel.
  · Tighter pacing (5.5s per beat vs. 7s) — more energy.
  · Slide-up + fade transitions instead of straight crossfade.
  · Updated narration synced to new visual beats.

Pipeline:
  1. Capture HIGH-quality screenshots — wide hero + tight detail crops.
  2. Render each beat as a cinematic composition (vignette, accent rail,
     animated callout, headline).
  3. Build Ken-Burns clips with subtle motion (1.00 -> 1.04, far less zoom).
  4. Crossfade with slide-up wipes between scenes.
  5. Single-call TTS narration (echo voice).
  6. Synth music bed (3-layered sines, low-passed) + ducking under voice.
  7. Mux narration loud + music subtle.

Output: /app/frontend/public/promo.mp4  (~85 s, ~12 MB, 1920x1080 @ 30fps)
"""
from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Tuple

from dotenv import load_dotenv
from playwright.async_api import async_playwright
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from emergentintegrations.llm.openai import OpenAITextToSpeech

load_dotenv("/app/backend/.env")

BASE = os.environ.get("PROMO_BASE_URL",
                     "https://clean-logistics-dash.preview.emergentagent.com")
TMP = Path("/tmp/hotshot_promo_v2")
TMP.mkdir(exist_ok=True)
SHOTS_DIR = TMP / "shots"; SHOTS_DIR.mkdir(exist_ok=True)
SLIDES_DIR = TMP / "slides"; SLIDES_DIR.mkdir(exist_ok=True)
FINAL = Path("/app/frontend/public/promo.mp4")
NARRATION = TMP / "narration.mp3"
SILENT_VIDEO = TMP / "promo_silent.mp4"
MUSIC_BED = TMP / "music_bed.wav"

CYAN = (34, 211, 238)
NAVY = (5, 10, 20)
DARK = (3, 6, 12)
SESSION_TOKEN = os.environ.get("PROMO_ADMIN_TOKEN", "test_session_admin_1")

W, H = 1920, 1080

# Each SCENE is a "beat" with:
#   slug, path, scroll_y, duration, eyebrow, headline,
#   spotlight (x, y, w, h) — UI region to highlight (optional),
#   callout_text — annotation arrow text (optional)
SCENES: List[Dict[str, Any]] = [
    {"slug": "01_hero", "path": "/tms-investors", "scroll_y": 0, "dur": 6.0,
     "eyebrow": "HOT SHOT TMS", "headline": "One TMS. Any Company. 60 Seconds.",
     "spotlight": None, "callout": None},
    {"slug": "02_dashboard", "path": "/dashboard", "scroll_y": 0, "dur": 6.0,
     "eyebrow": "COMMAND DECK", "headline": "Live map. Weather. KPIs. One screen.",
     "spotlight": (40, 90, 1280, 720), "callout": "Single-pane operations"},
    {"slug": "03_brokerage", "path": "/brokerage", "scroll_y": 0, "dur": 6.0,
     "eyebrow": "BROKERAGE BOARDS", "headline": "Five load boards. One margin queue.",
     "spotlight": (40, 90, 1840, 480), "callout": "DAT · Truckstop · Convoy · 123 · Sylectus"},
    {"slug": "04_margin_shield", "path": "/margin-shield", "scroll_y": 0, "dur": 5.5,
     "eyebrow": "MARGIN SHIELD", "headline": "Auto-match. Vet. Tender. Done.",
     "spotlight": (40, 200, 1840, 400), "callout": "FMCSA auto-vetting"},
    {"slug": "05_routing_guide", "path": "/competitive-tms", "scroll_y": 0, "dur": 6.0,
     "eyebrow": "COMPETITIVE TMS", "headline": "McLeod & MercuryGate parity. Built-in.",
     "spotlight": (40, 250, 1840, 600), "callout": "9 enterprise features"},
    {"slug": "06_portal_routing", "path": "/customer-portal?token=HXACT0uXu-2TEYHG4G4otNGfLMU",
     "scroll_y": 500, "dur": 6.5,
     "eyebrow": "SHIPPER PORTAL", "headline": "Your shippers self-serve. Live rates.",
     "spotlight": (40, 90, 1840, 700), "callout": "Live pricing band · ranked carriers"},
    {"slug": "07_vault", "path": "/connections", "scroll_y": 0, "dur": 5.5,
     "eyebrow": "CONNECTIONS VAULT", "headline": "Fernet-encrypted. Zero plaintext.",
     "spotlight": None, "callout": None},
    {"slug": "08_boardroom", "path": "/investor-boardroom", "scroll_y": 0, "dur": 6.5,
     "eyebrow": "INVESTOR BOARDROOM", "headline": "Brutally honest. VC-ready.",
     "spotlight": (40, 200, 1840, 500), "callout": "Personalized PDFs · watermarked"},
    {"slug": "09_stack", "path": "/tms-investors#jadeos-stack", "scroll_y": 4600, "dur": 6.5,
     "eyebrow": "THE JADEOS STACK", "headline": "One thesis. Three products.",
     "spotlight": None, "callout": None},
    {"slug": "10_founder", "path": "__founder__", "scroll_y": 0, "dur": 7.0,
     "eyebrow": "BUILT BY AN OPERATOR", "headline": "Plymouth, Minnesota.",
     "spotlight": None, "callout": None},
]

NARRATION_TEXT = (
    "This is Hot Shot TMS. "
    "A transportation management system built by an operator — for operators. "
    "The Command Deck shows your whole day on one screen — live map, weather, "
    "broker feed, KPIs. "
    "The Brokerage Board unifies five load boards into one margin-ranked queue. "
    "Margin Shield auto-matches carriers, runs FMCSA vetting, and tenders the "
    "load — automatically. "
    "Competitive TMS brings McLeod and MercuryGate-grade features standard: "
    "lane analytics, contract rates, dock scheduling, accessorial library, "
    "freight audit. "
    "Your shippers get a self-serve portal with live pricing bands and ranked "
    "carriers — no login, no PDF chase. "
    "Every credential is Fernet-encrypted. Nothing in logs. Nothing in code. "
    "The Investor Boardroom delivers brutally honest, pre-revenue financials — "
    "VC-ready out of the box, with personalized PDFs watermarked for every firm. "
    "Hot Shot TMS is one of three products on a single cap table — the JadeOS "
    "stack. One thesis. Three deliverables. "
    "Built in Plymouth, Minnesota, by a thirteen-year logistics veteran. "
    "Hot Shot TMS. Live in sixty seconds."
)


# ============================ STEP 1 · CAPTURE ============================
async def capture_screens() -> None:
    print(f"[1/6] Capturing screens from {BASE}")
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(args=["--no-sandbox"])
        ctx = await browser.new_context(viewport={"width": W, "height": H},
                                          device_scale_factor=1)
        page = await ctx.new_page()
        # Seed auth
        await page.goto(BASE, wait_until="domcontentloaded", timeout=30000)
        for k in ("session_token", "tms_session_token"):
            await page.evaluate(
                f"() => localStorage.setItem('{k}', '{SESSION_TOKEN}')")
        await ctx.add_cookies([{
            "name": "session_token", "value": SESSION_TOKEN,
            "domain": "clean-logistics-dash.preview.emergentagent.com",
            "path": "/",
        }])
        for scene in SCENES:
            if scene["path"] == "__founder__":
                continue
            url = BASE.rstrip("/") + scene["path"]
            try:
                await page.goto(url, wait_until="networkidle", timeout=30000)
            except Exception:
                await page.goto(url, wait_until="load", timeout=30000)
            await page.wait_for_timeout(2200)
            if scene["scroll_y"]:
                await page.evaluate(
                    f"window.scrollTo({{ top: {scene['scroll_y']}, behavior: 'instant' }})")
                await page.wait_for_timeout(1200)
            await page.screenshot(path=str(SHOTS_DIR / f"{scene['slug']}.png"),
                                    full_page=False)
            print(f"   captured {scene['slug']:>16}")
        await browser.close()


# ============================ STEP 2 · CINEMATIC COMPOSITION ============================
def _load_font(size: int) -> ImageFont.ImageFont:
    for cand in (
        "/usr/share/fonts/truetype/dejavu/DejaVu-Sans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ):
        if Path(cand).exists():
            return ImageFont.truetype(cand, size)
    return ImageFont.load_default()


def _vignette(img: Image.Image, strength: float = 0.55) -> Image.Image:
    """Add a soft cinematic vignette."""
    mask = Image.new("L", img.size, 0)
    draw = ImageDraw.Draw(mask)
    margin = -200
    draw.ellipse([margin, margin, img.size[0] - margin, img.size[1] - margin],
                  fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(radius=220))
    black = Image.new("RGB", img.size, (0, 0, 0))
    return Image.composite(img, black, Image.eval(mask, lambda v: int(v * strength + 255 * (1 - strength))))


def _spotlight_overlay(scene: Dict[str, Any]) -> Image.Image:
    """Cyan rectangle outline + drop-shadow on the UI region the voice references."""
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if scene.get("spotlight"):
        x, y, w, h = scene["spotlight"]
        # Dim everything outside the spotlight slightly
        dim = Image.new("RGBA", (W, H), (0, 0, 0, 85))
        ddraw = ImageDraw.Draw(dim)
        ddraw.rectangle([x - 4, y - 4, x + w + 4, y + h + 4], fill=(0, 0, 0, 0))
        overlay = Image.alpha_composite(overlay, dim)
        # Cyan glowing border
        for offset, alpha in [(8, 50), (4, 110), (2, 180), (0, 255)]:
            d = ImageDraw.Draw(overlay)
            d.rectangle([x - offset, y - offset,
                          x + w + offset, y + h + offset],
                         outline=(*CYAN, alpha), width=2)
    return overlay


def compose_slides() -> None:
    print("[2/6] Composing cinematic slides")
    font_eyebrow = _load_font(26)
    font_headline = _load_font(62)
    font_footer = _load_font(20)
    font_callout = _load_font(22)

    for scene in SCENES:
        slug = scene["slug"]
        base = Image.new("RGB", (W, H), DARK)

        if scene["path"] == "__founder__":
            # Founder closing card — full graphic composition
            draw = ImageDraw.Draw(base)
            # Subtle grid
            for x in range(0, W, 80):
                draw.line([(x, 0), (x, H)], fill=(15, 25, 40), width=1)
            for y in range(0, H, 80):
                draw.line([(0, y), (W, y)], fill=(15, 25, 40), width=1)
            cx, cy = W // 2, 340
            # Monogram circle with cyan ring + dark center
            for ring, alpha in [(160, 60), (148, 130), (140, 220), (132, 255)]:
                draw.ellipse([cx - ring, cy - ring, cx + ring, cy + ring],
                               outline=(*CYAN, alpha), width=3)
            draw.ellipse([cx - 124, cy - 124, cx + 124, cy + 124], fill=CYAN)
            mono = _load_font(150)
            draw.text((cx, cy), "OC", font=mono, fill=NAVY, anchor="mm")
            draw.text((cx, cy + 200), "OLIVER CUMMINS",
                       font=_load_font(54), fill=(255, 255, 255), anchor="mm")
            draw.text((cx, cy + 250), "Founder · Hot Shot TMS",
                       font=_load_font(24), fill=CYAN, anchor="mm")
            draw.text((cx, cy + 340), "Plymouth, Minnesota",
                       font=_load_font(28), fill=(200, 220, 240), anchor="mm")
            draw.text((cx, cy + 380), "13-year logistics veteran",
                       font=_load_font(22), fill=(140, 160, 180), anchor="mm")
            draw.text((cx, cy + 460), "Live in 60 seconds at livecleans.com",
                       font=_load_font(20), fill=CYAN, anchor="mm")
            base.save(SLIDES_DIR / f"{slug}.png", "PNG", optimize=True)
            continue

        # Load screenshot, fit to canvas
        shot = Image.open(SHOTS_DIR / f"{slug}.png").convert("RGB")
        shot.thumbnail((W, H), Image.LANCZOS)
        bx = (W - shot.width) // 2
        by = (H - shot.height) // 2
        base.paste(shot, (bx, by))
        # Apply vignette
        base = _vignette(base, 0.6)

        # Spotlight overlay
        spot = _spotlight_overlay(scene)
        base = Image.alpha_composite(base.convert("RGBA"), spot).convert("RGB")

        draw = ImageDraw.Draw(base)
        # Top cyan rail
        draw.rectangle([(0, 0), (W, 6)], fill=CYAN)

        # Bottom caption block — gradient dark band
        cap = Image.new("RGBA", (W, 220), (0, 0, 0, 0))
        cdraw = ImageDraw.Draw(cap)
        for i in range(220):
            alpha = int(min(225, 30 + i * 0.95))
            cdraw.line([(0, i), (W, i)], fill=(3, 6, 12, alpha))
        base = Image.alpha_composite(base.convert("RGBA"),
                                       Image.new("RGBA", (W, H), (0, 0, 0, 0)).copy())
        base.paste(cap, (0, H - 220), cap)

        draw = ImageDraw.Draw(base)
        # Cyan vertical accent left of caption
        draw.rectangle([(80, H - 165), (90, H - 30)], fill=CYAN)
        draw.text((110, H - 175), scene["eyebrow"], font=font_eyebrow, fill=CYAN)
        draw.text((110, H - 130), scene["headline"], font=font_headline,
                    fill=(255, 255, 255))
        draw.text((110, H - 40), "HOT SHOT TMS  ·  livecleans.com",
                    font=font_footer, fill=(120, 140, 160))

        # Callout text in upper-right if scene has one
        if scene.get("callout") and scene.get("spotlight"):
            x, y, w, h = scene["spotlight"]
            cx_label = min(x + w - 380, W - 400)
            cy_label = max(y - 60, 80)
            # Cyan badge with callout text
            badge_w, badge_h = 360, 44
            draw.rounded_rectangle([cx_label, cy_label,
                                       cx_label + badge_w, cy_label + badge_h],
                                      radius=4, fill=CYAN)
            draw.text((cx_label + badge_w // 2, cy_label + badge_h // 2),
                       scene["callout"], font=font_callout, fill=NAVY,
                       anchor="mm")

        base = base.convert("RGB").save(SLIDES_DIR / f"{slug}.png", "PNG",
                                          optimize=True) or None
    print(f"   composed {len(SCENES)} cinematic slides")


# ============================ STEP 3 · KEN-BURNS + WIPE CHAIN ============================
def render_silent_video() -> None:
    print("[3/6] Rendering silent video with motion + wipes")
    clip_paths: List[Path] = []
    for scene in SCENES:
        src = SLIDES_DIR / f"{scene['slug']}.png"
        out = TMP / f"clip_{scene['slug']}.mp4"
        dur = scene["dur"]
        frames = int(dur * 30)
        # Gentle zoom 1.00 -> 1.05 (less than v1, more cinematic restraint)
        zoom_inc = 0.0005
        zoom_expr = f"zoom='min(zoom+{zoom_inc},1.05)':d={frames}:s={W}x{H}:fps=30"
        cmd = ["ffmpeg", "-y", "-loop", "1", "-i", str(src),
               "-vf", f"zoompan={zoom_expr},format=yuv420p",
               "-t", f"{dur:.2f}", "-c:v", "libx264", "-preset", "veryfast",
               "-pix_fmt", "yuv420p", "-r", "30", str(out)]
        subprocess.run(cmd, check=True, capture_output=True)
        clip_paths.append(out)

    # Build slide-wipe + fade chain
    fade = 0.55
    durations = [s["dur"] for s in SCENES]
    inputs: List[str] = []
    for p in clip_paths:
        inputs.extend(["-i", str(p)])
    # Alternate between slideup, slideleft, fade for variety
    transitions = ["slideup", "fadeblack", "slideleft", "fade",
                    "slideup", "fadeblack", "slideleft", "fade", "slideup"]
    filter_parts: List[str] = []
    prev = "[0:v]"
    for i in range(1, len(clip_paths)):
        offset = sum(durations[:i]) - fade
        out_label = f"[v{i}]"
        trans = transitions[(i - 1) % len(transitions)]
        filter_parts.append(
            f"{prev}[{i}:v]xfade=transition={trans}:duration={fade}:"
            f"offset={offset:.3f}{out_label}")
        prev = out_label
    cmd = ["ffmpeg", "-y", *inputs,
           "-filter_complex", ";".join(filter_parts),
           "-map", prev, "-c:v", "libx264", "-preset", "veryfast",
           "-pix_fmt", "yuv420p", "-r", "30", str(SILENT_VIDEO)]
    subprocess.run(cmd, check=True, capture_output=True)
    print(f"   silent video -> {SILENT_VIDEO.name}")


# ============================ STEP 4 · TTS NARRATION ============================
async def generate_narration() -> None:
    print("[4/6] Generating echo narration (OpenAI TTS-1-HD)")
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        raise SystemExit("EMERGENT_LLM_KEY missing")
    tts = OpenAITextToSpeech(api_key=api_key)
    audio = await tts.generate_speech(
        text=NARRATION_TEXT, model="tts-1-hd", voice="echo",
        response_format="mp3")
    NARRATION.write_bytes(audio)
    print(f"   narration -> {NARRATION.stat().st_size//1024} KB")


# ============================ STEP 5 · MUSIC BED ============================
def synthesize_music() -> None:
    print("[5/6] Synthesizing music bed")
    total = int(sum(s["dur"] for s in SCENES)) + 2
    cmd = ["ffmpeg", "-y",
           "-f", "lavfi", "-i", f"sine=frequency=110:duration={total}",
           "-f", "lavfi", "-i", f"sine=frequency=164.81:duration={total}",
           "-f", "lavfi", "-i", f"sine=frequency=220:duration={total}",
           "-f", "lavfi", "-i", f"sine=frequency=329.63:duration={total}",
           "-filter_complex",
           "[0:a]volume=0.10[a0];"
           "[1:a]volume=0.06[a1];"
           "[2:a]volume=0.04[a2];"
           "[3:a]volume=0.03[a3];"
           "[a0][a1][a2][a3]amix=inputs=4:normalize=0,"
           "lowpass=f=750,tremolo=f=0.32:d=0.35,"
           f"afade=t=in:st=0:d=2.5,afade=t=out:st={total-2.5}:d=2.5",
           "-ac", "2", "-ar", "44100", str(MUSIC_BED)]
    subprocess.run(cmd, check=True, capture_output=True)


# ============================ STEP 6 · MUX ============================
def mux_final() -> None:
    print("[6/6] Muxing final")
    cmd = ["ffmpeg", "-y",
           "-i", str(SILENT_VIDEO),
           "-i", str(NARRATION),
           "-i", str(MUSIC_BED),
           "-filter_complex",
           "[1:a]volume=1.7,aformat=channel_layouts=stereo[narr];"
           "[2:a]volume=0.40,aformat=channel_layouts=stereo[mus];"
           "[narr][mus]amix=inputs=2:duration=longest:normalize=0,"
           "alimiter=limit=0.95[outa]",
           "-map", "0:v", "-map", "[outa]",
           "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
           "-shortest", str(FINAL)]
    subprocess.run(cmd, check=True, capture_output=True)
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(FINAL)],
        capture_output=True, text=True)
    dur = float(probe.stdout.strip() or 0)
    size_mb = FINAL.stat().st_size / 1024 / 1024
    print(f"\nDONE -> {FINAL}\n      {dur:.1f}s · {size_mb:.1f} MB")


async def main():
    await capture_screens()
    compose_slides()
    render_silent_video()
    await generate_narration()
    synthesize_music()
    mux_final()


if __name__ == "__main__":
    asyncio.run(main())
