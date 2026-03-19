from fastapi import APIRouter, Depends

from app.api.deps import get_standings_service
from app.schemas import StandingRead
from app.services.standings import StandingsService

router = APIRouter(prefix="/standings", tags=["standings"])


@router.get("", response_model=list[StandingRead])
async def list_standings(
    service: StandingsService = Depends(get_standings_service),
) -> list[StandingRead]:
    standings = await service.list_standings()
    return [StandingRead.model_validate(item) for item in standings]
