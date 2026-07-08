"""Tactic schemas."""

from pydantic import BaseModel
from typing import Optional


class TacticCreate(BaseModel):
    team_id: int
    name: str
    formation: str = "4-3-3"
    player_positions: dict = {}
    pressing_level: int = 5
    defensive_line: int = 5
    attacking_width: int = 5
    tempo: int = 5
    passing_style: str = "mixed"
    build_up_style: str = "balanced"


class TacticUpdate(BaseModel):
    name: Optional[str] = None
    formation: Optional[str] = None
    player_positions: Optional[dict] = None
    pressing_level: Optional[int] = None
    defensive_line: Optional[int] = None
    attacking_width: Optional[int] = None
    tempo: Optional[int] = None
    passing_style: Optional[str] = None
    build_up_style: Optional[str] = None


class TacticResponse(BaseModel):
    id: int
    user_id: int
    team_id: int
    name: str
    formation: str
    player_positions: dict
    pressing_level: int
    defensive_line: int
    attacking_width: int
    tempo: int
    passing_style: str
    build_up_style: str
