from datetime import date, datetime

# ruff: noqa: E501
from enum import StrEnum
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
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
        UniqueConstraint("email_normalized", name="uq_users_email_normalized"),
        CheckConstraint("length(email_normalized) > 3", name="ck_users_email_normalized_length"),
    )
    id: Mapped[UUID] = uuid_column()
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    email_normalized: Mapped[str] = mapped_column(String(320), nullable=False)
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
    __table_args__ = (
        Index("ix_sessions_user_expires", "user_id", "expires_at"),
        Index("ix_sessions_kind_activity", "session_kind", "last_activity_at"),
    )
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
    session_kind: Mapped[str] = mapped_column(String(20), nullable=False, default="user", server_default="user")
    mfa_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
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
        Index("ix_conversations_organization", "organization_id"),
        CheckConstraint("length(trim(title)) > 0", name="ck_conversations_title_not_blank"),
    )
    id: Mapped[UUID] = uuid_column()
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[UUID | None] = mapped_column(nullable=True)
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
        Index("ix_generation_runs_organization", "organization_id"),
        CheckConstraint(
            "status IN ('queued', 'streaming', 'completed', 'cancelled', 'failed', 'incomplete')",
            name="ck_generation_runs_status",
        ),
    )
    id: Mapped[UUID] = uuid_column()
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[UUID | None] = mapped_column(nullable=True)
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
        Index("ix_messages_organization", "organization_id"),
        CheckConstraint("role IN ('user', 'assistant', 'system')", name="ck_messages_role"),
        CheckConstraint("length(content) > 0", name="ck_messages_content_not_empty"),
    )
    id: Mapped[UUID] = uuid_column()
    conversation_id: Mapped[UUID] = mapped_column(nullable=False)
    user_id: Mapped[UUID] = mapped_column(nullable=False)
    organization_id: Mapped[UUID | None] = mapped_column(nullable=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    generation_run_id: Mapped[UUID | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=MessageStatus.completed, server_default="completed"
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    citations: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)
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
        Index("ix_ai_usage_organization", "organization_id"),
        CheckConstraint("prompt_tokens >= 0", name="ck_ai_usage_prompt_tokens_nonnegative"),
        CheckConstraint("completion_tokens >= 0", name="ck_ai_usage_completion_tokens_nonnegative"),
    )
    id: Mapped[UUID] = uuid_column()
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[UUID | None] = mapped_column(nullable=True)
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


class DocumentStatus(StrEnum):
    quarantined = "quarantined"
    queued = "queued"
    parsing = "parsing"
    chunking = "chunking"
    embedding = "embedding"
    ready = "ready"
    failed = "failed"
    cancelled = "cancelled"
    ocr_required = "ocr_required"
    partially_extracted = "partially_extracted"


