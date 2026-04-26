"""Text-to-Speech service using gTTS — voice responses."""
import os
import logging
import tempfile
from typing import Optional
from config import TICKETS_DIR, APP_BASE_URL

logger = logging.getLogger("TTSService")


def _tts_lang_code(lang: str) -> str:
    """Map app language codes to gTTS language codes."""
    mapping = {"fr": "fr", "en": "en", "wo": "fr", "fon": "fr", "yo": "fr", "ha": "fr", "sw": "sw"}
    return mapping.get(lang, "fr")


async def text_to_speech(text: str, lang: str = "fr", filename_prefix: str = "voice") -> Optional[str]:
    """Convert text to MP3 audio. Returns the filename (saved in TICKETS_DIR)."""
    try:
        from gtts import gTTS
        import uuid
        tts_lang = _tts_lang_code(lang)
        tts = gTTS(text=text, lang=tts_lang, slow=False)
        fname = f"{filename_prefix}_{uuid.uuid4().hex[:8]}.mp3"
        fpath = str(TICKETS_DIR / fname)
        tts.save(fpath)
        logger.info(f"[TTS] Generated: {fname} ({len(text)} chars, lang={tts_lang})")
        return fname
    except Exception as e:
        logger.error(f"[TTS] Error: {e}")
        return None


async def send_voice_response(phone: str, text: str, lang: str = "fr"):
    """Generate TTS audio and send as audio message."""
    fname = await text_to_speech(text, lang)
    if not fname:
        return

    audio_url = f"{APP_BASE_URL}/api/tickets/{fname}"

    from services.channel import get_channel
    channel = get_channel(phone)

    if channel == "telegram":
        await _send_telegram_voice(phone, audio_url)
    else:
        await _send_whatsapp_audio(phone, audio_url)


async def _send_whatsapp_audio(phone: str, audio_url: str):
    """Send audio message via WhatsApp Cloud API."""
    from config import WHATSAPP_PHONE_ID, WHATSAPP_TOKEN, WHATSAPP_BASE_URL, WHATSAPP_API_VERSION
    from utils.helpers import normalize_phone
    import httpx

    if not WHATSAPP_TOKEN or WHATSAPP_TOKEN == 'your_token_here':
        logger.info(f"[TTS SIM] Audio to {phone[-4:]}: {audio_url}")
        return

    normalized = normalize_phone(phone)
    url = f"{WHATSAPP_BASE_URL}/{WHATSAPP_API_VERSION}/{WHATSAPP_PHONE_ID}/messages"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json={
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": normalized,
                "type": "audio",
                "audio": {"link": audio_url}
            }, headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"})
            if resp.status_code == 200:
                logger.info(f"[TTS] WhatsApp audio sent to {phone[-4:]}")
            else:
                logger.warning(f"[TTS] WhatsApp audio failed: {resp.status_code}")
    except Exception as e:
        logger.error(f"[TTS] WhatsApp audio error: {e}")


async def _send_telegram_voice(phone: str, audio_url: str):
    """Send voice message via Telegram Bot API."""
    from services.telegram import get_chat_id
    from config import TELEGRAM_BOT_TOKEN
    import httpx

    chat_id = get_chat_id(phone)
    if not chat_id or not TELEGRAM_BOT_TOKEN:
        logger.info(f"[TTS SIM] Telegram voice to {phone[-4:]}: {audio_url}")
        return

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVoice",
                json={"chat_id": chat_id, "voice": audio_url})
            if resp.status_code == 200:
                logger.info(f"[TTS] Telegram voice sent to {phone[-4:]}")
    except Exception as e:
        logger.error(f"[TTS] Telegram voice error: {e}")
