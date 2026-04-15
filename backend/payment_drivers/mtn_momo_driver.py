"""MTN MoMo payment driver — UEMOA region."""
import uuid
import base64
import logging
from typing import Dict, Optional
import httpx
from payment_drivers import BasePaymentDriver, PaymentResult
from config import (
    MOMO_SUBSCRIPTION_KEY, MOMO_API_USER, MOMO_API_KEY,
    MOMO_BASE_URL, MOMO_ENVIRONMENT, API_TIMEOUT, get_momo_mode
)

logger = logging.getLogger("MoMoDriver")


class MtnMomoDriver(BasePaymentDriver):
    name = "mtn_momo"
    display_name = "MTN MoMo"
    currency = "XOF"

    def __init__(self):
        self.mode = get_momo_mode()

    async def _get_token(self) -> Optional[str]:
        try:
            auth = base64.b64encode(f"{MOMO_API_USER}:{MOMO_API_KEY}".encode()).decode()
            async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
                resp = await client.post(f"{MOMO_BASE_URL}/collection/token/",
                    headers={"Authorization": f"Basic {auth}",
                             "Ocp-Apim-Subscription-Key": MOMO_SUBSCRIPTION_KEY})
                if resp.status_code == 200:
                    return resp.json().get("access_token")
        except Exception as e:
            logger.error(f"MoMo token error: {e}")
        return None

    async def initiate_payment(self, phone: str, amount: float, currency: str,
                               reference: str, metadata: dict = None) -> PaymentResult:
        self._log("initiate", reference, f"phone=****{phone[-4:]} amount={amount}{currency}")
        if self.mode == "MOCK":
            mock_ref = f"MOMO-SIM-{uuid.uuid4().hex[:8].upper()}"
            return PaymentResult(success=True, reference=mock_ref, status="PENDING")

        token = await self._get_token()
        if not token:
            return PaymentResult(success=False, error="MoMo authentication failed")

        ext_ref = str(uuid.uuid4())
        try:
            async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
                resp = await client.post(f"{MOMO_BASE_URL}/collection/v1_0/requesttopay",
                    json={"amount": str(int(amount)), "currency": currency,
                          "externalId": ext_ref, "payer": {"partyIdType": "MSISDN", "partyId": phone},
                          "payerMessage": f"Travelioo {reference}", "payeeNote": reference},
                    headers={"Authorization": f"Bearer {token}",
                             "X-Reference-Id": ext_ref,
                             "X-Target-Environment": MOMO_ENVIRONMENT,
                             "Ocp-Apim-Subscription-Key": MOMO_SUBSCRIPTION_KEY,
                             "Content-Type": "application/json"})
                if resp.status_code in [200, 202]:
                    return PaymentResult(success=True, reference=ext_ref, status="PENDING")
                return PaymentResult(success=False, error=f"MoMo status {resp.status_code}")
        except Exception as e:
            return PaymentResult(success=False, error=str(e))

    async def check_payment_status(self, reference: str) -> PaymentResult:
        self._log("check_status", reference)
        if self.mode == "MOCK":
            return PaymentResult(success=True, reference=reference, status="SUCCESSFUL")

        token = await self._get_token()
        if not token:
            return PaymentResult(success=False, reference=reference, error="Auth failed")
        try:
            async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
                resp = await client.get(
                    f"{MOMO_BASE_URL}/collection/v1_0/requesttopay/{reference}",
                    headers={"Authorization": f"Bearer {token}",
                             "X-Target-Environment": MOMO_ENVIRONMENT,
                             "Ocp-Apim-Subscription-Key": MOMO_SUBSCRIPTION_KEY})
                if resp.status_code == 200:
                    data = resp.json()
                    status = data.get("status", "PENDING")
                    return PaymentResult(success=status == "SUCCESSFUL", reference=reference,
                                         status=status, raw=data)
        except Exception as e:
            return PaymentResult(success=False, reference=reference, error=str(e))
        return PaymentResult(success=False, reference=reference, status="PENDING")

    async def process_refund(self, reference: str, amount: float, reason: str = "") -> PaymentResult:
        self._log("refund", reference, f"amount={amount}")
        if self.mode == "MOCK":
            ref = f"REFUND-MOMO-{uuid.uuid4().hex[:8].upper()}"
            return PaymentResult(success=True, reference=ref, status="REFUNDED")
        # Real MoMo refund: use disbursement API
        ref = f"REFUND-MOMO-{uuid.uuid4().hex[:8].upper()}"
        logger.warning(f"MoMo refund queued for manual processing: {reference}")
        return PaymentResult(success=True, reference=ref, status="QUEUED")

    async def get_transaction_details(self, reference: str) -> Optional[Dict]:
        if self.mode == "MOCK":
            return {"reference": reference, "status": "SUCCESSFUL", "driver": "mtn_momo", "mode": "MOCK"}
        result = await self.check_payment_status(reference)
        return result.raw if result.raw else None
