"""Generate a brand-new 12-second Orisei Freight Solutions launch promo
with Sora 2 via the Emergent Universal Key. Saves to
/app/frontend/public/promo.mp4 so the in-app /promo page picks it up
automatically (the page hot-swaps when the file is > 100KB).

Run:
    python /app/backend/scripts/generate_orisei_promo.py
"""
import os
import sys
import traceback
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(""))

from emergentintegrations.llm.openai.video_generation import OpenAIVideoGeneration  # noqa: E402

load_dotenv("/app/backend/.env")

OUTPUT_PATH = Path("/app/frontend/public/promo.mp4")
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

PROMPT = (
    "Cinematic 12-second freight brokerage launch promo for ORISEI FREIGHT "
    "SOLUTIONS, set in the upper Midwest at golden hour. Color grade: deep "
    "navy blue shadows and warm antique gold highlights, almost heraldic. "
    "Shot 1 (3 sec): aerial of a single black Peterbilt semi truck crawling "
    "down an empty US interstate at sunset, lone headlight, rolling farmland, "
    "Minnesota grain silos in the distance. Shot 2 (2 sec): close on an "
    "operator-grade dispatch desk at night — multiple glowing monitors with a "
    "freight map, a paper Bill of Lading being slid forward, a gold heraldic "
    "wax seal of Queen Calafia on a griffin pressed onto the document with "
    "tactile detail. Shot 3 (2 sec): a phone screen ringing with the contact "
    "'OLIVER · ORISEI BROKER' as a hand swipes to answer, soft rim light. "
    "Shot 4 (2 sec): macro of a forklift gently lowering a wrapped pallet "
    "onto a loading dock, dust motes in golden light, gloved hand snapping a "
    "phone photo of the POD. Shot 5 (3 sec): final card on deep navy — the "
    "wordmark 'ORISEI FREIGHT SOLUTIONS' in serif type, gold tagline beneath "
    "reading 'Operator-built freight brokerage · Minneapolis · Saint Paul'. "
    "Cinematic 35mm depth of field, anamorphic flares, atmospheric haze, "
    "tasteful, premium, no people speaking, no text overlays except the "
    "final card. Soundtrack: low cinematic orchestral swell with a single "
    "warm cello note at the close."
)


def main() -> None:
    key = os.environ.get("EMERGENT_LLM_KEY")
    if not key:
        raise SystemExit("EMERGENT_LLM_KEY missing in /app/backend/.env")
    print("starting sora-2 generation (~3-5 min)…", flush=True)
    try:
        gen = OpenAIVideoGeneration(api_key=key)
        video_bytes = gen.text_to_video(
            prompt=PROMPT,
            model="sora-2",
            size="1280x720",
            duration=12,
            max_wait_time=900,
        )
        if not video_bytes:
            raise SystemExit("Sora returned empty payload")
        gen.save_video(video_bytes, str(OUTPUT_PATH))
        size_kb = OUTPUT_PATH.stat().st_size / 1024
        print(f"OK: saved {OUTPUT_PATH} ({size_kb:.0f} KB)")
    except Exception as exc:
        print("FAILED:", exc)
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
