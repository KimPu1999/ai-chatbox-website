# Phase 12 audit

The existing application keeps personal conversations and documents owned by
`users.id`. Phase 12 adds organization scope as a nullable field, so existing
rows remain personal and private. Organization membership is checked on every
organization route; the browser supplied organization ID is only a selector.

The additive migrations are `0014_phase12_multi_tenant` and
`0015_phase12_tenant_rls_existing`. The first creates organizations,
memberships, invitations, settings, knowledge bases, organization
subscriptions, usage, and audit records. The second adds row policies to
existing shared resource tables. No historical personal rows are backfilled.

Known limitation: RLS policy behavior against a separately provisioned
non-owner runtime database role still requires a deployment-specific role and
negative integration test. The local isolated database runs the migrations and
application authorization tests, but the current local role owns the tables.

