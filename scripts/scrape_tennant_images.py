"""Pull real Tennant product hero images by visiting each product URL and
extracting the <meta property="og:image"> tag. Falls back to a regex scan
of the HTML for tennantco.com/services/product/image.tennant.NNNN paths.

Run: python /app/scripts/scrape_tennant_images.py
Writes: /tmp/tennant_image_map.json   { "T7": "https://...jpg", ... }
"""
import json
import re
import sys
import time
import requests
from pathlib import Path

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9",
}

# Map model -> product page URL (mirrors TENNANT_MACHINES product_url field).
PRODUCT_URLS = {
    "X4 ROVR": "https://www.tennantco.com/en_us/1/machines/robotic-cleaning-machines/product.x4rovr.compact-robotic-sweeper-scrubber.html",
    "X6 ROVR": "https://www.tennantco.com/en_us/1/machines/robotic-cleaning-machines/product.x6rovr.mid-size-robotic-sweeper-scrubber.html",
    "X16 SWEEP": "https://www.tennantco.com/en_us/1/machines/robotic-cleaning-machines/product.x16sweep.industrial-robotic-sweeper.html",
    "T7AMR": "https://www.tennantco.com/en_us/1/machines/scrubbers/product.t7amr.robotic-floor-scrubber.2000056.html",
    "T16AMR": "https://www.tennantco.com/en_us/1/machines/scrubbers/product.t16amr.industrial-robotic-floor-scrubber.2000054.html",
    "T2": "https://www.tennantco.com/en_us/1/machines/scrubbers/product.t2.compact-floor-scrubber.html",
    "T300": "https://www.tennantco.com/en_us/1/machines/scrubbers/product.t300.walk-behind-floor-scrubber.html",
    "T350": "https://www.tennantco.com/en_us/1/machines/scrubbers/product.t350.walk-behind-floor-scrubber.html",
    "T381": "https://www.tennantco.com/en_us/1/machines/scrubbers/product.t381.walk-behind-floor-scrubber.html",
    "T500": "https://www.tennantco.com/en_us/1/machines/scrubbers/product.t500.walk-behind-floor-scrubber.html",
    "T600": "https://www.tennantco.com/en_us/1/machines/scrubbers/product.t600.walk-behind-floor-scrubber.html",
    "T7": "https://www.tennantco.com/en_us/1/machines/scrubbers/product.t7.ride-on-floor-scrubber.2000074.html",
    "T12": "https://www.tennantco.com/en_us/1/machines/scrubbers/product.t12.battery-ride-on-floor-scrubber.html",
    "T16": "https://www.tennantco.com/en_us/1/machines/scrubbers/product.t16.battery-ride-on-floor-scrubber.2000070.html",
    "T17": "https://www.tennantco.com/en_us/1/machines/scrubbers/product.t17.battery-ride-on-floor-scrubber.html",
    "T20": "https://www.tennantco.com/en_us/1/machines/scrubbers/product.t20.industrial-ride-on-floor-scrubber.html",
    "S3": "https://www.tennantco.com/en_us/1/machines/sweepers/product.s3.compact-sweeper.html",
    "S5": "https://www.tennantco.com/en_us/1/machines/sweepers/product.s5.walk-behind-sweeper.html",
    "S6": "https://www.tennantco.com/en_us/1/machines/sweepers/product.s6.walk-behind-sweeper.html",
    "S7": "https://www.tennantco.com/en_us/1/machines/sweepers/product.s7.battery-rider-sweeper.html",
    "S12": "https://www.tennantco.com/en_us/1/machines/sweepers/product.s12.industrial-rider-sweeper.html",
    "S16": "https://www.tennantco.com/en_us/1/machines/sweepers/product.s16.industrial-rider-sweeper.html",
    "S20": "https://www.tennantco.com/en_us/1/machines/sweepers/product.s20.mid-sized-sweeper.html",
    "S30": "https://www.tennantco.com/en_us/1/machines/sweepers/product.s30.industrial-sweeper.html",
    "M17": "https://www.tennantco.com/en_us/1/machines/sweeper-scrubbers/product.m17.battery-powered-ride-on-sweeper-scrubber.2000131.html",
    "M20": "https://www.tennantco.com/en_us/1/machines/sweeper-scrubbers/product.m20.industrial-sweeper-scrubber.html",
    "M30": "https://www.tennantco.com/en_us/1/machines/sweeper-scrubbers/product.m30.industrial-sweeper-scrubber.html",
    "B5": "https://www.tennantco.com/en_us/1/machines/burnishers/product.b5.walk-behind-burnisher.html",
    "B7": "https://www.tennantco.com/en_us/1/machines/burnishers/product.b7.battery-rider-burnisher.html",
    "B10": "https://www.tennantco.com/en_us/1/machines/burnishers/product.b10.lpg-rider-burnisher.html",
    "EX-CAN-7": "https://www.tennantco.com/en_us/1/machines/carpet-extractors/product.ex-can-7.canister-extractor.html",
    "E5": "https://www.tennantco.com/en_us/1/machines/carpet-extractors/product.e5.walk-behind-extractor.html",
    "1610": "https://www.tennantco.com/en_us/1/machines/carpet-extractors/product.1610.heated-extractor.html",
    "Green Machine 414HS": "https://www.tennantco.com/en_us/1/machines/outdoor-cleaning/product.414hs.compact-street-sweeper.html",
    "ATLV 4300": "https://www.tennantco.com/en_us/1/machines/outdoor-cleaning/product.atlv-4300.all-terrain-litter-vacuum.html",
}

