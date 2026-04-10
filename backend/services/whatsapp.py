"""WhatsApp messaging service with message chunking."""
import logging
from typing import Dict
import httpx
from config import WHATSAPP_PHONE_ID, WHATSAPP_TOKEN, API_TIMEOUT, WHATSAPP_MSG_LIMIT

logger = logging.getLogger("WhatsAppService")


def _is_configured() -> bool:
    return bool(WHATSAPP_PHONE_ID and WHATSAPP_TOKEN and WHATSAPP_PHONE_ID != 'your_phone_id_here')


def _normalize_phone(phone: str) -> str:
    return phone.replace("+", "").replace(" ", "").replace("-", "")


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
            # If single paragraph exceeds limit, split by lines
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


async def send_whatsapp_message(to: str, message: str) -> Dict:
    """Send a WhatsApp text message, auto-chunking if needed."""
    chunks = chunk_message(message)
    last_result = {"status": "simulated"}

    for chunk in chunks:
        last_result = await _send_single_message(to, chunk)

    return last_result


async def _send_single_message(to: str, message: str) -> Dict:
    if not _is_configured():
        logger.info(f"[WhatsApp SIM] To {to}:\n{message[:500]}...")
        return {"status": "simulated"}

    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
    phone = _normalize_phone(to)

    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            response = await client.post(url,
                json={"messaging_product": "whatsapp", "to": phone, "type": "text", "text": {"body": message}},
                headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"})
            return {"status": "sent" if response.status_code == 200 else "failed"}
    except Exception as e:
        logger.error(f"WhatsApp error: {e}")
        return {"status": "failed"}


async def send_whatsapp_document(to: str, document_url: str, filename: str, caption: str = "") -> Dict:
    if not _is_configured():
        logger.info(f"[WhatsApp SIM] Document to {to}: {filename}")
        return {"status": "simulated"}

    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
    phone = _normalize_phone(to)

    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            response = await client.post(url,
                json={"messaging_product": "whatsapp", "to": phone, "type": "document",
                      "document": {"link": document_url, "filename": filename, "caption": caption}},
                headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"})
            return {"status": "sent" if response.status_code == 200 else "failed"}
    except Exception as e:
        logger.error(f"WhatsApp document error: {e}")
        return {"status": "failed"}


async def send_whatsapp_interactive_list(to: str, header: str, body: str, button_text: str, sections: list) -> Dict:
    """Send WhatsApp interactive list message (for date picker, etc.)."""
    if not _is_configured():
        logger.info(f"[WhatsApp SIM] Interactive list to {to}: {header}")
        return {"status": "simulated"}

    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
    phone = _normalize_phone(to)

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
                headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"})
            return {"status": "sent" if response.status_code == 200 else "failed"}
    except Exception as e:
        logger.error(f"WhatsApp interactive error: {e}")
        return {"status": "failed"}
