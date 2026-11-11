# Platform security boundaries

Platform login is separate from normal chat authentication. It uses a second HttpOnly session cookie, SameSite=Lax, no Domain attribute, an absolute and idle timeout inherited from the existing session policy, origin checks, CSRF tokens, rate limiting, active-account checks, verified email, role checks, and TOTP step-up verification.

MFA secrets are encrypted at rest with `PLATFORM_MFA_ENCRYPTION_KEY`. Recovery codes are generated with cryptographic randomness and stored as hashes. MFA counters prevent reuse of the same TOTP time step. Failed verification attempts are temporarily locked. The key must be configured in staging/production; it must never be committed or returned by an API.

Audit records contain action, actor, target, result, correlation metadata and safe metadata only. Passwords, session tokens, MFA secrets, recovery tokens, chat content, document content and provider keys are excluded. Admin analytics expose aggregate document/storage information and never provide unrestricted document downloads.

The API is the authorization boundary. Admin UI route guards cannot grant permission. Status and role mutations require a fresh MFA step-up, reject self role changes, protect the last active superadmin, and revoke affected sessions. Cost numbers are application estimates from recorded usage and effective-dated pricing; they are not provider invoices.
