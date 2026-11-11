# PyChat AI database schema

Phase 2 uses PostgreSQL UUID primary keys and timezone-aware `timestamptz` fields. Alembic revision `0002_phase2` upgrades the Phase 1 schema without replacing the existing revision history.

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

## Ownership protection

Conversation repository queries always include both the resource ID and the authenticated user ID. Messages, attachments, and usage rows also carry the owner ID. Composite foreign keys make it impossible for a row owned by one user to reference a conversation or message owned by another user, even if application code makes a mistake.

Emails are stored in their original display form and in `email_normalized`, which the user repository populates with trimmed case-folded text and the database protects with a unique constraint. Passwords, sessions, and reset tokens store hashes only; plaintext secrets never belong in the database.

## Migration and test procedure

```bash
alembic -c backend/alembic.ini upgrade head
alembic -c backend/alembic.ini downgrade -1
alembic -c backend/alembic.ini upgrade head
TEST_DATABASE_URL='postgresql+asyncpg://<isolated-db-url>' pytest -q backend/tests
```

The integration test fixture creates and drops schema objects in the database named by `TEST_DATABASE_URL`. It intentionally skips when that variable is absent or is not a PostgreSQL async URL. Use a disposable database owned by the test runner; never use a shared or production database.
