"""Add chat workspace lifecycle fields."""

import sqlalchemy as sa
from alembic import op

revision = "0004_chat_workspace"
down_revision = "0003_authentication"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("conversations", sa.Column("deleted_at", sa.DateTime(timezone=True)))
    op.add_column(
        "conversations",
        sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index(
        "ix_conversations_user_deleted_updated",
        "conversations",
        ["user_id", "deleted_at", "updated_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_conversations_user_deleted_updated", table_name="conversations")
    op.drop_column("conversations", "is_pinned")
    op.drop_column("conversations", "deleted_at")
