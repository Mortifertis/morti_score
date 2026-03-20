import asyncio
from collections.abc import Iterable
from pathlib import Path

from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import command
from app.core.config import get_settings

EXPECTED_TABLES = (
    "teams",
    "matches",
    "standings",
)
ALEMBIC_VERSION_TABLE = "alembic_version"


def _all_tables_exist(existing_tables: Iterable[str]) -> bool:
    existing = set(existing_tables)
    return set(EXPECTED_TABLES).issubset(existing)


async def _get_table_names(database_url: str) -> list[str]:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            return await connection.run_sync(
                lambda sync_connection: inspect(
                    sync_connection
                ).get_table_names()
            )
    finally:
        await engine.dispose()


def should_stamp_head(database_url: str) -> bool:
    table_names = asyncio.run(_get_table_names(database_url))
    return ALEMBIC_VERSION_TABLE not in table_names and _all_tables_exist(
        table_names
    )


def build_alembic_config(database_url: str) -> Config:
    project_root = Path(__file__).resolve().parents[1]
    config = Config(str(project_root / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def run_migrations() -> str:
    settings = get_settings()
    config = build_alembic_config(settings.database_url)

    if should_stamp_head(settings.database_url):
        command.stamp(config, "head")
        return "stamped"

    command.upgrade(config, "head")
    return "upgraded"


if __name__ == "__main__":
    result = run_migrations()
    print(f"Migration status: {result}")
