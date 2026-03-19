import math
from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.redis import get_redis
from app.models import MatchStatus
from app.repositories.match import MatchRepository
from app.repositories.team import TeamRepository
from app.schemas.prediction import (
    ModelInfoRead,
    PredictionRead,
    ProbabilityRead,
    ScorelineRead,
    TeamSummary,
)


@dataclass
class TeamMetrics:
    home_attack: float
    home_defense: float
    away_attack: float
    away_defense: float


class PredictionService:
    MODEL_NAME = "basic_poisson"

    def __init__(self, session: AsyncSession, cache_ttl: int = 300) -> None:
        self.session = session
        self.team_repository = TeamRepository(session)
        self.match_repository = MatchRepository(session)
        self.cache_ttl = cache_ttl

    async def predict_match(
        self,
        home_team_id: int,
        away_team_id: int,
    ) -> PredictionRead:
        if home_team_id == away_team_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Teams must be different",
            )
        redis = await get_redis()
        cache_key = f"prediction:{home_team_id}:{away_team_id}"
        cached = await redis.get(cache_key)
        if cached:
            return PredictionRead.model_validate_json(cached)

        home_team = await self.team_repository.get_team(home_team_id)
        away_team = await self.team_repository.get_team(away_team_id)
        if home_team is None or away_team is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="One or both teams not found",
            )

        matches = await self.match_repository.list_matches(
            status=MatchStatus.FINISHED,
            limit=1000,
        )
        if len(matches) < 10:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Not enough historical match data",
            )

        metrics = self._build_metrics(matches)
        if home_team_id not in metrics or away_team_id not in metrics:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Not enough data for one or both teams",
            )

        league_home_goals = sum(
            match.home_goals or 0 for match in matches
        ) / len(matches)
        league_away_goals = sum(
            match.away_goals or 0 for match in matches
        ) / len(matches)

        home_metrics = metrics[home_team_id]
        away_metrics = metrics[away_team_id]
        expected_home_goals = (
            league_home_goals
            * home_metrics.home_attack
            * away_metrics.away_defense
        )
        expected_away_goals = (
            league_away_goals
            * away_metrics.away_attack
            * home_metrics.home_defense
        )
        probabilities, top_scorelines = self._score_matrix(
            expected_home_goals,
            expected_away_goals,
        )
        payload = PredictionRead(
            home_team=TeamSummary(id=home_team.id, name=home_team.name),
            away_team=TeamSummary(id=away_team.id, name=away_team.name),
            expected_home_goals=round(expected_home_goals, 2),
            expected_away_goals=round(expected_away_goals, 2),
            probabilities=probabilities,
            top_scorelines=top_scorelines,
            model_info=ModelInfoRead(
                name=self.MODEL_NAME,
                historical_matches_used=len(matches),
            ),
        )
        await redis.set(
            cache_key,
            payload.model_dump_json(),
            ex=self.cache_ttl,
        )
        return payload

    def _build_metrics(self, matches) -> dict[int, TeamMetrics]:
        aggregates: dict[int, dict[str, float]] = {}
        for match in matches:
            if match.home_goals is None or match.away_goals is None:
                continue
            home = aggregates.setdefault(
                match.home_team_id,
                {
                    "home_played": 0,
                    "home_scored": 0,
                    "home_conceded": 0,
                    "away_played": 0,
                    "away_scored": 0,
                    "away_conceded": 0,
                },
            )
            away = aggregates.setdefault(
                match.away_team_id,
                {
                    "home_played": 0,
                    "home_scored": 0,
                    "home_conceded": 0,
                    "away_played": 0,
                    "away_scored": 0,
                    "away_conceded": 0,
                },
            )
            home["home_played"] += 1
            home["home_scored"] += match.home_goals
            home["home_conceded"] += match.away_goals
            away["away_played"] += 1
            away["away_scored"] += match.away_goals
            away["away_conceded"] += match.home_goals

        league_home_avg = sum(
            match.home_goals or 0 for match in matches
        ) / len(matches)
        league_away_avg = sum(
            match.away_goals or 0 for match in matches
        ) / len(matches)
        metrics: dict[int, TeamMetrics] = {}
        for team_id, values in aggregates.items():
            if values["home_played"] == 0 or values["away_played"] == 0:
                continue
            metrics[team_id] = TeamMetrics(
                home_attack=(values["home_scored"] / values["home_played"])
                / max(league_home_avg, 0.1),
                home_defense=(values["home_conceded"] / values["home_played"])
                / max(league_away_avg, 0.1),
                away_attack=(values["away_scored"] / values["away_played"])
                / max(league_away_avg, 0.1),
                away_defense=(values["away_conceded"] / values["away_played"])
                / max(league_home_avg, 0.1),
            )
        return metrics

    def _poisson_probability(self, expected_goals: float, goals: int) -> float:
        return (
            math.exp(-expected_goals)
            * (expected_goals**goals)
            / math.factorial(goals)
        )

    def _score_matrix(
        self,
        expected_home_goals: float,
        expected_away_goals: float,
        max_goals: int = 5,
    ) -> tuple[ProbabilityRead, list[ScorelineRead]]:
        scorelines: list[ScorelineRead] = []
        home_win = 0.0
        draw = 0.0
        away_win = 0.0
        for home_goals in range(max_goals + 1):
            for away_goals in range(max_goals + 1):
                probability = self._poisson_probability(
                    expected_home_goals,
                    home_goals,
                ) * self._poisson_probability(expected_away_goals, away_goals)
                scorelines.append(
                    ScorelineRead(
                        home_goals=home_goals,
                        away_goals=away_goals,
                        probability=round(probability, 4),
                    )
                )
                if home_goals > away_goals:
                    home_win += probability
                elif home_goals == away_goals:
                    draw += probability
                else:
                    away_win += probability
        scorelines.sort(key=lambda item: item.probability, reverse=True)
        return (
            ProbabilityRead(
                home_win=round(home_win, 4),
                draw=round(draw, 4),
                away_win=round(away_win, 4),
            ),
            scorelines[:5],
        )

    async def clear_cached_predictions(self) -> None:
        redis = await get_redis()
        keys = await redis.keys("prediction:*")
        if keys:
            await redis.delete(*keys)
