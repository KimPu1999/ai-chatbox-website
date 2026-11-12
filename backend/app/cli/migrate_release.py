"""Run one controlled Alembic migration executor with a PostgreSQL advisory lock."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.db import _async_database_config

LOCK_ID = 4_912_770_321
BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _migration_config() -> tuple[str, dict]:
    value = os.getenv("MIGRATION_DATABASE_URL", "").strip()
    if not value:
        raise SystemExit("MIGRATION_DATABASE_URL is required for a release migration")
    return _async_database_config(value)


async def run() -> int:
    url, connect_args = _migration_config()
    engine = create_async_engine(
        url, pool_pre_ping=True, poolclass=NullPool, connect_args=connect_args
    )
    async with engine.connect() as connection:
        await connection.execute(text("SELECT pg_advisory_lock(:lock_id)"), {"lock_id": LOCK_ID})
        try:
            environment = os.environ.copy()
            environment["DATABASE_URL"] = url
            environment["MIGRATION_DATABASE_URL"] = url
            result = subprocess.run(
                [sys.executable, "-m", "alembic", "upgrade", "head"],
                cwd=BACKEND_ROOT,
                env=environment,
                check=False,
            )
            return result.returncode
        finally:
            await connection.execute(
                text("SELECT pg_advisory_unlock(:lock_id)"), {"lock_id": LOCK_ID}
            )
            await engine.dispose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
