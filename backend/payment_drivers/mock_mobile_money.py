"""Generic MOCK mobile money driver — covers any operator from COUNTRY_PAYMENT_METHODS.

Each instance is parameterized with name + display_name + currency so we don't need
to maintain a separate driver file per operator. All operations always succeed in
MOCK mode (this is a demo, not production)."""

import uuid
import logging
from typing import Dict, Optional

from payment_drivers import BasePaymentDriver, PaymentResult

logger = logging.getLogger("MockMobileMoney")


class MockMobileMoneyDriver(BasePaymentDriver):
    """Generic mock driver. mode is always 'MOCK'."""

    def __init__(self, name: str, display_name: str, currency: str = "XOF"):
        self.name = name
        self.display_name = display_name
        self.currency = currency
        self.mode = "MOCK"

    async def initiate_payment(self, phone: str, amount: float, currency: str,
                               reference: str, metadata: dict = None) -> PaymentResult:
        self._log("initiate", reference, f"phone=...{phone[-4:]} amount={amount}{currency}")
        mock_ref = f"{self.name.upper().replace('_', '')[:6]}-SIM-{uuid.uuid4().hex[:8].upper()}"
        return PaymentResult(success=True, reference=mock_ref, status="PENDING")

    async def check_payment_status(self, reference: str) -> PaymentResult:
        self._log("check_status", reference)
        return PaymentResult(success=True, reference=reference, status="SUCCESSFUL")

    async def process_refund(self, reference: str, amount: float, reason: str = "") -> PaymentResult:
        self._log("refund", reference, f"amount={amount}")
        ref = f"REFUND-{self.name.upper().replace('_', '')[:6]}-{uuid.uuid4().hex[:8].upper()}"
        return PaymentResult(success=True, reference=ref, status="REFUNDED")

    async def get_transaction_details(self, reference: str) -> Optional[Dict]:
        return {
            "reference": reference,
            "status": "SUCCESSFUL",
            "driver": self.name,
            "display_name": self.display_name,
            "currency": self.currency,
            "mode": "MOCK",
        }
