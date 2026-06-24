from app.db.redis import get_redis
from app.schemas.prediction import PredictionRead


class PredictionCache:
    def __init__(self, ttl: int = 300) -> None:
        self.ttl = ttl

    def build_key(
        self,
        *,
        model_name: str,
        home_team_id: int,
        away_team_id: int,
    ) -> str:
        return f"prediction:{model_name}:{home_team_id}:{away_team_id}"

    async def get(self, key: str) -> PredictionRead | None:
        redis = await get_redis()
        cached = await redis.get(key)
        if not cached:
            return None
        return PredictionRead.model_validate_json(cached)

    async def set(self, key: str, payload: PredictionRead) -> None:
        redis = await get_redis()
        await redis.set(key, payload.model_dump_json(), ex=self.ttl)

    async def clear(self) -> None:
        redis = await get_redis()
        keys = await redis.keys("prediction:*")
        if keys:
            await redis.delete(*keys)
