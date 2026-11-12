# Phase 11 audit

The existing application already provides session authentication, MFA-gated
platform access, generation quotas, usage records, durable ARQ document jobs,
conversation ownership checks and deployment configuration. Phase 11 reuses
those paths and adds account maturity and operations data.

## Findings and decisions

- **Plan state:** no customer billing is active. A `free` plan and active
  no-charge subscription are seeded for existing users.
- **Quota state:** generation limits continue through the existing quota engine;
  plan entitlements and user overrides are evaluated before platform caps.
- **Privacy:** exports and deletion requests are durable PostgreSQL jobs. The
  worker performs the operation and records a terminal status.
- **Support:** tickets and messages are owner-scoped; internal messages are
  never returned to users.
- **Observability:** OpenTelemetry is optional and disabled by default. When
  enabled, only low-cardinality safe attributes are exported.
- **Billing:** the provider boundary intentionally raises a disabled error
  until a separately authorized provider implementation is configured.

Production remains gated on malware scanning, cloud verification, backup
restore testing, and measured operational alert delivery.
