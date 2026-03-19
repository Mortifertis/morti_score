from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models import Match, MatchStatus


class MatchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_matches(
        self,
        *,
        status: MatchStatus | None = None,
        team_id: int | None = None,
        season: str | None = None,
        sort_order: str = "desc",
        limit: int = 100,
    ) -> list[Match]:
        order_by = Match.match_date.desc()
        id_order = Match.id.desc()
        if sort_order == "asc":
            order_by = Match.match_date.asc()
            id_order = Match.id.asc()

        stmt: Select[tuple[Match]] = (
            select(Match)
            .options(joinedload(Match.home_team), joinedload(Match.away_team))
            .order_by(order_by, id_order)
            .limit(limit)
        )
        if status is not None:
            stmt = stmt.where(Match.status == status)
        if team_id is not None:
            stmt = stmt.where(
                (Match.home_team_id == team_id)
                | (Match.away_team_id == team_id)
            )
        if season is not None:
            stmt = stmt.where(Match.season == season)
        result = await self.session.execute(stmt)
        return list(result.scalars().unique().all())

    async def get_match(self, match_id: int) -> Match | None:
        stmt = (
            select(Match)
            .options(joinedload(Match.home_team), joinedload(Match.away_team))
            .where(Match.id == match_id)
        )
        result = await self.session.execute(stmt)
        return result.scalars().unique().one_or_none()
