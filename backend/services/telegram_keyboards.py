"""Telegram inline keyboard builder — adds buttons to bot messages."""
from typing import Dict, List, Optional


def build_inline_keyboard(buttons: List[List[Dict]]) -> Dict:
    """Build Telegram inline_keyboard reply_markup JSON."""
    return {
        "inline_keyboard": [
            [{"text": btn["text"], "callback_data": btn["data"]} for btn in row]
            for row in buttons
        ]
    }


def keyboard_welcome() -> Dict:
    return build_inline_keyboard([
        [{"text": "Reserver un vol", "data": "action_book"}],
        [{"text": "Mes reservations", "data": "action_history"}, {"text": "Mon profil", "data": "action_profile"}],
        [{"text": "Aide", "data": "action_help"}],
    ])


def keyboard_enrollment() -> Dict:
    return build_inline_keyboard([
        [{"text": "Scanner mon passeport", "data": "enroll_scan"}],
        [{"text": "Saisie manuelle", "data": "enroll_manual"}],
    ])


def keyboard_travel_purpose(name: str = "") -> Dict:
    return build_inline_keyboard([
        [{"text": f"Pour moi ({name})" if name else "Pour moi", "data": "travel_self"}],
        [{"text": "Pour quelqu'un d'autre", "data": "travel_other"}],
    ])


def keyboard_flight_selection(flights: List[Dict]) -> Dict:
    labels = ["LE PLUS BAS", "LE PLUS RAPIDE", "PREMIUM"]
    buttons = []
    for i, f in enumerate(flights[:3]):
        price = f.get("final_price", 0)
        label = labels[i] if i < len(labels) else f"Option {i+1}"
        buttons.append([{"text": f"{i+1}. {label} - {price}EUR", "data": f"flight_{i+1}"}])
    buttons.append([{"text": "Nouvelle recherche", "data": "flight_new"}])
    return build_inline_keyboard(buttons)


def keyboard_payment(menu: List[Dict]) -> Dict:
    driver_labels = {
        "celtiis_cash": "Celtiis Cash (Recommande)",
        "mtn_momo": "MTN MoMo",
        "moov_money": "Moov Money",
        "stripe": "Google Pay / Apple Pay",
    }
    buttons = []
    for item in menu:
        label = driver_labels.get(item["driver_name"], item["label"])
        buttons.append([{"text": label, "data": f"pay_{item['driver_name']}"}])
    buttons.append([{"text": "Paiement partage", "data": "pay_split"}])
    return build_inline_keyboard(buttons)


def keyboard_payment_confirm() -> Dict:
    return build_inline_keyboard([
        [{"text": "Confirmer le paiement", "data": "confirm_yes"}],
        [{"text": "Annuler", "data": "confirm_cancel"}],
    ])


def keyboard_return_flight() -> Dict:
    return build_inline_keyboard([
        [{"text": "Oui, vol retour", "data": "return_yes"}],
        [{"text": "Non, aller simple", "data": "return_no"}],
    ])


def keyboard_consent() -> Dict:
    return build_inline_keyboard([
        [{"text": "J'accepte, continuer", "data": "action_book"}],
        [{"text": "Non merci", "data": "confirm_cancel"}],
    ])
