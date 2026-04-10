"""Payment service - MTN MoMo, Moov Money, Stripe (Google/Apple Pay)."""
import logging
import math
import uuid
from typing import Dict
import asyncio
import httpx
import stripe as stripe_lib
from config import (
    EUR_TO_XOF, API_TIMEOUT, APP_BASE_URL,
    STRIPE_SECRET_KEY, MOMO_API_USER, MOMO_API_KEY,
    MOMO_SUBSCRIPTION_KEY, MOMO_BASE_URL, MOMO_ENVIRONMENT,
    MOOV_API_KEY, MOOV_BASE_URL
)
from models import PaymentOperator
from database import db

stripe_lib.api_key = STRIPE_SECRET_KEY
logger = logging.getLogger("PaymentService")


class PaymentService:
    def __init__(self):
        self.logger = logger

    @staticmethod
    def _normalize_phone(phone: str) -> str:
        phone = phone.replace("+", "").replace(" ", "").replace("-", "")
        if phone.startswith("00"):
            phone = phone[2:]
        if len(phone) == 8:
            phone = "229" + phone
        return phone

    @staticmethod
    def _eur_to_xof(amount_eur: float) -> int:
        xof = amount_eur * EUR_TO_XOF
        return int(math.ceil(xof / 5) * 5)

    async def request_payment(self, operator: str, phone: str, amount_eur: float, booking_id: str, destination: str = "") -> Dict:
        amount_xof = self._eur_to_xof(amount_eur)
        phone_normalized = self._normalize_phone(phone)
        self.logger.info(f"Payment request: {operator} | {amount_eur}EUR ({amount_xof} XOF) | {booking_id}")
        try:
            if operator == PaymentOperator.MTN_MOMO:
                return await self._momo_pay(phone_normalized, amount_xof, booking_id, destination)
            elif operator == PaymentOperator.MOOV_MONEY:
                return await self._moov_pay(phone_normalized, amount_xof, booking_id, destination)
            elif operator == PaymentOperator.GOOGLE_PAY:
                return await self._google_pay(amount_eur, booking_id)
            elif operator == PaymentOperator.APPLE_PAY:
                return await self._apple_pay(amount_eur, booking_id)
            elif operator == PaymentOperator.CELTIIS_CASH:
                raise NotImplementedError("Celtiis Cash -- pending partner agreement.")
            else:
                raise ValueError(f"Unknown operator: {operator}")
        except Exception as e:
            self.logger.error(f"Payment error ({operator}): {e}")
            return {"status": "error", "error": str(e), "is_simulated": False}

    async def _momo_pay(self, phone: str, amount_xof: int, booking_id: str, destination: str) -> Dict:
        if not all([MOMO_API_USER, MOMO_API_KEY, MOMO_SUBSCRIPTION_KEY]) or MOMO_API_USER == 'your_uuid_here':
            return {"status": "pending", "reference_id": f"MOMO-SIM-{uuid.uuid4().hex[:8].upper()}", "is_simulated": True, "operator": PaymentOperator.MTN_MOMO}
        try:
            async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
                token_response = await client.post(f"{MOMO_BASE_URL}/collection/token/", auth=(MOMO_API_USER, MOMO_API_KEY), headers={"Ocp-Apim-Subscription-Key": MOMO_SUBSCRIPTION_KEY})
                if token_response.status_code != 200:
                    raise Exception(f"Token failed: {token_response.status_code}")
                token = token_response.json().get("access_token")
            reference_id = str(uuid.uuid4())
            async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
                response = await client.post(f"{MOMO_BASE_URL}/collection/v1_0/requesttopay",
                    json={"amount": str(amount_xof), "currency": "XOF", "externalId": booking_id, "payer": {"partyIdType": "MSISDN", "partyId": phone}, "payerMessage": f"Travelio - Vol {destination}", "payeeNote": f"Booking {booking_id}"},
                    headers={"Authorization": f"Bearer {token}", "X-Reference-Id": reference_id, "X-Target-Environment": MOMO_ENVIRONMENT, "Ocp-Apim-Subscription-Key": MOMO_SUBSCRIPTION_KEY, "Content-Type": "application/json"})
                if response.status_code == 202:
                    return {"status": "pending", "reference_id": reference_id, "is_simulated": False, "operator": PaymentOperator.MTN_MOMO}
        except Exception as e:
            self.logger.error(f"MoMo request error: {e}")
        return {"status": "pending", "reference_id": f"MOMO-SIM-{uuid.uuid4().hex[:8].upper()}", "is_simulated": True, "operator": PaymentOperator.MTN_MOMO}

    async def _moov_pay(self, phone: str, amount_xof: int, booking_id: str, destination: str) -> Dict:
        if not MOOV_API_KEY or MOOV_API_KEY == 'your_key_here':
            return {"status": "pending", "reference_id": f"MOOV-SIM-{uuid.uuid4().hex[:8].upper()}", "is_simulated": True, "operator": PaymentOperator.MOOV_MONEY}
        try:
            async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
                response = await client.post(f"{MOOV_BASE_URL}/v1/cash-in",
                    json={"amount": amount_xof, "currency": "XOF", "msisdn": phone, "description": f"Travelio - Vol {destination}", "externalRef": booking_id},
                    headers={"Authorization": f"Bearer {MOOV_API_KEY}", "Content-Type": "application/json"})
                if response.status_code in [200, 201, 202]:
                    data = response.json()
                    return {"status": "pending", "reference_id": data.get("transactionId", booking_id), "is_simulated": False, "operator": PaymentOperator.MOOV_MONEY}
        except Exception as e:
            self.logger.error(f"Moov request error: {e}")
        return {"status": "pending", "reference_id": f"MOOV-SIM-{uuid.uuid4().hex[:8].upper()}", "is_simulated": True, "operator": PaymentOperator.MOOV_MONEY}

    async def _google_pay(self, amount_eur: float, booking_id: str) -> Dict:
        if not STRIPE_SECRET_KEY or STRIPE_SECRET_KEY == 'your_stripe_secret_key_here':
            return {"status": "pending_redirect", "reference_id": f"GPAY-SIM-{uuid.uuid4().hex[:8].upper()}", "payment_url": f"{APP_BASE_URL}/api/pay/{booking_id}?sim=1", "is_simulated": True, "operator": PaymentOperator.GOOGLE_PAY}
        try:
            from datetime import datetime, timezone
            amount_cents = int(amount_eur * 100)
            intent = stripe_lib.PaymentIntent.create(amount=amount_cents, currency="eur", payment_method_types=["card"], metadata={"booking_id": booking_id, "operator": "google_pay"})
            await db.payment_intents.insert_one({"booking_id": booking_id, "stripe_intent_id": intent.id, "client_secret": intent.client_secret, "amount_eur": amount_eur, "status": "pending", "operator": PaymentOperator.GOOGLE_PAY, "created_at": datetime.now(timezone.utc).isoformat()})
            return {"status": "pending_redirect", "reference_id": intent.id, "payment_url": f"{APP_BASE_URL}/api/pay/{booking_id}", "is_simulated": False, "operator": PaymentOperator.GOOGLE_PAY}
        except Exception as e:
            self.logger.error(f"Stripe error: {e}")
            return {"status": "pending_redirect", "reference_id": f"GPAY-SIM-{uuid.uuid4().hex[:8].upper()}", "payment_url": f"{APP_BASE_URL}/api/pay/{booking_id}?sim=1", "is_simulated": True, "operator": PaymentOperator.GOOGLE_PAY}

    async def _apple_pay(self, amount_eur: float, booking_id: str) -> Dict:
        result = await self._google_pay(amount_eur, booking_id)
        result["operator"] = PaymentOperator.APPLE_PAY
        return result

    async def poll_status(self, operator: str, reference_id: str, max_attempts: int = 10, phone: str = None) -> str:
        for attempt in range(max_attempts):
            await asyncio.sleep(3)
            status = await self._check_status(operator, reference_id, phone=phone)
            if status in ["SUCCESSFUL", "SUCCESS", "COMPLETED"]:
                return "SUCCESSFUL"
            elif status in ["FAILED", "REJECTED", "CANCELLED"]:
                return "FAILED"
        return "TIMEOUT"

    async def _check_status(self, operator: str, reference_id: str, phone: str = None) -> str:
        if phone:
            session = await db.sessions.find_one({"phone": phone}, {"_id": 0})
            if session and session.get("_test_force_fail"):
                return "FAILED"
        if "-SIM-" in reference_id:
            return "SUCCESSFUL"
        if operator == PaymentOperator.MTN_MOMO:
            return await self._check_momo_status(reference_id)
        elif operator == PaymentOperator.MOOV_MONEY:
            return await self._check_moov_status(reference_id)
        return "PENDING"

    async def _check_momo_status(self, reference_id: str) -> str:
        if not all([MOMO_API_USER, MOMO_API_KEY, MOMO_SUBSCRIPTION_KEY]):
            return "SUCCESSFUL"
        try:
            async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
                token_resp = await client.post(f"{MOMO_BASE_URL}/collection/token/", auth=(MOMO_API_USER, MOMO_API_KEY), headers={"Ocp-Apim-Subscription-Key": MOMO_SUBSCRIPTION_KEY})
                token = token_resp.json().get("access_token")
                status_resp = await client.get(f"{MOMO_BASE_URL}/collection/v1_0/requesttopay/{reference_id}", headers={"Authorization": f"Bearer {token}", "X-Target-Environment": MOMO_ENVIRONMENT, "Ocp-Apim-Subscription-Key": MOMO_SUBSCRIPTION_KEY})
                if status_resp.status_code == 200:
                    return status_resp.json().get("status", "PENDING")
        except Exception as e:
            self.logger.error(f"MoMo status check error: {e}")
        return "PENDING"

    async def _check_moov_status(self, reference_id: str) -> str:
        if not MOOV_API_KEY or MOOV_API_KEY == 'your_key_here':
            return "SUCCESSFUL"
        try:
            async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
                response = await client.get(f"{MOOV_BASE_URL}/v1/transaction/{reference_id}", headers={"Authorization": f"Bearer {MOOV_API_KEY}"})
                if response.status_code == 200:
                    status = response.json().get("status", "PENDING").upper()
                    if status in ["SUCCESS", "COMPLETED", "SUCCESSFUL"]:
                        return "SUCCESSFUL"
                    elif status in ["FAILED", "REJECTED", "CANCELLED"]:
                        return "FAILED"
                    return "PENDING"
        except Exception as e:
            self.logger.error(f"Moov status check error: {e}")
        return "PENDING"


payment_service = PaymentService()
