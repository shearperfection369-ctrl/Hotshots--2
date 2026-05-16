"""One-shot: generate the Orisei Freight Solutions logo via Gemini Nano Banana.

Run with:
    cd /app/backend && python scripts/generate_orisei_logo.py
"""
import asyncio
import base64
import os
from pathlib import Path

from dotenv import load_dotenv
from emergentintegrations.llm.chat import LlmChat, UserMessage


PROMPT = (
    "A clean, premium vector-style logo for 'Orisei Freight Solutions LLC', a Minnesota-based "
    "freight brokerage. The design is inspired by ancient Moorish geometry: an eight-pointed "
    "Moorish star (Khatim Sulayman / Seal of Solomon) interlaced with subtle North African "
    "tessellation patterns, evoking science, navigation, and trade routes. At the center of "
    "the star, a stylized arrow or freight chevron pointing forward (representing movement of "
    "goods). Color palette: deep azure (#0E3A6B) and burnished gold (#C9A24A) on a transparent "
    "background. The mark must be perfectly symmetrical, readable at 32x32px favicon size, "
    "and equally elegant at 2048x2048 hero size. No text, no wordmark, no shadow, no gradient "
    "beyond two subtle inner tones. Crisp vector edges, white space generous, balanced negative "
    "space, square 1:1 composition. Reference aesthetic: Alhambra tilework precision + modern "
    "fintech minimalism (think Stripe, Linear). Output: standalone glyph, ready for use as "
    "the official brand mark."
)


async def main() -> None:
    load_dotenv()
    api_key = os.getenv("EMERGENT_LLM_KEY")
    if not api_key:
        raise SystemExit("EMERGENT_LLM_KEY missing from backend/.env")

    chat = (
        LlmChat(api_key=api_key, session_id="orisei-logo-v1",
                system_message="You are a senior brand designer specializing in geometric and Moorish-inspired logomarks.")
        .with_model("gemini", "gemini-3.1-flash-image-preview")
        .with_params(modalities=["image", "text"])
    )
    msg = UserMessage(text=PROMPT)
    text, images = await chat.send_message_multimodal_response(msg)
    print(f"Model said: {text[:140] if text else '(no text)'}")

    out_dir = Path("/app/frontend/public/brand")
    out_dir.mkdir(parents=True, exist_ok=True)

    for i, img in enumerate(images or []):
        png_bytes = base64.b64decode(img["data"])
        target = out_dir / ("orisei_logo.png" if i == 0 else f"orisei_logo_alt_{i}.png")
        target.write_bytes(png_bytes)
        print(f"Saved {target} ({len(png_bytes)/1024:.1f} KB)")

    if not images:
        raise SystemExit("Nano Banana returned no images")


if __name__ == "__main__":
    asyncio.run(main())
