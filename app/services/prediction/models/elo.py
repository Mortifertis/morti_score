from app.models import Match
from app.services.prediction.constants import (
    ELO_BASE_RATING,
    ELO_K_FACTOR,
    ELO_MODEL_NAME,
    HOME_ADVANTAGE_ELO,
    MIN_TEAM_MATCHES,
)
from app.services.prediction.errors import raise_insufficient_team_history
from app.services.prediction.models.helpers import league_averages
from app.services.prediction.types import EloRating


class EloModel:
    name = ELO_MODEL_NAME

    def predict_expected_goals(
        self,
        *,
        home_team_id: int,
        away_team_id: int,
        matches: list[Match],
    ) -> tuple[float, float, int]:
        ratings = self.calculate_elo(matches)
        home_rating = ratings.get(home_team_id)
        away_rating = ratings.get(away_team_id)
        if (
            home_rating is None
            or home_rating.matches_played < MIN_TEAM_MATCHES
        ):
            raise_insufficient_team_history("home")
        if (
            away_rating is None
            or away_rating.matches_played < MIN_TEAM_MATCHES
        ):
            raise_insufficient_team_history("away")

        league = league_averages(matches)
        rating_gap = (
            home_rating.rating + HOME_ADVANTAGE_ELO - away_rating.rating
        )
        win_expectancy = 1.0 / (1.0 + 10 ** (-rating_gap / 400))
        goal_shift = (win_expectancy - 0.5) * 1.35
        expected_home_goals = league.home_goals + goal_shift
        expected_away_goals = league.away_goals - goal_shift * 0.9
        return expected_home_goals, expected_away_goals, len(matches)

    def calculate_elo(self, matches: list[Match]) -> dict[int, EloRating]:
        ratings: dict[int, EloRating] = {}
        ordered = sorted(matches, key=lambda item: (item.match_date, item.id))
        for match in ordered:
            home = ratings.setdefault(
                match.home_team_id,
                EloRating(ELO_BASE_RATING, 0),
            )
            away = ratings.setdefault(
                match.away_team_id,
                EloRating(ELO_BASE_RATING, 0),
            )
            home_expected = 1.0 / (
                1.0
                + 10
                ** ((away.rating - home.rating - HOME_ADVANTAGE_ELO) / 400)
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
                ELO_K_FACTOR * margin_factor * (home_result - home_expected)
            )
            away.rating += (
                ELO_K_FACTOR * margin_factor * (away_result - away_expected)
            )
            home.matches_played += 1
            away.matches_played += 1
        return ratings
