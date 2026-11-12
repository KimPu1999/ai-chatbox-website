"""Add Phase 11 SaaS plans, operations, support and privacy workflows.

All changes are additive. Existing accounts are assigned the seeded free plan
through active subscriptions; no payment provider is enabled by this migration.
"""

# ruff: noqa: E501

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0012_phase11_saas_operations"
down_revision = "0011_platform_schema_alignment"
branch_labels = None
depends_on = None


def _uuid():
    return postgresql.UUID(as_uuid=True)


def _jsonb(name, default):
    return sa.Column(
        name,
        postgresql.JSONB,
        nullable=False,
        server_default=sa.text(f"'{default}'::jsonb"),
        default=default,
    )


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.create_table(
        "plans",
        sa.Column("id", _uuid(), primary_key=True),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("length(trim(code)) > 0", name="ck_plans_code"),
        sa.UniqueConstraint("code", name="uq_plans_code"),
    )
    op.create_index("ix_plans_enabled_order", "plans", ["enabled", "sort_order"])
    op.create_table(
        "plan_entitlements",
        sa.Column("id", _uuid(), primary_key=True),
        sa.Column("plan_id", _uuid(), sa.ForeignKey("plans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("feature", sa.String(100), nullable=False),
        _jsonb("value", "{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("plan_id", "feature", name="uq_plan_entitlements_feature"),
    )
    op.create_table(
        "subscriptions",
        sa.Column("id", _uuid(), primary_key=True),
        sa.Column("user_id", _uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plan_id", _uuid(), sa.ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("provider", sa.String(40)),
        sa.Column("provider_customer_ref", sa.String(200)),
        sa.Column("provider_subscription_ref", sa.String(200), unique=True),
        sa.Column("current_period_start", sa.DateTime(timezone=True)),
        sa.Column("current_period_end", sa.DateTime(timezone=True)),
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('active','trialing','past_due','canceled','incomplete')", name="ck_subscriptions_status"),
    )
    op.create_index("ix_subscriptions_user_status", "subscriptions", ["user_id", "status"])
    op.create_table(
        "feature_flags",
        sa.Column("id", _uuid(), primary_key=True),
        sa.Column("key", sa.String(100), nullable=False, unique=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("admin_only", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("rollout_percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("plan_codes", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("user_allowlist", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("updated_by", _uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("rollout_percent >= 0 AND rollout_percent <= 100", name="ck_feature_flags_rollout"),
    )
    op.create_index("ix_feature_flags_enabled", "feature_flags", ["enabled"])
    op.create_table(
        "user_feedback",
        sa.Column("id", _uuid(), primary_key=True),
        sa.Column("user_id", _uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("rating", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_user_feedback_user_created", "user_feedback", ["user_id", "created_at"])
    op.create_table(
        "support_tickets",
        sa.Column("id", _uuid(), primary_key=True),
        sa.Column("user_id", _uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ticket_number", sa.String(24), nullable=False, unique=True),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("priority", sa.String(20), nullable=False, server_default="normal"),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("assigned_to", _uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('open','pending','resolved','closed')", name="ck_support_tickets_status"),
        sa.CheckConstraint("priority IN ('low','normal','high','urgent')", name="ck_support_tickets_priority"),
    )
    op.create_index("ix_support_tickets_user_status", "support_tickets", ["user_id", "status", "updated_at"])
    op.create_table(
        "support_ticket_messages",
        sa.Column("id", _uuid(), primary_key=True),
        sa.Column("ticket_id", _uuid(), sa.ForeignKey("support_tickets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author_user_id", _uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("is_internal", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_support_ticket_messages_ticket_created", "support_ticket_messages", ["ticket_id", "created_at"])
    op.create_table(
        "incident_records",
        sa.Column("id", _uuid(), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False, server_default="minor"),
        sa.Column("status", sa.String(20), nullable=False, server_default="investigating"),
        sa.Column("owner_id", _uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("details_safe", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_incident_records_status_created", "incident_records", ["status", "created_at"])
    op.create_table(
        "data_privacy_requests",
        sa.Column("id", _uuid(), primary_key=True),
        sa.Column("user_id", _uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("request_type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("result_storage_key", sa.String(500)),
        sa.Column("error_code", sa.String(80)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("request_type IN ('export','delete')", name="ck_privacy_request_type"),
        sa.CheckConstraint("status IN ('queued','processing','completed','failed','cancelled')", name="ck_privacy_request_status"),
        sa.UniqueConstraint("user_id", "request_type", "idempotency_key", name="uq_privacy_request_idempotency"),
    )
    op.create_index("ix_privacy_requests_user_status", "data_privacy_requests", ["user_id", "status", "created_at"])

    op.execute(
        "INSERT INTO plans (id, code, name, description, sort_order) VALUES "
        "(gen_random_uuid(), 'free', 'Free', 'Default no-charge plan', 0), "
        "(gen_random_uuid(), 'pro', 'Pro', 'Configurable paid plan catalog entry', 10), "
        "(gen_random_uuid(), 'business', 'Business', 'Configurable business plan catalog entry', 20) "
        "ON CONFLICT (code) DO NOTHING"
    )
    op.execute(
        "INSERT INTO plan_entitlements (id, plan_id, feature, value) "
        "SELECT gen_random_uuid(), id, 'limits', "
        "jsonb_build_object('daily_token_limit', 100000, 'document_count_limit', 100, "
        "'storage_size_limit_bytes', 524288000, 'concurrent_generation_limit', 2) "
        "FROM plans WHERE code='free' ON CONFLICT (plan_id, feature) DO NOTHING"
    )
    op.execute("INSERT INTO subscriptions (id, user_id, plan_id, status) SELECT gen_random_uuid(), u.id, p.id, 'active' FROM users u CROSS JOIN plans p WHERE p.code='free' AND NOT EXISTS (SELECT 1 FROM subscriptions s WHERE s.user_id=u.id AND s.status IN ('active','trialing'))")


def downgrade() -> None:
    op.drop_index("ix_privacy_requests_user_status", table_name="data_privacy_requests")
    op.drop_table("data_privacy_requests")
    op.drop_index("ix_incident_records_status_created", table_name="incident_records")
    op.drop_table("incident_records")
    op.drop_index("ix_support_ticket_messages_ticket_created", table_name="support_ticket_messages")
    op.drop_table("support_ticket_messages")
    op.drop_index("ix_support_tickets_user_status", table_name="support_tickets")
    op.drop_table("support_tickets")
    op.drop_index("ix_user_feedback_user_created", table_name="user_feedback")
    op.drop_table("user_feedback")
    op.drop_index("ix_feature_flags_enabled", table_name="feature_flags")
    op.drop_table("feature_flags")
    op.drop_index("ix_subscriptions_user_status", table_name="subscriptions")
    op.drop_table("subscriptions")
    op.drop_table("plan_entitlements")
    op.drop_index("ix_plans_enabled_order", table_name="plans")
    op.drop_table("plans")
