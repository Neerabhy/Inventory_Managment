"""
core/database.py
================
Async SQLAlchemy engine configuration using aiosqlite.
WAL (Write-Ahead Logging) mode is enabled on every new connection for
concurrency-safe reads/writes under simultaneous API load.
"""

from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from .config import settings


# ------------------------------------------------------------------ #
# Declarative Base — all ORM models inherit from this
# ------------------------------------------------------------------ #
class Base(DeclarativeBase):
    """Shared declarative base for all SQLAlchemy model classes."""
    pass


# ------------------------------------------------------------------ #
# Engine Factory
# ------------------------------------------------------------------ #
def _build_engine() -> AsyncEngine:
    """
    Create and configure the async SQLAlchemy engine.
    connect_args are SQLite-specific:
      - check_same_thread=False  → required for async usage
      - timeout=60               → busy-wait up to 60 s before raising OperationalError
    """
    connect_args: dict = {}
    if "sqlite" in settings.database_url:
        connect_args = {
            "check_same_thread": False,
            "timeout": 60,
        }

    engine = create_async_engine(
        settings.database_url,
        echo=settings.debug,            # SQL echo only in debug mode
        future=True,
        connect_args=connect_args,
        pool_pre_ping=True,             # Validates connections before checkout
    )
    return engine


engine: AsyncEngine = _build_engine()


# ------------------------------------------------------------------ #
# WAL Mode Pragma — fires once per new raw DBAPI connection
# ------------------------------------------------------------------ #
@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):  # type: ignore[no-untyped-def]
    """
    Enable WAL journaling and foreign-key enforcement for every new
    SQLite connection.  This mirrors the pragma block in the migration script.
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.execute("PRAGMA busy_timeout=60000;")
    cursor.execute("PRAGMA synchronous=NORMAL;")
    cursor.execute("PRAGMA cache_size=-64000;")   # 64 MB page cache
    cursor.execute("PRAGMA temp_store=MEMORY;")
    cursor.close()


# ------------------------------------------------------------------ #
# Session Factory
# ------------------------------------------------------------------ #
AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,     # Prevent lazy-load errors after commit
    autoflush=False,
    autocommit=False,
)


# ------------------------------------------------------------------ #
# Dependency-injectable session generator
# ------------------------------------------------------------------ #
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields a scoped async database session.
    Commits on clean exit, rolls back on any exception, and always closes.

    Usage:
        @router.get("/example")
        async def handler(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ------------------------------------------------------------------ #
# Schema Initializer — called at application startup
# ------------------------------------------------------------------ #
async def init_db() -> None:
    """
    Create all tables if they do not already exist.
    Should be called once from the FastAPI lifespan startup hook.
    """

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
