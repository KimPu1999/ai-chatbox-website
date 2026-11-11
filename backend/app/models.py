from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class MessageRole(StrEnum):
    user = "user"
    assistant = "assistant"
    system = "system"


class UserRole(StrEnum):
    user = "user"
    admin = "admin"
    superadmin = "superadmin"


class AccountStatus(StrEnum):
    pending_verification = "pending_verification"
    active = "active"
    suspended = "suspended"
    deleted = "deleted"


class GenerationStatus(StrEnum):
    queued = "queued"
    streaming = "streaming"
    completed = "completed"
    cancelled = "cancelled"
    failed = "failed"
    incomplete = "incomplete"


class MessageStatus(StrEnum):
    completed = "completed"
    streaming = "streaming"
    failed = "failed"
    superseded = "superseded"


class BulkJobStatus(StrEnum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


def uuid_column() -> Mapped[UUID]:
    return mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("length(email_normalized) > 3", name="ck_users_email_normalized_length"),
    )
    id: Mapped[UUID] = uuid_column()
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    email_normalized: Mapped[str] = mapped_column(
        String(320), unique=True, index=True, nullable=False
    )
    password_hash: Mapped[str | None] = mapped_column(String(255))
    display_name: Mapped[str | None] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, default=UserRole.user, server_default="user"
    )
    account_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=AccountStatus.pending_verification,
        server_default="pending_verification",
    )
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sessions: Mapped[list["Session"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    settings: Mapped["UserSettings | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    model_settings: Mapped[list["AIModelSetting"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    folders: Mapped[list["ConversationFolder"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    shares: Mapped[list["ConversationShare"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )
    bulk_jobs: Mapped[list["ConversationBulkJob"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Session(Base):
    __tablename__ = "sessions"
    __table_args__ = (Index("ix_sessions_user_expires", "user_id", "expires_at"),)
    id: Mapped[UUID] = uuid_column()
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    csrf_token_hash: Mapped[str | None] = mapped_column(String(128))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user: Mapped[User] = relationship(back_populates="sessions")


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["folder_id", "user_id"],
            ["conversation_folders.id", "conversation_folders.user_id"],
            name="fk_conversations_folder_user",
        ),
        UniqueConstraint("id", "user_id", name="uq_conversations_id_user"),
        Index("ix_conversations_user_updated", "user_id", "updated_at", "id"),
        Index("ix_conversations_user_folder", "user_id", "folder_id", "updated_at", "id"),
        Index("ix_conversations_user_pinned", "user_id", "pinned_at", "updated_at", "id"),
        CheckConstraint("length(trim(title)) > 0", name="ck_conversations_title_not_blank"),
    )
    id: Mapped[UUID] = uuid_column()
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(
        String(200), nullable=False, default="New conversation", server_default="New conversation"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    folder_id: Mapped[UUID | None] = mapped_column(nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pinned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    search_vector: Mapped[object | None] = mapped_column(
        TSVECTOR, Computed("to_tsvector('simple', coalesce(title, ''))", persisted=True)
    )
    is_pinned: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    user: Mapped[User] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
    folder: Mapped["ConversationFolder | None"] = relationship(
        back_populates="conversations", overlaps="conversations,user"
    )


class ConversationFolder(Base):
    __tablename__ = "conversation_folders"
    __table_args__ = (
        UniqueConstraint("id", "user_id", name="uq_conversation_folders_id_user"),
        UniqueConstraint("user_id", "normalized_name", name="uq_conversation_folders_user_name"),
        Index("ix_conversation_folders_user_sort", "user_id", "sort_order", "created_at", "id"),
        CheckConstraint("length(trim(name)) > 0", name="ck_conversation_folders_name_not_blank"),
        CheckConstraint(
            "length(normalized_name) > 0", name="ck_conversation_folders_normalized_name"
        ),
    )
    id: Mapped[UUID] = uuid_column()
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(100), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    user: Mapped[User] = relationship(back_populates="folders")
    conversations: Mapped[list[Conversation]] = relationship(
        back_populates="folder", overlaps="conversations,user"
    )


class ConversationShare(Base):
    __tablename__ = "conversation_shares"
    __table_args__ = (
        ForeignKeyConstraint(
            ["conversation_id", "owner_id"],
            ["conversations.id", "conversations.user_id"],
            ondelete="CASCADE",
            name="fk_conversation_shares_conversation_owner",
        ),
        Index("ix_conversation_shares_owner_created", "owner_id", "created_at", "id"),
        Index("ix_conversation_shares_expires_revoked", "expires_at", "revoked_at"),
    )
    id: Mapped[UUID] = uuid_column()
    owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    conversation_id: Mapped[UUID] = mapped_column(nullable=False)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    snapshot_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    password_hash: Mapped[str | None] = mapped_column(String(255))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_accessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    owner: Mapped[User] = relationship(back_populates="shares")
    conversation: Mapped[Conversation] = relationship(overlaps="owner,shares")


class ConversationBulkJob(Base):
    __tablename__ = "conversation_bulk_jobs"
    __table_args__ = (
        Index("ix_conversation_bulk_jobs_user_status", "user_id", "status", "created_at"),
        CheckConstraint(
            "action IN ('archive','unarchive','pin','unpin','move_to_folder',"
            "'soft_delete','restore')",
            name="ck_conversation_bulk_jobs_action",
        ),
        CheckConstraint(
            "status IN ('queued','running','completed','failed')",
            name="ck_conversation_bulk_jobs_status",
        ),
        CheckConstraint("total_count >= 0 AND processed_count >= 0", name="ck_bulk_job_counts"),
    )
    id: Mapped[UUID] = uuid_column()
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=BulkJobStatus.queued, server_default="queued"
    )
    total_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    processed_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    error_summary: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user: Mapped[User] = relationship(back_populates="bulk_jobs")


class GenerationRun(Base):
    __tablename__ = "generation_runs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["conversation_id", "user_id"],
            ["conversations.id", "conversations.user_id"],
            ondelete="CASCADE",
            name="fk_generation_runs_conversation_user",
        ),
        UniqueConstraint("id", "user_id", name="uq_generation_runs_id_user"),
        UniqueConstraint("user_id", "idempotency_key", name="uq_generation_runs_user_idempotency"),
        Index("ix_generation_runs_user_status", "user_id", "status", "created_at"),
        Index("ix_generation_runs_conversation_created", "conversation_id", "created_at"),
        CheckConstraint(
            "status IN ('queued', 'streaming', 'completed', 'cancelled', 'failed', 'incomplete')",
            name="ck_generation_runs_status",
        ),
    )
    id: Mapped[UUID] = uuid_column()
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    conversation_id: Mapped[UUID] = mapped_column(nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=GenerationStatus.queued, server_default="queued"
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_response_id: Mapped[str | None] = mapped_column(String(200))
    error_code: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user: Mapped[User] = relationship()
    conversation: Mapped[Conversation] = relationship(overlaps="user")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="generation_run", overlaps="conversation,messages"
    )
    usage: Mapped["AIUsage | None"] = relationship(back_populates="generation_run", uselist=False)


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        ForeignKeyConstraint(
            ["conversation_id", "user_id"],
            ["conversations.id", "conversations.user_id"],
            ondelete="CASCADE",
            name="fk_messages_conversation_user",
        ),
        UniqueConstraint("id", "user_id", name="uq_messages_id_user"),
        ForeignKeyConstraint(
            ["generation_run_id", "user_id"],
            ["generation_runs.id", "generation_runs.user_id"],
            ondelete="SET NULL",
            name="fk_messages_generation_run_user",
        ),
        Index("ix_messages_conversation_created", "conversation_id", "created_at", "id"),
        CheckConstraint("role IN ('user', 'assistant', 'system')", name="ck_messages_role"),
        CheckConstraint("length(content) > 0", name="ck_messages_content_not_empty"),
    )
    id: Mapped[UUID] = uuid_column()
    conversation_id: Mapped[UUID] = mapped_column(nullable=False)
    user_id: Mapped[UUID] = mapped_column(nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    generation_run_id: Mapped[UUID | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=MessageStatus.completed, server_default="completed"
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    search_vector: Mapped[object | None] = mapped_column(
        TSVECTOR, Computed("to_tsvector('simple', coalesce(content, ''))", persisted=True)
    )
    prompt_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    completion_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    conversation: Mapped[Conversation] = relationship(
        back_populates="messages", overlaps="messages"
    )
    generation_run: Mapped[GenerationRun | None] = relationship(
        back_populates="messages", overlaps="conversation,messages"
    )


class AIUsage(Base):
    __tablename__ = "ai_usage"
    __table_args__ = (
        ForeignKeyConstraint(
            ["message_id", "user_id"],
            ["messages.id", "messages.user_id"],
            ondelete="CASCADE",
            name="fk_ai_usage_message_user",
        ),
        ForeignKeyConstraint(
            ["generation_run_id", "user_id"],
            ["generation_runs.id", "generation_runs.user_id"],
            ondelete="CASCADE",
            name="fk_ai_usage_generation_run_user",
        ),
        UniqueConstraint("generation_run_id", name="uq_ai_usage_generation_run"),
        Index("ix_ai_usage_user_created", "user_id", "created_at", "id"),
        CheckConstraint("prompt_tokens >= 0", name="ck_ai_usage_prompt_tokens_nonnegative"),
        CheckConstraint("completion_tokens >= 0", name="ck_ai_usage_completion_tokens_nonnegative"),
    )
    id: Mapped[UUID] = uuid_column()
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    message_id: Mapped[UUID | None] = mapped_column(nullable=True)
    generation_run_id: Mapped[UUID | None] = mapped_column(nullable=True)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    completion_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    total_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    cached_input_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    reasoning_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    estimated_cost: Mapped[float | None] = mapped_column(Numeric(18, 8))
    pricing_version: Mapped[str | None] = mapped_column(String(40))
    usage_confirmed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    provider_response_id: Mapped[str | None] = mapped_column(String(200))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    generation_run: Mapped[GenerationRun | None] = relationship(back_populates="usage")


class Attachment(Base):
    __tablename__ = "attachments"
    __table_args__ = (
        ForeignKeyConstraint(
            ["message_id", "user_id"],
            ["messages.id", "messages.user_id"],
            ondelete="CASCADE",
            name="fk_attachments_message_user",
        ),
        Index("ix_attachments_user_created", "user_id", "created_at", "id"),
        CheckConstraint("byte_size >= 0", name="ck_attachments_byte_size_nonnegative"),
    )
    id: Mapped[UUID] = uuid_column()
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    message_id: Mapped[UUID | None] = mapped_column(nullable=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class UserSettings(Base):
    __tablename__ = "user_settings"
    __table_args__ = (
        CheckConstraint("theme IN ('system', 'light', 'dark')", name="ck_user_settings_theme"),
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    theme: Mapped[str] = mapped_column(
        String(20), nullable=False, default="system", server_default="system"
    )
    settings: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    notifications_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    user: Mapped[User] = relationship(back_populates="settings")


class AIModelSetting(Base):
    __tablename__ = "ai_model_settings"
    __table_args__ = (UniqueConstraint("user_id", "model", name="uq_ai_model_settings_user_model"),)
    id: Mapped[UUID] = uuid_column()
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    parameters: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    user: Mapped[User] = relationship(back_populates="model_settings")


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_user_created", "user_id", "created_at", "id"),)
    id: Mapped[UUID] = uuid_column()
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    metadata_json: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    __table_args__ = (Index("ix_password_reset_tokens_user_expires", "user_id", "expires_at"),)
    id: Mapped[UUID] = uuid_column()
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class EmailVerificationToken(Base):
    __tablename__ = "email_verification_tokens"
    __table_args__ = (Index("ix_email_verification_tokens_user_expires", "user_id", "expires_at"),)
    id: Mapped[UUID] = uuid_column()
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
