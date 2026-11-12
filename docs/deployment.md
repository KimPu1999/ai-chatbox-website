# Deployment notes

The complete Phase 10 runbook is in
[`docs/deployment-readiness.md`](deployment-readiness.md). It covers the
Railway API/worker images, Neon connection handling, R2 storage, Vercel
environment variables, migration locking and launch gates.

Run the dedicated migration executor with a migration-only role allowed to alter
the schema. Revisions `0010_platform_admin` and `0011_platform_schema_alignment`
are additive; `0011` only normalizes an existing constraint name. Set exact
frontend origins, `COOKIE_SECURE=true`, a strong MFA encryption key, `REDIS_URL`,
and the R2 private storage backend before production uploads. Do not expose
PostgreSQL, Redis, or private document storage publicly.

Bootstrap the first superadmin once through the trusted CLI, store the generated TOTP/recovery material securely, and disable `PLATFORM_BOOTSTRAP_ENABLED`. Configure HTTPS before using platform sessions. Review audit retention, database backups, object-storage deletion behavior, and worker recovery separately; the health endpoint does not perform paid OpenAI probes.
