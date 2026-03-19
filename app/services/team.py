from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.team import TeamRepository


class TeamService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = TeamRepository(session)

    async def list_teams(self):
        return await self.repository.list_teams()

    async def get_team(self, team_id: int):
        team = await self.repository.get_team(team_id)
        if team is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Team not found",
            )
        return team
