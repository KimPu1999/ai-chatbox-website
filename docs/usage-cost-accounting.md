# Usage and cost accounting

Platform analytics read `generation_runs` and `ai_usage`. A generation has one unique usage row through `generation_run_id`, preventing retry double counting. Provider metrics are stored when available. Missing metrics remain unknown and are counted in the dashboard.

`model_pricing_versions` stores provider/model, currency, effective dates, Decimal price-per-million-token fields, and a pricing version. Estimated spend is application-side accounting. Provider organization billing reconciliation is intentionally optional and is not required for the control center. Prices should be entered by a superadmin through a separately reviewed pricing workflow before cost figures are treated as meaningful.

Daily aggregates are projections that can be rebuilt from source usage rows. Quotas are stored as explicit nullable limits: `NULL` means unlimited, while `0` means no allowance. Distributed enforcement must use the existing Redis configuration before enabling multi-worker production quotas.
