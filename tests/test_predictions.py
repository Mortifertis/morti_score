from datetime import date

from fastapi import HTTPException
import pytest

from app.db.base import Base
from app.models import Match, MatchStatus, Team
from app.services.prediction import PredictionService
from app.services.seed import SeedService


@pytest.mark.anyio
async def test_prediction_endpoint_returns_probabilities(client):
    response = await client.get("/api/v1/predictions/match/1/2")
    assert response.status_code == 200
    data = response.json()
    assert data["home_team"]["name"] == "Arsenal"
    total = sum(data["probabilities"].values())
    assert 0.99 <= total <= 1.01
    assert len(data["top_scorelines"]) == 5
    assert data["model_info"]["name"] == "improved_poisson"


@pytest.mark.anyio
async def test_basic_model_calculation(session_factory):
    async with session_factory() as session:
        service = PredictionService(session)
        result = await service.compare_models(1, 2)
    assert result.basic_poisson.expected_home_goals > 0
    assert result.improved_poisson.expected_home_goals > 0
    assert result.elo_based.expected_away_goals > 0
    assert result.basic_poisson.model_info.historical_matches_used >= 20


@pytest.mark.anyio
async def test_compare_endpoint_returns_all_models(client):
    response = await client.get("/api/v1/predictions/compare/1/2")
    assert response.status_code == 200
    data = response.json()
    assert set(data) == {
        "basic_poisson",
        "improved_poisson",
        "elo_based",
    }
    assert data["basic_poisson"]["model_info"]["name"] == "basic_poisson"
    assert data["improved_poisson"]["model_info"]["name"] == "improved_poisson"
    assert data["elo_based"]["model_info"]["name"] == "elo_based"


@pytest.mark.anyio
async def test_prediction_rejects_same_team(client):
    response = await client.get("/api/v1/predictions/match/1/1")
    assert response.status_code == 422
    assert response.json()["detail"] == {
        "code": "same_team_matchup",
        "message": "Home and away teams must be different.",
    }


@pytest.mark.anyio
async def test_prediction_returns_not_found_for_missing_team(client):
    response = await client.get("/api/v1/predictions/match/999/2")
    assert response.status_code == 404
    assert response.json()["detail"] == {
        "code": "home_team_not_found",
        "message": "Home team not found.",
    }


@pytest.mark.anyio
async def test_prediction_fails_without_finished_matches(session_factory):
    async with session_factory() as session:
        service = PredictionService(session)
        await service.clear_cached_predictions()
        await session.execute(Base.metadata.tables["matches"].delete())
        await session.commit()
        try:
            with pytest.raises(HTTPException) as exc_info:
                await service.predict_match(1, 2)
        finally:
            await SeedService(session).seed_all()
            await service.clear_cached_predictions()
    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == {
        "code": "no_finished_matches",
        "message": (
            "Prediction is unavailable because there are no finished "
            "matches to analyze."
        ),
    }


@pytest.mark.anyio
async def test_prediction_fails_for_team_without_enough_history(
    session_factory,
):
    async with session_factory() as session:
        service = PredictionService(session)
        await service.clear_cached_predictions()
        team = Team(
            name="Test United",
            short_name="TST",
            country="England",
            league="Premier League",
        )
        session.add(team)
        await session.flush()
        match = Match(
            home_team_id=1,
            away_team_id=team.id,
            home_goals=1,
            away_goals=0,
            match_date=date(2024, 8, 1),
            season="2024/2025",
            status=MatchStatus.FINISHED,
        )
        session.add(match)
        await session.commit()
        try:
            with pytest.raises(HTTPException) as exc_info:
                await service.predict_match(1, team.id)
        finally:
            await session.delete(match)
            await session.delete(team)
            await session.commit()
            await service.clear_cached_predictions()
    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == {
        "code": "insufficient_away_team_history",
        "message": (
            "Away team does not have enough historical matches for "
            "prediction."
        ),
    }
