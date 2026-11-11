"""Track provider token usage for document embedding jobs."""

import sqlalchemy as sa
from alembic import op

revision = "0009_document_embedding_usage"
down_revision = "0008_documents_rag"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "document_processing_jobs",
        sa.Column("embedding_tokens", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "document_processing_jobs",
        sa.Column("embedding_cost_estimate", sa.Numeric(18, 8), nullable=True),
    )
    op.create_check_constraint(
        "ck_document_jobs_embedding_tokens_nonnegative",
        "document_processing_jobs",
        "embedding_tokens >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_document_jobs_embedding_tokens_nonnegative",
        "document_processing_jobs",
        type_="check",
    )
    op.drop_column("document_processing_jobs", "embedding_cost_estimate")
    op.drop_column("document_processing_jobs", "embedding_tokens")
