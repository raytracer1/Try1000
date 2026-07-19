"""Action types, ActionOutput, and base Action class."""

from dataclasses import dataclass, field
from enum import IntEnum
from abc import ABC, abstractmethod
from try1000_engine.physics.ball import Ball
from try1000_engine.physics.player import Player
from try1000_engine.physics.stamina import Stamina

import math
import random


class ActionType(IntEnum):
    """All possible player actions."""
    HOLD = 0
    MOVE = 1
    PASS = 2
    SHOOT = 3
    CROSS = 4
    DRIBBLE = 5
    TACKLE = 6
    INTERCEPT = 7

    @property
    def triggers_cooldown(self) -> bool:
        """Whether this action triggers the post-action cooldown."""
        return self in (ActionType.PASS, ActionType.SHOOT, ActionType.CROSS,
                        ActionType.DRIBBLE, ActionType.TACKLE)

    @property
    def label(self) -> str:
        labels = {
            ActionType.HOLD: "Hold",
            ActionType.MOVE: "Move",
            ActionType.PASS: "Pass",
            ActionType.SHOOT: "Shoot",
            ActionType.CROSS: "Cross",
            ActionType.DRIBBLE: "Dribble",
            ActionType.TACKLE: "Tackle",
            ActionType.INTERCEPT: "Intercept",
        }
        return labels[self]


@dataclass
class ActionOutput:
    """What a policy returns. Action type + continuous parameters.

    Parameters are ignored for action types that don't use them.
    """
    action_type: int  # ActionType value

    # Move / Dribble
    dx: float = 0.0
    dy: float = 0.0
    speed: float = 0.0   # 0.0–1.0 fraction of max speed

    # Pass / Shoot / Cross
    power: float = 10.0      # 1.0–20.0
    angle: float = 0.0       # degrees, for Shoot
    target_x: float = 0.0    # normalized 0-1, for Pass/Cross
    target_y: float = 0.0    # normalized 0-1, for Pass/Cross

    # Tackle
    target_player_id: str = ""

    @staticmethod
    def hold() -> 'ActionOutput':
        return ActionOutput(action_type=ActionType.HOLD)

    @staticmethod
    def move(dx: float, dy: float, speed: float) -> 'ActionOutput':
        return ActionOutput(action_type=ActionType.MOVE, dx=dx, dy=dy, speed=speed)

    @staticmethod
    def pass_(target_x: float, target_y: float, power: float) -> 'ActionOutput':
        return ActionOutput(action_type=ActionType.PASS,
                            target_x=target_x, target_y=target_y, power=power)

    @staticmethod
    def shoot(angle: float, power: float) -> 'ActionOutput':
        return ActionOutput(action_type=ActionType.SHOOT, angle=angle, power=power)

    @staticmethod
    def cross(target_x: float, target_y: float, power: float) -> 'ActionOutput':
        return ActionOutput(action_type=ActionType.CROSS,
                            target_x=target_x, target_y=target_y, power=power)

    @staticmethod
    def dribble(dx: float, dy: float, speed: float) -> 'ActionOutput':
        return ActionOutput(action_type=ActionType.DRIBBLE, dx=dx, dy=dy, speed=speed)

    @staticmethod
    def tackle(target_player_id: str) -> 'ActionOutput':
        """Create a Tackle action targeting a specific player by string ID."""
        return ActionOutput(action_type=ActionType.TACKLE,
                            target_player_id=target_player_id)


class Action(ABC):
    """Base class for action resolution logic."""

    @abstractmethod
    def resolve(self, actor: Player, ball: Ball, players: list[Player],
                rng: random.Random, output: ActionOutput) -> dict | None:
        """Execute the action. Returns event dict or None."""
        ...

    def _clamp_power(self, power: float) -> float:
        return max(1.0, min(20.0, power))

    def _power_to_speed(self, power: float) -> float:
        """Convert power (1-20) to ball speed in m/s."""
        from try1000_engine.config import BALL_MAX_SPEED
        return (power / 20.0) * BALL_MAX_SPEED

    def _angle_to_vector(self, angle_deg: float) -> tuple[float, float]:
        """Convert degrees to unit vector. 0° = toward opponent goal (right)."""
        rad = math.radians(angle_deg)
        return (math.cos(rad), math.sin(rad))

    def _normalized_to_meters(self, nx: float, ny: float) -> tuple[float, float]:
        """Convert AgentPitch field coords (100×60) → engine meters."""
        from try1000_engine.config import field_to_meters
        return field_to_meters(nx, ny)
