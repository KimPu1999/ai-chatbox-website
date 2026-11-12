import pytest
from cryptography.fernet import Fernet

from app.core.config import Settings
from app.db import _async_database_config


def test_deployment_environment_aliases_are_supported() -> None:
    settings = Settings(
        APP_ENV="staging",
        CORS_ORIGINS="https://chat.example.com",
        TRUSTED_HOSTS="api.example.com",
        COOKIE_SECURE=True,
        DATABASE_URL="postgresql://user:pass@db.example/pychat?sslmode=require",
        MIGRATION_DATABASE_URL="postgresql://migrator:pass@db.example/pychat?sslmode=require",
        REDIS_URL="redis://redis.example:6379/0",
        OPENAI_API_KEY="test-key",
        SESSION_SIGNING_SECRET="x" * 48,
        MFA_ENCRYPTION_KEY=Fernet.generate_key().decode(),
        FRONTEND_URL="https://chat.example.com",
        API_PUBLIC_URL="https://api.example.com",
        STORAGE_BACKEND="r2",
        DOCUMENT_MALWARE_SCAN_REQUIRED=True,
        R2_ACCOUNT_ID="account",
        R2_BUCKET_NAME="bucket",
        R2_ACCESS_KEY_ID="access",
        R2_SECRET_ACCESS_KEY="secret",
    )
    assert settings.environment == "staging"
    assert settings.allowed_origins == ["https://chat.example.com"]
    assert settings.document_storage_backend == "r2"
    assert settings.r2_s3_endpoint == "https://account.r2.cloudflarestorage.com"


def test_async_database_config_normalizes_neon_pooler_urls() -> None:
    url, connect_args = _async_database_config(
        "postgresql://user:pass@ep-example-pooler.neon.tech/db?sslmode=require"
    )
    assert url.startswith("postgresql+asyncpg://")
    assert "sslmode" not in url
    assert connect_args["ssl"] == "require"
    assert connect_args["statement_cache_size"] == 0


def test_production_storage_and_secret_requirements_fail_closed() -> None:
    with pytest.raises(ValueError, match="Missing required production settings"):
        Settings(
            APP_ENV="production",
            COOKIE_SECURE=True,
            TRUSTED_HOSTS="api.example.com",
            FRONTEND_URL="https://chat.example.com",
            API_PUBLIC_URL="https://api.example.com",
        )
