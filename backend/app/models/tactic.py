"""Tactic model."""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSON
from app.database import Base


class Tactic(Base):
    __tablename__ = "tactics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    team_id = Column(UUID(as_uuid=True), ForeignKey("teams.id"), nullable=False)
    name = Column(String(200), nullable=False)
    formation = Column(String(10), nullable=False, default="4-3-3")

    # Player positioning: {player_id: {x: float, y: float, role: str}}
    player_positions = Column(JSON, nullable=False, default=dict)

    # Tactical parameters (1-10 scale)
    pressing_level = Column(Integer, default=5)
    defensive_line = Column(Integer, default=5)
    attacking_width = Column(Integer, default=5)
    tempo = Column(Integer, default=5)

    # Style enums
    passing_style = Column(String(20), default="mixed")  # short, mixed, direct
    build_up_style = Column(String(20), default="balanced")  # slow, balanced, fast

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
