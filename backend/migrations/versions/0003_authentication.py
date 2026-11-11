"""Add authentication, verification, roles, and session security fields."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003_authentication"
down_revision = "0002_phase2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("role", sa.String(20), nullable=False, server_default="user"))
    op.add_column(
        "users",
        sa.Column(
            "account_status", sa.String(30), nullable=False, server_default="pending_verification"
        ),
    )
    op.add_column("users", sa.Column("email_verified_at", sa.DateTime(timezone=True)))
    op.create_check_constraint("ck_users_role", "users", "role IN ('user', 'admin', 'superadmin')")
    op.create_check_constraint(
        "ck_users_account_status",
        "users",
        "account_status IN ('pending_verification', 'active', 'suspended', 'deleted')",
    )
    op.create_index("ix_users_status_role", "users", ["account_status", "role"])
    op.add_column(
        "sessions",
        sa.Column(
            "last_activity_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.add_column("sessions", sa.Column("csrf_token_hash", sa.String(128)))
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "email_verification_tokens",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("user_id", uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(128), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_email_verification_tokens_user_expires",
        "email_verification_tokens",
        ["user_id", "expires_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_email_verification_tokens_user_expires", table_name="email_verification_tokens"
    )
    op.drop_table("email_verification_tokens")
    op.drop_column("sessions", "csrf_token_hash")
    op.drop_column("sessions", "last_activity_at")
    op.drop_index("ix_users_status_role", table_name="users")
    op.drop_constraint("ck_users_account_status", "users", type_="check")
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.drop_column("users", "email_verified_at")
    op.drop_column("users", "account_status")
    op.drop_column("users", "role")
