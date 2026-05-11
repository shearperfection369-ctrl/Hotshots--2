"""Use headless Chrome with a pre-set session cookie to screenshot every key
TMS page, then build a NEW promo video that intercuts those real UI shots
with explanatory captions.

Output: /app/frontend/public/promo.mp4 (regenerated, ~50s, ~3 MB).
"""
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

BASE = "https://clean-logistics-dash.preview.emergentagent.com"
TOKEN = "test_session_admin_1"
TMP = Path("/tmp/tms_promo_v2")
TMP.mkdir(exist_ok=True)
SHOTS_DIR = TMP / "shots"
SHOTS_DIR.mkdir(exist_ok=True)
SLIDES_DIR = TMP / "slides"
SLIDES_DIR.mkdir(exist_ok=True)
FINAL = Path("/app/frontend/public/promo.mp4")

# Pages to capture: (URL path, slide title, body line(s), eyebrow)
SCENES = [
    ("/dashboard", "01_command",
     "COMMAND CENTER",
     "Live Mission Control",
     ["Geo-spatial tracker, live weather, traffic and ETAs",
      "for every truck, container, pallet and parcel —",
      "across TL, LTL, Parcel, Ocean, Air and Rail."]),
    ("/shipments", "02_shipments",
     "SHIPMENTS",
     "One Table · All Modes",
     ["Edit on the row. Soft-delete with audit log.",
      "Resize, hide, drag-reorder every column.",
      "SAP deep-links on Order, Material and BOL fields."]),
    ("/workbook", "03_booking",
     "TRUCKLOAD BOOKING SHEET",
     "Excel-Style · Real-Time",
     ["Click any cell to edit. Auto-save on blur.",
      "Other dispatchers see your edits within 4 seconds.",
      "Replaces the legacy XLSX — no more emailed copies."]),
    ("/documents", "04_documents",
     "DOCUMENTS · BOL ARCHIVE",
     "Store · Amend · Email",
     ["Every BOL on file. Amend with reason + diff trail.",
      "One-click email with PDF attachment.",
      "Generate a BOL directly from any shipment."]),
    ("/equipment", "05_equipment",
     "EQUIPMENT · YARD",
     "Daily Excel → Live KPIs",
     ["Drop your daily yard report. Instant analytics:",
      "door map, dwell, sealed%, carrier mix.",
      "Stale-trailer alerts auto-surface."]),
    ("/trade-compliance", "06_trade",
     "TRADE COMPLIANCE",
     "Incoterms · 301 · 232 · ACE",
     ["All 11 Incoterms 2020 reference cards.",
      "Section 301/232 watch. USMCA · KORUS · FTZ.",
      "Direct UPS_SCS broker portal access."]),
    ("/machines", "07_catalog",
     "MACHINE CATALOG",
     "35 Models · 12 Categories",
     ["X-series ROVR · T-series scrubbers ·",
      "S-series sweepers · M / B / E lines.",
      "Real Tennant photos and complete specs."]),
    ("/carrier-rates", "08_rates",
     "CARRIER RATES",
     "MSAs · Lanes · Surcharges",
     ["80+ carrier rate decks at your fingertips.",
      "Cube weight, accessorials, dunnage included.",
      "Side-by-side compare before tendering a load."]),
]

# ------- 1. Screenshot every page with Chrome headless -------
COMMON_FLAGS = [
    "--headless=new",
    "--no-sandbox",
    "--disable-gpu",
    "--disable-dev-shm-usage",
    "--hide-scrollbars",
    "--window-size=1920,1080",
    "--virtual-time-budget=15000",
    f"--user-data-dir={tempfile.mkdtemp(prefix='chrome-promo-')}",
]


def set_cookie_userdata():
    """Drop a Chromium Cookies SQLite entry so all subsequent navigations
    are authenticated. Easier: use --header-injection via DevTools? simpler
    is to just inject via Set-Cookie on a tiny first navigation."""


def capture(url: str, slug: str) -> Path:
    out = SHOTS_DIR / f"{slug}.png"
    # Use DevTools Protocol via 'browser' protocol isn't trivial here; simpler
    # path: inject cookie via a tiny HTML redirect through document.cookie.
    bridge = TMP / f"_bridge_{slug}.html"
    bridge.write_text(f"""<!doctype html><meta http-equiv="refresh"
content="0;url={url}"><script>
document.cookie="session_token={TOKEN}; domain=.preview.emergentagent.com; path=/; secure; samesite=none";
location.replace({json.dumps(url)});
</script>""")
    cmd = [
        "/usr/bin/google-chrome",
        *COMMON_FLAGS,
        f"--screenshot={out}",
        f"file://{bridge}",
    ]
    subprocess.run(cmd, capture_output=True, timeout=60)
    return out


print("[promo] Capturing screenshots via Playwright…")
# Delegate to the playwright-based capture script so we get authenticated
# views of every page. If the shots already exist from a previous run, skip.
needed = [SHOTS_DIR / f"{slug}.png" for _, slug, *_ in SCENES]
if not all(p.exists() and os.path.getsize(p) > 50000 for p in needed):
    subprocess.run(["python3", "/app/scripts/capture_tms_screens_pw.py"], check=False)
