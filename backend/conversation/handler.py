"""Main conversation handler - message dispatcher."""
import logging
from typing import Dict
from models import ConversationState
from services.session import get_or_create_session, update_session, clear_session, get_passenger_by_phone, get_passenger_by_id
from services.whatsapp import send_whatsapp_message
from services.whisper import transcribe_audio
from services.ai import detect_language
from services.security import check_rate_limit, sanitize_input
from conversation.enrollment import (
    handle_enrollment_method_selection, handle_manual_first_name, handle_manual_last_name,
    handle_manual_passport, handle_profile_confirmation, handle_passport_scan,
    handle_travel_purpose, handle_third_party_selection, handle_save_tp_prompt,
    handle_passenger_count, handle_passenger_count_prompt
)
from conversation.booking import (
    handle_awaiting_destination, handle_awaiting_date, handle_flight_selection,
    handle_payment_method, handle_pre_debit_confirm, handle_retry
)
from conversation.cancellation import start_cancellation_flow, handle_cancellation_identify, handle_cancellation_confirm, handle_refund_failed
from conversation.modification import start_modification_flow, handle_modification_requested, handle_modification_confirm

logger = logging.getLogger("ConversationHandler")


async def handle_message(phone: str, message_text: str, audio_id: str = None, image_id: str = None):
    """Main entry point for all WhatsApp messages."""
    # Rate limiting
    allowed = await check_rate_limit(phone, "message")
    if not allowed:
        await send_whatsapp_message(phone, "Trop de messages. Veuillez patienter.")
        return

    session = await get_or_create_session(phone)

    if session.pop("_expired", False):
        lang = session.get("language", "fr")
        msg = "Session expiree. Envoyez un message pour recommencer." if lang == "fr" else "Session expired. Send a message to start again."
        await send_whatsapp_message(phone, msg)

    # Voice -> transcription
    if audio_id and not message_text:
        transcribed = await transcribe_audio(audio_id)
        if transcribed:
            message_text = transcribed
            logger.info(f"Voice transcription for {phone}: '{transcribed[:80]}'")
        else:
            lang = session.get("language", "fr")
            msg = "Je n'ai pas pu transcrire votre message vocal. Pouvez-vous l'ecrire ?" if lang == "fr" else "I couldn't transcribe your voice message. Could you type it instead?"
            await send_whatsapp_message(phone, msg)
            return

    # Sanitize input
    message_text = sanitize_input(message_text) if message_text else ""
    text = message_text.strip().lower()
    original_text = message_text.strip()
    state = session.get("state", ConversationState.IDLE)

    # Detect language
    if state in [ConversationState.IDLE, ConversationState.NEW]:
        if original_text:
            lang = detect_language(original_text)
            await update_session(phone, {"language": lang})
        else:
            lang = session.get("language", "fr")
    else:
        lang = session.get("language", "fr")

    # Image -> passport scan
    if image_id and state in [ConversationState.ENROLLING_SCAN, ConversationState.ENROLLING_TP_SCAN]:
        await handle_passport_scan(phone, image_id, state, session, lang)
        return

    # Global cancel
    if text in ["annuler", "cancel", "stop", "reset"]:
        cancelable = [
            ConversationState.AWAITING_PAYMENT_METHOD, "retry",
            ConversationState.ENROLLMENT_METHOD, ConversationState.ENROLLING_SCAN,
            ConversationState.ENROLLING_MANUAL_FN, ConversationState.ENROLLING_MANUAL_LN,
            ConversationState.ENROLLING_MANUAL_PP, ConversationState.CONFIRMING_PROFILE,
            ConversationState.ASKING_TRAVEL_PURPOSE, ConversationState.SELECTING_THIRD_PARTY,
            ConversationState.ENROLLING_THIRD_PARTY_METHOD, ConversationState.ENROLLING_TP_SCAN,
            ConversationState.ENROLLING_TP_MANUAL_FN, ConversationState.ENROLLING_TP_MANUAL_LN,
            ConversationState.ENROLLING_TP_MANUAL_PP, ConversationState.CONFIRMING_TP_PROFILE,
            ConversationState.SAVE_TP_PROMPT,
        ]
        if state in cancelable:
            await clear_session(phone)
            msg = "Annule. Envoyez un message pour recommencer." if lang == "fr" else "Cancelled. Send a message to start again."
            await send_whatsapp_message(phone, msg)
            return

    # Global start/help
    if text in ["start", "aide", "help", "menu"]:
        await clear_session(phone)
        await start_conversation(phone, lang)
        return

    # === ENROLLMENT STATES ===
    if state == ConversationState.ENROLLMENT_METHOD:
        await handle_enrollment_method_selection(phone, text, session, lang)
        return
    if state == ConversationState.ENROLLING_SCAN:
        msg = "Envoyez une *photo* de votre passeport, ou tapez *3* pour la saisie manuelle." if lang == "fr" else "Send a *photo* of your passport, or type *3* for manual entry."
        await send_whatsapp_message(phone, msg)
        return
    if state == ConversationState.ENROLLING_MANUAL_FN:
        await handle_manual_first_name(phone, original_text, session, lang, is_tp=False)
        return
    if state == ConversationState.ENROLLING_MANUAL_LN:
        await handle_manual_last_name(phone, original_text, session, lang, is_tp=False)
        return
    if state == ConversationState.ENROLLING_MANUAL_PP:
        await handle_manual_passport(phone, original_text, session, lang, is_tp=False)
        return
    if state == ConversationState.CONFIRMING_PROFILE:
        await handle_profile_confirmation(phone, text, session, lang, is_tp=False)
        return

    # === THIRD-PARTY ENROLLMENT ===
    if state == ConversationState.ASKING_TRAVEL_PURPOSE:
        await handle_travel_purpose(phone, text, session, lang)
        return
    if state == ConversationState.SELECTING_THIRD_PARTY:
        await handle_third_party_selection(phone, text, session, lang)
        return
    if state == ConversationState.ENROLLING_THIRD_PARTY_METHOD:
        await handle_enrollment_method_selection(phone, text, session, lang, is_tp=True)
        return
    if state == ConversationState.ENROLLING_TP_SCAN:
        msg = "Envoyez une *photo* du passeport, ou tapez *3* pour la saisie manuelle." if lang == "fr" else "Send a *photo* of the passport, or type *3* for manual entry."
        await send_whatsapp_message(phone, msg)
        return
    if state == ConversationState.ENROLLING_TP_MANUAL_FN:
        await handle_manual_first_name(phone, original_text, session, lang, is_tp=True)
        return
    if state == ConversationState.ENROLLING_TP_MANUAL_LN:
        await handle_manual_last_name(phone, original_text, session, lang, is_tp=True)
        return
    if state == ConversationState.ENROLLING_TP_MANUAL_PP:
        await handle_manual_passport(phone, original_text, session, lang, is_tp=True)
        return
    if state == ConversationState.CONFIRMING_TP_PROFILE:
        await handle_profile_confirmation(phone, text, session, lang, is_tp=True)
        return
    if state == ConversationState.SAVE_TP_PROMPT:
        await handle_save_tp_prompt(phone, text, session, lang)
        return

    # === MULTI-PASSENGER STUB ===
    if state == ConversationState.ASKING_PASSENGER_COUNT:
        await handle_passenger_count(phone, text, session, lang)
        return

    # === IDLE - Entry point ===
    if state == ConversationState.IDLE:
        if text in ["remboursement", "refund", "rembourser", "annuler reservation", "cancel booking"]:
            await start_cancellation_flow(phone, lang)
            return
        if text in ["modifier", "changer", "change", "modify", "modification"]:
            await start_modification_flow(phone, lang)
            return
        if text in ["bonjour", "hello", "hi", "salut"]:
            await start_conversation(phone, lang)
            return
        passenger = await get_passenger_by_phone(phone)
        if passenger:
            await update_session(phone, {"passenger_id": passenger["id"]})
            await handle_returning_user(phone, passenger, lang)
            return
        else:
            await handle_new_user(phone, lang)
            return

    # === TRAVEL FLOW - Allow cancel/refund/modify ===
    if text in ["remboursement", "refund", "rembourser"] and state in [
        ConversationState.ASKING_TRAVEL_PURPOSE, ConversationState.AWAITING_DESTINATION,
        ConversationState.AWAITING_DATE, ConversationState.ASKING_PASSENGER_COUNT
    ]:
        await start_cancellation_flow(phone, lang)
        return
    if text in ["modifier", "changer", "change", "modify"] and state in [
        ConversationState.ASKING_TRAVEL_PURPOSE, ConversationState.AWAITING_DESTINATION,
        ConversationState.AWAITING_DATE, ConversationState.ASKING_PASSENGER_COUNT
    ]:
        await start_modification_flow(phone, lang)
        return

    # === BOOKING STATES ===
    if state == ConversationState.AWAITING_DESTINATION:
        await handle_awaiting_destination(phone, original_text, session, lang)
        return
    if state == ConversationState.AWAITING_DATE:
        await handle_awaiting_date(phone, original_text, text, session, lang)
        return
    if state == ConversationState.AWAITING_FLIGHT_SELECTION:
        await handle_flight_selection(phone, text, session, lang)
        return
    if state == ConversationState.AWAITING_PAYMENT_METHOD:
        await handle_payment_method(phone, text, session, lang)
        return
    if state == ConversationState.AWAITING_PAYMENT_CONFIRM:
        await handle_pre_debit_confirm(phone, text, session, lang)
        return
    if state == "retry":
        await handle_retry(phone, text, session, lang)
        return
    if state == ConversationState.AWAITING_MOBILE_PAYMENT:
        msg = "Paiement en cours... Approuvez sur votre telephone." if lang == "fr" else "Payment in progress... Approve on your phone."
        await send_whatsapp_message(phone, msg)
        return
    if state == ConversationState.AWAITING_CARD_PAYMENT:
        booking_ref = session.get("booking_ref")
        msg = f"En attente du paiement...\nUtilisez le lien envoye pour payer.\nReference : {booking_ref}" if lang == "fr" else f"Waiting for payment...\nUse the link sent to complete payment.\nReference: {booking_ref}"
        await send_whatsapp_message(phone, msg)
        return

    # === POST-BOOKING STATES ===
    if state == ConversationState.CANCELLATION_IDENTIFY:
        await handle_cancellation_identify(phone, text, session, lang)
        return
    if state == ConversationState.CANCELLATION_CONFIRM:
        await handle_cancellation_confirm(phone, text, session, lang)
        return
    if state == ConversationState.CANCELLATION_PROCESSING:
        msg = "Remboursement en cours... Veuillez patienter." if lang == "fr" else "Refund in progress... Please wait."
        await send_whatsapp_message(phone, msg)
        return
    if state == ConversationState.REFUND_FAILED:
        await handle_refund_failed(phone, text, session, lang)
        return
    if state == ConversationState.MODIFICATION_REQUESTED:
        await handle_modification_requested(phone, text, session, lang)
        return
    if state == ConversationState.MODIFICATION_CONFIRM:
        await handle_modification_confirm(phone, text, session, lang)
        return

    # Fallback
    await clear_session(phone)
    await start_conversation(phone, lang)


