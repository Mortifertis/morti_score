from fastapi import APIRouter, Depends

from app.api.deps import get_prediction_service
from app.schemas import ModelComparisonRead, PredictionRead, PredictionRequest
from app.services.prediction import PredictionService

router = APIRouter(prefix="/predictions", tags=["predictions"])


@router.post("/match", response_model=PredictionRead)
async def predict_match(
    payload: PredictionRequest,
    service: PredictionService = Depends(get_prediction_service),
) -> PredictionRead:
    return await service.predict_match(
        payload.home_team_id,
        payload.away_team_id,
    )


@router.get(
    "/match/{home_team_id}/{away_team_id}",
    response_model=PredictionRead,
)
async def get_match_prediction(
    home_team_id: int,
    away_team_id: int,
    service: PredictionService = Depends(get_prediction_service),
) -> PredictionRead:
    return await service.predict_match(home_team_id, away_team_id)


@router.get(
    "/compare/{home_team_id}/{away_team_id}",
    response_model=ModelComparisonRead,
)
async def compare_predictions(
    home_team_id: int,
    away_team_id: int,
    service: PredictionService = Depends(get_prediction_service),
) -> ModelComparisonRead:
    return await service.compare_models(home_team_id, away_team_id)
