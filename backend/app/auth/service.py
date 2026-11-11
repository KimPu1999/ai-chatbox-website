from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import generate_token, hash_token, session_expiration, utc_now
from app.core.config import get_settings
from app.models import (
    AuditLog,
    EmailVerificationToken,
    PasswordResetToken,
    Session,
    User,
)


async def create_session(db: AsyncSession, user: User) -> tuple[Session, str]:
    raw_token = generate_token()
    session = Session(
        id=uuid4(),
        user_id=user.id,
        token_hash=hash_token(raw_token),
        expires_at=session_expiration(),
        last_activity_at=utc_now(),
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session, raw_token


async def create_email_verification_token(db: AsyncSession, user: User) -> str:
    raw_token = generate_token()
    await db.execute(
        delete(EmailVerificationToken).where(EmailVerificationToken.user_id == user.id)
    )
    db.add(
        EmailVerificationToken(
            user_id=user.id,
            token_hash=hash_token(raw_token),
            expires_at=utc_now()
            + timedelta(minutes=get_settings().email_verification_expire_minutes),
        )
    )
    await db.commit()
    return raw_token


async def create_reset_token(db: AsyncSession, user: User) -> str:
    raw_token = generate_token()
    await db.execute(delete(PasswordResetToken).where(PasswordResetToken.user_id == user.id))
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_token(raw_token),
            expires_at=utc_now() + timedelta(minutes=get_settings().password_reset_expire_minutes),
        )
    )
    await db.commit()
    return raw_token


async def revoke_all_sessions(db: AsyncSession, user_id: UUID) -> None:
    await db.execute(
        update(Session)
        .where(Session.user_id == user_id, Session.revoked_at.is_(None))
        .values(revoked_at=utc_now())
    )
    await db.commit()


async def record_audit(
    db: AsyncSession,
    *,
    user_id: UUID | None,
    action: str,
    entity_type: str,
    entity_id: UUID | None = None,
) -> None:
    db.add(
        AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
        )
    )
    await db.commit()
