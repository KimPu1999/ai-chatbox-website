"""Shared isolated integration-test infrastructure.

The application uses PostgreSQL-specific features (JSONB, TSVECTOR and
pgvector), so SQLite is intentionally not used as the integration database.
The guard below is deliberately strict: a test URL must be an explicit
PostgreSQL database whose name identifies it as a test database.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db import get_db  # noqa: E402
from app.main import app  # noqa: E402


def isolated_database_url() -> URL:
    raw = os.getenv("TEST_DATABASE_URL", "").strip()
    if not raw:
        pytest.skip("Set TEST_DATABASE_URL to an isolated PostgreSQL database")
    parsed = make_url(raw)
    database = (parsed.database or "").lower()
    if parsed.drivername != "postgresql+asyncpg":
        raise RuntimeError("TEST_DATABASE_URL must use postgresql+asyncpg")
    if any(marker in database for marker in ("prod", "production", "develop", "development")):
        raise RuntimeError("Refusing to run tests against a development or production database")
    if not (
        database.endswith("_test")
        or database.endswith("_testing")
        or database.endswith("_phase9")
        or database in {"test", "testing"}
    ):
        raise RuntimeError(
            "TEST_DATABASE_URL database name must end in _test, _testing, or _phase9"
        )
    return parsed


@pytest.fixture(scope="session")
def test_database_url() -> Iterator[str]:
    yield str(isolated_database_url())


@pytest.fixture(scope="session")
def migrated_test_database(test_database_url: str) -> Iterator[str]:
    """Upgrade the isolated database through Alembic before integration tests."""
    environment = os.environ.copy()
    environment["DATABASE_URL"] = test_database_url
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.fail(
            "Alembic upgrade failed for the isolated test database:\n"
            f"{result.stdout}\n{result.stderr}"
        )
    yield test_database_url


@pytest_asyncio.fixture
async def test_engine(migrated_test_database: str) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(migrated_test_database, pool_pre_ping=True)
    yield engine
    await engine.dispose()


async def _truncate_test_tables(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        table_names = list(
            (
                await connection.execute(
                    text(
                        "SELECT quote_ident(tablename) "
                        "FROM pg_tables WHERE schemaname = 'public' "
                        "AND tablename <> 'alembic_version'"
                    )
                )
            ).scalars()
        )
        if table_names:
            await connection.execute(
                text(f"TRUNCATE TABLE {', '.join(table_names)} RESTART IDENTITY CASCADE")
            )


@pytest_asyncio.fixture
async def isolated_test_session(test_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    await _truncate_test_tables(test_engine)
    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest_asyncio.fixture
async def test_client(isolated_test_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    """HTTPX client bound to the app with only the DB dependency overridden."""

    async def override_db() -> AsyncIterator[AsyncSession]:
        yield isolated_test_session

    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test", headers={"Origin": "http://localhost:5173"}
        ) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)
