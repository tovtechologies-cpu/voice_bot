import asyncio
import base64
import json
import logging
import os
import websockets
from typing import AsyncGenerator

logger = logging.getLogger("GeminiLive")

GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")
GEMINI_MODEL = "gemini-2.0-flash-live-001"
GEMINI_WS_URL = (
    f"wss://generativelanguage.googleapis.com/ws/"
    f"google.ai.generativelanguage.v1alpha."
    f"GenerativeService.BidiGenerateContent"
    f"?key={GEMINI_API_KEY}"
)

SYSTEM_PROMPT = """
Tu es Travelioo, un agent de voyage IA.
Tu parles en français par défaut.
Tu comprends aussi le Fon, le Yoruba,
l'Anglais, le Hausa et le Wolof.
Tu aides les utilisateurs à réserver
des vols depuis l'Afrique de l'Ouest.
Sois concis, chaleureux et professionnel.
Quand l'utilisateur mentionne une destination
et des dates, confirme et propose de chercher.
"""

class GeminiLiveService:
    def __init__(self):
        self.api_key = GEMINI_API_KEY
        if self.api_key:
            logger.info("[GeminiLive] Service ready")
        else:
            logger.error("[GeminiLive] GOOGLE_API_KEY missing!")

    async def transcribe_and_respond(
        self,
        audio_bytes: bytes,
        audio_format: str = "audio/webm",
        context: str = ""
    ) -> dict:
        """
        Send audio to Gemini Live and get:
        - transcription of what user said
        - text response
        - audio response bytes
        """
        if not self.api_key:
            return {
                "transcription": "",
                "response_text": "",
                "response_audio": b""
            }

        try:
            async with websockets.connect(
                GEMINI_WS_URL,
                additional_headers={
                    "Content-Type": "application/json"
                }
            ) as ws:

                # 1. Send setup message
                setup_msg = {
                    "setup": {
                        "model": f"models/{GEMINI_MODEL}",
                        "generation_config": {
                            "response_modalities": [
                                "AUDIO", "TEXT"
                            ],
                            "speech_config": {
                                "voice_config": {
                                    "prebuilt_voice_config": {
                                        "voice_name": "Aoede"
                                        # Options: Puck, Charon, Kore,
                                        # Fenrir, Aoede
                                        # Aoede = warm female French voice
                                    }
                                }
                            }
                        },
                        "system_instruction": {
                            "parts": [{
                                "text": SYSTEM_PROMPT + (
                                    f"\n\nContexte conversation:\n{context}"
                                    if context else ""
                                )
                            }]
                        }
                    }
                }
                await ws.send(json.dumps(setup_msg))

                # Wait for setup complete
                setup_response = await ws.recv()
                logger.info("[GeminiLive] Setup complete")

                # 2. Send audio data
                audio_b64 = base64.b64encode(
                    audio_bytes
                ).decode()

                audio_msg = {
                    "realtimeInput": {
                        "mediaChunks": [{
                            "mimeType": audio_format,
                            "data": audio_b64
                        }]
                    }
                }
                await ws.send(json.dumps(audio_msg))

                # 3. Signal end of turn
                end_msg = {
                    "clientContent": {
                        "turns": [{
                            "role": "user",
                            "parts": []
                        }],
                        "turnComplete": True
                    }
                }
                await ws.send(json.dumps(end_msg))

                # 4. Collect response
                transcription = ""
                response_text = ""
                response_audio_chunks = []

                async for raw_msg in ws:
                    msg = json.loads(raw_msg)

                    # Extract transcription
                    if "serverContent" in msg:
                        content = msg["serverContent"]

                        # Get model turn
                        model_turn = content.get(
                            "modelTurn", {}
                        )
                        for part in model_turn.get(
                            "parts", []
                        ):
                            # Text response
                            if "text" in part:
                                response_text += part["text"]

                            # Audio response
                            if "inlineData" in part:
                                chunk = base64.b64decode(
                                    part["inlineData"]["data"]
                                )
                                response_audio_chunks.append(
                                    chunk
                                )

                        # Get input transcription
                        input_transcript = content.get(
                            "inputTranscription", {}
                        )
                        if input_transcript.get("text"):
                            transcription = input_transcript[
                                "text"
                            ]

                        # Check if turn complete
                        if content.get("turnComplete"):
                            break

                response_audio = b"".join(
                    response_audio_chunks
                )

                logger.info(
                    f"[GeminiLive] Transcription: "
                    f"'{transcription[:80]}'"
                )
                logger.info(
                    f"[GeminiLive] Response: "
                    f"'{response_text[:80]}'"
                )
                logger.info(
                    f"[GeminiLive] Audio: "
                    f"{len(response_audio)} bytes"
                )

                return {
                    "transcription": transcription,
                    "response_text": response_text,
                    "response_audio": response_audio
                }

        except Exception as e:
            logger.error(
                f"[GeminiLive] Error: "
                f"{type(e).__name__}: {e}"
            )
            return {
                "transcription": "",
                "response_text": "",
                "response_audio": b""
            }

    async def text_to_speech(
        self, text: str
    ) -> bytes:
        """Convert text to speech using Gemini."""
        if not self.api_key or not text:
            return b""

        try:
            async with websockets.connect(
                GEMINI_WS_URL
            ) as ws:
                setup_msg = {
                    "setup": {
                        "model": f"models/{GEMINI_MODEL}",
                        "generation_config": {
                            "response_modalities": ["AUDIO"],
                            "speech_config": {
                                "voice_config": {
                                    "prebuilt_voice_config": {
                                        "voice_name": "Aoede"
                                    }
                                }
                            }
                        }
                    }
                }
                await ws.send(json.dumps(setup_msg))
                await ws.recv()  # setup complete

                text_msg = {
                    "clientContent": {
                        "turns": [{
                            "role": "user",
                            "parts": [{"text": text}]
                        }],
                        "turnComplete": True
                    }
                }
                await ws.send(json.dumps(text_msg))

                audio_chunks = []
                async for raw in ws:
                    msg = json.loads(raw)
                    if "serverContent" in msg:
                        content = msg["serverContent"]
                        for part in content.get(
                            "modelTurn", {}
                        ).get("parts", []):
                            if "inlineData" in part:
                                chunk = base64.b64decode(
                                    part["inlineData"]["data"]
                                )
                                audio_chunks.append(chunk)
                        if content.get("turnComplete"):
                            break

                return b"".join(audio_chunks)

        except Exception as e:
            logger.error(f"[GeminiLive TTS] Error: {e}")
            return b""

gemini_live_service = GeminiLiveService()
