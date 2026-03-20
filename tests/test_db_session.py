from app.db.session import build_engine_kwargs


def test_build_engine_kwargs_for_postgres_enables_pool_health_checks():
    kwargs = build_engine_kwargs(
        database_url=(
            "postgresql+asyncpg://postgres:postgres@localhost:5433/"
            "football_analytics"
        ),
        debug=False,
    )

    assert kwargs == {
        "echo": False,
        "pool_pre_ping": True,
        "pool_recycle": 1800,
    }


def test_build_engine_kwargs_for_sqlite_skips_pool_recycle():
    kwargs = build_engine_kwargs(
        database_url="sqlite+aiosqlite:///./test.db",
        debug=True,
    )

    assert kwargs == {
        "echo": True,
        "pool_pre_ping": True,
    }
