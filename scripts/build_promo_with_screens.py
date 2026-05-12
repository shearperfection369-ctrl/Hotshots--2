"""Build the Tennant TMS launch promotional video with NEW v2 feature
coverage and SYNCHRONIZED AUDIO.

Pipeline:
  1. Capture every flagship page via Playwright (capture_tms_screens_pw.py)
  2. Compose each slide: real UI screenshot + on-canvas caption
  3. Render the slideshow with ffmpeg + xfade
  4. Generate AI narration MP3 via OpenAI TTS (generate_promo_narration.py)
  5. Synthesize a soft ambient music bed in ffmpeg (no download required —
     keeps the script firewall-safe)
  6. Mux narration (loud) + music (quiet) under the video and write the
     final MP4 to /app/frontend/public/promo.mp4

Output: /app/frontend/public/promo.mp4  (~108 s, ~10 MB)
"""
import os
import shutil
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

BASE = os.environ.get("PROMO_BASE_URL", "https://clean-logistics-dash.preview.emergentagent.com")
TMP = Path("/tmp/tms_promo_v2")
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

# (URL path, slug, eyebrow, headline, body lines)
SCENES = [
    ("/dashboard", "01_command", "COMMAND CENTER", "Your Daily 9 a.m. Stand-Up",
     ["One screen replaces the morning email blast:",
      "live map, weather, traffic, KPIs, broker feed —",
      "everything the team checks before standing up."]),
    ("/workbook", "02_booking", "TRUCKLOAD BOOKING SHEET", "The Team's Live Booking Board",
     ["Click any cell to edit. Auto-saves on blur.",
      "Other dispatchers see your edits in 4 seconds.",
      "Retires the daily emailed XLSX for good."]),
    ("/shipments", "03_shipments", "SHIPMENTS", "Edit in Place. No More Spreadsheets",
     ["Update status, ETAs and pricing on the row.",
      "Drag-reorder columns to match your workflow.",
      "Soft-delete with audit log — zero data loss."]),
    ("/tracking", "04_tracking", "LIVE TRACKING", "Every Truck. Every Container. One Map",
     ["Pulsing markers across road, ocean, air, rail.",
      "Weather radar overlay surfaces storm risk.",
      "Click any pin to open the live shipment file."]),
    ("/equipment", "05_equipment", "EQUIPMENT & YARD", "Drop the XLSX, Get Live KPIs",
     ["Drag in the daily yard report each morning.",
      "Instant door map, dwell, sealed %, carrier mix.",
      "Stale-trailer alerts surface before they hurt."]),
    ("/carrier-rates", "06_rates", "CARRIER RATES", "Rate-Shop Before You Tender",
     ["80+ carrier rate decks, MSAs, accessorials.",
      "Side-by-side compare for every lane.",
      "Cube weight + dunnage baked in — no surprises."]),
    ("/specialty-carriers", "07_specialty", "SPECIALTY CARRIERS", "Logix · Panther · Fastfrate · Ryan",
     ["Single pane for the niche / expedite network.",
      "Live shipment status, contact rosters, rates.",
      "Built for hot loads the standard board can't run."]),
    ("/routing-guide", "08_routing", "INBOUND ROUTING GUIDE", "One Click. Every Supplier",
     ["Drop the latest PDF, hit Send to Suppliers.",
      "Delivery receipts and read counts in real time.",
      "Carrier of choice baked into each lane / mode."]),
    ("/documents", "09_documents", "DOCUMENTS · BOL ARCHIVE", "Generate. Amend. Email. In Seconds",
     ["Every BOL on file with full version history.",
      "Amend with reason + diff trail for compliance.",
      "One-click email — no more printer runs."]),
    ("/trade-compliance", "10_trade", "TRADE COMPLIANCE", "Daily HTS · Incoterms · 301 Desk",
     ["All 11 Incoterms 2020 at your fingertips.",
      "Section 301/232 watch, USMCA, FTZ, drawback.",
      "Broker portal, contacts, ACE — one place."]),
    ("/suppliers", "11_suppliers", "SUPPLIER SOURCING", "Risk, Spend, Single-Source Exposure",
     ["20 seeded suppliers + manual entry on the fly.",
      "Filter by country, category, primary, single-src.",
      "Spend-by-country chart for executive review."]),
    ("/machines", "12_catalog", "MACHINE CATALOG", "35 Live Tennant Models",
     ["Real photos, dimensions, power, capacity.",
      "Linked from shipments and BOLs automatically.",
      "Add a new SKU from the Admin Settings panel."]),
    ("/powerbi", "13_powerbi", "POWER BI", "Finance & Ops Dashboards · Embedded",
     ["Native Power BI tiles inside the TMS.",
      "Booking numbers, freight spend, on-time KPIs.",
      "No alt-tab — one workspace for the whole team."]),
    ("/sharepoint", "14_sharepoint", "SHAREPOINT", "Contracts · SOPs · Audit Folders",
     ["Document libraries surface inside the TMS.",
      "Search, preview, link from any shipment record.",
      "Permissions roll up from Microsoft 365 AD."]),
    ("/copilot", "15_copilot", "MICROSOFT COPILOT", "Ask. Draft. Summarize. In-Workspace",
     ["Launch Copilot without leaving the TMS.",
      "Draft carrier emails, summarize policies,",
      "extract data from a BOL in one prompt."]),
    ("/reports", "16_reports", "KPI REPORTS", "45-Metric Carrier Scorecard",
     ["OTD, on-time pickup, tender accept, claims %.",
      "Auto-emailed weekly digest to leadership.",
      "Export PDF / Excel for board reviews."]),
    ("/driver-registry", "17_driver_registry", "DRIVER & TRAILER REGISTRY",
     "CDL · Medical · DOT Inspection",
     ["CDL class, state, expiry and endorsements.",
      "Medical card and TWIC expiry color-coded.",
      "Trailer plate, VIN, capacity, next inspection."]),
    ("/arcade", "18_arcade", "ARCADE · LUNCH BREAK", "Connect 4 · Chess · Tournaments",
     ["Challenge a teammate, climb the leaderboard.",
      "Solo chess vs the HUDLINK engine.",
      "Because dispatchers deserve a break too."]),
]

