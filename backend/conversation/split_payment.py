"""Multi-number split payment handler — Phase B."""
import logging
import uuid
import asyncio
from typing import Dict, List
from datetime import datetime, timezone
from models import ConversationState
from services.session import update_session, clear_session
from services.whatsapp import send_whatsapp_message, send_whatsapp_document
from services.flight import eur_to_xof
from services.ticket import generate_ticket_pdf
from services.shadow_profile import add_to_travel_history, add_payment_method, add_trusted_payer
from utils.helpers import generate_booking_ref, mask_phone, format_timestamp_gmt1
from config import (
    APP_BASE_URL, SPLIT_PAYMENT_RECONCILIATION_FEE_EUR,
    SPLIT_PAYMENT_RECONCILIATION_FEE_XOF, PRICE_LOCK_MINUTES
)
from database import db

logger = logging.getLogger("SplitPayment")


def _normalize_split_phone(raw: str) -> str:
    """Normalize a phone number for split payment."""
    phone = raw.strip().replace(" ", "").replace("-", "")
    if not phone.startswith("+"):
        if phone.startswith("00"):
            phone = "+" + phone[2:]
        elif len(phone) == 8:
            phone = "+229" + phone
        elif len(phone) >= 10 and not phone.startswith("+"):
            phone = "+" + phone
    return phone


async def handle_split_payer_count(phone: str, text: str, session: Dict, lang: str):
    """Ask how many payers for the split."""
    try:
        count = int(text.strip())
    except (ValueError, TypeError):
        msg = "Combien de numeros participent au paiement ? (2-5)" if lang == "fr" else "How many numbers will split the payment? (2-5)"
        await send_whatsapp_message(phone, msg)
        return

    if count < 2 or count > 5:
        msg = "Le paiement peut etre divise entre 2 et 5 numeros." if lang == "fr" else "Payment can be split between 2 and 5 numbers."
        await send_whatsapp_message(phone, msg)
        return

    from models import format_price_display
    pricing = session.get("_pricing", {})
    country = session.get("_country_code", "BJ")
    total_eur = pricing.get("total_eur", 0)

    # Calculate split amounts
    extra_payers = count - 1  # First payer is the booker
    recon_fee_eur = SPLIT_PAYMENT_RECONCILIATION_FEE_EUR * extra_payers
    grand_total = total_eur + recon_fee_eur
    per_person = round(grand_total / count, 2)

    if lang == "fr":
        msg = f"*Paiement divise en {count}*\n\n"
        msg += f"Prix total : {format_price_display(total_eur, country)}\n"
        msg += f"Frais de reconciliation : {format_price_display(recon_fee_eur, country)} ({extra_payers}x {SPLIT_PAYMENT_RECONCILIATION_FEE_XOF} XOF)\n"
        msg += f"*Grand total : {format_price_display(grand_total, country)}*\n"
        msg += f"Par personne : ~{format_price_display(per_person, country)}\n\n"
        msg += f"Votre numero ({mask_phone(phone)}) est le payeur n1.\n"
        msg += f"Envoyez les {extra_payers} autre(s) numero(s), un par ligne.\n"
        msg += "Exemple :\n+22997000001\n+22997000002"
    else:
        msg = f"*Payment split {count} ways*\n\n"
        msg += f"Total price: {format_price_display(total_eur, country)}\n"
        msg += f"Reconciliation fee: {format_price_display(recon_fee_eur, country)} ({extra_payers}x {SPLIT_PAYMENT_RECONCILIATION_FEE_XOF} XOF)\n"
        msg += f"*Grand total: {format_price_display(grand_total, country)}*\n"
        msg += f"Per person: ~{format_price_display(per_person, country)}\n\n"
        msg += f"Your number ({mask_phone(phone)}) is payer #1.\n"
        msg += f"Send the other {extra_payers} number(s), one per line.\n"
        msg += "Example:\n+22997000001\n+22997000002"

    await update_session(phone, {
        "state": ConversationState.SPLIT_COLLECTING_NUMBERS,
        "_split_count": count,
        "_split_payers": [phone],
        "_split_recon_fee_eur": recon_fee_eur,
        "_split_grand_total": grand_total,
        "_split_per_person": per_person,
    })
    await send_whatsapp_message(phone, msg)


