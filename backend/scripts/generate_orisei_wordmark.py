"""Generate the horizontal wordmark variant + favicon for Orisei Freight Solutions."""
import asyncio
import base64
import os
from pathlib import Path

from dotenv import load_dotenv
from emergentintegrations.llm.chat import LlmChat, UserMessage


WORDMARK_PROMPT = (
    "A premium horizontal wordmark logo lockup for 'Orisei Freight Solutions LLC'. "
    "On the left: a small Moorish eight-pointed star (Seal of Solomon) interlaced with "
    "tessellation, in burnished gold (#C9A24A) and deep azure (#0E3A6B). "
    "To the right of the star: the wordmark 'ORISEI' in a confident, geometric serif/sans hybrid "
    "(think Optima or Cormorant Infant), in deep azure, all-caps, generously tracked. "
    "Below 'ORISEI' in smaller, lighter sans-serif: 'FREIGHT SOLUTIONS'. "
    "Aspect ratio 3:1 (wide). White space on all sides. Transparent background. "
    "No tagline, no shadow, no glow, no gradient. Production-ready vector aesthetic. "
    "Aesthetic: Alhambra tilework precision meets contemporary luxury fintech."
)


async def main() -> None:
    load_dotenv()
    api_key = os.getenv("EMERGENT_LLM_KEY")
    chat = (LlmChat(api_key=api_key, session_id="orisei-wordmark-v1",
                    system_message="You are a senior brand designer specializing in luxury fintech wordmarks.")
            .with_model("gemini", "gemini-3.1-flash-image-preview")
            .with_params(modalities=["image", "text"]))
    text, images = await chat.send_message_multimodal_response(UserMessage(text=WORDMARK_PROMPT))
    print(f"Model said: {(text or '')[:140]}")
    out = Path("/app/frontend/public/brand")
    out.mkdir(parents=True, exist_ok=True)
    for i, img in enumerate(images or []):
        b = base64.b64decode(img["data"])
        target = out / ("orisei_wordmark.png" if i == 0 else f"orisei_wordmark_{i}.png")
        target.write_bytes(b)
        print(f"Saved {target} ({len(b)/1024:.1f} KB)")


if __name__ == "__main__":
    asyncio.run(main())
