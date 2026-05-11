"""Iteration 8 (machine catalog SVG override) backend tests."""
import os
import urllib.parse
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://clean-logistics-dash.preview.emergentagent.com").rstrip("/")
HEADERS = {"Authorization": "Bearer test_session_admin_1"}

SPOT_MODELS = ["T7", "T16AMR", "X4 ROVR", "X6 ROVR", "X16 SWEEP", "S30", "B10", "EX-CAN-7"]


@pytest.fixture(scope="module")
def machines():
    r = requests.get(f"{BASE_URL}/api/machines", headers=HEADERS, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()


# --- /api/machines override ---
def test_machines_count_and_categories(machines):
    assert "machines" in machines
    assert len(machines["machines"]) == 35, f"got {len(machines['machines'])} machines"
    assert "categories" in machines
    assert len(machines["categories"]) == 12, f"got {len(machines['categories'])} categories"


def test_machines_image_url_is_relative_api(machines):
    bad = [m["model"] for m in machines["machines"] if not m.get("image_url", "").startswith("/api/machines/")]
    assert not bad, f"machines with non-/api image_url: {bad}"


# --- SVG endpoint spot checks ---
@pytest.mark.parametrize("model", SPOT_MODELS)
def test_machine_svg_returns_200_and_svg(model):
    encoded = urllib.parse.quote(model)
    url = f"{BASE_URL}/api/machines/{encoded}/image.svg"
    r = requests.get(url, headers=HEADERS, timeout=15)
    assert r.status_code == 200, f"{url} => {r.status_code}"
    ct = r.headers.get("content-type", "")
    assert "image/svg+xml" in ct, f"{model} content-type: {ct}"
    body = r.text
    assert body.lstrip().startswith("<svg") or "<svg" in body[:200], f"{model} body doesn't look like SVG"
    # Model name should appear inside SVG body
    assert model in body, f"model name '{model}' not found inside SVG body for {model}"


def test_all_35_models_svg_200(machines):
    """Make sure every one of the 35 models returns a valid SVG (not just spot models)."""
    failures = []
    for m in machines["machines"]:
        url = f"{BASE_URL}{m['image_url']}"
        r = requests.get(url, headers=HEADERS, timeout=15)
        ct = r.headers.get("content-type", "")
        if r.status_code != 200 or "image/svg+xml" not in ct:
            failures.append({"model": m["model"], "status": r.status_code, "ct": ct})
    assert not failures, f"models with broken SVG: {failures}"


def test_url_encoded_space_works():
    """X4 ROVR with %20 encoded space must work."""
    r = requests.get(f"{BASE_URL}/api/machines/X4%20ROVR/image.svg", headers=HEADERS, timeout=15)
    assert r.status_code == 200
    assert "image/svg+xml" in r.headers.get("content-type", "")
    assert "X4 ROVR" in r.text
