# PyChat AI

Phase 1 establishes the production foundation for a modular AI chat application.

## Stack

- Python 3.11+, FastAPI, Pydantic Settings, SQLAlchemy 2 async ORM, Alembic
- PostgreSQL with asyncpg in production
- React, TypeScript, Vite, Tailwind CSS
- pytest and Vitest

## Local setup

1. Copy `.env.example` to `.env` and set the values for your environment.
2. Start PostgreSQL and set `DATABASE_URL` to the async PostgreSQL URL.
3. Install backend dependencies and run migrations:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
alembic -c backend/alembic.ini upgrade head
uvicorn app.main:app --app-dir backend --reload
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
pytest -q
cd frontend && npm run typecheck && npm run build && npm run test
```

The database integration tests require a disposable PostgreSQL database. Set `TEST_DATABASE_URL` to its `postgresql+asyncpg://...` URL before running `pytest`; the fixture creates and drops the schema in that database for each test. Never point it at a shared or production database.

The full table, relationship, ownership, constraint, and migration notes are in [`docs/database-schema.md`](docs/database-schema.md).

Authentication setup and security behavior are documented in [`docs/authentication.md`](docs/authentication.md).

The Phase 4 workspace architecture, API contract, security boundary, and Phase 5 handoff are documented in [`docs/chat-workspace.md`](docs/chat-workspace.md).

The backend exposes `GET /health` for service status and `GET /api/v1/health` for versioned API status. Phase 4 persists authenticated user messages but does not make AI provider calls or return fabricated assistant responses; streaming generation belongs to Phase 5.
