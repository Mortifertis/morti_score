from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.team import TeamRead


class StandingRead(BaseModel):
    id: int
    team_id: int
    played: int
    wins: int
    draws: int
    losses: int
    goals_for: int
    goals_against: int
    goal_difference: int
    points: int
    updated_at: datetime
    team: TeamRead

    model_config = ConfigDict(from_attributes=True)
