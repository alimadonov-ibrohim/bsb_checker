"""
Payment Service — provider-agnostic interface.
Real provider can be plugged via .env without changing business logic.
"""
import os
import uuid
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class PaymentProvider(ABC):
    """Abstract payment provider. Implement this for Click, Payme, Stripe, etc."""

    @abstractmethod
    async def create_payment(
        self,
        amount: float,
        user_id: int,
        description: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Returns:
        {
          "transaction_id": str,
          "payment_url": str | None,
          "status": "pending",
          "raw": {...}
        }
        """
        pass

    @abstractmethod
    async def check_status(self, transaction_id: str) -> Dict[str, Any]:
        """
        Returns:
        {
          "status": "pending" | "paid" | "failed" | "cancelled",
          "paid_at": datetime | None,
          "raw": {...}
        }
        """
        pass

    @abstractmethod
    async def handle_callback(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process webhook/callback from provider.
        Returns normalized status dict.
        """
        pass


class NullPaymentProvider(PaymentProvider):
    """
    Used when no real provider is configured.
    Creates a pending payment record that can only be
    marked as paid by an admin (manual activation).
    """

    async def create_payment(
        self,
        amount: float,
        user_id: int,
        description: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        tx_id = f"manual_{uuid.uuid4().hex[:16]}"
        return {
            "transaction_id": tx_id,
            "payment_url": None,
            "status": "pending",
            "raw": {
                "message": "No payment provider configured. Admin can activate premium manually.",
                "user_id": user_id,
                "amount": amount,
            },
        }

    async def check_status(self, transaction_id: str) -> Dict[str, Any]:
        return {
            "status": "pending",
            "paid_at": None,
            "raw": {"transaction_id": transaction_id},
        }

    async def handle_callback(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "status": "pending",
            "paid_at": None,
            "transaction_id": payload.get("transaction_id"),
            "raw": payload,
        }


class PaymentService:
    def __init__(self, provider: Optional[PaymentProvider] = None):
        self.provider = provider or self._load_provider()

    def _load_provider(self) -> PaymentProvider:
        provider_name = (os.getenv("PAYMENT_PROVIDER") or "").strip().lower()
        api_key = os.getenv("PAYMENT_API_KEY") or ""

        if not provider_name or not api_key:
            logger.warning("No payment provider configured — using NullPaymentProvider")
            return NullPaymentProvider()

        # Placeholder for future real providers (Click, Payme, etc.)
        # Example:
        # if provider_name == "click":
        #     from .providers.click import ClickProvider
        #     return ClickProvider(api_key=api_key, secret=os.getenv("PAYMENT_SECRET"))
        #
        # if provider_name == "payme":
        #     from .providers.payme import PaymeProvider
        #     return PaymeProvider(...)

        logger.warning(f"Unknown payment provider '{provider_name}' — falling back to Null")
        return NullPaymentProvider()

    async def initiate_premium_payment(
        self,
        user_id: int,
        amount: float,
        duration_days: int = 30,
    ) -> Dict[str, Any]:
        description = f"BSB/CHSB Premium — {duration_days} kun"
        result = await self.provider.create_payment(
            amount=amount,
            user_id=user_id,
            description=description,
            metadata={"type": "premium", "duration_days": duration_days},
        )
        return result

    async def verify_and_activate(
        self,
        transaction_id: str,
    ) -> Dict[str, Any]:
        return await self.provider.check_status(transaction_id)

    async def process_callback(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self.provider.handle_callback(payload)

    @staticmethod
    def calculate_premium_until(days: int = 30) -> datetime:
        return datetime.now(timezone.utc) + timedelta(days=days)
