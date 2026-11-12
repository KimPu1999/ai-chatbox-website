# PyChat AI

PyChat AI is a modular AI chat application with secure sessions, persistent conversations, Responses API streaming, and advanced conversation management.

## Stack

- Python 3.11+, FastAPI, Pydantic Settings, SQLAlchemy 2 async ORM, Alembic
- PostgreSQL with asyncpg in production
- React, TypeScript, Vite, Tailwind CSS
- pytest and Vitest

## Local setup

1. Copy `.env.example` to `backend/.env` and set the values for your environment.
2. Start PostgreSQL with the pgvector extension available and set `DATABASE_URL` to the async PostgreSQL URL.
3. Install backend dependencies and run migrations:

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

4. Install and run the frontend:

```bash
cd frontend
npm install
npm run dev
```

The API is available at `http://localhost:8000`, with Swagger UI at `/docs` and ReDoc at `/redoc`. The Vite development server proxies `/api` to the API at `http://localhost:8000`.

## Checks

```bash
(cd backend && .venv/bin/pytest -q)
(cd frontend && npm run typecheck && npm run build && npm run test)
```

The database integration tests require a disposable PostgreSQL database with pgvector. Set `TEST_DATABASE_URL` to its `postgresql+asyncpg://...` URL before running `pytest`; the fail-closed fixture requires a database name ending in `_test`, `_testing`, or `_phase9`, runs `alembic upgrade head`, and truncates only that guarded test database. Never point it at a shared, development, or production database.

The full table, relationship, ownership, constraint, and migration notes are in [`docs/database-schema.md`](docs/database-schema.md).

Authentication setup and security behavior are documented in [`docs/authentication.md`](docs/authentication.md).

Advanced conversation history, folders, search, exports, bulk actions, and read-only sharing are documented in [`docs/conversation-management.md`](docs/conversation-management.md). The database schema and migration procedure are documented in [`docs/database-schema.md`](docs/database-schema.md), with security boundaries in [`docs/security.md`](docs/security.md).

The Phase 4 workspace architecture, API contract, security boundary, and Phase 5 handoff are documented in [`docs/chat-workspace.md`](docs/chat-workspace.md).

Phase 5 OpenAI Responses streaming, generation lifecycle, usage controls, and SSE protocol are documented in [`docs/ai-streaming.md`](docs/ai-streaming.md).

Phase 7 document upload, private storage, extraction, pgvector indexing, grounded retrieval, citation events, worker setup, limits, and privacy behavior are documented in [`docs/document-chat.md`](docs/document-chat.md) and [`docs/rag-architecture.md`](docs/rag-architecture.md).

Phase 8 platform administration, MFA, permission enforcement, usage/cost analytics, quotas, storage monitoring, audit logs, health, and the bootstrap procedure are documented in [`docs/platform-admin.md`](docs/platform-admin.md), [`docs/platform-security.md`](docs/platform-security.md), and [`docs/usage-cost-accounting.md`](docs/usage-cost-accounting.md).

Phase 9 audit findings, test infrastructure, OWASP review, CI quality gate,
performance limits, production blockers, and backup/recovery procedures are in
[`docs/phase9-audit.md`](docs/phase9-audit.md), [`docs/testing-strategy.md`](docs/testing-strategy.md),
[`docs/owasp-assessment.md`](docs/owasp-assessment.md), [`docs/ci-cd.md`](docs/ci-cd.md),
[`docs/performance-report.md`](docs/performance-report.md), [`docs/production-readiness.md`](docs/production-readiness.md),
and [`docs/backup-recovery.md`](docs/backup-recovery.md).

Phase 10 production deployment configuration, Docker/Compose, Railway API and
worker services, Neon migration procedures, Cloudflare R2 storage, Vercel
configuration, launch gates and deployment blockers are documented in
[`docs/deployment-readiness.md`](docs/deployment-readiness.md).

The backend exposes `GET /health` for service status and `GET /api/v1/health` for versioned API status. Phase 5 makes real provider calls only when `OPENAI_API_KEY` is configured. Phase 6 management APIs never broaden owner access and public share links expose immutable read-only snapshots only.

For document processing with multiple workers, configure `REDIS_URL` and run `arq app.worker.WorkerSettings` from `backend`. Without an OpenAI key, uploads can be validated and parsed locally but embedding and grounded retrieval cannot complete. No paid OpenAI request is made by the test suite.

For a bounded provider-free performance check, install `perf/requirements.txt`,
set `PYCHAT_LOAD_TEST_ACK=isolated`, and use the Locust command in
[`docs/performance-report.md`](docs/performance-report.md). Do not target a
production service.
