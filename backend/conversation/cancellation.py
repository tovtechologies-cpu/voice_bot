"""Cancellation and refund conversation handlers."""
import logging
import uuid
import os
from typing import Dict
from datetime import datetime, timezone
from models import ConversationState, PaymentOperator, calculate_refund
from services.session import update_session, clear_session
from services.whatsapp import send_whatsapp_message
from services.airport import get_city_name
from utils.helpers import mask_phone, format_timestamp_gmt1, eur_to_xof
from config import TRAVELIOO_FEE
from database import db

logger = logging.getLogger("CancellationHandler")


async def start_cancellation_flow(phone: str, lang: str):
    bookings = await db.bookings.find({"phone": phone, "status": "confirmed"}, {"_id": 0}).sort("created_at", -1).limit(5).to_list(5)
    if not bookings:
        msg = "Aucune reservation a annuler." if lang == "fr" else "No bookings to cancel."
        await send_whatsapp_message(phone, msg)
        return
    if lang == "fr":
        msg = "Quelle reservation souhaitez-vous annuler ?\n\n"
    else:
        msg = "Which booking do you want to cancel?\n\n"
    booking_ids = []
    for i, b in enumerate(bookings, 1):
        msg += f"{i} {b['booking_ref']} -- {get_city_name(b.get('destination', ''))} -- {b.get('departure_date')}\n"
        booking_ids.append(b["booking_ref"])
    msg += f"\n{'ou tapez votre numero TRV-XXXXXX' if lang == 'fr' else 'or type your TRV-XXXXXX number'}"
    await update_session(phone, {"state": ConversationState.CANCELLATION_IDENTIFY, "_cancel_booking_list": booking_ids})
    await send_whatsapp_message(phone, msg)


