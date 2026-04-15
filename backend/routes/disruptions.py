"""Disruption notification routes — Phase C SAV."""
import logging
from fastapi import APIRouter
from services.disruption import process_disruption, DELAY, CANCELLATION, GATE_CHANGE, SCHEDULE_CHANGE
from database import db

router = APIRouter(prefix="/disruptions")
logger = logging.getLogger("DisruptionRoutes")


@router.post("/notify")
async def trigger_disruption(payload: dict):
    """Manually trigger a disruption notification (for testing or webhook from GDS)."""
    booking_ref = payload.get("booking_ref")
    disruption_type = payload.get("type", DELAY)
    details = payload.get("details", {})

    if not booking_ref:
        return {"error": "booking_ref required"}

    if disruption_type not in [DELAY, CANCELLATION, GATE_CHANGE, SCHEDULE_CHANGE]:
        return {"error": "Invalid type. Use: DELAY, CANCELLATION, GATE_CHANGE, SCHEDULE_CHANGE"}

    success = await process_disruption(booking_ref, disruption_type, details)
    return {"status": "notified" if success else "failed", "booking_ref": booking_ref, "type": disruption_type}


@router.get("/events/{booking_ref}")
async def get_disruption_events(booking_ref: str):
    """Get disruption events for a booking."""
    booking = await db.bookings.find_one({"booking_ref": booking_ref}, {"_id": 0})
    if not booking:
        return {"error": "Booking not found"}
    events = booking.get("disruption_events", [])
    return {"booking_ref": booking_ref, "events": events, "count": len(events)}
