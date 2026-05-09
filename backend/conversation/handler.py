"""Main conversation handler - message dispatcher."""
import logging
from typing import Dict
from database import db
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
    handle_awaiting_origin, handle_awaiting_destination, handle_awaiting_date,
    handle_awaiting_return_flight, handle_flight_selection,
    handle_payment_method, handle_pre_debit_confirm, handle_retry,
    handle_payment_fasttrack, handle_asking_trip_type, handle_awaiting_return_date,
    handle_country_switch
)
from conversation.split_payment import (
    handle_split_payer_count, handle_split_collecting_numbers,
    handle_split_confirm
)
from conversation.cancellation import start_cancellation_flow, handle_cancellation_identify, handle_cancellation_confirm, handle_refund_failed
from conversation.modification import start_modification_flow, handle_modification_requested, handle_modification_confirm

logger = logging.getLogger("ConversationHandler")


async def handle_message(phone: str, message_text: str, audio_id: str = None, image_id: str = None):
    """Public entry point — adds crash protection + voice TTS post-hook around the dispatcher."""
    user_sent_voice = bool(audio_id)
    channel_label = "AUDIO-TG" if (audio_id or "").startswith("tg:") else "AUDIO-WA"
    if user_sent_voice:
        logger.info(f"[{channel_label}] Incoming voice for {phone}: id={audio_id[:24]}...")

    try:
        await _handle_message_inner(phone, message_text, audio_id=audio_id, image_id=image_id)
    except Exception as e:
        import traceback
        logger.error(f"[HANDLER] Crashed: {type(e).__name__}: {e}")
        logger.error(traceback.format_exc())
        # Send fallback so user is never left in silence
        try:
            await send_whatsapp_message(
                phone,
                "Une erreur est survenue.\nTapez /start pour recommencer."
            )
        except Exception as fallback_err:
            logger.error(f"[HANDLER] Fallback send also failed: {fallback_err}")
        return

    # Send TTS voice response if user originally sent voice and no voice was sent yet
    if user_sent_voice:
        session = await get_or_create_session(phone)
        if not session.get("_voice_response_sent", False):
            try:
                from services.whatsapp import get_last_response_for
                last_response = get_last_response_for(phone)
                if last_response:
                    await send_voice_if_needed(phone, last_response, force=True)
            except Exception as e:
                logger.error(f"[TTS] Voice response failed: {type(e).__name__}: {e}")
        else:
            # Reset the flag for the next turn
            await update_session(phone, {"_voice_response_sent": False})


