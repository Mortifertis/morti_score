from app.models import Match
from app.services.prediction.constants import MIN_TEAM_MATCHES, ROLLING_WINDOW
from app.services.prediction.types import LeagueAverages, TeamForm, TeamMetrics


def empty_aggregate() -> dict[str, float]:
    return {
        "home_played": 0.0,
        "home_scored": 0.0,
        "home_conceded": 0.0,
        "away_played": 0.0,
        "away_scored": 0.0,
        "away_conceded": 0.0,
    }


def recent_weight(index: int) -> float:
    return max(0.35, 1.0 - index * 0.08)


def blend_values(base_value: float, form_value: float) -> float:
    normalized_form = max(form_value, 0.1)
    return (base_value * 0.65) + (normalized_form * 0.35)


def team_match_xg(match: Match, team_id: int) -> float:
    is_home = match.home_team_id == team_id
    goals_for = match.home_goals if is_home else match.away_goals
    goals_against = match.away_goals if is_home else match.home_goals
    shots_proxy = 1.0 if is_home else 0.92
    attack_bonus = 0.28 * (goals_for or 0)
    defense_bonus = 0.08 * (goals_against or 0)
    return max(0.25, 0.72 + attack_bonus + defense_bonus * shots_proxy)


def match_expected_goals(match: Match, is_home: bool) -> float:
    team_id = match.home_team_id if is_home else match.away_team_id
    return team_match_xg(match, team_id)


def league_averages(matches: list[Match]) -> LeagueAverages:
    total_matches = max(len(matches), 1)
    home_goals = sum(match.home_goals or 0 for match in matches)
    away_goals = sum(match.away_goals or 0 for match in matches)
    home_xg = sum(match_expected_goals(match, True) for match in matches)
    away_xg = sum(match_expected_goals(match, False) for match in matches)
    return LeagueAverages(
        home_goals=home_goals / total_matches,
        away_goals=away_goals / total_matches,
        home_xg=home_xg / total_matches,
        away_xg=away_xg / total_matches,
    )


def build_basic_metrics(matches: list[Match]) -> dict[int, TeamMetrics]:
    aggregates: dict[int, dict[str, float]] = {}
    for match in matches:
        home = aggregates.setdefault(match.home_team_id, empty_aggregate())
        away = aggregates.setdefault(match.away_team_id, empty_aggregate())
        home["home_played"] += 1
        home["home_scored"] += match.home_goals or 0
        home["home_conceded"] += match.away_goals or 0
        away["away_played"] += 1
        away["away_scored"] += match.away_goals or 0
        away["away_conceded"] += match.home_goals or 0

    league = league_averages(matches)
    metrics: dict[int, TeamMetrics] = {}
    for team_id, values in aggregates.items():
        if (
            values["home_played"] < MIN_TEAM_MATCHES
            or values["away_played"] < MIN_TEAM_MATCHES
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


def team_recent_matches(matches: list[Match], team_id: int) -> list[Match]:
    relevant = [
        match
        for match in matches
        if team_id in {match.home_team_id, match.away_team_id}
    ]
    relevant.sort(key=lambda item: (item.match_date, item.id), reverse=True)
    return relevant[:ROLLING_WINDOW]


def weighted_team_form(matches: list[Match], *, team_id: int) -> TeamForm:
    home_scored = 0.0
    home_conceded = 0.0
    home_weight = 0.0
    away_scored = 0.0
    away_conceded = 0.0
    away_weight = 0.0
    for index, match in enumerate(matches):
        weight = recent_weight(index)
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


def weighted_expected_goals(matches: list[Match], *, team_id: int) -> float:
    total = 0.0
    weights = 0.0
    for index, match in enumerate(matches):
        weight = recent_weight(index)
        total += team_match_xg(match, team_id) * weight
        weights += weight
    return total / max(weights, 0.1)
