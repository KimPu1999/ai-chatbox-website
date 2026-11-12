import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from app import models  # noqa: F401
from app.core.config import get_settings
from app.db import Base, _async_database_config

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
# ruff: noqa: E501
_migration_url = os.getenv("MIGRATION_DATABASE_URL") or os.getenv("DATABASE_URL") or get_settings().database_url
_migration_url, _migration_connect_args = _async_database_config(_migration_url)
config.set_main_option("sqlalchemy.url", _migration_url)
target_metadata = Base.metadata

# These objects were created by the Phase 1-7 migrations but are not modelled
# with identical names/types today (for example, composite ownership FKs now
# replace the original single-column FK in the ORM). They are intentionally
# preserved in the database. Keeping this small, named allowlist makes
# ``alembic check`` useful without proposing destructive drops or JSON/JSONB
# rewrites for historical data.
_KNOWN_BASELINE_DRIFT = {
    ("index", "ai_usage", "ix_ai_usage_user_id"),
    ("foreign_key_constraint", "ai_usage", "ai_usage_message_id_fkey"),
    ("index", "attachments", "ix_attachments_user_id"),
    ("foreign_key_constraint", "attachments", "attachments_message_id_fkey"),
    ("unique_constraint", "conversation_documents", "uq_conversation_documents"),
    ("index", "conversations", "ix_conversations_search_vector"),
    ("index", "conversations", "ix_conversations_user_deleted_updated"),
    ("index", "conversations", "ix_conversations_user_id"),
    ("index", "document_chunks", "ix_document_chunks_embedding_hnsw"),
    ("index", "messages", "ix_messages_conversation_id"),
    ("index", "messages", "ix_messages_search_vector"),
    ("foreign_key_constraint", "messages", "messages_conversation_id_fkey"),
    ("index", "sessions", "ix_sessions_user_id"),
    ("index", "users", "ix_users_email"),
    ("index", "users", "ix_users_status_role"),
    ("unique_constraint", "users", "users_email_key"),
    ("unique_constraint", "users", "uq_users_email_normalized"),
}
_KNOWN_TYPE_BASELINE_DRIFT = {
    ("document_chunks", "source_locator"),
    ("messages", "citations"),
}


def include_object(object_, name, type_, reflected, compare_to):
    table_name = getattr(getattr(object_, "table", None), "name", None)
    if (type_, table_name, name) in _KNOWN_BASELINE_DRIFT:
        return False
    return True


def compare_type(context, inspected_column, metadata_column, inspected_type, metadata_type):
    table_name = getattr(getattr(metadata_column, "table", None), "name", None)
    if (table_name, metadata_column.name) in _KNOWN_TYPE_BASELINE_DRIFT:
        return False
    return None


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        include_object=include_object,
        compare_type=compare_type,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=include_object,
        compare_type=compare_type,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=_migration_connect_args,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
