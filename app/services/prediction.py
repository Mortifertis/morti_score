from dataclasses import dataclass
import math

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.redis import get_redis
from app.models import Match, MatchStatus, Team
from app.repositories.match import MatchRepository
from app.repositories.team import TeamRepository
from app.schemas.prediction import (
    ModelComparisonRead,
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


@dataclass
class LeagueAverages:
    home_goals: float
    away_goals: float
    home_xg: float
    away_xg: float


@dataclass
class TeamForm:
    home_attack: float
    home_defense: float
    away_attack: float
    away_defense: float


@dataclass
class EloRating:
    rating: float
    matches_played: int


class PredictionService:
    BASIC_MODEL_NAME = "basic_poisson"
    IMPROVED_MODEL_NAME = "improved_poisson"
    ELO_MODEL_NAME = "elo_based"
    MIN_HISTORICAL_MATCHES = 10
    MIN_TEAM_MATCHES = 2
    ROLLING_WINDOW = 8
    DRAW_FACTOR = 0.24
    MIN_PROBABILITY_SUM = 0.0001
    ELO_BASE_RATING = 1500.0
    ELO_K_FACTOR = 28.0
    HOME_ADVANTAGE_ELO = 55.0

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
        return await self._predict_model(
            home_team_id,
            away_team_id,
            model_name=self.IMPROVED_MODEL_NAME,
        )

    async def compare_models(
        self,
        home_team_id: int,
        away_team_id: int,
    ) -> ModelComparisonRead:
        basic = await self._predict_model(
            home_team_id,
            away_team_id,
            model_name=self.BASIC_MODEL_NAME,
        )
        improved = await self._predict_model(
            home_team_id,
            away_team_id,
            model_name=self.IMPROVED_MODEL_NAME,
        )
        elo_based = await self._predict_model(
            home_team_id,
            away_team_id,
            model_name=self.ELO_MODEL_NAME,
        )
        return ModelComparisonRead(
            basic_poisson=basic,
            improved_poisson=improved,
            elo_based=elo_based,
        )

    async def _predict_model(
        self,
        home_team_id: int,
        away_team_id: int,
        *,
        model_name: str,
    ) -> PredictionRead:
        self._validate_distinct_teams(home_team_id, away_team_id)
        redis = await get_redis()
        cache_key = f"prediction:{model_name}:{home_team_id}:{away_team_id}"
        cached = await redis.get(cache_key)
        if cached:
            return PredictionRead.model_validate_json(cached)

        home_team, away_team, matches = await self._load_prediction_context(
            home_team_id,
            away_team_id,
        )
        if model_name == self.BASIC_MODEL_NAME:
            payload = self._build_basic_prediction(
                home_team=home_team,
                away_team=away_team,
                home_team_id=home_team_id,
                away_team_id=away_team_id,
                matches=matches,
            )
        elif model_name == self.IMPROVED_MODEL_NAME:
            payload = self._build_improved_prediction(
                home_team=home_team,
                away_team=away_team,
                home_team_id=home_team_id,
                away_team_id=away_team_id,
                matches=matches,
            )
        else:
            payload = self._build_elo_prediction(
                home_team=home_team,
                away_team=away_team,
                home_team_id=home_team_id,
                away_team_id=away_team_id,
                matches=matches,
            )
        await redis.set(
            cache_key, payload.model_dump_json(), ex=self.cache_ttl
        )
        return payload

    async def _load_prediction_context(
        self,
        home_team_id: int,
        away_team_id: int,
    ) -> tuple[Team, Team, list[Match]]:
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
        finished_matches = [
            match
            for match in matches
            if match.home_goals is not None and match.away_goals is not None
        ]
        if not finished_matches:
            self._raise_prediction_error(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                code="no_finished_matches",
                message=(
                    "Prediction is unavailable because there are no finished "
                    "matches to analyze."
                ),
            )
        if len(finished_matches) < self.MIN_HISTORICAL_MATCHES:
            self._raise_prediction_error(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                code="insufficient_historical_matches",
                message=(
                    "Prediction needs more finished matches before the model "
                    "can be used."
                ),
                extra={
                    "historical_matches": len(finished_matches),
                    "minimum_required": self.MIN_HISTORICAL_MATCHES,
                },
            )
        return home_team, away_team, finished_matches

    def _build_basic_prediction(
        self,
        *,
        home_team: Team,
        away_team: Team,
        home_team_id: int,
        away_team_id: int,
        matches: list[Match],
    ) -> PredictionRead:
        metrics = self._build_basic_metrics(matches)
        if home_team_id not in metrics:
            self._raise_insufficient_team_history("home")
        if away_team_id not in metrics:
            self._raise_insufficient_team_history("away")

        league = self._league_averages(matches)
        home_metrics = metrics[home_team_id]
        away_metrics = metrics[away_team_id]
        expected_home_goals = (
            league.home_goals
            * home_metrics.home_attack
            * away_metrics.away_defense
        )
        expected_away_goals = (
            league.away_goals
            * away_metrics.away_attack
            * home_metrics.home_defense
        )
        return self._build_prediction_response(
            home_team=home_team,
            away_team=away_team,
            model_name=self.BASIC_MODEL_NAME,
            historical_matches_used=len(matches),
            expected_home_goals=expected_home_goals,
            expected_away_goals=expected_away_goals,
        )

    def _build_improved_prediction(
        self,
        *,
        home_team: Team,
        away_team: Team,
        home_team_id: int,
        away_team_id: int,
        matches: list[Match],
    ) -> PredictionRead:
        metrics = self._build_basic_metrics(matches)
        if home_team_id not in metrics:
            self._raise_insufficient_team_history("home")
        if away_team_id not in metrics:
            self._raise_insufficient_team_history("away")

        home_matches = self._team_recent_matches(matches, home_team_id)
        away_matches = self._team_recent_matches(matches, away_team_id)
        if len(home_matches) < self.MIN_TEAM_MATCHES:
            self._raise_insufficient_team_history("home")
        if len(away_matches) < self.MIN_TEAM_MATCHES:
            self._raise_insufficient_team_history("away")

        league = self._league_averages(matches)
        home_form = self._weighted_team_form(
            home_matches, team_id=home_team_id
        )
        away_form = self._weighted_team_form(
            away_matches, team_id=away_team_id
        )
        home_xg = self._weighted_expected_goals(
            home_matches, team_id=home_team_id
        )
        away_xg = self._weighted_expected_goals(
            away_matches, team_id=away_team_id
        )
        home_metrics = metrics[home_team_id]
        away_metrics = metrics[away_team_id]

        base_home_goals = (
            league.home_goals
            * self._blend_values(
                home_metrics.home_attack, home_form.home_attack
            )
            * self._blend_values(
                away_metrics.away_defense, away_form.away_defense
            )
        )
        base_away_goals = (
            league.away_goals
            * self._blend_values(
                away_metrics.away_attack, away_form.away_attack
            )
            * self._blend_values(
                home_metrics.home_defense, home_form.home_defense
            )
        )
        xg_home_factor = home_xg / max(league.home_xg, 0.1)
        xg_away_factor = away_xg / max(league.away_xg, 0.1)
        expected_home_goals = base_home_goals * self._blend_values(
            1.0,
            xg_home_factor,
        )
        expected_away_goals = base_away_goals * self._blend_values(
            1.0,
            xg_away_factor,
        )
        return self._build_prediction_response(
            home_team=home_team,
            away_team=away_team,
            model_name=self.IMPROVED_MODEL_NAME,
            historical_matches_used=min(
                self.ROLLING_WINDOW,
                len(home_matches),
                len(away_matches),
            ),
            expected_home_goals=expected_home_goals,
            expected_away_goals=expected_away_goals,
        )

    def _build_elo_prediction(
        self,
        *,
        home_team: Team,
        away_team: Team,
        home_team_id: int,
        away_team_id: int,
        matches: list[Match],
    ) -> PredictionRead:
        ratings = self._calculate_elo(matches)
        home_rating = ratings.get(home_team_id)
        away_rating = ratings.get(away_team_id)
        if (
            home_rating is None
            or home_rating.matches_played < self.MIN_TEAM_MATCHES
        ):
            self._raise_insufficient_team_history("home")
        if (
            away_rating is None
            or away_rating.matches_played < self.MIN_TEAM_MATCHES
        ):
            self._raise_insufficient_team_history("away")

        league = self._league_averages(matches)
        rating_gap = (
            home_rating.rating + self.HOME_ADVANTAGE_ELO - away_rating.rating
        )
        win_expectancy = 1.0 / (1.0 + 10 ** (-rating_gap / 400))
        goal_shift = (win_expectancy - 0.5) * 1.35
        expected_home_goals = league.home_goals + goal_shift
        expected_away_goals = league.away_goals - goal_shift * 0.9
        return self._build_prediction_response(
            home_team=home_team,
            away_team=away_team,
            model_name=self.ELO_MODEL_NAME,
            historical_matches_used=len(matches),
            expected_home_goals=expected_home_goals,
            expected_away_goals=expected_away_goals,
        )

    def _build_prediction_response(
        self,
        *,
        home_team: Team,
        away_team: Team,
        model_name: str,
        historical_matches_used: int,
        expected_home_goals: float,
        expected_away_goals: float,
    ) -> PredictionRead:
        self._validate_expected_goals(
            expected_home_goals=expected_home_goals,
            expected_away_goals=expected_away_goals,
        )
        probabilities, top_scorelines = self._score_matrix(
            expected_home_goals,
            expected_away_goals,
        )
        return PredictionRead(
            home_team=TeamSummary(id=home_team.id, name=home_team.name),
            away_team=TeamSummary(id=away_team.id, name=away_team.name),
            expected_home_goals=round(expected_home_goals, 2),
            expected_away_goals=round(expected_away_goals, 2),
            probabilities=probabilities,
            top_scorelines=top_scorelines,
            model_info=ModelInfoRead(
                name=model_name,
                historical_matches_used=historical_matches_used,
            ),
        )

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
        if any(not math.isfinite(value) or value < 0.05 for value in values):
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

    def _raise_insufficient_team_history(self, team_side: str) -> None:
        self._raise_prediction_error(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code=f"insufficient_{team_side}_team_history",
            message=(
                f"{team_side.capitalize()} team does not have enough "
                "historical matches for prediction."
            ),
        )

    def _build_basic_metrics(
        self, matches: list[Match]
    ) -> dict[int, TeamMetrics]:
        aggregates: dict[int, dict[str, float]] = {}
        for match in matches:
            home = aggregates.setdefault(
                match.home_team_id,
                self._empty_aggregate(),
            )
            away = aggregates.setdefault(
                match.away_team_id,
                self._empty_aggregate(),
            )
            home["home_played"] += 1
            home["home_scored"] += match.home_goals or 0
            home["home_conceded"] += match.away_goals or 0
            away["away_played"] += 1
            away["away_scored"] += match.away_goals or 0
            away["away_conceded"] += match.home_goals or 0

        league = self._league_averages(matches)
        metrics: dict[int, TeamMetrics] = {}
        for team_id, values in aggregates.items():
            if (
                values["home_played"] < self.MIN_TEAM_MATCHES
                or values["away_played"] < self.MIN_TEAM_MATCHES
            ):
                continue
            metrics[team_id] = TeamMetrics(
                home_attack=(values["home_scored"] / values["home_played"])
                / max(league.home_goals, 0.1),
                home_defense=(values["home_conceded"] / values["home_played"])
                / max(league.away_goals, 0.1),
                away_attack=(values["away_scored"] / values["away_played"])
                / max(league.away_goals, 0.1),
                away_defense=(values["away_conceded"] / values["away_played"])
                / max(league.home_goals, 0.1),
            )
        return metrics

    def _league_averages(self, matches: list[Match]) -> LeagueAverages:
        total_matches = max(len(matches), 1)
        home_goals = sum(match.home_goals or 0 for match in matches)
        away_goals = sum(match.away_goals or 0 for match in matches)
        home_xg = sum(
            self._match_expected_goals(match, True) for match in matches
        )
        away_xg = sum(
            self._match_expected_goals(match, False) for match in matches
        )
        return LeagueAverages(
            home_goals=home_goals / total_matches,
            away_goals=away_goals / total_matches,
            home_xg=home_xg / total_matches,
            away_xg=away_xg / total_matches,
        )

    def _team_recent_matches(
        self,
        matches: list[Match],
        team_id: int,
    ) -> list[Match]:
        relevant = [
            match
            for match in matches
            if team_id in {match.home_team_id, match.away_team_id}
        ]
        relevant.sort(
            key=lambda item: (item.match_date, item.id), reverse=True
        )
        return relevant[: self.ROLLING_WINDOW]

    def _weighted_team_form(
        self,
        matches: list[Match],
        *,
        team_id: int,
    ) -> TeamForm:
        home_scored = 0.0
        home_conceded = 0.0
        home_weight = 0.0
        away_scored = 0.0
        away_conceded = 0.0
        away_weight = 0.0
        for index, match in enumerate(matches):
            weight = self._recent_weight(index)
            is_home = match.home_team_id == team_id
            if is_home:
                home_scored += (match.home_goals or 0) * weight
                home_conceded += (match.away_goals or 0) * weight
                home_weight += weight
            else:
                away_scored += (match.away_goals or 0) * weight
                away_conceded += (match.home_goals or 0) * weight
                away_weight += weight
        return TeamForm(
            home_attack=home_scored / max(home_weight, 0.1),
            home_defense=home_conceded / max(home_weight, 0.1),
            away_attack=away_scored / max(away_weight, 0.1),
            away_defense=away_conceded / max(away_weight, 0.1),
        )

    def _weighted_expected_goals(
        self,
        matches: list[Match],
        *,
        team_id: int,
    ) -> float:
        total = 0.0
        weights = 0.0
        for index, match in enumerate(matches):
            weight = self._recent_weight(index)
            total += self._team_match_xg(match, team_id) * weight
            weights += weight
        return total / max(weights, 0.1)

    def _team_match_xg(self, match: Match, team_id: int) -> float:
        is_home = match.home_team_id == team_id
        goals_for = match.home_goals if is_home else match.away_goals
        goals_against = match.away_goals if is_home else match.home_goals
        shots_proxy = 1.0 if is_home else 0.92
        attack_bonus = 0.28 * (goals_for or 0)
        defense_bonus = 0.08 * (goals_against or 0)
        return max(0.25, 0.72 + attack_bonus + defense_bonus * shots_proxy)

    def _match_expected_goals(self, match: Match, is_home: bool) -> float:
        team_id = match.home_team_id if is_home else match.away_team_id
        return self._team_match_xg(match, team_id)

    def _calculate_elo(self, matches: list[Match]) -> dict[int, EloRating]:
        ratings: dict[int, EloRating] = {}
        ordered = sorted(matches, key=lambda item: (item.match_date, item.id))
        for match in ordered:
            home = ratings.setdefault(
                match.home_team_id,
                EloRating(self.ELO_BASE_RATING, 0),
            )
            away = ratings.setdefault(
                match.away_team_id,
                EloRating(self.ELO_BASE_RATING, 0),
            )
            home_expected = 1.0 / (
                1.0
                + 10
                ** (
                    (away.rating - home.rating - self.HOME_ADVANTAGE_ELO) / 400
                )
            )
            away_expected = 1.0 - home_expected
            if (match.home_goals or 0) > (match.away_goals or 0):
                home_result = 1.0
            elif (match.home_goals or 0) == (match.away_goals or 0):
                home_result = 0.5
            else:
                home_result = 0.0
            away_result = 1.0 - home_result
            goal_margin = abs(
                (match.home_goals or 0) - (match.away_goals or 0)
            )
            margin_factor = 1.0 + goal_margin * 0.12
            home.rating += (
                self.ELO_K_FACTOR
                * margin_factor
                * (home_result - home_expected)
            )
            away.rating += (
                self.ELO_K_FACTOR
                * margin_factor
                * (away_result - away_expected)
            )
            home.matches_played += 1
            away.matches_played += 1
        return ratings

    def _empty_aggregate(self) -> dict[str, float]:
        return {
            "home_played": 0.0,
            "home_scored": 0.0,
            "home_conceded": 0.0,
            "away_played": 0.0,
            "away_scored": 0.0,
            "away_conceded": 0.0,
        }

    def _recent_weight(self, index: int) -> float:
        return max(0.35, 1.0 - index * 0.08)

    def _blend_values(self, base_value: float, form_value: float) -> float:
        normalized_form = max(form_value, 0.1)
        return (base_value * 0.65) + (normalized_form * 0.35)

    def _poisson_probability(self, expected_goals: float, goals: int) -> float:
        return (
            math.exp(-expected_goals)
            * (expected_goals**goals)
            / math.factorial(goals)
        )

    def _normalize_probabilities(
        self,
        *,
        home_win: float,
        draw: float,
        away_win: float,
    ) -> tuple[float, float, float]:
        total_probability = home_win + draw + away_win
        adjusted_draw = min(
            draw + self.DRAW_FACTOR * (1 - total_probability),
            1,
        )
        remainder = max(
            home_win + adjusted_draw + away_win,
            self.MIN_PROBABILITY_SUM,
        )
        return (
            home_win / remainder,
            adjusted_draw / remainder,
            away_win / remainder,
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
        home_win, draw, away_win = self._normalize_probabilities(
            home_win=home_win,
            draw=draw,
            away_win=away_win,
        )
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
