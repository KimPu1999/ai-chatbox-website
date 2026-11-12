# Testing strategy

The project uses three layers.

1. **Unit tests** run without PostgreSQL and cover password policy, Argon2
   verification, token hashing, provider event translation, cursor validation,
   document parsing/chunking, permission matrices and cost/time helpers.
2. **Integration tests** use PostgreSQL plus pgvector. `backend/tests/conftest.py`
   requires a URL using `postgresql+asyncpg` whose database name ends in
   `_test`, `_testing` or `_phase9`. It runs Alembic before tests and refuses
   development/production names. It resets only that guarded test database.
3. **Browser tests** live in `frontend/e2e/` and use Playwright role/selectors,
   desktop and mobile projects, traces and screenshots on failure. The checked-in
   smoke tests cover protected routes and accessible auth surfaces. Full seeded
   register/verify/stream/RAG/admin journeys require the dedicated E2E seed
   harness and fake providers; they are not silently represented as passing.

The latest isolated backend coverage run was 52% overall. This is below the
85% project target, so the release gate must keep the coverage gap visible while
the critical authentication, MFA, ownership and configuration paths remain
covered by focused tests.

Run the local suites:

```bash
backend/.venv/bin/pytest -q
TEST_DATABASE_URL='postgresql+asyncpg://USER@127.0.0.1:5432/pychat_phase9_test' backend/.venv/bin/pytest -q
cd frontend && npm run typecheck && npm run test -- --run && npm run build
cd frontend && npx playwright install chromium && npm run test:e2e
```

Use an isolated Redis database such as `redis://127.0.0.1:6379/9` for tests.
Fake email/provider objects belong in test fixtures only; production routes never
return synthetic AI output.
