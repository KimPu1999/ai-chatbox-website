"""Protect organization-scoped rows in existing shared resource tables."""

# ruff: noqa: E501

import sqlalchemy as sa
from alembic import op

revision = "0015_phase12_tenant_rls_existing"
down_revision = "0014_phase12_multi_tenant"
branch_labels = None
depends_on = None


def upgrade() -> None:
    tables = (
        "conversations",
        "messages",
        "generation_runs",
        "ai_usage",
        "documents",
        "document_chunks",
        "document_processing_jobs",
        "conversation_documents",
    )
    for table in tables:
        op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
        op.execute(sa.text(f"CREATE POLICY {table}_organization_policy ON {table} USING (organization_id IS NULL OR organization_id::text = current_setting('app.current_organization_id', true)) WITH CHECK (organization_id IS NULL OR organization_id::text = current_setting('app.current_organization_id', true))"))


def downgrade() -> None:
    tables = (
        "conversations",
        "messages",
        "generation_runs",
        "ai_usage",
        "documents",
        "document_chunks",
        "document_processing_jobs",
        "conversation_documents",
    )
    for table in tables:
        op.execute(sa.text(f"DROP POLICY IF EXISTS {table}_organization_policy ON {table}"))
