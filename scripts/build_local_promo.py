"""
Build a branded Tennant TMS promo video locally — no Sora 2, no YouTube, no
external CDN. Produces /app/frontend/public/promo.mp4 that the HTML5 <video>
tag in PromoVideo.jsx will play instantly even on locked-down corporate
networks that block youtube.com.

Render strategy:
  1. Generate N branded slide PNGs (1920x1080) with PIL — cyan/navy HUD style.
  2. Stitch with ffmpeg into an h264 mp4 with smooth crossfades.
"""
import os
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT_DIR = Path("/tmp/promo_slides")
OUT_DIR.mkdir(exist_ok=True)
FINAL = Path("/app/frontend/public/promo.mp4")
FINAL.parent.mkdir(parents=True, exist_ok=True)

W, H = 1920, 1080
NAVY = (11, 14, 20)         # #0B0E14
CYAN = (34, 211, 238)        # tailwind cyan-400
CYAN_DIM = (14, 116, 144)    # cyan-700
SLATE = (203, 213, 225)      # slate-300
SLATE_DIM = (100, 116, 139)  # slate-500

# Pick the best available bold + mono fonts
def _pick_font(candidates, size):
    for c in candidates:
        if os.path.exists(c):
            return ImageFont.truetype(c, size)
    return ImageFont.load_default()

FONT_DISPLAY_HUGE = _pick_font([
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
], 140)
FONT_DISPLAY = _pick_font([
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
], 92)
FONT_BODY = _pick_font([
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
], 40)
FONT_MONO_SMALL = _pick_font([
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf",
], 26)
FONT_MONO_TINY = _pick_font([
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
], 20)


def base_frame() -> Image.Image:
    img = Image.new("RGB", (W, H), NAVY)
    d = ImageDraw.Draw(img)
    # Faint HUD grid
    for x in range(0, W, 60):
        d.line([(x, 0), (x, H)], fill=(18, 28, 40), width=1)
    for y in range(0, H, 60):
        d.line([(0, y), (W, y)], fill=(18, 28, 40), width=1)
    # Top corner bracket marks (HUD aesthetic)
    for (ox, oy) in [(60, 60), (W - 60, 60), (60, H - 60), (W - 60, H - 60)]:
        sx = -1 if ox > W / 2 else 1
        sy = -1 if oy > H / 2 else 1
        d.line([(ox, oy), (ox + sx * 50, oy)], fill=CYAN, width=3)
        d.line([(ox, oy), (ox, oy + sy * 50)], fill=CYAN, width=3)
    # Footer marker
    d.text((60, H - 50), "TENNANT · TMS · v1.6", font=FONT_MONO_TINY, fill=SLATE_DIM)
    d.text((W - 320, H - 50), "MISSION-CONTROL · 250 USERS", font=FONT_MONO_TINY, fill=SLATE_DIM)
    return img


def slide_hero(path):
    img = base_frame()
    d = ImageDraw.Draw(img)
    # Eyebrow
    d.text((140, 280), "TENNANT COMPANIES · TRANSPORTATION MANAGEMENT SYSTEM",
           font=FONT_MONO_SMALL, fill=CYAN)
    # Headline (two-line)
    d.text((140, 360), "One Glass.", font=FONT_DISPLAY_HUGE, fill=SLATE)
    d.text((140, 510), "Every Mode. Total Command.", font=FONT_DISPLAY_HUGE, fill=CYAN)
    # Subline
    d.text((140, 720), "Mission-control TMS for Golden Valley · Holland · Louisville",
           font=FONT_BODY, fill=SLATE_DIM)
    img.save(path, "PNG")


def slide_feature(path, eyebrow, title, body_lines):
    img = base_frame()
    d = ImageDraw.Draw(img)
    d.text((140, 280), eyebrow, font=FONT_MONO_SMALL, fill=CYAN)
    d.text((140, 350), title, font=FONT_DISPLAY, fill=SLATE)
    # Cyan rule
    d.line([(140, 470), (380, 470)], fill=CYAN, width=4)
    y = 520
    for line in body_lines:
        d.text((140, y), line, font=FONT_BODY, fill=SLATE)
        y += 60
    img.save(path, "PNG")


