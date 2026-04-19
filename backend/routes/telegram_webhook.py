"""Telegram webhook routes."""
import logging
import hashlib
import hmac
from fastapi import APIRouter, Request, Response
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_WEBHOOK_SECRET
from conversation.handler import handle_message
from services.telegram import register_chat
from services.channel import set_channel
from services.shadow_profile import get_or_create_shadow_profile, link_channel
from database import db

router = APIRouter(prefix="/telegram")
logger = logging.getLogger("TelegramWebhook")


def _verify_secret_token(request: Request) -> bool:
    """Verify Telegram webhook secret token if configured."""
    if not TELEGRAM_WEBHOOK_SECRET:
        return True
    header = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not header:
        return True
    return hmac.compare_digest(header, TELEGRAM_WEBHOOK_SECRET)


def _extract_phone_from_contact(contact: dict) -> str:
    """Extract phone from Telegram contact sharing."""
    phone = contact.get("phone_number", "")
    if phone and not phone.startswith("+"):
        phone = f"+{phone}"
    return phone


@router.post("/webhook")
async def telegram_webhook(request: Request):
    """Handle incoming Telegram Bot updates."""
    if not _verify_secret_token(request):
        logger.warning("[Telegram] Invalid secret token")
        return Response(status_code=403)

    try:
        update = await request.json()
    except Exception:
        return {"ok": True}

    message = update.get("message")
    if not message:
        return {"ok": True}

    chat_id = message["chat"]["id"]
    from_user = message.get("from", {})
    telegram_user_id = str(from_user.get("id", ""))

    # Determine phone — Telegram users don't always share their phone
    # Use a synthetic phone based on telegram user ID for session tracking
    # When user shares contact, we link to their real phone
    phone = f"+tg{telegram_user_id}"

    # Check if this Telegram user is already linked to a real phone
    linked = await db.shadow_profiles.find_one(
        {"telegram_id": telegram_user_id}, {"_id": 0, "phone_number": 1})
    if linked:
        phone = linked["phone_number"]

    # Handle contact sharing (phone number verification)
    contact = message.get("contact")
    if contact:
        real_phone = _extract_phone_from_contact(contact)
        if real_phone:
            # Link this Telegram user to their real phone
            await link_channel(real_phone, "telegram", telegram_user_id)
            # Migrate session from synthetic to real phone
            old_session = await db.sessions.find_one({"phone": phone}, {"_id": 0})
            if old_session and phone.startswith("+tg"):
                await db.sessions.delete_one({"phone": phone})
                old_session["phone"] = real_phone
                await db.sessions.replace_one(
                    {"phone": real_phone}, old_session, upsert=True)
            phone = real_phone
            register_chat(phone, chat_id)
            set_channel(phone, "telegram")
            from services.telegram import send_telegram_message
            await send_telegram_message(phone,
                "Numero verifie ! Votre compte Telegram est maintenant lie.\n"
                "Verified! Your Telegram account is now linked.")
            return {"ok": True}

    # Register chat mapping and set channel
    register_chat(phone, chat_id)
    set_channel(phone, "telegram")

    # Create/update shadow profile with Telegram link
    await get_or_create_shadow_profile(phone, channel="telegram", channel_id=telegram_user_id)

    # Extract message content
    text = message.get("text", "")
    audio_id = None
    image_id = None

    # Handle voice messages
    voice = message.get("voice") or message.get("audio")
    if voice:
        audio_id = f"tg:{voice['file_id']}"

    # Handle photos (passport scan)
    photos = message.get("photo")
    if photos:
        # Telegram sends multiple sizes, pick the largest
        best = max(photos, key=lambda p: p.get("file_size", 0))
        image_id = f"tg:{best['file_id']}"

    # Handle documents (could be passport photo)
    document = message.get("document")
    if document and document.get("mime_type", "").startswith("image/"):
        image_id = f"tg:{document['file_id']}"

    # Strip bot commands
    if text.startswith("/start"):
        text = "bonjour"
    elif text.startswith("/aide") or text.startswith("/help"):
        text = "aide"
    elif text.startswith("/annuler") or text.startswith("/cancel"):
        text = "annuler"
    elif text.startswith("/"):
        text = text[1:]  # Strip leading slash

    if not text and not audio_id and not image_id:
        return {"ok": True}

    # Route through shared state machine
    await handle_message(phone, text, audio_id=audio_id, image_id=image_id)
    return {"ok": True}
