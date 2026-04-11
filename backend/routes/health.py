"""Health and status routes with environment-aware mode detection."""
import logging
from datetime import datetime, timezone
from fastapi import APIRouter
from database import db
from config import (
    WHATSAPP_PHONE_ID, WHATSAPP_TOKEN, WHATSAPP_WEBHOOK_SECRET,
    EMERGENT_LLM_KEY, DUFFEL_API_KEY, STRIPE_SECRET_KEY,
    MOMO_API_USER, MOOV_API_KEY,
    get_duffel_mode, get_momo_mode, get_moov_mode, get_stripe_mode
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
    duffel_mode = get_duffel_mode()
    momo_mode = get_momo_mode()
    moov_mode = get_moov_mode()
    stripe_mode = get_stripe_mode()

    # Webhook security status
    sig_active = bool(WHATSAPP_WEBHOOK_SECRET)
    from routes.webhook import get_last_verified_at
    last_verified = get_last_verified_at()

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "version": "7.1",
        "type": "WhatsApp Agent",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": {
            "mongodb": db_status,
            "whatsapp": "configured" if wa_configured else "not_configured",
            "claude_ai": "configured" if EMERGENT_LLM_KEY else "not_configured",
            "whisper": "configured" if EMERGENT_LLM_KEY else "not_configured",
            "duffel": duffel_mode.lower(),
            "stripe": stripe_mode.lower(),
            "mtn_momo": momo_mode.lower(),
            "moov_money": moov_mode.lower(),
        },
        "payment_operators": {
            "mtn_momo": {"status": momo_mode.lower(), "mode": momo_mode},
            "moov_money": {"status": moov_mode.lower(), "mode": moov_mode},
            "google_pay": {"status": stripe_mode.lower(), "mode": stripe_mode},
            "apple_pay": {"status": stripe_mode.lower(), "mode": stripe_mode},
        },
        "integrations": {
            "claude_ai": "configured" if EMERGENT_LLM_KEY else "missing",
            "duffel": duffel_mode.lower(),
            "whatsapp": "configured" if wa_configured else "missing",
            "whisper": "configured" if EMERGENT_LLM_KEY else "missing",
        },
        "webhook_security": {
            "signature_verification": "active" if sig_active else "disabled",
            "last_verified": last_verified,
        },
        "environment_modes": {
            "duffel": duffel_mode,
            "mtn_momo": momo_mode,
            "moov_money": moov_mode,
            "stripe": stripe_mode,
        }
    }


@router.get("/")
async def root():
    return {
        "name": "Travelioo WhatsApp Travel Agent",
        "version": "7.1",
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
