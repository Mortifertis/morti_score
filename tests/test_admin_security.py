import pytest


@pytest.mark.anyio
async def test_admin_endpoint_rejects_missing_token(client) -> None:
    response = await client.post("/api/v1/admin/seed-data")

    assert response.status_code == 403


@pytest.mark.anyio
async def test_admin_endpoint_rejects_invalid_token(client) -> None:
    response = await client.post(
        "/api/v1/admin/seed-data",
        headers={"X-Admin-Token": "wrong-token"},
    )

    assert response.status_code == 403


@pytest.mark.anyio
async def test_admin_endpoint_accepts_valid_token(client) -> None:
    response = await client.post(
        "/api/v1/admin/seed-data",
        headers={"X-Admin-Token": "super-secret-admin-token"},
    )

    assert response.status_code == 200
    assert response.json()["message"].startswith("Seed finished:")