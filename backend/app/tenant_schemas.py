from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


def clean_name(value: str) -> str:
    value = " ".join(value.strip().split())
    if not value:
        raise ValueError("Name cannot be blank")
    return value


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    slug: str = Field(min_length=3, max_length=100)
    description: str | None = Field(default=None, max_length=500)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return clean_name(value)

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, value: str) -> str:
        value = value.strip().casefold()
        if not value.replace("-", "").replace("_", "").isalnum():
            raise ValueError("Slug may contain letters, numbers, hyphens and underscores")
        return value


class OrganizationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=500)
    logo_url: str | None = Field(default=None, max_length=500)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        return clean_name(value) if value is not None else None


class OrganizationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    owner_id: UUID
    slug: str
    name: str
    description: str | None
    logo_url: str | None
    status: str
    role: str
    created_at: datetime
    updated_at: datetime


class OrganizationSummary(BaseModel):
    id: UUID
    slug: str
    name: str
    status: str
    role: str


class MemberRead(BaseModel):
    id: UUID
    user_id: UUID
    email: str
    display_name: str | None
    role: str
    status: str
    created_at: datetime


class MemberUpdate(BaseModel):
    role: str | None = Field(default=None, pattern="^(owner|admin|member|viewer)$")
    status: str | None = Field(default=None, pattern="^(active|suspended)$")


class InvitationCreate(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    role: str = Field(default="member", pattern="^(admin|member|viewer)$")
    expires_in_days: int = Field(default=7, ge=1, le=30)


class InvitationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    email_normalized: str
    role: str
    expires_at: datetime
    accepted_at: datetime | None
    declined_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime


class InvitationCreated(BaseModel):
    invitation: InvitationRead
    token: str | None = None


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=500)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return clean_name(value)


class KnowledgeBaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    name: str
    description: str | None
    status: str
    created_by: UUID
    created_at: datetime
    updated_at: datetime
