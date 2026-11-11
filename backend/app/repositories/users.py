from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


def normalize_email(email: str) -> str:
    return email.strip().casefold()


async def get_by_id(db: AsyncSession, user_id: UUID) -> User | None:
    return await db.get(User, user_id)


async def get_by_email(db: AsyncSession, email: str) -> User | None:
    return await db.scalar(select(User).where(User.email_normalized == normalize_email(email)))


async def create_user(
    db: AsyncSession, *, email: str, password_hash: str, display_name: str | None = None
) -> User:
    user = User(
        email=email.strip(),
        email_normalized=normalize_email(email),
        password_hash=password_hash,
        display_name=display_name,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
