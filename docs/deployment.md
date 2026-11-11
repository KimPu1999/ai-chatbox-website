# Deployment notes

Run `alembic upgrade head` with a database role allowed to alter the schema. Revisions `0010_platform_admin` and `0011_platform_schema_alignment` are additive; `0011` only normalizes an existing constraint name. Set exact frontend origins, `COOKIE_SECURE=true`, a strong `PLATFORM_MFA_ENCRYPTION_KEY`, `REDIS_URL` when using multiple workers, and a private storage backend. Do not expose PostgreSQL, Redis, or private document storage publicly.

Bootstrap the first superadmin once through the trusted CLI, store the generated TOTP/recovery material securely, and disable `PLATFORM_BOOTSTRAP_ENABLED`. Configure HTTPS before using platform sessions. Review audit retention, database backups, object-storage deletion behavior, and worker recovery separately; the health endpoint does not perform paid OpenAI probes.
