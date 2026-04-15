"""Moov Money (Flooz) payment driver — UEMOA region."""
import uuid
import logging
from typing import Dict, Optional
import httpx
from payment_drivers import BasePaymentDriver, PaymentResult
from config import MOOV_API_KEY, MOOV_BASE_URL, API_TIMEOUT, get_moov_mode

logger = logging.getLogger("MoovDriver")


class MoovDriver(BasePaymentDriver):
    name = "moov_money"
    display_name = "Moov Money (Flooz)"
    currency = "XOF"

    def __init__(self):
        self.mode = get_moov_mode()

    async def initiate_payment(self, phone: str, amount: float, currency: str,
                               reference: str, metadata: dict = None) -> PaymentResult:
        self._log("initiate", reference, f"phone=****{phone[-4:]} amount={amount}{currency}")
        if self.mode == "MOCK":
            mock_ref = f"MOOV-SIM-{uuid.uuid4().hex[:8].upper()}"
            return PaymentResult(success=True, reference=mock_ref, status="PENDING")

        try:
            async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
                resp = await client.post(f"{MOOV_BASE_URL}/v1/cash-in",
                    json={"phone": phone, "amount": int(amount), "currency": currency,
                          "reference": reference, "description": f"Travelioo {reference}"},
                    headers={"Authorization": f"Bearer {MOOV_API_KEY}",
                             "Content-Type": "application/json"})
                data = resp.json()
                if resp.status_code == 200:
                    return PaymentResult(success=True,
                                         reference=data.get("transaction_id", reference),
                                         status=data.get("status", "PENDING"), raw=data)
                return PaymentResult(success=False, error=data.get("message", "Moov initiation failed"))
        except Exception as e:
            return PaymentResult(success=False, error=str(e))

    async def check_payment_status(self, reference: str) -> PaymentResult:
        self._log("check_status", reference)
        if self.mode == "MOCK":
            return PaymentResult(success=True, reference=reference, status="SUCCESSFUL")
        try:
            async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
                resp = await client.get(f"{MOOV_BASE_URL}/v1/transactions/{reference}",
                    headers={"Authorization": f"Bearer {MOOV_API_KEY}"})
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
            ref = f"REFUND-MOOV-{uuid.uuid4().hex[:8].upper()}"
            return PaymentResult(success=True, reference=ref, status="REFUNDED")
        ref = f"REFUND-MOOV-{uuid.uuid4().hex[:8].upper()}"
        logger.warning(f"Moov refund queued for manual processing: {reference}")
        return PaymentResult(success=True, reference=ref, status="QUEUED")

    async def get_transaction_details(self, reference: str) -> Optional[Dict]:
        if self.mode == "MOCK":
            return {"reference": reference, "status": "SUCCESSFUL", "driver": "moov_money", "mode": "MOCK"}
        result = await self.check_payment_status(reference)
        return result.raw if result.raw else None
