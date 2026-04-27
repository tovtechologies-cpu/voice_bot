"""Telegram Bot API messaging service with auto-keyboard detection."""
import logging
import re
from typing import Dict, Optional
import httpx
from config import TELEGRAM_BOT_TOKEN, API_TIMEOUT
from utils.helpers import mask_phone

logger = logging.getLogger("TelegramService")

_phone_to_chat_id: dict = {}


def register_chat(phone: str, chat_id: int):
    _phone_to_chat_id[phone] = chat_id


def get_chat_id(phone: str) -> Optional[int]:
    return _phone_to_chat_id.get(phone)


def _is_configured() -> bool:
    return bool(TELEGRAM_BOT_TOKEN and TELEGRAM_BOT_TOKEN != 'your_bot_token_here')


def _api_url(method: str) -> str:
    return f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}"


def _auto_detect_keyboard(message: str) -> Optional[dict]:
    """Auto-detect and attach inline keyboard based on message content."""
    from services.telegram_keyboards import (
        keyboard_welcome, keyboard_enrollment, keyboard_consent,
        keyboard_return_flight, keyboard_payment_confirm, build_inline_keyboard
    )
    msg_lower = message.lower()

    # Welcome / Start
    if "bienvenue sur travelioo" in msg_lower or "welcome to travelioo" in msg_lower:
        return keyboard_welcome()

    # Consent
    if ("j'accepte" in msg_lower or "i agree" in msg_lower) and ("1" in message):
        return keyboard_consent()

    # Enrollment method
    if ("scanner" in msg_lower or "scan" in msg_lower) and ("manuelle" in msg_lower or "manual" in msg_lower):
        return keyboard_enrollment()

    # Return flight question
    if ("vol retour" in msg_lower or "return flight" in msg_lower) and ("aller simple" in msg_lower or "one-way" in msg_lower):
        return keyboard_return_flight()

    # Payment confirmation
    if ("notification de paiement" in msg_lower or "send payment" in msg_lower) and ("annuler" in msg_lower or "cancel" in msg_lower):
        return keyboard_payment_confirm()

    # Flight selection (prices + "selectionner" or "select")
    if ("selectionner" in msg_lower or "to select" in msg_lower):
        prices = re.findall(r'(\d+)EUR', message)
        labels = ["LE PLUS BAS", "LE PLUS RAPIDE", "PREMIUM"]
        buttons = []
        for i, price in enumerate(prices[:3]):
            label = labels[i] if i < len(labels) else f"Option {i+1}"
            buttons.append([{"text": f"{i+1}. {label} - {price}EUR", "data": f"flight_{i+1}"}])
        if buttons:
            buttons.append([{"text": "Nouvelle recherche", "data": "flight_new"}])
            return build_inline_keyboard(buttons)

    # Payment method menu
    if ("celtiis" in msg_lower or "mtn" in msg_lower) and ("split" in msg_lower or "partager" in msg_lower or "fractionner" in msg_lower):
        buttons = []
        if "celtiis" in msg_lower:
            buttons.append([{"text": "Celtiis Cash (Recommande)", "data": "pay_celtiis"}])
        if "mtn" in msg_lower:
            buttons.append([{"text": "MTN MoMo", "data": "pay_mtn"}])
        if "moov" in msg_lower:
            buttons.append([{"text": "Moov Money", "data": "pay_moov"}])
        if "google" in msg_lower or "apple" in msg_lower:
            buttons.append([{"text": "Google Pay / Apple Pay", "data": "pay_stripe"}])
        buttons.append([{"text": "Paiement partage", "data": "pay_split"}])
        return build_inline_keyboard(buttons)

    return None


async def send_telegram_message(to: str, message: str, reply_markup: dict = None) -> Dict:
    """Send a text message via Telegram Bot API with auto-detected inline keyboard."""
    chat_id = get_chat_id(to)
    if not chat_id:
        logger.warning(f"[Telegram] No chat_id for {mask_phone(to)}")
        return {"status": "no_chat_id"}

    if not _is_configured():
        logger.info(f"[Telegram SIM] To {mask_phone(to)} (chat={chat_id}):\n{message[:200]}")
        return {"status": "simulated"}

    # Auto-attach inline keyboards if not explicitly provided
    if not reply_markup:
        reply_markup = _auto_detect_keyboard(message)

    try:
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown",
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup

        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            resp = await client.post(_api_url("sendMessage"), json=payload)
            data = resp.json()
            if data.get("ok"):
                return {"status": "sent", "message_id": data["result"]["message_id"]}
            # If Markdown fails, retry without
            if "can't parse" in data.get("description", "").lower():
                payload.pop("parse_mode", None)
                resp = await client.post(_api_url("sendMessage"), json=payload)
                data = resp.json()
                if data.get("ok"):
                    return {"status": "sent", "message_id": data["result"]["message_id"]}
            logger.error(f"[Telegram] Send failed: {data.get('description')}")
            return {"status": "failed", "error": data.get("description")}
    except Exception as e:
        logger.error(f"[Telegram] Send error: {e}")
        return {"status": "failed", "error": str(e)}


async def send_telegram_document(to: str, document_url: str, filename: str, caption: str = "") -> Dict:
    """Send a document via Telegram Bot API."""
    chat_id = get_chat_id(to)
    if not chat_id:
        return {"status": "no_chat_id"}
    if not _is_configured():
        logger.info(f"[Telegram SIM] Document to {mask_phone(to)}: {filename}")
        return {"status": "simulated"}
    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            resp = await client.post(_api_url("sendDocument"), json={
                "chat_id": chat_id,
                "document": document_url,
                "caption": caption[:1024],
                "parse_mode": "Markdown",
            })
            data = resp.json()
            if data.get("ok"):
                return {"status": "sent"}
            return {"status": "failed"}
    except Exception as e:
        logger.error(f"[Telegram] Document error: {e}")
        return {"status": "failed"}
