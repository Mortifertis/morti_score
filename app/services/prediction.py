from dataclasses import dataclass
import math

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
    MIN_HISTORICAL_MATCHES = 10

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
        self._validate_distinct_teams(home_team_id, away_team_id)
        redis = await get_redis()
        cache_key = f"prediction:{home_team_id}:{away_team_id}"
        cached = await redis.get(cache_key)
        if cached:
            return PredictionRead.model_validate_json(cached)

        home_team = await self.team_repository.get_team(home_team_id)
        away_team = await self.team_repository.get_team(away_team_id)
        if home_team is None:
            self._raise_prediction_error(
                status_code=status.HTTP_404_NOT_FOUND,
                code="home_team_not_found",
                message="Home team not found.",
            )
        if away_team is None:
            self._raise_prediction_error(
                status_code=status.HTTP_404_NOT_FOUND,
                code="away_team_not_found",
                message="Away team not found.",
            )

        matches = await self.match_repository.list_matches(
            status=MatchStatus.FINISHED,
            limit=1000,
        )
        if not matches:
            self._raise_prediction_error(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                code="no_finished_matches",
                message=(
                    "Prediction is unavailable because there are no finished "
                    "matches to analyze."
                ),
            )
        if len(matches) < self.MIN_HISTORICAL_MATCHES:
            self._raise_prediction_error(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                code="insufficient_historical_matches",
                message=(
                    "Prediction needs more finished matches before the model "
                    "can be used."
                ),
                extra={
                    "historical_matches": len(matches),
                    "minimum_required": self.MIN_HISTORICAL_MATCHES,
                },
            )

        metrics = self._build_metrics(matches)
        if home_team_id not in metrics:
            self._raise_prediction_error(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                code="insufficient_home_team_history",
                message=(
                    "Home team does not have enough historical matches for "
                    "prediction."
                ),
            )
        if away_team_id not in metrics:
            self._raise_prediction_error(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                code="insufficient_away_team_history",
                message=(
                    "Away team does not have enough historical matches for "
                    "prediction."
                ),
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
        self._validate_expected_goals(
            expected_home_goals=expected_home_goals,
            expected_away_goals=expected_away_goals,
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

    def _validate_distinct_teams(
        self,
        home_team_id: int,
        away_team_id: int,
    ) -> None:
        if home_team_id == away_team_id:
            self._raise_prediction_error(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                code="same_team_matchup",
                message="Home and away teams must be different.",
            )

    def _validate_expected_goals(
        self,
        *,
        expected_home_goals: float,
        expected_away_goals: float,
    ) -> None:
        values = (expected_home_goals, expected_away_goals)
        if any(not math.isfinite(value) or value < 0 for value in values):
            self._raise_prediction_error(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                code="invalid_expected_goals",
                message=(
                    "Prediction model could not calculate expected goals "
                    "for the selected teams."
                ),
            )

    def _raise_prediction_error(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        extra: dict[str, int] | None = None,
    ) -> None:
        detail: dict[str, object] = {
            "code": code,
            "message": message,
        }
        if extra:
            detail.update(extra)
        raise HTTPException(status_code=status_code, detail=detail)

    def _build_metrics(self, matches) -> dict[int, TeamMetrics]:
        aggregates: dict[int, dict[str, float]] = {}
        valid_matches_count = 0
        for match in matches:
            if match.home_goals is None or match.away_goals is None:
                continue
            valid_matches_count += 1
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

        if valid_matches_count == 0:
            return {}

        league_home_avg = (
            sum(match.home_goals or 0 for match in matches)
            / valid_matches_count
        )
        league_away_avg = (
            sum(match.away_goals or 0 for match in matches)
            / valid_matches_count
        )
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
