"""Proactive SAV — Flight disruption monitoring and notification — Phase C."""
import logging
import asyncio
from typing import Dict, List, Optional
from datetime import datetime, timezone, timedelta
from database import db
from services.whatsapp import send_whatsapp_message
from services.channel import set_channel
from config import APP_BASE_URL

logger = logging.getLogger("DisruptionService")

# Disruption types
DELAY = "DELAY"
CANCELLATION = "CANCELLATION"
GATE_CHANGE = "GATE_CHANGE"
SCHEDULE_CHANGE = "SCHEDULE_CHANGE"


async def check_flight_disruptions(booking: Dict) -> Optional[Dict]:
    """Check a booking's flight for disruptions via Duffel API.
    Returns disruption dict if found, None otherwise."""
    from config import DUFFEL_API_KEY, get_duffel_mode, API_TIMEOUT
    import httpx

    duffel_mode = get_duffel_mode()
    offer_id = booking.get("duffel_offer_id")

    if duffel_mode == "MOCK" or not offer_id:
        return None

    # Query Duffel for order status (requires order_id, not offer_id)
    order_id = booking.get("duffel_order_id")
    if not order_id:
        return None

    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            resp = await client.get(
                f"https://api.duffel.com/air/orders/{order_id}",
                headers={
                    "Authorization": f"Bearer {DUFFEL_API_KEY}",
                    "Duffel-Version": "v2",
                    "Accept": "application/json",
                })
            if resp.status_code != 200:
                return None

            data = resp.json().get("data", {})
            slices = data.get("slices", [])
            for s in slices:
                for seg in s.get("segments", []):
                    conditions = seg.get("conditions", {})
                    if conditions.get("change_before_departure"):
                        return _parse_duffel_disruption(seg, booking)
    except Exception as e:
        logger.error(f"Disruption check failed for {booking.get('booking_ref')}: {e}")
    return None


def _parse_duffel_disruption(segment: Dict, booking: Dict) -> Optional[Dict]:
    """Parse Duffel segment data for disruption info."""
    # This would parse actual Duffel disruption data
    # For now, this is structured for when real Duffel orders are available
    return None


async def process_disruption(booking_ref: str, disruption_type: str,
                              details: Dict) -> bool:
    """Process a flight disruption — notify passengers and handle refunds."""
    booking = await db.bookings.find_one({"booking_ref": booking_ref}, {"_id": 0})
    if not booking:
        logger.error(f"Booking not found: {booking_ref}")
        return False

    phone = booking.get("phone")
    lang = "fr"  # Default
    session = await db.sessions.find_one({"phone": phone}, {"_id": 0})
    if session:
        lang = session.get("language", "fr")

    # Store disruption event in booking
    disruption_event = {
        "type": disruption_type,
        "details": details,
        "detected_at": datetime.now(timezone.utc).isoformat(),
        "notified": False,
        "action_taken": None,
    }

    await db.bookings.update_one(
        {"booking_ref": booking_ref},
        {"$push": {"disruption_events": disruption_event}}
    )

    # Build notification message
    msg = _build_disruption_message(booking, disruption_type, details, lang)

    # Notify on ALL available channels
    await _notify_all_channels(phone, msg)

    # Notify co-payers if split payment
    split_payments = booking.get("split_payments", [])
    for sp in split_payments:
        payer_phone = sp.get("payer_phone")
        if payer_phone and payer_phone != phone:
            await _notify_all_channels(payer_phone, msg)

    # Mark as notified
    await db.bookings.update_one(
        {"booking_ref": booking_ref, "disruption_events.detected_at": disruption_event["detected_at"]},
        {"$set": {"disruption_events.$.notified": True}}
    )

    # Handle specific disruption types
    if disruption_type == CANCELLATION:
        await _handle_cancellation_disruption(booking, lang)
    elif disruption_type == DELAY:
        delay_minutes = details.get("delay_minutes", 0)
        if delay_minutes > 120:
            await _offer_rebooking(phone, booking, lang)

    return True


