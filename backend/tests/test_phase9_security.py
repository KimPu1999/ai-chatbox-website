from datetime import timedelta
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient

from app.auth.security import hash_token, utc_now
from app.core.config import Settings
from app.main import _safe_request_path, app
from app.models import AccountStatus, Session, User, UserRole
from app.platform import security
from app.platform.dependencies import platform_cookie_name
from app.platform.security import has_permission, mfa_is_recent


@pytest.mark.asyncio
async def test_api_security_headers_and_request_id_are_present() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health", headers={"X-Request-ID": "phase9-test"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "phase9-test"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"


@pytest.mark.asyncio
async def test_unauthenticated_users_cannot_reach_platform_api() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/platform/overview")

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "PLATFORM_AUTH_REQUIRED"


@pytest.mark.asyncio
async def test_platform_cookie_without_mfa_cannot_read_control_center(
    test_client, isolated_test_session
) -> None:
    user = User(
        email="phase9-admin@example.com",
        email_normalized="phase9-admin@example.com",
        role=UserRole.admin.value,
        account_status=AccountStatus.active.value,
        email_verified_at=utc_now(),
    )
    isolated_test_session.add(user)
    await isolated_test_session.flush()
    raw_token = "phase9-platform-session-token"
    isolated_test_session.add(
        Session(
            user_id=user.id,
            token_hash=hash_token(raw_token),
            session_kind="platform",
            expires_at=utc_now() + timedelta(hours=1),
            last_activity_at=utc_now(),
        )
    )
    await isolated_test_session.commit()
    test_client.cookies.set(platform_cookie_name(), raw_token)

    response = await test_client.get("/api/v1/platform/overview")

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "PLATFORM_MFA_STEP_UP_REQUIRED"


@pytest.mark.asyncio
async def test_platform_mfa_verified_session_can_read_overview(
    test_client, isolated_test_session
) -> None:
    user = User(
        email="phase9-mfa-admin@example.com",
        email_normalized="phase9-mfa-admin@example.com",
        role=UserRole.admin.value,
        account_status=AccountStatus.active.value,
        email_verified_at=utc_now(),
    )
    isolated_test_session.add(user)
    await isolated_test_session.flush()
    raw_token = "phase9-platform-mfa-session-token"
    isolated_test_session.add(
        Session(
            user_id=user.id,
            token_hash=hash_token(raw_token),
            session_kind="platform",
            expires_at=utc_now() + timedelta(hours=1),
            last_activity_at=utc_now(),
            mfa_verified_at=utc_now(),
        )
    )
    await isolated_test_session.commit()
    test_client.cookies.set(platform_cookie_name(), raw_token)

    response = await test_client.get("/api/v1/platform/overview")

    assert response.status_code == 200
    assert response.json()["total_users"] >= 1


@pytest.mark.asyncio
async def test_untrusted_host_is_rejected() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health", headers={"host": "evil.example"})

    assert response.status_code == 400


def test_platform_permission_matrix_defaults_to_deny() -> None:
    assert has_permission("user", "platform.overview.read") is False
    assert has_permission("admin", "platform.users.role.update") is False
    assert has_permission("superadmin", "platform.settings.update") is True


def test_mfa_secret_is_encrypted_at_rest(monkeypatch: pytest.MonkeyPatch) -> None:
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(
        security,
        "get_settings",
        lambda: SimpleNamespace(platform_mfa_encryption_key=key, platform_mfa_issuer="Test"),
    )
    encrypted = security.encrypt_mfa_secret("totp-secret")
    assert encrypted != "totp-secret"
    assert security.decrypt_mfa_secret(encrypted) == "totp-secret"


def test_production_settings_reject_wildcard_trusted_hosts() -> None:
    with pytest.raises(ValueError, match="wildcard"):
        Settings(environment="production", cookie_secure=True, trusted_hosts=["*"])


def test_production_settings_require_explicit_trusted_host() -> None:
    with pytest.raises(ValueError, match="explicit deployment host"):
        Settings(environment="production", cookie_secure=True)


def test_recent_mfa_is_time_bounded() -> None:
    assert mfa_is_recent(None) is False


def test_public_share_tokens_are_redacted_from_request_paths() -> None:
    assert _safe_request_path("/api/v1/shared/secret-share-token") == "/api/v1/shared/[redacted]"
    assert _safe_request_path("/api/v1/conversations/123") == "/api/v1/conversations/123"
