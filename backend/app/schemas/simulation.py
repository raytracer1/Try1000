"""Simulation schemas."""

from pydantic import BaseModel
from typing import Optional


class SimulateRequest(BaseModel):
    home_team_id: int
    away_team_id: int
    home_tactic_id: int
    away_tactic_id: int
    match_count: int = 10


class SimulateResponse(BaseModel):
    job_id: int


class JobStatusResponse(BaseModel):
    id: int
    status: str
    progress: int
    match_count: int
    home_team_id: int
    away_team_id: int
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
