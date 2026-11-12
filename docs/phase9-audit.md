# Phase 9 audit

Audit date: 2026-11-12. Scope: the Phase 1–8 FastAPI, PostgreSQL, Redis/ARQ,
React and platform-admin implementation in this repository.

## Findings and disposition

| Severity | Priority | Finding | Disposition |
| --- | --- | --- | --- |
| High | P0 | Platform data endpoints could be reached with a platform cookie before MFA was verified. | Fixed: every `require_platform_permission` dependency now requires a recent MFA verification; enrollment and verification remain the only pre-MFA flows. |
| High | P0 | Authentication and generation rate limits were process-local, so multiple workers could bypass the limit. | Fixed: Redis Lua increment/expiry is used when `REDIS_URL` is configured and fails closed if Redis is unavailable. Local development retains a bounded in-process fallback. |
| High | P0 | Integration tests used `drop_all/create_all`, so migration regressions could be missed and a stale test schema could be mistaken for a valid one. | Fixed: the shared fixture runs `alembic upgrade head`, rejects non-test databases, and truncates only the explicitly named test database. |
| High | P1 | Alembic autogenerate reported historical Phase 1–7 index/FK/JSON compatibility drift. | Fixed without destructive DDL: a named compatibility allowlist preserves those legacy objects and `alembic check` now passes. New unexpected drift still fails the check. |
| Medium | P1 | API responses lacked a common request correlation ID and baseline security headers. | Fixed: request IDs, timing logs, `nosniff`, frame protection, referrer policy and permissions policy are added. Logs exclude bodies, cookies and query strings. |
| Medium | P1 | Public share tokens in URL paths could be copied into application request logs. | Fixed: the application correlation logger redacts `/api/v1/shared/{token}`. Reverse-proxy/Uvicorn access-log redaction remains a deployment requirement. |
| Medium | P1 | Document parsing falls back to API-process execution when Redis is not configured, and malware scanning is optional by configuration. | Open blocker: production must require the durable worker and a fail-closed scanner before accepting uploads. The API keeps a bounded upload size and quarantine/status workflow. |
| Medium | P1 | The platform API module is densely formatted and contains scoped Ruff suppressions. | Open maintainability item. Ruff still runs; the suppressions are documented for refactoring rather than used to skip the security gate. |
| Medium | P2 | No measured restore drill or production load run was available in this workspace. | Documented as not run; see `backup-recovery.md` and `performance-report.md`. |
| Low | P2 | The initial restricted npm audit could not reach the registry. | Re-run with network access passed: `npm audit --audit-level=high` reports zero vulnerabilities. |

The dependency audit also found outdated pinned versions during the review
(`pypdf`, `pytest` and `cryptography`). Compatible minimums were raised and the
final `pip-audit` run reported no known vulnerabilities.

No confirmed credential leak, cross-user access bypass, or paid provider call was
found during this audit. Automated results are evidence for the tested paths only;
they are not a claim of vulnerability-free status.

## Verification snapshot

- Backend unit/security suite: **26 passed** with no test database; four PostgreSQL-only tests are skipped without `TEST_DATABASE_URL`.
- Isolated PostgreSQL integration suite: **30 passed** when run with `pychat_test` after Alembic migration.
- Isolated coverage run: **30 passed**, **52% total coverage**. The requested 85% target is not met; critical security paths received new tests, while the wider endpoint surface still needs coverage.
- `ruff check backend/app backend/tests`: **passed**.
- `bandit -r backend/app -ll`: **passed**.
- `pip-audit -r backend/requirements.txt`: **passed** with no known vulnerabilities.
- `pip check`: **passed**.
- `alembic check`: **passed** after the explicit legacy compatibility allowlist.
- Frontend typecheck, Vitest, production build and `npm audit --audit-level=high`: **passed**.
- Playwright discovery listed 16 tests, but browser execution is **blocked** on this macOS 12 host because the required Chromium binary is unavailable and current Playwright Chromium does not support this OS. CI installs Chromium on Linux.
- A Locust run, EXPLAIN/ANALYZE benchmark, and restore drill were not run in this workspace.
