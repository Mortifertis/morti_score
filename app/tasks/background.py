import logging

from app.db.session import AsyncSessionLocal
from app.services.prediction import PredictionService
from app.services.standings import StandingsService

logger = logging.getLogger(__name__)


async def rebuild_standings_task() -> None:
    async with AsyncSessionLocal() as session:
        service = StandingsService(session)
        await service.rebuild_standings()
    logger.info("Background standings rebuild completed")


async def recalculate_model_task() -> None:
    async with AsyncSessionLocal() as session:
        service = PredictionService(session)
        await service.clear_cached_predictions()
    logger.info("Prediction cache invalidated")
