from dataclasses import dataclass

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Match, MatchStatus, Team
from app.repositories.match import MatchRepository
from app.repositories.team import TeamRepository
from app.services.prediction.constants import MIN_HISTORICAL_MATCHES
from app.services.prediction.errors import raise_prediction_error


@dataclass
class PredictionContext:
    home_team: Team
    away_team: Team
    matches: list[Match]


class PredictionContextLoader:
    def __init__(self, session: AsyncSession) -> None:
        self.team_repository = TeamRepository(session)
        self.match_repository = MatchRepository(session)

    async def load(
        self,
        home_team_id: int,
        away_team_id: int,
    ) -> PredictionContext:
        home_team = await self.team_repository.get_team(home_team_id)
        away_team = await self.team_repository.get_team(away_team_id)
        if home_team is None:
            raise_prediction_error(
                status_code=status.HTTP_404_NOT_FOUND,
                code="home_team_not_found",
                message="Home team not found.",
            )
        if away_team is None:
            raise_prediction_error(
                status_code=status.HTTP_404_NOT_FOUND,
                code="away_team_not_found",
                message="Away team not found.",
            )

        matches = await self.match_repository.list_matches(
            status=MatchStatus.FINISHED,
            limit=1000,
        )
        finished_matches = [
            match
            for match in matches
            if match.home_goals is not None and match.away_goals is not None
        ]
        if not finished_matches:
            raise_prediction_error(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                code="no_finished_matches",
                message=(
                    "Prediction is unavailable because there are no "
                    "finished matches to analyze."
                ),
            )
        if len(finished_matches) < MIN_HISTORICAL_MATCHES:
            raise_prediction_error(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                code="insufficient_historical_matches",
                message=(
                    "Prediction needs more finished matches before the "
                    "model can be used."
                ),
                extra={
                    "historical_matches": len(finished_matches),
                    "minimum_required": MIN_HISTORICAL_MATCHES,
                },
            )
        return PredictionContext(home_team, away_team, finished_matches)
