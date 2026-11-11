"""Add private documents, pgvector chunks and document attachments."""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision = "0008_documents_rag"
down_revision = "0007_fix_folder_ownership_fk"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The extension must be installed by a database role allowed to create
    # extensions. Deployment automation may run this migration with that role.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "documents",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("mime_type", sa.String(length=120), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256_hash", sa.String(length=64), nullable=False),
        sa.Column("page_count", sa.Integer()),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="quarantined"),
        sa.Column("error_code", sa.String(length=80)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("id", "user_id", name="uq_documents_id_user"),
        sa.UniqueConstraint("storage_key", name="uq_documents_storage_key"),
        sa.CheckConstraint("size_bytes >= 0", name="ck_documents_size_nonnegative"),
        sa.CheckConstraint(
            "status IN ("
            "'quarantined','queued','parsing','chunking','embedding','ready',"
            "'failed','cancelled','ocr_required','partially_extracted')",
            name="ck_documents_status",
        ),
    )
    op.create_index("ix_documents_user_created", "documents", ["user_id", "created_at", "id"])
    op.create_index("ix_documents_user_status", "documents", ["user_id", "status", "created_at"])

    op.create_table(
        "document_chunks",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("page_number", sa.Integer()),
        sa.Column("source_locator", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("embedding_model", sa.String(length=100), nullable=False),
        sa.Column("embedding_dimensions", sa.Integer(), nullable=False, server_default="1536"),
        sa.Column("embedding", Vector(1536)),
        sa.Column("processing_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["document_id", "user_id"],
            ["documents.id", "documents.user_id"],
            ondelete="CASCADE",
            name="fk_document_chunks_document_user",
        ),
        sa.UniqueConstraint(
            "document_id",
            "processing_version",
            "chunk_index",
            name="uq_document_chunks_version_index",
        ),
        sa.CheckConstraint("token_count > 0", name="ck_document_chunks_token_count"),
        sa.CheckConstraint("embedding_dimensions > 0", name="ck_document_chunks_dimensions"),
    )
    op.create_index(
        "ix_document_chunks_user_document",
        "document_chunks",
        ["user_id", "document_id", "chunk_index"],
    )
    op.execute(
        "CREATE INDEX ix_document_chunks_embedding_hnsw "
        "ON document_chunks USING hnsw (embedding vector_cosine_ops) "
        "WHERE embedding IS NOT NULL"
    )

    op.create_table(
        "document_processing_jobs",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="queued"),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(length=80)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["document_id", "user_id"],
            ["documents.id", "documents.user_id"],
            ondelete="CASCADE",
            name="fk_document_jobs_document_user",
        ),
        sa.UniqueConstraint("document_id", "attempt_count", name="uq_document_jobs_attempt"),
        sa.CheckConstraint("progress >= 0 AND progress <= 100", name="ck_document_jobs_progress"),
        sa.CheckConstraint("attempt_count >= 0", name="ck_document_jobs_attempt_nonnegative"),
        sa.CheckConstraint(
            "status IN ('queued','running','completed','failed','cancelled')",
            name="ck_document_jobs_status",
        ),
    )
    op.create_index(
        "ix_document_jobs_user_status",
        "document_processing_jobs",
        ["user_id", "status", "created_at"],
    )

    op.create_table(
        "conversation_documents",
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("attached_by", sa.UUID(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id", "attached_by"],
            ["conversations.id", "conversations.user_id"],
            ondelete="CASCADE",
            name="fk_conversation_documents_conversation_user",
        ),
        sa.ForeignKeyConstraint(
            ["document_id", "attached_by"],
            ["documents.id", "documents.user_id"],
            ondelete="CASCADE",
            name="fk_conversation_documents_document_user",
        ),
        sa.PrimaryKeyConstraint("conversation_id", "document_id"),
        sa.UniqueConstraint("conversation_id", "document_id", name="uq_conversation_documents"),
    )
    op.create_index(
        "ix_conversation_documents_user", "conversation_documents", ["attached_by", "created_at"]
    )
    op.add_column("messages", sa.Column("citations", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("messages", "citations")
    op.drop_index("ix_conversation_documents_user", table_name="conversation_documents")
    op.drop_table("conversation_documents")
    op.drop_index("ix_document_jobs_user_status", table_name="document_processing_jobs")
    op.drop_table("document_processing_jobs")
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding_hnsw")
    op.drop_index("ix_document_chunks_user_document", table_name="document_chunks")
    op.drop_table("document_chunks")
    op.drop_index("ix_documents_user_status", table_name="documents")
    op.drop_index("ix_documents_user_created", table_name="documents")
    op.drop_table("documents")
    op.execute("DROP EXTENSION IF EXISTS vector")
