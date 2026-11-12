# Usage and cost controls

Existing `ai_usage`, pricing versions and Redis/PostgreSQL quota controls remain
the source of truth. Account usage reports recorded tokens, generation count,
document count and storage bytes. Unknown provider usage remains unknown rather
than being represented as confirmed zero.

Plan limits are capped by platform safety settings. Reservations and actual
usage reconciliation continue to be handled by the Phase 5 generation
lifecycle. Estimated cost is application accounting and is distinct from an
OpenAI organization invoice.
