from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    code: str
    name: str
    description: str
    enabled: bool
    entitlements: dict[str, dict] = {}


class PlanUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    enabled: bool | None = None
    sort_order: int | None = Field(default=None, ge=0, le=100_000)
    entitlements: dict[str, dict] | None = None


class AccountPlanRead(BaseModel):
    plan: PlanRead
    subscription_status: str
    current_period_end: datetime | None = None
    billing_enabled: bool


class AccountUsageRead(BaseModel):
    plan_code: str
    daily_tokens: int
    daily_token_limit: int | None
    generation_requests: int
    document_count: int
    storage_bytes: int
    reset_at: datetime


class FeedbackCreate(BaseModel):
    category: Literal["bug", "feature", "general", "ai_quality"]
    message: str = Field(min_length=1, max_length=5000)
    rating: int | None = Field(default=None, ge=1, le=5)


class FeedbackRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    category: str
    message: str
    rating: int | None
    created_at: datetime


class SupportTicketCreate(BaseModel):
    subject: str = Field(min_length=3, max_length=200)
    body: str = Field(min_length=1, max_length=10_000)
    priority: Literal["low", "normal", "high", "urgent"] = "normal"


class SupportMessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=10_000)


class SupportTicketRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    ticket_number: str
    subject: str
    priority: str
    status: str
    created_at: datetime
    updated_at: datetime


class SupportTicketDetail(SupportTicketRead):
    messages: list[dict]


class PrivacyRequestCreate(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=128)


class PrivacyRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    request_type: str
    status: str
    created_at: datetime
    finished_at: datetime | None


class FeatureFlagRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    key: str
    enabled: bool
    admin_only: bool
    rollout_percent: int
    plan_codes: list
    user_allowlist: list


class FeatureFlagUpdate(BaseModel):
    enabled: bool | None = None
    admin_only: bool | None = None
    rollout_percent: int | None = Field(default=None, ge=0, le=100)
    plan_codes: list[str] | None = None
    user_allowlist: list[str] | None = None


class OperationsSummary(BaseModel):
    active_incidents: int
    open_support_tickets: int
    queued_documents: int
    failed_generations_24h: int
    estimated_cost_24h: Decimal | None
    flags_enabled: int


class SLOStatus(BaseModel):
    name: str
    target: float
    observed: float | None
    error_budget_remaining: float | None
    window_days: int = 28
