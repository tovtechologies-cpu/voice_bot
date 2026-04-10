"""Booking conversation handlers - destination, date, flight selection, payment."""
import logging
import uuid
import asyncio
from typing import Dict
from datetime import datetime, timezone
from models import ConversationState, PaymentOperator, get_fare_conditions
from services.session import update_session, clear_session, get_passenger_by_id
from services.whatsapp import send_whatsapp_message, send_whatsapp_document
from services.flight import search_flights, categorize_flights, eur_to_xof
from services.airport import resolve_airport, get_city_name, suggest_airports
from services.date_parser import parse_date, generate_date_options
from services.ai import parse_travel_intent
from services.payment import payment_service
from services.ticket import generate_ticket_pdf
from services.security import check_rate_limit, check_payment_velocity
from utils.helpers import generate_booking_ref, mask_phone, format_timestamp_gmt1
from utils.formatting import (
    format_flight_options_message, format_payment_method_selection,
    format_card_payment_link, format_payment_success, format_payment_failed,
    format_retry_options, format_booking_confirmed
)
from config import APP_BASE_URL
from database import db

logger = logging.getLogger("BookingHandler")


async def handle_awaiting_destination(phone: str, original_text: str, session: Dict, lang: str):
    intent = session.get("intent", {})
    parsed = await parse_travel_intent(original_text, lang)

    if parsed.get("destination"):
        # Try resolve via airport service (fuzzy matching)
        dest_code = resolve_airport(parsed["destination"]) or parsed["destination"]
        intent["destination"] = dest_code
        if parsed.get("origin"):
            intent["origin"] = resolve_airport(parsed["origin"]) or parsed.get("origin")
        if parsed.get("departure_date"):
            intent["departure_date"] = parsed["departure_date"]
        if parsed.get("passengers"):
            intent["passengers"] = parsed["passengers"]
    else:
        # Direct airport resolve with fuzzy matching
        dest_code = resolve_airport(original_text)
        if dest_code:
            intent["destination"] = dest_code
        else:
            # Suggest alternatives
            suggestions = suggest_airports(original_text, limit=3)
            if suggestions:
                if lang == "fr":
                    msg = "Je n'ai pas reconnu cette ville. Vouliez-vous dire :\n"
                    for i, s in enumerate(suggestions, 1):
                        msg += f"{i} {s['city'].title()} ({s['code']})\n"
                else:
                    msg = "I didn't recognize that city. Did you mean:\n"
                    for i, s in enumerate(suggestions, 1):
                        msg += f"{i} {s['city'].title()} ({s['code']})\n"
            else:
                msg = "Je n'ai pas reconnu cette ville. Essayez: Paris, Dakar, Lagos..." if lang == "fr" else "I didn't recognize that city. Try: Paris, Dakar, Lagos..."
            await send_whatsapp_message(phone, msg)
            return

    if not intent.get("departure_date"):
        # Show date options with dateparser hint
        if lang == "fr":
            msg = "Quelle est votre date de depart ?\n(ex: demain, vendredi prochain, 15 mars...)"
        else:
            msg = "When do you want to depart?\n(e.g.: tomorrow, next Friday, March 15...)"
        await update_session(phone, {"state": ConversationState.AWAITING_DATE, "intent": intent})
        await send_whatsapp_message(phone, msg)
        return

    await search_and_show_flights(phone, intent, lang)


async def handle_awaiting_date(phone: str, original_text: str, text: str, session: Dict, lang: str):
    intent = session.get("intent", {})

    # Try dateparser first (handles French/English natural language)
    parsed_date = parse_date(original_text, lang)
    if parsed_date:
        intent["departure_date"] = parsed_date
    else:
        # Fallback: try Claude
        parsed = await parse_travel_intent(f"vol {original_text}", lang)
        if parsed.get("departure_date"):
            intent["departure_date"] = parsed["departure_date"]
        else:
            if lang == "fr":
                msg = "Je n'ai pas compris la date. Essayez: demain, vendredi prochain, 15 janvier..."
            else:
                msg = "I didn't understand the date. Try: tomorrow, next Friday, January 15..."
            await send_whatsapp_message(phone, msg)
            return

    await search_and_show_flights(phone, intent, lang)


