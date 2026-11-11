"""Create the first superadmin through an explicit local-only bootstrap."""

import argparse
import asyncio
import getpass
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import select

from app.auth.security import hash_password, validate_password
from app.db import SessionLocal
from app.models import AccountStatus, User, UserRole
from app.repositories.users import normalize_email


async def bootstrap(email: str, password: str) -> None:
    async with SessionLocal() as db:
        existing = await db.scalar(
            select(User).where(User.email_normalized == normalize_email(email))
        )
        if existing:
            raise RuntimeError("A user with that email already exists")
        count = await db.scalar(select(User.id).where(User.role == UserRole.superadmin).limit(1))
        if count:
            raise RuntimeError("A superadmin already exists")
        user = User(
            email=email.strip(),
            email_normalized=normalize_email(email),
            password_hash=hash_password(password),
            role=UserRole.superadmin,
            account_status=AccountStatus.active,
        )
        from app.auth.security import utc_now

        user.email_verified_at = utc_now()
        db.add(user)
        await db.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the first PyChat superadmin")
    parser.add_argument("email")
    args = parser.parse_args()
    if os.getenv("PYCHAT_BOOTSTRAP_CONFIRM") != "YES":
        raise SystemExit("Set PYCHAT_BOOTSTRAP_CONFIRM=YES for an explicit local bootstrap")
    password = getpass.getpass("Superadmin password: ")
    try:
        validate_password(password)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    asyncio.run(bootstrap(args.email, password))
    print("Superadmin created")


if __name__ == "__main__":
    main()
