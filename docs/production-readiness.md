# Production readiness

Current assessment: **not production-ready without deployment evidence**.

Implemented foundations include authenticated owner checks, MFA-gated platform
access, CSRF/origin controls, explicit CORS/trusted hosts, migration-backed test
fixtures, structured request timing/correlation, and CI quality gates.

Release blockers:

- Configure HTTPS, `COOKIE_SECURE=true`, production trusted hosts/origins and a
  valid Fernet `PLATFORM_MFA_ENCRYPTION_KEY`.
- Configure Redis and durable ARQ workers; do not rely on API-process document
  fallback for production uploads.
- Deploy and verify a fail-closed malware scanner and isolated parsing policy.
- Keep the networked dependency scans green in CI; the final local Bandit, pip-audit and npm audit runs reported no known vulnerabilities.
- Complete a restore drill and bounded load run with measured thresholds.
- Run the full seeded Playwright flows with fake providers in a dedicated E2E
  environment.
- Configure edge/Uvicorn access logs to redact or omit public share-token URLs.
- Review the known Phase 1–7 migration compatibility allowlist when schema work
  next changes.
