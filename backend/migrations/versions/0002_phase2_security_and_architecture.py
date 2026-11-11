"""Add Phase 2 security, ownership, settings, audit, and reset-token structures."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_phase2"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def timestamp() -> sa.Column:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)

    op.add_column("users", sa.Column("email_normalized", sa.String(320), nullable=True))
    op.execute(
        "UPDATE users SET email_normalized = lower(trim(email)) WHERE email_normalized IS NULL"
    )
    op.alter_column("users", "email_normalized", nullable=False)
    op.add_column("users", sa.Column("password_hash", sa.String(255), nullable=True))
    op.add_column(
        "users", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true())
    )
    op.add_column(
        "users",
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
    op.create_unique_constraint("uq_users_email_normalized", "users", ["email_normalized"])
    op.create_check_constraint(
        "ck_users_email_normalized_length", "users", "length(email_normalized) > 3"
    )

    op.add_column("sessions", sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_sessions_user_expires", "sessions", ["user_id", "expires_at"])

    op.add_column(
        "conversations", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_unique_constraint("uq_conversations_id_user", "conversations", ["id", "user_id"])
    op.create_check_constraint(
        "ck_conversations_title_not_blank", "conversations", "length(trim(title)) > 0"
    )
    op.create_index(
        "ix_conversations_user_updated", "conversations", ["user_id", "updated_at", "id"]
    )

    op.add_column("messages", sa.Column("user_id", uuid, nullable=True))
    op.add_column(
        "messages", sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column(
        "messages", sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0")
    )
    op.execute(
        "UPDATE messages m SET user_id = c.user_id FROM conversations c "
        "WHERE c.id = m.conversation_id"
    )
    op.alter_column("messages", "user_id", nullable=False)
    op.create_foreign_key(
        "fk_messages_conversation_user",
        "messages",
        "conversations",
        ["conversation_id", "user_id"],
        ["id", "user_id"],
        ondelete="CASCADE",
    )
    op.create_unique_constraint("uq_messages_id_user", "messages", ["id", "user_id"])
    op.create_check_constraint(
        "ck_messages_role", "messages", "role IN ('user', 'assistant', 'system')"
    )
    op.create_check_constraint("ck_messages_content_not_empty", "messages", "length(content) > 0")
    op.create_index(
        "ix_messages_conversation_created", "messages", ["conversation_id", "created_at", "id"]
    )

    op.add_column("ai_usage", sa.Column("latency_ms", sa.Integer(), nullable=True))
    op.execute(
        "UPDATE ai_usage u SET user_id = m.user_id FROM messages m WHERE m.id = u.message_id"
    )
    op.create_foreign_key(
        "fk_ai_usage_message_user",
        "ai_usage",
        "messages",
        ["message_id", "user_id"],
        ["id", "user_id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_ai_usage_user_created", "ai_usage", ["user_id", "created_at", "id"])
    op.create_check_constraint(
        "ck_ai_usage_prompt_tokens_nonnegative", "ai_usage", "prompt_tokens >= 0"
    )
    op.create_check_constraint(
        "ck_ai_usage_completion_tokens_nonnegative", "ai_usage", "completion_tokens >= 0"
    )

    op.add_column(
        "attachments", sa.Column("byte_size", sa.Integer(), nullable=False, server_default="0")
    )
    op.execute(
        "UPDATE attachments a SET user_id = m.user_id FROM messages m "
        "WHERE m.id = a.message_id AND a.user_id <> m.user_id"
    )
    op.create_foreign_key(
        "fk_attachments_message_user",
        "attachments",
        "messages",
        ["message_id", "user_id"],
        ["id", "user_id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_attachments_user_created", "attachments", ["user_id", "created_at", "id"])
    op.create_check_constraint(
        "ck_attachments_byte_size_nonnegative", "attachments", "byte_size >= 0"
    )

    op.create_check_constraint(
        "ck_user_settings_theme", "user_settings", "theme IN ('system', 'light', 'dark')"
    )
    op.create_table(
        "ai_model_settings",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("user_id", uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("parameters", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default=sa.false()),
        timestamp(),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("user_id", "model", name="uq_ai_model_settings_user_model"),
    )
    op.create_table(
        "audit_logs",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("user_id", uuid, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(100), nullable=False),
        sa.Column("entity_id", uuid),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        timestamp(),
    )
    op.create_index("ix_audit_logs_user_created", "audit_logs", ["user_id", "created_at", "id"])
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("user_id", uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(128), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        timestamp(),
    )
    op.create_index(
        "ix_password_reset_tokens_user_expires", "password_reset_tokens", ["user_id", "expires_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_password_reset_tokens_user_expires", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
    op.drop_index("ix_audit_logs_user_created", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_table("ai_model_settings")
    op.drop_constraint("ck_user_settings_theme", "user_settings", type_="check")
    op.drop_constraint("ck_attachments_byte_size_nonnegative", "attachments", type_="check")
    op.drop_index("ix_attachments_user_created", table_name="attachments")
    op.drop_constraint("fk_attachments_message_user", "attachments", type_="foreignkey")
    op.drop_column("attachments", "byte_size")
    op.drop_constraint("ck_ai_usage_completion_tokens_nonnegative", "ai_usage", type_="check")
    op.drop_constraint("ck_ai_usage_prompt_tokens_nonnegative", "ai_usage", type_="check")
    op.drop_index("ix_ai_usage_user_created", table_name="ai_usage")
    op.drop_constraint("fk_ai_usage_message_user", "ai_usage", type_="foreignkey")
    op.drop_column("ai_usage", "latency_ms")
    op.drop_index("ix_messages_conversation_created", table_name="messages")
    op.drop_constraint("ck_messages_content_not_empty", "messages", type_="check")
    op.drop_constraint("ck_messages_role", "messages", type_="check")
    op.drop_constraint("uq_messages_id_user", "messages", type_="unique")
    op.drop_constraint("fk_messages_conversation_user", "messages", type_="foreignkey")
    op.drop_column("messages", "completion_tokens")
    op.drop_column("messages", "prompt_tokens")
    op.drop_column("messages", "user_id")
    op.drop_index("ix_conversations_user_updated", table_name="conversations")
    op.drop_constraint("ck_conversations_title_not_blank", "conversations", type_="check")
    op.drop_constraint("uq_conversations_id_user", "conversations", type_="unique")
    op.drop_column("conversations", "archived_at")
    op.drop_index("ix_sessions_user_expires", table_name="sessions")
    op.drop_column("sessions", "revoked_at")
    op.drop_constraint("ck_users_email_normalized_length", "users", type_="check")
    op.drop_constraint("uq_users_email_normalized", "users", type_="unique")
    op.drop_column("users", "last_login_at")
    op.drop_column("users", "updated_at")
    op.drop_column("users", "is_active")
    op.drop_column("users", "password_hash")
    op.drop_column("users", "email_normalized")
