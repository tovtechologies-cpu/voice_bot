"""Premium message formatting for WhatsApp and Telegram."""
from typing import Dict, List
from models import format_price_display
from services.airport import get_city_name
from utils.helpers import eur_to_xof

SEP = "━━━━━━━━━━━━━━━━━━━━━"


def format_flight_options_message(categorized: Dict, origin: str, destination: str, date: str, lang: str = "fr", country: str = "BJ") -> str:
    origin_city = get_city_name(origin)
    dest_city = get_city_name(destination)
    count = len(categorized)

    if lang == "fr":
        msg = f"*{count} vols trouves pour vous*\n_{origin_city} -> {dest_city} | {date}_\n\n"
    else:
        msg = f"*{count} flights found for you*\n_{origin_city} -> {dest_city} | {date}_\n\n"

    labels_fr = {"PLUS_BAS": "LE PLUS BAS", "PLUS_RAPIDE": "LE PLUS RAPIDE", "PREMIUM": "PREMIUM"}
    labels_en = {"PLUS_BAS": "CHEAPEST", "PLUS_RAPIDE": "FASTEST", "PREMIUM": "PREMIUM"}
    icons = {"PLUS_BAS": "", "PLUS_RAPIDE": "", "PREMIUM": ""}
    labels = labels_fr if lang == "fr" else labels_en

    option_num = 1
    for cat in ["PLUS_BAS", "PLUS_RAPIDE", "PREMIUM"]:
        if cat in categorized:
            f = categorized[cat]
            label = labels.get(cat, cat)
            icon = icons.get(cat, "")
            price_eur = f['final_price']
            price_xof = eur_to_xof(price_eur)
            airline = f.get('airline', '')
            flight_num = f.get('flight_number', '')
            dep_time = f.get('departure_time', '')
            arr_time = f.get('arrival_time', '')
            duration = f.get('duration_formatted', '')
            stops = f.get('stops_text', '')

            msg += f"{SEP}\n"
            msg += f"{icon} *{label}*\n"
            msg += f"  {airline} | {flight_num}\n"
            if dep_time and arr_time:
                msg += f"  {dep_time} -> {arr_time} _({duration})_\n"
            else:
                msg += f"  {stops} | {duration}\n"
            msg += f"  *{price_eur}EUR* _({price_xof:,} XOF)_\n\n"
            option_num += 1

    msg += f"{SEP}\n\n"
    msg += "*1*, *2* ou *3* pour selectionner." if lang == "fr" else "*1*, *2* or *3* to select."
    return msg


def format_payment_menu(menu: List[Dict], pricing: Dict, country: str, lang: str) -> str:
    total_eur = pricing.get("total_eur", 0)
    gds_eur = pricing.get("gds_price_eur", total_eur)
    fee_eur = pricing.get("travelioo_fee_eur", 0)
    total_display = format_price_display(total_eur, country)
    gds_display = format_price_display(gds_eur, country)
    fee_display = format_price_display(fee_eur, country)

    if lang == "fr":
        msg = f"*Choisissez votre mode de paiement*\n\n"
        msg += f"Prix vol : {gds_display}\n"
        msg += f"Frais Travelioo : {fee_display}\n"
        msg += f"*Total : {total_display}*\n\n"
    else:
        msg = f"*Choose your payment method*\n\n"
        msg += f"Flight price: {gds_display}\n"
        msg += f"Travelioo fee: {fee_display}\n"
        msg += f"*Total: {total_display}*\n\n"

    driver_icons = {
        "celtiis_cash": "  ",
        "mtn_momo": "",
        "moov_money": "",
        "stripe": "",
    }
    for item in menu:
        icon = driver_icons.get(item["driver_name"], "")
        recommended = " _(Recommande)_" if item["index"] == 1 and item["driver_name"] == "celtiis_cash" and lang == "fr" else ""
        recommended = " _(Recommended)_" if item["index"] == 1 and item["driver_name"] == "celtiis_cash" and lang == "en" else recommended
        msg += f"*{item['index']}* {icon} {item['label']}{recommended}\n"

    msg += f"\n_Payer a plusieurs ?_\nTapez *split* pour fractionner." if lang == "fr" else f"\n_Split payment?_\nType *split* to share."
    return msg


