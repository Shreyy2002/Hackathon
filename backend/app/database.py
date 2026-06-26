import os

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

# Requirements 7.1, 7.2 — async DB connectivity
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://perf:perf@localhost:5432/perf_ledger",
)

engine = create_async_engine(DATABASE_URL, echo=False)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


async def get_db():
    """FastAPI dependency that yields an AsyncSession and always closes it."""
    session: AsyncSession = AsyncSessionLocal()
    try:
        yield session
    finally:
        await session.close()
