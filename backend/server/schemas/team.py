"""Team and Player schemas."""

from pydantic import BaseModel


class PlayerCreate(BaseModel):
    name: str
    number: int
    position: str
    attributes: dict = {}


class PlayerResponse(BaseModel):
    id: int
    name: str
    number: int
    position: str
    attributes: dict


class TeamCreate(BaseModel):
    name: str


class TeamResponse(BaseModel):
    id: int
    user_id: int
    name: str
    players: list[PlayerResponse] = []