class DocumentJobStatus(StrEnum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("id", "user_id", name="uq_documents_id_user"),
        Index("ix_documents_user_created", "user_id", "created_at", "id"),
        Index("ix_documents_user_status", "user_id", "status", "created_at"),
        Index("ix_documents_organization", "organization_id"),
        CheckConstraint("size_bytes >= 0", name="ck_documents_size_nonnegative"),
        CheckConstraint(
            "status IN ("
            "'quarantined','queued','parsing','chunking','embedding','ready',"
            "'failed','cancelled','ocr_required','partially_extracted')",
            name="ck_documents_status",
        ),
    )
    id: Mapped[UUID] = uuid_column()
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[UUID | None] = mapped_column(nullable=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    page_count: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="quarantined")
    error_code: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "processing_version",
            "chunk_index",
            name="uq_document_chunks_version_index",
        ),
        ForeignKeyConstraint(
            ["document_id", "user_id"],
            ["documents.id", "documents.user_id"],
            ondelete="CASCADE",
            name="fk_document_chunks_document_user",
        ),
        Index("ix_document_chunks_user_document", "user_id", "document_id", "chunk_index"),
        Index("ix_document_chunks_organization", "organization_id"),
    )
    id: Mapped[UUID] = uuid_column()
    document_id: Mapped[UUID] = mapped_column(nullable=False)
    user_id: Mapped[UUID] = mapped_column(nullable=False)
    organization_id: Mapped[UUID | None] = mapped_column(nullable=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer)
    source_locator: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(100), nullable=False)
    embedding_dimensions: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="1536"
    )
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))
    processing_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class DocumentProcessingJob(Base):
    __tablename__ = "document_processing_jobs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["document_id", "user_id"],
            ["documents.id", "documents.user_id"],
            ondelete="CASCADE",
            name="fk_document_jobs_document_user",
        ),
        Index("ix_document_jobs_user_status", "user_id", "status", "created_at"),
        Index("ix_document_processing_jobs_organization", "organization_id"),
        UniqueConstraint("document_id", "attempt_count", name="uq_document_jobs_attempt"),
        CheckConstraint("progress >= 0 AND progress <= 100", name="ck_document_jobs_progress"),
        CheckConstraint("attempt_count >= 0", name="ck_document_jobs_attempt_nonnegative"),
    )
    id: Mapped[UUID] = uuid_column()
    document_id: Mapped[UUID] = mapped_column(nullable=False)
    user_id: Mapped[UUID] = mapped_column(nullable=False)
    organization_id: Mapped[UUID | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="queued")
    progress: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(80))
    embedding_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    embedding_cost_estimate: Mapped[float | None] = mapped_column(Numeric(18, 8))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ConversationDocument(Base):
    __tablename__ = "conversation_documents"
    __table_args__ = (
        ForeignKeyConstraint(
            ["conversation_id", "attached_by"],
            ["conversations.id", "conversations.user_id"],
            ondelete="CASCADE",
            name="fk_conversation_documents_conversation_user",
        ),
        ForeignKeyConstraint(
            ["document_id", "attached_by"],
            ["documents.id", "documents.user_id"],
            ondelete="CASCADE",
            name="fk_conversation_documents_document_user",
        ),
        UniqueConstraint("conversation_id", "document_id", name="uq_conversation_documents"),
        Index("ix_conversation_documents_user", "attached_by", "created_at"),
        Index("ix_conversation_documents_organization", "organization_id"),
    )
    conversation_id: Mapped[UUID] = mapped_column(primary_key=True)
    document_id: Mapped[UUID] = mapped_column(primary_key=True)
    attached_by: Mapped[UUID] = mapped_column(nullable=False)
    organization_id: Mapped[UUID | None] = mapped_column(nullable=True)
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
    __table_args__ = (
        Index("ix_audit_logs_user_created", "user_id", "created_at", "id"),
        Index("ix_audit_logs_action_created", "action", "created_at", "id"),
    )
    id: Mapped[UUID] = uuid_column()
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    metadata_json: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict, server_default="{}"
    )
    result: Mapped[str] = mapped_column(String(20), nullable=False, default="success", server_default="success")
    correlation_id: Mapped[str | None] = mapped_column(String(100))
    network_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
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


