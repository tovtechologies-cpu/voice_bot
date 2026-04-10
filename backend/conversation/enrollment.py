"""Enrollment conversation handlers."""
import logging
from typing import Dict
from models import ConversationState
from services.session import (
    update_session, save_passenger, get_passenger_by_id,
    get_third_party_passengers, validate_name, validate_passport_number, title_case_name
)
from services.whatsapp import send_whatsapp_message
from services.passport import download_whatsapp_image, extract_passport_data
from config import MAX_THIRD_PARTY_PROFILES
from database import db

logger = logging.getLogger("EnrollmentHandler")


async def handle_consent(phone: str, text: str, session: Dict, lang: str):
    """Handle GDPR consent response."""
    if text in ["1", "oui", "yes", "ok", "accepte", "accept", "j'accepte"]:
        # Consent granted — record and proceed to enrollment
        await update_session(phone, {"_consent_granted": True, "_consent_at": __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()})
        await _show_enrollment_menu(phone, lang, is_tp=False)
    elif text in ["2", "non", "no"]:
        if lang == "fr":
            msg = "Nous respectons votre choix. Sans votre accord, nous ne pouvons pas traiter votre reservation.\n\nEnvoyez un message si vous changez d'avis."
        else:
            msg = "We respect your choice. Without your agreement, we cannot process your booking.\n\nSend a message if you change your mind."
        from services.session import clear_session
        await clear_session(phone)
        await send_whatsapp_message(phone, msg)
    else:
        msg = "Repondez *1* (accepter) ou *2* (refuser)" if lang == "fr" else "Reply *1* (accept) or *2* (decline)"
        await send_whatsapp_message(phone, msg)


async def _show_enrollment_menu(phone: str, lang: str, is_tp: bool = False):
    """Show the enrollment method selection menu."""
    if is_tp:
        if lang == "fr":
            msg = """Comment souhaitez-vous renseigner les informations du passager ?

1 Scanner le passeport (photo)
2 Envoyer une photo du passeport
3 Saisie manuelle"""
        else:
            msg = """How would you like to provide the passenger's information?

1 Scan passport (photo)
2 Send a photo of the passport
3 Manual entry"""
        target_state = ConversationState.ENROLLING_THIRD_PARTY_METHOD
    else:
        if lang == "fr":
            msg = """Comment souhaitez-vous renseigner vos informations ?

1 Scanner mon passeport (photo)
2 Envoyer une photo de mon passeport
3 Saisie manuelle"""
        else:
            msg = """How would you like to provide your information?

1 Scan my passport (photo)
2 Send a photo of my passport
3 Manual entry"""
        target_state = ConversationState.ENROLLMENT_METHOD
    await update_session(phone, {"state": target_state})
    await send_whatsapp_message(phone, msg)


async def handle_enrollment_method_selection(phone: str, text: str, session: Dict, lang: str, is_tp: bool = False):
    if text in ["1", "2"]:
        if lang == "fr":
            msg = """Envoyez une photo de votre passeport.
Assurez-vous que la photo est nette et que les deux lignes du bas sont visibles (zone MRZ)."""
        else:
            msg = """Send a photo of your passport.
Make sure the photo is clear and the two bottom lines are visible (MRZ zone)."""
        scan_state = ConversationState.ENROLLING_TP_SCAN if is_tp else ConversationState.ENROLLING_SCAN
        await update_session(phone, {"state": scan_state})
        await send_whatsapp_message(phone, msg)
    elif text in ["3", "manuel", "manual", "saisie"]:
        if lang == "fr":
            msg = "Quel est votre prenom ?\n(tel qu'il apparait sur votre passeport)"
        else:
            msg = "What is your first name?\n(as it appears on your passport)"
        fn_state = ConversationState.ENROLLING_TP_MANUAL_FN if is_tp else ConversationState.ENROLLING_MANUAL_FN
        await update_session(phone, {"state": fn_state, "enrollment_data": {}})
        await send_whatsapp_message(phone, msg)
    else:
        msg = "Repondez 1, 2 ou 3" if lang == "fr" else "Reply 1, 2, or 3"
        await send_whatsapp_message(phone, msg)


