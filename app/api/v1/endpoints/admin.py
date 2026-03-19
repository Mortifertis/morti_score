from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_prediction_service,
    get_seed_service,
    get_standings_service,
)
from app.core.security import verify_admin_token
from app.db.session import get_db_session
from app.schemas import MessageResponse
from app.services.prediction import PredictionService
from app.services.seed import SeedService
from app.services.standings import StandingsService
from app.tasks.background import rebuild_standings_task, recalculate_model_task

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post(
    "/seed-data",
    response_model=MessageResponse,
    dependencies=[Depends(verify_admin_token)],
)
async def seed_data(
    service: SeedService = Depends(get_seed_service),
) -> MessageResponse:
    result = await service.seed_all()
    return MessageResponse(message=f"Seed finished: {result}")


@router.post(
    "/rebuild-standings",
    response_model=MessageResponse,
    dependencies=[Depends(verify_admin_token)],
)
async def rebuild_standings(
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db_session),
) -> MessageResponse:
    background_tasks.add_task(rebuild_standings_task, session)
    return MessageResponse(message="Standings rebuild started")


@router.post(
    "/recalculate-model",
    response_model=MessageResponse,
    dependencies=[Depends(verify_admin_token)],
)
async def recalculate_model(
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db_session),
    service: PredictionService = Depends(get_prediction_service),
    standings_service: StandingsService = Depends(get_standings_service),
) -> MessageResponse:
    await service.clear_cached_predictions()
    await standings_service.list_standings()
    background_tasks.add_task(recalculate_model_task, session)
    return MessageResponse(message="Prediction model cache reset")
