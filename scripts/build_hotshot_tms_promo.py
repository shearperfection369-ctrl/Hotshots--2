"""Build the Hot Shot TMS launch video — real-screen demo cut.

Pipeline:
  1. Capture HIGH-quality screenshots of every flagship Hot Shot TMS module
     via Playwright (1920x1080) — public + admin views with localStorage auth.
  2. Render each scene with a Ken-Burns zoom + brand-cyan accent bar + headline.
  3. Crossfade scenes with ffmpeg xfade.
  4. Generate echo-voice narration MP3 via OpenAI TTS-1-HD (Emergent universal
     key, single call so it sounds coherent — well under the 4096-char cap).
  5. Synthesize a subtle synth-pulse music bed (ffmpeg sine + filters, no
     external download — keeps the script firewall-safe).
  6. Mux narration (loud) + music (quiet) under the video.
  7. Write final MP4 → /app/frontend/public/promo.mp4 (overwrites existing).

Run: python3 /app/scripts/build_hotshot_tms_promo.py

Output: /app/frontend/public/promo.mp4  (~75 s, ~10 MB, 1920x1080 @ 30fps)
"""
from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
from pathlib import Path
from typing import List, Tuple

from dotenv import load_dotenv
from playwright.async_api import async_playwright
from PIL import Image, ImageDraw, ImageFont
from emergentintegrations.llm.openai import OpenAITextToSpeech

load_dotenv("/app/backend/.env")

BASE = os.environ.get("PROMO_BASE_URL",
                     "https://clean-logistics-dash.preview.emergentagent.com")
TMP = Path("/tmp/hotshot_promo")
TMP.mkdir(exist_ok=True)
SHOTS_DIR = TMP / "shots"
SHOTS_DIR.mkdir(exist_ok=True)
SLIDES_DIR = TMP / "slides"
SLIDES_DIR.mkdir(exist_ok=True)
FINAL = Path("/app/frontend/public/promo.mp4")
NARRATION = TMP / "narration.mp3"
SILENT_VIDEO = TMP / "promo_silent.mp4"
MUSIC_BED = TMP / "music_bed.wav"
MIXED_AUDIO = TMP / "mixed_audio.aac"

CYAN = (34, 211, 238)
NAVY = (5, 10, 20)


# (url_path, slug, eyebrow, headline, scroll_y, duration_s)
SCENES: List[Tuple[str, str, str, str, int, float]] = [
    # Open with the public investor page hero (most polished frame)
    ("/tms-investors",       "01_hero",       "HOT SHOT TMS",
     "One TMS. Any Company. 60 Seconds to Skin.",        0,   7.0),
    # Show the brand reel actively re-theming
    ("/tms-investors#changeability", "02_changeability", "CHANGEABILITY",
     "Watch the app re-theme itself in real time.",      1400, 7.0),
    # Plug-and-play vault
    ("/tms-investors#plug-and-play", "03_plug",       "PLUG & PLAY",
     "9 ERPs. 14 integrations. Two clicks.",             2400, 7.0),
    # Admin Command Deck
    ("/dashboard",           "04_command",    "COMMAND DECK",
     "Live map. Weather. KPIs. One screen.",             0,   7.0),
    # Admin Booked Loads / Brokerage
    ("/brokerage",           "05_brokerage",  "BROKERAGE BOARDS",
     "Five load boards. One unified margin queue.",      0,   7.0),
    # Connections Vault (Fernet-encrypted creds)
    ("/connections",         "06_vault",      "CONNECTIONS VAULT",
     "Fernet-encrypted. Zero plaintext in logs.",        0,   6.0),
    # Investor Boardroom
    ("/investor-boardroom",  "07_boardroom",  "INVESTOR BOARDROOM",
     "Brutally honest pre-revenue financials. VC-ready.", 0,  7.0),
    # Personalized invite-link gate
    ("/investor-invite-links","08_invite",    "ONE-TIME LINKS",
     "Personalized URLs. Watermarked PDFs. Full audit.",  0,  6.0),
    # Founder closing card (rendered, not screenshot)
    ("__founder__",          "09_founder",    "BUILT BY AN OPERATOR",
     "Plymouth, Minnesota · 13-year logistics veteran.",  0,  8.0),
]

