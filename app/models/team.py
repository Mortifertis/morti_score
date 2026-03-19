from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    short_name: Mapped[str] = mapped_column(String(20), nullable=False)
    country: Mapped[str] = mapped_column(String(80), nullable=False)
    league: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    home_matches = relationship(
        "Match",
        back_populates="home_team",
        foreign_keys="Match.home_team_id",
    )
    away_matches = relationship(
        "Match",
        back_populates="away_team",
        foreign_keys="Match.away_team_id",
    )
    standing = relationship("Standing", back_populates="team", uselist=False)
