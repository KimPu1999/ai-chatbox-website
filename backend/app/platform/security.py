from __future__ import annotations

# ruff: noqa: E501
import secrets
from datetime import timedelta

import pyotp
from cryptography.fernet import Fernet

from app.auth.security import hash_token, utc_now
from app.core.config import get_settings

PLATFORM_PERMISSIONS: dict[str, frozenset[str]] = {
    "platform.overview.read": frozenset({"admin", "superadmin"}),
    "platform.users.read": frozenset({"admin", "superadmin"}),
    "platform.users.status.update": frozenset({"admin", "superadmin"}),
    "platform.users.role.update": frozenset({"superadmin"}),
    "platform.usage.read": frozenset({"admin", "superadmin"}),
    "platform.costs.read": frozenset({"admin", "superadmin"}),
    "platform.models.read": frozenset({"admin", "superadmin"}),
    "platform.models.update": frozenset({"superadmin"}),
    "platform.quotas.read": frozenset({"admin", "superadmin"}),
    "platform.quotas.update": frozenset({"superadmin"}),
    "platform.storage.read": frozenset({"admin", "superadmin"}),
    "platform.audit.read": frozenset({"superadmin"}),
    "platform.health.read": frozenset({"admin", "superadmin"}),
    "platform.settings.update": frozenset({"superadmin"}),
    "platform.operations.read": frozenset({"admin", "superadmin"}),
    "platform.feature_flags.read": frozenset({"admin", "superadmin"}),
    "platform.feature_flags.update": frozenset({"superadmin"}),
    "platform.support.read": frozenset({"admin", "superadmin"}),
    "platform.support.update": frozenset({"admin", "superadmin"}),
    "platform.plans.read": frozenset({"admin", "superadmin"}),
    "platform.plans.update": frozenset({"superadmin"}),
}


def has_permission(role: str, permission: str) -> bool:
    return role in PLATFORM_PERMISSIONS.get(permission, frozenset())


def _fernet() -> Fernet:
    key = get_settings().platform_mfa_encryption_key
    if not key:
        raise RuntimeError("PLATFORM_MFA_ENCRYPTION_KEY is not configured")
    try:
        return Fernet(key.encode())
    except (ValueError, TypeError) as exc:
        raise RuntimeError("PLATFORM_MFA_ENCRYPTION_KEY is invalid") from exc


def encrypt_mfa_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode()).decode()


def decrypt_mfa_secret(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode()).decode()
    except Exception as exc:  # noqa: BLE001 - never expose crypto details to callers
        raise RuntimeError("Stored MFA credential could not be decrypted") from exc


def new_totp_secret() -> str:
    return pyotp.random_base32()


def provisioning_uri(secret: str, email: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=get_settings().platform_mfa_issuer)


def new_recovery_codes(count: int = 10) -> list[str]:
    return [secrets.token_urlsafe(12) for _ in range(count)]


def recovery_code_hash(code: str) -> str:
    return hash_token(code.strip())


def mfa_is_recent(verified_at) -> bool:
    return bool(verified_at and verified_at >= utc_now() - timedelta(minutes=get_settings().platform_mfa_recent_minutes))

