"""Modification conversation handlers — cancels original booking when rebooking."""
import logging
from typing import Dict
from datetime import datetime, timezone
from models import ConversationState, calculate_refund
from services.session import update_session, clear_session
from services.whatsapp import send_whatsapp_message
from services.airport import get_city_name
from database import db
from conversation.cancellation import start_cancellation_flow, process_refund

logger = logging.getLogger("ModificationHandler")


async def start_modification_flow(phone: str, lang: str):
    bookings = await db.bookings.find({"phone": phone, "status": "confirmed"}, {"_id": 0}).sort("created_at", -1).limit(5).to_list(5)
    if not bookings:
        msg = "Aucune reservation a modifier." if lang == "fr" else "No bookings to modify."
        await send_whatsapp_message(phone, msg)
        return
    booking_ids = []
    if lang == "fr":
        msg = "Quelle reservation souhaitez-vous modifier ?\n\n"
    else:
        msg = "Which booking do you want to modify?\n\n"
    for i, b in enumerate(bookings, 1):
        msg += f"{i} {b['booking_ref']} -- {get_city_name(b.get('destination', ''))} -- {b.get('departure_date')}\n"
        booking_ids.append(b["booking_ref"])
    await update_session(phone, {"state": ConversationState.MODIFICATION_REQUESTED, "_mod_booking_list": booking_ids})
    await send_whatsapp_message(phone, msg)


async def handle_modification_requested(phone: str, text: str, session: Dict, lang: str):
    booking_list = session.get("_mod_booking_list", [])
    booking_ref = None
    try:
        idx = int(text) - 1
        if 0 <= idx < len(booking_list):
            booking_ref = booking_list[idx]
    except (ValueError, TypeError):
        pass
    if not booking_ref and text.upper().startswith("TRV-"):
        booking_ref = text.upper()
    if not booking_ref:
        msg = "Tapez un numero ou votre reference TRV-XXXXXX" if lang == "fr" else "Type a number or your TRV-XXXXXX reference"
        await send_whatsapp_message(phone, msg)
        return
    booking = await db.bookings.find_one({"booking_ref": booking_ref, "phone": phone}, {"_id": 0})
    if not booking:
        msg = "Reservation non trouvee." if lang == "fr" else "Booking not found."
        await send_whatsapp_message(phone, msg)
        return
    if not booking.get("change_allowed", False):
        if lang == "fr":
            msg = """Billet non modifiable.
1 Voir conditions d'annulation
2 Conserver"""
        else:
            msg = """Ticket not modifiable.
1 View cancellation conditions
2 Keep it"""
        await update_session(phone, {"state": ConversationState.MODIFICATION_CONFIRM, "_mod_booking_ref": booking_ref, "_mod_allowed": False})
        await send_whatsapp_message(phone, msg)
        return
    change_penalty = booking.get("change_penalty_eur", 0) or 0
    if lang == "fr":
        msg = f"""Billet modifiable.
Penalite de modification : {change_penalty}EUR

Que souhaitez-vous modifier ?
1 Date de depart
2 Annuler plutot

L'ancienne reservation sera annulee et une nouvelle sera creee.
La penalite de {change_penalty}EUR sera appliquee."""
    else:
        msg = f"""Ticket modifiable.
Modification penalty: {change_penalty}EUR

What would you like to change?
1 Departure date
2 Cancel instead

The original booking will be cancelled and a new one created.
A penalty of {change_penalty}EUR will apply."""
    await update_session(phone, {"state": ConversationState.MODIFICATION_CONFIRM, "_mod_booking_ref": booking_ref, "_mod_allowed": True, "_mod_penalty": change_penalty})
    await send_whatsapp_message(phone, msg)


async def handle_modification_confirm(phone: str, text: str, session: Dict, lang: str):
    allowed = session.get("_mod_allowed", False)
    booking_ref = session.get("_mod_booking_ref")
    if not allowed:
        if text == "1":
            await update_session(phone, {"state": ConversationState.IDLE})
            await start_cancellation_flow(phone, lang)
            return
        await clear_session(phone)
        msg = "Reservation conservee." if lang == "fr" else "Booking kept."
        await send_whatsapp_message(phone, msg)
        return
    if text == "2":
        await update_session(phone, {"state": ConversationState.IDLE})
        await start_cancellation_flow(phone, lang)
        return
    if text == "1":
        # Cancel the original booking first
        booking = await db.bookings.find_one({"booking_ref": booking_ref}, {"_id": 0})
        if booking:
            now_utc = datetime.now(timezone.utc)
            await db.bookings.update_one(
                {"booking_ref": booking_ref},
                {"$set": {
                    "status": "modified_cancelled",
                    "cancellation_timestamp": now_utc.isoformat(),
                    "modification_note": "Cancelled for modification — new booking pending"
                }}
            )
            await db.cancelled_bookings.insert_one({
                "booking_ref": booking_ref,
                "cancelled_at": now_utc.isoformat(),
                "reason": "modification"
            })

            # Process refund for original booking (minus change penalty)
            refund_info = calculate_refund(booking)
            change_penalty = session.get("_mod_penalty", 0)
            refund_amount = max(0, refund_info.get("refund_eur", 0) - change_penalty)

            if refund_amount > 0:
                refund_result = await process_refund(booking, refund_amount)
                if refund_result.get("success"):
                    await db.bookings.update_one(
                        {"booking_ref": booking_ref},
                        {"$set": {"refund_status": "PROCESSED", "refund_amount_eur": refund_amount, "refund_reference": refund_result.get("reference", "")}}
                    )

            if lang == "fr":
                msg = f"Reservation {booking_ref} annulee pour modification.\nRecherchons de nouveaux vols..."
            else:
                msg = f"Booking {booking_ref} cancelled for modification.\nSearching for new flights..."
            await send_whatsapp_message(phone, msg)

            # Enter new booking flow with same route
            await update_session(phone, {
                "state": ConversationState.AWAITING_DATE,
                "intent": {
                    "origin": booking.get("origin"),
                    "destination": booking.get("destination")
                },
                "_mod_original_ref": booking_ref,
                "_mod_penalty": change_penalty
            })
            if lang == "fr":
                msg = f"Quelle nouvelle date de depart pour {get_city_name(booking.get('origin', ''))} -> {get_city_name(booking.get('destination', ''))} ?"
            else:
                msg = f"What new departure date for {get_city_name(booking.get('origin', ''))} -> {get_city_name(booking.get('destination', ''))}?"
            await send_whatsapp_message(phone, msg)
        else:
            await clear_session(phone)
            msg = "Reservation non trouvee." if lang == "fr" else "Booking not found."
            await send_whatsapp_message(phone, msg)
        return
    msg = "Repondez 1 ou 2" if lang == "fr" else "Reply 1 or 2"
    await send_whatsapp_message(phone, msg)
