# OWASP ASVS/API assessment

This is a focused verification record, not a certification.

| Area | Evidence | Status |
| --- | --- | --- |
| BOLA/BFLA | Owner-scoped repository queries, platform permission matrix, isolated cross-user FK test | PASS for covered paths |
| Authentication | Argon2, opaque hashed sessions, expiry/revocation tests, CSRF/origin checks | PASS for covered paths |
| Object property authorization | Registration never accepts a role; generation accepts user content only; admin role changes require superadmin | PASS for covered paths |
| Resource consumption | Bounded pagination, upload limits, document limits, Redis rate limits, generation quotas | PARTIAL: production Redis/worker behavior needs deployment verification |
| Injection | SQLAlchemy bound expressions; Markdown sanitizer and safe URL transform | PASS for covered paths |
| Misconfiguration | Trusted hosts, explicit CORS, secure production cookie validation, safe error responses | PASS in code; production environment still needs deployment check |
| External API use | Server-only OpenAI client, timeout/error mapping, no live paid request in tests | PASS for reviewed code |
| Logging/privacy | Correlation IDs without bodies/tokens; audit metadata is safe by convention | PARTIAL: retention/database privilege review remains |

Known open risk is upload parser isolation and malware scanning. Automated tests
must be complemented by an isolated worker and scanner deployment review.
