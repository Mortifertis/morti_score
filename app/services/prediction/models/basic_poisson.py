from app.models import Match
from app.services.prediction.constants import BASIC_MODEL_NAME
from app.services.prediction.errors import raise_insufficient_team_history
from app.services.prediction.models.helpers import (
    build_basic_metrics,
    league_averages,
)


class BasicPoissonModel:
    name = BASIC_MODEL_NAME

    def predict_expected_goals(
        self,
        *,
        home_team_id: int,
        away_team_id: int,
        matches: list[Match],
    ) -> tuple[float, float, int]:
        metrics = build_basic_metrics(matches)
        if home_team_id not in metrics:
            raise_insufficient_team_history("home")
        if away_team_id not in metrics:
            raise_insufficient_team_history("away")

        league = league_averages(matches)
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
        return expected_home_goals, expected_away_goals, len(matches)
