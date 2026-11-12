# ruff: noqa: E501

import pytest
from cryptography.fernet import Fernet

from app.core.config import Settings
from app.observability import safe_generation_attributes
from app.phase11_schemas import FeedbackCreate, SupportTicketCreate


def test_phase11_defaults_keep_billing_disabled() -> None:
    settings = Settings()
    assert settings.billing_enabled is False
    assert settings.billing_provider == "disabled"


def test_production_billing_requires_a_provider() -> None:
    with pytest.raises(ValueError, match="BILLING_PROVIDER"):
        Settings(
            APP_ENV="production",
            COOKIE_SECURE=True,
            TRUSTED_HOSTS="api.example.com",
            FRONTEND_URL="https://chat.example.com",
            API_PUBLIC_URL="https://api.example.com",
            DATABASE_URL="postgresql://app:secret@db/pychat",
            MIGRATION_DATABASE_URL="postgresql://migration:secret@db/pychat",
            REDIS_URL="redis://redis:6379/0",
            OPENAI_API_KEY="placeholder",
            SESSION_SIGNING_SECRET="s" * 48,
            MFA_ENCRYPTION_KEY=Fernet.generate_key().decode(),
            STORAGE_BACKEND="r2",
            DOCUMENT_MALWARE_SCAN_REQUIRED=True,
            R2_ACCOUNT_ID="account",
            R2_BUCKET_NAME="bucket",
            R2_ACCESS_KEY_ID="access",
            R2_SECRET_ACCESS_KEY="secret",
            BILLING_ENABLED=True,
        )


def test_feedback_and_support_payloads_are_bounded() -> None:
    assert FeedbackCreate(category="bug", message="A problem", rating=4).rating == 4
    assert SupportTicketCreate(subject="Help", body="Please investigate").priority == "normal"
    with pytest.raises(ValueError):
        FeedbackCreate(category="bug", message="")


def test_telemetry_attributes_exclude_user_content() -> None:
    attributes = safe_generation_attributes("gpt-4o-mini", "completed", 12.3456)
    assert attributes == {"ai.model": "gpt-4o-mini", "ai.status": "completed", "ai.latency_ms": 12.35}