async def handle_manual_first_name(phone: str, text: str, session: Dict, lang: str, is_tp: bool):
    name = text.strip()
    if not validate_name(name):
        msg = "Nom invalide. Utilisez uniquement des lettres, espaces ou tirets. (minimum 2 caracteres)" if lang == "fr" else "Invalid name. Use only letters, spaces, or hyphens. (minimum 2 characters)"
        await send_whatsapp_message(phone, msg)
        return
    enrollment = session.get("enrollment_data", {})
    enrollment["firstName"] = title_case_name(name)
    ln_state = ConversationState.ENROLLING_TP_MANUAL_LN if is_tp else ConversationState.ENROLLING_MANUAL_LN
    await update_session(phone, {"state": ln_state, "enrollment_data": enrollment})
    msg = "Quel est votre nom de famille ?" if lang == "fr" else "What is your last name?"
    await send_whatsapp_message(phone, msg)


async def handle_manual_last_name(phone: str, text: str, session: Dict, lang: str, is_tp: bool):
    name = text.strip()
    if not validate_name(name):
        msg = "Nom invalide. Utilisez uniquement des lettres, espaces ou tirets." if lang == "fr" else "Invalid name. Use only letters, spaces, or hyphens."
        await send_whatsapp_message(phone, msg)
        return
    enrollment = session.get("enrollment_data", {})
    enrollment["lastName"] = title_case_name(name)
    pp_state = ConversationState.ENROLLING_TP_MANUAL_PP if is_tp else ConversationState.ENROLLING_MANUAL_PP
    await update_session(phone, {"state": pp_state, "enrollment_data": enrollment})
    if lang == "fr":
        msg = "Quel est votre numero de passeport ?\n(facultatif -- tapez 'passer' pour ignorer)"
    else:
        msg = "What is your passport number?\n(optional -- type 'skip' to skip)"
    await send_whatsapp_message(phone, msg)


async def handle_manual_passport(phone: str, text: str, session: Dict, lang: str, is_tp: bool):
    enrollment = session.get("enrollment_data", {})
    txt = text.strip().lower()
    if txt in ["passer", "skip", "ignorer", "-", "non", "no"]:
        enrollment["passportNumber"] = None
    else:
        clean = text.strip().upper()
        if not validate_passport_number(clean):
            msg = "Numero invalide (6-9 caracteres alphanumeriques). Tapez 'passer' pour ignorer." if lang == "fr" else "Invalid number (6-9 alphanumeric characters). Type 'skip' to skip."
            await send_whatsapp_message(phone, msg)
            return
        enrollment["passportNumber"] = clean
    confirm_state = ConversationState.CONFIRMING_TP_PROFILE if is_tp else ConversationState.CONFIRMING_PROFILE
    await update_session(phone, {"state": confirm_state, "enrollment_data": enrollment})
    await send_profile_confirmation(phone, enrollment, lang)


async def send_profile_confirmation(phone: str, data: Dict, lang: str):
    fn = data.get("firstName", "")
    ln = data.get("lastName", "")
    pp = data.get("passportNumber") or ("Non renseigne" if lang == "fr" else "Not provided")
    nat = data.get("nationality") or ("Non renseignee" if lang == "fr" else "Not provided")
    if lang == "fr":
        msg = f"""Voici les informations que j'ai relevees :

Nom : {ln} {fn}
Passeport : {pp}
Nationalite : {nat}

Ces informations sont-elles correctes ?

1 Oui, continuer
2 Non, recommencer"""
    else:
        msg = f"""Here is the information I collected:

Name: {ln} {fn}
Passport: {pp}
Nationality: {nat}

Is this information correct?

1 Yes, continue
2 No, start over"""
    await send_whatsapp_message(phone, msg)


