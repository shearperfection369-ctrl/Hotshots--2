"""Generate Queen Calafia + griffin logo and wordmark via Gemini nano-banana.

Run: python3 /app/backend/scripts/generate_calafia_logo.py
"""
import asyncio
import base64
import os
from pathlib import Path

from PIL import Image
from dotenv import load_dotenv
from emergentintegrations.llm.chat import LlmChat, UserMessage

load_dotenv(Path("/app/backend/.env"))

BRAND_DIR = Path("/app/frontend/public/brand")
PDF_DIR = Path("/app/backend/routes")


async def generate(prompt: str, out: Path, session: str) -> None:
    print(f"→ {out.name}")
    chat = LlmChat(
        api_key=os.environ["EMERGENT_LLM_KEY"],
        session_id=session,
        system_message="You are a heraldic illustrator generating premium brand artwork.",
    )
    chat.with_model("gemini", "gemini-3.1-flash-image-preview").with_params(modalities=["image", "text"])
    _, images = await chat.send_message_multimodal_response(UserMessage(text=prompt))
    if not images:
        raise RuntimeError("No image returned from nano-banana")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(base64.b64decode(images[0]["data"]))
    print(f"  saved · {out.stat().st_size:,} bytes")


def downsample(src: Path, dst: Path, max_dim: int) -> None:
    img = Image.open(src).convert("RGB")
    img.thumbnail((max_dim, max_dim), Image.LANCZOS)
    img.save(dst, "PNG", optimize=True)
    print(f"  pdf-version · {dst.name} {img.size} · {dst.stat().st_size:,} bytes")


LOGO_PROMPT = (
    "Heraldic medallion emblem. Subject: Queen Calafia, the legendary Black "
    "warrior queen of the mythical island of California, depicted as a regal "
    "woman with a golden laurel/crown and ornate armor, mounted on the back "
    "of a powerful golden griffin (gryphon) with broad outstretched wings "
    "and an eagle's head. She raises a slender sword or spear toward the sky. "
    "Style: bold engraved-coin / heraldic crest illustration, symmetrical, "
    "premium minimalist line-work. Palette strictly limited to gold leaf "
    "(#C9A24A) for all line work and deep navy blue (#0E3A6B) for the "
    "circular background. Centered, perfectly round medallion. No text, no "
    "lettering, no banners. Suitable as a freight company emblem. "
    "High-contrast, clean vector-style illustration, transparent corners."
)

WORDMARK_PROMPT = (
    "Horizontal wordmark logo. The single word 'ORISEI' in a tall, sharp, "
    "engraved serif typeface, all caps, rendered in gold leaf (#C9A24A) on "
    "a deep navy blue (#0E3A6B) background. To the immediate left of the "
    "word, a small heraldic griffin head facing right in matching gold line "
    "work. Beneath the word, in smaller monospace caps with wide letter "
    "spacing, the line 'FREIGHT SOLUTIONS'. Banner aspect ratio, premium "
    "minimalist crest. No additional ornamentation."
)


async def main() -> None:
    await generate(LOGO_PROMPT, BRAND_DIR / "orisei_logo.png", "calafia-emblem")
    await generate(WORDMARK_PROMPT, BRAND_DIR / "orisei_wordmark.png", "calafia-wordmark")
    downsample(BRAND_DIR / "orisei_logo.png", PDF_DIR / "_orisei_logo_pdf.png", 300)
    downsample(BRAND_DIR / "orisei_wordmark.png", PDF_DIR / "_orisei_wordmark_pdf.png", 600)


if __name__ == "__main__":
    asyncio.run(main())