def _build_disruption_message(booking: Dict, disruption_type: str,
                               details: Dict, lang: str) -> str:
    """Build the disruption notification message."""
    flight_num = booking.get("flight_number", "")
    route = f"{booking.get('origin', '')} -> {booking.get('destination', '')}"
    ref = booking.get("booking_ref", "")

    if disruption_type == DELAY:
        delay_min = details.get("delay_minutes", 0)
        new_time = details.get("new_departure_time", "")
        if lang == "fr":
            msg = "*Information importante sur votre vol*\n\n"
            msg += f"Vol {flight_num} ({route})\n"
            msg += f"Retard : {delay_min} minutes\n"
            if new_time:
                msg += f"Nouvelle heure de depart : {new_time}\n"
            msg += f"\nReservation : {ref}"
        else:
            msg = "*Important information about your flight*\n\n"
            msg += f"Flight {flight_num} ({route})\n"
            msg += f"Delay: {delay_min} minutes\n"
            if new_time:
                msg += f"New departure time: {new_time}\n"
            msg += f"\nBooking: {ref}"

    elif disruption_type == CANCELLATION:
        reason = details.get("reason", "")
        if lang == "fr":
            msg = "*Vol annule*\n\n"
            msg += f"Vol {flight_num} ({route})\n"
            msg += "Annulation par la compagnie aerienne\n"
            if reason:
                msg += f"Raison : {reason}\n"
            msg += f"\nReservation : {ref}\n"
            msg += "\nUn remboursement automatique est en cours."
        else:
            msg = "*Flight Cancelled*\n\n"
            msg += f"Flight {flight_num} ({route})\n"
            msg += "Cancelled by airline\n"
            if reason:
                msg += f"Reason: {reason}\n"
            msg += f"\nBooking: {ref}\n"
            msg += "\nAn automatic refund is being processed."

    elif disruption_type == GATE_CHANGE:
        new_gate = details.get("new_gate", "")
        if lang == "fr":
            msg = "*Changement de porte*\n\n"
            msg += f"Vol {flight_num} ({route})\n"
            msg += f"Nouvelle porte : *{new_gate}*\n"
            msg += f"\nReservation : {ref}"
        else:
            msg = "*Gate Change*\n\n"
            msg += f"Flight {flight_num} ({route})\n"
            msg += f"New gate: *{new_gate}*\n"
            msg += f"\nBooking: {ref}"

    elif disruption_type == SCHEDULE_CHANGE:
        new_time = details.get("new_departure_time", "")
        if lang == "fr":
            msg = "*Changement d'horaire*\n\n"
            msg += f"Vol {flight_num} ({route})\n"
            msg += f"Nouvel horaire de depart : *{new_time}*\n"
            msg += f"\nReservation : {ref}"
        else:
            msg = "*Schedule Change*\n\n"
            msg += f"Flight {flight_num} ({route})\n"
            msg += f"New departure time: *{new_time}*\n"
            msg += f"\nBooking: {ref}"
    else:
        msg = f"Disruption on {flight_num} ({route}): {disruption_type}"

    return msg


async def _notify_all_channels(phone: str, msg: str):
    """Send notification on all available channels for this user."""
    # Check shadow profile for linked channels
    profile = await db.shadow_profiles.find_one({"phone_number": phone}, {"_id": 0})

    # Always try WhatsApp (default)
    set_channel(phone, "whatsapp")
    await send_whatsapp_message(phone, msg)

    # Also send via Telegram if linked
    if profile and profile.get("telegram_id"):
        from services.telegram import register_chat, send_telegram_message
        tg_id = profile.get("telegram_id")
        # Try to send via Telegram too
        try:
            chat_id = int(tg_id)
            register_chat(phone, chat_id)
            set_channel(phone, "telegram")
            await send_whatsapp_message(phone, msg)  # Auto-routes to Telegram
            set_channel(phone, "whatsapp")  # Reset to WhatsApp
        except (ValueError, TypeError):
            pass


