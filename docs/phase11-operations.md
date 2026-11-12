# Phase 11 operations

`GET /api/v1/platform/operations/summary` exposes database-backed counts for
active incidents, support backlog, document queue, failed generations and
recorded estimated cost. `GET /api/v1/platform/operations/slo` reports an
observed generation completion ratio when the window has data.

The endpoints require platform MFA and named platform permissions. They do not
expose chat contents, document contents, provider keys or private storage
paths. The SLO target is a planning target, not a claim of actual availability.

OpenTelemetry is enabled with `OTEL_ENABLED=true` and can export to
`OTEL_EXPORTER_ENDPOINT`. Local runs with no endpoint use a console exporter.
Telemetry must remain free of prompts, documents, cookies and authentication
headers.
