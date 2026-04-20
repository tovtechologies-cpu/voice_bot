"""Travelioo v7.1 - WhatsApp Travel Booking Agent
Modular FastAPI backend with Duffel GDS, AES-256 encryption, and smart airport recognition.
"""
import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import client, db
from config import CORS_ORIGINS
from services.security import cleanup_rate_limits

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Travelioo")

# Background tasks
async def periodic_cleanup():
    """Run periodic cleanup tasks."""
    while True:
        try:
            await cleanup_rate_limits()
            # Data retention: cleanup old sessions (30 days)
            from datetime import datetime, timezone, timedelta
            cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
            await db.sessions.delete_many({"last_activity": {"$lt": cutoff}})
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
        await asyncio.sleep(3600)  # Every hour


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Travelioo v7.1 starting...")
    try:
        await db.command("ping")
        logger.info("MongoDB connected")
    except Exception as e:
        logger.error(f"MongoDB connection failed: {e}")

    # Create indexes (non-fatal — app works without them, just slower queries)
    try:
        await db.sessions.create_index("phone", unique=True)
        await db.passengers.create_index("whatsapp_phone")
        await db.passengers.create_index("id", unique=True)
        await db.bookings.create_index("booking_ref")
        await db.bookings.create_index("phone")
        await db.rate_limits.create_index("timestamp", expireAfterSeconds=3600)
        await db.rate_limits.create_index([("phone", 1), ("action", 1)])
        await db.shadow_profiles.create_index("phone_number", unique=True)
        await db.shadow_profiles.create_index("user_id", unique=True)
        await db.shadow_profiles.create_index("whatsapp_id", sparse=True)
        await db.shadow_profiles.create_index("telegram_id", sparse=True)
        await db.hitl_reviews.create_index("review_id", unique=True)
        await db.hitl_reviews.create_index("status")
        await db.hitl_reviews.create_index("phone")
        await db.fare_cache.create_index("route", unique=True)
        await db.fare_alerts.create_index([("phone", 1), ("route", 1), ("sent_at", -1)])
        logger.info("MongoDB indexes created")
    except Exception as e:
        logger.warning(f"Index creation skipped (non-fatal): {e}")

    # Log environment modes
    from config import get_duffel_mode, get_momo_mode, get_moov_mode, get_stripe_mode, WHATSAPP_WEBHOOK_SECRET, WHATSAPP_PHONE_ID, WHATSAPP_TOKEN, CELTIIS_API_KEY
    duffel_mode = get_duffel_mode()
    momo_mode = get_momo_mode()
    moov_mode = get_moov_mode()
    stripe_mode = get_stripe_mode()
    celtiis_mode = "PRODUCTION" if (CELTIIS_API_KEY and CELTIIS_API_KEY != 'your_key_here') else "MOCK"
    wa_configured = WHATSAPP_PHONE_ID and WHATSAPP_TOKEN and WHATSAPP_PHONE_ID != 'your_phone_id_here'

    logger.info(f"[DUFFEL] Mode: {duffel_mode}" + (" (real flights)" if duffel_mode == "PRODUCTION" else " (test data)" if duffel_mode == "SANDBOX" else " (no key configured)"))
    logger.info(f"[PAYMENTS] Celtiis Cash: {celtiis_mode} (Benin priority)")
    logger.info(f"[PAYMENTS] MTN MoMo: {momo_mode}")
    logger.info(f"[PAYMENTS] Moov Money: {moov_mode}")
    logger.info(f"[PAYMENTS] Stripe: {stripe_mode}")
    logger.info(f"[WHATSAPP] {'Configured' if wa_configured else 'NOT configured (messages logged only)'}")
    if WHATSAPP_WEBHOOK_SECRET:
        logger.info("[WEBHOOK] Signature verification: ACTIVE")
    else:
        logger.warning("[WARNING] WHATSAPP_WEBHOOK_SECRET not set. Webhook signature verification is DISABLED. Set this variable before going to production.")

    # Start periodic cleanup
    cleanup_task = asyncio.create_task(periodic_cleanup())
    # Start disruption monitoring (check every 15 minutes)
    async def periodic_disruption_check():
        while True:
            try:
                from services.disruption import monitor_active_bookings
                await monitor_active_bookings()
            except Exception as e:
                logger.error(f"Disruption monitor error: {e}")
            await asyncio.sleep(900)  # Every 15 minutes
    disruption_task = asyncio.create_task(periodic_disruption_check())
    # Start fare alert monitoring (check every 24 hours)
    async def periodic_fare_check():
        await asyncio.sleep(60)  # Wait 1 min after startup
        while True:
            try:
                from services.fare_alerts import monitor_fares_for_all_users
                await monitor_fares_for_all_users()
            except Exception as e:
                logger.error(f"Fare alert monitor error: {e}")
            await asyncio.sleep(86400)  # Every 24 hours
    fare_task = asyncio.create_task(periodic_fare_check())
    logger.info("Travelioo v7.1 ready")
    yield

    # Shutdown
    cleanup_task.cancel()
    disruption_task.cancel()
    fare_task.cancel()
    client.close()
    logger.info("Travelioo v7.1 shutdown")