async def handle_split_collecting_numbers(phone: str, text: str, session: Dict, lang: str):
    """Collect phone numbers for split payment."""
    split_count = session.get("_split_count", 2)
    existing_payers = session.get("_split_payers", [phone])
    needed = split_count - len(existing_payers)

    # Parse phone numbers from text (one per line or comma-separated)
    raw_numbers = [n.strip() for n in text.replace(",", "\n").split("\n") if n.strip()]
    new_payers = []
    invalid = []

    for raw in raw_numbers:
        normalized = _normalize_split_phone(raw)
        if len(normalized) < 10:
            invalid.append(raw)
        elif normalized == phone:
            invalid.append(f"{raw} (votre numero)" if lang == "fr" else f"{raw} (your number)")
        elif normalized in existing_payers or normalized in new_payers:
            invalid.append(f"{raw} (doublon)" if lang == "fr" else f"{raw} (duplicate)")
        else:
            new_payers.append(normalized)

    if invalid:
        inv_str = ", ".join(invalid)
        msg = f"Numero(s) invalide(s) : {inv_str}\nRenvoyez les numeros corrects." if lang == "fr" else f"Invalid number(s): {inv_str}\nResend the correct numbers."
        await send_whatsapp_message(phone, msg)
        return

    if len(new_payers) != needed:
        msg = f"J'ai besoin de {needed} numero(s), vous en avez envoye {len(new_payers)}." if lang == "fr" else f"I need {needed} number(s), you sent {len(new_payers)}."
        await send_whatsapp_message(phone, msg)
        return

    all_payers = existing_payers + new_payers
    per_person = session.get("_split_per_person", 0)
    grand_total = session.get("_split_grand_total", 0)
    country = session.get("_country_code", "BJ")

    from models import format_price_display
    driver_name = session.get("_selected_driver", "celtiis_cash")
    from payment_drivers.router import get_driver
    driver = get_driver(driver_name)
    op_name = driver.display_name if driver else driver_name

    if lang == "fr":
        msg = f"*Recapitulatif du paiement divise*\n\nMethode : {op_name}\n\n"
        for i, p in enumerate(all_payers, 1):
            label = "(vous)" if p == phone else ""
            msg += f"Payeur {i}: {mask_phone(p)} {label} — {format_price_display(per_person, country)}\n"
        msg += f"\n*Grand total : {format_price_display(grand_total, country)}*\n"
        msg += f"Verrou de prix : {PRICE_LOCK_MINUTES} minutes\n\n"
        msg += "*1* Confirmer et envoyer les notifications\n*2* Annuler"
    else:
        msg = f"*Split Payment Summary*\n\nMethod: {op_name}\n\n"
        for i, p in enumerate(all_payers, 1):
            label = "(you)" if p == phone else ""
            msg += f"Payer {i}: {mask_phone(p)} {label} — {format_price_display(per_person, country)}\n"
        msg += f"\n*Grand total: {format_price_display(grand_total, country)}*\n"
        msg += f"Price lock: {PRICE_LOCK_MINUTES} minutes\n\n"
        msg += "*1* Confirm and send notifications\n*2* Cancel"

    await update_session(phone, {
        "state": ConversationState.SPLIT_CONFIRM,
        "_split_payers": all_payers,
    })
    await send_whatsapp_message(phone, msg)


async def handle_split_confirm(phone: str, text: str, session: Dict, lang: str):
    """Confirm split payment and initiate all payment requests."""
    if text in ["2", "non", "no", "annuler", "cancel"]:
        await clear_session(phone)
        msg = "Paiement divise annule." if lang == "fr" else "Split payment cancelled."
        await send_whatsapp_message(phone, msg)
        return

    if text not in ["1", "oui", "yes", "confirmer", "confirm"]:
        msg = "Repondez *1* (confirmer) ou *2* (annuler)" if lang == "fr" else "Reply *1* (confirm) or *2* (cancel)"
        await send_whatsapp_message(phone, msg)
        return

    # Execute split payments
    payers = session.get("_split_payers", [])
    per_person = session.get("_split_per_person", 0)
    driver_name = session.get("_selected_driver", "celtiis_cash")
    booking_id = session.get("booking_id")
    booking_ref = session.get("booking_ref")
    country = session.get("_country_code", "BJ")

    from payment_drivers.router import get_driver
    from models import format_price_display
    driver = get_driver(driver_name)
    if not driver:
        msg = "Methode de paiement indisponible." if lang == "fr" else "Payment method unavailable."
        await send_whatsapp_message(phone, msg)
        return

    is_mobile = driver_name in ["celtiis_cash", "mtn_momo", "moov_money"]
    currency = "XOF" if is_mobile else "EUR"
    amount = eur_to_xof(per_person) if is_mobile else per_person

    # Store split payment details in booking
    split_records = []
    for payer in payers:
        ref = f"SPLIT-{uuid.uuid4().hex[:8].upper()}"
        result = await driver.initiate_payment(
            phone=payer, amount=amount, currency=currency,
            reference=ref, metadata={"booking_id": booking_id, "split": True})
        split_records.append({
            "payer_phone": payer,
            "amount_eur": per_person,
            "reference": result.reference if result.success else ref,
            "status": "PENDING" if result.success else "FAILED",
            "initiated_at": datetime.now(timezone.utc).isoformat(),
        })

        if result.success:
            # Notify each payer
            op_name = driver.display_name
            price_display = format_price_display(per_person, country)
            if payer == phone:
                if lang == "fr":
                    msg = f"*Notification envoyee sur votre numero !*\nMontant : {price_display}\nOuvrez {op_name} et confirmez."
                else:
                    msg = f"*Notification sent to your number!*\nAmount: {price_display}\nOpen {op_name} and confirm."
                await send_whatsapp_message(phone, msg)
            else:
                # Notify the co-payer
                if lang == "fr":
                    co_msg = f"*Travelioo — Demande de paiement*\n\n{mask_phone(phone)} vous demande de contribuer a un billet d'avion.\n\nMontant : {price_display}\nMethode : {op_name}\n\nOuvrez {op_name} et confirmez avec votre PIN."
                else:
                    co_msg = f"*Travelioo — Payment Request*\n\n{mask_phone(phone)} is asking you to contribute to a flight ticket.\n\nAmount: {price_display}\nMethod: {op_name}\n\nOpen {op_name} and confirm with your PIN."
                await send_whatsapp_message(payer, co_msg)
        else:
            logger.error(f"Split payment initiate failed for {mask_phone(payer)}: {result.error}")

    # Update booking with split payment info
    await db.bookings.update_one({"id": booking_id}, {"$set": {
        "split_payments": split_records,
        "split_payer_count": len(payers),
        "split_grand_total_eur": session.get("_split_grand_total", 0),
        "split_recon_fee_eur": session.get("_split_recon_fee_eur", 0),
        "payment_driver": driver_name,
        "price_lock_until": datetime.now(timezone.utc).isoformat(),
    }})

    await update_session(phone, {"state": ConversationState.SPLIT_AWAITING_PAYMENTS})

    # Start polling all payers
    asyncio.create_task(poll_split_payments(
        phone, booking_id, booking_ref, driver_name, split_records, payers, lang))