# Single narration block (~75s) — falls under the 4096-char TTS cap.
NARRATION_TEXT = (
    "This is Hot Shot TMS. "
    "The first Transportation Management System that re-themes itself "
    "for any company in 60 seconds. "
    "Type the name of the prospect's business. "
    "Watch the entire app — colors, sample data, suppliers, lanes, document "
    "headers — reshape around them, live, during the sales call. "
    "Plug-and-play: nine ERP connectors and fourteen launch-day integrations "
    "are pre-wired in a Fernet-encrypted credentials vault. Two clicks to "
    "go live. "
    "Inside, the Command Deck shows the whole day on one screen — live map, "
    "weather radar, KPIs, broker feed. "
    "The Brokerage Board unifies five load boards into one margin-ranked "
    "queue. "
    "The Investor Boardroom delivers brutally honest, pre-revenue "
    "financials — VC-ready out of the box. "
    "And every PDF you send to an investor is watermarked, audit-logged, and "
    "personalized for that firm. "
    "Built in Plymouth, Minnesota, by a thirteen-year logistics veteran. "
    "Hot Shot TMS — one platform. Any company. Live in sixty seconds."
)

# Optional admin session token for protected routes (test creds)
SESSION_TOKEN = os.environ.get("PROMO_ADMIN_TOKEN", "test_session_admin_1")

# ------------ STEP 1 · PLAYWRIGHT CAPTURE ------------
async def capture_screens() -> None:
    print(f"[1/6] Capturing screens from {BASE}")
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(args=["--no-sandbox"])
        ctx = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            device_scale_factor=1,
        )
        page = await ctx.new_page()
        # Seed auth via localStorage by visiting the root first
        await page.goto(BASE, wait_until="domcontentloaded", timeout=30000)
        await page.evaluate(
            f"() => localStorage.setItem('session_token', '{SESSION_TOKEN}')")
        for path, slug, *_rest, scroll_y, _dur in [(s[0], s[1], 0, 0, s[4], s[5]) for s in SCENES]:
            if path == "__founder__":
                continue  # founder card is rendered, not screenshotted
            out = SHOTS_DIR / f"{slug}.png"
            url = BASE.rstrip("/") + path
            try:
                await page.goto(url, wait_until="networkidle", timeout=30000)
            except Exception:
                # Some pages do background polling — fall back to load
                await page.goto(url, wait_until="load", timeout=30000)
            await page.wait_for_timeout(1800)
            if scroll_y:
                await page.evaluate(f"window.scrollTo({{ top: {scroll_y}, behavior: 'instant' }})")
                await page.wait_for_timeout(1200)
            await page.screenshot(path=str(out), full_page=False)
            print(f"   captured {slug:>14}  ->  {out.name}")
        await browser.close()


