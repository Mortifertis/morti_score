from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

settings = get_settings()


def build_engine_kwargs(database_url: str, debug: bool) -> dict[str, Any]:
    engine_kwargs: dict[str, Any] = {
        "echo": debug,
        "pool_pre_ping": True,
        "pool_recycle": 1800,
    }
    backend_name = make_url(database_url).get_backend_name()
    if backend_name == "sqlite":
        engine_kwargs.pop("pool_recycle")
    return engine_kwargs


engine = create_async_engine(
    settings.database_url,
    **build_engine_kwargs(
        database_url=settings.database_url,
        debug=settings.debug,
    ),
)
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
