# Backup and recovery runbook

This repository documents the procedure; a restore drill was not run in the
developer workspace.

1. Take a PostgreSQL base backup plus WAL/PITR according to the hosting provider.
2. Back up private document storage using versioned, encrypted object storage.
3. Restore into a separate recovery PostgreSQL database and private storage
   prefix. Never test restoration over the live database.
4. Run `alembic upgrade head` and verify `alembic current`.
5. Check counts and hashes for documents, chunks and processing jobs. Redis is
   reconstructed from PostgreSQL job/session state; it is not the source of
   truth for user data.
6. Start workers in recovery mode, recover stale jobs, and verify owner-scoped
   download/retrieval checks.
7. Record measured restore duration and data-loss window before publishing RPO/RTO.

Until this drill is measured, RPO/RTO are targets to be agreed with operations,
not guarantees. Deleted files may remain in provider backups until retention
expiry.
