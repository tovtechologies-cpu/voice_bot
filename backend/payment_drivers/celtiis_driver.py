"""Celtiis Cash payment driver — Benin exclusive partner."""
import uuid
import logging
from typing import Dict, Optional
import httpx
from payment_drivers import BasePaymentDriver, PaymentResult
from config import CELTIIS_API_KEY, CELTIIS_API_URL, API_TIMEOUT

logger = logging.getLogger("CeltiisDriver")


class CeltiisDriver(BasePaymentDriver):
    name = "celtiis_cash"
    display_name = "Celtiis Cash"
    currency = "XOF"

    def __init__(self):
        if CELTIIS_API_KEY and CELTIIS_API_KEY != 'your_key_here':
            self.mode = "PRODUCTION"
        else:
            self.mode = "MOCK"

    async def initiate_payment(self, phone: str, amount: float, currency: str,
                               reference: str, metadata: dict = None) -> PaymentResult:
        self._log("initiate", reference, f"phone={phone[-4:]} amount={amount}{currency}")
        if self.mode == "MOCK":
            mock_ref = f"CELT-SIM-{uuid.uuid4().hex[:8].upper()}"
            return PaymentResult(success=True, reference=mock_ref, status="PENDING")

        try:
            async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
                resp = await client.post(f"{CELTIIS_API_URL}/v1/payments/initiate",
                    json={
                        "phone": phone, "amount": int(amount),
                        "currency": currency, "reference": reference,
                        "description": f"Travelioo flight booking {reference}",
                        **(metadata or {})
                    },
                    headers={"Authorization": f"Bearer {CELTIIS_API_KEY}",
                             "Content-Type": "application/json"})
                data = resp.json()
                if resp.status_code == 200 and data.get("status") in ["PENDING", "SUCCESS"]:
                    return PaymentResult(success=True, reference=data.get("transaction_id", reference),
                                         status=data.get("status", "PENDING"), raw=data)
                return PaymentResult(success=False, error=data.get("message", "Celtiis initiation failed"))
        except Exception as e:
            logger.error(f"Celtiis initiate error: {e}")
            return PaymentResult(success=False, error=str(e))

    async def check_payment_status(self, reference: str) -> PaymentResult:
        self._log("check_status", reference)
        if self.mode == "MOCK":
            return PaymentResult(success=True, reference=reference, status="SUCCESSFUL")

        try:
            async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
                resp = await client.get(f"{CELTIIS_API_URL}/v1/payments/{reference}",
                    headers={"Authorization": f"Bearer {CELTIIS_API_KEY}"})
                data = resp.json()
                status = data.get("status", "PENDING")
                return PaymentResult(success=status == "SUCCESSFUL", reference=reference,
                                     status=status, raw=data)
        except Exception as e:
            return PaymentResult(success=False, reference=reference, error=str(e))

    async def process_refund(self, reference: str, amount: float, reason: str = "") -> PaymentResult:
        self._log("refund", reference, f"amount={amount}")
        if self.mode == "MOCK":
            ref = f"REFUND-CELT-{uuid.uuid4().hex[:8].upper()}"
            return PaymentResult(success=True, reference=ref, status="REFUNDED")

        try:
            async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
                resp = await client.post(f"{CELTIIS_API_URL}/v1/refunds",
                    json={"transaction_id": reference, "amount": int(amount), "reason": reason},
                    headers={"Authorization": f"Bearer {CELTIIS_API_KEY}",
                             "Content-Type": "application/json"})
                data = resp.json()
                if resp.status_code == 200:
                    return PaymentResult(success=True, reference=data.get("refund_id", reference),
                                         status="REFUNDED", raw=data)
                return PaymentResult(success=False, error=data.get("message", "Refund failed"))
        except Exception as e:
            return PaymentResult(success=False, error=str(e))

    async def get_transaction_details(self, reference: str) -> Optional[Dict]:
        if self.mode == "MOCK":
            return {"reference": reference, "status": "SUCCESSFUL", "driver": "celtiis_cash", "mode": "MOCK"}
        try:
            async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
                resp = await client.get(f"{CELTIIS_API_URL}/v1/payments/{reference}",
                    headers={"Authorization": f"Bearer {CELTIIS_API_KEY}"})
                return resp.json() if resp.status_code == 200 else None
        except Exception:
            return None
