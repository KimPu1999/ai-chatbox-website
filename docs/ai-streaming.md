# Phase 5 AI streaming

Phase 5 adds a server owned OpenAI Responses API generation lifecycle. The browser sends authenticated requests to FastAPI; only FastAPI reads `OPENAI_API_KEY`. The application stores conversation messages and generation state in PostgreSQL, while OpenAI is used as a bounded provider for one response at a time.

## Configuration

Copy `.env.example` to `backend/.env` and set `OPENAI_API_KEY` locally. The key is never returned by an endpoint or bundled into React. `OPENAI_MODEL` selects the default model and `AI_ALLOWED_MODELS` can contain a comma separated allowlist. The provider uses `store=false` because PostgreSQL is the application source of truth.

The limits are controlled by `AI_TIMEOUT_SECONDS`, `AI_MAX_OUTPUT_TOKENS`, `AI_CONTEXT_TOKEN_BUDGET`, `AI_MAX_REQUESTS_PER_MINUTE`, `AI_MAX_CONCURRENT_GENERATIONS`, and `AI_DAILY_TOKEN_BUDGET`. `REDIS_URL` is reserved for shared rate coordination; the current local implementation uses PostgreSQL generation state and the existing process-local request limiter, so Redis should be enabled before horizontally scaling rate enforcement.

## Routes and event protocol

- `POST /api/v1/conversations/{conversation_id}/generate` accepts `{content, model?, idempotency_key?}`.
- `POST /api/v1/conversations/{conversation_id}/regenerate` uses the latest active user turn and excludes the previous assistant version.
- `POST /api/v1/generations/{run_id}/cancel` marks an owned queued or streaming run cancelled.
- `GET /api/v1/models` returns only server-configured model identifiers and availability.
- `GET /api/v1/usage` returns the authenticated user's safe daily token summary.

Generation responses are `text/event-stream` frames with `id`, `event`, and JSON `data`. Supported events are `run.started`, `message.delta`, `message.completed`, `usage.updated`, `run.completed`, `run.cancelled`, and `run.failed`. The client parses arbitrary chunk boundaries and uses both `AbortController` and the authenticated cancel route; an HTTP disconnect alone does not guarantee cancellation.

## Data and recovery

`generation_runs` records queued, streaming, completed, cancelled, failed, and incomplete states. Streaming assistant messages are persisted incrementally and marked failed when a provider stream ends unexpectedly, so failed partial output is excluded from future context. Final usage is written once per run with the provider response ID. Pricing is deliberately `unpriced-v1` until a reviewed pricing table is configured; no invented dollar amount is returned.

Context is loaded only from the owned conversation, in chronological order, and includes completed active user and assistant messages. A conservative character based estimate trims oldest turns to `AI_CONTEXT_TOKEN_BUDGET`. User supplied roles never override the server instruction.

## Local setup and verification

```bash
cd backend
source .venv/bin/activate
alembic upgrade head
uvicorn app.main:app --reload --port 8000

cd ../frontend
npm run dev
```

Without a configured key, the API returns a safe provider-unavailable response and no paid request is attempted. Tests use fake provider objects or protocol fixtures; a real smoke test must be explicitly authorized because it can incur cost. Phase 6 can add durable Redis coordination, richer pricing, moderation, reconnect reconciliation, and model capability discovery.
