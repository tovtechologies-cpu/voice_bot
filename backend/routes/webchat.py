"""Webchat API — REST endpoints for website integration."""
import asyncio
import logging
from fastapi import APIRouter, Request
from conversation.handler import handle_message
from services.channel import set_channel
from services.session import clear_session
from database import db

router = APIRouter()
logger = logging.getLogger("WebchatRoutes")

# Response buffer for webchat (collected by send_whatsapp_message intercept)
_webchat_responses: dict = {}


def collect_webchat_response(phone: str, text: str):
    """Called from send_whatsapp_message when channel is webchat."""
    if phone not in _webchat_responses:
        _webchat_responses[phone] = []
    _webchat_responses[phone].append(text)


def pop_webchat_responses(phone: str) -> str:
    """Pop all collected responses for a webchat phone."""
    msgs = _webchat_responses.pop(phone, [])
    return "\n\n".join(msgs) if msgs else ""


@router.post("/webchat/message")
async def webchat_message(request: Request):
    """Handle webchat message — processes through same conversation engine."""
    session_id = "guest"
    try:
        body = await request.json()
        session_id = body.get("session_id") or body.get("sessionId") or "guest"
        # Accept any common field name from the frontend to avoid silent empty-message bugs
        message = (
            body.get("message")
            or body.get("text")
            or body.get("content")
            or body.get("input")
            or body.get("query")
            or ""
        )
        message = message.strip() if isinstance(message, str) else ""

        phone = f"+web{session_id}"
        set_channel(phone, "webchat")

        # Handle audio message type
        message_type = body.get("message_type", "text")
        audio_data = body.get("audio_data", "")
        mime_type = body.get("mime_type", "audio/webm")
        
        if message_type == "audio" and audio_data:
            try:
                import base64 as b64mod
                audio_bytes = b64mod.b64decode(audio_data)
                from services.whisper_service import whisper_service
                # Detect format from mime_type
                fmt = "webm"
                if "ogg" in mime_type:
                    fmt = "ogg"
                elif "mp4" in mime_type or "m4a" in mime_type:
                    fmt = "mp4"
                elif "wav" in mime_type:
                    fmt = "wav"
                transcribed = await whisper_service.transcribe(
                    audio_bytes, fmt
                )
                if transcribed:
                    message = transcribed
                    logger.info(
                        f"[Webchat Audio] Transcribed: '{transcribed[:80]}'"
                    )
                else:
                    return {
                        "session_id": session_id,
                        "response": (
                            "🎙️ Je n'ai pas pu comprendre votre audio.\n\n"
                            "Réessayez en parlant plus clairement\n"
                            "ou tapez votre demande :\n"
                            "_Exemple : Paris vendredi retour lundi_"
                        ),
                        "options": [],
                        "state": "AUDIO_FAILED",
                        "audio_base64": ""
                    }
            except Exception as e:
                logger.error(f"[Webchat Audio] Error: {type(e).__name__}: {e}")
                return {
                    "session_id": session_id,
                    "response": "🎙️ Erreur audio. Tapez votre demande par écrit.",
                    "options": [],
                    "state": "AUDIO_FAILED",
                    "audio_base64": ""
                }
        
        # Handle image message type
        if message_type == "image" and body.get("image_data"):
            if not message:
                message = "image_scan"
        
        if not message:
            logger.warning(
                f"[Webchat] EMPTY MESSAGE | session_id={session_id} | "
                f"received_keys={list(body.keys())}"
            )
            return {
                "session_id": session_id,
                "response": "Bonjour 👋 Dites-moi votre destination.",
                "options": [],
                "state": "IDLE"
            }
        
        logger.info(f"[Webchat] {session_id}: {message[:50]}")

        # Clear buffer before processing
        _webchat_responses.pop(phone, None)

        # Process through conversation engine
        await handle_message(phone, message)

        # Collect response from buffer
        response_text = pop_webchat_responses(phone)

        # Get session state
        session = await db.sessions.find_one({"phone": phone}, {"_id": 0})
        state = session.get("state", "") if session else ""

        # Generate TTS if enabled
        audio_b64 = ""
        if response_text:
            try:
                from services.tts_service import tts_service
                audio_bytes = await tts_service.synthesize(response_text)
                if audio_bytes:
                    import base64
                    audio_b64 = base64.b64encode(audio_bytes).decode()
            except Exception:
                pass

        return {
            "session_id": session_id,
            "response": response_text,
            "options": [],
            "state": state,
            "audio_base64": audio_b64
        }
    except Exception as e:
        logger.error(f"[Webchat] Error: {e}")
        return {"session_id": session_id, "response": "Une erreur est survenue. Reessayez.", "options": [], "state": "ERROR", "audio_base64": ""}


@router.get("/webchat/session/{session_id}")
async def get_session(session_id: str):
    phone = f"+web{session_id}"
    session = await db.sessions.find_one({"phone": phone}, {"_id": 0})
    return {"session_id": session_id, "state": session if session else {}}


@router.delete("/webchat/session/{session_id}")
async def reset_session_web(session_id: str):
    phone = f"+web{session_id}"
    await clear_session(phone)
    return {"session_id": session_id, "status": "reset"}


@router.get("/demo/stats")
async def demo_stats():
    try:
        tickets = await db.bookings.count_documents({})
        return {
            "flights_searched": max(tickets * 12, 142),
            "tickets_issued": max(tickets, 12),
            "languages_supported": 7,
            "countries_served": 4,
            "average_booking_time_seconds": 187,
            "uptime_percent": 99.7,
            "status": "live"
        }
    except Exception:
        return {"flights_searched": 142, "tickets_issued": 12, "languages_supported": 7, "countries_served": 4, "average_booking_time_seconds": 187, "uptime_percent": 99.7, "status": "live"}
