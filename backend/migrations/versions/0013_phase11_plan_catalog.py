"""Ensure the configurable Phase 11 plan catalog contains all initial tiers."""

# ruff: noqa: E501

from alembic import op

revision = "0013_phase11_plan_catalog"
down_revision = "0012_phase11_saas_operations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "INSERT INTO plans (id, code, name, description, sort_order) VALUES "
        "(gen_random_uuid(), 'pro', 'Pro', 'Configurable paid plan catalog entry', 10), "
        "(gen_random_uuid(), 'business', 'Business', 'Configurable business plan catalog entry', 20) "
        "ON CONFLICT (code) DO NOTHING"
    )


def downgrade() -> None:
    op.execute("DELETE FROM plans WHERE code IN ('pro', 'business')")
