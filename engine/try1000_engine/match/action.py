"""Action types — exact replica of AgentPitch foundation/action.py.

Frozen dataclasses returned by decide() callbacks. The ARE dispatches
on isinstance() checks — same semantics as AgentPitch.
"""

from __future__ import annotations
from dataclasses import dataclass


class Action:
    """Marker base class for all player actions."""
    __slots__ = ()


@dataclass(frozen=True)
class Move(Action):
    """Move toward a direction at a given speed ratio."""
    dx: float
    dy: float
    speed: float  # [0.0, 1.0]


@dataclass(frozen=True)
class Pass(Action):
    """Pass the ball toward a target position with a given power."""
    target_pos: tuple[float, float]  # (x, y) in field coords
    power: int  # [1, 20]


@dataclass(frozen=True)
class Shoot(Action):
    """Shoot at the goal with a given angle offset and power."""
    angle: float  # degrees, relative to goal center
    power: int    # [1, 20]


@dataclass(frozen=True)
class Tackle(Action):
    """Tackle a specific opponent to try to win the ball."""
    target_player_id: str  # ADR-0004 format "{team_id}_{index}"


@dataclass(frozen=True)
class Hold(Action):
    """Do nothing — universal fallback."""
    pass
