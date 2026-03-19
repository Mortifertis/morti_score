from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TeamBase(BaseModel):
    name: str
    short_name: str
    country: str
    league: str


class TeamRead(TeamBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
