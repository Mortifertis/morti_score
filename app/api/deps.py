from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db_session
from app.services.match import MatchService
from app.services.prediction import PredictionService
from app.services.seed import SeedService
from app.services.standings import StandingsService
from app.services.team import TeamService


async def get_team_service(
    session: AsyncSession = Depends(get_db_session),
) -> TeamService:
    return TeamService(session)


async def get_match_service(
    session: AsyncSession = Depends(get_db_session),
) -> MatchService:
    return MatchService(session)


async def get_standings_service(
    session: AsyncSession = Depends(get_db_session),
) -> StandingsService:
    settings = get_settings()
    return StandingsService(session, cache_ttl=settings.cache_ttl_seconds)


async def get_prediction_service(
    session: AsyncSession = Depends(get_db_session),
) -> PredictionService:
    settings = get_settings()
    return PredictionService(session, cache_ttl=settings.cache_ttl_seconds)


async def get_seed_service(
    session: AsyncSession = Depends(get_db_session),
) -> SeedService:
    return SeedService(session)
