"""Whisper audio transcription service."""
import os
import logging
from typing import Optional
from config import EMERGENT_LLM_KEY
from services.whatsapp import download_whatsapp_media

logger = logging.getLogger("WhisperService")


async def transcribe_audio(audio_id: str) -> Optional[str]:
    try:
        from emergentintegrations.llm.openai import OpenAISpeechToText
        if not EMERGENT_LLM_KEY:
            logger.error("Whisper: No API key configured")
            return None
        audio_bytes = await download_whatsapp_media(audio_id)
        if not audio_bytes:
            logger.error(f"Whisper: Failed to download audio {audio_id}")
            return None
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp.write(audio_bytes)
            ogg_path = tmp.name
        mp3_path = ogg_path.replace(".ogg", ".mp3")
        try:
            from pydub import AudioSegment
            audio = AudioSegment.from_ogg(ogg_path)
            audio.export(mp3_path, format="mp3")
        except Exception as e:
            logger.error(f"Audio conversion error: {e}")
            os.unlink(ogg_path)
            return None
        finally:
            if os.path.exists(ogg_path):
                os.unlink(ogg_path)
        try:
            stt = OpenAISpeechToText(api_key=EMERGENT_LLM_KEY)
            with open(mp3_path, "rb") as audio_file:
                response = await stt.transcribe(file=audio_file, model="whisper-1", response_format="json")
            transcribed = response.text.strip()
            logger.info(f"Whisper transcription: '{transcribed[:100]}'")
            return transcribed if transcribed else None
        finally:
            if os.path.exists(mp3_path):
                os.unlink(mp3_path)
    except Exception as e:
        logger.error(f"Whisper transcription error: {e}")
        return None
