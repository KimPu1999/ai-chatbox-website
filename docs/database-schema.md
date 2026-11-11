# PyChat AI database schema

The schema uses PostgreSQL UUID primary keys and timezone-aware `timestamptz` fields. Alembic revision `0006_conversation_management` adds folders, generated search vectors and GIN indexes, immutable share snapshots, bulk job records, pinned/last-message timestamps, and safe backfills without replacing earlier revision history.

## Tables

| Table | Purpose | Ownership |
| --- | --- | --- |
| `users` | Account identity, normalized email, password hash, lifecycle state | Root entity |
| `sessions` | Hashed session tokens, expiry, and revocation | `user_id` → `users` |
| `conversations` | Chat containers and pagination timestamps | `user_id` → `users` |
| `messages` | User, assistant, and system messages with token counters | Composite `conversation_id + user_id` → `conversations` |
| `attachments` | Metadata for externally stored files | Composite `message_id + user_id` → `messages` |
| `ai_usage` | Model, token, and latency accounting | Composite `message_id + user_id` → `messages` |
| `user_settings` | Per-user theme, notification, and extensible settings | `user_id` primary key → `users` |
| `ai_model_settings` | Per-user model parameters and default selection | `user_id` → `users` |
| `audit_logs` | Security and lifecycle audit events | Nullable `user_id` → `users` |
| `password_reset_tokens` | Hashed, expiring, one-time reset tokens | `user_id` → `users` |
| `email_verification_tokens` | Hashed, expiring, one-time verification tokens | `user_id` → `users` |
| `generation_runs` | Provider generation lifecycle and idempotency | Composite conversation/user ownership |
| `conversation_folders` | Per-user named folders and ordering | `user_id` → `users` |
| `conversation_shares` | Immutable read-only share snapshots | Composite conversation/owner ownership |
| `conversation_bulk_jobs` | Audited bounded bulk action progress | `user_id` → `users` |

## Ownership protection

Conversation repository queries always include both the resource ID and the authenticated user ID. Messages, attachments, and usage rows also carry the owner ID. Composite foreign keys make it impossible for a row owned by one user to reference a conversation or message owned by another user, even if application code makes a mistake.

Emails are stored in their original display form and in `email_normalized`, which the user repository populates with trimmed case-folded text and the database protects with a unique constraint. Passwords, sessions, and reset tokens store hashes only; plaintext secrets never belong in the database.

## Search and management indexes

`conversations.search_vector` indexes titles and `messages.search_vector` indexes message content using PostgreSQL `simple` text search and GIN. The API combines `websearch_to_tsquery` with a bounded substring fallback for Burmese and mixed Unicode. It does not claim Burmese linguistic tokenization.

Conversation ordering uses `pinned_at`, `last_message_at`, `updated_at`, and UUID. Cursor pagination avoids offset instability while conversations change. Existing `is_pinned` values are backfilled into `pinned_at`; existing message timestamps backfill `last_message_at`.

## Migration and test procedure

```bash
alembic -c backend/alembic.ini upgrade head
alembic -c backend/alembic.ini upgrade head
TEST_DATABASE_URL='postgresql+asyncpg://<isolated-db-url>' pytest -q backend/tests
```

The integration test fixture creates and drops schema objects in the database named by `TEST_DATABASE_URL`. It intentionally skips when that variable is absent or is not a PostgreSQL async URL. Use a disposable database owned by the test runner; never use a shared or production database.