# ------------ STEP 2 · COMPOSE BRANDED SLIDES ------------
def _load_font(size: int) -> ImageFont.ImageFont:
    for cand in (
        "/usr/share/fonts/truetype/dejavu/DejaVu-Sans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    ):
        if Path(cand).exists():
            return ImageFont.truetype(cand, size)
    return ImageFont.load_default()


def compose_slides() -> None:
    print("[2/6] Composing branded slides")
    font_eyebrow = _load_font(22)
    font_headline = _load_font(58)
    font_footer = _load_font(20)
    for path, slug, eyebrow, headline, *_rest in SCENES:
        slide = Image.new("RGB", (1920, 1080), NAVY)
        if path == "__founder__":
            # Render solid navy founder card with monogram + body
            draw = ImageDraw.Draw(slide)
            cx, cy = 960, 380
            # Monogram circle
            r = 130
            draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)], fill=CYAN)
            mono_font = _load_font(140)
            draw.text((cx, cy), "OC", font=mono_font, fill=NAVY, anchor="mm")
            draw.text((cx, cy + r + 60), "Oliver Cummins", font=_load_font(46),
                      fill=(255, 255, 255), anchor="mm")
            draw.text((cx, cy + r + 110), "Founder · Hot Shot TMS",
                      font=_load_font(22), fill=CYAN, anchor="mm")
            draw.text((cx, cy + r + 200), "Plymouth, Minnesota · 13-year logistics veteran",
                      font=_load_font(28), fill=(180, 200, 220), anchor="mm")
            draw.text((cx, cy + r + 260), "shearperfection369@gmail.com",
                      font=_load_font(22), fill=(120, 140, 160), anchor="mm")
        else:
            shot = Image.open(SHOTS_DIR / f"{slug}.png").convert("RGB")
            # Resize / crop preserving aspect to 1920x1080
            shot.thumbnail((1920, 1080), Image.LANCZOS)
            # Center on canvas
            bx = (1920 - shot.width) // 2
            by = (1080 - shot.height) // 2
            slide.paste(shot, (bx, by))
            # Brand accent: cyan top bar + bottom gradient strip
            draw = ImageDraw.Draw(slide)
            draw.rectangle([(0, 0), (1920, 6)], fill=CYAN)
            # Semi-opaque caption block bottom-left
            overlay = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
            ov = ImageDraw.Draw(overlay)
            ov.rectangle([(0, 920), (1920, 1080)], fill=(5, 10, 20, 215))
            ov.rectangle([(80, 940), (90, 1060)], fill=(*CYAN, 255))
            slide = Image.alpha_composite(slide.convert("RGBA"), overlay).convert("RGB")
            draw = ImageDraw.Draw(slide)
            draw.text((110, 950), eyebrow.upper(), font=font_eyebrow, fill=CYAN)
            draw.text((110, 985), headline, font=font_headline, fill=(255, 255, 255))
            draw.text((110, 1055), "HOT SHOT TMS · livecleans.com",
                      font=font_footer, fill=(120, 140, 160))
        slide.save(SLIDES_DIR / f"{slug}.png", "PNG", optimize=True)
    print(f"   composed {len(SCENES)} slides")


