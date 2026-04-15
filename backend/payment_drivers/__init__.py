"""Abstract base class for all payment drivers."""
from abc import ABC, abstractmethod
from typing import Dict, Optional
from datetime import datetime, timezone
import logging

logger = logging.getLogger("PaymentDriver")


class PaymentResult:
    def __init__(self, success: bool, reference: str = "", status: str = "PENDING",
                 error: str = "", raw: dict = None):
        self.success = success
        self.reference = reference
        self.status = status
        self.error = error
        self.raw = raw or {}
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "reference": self.reference,
            "status": self.status,
            "error": self.error,
            "timestamp": self.timestamp,
        }


class BasePaymentDriver(ABC):
    """All payment drivers must implement these 4 methods."""

    name: str = "base"
    display_name: str = "Base"
    currency: str = "EUR"
    mode: str = "MOCK"  # MOCK, SANDBOX, PRODUCTION

    @abstractmethod
    async def initiate_payment(self, phone: str, amount: float, currency: str,
                               reference: str, metadata: dict = None) -> PaymentResult:
        """Initiate a payment request to the user's device/account."""
        pass

    @abstractmethod
    async def check_payment_status(self, reference: str) -> PaymentResult:
        """Poll for payment status."""
        pass

    @abstractmethod
    async def process_refund(self, reference: str, amount: float,
                             reason: str = "") -> PaymentResult:
        """Process a refund for a completed payment."""
        pass

    @abstractmethod
    async def get_transaction_details(self, reference: str) -> Optional[Dict]:
        """Retrieve full transaction details."""
        pass

    def _log(self, action: str, ref: str, detail: str = ""):
        logger.info(f"[{self.name.upper()} {self.mode}] {action} | ref={ref} {detail}")
