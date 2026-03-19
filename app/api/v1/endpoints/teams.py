from fastapi import APIRouter, Depends

from app.api.deps import get_team_service
from app.schemas import TeamRead
from app.services.team import TeamService

router = APIRouter(prefix="/teams", tags=["teams"])


@router.get("", response_model=list[TeamRead])
async def list_teams(
    service: TeamService = Depends(get_team_service),
) -> list[TeamRead]:
    return await service.list_teams()


@router.get("/{team_id}", response_model=TeamRead)
async def get_team(
    team_id: int,
    service: TeamService = Depends(get_team_service),
) -> TeamRead:
    return await service.get_team(team_id)