# Create app
app = FastAPI(title="Travelioo", version="7.1", lifespan=lifespan)

# CORS
origins = CORS_ORIGINS.split(",") if CORS_ORIGINS != "*" else ["*"]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# Mount routes
from routes.webhook import router as webhook_router
from routes.payments import router as payments_router
from routes.legal import router as legal_router
from routes.health import router as health_router
from routes.test import router as test_router
from routes.telegram_webhook import router as telegram_router
from routes.hitl import router as hitl_router
from routes.disruptions import router as disruption_router
from routes.fare_alerts import router as fare_alerts_router

# All routes under /api prefix
from fastapi import APIRouter
api_router = APIRouter(prefix="/api")
api_router.include_router(webhook_router)
api_router.include_router(payments_router)
api_router.include_router(legal_router)
api_router.include_router(health_router)
api_router.include_router(test_router)
api_router.include_router(telegram_router)
api_router.include_router(hitl_router)
api_router.include_router(disruption_router)
api_router.include_router(fare_alerts_router)

app.include_router(api_router)


# Root route (outside /api prefix) for Railway health checks and browser access
@app.get("/")
async def app_root():
    return {
        "name": "Travelioo",
        "version": "7.1",
        "status": "running",
        "health": "/api/health",
        "webhook": "/api/webhook",
        "telegram": "/api/telegram/webhook",
    }


# Static HTML pages (outside /api prefix)
from fastapi.responses import HTMLResponse

@app.get("/privacy", response_class=HTMLResponse)
async def privacy_page():
    return """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Politique de Confidentialit\u00e9 \u2014 Travelioo</title>
<style>
  body { font-family: Arial, sans-serif; max-width: 800px;
         margin: 40px auto; padding: 20px; color: #333; }
  h1 { color: #6C63FF; }
  h2 { color: #0A0F1E; margin-top: 30px; }
</style>
</head>
<body>
<h1>Politique de Confidentialit\u00e9 \u2014 Travelioo</h1>
<p><em>Derni\u00e8re mise \u00e0 jour : Avril 2026</em></p>

<h2>1. Collecte des donn\u00e9es</h2>
<p>Travelioo collecte les informations suivantes
dans le cadre de la r\u00e9servation de billets d\u2019avion :
nom, pr\u00e9nom, date de naissance, num\u00e9ro de passeport,
nationalit\u00e9, num\u00e9ro de t\u00e9l\u00e9phone WhatsApp ou Telegram.</p>

<h2>2. Utilisation des donn\u00e9es</h2>
<p>Vos donn\u00e9es sont utilis\u00e9es exclusivement pour :
\u00e9mettre vos billets d\u2019avion, v\u00e9rifier votre identit\u00e9
aupr\u00e8s des compagnies a\u00e9riennes, vous envoyer votre
billet et les rappels de vol.</p>

<h2>3. Protection des donn\u00e9es</h2>
<p>Toutes les donn\u00e9es personnelles sont chiffr\u00e9es
avec AES-256-GCM. Elles ne sont jamais revendues
ni partag\u00e9es avec des tiers \u00e0 des fins commerciales.</p>

<h2>4. Conservation des donn\u00e9es</h2>
<p>Vos donn\u00e9es sont conserv\u00e9es pendant 3 ans
maximum apr\u00e8s votre derni\u00e8re r\u00e9servation.</p>

<h2>5. Suppression des donn\u00e9es</h2>
<p>Vous pouvez supprimer votre profil \u00e0 tout moment
en envoyant le message SUPPRIMER MES DONN\u00c9ES
sur WhatsApp (+229 01 29 88 83 69) ou Telegram
(@travelioo_bot).</p>

<h2>6. Paiements</h2>
<p>Les transactions sont trait\u00e9es par Celtiis Cash,
MTN MoMo, Moov Money et Stripe. Travelioo ne
stocke aucune information bancaire.</p>

<h2>7. Contact</h2>
<p>Pour toute question : bryan@travelioo.com<br>
WhatsApp : +229 01 97 97 33 46</p>
</body>
</html>"""