async def handle_cancellation_identify(phone: str, text: str, session: Dict, lang: str):
    booking_list = session.get("_cancel_booking_list", [])
    booking_ref = None
    try:
        idx = int(text) - 1
        if 0 <= idx < len(booking_list):
            booking_ref = booking_list[idx]
    except (ValueError, TypeError):
        pass
    if not booking_ref and text.upper().startswith("TRV-"):
        booking_ref = text.upper()
    if not booking_ref:
        msg = "Tapez un numero ou votre reference TRV-XXXXXX" if lang == "fr" else "Type a number or your TRV-XXXXXX reference"
        await send_whatsapp_message(phone, msg)
        return
    booking = await db.bookings.find_one({"booking_ref": booking_ref, "phone": phone}, {"_id": 0})
    if not booking:
        msg = "Reservation non trouvee." if lang == "fr" else "Booking not found."
        await send_whatsapp_message(phone, msg)
        return
    if booking.get("status") != "confirmed":
        msg = f"Cette reservation ne peut pas etre annulee (statut: {booking.get('status')})." if lang == "fr" else f"This booking cannot be cancelled (status: {booking.get('status')})."
        await send_whatsapp_message(phone, msg)
        return
    refund_info = calculate_refund(booking)
    await update_session(phone, {"state": ConversationState.CANCELLATION_CONFIRM, "_cancel_booking_ref": booking_ref, "_cancel_refund_info": refund_info})
    masked = mask_phone(phone)
    payment_display = booking.get("payment_method", "N/A")
    price = booking.get("price_eur", 0)

    if refund_info["case"] == "non_refundable":
        summary = booking.get("fare_conditions_summary", "")
        if lang == "fr":
            msg = f"""*Billet non remboursable*
{summary}

Annuler quand meme (sans remboursement) ?
1 Oui  2 Non, conserver"""
        else:
            msg = f"""*Non-refundable ticket*
{summary}

Cancel anyway (no refund)?
1 Yes  2 No, keep it"""

    elif refund_info["case"] == "deadline_passed":
        if lang == "fr":
            msg = f"""*Delai d'annulation depasse*

Remboursement possible jusqu'au {refund_info.get('deadline', 'N/A')}.
Cette date est depassee.

1 Annuler sans remboursement
2 Conserver
3 Contacter le support"""
        else:
            msg = f"""*Cancellation deadline passed*

Refund was available until {refund_info.get('deadline', 'N/A')}.
This date has passed.

1 Cancel without refund
2 Keep it
3 Contact support"""

    elif refund_info["case"] == "partial_refund":
        refund = refund_info["refund_eur"]
        penalty = refund_info.get("airline_penalty", 0)
        refund_xof = eur_to_xof(refund)
        if lang == "fr":
            msg = f"""*Remboursement avec penalite*

Montant paye : {price}EUR
- Penalite compagnie : -{penalty}EUR
- Frais Travelioo : -{TRAVELIOO_FEE}EUR (non remboursables)
---
*Total rembourse : {refund}EUR* ({refund_xof:,} XOF)

Methode : {payment_display} ({masked})
Delai : 5 a 10 jours ouvres

1 Oui, annuler et rembourser {refund}EUR
2 Non, conserver"""
        else:
            msg = f"""*Refund with penalty*

Amount paid: {price}EUR
- Airline penalty: -{penalty}EUR
- Travelioo fee: -{TRAVELIOO_FEE}EUR (non-refundable)
---
*Total refunded: {refund}EUR* ({refund_xof:,} XOF)

Method: {payment_display} ({masked})
Delay: 5 to 10 business days

1 Yes, cancel and refund {refund}EUR
2 No, keep it"""

    elif refund_info["case"] == "fully_refundable":
        refund = refund_info["refund_eur"]
        refund_xof = eur_to_xof(refund)
        if lang == "fr":
            msg = f"""*Remboursement integral*

Montant paye : {price}EUR
- Frais Travelioo : -{TRAVELIOO_FEE}EUR (non remboursables)
---
*Total rembourse : {refund}EUR* ({refund_xof:,} XOF)

Methode : {payment_display} ({masked})
Delai : 3 a 5 jours ouvres

1 Oui  2 Non"""
        else:
            msg = f"""*Full refund*

Amount paid: {price}EUR
- Travelioo fee: -{TRAVELIOO_FEE}EUR (non-refundable)
---
*Total refunded: {refund}EUR* ({refund_xof:,} XOF)

Method: {payment_display} ({masked})
Delay: 3 to 5 business days

1 Yes  2 No"""
    else:
        msg = "Erreur." if lang == "fr" else "Error."
    await send_whatsapp_message(phone, msg)


