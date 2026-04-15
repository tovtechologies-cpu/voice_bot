"""Message formatting for WhatsApp responses."""
from typing import Dict
from models import PaymentOperator, format_price_display
from services.airport import get_city_name
from utils.helpers import eur_to_xof


def format_flight_options_message(categorized: Dict, origin: str, destination: str, date: str) -> str:
    origin_city = get_city_name(origin)
    dest_city = get_city_name(destination)
    msg = f"""*Travelioo -- 3 options trouvees*
{origin_city} -> {dest_city} | {date}
"""
    option_num = 1
    for cat in ["PLUS_BAS", "PLUS_RAPIDE", "PREMIUM"]:
        if cat in categorized:
            f = categorized[cat]
            demo = " Demo" if f.get("is_demo") else ""
            msg += f"""
{f['label']}{demo}
{f['airline']} | {f['stops_text']}
Duree : {f['duration_formatted']}
Prix : *{f['final_price']}EUR* ({f['price_xof']:,} XOF)
Taper *{option_num}* pour selectionner
"""
            option_num += 1
    msg += """
Repondez 1, 2 ou 3 pour continuer."""
    return msg


def format_payment_method_selection(amount_eur: float, lang: str) -> str:
    amount_xof = eur_to_xof(amount_eur)
    if lang == "fr":
        return f"""*Choisissez votre moyen de paiement*
Montant : *{amount_eur}EUR* ({amount_xof:,} XOF)

1 MTN MoMo
2 Moov Money (Flooz)
3 Google Pay
4 Apple Pay

Repondez 1, 2, 3 ou 4"""
    else:
        return f"""*Choose your payment method*
Amount: *{amount_eur}EUR* ({amount_xof:,} XOF)

1 MTN MoMo
2 Moov Money (Flooz)
3 Google Pay
4 Apple Pay

Reply 1, 2, 3, or 4"""


def format_card_payment_link(payment_url: str, lang: str) -> str:
    if lang == "fr":
        return f"""Finalisez votre paiement ici :
{payment_url}

Google Pay disponible sur Android
Apple Pay disponible sur iPhone / Mac
Carte bancaire acceptee sur tous les appareils

Lien valable 15 minutes."""
    else:
        return f"""Complete your payment here:
{payment_url}

Google Pay available on Android
Apple Pay available on iPhone / Mac
Card payment accepted on all devices

Link valid for 15 minutes."""


def format_payment_success(lang: str) -> str:
    if lang == "fr":
        return """Paiement confirme !
Generation de votre billet en cours...
Vous le recevrez dans quelques secondes."""
    else:
        return """Payment confirmed!
Generating your ticket...
You'll receive it in a few seconds."""


def format_payment_failed(operator: str, lang: str) -> str:
    operator_name = {"mtn_momo": "MTN MoMo", "moov_money": "Moov Money"}.get(operator, operator)
    if lang == "fr":
        return f"""Paiement {operator_name} echoue.
Reessayez ou choisissez une autre methode."""
    else:
        return f"""{operator_name} payment failed.
Try again or choose another method."""


def format_retry_options(operator: str, lang: str) -> str:
    operator_name = {"mtn_momo": "MTN MoMo", "moov_money": "Moov Money", "google_pay": "Google Pay", "apple_pay": "Apple Pay"}.get(operator, operator)
    if lang == "fr":
        return f"""Souhaitez-vous reessayer ?

1 Reessayer avec {operator_name}
2 Choisir une autre methode
3 Annuler la reservation"""
    else:
        return f"""Would you like to retry?

1 Retry with {operator_name}
2 Choose another method
3 Cancel booking"""


def format_booking_confirmed(booking: Dict, lang: str) -> str:
    if lang == "fr":
        return f"""Votre billet Travelioo est pret !
Vol {get_city_name(booking['origin'])} -> {get_city_name(booking['destination'])}
{booking['departure_date']}
Reservation : {booking['booking_ref']}
Bon voyage !"""
    else:
        return f"""Your Travelioo ticket is ready!
Flight {get_city_name(booking['origin'])} -> {get_city_name(booking['destination'])}
{booking['departure_date']}
Booking: {booking['booking_ref']}
Have a great trip!"""