async def _handle_message_inner(phone: str, message_text: str, audio_id: str = None, image_id: str = None):
    """Main entry point for all WhatsApp/Telegram/webchat messages."""
    # Rate limiting
    allowed = await check_rate_limit(phone, "message")
    if not allowed:
        await send_whatsapp_message(phone, "Trop de messages. Veuillez patienter.")
        return

    session = await get_or_create_session(phone)

    # Track if input was voice
    if audio_id:
        await update_session(phone, {"_last_input_was_voice": True})

    if session.pop("_expired", False):
        lang = session.get("language", "fr")
        msg = "Session expiree. Envoyez un message pour recommencer." if lang == "fr" else "Session expired. Send a message to start again."
        await send_whatsapp_message(phone, msg)

    # Voice -> transcription
    if audio_id and not message_text:
        try:
            transcribed = await transcribe_audio(audio_id)
        except Exception as e:
            logger.error(f"[AUDIO] Transcription crashed: {type(e).__name__}: {e}")
            transcribed = None

        if transcribed:
            message_text = transcribed
            logger.info(f"[AUDIO] Transcribed for {phone}: '{transcribed[:80]}'")
        else:
            logger.warning(f"[AUDIO] Empty transcription for {phone}")
            msg = (
                "Je n'ai pas pu comprendre votre audio.\n\n"
                "Tapez votre demande par ecrit :\n"
                "_Exemple : Paris vendredi retour lundi_"
            )
            await send_whatsapp_message(phone, msg)
            return

    # Sanitize input
    message_text = sanitize_input(message_text) if message_text else ""
    text = message_text.strip().lower()
    original_text = message_text.strip()
    state = session.get("state", ConversationState.IDLE)

    # ── LANGUAGE DETECTION ──
    # Priority: 1) saved session lang, 2) text detection, 3) phone country code
    from services.i18n import detect_lang_from_phone, SUPPORTED_LANGS, t
    detected_lang = session.get("language")

    if not detected_lang or state in [ConversationState.IDLE, ConversationState.NEW]:
        if original_text:
            text_detected = detect_language(original_text)
            # Map African langs → fr for response, keep for translation
            if text_detected in SUPPORTED_LANGS:
                detected_lang = text_detected
            elif text_detected in ["wo", "fon", "yo", "ha", "sw"]:
                detected_lang = "fr"  # Respond in French for African langs
            else:
                # Fallback to phone country code
                detected_lang = detect_lang_from_phone(phone)
        else:
            detected_lang = detect_lang_from_phone(phone)
        await update_session(phone, {"language": detected_lang, "_source_lang": detect_language(original_text) if original_text else detected_lang})
        from services.shadow_profile import update_shadow_profile
        await update_shadow_profile(phone, {"language_pref": detected_lang})

    # ── COUNTRY DETECTION (set once per session) ──
    # Used by the country-aware payment flow. Source priority:
    #   1) Already saved on session
    #   2) Phone dial code (WhatsApp / Telegram)
    #   3) BJ default (also for webchat — frontend may send country override)
    if not session.get("_country_code"):
        from services.country import country_from_phone
        cc = country_from_phone(phone)
        await update_session(phone, {"_country_code": cc})
        session["_country_code"] = cc

    # ── LANGUAGE CHANGE COMMAND ──
    if text in ["langue", "language", "idioma", "لغة", "cambiar idioma", "change language", "/langue", "/language"]:
        msg = t("change_language", detected_lang)
        await update_session(phone, {"state": "changing_language"})
        await send_whatsapp_message(phone, msg)
        return

    if state == "changing_language":
        lang_map = {"1": "fr", "2": "en", "3": "es", "4": "ar", "5": "pt"}
        if text in lang_map:
            new_lang = lang_map[text]
            await update_session(phone, {"language": new_lang, "state": ConversationState.IDLE})
            from services.shadow_profile import update_shadow_profile as _up
            await _up(phone, {"language_pref": new_lang})
            msg = t("language_changed", new_lang)
            await send_whatsapp_message(phone, msg)
            return
        msg = t("change_language", detected_lang)
        await send_whatsapp_message(phone, msg)
        return

    # Translation pipeline for African languages
    from services.translation import AFRICAN_LANGUAGES, translate_to_french, LANGUAGE_NAMES
    source_lang = session.get("_source_lang") or detected_lang or "fr"

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
    if state == ConversationState.AWAITING_ORIGIN:
        await handle_awaiting_origin(phone, original_text, session, lang)
        return
    if state == ConversationState.AWAITING_DESTINATION:
        await handle_awaiting_destination(phone, original_text, session, lang)
        return
    if state == ConversationState.AWAITING_DATE:
        await handle_awaiting_date(phone, original_text, text, session, lang)
        return
    if state == ConversationState.ASKING_TRIP_TYPE:
        await handle_asking_trip_type(phone, text, session, lang)
        return
    if state == ConversationState.AWAITING_RETURN_DATE:
        await handle_awaiting_return_date(phone, original_text, text, session, lang)
        return
    if state == ConversationState.AWAITING_RETURN_FLIGHT:
        await handle_awaiting_return_flight(phone, text, session, lang)
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
    if state == ConversationState.AWAITING_COUNTRY_SWITCH:
        await handle_country_switch(phone, text, session, lang)
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

    # Fallback — NEVER stay silent
    from services.i18n import t as _t
    msg = _t("fallback_error", lang)
    await send_whatsapp_message(phone, msg)


async def start_conversation(phone: str, lang: str):
    passenger = await get_passenger_by_phone(phone)
    if passenger:
        await update_session(phone, {"passenger_id": passenger["id"]})
        await handle_returning_user(phone, passenger, lang)
    else:
        await handle_new_user(phone, lang)


async def handle_new_user(phone: str, lang: str):
    from services.i18n import t
    msg = t("welcome_consent", lang)
    await update_session(phone, {"state": ConversationState.AWAITING_CONSENT, "enrolling_for": "self"})
    await send_whatsapp_message(phone, msg)
    await send_voice_if_needed(phone, "Bienvenue sur Travelioo ! Dites-moi votre destination et vos dates de voyage.", force=True)


async def handle_returning_user(phone: str, passenger: Dict, lang: str):
    from services.i18n import t
    fn = passenger.get("firstName", "")
    ln = passenger.get("lastName", "")
    msg = t("returning_user", lang, name=fn, fullname=f"{fn} {ln}")
    await update_session(phone, {"state": ConversationState.ASKING_TRAVEL_PURPOSE})
    await send_whatsapp_message(phone, msg)


async def send_voice_if_needed(phone: str, text: str, force: bool = False):
    """Send TTS voice response after text if user sent voice or if force=True."""
    from services.channel import get_channel
    channel = get_channel(phone)
    if channel == "webchat":
        return  # Webchat handles audio via base64 in response

    session = await db.sessions.find_one({"phone": phone}, {"_id": 0})
    was_voice = session.get("_last_input_was_voice", False) if session else False
    if not was_voice and not force:
        return

    try:
        from services.tts_service import tts_service
        audio_bytes = await tts_service.synthesize(text)
        if not audio_bytes:
            return

        if channel == "whatsapp":
            from services.whatsapp import send_whatsapp_voice
            await send_whatsapp_voice(phone, audio_bytes)
        elif channel == "telegram":
            from services.telegram import send_telegram_voice_bytes
            await send_telegram_voice_bytes(phone, audio_bytes)

        # Set flag so we don't send a redundant one in the post-hook
        await update_session(phone, {"_last_input_was_voice": False, "_voice_response_sent": True})
    except Exception as e:
        logger.error(f"[Voice] TTS send error: {e}")