def slide_stat_grid(path):
    img = base_frame()
    d = ImageDraw.Draw(img)
    d.text((140, 200), "BY THE NUMBERS", font=FONT_MONO_SMALL, fill=CYAN)
    d.text((140, 260), "v1.6 Coverage", font=FONT_DISPLAY, fill=SLATE)
    stats = [
        ("250", "concurrent users"),
        ("30+", "modules"),
        ("100+", "API endpoints"),
        ("6", "modes of transit"),
        ("11", "Incoterms 2020"),
        ("7", "visual themes"),
    ]
    col_w, row_h = 580, 230
    base_x, base_y = 140, 440
    for i, (n, lbl) in enumerate(stats):
        cx = base_x + (i % 3) * col_w
        cy = base_y + (i // 3) * row_h
        d.rectangle([(cx, cy), (cx + col_w - 40, cy + row_h - 40)], outline=CYAN_DIM, width=2)
        d.text((cx + 30, cy + 25), n, font=FONT_DISPLAY_HUGE, fill=CYAN)
        d.text((cx + 30, cy + 175), lbl.upper(), font=FONT_MONO_SMALL, fill=SLATE_DIM)
    img.save(path, "PNG")


def slide_close(path):
    img = base_frame()
    d = ImageDraw.Draw(img)
    d.text((140, 360), "READY WHEN YOU ARE.", font=FONT_MONO_SMALL, fill=CYAN)
    d.text((140, 430), "Launch the dashboard.", font=FONT_DISPLAY, fill=SLATE)
    d.text((140, 540), "Share driver links.", font=FONT_DISPLAY, fill=SLATE)
    d.text((140, 650), "Let HUDLINK answer the hard questions.", font=FONT_DISPLAY, fill=CYAN)
    img.save(path, "PNG")
    img.save(path, "PNG")


# ----- Build slides -----
SLIDES = []

def add(p, builder):
    builder(p)
    SLIDES.append(p)


add(OUT_DIR / "00_hero.png", slide_hero)

def f_all_modes(p):
    slide_feature(p, "ALL MODES · ONE GLASS",
                  "TL · LTL · Parcel",
                  ["Ocean · Air · Rail in a single", "mission-control view."])
    Image.open(p)  # ensure saved
SLIDES.append(OUT_DIR / "01_modes.png")
slide_feature(SLIDES[-1], "ALL MODES · ONE GLASS", "TL · LTL · Parcel",
              ["Ocean · Air · Rail in a single", "mission-control view."])
SLIDES[-1] = str(SLIDES[-1])

def emit(name, *args):
    p = str(OUT_DIR / name)
    slide_feature(p, *args)
    SLIDES.append(p)

# Replace the awkward append above
SLIDES = [str(OUT_DIR / "00_hero.png")]
slide_hero(SLIDES[0])
emit("01_modes.png", "ALL MODES · ONE GLASS", "TL · LTL · Parcel",
     ["Ocean · Air · Rail — every load in one view.",
      "Live map. Live ETAs. Live cost."])
emit("02_audit.png", "FREIGHT AUDIT & PAY", "Auto-Detect Overcharges",
     ["Accessorials parsed automatically.",
      "Approve, pay, or dispute in clicks."])
emit("03_sap.png", "SAP S/4HANA · ODATA", "Live SO / PO Sync",
     ["Pull-from-SAP auto-fills Book Load.",
      "Write-back on delivery & POD."])
emit("04_trade.png", "TRADE COMPLIANCE", "Tariffs · 301 · 232",
     ["11 Incoterms 2020 reference cards.",
      "USMCA · KORUS · FTZ · Drawback."])
emit("05_ai.png", "HUDLINK · CLAUDE 4.5", "AI Co-Pilot",
     ["Tennant-tuned for HS codes,",
      "carrier strategy, customs questions."])
emit("06_bol.png", "v1.7 · DOCUMENTS", "BOL Store · Amend · Email",
     ["Every BOL on file — audit-trailed.",
      "One-click generate from any shipment."])
emit("07_yard.png", "v1.7 · EQUIPMENT", "Yard Excel · Live Analytics",
     ["Drop the daily yard report. Get",
      "live door map, dwell, carrier mix."])
emit("08_drag.png", "v1.7 · COMMAND TILES", "Drag-Drop Layout",
     ["Reorder every Command tile.",
      "Resize columns. Reorder headers."])
emit("09_catalog.png", "v1.7 · CATALOG", "35 Machine Models",
     ["X-series ROVR · T-series scrubbers",
      "S-sweepers · M-combos · B-burnishers."])
emit("10_vault.png", "VAULT · CLAIMS · CARRIERS", "Everything Filed",
     ["GridFS BOLs · COIs · W-9s.",
      "Claims tracked from intake to recovery."])
slide_stat_grid(str(OUT_DIR / "11_stats.png"))
SLIDES.append(str(OUT_DIR / "11_stats.png"))
slide_close(str(OUT_DIR / "12_close.png"))
SLIDES.append(str(OUT_DIR / "12_close.png"))


# ----- Stitch with ffmpeg -----
# Each slide held for 3.5s, with 0.5s crossfades between.
SLIDE_DUR = 3.5
XFADE = 0.5

# Concat with xfade filter chain
inputs = []
for s in SLIDES:
    inputs += ["-loop", "1", "-t", str(SLIDE_DUR), "-i", s]

# Build filter graph: xfade chain
n = len(SLIDES)
filters = []
prev = "[0:v]"
offset = SLIDE_DUR - XFADE
for i in range(1, n):
    out = f"[v{i}]"
    filters.append(f"{prev}[{i}:v]xfade=transition=fade:duration={XFADE}:offset={offset * i - XFADE * (i - 1)}{out}")
    prev = out
# Re-derive offsets accurately. xfade offset is absolute from start of first input.
filters = []
prev = "[0:v]"
running_end = SLIDE_DUR
for i in range(1, n):
    out = f"[v{i}]" if i < n - 1 else "[vout]"
    offset_i = running_end - XFADE
    filters.append(f"{prev}[{i}:v]xfade=transition=fade:duration={XFADE}:offset={offset_i}{out}")
    prev = out
    running_end = running_end + SLIDE_DUR - XFADE

filter_complex = ";".join(filters)
cmd = [
    "ffmpeg", "-y",
    *inputs,
    "-filter_complex", filter_complex,
    "-map", "[vout]",
    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30", "-preset", "veryfast",
    "-movflags", "+faststart",
    str(FINAL),
]
print("[promo] Rendering", n, "slides ->", FINAL, flush=True)
res = subprocess.run(cmd, capture_output=True, text=True)
if res.returncode != 0:
    print("[promo] FFMPEG STDERR:", res.stderr[-2000:])
    raise SystemExit(res.returncode)
size_mb = os.path.getsize(FINAL) / (1024 * 1024)
print(f"[promo] OK · {FINAL} · {size_mb:.2f} MB · {n * (SLIDE_DUR - XFADE) + XFADE:.1f}s")
