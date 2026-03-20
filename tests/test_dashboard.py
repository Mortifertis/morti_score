import pytest


@pytest.mark.anyio
async def test_dashboard_prediction_shows_model_comparison(client):
    response = await client.post(
        "/dashboard",
        data={"home_team_id": 1, "away_team_id": 2},
    )

    assert response.status_code == 200
    assert "Compare models" in response.text
    assert "basic_poisson" in response.text
    assert "improved_poisson" in response.text
    assert "elo_based" in response.text
