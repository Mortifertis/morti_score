import math
from typing import Protocol

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Match, Team
from app.schemas.prediction import (
    ModelComparisonRead,
    ModelInfoRead,
    PredictionRead,
    TeamSummary,
)
from app.services.prediction.cache import PredictionCache
from app.services.prediction.constants import (
    BASIC_MODEL_NAME,
    ELO_MODEL_NAME,
    IMPROVED_MODEL_NAME,
)
from app.services.prediction.context import PredictionContextLoader
from app.services.prediction.errors import raise_prediction_error
from app.services.prediction.models import (
    BasicPoissonModel,
    EloModel,
    ImprovedPoissonModel,
)
from app.services.prediction.score_matrix import build_score_matrix


class PredictionModel(Protocol):
    name: str

    def predict_expected_goals(
        self,
        *,
        home_team_id: int,
        away_team_id: int,
        matches: list[Match],
    ) -> tuple[float, float, int]: ...


class PredictionService:
    BASIC_MODEL_NAME = BASIC_MODEL_NAME
    IMPROVED_MODEL_NAME = IMPROVED_MODEL_NAME
    ELO_MODEL_NAME = ELO_MODEL_NAME

    def __init__(self, session: AsyncSession, cache_ttl: int = 300) -> None:
        self.session = session
        self.cache = PredictionCache(ttl=cache_ttl)
        self.context_loader = PredictionContextLoader(session)
        self.models: dict[str, PredictionModel] = {
            BASIC_MODEL_NAME: BasicPoissonModel(),
            IMPROVED_MODEL_NAME: ImprovedPoissonModel(),
            ELO_MODEL_NAME: EloModel(),
        }

    async def predict_match(
        self,
        home_team_id: int,
        away_team_id: int,
    ) -> PredictionRead:
        return await self._predict_model(
            home_team_id,
            away_team_id,
            model_name=IMPROVED_MODEL_NAME,
        )

    async def compare_models(
        self,
        home_team_id: int,
        away_team_id: int,
    ) -> ModelComparisonRead:
        basic = await self._predict_model(
            home_team_id,
            away_team_id,
            model_name=BASIC_MODEL_NAME,
        )
        improved = await self._predict_model(
            home_team_id,
            away_team_id,
            model_name=IMPROVED_MODEL_NAME,
        )
        elo_based = await self._predict_model(
            home_team_id,
            away_team_id,
            model_name=ELO_MODEL_NAME,
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
        cache_key = self.cache.build_key(
            model_name=model_name,
            home_team_id=home_team_id,
            away_team_id=away_team_id,
        )
        cached = await self.cache.get(cache_key)
        if cached:
            return cached

        context = await self.context_loader.load(home_team_id, away_team_id)
        model = self.models[model_name]
        expected_home_goals, expected_away_goals, history_used = (
            model.predict_expected_goals(
                home_team_id=home_team_id,
                away_team_id=away_team_id,
                matches=context.matches,
            )
        )
        payload = self._build_prediction_response(
            home_team=context.home_team,
            away_team=context.away_team,
            model_name=model.name,
            historical_matches_used=history_used,
            expected_home_goals=expected_home_goals,
            expected_away_goals=expected_away_goals,
        )
        await self.cache.set(cache_key, payload)
        return payload

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
        probabilities, top_scorelines = build_score_matrix(
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
            raise_prediction_error(
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
            raise_prediction_error(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                code="invalid_expected_goals",
                message=(
                    "Prediction model could not calculate expected goals "
                    "for the selected teams."
                ),
            )

    async def clear_cached_predictions(self) -> None:
        await self.cache.clear()
