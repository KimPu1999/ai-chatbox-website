# Incident runbook

1. Confirm the incident with `/health/ready`, platform health and database
   connectivity. Do not use a paid AI call as a health probe.
2. Identify the correlation ID and affected component from structured logs.
3. Apply the smallest safe mitigation: disable a feature flag, pause a worker,
   or roll back the last release using provider deployment controls.
4. Preserve audit records and avoid inspecting private chat/document content.
5. Record detection, owner, mitigation, recovery time, root cause and follow-up
   actions in an incident record.

Alert delivery and rollback timing must be tested in staging before claiming an
operational SLO.
