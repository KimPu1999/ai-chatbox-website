"""Prevent composite folder deletion from nulling the conversation owner."""

from alembic import op

revision = "0007_fix_folder_ownership_fk"
down_revision = "0006_conversation_management"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("fk_conversations_folder_user", "conversations", type_="foreignkey")
    op.create_foreign_key(
        "fk_conversations_folder_user",
        "conversations",
        "conversation_folders",
        ["folder_id", "user_id"],
        ["id", "user_id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_conversations_folder_user", "conversations", type_="foreignkey")
    op.create_foreign_key(
        "fk_conversations_folder_user",
        "conversations",
        "conversation_folders",
        ["folder_id", "user_id"],
        ["id", "user_id"],
        ondelete="SET NULL",
    )
