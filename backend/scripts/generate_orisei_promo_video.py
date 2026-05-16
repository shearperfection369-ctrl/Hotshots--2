"""Regenerate the Orisei launch promo via Sora 2 — investor-grade brokerage pitch.

Riveting 12-second presentation built around:
  - Oliver's 13-year tenure in shipping
  - Precision & operator-grade discipline
  - Calafia + griffin Orisei branding
  - Tight, confidence-building call to action

Run: python3 /app/backend/scripts/generate_orisei_promo_video.py
Saves: /app/frontend/public/promo.mp4
"""
import os
import sys
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(""))
from emergentintegrations.llm.openai.video_generation import OpenAIVideoGeneration

load_dotenv("/app/backend/.env")

PROMPT = (
    "Cinematic 12-second freight brokerage promotional video for ORISEI FREIGHT "
    "SOLUTIONS. Premium documentary-style color grading, deep navy and gold leaf "
    "palette throughout. Smooth, deliberate camera moves — no jump cuts.\n\n"

    "0–2 sec: Aerial shot at golden hour over a fleet of 18-wheeler trucks rolling "
    "in formation down a Minnesota interstate, sunlight glinting off chrome.\n\n"

    "2–4 sec: Close-up on the calloused hands of a seasoned freight veteran (the "
    "owner) signing a Bill of Lading on a tablet. Wedding band visible. Behind him, "
    "warehouse floor, blurred forklifts, controlled chaos.\n\n"

    "4–6 sec: Cut to a high-tech operations command deck. Wall of monitors showing "
    "live load boards, lane maps, ticking margin numbers — all in deep navy with "
    "glowing gold leaf accents. A dispatcher's silhouette in the foreground.\n\n"

    "6–8 sec: A heraldic golden griffin medallion (Queen Calafia mounted on a "
    "winged griffin) rotates slowly into frame against deep navy, catching the "
    "light. Subtle particle dust drifts past.\n\n"

    "8–10 sec: Wide shot — the same fleet of trucks at dusk, headlights blazing, "
    "moving as one disciplined column. A slow zoom into the lead trailer where the "
    "Calafia gold-on-navy Orisei emblem is painted, sharp and proud.\n\n"

    "10–12 sec: Final hold — the ORISEI wordmark in tall gold serif fades up "
    "against deep navy. Below it, in smaller monospace gold caps: "
    "'13 YEARS · OPERATOR-GRADE FREIGHT.' Hold for 1.5 seconds, then a quick "
    "gold-leaf shimmer accent across the wordmark.\n\n"

    "Mood: confident, precise, premium. No music dialog overlay. No on-screen "
    "text other than the final 'ORISEI · 13 YEARS · OPERATOR-GRADE FREIGHT' "
    "wordmark in the last 2 seconds. Color palette strictly limited to deep "
    "navy (#0E3A6B), gold leaf (#C9A24A), warm sunlight, and asphalt blacks."
)


def main() -> None:
    out = "/app/frontend/public/promo.mp4"
    print(f"Generating Orisei brokerage promo to {out} ...")
    gen = OpenAIVideoGeneration(api_key=os.environ["EMERGENT_LLM_KEY"])
    video_bytes = gen.text_to_video(
        prompt=PROMPT, model="sora-2", size="1280x720", duration=12,
        max_wait_time=900,
    )
    if not video_bytes:
        print("Generation failed.")
        sys.exit(1)
    gen.save_video(video_bytes, out)
    print(f"Saved {os.path.getsize(out):,} bytes to {out}")


if __name__ == "__main__":
    main()
