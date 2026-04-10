"""Health and status routes."""
import logging
from datetime import datetime, timezone
from fastapi import APIRouter
from database import db
from config import (
    WHATSAPP_PHONE_ID, WHATSAPP_TOKEN, EMERGENT_LLM_KEY,
    DUFFEL_API_KEY, is_duffel_sandbox, STRIPE_SECRET_KEY,
    MOMO_API_USER, MOOV_API_KEY
)

router = APIRouter()
logger = logging.getLogger("HealthRoutes")


@router.get("/health")
async def health():
    try:
        await db.command("ping")
        db_status = "connected"
    except Exception:
        db_status = "disconnected"

    wa_configured = WHATSAPP_PHONE_ID and WHATSAPP_TOKEN and WHATSAPP_PHONE_ID != 'your_phone_id_here'
    stripe_configured = STRIPE_SECRET_KEY and STRIPE_SECRET_KEY != 'your_stripe_secret_key_here'
    momo_configured = MOMO_API_USER and MOMO_API_USER != 'your_uuid_here'
    moov_configured = MOOV_API_KEY and MOOV_API_KEY != 'your_key_here'

    def _status(configured, label="configured"):
        return {"status": label if configured else "missing"}

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "version": "7.0",
        "type": "WhatsApp Agent",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": {
            "mongodb": db_status,
            "whatsapp": "configured" if wa_configured else "not_configured",
            "claude_ai": "configured" if EMERGENT_LLM_KEY else "not_configured",
            "whisper": "configured" if EMERGENT_LLM_KEY else "not_configured",
            "duffel": "sandbox" if is_duffel_sandbox() else ("configured" if DUFFEL_API_KEY else "not_configured"),
            "stripe": "configured" if stripe_configured else "not_configured",
            "mtn_momo": "configured" if momo_configured else "not_configured",
            "moov_money": "configured" if moov_configured else "not_configured",
        },
        "payment_operators": {
            "mtn_momo": _status(momo_configured),
            "moov_money": _status(moov_configured),
            "google_pay": _status(stripe_configured),
            "apple_pay": _status(stripe_configured),
        },
        "integrations": {
            "claude_ai": "configured" if EMERGENT_LLM_KEY else "missing",
            "duffel": "sandbox" if is_duffel_sandbox() else ("configured" if DUFFEL_API_KEY else "missing"),
            "whatsapp": "configured" if wa_configured else "missing",
            "whisper": "configured" if EMERGENT_LLM_KEY else "missing",
        }
    }


@router.get("/")
async def root():
    return {
        "name": "Travelio WhatsApp Travel Agent",
        "version": "7.0",
        "description": "WhatsApp-based flight booking with Duffel GDS, AES-256 encryption, and smart airport recognition",
        "endpoints": {
            "webhook": "/api/webhook",
            "health": "/api/health",
            "legal_terms": "/api/legal/terms",
            "legal_privacy": "/api/legal/privacy",
            "payment": "/api/pay/{booking_id}",
            "verify_qr": "/api/verify_qr/{booking_ref}",
            "simulate": "/api/test/simulate"
        }
    }
