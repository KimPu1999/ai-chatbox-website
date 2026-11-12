# SaaS entitlements

Migrations `0012_phase11_saas_operations` and `0013_phase11_plan_catalog` add
`plans`, `plan_entitlements` and `subscriptions`. They seed a configurable
`free` plan and assign it to existing users without charging them; `pro` and
`business` are catalog entries with no assumed prices or paid entitlements.

The entitlement service combines active subscription state, plan limits, user
overrides and platform safety caps. The browser cannot supply a plan, role,
quota, payment status or model permission. Generation and document upload paths
call the server-side evaluator before expensive work.
