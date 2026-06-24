import math

from app.schemas.prediction import ProbabilityRead, ScorelineRead
from app.services.prediction.constants import DRAW_FACTOR, MIN_PROBABILITY_SUM


def poisson_probability(expected_goals: float, goals: int) -> float:
    return (
        math.exp(-expected_goals)
        * (expected_goals**goals)
        / math.factorial(goals)
    )


def normalize_probabilities(
    *,
    home_win: float,
    draw: float,
    away_win: float,
) -> tuple[float, float, float]:
    total_probability = home_win + draw + away_win
    adjusted_draw = min(
        draw + DRAW_FACTOR * (1 - total_probability),
        1,
    )
    remainder = max(
        home_win + adjusted_draw + away_win,
        MIN_PROBABILITY_SUM,
    )
    return (
        home_win / remainder,
        adjusted_draw / remainder,
        away_win / remainder,
    )


def build_score_matrix(
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
            probability = poisson_probability(
                expected_home_goals,
                home_goals,
            ) * poisson_probability(expected_away_goals, away_goals)
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
    home_win, draw, away_win = normalize_probabilities(
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
