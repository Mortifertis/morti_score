from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Team


class TeamRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_teams(self) -> list[Team]:
        result = await self.session.execute(select(Team).order_by(Team.name))
        return list(result.scalars().all())

    async def get_team(self, team_id: int) -> Team | None:
        return await self.session.get(Team, team_id)
