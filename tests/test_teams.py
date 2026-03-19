import pytest


@pytest.mark.asyncio
async def test_teams_endpoint_returns_seeded_data(client):
    response = await client.get("/api/v1/teams")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 8
    assert data[0]["name"] == "Arsenal"
