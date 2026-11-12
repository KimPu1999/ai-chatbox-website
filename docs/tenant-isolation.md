# Tenant isolation

All organization endpoints require a verified session and an active
membership. Organization-owned tables have foreign keys and tenant indexes.
Existing conversations, messages, generation runs, usage rows, documents and
processing jobs now carry a nullable organization scope. RLS policies compare
that scope with the transaction-local setting.

Production must use a non-superuser runtime role without `BYPASSRLS`; migration
credentials must be separate. Verify `rolsuper` and `rolbypassrls` before
enabling organization traffic, then run cross-tenant negative tests with two
independent sessions.

