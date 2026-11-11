# Platform Admin Control Center

Phase 8 adds a separate platform session and a server-enforced admin control plane. Normal user sessions use `pychat_session`; platform sessions use `pychat_platform_session` (or the `__Host-` form in HTTPS deployments). Platform endpoints require a verified active `admin` or `superadmin` account and a recent TOTP MFA verification.

## Bootstrap

Generate a Fernet key and put it in the trusted backend environment:

```bash
cd backend
./.venv/bin/python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
```

Set `PLATFORM_MFA_ENCRYPTION_KEY` and temporarily set `PLATFORM_BOOTSTRAP_ENABLED=true`. Then run:

```bash
./.venv/bin/python -m app.cli.bootstrap_superadmin
```

The command reads the email and password interactively, never from command-line arguments. It creates an already verified first superadmin through the trusted local/deployment process, encrypts the TOTP secret, stores only recovery-code hashes, and prints enrollment values once. Disable bootstrap immediately afterward. A second superadmin cannot be created by repeating this command.

## API surface

Authentication is under `/api/v1/platform/auth`: login, MFA enrollment/verification, CSRF, current platform identity and logout. Permission-protected routes provide `/overview`, `/users`, `/usage/summary`, `/usage/trends`, `/usage/by-model`, `/costs`, `/models`, `/quotas`, `/storage`, `/storage/jobs`, `/audit-logs`, `/health`, and `/settings`.

Overview and analytics are calculated from `users`, `conversations`, `generation_runs`, `ai_usage`, `documents`, and processing jobs. `usage_aggregates_daily` is intentionally a rebuildable projection. A missing provider usage or pricing value is exposed as unknown rather than silently treated as confirmed zero. Application estimates are separate from OpenAI organization billing.

## Permissions

`admin` can read overview, users, usage, costs, models, quotas, storage, and health, and can manage ordinary user status. `superadmin` additionally manages roles, models, quotas, audit logs, and platform settings. Backend dependencies enforce this matrix; React route guards only improve navigation UX. Role changes and status changes protect the last active superadmin and revoke affected sessions.

## Local run

```bash
cd backend
source .venv/bin/activate
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Open `http://localhost:5173/platform/login`. With no `OPENAI_API_KEY`, the health page reports OpenAI as unconfigured and no paid request is made. Redis health is reported as unconfigured when `REDIS_URL` is empty.
