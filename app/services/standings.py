from dataclasses import dataclass
import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.redis import get_redis
from app.models import Match, MatchStatus, Standing, Team
from app.repositories.match import MatchRepository
from app.repositories.standing import StandingRepository
from app.schemas.standing import StandingRead

logger = logging.getLogger(__name__)


@dataclass
class StandingAccumulator:
    team_id: int
    played: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0
    goals_for: int = 0
    goals_against: int = 0
    goal_difference: int = 0
    points: int = 0


class StandingsService:
    CACHE_KEY = "standings:table"

    def __init__(self, session: AsyncSession, cache_ttl: int = 300) -> None:
        self.session = session
        self.repository = StandingRepository(session)
        self.match_repository = MatchRepository(session)
        self.cache_ttl = cache_ttl

    async def list_standings(self) -> list[Standing]:
        redis = await get_redis()
        cached = await redis.get(self.CACHE_KEY)
        if cached:
            logger.info("Serving standings from Redis cache")
            data = json.loads(cached)
            return [StandingRead.model_validate(item) for item in data]
        standings = await self.repository.list_standings()
        payload = [
            StandingRead.model_validate(item).model_dump(mode="json")
            for item in standings
        ]
        await redis.set(self.CACHE_KEY, json.dumps(payload), ex=self.cache_ttl)
        return standings

    async def rebuild_standings(self) -> list[Standing]:
        teams = await self.session.execute(
            Team.__table__.select().order_by(Team.id.asc())
        )
        team_rows = teams.fetchall()
        accumulators = {
            row.id: StandingAccumulator(team_id=row.id) for row in team_rows
        }
        matches = await self.match_repository.list_matches(
            status=MatchStatus.FINISHED,
            limit=1000,
        )
        for match in matches:
            self._apply_match(accumulators, match)

        await self.repository.clear()
        standing_models: list[Standing] = []
        for accumulator in accumulators.values():
            standing_models.append(
                Standing(
                    team_id=accumulator.team_id,
                    played=accumulator.played,
                    wins=accumulator.wins,
                    draws=accumulator.draws,
                    losses=accumulator.losses,
                    goals_for=accumulator.goals_for,
                    goals_against=accumulator.goals_against,
                    goal_difference=accumulator.goal_difference,
                    points=accumulator.points,
                )
            )
        self.session.add_all(standing_models)
        await self.session.commit()
        redis = await get_redis()
        await redis.delete(self.CACHE_KEY)
        logger.info(
            "Standings rebuilt using %s finished matches", len(matches)
        )
        return await self.repository.list_standings()

    def _apply_match(
        self,
        accumulators: dict[int, StandingAccumulator],
        match: Match,
    ) -> None:
        if match.home_goals is None or match.away_goals is None:
            return
        home = accumulators[match.home_team_id]
        away = accumulators[match.away_team_id]
        home.played += 1
        away.played += 1
        home.goals_for += match.home_goals
        home.goals_against += match.away_goals
        away.goals_for += match.away_goals
        away.goals_against += match.home_goals
        if match.home_goals > match.away_goals:
            home.wins += 1
            away.losses += 1
            home.points += 3
        elif match.home_goals < match.away_goals:
            away.wins += 1
            home.losses += 1
            away.points += 3
        else:
            home.draws += 1
            away.draws += 1
            home.points += 1
            away.points += 1
        home.goal_difference = home.goals_for - home.goals_against
        away.goal_difference = away.goals_for - away.goals_against
