import random
from datetime import datetime, timedelta
from config import TRAVELIO_FEE


class ConversationState:
    IDLE = "idle"
    NEW = "new"
    ENROLLMENT_METHOD = "enrollment_method"
    ENROLLING_SCAN = "enrolling_scan"
    ENROLLING_MANUAL_FN = "enrolling_manual_fn"
    ENROLLING_MANUAL_LN = "enrolling_manual_ln"
    ENROLLING_MANUAL_PP = "enrolling_manual_pp"
    CONFIRMING_PROFILE = "confirming_profile"
    ASKING_TRAVEL_PURPOSE = "asking_travel_purpose"
    SELECTING_THIRD_PARTY = "selecting_third_party"
    ENROLLING_THIRD_PARTY_METHOD = "enrolling_third_party_method"
    ENROLLING_TP_SCAN = "enrolling_tp_scan"
    ENROLLING_TP_MANUAL_FN = "enrolling_tp_manual_fn"
    ENROLLING_TP_MANUAL_LN = "enrolling_tp_manual_ln"
    ENROLLING_TP_MANUAL_PP = "enrolling_tp_manual_pp"
    CONFIRMING_TP_PROFILE = "confirming_tp_profile"
    SAVE_TP_PROMPT = "save_tp_prompt"
    ASKING_PASSENGER_COUNT = "asking_passenger_count"
    AWAITING_DESTINATION = "awaiting_destination"
    AWAITING_DATE = "awaiting_date"
    AWAITING_FLIGHT_SELECTION = "awaiting_flight_selection"
    AWAITING_PAYMENT_METHOD = "awaiting_payment_method"
    AWAITING_PAYMENT_CONFIRM = "awaiting_payment_confirm"
    AWAITING_PAYMENT_CONFIRMATION = "awaiting_payment_confirmation"
    AWAITING_MOBILE_PAYMENT = "awaiting_mobile_payment"
    AWAITING_CARD_PAYMENT = "awaiting_card_payment"
    CANCELLATION_IDENTIFY = "cancellation_identify"
    CANCELLATION_CONFIRM = "cancellation_confirm"
    CANCELLATION_PROCESSING = "cancellation_processing"
    REFUND_FAILED = "refund_failed"
    MODIFICATION_REQUESTED = "modification_requested"
    MODIFICATION_CONFIRM = "modification_confirm"
    # Legal consent
    AWAITING_CONSENT = "awaiting_consent"


class PaymentOperator:
    MTN_MOMO = "mtn_momo"
    MOOV_MONEY = "moov_money"
    GOOGLE_PAY = "google_pay"
    APPLE_PAY = "apple_pay"
    CELTIIS_CASH = "celtiis_cash"


MOCK_FARE_PROFILES = [
    {
        "name": "Budget",
        "refundable": "NO",
        "refund_penalty_eur": None,
        "change_allowed": False,
        "change_penalty_eur": None,
        "refund_deadline": None,
        "conditions_raw": "Billet non remboursable, non modifiable. Aucun changement autorise apres l'achat.",
        "conditions_summary": "- Remboursable : Non -- aucun remboursement\n- Modifiable : Non -- billet sec\n- Delai : Sans objet"
    },
    {
        "name": "Standard",
        "refundable": "PARTIAL",
        "refund_penalty_eur": 80.0,
        "change_allowed": True,
        "change_penalty_eur": 50.0,
        "refund_deadline_hours_before": 48,
        "conditions_raw": "Remboursable avec penalite de 80EUR. Modifiable avec frais de 50EUR. Annulation et modification possibles jusqu'a 48h avant le depart.",
        "conditions_summary": "- Remboursable : Oui avec penalite de 80EUR\n- Modifiable : Oui avec frais de 50EUR\n- Delai : Annulation/modification 48h avant le depart"
    },
    {
        "name": "Flex",
        "refundable": "YES",
        "refund_penalty_eur": 0.0,
        "change_allowed": True,
        "change_penalty_eur": 0.0,
        "refund_deadline_hours_before": 2,
        "conditions_raw": "Billet entierement remboursable sans penalite. Modifiable sans frais. Delai d'annulation jusqu'a 2h avant le depart.",
        "conditions_summary": "- Remboursable : Oui -- remboursement integral\n- Modifiable : Oui -- sans frais\n- Delai : Jusqu'a 2h avant le depart"
    }
]


def get_fare_conditions(departure_date: str = None) -> dict:
    """Get fare conditions -- mock in sandbox, real from Duffel in production."""
    profile = random.choice(MOCK_FARE_PROFILES).copy()
    if departure_date and profile.get("refund_deadline_hours_before"):
        try:
            dep = datetime.strptime(departure_date, "%Y-%m-%d")
            deadline = dep - timedelta(hours=profile["refund_deadline_hours_before"])
            profile["refund_deadline"] = deadline.strftime("%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            profile["refund_deadline"] = None
    else:
        profile["refund_deadline"] = profile.get("refund_deadline")
    profile.pop("refund_deadline_hours_before", None)
    return profile


def calculate_refund(booking: dict) -> dict:
    """Calculate refund based on fare conditions and Travelio fee policy."""
    price_eur = booking.get("price_eur", 0)
    refundable = booking.get("refundable", "NO")
    penalty = booking.get("refund_penalty_eur") or 0
    deadline_str = booking.get("refund_deadline")

    deadline_passed = False
    if deadline_str:
        try:
            deadline = datetime.strptime(deadline_str, "%Y-%m-%d %H:%M")
            if datetime.now() > deadline:
                deadline_passed = True
        except (ValueError, TypeError):
            pass

    if refundable == "NO":
        return {"case": "non_refundable", "refund_eur": 0, "deadline_passed": False}
    if deadline_passed:
        return {"case": "deadline_passed", "refund_eur": 0, "deadline_passed": True, "deadline": deadline_str}
    if refundable == "YES":
        refund = price_eur - TRAVELIO_FEE
        return {"case": "fully_refundable", "refund_eur": round(refund, 2), "deadline_passed": False}
    if refundable == "PARTIAL":
        refund = max(0, price_eur - penalty - TRAVELIO_FEE)
        return {"case": "partial_refund", "refund_eur": round(refund, 2), "airline_penalty": penalty, "deadline_passed": False}
    return {"case": "non_refundable", "refund_eur": 0, "deadline_passed": False}
