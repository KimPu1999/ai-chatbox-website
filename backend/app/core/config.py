from functools import lru_cache

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "PyChat AI"
    environment: str = "development"
    debug: bool = False
    database_url: str = "postgresql+asyncpg://pychat:pychat@localhost:5432/pychat"
    test_database_url: str = "sqlite+aiosqlite:///:memory:"
    allowed_origins: list[str] = ["http://localhost:5173"]
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    log_level: str = "INFO"
    session_max_age_seconds: int = Field(default=28_800, gt=0)
    session_idle_timeout_seconds: int = Field(default=1_800, gt=0)
    cookie_secure: bool = False
    frontend_url: str = "http://localhost:5173"
    email_provider: str = "smtp"
    smtp_host: str = ""
    smtp_port: int = Field(default=587, ge=1, le=65_535)
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    email_verification_expire_minutes: int = Field(default=60, gt=0)
    password_reset_expire_minutes: int = Field(default=30, gt=0)
    session_cookie_name: str = "pychat_session"
    csrf_cookie_name: str = "pychat_csrf"
    password_min_length: int = Field(default=12, ge=8, le=128)
    auth_rate_limit_per_minute: int = Field(default=10, ge=1, le=100)
    password_breach_check_enabled: bool = False
    password_breach_api_url: str = "https://api.pwnedpasswords.com/range"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug(cls, value: bool | str) -> bool:
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on", "debug"}
        return value

    @model_validator(mode="after")
    def validate_production_cookie(self) -> "Settings":
        if self.environment.lower() in {"production", "staging"} and not self.cookie_secure:
            raise ValueError("COOKIE_SECURE must be true outside local development")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
