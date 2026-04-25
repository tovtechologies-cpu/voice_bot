"""WhatsApp webhook routes with signature verification and async processing."""
import hmac
import hashlib
import json
import asyncio
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Request, Query, Response, BackgroundTasks
from conversation.handler import handle_message
from config import WHATSAPP_VERIFY_TOKEN, WHATSAPP_WEBHOOK_SECRET
from utils.helpers import normalize_phone, mask_phone
from services.whatsapp import update_user_message_timestamp, set_last_message_received_at

router = APIRouter()
logger = logging.getLogger("WebhookRoutes")

# Track last verified timestamp for health check
_last_verified_at = None


def get_last_verified_at():
    return _last_verified_at


def verify_whatsapp_signature(payload_body: bytes, signature_header: str, secret: str) -> bool:
    """Verify X-Hub-Signature-256 from WhatsApp Cloud API.
    The secret is the Meta App Secret (from App Settings > Basic)."""
    if not secret:
        return True
    if not signature_header:
        logger.warning("[WEBHOOK] No signature header present")
        return False
    expected = 'sha256=' + hmac.new(
        secret.encode('utf-8'),
        payload_body,
        hashlib.sha256
    ).hexdigest()
    match = hmac.compare_digest(expected, signature_header)
    if not match:
        logger.warning(f"[WEBHOOK] Signature mismatch | received={signature_header[:30]}... | expected={expected[:30]}...")
    return match


@router.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge")
):
    """Webhook verification — Meta sends GET to verify endpoint ownership."""
    valid_tokens = [t for t in [WHATSAPP_WEBHOOK_SECRET, WHATSAPP_VERIFY_TOKEN] if t]
    logger.info(f"[WEBHOOK] Verify request: mode={hub_mode}, token={hub_token[:10] if hub_token else 'none'}..., valid_count={len(valid_tokens)}")
    if hub_mode == "subscribe" and hub_token and hub_token in valid_tokens:
        logger.info("[WEBHOOK] Verification successful")
        return Response(content=hub_challenge, media_type="text/plain")
    logger.warning(f"[WEBHOOK] Verification failed — received token does not match any configured token")
    return {"error": "Verification failed"}


async def _process_message_async(phone: str, text_body: str, audio_id: str, image_id: str):
    """Process incoming WhatsApp message asynchronously."""
    try:
        normalized = normalize_phone(phone)
        from services.channel import set_channel
        set_channel(normalized, "whatsapp")
        await update_user_message_timestamp(normalized)
        set_last_message_received_at()
        await handle_message(normalized, text_body, audio_id=audio_id, image_id=image_id)
    except Exception as e:
        logger.error(f"[WEBHOOK] Handler error for {mask_phone(phone)}: {e}")


@router.post("/webhook")
async def receive_webhook(request: Request, background_tasks: BackgroundTasks):
    global _last_verified_at

    # Signature verification
    payload_body = await request.body()
    signature_header = request.headers.get("x-hub-signature-256", "")

    if WHATSAPP_WEBHOOK_SECRET:
        if not verify_whatsapp_signature(payload_body, signature_header, WHATSAPP_WEBHOOK_SECRET):
            client_ip = request.client.host if request.client else "unknown"
            masked_ip = client_ip[:client_ip.rfind(".")] + ".***" if "." in client_ip else client_ip
            logger.warning(f"[WEBHOOK] Signature FAILED | ip={masked_ip} | sig_present={bool(signature_header)} | secret_len={len(WHATSAPP_WEBHOOK_SECRET)} | payload_len={len(payload_body)}")
            return Response(content='{"error":"signature_verification_failed"}', status_code=403, media_type="application/json")
        _last_verified_at = datetime.now(timezone.utc).isoformat()
        logger.debug("[WEBHOOK] Signature verified")

    try:
        data = json.loads(payload_body)
    except Exception:
        return {"status": "invalid_json"}

    # Return 200 immediately to Meta, process in background
    entries = data.get("entry", [])
    for entry in entries:
        changes = entry.get("changes", [])
        for change in changes:
            value = change.get("value", {})

            # Handle status updates (delivery receipts)
            statuses = value.get("statuses", [])
            for status in statuses:
                logger.debug(f"[WEBHOOK] Status update: {status.get('status')} for {mask_phone(status.get('recipient_id', ''))}")

            # Handle incoming messages
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
                elif msg_type == "document":
                    logger.info(f"[WEBHOOK] Document received from {mask_phone(phone)} (not processed)")
                elif msg_type == "interactive":
                    interactive = msg.get("interactive", {})
                    if interactive.get("type") == "list_reply":
                        text_body = interactive.get("list_reply", {}).get("id", "")
                    elif interactive.get("type") == "button_reply":
                        text_body = interactive.get("button_reply", {}).get("id", "")

                if phone and (text_body or audio_id or image_id):
                    # Process asynchronously in background
                    background_tasks.add_task(
                        _process_message_async, phone, text_body, audio_id, image_id
                    )

    return {"status": "ok"}
