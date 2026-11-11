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

The database integration tests require a disposable PostgreSQL database. Set `TEST_DATABASE_URL` to its `postgresql+asyncpg://...` URL before running `pytest`; the fixture creates and drops the schema in that database for each test. Never point it at a shared or production database.

The full table, relationship, ownership, constraint, and migration notes are in [`docs/database-schema.md`](docs/database-schema.md).

Authentication setup and security behavior are documented in [`docs/authentication.md`](docs/authentication.md).

Advanced conversation history, folders, search, exports, bulk actions, and read-only sharing are documented in [`docs/conversation-management.md`](docs/conversation-management.md). The database schema and migration procedure are documented in [`docs/database-schema.md`](docs/database-schema.md), with security boundaries in [`docs/security.md`](docs/security.md).

The Phase 4 workspace architecture, API contract, security boundary, and Phase 5 handoff are documented in [`docs/chat-workspace.md`](docs/chat-workspace.md).

Phase 5 OpenAI Responses streaming, generation lifecycle, usage controls, and SSE protocol are documented in [`docs/ai-streaming.md`](docs/ai-streaming.md).

Phase 7 document upload, private storage, extraction, pgvector indexing, grounded retrieval, citation events, worker setup, limits, and privacy behavior are documented in [`docs/document-chat.md`](docs/document-chat.md) and [`docs/rag-architecture.md`](docs/rag-architecture.md).

The backend exposes `GET /health` for service status and `GET /api/v1/health` for versioned API status. Phase 5 makes real provider calls only when `OPENAI_API_KEY` is configured. Phase 6 management APIs never broaden owner access and public share links expose immutable read-only snapshots only.

For document processing with multiple workers, configure `REDIS_URL` and run `arq app.worker.WorkerSettings` from `backend`. Without an OpenAI key, uploads can be validated and parsed locally but embedding and grounded retrieval cannot complete. No paid OpenAI request is made by the test suite.