OG_RE = re.compile(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', re.I)
ALT_RE = re.compile(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', re.I)
DAM_RE = re.compile(r'(https?:[^"\'\s]*?/content/dam/tennant/[^"\'\s]+?\.(?:png|jpg|jpeg))', re.I)
SVC_RE = re.compile(r'(https?:[^"\'\s]*?/services/product/image\.tennant\.\d+\.[a-z0-9_-]+)', re.I)


def pick_best(html: str, url: str) -> str | None:
    # 1. og:image
    m = OG_RE.search(html) or ALT_RE.search(html)
    if m:
        candidate = m.group(1).strip()
        if candidate.startswith("//"):
            candidate = "https:" + candidate
        elif candidate.startswith("/"):
            candidate = "https://www.tennantco.com" + candidate
        # Verify it returns a real image, not a placeholder
        try:
            r = requests.head(candidate, timeout=10, allow_redirects=True, headers=HEADERS)
            if r.status_code == 200 and int(r.headers.get("content-length", 0) or 0) > 15000:
                return candidate
        except Exception:
            pass
    # 2. content/dam path
    for m in DAM_RE.finditer(html):
        c = m.group(1)
        try:
            r = requests.head(c, timeout=10, allow_redirects=True, headers=HEADERS)
            if r.status_code == 200 and int(r.headers.get("content-length", 0) or 0) > 15000:
                return c
        except Exception:
            pass
    # 3. service/product
    for m in SVC_RE.finditer(html):
        c = m.group(1)
        # Only accept ones bigger than the 8689-byte placeholder
        try:
            r = requests.head(c, timeout=10, allow_redirects=True, headers=HEADERS)
            size = int(r.headers.get("content-length", 0) or 0)
            if r.status_code == 200 and size > 12000:
                return c
        except Exception:
            pass
    return None


def main():
    out: dict[str, str] = {}
    failed: list[str] = []
    for model, url in PRODUCT_URLS.items():
        try:
            r = requests.get(url, timeout=20, headers=HEADERS)
            if r.status_code != 200:
                print(f"  ✗ {model:20s} HTTP {r.status_code} on product page")
                failed.append(model)
                continue
            best = pick_best(r.text, url)
            if best:
                out[model] = best
                print(f"  ✓ {model:20s} {best[:90]}")
            else:
                print(f"  ✗ {model:20s} no image found")
                failed.append(model)
        except Exception as e:
            print(f"  ✗ {model:20s} {e}")
            failed.append(model)
        time.sleep(0.4)  # be polite to Tennant CDN

    out_path = Path("/tmp/tennant_image_map.json")
    out_path.write_text(json.dumps(out, indent=2))
    print(f"\nSaved {len(out)} / {len(PRODUCT_URLS)} images to {out_path}")
    if failed:
        print("Failed models:", failed)
    return 0 if out else 1


if __name__ == "__main__":
    sys.exit(main())
