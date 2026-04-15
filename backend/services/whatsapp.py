"""WhatsApp Cloud API messaging service — Meta official integration."""
import logging
from typing import Dict, Optional
from datetime import datetime, timezone
import httpx
from config import (
    WHATSAPP_PHONE_ID, WHATSAPP_TOKEN, WHATSAPP_API_VERSION,
    WHATSAPP_BASE_URL, API_TIMEOUT, WHATSAPP_MSG_LIMIT
)
from utils.helpers import normalize_phone, mask_phone
from database import db

logger = logging.getLogger("WhatsAppService")

# Track last message timestamps for health check
_last_message_sent_at = None
_last_message_received_at = None


def get_last_message_sent_at():
    return _last_message_sent_at


def get_last_message_received_at():
    return _last_message_received_at


def set_last_message_received_at():
    global _last_message_received_at
    _last_message_received_at = datetime.now(timezone.utc).isoformat()


def _is_configured() -> bool:
    return bool(WHATSAPP_PHONE_ID and WHATSAPP_TOKEN
                and WHATSAPP_PHONE_ID != 'your_phone_id_here'
                and WHATSAPP_TOKEN != 'your_token_here')


def _api_url(path: str = "messages") -> str:
    return f"{WHATSAPP_BASE_URL}/{WHATSAPP_API_VERSION}/{WHATSAPP_PHONE_ID}/{path}"


def _auth_headers() -> dict:
    return {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }


# ---------------------------------------------------------------------------
# Error handling for WhatsApp API responses
# ---------------------------------------------------------------------------
ERROR_HANDLERS = {
    131047: "outside_24h_window",
    131026: "not_on_whatsapp",
    100: "invalid_phone_format",
    190: "token_expired_or_invalid",
}


