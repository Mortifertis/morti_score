from app.models import Match
from app.services.prediction.constants import (
    IMPROVED_MODEL_NAME,
    MIN_TEAM_MATCHES,
    ROLLING_WINDOW,
)
from app.services.prediction.errors import raise_insufficient_team_history
from app.services.prediction.models.helpers import (
    blend_values,
    build_basic_metrics,
    league_averages,
    team_recent_matches,
    weighted_expected_goals,
    weighted_team_form,
)


class ImprovedPoissonModel:
    name = IMPROVED_MODEL_NAME

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

        home_matches = team_recent_matches(matches, home_team_id)
        away_matches = team_recent_matches(matches, away_team_id)
        if len(home_matches) < MIN_TEAM_MATCHES:
            raise_insufficient_team_history("home")
        if len(away_matches) < MIN_TEAM_MATCHES:
            raise_insufficient_team_history("away")

        league = league_averages(matches)
        home_form = weighted_team_form(home_matches, team_id=home_team_id)
        away_form = weighted_team_form(away_matches, team_id=away_team_id)
        home_xg = weighted_expected_goals(home_matches, team_id=home_team_id)
        away_xg = weighted_expected_goals(away_matches, team_id=away_team_id)
        home_metrics = metrics[home_team_id]
        away_metrics = metrics[away_team_id]

        base_home_goals = (
            league.home_goals
            * blend_values(home_metrics.home_attack, home_form.home_attack)
            * blend_values(away_metrics.away_defense, away_form.away_defense)
        )
        base_away_goals = (
            league.away_goals
            * blend_values(away_metrics.away_attack, away_form.away_attack)
            * blend_values(home_metrics.home_defense, home_form.home_defense)
        )
        xg_home_factor = home_xg / max(league.home_xg, 0.1)
        xg_away_factor = away_xg / max(league.away_xg, 0.1)
        expected_home_goals = base_home_goals * blend_values(
            1.0,
            xg_home_factor,
        )
        expected_away_goals = base_away_goals * blend_values(
            1.0,
            xg_away_factor,
        )
        historical_matches_used = min(
            ROLLING_WINDOW,
            len(home_matches),
            len(away_matches),
        )
        return (
            expected_home_goals,
            expected_away_goals,
            historical_matches_used,
        )
