from pydantic import BaseModel, Field


class TeamSummary(BaseModel):
    id: int
    name: str


class PredictionRequest(BaseModel):
    home_team_id: int = Field(gt=0)
    away_team_id: int = Field(gt=0)


class ProbabilityRead(BaseModel):
    home_win: float
    draw: float
    away_win: float


class ScorelineRead(BaseModel):
    home_goals: int
    away_goals: int
    probability: float


class ModelInfoRead(BaseModel):
    name: str
    historical_matches_used: int


class PredictionRead(BaseModel):
    home_team: TeamSummary
    away_team: TeamSummary
    expected_home_goals: float
    expected_away_goals: float
    probabilities: ProbabilityRead
    top_scorelines: list[ScorelineRead]
    model_info: ModelInfoRead


class ModelComparisonRead(BaseModel):
    basic_poisson: PredictionRead
    improved_poisson: PredictionRead
    elo_based: PredictionRead
