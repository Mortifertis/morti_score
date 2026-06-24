from collections.abc import AsyncIterator
import logging

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class InMemoryRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.store[key] = value

    async def delete(self, *keys: str) -> None:
        for key in keys:
            self.store.pop(key, None)

    async def scan_iter(self, match: str) -> AsyncIterator[str]:
        if match == "prediction:*":
            keys = [key for key in self.store if key.startswith("prediction:")]
        else:
            keys = [key for key in self.store if key == match]
        for key in keys:
            yield key

    async def close(self) -> None:
        self.store.clear()


_redis_client: Redis | InMemoryRedis | None = None


async def get_redis() -> Redis | InMemoryRedis:
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        client = Redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        try:
            await client.ping()
            _redis_client = client
        except RedisError:
            await client.aclose()
            if not settings.cache_fallback_enabled:
                logger.exception(
                    "Redis unavailable and cache fallback is disabled"
                )
                raise
            logger.warning("Redis unavailable, using in-memory cache fallback")
            _redis_client = InMemoryRedis()
    return _redis_client


async def close_redis() -> None:
    global _redis_client
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None
