"""Stripe payment driver — Google Pay / Apple Pay / International cards."""
import uuid
import logging
from typing import Dict, Optional
import httpx
from payment_drivers import BasePaymentDriver, PaymentResult
from config import STRIPE_SECRET_KEY, get_stripe_mode

logger = logging.getLogger("StripeDriver")


class StripeDriver(BasePaymentDriver):
    name = "stripe"
    display_name = "Carte / Google Pay / Apple Pay"
    currency = "EUR"

    def __init__(self):
        self.mode = get_stripe_mode()

    async def initiate_payment(self, phone: str, amount: float, currency: str,
                               reference: str, metadata: dict = None) -> PaymentResult:
        self._log("initiate", reference, f"amount={amount}{currency}")
        if self.mode == "MOCK":
            mock_ref = f"STRIPE-SIM-{uuid.uuid4().hex[:8].upper()}"
            return PaymentResult(success=True, reference=mock_ref, status="PENDING")

        try:
            import stripe
            stripe.api_key = STRIPE_SECRET_KEY
            intent = stripe.PaymentIntent.create(
                amount=int(amount * 100),
                currency=currency.lower(),
                metadata={"booking_ref": reference, "phone": phone, **(metadata or {})},
                payment_method_types=["card"],
            )
            return PaymentResult(success=True, reference=intent.id,
                                 status="PENDING", raw={"client_secret": intent.client_secret})
        except Exception as e:
            return PaymentResult(success=False, error=str(e))

    async def check_payment_status(self, reference: str) -> PaymentResult:
        self._log("check_status", reference)
        if self.mode == "MOCK":
            return PaymentResult(success=True, reference=reference, status="SUCCESSFUL")
        try:
            import stripe
            stripe.api_key = STRIPE_SECRET_KEY
            intent = stripe.PaymentIntent.retrieve(reference)
            status = "SUCCESSFUL" if intent.status == "succeeded" else intent.status.upper()
            return PaymentResult(success=intent.status == "succeeded", reference=reference,
                                 status=status)
        except Exception as e:
            return PaymentResult(success=False, reference=reference, error=str(e))

    async def process_refund(self, reference: str, amount: float, reason: str = "") -> PaymentResult:
        self._log("refund", reference, f"amount={amount}")
        if self.mode == "MOCK":
            ref = f"REFUND-STRIPE-{uuid.uuid4().hex[:8].upper()}"
            return PaymentResult(success=True, reference=ref, status="REFUNDED")
        try:
            import stripe
            stripe.api_key = STRIPE_SECRET_KEY
            refund = stripe.Refund.create(
                payment_intent=reference, amount=int(amount * 100), reason="requested_by_customer")
            return PaymentResult(success=True, reference=refund.id, status="REFUNDED")
        except Exception as e:
            return PaymentResult(success=False, error=str(e))

    async def get_transaction_details(self, reference: str) -> Optional[Dict]:
        if self.mode == "MOCK":
            return {"reference": reference, "status": "SUCCESSFUL", "driver": "stripe", "mode": "MOCK"}
        try:
            import stripe
            stripe.api_key = STRIPE_SECRET_KEY
            intent = stripe.PaymentIntent.retrieve(reference)
            return {"reference": intent.id, "status": intent.status, "amount": intent.amount / 100}
        except Exception:
            return None
