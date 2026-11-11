from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PlatformLoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=128)


class PlatformLoginResponse(BaseModel):
    code: str
    message: str
    mfa_required: bool
    mfa_enrollment_required: bool = False


class PlatformMfaVerifyRequest(BaseModel):
    code: str = Field(min_length=6, max_length=64)


class PlatformMfaEnrollment(BaseModel):
    secret: str
    provisioning_uri: str
    recovery_codes: list[str]


class PlatformMe(BaseModel):
    id: UUID
    email: str
    display_name: str | None
    role: str
    mfa_verified: bool


class DateRangeQuery(BaseModel):
    range: Literal["today", "yesterday", "7d", "30d", "custom"] = "30d"
    start: date | None = None
    end: date | None = None


class OverviewResponse(BaseModel):
    range_start: datetime
    range_end: datetime
    total_users: int
    active_users: int
    new_users: int
    conversations: int
    generation_requests: int
    completed_generations: int
    failed_generations: int
    input_tokens: int
    output_tokens: int
    estimated_ai_spend: Decimal | None
    document_storage_bytes: int
    documents: int
    processing_queue: int
    recent_activity: list[dict[str, Any]]


class PlatformUserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: str
    display_name: str | None
    role: str
    account_status: str
    email_verified_at: datetime | None
    created_at: datetime
    last_login_at: datetime | None


class PlatformUserPage(BaseModel):
    items: list[PlatformUserRead]
    total: int
    page: int
    page_size: int


class StatusUpdate(BaseModel):
    account_status: Literal["active", "suspended", "deleted"]


class RoleUpdate(BaseModel):
    role: Literal["user", "admin", "superadmin"]


class UsageSummary(BaseModel):
    requests: int
    completed: int
    failed: int
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int
    embedding_tokens: int
    average_latency_ms: float | None
    confirmed_usage_rows: int
    unknown_usage_rows: int


class UsageTrendPoint(BaseModel):
    date: date
    requests: int
    completed: int
    failed: int
    input_tokens: int
    output_tokens: int
    estimated_cost: Decimal | None


class ModelUsagePoint(BaseModel):
    model: str
    requests: int
    input_tokens: int
    output_tokens: int
    estimated_cost: Decimal | None


class PricingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    provider: str
    model_identifier: str
    effective_start: datetime
    effective_end: datetime | None
    currency: str
    input_price_per_million: Decimal
    output_price_per_million: Decimal
    cached_input_price_per_million: Decimal
    embedding_price_per_million: Decimal
    pricing_version: str


class PricingCreate(BaseModel):
    provider: str = Field(min_length=1, max_length=40)
    model_identifier: str = Field(min_length=1, max_length=100)
    effective_start: datetime
    effective_end: datetime | None = None
    currency: str = Field(default="USD", min_length=3, max_length=3)
    input_price_per_million: Decimal = Field(default=Decimal("0"), ge=0)
    output_price_per_million: Decimal = Field(default=Decimal("0"), ge=0)
    cached_input_price_per_million: Decimal = Field(default=Decimal("0"), ge=0)
    embedding_price_per_million: Decimal = Field(default=Decimal("0"), ge=0)
    pricing_version: str = Field(default="unpriced-v1", min_length=1, max_length=40)


class PlatformModelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    identifier: str
    display_name: str
    provider: str
    enabled: bool
    is_default: bool
    capabilities: dict[str, Any]
    max_output_tokens: int
    context_limit: int
    last_availability_check: datetime | None


class PlatformModelUpdate(BaseModel):
    enabled: bool | None = None
    is_default: bool | None = None
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    max_output_tokens: int | None = Field(default=None, gt=0, le=128000)
    context_limit: int | None = Field(default=None, gt=0, le=1_000_000)


class QuotaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    scope: str
    scope_key: str
    requests_per_minute: int | None
    requests_per_hour: int | None
    daily_token_limit: int | None
    monthly_token_limit: int | None
    daily_spend_limit: Decimal | None
    concurrent_generation_limit: int | None
    document_count_limit: int | None
    storage_size_limit_bytes: int | None
    embedding_token_budget: int | None
    enabled: bool


class QuotaUpdate(BaseModel):
    requests_per_minute: int | None = Field(default=None, ge=0)
    requests_per_hour: int | None = Field(default=None, ge=0)
    daily_token_limit: int | None = Field(default=None, ge=0)
    monthly_token_limit: int | None = Field(default=None, ge=0)
    daily_spend_limit: Decimal | None = Field(default=None, ge=0)
    concurrent_generation_limit: int | None = Field(default=None, ge=0)
    document_count_limit: int | None = Field(default=None, ge=0)
    storage_size_limit_bytes: int | None = Field(default=None, ge=0)
    embedding_token_budget: int | None = Field(default=None, ge=0)
    enabled: bool = True


class AuditLogRead(BaseModel):
    id: UUID
    user_id: UUID | None
    action: str
    entity_type: str
    entity_id: UUID | None
    result: str
    metadata: dict[str, Any]
    correlation_id: str | None
    created_at: datetime


class AuditLogPage(BaseModel):
    items: list[AuditLogRead]
    total: int
    page: int
    page_size: int


class PlatformSettingsRead(BaseModel):
    app_display_name: str
    signup_enabled: bool
    email_verification_required: bool
    default_user_role: Literal["user"]
    default_model: str
    maintenance_message: str | None
    feature_flags: dict[str, bool]
    language: str


class PlatformSettingsUpdate(BaseModel):
    app_display_name: str | None = Field(default=None, min_length=1, max_length=120)
    signup_enabled: bool | None = None
    email_verification_required: bool | None = None
    default_model: str | None = Field(default=None, min_length=1, max_length=100)
    maintenance_message: str | None = Field(default=None, max_length=500)
    feature_flags: dict[str, bool] | None = None
    language: Literal["en", "my"] | None = None
