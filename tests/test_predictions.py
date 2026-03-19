import pytest

from app.services.prediction import PredictionService


@pytest.mark.asyncio
async def test_prediction_endpoint_returns_probabilities(client):
    response = await client.get("/api/v1/predictions/match/1/2")
    assert response.status_code == 200
    data = response.json()
    assert data["home_team"]["name"] == "Arsenal"
    total = sum(data["probabilities"].values())
    assert 0.9 <= total <= 1.0
    assert len(data["top_scorelines"]) == 5


@pytest.mark.asyncio
async def test_basic_model_calculation(session_factory):
    async with session_factory() as session:
        service = PredictionService(session)
        result = await service.predict_match(1, 2)
    assert result.expected_home_goals > 0
    assert result.expected_away_goals > 0
    assert result.model_info.historical_matches_used >= 20
