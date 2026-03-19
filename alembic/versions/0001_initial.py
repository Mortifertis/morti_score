"""initial schema"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
        match_status_enum = postgresql.ENUM(
        "finished",
        "scheduled",
        name="match_status",
        create_type=False,
    )
    match_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "teams",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False, unique=True),
        sa.Column("short_name", sa.String(length=20), nullable=False),
        sa.Column("country", sa.String(length=80), nullable=False),
        sa.Column("league", sa.String(length=120), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_teams_id", "teams", ["id"])

    op.create_table(
        "matches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("home_team_id", sa.Integer(), nullable=False),
        sa.Column("away_team_id", sa.Integer(), nullable=False),
        sa.Column("home_goals", sa.Integer(), nullable=True),
        sa.Column("away_goals", sa.Integer(), nullable=True),
        sa.Column("match_date", sa.Date(), nullable=False),
        sa.Column("season", sa.String(length=20), nullable=False),
        sa.Column("status", match_status_enum, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["away_team_id"], ["teams.id"]),
        sa.ForeignKeyConstraint(["home_team_id"], ["teams.id"]),
    )
    op.create_index("ix_matches_id", "matches", ["id"])

    op.create_table(
        "standings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("team_id", sa.Integer(), nullable=False, unique=True),
        sa.Column("played", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("wins", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("draws", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("losses", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "goals_for",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "goals_against",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "goal_difference",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("points", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"]),
    )
    op.create_index("ix_standings_id", "standings", ["id"])


def downgrade() -> None:
    op.drop_index("ix_standings_id", table_name="standings")
    op.drop_table("standings")
    op.drop_index("ix_matches_id", table_name="matches")
    op.drop_table("matches")
    op.drop_index("ix_teams_id", table_name="teams")
    op.drop_table("teams")

    match_status_enum = postgresql.ENUM(
        "finished",
        "scheduled",
        name="match_status",
        create_type=False,
    )
    match_status_enum.drop(op.get_bind(), checkfirst=True)
