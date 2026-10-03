"""إدارة اتصال قاعدة البيانات وتهيئة الجداول."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from database.models import Base

logger = logging.getLogger(__name__)


class Database:
    """غلاف بسيط حول SQLAlchemy async engine.

    مثال الاستخدام:
        async with db.session() as session:
            await session.execute(...)
    """

    def __init__(self, url: str) -> None:
        connect_args = (
            {
                "server_settings": {
                    "statement_timeout": "5000",
                    "lock_timeout": "2000",
                    "idle_in_transaction_session_timeout": "120000",
                },
                "timeout": 10,
                "command_timeout": 10,
            }
            if url.startswith("postgresql+asyncpg:")
            else {}
        )
        self.engine: AsyncEngine = create_async_engine(
            url,
            echo=False,
            pool_pre_ping=True,
            connect_args=connect_args,
        )
        self.session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
        )

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self.session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    async def init_models(self) -> None:
        async with self.engine.begin() as conn:
            if self.engine.dialect.name == "sqlite":
                await conn.run_sync(Base.metadata.create_all)
            else:
                # Production schema is operator-managed. Never run migrations on startup.
                await conn.execute(text("SELECT revision FROM applications LIMIT 0"))
                await conn.execute(text("SELECT application_id FROM site_delivery_sources LIMIT 0"))
        logger.info("Database schema ready.")

    async def close(self) -> None:
        await self.engine.dispose()


_db: Database | None = None


def init_db(url: str) -> Database:
    """إنشاء مثيل قاعدة البيانات مرة واحدة (Singleton)."""
    global _db
    if _db is None:
        _db = Database(url)
    return _db


def get_db() -> Database:
    if _db is None:
        raise RuntimeError("Database not initialised. Call init_db() first.")
    return _db
