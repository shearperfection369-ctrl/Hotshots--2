"""Generate demo reel narration MP3s via OpenAI TTS (tts-1-hd, onyx)."""
import asyncio
import json
import os
import sys

sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
from emergentintegrations.llm.openai import OpenAITextToSpeech  # noqa: E402

SEGMENTS = [
    ("intro", "This is Hot Shot TMS. The AI-driven freight platform built by a working brokerage — not a software company."),
    ("hunter", "Meet the AI Load Hunter. It works the load boards twenty-four seven, scores every load against your lanes and your margin floor, and hands you a ranked list of money — with the reasoning to back it up."),
    ("automatch", "Found a load? Auto-Match scores your entire carrier pool in seconds — compliance, performance, and price — then tenders to the best fit in a single click."),
    ("liveops", "Every shipment lives on the Live Ops map. Real road routing, real E-T-As, and exceptions flagged before your customer ever has to call."),
    ("routeopt", "The Route Optimizer prices any lane on live road data — miles, fuel, and margin — so you quote in seconds, not spreadsheets."),
    ("sandbox", "And the Operational Sandbox simulates a full month of your brokerage — real diesel prices, real overhead — before you bet a single real dollar."),
    ("whitelabel", "Your clients get all of it under your own brand. Isolated workspace, your logo, your colors — live in thirty seconds."),
    ("outro", "Hot Shot TMS. Verified sell-ready, every single night. Book a demo — and watch it book a load, live."),
]


async def main():
    tts = OpenAITextToSpeech(api_key=os.getenv("EMERGENT_LLM_KEY"))
    os.makedirs("/app/demo_reel/vo", exist_ok=True)
    for name, text in SEGMENTS:
        audio = await tts.generate_speech(text=text, model="tts-1-hd", voice="onyx", speed=1.02)
        path = f"/app/demo_reel/vo/{name}.mp3"
        with open(path, "wb") as f:
            f.write(audio)
        print(f"OK {name}: {len(audio)}b")
    print(json.dumps([s[0] for s in SEGMENTS]))


asyncio.run(main())