async def poll_split_payments(phone: str, booking_id: str, booking_ref: str,
                              driver_name: str, split_records: List[Dict],
                              payers: List[str], lang: str):
    """Poll all split payment references. Confirm only when ALL succeed. Auto-refund on failure."""
    from payment_drivers.router import get_driver
    from models import format_price_display

    driver = get_driver(driver_name)
    if not driver:
        return

    statuses = {r["reference"]: "PENDING" for r in split_records if r["status"] == "PENDING"}
    failed_refs = [r["reference"] for r in split_records if r["status"] == "FAILED"]

    if failed_refs:
        # Some payments failed to initiate — abort immediately
        await _handle_split_failure(phone, booking_id, booking_ref, driver, split_records, payers, lang)
        return

    # Poll for up to 60 seconds (20 attempts x 3s)
    for attempt in range(20):
        await asyncio.sleep(3)
        all_done = True

        for ref in list(statuses.keys()):
            if statuses[ref] in ["SUCCESSFUL", "FAILED", "REJECTED", "CANCELLED"]:
                continue
            result = await driver.check_payment_status(ref)
            statuses[ref] = result.status
            logger.info(f"Split poll {attempt + 1}/20: {ref[:16]} = {result.status}")

            if result.status in ["FAILED", "REJECTED", "CANCELLED"]:
                # One payer failed — trigger refunds for all successful ones
                await _handle_split_failure(phone, booking_id, booking_ref, driver, split_records, payers, lang)
                return

            if result.status not in ["SUCCESSFUL", "SUCCESS", "COMPLETED"]:
                all_done = False

        if all_done:
            # ALL payments successful — confirm booking
            await _handle_split_success(phone, booking_id, booking_ref, driver_name, payers, lang)
            return

        # Progress updates
        confirmed = sum(1 for s in statuses.values() if s in ["SUCCESSFUL", "SUCCESS", "COMPLETED"])
        total = len(statuses)
        elapsed = (attempt + 1) * 3
        if elapsed == 15:
            msg = f"En attente... {confirmed}/{total} paiements recus." if lang == "fr" else f"Waiting... {confirmed}/{total} payments received."
            await send_whatsapp_message(phone, msg)
        elif elapsed == 30:
            pending = [r["payer_phone"] for r in split_records if statuses.get(r["reference"]) not in ["SUCCESSFUL", "SUCCESS", "COMPLETED"]]
            pending_names = ", ".join(mask_phone(p) for p in pending)
            msg = f"Toujours en attente de : {pending_names}" if lang == "fr" else f"Still waiting for: {pending_names}"
            await send_whatsapp_message(phone, msg)

    # Timeout — treat as failure
    await _handle_split_failure(phone, booking_id, booking_ref, driver, split_records, payers, lang, timeout=True)


