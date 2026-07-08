"""Simulation schemas."""

from pydantic import BaseModel
from typing import Optional


class SimulateRequest(BaseModel):
    home_team_id: str
    away_team_id: str
    home_tactic_id: str
    away_tactic_id: str
    match_count: int = 10  # 1, 10, 100, 1000


class SimulateResponse(BaseModel):
    job_id: str


class JobStatusResponse(BaseModel):
    id: str
    status: str
    progress: int
    match_count: int
    home_team_id: str
    away_team_id: str
    created_at: str
    completed_at: Optional[str] = None


class MatchResultResponse(BaseModel):
    match_index: int
    home_score: int
    away_score: int
    home_xg: float
    away_xg: float
    home_possession: float
    away_possession: float
    stats: dict


class JobDetailResponse(JobStatusResponse):
    results: list[MatchResultResponse] = []
