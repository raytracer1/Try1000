"""Team and Player schemas."""

from pydantic import BaseModel
from typing import Optional


class PlayerCreate(BaseModel):
    name: str
    number: int
    position: str
    attributes: dict = {}


class PlayerResponse(BaseModel):
    id: str
    name: str
    number: int
    position: str
    attributes: dict


class TeamCreate(BaseModel):
    name: str


class TeamResponse(BaseModel):
    id: str
    user_id: str
    name: str
    players: list[PlayerResponse] = []
