"""Billing boundary. Live checkout is intentionally disabled by default."""

# ruff: noqa: E501

from dataclasses import dataclass

from app.core.config import get_settings


class BillingDisabled(RuntimeError):
    pass


@dataclass(frozen=True)
class BillingEvent:
    event_id: str
    event_type: str
    provider_customer_ref: str | None
    provider_subscription_ref: str | None
    plan_code: str | None
    status: str | None


class BillingProvider:
    async def create_checkout_session(self, *, user_id: str, plan_code: str, return_url: str) -> str:
        raise BillingDisabled("Billing is disabled")

    def verify_webhook(self, raw_payload: bytes, signature: str) -> BillingEvent:
        raise BillingDisabled("Billing is disabled")


def get_billing_provider() -> BillingProvider:
    settings = get_settings()
    if not settings.billing_enabled or settings.billing_provider == "disabled":
        return BillingProvider()
    raise RuntimeError("Configured billing provider has no adapter installed")
