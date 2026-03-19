from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models import Standing


class StandingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_standings(self) -> list[Standing]:
        stmt = (
            select(Standing)
            .options(joinedload(Standing.team))
            .order_by(
                Standing.points.desc(),
                Standing.goal_difference.desc(),
                Standing.goals_for.desc(),
                Standing.team_id.asc(),
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().unique().all())

    async def clear(self) -> None:
        await self.session.execute(delete(Standing))