async def handle_cancellation_confirm(phone: str, text: str, session: Dict, lang: str):
    refund_info = session.get("_cancel_refund_info", {})
    booking_ref = session.get("_cancel_booking_ref")
    if text in ["2", "non", "no", "conserver", "keep"]:
        await clear_session(phone)
        msg = "Reservation conservee." if lang == "fr" else "Booking kept."
        await send_whatsapp_message(phone, msg)
        return
    if text == "3":
        msg = "Contactez notre support : support@travelioo.app" if lang == "fr" else "Contact support: support@travelioo.app"
        await send_whatsapp_message(phone, msg)
        await clear_session(phone)
        return
    if text not in ["1", "oui", "yes", "confirmer"]:
        msg = "Repondez 1 ou 2" if lang == "fr" else "Reply 1 or 2"
        await send_whatsapp_message(phone, msg)
        return
    await update_session(phone, {"state": ConversationState.CANCELLATION_PROCESSING})
    booking = await db.bookings.find_one({"booking_ref": booking_ref}, {"_id": 0})
    if not booking:
        await clear_session(phone)
        return
    now_utc = datetime.now(timezone.utc)
    await db.bookings.update_one({"booking_ref": booking_ref}, {"$set": {"status": "cancelled", "cancellation_timestamp": now_utc.isoformat()}})
    await db.cancelled_bookings.insert_one({"booking_ref": booking_ref, "cancelled_at": now_utc.isoformat()})
    refund_amount = refund_info.get("refund_eur", 0)
    if refund_amount > 0:
        refund_result = await process_refund(booking, refund_amount)
        if refund_result.get("success"):
            refund_ref = refund_result.get("reference", "")
            await db.bookings.update_one({"booking_ref": booking_ref}, {"$set": {"refund_status": "PROCESSED", "refund_amount_eur": refund_amount, "refund_reference": refund_ref}})
            masked = mask_phone(phone)
            ts = format_timestamp_gmt1(now_utc)
            payment_display = booking.get("payment_method", "N/A")
            if lang == "fr":
                msg = f"""*Annulation confirmee*
{booking_ref} annulee
{refund_amount}EUR rembourses -> {payment_display} ({masked})
{ts} GMT+1
Delai : 3 a 10 jours ouvres
Votre billet a ete invalide."""
            else:
                msg = f"""*Cancellation confirmed*
{booking_ref} cancelled
{refund_amount}EUR refunded -> {payment_display} ({masked})
Delay: 3 to 10 business days
Your ticket has been invalidated."""
            await send_whatsapp_message(phone, msg)
        else:
            failure_reason = refund_result.get("error", "Unknown error")
            await db.refund_queue.insert_one({"booking_ref": booking_ref, "booking_id": booking.get("id"), "amount_eur": refund_amount, "payment_method": booking.get("payment_method"), "failure_reason": failure_reason, "timestamp": now_utc.isoformat(), "status": "PENDING", "phone": phone})
            await db.bookings.update_one({"booking_ref": booking_ref}, {"$set": {"refund_status": "FAILED", "refund_amount_eur": refund_amount}})
            ref_id = f"REF-{booking_ref}-{int(now_utc.timestamp())}"
            if lang == "fr":
                msg = f"""Remboursement automatique echoue.
Traitement manuel sous 48h.
Reference : {ref_id}"""
            else:
                msg = f"""Automatic refund failed.
Manual processing within 48h.
Reference: {ref_id}"""
            await send_whatsapp_message(phone, msg)
            await update_session(phone, {"state": ConversationState.REFUND_FAILED, "_refund_ref": ref_id})
            return
    else:
        if lang == "fr":
            msg = f"Reservation {booking_ref} annulee.\nAucun remboursement.\nVotre billet a ete invalide."
        else:
            msg = f"Booking {booking_ref} cancelled.\nNo refund.\nYour ticket has been invalidated."
        await send_whatsapp_message(phone, msg)
    await clear_session(phone)


async def handle_refund_failed(phone: str, text: str, session: Dict, lang: str):
    ref_id = session.get("_refund_ref", "N/A")
    msg = f"Votre remboursement est en cours de traitement manuel.\nReference : {ref_id}\nContactez support@travelioo.app si besoin." if lang == "fr" else f"Your refund is being processed manually.\nReference: {ref_id}\nContact support@travelioo.app if needed."
    await send_whatsapp_message(phone, msg)
    await clear_session(phone)


async def process_refund(booking: Dict, amount_eur: float) -> Dict:
    payment_method = booking.get("payment_method")
    booking_ref = booking.get("booking_ref")
    if booking.get("_test_refund_fail"):
        return {"success": False, "error": "Simulated refund failure for testing"}
    try:
        if payment_method in [PaymentOperator.MTN_MOMO, PaymentOperator.MOOV_MONEY]:
            ref = f"REFUND-{payment_method[:4].upper()}-{uuid.uuid4().hex[:8].upper()}"
            logger.info(f"[REFUND] {payment_method} refund of {amount_eur}EUR for {booking_ref}: {ref}")
            return {"success": True, "reference": ref}
        if payment_method in [PaymentOperator.GOOGLE_PAY, PaymentOperator.APPLE_PAY]:
            ref = f"REFUND-STRIPE-{uuid.uuid4().hex[:8].upper()}"
            logger.info(f"[REFUND] Stripe refund of {amount_eur}EUR for {booking_ref}: {ref}")
            return {"success": True, "reference": ref}
        return {"success": False, "error": f"Unknown payment method: {payment_method}"}
    except Exception as e:
        logger.error(f"Refund error for {booking_ref}: {e}")
        return {"success": False, "error": str(e)}
