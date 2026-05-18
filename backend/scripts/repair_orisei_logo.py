"""Repair the Orisei brand logos by stripping their background and
replacing it with transparency.

The current `orisei_logo.png` / `orisei_wordmark.png` were generated with
flat-color backgrounds (mix of gray ~205,207,206 and near-white ~255) instead
of an alpha channel, so they visibly render inside a "bitmap box" wherever
they're placed on a non-matching surface.

Strategy: treat any pixel that is BOTH (a) bright AND (b) low-saturation as
background — this catches gray, off-white, and pure white in one sweep
without touching the dark navy / gold logo pixels.
"""
from pathlib import Path
from PIL import Image, ImageFilter
import colorsys
import shutil

FILES = [
    ("/app/frontend/public/brand/orisei_logo.png", (1024, 1024)),
    ("/app/frontend/public/brand/orisei_wordmark.png", None),
    ("/app/backend/routes/_orisei_logo_pdf.png", (300, 300)),
    ("/app/backend/routes/_orisei_wordmark_pdf.png", None),
]


def _is_bg(r: int, g: int, b: int) -> float:
    """Return alpha (0..255) for a pixel — 0 = full background, 255 = fully
    foreground. Pixels that are both bright (V>0.75) AND low-saturation
    (S<0.18) are background; everything else stays opaque."""
    rn, gn, bn = r / 255.0, g / 255.0, b / 255.0
    _h, s, v = colorsys.rgb_to_hsv(rn, gn, bn)
    # Pure-white / off-white / light-gray spectrum
    if v >= 0.78 and s <= 0.18:
        return 0  # full transparent
    # Mid-bright low-sat = soft edge feather
    if v >= 0.68 and s <= 0.22:
        # ramp 0..255 as the pixel gets less "background-y"
        v_factor = (v - 0.78) / -0.10 if v < 0.78 else 0  # 0..1
        s_factor = (0.22 - s) / 0.04 if s > 0.18 else 1   # 0..1 (more sat → 0)
        # If both factors say "background-ish", fade to transparent
        fade = max(0.0, 1.0 - max(v_factor, s_factor))
        return int(255 * (1 - fade))
    return 255


def repair(path_str: str, resize_to=None) -> None:
    path = Path(path_str)
    if not path.exists():
        print(f"  · skip (missing): {path}")
        return
    backup = path.with_suffix(path.suffix + ".bak")
    if not backup.exists():
        shutil.copy2(path, backup)
        print(f"  · backed up to {backup.name}")
    else:
        # Restore from backup so the script is idempotent
        shutil.copy2(backup, path)
        print(f"  · restored from {backup.name}")

    img = Image.open(path).convert("RGBA")
    px = img.load()
    w, h = img.size

    # Detect whether this asset's background is bright (wordmark uses bright
    # paper) or dark (wordmark on navy). Sample 5×5 corners.
    corner_pixels = []
    for cx, cy in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        for dx in range(-2, 3):
            for dy in range(-2, 3):
                xx, yy = max(0, min(w - 1, cx + dx)), max(0, min(h - 1, cy + dy))
                r, g, b, _ = px[xx, yy]
                corner_pixels.append((r, g, b))
    avg = tuple(int(sum(c) / len(corner_pixels)) for c in zip(*corner_pixels))
    print(f"  · avg corner color: RGB{avg}")

    is_dark_bg = sum(avg) / 3 < 80
    if is_dark_bg:
        print(f"  · detected DARK background → using brightness ratio match")
    else:
        print(f"  · detected BRIGHT background → using low-sat bright match")

    mask = Image.new("L", img.size, 255)
    mpx = mask.load()
    for y in range(h):
        for x in range(w):
            r, g, b, _ = px[x, y]
            if is_dark_bg:
                # Bg is dark navy/black — keep only pixels far enough from it
                bg_r, bg_g, bg_b = avg
                d2 = (r - bg_r)**2 + (g - bg_g)**2 + (b - bg_b)**2
                if d2 < 30 * 30:
                    mpx[x, y] = 0
                elif d2 < 60 * 60:
                    ramp = (d2 ** 0.5 - 30) / 30
                    mpx[x, y] = int(255 * ramp)
            else:
                mpx[x, y] = _is_bg(r, g, b)

    # Light feather so the edges blend
    mask = mask.filter(ImageFilter.GaussianBlur(radius=1.2))
    img.putalpha(mask)

    if resize_to and img.size != resize_to:
        img = img.resize(resize_to, Image.LANCZOS)
    img.save(path, "PNG", optimize=True)
    print(f"  · saved transparent {path.name}  ({path.stat().st_size // 1024} KB)")
    # Spot-check 4 corners after
    out_px = img.load()
    for cx, cy in ((0, 0), (img.width - 1, 0), (img.width // 2, img.height // 2)):
        r, g, b, a = out_px[cx, cy]
        tag = "transparent" if a < 20 else f"alpha={a}"
        print(f"    pixel ({cx},{cy}) → RGB({r},{g},{b}) {tag}")


def main() -> None:
    print("Repairing Orisei brand logos (smart background detection)…")
    for path, resize in FILES:
        print(f"\n▶  {path}")
        repair(path, resize)
    print("\n✅ done")


if __name__ == "__main__":
    main()
