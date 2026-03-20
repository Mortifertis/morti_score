from datetime import date
import json
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Match, MatchStatus, Team
from app.services.standings import StandingsService


class SeedService:
    def __init__(self, session: AsyncSession, data_dir: str = "data") -> None:
        self.session = session
        self.data_dir = Path(data_dir)

    async def seed_all(self) -> dict[str, int]:
        teams_created = await self._seed_teams()
        matches_created = await self._seed_matches()
        standings_service = StandingsService(self.session)
        await standings_service.rebuild_standings()
        return {
            "teams_created": teams_created,
            "matches_created": matches_created,
        }

    async def _seed_teams(self) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(Team)
        )
        team_count = result.scalar_one()
        if team_count > 0:
            return 0
        teams = json.loads((self.data_dir / "teams.json").read_text())
        self.session.add_all([Team(**team) for team in teams])
        await self.session.commit()
        return len(teams)

    async def _seed_matches(self) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(Match)
        )
        match_count = result.scalar_one()
        if match_count > 0:
            return 0
        matches = json.loads((self.data_dir / "matches.json").read_text())
        self.session.add_all(
            [
                Match(
                    **{
                        **match,
                        "match_date": date.fromisoformat(match["match_date"]),
                        "status": MatchStatus(match["status"]),
                    }
                )
                for match in matches
            ]
        )
        await self.session.commit()
        return len(matches)
