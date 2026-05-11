"""
Generate the Tennant TMS promotional video using Sora 2.
Runs in background; output goes to /app/frontend/public/promo.mp4
"""
import os
import sys
import time
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(''))
from emergentintegrations.llm.openai.video_generation import OpenAIVideoGeneration

load_dotenv('/app/backend/.env')

PROMPT = (
    "Cinematic promotional video for Tennant Company, a Minnesota-based maker of industrial floor scrubbers. "
    "Opens with a sweeping aerial shot over an industrial complex at dawn — three pin-lit manufacturing facilities glowing on a dark map of the United States, "
    "with neon cyan flight paths arcing between Louisville, Holland, and Golden Valley. "
    "Cut to a futuristic mission-control dashboard with holographic charts, a live shipment map dotted with pulsing cyan markers, "
    "and tablets showing freight bills auto-auditing in real time. "
    "Close on a Tennant T16 AMR floor scrubber rolling through a polished warehouse, "
    "then transition to a driver in a truck cab tapping a smartphone, GPS pin glowing. "
    "Color grade: deep navy and electric cyan, subtle film grain, motion blur, lens flares. "
    "Mood: confident, precision-engineered, command-center energy. Cinematic, 16:9, smooth camera moves."
)

def main():
    print(f"[{time.strftime('%H:%M:%S')}] Starting Sora 2 generation...", flush=True)
    video_gen = OpenAIVideoGeneration(api_key=os.environ['EMERGENT_LLM_KEY'])
    video_bytes = video_gen.text_to_video(
        prompt=PROMPT,
        model="sora-2",
        size="1280x720",
        duration=4,
        max_wait_time=600,
    )
    if video_bytes:
        output = '/app/frontend/public/promo.mp4'
        video_gen.save_video(video_bytes, output)
        size_mb = os.path.getsize(output) / 1024 / 1024
        print(f"[{time.strftime('%H:%M:%S')}] OK: saved {output} ({size_mb:.2f} MB)", flush=True)
    else:
        print(f"[{time.strftime('%H:%M:%S')}] FAILED: no video bytes returned", flush=True)

if __name__ == "__main__":
    main()
