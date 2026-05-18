"""Generate brand-themed monogram logos for every brand that doesn't
already ship a hand-designed logo. Run on:
  • Initial deploy
  • Whenever a new brand is created via /api/branding

Outputs two PNGs per brand:
  /app/frontend/public/brand/logos/{brand_id}.png    — 512×512, public-served
  /app/backend/routes/_brand_logos/{brand_id}.png    — 200×200, PDF-optimized

The logo design: a deep-color circle with a subtle inner ring, the brand's
short-name monogram (1-2 chars) in serif type using the brand's accent
color, plus tiny diamond flourishes top + bottom. Avoids any IP issue while
looking genuinely premium across the brand color spectrum.
"""
import asyncio
import os
import sys
from pathlib import Path
from typing import Any, Dict, Tuple

from PIL import Image, ImageDraw, ImageFont
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
sys.path.insert(0, "/app/backend")

PUBLIC_DIR = Path("/app/frontend/public/brand/logos")
PDF_DIR = Path("/app/backend/routes/_brand_logos")
PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
PDF_DIR.mkdir(parents=True, exist_ok=True)

SERIF_BOLD = "/usr/share/fonts/truetype/freefont/FreeSerifBold.ttf"
SANS_BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"


def _hex_to_rgb(h: str) -> Tuple[int, int, int]:
    h = (h or "#0E3A6B").lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        return (int(h[:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    except ValueError:
        return (14, 58, 107)


def _lighten(rgb: Tuple[int, int, int], pct: float = 0.18) -> Tuple[int, int, int]:
    r, g, b = rgb
    return (int(r + (255 - r) * pct), int(g + (255 - g) * pct), int(b + (255 - b) * pct))


def _darken(rgb: Tuple[int, int, int], pct: float = 0.22) -> Tuple[int, int, int]:
    r, g, b = rgb
    return (int(r * (1 - pct)), int(g * (1 - pct)), int(b * (1 - pct)))


def _monogram(short: str) -> str:
    """Smart monogram: prefer two-letter initials when there's a word break.
    Falls back to single letter, then '?'."""
    if not short:
        return "?"
    cleaned = "".join(c for c in short if c.isalpha() or c.isspace())
    parts = [p for p in cleaned.split() if p]
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    return cleaned[:1].upper() or "?"


def _build_logo(brand: Dict[str, Any], size: int = 512) -> Image.Image:
    primary = _hex_to_rgb(brand.get("primary_color") or "#0E3A6B")
    accent = _hex_to_rgb(brand.get("accent_color") or "#C9A24A")
    primary_light = _lighten(primary, 0.20)
    primary_dark = _darken(primary, 0.30)
    short = (brand.get("short_name") or brand.get("company_name") or "Brand").strip()
    mono = _monogram(short)

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pad = size // 16  # 6%
    # Vertical color stops for a subtle radial-ish gradient
    for i in range(size):
        # interpolate primary_light at top → primary_dark at bottom
        t = i / size
        r = int(primary_light[0] * (1 - t) + primary_dark[0] * t)
        g = int(primary_light[1] * (1 - t) + primary_dark[1] * t)
        b = int(primary_light[2] * (1 - t) + primary_dark[2] * t)
        d.line([(0, i), (size, i)], fill=(r, g, b, 255))

    # Mask circle so the gradient becomes a disc
    mask = Image.new("L", (size, size), 0)
    md = ImageDraw.Draw(mask)
    md.ellipse((pad, pad, size - pad, size - pad), fill=255)
    disc = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    disc.paste(img, (0, 0), mask)

    # Outer accent ring
    rd = ImageDraw.Draw(disc)
    ring_w = max(3, size // 90)
    rd.ellipse((pad, pad, size - pad, size - pad), outline=accent + (255,), width=ring_w)
    # Inner thin ring
    inner_pad = pad + size // 28
    rd.ellipse((inner_pad, inner_pad, size - inner_pad, size - inner_pad),
               outline=accent + (170,), width=max(1, ring_w // 2))

    # Monogram: serif bold if available, else sans bold
    font_path = SERIF_BOLD if os.path.exists(SERIF_BOLD) else SANS_BOLD
    # Size monogram to fit nicely; one-letter monogram = bigger
    target_height = size // (2 if len(mono) == 1 else 2.4)
    font_size = int(target_height)
    try:
        font = ImageFont.truetype(font_path, font_size)
    except IOError:
        font = ImageFont.load_default()
    bbox = rd.textbbox((0, 0), mono, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = (size - tw) // 2 - bbox[0]
    ty = (size - th) // 2 - bbox[1] - size // 60   # nudge up slightly
    # Subtle shadow
    rd.text((tx + 3, ty + 4), mono, font=font, fill=primary_dark + (90,))
    # Main monogram
    rd.text((tx, ty), mono, font=font, fill=accent + (255,))

    # Diamond flourishes top + bottom
    diamond = size // 26
    cy_top = pad + size // 18 + size // 30
    cy_bot = size - pad - size // 18 - size // 30
    cx = size // 2
    for cy in (cy_top, cy_bot):
        rd.polygon([
            (cx, cy - diamond), (cx + diamond, cy),
            (cx, cy + diamond), (cx - diamond, cy),
        ], fill=accent + (255,))

    return disc


async def main() -> None:
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    if not mongo_url or not db_name:
        raise SystemExit("MONGO_URL or DB_NAME missing in /app/backend/.env")
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    brands = await db.company_brand.find({}, {"_id": 0}).to_list(length=200)
    print(f"Found {len(brands)} brand(s).")

    for brand in brands:
        brand_id = brand.get("brand_id")
        if not brand_id:
            continue
        # Orisei + Tennant keep their hand-designed assets; everyone else
        # gets a generated branded monogram.
        if brand_id in ("orisei", "orisei-freight"):
            print(f"  · {brand_id}: skipping (using Calafia griffin asset)")
            continue
        big = _build_logo(brand, size=512)
        small = _build_logo(brand, size=200)
        big_path = PUBLIC_DIR / f"{brand_id}.png"
        small_path = PDF_DIR / f"{brand_id}.png"
        big.save(big_path, "PNG", optimize=True)
        small.save(small_path, "PNG", optimize=True)
        public_url = f"/brand/logos/{brand_id}.png"
        # Persist on the brand doc so the frontend + PDFs can resolve
        await db.company_brand.update_one(
            {"brand_id": brand_id},
            {"$set": {
                "logo_url": public_url,
                "logo_pdf_path": str(small_path),
            }},
        )
        print(f"  · {brand_id}: generated → {big_path}, {small_path}, db updated")

    client.close()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
