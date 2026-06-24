import pytest
from redis.exceptions import RedisError

from app.core.config import Settings
from app.db import redis as redis_module
from app.db.redis import InMemoryRedis, get_redis


class BrokenRedisClient:
    async def ping(self) -> None:
        raise RedisError("redis is unavailable")

    async def aclose(self) -> None:
        return None


@pytest.fixture(autouse=True)
async def reset_redis_client():
    await redis_module.close_redis()
    yield
    await redis_module.close_redis()


def make_settings(cache_fallback_enabled: bool) -> Settings:
    return Settings(
        cache_fallback_enabled=cache_fallback_enabled,
        _env_file=None,
    )


@pytest.mark.anyio
async def test_get_redis_uses_in_memory_fallback_when_enabled(monkeypatch):
    monkeypatch.setattr(
        redis_module,
        "get_settings",
        lambda: make_settings(cache_fallback_enabled=True),
    )
    monkeypatch.setattr(
        redis_module.Redis,
        "from_url",
        lambda *args, **kwargs: BrokenRedisClient(),
    )

    client = await get_redis()

    assert isinstance(client, InMemoryRedis)


@pytest.mark.anyio
async def test_get_redis_raises_when_fallback_is_disabled(monkeypatch):
    monkeypatch.setattr(
        redis_module,
        "get_settings",
        lambda: make_settings(cache_fallback_enabled=False),
    )
    monkeypatch.setattr(
        redis_module.Redis,
        "from_url",
        lambda *args, **kwargs: BrokenRedisClient(),
    )

    with pytest.raises(RedisError):
        await get_redis()
