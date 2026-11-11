from datetime import timedelta

import pyotp

from app.auth.security import utc_now
from app.platform.security import (
    PLATFORM_PERMISSIONS,
    has_permission,
    mfa_is_recent,
    recovery_code_hash,
)


def test_platform_permission_matrix_is_default_deny() -> None:
    assert has_permission("admin", "platform.overview.read")
    assert has_permission("superadmin", "platform.settings.update")
    assert not has_permission("user", "platform.overview.read")
    assert not has_permission("admin", "platform.users.role.update")
    assert "platform.audit.read" in PLATFORM_PERMISSIONS


def test_recovery_hash_is_deterministic_but_not_plaintext() -> None:
    value = "recovery-code-example"
    assert recovery_code_hash(value) == recovery_code_hash(value)
    assert value not in recovery_code_hash(value)


def test_mfa_recent_window() -> None:
    assert mfa_is_recent(utc_now())
    assert not mfa_is_recent(utc_now() - timedelta(hours=2))
    assert pyotp.random_base32()
