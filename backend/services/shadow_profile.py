"""Shadow Profile service — unified cross-channel user profiles."""
import uuid
import logging
from typing import Dict, Optional
from datetime import datetime, timezone
from database import db
from services.security import encrypt_field, decrypt_field

logger = logging.getLogger("ShadowProfileService")


async def get_or_create_shadow_profile(phone: str, channel: str = "whatsapp",
                                        channel_id: str = None) -> Dict:
    """Get existing or create new shadow profile. Matched by phone number."""
    existing = await db.shadow_profiles.find_one({"phone_number": phone}, {"_id": 0})
    if existing:
        # Update channel link if new
        updates = {"last_active": datetime.now(timezone.utc).isoformat()}
        if channel == "whatsapp" and channel_id and not existing.get("whatsapp_id"):
            updates["whatsapp_id"] = channel_id
        elif channel == "telegram" and channel_id and not existing.get("telegram_id"):
            updates["telegram_id"] = channel_id
        if updates:
            await db.shadow_profiles.update_one({"phone_number": phone}, {"$set": updates})
        existing.update(updates)
        return existing

    profile = {
        "user_id": str(uuid.uuid4()),
        "whatsapp_id": channel_id if channel == "whatsapp" else None,
        "telegram_id": channel_id if channel == "telegram" else None,
        "phone_number": phone,
        "language_pref": "fr",
        "country_code": "BJ",
        "travel_history": [],
        "payment_methods": [],
        "trusted_payers": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_active": datetime.now(timezone.utc).isoformat(),
        "consent_granted": False,
        "consent_at": None,
    }
    await db.shadow_profiles.insert_one(profile)
    profile.pop("_id", None)
    return profile


async def update_shadow_profile(phone: str, updates: Dict):
    """Update shadow profile fields."""
    await db.shadow_profiles.update_one(
        {"phone_number": phone},
        {"$set": {**updates, "last_active": datetime.now(timezone.utc).isoformat()}}
    )


async def link_channel(phone: str, channel: str, channel_id: str):
    """Link a WhatsApp or Telegram ID to an existing profile."""
    field = "whatsapp_id" if channel == "whatsapp" else "telegram_id"
    await db.shadow_profiles.update_one(
        {"phone_number": phone}, {"$set": {field: channel_id}})


async def add_to_travel_history(phone: str, booking_ref: str):
    """Append a booking reference to travel history."""
    await db.shadow_profiles.update_one(
        {"phone_number": phone},
        {"$push": {"travel_history": {"ref": booking_ref, "at": datetime.now(timezone.utc).isoformat()}}}
    )


async def add_payment_method(phone: str, method: str):
    """Remember a payment number used by this user."""
    await db.shadow_profiles.update_one(
        {"phone_number": phone},
        {"$addToSet": {"payment_methods": method}}
    )


async def add_trusted_payer(phone: str, payer_phone: str):
    """Remember a trusted split-payment payer."""
    await db.shadow_profiles.update_one(
        {"phone_number": phone},
        {"$addToSet": {"trusted_payers": payer_phone}}
    )


async def delete_user_data(phone: str) -> bool:
    """GDPR/APDP data deletion — remove all user data across collections."""
    logger.info(f"[DELETION] Processing data deletion for ****{phone[-4:]}")
    try:
        await db.shadow_profiles.delete_many({"phone_number": phone})
        await db.passengers.delete_many({"whatsapp_phone": phone})
        await db.sessions.delete_many({"phone": phone})
        # Keep bookings for financial compliance but anonymize
        await db.bookings.update_many(
            {"phone": phone},
            {"$set": {
                "passenger_name": "DELETED",
                "passenger_passport": None,
                "phone": f"deleted_{phone[-4:]}",
                "anonymized_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        logger.info(f"[DELETION] Complete for ****{phone[-4:]}")
        return True
    except Exception as e:
        logger.error(f"[DELETION] Failed for ****{phone[-4:]}: {e}")
        return False


async def get_profile_by_user_id(user_id: str) -> Optional[Dict]:
    """Look up shadow profile by internal Travelioo user_id."""
    return await db.shadow_profiles.find_one({"user_id": user_id}, {"_id": 0})