@app.get("/terms", response_class=HTMLResponse)
async def terms_page():
    return """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Conditions G\u00e9n\u00e9rales d\u2019Utilisation \u2014 Travelioo</title>
<style>
  body { font-family: Arial, sans-serif; max-width: 800px;
         margin: 40px auto; padding: 20px; color: #333; }
  h1 { color: #6C63FF; }
  h2 { color: #0A0F1E; margin-top: 30px; }
</style>
</head>
<body>
<h1>Conditions G\u00e9n\u00e9rales d\u2019Utilisation \u2014 Travelioo</h1>
<p><em>Derni\u00e8re mise \u00e0 jour : Avril 2026</em></p>

<h2>1. Objet</h2>
<p>Travelioo est un service de r\u00e9servation de billets d\u2019avion
accessible via WhatsApp et Telegram. Les pr\u00e9sentes conditions
r\u00e9gissent l\u2019utilisation du service.</p>

<h2>2. Inscription et profil</h2>
<p>En utilisant Travelioo, vous acceptez de fournir des informations
exactes (nom, passeport) n\u00e9cessaires \u00e0 l\u2019\u00e9mission de votre billet.
Vous \u00eates responsable de l\u2019exactitude de ces informations.</p>

<h2>3. R\u00e9servation et paiement</h2>
<p>Les prix affich\u00e9s incluent le tarif a\u00e9rien et les frais de service
Travelioo. Le paiement est effectu\u00e9 via Celtiis Cash, MTN MoMo,
Moov Money ou carte bancaire (Stripe). La r\u00e9servation est confirm\u00e9e
uniquement apr\u00e8s r\u00e9ception compl\u00e8te du paiement.</p>

<h2>4. Frais de service Travelioo</h2>
<p>Les frais de service Travelioo sont non remboursables en toute
circonstance, y compris en cas d\u2019annulation ou de modification
du billet.</p>

<h2>5. Annulation et remboursement</h2>
<p>Les conditions d\u2019annulation et de remboursement d\u00e9pendent du
type de billet achet\u00e9 (Budget, Standard, Flex). Ces conditions
vous sont communiqu\u00e9es avant la confirmation du paiement.
Le remboursement porte uniquement sur le tarif a\u00e9rien, d\u00e9duction
faite des p\u00e9nalit\u00e9s \u00e9ventuelles de la compagnie a\u00e9rienne.</p>

<h2>6. Paiement divis\u00e9</h2>
<p>Le paiement peut \u00eatre divis\u00e9 entre 2 \u00e0 5 num\u00e9ros. Des frais de
r\u00e9conciliation de 2\u20ac (1 300 XOF) par payeur suppl\u00e9mentaire
s\u2019appliquent. Si un payeur ne confirme pas dans le d\u00e9lai imparti,
tous les paiements re\u00e7us sont automatiquement rembours\u00e9s.</p>

<h2>7. Perturbations de vol</h2>
<p>En cas d\u2019annulation par la compagnie a\u00e9rienne, Travelioo
d\u00e9clenche automatiquement le remboursement du tarif a\u00e9rien.
En cas de retard sup\u00e9rieur \u00e0 2 heures, une option de
relogement sur un autre vol vous est propos\u00e9e.</p>

<h2>8. Limitation de responsabilit\u00e9</h2>
<p>Travelioo agit en qualit\u00e9 d\u2019interm\u00e9diaire entre vous et les
compagnies a\u00e9riennes. Travelioo n\u2019est pas responsable des
retards, annulations ou modifications d\u00e9cid\u00e9es par les
compagnies a\u00e9riennes.</p>

<h2>9. Donn\u00e9es personnelles</h2>
<p>Voir notre <a href="/privacy">Politique de Confidentialit\u00e9</a>
pour les d\u00e9tails sur la collecte et le traitement de vos
donn\u00e9es personnelles.</p>

<h2>10. Contact</h2>
<p>Pour toute r\u00e9clamation : bryan@travelioo.com<br>
WhatsApp : +229 01 97 97 33 46</p>
</body>
</html>"""
