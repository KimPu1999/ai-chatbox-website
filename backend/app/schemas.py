from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class HealthResponse(BaseModel):
    status: str
    service: str


class DatabaseHealthResponse(BaseModel):
    status: str
    database: str


class ConversationCreate(BaseModel):
    title: str = Field(default="New conversation", min_length=1, max_length=200)

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Title cannot be blank")
        return value


class ConversationUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    is_pinned: bool | None = None
    archived: bool | None = None
    folder_id: UUID | None = None


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=32_000)

    @field_validator("content")
    @classmethod
    def content_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Message cannot be blank")
        return value


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    conversation_id: UUID
    user_id: UUID
    role: str
    content: str
    created_at: datetime
    status: str = "completed"
    generation_run_id: UUID | None = None
    sequence: int = 0
    version: int = 1


class ModelOption(BaseModel):
    id: str
    name: str
    description: str
    available: bool
    context_window: int | None = None
    max_output_tokens: int | None = None


class GenerationCreate(BaseModel):
    content: str | None = Field(default=None, min_length=1, max_length=32_000)
    model: str | None = Field(default=None, min_length=1, max_length=100)
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=128)

    @field_validator("content")
    @classmethod
    def content_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("Message cannot be blank")
        return value


class GenerationRead(BaseModel):
    id: UUID
    conversation_id: UUID
    model: str
    status: str
    message_id: UUID | None = None


class UsageRead(BaseModel):
    input_tokens: int
    output_tokens: int
    total_tokens: int
    daily_tokens: int
    daily_budget: int


class Pagination(BaseModel):
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class ConversationRead(ConversationCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None = None
    deleted_at: datetime | None = None
    folder_id: UUID | None = None
    pinned_at: datetime | None = None
    last_message_at: datetime | None = None
    is_pinned: bool = False


class ConversationPage(BaseModel):
    items: list[ConversationRead]
    next_cursor: str | None = None
    has_more: bool = False


class FolderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    sort_order: int = Field(default=0, ge=0, le=100_000)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        value = " ".join(value.strip().split())
        if not value:
            raise ValueError("Folder name cannot be blank")
        return value


class FolderUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    sort_order: int | None = Field(default=None, ge=0, le=100_000)

    @field_validator("name")
    @classmethod
    def update_name_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = " ".join(value.strip().split())
        if not value:
            raise ValueError("Folder name cannot be blank")
        return value


class FolderRead(FolderCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    user_id: UUID
    normalized_name: str
    created_at: datetime
    updated_at: datetime


class ConversationSearchResult(BaseModel):
    conversation_id: UUID
    message_id: UUID | None = None
    title: str
    snippet: str
    role: str | None = None
    created_at: datetime
    rank: float = 0


class ConversationSearchPage(BaseModel):
    items: list[ConversationSearchResult]
    next_cursor: str | None = None
    has_more: bool = False


class BulkActionRequest(BaseModel):
    conversation_ids: list[UUID] = Field(min_length=1, max_length=100)
    action: str = Field(
        pattern="^(archive|unarchive|pin|unpin|move_to_folder|soft_delete|restore)$"
    )
    folder_id: UUID | None = None

    @field_validator("conversation_ids")
    @classmethod
    def unique_ids(cls, value: list[UUID]) -> list[UUID]:
        if len(set(value)) != len(value):
            raise ValueError("conversation_ids must be unique")
        return value


class BulkActionRead(BaseModel):
    id: UUID
    action: str
    status: str
    total_count: int
    processed_count: int
    error_summary: str | None = None


class ShareCreate(BaseModel):
    expires_in_days: int | None = Field(default=7, ge=1, le=365)
    password: str | None = Field(default=None, min_length=8, max_length=128)
    message_ids: list[UUID] | None = Field(default=None, max_length=500)


class ShareRead(BaseModel):
    id: UUID
    conversation_id: UUID
    expires_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime
    last_accessed_at: datetime | None
    password_protected: bool


class ShareCreated(ShareRead):
    public_token: str


class SharedMessageRead(BaseModel):
    id: UUID
    role: str
    content: str
    created_at: datetime
    version: int


class SharedConversationRead(BaseModel):
    schema_version: str
    title: str
    created_at: datetime
    messages: list[SharedMessageRead]
