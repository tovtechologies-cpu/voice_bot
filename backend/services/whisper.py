"""Whisper audio transcription service — fixed pipeline."""
import os
import logging
import tempfile
from typing import Optional
from config import EMERGENT_LLM_KEY
from services.whatsapp import download_whatsapp_media

logger = logging.getLogger("WhisperService")


async def _download_telegram_audio(file_id: str) -> Optional[bytes]:
    """Download audio from Telegram Bot API."""
    from config import TELEGRAM_BOT_TOKEN
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == 'your_bot_token_here':
        return None
    import httpx
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getFile", params={"file_id": file_id})
            if resp.status_code != 200:
                return None
            file_path = resp.json().get("result", {}).get("file_path")
            if not file_path:
                return None
            dl = await client.get(f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}")
            if dl.status_code == 200:
                return dl.content
    except Exception as e:
        logger.error(f"Telegram audio download error: {e}")
    return None


def _convert_ogg_to_mp3(ogg_bytes: bytes) -> Optional[str]:
    """Convert OGG/opus audio to MP3 using pydub+ffmpeg. Returns MP3 file path."""
    ogg_path = None
    mp3_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp.write(ogg_bytes)
            ogg_path = tmp.name
        mp3_path = ogg_path.replace(".ogg", ".mp3")
        from pydub import AudioSegment
        audio = AudioSegment.from_ogg(ogg_path)
        audio.export(mp3_path, format="mp3", bitrate="64k")
        logger.info(f"[Whisper] OGG->MP3 conversion OK ({len(ogg_bytes)} bytes)")
        return mp3_path
    except Exception as e:
        logger.error(f"[Whisper] OGG->MP3 conversion failed: {e}")
        if mp3_path and os.path.exists(mp3_path):
            os.unlink(mp3_path)
        return None
    finally:
        if ogg_path and os.path.exists(ogg_path):
            os.unlink(ogg_path)


async def transcribe_audio(audio_id: str) -> Optional[str]:
    """Transcribe audio from WhatsApp or Telegram using Emergent Whisper."""
    if not EMERGENT_LLM_KEY:
        logger.error("[Whisper] No EMERGENT_LLM_KEY configured")
        return None

    # Download audio
    if audio_id.startswith("tg:"):
        real_id = audio_id[3:]
        audio_bytes = await _download_telegram_audio(real_id)
    else:
        audio_bytes = await download_whatsapp_media(audio_id)

    if not audio_bytes:
        logger.error(f"[Whisper] Failed to download audio: {audio_id[:20]}")
        return None

    logger.info(f"[Whisper] Audio downloaded: {len(audio_bytes)} bytes")

    # Convert OGG to MP3 (Whisper API accepts mp3 but not ogg)
    mp3_path = _convert_ogg_to_mp3(audio_bytes)
    if not mp3_path:
        return None

    try:
        from emergentintegrations.llm.openai import OpenAISpeechToText
        stt = OpenAISpeechToText(api_key=EMERGENT_LLM_KEY)
        with open(mp3_path, "rb") as audio_file:
            response = await stt.transcribe(
                file=audio_file,
                model="whisper-1",
                response_format="json",
                prompt="Voyage, vol, avion, Cotonou, Paris, Dakar, billet, reservation. Fon, Yoruba, Francais, Anglais."
            )
        transcribed = response.text.strip()
        logger.info(f"[Whisper] Transcription: '{transcribed[:100]}'")
        return transcribed if transcribed else None
    except Exception as e:
        logger.error(f"[Whisper] Transcription error: {e}")
        return None
    finally:
        if os.path.exists(mp3_path):
            os.unlink(mp3_path)