for path, slug, *_ in SCENES:
    p = SHOTS_DIR / f"{slug}.png"
    size_kb = os.path.getsize(p) // 1024 if p.exists() else 0
    print(f"  {slug}: {size_kb} KB  ←  {path}")


# ------- 2. Compose each slide: screenshot + caption strip -------
W, H = 1920, 1080
NAVY = (11, 14, 20)
CYAN = (34, 211, 238)
SLATE = (203, 213, 225)
SLATE_DIM = (100, 116, 139)

FONT_HEAD = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 78)
FONT_EYE = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf", 22)
FONT_BODY = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", 34)
FONT_FOOTER = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf", 18)


def build_slide(shot_path: Path, slug: str, eyebrow: str, title: str, lines: list, out_path: Path):
    canvas = Image.new("RGB", (W, H), NAVY)

    # Load the screenshot and place it on the LEFT half, blurred & dimmed
    if shot_path.exists() and os.path.getsize(shot_path) > 1000:
        shot = Image.open(shot_path).convert("RGB")
        # Resize keeping aspect ratio to fit 1080x1080 area
        shot_w = 1080
        shot_h = int(shot.size[1] * shot_w / shot.size[0])
        shot = shot.resize((shot_w, shot_h))
        if shot.size[1] > H:
            shot = shot.crop((0, 0, shot_w, H))
        # Subtle dim
        dim_layer = Image.new("RGB", shot.size, (11, 14, 20))
        shot = Image.blend(shot, dim_layer, 0.20)
        canvas.paste(shot, (40, (H - shot.size[1]) // 2))
        # Cyan border
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

    # Text panel on the RIGHT
    tx = 1200
    d.text((tx, 200), eyebrow, font=FONT_EYE, fill=CYAN)
    d.text((tx, 250), title, font=FONT_HEAD, fill=SLATE)
    d.line([(tx, 380), (tx + 200, 380)], fill=CYAN, width=4)
    y = 430
    for line in lines:
        d.text((tx, y), line, font=FONT_BODY, fill=SLATE)
        y += 55
    d.text((60, H - 50), "TENNANT · TMS v1.9 · 250 USERS", font=FONT_FOOTER, fill=SLATE_DIM)
    d.text((W - 320, H - 50), f"SCENE {slug.split('_')[0]} / {len(SCENES):02d}", font=FONT_FOOTER, fill=SLATE_DIM)
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
    d.text((140, 430), "One Glass.", font=huge, fill=SLATE)
    d.text((140, 580), "Every Mode.", font=huge, fill=CYAN)
    d.text((140, 770), "A guided tour of the Tennant TMS, feature by feature.",
           font=FONT_BODY, fill=SLATE_DIM)
    d.text((60, H - 50), "TENNANT · TMS v1.9", font=FONT_FOOTER, fill=SLATE_DIM)
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
    d.text((140, 380), "READY WHEN YOU ARE", font=FONT_EYE, fill=CYAN)
    d.text((140, 430), "Launch the dashboard.", font=FONT_HEAD, fill=SLATE)
    d.text((140, 540), "Sync the carriers.", font=FONT_HEAD, fill=SLATE)
    d.text((140, 650), "Let HUDLINK answer the rest.", font=FONT_HEAD, fill=CYAN)
    d.text((140, 800), "TENNANT · TMS v1.9 · 35 machines · 30+ modules · 100+ API endpoints",
           font=FONT_FOOTER, fill=SLATE_DIM)
    canvas.save(out_path, "PNG")


print("[promo] Composing slides…")
slides: list[str] = []
intro = SLIDES_DIR / "00_intro.png"
build_hero(intro)
slides.append(str(intro))
for path, slug, eyebrow, title, lines in SCENES:
    sp = SHOTS_DIR / f"{slug}.png"
    out = SLIDES_DIR / f"{slug}.png"
    build_slide(sp, slug, eyebrow, title, lines, out)
    slides.append(str(out))
outro = SLIDES_DIR / "99_outro.png"
build_outro(outro)
slides.append(str(outro))


# ------- 3. Render with ffmpeg + xfade -------
SLIDE_DUR = 4.5
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

cmd = [
    "ffmpeg", "-y",
    *inputs,
    "-filter_complex", ";".join(filters),
    "-map", "[vout]",
    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30", "-preset", "veryfast",
    "-movflags", "+faststart",
    str(FINAL),
]
print(f"[promo] Rendering {len(slides)} slides to {FINAL}…")
res = subprocess.run(cmd, capture_output=True, text=True)
if res.returncode != 0:
    print("FFMPEG STDERR:", res.stderr[-2000:])
    raise SystemExit(res.returncode)

size_mb = os.path.getsize(FINAL) / (1024 * 1024)
dur = len(slides) * (SLIDE_DUR - XFADE) + XFADE
print(f"[promo] DONE · {FINAL} · {size_mb:.2f} MB · {dur:.1f}s · {len(slides)} slides")
