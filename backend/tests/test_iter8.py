"""Iteration 8 backend tests:
- Tennant real photo machines (17 real + 18 SVG out of 35)
- Real-photo URL validation (HTTP 200, image/*, > 15KB)
- promo.mp4 endpoint (1MB+ video/mp4)
- ADMIN_EMAILS env presence
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://clean-logistics-dash.preview.emergentagent.com").rstrip("/")
ADMIN_TOKEN = "test_session_admin_1"
AUTH = {"Authorization": f"Bearer {ADMIN_TOKEN}"}

EXPECTED_REAL_MODELS = {
    "T7", "T16", "T7AMR", "T16AMR", "T12", "T17", "T20", "T2",
    "T300", "T500", "S3", "S5", "M17", "B5", "B7", "EX-CAN-7",
    "Green Machine 414HS",
}
TENNANT_CDN_PREFIX = "https://www.tennantco.com/services/product/image.tennant."
SVG_PREFIX_PATH = "/api/machines/"


@pytest.fixture(scope="module")
def machines():
    r = requests.get(f"{BASE_URL}/api/machines", headers=AUTH, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    # API returns either a list or {machines: [...], count, categories}
    if isinstance(data, dict) and "machines" in data:
        return data["machines"]
    assert isinstance(data, list)
    return data


# --- Machines: counts and split ---
def test_machines_total_count(machines):
    assert len(machines) == 35, f"expected 35 machines, got {len(machines)}"


def test_machines_real_photo_count_is_17(machines):
    real = [m for m in machines if m.get("image_url", "").startswith(TENNANT_CDN_PREFIX)]
    assert len(real) == 17, f"expected 17 real-photo machines, got {len(real)}"


def test_machines_svg_count_is_18(machines):
    svg = [m for m in machines if m.get("image_url", "").startswith(SVG_PREFIX_PATH)]
    assert len(svg) == 18, f"expected 18 SVG fallback machines, got {len(svg)}"


def test_machines_real_photo_models_match_expected(machines):
    real_models = {m["model"] for m in machines if m.get("image_url", "").startswith(TENNANT_CDN_PREFIX)}
    assert real_models == EXPECTED_REAL_MODELS, f"mismatch: {real_models ^ EXPECTED_REAL_MODELS}"


def test_machines_url_partition_is_exhaustive(machines):
    """Every machine must be either CDN real photo or SVG fallback."""
    for m in machines:
        url = m.get("image_url", "")
        assert url.startswith(TENNANT_CDN_PREFIX) or url.startswith(SVG_PREFIX_PATH), \
            f"unexpected image_url for {m.get('model')}: {url}"


# --- Real photo URL validation ---
@pytest.mark.parametrize("model", sorted(EXPECTED_REAL_MODELS))
def test_real_photo_url_returns_image(machines, model):
    m = next((x for x in machines if x["model"] == model), None)
    assert m is not None, f"machine {model} not found"
    url = m["image_url"]
    assert url.startswith(TENNANT_CDN_PREFIX)
    r = requests.get(url, timeout=30, allow_redirects=True)
    assert r.status_code == 200, f"{model} -> {url} got {r.status_code}"
    # Tennant CDN does NOT send content-type. Validate via magic bytes instead.
    head = r.content[:8]
    is_jpeg = head.startswith(b"\xff\xd8\xff")
    is_png = head.startswith(b"\x89PNG\r\n\x1a\n")
    is_gif = head.startswith(b"GIF8")
    assert is_jpeg or is_png or is_gif, f"{model} not a valid image (magic={head!r})"
    assert len(r.content) > 15000, f"{model} content size={len(r.content)} (<15KB)"


# --- SVG fallback still works ---
def test_svg_endpoint_works(machines):
    svg_machine = next((m for m in machines if m.get("image_url", "").startswith(SVG_PREFIX_PATH)), None)
    assert svg_machine is not None
    url = BASE_URL + svg_machine["image_url"]
    r = requests.get(url, headers=AUTH, timeout=15)
    assert r.status_code == 200
    assert "svg" in r.headers.get("content-type", "").lower()


# --- Promo video ---
def test_promo_mp4_endpoint():
    r = requests.get(f"{BASE_URL}/promo.mp4", timeout=30)
    assert r.status_code == 200
    ctype = r.headers.get("content-type", "")
    assert "video/mp4" in ctype or "mp4" in ctype, f"content-type={ctype}"
    # 1.05 MB expected (allow 0.5 MB - 2 MB band)
    size = len(r.content)
    assert size > 500_000, f"promo.mp4 too small: {size}"
    assert size < 3_000_000, f"promo.mp4 too large: {size}"


# --- Admin config ---
def test_admin_emails_env_contains_shearperfection():
    # read from backend .env file (env passed to backend process may not be in test env)
    with open("/app/backend/.env") as f:
        content = f.read()
    assert "oliver@oriseifreightsolutions.com" in content.lower()
    assert "ADMIN_EMAILS" in content


def test_test_credentials_md_has_shearperfection():
    with open("/app/memory/test_credentials.md") as f:
        content = f.read().lower()
    assert "oliver@oriseifreightsolutions.com" in content
    assert "admin" in content


# --- Auth me check ---
def test_admin_token_authenticates():
    r = requests.get(f"{BASE_URL}/api/auth/me", headers=AUTH, timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("role") == "admin"