async def handle_profile_confirmation(phone: str, text: str, session: Dict, lang: str, is_tp: bool):
    enrollment = session.get("enrollment_data", {})
    if text in ["1", "oui", "yes", "ok", "correct"]:
        if is_tp:
            await update_session(phone, {"state": ConversationState.SAVE_TP_PROMPT})
            msg = "Souhaitez-vous sauvegarder ce profil pour vos prochaines reservations ?\n1 Oui  2 Non" if lang == "fr" else "Would you like to save this profile for future bookings?\n1 Yes  2 No"
            await send_whatsapp_message(phone, msg)
        else:
            passenger_id = await save_passenger({
                "whatsapp_phone": phone, "firstName": enrollment.get("firstName", ""),
                "lastName": enrollment.get("lastName", ""), "passportNumber": enrollment.get("passportNumber"),
                "nationality": enrollment.get("nationality"), "dateOfBirth": enrollment.get("dateOfBirth"),
                "expiryDate": enrollment.get("expiryDate"), "created_by_phone": phone
            })
            await update_session(phone, {"passenger_id": passenger_id, "booking_passenger_id": passenger_id, "enrollment_data": {}})
            msg = "Profil enregistre. Vous n'aurez plus a ressaisir ces informations la prochaine fois." if lang == "fr" else "Profile saved. You won't need to enter this information again."
            await send_whatsapp_message(phone, msg)
            passenger = await get_passenger_by_id(passenger_id)
            from conversation.handler import handle_returning_user
            await handle_returning_user(phone, passenger, lang)
    elif text in ["2", "non", "no"]:
        if is_tp:
            await update_session(phone, {"state": ConversationState.ENROLLING_THIRD_PARTY_METHOD, "enrollment_data": {}})
            if lang == "fr":
                msg = """Comment souhaitez-vous renseigner les informations ?

1 Scanner le passeport (photo)
2 Envoyer une photo du passeport
3 Saisie manuelle"""
            else:
                msg = """How would you like to provide the information?

1 Scan passport (photo)
2 Send a photo of the passport
3 Manual entry"""
            await update_session(phone, {"state": ConversationState.ENROLLING_THIRD_PARTY_METHOD})
            await send_whatsapp_message(phone, msg)
        else:
            await update_session(phone, {"state": ConversationState.ENROLLMENT_METHOD, "enrollment_data": {}})
            from conversation.handler import handle_new_user
            await handle_new_user(phone, lang)
    else:
        msg = "Repondez 1 (oui) ou 2 (non)" if lang == "fr" else "Reply 1 (yes) or 2 (no)"
        await send_whatsapp_message(phone, msg)


async def handle_passport_scan(phone: str, image_id: str, state: str, session: Dict, lang: str):
    is_tp = state in [ConversationState.ENROLLING_TP_SCAN]
    image_bytes = await download_whatsapp_image(image_id)
    if not image_bytes:
        msg = "Impossible de telecharger l'image. Essayez la saisie manuelle (tapez 3)." if lang == "fr" else "Couldn't download image. Try manual entry (type 3)."
        method_state = ConversationState.ENROLLING_THIRD_PARTY_METHOD if is_tp else ConversationState.ENROLLMENT_METHOD
        await update_session(phone, {"state": method_state})
        await send_whatsapp_message(phone, msg)
        return
    msg = "Analyse du passeport en cours..." if lang == "fr" else "Analyzing passport..."
    await send_whatsapp_message(phone, msg)
    data = await extract_passport_data(image_bytes)
    if not data.get("success"):
        msg = "Je n'ai pas pu lire votre passeport.\nReessayez avec une photo plus nette ou choisissez la saisie manuelle (option 3)." if lang == "fr" else "I couldn't read your passport.\nTry again with a clearer photo or choose manual entry (option 3)."
        method_state = ConversationState.ENROLLING_THIRD_PARTY_METHOD if is_tp else ConversationState.ENROLLMENT_METHOD
        await update_session(phone, {"state": method_state})
        await send_whatsapp_message(phone, msg)
        return
    enrollment = {k: data.get(k) for k in ["firstName", "lastName", "passportNumber", "nationality", "dateOfBirth", "expiryDate"]}
    if data.get("partial"):
        if not enrollment.get("firstName"):
            fn_state = ConversationState.ENROLLING_TP_MANUAL_FN if is_tp else ConversationState.ENROLLING_MANUAL_FN
            await update_session(phone, {"state": fn_state, "enrollment_data": enrollment})
            msg = "Nom partiellement detecte. Quel est le prenom ?" if lang == "fr" else "Name partially detected. What is the first name?"
            await send_whatsapp_message(phone, msg)
            return
        if not enrollment.get("lastName"):
            ln_state = ConversationState.ENROLLING_TP_MANUAL_LN if is_tp else ConversationState.ENROLLING_MANUAL_LN
            await update_session(phone, {"state": ln_state, "enrollment_data": enrollment})
            msg = "Nom de famille non detecte. Quel est le nom de famille ?" if lang == "fr" else "Last name not detected. What is the last name?"
            await send_whatsapp_message(phone, msg)
            return
    confirm_state = ConversationState.CONFIRMING_TP_PROFILE if is_tp else ConversationState.CONFIRMING_PROFILE
    await update_session(phone, {"state": confirm_state, "enrollment_data": enrollment})
    await send_profile_confirmation(phone, enrollment, lang)


