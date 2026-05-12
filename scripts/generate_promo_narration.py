"""Generate a narration MP3 for the Tennant TMS launch promo video using
OpenAI's TTS via the Emergent universal LLM key.

The narration mirrors the SCENES list in build_promo_with_screens.py so each
scene gets a matching voice-over line. Final MP3 lands at:
    /tmp/tms_promo_v2/narration.mp3

This script is invoked automatically by build_promo_with_screens.py if the
narration file does not yet exist.

Run standalone:
    python3 /app/scripts/generate_promo_narration.py
"""
import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Make sure we read backend/.env which carries EMERGENT_LLM_KEY
load_dotenv("/app/backend/.env")

from emergentintegrations.llm.openai import OpenAITextToSpeech

OUT = Path("/tmp/tms_promo_v2/narration.mp3")
OUT.parent.mkdir(parents=True, exist_ok=True)

# 18 scenes + intro/outro = ~20 lines. Each scene ~3.7s of video; we keep
# narration lines tight (10-14 words each) so the voice fits cleanly inside
# the scene without crowding the music bed.
SCRIPT = (
    "Tennant Transportation Management System. Built for the team's day, "
    "every shift. "
    "Command Center: one screen replaces the morning email blast. Live map, "
    "weather, traffic, and KPIs ready before stand-up. "
    "Truckload Booking Sheet: the team's shared live board. Click any cell, "
    "auto-saves to the cloud, no more emailed spreadsheets. "
    "Shipments: edit in place, drag to reorder, soft-delete with full audit. "
    "Live Tracking: pulsing markers for every truck, ocean container, and air "
    "lane on one interactive map. "
    "Equipment and Yard Status: drop today's report, instant door map, dwell "
    "metrics, and stale-trailer alerts. "
    "Carrier Rates: eighty plus rate decks, side-by-side comparison, cube and "
    "dunnage already baked in. "
    "Specialty Carriers: Logix, ArcBest Panther, Fastfrate, and Ryan tracked "
    "with live status and contacts. "
    "Inbound Routing Guide: distribute the latest version to every supplier "
    "in seconds, with delivery receipts. "
    "Documents: every BOL on file with version history, amendment trail, and "
    "one-click email. "
    "Trade Compliance: every Incoterm, Section 301 list, USMCA rule, and FTZ "
    "lot at your fingertips. "
    "Supplier Sourcing: track risk, spend, single-source exposure, and add "
    "new vendors in seconds. "
    "Machine Catalog: thirty-five live Tennant models with photos, specs, and "
    "linked shipments. "
    "Power BI: dashboards embed natively for finance, ops, and "
    "executive review. "
    "SharePoint: every contract, SOP, and audit folder one click from the TMS. "
    "Microsoft Copilot: ask anything, draft anything, summarize anything, "
    "right inside the workspace. "
    "KPI Reports: forty-five carrier scorecard metrics with auto-emailed "
    "weekly summaries. "
    "Driver Registry: CDL endorsements, medical card expiries, trailer "
    "inspections, all in one place. "
    "Arcade: Connect 4 tournaments and chess matches for the team's lunch "
    "break. "
    "Tennant TMS: sign in, see the map, book the load. The platform handles "
    "the rest."
)


async def main():
    key = os.environ.get("EMERGENT_LLM_KEY")
    if not key:
        print("ERROR: EMERGENT_LLM_KEY missing in /app/backend/.env", file=sys.stderr)
        sys.exit(1)

    tts = OpenAITextToSpeech(api_key=key)
    print(f"[narration] generating with tts-1-hd / voice=onyx ({len(SCRIPT)} chars)...")
    audio_bytes = await tts.generate_speech(
        text=SCRIPT,
        model="tts-1-hd",
        voice="onyx",
        speed=1.05,
        response_format="mp3",
    )
    OUT.write_bytes(audio_bytes)
    size_kb = OUT.stat().st_size // 1024
    print(f"[narration] wrote {OUT}  ({size_kb} KB)")


if __name__ == "__main__":
    asyncio.run(main())