# ------------ STEP 3 · BUILD KEN-BURNS CLIPS + XFADE ------------
def render_silent_video() -> None:
    print("[3/6] Rendering silent video with Ken-Burns + xfade")
    clip_paths: List[Path] = []
    for path, slug, *_rest, _scroll, dur in SCENES:
        src = SLIDES_DIR / f"{slug}.png"
        out = TMP / f"clip_{slug}.mp4"
        # Slow Ken-Burns zoom from 1.00x to 1.08x over the duration
        frames = int(dur * 30)
        zoom_expr = f"zoom='min(zoom+0.0008,1.08)':d={frames}:s=1920x1080:fps=30"
        cmd = [
            "ffmpeg", "-y", "-loop", "1", "-i", str(src),
            "-vf", f"zoompan={zoom_expr},format=yuv420p",
            "-t", f"{dur:.2f}", "-c:v", "libx264", "-preset", "veryfast",
            "-pix_fmt", "yuv420p", "-r", "30", str(out),
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        clip_paths.append(out)

    # Crossfade chain
    fade = 0.6  # crossfade seconds
    durations = [s[5] for s in SCENES]
    # Build filter_complex for an N-clip xfade chain
    inputs: List[str] = []
    for p in clip_paths:
        inputs.extend(["-i", str(p)])
    filter_parts: List[str] = []
    prev = "[0:v]"
    accum_offset = 0.0
    for i in range(1, len(clip_paths)):
        offset = sum(durations[:i]) - fade
        accum_offset = offset
        out_label = f"[v{i}]"
        filter_parts.append(
            f"{prev}[{i}:v]xfade=transition=fade:duration={fade}:"
            f"offset={offset:.3f}{out_label}"
        )
        prev = out_label
    filter_complex = ";".join(filter_parts)
    cmd = ["ffmpeg", "-y", *inputs, "-filter_complex", filter_complex,
           "-map", prev, "-c:v", "libx264", "-preset", "veryfast",
           "-pix_fmt", "yuv420p", "-r", "30", str(SILENT_VIDEO)]
    subprocess.run(cmd, check=True, capture_output=True)
    print(f"   silent video -> {SILENT_VIDEO.name}")


# ------------ STEP 4 · NARRATION (OPENAI TTS-1-HD) ------------
async def generate_narration() -> None:
    print("[4/6] Generating echo narration via OpenAI TTS-1-HD")
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        raise SystemExit("EMERGENT_LLM_KEY missing — set in /app/backend/.env")
    tts = OpenAITextToSpeech(api_key=api_key)
    audio_bytes = await tts.generate_speech(
        text=NARRATION_TEXT,
        model="tts-1-hd",
        voice="echo",
        response_format="mp3",
    )
    NARRATION.write_bytes(audio_bytes)
    print(f"   narration -> {NARRATION.name} ({NARRATION.stat().st_size//1024} KB)")


# ------------ STEP 5 · SYNTH MUSIC BED ------------
def synthesize_music() -> None:
    """Subtle synth pulse: detuned low-cyan sines + soft pad, very quiet."""
    print("[5/6] Synthesizing subtle synth music bed")
    total = int(sum(s[5] for s in SCENES))
    # Three layered sine waves (root + 5th + octave) low-pass filtered
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"sine=frequency=110:duration={total}",
        "-f", "lavfi", "-i", f"sine=frequency=164.81:duration={total}",
        "-f", "lavfi", "-i", f"sine=frequency=220:duration={total}",
        "-filter_complex",
        "[0:a]volume=0.10[a0];"
        "[1:a]volume=0.06[a1];"
        "[2:a]volume=0.05[a2];"
        "[a0][a1][a2]amix=inputs=3:normalize=0,"
        "lowpass=f=600,tremolo=f=0.35:d=0.4,"
        "afade=t=in:st=0:d=2.5,afade=t=out:st=" + f"{total-2.5}:d=2.5",
        "-ac", "2", "-ar", "44100", str(MUSIC_BED),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    print(f"   music bed -> {MUSIC_BED.name}")


# ------------ STEP 6 · MUX FINAL ------------
def mux_final() -> None:
    print("[6/6] Muxing final video")
    cmd = [
        "ffmpeg", "-y",
        "-i", str(SILENT_VIDEO),
        "-i", str(NARRATION),
        "-i", str(MUSIC_BED),
        "-filter_complex",
        # Mix narration loud + music quiet underneath, normalize, gentle limit
        "[1:a]volume=1.6,aformat=channel_layouts=stereo[narr];"
        "[2:a]volume=0.45,aformat=channel_layouts=stereo[mus];"
        "[narr][mus]amix=inputs=2:duration=longest:normalize=0,"
        "alimiter=limit=0.95[outa]",
        "-map", "0:v", "-map", "[outa]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-shortest", str(FINAL),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    size_mb = FINAL.stat().st_size / 1024 / 1024
    # Probe duration
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(FINAL)],
        capture_output=True, text=True,
    )
    dur = float(probe.stdout.strip() or 0)
    print(f"\nDONE -> {FINAL} · {dur:.1f}s · {size_mb:.1f} MB")


async def main():
    await capture_screens()
    compose_slides()
    render_silent_video()
    await generate_narration()
    synthesize_music()
    mux_final()


if __name__ == "__main__":
    asyncio.run(main())
