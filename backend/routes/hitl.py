"""HITL (Human-in-the-Loop) review routes — Phase C."""
import logging
from fastapi import APIRouter
from services.hitl import get_pending_reviews, resolve_review
from database import db

router = APIRouter(prefix="/hitl")
logger = logging.getLogger("HITLRoutes")


@router.get("/reviews")
async def list_reviews(status: str = "pending", limit: int = 20):
    """List HITL reviews for the human review dashboard."""
    reviews = await db.hitl_reviews.find(
        {"status": status}, {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    return {"reviews": reviews, "count": len(reviews)}


@router.post("/reviews/{review_id}/resolve")
async def resolve(review_id: str, payload: dict):
    """Resolve a HITL review."""
    resolved_by = payload.get("resolved_by", "admin")
    resolution = payload.get("resolution", "approved")
    corrected_text = payload.get("corrected_text")

    success = await resolve_review(review_id, resolved_by, resolution, corrected_text)
    if success:
        # If corrected text provided, re-process the message
        if corrected_text:
            review = await db.hitl_reviews.find_one({"review_id": review_id}, {"_id": 0})
            if review:
                phone = review.get("phone")
                from conversation.handler import handle_message
                await handle_message(phone, corrected_text)
                return {"status": "resolved_and_reprocessed", "review_id": review_id}
        return {"status": "resolved", "review_id": review_id}
    return {"status": "not_found_or_already_resolved", "review_id": review_id}
