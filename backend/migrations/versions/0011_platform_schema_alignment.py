"""Align the named MFA uniqueness constraint for deterministic schema checks."""

from alembic import op

revision = "0011_platform_schema_alignment"
down_revision = "0010_platform_admin"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conrelid = 'admin_mfa_credentials'::regclass
                  AND conname = 'admin_mfa_credentials_user_id_key'
            ) AND NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conrelid = 'admin_mfa_credentials'::regclass
                  AND conname = 'uq_admin_mfa_user'
            ) THEN
                ALTER TABLE admin_mfa_credentials
                RENAME CONSTRAINT admin_mfa_credentials_user_id_key TO uq_admin_mfa_user;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conrelid = 'admin_mfa_credentials'::regclass
                  AND conname = 'uq_admin_mfa_user'
            ) THEN
                ALTER TABLE admin_mfa_credentials
                RENAME CONSTRAINT uq_admin_mfa_user TO admin_mfa_credentials_user_id_key;
            END IF;
        END $$;
        """
    )