class PlatformSetting(Base):
    __tablename__ = "platform_settings"
    __table_args__ = (Index("ix_platform_settings_updated", "updated_at"),)
    id: Mapped[UUID] = uuid_column()
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    updated_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class PlatformModel(Base):
    __tablename__ = "platform_models"
    __table_args__ = (
        CheckConstraint("length(trim(identifier)) > 0", name="ck_platform_models_identifier"),
        CheckConstraint("max_output_tokens > 0 AND context_limit > 0", name="ck_platform_models_limits"),
        Index("ix_platform_models_enabled_default", "enabled", "is_default"),
    )
    id: Mapped[UUID] = uuid_column()
    identifier: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False, default="openai", server_default="openai")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    capabilities: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    max_output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=1024, server_default="1024")
    context_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=8000, server_default="8000")
    last_availability_check: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class ModelPricingVersion(Base):
    __tablename__ = "model_pricing_versions"
    __table_args__ = (
        UniqueConstraint("provider", "model_identifier", "effective_start", name="uq_model_pricing_effective_start"),
        CheckConstraint("input_price_per_million >= 0 AND output_price_per_million >= 0 AND cached_input_price_per_million >= 0 AND embedding_price_per_million >= 0", name="ck_model_pricing_nonnegative"),
        Index("ix_model_pricing_model_dates", "provider", "model_identifier", "effective_start", "effective_end"),
    )
    id: Mapped[UUID] = uuid_column()
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    model_identifier: Mapped[str] = mapped_column(String(100), nullable=False)
    effective_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD", server_default="USD")
    input_price_per_million: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False, default=0, server_default="0")
    output_price_per_million: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False, default=0, server_default="0")
    cached_input_price_per_million: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False, default=0, server_default="0")
    embedding_price_per_million: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False, default=0, server_default="0")
    additional_billing: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    pricing_version: Mapped[str] = mapped_column(String(40), nullable=False, default="unpriced-v1", server_default="unpriced-v1")
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class QuotaPolicy(Base):
    __tablename__ = "quota_policies"
    __table_args__ = (
        UniqueConstraint("scope", "scope_key", name="uq_quota_policies_scope"),
        CheckConstraint("scope IN ('global','role')", name="ck_quota_policies_scope"),
        CheckConstraint("requests_per_minute IS NULL OR requests_per_minute >= 0", name="ck_quota_rpm"),
        CheckConstraint("daily_token_limit IS NULL OR daily_token_limit >= 0", name="ck_quota_daily_tokens"),
    )
    id: Mapped[UUID] = uuid_column()
    scope: Mapped[str] = mapped_column(String(20), nullable=False, default="global", server_default="global")
    scope_key: Mapped[str] = mapped_column(String(50), nullable=False, default="default", server_default="default")
    requests_per_minute: Mapped[int | None] = mapped_column(Integer)
    requests_per_hour: Mapped[int | None] = mapped_column(Integer)
    daily_token_limit: Mapped[int | None] = mapped_column(Integer)
    monthly_token_limit: Mapped[int | None] = mapped_column(Integer)
    daily_spend_limit: Mapped[float | None] = mapped_column(Numeric(18, 8))
    concurrent_generation_limit: Mapped[int | None] = mapped_column(Integer)
    document_count_limit: Mapped[int | None] = mapped_column(Integer)
    storage_size_limit_bytes: Mapped[int | None] = mapped_column(Integer)
    embedding_token_budget: Mapped[int | None] = mapped_column(Integer)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    updated_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class UserQuotaOverride(Base):
    __tablename__ = "user_quota_overrides"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    limits: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    updated_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class UsageAggregateDaily(Base):
    __tablename__ = "usage_aggregates_daily"
    __table_args__ = (
        UniqueConstraint("usage_date", "user_id", "model", name="uq_usage_aggregate_daily"),
        Index("ix_usage_aggregate_date", "usage_date"),
    )
    id: Mapped[UUID] = uuid_column()
    usage_date: Mapped[date] = mapped_column(nullable=False)
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    completed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    cached_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    embedding_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    estimated_cost: Mapped[float | None] = mapped_column(Numeric(18, 8))
    rebuilt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class SystemHealthSnapshot(Base):
    __tablename__ = "system_health_snapshots"
    __table_args__ = (Index("ix_health_snapshots_component_checked", "component", "checked_at"),)
    id: Mapped[UUID] = uuid_column()
    component: Mapped[str] = mapped_column(String(60), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    detail_safe: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class AdminMFACredential(Base):
    __tablename__ = "admin_mfa_credentials"
    __table_args__ = (UniqueConstraint("user_id", name="uq_admin_mfa_user"),)
    id: Mapped[UUID] = uuid_column()
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    encrypted_secret: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_counter: Mapped[int | None] = mapped_column(Integer)
    failed_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class AdminRecoveryCode(Base):
    __tablename__ = "admin_recovery_codes"
    __table_args__ = (Index("ix_admin_recovery_codes_credential", "mfa_credential_id", "used_at"),)
    id: Mapped[UUID] = uuid_column()
    mfa_credential_id: Mapped[UUID] = mapped_column(ForeignKey("admin_mfa_credentials.id", ondelete="CASCADE"), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Plan(Base):
    __tablename__ = "plans"
    __table_args__ = (
        CheckConstraint("code IN ('free', 'pro', 'business') OR length(trim(code)) > 0", name="ck_plans_code"),
        Index("ix_plans_enabled_order", "enabled", "sort_order"),
    )
    id: Mapped[UUID] = uuid_column()
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class PlanEntitlement(Base):
    __tablename__ = "plan_entitlements"
    __table_args__ = (UniqueConstraint("plan_id", "feature", name="uq_plan_entitlements_feature"),)
    id: Mapped[UUID] = uuid_column()
    plan_id: Mapped[UUID] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"), nullable=False)
    feature: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class Subscription(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (
        Index("ix_subscriptions_user_status", "user_id", "status"),
        CheckConstraint("status IN ('active', 'trialing', 'past_due', 'canceled', 'incomplete')", name="ck_subscriptions_status"),
    )
    id: Mapped[UUID] = uuid_column()
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    plan_id: Mapped[UUID] = mapped_column(ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", server_default="active")
    provider: Mapped[str | None] = mapped_column(String(40))
    provider_customer_ref: Mapped[str | None] = mapped_column(String(200))
    provider_subscription_ref: Mapped[str | None] = mapped_column(String(200), unique=True)
    current_period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class FeatureFlag(Base):
    __tablename__ = "feature_flags"
    __table_args__ = (
        CheckConstraint("rollout_percent >= 0 AND rollout_percent <= 100", name="ck_feature_flags_rollout"),
        Index("ix_feature_flags_enabled", "enabled"),
    )
    id: Mapped[UUID] = uuid_column()
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    admin_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    rollout_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    plan_codes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    user_allowlist: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    updated_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class UserFeedback(Base):
    __tablename__ = "user_feedback"
    __table_args__ = (Index("ix_user_feedback_user_created", "user_id", "created_at"),)
    id: Mapped[UUID] = uuid_column()
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    rating: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class SupportTicket(Base):
    __tablename__ = "support_tickets"
    __table_args__ = (
        Index("ix_support_tickets_user_status", "user_id", "status", "updated_at"),
        CheckConstraint("status IN ('open', 'pending', 'resolved', 'closed')", name="ck_support_tickets_status"),
        CheckConstraint("priority IN ('low', 'normal', 'high', 'urgent')", name="ck_support_tickets_priority"),
    )
    id: Mapped[UUID] = uuid_column()
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    ticket_number: Mapped[str] = mapped_column(String(24), unique=True, nullable=False)
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="normal", server_default="normal")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", server_default="open")
    assigned_to: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class SupportTicketMessage(Base):
    __tablename__ = "support_ticket_messages"
    __table_args__ = (Index("ix_support_ticket_messages_ticket_created", "ticket_id", "created_at"),)
    id: Mapped[UUID] = uuid_column()
    ticket_id: Mapped[UUID] = mapped_column(ForeignKey("support_tickets.id", ondelete="CASCADE"), nullable=False)
    author_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_internal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class IncidentRecord(Base):
    __tablename__ = "incident_records"
    __table_args__ = (Index("ix_incident_records_status_created", "status", "created_at"),)
    id: Mapped[UUID] = uuid_column()
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="minor", server_default="minor")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="investigating", server_default="investigating")
    owner_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    details_safe: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class DataPrivacyRequest(Base):
    __tablename__ = "data_privacy_requests"
    __table_args__ = (
        Index("ix_privacy_requests_user_status", "user_id", "status", "created_at"),
        UniqueConstraint("user_id", "request_type", "idempotency_key", name="uq_privacy_request_idempotency"),
        CheckConstraint("request_type IN ('export', 'delete')", name="ck_privacy_request_type"),
        CheckConstraint("status IN ('queued', 'processing', 'completed', 'failed', 'cancelled')", name="ck_privacy_request_status"),
    )
    id: Mapped[UUID] = uuid_column()
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    request_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued", server_default="queued")
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    result_storage_key: Mapped[str | None] = mapped_column(String(500))
    error_code: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Organization(Base):
    __tablename__ = "organizations"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_organizations_slug"),
        CheckConstraint("length(trim(name)) > 0", name="ck_organizations_name_not_blank"),
        CheckConstraint("status IN ('active','suspended','deleted')", name="ck_organizations_status"),
        Index("ix_organizations_owner_status", "owner_id", "status", "created_at"),
    )
    id: Mapped[UUID] = uuid_column()
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    logo_url: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", server_default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class OrganizationMembership(Base):
    __tablename__ = "organization_memberships"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_org_memberships_org_user"),
        CheckConstraint("role IN ('owner','admin','member','viewer')", name="ck_org_memberships_role"),
        CheckConstraint("status IN ('active','suspended','removed')", name="ck_org_memberships_status"),
        Index("ix_org_memberships_user_status", "user_id", "status", "organization_id"),
        Index("ix_org_memberships_org_status", "organization_id", "status", "role"),
    )
    id: Mapped[UUID] = uuid_column()
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="member", server_default="member")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", server_default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class OrganizationInvitation(Base):
    __tablename__ = "organization_invitations"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_org_invitations_token_hash"),
        CheckConstraint("role IN ('admin','member','viewer')", name="ck_org_invitations_role"),
        Index("ix_org_invitations_org_status", "organization_id", "expires_at", "accepted_at", "revoked_at"),
    )
    id: Mapped[UUID] = uuid_column()
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    invited_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    email_normalized: Mapped[str] = mapped_column(String(320), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="member", server_default="member")
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    declined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class OrganizationSetting(Base):
    __tablename__ = "organization_settings"
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True)
    settings: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"
    __table_args__ = (
        UniqueConstraint("organization_id", "normalized_name", name="uq_knowledge_bases_org_name"),
        CheckConstraint("length(trim(name)) > 0", name="ck_knowledge_bases_name_not_blank"),
        Index("ix_knowledge_bases_org_status", "organization_id", "status", "updated_at"),
    )
    id: Mapped[UUID] = uuid_column()
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", server_default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class KnowledgeBaseDocument(Base):
    __tablename__ = "knowledge_base_documents"
    __table_args__ = (UniqueConstraint("knowledge_base_id", "document_id", name="uq_kb_documents"), Index("ix_kb_documents_document", "document_id"))
    id: Mapped[UUID] = uuid_column()
    knowledge_base_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    attached_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class OrganizationSubscription(Base):
    __tablename__ = "organization_subscriptions"
    __table_args__ = (UniqueConstraint("organization_id", name="uq_org_subscriptions_org"), CheckConstraint("status IN ('active','trialing','past_due','canceled','incomplete')", name="ck_org_subscriptions_status"))
    id: Mapped[UUID] = uuid_column()
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    plan_id: Mapped[UUID] = mapped_column(ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False)
    billing_owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", server_default="active")
    seat_limit: Mapped[int | None] = mapped_column(Integer)
    current_period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class OrganizationUsage(Base):
    __tablename__ = "organization_usage"
    __table_args__ = (UniqueConstraint("organization_id", "usage_date", "model", name="uq_org_usage_day_model"), Index("ix_org_usage_org_date", "organization_id", "usage_date"))
    id: Mapped[UUID] = uuid_column()
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    usage_date: Mapped[date] = mapped_column(nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    completed_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    estimated_cost: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class OrganizationAuditLog(Base):
    __tablename__ = "organization_audit_logs"
    __table_args__ = (Index("ix_org_audit_org_created", "organization_id", "created_at", "id"),)
    id: Mapped[UUID] = uuid_column()
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    actor_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(60))
    target_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    metadata_safe: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
