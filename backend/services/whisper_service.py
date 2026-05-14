import logging
from services.whisper import _transcribe_bytes

logger = logging.getLogger("WhisperService")

class WhisperService:
    async def transcribe(self, audio_bytes: bytes, file_ext: str = "mp3") -> str:
        """Transcribe audio bytes using Whisper."""
        try:
            return await _transcribe_bytes(audio_bytes, file_ext)
        except Exception as e:
            logger.error(f"[WhisperService] Error: {e}")
            return ""

whisper_service = WhisperService()
