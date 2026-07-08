"""Simulation job and result models."""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSON
from app.database import Base


class SimulationJob(Base):
    __tablename__ = "simulation_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    home_team_id = Column(UUID(as_uuid=True), ForeignKey("teams.id"), nullable=False)
    away_team_id = Column(UUID(as_uuid=True), ForeignKey("teams.id"), nullable=False)
    home_tactic_id = Column(UUID(as_uuid=True), ForeignKey("tactics.id"), nullable=False)
    away_tactic_id = Column(UUID(as_uuid=True), ForeignKey("tactics.id"), nullable=False)

    match_count = Column(Integer, nullable=False, default=10)
    status = Column(String(20), default="pending")  # pending, running, completed, failed
    progress = Column(Integer, default=0)  # 0-100
    seed_base = Column(Integer, default=42)
    engine_version = Column(String(20), default="rule-based-v1")

    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


class SimulationResult(Base):
    __tablename__ = "simulation_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("simulation_jobs.id"), nullable=False)

    match_index = Column(Integer, nullable=False)
    home_score = Column(Integer, default=0)
    away_score = Column(Integer, default=0)
    home_xg = Column(Float, default=0.0)
    away_xg = Column(Float, default=0.0)
    home_possession = Column(Float, default=50.0)
    away_possession = Column(Float, default=50.0)

    # Detailed stats (JSON blob)
    stats = Column(JSON, nullable=False, default=dict)

    # Replay data: stored as JSON array of tick snapshots
    events = Column(JSON, nullable=False, default=list)

    created_at = Column(DateTime, default=datetime.utcnow)
