# Security checklist

- [x] Argon2 password hashes and SHA-256 hashes for high-entropy opaque tokens.
- [x] HttpOnly session cookies, SameSite=Lax, no Domain, HTTPS `Secure` mode in production.
- [x] Server-side CSRF token checks and trusted Origin/Referer checks on mutations.
- [x] Explicit CORS origins; no wildcard credentialed CORS.
- [x] Trusted hosts and common security response headers.
- [x] Application request logs redact public share-token path segments; configure edge access logs likewise.
- [x] Session idle/absolute expiry, rotation on login, revocation and logout-all.
- [x] Server-side owner checks for conversations, documents, folders, shares and platform APIs.
- [x] MFA required for platform data access and recent MFA for sensitive changes.
- [x] Last active superadmin and self-role-change protections.
- [x] No frontend storage of session credentials; appearance preference is the only local storage use.
- [x] Sanitized Markdown and safe URL protocols; no unsafe raw HTML.
- [x] Private storage paths are outside the public web root and download responses are `no-store`.
- [x] Bounded upload sizes, parser limits and document ownership filters.
- [x] Redis-backed limits fail closed when configured Redis is unavailable.
- [ ] Production malware scanner and isolated parser workers are still required.
- [ ] HTTPS reverse-proxy/HSTS deployment verification is still required.
- [x] Networked Bandit, pip-audit and npm audit runs completed with no reported vulnerabilities; CI repeats these checks.

Review this file with the deployment configuration before enabling production
uploads or platform administration.
