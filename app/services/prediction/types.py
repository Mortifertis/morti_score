from dataclasses import dataclass


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
