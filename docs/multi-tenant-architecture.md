# Multi-tenant architecture

Users are identities. Personal conversations and documents retain `user_id`
and have a null `organization_id`. Organizations are independent workspaces;
membership rows authorize access and carry the workspace role. Platform roles
(`user`, `admin`, `superadmin`) remain separate from workspace roles.

Organization requests establish `app.current_organization_id` with PostgreSQL
`set_config(..., true)`, which is transaction local and safe with pooled
connections. The API then verifies an active membership before reading or
mutating resources. Workers must repeat this verification with a fresh session.

No personal conversation or document is automatically migrated into a team.
Future team conversations use an explicit organization scope. Team document
upload and fully grounded team generation should extend the existing Phase 7
pipeline using the same scope fields and authorization service.

