# Billing foundation

`BILLING_ENABLED=false` and `BILLING_PROVIDER=disabled` are the safe defaults.
The server-side `BillingProvider` boundary is ready for a provider adapter, but
there is no checkout endpoint and no live charge path in this phase.

Any future provider must verify raw webhook signatures, reject stale events,
persist unique event IDs, handle duplicate and out-of-order events, and derive
entitlements from verified server state. A browser redirect must never mark a
subscription paid.
