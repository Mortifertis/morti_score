import pytest


@pytest.mark.anyio
async def test_matches_endpoint_filters_and_sorts(client):
    response = await client.get(
        "/api/v1/matches",
        params={
            "status": "finished",
            "team_id": 1,
            "season": "2024/2025",
            "sort_order": "asc",
            "limit": 5,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data
    assert all(match["status"] == "finished" for match in data)
    assert all(match["season"] == "2024/2025" for match in data)
    assert all(
        1 in (match["home_team_id"], match["away_team_id"]) for match in data
    )
    dates = [match["match_date"] for match in data]
    assert dates == sorted(dates)
