"""Human-in-the-loop service — Phase C."""
import logging
from typing import Dict, Optional
from datetime import datetime, timezone
import httpx
from config import HUMAN_REVIEW_WEBHOOK, API_TIMEOUT
from database import db
from utils.helpers import mask_phone

logger = logging.getLogger("HITLService")

# Confidence and amount thresholds
CONFIDENCE_THRESHOLD = 0.85
HIGH_VALUE_THRESHOLD_EUR = 500.0


def needs_human_review(confidence: float, amount_eur: float = 0) -> bool:
    """Check if a transaction needs human review."""
    if confidence < CONFIDENCE_THRESHOLD:
        return True
    if amount_eur > HIGH_VALUE_THRESHOLD_EUR:
        return True
    return False


async def trigger_human_review(phone: str, original_text: str, translated_text: str,
                                source_lang: str, confidence: float,
                                reason: str, context: Dict = None) -> str:
    """Send a review request to the HITL webhook and store in DB."""
    review_id = f"HITL-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{phone[-4:]}"

    review = {
        "review_id": review_id,
        "phone": phone,
        "phone_masked": mask_phone(phone),
        "original_text": original_text,
        "translated_text": translated_text,
        "source_language": source_lang,
        "confidence": confidence,
        "reason": reason,
        "context": context or {},
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "resolved_at": None,
        "resolved_by": None,
        "resolution": None,
    }

    await db.hitl_reviews.insert_one(review)
    review.pop("_id", None)

    # Send webhook alert
    if HUMAN_REVIEW_WEBHOOK:
        try:
            async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
                resp = await client.post(HUMAN_REVIEW_WEBHOOK, json={
                    "type": "hitl_review_request",
                    "review_id": review_id,
                    "phone_masked": mask_phone(phone),
                    "original_text": original_text[:200],
                    "translated_text": translated_text[:200],
                    "source_language": source_lang,
                    "confidence": confidence,
                    "reason": reason,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                if resp.status_code in [200, 201, 202, 204]:
                    logger.info(f"[HITL] Review alert sent: {review_id}")
                else:
                    logger.warning(f"[HITL] Webhook returned {resp.status_code}")
        except Exception as e:
            logger.error(f"[HITL] Webhook failed: {e}")
    else:
        logger.info(f"[HITL] Review created (no webhook configured): {review_id}")

    return review_id


async def resolve_review(review_id: str, resolved_by: str, resolution: str,
                          corrected_text: str = None) -> bool:
    """Mark a HITL review as resolved."""
    update = {
        "status": "resolved",
        "resolved_at": datetime.now(timezone.utc).isoformat(),
        "resolved_by": resolved_by,
        "resolution": resolution,
    }
    if corrected_text:
        update["corrected_text"] = corrected_text

    result = await db.hitl_reviews.update_one(
        {"review_id": review_id, "status": "pending"},
        {"$set": update}
    )
    if result.modified_count > 0:
        logger.info(f"[HITL] Review resolved: {review_id} by {resolved_by}")
        return True
    return False


async def get_pending_reviews(limit: int = 20) -> list:
    """Get pending HITL reviews for dashboard."""
    reviews = await db.hitl_reviews.find(
        {"status": "pending"}, {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    return reviews