async def _handle_cancellation_disruption(booking: Dict, lang: str):
    """Auto-trigger refund when airline cancels the flight."""
    phone = booking.get("phone")
    booking_id = booking.get("id")
    driver_name = booking.get("payment_driver")

    if not driver_name:
        return

    from payment_drivers.router import get_driver
    from models import format_price_display, calculate_travelioo_fee

    driver = get_driver(driver_name)
    if not driver:
        return

    # Calculate refund: GDS base only, Travelioo fees non-refundable
    gds_price = booking.get("gds_price_eur", 0)
    travelioo_fee = booking.get("travelioo_fee_eur") or calculate_travelioo_fee(gds_price)
    refund_amount = gds_price  # Only GDS price is refundable
    country = "BJ"

    # Check for split payments
    split_payments = booking.get("split_payments", [])
    if split_payments:
        # Refund each payer their share (minus reconciliation fee per person)
        for sp in split_payments:
            payer_phone = sp.get("payer_phone")
            ref = sp.get("reference")
            per_person_refund = sp.get("amount_eur", 0)

            result = await driver.process_refund(ref, per_person_refund, reason="airline_cancellation")
            status_msg = "traite" if result.success else "echoue"
            status_msg_en = "processed" if result.success else "failed"

            if payer_phone:
                if lang == "fr":
                    rmsg = f"*Remboursement automatique — annulation compagnie*\n\nMontant : {format_price_display(per_person_refund, country)}\nReference : {result.reference if result.success else 'en attente'}\nStatut : {status_msg}"
                else:
                    rmsg = f"*Automatic Refund — airline cancellation*\n\nAmount: {format_price_display(per_person_refund, country)}\nReference: {result.reference if result.success else 'pending'}\nStatus: {status_msg_en}"
                set_channel(payer_phone, "whatsapp")
                await send_whatsapp_message(payer_phone, rmsg)
    else:
        # Single payer refund
        ref = booking.get("payment_reference", "")
        result = await driver.process_refund(ref, refund_amount, reason="airline_cancellation")

        if lang == "fr":
            msg = f"*Remboursement automatique*\n\nMontant rembourse : {format_price_display(refund_amount, country)}\n"
            msg += f"Frais Travelioo : {format_price_display(travelioo_fee, country)} (non remboursables)\n"
            msg += f"Reference : {result.reference if result.success else 'en attente'}"
        else:
            msg = f"*Automatic Refund*\n\nRefunded amount: {format_price_display(refund_amount, country)}\n"
            msg += f"Travelioo fee: {format_price_display(travelioo_fee, country)} (non-refundable)\n"
            msg += f"Reference: {result.reference if result.success else 'pending'}"
        await send_whatsapp_message(phone, msg)

    # Update booking status
    await db.bookings.update_one({"id": booking_id}, {"$set": {
        "status": "cancelled_by_airline",
        "refund_status": "PROCESSED",
        "cancellation_timestamp": datetime.now(timezone.utc).isoformat(),
    }})


async def _offer_rebooking(phone: str, booking: Dict, lang: str):
    """Offer rebooking option for delays > 2 hours."""
    from services.session import update_session, get_or_create_session
    from models import ConversationState

    booking_ref = booking.get("booking_ref")

    # Ensure session exists
    await get_or_create_session(phone)

    if lang == "fr":
        msg = f"Votre vol {booking.get('flight_number')} a plus de 2 heures de retard.\n\n"
        msg += "Souhaitez-vous etre reloge sur un autre vol ?\n\n"
        msg += "*1* Oui, chercher un autre vol\n"
        msg += "*2* Non, je garde ma reservation"
    else:
        msg = f"Your flight {booking.get('flight_number')} is delayed by more than 2 hours.\n\n"
        msg += "Would you like to be rebooked on another flight?\n\n"
        msg += "*1* Yes, search another flight\n"
        msg += "*2* No, keep my booking"

    await update_session(phone, {
        "state": ConversationState.MODIFICATION_REQUESTED,
        "_disruption_rebooking": True,
        "_disruption_booking_ref": booking_ref,
    })
    await send_whatsapp_message(phone, msg)


async def monitor_active_bookings():
    """Background task: check all active bookings for disruptions.
    Called periodically from server lifespan."""
    now = datetime.now(timezone.utc)
    # Find confirmed bookings with departure in the next 48 hours
    cutoff = (now + timedelta(hours=48)).isoformat()

    active_bookings = await db.bookings.find({
        "status": "confirmed",
        "departure_date": {"$lte": cutoff[:10]},
    }, {"_id": 0}).to_list(100)

    for booking in active_bookings:
        try:
            disruption = await check_flight_disruptions(booking)
            if disruption:
                await process_disruption(
                    booking["booking_ref"],
                    disruption["type"],
                    disruption["details"]
                )
        except Exception as e:
            logger.error(f"Disruption monitor error for {booking.get('booking_ref')}: {e}")
