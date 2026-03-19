from fastapi import APIRouter, Depends, Query

from app.api.deps import get_match_service
from app.models import MatchStatus
from app.schemas import MatchRead
from app.services.match import MatchService

router = APIRouter(prefix="/matches", tags=["matches"])


@router.get("", response_model=list[MatchRead])
async def list_matches(
    status: MatchStatus | None = Query(default=None),
    team_id: int | None = Query(default=None, gt=0),
    season: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    service: MatchService = Depends(get_match_service),
) -> list[MatchRead]:
    return await service.list_matches(
        status=status,
        team_id=team_id,
        season=season,
        limit=limit,
    )


@router.get("/{match_id}", response_model=MatchRead)
async def get_match(
    match_id: int,
    service: MatchService = Depends(get_match_service),
) -> MatchRead:
    return await service.get_match(match_id)
