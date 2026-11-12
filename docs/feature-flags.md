# Feature flags

Feature flags use stable SHA-256 bucketing by `(flag key, user UUID)` for
deterministic percentage rollout. Flags may be globally enabled, restricted to
admins, restricted to plan codes, or allowlisted by user ID.

Flags are a release control only. They do not bypass authentication, CSRF,
RBAC, ownership checks or entitlement enforcement. Changes must be audited by
the platform API.