def format_payment_confirm(selected: Dict, passenger_name: str, driver_name: str,
                            pricing: Dict, fare_summary: str, country: str, lang: str) -> str:
    total_eur = pricing.get("total_eur", 0)
    gds_eur = pricing.get("gds_price_eur", total_eur)
    fee_eur = pricing.get("travelioo_fee_eur", 0)
    total_display = format_price_display(total_eur, country)
    gds_display = format_price_display(gds_eur, country)
    fee_display = format_price_display(fee_eur, country)
    dep_date = selected.get('departure_time', '').split('T')[0]

    if lang == "fr":
        msg = f"*Recapitulatif de votre paiement*\n\n"
        msg += f"Vol : {selected['origin']} -> {selected['destination']}\n"
        msg += f"Depart : {dep_date}\n"
        msg += f"Passager : {passenger_name}\n"
        msg += f"Classe : {selected.get('category', 'Economy')}\n"
        msg += f"Methode : {driver_name}\n\n"
        msg += f"*Conditions du billet :*\n{fare_summary}\n\n"
        msg += f"Prix vol : {gds_display}\n"
        msg += f"Frais Travelioo : {fee_display} _(non remboursables)_\n"
        msg += f"*Total : {total_display}*\n\n"
        msg += "*1* Oui, envoyer la notification de paiement\n"
        msg += "*2* Non, annuler\n"
        msg += "*3* Voir les conditions completes"
    else:
        msg = f"*Payment Summary*\n\n"
        msg += f"Flight: {selected['origin']} -> {selected['destination']}\n"
        msg += f"Departure: {dep_date}\n"
        msg += f"Passenger: {passenger_name}\n"
        msg += f"Class: {selected.get('category', 'Economy')}\n"
        msg += f"Method: {driver_name}\n\n"
        msg += f"*Ticket conditions:*\n{fare_summary}\n\n"
        msg += f"Flight price: {gds_display}\n"
        msg += f"Travelioo fee: {fee_display} _(non-refundable)_\n"
        msg += f"*Total: {total_display}*\n\n"
        msg += "*1* Yes, send payment notification\n"
        msg += "*2* No, cancel\n"
        msg += "*3* View full conditions"
    return msg


def format_booking_confirmed(booking: Dict, lang: str) -> str:
    origin_city = get_city_name(booking.get('origin', ''))
    dest_city = get_city_name(booking.get('destination', ''))
    ref = booking.get('booking_ref', '')
    passenger = booking.get('passenger_name', '')
    date = booking.get('departure_date', '')
    flight = booking.get('flight_number', '')

    if lang == "fr":
        return f"""*Votre billet Travelioo est pret !*

{passenger}
{origin_city} -> {dest_city}
Vol {flight} | {date}
Reference : `{ref}`

Bon voyage !"""
    else:
        return f"""*Your Travelioo ticket is ready!*

{passenger}
{origin_city} -> {dest_city}
Flight {flight} | {date}
Reference: `{ref}`

Have a great trip!"""


def format_welcome_message(first_name: str = "", lang: str = "fr") -> str:
    name = f" {first_name}" if first_name else ""
    if lang == "fr":
        return f"""*Bienvenue sur Travelioo{name} !*

Speak'n Go — Reservez votre vol par vocal ou par ecrit.

*1* Chercher un vol
*2* Mes reservations
*3* Aide

_Partenaire exclusif Celtiis Cash_"""
    else:
        return f"""*Welcome to Travelioo{name}!*

Speak'n Go — Book your flight by voice or text.

*1* Search a flight
*2* My bookings
*3* Help

_Exclusive Celtiis Cash partner_"""


def format_payment_success(booking: Dict, driver_name: str, lang: str) -> str:
    ref = booking.get('booking_ref', '')
    if lang == "fr":
        return f"""*Paiement confirme !*

{booking.get('price_eur', 0)}EUR debites via {driver_name}
Reservation : `{ref}`

Votre billet est en cours de generation..."""
    else:
        return f"""*Payment confirmed!*

{booking.get('price_eur', 0)}EUR debited via {driver_name}
Booking: `{ref}`

Your ticket is being generated..."""


def format_payment_failed(operator: str, lang: str) -> str:
    if lang == "fr":
        return f"*Paiement echoue*\n\nReessayez ou choisissez une autre methode."
    return f"*Payment failed*\n\nPlease try again or choose another method."


def format_retry_options(operator: str, lang: str) -> str:
    if lang == "fr":
        return "*1* Reessayer\n*2* Choisir une autre methode\n*3* Annuler la reservation"
    return "*1* Retry\n*2* Choose another method\n*3* Cancel booking"
