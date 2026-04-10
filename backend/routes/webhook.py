"""WhatsApp webhook routes with signature verification."""
import hmac
import hashlib
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Request, Query, Response
from conversation.handler import handle_message
from config import WHATSAPP_VERIFY_TOKEN, WHATSAPP_WEBHOOK_SECRET

router = APIRouter()
logger = logging.getLogger("WebhookRoutes")

# Track last verified timestamp for health check
_last_verified_at = None


def get_last_verified_at():
    return _last_verified_at


def verify_whatsapp_signature(payload_body: bytes, signature_header: str, secret: str) -> bool:
    """Verify X-Hub-Signature-256 from WhatsApp Cloud API."""
    if not secret:
        return True  # Skip verification if secret not configured (dev mode)
    if not signature_header:
        return False
    expected = 'sha256=' + hmac.new(
        secret.encode('utf-8'),
        payload_body,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


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
    global _last_verified_at

    # Signature verification
    payload_body = await request.body()
    signature_header = request.headers.get("x-hub-signature-256", "")

    if WHATSAPP_WEBHOOK_SECRET:
        if not verify_whatsapp_signature(payload_body, signature_header, WHATSAPP_WEBHOOK_SECRET):
            client_ip = request.client.host if request.client else "unknown"
            masked_ip = client_ip[:client_ip.rfind(".")] + ".***" if "." in client_ip else client_ip
            logger.warning(f"[WEBHOOK] Signature verification FAILED | ip={masked_ip} | timestamp={datetime.now(timezone.utc).isoformat()}")
            return Response(content='{"error":"signature_verification_failed"}', status_code=403, media_type="application/json")
        _last_verified_at = datetime.now(timezone.utc).isoformat()
        logger.debug("[WEBHOOK] Signature verified")

    try:
        import json
        data = json.loads(payload_body)
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
