# Privacy lifecycle

`POST /api/v1/account/data-export` queues an idempotent export request. The ARQ
worker writes a private UTF-8 JSON export to configured private storage and
records completion. `POST /api/v1/account/delete-request` requires a recent
session, CSRF and verified account; the worker removes owned private files and
marks the account deleted while retaining operational audit records according
to policy.

Requests are durable and retryable. A completed deletion does not claim that
provider backups or previously copied material disappear immediately. Export
retention is controlled by `PRIVACY_EXPORT_RETENTION_DAYS`.
