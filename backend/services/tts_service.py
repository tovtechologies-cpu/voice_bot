"""OpenAI TTS (Text-to-Speech) service — voice responses."""
import os
import re
import logging
import tempfile
import openai

logger = logging.getLogger("TTSService")


def _is_placeholder(key):
    if not key:
        return True
    low = key.strip().lower()
    return low.startswith("your_") or "_here" in low or low in ("changeme", "placeholder", "todo", "")


class TTSService:
    def __init__(self):
        primary = os.environ.get("OPENAI_API_KEY")
        fallback = os.environ.get("EMERGENT_LLM_KEY")
        self.api_key = primary if not _is_placeholder(primary) else (fallback if not _is_placeholder(fallback) else None)
        self.voice = os.environ.get("TTS_VOICE", "nova")
        self.enabled = os.environ.get("TTS_ENABLED", "true").lower() == "true"
        if self.api_key and self.enabled:
            self.client = openai.OpenAI(api_key=self.api_key)
            logger.info(f"[TTS] Ready — voice: {self.voice}")
        else:
            self.client = None
            logger.info(f"[TTS] Disabled (enabled={self.enabled}, key={'set' if self.api_key else 'missing'})")

    async def synthesize(self, text: str) -> bytes:
        """Convert text to speech MP3 bytes using Gemini or OpenAI TTS."""
        if not self.enabled:
            return b""

        clean = self._clean_for_speech(text)
        if not clean.strip() or len(clean) < 5:
            return b""

        # Limit length to avoid excessive API costs
        if len(clean) > 500:
            clean = clean[:500]

        # Try Gemini Live TTS first (better quality)
        try:
            from services.gemini_live_service import (
                gemini_live_service
            )
            if gemini_live_service.api_key:
                audio = await (
                    gemini_live_service.text_to_speech(clean)
                )
                if audio:
                    logger.info(
                        f"[TTS] Gemini: {len(audio)} bytes"
                    )
                    return audio
        except Exception as e:
            logger.warning(f"[TTS] Gemini failed: {e}")

        # Fallback to OpenAI TTS
        return await self._openai_tts(clean)

    async def _openai_tts(self, clean: str) -> bytes:
        """Fallback to OpenAI TTS."""
        if not self.client:
            return b""
        try:
            logger.info(f"[TTS] Synthesizing with OpenAI: '{clean[:80]}'")
            response = self.client.audio.speech.create(
                model="tts-1",
                voice=self.voice,
                input=clean,
                response_format="mp3",
                speed=1.0
            )
            audio_bytes = response.content
            logger.info(f"[TTS] OK (OpenAI): {len(audio_bytes)} bytes")
            return audio_bytes
        except Exception as e:
            logger.error(f"[TTS] OpenAI Error: {type(e).__name__}: {e}")
            return b""

    def _clean_for_speech(self, text: str) -> str:
        """Remove markdown/formatting for natural speech."""
        # Remove markdown
        clean = re.sub(r'\*+', '', text)
        clean = re.sub(r'_+', '', clean)
        clean = re.sub(r'`+', '', clean)

        # Handle flight specific symbols
        clean = clean.replace("->", " vers ")

        # Expand common IATA codes for natural speech
        iata_map = {
            r'\bCOO\b': 'Cotonou',
            r'\bCDG\b': 'Paris',
            r'\bDSS\b': 'Dakar',
            r'\bABJ\b': 'Abidjan',
            r'\bACC\b': 'Accra',
            r'\bLOS\b': 'Lagos',
            r'\bLFW\b': 'Lomé',
            r'\bOUA\b': 'Ouagadougou',
            r'\bBKO\b': 'Bamako',
            r'\bNIM\b': 'Niamey',
            r'\bORY\b': 'Paris Orly',
            r'\bLHR\b': 'Londres',
        }
        for code, city in iata_map.items():
            clean = re.sub(code, city, clean)

        # Handle currencies (handle cases like 100EUR without space)
        clean = re.sub(r'(\d)EUR\b', r'\1 euros', clean)
        clean = re.sub(r'\bEUR\b', ' euros ', clean)
        clean = re.sub(r'(\d)XOF\b', r'\1 francs CFA', clean)
        clean = re.sub(r'\bXOF\b', ' francs CFA ', clean)

        # Clean up whitespace and newlines
        clean = re.sub(r'[━─]+', '. ', clean)
        clean = re.sub(r'\n+', '. ', clean)
        clean = re.sub(r'\s+', ' ', clean)

        return clean.strip()


tts_service = TTSService()
