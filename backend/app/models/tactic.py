"""Tactic model."""

from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, ForeignKey, DateTime, JSON
from app.database import Base


class Tactic(Base):
    __tablename__ = "tactics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    name = Column(String(200), nullable=False)
    formation = Column(String(10), nullable=False, default="4-3-3")
    player_positions = Column(JSON, nullable=False, default=dict)
    pressing_level = Column(Integer, default=5)
    defensive_line = Column(Integer, default=5)
    attacking_width = Column(Integer, default=5)
    tempo = Column(Integer, default=5)
    passing_style = Column(String(20), default="mixed")
    build_up_style = Column(String(20), default="balanced")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
