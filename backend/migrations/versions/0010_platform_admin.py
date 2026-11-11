"""Add the platform administration control-plane schema.

All changes are additive. Existing users, conversations, documents and usage rows
remain intact; daily aggregates are rebuildable projections rather than the source
of truth.
"""

# ruff: noqa: E501

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0010_platform_admin"
down_revision = "0009_document_embedding_usage"
branch_labels = None
depends_on = None

uuid = postgresql.UUID(as_uuid=True)
jsonb = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.add_column("sessions", sa.Column("session_kind", sa.String(20), nullable=False, server_default="user"))
    op.add_column("sessions", sa.Column("mfa_verified_at", sa.DateTime(timezone=True)))
    op.create_index("ix_sessions_kind_activity", "sessions", ["session_kind", "last_activity_at"])

    op.add_column("audit_logs", sa.Column("result", sa.String(20), nullable=False, server_default="success"))
    op.add_column("audit_logs", sa.Column("correlation_id", sa.String(100)))
    op.add_column("audit_logs", sa.Column("network_metadata", jsonb, nullable=False, server_default="{}"))
    op.create_index("ix_audit_logs_action_created", "audit_logs", ["action", "created_at", "id"])

    op.create_table(
        "platform_settings",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("key", sa.String(100), nullable=False, unique=True),
        sa.Column("value", jsonb, nullable=False, server_default="{}"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_by", uuid, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_platform_settings_updated", "platform_settings", ["updated_at"])

    op.create_table(
        "platform_models",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("identifier", sa.String(100), nullable=False, unique=True),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False, server_default="openai"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("capabilities", jsonb, nullable=False, server_default="{}"),
        sa.Column("max_output_tokens", sa.Integer(), nullable=False, server_default="1024"),
        sa.Column("context_limit", sa.Integer(), nullable=False, server_default="8000"),
        sa.Column("last_availability_check", sa.DateTime(timezone=True)),
        sa.Column("updated_by", uuid, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("length(trim(identifier)) > 0", name="ck_platform_models_identifier"),
        sa.CheckConstraint("max_output_tokens > 0 AND context_limit > 0", name="ck_platform_models_limits"),
    )
    op.create_index("ix_platform_models_enabled_default", "platform_models", ["enabled", "is_default"])

    op.create_table(
        "model_pricing_versions",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("model_identifier", sa.String(100), nullable=False),
        sa.Column("effective_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_end", sa.DateTime(timezone=True)),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("input_price_per_million", sa.Numeric(18, 8), nullable=False, server_default="0"),
        sa.Column("output_price_per_million", sa.Numeric(18, 8), nullable=False, server_default="0"),
        sa.Column("cached_input_price_per_million", sa.Numeric(18, 8), nullable=False, server_default="0"),
        sa.Column("embedding_price_per_million", sa.Numeric(18, 8), nullable=False, server_default="0"),
        sa.Column("additional_billing", jsonb, nullable=False, server_default="{}"),
        sa.Column("pricing_version", sa.String(40), nullable=False, server_default="unpriced-v1"),
        sa.Column("created_by", uuid, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("provider", "model_identifier", "effective_start", name="uq_model_pricing_effective_start"),
        sa.CheckConstraint("input_price_per_million >= 0 AND output_price_per_million >= 0 AND cached_input_price_per_million >= 0 AND embedding_price_per_million >= 0", name="ck_model_pricing_nonnegative"),
    )
    op.create_index("ix_model_pricing_model_dates", "model_pricing_versions", ["provider", "model_identifier", "effective_start", "effective_end"])

    op.create_table(
        "quota_policies",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("scope", sa.String(20), nullable=False, server_default="global"),
        sa.Column("scope_key", sa.String(50), nullable=False, server_default="default"),
        sa.Column("requests_per_minute", sa.Integer()),
        sa.Column("requests_per_hour", sa.Integer()),
        sa.Column("daily_token_limit", sa.Integer()),
        sa.Column("monthly_token_limit", sa.Integer()),
        sa.Column("daily_spend_limit", sa.Numeric(18, 8)),
        sa.Column("concurrent_generation_limit", sa.Integer()),
        sa.Column("document_count_limit", sa.Integer()),
        sa.Column("storage_size_limit_bytes", sa.Integer()),
        sa.Column("embedding_token_budget", sa.Integer()),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_by", uuid, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("scope", "scope_key", name="uq_quota_policies_scope"),
        sa.CheckConstraint("scope IN ('global','role')", name="ck_quota_policies_scope"),
        sa.CheckConstraint("requests_per_minute IS NULL OR requests_per_minute >= 0", name="ck_quota_rpm"),
        sa.CheckConstraint("daily_token_limit IS NULL OR daily_token_limit >= 0", name="ck_quota_daily_tokens"),
    )

    op.create_table(
        "user_quota_overrides",
        sa.Column("user_id", uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("limits", jsonb, nullable=False, server_default="{}"),
        sa.Column("updated_by", uuid, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "usage_aggregates_daily",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("usage_date", sa.Date(), nullable=False),
        sa.Column("user_id", uuid, sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cached_input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("embedding_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_cost", sa.Numeric(18, 8)),
        sa.Column("rebuilt_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("usage_date", "user_id", "model", name="uq_usage_aggregate_daily"),
    )
    op.create_index("ix_usage_aggregate_date", "usage_aggregates_daily", ["usage_date"])

    op.create_table(
        "system_health_snapshots",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("component", sa.String(60), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("latency_ms", sa.Integer()),
        sa.Column("detail_safe", jsonb, nullable=False, server_default="{}"),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_health_snapshots_component_checked", "system_health_snapshots", ["component", "checked_at"])

    op.create_table(
        "admin_mfa_credentials",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("user_id", uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("encrypted_secret", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_verified_at", sa.DateTime(timezone=True)),
        sa.Column("last_counter", sa.Integer()),
        sa.Column("failed_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", name="uq_admin_mfa_user"),
    )
    op.create_table(
        "admin_recovery_codes",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("mfa_credential_id", uuid, sa.ForeignKey("admin_mfa_credentials.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code_hash", sa.String(128), nullable=False, unique=True),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_admin_recovery_codes_credential", "admin_recovery_codes", ["mfa_credential_id", "used_at"])


def downgrade() -> None:
    op.drop_index("ix_admin_recovery_codes_credential", table_name="admin_recovery_codes")
    op.drop_table("admin_recovery_codes")
    op.drop_table("admin_mfa_credentials")
    op.drop_index("ix_health_snapshots_component_checked", table_name="system_health_snapshots")
    op.drop_table("system_health_snapshots")
    op.drop_index("ix_usage_aggregate_date", table_name="usage_aggregates_daily")
    op.drop_table("usage_aggregates_daily")
    op.drop_table("user_quota_overrides")
    op.drop_table("quota_policies")
    op.drop_index("ix_model_pricing_model_dates", table_name="model_pricing_versions")
    op.drop_table("model_pricing_versions")
    op.drop_index("ix_platform_models_enabled_default", table_name="platform_models")
    op.drop_table("platform_models")
    op.drop_index("ix_platform_settings_updated", table_name="platform_settings")
    op.drop_table("platform_settings")
    op.drop_index("ix_audit_logs_action_created", table_name="audit_logs")
    op.drop_column("audit_logs", "network_metadata")
    op.drop_column("audit_logs", "correlation_id")
    op.drop_column("audit_logs", "result")
    op.drop_index("ix_sessions_kind_activity", table_name="sessions")
    op.drop_column("sessions", "mfa_verified_at")
    op.drop_column("sessions", "session_kind")