W, H = 1920, 1080
NAVY = (11, 14, 20)
CYAN = (34, 211, 238)
SLATE = (203, 213, 225)
SLATE_DIM = (100, 116, 139)

FONT_HEAD = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 64)
FONT_EYE = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf", 22)
FONT_BODY = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", 30)
FONT_FOOTER = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf", 18)


def build_slide(shot_path: Path, slug: str, eyebrow: str, title: str, lines, out_path: Path):
    canvas = Image.new("RGB", (W, H), NAVY)
    if shot_path.exists() and os.path.getsize(shot_path) > 1000:
        shot = Image.open(shot_path).convert("RGB")
        shot_w = 1080
        shot_h = int(shot.size[1] * shot_w / shot.size[0])
        shot = shot.resize((shot_w, shot_h))
        if shot.size[1] > H:
            shot = shot.crop((0, 0, shot_w, H))
        dim_layer = Image.new("RGB", shot.size, (11, 14, 20))
        shot = Image.blend(shot, dim_layer, 0.20)
        canvas.paste(shot, (40, (H - shot.size[1]) // 2))
        d = ImageDraw.Draw(canvas)
        d.rectangle([40, (H - shot.size[1]) // 2, 40 + shot_w, (H - shot.size[1]) // 2 + shot.size[1]],
                    outline=CYAN, width=3)
    d = ImageDraw.Draw(canvas)
    # HUD corner brackets
    for (ox, oy) in [(40, 40), (W - 40, 40), (40, H - 40), (W - 40, H - 40)]:
        sx = -1 if ox > W / 2 else 1
        sy = -1 if oy > H / 2 else 1
        d.line([(ox, oy), (ox + sx * 50, oy)], fill=CYAN, width=3)
        d.line([(ox, oy), (ox, oy + sy * 50)], fill=CYAN, width=3)
    tx = 1180
    d.text((tx, 200), eyebrow, font=FONT_EYE, fill=CYAN)
    d.text((tx, 250), title, font=FONT_HEAD, fill=SLATE)
    d.line([(tx, 370), (tx + 200, 370)], fill=CYAN, width=4)
    y = 420
    for line in lines:
        d.text((tx, y), line, font=FONT_BODY, fill=SLATE)
        y += 50
    d.text((60, H - 50), "TENNANT · TMS v2.0 · LAUNCH BUILD", font=FONT_FOOTER, fill=SLATE_DIM)
    n = slug.split("_")[0]
    d.text((W - 320, H - 50), f"SCENE {n} / {len(SCENES):02d}", font=FONT_FOOTER, fill=SLATE_DIM)
    canvas.save(out_path, "PNG")


def build_hero(out_path: Path):
    canvas = Image.new("RGB", (W, H), NAVY)
    d = ImageDraw.Draw(canvas)
    for x in range(0, W, 60): d.line([(x, 0), (x, H)], fill=(18, 28, 40), width=1)
    for y in range(0, H, 60): d.line([(0, y), (W, y)], fill=(18, 28, 40), width=1)
    for (ox, oy) in [(60, 60), (W - 60, 60), (60, H - 60), (W - 60, H - 60)]:
        sx = -1 if ox > W / 2 else 1
        sy = -1 if oy > H / 2 else 1
        d.line([(ox, oy), (ox + sx * 50, oy)], fill=CYAN, width=3)
        d.line([(ox, oy), (ox, oy + sy * 50)], fill=CYAN, width=3)
    d.text((140, 380), "TENNANT COMPANIES · TRANSPORTATION MANAGEMENT SYSTEM",
           font=FONT_EYE, fill=CYAN)
    huge = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 140)
    d.text((140, 430), "Built for the", font=huge, fill=SLATE)
    d.text((140, 580), "Team's Day.", font=huge, fill=CYAN)
    d.text((140, 770),
           "Launch v2 · 18 flagship modules · Power BI · SharePoint · Copilot · Specialty Carriers",
           font=FONT_BODY, fill=SLATE_DIM)
    d.text((60, H - 50), "TENNANT · TMS v2.0", font=FONT_FOOTER, fill=SLATE_DIM)
    canvas.save(out_path, "PNG")


def build_outro(out_path: Path):
    canvas = Image.new("RGB", (W, H), NAVY)
    d = ImageDraw.Draw(canvas)
    for x in range(0, W, 60): d.line([(x, 0), (x, H)], fill=(18, 28, 40), width=1)
    for y in range(0, H, 60): d.line([(0, y), (W, y)], fill=(18, 28, 40), width=1)
    for (ox, oy) in [(60, 60), (W - 60, 60), (60, H - 60), (W - 60, H - 60)]:
        sx = -1 if ox > W / 2 else 1
        sy = -1 if oy > H / 2 else 1
        d.line([(ox, oy), (ox + sx * 50, oy)], fill=CYAN, width=3)
        d.line([(ox, oy), (ox, oy + sy * 50)], fill=CYAN, width=3)
    d.text((140, 380), "USED BY THE TEAM · EVERY DAY", font=FONT_EYE, fill=CYAN)
    d.text((140, 430), "Sign in. See the map.", font=FONT_HEAD, fill=SLATE)
    d.text((140, 530), "Book the load.", font=FONT_HEAD, fill=SLATE)
    d.text((140, 630), "The platform handles the rest.", font=FONT_HEAD, fill=CYAN)
    d.text((140, 800),
           "TENNANT · TMS v2.0 · 35 machines · 50+ modules · 200+ API endpoints",
           font=FONT_FOOTER, fill=SLATE_DIM)
    canvas.save(out_path, "PNG")


def main():
    # 1. Screenshots --------------------------------------------------------
    print("[promo] Capturing screenshots via Playwright…")
    needed = [SHOTS_DIR / f"{slug}.png" for _, slug, *_ in SCENES]
    if not all(p.exists() and os.path.getsize(p) > 50000 for p in needed):
        subprocess.run(["python3", "/app/scripts/capture_tms_screens_pw.py"], check=False)
    for _, slug, *_ in SCENES:
        p = SHOTS_DIR / f"{slug}.png"
        kb = os.path.getsize(p) // 1024 if p.exists() else 0
        print(f"  {slug}: {kb} KB")

    # 2. Compose slides -----------------------------------------------------
    print("[promo] Composing slides…")
    slides = []
    intro = SLIDES_DIR / "00_intro.png"
    build_hero(intro)
    slides.append(str(intro))
    for _, slug, eye, title, lines in SCENES:
        sp = SHOTS_DIR / f"{slug}.png"
        out = SLIDES_DIR / f"{slug}.png"
        build_slide(sp, slug, eye, title, lines, out)
        slides.append(str(out))
    outro = SLIDES_DIR / "99_outro.png"
    build_outro(outro)
    slides.append(str(outro))

    # 3. Render silent video with xfade ------------------------------------
    SLIDE_DUR = 5.4
    XFADE = 0.6
    inputs = []
    for s in slides:
        inputs += ["-loop", "1", "-t", str(SLIDE_DUR), "-i", s]
    filters = []
    prev = "[0:v]"
    running_end = SLIDE_DUR
    for i in range(1, len(slides)):
        out = f"[v{i}]" if i < len(slides) - 1 else "[vout]"
        offset_i = running_end - XFADE
        filters.append(f"{prev}[{i}:v]xfade=transition=fade:duration={XFADE}:offset={offset_i}{out}")
        prev = out
        running_end = running_end + SLIDE_DUR - XFADE
    cmd_silent = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", ";".join(filters),
        "-map", "[vout]",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30", "-preset", "veryfast",
        "-movflags", "+faststart",
        str(SILENT_VIDEO),
    ]
    print(f"[promo] Rendering silent video ({len(slides)} slides, ~{running_end:.1f}s)…")
    r = subprocess.run(cmd_silent, capture_output=True, text=True)
    if r.returncode != 0:
        print("FFMPEG STDERR:", r.stderr[-2000:])
        raise SystemExit(r.returncode)

    # 4. Generate AI narration ---------------------------------------------
    if not NARRATION.exists():
        print("[promo] Generating AI narration (OpenAI TTS via Emergent key)…")
        r = subprocess.run(
            ["python3", "/app/scripts/generate_promo_narration.py"],
            capture_output=True, text=True,
        )
        if r.returncode != 0 or not NARRATION.exists():
            print("[promo] Narration generation failed:", r.stderr[-1500:])
            raise SystemExit(1)

    # 5. Synthesize soft ambient music bed via ffmpeg lavfi sine generators.
    # Three sustained sine tones (A minor: A3, C4, E4) at very low volume with
    # a slow attack & release create a calming pad — no external download
    # required (corporate firewall-safe).
    video_dur = running_end
    print(f"[promo] Synthesizing ambient music bed (~{video_dur:.1f}s)…")
    music_filter = (
        "sine=frequency=220:duration={d}[a1];"
        "sine=frequency=261.63:duration={d}[a2];"
        "sine=frequency=329.63:duration={d}[a3];"
        "sine=frequency=440:duration={d}[a4];"
        "[a1][a2][a3][a4]amix=inputs=4:duration=longest:weights='1 0.8 0.6 0.4',"
        "tremolo=f=0.25:d=0.4,"
        "volume=0.05,"
        "afade=t=in:st=0:d=2,"
        f"afade=t=out:st={max(video_dur - 3, 0):.2f}:d=3"
    ).format(d=video_dur)
    cmd_music = [
        "ffmpeg", "-y",
        "-filter_complex", music_filter,
        "-ac", "2", "-ar", "44100",
        "-t", f"{video_dur}",
        str(MUSIC_BED),
    ]
    r = subprocess.run(cmd_music, capture_output=True, text=True)
    if r.returncode != 0:
        print("MUSIC STDERR:", r.stderr[-1500:])
        raise SystemExit(r.returncode)

    # 6. Mix narration (full volume) + music (-22 dB) to single AAC track.
    print("[promo] Mixing narration + music bed…")
    cmd_mix = [
        "ffmpeg", "-y",
        "-i", str(NARRATION),
        "-i", str(MUSIC_BED),
        "-filter_complex",
        "[0:a]volume=1.0,adelay=500|500[narr];"
        "[1:a]volume=0.32[bg];"
        "[narr][bg]amix=inputs=2:duration=longest:dropout_transition=0,"
        "alimiter=limit=0.95",
        "-c:a", "aac", "-b:a", "192k",
        str(MIXED_AUDIO),
    ]
    r = subprocess.run(cmd_mix, capture_output=True, text=True)
    if r.returncode != 0:
        print("MIX STDERR:", r.stderr[-1500:])
        raise SystemExit(r.returncode)

    # 7. Mux mixed audio into the silent video → FINAL.
    print(f"[promo] Muxing audio into {FINAL}…")
    cmd_final = [
        "ffmpeg", "-y",
        "-i", str(SILENT_VIDEO),
        "-i", str(MIXED_AUDIO),
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        "-movflags", "+faststart",
        str(FINAL),
    ]
    r = subprocess.run(cmd_final, capture_output=True, text=True)
    if r.returncode != 0:
        print("FINAL STDERR:", r.stderr[-1500:])
        raise SystemExit(r.returncode)

    size_mb = os.path.getsize(FINAL) / (1024 * 1024)
    print(f"[promo] DONE · {FINAL} · {size_mb:.2f} MB · {video_dur:.1f}s · "
          f"{len(slides)} slides · AI narration + ambient bed")


if __name__ == "__main__":
    main()
