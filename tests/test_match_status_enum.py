import pytest
from sqlalchemy import text

from app.models import Match, MatchStatus


@pytest.mark.anyio
async def test_match_status_uses_enum_values_in_database(session_factory):
    async with session_factory() as session:
        match = await session.get(Match, 1)
        assert match is not None
        assert match.status == MatchStatus.FINISHED

        result = await session.execute(
            text("SELECT status FROM matches WHERE id = :match_id"),
            {"match_id": 1},
        )

    assert result.scalar_one() == MatchStatus.FINISHED.value
