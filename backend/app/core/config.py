from functools import lru_cache

# ruff: noqa: E501
from typing import Literal

from cryptography.fernet import Fernet, InvalidToken
from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "PyChat AI"
    environment: str = Field(
        default="development", validation_alias=AliasChoices("APP_ENV", "ENVIRONMENT")
    )
    debug: bool = False
    database_url: str = "postgresql+asyncpg://localhost:5432/pychat"
    migration_database_url: str | None = Field(
        default=None, validation_alias=AliasChoices("MIGRATION_DATABASE_URL")
    )
    test_database_url: str = "sqlite+aiosqlite:///:memory:"
    allowed_origins: list[str] = Field(
        default=["http://localhost:5173"],
        validation_alias=AliasChoices("CORS_ORIGINS", "ALLOWED_ORIGINS"),
    )
    trusted_hosts: list[str] = ["localhost", "127.0.0.1", "testserver", "test"]
    frontend_url: str = "http://localhost:5173"
    api_public_url: str = "http://localhost:8000"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    ai_timeout_seconds: float = Field(default=60.0, gt=0, le=300)
    ai_max_output_tokens: int = Field(default=1024, gt=0, le=16_384)
    ai_context_token_budget: int = Field(default=8_000, gt=256, le=128_000)
    ai_max_requests_per_minute: int = Field(default=10, ge=1, le=100)
    ai_max_concurrent_generations: int = Field(default=2, ge=1, le=20)
    ai_daily_token_budget: int = Field(default=100_000, gt=0, le=10_000_000)
    ai_pricing_version: str = "unpriced-v1"
    ai_allowed_models: str = ""
    redis_url: str | None = None
    log_level: str = "INFO"
    db_pool_size: int = Field(default=5, ge=1, le=50)
    db_max_overflow: int = Field(default=10, ge=0, le=100)
    db_ssl_ca_file: str | None = None
    session_max_age_seconds: int = Field(default=28_800, gt=0)
    session_idle_timeout_seconds: int = Field(default=1_800, gt=0)
    cookie_secure: bool = False
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    session_signing_secret: str | None = Field(default=None, validation_alias="SESSION_SIGNING_SECRET")
    email_provider: str = "smtp"
    smtp_host: str = ""
    smtp_port: int = Field(default=587, ge=1, le=65_535)
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    email_verification_expire_minutes: int = Field(default=60, gt=0)
    password_reset_expire_minutes: int = Field(default=30, gt=0)
    session_cookie_name: str = "pychat_session"
    platform_session_cookie_name: str = "pychat_platform_session"
    csrf_cookie_name: str = "pychat_csrf"
    password_min_length: int = Field(default=8, ge=8, le=12)
    password_max_length: int = Field(default=12, ge=8, le=12)
    auth_rate_limit_per_minute: int = Field(default=10, ge=1, le=100)
    password_breach_check_enabled: bool = False
    password_breach_api_url: str = "https://api.pwnedpasswords.com/range"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = Field(default=1536, gt=0, le=8192)
    document_max_upload_mb: int = Field(default=20, gt=0, le=200)
    document_max_pages: int = Field(default=200, gt=0, le=10_000)
    document_chunk_tokens: int = Field(default=500, gt=50, le=4_000)
    document_chunk_overlap: int = Field(default=75, ge=0, le=1_000)
    document_retrieval_top_k: int = Field(default=5, ge=1, le=50)
    document_storage_backend: str = Field(
        default="local", validation_alias=AliasChoices("STORAGE_BACKEND", "DOCUMENT_STORAGE_BACKEND")
    )
    document_storage_path: str = "./storage/private"
    r2_account_id: str = ""
    r2_bucket_name: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_endpoint_url: str | None = None
    document_max_files_per_user: int = Field(default=100, gt=0, le=10_000)
    document_max_storage_mb_per_user: int = Field(default=500, gt=0, le=100_000)
    document_processing_timeout_seconds: int = Field(default=120, gt=0, le=3_600)
    document_max_csv_rows: int = Field(default=100_000, gt=0, le=1_000_000)
    document_max_csv_columns: int = Field(default=100, gt=0, le=1_000)
    document_max_extracted_characters: int = Field(default=5_000_000, gt=0, le=50_000_000)
    document_processing_enabled: bool = True
    document_malware_scan_required: bool = False
    platform_mfa_encryption_key: str | None = Field(
        default=None, validation_alias=AliasChoices("MFA_ENCRYPTION_KEY", "PLATFORM_MFA_ENCRYPTION_KEY")
    )
    platform_mfa_issuer: str = "PyChat AI Platform"
    platform_mfa_recent_minutes: int = Field(default=15, gt=0, le=120)
    platform_bootstrap_enabled: bool = False
    platform_bootstrap_environment: str = "local"
    quota_reset_timezone: str = "UTC"
    billing_enabled: bool = False
    billing_provider: str = "disabled"
    otel_enabled: bool = False
    otel_exporter_endpoint: str | None = None
    otel_service_name: str = "pychat-api"
    otel_sample_ratio: float = Field(default=0.1, ge=0, le=1)
    privacy_export_retention_days: int = Field(default=7, gt=0, le=365)
    account_deletion_grace_days: int = Field(default=30, ge=0, le=365)
    sso_feature_enabled: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("trusted_hosts", mode="before")
    @classmethod
    def parse_trusted_hosts(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [host.strip() for host in value.split(",") if host.strip()]
        return value

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug(cls, value: bool | str) -> bool:
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on", "debug"}
        return value

    @model_validator(mode="after")
    def validate_production_cookie(self) -> "Settings":
        environment = self.environment.lower()
        if environment in {"production", "staging"} and not self.cookie_secure:
            raise ValueError("COOKIE_SECURE must be true outside local development")
        if self.cookie_samesite == "none" and not self.cookie_secure:
            raise ValueError("COOKIE_SAMESITE=none requires COOKIE_SECURE=true")
        if "*" in self.trusted_hosts:
            raise ValueError("TRUSTED_HOSTS cannot contain a wildcard")
        if environment in {"production", "staging"} and not any(
            host not in {"localhost", "127.0.0.1", "testserver", "test"}
            for host in self.trusted_hosts
        ):
            raise ValueError("TRUSTED_HOSTS must include an explicit deployment host")
        if environment in {"production", "staging"}:
            required = {
                "DATABASE_URL": self.database_url,
                "MIGRATION_DATABASE_URL": self.migration_database_url,
                "REDIS_URL": self.redis_url,
                "OPENAI_API_KEY": self.openai_api_key,
                "SESSION_SIGNING_SECRET": self.session_signing_secret,
                "MFA_ENCRYPTION_KEY": self.platform_mfa_encryption_key,
                "FRONTEND_URL": self.frontend_url,
                "API_PUBLIC_URL": self.api_public_url,
            }
            missing = [name for name, value in required.items() if not str(value or "").strip()]
            if missing:
                raise ValueError(f"Missing required production settings: {', '.join(missing)}")
            if self.debug:
                raise ValueError("DEBUG must be false outside local development")
            if not self.frontend_url.startswith("https://") or not self.api_public_url.startswith("https://"):
                raise ValueError("FRONTEND_URL and API_PUBLIC_URL must use HTTPS outside local development")
            if self.document_storage_backend != "r2":
                raise ValueError("STORAGE_BACKEND must be r2 outside local development")
            if not self.document_malware_scan_required:
                raise ValueError("DOCUMENT_MALWARE_SCAN_REQUIRED must be true outside local development")
            if len(self.session_signing_secret or "") < 32:
                raise ValueError("SESSION_SIGNING_SECRET must contain at least 32 characters")
            try:
                Fernet((self.platform_mfa_encryption_key or "").encode())
            except (ValueError, TypeError, InvalidToken) as exc:
                raise ValueError("MFA_ENCRYPTION_KEY must be a valid Fernet key") from exc
            r2_required = {
                "R2_ACCOUNT_ID": self.r2_account_id,
                "R2_BUCKET_NAME": self.r2_bucket_name,
                "R2_ACCESS_KEY_ID": self.r2_access_key_id,
                "R2_SECRET_ACCESS_KEY": self.r2_secret_access_key,
            }
            missing_r2 = [name for name, value in r2_required.items() if not value.strip()]
            if missing_r2:
                raise ValueError(f"Missing required R2 settings: {', '.join(missing_r2)}")
            if self.billing_enabled and self.billing_provider == "disabled":
                raise ValueError("BILLING_PROVIDER must be configured when BILLING_ENABLED is true")
        return self

    @property
    def r2_s3_endpoint(self) -> str:
        return self.r2_endpoint_url or f"https://{self.r2_account_id}.r2.cloudflarestorage.com"

    @model_validator(mode="after")
    def validate_password_bounds(self) -> "Settings":
        if self.password_min_length > self.password_max_length:
            raise ValueError("PASSWORD_MIN_LENGTH cannot exceed PASSWORD_MAX_LENGTH")
        return self

    @model_validator(mode="after")
    def validate_document_chunking(self) -> "Settings":
        if self.document_chunk_overlap >= self.document_chunk_tokens:
            raise ValueError("DOCUMENT_CHUNK_OVERLAP must be less than DOCUMENT_CHUNK_TOKENS")
        if self.embedding_dimensions != 1536:
            raise ValueError(
                "EMBEDDING_DIMENSIONS must remain 1536 until a re-embedding migration is applied"
            )
        return self

    @model_validator(mode="after")
    def validate_platform_security(self) -> "Settings":
        if self.environment.lower() in {"production", "staging"} and not self.platform_mfa_encryption_key:
            raise ValueError("PLATFORM_MFA_ENCRYPTION_KEY must be configured outside local development")
        if self.platform_bootstrap_enabled and self.environment.lower() in {"production", "staging"}:
            if self.platform_bootstrap_environment != self.environment.lower():
                raise ValueError("PLATFORM_BOOTSTRAP_ENVIRONMENT must match the deployment environment")
        return self

    @property
    def allowed_ai_models(self) -> tuple[str, ...]:
        configured = tuple(
            item.strip() for item in self.ai_allowed_models.split(",") if item.strip()
        )
        return configured or (self.openai_model,)


@lru_cache
def get_settings() -> Settings:
    return Settings()
