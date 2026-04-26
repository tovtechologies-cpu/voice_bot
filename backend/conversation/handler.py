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
    handle_manual_passport, handle_manual_nationality, handle_profile_confirmation, handle_passport_scan,
    handle_travel_purpose, handle_third_party_selection, handle_save_tp_prompt,
    handle_passenger_count, handle_passenger_count_prompt, handle_consent,
    handle_ocr_correction
)
from conversation.booking import (
    handle_awaiting_destination, handle_awaiting_date, handle_flight_selection,
    handle_payment_method, handle_pre_debit_confirm, handle_retry,
    handle_payment_fasttrack
)
from conversation.split_payment import (
    handle_split_payer_count, handle_split_collecting_numbers,
    handle_split_confirm
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

    # Detect language (extended: fr, en, wo, fon, yo, ha, sw)
    detected_lang = None
    if state in [ConversationState.IDLE, ConversationState.NEW]:
        if original_text:
            detected_lang = detect_language(original_text)
            await update_session(phone, {"language": detected_lang, "_source_lang": detected_lang})
            # Update shadow profile language
            from services.shadow_profile import update_shadow_profile
            await update_shadow_profile(phone, {"language_pref": detected_lang})
        else:
            detected_lang = session.get("language", "fr")
    else:
        detected_lang = session.get("language", "fr")

    # Translation pipeline for African languages
    from services.translation import AFRICAN_LANGUAGES, translate_to_french, LANGUAGE_NAMES
    source_lang = detected_lang or session.get("_source_lang", "fr")

    if source_lang in AFRICAN_LANGUAGES and original_text:
        translated, confidence = await translate_to_french(original_text, source_lang)
        logger.info(f"[MULTILINGUAL] {source_lang} -> FR | conf={confidence:.2f} | {phone}")

        # HITL check: low confidence or high-value context
        from services.hitl import needs_human_review, trigger_human_review
        booking_amount = session.get("_pricing", {}).get("total_eur", 0)
        if needs_human_review(confidence, booking_amount):
            reason = f"low_confidence ({confidence:.2f})" if confidence < 0.85 else f"high_value ({booking_amount} EUR)"
            review_id = await trigger_human_review(
                phone=phone, original_text=original_text, translated_text=translated,
                source_lang=source_lang, confidence=confidence, reason=reason,
                context={"state": state, "booking_amount": booking_amount})
            await update_session(phone, {"_hitl_review_id": review_id, "_hitl_original": original_text})
            lang_name = LANGUAGE_NAMES.get(source_lang, source_lang)
            msg = f"Je verifie votre demande en {lang_name}, je reviens vers vous dans 2 minutes."
            await send_whatsapp_message(phone, msg)
            # Still process the translated message but log the HITL flag
            logger.info(f"[HITL] Review triggered: {review_id} — proceeding with best-effort translation")

        # Use translated text for the rest of the flow
        message_text = translated
        text = translated.strip().lower()
        original_text = translated.strip()
        # Response language stays French for African language users
        lang = "fr"
    else:
        # Direct language (fr or en)
        lang = detected_lang if detected_lang in ["fr", "en"] else "fr"

    # Image -> passport scan
    if image_id and state in [ConversationState.ENROLLING_SCAN, ConversationState.ENROLLING_TP_SCAN]:
        await handle_passport_scan(phone, image_id, state, session, lang)
        return

    # Global cancel
    if text in ["annuler", "cancel", "stop", "reset"]:
        cancelable = [
            ConversationState.AWAITING_PAYMENT_METHOD, ConversationState.PAYMENT_FASTTRACK,
            ConversationState.SPLIT_PAYER_COUNT, ConversationState.SPLIT_COLLECTING_NUMBERS,
            ConversationState.SPLIT_CONFIRM, "retry",
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

    # === CONSENT STATE ===
    if state == ConversationState.AWAITING_CONSENT:
        await handle_consent(phone, text, session, lang)
        return

    # === DATA DELETION ===
    if text.upper() in ["SUPPRIMER MES DONNEES", "SUPPRIMER MES DONNÉES", "DELETE MY DATA"]:
        from services.whatsapp import send_whatsapp_message as _send
        if lang == "fr":
            msg = "Etes-vous sur de vouloir supprimer toutes vos donnees ? Cette action est irreversible.\n\n*1* Oui, supprimer tout\n*2* Non, annuler"
        else:
            msg = "Are you sure you want to delete all your data? This action is irreversible.\n\n*1* Yes, delete everything\n*2* No, cancel"
        await update_session(phone, {"state": ConversationState.CONFIRMING_DELETION})
        await send_whatsapp_message(phone, msg)
        return

    if state == ConversationState.CONFIRMING_DELETION:
        if text in ["1", "oui", "yes"]:
            from services.shadow_profile import delete_user_data
            success = await delete_user_data(phone)
            if success:
                msg = "Toutes vos donnees ont ete supprimees." if lang == "fr" else "All your data has been deleted."
            else:
                msg = "Erreur lors de la suppression. Contactez support@travelioo.app" if lang == "fr" else "Deletion error. Contact support@travelioo.app"
            await clear_session(phone)
            await send_whatsapp_message(phone, msg)
        else:
            msg = "Suppression annulee." if lang == "fr" else "Deletion cancelled."
            await clear_session(phone)
            await send_whatsapp_message(phone, msg)
        return

    # === OCR CORRECTION STATES ===
    if state in [ConversationState.CORRECTING_OCR, ConversationState.CORRECTING_TP_OCR]:
        from conversation.enrollment import handle_ocr_correction
        is_tp = state == ConversationState.CORRECTING_TP_OCR
        await handle_ocr_correction(phone, original_text, session, lang, is_tp=is_tp)
        return

    # === ENROLLMENT STATES ===
    if state == ConversationState.ENROLLMENT_METHOD:
        await handle_enrollment_method_selection(phone, text, session, lang)
        return
    if state == ConversationState.ENROLLING_SCAN:
        if text == "3" or text.lower() in ["manuel", "manual"]:
            await handle_enrollment_method_selection(phone, "3", session, lang)
            return
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
    if state == ConversationState.ENROLLING_MANUAL_NAT:
        await handle_manual_nationality(phone, original_text, session, lang, is_tp=False)
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
        if text == "3" or text.lower() in ["manuel", "manual"]:
            await handle_enrollment_method_selection(phone, "3", session, lang, is_tp=True)
            return
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
    if state == ConversationState.ENROLLING_TP_MANUAL_NAT:
        await handle_manual_nationality(phone, original_text, session, lang, is_tp=True)
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
    if state == ConversationState.PAYMENT_FASTTRACK:
        await handle_payment_fasttrack(phone, text, session, lang)
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
    # === SPLIT PAYMENT STATES ===
    if state == ConversationState.SPLIT_PAYER_COUNT:
        await handle_split_payer_count(phone, text, session, lang)
        return
    if state == ConversationState.SPLIT_COLLECTING_NUMBERS:
        await handle_split_collecting_numbers(phone, text, session, lang)
        return
    if state == ConversationState.SPLIT_CONFIRM:
        await handle_split_confirm(phone, text, session, lang)
        return
    if state == ConversationState.SPLIT_AWAITING_PAYMENTS:
        msg = "Paiements en cours... En attente de tous les payeurs." if lang == "fr" else "Payments in progress... Waiting for all payers."
        await send_whatsapp_message(phone, msg)
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
        msg = """Bienvenue sur Travelioo !

Avant de continuer, nous avons besoin de votre accord :

- Utiliser votre nom pour emettre votre billet
- Stocker votre profil pour vos prochaines reservations (supprimable a tout moment)
- Traiter votre paiement de facon securisee

Vos donnees sont chiffrees (AES-256) et vous pouvez demander leur suppression a tout moment.

Politique de confidentialite : /api/legal/privacy
Conditions : /api/legal/terms

*1* J'accepte, continuer
*2* Non merci"""
    else:
        msg = """Welcome to Travelioo!

Before we continue, we need your agreement to:

- Use your name to issue your ticket
- Store your profile for future bookings (deletable anytime)
- Process your payment securely

Your data is encrypted (AES-256) and you can request deletion at any time.

Privacy policy: /api/legal/privacy
Terms: /api/legal/terms

*1* I agree, continue
*2* No thanks"""
    await update_session(phone, {"state": ConversationState.AWAITING_CONSENT, "enrolling_for": "self"})
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
