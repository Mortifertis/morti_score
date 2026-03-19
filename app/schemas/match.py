from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.models.match import MatchStatus
from app.schemas.team import TeamRead


class MatchRead(BaseModel):
    id: int
    home_team_id: int
    away_team_id: int
    home_goals: int | None
    away_goals: int | None
    match_date: date
    season: str
    status: MatchStatus
    created_at: datetime
    home_team: TeamRead
    away_team: TeamRead

    model_config = ConfigDict(from_attributes=True)
