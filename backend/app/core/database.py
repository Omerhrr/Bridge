"""Async SQLAlchemy engine and session management (spec section 14).

PostgreSQL (asyncpg) is used in production via DATABASE_URL; local development
falls back to SQLite (aiosqlite) so the platform runs without infrastructure.
"""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True,
)

async_session_factory = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an async database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Create tables on startup (MVP: create_all; migrations can replace this later)."""
    from app.core import models_register  # noqa: F401  ensures all models are imported

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
