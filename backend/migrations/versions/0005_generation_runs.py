"""Add generation lifecycle and provider usage metadata."""

import sqlalchemy as sa
from alembic import op

revision = "0005_generation_runs"
down_revision = "0004_chat_workspace"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "generation_runs",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="queued"),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("provider_response_id", sa.String(length=200)),
        sa.Column("error_code", sa.String(length=80)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["conversation_id", "user_id"],
            ["conversations.id", "conversations.user_id"],
            ondelete="CASCADE",
            name="fk_generation_runs_conversation_user",
        ),
        sa.UniqueConstraint("id", "user_id", name="uq_generation_runs_id_user"),
        sa.UniqueConstraint(
            "user_id", "idempotency_key", name="uq_generation_runs_user_idempotency"
        ),
        sa.CheckConstraint(
            "status IN ('queued','streaming','completed','cancelled','failed','incomplete')",
            name="ck_generation_runs_status",
        ),
    )
    op.create_index(
        "ix_generation_runs_user_status", "generation_runs", ["user_id", "status", "created_at"]
    )
    op.create_index(
        "ix_generation_runs_conversation_created",
        "generation_runs",
        ["conversation_id", "created_at"],
    )
    op.add_column("messages", sa.Column("generation_run_id", sa.UUID(), nullable=True))
    op.add_column(
        "messages",
        sa.Column("status", sa.String(length=20), nullable=False, server_default="completed"),
    )
    op.add_column(
        "messages", sa.Column("sequence", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column(
        "messages", sa.Column("version", sa.Integer(), nullable=False, server_default="1")
    )
    op.add_column("messages", sa.Column("superseded_at", sa.DateTime(timezone=True)))
    op.create_foreign_key(
        "fk_messages_generation_run_user",
        "messages",
        "generation_runs",
        ["generation_run_id", "user_id"],
        ["id", "user_id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "ck_messages_status",
        "messages",
        "status IN ('completed','streaming','failed','superseded')",
    )
    op.add_column("ai_usage", sa.Column("generation_run_id", sa.UUID(), nullable=True))
    op.add_column(
        "ai_usage", sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column(
        "ai_usage",
        sa.Column("cached_input_tokens", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "ai_usage", sa.Column("reasoning_tokens", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column("ai_usage", sa.Column("estimated_cost", sa.Numeric(18, 8)))
    op.add_column("ai_usage", sa.Column("pricing_version", sa.String(length=40)))
    op.add_column(
        "ai_usage",
        sa.Column("usage_confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("ai_usage", sa.Column("provider_response_id", sa.String(length=200)))
    op.create_foreign_key(
        "fk_ai_usage_generation_run_user",
        "ai_usage",
        "generation_runs",
        ["generation_run_id", "user_id"],
        ["id", "user_id"],
        ondelete="CASCADE",
    )
    op.create_unique_constraint("uq_ai_usage_generation_run", "ai_usage", ["generation_run_id"])


def downgrade() -> None:
    op.drop_constraint("uq_ai_usage_generation_run", "ai_usage", type_="unique")
    op.drop_constraint("fk_ai_usage_generation_run_user", "ai_usage", type_="foreignkey")
    for column in (
        "provider_response_id",
        "usage_confirmed",
        "pricing_version",
        "estimated_cost",
        "reasoning_tokens",
        "cached_input_tokens",
        "total_tokens",
        "generation_run_id",
    ):
        op.drop_column("ai_usage", column)
    op.drop_constraint("ck_messages_status", "messages", type_="check")
    op.drop_constraint("fk_messages_generation_run_user", "messages", type_="foreignkey")
    for column in ("superseded_at", "version", "sequence", "status", "generation_run_id"):
        op.drop_column("messages", column)
    op.drop_index("ix_generation_runs_conversation_created", table_name="generation_runs")
    op.drop_index("ix_generation_runs_user_status", table_name="generation_runs")
    op.drop_constraint("uq_generation_runs_id_user", "generation_runs", type_="unique")
    op.drop_table("generation_runs")
