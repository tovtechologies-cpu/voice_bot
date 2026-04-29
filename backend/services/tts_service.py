"""OpenAI TTS (Text-to-Speech) service — voice responses."""
import os
import re
import logging
import tempfile
import openai

logger = logging.getLogger("TTSService")


class TTSService:
    def __init__(self):
        self.api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("EMERGENT_LLM_KEY")
        self.voice = os.environ.get("TTS_VOICE", "nova")
        self.enabled = os.environ.get("TTS_ENABLED", "true").lower() == "true"
        if self.api_key and self.enabled:
            self.client = openai.OpenAI(api_key=self.api_key)
            logger.info(f"[TTS] Ready — voice: {self.voice}")
        else:
            self.client = None
            logger.info(f"[TTS] Disabled (enabled={self.enabled}, key={'set' if self.api_key else 'missing'})")

    async def synthesize(self, text: str) -> bytes:
        """Convert text to speech MP3 bytes using OpenAI TTS."""
        if not self.enabled or not self.client:
            return b""
        clean = self._clean_for_speech(text)
        if not clean.strip() or len(clean) < 5:
            return b""
        # Limit length to avoid excessive API costs
        if len(clean) > 500:
            clean = clean[:500]
        try:
            logger.info(f"[TTS] Synthesizing: '{clean[:80]}'")
            response = self.client.audio.speech.create(
                model="tts-1",
                voice=self.voice,
                input=clean,
                response_format="mp3",
                speed=1.0
            )
            audio_bytes = response.content
            logger.info(f"[TTS] OK: {len(audio_bytes)} bytes")
            return audio_bytes
        except Exception as e:
            logger.error(f"[TTS] Error: {type(e).__name__}: {e}")
            return b""

    def _clean_for_speech(self, text: str) -> str:
        """Remove markdown/formatting for natural speech."""
        clean = re.sub(r'\*+', '', text)
        clean = re.sub(r'_+', '', clean)
        clean = re.sub(r'`+', '', clean)
        clean = re.sub(r'[━─]+', '. ', clean)
        clean = re.sub(r'\n+', '. ', clean)
        clean = re.sub(r'\s+', ' ', clean)
        return clean.strip()


tts_service = TTSService()