async def handle_travel_purpose(phone: str, text: str, session: Dict, lang: str):
    if text in ["1", "moi", "me", "pour moi", "for me"]:
        passenger_id = session.get("passenger_id")
        await update_session(phone, {"booking_passenger_id": passenger_id, "state": ConversationState.ASKING_PASSENGER_COUNT})
        await handle_passenger_count_prompt(phone, lang)
    elif text in ["2", "tiers", "autre", "other", "someone", "third"]:
        await update_session(phone, {"enrolling_for": "third_party"})
        third_parties = await get_third_party_passengers(phone)
        if third_parties:
            if lang == "fr":
                msg = "Pour qui reservez-vous ce vol ?\n\n"
                for i, tp in enumerate(third_parties, 1):
                    msg += f"{i} {tp['firstName']} {tp['lastName']}\n"
                msg += f"{len(third_parties) + 1} Nouvelle personne"
            else:
                msg = "Who are you booking for?\n\n"
                for i, tp in enumerate(third_parties, 1):
                    msg += f"{i} {tp['firstName']} {tp['lastName']}\n"
                msg += f"{len(third_parties) + 1} New person"
            await update_session(phone, {"state": ConversationState.SELECTING_THIRD_PARTY, "_tp_list": [tp["id"] for tp in third_parties]})
            await send_whatsapp_message(phone, msg)
        else:
            if lang == "fr":
                msg = """Pour qui reservez-vous ce vol ?

1 Quelqu'un deja enregistre
2 Nouvelle personne"""
            else:
                msg = """Who are you booking for?

1 Someone already registered
2 New person"""
            await update_session(phone, {"state": ConversationState.SELECTING_THIRD_PARTY, "_tp_list": []})
            await send_whatsapp_message(phone, msg)
    else:
        msg = "Repondez 1 ou 2" if lang == "fr" else "Reply 1 or 2"
        await send_whatsapp_message(phone, msg)


