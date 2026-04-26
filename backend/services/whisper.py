"""Whisper audio transcription — direct OpenAI SDK."""
import os
import logging
import subprocess
import tempfile
import traceback
from typing import Optional
import openai
from services.whatsapp import download_whatsapp_media

logger = logging.getLogger("WhisperService")

WHISPER_PROMPT = (
    "Tu es un expert en langues beninoises et africaines. "
    "Extrais les donnees de voyage: villes, destinations, dates, prix. "
    "Langues: Francais, Fon, Yoruba, Anglais, Hausa. "
    "Paris, Cotonou, Dakar, Abidjan sont toujours des destinations de voyage."
)


def _get_api_key() -> Optional[str]:
    """Get OpenAI API key — try OPENAI_API_KEY first, then EMERGENT_LLM_KEY."""
    key = os.environ.get("OPENAI_API_KEY") or os.environ.get("EMERGENT_LLM_KEY")
    return key if key else None


async def _download_telegram_audio(file_id: str) -> Optional[bytes]:
    """Download audio from Telegram Bot API."""
    from config import TELEGRAM_BOT_TOKEN
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == 'your_bot_token_here':
        return None
    import httpx
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getFile",
                params={"file_id": file_id})
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
    """Convert OGG/opus to MP3 using ffmpeg subprocess. Returns MP3 path."""
    ogg_path = None
    mp3_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp.write(ogg_bytes)
            ogg_path = tmp.name
        mp3_path = ogg_path.replace(".ogg", ".mp3")
        result = subprocess.run(
            ["ffmpeg", "-i", ogg_path, "-ar", "16000", "-ac", "1", "-b:a", "64k", mp3_path, "-y"],
            capture_output=True, timeout=30)
        if result.returncode != 0:
            logger.error(f"[Whisper] ffmpeg error: {result.stderr.decode()[:200]}")
            return None
        logger.info(f"[Whisper] OGG->MP3 OK: {os.path.getsize(mp3_path)} bytes")
        return mp3_path
    except Exception as e:
        logger.error(f"[Whisper] OGG->MP3 conversion failed: {e}")
        if mp3_path and os.path.exists(mp3_path):
            os.unlink(mp3_path)
        return None
    finally:
        if ogg_path and os.path.exists(ogg_path):
            os.unlink(ogg_path)


async def _transcribe_bytes(audio_bytes: bytes, file_ext: str = "mp3") -> str:
    """Transcribe audio bytes using OpenAI Whisper API directly."""
    api_key = _get_api_key()
    if not api_key:
        logger.error("[Whisper] No API key (OPENAI_API_KEY or EMERGENT_LLM_KEY)")
        return ""

    logger.info(f"[Whisper] Key found: {api_key[:12]}...")
    logger.info(f"[Whisper] Audio size: {len(audio_bytes)} bytes, format: {file_ext}")

    client = openai.OpenAI(api_key=api_key)

    with tempfile.NamedTemporaryFile(suffix=f".{file_ext}", delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        logger.info("[Whisper] Sending to OpenAI Whisper-1...")
        with open(tmp_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="text",
                prompt=WHISPER_PROMPT
            )
        text = transcript.strip() if isinstance(transcript, str) else transcript.text.strip()
        logger.info(f"[Whisper] Transcription OK: '{text[:100]}'")
        return text
    except openai.AuthenticationError as e:
        logger.error(f"[Whisper] Auth FAILED — invalid key: {e}")
        return ""
    except openai.RateLimitError as e:
        logger.error(f"[Whisper] Rate limit exceeded: {e}")
        return ""
    except openai.APIConnectionError as e:
        logger.error(f"[Whisper] Connection error: {e}")
        return ""
    except Exception as e:
        logger.error(f"[Whisper] Unexpected error: {type(e).__name__}: {e}")
        logger.error(traceback.format_exc())
        return ""
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


async def transcribe_audio(audio_id: str) -> Optional[str]:
    """Download and transcribe audio from WhatsApp or Telegram."""
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

    # Convert OGG to MP3
    mp3_path = _convert_ogg_to_mp3(audio_bytes)
    if not mp3_path:
        # Try transcribing raw bytes as fallback
        logger.warning("[Whisper] OGG conversion failed, trying raw audio...")
        result = await _transcribe_bytes(audio_bytes, "ogg")
        return result if result else None

    try:
        with open(mp3_path, "rb") as f:
            mp3_bytes = f.read()
        result = await _transcribe_bytes(mp3_bytes, "mp3")
        return result if result else None
    finally:
        if os.path.exists(mp3_path):
            os.unlink(mp3_path)
