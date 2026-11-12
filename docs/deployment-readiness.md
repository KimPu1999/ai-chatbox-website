# Production deployment readiness

Phase 10 adds deployment artifacts for the intended topology:

```text
Vercel SPA -> Railway API -> Neon PostgreSQL
                    |       
                    +-> Railway Redis -> Railway ARQ worker
                    +-> Cloudflare R2 private objects
```

No cloud account was connected and no production deployment was attempted.
The release is ready for a controlled staging deployment after the blockers
below are completed.

## Configuration contract

`backend/app/core/config.py` accepts the new deployment names while retaining
the Phase 1–9 names as aliases. In `staging` and `production`, startup fails
when the database, migration database, Redis, OpenAI key, session secret, MFA
encryption key, HTTPS URLs, trusted host or R2 settings are missing. `DEBUG`
must be false, `COOKIE_SECURE` must be true and wildcard CORS/trusted hosts are
rejected.

Only `VITE_*` values belong in the Vercel project. They are compiled into the
browser and must contain public configuration such as `VITE_API_BASE_URL`,
never API keys or database credentials.

## API and worker images

- `backend/Dockerfile` uses Python 3.11.11 slim, installs the generated
  `requirements.runtime.lock` plus only runtime system libraries, runs as UID
  10001 and listens on Railway's `PORT`.
- The API image uses `/health/ready` as its bounded readiness probe.
- `deploy/railway-api.toml` starts only the API. It does not run migrations on
  every replica.
- `deploy/railway-worker.toml` starts `arq app.worker.WorkerSettings`.
- `backend/.dockerignore` excludes local environments, tests, private storage,
  logs and dotenv files.

Build locally when Docker is installed:

```bash
docker build -f backend/Dockerfile . -t pychat-ai-api:local
docker run --rm -p 8000:8000 \
  -e APP_ENV=development \
  -e DATABASE_URL=postgresql+asyncpg://host.docker.internal:5432/pychat \
  pychat-ai-api:local
```

Docker was unavailable in the implementation environment, so these commands
were not executed here.

## Local services

```bash
docker compose -f deploy/docker-compose.dev.yml up --build
docker compose -f deploy/docker-compose.dev.yml --profile mail up --build
```

The Compose file uses persistent development-only volumes for PostgreSQL,
Redis and private local files. Ports bind to `127.0.0.1`; no production
credentials are mounted. Mailpit is optional and available at
`http://localhost:8025`.

## Neon and migration release

Use Neon pooled runtime connections only for API traffic and a direct or
dedicated migration connection for Alembic. The SQLAlchemy adapter normalizes
`postgresql://` URLs to `postgresql+asyncpg://`, disables asyncpg prepared
statement caching for pooler compatibility and supports `sslmode=require`.
For certificate verification, provide `DB_SSL_CA_FILE` and use
`sslmode=verify-full`.

Validate a Neon database before a release:

```sql
SELECT version();
SELECT current_database(), current_user;
CREATE EXTENSION IF NOT EXISTS vector;
SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';
```

Confirm the configured embedding dimension remains 1536 before indexing.

Run one migration executor from the backend directory:

```bash
cd backend
export MIGRATION_DATABASE_URL='postgresql+asyncpg://MIGRATOR:PASSWORD@HOST/DB?sslmode=require'
.venv/bin/python -m app.cli.migrate_release
.venv/bin/alembic current
.venv/bin/alembic heads
.venv/bin/alembic check
```

The release command takes a PostgreSQL advisory lock and invokes
`alembic upgrade head`. Take a provider backup/PITR checkpoint before running
it. Restore the checkpoint into a separate database if a migration fails;
never downgrade production blindly or run migrations from every API/worker
replica.

## Launch gates

- Set Railway API healthcheck path to `/health/ready`; this checks PostgreSQL
  and configured Redis but never calls OpenAI.
- Set exact `CORS_ORIGINS`, `TRUSTED_HOSTS`, `FRONTEND_URL` and
  `API_PUBLIC_URL` values for the deployed domains.
- Configure the worker with the same database, Redis and R2 settings.
- Configure a fail-closed malware scanner before enabling production uploads.
- Verify R2 lifecycle/retention, Neon backups/PITR, Redis recovery assumptions,
  SMTP delivery, MFA enrollment and the first superadmin bootstrap.
- Run staging smoke tests using a fake provider or zero-cost disabled AI mode;
  no paid OpenAI call is part of CI or deployment validation.

The manual `.github/workflows/production-smoke.yml` workflow only checks the
public health endpoints and requires a GitHub `production` environment. It does
not authenticate as a user, mutate data or call OpenAI. Run the same check
locally with:

```bash
python deploy/smoke.py --base-url https://api.example.com
```

For a Vercel deployment, set the public build variable
`VITE_API_BASE_URL=https://api.example.com/api/v1`. The SPA rewrite serves
frontend routes; it is not an API proxy, so the browser must use the Railway
API origin and that origin must allow the exact Vercel origin in CORS.

Railway healthchecks are deployment readiness checks rather than continuous
monitoring; keep external uptime/metrics monitoring configured separately.

## Current blockers

Cloud credentials, domains, DNS, Neon, Railway, Vercel and R2 were not
connected. Docker image build, cloud migration, backup restore and staging
smoke tests therefore remain **NOT RUN**. Production should remain blocked until
those steps are completed and reviewed.

## Validation recorded on 2026-11-12

- **PASSED**: backend Ruff and local regression suite: 29 passed, 4 skipped.
- **PASSED**: isolated PostgreSQL integration suite: 33 passed; Alembic current
  is `0011_platform_schema_alignment (head)` and `alembic check` reports no
  pending operations.
- **PASSED**: Bandit reported no medium/high findings; `pip-audit` reported no
  known vulnerabilities for application and runtime lock requirements;
  `npm audit --audit-level=high` reported 0 vulnerabilities.
- **PASSED**: frontend TypeScript check, 6 Vitest files/8 tests, production
  build, Compose YAML parsing and Python deployment utility compilation.
- **LIMITATION**: measured backend coverage is 51% (33 tests); the Phase 9
  85% target is not met.
- **WARNING**: Vite production output still contains bundles above 500 kB after
  minification and should be code-split before a performance-sensitive launch.
- **NOT RUN**: Docker image build, cloud migrations, R2 verification, backup
  restore drill, Playwright in this macOS environment and paid OpenAI smoke
  testing. Docker is unavailable locally and cloud credentials are not
  connected.
