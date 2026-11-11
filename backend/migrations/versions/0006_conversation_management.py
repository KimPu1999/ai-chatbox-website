"""Add folders, cursor history metadata, search indexes, bulk jobs, and shares."""

# Alembic constraint/index declarations are kept close to their database names.
# ruff: noqa: E501

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006_conversation_management"
down_revision = "0005_generation_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)

    op.create_table(
        "conversation_folders",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("user_id", uuid, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("normalized_name", sa.String(100), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("id", "user_id", name="uq_conversation_folders_id_user"),
        sa.UniqueConstraint("user_id", "normalized_name", name="uq_conversation_folders_user_name"),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_conversation_folders_name_not_blank"),
        sa.CheckConstraint(
            "length(normalized_name) > 0", name="ck_conversation_folders_normalized_name"
        ),
    )
    op.create_index(
        "ix_conversation_folders_user_sort",
        "conversation_folders",
        ["user_id", "sort_order", "created_at", "id"],
    )

    op.add_column("conversations", sa.Column("folder_id", uuid, nullable=True))
    op.add_column(
        "conversations", sa.Column("pinned_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "conversations",
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute("UPDATE conversations SET pinned_at = updated_at WHERE is_pinned = true")
    op.execute(
        "UPDATE conversations c SET last_message_at = x.last_message_at "
        "FROM (SELECT conversation_id, max(created_at) AS last_message_at FROM messages GROUP BY conversation_id) x "
        "WHERE c.id = x.conversation_id"
    )
    op.create_foreign_key(
        "fk_conversations_folder_user",
        "conversations",
        "conversation_folders",
        ["folder_id", "user_id"],
        ["id", "user_id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_conversations_user_folder",
        "conversations",
        ["user_id", "folder_id", "updated_at", "id"],
    )
    op.create_index(
        "ix_conversations_user_pinned",
        "conversations",
        ["user_id", "pinned_at", "updated_at", "id"],
    )

    op.add_column(
        "conversations",
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('simple', coalesce(title, ''))", persisted=True),
        ),
    )
    op.add_column(
        "messages",
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('simple', coalesce(content, ''))", persisted=True),
        ),
    )
    op.create_index(
        "ix_conversations_search_vector",
        "conversations",
        ["search_vector"],
        postgresql_using="gin",
    )
    op.create_index(
        "ix_messages_search_vector",
        "messages",
        ["search_vector"],
        postgresql_using="gin",
    )

    op.create_table(
        "conversation_shares",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("owner_id", uuid, nullable=False),
        sa.Column("conversation_id", uuid, nullable=False),
        sa.Column("token_hash", sa.String(128), nullable=False, unique=True),
        sa.Column("snapshot_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("password_hash", sa.String(255)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("last_accessed_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["conversation_id", "owner_id"],
            ["conversations.id", "conversations.user_id"],
            ondelete="CASCADE",
            name="fk_conversation_shares_conversation_owner",
        ),
    )
    op.create_index(
        "ix_conversation_shares_owner_created",
        "conversation_shares",
        ["owner_id", "created_at", "id"],
    )
    op.create_index(
        "ix_conversation_shares_expires_revoked",
        "conversation_shares",
        ["expires_at", "revoked_at"],
    )

    op.create_table(
        "conversation_bulk_jobs",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("user_id", uuid, nullable=False),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("total_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("processed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_summary", sa.String(500)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "action IN ('archive','unarchive','pin','unpin','move_to_folder','soft_delete','restore')",
            name="ck_conversation_bulk_jobs_action",
        ),
        sa.CheckConstraint(
            "status IN ('queued','running','completed','failed')",
            name="ck_conversation_bulk_jobs_status",
        ),
        sa.CheckConstraint("total_count >= 0 AND processed_count >= 0", name="ck_bulk_job_counts"),
    )
    op.create_index(
        "ix_conversation_bulk_jobs_user_status",
        "conversation_bulk_jobs",
        ["user_id", "status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_conversation_bulk_jobs_user_status", table_name="conversation_bulk_jobs")
    op.drop_table("conversation_bulk_jobs")
    op.drop_index("ix_conversation_shares_expires_revoked", table_name="conversation_shares")
    op.drop_index("ix_conversation_shares_owner_created", table_name="conversation_shares")
    op.drop_table("conversation_shares")
    op.drop_index("ix_messages_search_vector", table_name="messages")
    op.drop_index("ix_conversations_search_vector", table_name="conversations")
    op.drop_column("messages", "search_vector")
    op.drop_column("conversations", "search_vector")
    op.drop_index("ix_conversations_user_pinned", table_name="conversations")
    op.drop_index("ix_conversations_user_folder", table_name="conversations")
    op.drop_constraint("fk_conversations_folder_user", "conversations", type_="foreignkey")
    op.drop_column("conversations", "last_message_at")
    op.drop_column("conversations", "pinned_at")
    op.drop_column("conversations", "folder_id")
    op.drop_index("ix_conversation_folders_user_sort", table_name="conversation_folders")
    op.drop_table("conversation_folders")
