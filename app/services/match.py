from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MatchStatus
from app.repositories.match import MatchRepository


class MatchService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = MatchRepository(session)

    async def list_matches(
        self,
        *,
        status: MatchStatus | None = None,
        team_id: int | None = None,
        season: str | None = None,
        limit: int = 100,
    ):
        return await self.repository.list_matches(
            status=status,
            team_id=team_id,
            season=season,
            limit=limit,
        )

    async def get_match(self, match_id: int):
        match = await self.repository.get_match(match_id)
        if match is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Match not found",
            )
        return match
