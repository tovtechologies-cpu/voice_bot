"""Test simulation routes for development."""
import logging
from fastapi import APIRouter
from conversation.handler import handle_message
from database import db
from services.session import get_or_create_session

router = APIRouter(prefix="/test")
logger = logging.getLogger("TestRoutes")


@router.post("/simulate")
async def simulate_message(payload: dict):
    phone = payload.get("phone", "+22990000001")
    message = payload.get("message", "")
    audio_id = payload.get("audio_id")
    image_id = payload.get("image_id")
    channel = payload.get("channel", "whatsapp")

    if not message and not audio_id and not image_id:
        return {"error": "No message, audio_id, or image_id provided"}

    from services.channel import set_channel
    set_channel(phone, channel)

    if channel == "telegram":
        from services.telegram import register_chat
        register_chat(phone, payload.get("chat_id", 12345))

    await handle_message(phone, message, audio_id=audio_id, image_id=image_id)
    session = await db.sessions.find_one({"phone": phone}, {"_id": 0})
    return {"status": "processed", "session_state": session.get("state") if session else "unknown", "phone": phone, "channel": channel}


@router.get("/session/{phone}")
async def get_session(phone: str):
    session = await db.sessions.find_one({"phone": phone}, {"_id": 0})
    return session or {"error": "Session not found"}


@router.delete("/session/{phone}")
async def delete_session(phone: str):
    result = await db.sessions.delete_one({"phone": phone})
    return {"deleted": result.deleted_count > 0}


@router.get("/bookings/{phone}")
async def get_bookings(phone: str):
    bookings = await db.bookings.find({"phone": phone}, {"_id": 0}).sort("created_at", -1).limit(10).to_list(10)
    return {"bookings": bookings}


@router.post("/force_fail")
async def force_payment_fail(payload: dict):
    phone = payload.get("phone", "+22990000001")
    await db.sessions.update_one({"phone": phone}, {"$set": {"_test_force_fail": True}})
    return {"status": "fail_mode_enabled", "phone": phone}


@router.post("/clear_fail")
async def clear_payment_fail(payload: dict):
    phone = payload.get("phone", "+22990000001")
    await db.sessions.update_one({"phone": phone}, {"$set": {"_test_force_fail": False}})
    return {"status": "fail_mode_cleared"}