async def handle_third_party_selection(phone: str, text: str, session: Dict, lang: str):
    tp_list = session.get("_tp_list", [])
    try:
        choice = int(text)
    except (ValueError, TypeError):
        choice = -1
    new_person_idx = len(tp_list) + 1 if tp_list else 2
    if text in ["2", "nouvelle", "new"] and not tp_list:
        choice = new_person_idx
    if 1 <= choice <= len(tp_list):
        tp_id = tp_list[choice - 1]
        tp = await get_passenger_by_id(tp_id)
        if tp:
            await update_session(phone, {"booking_passenger_id": tp_id, "state": ConversationState.ASKING_PASSENGER_COUNT})
            msg = f"Reservation pour {tp.get('firstName', '')} {tp.get('lastName', '')}" if lang == "fr" else f"Booking for {tp.get('firstName', '')} {tp.get('lastName', '')}"
            await send_whatsapp_message(phone, msg)
            await handle_passenger_count_prompt(phone, lang)
            return
    if choice == new_person_idx or text in ["nouvelle", "new"]:
        if lang == "fr":
            msg = """Comment souhaitez-vous renseigner les informations du passager ?

1 Scanner le passeport (photo)
2 Envoyer une photo du passeport
3 Saisie manuelle"""
        else:
            msg = """How would you like to provide the passenger's information?

1 Scan passport (photo)
2 Send a photo of the passport
3 Manual entry"""
        await update_session(phone, {"state": ConversationState.ENROLLING_THIRD_PARTY_METHOD, "enrollment_data": {}})
        await send_whatsapp_message(phone, msg)
        return
    if text == "1" and not tp_list:
        msg = "Aucun passager enregistre. Choisissez 2 pour ajouter une nouvelle personne." if lang == "fr" else "No registered passengers. Choose 2 to add a new person."
        await send_whatsapp_message(phone, msg)
        return
    msg = f"Repondez un numero de 1 a {new_person_idx}" if lang == "fr" else f"Reply a number from 1 to {new_person_idx}"
    await send_whatsapp_message(phone, msg)


async def handle_save_tp_prompt(phone: str, text: str, session: Dict, lang: str):
    enrollment = session.get("enrollment_data", {})
    if text in ["1", "oui", "yes"]:
        existing = await get_third_party_passengers(phone)
        if len(existing) >= MAX_THIRD_PARTY_PROFILES:
            oldest = existing[-1]
            await db.passengers.delete_one({"id": oldest["id"]})
        passenger_id = await save_passenger({
            "whatsapp_phone": None, "firstName": enrollment.get("firstName", ""),
            "lastName": enrollment.get("lastName", ""), "passportNumber": enrollment.get("passportNumber"),
            "nationality": enrollment.get("nationality"), "dateOfBirth": enrollment.get("dateOfBirth"),
            "expiryDate": enrollment.get("expiryDate"), "created_by_phone": phone
        })
        msg = "Profil sauvegarde." if lang == "fr" else "Profile saved."
        await send_whatsapp_message(phone, msg)
    else:
        passenger_id = await save_passenger({
            "whatsapp_phone": None, "firstName": enrollment.get("firstName", ""),
            "lastName": enrollment.get("lastName", ""), "passportNumber": enrollment.get("passportNumber"),
            "nationality": enrollment.get("nationality"), "created_by_phone": f"_temp_{phone}"
        })
    await update_session(phone, {"booking_passenger_id": passenger_id, "enrollment_data": {}, "state": ConversationState.ASKING_PASSENGER_COUNT})
    await handle_passenger_count_prompt(phone, lang)


async def handle_passenger_count_prompt(phone: str, lang: str):
    msg = "Combien de passagers voyagent ?\n(repondez 1 pour continuer -- multi-passagers disponible prochainement)" if lang == "fr" else "How many passengers are traveling?\n(reply 1 to continue -- multi-passenger coming soon)"
    await update_session(phone, {"state": ConversationState.ASKING_PASSENGER_COUNT})
    await send_whatsapp_message(phone, msg)


async def handle_passenger_count(phone: str, text: str, session: Dict, lang: str):
    try:
        count = int(text)
    except (ValueError, TypeError):
        count = 1
    if count > 1:
        msg = "La reservation multi-passagers arrive bientot.\nPour l'instant, je peux traiter 1 passager a la fois." if lang == "fr" else "Multi-passenger booking coming soon.\nFor now, I can process 1 passenger at a time."
        await send_whatsapp_message(phone, msg)
    await update_session(phone, {"state": ConversationState.AWAITING_DESTINATION, "intent": {}})
    if lang == "fr":
        msg = "Ou souhaitez-vous aller ?\n_\"Je veux un vol pour Paris vendredi prochain\"_"
    else:
        msg = "Where would you like to go?\n_\"I need a flight to Paris next Friday\"_"
    await send_whatsapp_message(phone, msg)
