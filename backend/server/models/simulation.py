"""Simulation job and result models."""

from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, ForeignKey, DateTime, JSON
from server.database import Base


class SimulationJob(Base):
    __tablename__ = "simulation_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    home_team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    away_team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    home_tactic_id = Column(Integer, ForeignKey("tactics.id"), nullable=False)
    away_tactic_id = Column(Integer, ForeignKey("tactics.id"), nullable=False)
    match_count = Column(Integer, nullable=False, default=10)
    status = Column(String(20), default="pending")
    progress = Column(Integer, default=0)
    seed_base = Column(Integer, default=42)
    engine_version = Column(String(20), default="rule-based-v1")
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


class SimulationResult(Base):
    __tablename__ = "simulation_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey("simulation_jobs.id"), nullable=False)
    match_index = Column(Integer, nullable=False)
    home_score = Column(Integer, default=0)
    away_score = Column(Integer, default=0)
    home_xg = Column(Float, default=0.0)
    away_xg = Column(Float, default=0.0)
    home_possession = Column(Float, default=50.0)
    away_possession = Column(Float, default=50.0)
    stats = Column(JSON, nullable=False, default=dict)
    replay_path = Column(String(500), nullable=True)  # relative path to .jsonl.gz file
    created_at = Column(DateTime, default=datetime.utcnow)
