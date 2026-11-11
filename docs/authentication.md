# PyChat AI authentication

Phase 3 uses cookie backed, server side sessions. The browser receives an opaque random session token in an HttpOnly cookie; PostgreSQL stores only its SHA-256 hash. Session cookies use `pychat_session` for explicit local HTTP development and `__Host-pychat_session` when `COOKIE_SECURE=true`. Production must use HTTPS, an exact `FRONTEND_URL`, and exact `ALLOWED_ORIGINS` values.

## Run locally

```bash
cd backend
source .venv/bin/activate
cp ../.env.example ../.env
alembic -c alembic.ini upgrade head
python -m uvicorn app.main:app --reload --port 8000

cd ../frontend
npm install
npm run dev
```

Use the same hostname on both sides. `http://localhost:5173` and `http://127.0.0.1:5173` are different origins and must be listed separately if both are used. The frontend never stores session or reset credentials in localStorage or sessionStorage. Axios uses `withCredentials`, retrieves a session-bound CSRF token from `GET /api/v1/auth/csrf`, and sends it in `X-CSRF-Token` for unsafe authenticated requests.

## Authentication behavior

- Registration always creates `user` role accounts. Roles are never accepted from public payloads.
- New users must verify email before protected chat access.
- Login creates a fresh opaque session. Absolute lifetime and idle timeout are enforced server-side.
- Logout, logout-all, password change, password reset, expiry, suspension, and deletion revoke sessions.
- Forgot-password responses are generic to avoid account enumeration.
- Optional breached-password checking uses a configured k-anonymity range service. It is disabled by default and failures fail open so account creation does not depend on an external service.
- Verification and reset tokens are single-use, expiring, randomly generated, and stored only as hashes.
- `401` means no valid session. `403` means a valid session lacks verification or permission, or the CSRF/origin check failed.
- Administrators can manage regular user status. Superadmin role changes require explicit server-side checks. The first superadmin is created only through the local bootstrap command.

## Bootstrap the first superadmin

Run this only against the intended local or deployment database, with an explicit confirmation and an interactive password prompt:

```bash
cd backend
PYCHAT_BOOTSTRAP_CONFIRM=YES .venv/bin/python scripts/bootstrap_superadmin.py admin@example.com
```

The command refuses to run without confirmation and refuses to create a second superadmin. It never accepts a password or role from a public API request.

## Email delivery

Set `EMAIL_PROVIDER=local` with an empty `SMTP_HOST` for development, or provide SMTP/Mailpit settings. Verification and recovery links are constructed from the configured `FRONTEND_URL`. Tokens are never written to logs or returned in production responses.

## Testing

Use a disposable PostgreSQL database for integration tests:

```bash
cd backend
TEST_DATABASE_URL='postgresql+asyncpg://user:password@localhost:5432/pychat_test' .venv/bin/python -m pytest -q
```

The integration fixture skips unless `TEST_DATABASE_URL` is a PostgreSQL async URL. Never point it at development, shared, or production data.
