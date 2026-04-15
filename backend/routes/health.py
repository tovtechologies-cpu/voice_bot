"""Health and status routes with environment-aware mode detection."""
import logging
from datetime import datetime, timezone
from fastapi import APIRouter
from database import db
from config import (
    WHATSAPP_PHONE_ID, WHATSAPP_TOKEN, WHATSAPP_WEBHOOK_SECRET,
    WHATSAPP_API_VERSION, WHATSAPP_BUSINESS_PHONE, WHATSAPP_COUNTRY,
    EMERGENT_LLM_KEY, DUFFEL_API_KEY, STRIPE_SECRET_KEY,
    MOMO_API_USER, MOOV_API_KEY,
    get_duffel_mode, get_momo_mode, get_moov_mode, get_stripe_mode
)

router = APIRouter()
logger = logging.getLogger("HealthRoutes")


def _get_whatsapp_status() -> dict:
    """Build detailed WhatsApp status for health check."""
    from routes.webhook import get_last_verified_at
    from services.whatsapp import get_last_message_sent_at, get_last_message_received_at

    is_configured = bool(
        WHATSAPP_PHONE_ID and WHATSAPP_TOKEN
        and WHATSAPP_PHONE_ID != 'your_phone_id_here'
        and WHATSAPP_TOKEN != 'your_token_here'
    )

    if is_configured:
        status = "live"
        mode = "production"
    else:
        status = "mock"
        mode = "mock"

    phone_masked = WHATSAPP_PHONE_ID[:6] + "***" if len(WHATSAPP_PHONE_ID) > 6 else WHATSAPP_PHONE_ID

    # Format business number for display
    biz_phone = WHATSAPP_BUSINESS_PHONE
    if len(biz_phone) == 13 and biz_phone.startswith("229"):
        biz_display = f"+{biz_phone[:3]} {biz_phone[3:5]} {biz_phone[5:7]} {biz_phone[7:9]} {biz_phone[9:11]} {biz_phone[11:]}"
    elif biz_phone:
        biz_display = f"+{biz_phone}"
    else:
        biz_display = None

    return {
        "status": status,
        "mode": mode,
        "api_version": WHATSAPP_API_VERSION,
        "country": f"{WHATSAPP_COUNTRY}",
        "phone_id_masked": phone_masked,
        "token_set": bool(WHATSAPP_TOKEN and WHATSAPP_TOKEN != 'your_token_here'),
        "webhook_secret_set": bool(WHATSAPP_WEBHOOK_SECRET),
        "business_number": biz_display,
        "last_message_received": get_last_message_received_at(),
        "last_message_sent": get_last_message_sent_at(),
    }


@router.get("/health")
async def health():
    try:
        await db.command("ping")
        db_status = "connected"
    except Exception:
        db_status = "disconnected"

    duffel_mode = get_duffel_mode()
    momo_mode = get_momo_mode()
    moov_mode = get_moov_mode()
    stripe_mode = get_stripe_mode()

    wa_status = _get_whatsapp_status()

    from routes.webhook import get_last_verified_at
    last_verified = get_last_verified_at()

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "version": "7.1",
        "type": "WhatsApp Agent",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": {
            "mongodb": db_status,
            "whatsapp": wa_status["status"],
            "claude_ai": "configured" if EMERGENT_LLM_KEY else "not_configured",
            "whisper": "configured" if EMERGENT_LLM_KEY else "not_configured",
            "duffel": duffel_mode.lower(),
            "stripe": stripe_mode.lower(),
            "mtn_momo": momo_mode.lower(),
            "moov_money": moov_mode.lower(),
        },
        "whatsapp": wa_status,
        "payment_operators": {
            "mtn_momo": {"status": momo_mode.lower(), "mode": momo_mode},
            "moov_money": {"status": moov_mode.lower(), "mode": moov_mode},
            "google_pay": {"status": stripe_mode.lower(), "mode": stripe_mode},
            "apple_pay": {"status": stripe_mode.lower(), "mode": stripe_mode},
        },
        "integrations": {
            "claude_ai": "configured" if EMERGENT_LLM_KEY else "missing",
            "duffel": duffel_mode.lower(),
            "whatsapp": wa_status["status"],
            "whisper": "configured" if EMERGENT_LLM_KEY else "missing",
        },
        "webhook_security": {
            "signature_verification": "active" if WHATSAPP_WEBHOOK_SECRET else "disabled",
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
