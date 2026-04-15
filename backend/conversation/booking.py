"""Booking conversation handlers - destination, date, flight selection, payment."""
import logging
import uuid
import asyncio
from typing import Dict
from datetime import datetime, timezone
from models import ConversationState, get_fare_conditions
from services.session import update_session, clear_session, get_passenger_by_id
from services.whatsapp import send_whatsapp_message, send_whatsapp_document
from services.flight import search_flights, categorize_flights, eur_to_xof
from services.airport import resolve_airport, get_city_name, suggest_airports
from services.date_parser import parse_date, generate_date_options
from services.ai import parse_travel_intent
from services.ticket import generate_ticket_pdf
from services.security import check_rate_limit, check_payment_velocity
from utils.helpers import generate_booking_ref, mask_phone, format_timestamp_gmt1
from utils.formatting import (
    format_flight_options_message,
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

    # Dynamic pricing — tiered Travelioo fee
    from models import apply_travelioo_pricing, format_price_display
    gds_base = selected.get("base_price", selected["final_price"])
    pricing = apply_travelioo_pricing(gds_base)

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
        "gds_price_eur": pricing["gds_price_eur"],
        "travelioo_fee_eur": pricing["travelioo_fee_eur"],
        "price_eur": pricing["total_eur"],
        "price_xof": eur_to_xof(pricing["total_eur"]),
        "category": selected["category"],
        "status": "awaiting_payment",
        "payment_method": None,
        "payment_driver": None,
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

    # Get country-aware payment menu
    country = session.get("_country_code", "BJ")
    from payment_drivers.router import get_payment_menu_for_country
    menu = get_payment_menu_for_country(country, lang)

    # Format payment selection message with fee breakdown
    price_display = format_price_display(pricing["total_eur"], country)
    fee_display = format_price_display(pricing["travelioo_fee_eur"], country)
    if lang == "fr":
        msg = "*Choisissez votre moyen de paiement*\n"
        msg += f"Prix vol : {format_price_display(pricing['gds_price_eur'], country)}\n"
        msg += f"Frais Travelioo : {fee_display}\n"
        msg += f"*Total : {price_display}*\n\n"
    else:
        msg = "*Choose your payment method*\n"
        msg += f"Flight price: {format_price_display(pricing['gds_price_eur'], country)}\n"
        msg += f"Travelioo fee: {fee_display}\n"
        msg += f"*Total: {price_display}*\n\n"
    for item in menu:
        msg += f"{item['index']} {item['label']}\n"
    msg += f"\n{'Repondez' if lang == 'fr' else 'Reply'} " + ", ".join(str(m["index"]) for m in menu)

    await update_session(phone, {
        "state": ConversationState.AWAITING_PAYMENT_METHOD,
        "selected_flight": selected,
        "booking_id": booking["id"],
        "booking_ref": booking_ref,
        "_fare_conditions": {"summary": fare.get("conditions_summary", ""), "raw": fare.get("conditions_raw", ""), "refundable": fare.get("refundable", "NO")},
        "_payment_menu": [m["driver_name"] for m in menu],
        "_pricing": pricing,
        "_country_code": country,
    })
    await send_whatsapp_message(phone, msg)


async def handle_payment_method(phone: str, text: str, session: Dict, lang: str):
    selected = session.get("selected_flight")
    booking_ref = session.get("booking_ref")
    booking_id = session.get("booking_id")
    if not selected or not booking_ref:
        await clear_session(phone)
        msg = "Session expiree. Recommencez." if lang == "fr" else "Session expired. Start again."
        await send_whatsapp_message(phone, msg)
        return

    # Use the dynamic payment menu from session
    payment_menu = session.get("_payment_menu", ["mtn_momo", "moov_money", "stripe"])
    pricing = session.get("_pricing", {})
    country = session.get("_country_code", "BJ")

    driver_name = None
    try:
        idx = int(text) - 1
        if 0 <= idx < len(payment_menu):
            driver_name = payment_menu[idx]
    except (ValueError, TypeError):
        pass

    # Also accept text names
    if not driver_name:
        text_lower = text.lower()
        name_map = {"celtiis": "celtiis_cash", "mtn": "mtn_momo", "momo": "mtn_momo",
                     "moov": "moov_money", "flooz": "moov_money",
                     "google": "stripe", "gpay": "stripe", "apple": "stripe", "apay": "stripe",
                     "carte": "stripe", "card": "stripe", "stripe": "stripe"}
        driver_name = name_map.get(text_lower)
        if driver_name and driver_name not in payment_menu:
            driver_name = None

    if not driver_name:
        max_opt = len(payment_menu)
        msg = f"Repondez 1 a {max_opt}" if lang == "fr" else f"Reply 1 to {max_opt}"
        await send_whatsapp_message(phone, msg)
        return

    # Velocity check
    velocity_ok = await check_payment_velocity(phone)
    if not velocity_ok:
        msg = "Trop de tentatives de paiement. Veuillez patienter avant de reessayer." if lang == "fr" else "Too many payment attempts. Please wait before retrying."
        await send_whatsapp_message(phone, msg)
        return

    # Map driver name to operator for backward compat
    from payment_drivers.router import get_driver
    driver = get_driver(driver_name)
    operator = driver_name

    await db.bookings.update_one({"id": booking_id}, {"$set": {"payment_method": operator, "payment_driver": driver_name}})
    await update_session(phone, {"selected_payment_method": operator, "_selected_driver": driver_name, "state": ConversationState.AWAITING_PAYMENT_CONFIRM})

    booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    passenger_name = booking.get("passenger_name", phone) if booking else phone
    fare_summary = session.get("_fare_conditions", {}).get("summary", "")

    op_name = driver.display_name if driver else operator
    total_eur = pricing.get("total_eur", selected["final_price"])

    from models import format_price_display
    price_display = format_price_display(total_eur, country)
    gds_display = format_price_display(pricing.get("gds_price_eur", total_eur), country)
    fee_display = format_price_display(pricing.get("travelioo_fee_eur", 0), country)

    if lang == "fr":
        msg = f"""*Recapitulatif de votre paiement*

Vol : {selected['origin']} -> {selected['destination']}
Depart : {selected.get('departure_time', '').split('T')[0]}
Passager : {passenger_name}
Classe : {selected['category']}
Methode : {op_name}

*Conditions du billet :*
{fare_summary}

Prix vol : {gds_display}
Frais Travelioo : {fee_display} (non remboursables)
*Total : {price_display}*

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

Flight price: {gds_display}
Travelioo fee: {fee_display} (non-refundable)
*Total: {price_display}*

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
    driver_name = session.get("_selected_driver")
    pricing = session.get("_pricing", {})
    country = session.get("_country_code", "BJ")
    total_eur = pricing.get("total_eur", selected.get("final_price", 0))

    from payment_drivers.router import get_driver
    from models import format_price_display
    driver = get_driver(driver_name)

    if not driver:
        logger.error(f"Unknown payment driver: {driver_name}")
        msg = "Methode de paiement indisponible. Veuillez reessayer." if lang == "fr" else "Payment method unavailable. Please try again."
        await send_whatsapp_message(phone, msg)
        await update_session(phone, {"state": ConversationState.AWAITING_PAYMENT_METHOD})
        return

    # Use new payment driver architecture
    is_mobile = driver_name in ["celtiis_cash", "mtn_momo", "moov_money"]
    currency = "XOF" if is_mobile else "EUR"
    amount = eur_to_xof(total_eur) if is_mobile else total_eur

    result = await driver.initiate_payment(
        phone=phone, amount=amount, currency=currency,
        reference=booking_ref, metadata={"booking_id": booking_id})

    if not result.success:
        await send_whatsapp_message(phone, format_payment_failed(driver_name, lang))
        await send_whatsapp_message(phone, format_retry_options(driver_name, lang))
        await update_session(phone, {"state": "retry"})
        return

    await update_session(phone, {"payment_reference": result.reference})
    await db.bookings.update_one({"id": booking_id}, {"$set": {"payment_reference": result.reference}})

    if is_mobile:
        op_name = driver.display_name
        price_display = format_price_display(total_eur, country)
        if lang == "fr":
            msg = f"""*Notification envoyee !*

Montant : *{price_display}*
Methode : {op_name}

Ouvrez {op_name} et confirmez avec votre PIN / mot de passe.

Vous avez *30 secondes*..."""
        else:
            msg = f"""*Notification sent!*

Amount: *{price_display}*
Method: {op_name}

Open {op_name} and confirm with your PIN / password.

You have *30 seconds*..."""
        await send_whatsapp_message(phone, msg)
        await update_session(phone, {"state": ConversationState.AWAITING_MOBILE_PAYMENT})
        asyncio.create_task(poll_and_complete_payment_v2(phone, booking_id, booking_ref, driver_name, result.reference, lang))
    else:
        # Card payment (Stripe)
        payment_url = result.raw.get("client_secret", "")
        if payment_url:
            await send_whatsapp_message(phone, format_card_payment_link(payment_url, lang))
        else:
            if lang == "fr":
                msg = f"Paiement en cours de traitement. Reference: {result.reference}"
            else:
                msg = f"Payment being processed. Reference: {result.reference}"
            await send_whatsapp_message(phone, msg)
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
            # Re-display dynamic payment menu
            country = session.get("_country_code", "BJ")
            pricing = session.get("_pricing", {})
            total = pricing.get("total_eur", selected.get("final_price", 0))
            from payment_drivers.router import get_payment_menu_for_country
            from models import format_price_display
            menu = get_payment_menu_for_country(country, lang)
            msg = f"*{'Choisissez votre moyen de paiement' if lang == 'fr' else 'Choose your payment method'}*\n*Total : {format_price_display(total, country)}*\n\n"
            for item in menu:
                msg += f"{item['index']} {item['label']}\n"
            await update_session(phone, {"_payment_menu": [m["driver_name"] for m in menu]})
            await send_whatsapp_message(phone, msg)
        else:
            await clear_session(phone)
    elif text == "3":
        await clear_session(phone)
        msg = "Reservation annulee. Envoyez un message pour recommencer." if lang == "fr" else "Booking cancelled. Send a message to start again."
        await send_whatsapp_message(phone, msg)
    else:
        await send_whatsapp_message(phone, format_retry_options(last_operator or "payment", lang))


async def poll_and_complete_payment_v2(phone: str, booking_id: str, booking_ref: str,
                                       driver_name: str, reference: str, lang: str):
    """Poll payment status using new payment driver architecture."""
    from payment_drivers.router import get_driver
    from models import format_price_display
    from services.shadow_profile import add_to_travel_history, add_payment_method

    driver = get_driver(driver_name)
    if not driver:
        logger.error(f"Unknown driver {driver_name} for polling")
        return

    op_name = driver.display_name

    # Check test force-fail flag
    session = await db.sessions.find_one({"phone": phone}, {"_id": 0})
    force_fail = session.get("_test_force_fail", False) if session else False

    for attempt in range(10):
        await asyncio.sleep(3)

        if force_fail:
            logger.info(f"Poll {attempt + 1}/10: {driver_name} {reference} = FORCED_FAIL (test mode)")
            break

        result = await driver.check_payment_status(reference)
        logger.info(f"Poll {attempt + 1}/10: {driver_name} {reference} = {result.status}")

        if result.status in ["SUCCESSFUL", "SUCCESS", "COMPLETED"]:
            booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
            if not booking:
                return
            now_utc = datetime.now(timezone.utc)
            await db.bookings.update_one({"id": booking_id}, {"$set": {
                "status": "confirmed", "payment_confirmed_at": now_utc.isoformat(),
                "payment_driver": driver_name, "payment_reference": reference
            }})

            # Update shadow profile
            await add_to_travel_history(phone, booking_ref)
            await add_payment_method(phone, driver_name)

            ts = format_timestamp_gmt1(now_utc)
            masked = mask_phone(phone)
            country = "BJ"  # Default
            session = await db.sessions.find_one({"phone": phone}, {"_id": 0})
            if session:
                country = session.get("_country_code", "BJ")
            price_display = format_price_display(booking.get("price_eur", 0), country)

            if lang == "fr":
                msg = f"*Paiement confirme !*\n\n{price_display} debites -- {op_name} ({masked})\n{ts} GMT+1\nReservation : {booking_ref}\n\nVotre billet est en cours de generation..."
            else:
                msg = f"*Payment confirmed!*\n\n{price_display} debited -- {op_name} ({masked})\n{ts} GMT+1\nBooking: {booking_ref}\n\nYour ticket is being generated..."
            await send_whatsapp_message(phone, msg)

            ticket_filename = generate_ticket_pdf(booking)
            await asyncio.sleep(2)
            fn = booking.get("passenger_name", "")
            if lang == "fr":
                ticket_msg = f"*Votre billet est pret !*\n{fn}\n{booking.get('origin')} -> {booking.get('destination')}\n{booking.get('departure_date')}\n{booking_ref}\nBon voyage !"
            else:
                ticket_msg = f"*Your ticket is ready!*\n{fn}\n{booking.get('origin')} -> {booking.get('destination')}\n{booking.get('departure_date')}\n{booking_ref}\nHave a great trip!"
            await send_whatsapp_document(phone, f"{APP_BASE_URL}/api/tickets/{ticket_filename}", ticket_filename, ticket_msg)
            await clear_session(phone)
            return

        if result.status in ["FAILED", "REJECTED", "CANCELLED"]:
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
        msg = "Delai depasse.\n1 Renvoyer la notification\n2 Changer de methode de paiement\n3 Annuler la reservation"
    else:
        msg = "Timeout.\n1 Resend notification\n2 Change payment method\n3 Cancel booking"
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
