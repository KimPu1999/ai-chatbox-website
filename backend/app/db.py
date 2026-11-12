import ssl
from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()


def _async_database_config(raw_url: str) -> tuple[str, dict]:
    """Normalize provider URLs and disable asyncpg prepared statements for poolers."""
    parsed = make_url(raw_url)
    if parsed.drivername in {"postgres", "postgresql"}:
        parsed = parsed.set(drivername="postgresql+asyncpg")
    connect_args: dict = {"statement_cache_size": 0}
    query = dict(parsed.query)
    # Neon poolers/PgBouncer do not guarantee prepared-statement affinity.
    query.setdefault("prepared_statement_cache_size", "0")
    sslmode = query.pop("sslmode", None)
    if sslmode in {"require", "verify-ca", "verify-full"}:
        if settings.db_ssl_ca_file and sslmode in {"verify-ca", "verify-full"}:
            context = ssl.create_default_context(cafile=settings.db_ssl_ca_file)
            context.check_hostname = sslmode == "verify-full"
            connect_args["ssl"] = context
        else:
            connect_args["ssl"] = "require"
    parsed = parsed.set(query=query)
    return str(parsed), connect_args


_database_url, _connect_args = _async_database_config(settings.database_url)
engine = create_async_engine(
    _database_url,
    echo=settings.debug,
    pool_pre_ping=True,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=10,
    pool_recycle=1_800,
    connect_args=_connect_args,
)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


async def check_database_connection() -> bool:
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
    return True


async def dispose_engine() -> None:
    await engine.dispose()
