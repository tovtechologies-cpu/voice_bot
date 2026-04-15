"""Data models, conversation states, pricing, and Shadow Profiles."""
import random
from datetime import datetime, timedelta


# ---------------------------------------------------------------------------
# Conversation States
# ---------------------------------------------------------------------------
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
    AWAITING_CONSENT = "awaiting_consent"
    # OCR correction states (Phase II)
    CORRECTING_OCR = "correcting_ocr"
    CORRECTING_TP_OCR = "correcting_tp_ocr"
    # Data deletion (Phase II)
    CONFIRMING_DELETION = "confirming_deletion"
    # Payment fast-track (Phase II)
    PAYMENT_FASTTRACK = "payment_fasttrack"
    # Split payment (Phase II)
    SPLIT_PAYER_COUNT = "split_payer_count"
    SPLIT_COLLECTING_NUMBERS = "split_collecting_numbers"
    SPLIT_CONFIRM = "split_confirm"
    SPLIT_AWAITING_PAYMENTS = "split_awaiting_payments"
    # HITL (Phase C)
    AWAITING_HITL_REVIEW = "awaiting_hitl_review"


# ---------------------------------------------------------------------------
# Payment Operators
# ---------------------------------------------------------------------------
class PaymentOperator:
    MTN_MOMO = "mtn_momo"
    MOOV_MONEY = "moov_money"
    GOOGLE_PAY = "google_pay"
    APPLE_PAY = "apple_pay"
    CELTIIS_CASH = "celtiis_cash"


# ---------------------------------------------------------------------------
# Dynamic Pricing — official Travelioo fee grid
# ---------------------------------------------------------------------------
def calculate_travelioo_fee(gds_price_eur: float) -> float:
    """Tiered Travelioo service fee. Non-refundable in all circumstances."""
    if gds_price_eur < 200:
        return 10.0
    elif gds_price_eur <= 500:
        return round(gds_price_eur * 0.08, 2)
    else:
        return round(gds_price_eur * 0.06, 2)


def apply_travelioo_pricing(gds_price_eur: float) -> dict:
    """Calculate full price breakdown with tiered fee."""
    fee = calculate_travelioo_fee(gds_price_eur)
    total = round(gds_price_eur + fee, 2)
    return {
        "gds_price_eur": round(gds_price_eur, 2),
        "travelioo_fee_eur": fee,
        "total_eur": total,
    }


def format_price_display(eur_amount: float, country_code: str = "BJ") -> str:
    """Localized price display — EUR always first, local currency in parentheses."""
    from config import CFA_COUNTRIES, EUR_TO_XOF
    if country_code in CFA_COUNTRIES:
        xof = round(eur_amount * EUR_TO_XOF)
        return f"{eur_amount:.0f}EUR ({xof:,} XOF)"
    elif country_code == "MA":
        mad = round(eur_amount * 10.9)
        return f"{eur_amount:.0f}EUR ({mad:,} MAD)"
    elif country_code == "NG":
        ngn = round(eur_amount * 1650)
        return f"{eur_amount:.0f}EUR ({ngn:,} NGN)"
    else:
        return f"{eur_amount:.0f}EUR"


# ---------------------------------------------------------------------------
# Fare Conditions (mock profiles for sandbox)
# ---------------------------------------------------------------------------
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
    """Calculate refund. Travelioo fee is NEVER refunded."""
    price_eur = booking.get("price_eur", 0)
    gds_price = booking.get("gds_price_eur") or price_eur
    travelioo_fee = booking.get("travelioo_fee_eur") or calculate_travelioo_fee(gds_price)
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
        return {"case": "non_refundable", "refund_eur": 0, "travelioo_fee": travelioo_fee, "deadline_passed": False}
    if deadline_passed:
        return {"case": "deadline_passed", "refund_eur": 0, "travelioo_fee": travelioo_fee, "deadline_passed": True, "deadline": deadline_str}
    if refundable == "YES":
        refund = gds_price  # Only GDS price is refunded, NOT travelioo fee
        return {"case": "fully_refundable", "refund_eur": round(refund, 2), "travelioo_fee": travelioo_fee, "deadline_passed": False}
    if refundable == "PARTIAL":
        refund = max(0, gds_price - penalty)  # Refund GDS base minus airline penalty
        return {"case": "partial_refund", "refund_eur": round(refund, 2), "airline_penalty": penalty, "travelioo_fee": travelioo_fee, "deadline_passed": False}
    return {"case": "non_refundable", "refund_eur": 0, "travelioo_fee": travelioo_fee, "deadline_passed": False}


# ---------------------------------------------------------------------------
# OCR field labels for interactive correction
# ---------------------------------------------------------------------------
FIELD_LABELS = {
    "firstName": "Prenom / First name",
    "lastName": "Nom de famille / Last name",
    "passportNumber": "Numero de passeport / Passport number",
    "nationality": "Nationalite / Nationality",
    "dateOfBirth": "Date de naissance / Date of birth",
    "expiryDate": "Date d'expiration / Expiry date",
}
