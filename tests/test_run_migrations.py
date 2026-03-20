from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from scripts.run_migrations import should_stamp_head


async def _create_schema(database_url: str, statements: list[str]) -> None:
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            for statement in statements:
                await connection.execute(text(statement))
    finally:
        await engine.dispose()


def test_should_stamp_head_when_schema_exists_without_version_table(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'existing.db'}"

    import asyncio

    asyncio.run(
        _create_schema(
            database_url,
            [
                "CREATE TABLE teams (id INTEGER PRIMARY KEY)",
                "CREATE TABLE matches (id INTEGER PRIMARY KEY)",
                "CREATE TABLE standings (id INTEGER PRIMARY KEY)",
            ],
        )
    )

    assert should_stamp_head(database_url) is True


def test_should_not_stamp_head_when_version_table_exists(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'versioned.db'}"

    import asyncio

    asyncio.run(
        _create_schema(
            database_url,
            [
                "CREATE TABLE teams (id INTEGER PRIMARY KEY)",
                "CREATE TABLE matches (id INTEGER PRIMARY KEY)",
                "CREATE TABLE standings (id INTEGER PRIMARY KEY)",
                "CREATE TABLE alembic_version (version_num VARCHAR(32))",
            ],
        )
    )

    assert should_stamp_head(database_url) is False


def test_should_not_stamp_head_for_partial_schema(tmp_path: Path) -> None:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'partial.db'}"

    import asyncio

    asyncio.run(
        _create_schema(
            database_url,
            ["CREATE TABLE teams (id INTEGER PRIMARY KEY)"],
        )
    )

    assert should_stamp_head(database_url) is False
