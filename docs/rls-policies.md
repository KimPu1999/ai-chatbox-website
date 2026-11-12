# RLS policy inventory

Migrations `0014` and `0015` enable policies for organization tables and for
existing shared resource tables. Organization tables require
`app.current_organization_id` to match. Existing personal rows remain
available only as `organization_id IS NULL`; application ownership checks still
protect personal data.

The setting is transaction-local. Never use a session-global `SET` on a pooled
connection. Inspect policies with `\dp` and role attributes with:

```sql
SELECT rolname, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user;
```