async def start_conversation(phone: str, lang: str):
    passenger = await get_passenger_by_phone(phone)
    if passenger:
        await update_session(phone, {"passenger_id": passenger["id"]})
        await handle_returning_user(phone, passenger, lang)
    else:
        await handle_new_user(phone, lang)


async def handle_new_user(phone: str, lang: str):
    if lang == "fr":
        msg = """Bienvenue sur Travelio !
Avant de rechercher votre vol, j'ai besoin de votre nom pour le billet.

Comment souhaitez-vous renseigner vos informations ?

1 Scanner mon passeport (photo)
2 Envoyer une photo de mon passeport
3 Saisie manuelle"""
    else:
        msg = """Welcome to Travelio!
Before searching for your flight, I need your name for the ticket.

How would you like to provide your information?

1 Scan my passport (photo)
2 Send a photo of my passport
3 Manual entry"""
    await update_session(phone, {"state": ConversationState.ENROLLMENT_METHOD, "enrolling_for": "self"})
    await send_whatsapp_message(phone, msg)


async def handle_returning_user(phone: str, passenger: Dict, lang: str):
    fn = passenger.get("firstName", "")
    ln = passenger.get("lastName", "")
    if lang == "fr":
        msg = f"""Rebonjour {fn} !
Reservez-vous ce vol pour vous-meme ou pour quelqu'un d'autre ?

1 Pour moi ({fn} {ln})
2 Pour un tiers"""
    else:
        msg = f"""Welcome back {fn}!
Are you booking this flight for yourself or someone else?

1 For me ({fn} {ln})
2 For someone else"""
    await update_session(phone, {"state": ConversationState.ASKING_TRAVEL_PURPOSE})
    await send_whatsapp_message(phone, msg)
