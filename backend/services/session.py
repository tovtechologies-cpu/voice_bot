"""Session and passenger management service."""
import re
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
from database import db
from config import SESSION_TIMEOUT_MINUTES, MAX_THIRD_PARTY_PROFILES
from models import ConversationState
from services.security import encrypt_passenger_pii, decrypt_passenger_pii

logger = logging.getLogger("SessionService")

NAME_REGEX = re.compile(r"^[a-zA-Z\u00C0-\u00FF\s\-']+$")
PASSPORT_REGEX = re.compile(r"^[A-Za-z0-9]{6,9}$")


def _default_session_fields(phone: str) -> Dict:
    return {
        "phone": phone,
        "state": ConversationState.IDLE,
        "language": "fr",
        "intent": {},
        "flights": [],
        "selected_flight": None,
        "selected_payment_method": None,
        "booking_id": None,
        "booking_ref": None,
        "payment_reference": None,
        "passenger_id": None,
        "booking_passenger_id": None,
        "enrollment_data": {},
        "enrolling_for": None,
        "last_activity": datetime.now(timezone.utc).isoformat()
    }


async def get_or_create_session(phone: str) -> Dict:
    session = await db.sessions.find_one({"phone": phone}, {"_id": 0})
    if session:
        last = session.get("last_activity")
        if last:
            try:
                last_dt = datetime.fromisoformat(last)
                if datetime.now(timezone.utc) - last_dt > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
                    logger.info(f"Session expired for {phone}")
                    await db.sessions.update_one({"phone": phone}, {"$set": _default_session_fields(phone)})
                    session = await db.sessions.find_one({"phone": phone}, {"_id": 0})
                    session["_expired"] = True
                    return session
            except (ValueError, TypeError):
                pass
        await db.sessions.update_one({"phone": phone}, {"$set": {"last_activity": datetime.now(timezone.utc).isoformat()}})
        return session
    new_session = _default_session_fields(phone)
    await db.sessions.insert_one(new_session)
    return new_session


async def update_session(phone: str, updates: Dict):
    updates["last_activity"] = datetime.now(timezone.utc).isoformat()
    await db.sessions.update_one({"phone": phone}, {"$set": updates})


async def clear_session(phone: str):
    await db.sessions.update_one({"phone": phone}, {"$set": {
        "state": ConversationState.IDLE, "intent": {}, "flights": [],
        "selected_flight": None, "selected_payment_method": None,
        "booking_id": None, "booking_ref": None, "payment_reference": None,
        "enrollment_data": {}, "enrolling_for": None, "booking_passenger_id": None,
        "last_activity": datetime.now(timezone.utc).isoformat()
    }})


async def get_passenger_by_phone(phone: str) -> Optional[Dict]:
    passenger = await db.passengers.find_one({"whatsapp_phone": phone}, {"_id": 0})
    return decrypt_passenger_pii(passenger) if passenger else None


async def save_passenger(data: Dict) -> str:
    passenger = {
        "id": str(uuid.uuid4()),
        "whatsapp_phone": data.get("whatsapp_phone"),
        "firstName": data.get("firstName", ""),
        "lastName": data.get("lastName", ""),
        "passportNumber": data.get("passportNumber"),
        "nationality": data.get("nationality"),
        "dateOfBirth": data.get("dateOfBirth"),
        "expiryDate": data.get("expiryDate"),
        "created_by_phone": data.get("created_by_phone"),
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "updatedAt": datetime.now(timezone.utc).isoformat()
    }
    # Encrypt PII before storing
    encrypted = encrypt_passenger_pii(passenger)
    await db.passengers.insert_one(encrypted)
    return passenger["id"]


async def get_third_party_passengers(phone: str) -> List[Dict]:
    cursor = db.passengers.find({"created_by_phone": phone, "whatsapp_phone": None}, {"_id": 0}).sort("createdAt", -1).limit(MAX_THIRD_PARTY_PROFILES)
    passengers = await cursor.to_list(length=MAX_THIRD_PARTY_PROFILES)
    return [decrypt_passenger_pii(p) for p in passengers]


async def get_passenger_by_id(passenger_id: str) -> Optional[Dict]:
    passenger = await db.passengers.find_one({"id": passenger_id}, {"_id": 0})
    return decrypt_passenger_pii(passenger) if passenger else None


def validate_name(name: str) -> bool:
    return bool(NAME_REGEX.match(name)) and len(name.strip()) >= 2


def validate_passport_number(pp: str) -> bool:
    return bool(PASSPORT_REGEX.match(pp.strip()))


def title_case_name(name: str) -> str:
    if name == name.upper() and len(name) > 1:
        return name.title()
    return name