async def _handle_split_success(phone: str, booking_id: str, booking_ref: str,
                                 driver_name: str, payers: List[str], lang: str):
    """All split payments confirmed — finalize booking."""
    booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    if not booking:
        return

    now_utc = datetime.now(timezone.utc)
    await db.bookings.update_one({"id": booking_id}, {"$set": {
        "status": "confirmed",
        "payment_confirmed_at": now_utc.isoformat(),
        "payment_driver": driver_name,
    }})

    # Update all split records to confirmed
    await db.bookings.update_one({"id": booking_id}, {"$set": {
        "split_payments.$[].status": "CONFIRMED"
    }})

    # Update shadow profiles for all payers
    for payer in payers:
        await add_to_travel_history(payer, booking_ref)
        await add_payment_method(payer, driver_name)
        if payer != phone:
            await add_trusted_payer(phone, payer)

    session = await db.sessions.find_one({"phone": phone}, {"_id": 0})
    country = session.get("_country_code", "BJ") if session else "BJ"

    from models import format_price_display
    price_display = format_price_display(booking.get("price_eur", 0), country)
    ts = format_timestamp_gmt1(now_utc)

    if lang == "fr":
        msg = f"*Tous les paiements confirmes !*\n\n{len(payers)} payeurs — Total : {price_display}\n{ts} GMT+1\nReservation : {booking_ref}\n\nVotre billet est en cours de generation..."
    else:
        msg = f"*All payments confirmed!*\n\n{len(payers)} payers — Total: {price_display}\n{ts} GMT+1\nBooking: {booking_ref}\n\nYour ticket is being generated..."
    await send_whatsapp_message(phone, msg)

    ticket_filename = generate_ticket_pdf(booking)
    await asyncio.sleep(2)
    fn = booking.get("passenger_name", "")
    if lang == "fr":
        ticket_msg = f"*Votre billet est pret !*\n{fn}\n{booking.get('origin')} -> {booking.get('destination')}\n{booking.get('departure_date')}\n{booking_ref}\nBon voyage !"
    else:
        ticket_msg = f"*Your ticket is ready!*\n{fn}\n{booking.get('origin')} -> {booking.get('destination')}\n{booking.get('departure_date')}\n{booking_ref}\nHave a great trip!"
    await send_whatsapp_document(phone, f"{APP_BASE_URL}/api/tickets/{ticket_filename}", ticket_filename, ticket_msg)
    await clear_session(phone)


async def _handle_split_failure(phone: str, booking_id: str, booking_ref: str,
                                 driver, split_records: List[Dict],
                                 payers: List[str], lang: str, timeout: bool = False):
    """One or more split payments failed — auto-refund successful ones."""
    logger.warning(f"Split payment failure for {booking_ref}: timeout={timeout}")

    # Find which payments succeeded and need refunding
    refund_tasks = []
    for record in split_records:
        if record["status"] in ["SUCCESSFUL", "SUCCESS", "COMPLETED", "CONFIRMED"]:
            refund_tasks.append({
                "payer": record["payer_phone"],
                "reference": record["reference"],
                "amount": record["amount_eur"],
            })

    # Process refunds
    refund_results = []
    for task in refund_tasks:
        result = await driver.process_refund(task["reference"], task["amount"], reason="split_payment_incomplete")
        refund_results.append({
            "payer": task["payer"],
            "refund_ref": result.reference if result.success else None,
            "success": result.success,
        })
        if result.success:
            # Notify the payer about refund
            if lang == "fr":
                rmsg = f"*Remboursement automatique*\n\nLe paiement divise pour {booking_ref} n'a pas ete complete. Votre paiement a ete rembourse.\nReference remboursement : {result.reference}"
            else:
                rmsg = f"*Automatic Refund*\n\nThe split payment for {booking_ref} was not completed. Your payment has been refunded.\nRefund reference: {result.reference}"
            await send_whatsapp_message(task["payer"], rmsg)

    # Update booking
    await db.bookings.update_one({"id": booking_id}, {"$set": {
        "status": "split_payment_failed",
        "split_refunds": refund_results,
    }})

    # Notify the booker
    reason = "Delai depasse" if timeout else "Un des paiements a echoue"
    reason_en = "Timeout" if timeout else "One of the payments failed"
    refunded_count = sum(1 for r in refund_results if r["success"])

    if lang == "fr":
        msg = f"*Paiement divise echoue*\n\n{reason}.\n"
        if refunded_count > 0:
            msg += f"{refunded_count} remboursement(s) automatique(s) en cours.\n"
        msg += "\n1 Reessayer\n2 Paiement simple (un seul payeur)\n3 Annuler"
    else:
        msg = f"*Split payment failed*\n\n{reason_en}.\n"
        if refunded_count > 0:
            msg += f"{refunded_count} automatic refund(s) processing.\n"
        msg += "\n1 Retry\n2 Single payment (one payer)\n3 Cancel"

    await update_session(phone, {"state": "retry"})
    await send_whatsapp_message(phone, msg)
