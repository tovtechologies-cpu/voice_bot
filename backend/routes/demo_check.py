"""Demo readiness check endpoint."""
import os
import logging
import subprocess
import httpx
from fastapi import APIRouter
from config import (
    EMERGENT_LLM_KEY, DUFFEL_API_KEY, WHATSAPP_TOKEN, WHATSAPP_PHONE_ID,
    TELEGRAM_BOT_TOKEN, get_duffel_mode
)
from database import db

router = APIRouter()
logger = logging.getLogger("DemoCheck")


@router.get("/demo-check")
async def demo_check():
    """Check readiness of all systems for demo."""
    results = {}

    # Whisper (needs OPENAI_API_KEY or EMERGENT_LLM_KEY)
    whisper_key = os.environ.get("OPENAI_API_KEY") or EMERGENT_LLM_KEY
    results["whisper"] = "ok" if whisper_key else "error"
    results["whisper_version"] = "whisper-1 (cloud)"

    # ffmpeg
    try:
        r = subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
        results["ffmpeg"] = "ok" if r.returncode == 0 else "error"
    except Exception:
        results["ffmpeg"] = "error"

    # OCR (pytesseract or Pillow)
    try:
        from PIL import Image
        results["ocr"] = "ok"
    except Exception:
        results["ocr"] = "error"

    # gTTS
    try:
        from gtts import gTTS
        results["gtts"] = "ok"
    except Exception:
        results["gtts"] = "error"

    # Telegram webhook
    if TELEGRAM_BOT_TOKEN and TELEGRAM_BOT_TOKEN != 'your_bot_token_here':
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getWebhookInfo")
                info = resp.json().get("result", {})
                url = info.get("url", "")
                results["telegram_webhook"] = "ok" if url else "not_set"
                results["telegram_webhook_url"] = url
        except Exception:
            results["telegram_webhook"] = "error"
    else:
        results["telegram_webhook"] = "not_configured"

    # WhatsApp
    if WHATSAPP_TOKEN and len(WHATSAPP_TOKEN) > 20:
        results["whatsapp_webhook"] = "ok"
    else:
        results["whatsapp_webhook"] = "not_configured"

    # Duffel
    results["duffel"] = get_duffel_mode().lower()

    # Claude AI
    results["claude"] = "ok" if (EMERGENT_LLM_KEY or os.environ.get("OPENAI_API_KEY")) else "error"

    # MongoDB
    try:
        await db.command("ping")
        results["mongodb"] = "ok"
    except Exception:
        results["mongodb"] = "error"

    # Languages
    results["languages_supported"] = ["fr", "en", "fon", "yoruba", "hausa", "wolof", "swahili"]

    # Demo ready?
    critical = [results.get("whisper"), results.get("ffmpeg"), results.get("claude"), results.get("mongodb")]
    results["demo_ready"] = all(v == "ok" for v in critical)

    return results
