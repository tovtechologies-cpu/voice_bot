"""Travelio v7.0 - WhatsApp Travel Booking Agent
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
logger = logging.getLogger("Travelio")

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
    logger.info("Travelio v7.0 starting...")
    try:
        await db.command("ping")
        logger.info("MongoDB connected")
    except Exception as e:
        logger.error(f"MongoDB connection failed: {e}")

    # Create indexes
    await db.sessions.create_index("phone", unique=True)
    await db.passengers.create_index("whatsapp_phone")
    await db.passengers.create_index("id", unique=True)
    await db.bookings.create_index("booking_ref")
    await db.bookings.create_index("phone")
    await db.rate_limits.create_index("timestamp", expireAfterSeconds=3600)
    await db.rate_limits.create_index([("phone", 1), ("action", 1)])

    # Start periodic cleanup
    cleanup_task = asyncio.create_task(periodic_cleanup())
    logger.info("Travelio v7.0 ready")
    yield

    # Shutdown
    cleanup_task.cancel()
    client.close()
    logger.info("Travelio v7.0 shutdown")


# Create app
app = FastAPI(title="Travelio", version="7.0", lifespan=lifespan)

# CORS
origins = CORS_ORIGINS.split(",") if CORS_ORIGINS != "*" else ["*"]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# Mount routes
from routes.webhook import router as webhook_router
from routes.payments import router as payments_router
from routes.legal import router as legal_router
from routes.health import router as health_router
from routes.test import router as test_router

# All routes under /api prefix
from fastapi import APIRouter
api_router = APIRouter(prefix="/api")
api_router.include_router(webhook_router)
api_router.include_router(payments_router)
api_router.include_router(legal_router)
api_router.include_router(health_router)
api_router.include_router(test_router)

app.include_router(api_router)
