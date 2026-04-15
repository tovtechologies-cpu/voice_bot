"""Telegram Bot API messaging service."""
import logging
from typing import Dict, Optional
from datetime import datetime, timezone
import httpx
from config import TELEGRAM_BOT_TOKEN, API_TIMEOUT
from utils.helpers import mask_phone

logger = logging.getLogger("TelegramService")

# Telegram chat_id mapping: phone -> chat_id
_phone_to_chat_id: dict = {}


def register_chat(phone: str, chat_id: int):
    """Map a phone number to a Telegram chat_id."""
    _phone_to_chat_id[phone] = chat_id


def get_chat_id(phone: str) -> Optional[int]:
    """Get the Telegram chat_id for a phone number."""
    return _phone_to_chat_id.get(phone)


def _is_configured() -> bool:
    return bool(TELEGRAM_BOT_TOKEN and TELEGRAM_BOT_TOKEN != 'your_bot_token_here')


def _api_url(method: str) -> str:
    return f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}"


async def send_telegram_message(to: str, message: str) -> Dict:
    """Send a text message via Telegram Bot API."""
    chat_id = get_chat_id(to)
    if not chat_id:
        logger.warning(f"[Telegram] No chat_id for {mask_phone(to)}, message logged only")
        logger.info(f"[Telegram SIM] To {mask_phone(to)}:\n{message[:300]}")
        return {"status": "no_chat_id"}

    if not _is_configured():
        logger.info(f"[Telegram SIM] To {mask_phone(to)} (chat={chat_id}):\n{message[:300]}")
        return {"status": "simulated"}

    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            resp = await client.post(_api_url("sendMessage"), json={
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "Markdown",
            })
            data = resp.json()
            if data.get("ok"):
                logger.debug(f"[Telegram] Message sent to {mask_phone(to)}")
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
        logger.info(f"[Telegram SIM] Document to {mask_phone(to)}: {filename}")
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
                logger.info(f"[Telegram] Document sent to {mask_phone(to)}: {filename}")
                return {"status": "sent"}
            logger.error(f"[Telegram] Document send failed: {data.get('description')}")
            return {"status": "failed"}
    except Exception as e:
        logger.error(f"[Telegram] Document error: {e}")
        return {"status": "failed"}
