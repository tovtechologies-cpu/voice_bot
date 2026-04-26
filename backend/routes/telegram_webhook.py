"""Telegram webhook routes with command router."""
import logging
import hmac
from fastapi import APIRouter, Request, Response
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_WEBHOOK_SECRET
from conversation.handler import handle_message
from services.telegram import register_chat, send_telegram_message
from services.channel import set_channel
from services.shadow_profile import get_or_create_shadow_profile, link_channel
from services.session import clear_session
from database import db

router = APIRouter(prefix="/telegram")
logger = logging.getLogger("TelegramWebhook")


def _verify_secret_token(request: Request) -> bool:
    if not TELEGRAM_WEBHOOK_SECRET:
        return True
    header = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not header:
        return True
    return hmac.compare_digest(header, TELEGRAM_WEBHOOK_SECRET)


def _extract_phone_from_contact(contact: dict) -> str:
    phone = contact.get("phone_number", "")
    if phone and not phone.startswith("+"):
        phone = f"+{phone}"
    return phone


async def _handle_command(phone: str, command: str, lang: str = "fr") -> bool:
    """Handle Telegram bot commands. Returns True if handled."""
    cmd = command.split()[0].lower().split("@")[0]

    if cmd == "/start":
        await clear_session(phone)
        msg = (
            "*Bienvenue sur Travelioo !*\n\n"
            "Le premier agent de voyage IA\n"
            "sur WhatsApp et Telegram au Benin.\n\n"
            "Pour reserver un vol, dites-moi\n"
            "votre destination et vos dates.\n\n"
            "Exemple :\n"
            "_Paris vendredi retour lundi_\n"
            "_Dakar moins de 150 000 XOF_\n\n"
            "Je m'occupe de tout en moins de 3 min.\n\n"
            "Speak'n Go"
        )
        await send_telegram_message(phone, msg)
        return True

    if cmd == "/annuler":
        await clear_session(phone)
        msg = "*Reservation annulee.*\n\nTapez /start pour commencer une nouvelle reservation."
        await send_telegram_message(phone, msg)
        return True

    if cmd == "/historique":
        bookings = await db.bookings.find(
            {"phone": phone, "status": {"$in": ["confirmed", "cancelled_by_airline"]}},
            {"_id": 0}
        ).sort("created_at", -1).limit(5).to_list(5)
        if not bookings:
            msg = "*Aucune reservation trouvee.*\n\nTapez /start pour reserver votre premier vol."
        else:
            msg = "*Vos dernieres reservations :*\n\n"
            for b in bookings:
                origin = b.get('origin', '?')
                dest = b.get('destination', '?')
                date = b.get('departure_date', '?')
                price = b.get('price_eur', '?')
                ref = b.get('booking_ref', 'N/A')
                status = b.get('status', '?')
                msg += f"{origin} -> {dest}\n{date}\n{price}EUR | `{ref}` | {status}\n\n"
        await send_telegram_message(phone, msg)
        return True

    if cmd == "/profil":
        passenger = await db.passengers.find_one(
            {"$or": [{"whatsapp_phone": phone}, {"created_by_phone": phone}]},
            {"_id": 0})
        if passenger and passenger.get("firstName"):
            fn = passenger.get("firstName", "N/A")
            ln = passenger.get("lastName", "N/A")
            nat = passenger.get("nationality", "Non renseignee")
            pp = passenger.get("passportNumber", "Non renseigne")
            msg = f"*Votre profil :*\n\nNom : {ln}\nPrenom : {fn}\nNationalite : {nat}\nPasseport : `{pp}`\n\nTapez /start pour reserver."
        else:
            msg = "Aucun profil trouve.\nTapez /start pour creer votre profil voyageur."
        await send_telegram_message(phone, msg)
        return True

    if cmd == "/alerte":
        msg = "*Alertes prix*\n\nIndiquez votre route :\n_Cotonou Paris alerte_\n\nJe vous notifie des que le tarif descend sous votre prix habituel."
        await send_telegram_message(phone, msg)
        return True

    if cmd == "/aide" or cmd == "/help":
        msg = (
            "*Aide Travelioo*\n\n"
            "/start — Nouvelle reservation\n"
            "/annuler — Annuler en cours\n"
            "/historique — Mes reservations\n"
            "/profil — Mon profil\n"
            "/alerte — Alertes prix\n"
            "/aide — Cette aide\n\n"
            "Envoyez un vocal ou ecrit :\n"
            "_Paris vendredi retour lundi_\n\n"
            "Speak'n Go"
        )
        await send_telegram_message(phone, msg)
        return True

    # Unknown command
    msg = "Commande inconnue.\nTapez /aide pour voir les commandes."
    await send_telegram_message(phone, msg)
    return True


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
    phone = f"+tg{telegram_user_id}"

    # Check if linked to real phone
    linked = await db.shadow_profiles.find_one(
        {"telegram_id": telegram_user_id}, {"_id": 0, "phone_number": 1})
    if linked:
        phone = linked["phone_number"]

    # Handle contact sharing
    contact = message.get("contact")
    if contact:
        real_phone = _extract_phone_from_contact(contact)
        if real_phone:
            await link_channel(real_phone, "telegram", telegram_user_id)
            old_session = await db.sessions.find_one({"phone": phone}, {"_id": 0})
            if old_session and phone.startswith("+tg"):
                await db.sessions.delete_one({"phone": phone})
                old_session["phone"] = real_phone
                await db.sessions.replace_one({"phone": real_phone}, old_session, upsert=True)
            phone = real_phone
            register_chat(phone, chat_id)
            set_channel(phone, "telegram")
            await send_telegram_message(phone, "Numero verifie ! Votre compte Telegram est maintenant lie.")
            return {"ok": True}

    # Register chat mapping and set channel
    register_chat(phone, chat_id)
    set_channel(phone, "telegram")

    # Create/update shadow profile
    await get_or_create_shadow_profile(phone, channel="telegram", channel_id=telegram_user_id)

    # Extract message content
    text = message.get("text", "")
    audio_id = None
    image_id = None

    # ── COMMAND ROUTER (runs BEFORE conversation handler) ──
    if text.startswith("/"):
        await _handle_command(phone, text)
        return {"ok": True}

    # Handle voice messages
    voice = message.get("voice") or message.get("audio")
    if voice:
        audio_id = f"tg:{voice['file_id']}"

    # Handle photos
    photos = message.get("photo")
    if photos:
        best = max(photos, key=lambda p: p.get("file_size", 0))
        image_id = f"tg:{best['file_id']}"

    document = message.get("document")
    if document and document.get("mime_type", "").startswith("image/"):
        image_id = f"tg:{document['file_id']}"

    if not text and not audio_id and not image_id:
        return {"ok": True}

    # ── CONVERSATION HANDLER (non-command messages) ──
    await handle_message(phone, text, audio_id=audio_id, image_id=image_id)
    return {"ok": True}
