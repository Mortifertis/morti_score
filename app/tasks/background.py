import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.prediction import PredictionService
from app.services.standings import StandingsService

logger = logging.getLogger(__name__)


async def rebuild_standings_task(session: AsyncSession) -> None:
    service = StandingsService(session)
    await service.rebuild_standings()
    logger.info("Background standings rebuild completed")


async def recalculate_model_task(session: AsyncSession) -> None:
    service = PredictionService(session)
    await service.clear_cached_predictions()
    logger.info("Prediction cache invalidated")
