"""Create the first superadmin from a trusted administrative terminal.

Run from the backend directory. The command is intentionally disabled by
default and never accepts credentials as command-line arguments.
"""

# ruff: noqa: E501

import asyncio
import getpass
from datetime import datetime, timezone

import pyotp
from sqlalchemy import func, select

from app.auth.security import hash_password, validate_password
from app.auth.service import record_audit
from app.core.config import get_settings
from app.db import SessionLocal
from app.models import AccountStatus, AdminMFACredential, AdminRecoveryCode, User, UserRole
from app.platform.security import (
    encrypt_mfa_secret,
    new_recovery_codes,
    provisioning_uri,
    recovery_code_hash,
)
from app.repositories.users import normalize_email


async def bootstrap() -> None:
    settings = get_settings()
    if not settings.platform_bootstrap_enabled:
        raise SystemExit("Bootstrap disabled. Set PLATFORM_BOOTSTRAP_ENABLED=true for this one-time trusted operation.")
    if settings.environment.lower() not in {"local", "development"} and settings.platform_bootstrap_environment != settings.environment.lower():
        raise SystemExit("Bootstrap environment authorization does not match the deployment environment.")
    if not settings.platform_mfa_encryption_key:
        raise SystemExit("PLATFORM_MFA_ENCRYPTION_KEY must be configured before bootstrap.")
    email = normalize_email(input("Superadmin email: "))
    password = getpass.getpass("Superadmin password (8-12 characters): ")
    confirmation = getpass.getpass("Repeat password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match.")
    try:
        validate_password(password)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    async with SessionLocal() as db:
        existing_admin = await db.scalar(select(func.count(User.id)).where(User.role == UserRole.superadmin.value))
        if existing_admin:
            raise SystemExit("A superadmin already exists. Bootstrap is one-time and will not modify it.")
        if await db.scalar(select(User).where(User.email_normalized == email)):
            raise SystemExit("An account with this email already exists.")
        now = datetime.now(timezone.utc)
        user = User(email=email, email_normalized=email, password_hash=hash_password(password), role=UserRole.superadmin.value, account_status=AccountStatus.active.value, email_verified_at=now, is_active=True)
        db.add(user)
        await db.flush()
        secret = pyotp.random_base32()
        credential = AdminMFACredential(user_id=user.id, encrypted_secret=encrypt_mfa_secret(secret))
        db.add(credential)
        recovery_codes = new_recovery_codes()
        await db.flush()
        db.add_all([AdminRecoveryCode(mfa_credential_id=credential.id, code_hash=recovery_code_hash(code)) for code in recovery_codes])
        await db.commit()
        await record_audit(db, user_id=user.id, action="platform.bootstrap.superadmin", entity_type="user", entity_id=user.id, metadata={"trusted_cli": True})
    print("Superadmin created. Store these MFA recovery values in a secure password manager.")
    print(f"TOTP secret: {secret}")
    print(f"Provisioning URI: {provisioning_uri(secret, email)}")
    print("Recovery codes:")
    for code in recovery_codes:
        print(code)


def main() -> None:
    asyncio.run(bootstrap())


if __name__ == "__main__":
    main()