async def search_and_show_flights(phone: str, intent: Dict, lang: str):
    origin = resolve_airport(intent.get("origin", "Cotonou")) or "COO"
    destination = resolve_airport(intent["destination"]) or intent["destination"].upper()[:3]
    date = intent["departure_date"]
    passengers = intent.get("passengers", 1)

    msg = f"Recherche de vols {get_city_name(origin)} -> {get_city_name(destination)}..." if lang == "fr" else f"Searching flights {get_city_name(origin)} -> {get_city_name(destination)}..."
    await send_whatsapp_message(phone, msg)

    flights = await search_flights(origin, destination, date, passengers)

    if not flights:
        await clear_session(phone)
        msg = "Recherche indisponible, reessayez." if lang == "fr" else "Search unavailable, please try again."
        await send_whatsapp_message(phone, msg)
        return

    categorized = categorize_flights(flights)
    if not categorized:
        await clear_session(phone)
        msg = "Aucun vol trouve." if lang == "fr" else "No flights found."
        await send_whatsapp_message(phone, msg)
        return

    flights_with_cat = list(categorized.values())
    await update_session(phone, {"state": ConversationState.AWAITING_FLIGHT_SELECTION, "intent": intent, "flights": flights_with_cat})
    await send_whatsapp_message(phone, format_flight_options_message(categorized, origin, destination, date))


