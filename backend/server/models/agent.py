"""Agent result model — stores completed AI analysis."""

from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, JSON, ForeignKey
from server.database import Base


class AgentResult(Base):
    __tablename__ = "agent_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    task_type = Column(String(30), nullable=False)  # analyze_tactics, match_report, optimize
    tactic_id = Column(Integer, nullable=True)
    job_id = Column(Integer, nullable=True)
    result = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
