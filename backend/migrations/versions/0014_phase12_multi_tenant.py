# ruff: noqa: E501

"""Add additive organization and knowledge-base tenancy primitives.

Personal rows remain organization_id NULL.  No historical personal resource is
assigned to an organization by this migration.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0014_phase12_multi_tenant"
down_revision = "0013_phase11_plan_catalog"
branch_labels = None
depends_on = None


def _uuid():
    return postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", _uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("owner_id", _uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.String(500)),
        sa.Column("logo_url", sa.String(500)),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("slug", name="uq_organizations_slug"),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_organizations_name_not_blank"),
        sa.CheckConstraint("status IN ('active','suspended','deleted')", name="ck_organizations_status"),
    )
    op.create_index("ix_organizations_owner_status", "organizations", ["owner_id", "status", "created_at"])
    op.create_table(
        "organization_memberships",
        sa.Column("id", _uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", _uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", _uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="member"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_org_memberships_org_user"),
        sa.CheckConstraint("role IN ('owner','admin','member','viewer')", name="ck_org_memberships_role"),
        sa.CheckConstraint("status IN ('active','suspended','removed')", name="ck_org_memberships_status"),
    )
    op.create_index("ix_org_memberships_user_status", "organization_memberships", ["user_id", "status", "organization_id"])
    op.create_index("ix_org_memberships_org_status", "organization_memberships", ["organization_id", "status", "role"])
    op.create_table(
        "organization_invitations",
        sa.Column("id", _uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", _uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("invited_by", _uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("email_normalized", sa.String(320), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="member"),
        sa.Column("token_hash", sa.String(128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
        sa.Column("declined_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("token_hash", name="uq_org_invitations_token_hash"),
        sa.CheckConstraint("role IN ('admin','member','viewer')", name="ck_org_invitations_role"),
    )
    op.create_index("ix_org_invitations_org_status", "organization_invitations", ["organization_id", "expires_at", "accepted_at", "revoked_at"])
    op.create_table(
        "organization_settings",
        sa.Column("organization_id", _uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("settings", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "knowledge_bases",
        sa.Column("id", _uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", _uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by", _uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("normalized_name", sa.String(160), nullable=False),
        sa.Column("description", sa.String(500)),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "normalized_name", name="uq_knowledge_bases_org_name"),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_knowledge_bases_name_not_blank"),
    )
    op.create_index("ix_knowledge_bases_org_status", "knowledge_bases", ["organization_id", "status", "updated_at"])
    op.create_table(
        "knowledge_base_documents",
        sa.Column("id", _uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("knowledge_base_id", _uuid(), sa.ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_id", _uuid(), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("attached_by", _uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("knowledge_base_id", "document_id", name="uq_kb_documents"),
    )
    op.create_index("ix_kb_documents_document", "knowledge_base_documents", ["document_id"])
    op.create_table(
        "organization_subscriptions",
        sa.Column("id", _uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", _uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plan_id", _uuid(), sa.ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("billing_owner_id", _uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("seat_limit", sa.Integer()),
        sa.Column("current_period_start", sa.DateTime(timezone=True)),
        sa.Column("current_period_end", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", name="uq_org_subscriptions_org"),
        sa.CheckConstraint("status IN ('active','trialing','past_due','canceled','incomplete')", name="ck_org_subscriptions_status"),
    )
    op.create_table(
        "organization_usage",
        sa.Column("id", _uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", _uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("usage_date", sa.Date(), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_cost", sa.Numeric(18, 8), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "usage_date", "model", name="uq_org_usage_day_model"),
    )
    op.create_index("ix_org_usage_org_date", "organization_usage", ["organization_id", "usage_date"])
    op.create_table(
        "organization_audit_logs",
        sa.Column("id", _uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", _uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_user_id", _uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("target_type", sa.String(60)),
        sa.Column("target_id", _uuid()),
        sa.Column("metadata_safe", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_org_audit_org_created", "organization_audit_logs", ["organization_id", "created_at", "id"])

    for table in ("conversations", "messages", "generation_runs", "ai_usage", "documents", "document_chunks", "document_processing_jobs", "conversation_documents"):
        op.add_column(table, sa.Column("organization_id", _uuid(), nullable=True))
        op.create_index(f"ix_{table}_organization", table, ["organization_id"])

    # Tenant tables are protected by a transaction-local context. Personal rows
    # remain accessible with organization_id NULL for backwards compatibility.
    for table in ("organization_memberships", "organization_invitations", "organization_settings", "knowledge_bases", "organization_subscriptions", "organization_usage", "organization_audit_logs"):
        op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
        op.execute(sa.text(f"CREATE POLICY {table}_tenant_policy ON {table} USING (organization_id::text = current_setting('app.current_organization_id', true)) WITH CHECK (organization_id::text = current_setting('app.current_organization_id', true))"))
    op.execute(sa.text("ALTER TABLE knowledge_base_documents ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text("CREATE POLICY knowledge_base_documents_tenant_policy ON knowledge_base_documents USING (knowledge_base_id IN (SELECT id FROM knowledge_bases WHERE organization_id::text = current_setting('app.current_organization_id', true))) WITH CHECK (knowledge_base_id IN (SELECT id FROM knowledge_bases WHERE organization_id::text = current_setting('app.current_organization_id', true)))"))
    op.execute(sa.text("ALTER TABLE organizations ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text("CREATE POLICY organizations_tenant_policy ON organizations USING (id::text = current_setting('app.current_organization_id', true)) WITH CHECK (id::text = current_setting('app.current_organization_id', true))"))


def downgrade() -> None:
    raise RuntimeError("Phase 12 migration is additive; restore a database backup before rollback.")