def _handle_api_error(response_data: dict, phone: str) -> str:
    """Process WhatsApp API error response and return error type."""
    error = response_data.get("error", {})
    code = error.get("code", 0)
    message = error.get("message", "Unknown error")

    error_type = ERROR_HANDLERS.get(code, "unknown_error")
    masked = mask_phone(phone)

    log_entry = {
        "event": f"whatsapp_send_error_{error_type}",
        "phone_masked": masked,
        "error_code": code,
        "error_message": message,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    if code == 190:
        logger.critical(f"[WHATSAPP] CRITICAL — Token expired/invalid | {masked} | {message}")
    elif code == 131047:
        logger.warning(f"[WHATSAPP] Outside 24h window | {masked} — switch to template")
    elif code == 131026:
        logger.warning(f"[WHATSAPP] Not on WhatsApp | {masked}")
    elif code == 100:
        logger.warning(f"[WHATSAPP] Invalid phone format | {masked}")
    else:
        logger.error(f"[WHATSAPP] Error {code} | {masked} | {message}")

    return error_type


# ---------------------------------------------------------------------------
# 24h conversation window check
# ---------------------------------------------------------------------------
async def _check_24h_window(phone: str) -> bool:
    """Check if we're within the 24h conversation window for this phone."""
    session = await db.sessions.find_one({"phone": phone}, {"_id": 0, "last_user_message_at": 1})
    if not session or not session.get("last_user_message_at"):
        return False
    try:
        last_msg = datetime.fromisoformat(session["last_user_message_at"])
        elapsed = (datetime.now(timezone.utc) - last_msg).total_seconds()
        return elapsed < 84600  # 23.5 hours
    except (ValueError, TypeError):
        return False


async def update_user_message_timestamp(phone: str):
    """Update the last user message timestamp for 24h window tracking."""
    await db.sessions.update_one(
        {"phone": phone},
        {"$set": {"last_user_message_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True
    )


# ---------------------------------------------------------------------------
# Message chunking
# ---------------------------------------------------------------------------
def chunk_message(message: str, limit: int = WHATSAPP_MSG_LIMIT) -> list:
    """Split long messages at paragraph boundaries to stay within WhatsApp limits."""
    if len(message) <= limit:
        return [message]

    chunks = []
    current = ""
    paragraphs = message.split("\n\n")

    for para in paragraphs:
        if len(current) + len(para) + 2 > limit:
            if current:
                chunks.append(current.strip())
                current = ""
            if len(para) > limit:
                lines = para.split("\n")
                for line in lines:
                    if len(current) + len(line) + 1 > limit:
                        if current:
                            chunks.append(current.strip())
                        current = line + "\n"
                    else:
                        current += line + "\n"
            else:
                current = para + "\n\n"
        else:
            current += para + "\n\n"

    if current.strip():
        chunks.append(current.strip())

    return chunks if chunks else [message]


# ---------------------------------------------------------------------------
# Send text message
# ---------------------------------------------------------------------------
async def send_whatsapp_message(to: str, message: str) -> Dict:
    """Send a text message, auto-routing to Telegram if the user is on that channel."""
    from services.channel import get_channel
    if get_channel(to) == "telegram":
        from services.telegram import send_telegram_message
        return await send_telegram_message(to, message)

    chunks = chunk_message(message)
    last_result = {"status": "simulated"}

    for chunk in chunks:
        last_result = await _send_single_message(to, chunk)

    return last_result


async def _send_single_message(to: str, message: str) -> Dict:
    global _last_message_sent_at

    if not _is_configured():
        logger.info(f"[WhatsApp SIM] To {mask_phone(to)}:\n{message[:300]}...")
        return {"status": "simulated"}

    phone = normalize_phone(to)
    url = _api_url("messages")

    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            response = await client.post(url,
                json={
                    "messaging_product": "whatsapp",
                    "recipient_type": "individual",
                    "to": phone,
                    "type": "text",
                    "text": {"body": message}
                },
                headers=_auth_headers())

            data = response.json()

            if response.status_code == 200:
                _last_message_sent_at = datetime.now(timezone.utc).isoformat()
                logger.debug(f"[WHATSAPP] Message sent to {mask_phone(phone)}")
                return {"status": "sent", "message_id": data.get("messages", [{}])[0].get("id")}

            error_type = _handle_api_error(data, phone)

            # Auto-retry with normalization for invalid phone format
            if error_type == "invalid_phone_format" and phone != to:
                logger.info(f"[WHATSAPP] Retrying with original number {mask_phone(to)}")
                response2 = await client.post(url,
                    json={
                        "messaging_product": "whatsapp",
                        "recipient_type": "individual",
                        "to": to.replace("+", "").replace(" ", ""),
                        "type": "text",
                        "text": {"body": message}
                    },
                    headers=_auth_headers())
                if response2.status_code == 200:
                    _last_message_sent_at = datetime.now(timezone.utc).isoformat()
                    return {"status": "sent"}

            # Outside 24h window — queue for template
            if error_type == "outside_24h_window":
                return {"status": "pending_window", "error": "outside_24h_window"}

            return {"status": "failed", "error": error_type}

    except Exception as e:
        logger.error(f"[WHATSAPP] Send error to {mask_phone(phone)}: {e}")
        return {"status": "failed", "error": str(e)}


# ---------------------------------------------------------------------------
# Send document (PDF ticket)
# ---------------------------------------------------------------------------
async def send_whatsapp_document(to: str, document_url: str, filename: str, caption: str = "") -> Dict:
    """Send a document, auto-routing to Telegram if needed."""
    from services.channel import get_channel
    if get_channel(to) == "telegram":
        from services.telegram import send_telegram_document
        return await send_telegram_document(to, document_url, filename, caption)

    global _last_message_sent_at

    if not _is_configured():
        logger.info(f"[WhatsApp SIM] Document to {mask_phone(to)}: {filename}")
        return {"status": "simulated"}

    phone = normalize_phone(to)
    url = _api_url("messages")

    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            response = await client.post(url,
                json={
                    "messaging_product": "whatsapp",
                    "recipient_type": "individual",
                    "to": phone,
                    "type": "document",
                    "document": {
                        "link": document_url,
                        "filename": filename,
                        "caption": caption
                    }
                },
                headers=_auth_headers())

            if response.status_code == 200:
                _last_message_sent_at = datetime.now(timezone.utc).isoformat()
                logger.info(f"[WHATSAPP] Document sent to {mask_phone(phone)}: {filename}")
                return {"status": "sent"}

            _handle_api_error(response.json(), phone)
            return {"status": "failed"}

    except Exception as e:
        logger.error(f"[WHATSAPP] Document send error: {e}")
        return {"status": "failed"}


# ---------------------------------------------------------------------------
# Send template message (outside 24h window)
# ---------------------------------------------------------------------------
async def send_whatsapp_template(to: str, template_name: str, language: str = "fr", params: list = None) -> Dict:
    """Send a pre-approved WhatsApp template message."""
    global _last_message_sent_at

    if not _is_configured():
        logger.info(f"[WhatsApp SIM] Template '{template_name}' to {mask_phone(to)}: params={params}")
        return {"status": "simulated"}

    phone = normalize_phone(to)
    url = _api_url("messages")

    components = []
    if params:
        components.append({
            "type": "body",
            "parameters": [{"type": "text", "text": str(p)} for p in params]
        })

    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            response = await client.post(url,
                json={
                    "messaging_product": "whatsapp",
                    "to": phone,
                    "type": "template",
                    "template": {
                        "name": template_name,
                        "language": {"code": language},
                        "components": components
                    }
                },
                headers=_auth_headers())

            if response.status_code == 200:
                _last_message_sent_at = datetime.now(timezone.utc).isoformat()
                logger.info(f"[WHATSAPP] Template '{template_name}' sent to {mask_phone(phone)}")
                return {"status": "sent"}

            _handle_api_error(response.json(), phone)
            return {"status": "failed"}

    except Exception as e:
        logger.error(f"[WHATSAPP] Template send error: {e}")
        return {"status": "failed"}


# ---------------------------------------------------------------------------
# Send interactive list
# ---------------------------------------------------------------------------
async def send_whatsapp_interactive_list(to: str, header: str, body: str, button_text: str, sections: list) -> Dict:
    """Send WhatsApp interactive list message."""
    if not _is_configured():
        logger.info(f"[WhatsApp SIM] Interactive list to {mask_phone(to)}: {header}")
        return {"status": "simulated"}

    phone = normalize_phone(to)
    url = _api_url("messages")

    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            response = await client.post(url,
                json={
                    "messaging_product": "whatsapp",
                    "to": phone,
                    "type": "interactive",
                    "interactive": {
                        "type": "list",
                        "header": {"type": "text", "text": header},
                        "body": {"text": body},
                        "action": {
                            "button": button_text,
                            "sections": sections
                        }
                    }
                },
                headers=_auth_headers())
            if response.status_code == 200:
                return {"status": "sent"}
            _handle_api_error(response.json(), phone)
            return {"status": "failed"}
    except Exception as e:
        logger.error(f"[WHATSAPP] Interactive error: {e}")
        return {"status": "failed"}


# ---------------------------------------------------------------------------
# Download media (audio / image) from WhatsApp
# ---------------------------------------------------------------------------
async def download_whatsapp_media(media_id: str) -> Optional[bytes]:
    """Download media file from WhatsApp Cloud API (2-step: get URL, then download)."""
    if not _is_configured():
        logger.info(f"[WhatsApp SIM] Media download skipped: {media_id}")
        return None

    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            # Step 1: Get media URL
            url_resp = await client.get(
                f"{WHATSAPP_BASE_URL}/{WHATSAPP_API_VERSION}/{media_id}",
                headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
            )
            if url_resp.status_code != 200:
                logger.error(f"[WHATSAPP] Media URL fetch failed: {url_resp.status_code}")
                return None

            media_url = url_resp.json().get("url")
            if not media_url:
                logger.error("[WHATSAPP] No media URL in response")
                return None

            # Step 2: Download actual file
            file_resp = await client.get(
                media_url,
                headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
            )
            if file_resp.status_code == 200:
                logger.info(f"[WHATSAPP] Media downloaded: {media_id} ({len(file_resp.content)} bytes)")
                return file_resp.content

            logger.error(f"[WHATSAPP] Media download failed: {file_resp.status_code}")
    except Exception as e:
        logger.error(f"[WHATSAPP] Media download error: {e}")
    return None
