"""Premium message formatting for WhatsApp and Telegram."""
from typing import Dict, List
from models import format_price_display
from services.airport import get_city_name
from utils.helpers import eur_to_xof

SEP = "━━━━━━━━━━━━━━━━━━━━━"


def format_flight_options_message(categorized: Dict, origin: str, destination: str, date: str, lang: str = "fr", country: str = "BJ", return_date: str = None) -> str:
    origin_city = get_city_name(origin)
    dest_city = get_city_name(destination)
    count = len(categorized)
    is_rt = return_date is not None

    if lang == "fr":
        if is_rt:
            msg = f"✨ *Vols aller-retour trouvés*\n_{origin_city} ✈️ {dest_city} ✈️ {origin_city}_\n_Aller : {date} | Retour : {return_date}_\n\n"
        else:
            msg = f"✨ *{count} vols trouvés pour vous*\n_{origin_city} ✈️ {dest_city} | {date}_\n\n"
    else:
        if is_rt:
            msg = f"✨ *Round-trip flights found*\n_{origin_city} ✈️ {dest_city} ✈️ {origin_city}_\n_Out: {date} | Return: {return_date}_\n\n"
        else:
            msg = f"✨ *{count} flights found for you*\n_{origin_city} ✈️ {dest_city} | {date}_\n\n"

    labels_fr = {"PLUS_BAS": "LE PLUS BAS", "PLUS_RAPIDE": "LE PLUS RAPIDE", "PREMIUM": "PREMIUM"}
    labels_en = {"PLUS_BAS": "CHEAPEST", "PLUS_RAPIDE": "FASTEST", "PREMIUM": "PREMIUM"}
    labels = labels_fr if lang == "fr" else labels_en

    option_num = 1
    for cat in ["PLUS_BAS", "PLUS_RAPIDE", "PREMIUM"]:
        if cat in categorized:
            f = categorized[cat]
            label = labels.get(cat, cat)
            price_eur = f['final_price']
            price_xof = eur_to_xof(price_eur)
            airline = f.get('airline', '')
            flight_num = f.get('flight_number', '')
            dep_time = f.get('departure_time', '').split('T')[1][:5] if 'T' in f.get('departure_time', '') else ''
            arr_time = f.get('arrival_time', '').split('T')[1][:5] if 'T' in f.get('arrival_time', '') else ''
            duration = f.get('duration_formatted', '')
            stops = f.get('stops_text', '')

            msg += f"{SEP}\n"
            msg += f"*{label}*\n\n"

            # Outbound
            if is_rt:
                msg += f"*ALLER*\n"
            msg += f"  {airline} | {flight_num}\n"
            if dep_time and arr_time:
                msg += f"  {dep_time} -> {arr_time} _({duration} {stops})_\n"

            # Return leg
            ret = f.get('return_leg')
            if ret and is_rt:
                ret_dep = ret.get('departure_time', '').split('T')[1][:5] if 'T' in ret.get('departure_time', '') else ''
                ret_arr = ret.get('arrival_time', '').split('T')[1][:5] if 'T' in ret.get('arrival_time', '') else ''
                ret_dur = ret.get('duration_formatted', '')
                ret_stops = ret.get('stops_text', '')
                msg += f"\n*RETOUR*\n" if lang == "fr" else f"\n*RETURN*\n"
                msg += f"  {ret.get('airline', airline)} | {ret.get('flight_number', '')}\n"
                if ret_dep and ret_arr:
                    msg += f"  {ret_dep} -> {ret_arr} _({ret_dur} {ret_stops})_\n"

            # Price
            from models import calculate_travelioo_fee, format_price_display
            from config import EUR_TO_XOF
            fee = calculate_travelioo_fee(f.get('base_price', price_eur))
            price_display = format_price_display(price_eur, country)
            fee_display = format_price_display(fee, country)
            if lang == "fr":
                msg += f"\n  *Prix total : {price_display}*\n"
                msg += f"  _(dont frais Travelioo : {fee_display})_\n\n"
            else:
                msg += f"\n  *Total price: {price_display}*\n"
                msg += f"  _(incl. Travelioo fee: {fee_display})_\n\n"
            option_num += 1

    msg += f"{SEP}\n\n"
    msg += "Tapez *1*, *2* ou *3* pour selectionner." if lang == "fr" else "Type *1*, *2* or *3* to select."
    return msg


def format_payment_menu(menu: List[Dict], pricing: Dict, country: str, lang: str) -> str:
    total_eur = pricing.get("total_eur", 0)
    gds_eur = pricing.get("gds_price_eur", total_eur)
    fee_eur = pricing.get("travelioo_fee_eur", 0)
    total_display = format_price_display(total_eur, country)
    gds_display = format_price_display(gds_eur, country)
    fee_display = format_price_display(fee_eur, country)

    if lang == "fr":
        msg = f"💳 *Choisissez votre mode de paiement*\n\n"
        msg += f"🎫 Prix vol : {gds_display}\n"
        msg += f"⚙️ Frais Travelioo : {fee_display}\n"
        msg += f"💰 *Total : {total_display}*\n\n"
    else:
        msg = f"💳 *Choose your payment method*\n\n"
        msg += f"🎫 Flight price: {gds_display}\n"
        msg += f"⚙️ Travelioo fee: {fee_display}\n"
        msg += f"💰 *Total: {total_display}*\n\n"

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
        msg = f"📝 *Récapitulatif de votre paiement*\n\n"
        msg += f"✈️ Vol : {selected['origin']} ➡️ {selected['destination']}\n"
        msg += f"📅 Départ : {dep_date}\n"
        msg += f"👤 Passager : {passenger_name}\n"
        msg += f"💺 Classe : {selected.get('category', 'Economy')}\n"
        msg += f"💳 Méthode : {driver_name}\n\n"
        msg += f"ℹ️ *Conditions du billet :*\n{fare_summary}\n\n"
        msg += f"🎫 Prix vol : {gds_display}\n"
        msg += f"⚙️ Frais Travelioo : {fee_display} _(non remboursables)_\n"
        msg += f"💰 *Total : {total_display}*\n\n"
        msg += "✅ *1* Oui, envoyer la notification\n"
        msg += "❌ *2* Non, annuler\n"
        msg += "📋 *3* Voir les conditions complètes"
    else:
        msg = f"📝 *Payment Summary*\n\n"
        msg += f"✈️ Flight: {selected['origin']} ➡️ {selected['destination']}\n"
        msg += f"📅 Departure: {dep_date}\n"
        msg += f"👤 Passenger: {passenger_name}\n"
        msg += f"💺 Class: {selected.get('category', 'Economy')}\n"
        msg += f"💳 Method: {driver_name}\n\n"
        msg += f"ℹ️ *Ticket conditions:*\n{fare_summary}\n\n"
        msg += f"🎫 Flight price: {gds_display}\n"
        msg += f"⚙️ Travelioo fee: {fee_display} _(non-refundable)_\n"
        msg += f"💰 *Total: {total_display}*\n\n"
        msg += "✅ *1* Yes, send notification\n"
        msg += "❌ *2* No, cancel\n"
        msg += "📋 *3* View full conditions"
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
