"""WhatsApp webhook routes."""
import logging
from fastapi import APIRouter, Request, Query, Response
from conversation.handler import handle_message
from config import WHATSAPP_VERIFY_TOKEN

router = APIRouter()
logger = logging.getLogger("WebhookRoutes")


@router.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge")
):
    if hub_mode == "subscribe" and hub_token == WHATSAPP_VERIFY_TOKEN:
        return Response(content=hub_challenge, media_type="text/plain")
    return {"error": "Verification failed"}


@router.post("/webhook")
async def receive_webhook(request: Request):
    try:
        data = await request.json()
    except Exception:
        return {"status": "invalid_json"}

    entries = data.get("entry", [])
    for entry in entries:
        changes = entry.get("changes", [])
        for change in changes:
            value = change.get("value", {})
            messages = value.get("messages", [])
            for msg in messages:
                phone = msg.get("from", "")
                msg_type = msg.get("type", "")
                text_body = ""
                audio_id = None
                image_id = None

                if msg_type == "text":
                    text_body = msg.get("text", {}).get("body", "")
                elif msg_type == "audio":
                    audio_id = msg.get("audio", {}).get("id")
                elif msg_type == "image":
                    image_id = msg.get("image", {}).get("id")
                elif msg_type == "interactive":
                    interactive = msg.get("interactive", {})
                    if interactive.get("type") == "list_reply":
                        text_body = interactive.get("list_reply", {}).get("id", "")
                    elif interactive.get("type") == "button_reply":
                        text_body = interactive.get("button_reply", {}).get("id", "")

                if phone and (text_body or audio_id or image_id):
                    try:
                        await handle_message(phone, text_body, audio_id=audio_id, image_id=image_id)
                    except Exception as e:
                        logger.error(f"Handler error for {phone}: {e}")

    return {"status": "ok"}
