import os
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db import Base
from app.models import Conversation, Message, User
from app.repositories.conversations import list_for_user

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL.startswith("postgresql+asyncpg://"),
    reason="Set TEST_DATABASE_URL to an isolated PostgreSQL database to run integration tests",
)


@pytest.fixture
async def db_session():
    engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await engine.dispose()


async def test_conversation_listing_is_isolated_by_user(db_session: AsyncSession) -> None:
    first_user = User(email="first@example.com", email_normalized="first@example.com")
    second_user = User(email="second@example.com", email_normalized="second@example.com")
    db_session.add_all([first_user, second_user])
    await db_session.flush()
    db_session.add_all(
        [
            Conversation(user_id=first_user.id, title="First private chat"),
            Conversation(user_id=second_user.id, title="Second private chat"),
        ]
    )
    await db_session.commit()

    rows = await list_for_user(db_session, first_user.id)
    assert [row.title for row in rows] == ["First private chat"]


async def test_database_rejects_cross_user_message_ownership(db_session: AsyncSession) -> None:
    first_user = User(email="owner@example.com", email_normalized="owner@example.com")
    second_user = User(email="attacker@example.com", email_normalized="attacker@example.com")
    db_session.add_all([first_user, second_user])
    await db_session.flush()
    conversation = Conversation(user_id=first_user.id, title="Private")
    db_session.add(conversation)
    await db_session.flush()
    db_session.add(
        Message(
            id=uuid4(),
            conversation_id=conversation.id,
            user_id=second_user.id,
            role="user",
            content="cross-user write",
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()