async def handle_flight_selection(phone: str, text: str, session: Dict, lang: str):
    flights = session.get("flights", [])
    selection = None
    if text in ["1", "un", "one", "premier", "plus bas"]:
        selection = "PLUS_BAS"
    elif text in ["2", "deux", "two", "deuxieme", "rapide"]:
        selection = "PLUS_RAPIDE"
    elif text in ["3", "trois", "three", "troisieme", "premium"]:
        selection = "PREMIUM"

    if not selection:
        msg = "Tapez 1, 2 ou 3 pour choisir un vol" if lang == "fr" else "Type 1, 2, or 3 to select a flight"
        await send_whatsapp_message(phone, msg)
        return

    selected = next((f for f in flights if f.get("category") == selection), None)
    if not selected:
        msg = "Option non disponible." if lang == "fr" else "Option not available."
        await send_whatsapp_message(phone, msg)
        return

    booking_passenger_id = session.get("booking_passenger_id")
    passenger = await get_passenger_by_id(booking_passenger_id) if booking_passenger_id else None
    passenger_name = f"{passenger['lastName']} {passenger['firstName']}" if passenger else phone

    departure_date = selected.get("departure_time", "").split("T")[0]
    fare = get_fare_conditions(departure_date)

    booking_ref = generate_booking_ref()
    booking = {
        "id": str(uuid.uuid4()),
        "booking_ref": booking_ref,
        "phone": phone,
        "passenger_id": booking_passenger_id,
        "passenger_name": passenger_name,
        "passenger_passport": passenger.get("passportNumber") if passenger else None,
        "airline": selected["airline"],
        "flight_number": selected["flight_number"],
        "origin": selected["origin"],
        "destination": selected["destination"],
        "departure_date": departure_date,
        "price_eur": selected["final_price"],
        "price_xof": selected["price_xof"],
        "category": selected["category"],
        "status": "awaiting_payment",
        "payment_method": None,
        "duffel_offer_id": selected.get("duffel_offer_id"),
        "fare_conditions_raw": fare.get("conditions_raw", ""),
        "fare_conditions_summary": fare.get("conditions_summary", ""),
        "refundable": fare.get("refundable", "NO"),
        "refund_penalty_eur": fare.get("refund_penalty_eur"),
        "change_allowed": fare.get("change_allowed", False),
        "change_penalty_eur": fare.get("change_penalty_eur"),
        "refund_deadline": fare.get("refund_deadline"),
        "refund_status": "NONE",
        "refund_amount_eur": None,
        "refund_reference": None,
        "cancellation_timestamp": None,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.bookings.insert_one(booking)
    await update_session(phone, {
        "state": ConversationState.AWAITING_PAYMENT_METHOD,
        "selected_flight": selected,
        "booking_id": booking["id"],
        "booking_ref": booking_ref,
        "_fare_conditions": {"summary": fare.get("conditions_summary", ""), "raw": fare.get("conditions_raw", ""), "refundable": fare.get("refundable", "NO")}
    })
    await send_whatsapp_message(phone, format_payment_method_selection(selected["final_price"], lang))


async def handle_payment_method(phone: str, text: str, session: Dict, lang: str):
    selected = session.get("selected_flight")
    booking_ref = session.get("booking_ref")
    booking_id = session.get("booking_id")
    if not selected or not booking_ref:
        await clear_session(phone)
        msg = "Session expiree. Recommencez." if lang == "fr" else "Session expired. Start again."
        await send_whatsapp_message(phone, msg)
        return

    operator = None
    if text in ["1", "mtn", "momo", "mtn momo"]:
        operator = PaymentOperator.MTN_MOMO
    elif text in ["2", "moov", "flooz", "moov money"]:
        operator = PaymentOperator.MOOV_MONEY
    elif text in ["3", "google", "google pay", "gpay"]:
        operator = PaymentOperator.GOOGLE_PAY
    elif text in ["4", "apple", "apple pay", "apay"]:
        operator = PaymentOperator.APPLE_PAY

    if not operator:
        msg = "Repondez 1, 2, 3 ou 4" if lang == "fr" else "Reply 1, 2, 3, or 4"
        await send_whatsapp_message(phone, msg)
        return

    # Velocity check
    velocity_ok = await check_payment_velocity(phone)
    if not velocity_ok:
        msg = "Trop de tentatives de paiement. Veuillez patienter avant de reessayer." if lang == "fr" else "Too many payment attempts. Please wait before retrying."
        await send_whatsapp_message(phone, msg)
        return

    await db.bookings.update_one({"id": booking_id}, {"$set": {"payment_method": operator}})
    await update_session(phone, {"selected_payment_method": operator, "state": ConversationState.AWAITING_PAYMENT_CONFIRM})

    booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    passenger_name = booking.get("passenger_name", phone) if booking else phone
    fare_summary = session.get("_fare_conditions", {}).get("summary", "")

    operator_names = {PaymentOperator.MTN_MOMO: "MTN MoMo", PaymentOperator.MOOV_MONEY: "Moov Money", PaymentOperator.GOOGLE_PAY: "Google Pay", PaymentOperator.APPLE_PAY: "Apple Pay"}
    op_name = operator_names.get(operator, operator)
    amount_xof = eur_to_xof(selected["final_price"])

    if lang == "fr":
        msg = f"""*Recapitulatif de votre paiement*

Vol : {selected['origin']} -> {selected['destination']}
Depart : {selected.get('departure_time', '').split('T')[0]}
Passager : {passenger_name}
Classe : {selected['category']}
Methode : {op_name}

*Conditions du billet :*
{fare_summary}

Montant : *{selected['final_price']}EUR* ({amount_xof:,} XOF)

Lisez attentivement avant de confirmer.

1 Oui, envoyer la notification de paiement
2 Non, annuler
3 Voir les conditions completes"""
    else:
        msg = f"""*Payment Summary*

Flight: {selected['origin']} -> {selected['destination']}
Departure: {selected.get('departure_time', '').split('T')[0]}
Passenger: {passenger_name}
Class: {selected['category']}
Method: {op_name}

*Ticket conditions:*
{fare_summary}

Amount: *{selected['final_price']}EUR* ({amount_xof:,} XOF)

Read carefully before confirming.

1 Yes, send payment notification
2 No, cancel
3 View full conditions"""
    await send_whatsapp_message(phone, msg)


async def handle_pre_debit_confirm(phone: str, text: str, session: Dict, lang: str):
    if text in ["3", "conditions"]:
        fare = session.get("_fare_conditions", {})
        raw = fare.get("raw", "Aucune condition disponible.")
        await send_whatsapp_message(phone, f"*Conditions completes :*\n\n{raw}")
        msg = "1 Confirmer le paiement\n2 Annuler" if lang == "fr" else "1 Confirm payment\n2 Cancel"
        await send_whatsapp_message(phone, msg)
        return
    if text in ["2", "non", "no", "annuler", "cancel"]:
        await clear_session(phone)
        msg = "Reservation annulee. Envoyez un message pour recommencer." if lang == "fr" else "Booking cancelled. Send a message to start again."
        await send_whatsapp_message(phone, msg)
        return
    if text in ["1", "oui", "yes", "confirmer", "confirm"]:
        await execute_payment(phone, session, lang)
        return
    msg = "Repondez 1, 2 ou 3" if lang == "fr" else "Reply 1, 2, or 3"
    await send_whatsapp_message(phone, msg)


async def execute_payment(phone: str, session: Dict, lang: str):
    selected = session.get("selected_flight")
    booking_ref = session.get("booking_ref")
    booking_id = session.get("booking_id")
    operator = session.get("selected_payment_method")

    result = await payment_service.request_payment(operator=operator, phone=phone, amount_eur=selected["final_price"], booking_id=booking_ref, destination=get_city_name(selected["destination"]))

    if result.get("status") == "error":
        await send_whatsapp_message(phone, format_payment_failed(operator, lang))
        await send_whatsapp_message(phone, format_retry_options(operator, lang))
        await update_session(phone, {"state": "retry"})
        return

    await update_session(phone, {"payment_reference": result.get("reference_id")})

    if operator in [PaymentOperator.MTN_MOMO, PaymentOperator.MOOV_MONEY]:
        amount_xof = eur_to_xof(selected["final_price"])
        operator_names = {PaymentOperator.MTN_MOMO: "MTN MoMo", PaymentOperator.MOOV_MONEY: "Moov Money"}
        op_name = operator_names.get(operator, operator)
        if lang == "fr":
            msg = f"""*Notification envoyee !*

Montant : *{selected['final_price']}EUR* ({amount_xof:,} XOF)
Methode : {op_name}

Ouvrez {op_name} et confirmez avec votre PIN / mot de passe.

Vous avez *30 secondes*..."""
        else:
            msg = f"""*Notification sent!*

Amount: *{selected['final_price']}EUR* ({amount_xof:,} XOF)
Method: {op_name}

Open {op_name} and confirm with your PIN / password.

You have *30 seconds*..."""
        await send_whatsapp_message(phone, msg)
        await update_session(phone, {"state": ConversationState.AWAITING_MOBILE_PAYMENT})
        asyncio.create_task(poll_and_complete_payment(phone, booking_id, booking_ref, operator, result["reference_id"], lang))
    else:
        await send_whatsapp_message(phone, format_card_payment_link(result["payment_url"], lang))
        await update_session(phone, {"state": ConversationState.AWAITING_CARD_PAYMENT})


async def handle_retry(phone: str, text: str, session: Dict, lang: str):
    last_operator = session.get("selected_payment_method")
    if text == "1":
        await update_session(phone, {"state": ConversationState.AWAITING_PAYMENT_METHOD, "_test_force_fail": False})
        from conversation.handler import handle_message
        await handle_message(phone, last_operator.replace("_", " ") if last_operator else "1")
    elif text == "2":
        selected = session.get("selected_flight")
        if selected:
            await update_session(phone, {"state": ConversationState.AWAITING_PAYMENT_METHOD, "_test_force_fail": False})
            await send_whatsapp_message(phone, format_payment_method_selection(selected["final_price"], lang))
        else:
            await clear_session(phone)
    elif text == "3":
        await clear_session(phone)
        msg = "Reservation annulee. Envoyez un message pour recommencer." if lang == "fr" else "Booking cancelled. Send a message to start again."
        await send_whatsapp_message(phone, msg)
    else:
        await send_whatsapp_message(phone, format_retry_options(last_operator or "payment", lang))


async def poll_and_complete_payment(phone: str, booking_id: str, booking_ref: str, operator: str, reference_id: str, lang: str):
    operator_names = {PaymentOperator.MTN_MOMO: "MTN MoMo", PaymentOperator.MOOV_MONEY: "Moov Money"}
    op_name = operator_names.get(operator, operator)

    for attempt in range(10):
        await asyncio.sleep(3)
        status = await payment_service._check_status(operator, reference_id, phone=phone)
        logger.info(f"Poll {attempt + 1}/10: {operator} {reference_id} = {status}")

        if status in ["SUCCESSFUL", "SUCCESS", "COMPLETED"]:
            booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
            if not booking:
                return
            now_utc = datetime.now(timezone.utc)
            await db.bookings.update_one({"id": booking_id}, {"$set": {"status": "confirmed", "payment_confirmed_at": now_utc.isoformat()}})
            ts = format_timestamp_gmt1(now_utc)
            masked = mask_phone(phone)
            if lang == "fr":
                msg = f"""*Paiement confirme !*

{booking.get('price_eur')}EUR debites -- {op_name} ({masked})
{ts} GMT+1
Reservation : {booking_ref}

Votre billet est en cours de generation..."""
            else:
                msg = f"""*Payment confirmed!*

{booking.get('price_eur')}EUR debited -- {op_name} ({masked})
{ts} GMT+1
Booking: {booking_ref}

Your ticket is being generated..."""
            await send_whatsapp_message(phone, msg)
            ticket_filename = generate_ticket_pdf(booking)
            await asyncio.sleep(2)
            fn = booking.get("passenger_name", "")
            if lang == "fr":
                ticket_msg = f"""*Votre billet est pret !*
{fn}
{booking.get('origin')} -> {booking.get('destination')}
{booking.get('departure_date')}
{booking_ref}
Bon voyage !"""
            else:
                ticket_msg = f"""*Your ticket is ready!*
{fn}
{booking.get('origin')} -> {booking.get('destination')}
{booking.get('departure_date')}
{booking_ref}
Have a great trip!"""
            await send_whatsapp_document(phone, f"{APP_BASE_URL}/api/tickets/{ticket_filename}", ticket_filename, ticket_msg)
            await clear_session(phone)
            return

        if status in ["FAILED", "REJECTED", "CANCELLED"]:
            break

        elapsed = (attempt + 1) * 3
        if elapsed == 9:
            msg = f"En attente de confirmation...\nVerifiez votre application {op_name}." if lang == "fr" else f"Waiting for confirmation...\nCheck your {op_name} app."
            await send_whatsapp_message(phone, msg)
        elif elapsed == 18:
            msg = "Toujours en attente...\nAssurez-vous d'avoir entre votre PIN." if lang == "fr" else "Still waiting...\nMake sure you entered your PIN."
            await send_whatsapp_message(phone, msg)

    await db.bookings.update_one({"id": booking_id}, {"$set": {"status": "payment_failed"}})
    if lang == "fr":
        msg = """Delai depasse.
1 Renvoyer la notification
2 Changer de methode de paiement
3 Annuler la reservation"""
    else:
        msg = """Timeout.
1 Resend notification
2 Change payment method
3 Cancel booking"""
    await send_whatsapp_message(phone, msg)
    await update_session(phone, {"state": "retry"})


async def complete_card_payment(booking_id: str, stripe_intent_id: str):
    payment_intent = await db.payment_intents.find_one({"stripe_intent_id": stripe_intent_id}, {"_id": 0})
    if not payment_intent:
        logger.error(f"Payment intent not found: {stripe_intent_id}")
        return
    bid = payment_intent.get("booking_id")
    booking = await db.bookings.find_one({"booking_ref": bid}, {"_id": 0})
    if not booking:
        booking = await db.bookings.find_one({"id": bid}, {"_id": 0})
    if not booking:
        logger.error(f"Booking not found for intent: {stripe_intent_id}")
        return
    phone = booking.get("phone")
    lang = "fr"
    session = await db.sessions.find_one({"phone": phone}, {"_id": 0})
    if session:
        lang = session.get("language", "fr")
    await db.bookings.update_one({"id": booking["id"]}, {"$set": {"status": "confirmed"}})
    await send_whatsapp_message(phone, format_payment_success(lang))
    ticket_filename = generate_ticket_pdf(booking)
    await asyncio.sleep(2)
    await send_whatsapp_document(phone, f"{APP_BASE_URL}/api/tickets/{ticket_filename}", ticket_filename, format_booking_confirmed(booking, lang))
    await clear_session(phone)
