"""Player state and movement."""

from dataclasses import dataclass
import math
from try1000_engine.config import (
    MAX_PLAYER_SPEED, JOG_SPEED, WALK_SPEED,
    PLAYER_RADIUS, TICK_DURATION,
)


@dataclass
class PlayerState:
    """Immutable snapshot of a player at a tick."""

    player_id: str
    team: str                  # "home" | "away"
    role: str                  # "GK", "CB", "ST", etc.
    x: float                   # meters
    y: float
    facing_angle: float = 0.0  # radians, 0 = toward opponent goal

    # Attributes (0-100)
    pace: float = 70.0
    shooting: float = 70.0
    passing: float = 70.0
    dribbling: float = 70.0
    defending: float = 70.0
    physicality: float = 70.0
    stamina_val: float = 100.0
    awareness: float = 70.0
    composure: float = 70.0

    # Status
    health: float = 1.0          # 0.0-1.0
    has_ball: bool = False
    cooldown_remaining: int = 0

    @property
    def speed_multiplier(self) -> float:
        """Speed modifier from stamina."""
        s = self.stamina_val
        if s > 70: return 1.0
        if s > 50: return 0.85
        return 0.70

    @property
    def max_speed(self) -> float:
        return MAX_PLAYER_SPEED * self.speed_multiplier * (self.pace / 70.0)

    @property
    def position_tuple(self) -> tuple[float, float]:
        return (self.x, self.y)


class Player:
    """Mutable player entity updated during a match."""

    def __init__(self, player_id: str, team: str, role: str,
                 x: float = 0.0, y: float = 0.0,
                 pace: float = 70.0, shooting: float = 70.0,
                 passing: float = 70.0, dribbling: float = 70.0,
                 defending: float = 70.0, physicality: float = 70.0,
                 stamina_val: float = 100.0, awareness: float = 70.0,
                 composure: float = 70.0):
        self.player_id = player_id
        self.team = team
        self.role = role
        self.x = x
        self.y = y
        self.facing_angle = 0.0 if team == "home" else math.pi
        self.pace = pace
        self.shooting = shooting
        self.passing = passing
        self.dribbling = dribbling
        self.defending = defending
        self.physicality = physicality
        self.stamina = stamina_val
        self.awareness = awareness
        self.composure = composure
        self.health = 1.0
        self.has_ball = False
        self.cooldown_remaining = 0
        self.sent_off = False  # red card → excluded from play

        # Movement state
        self._target_x: float | None = None
        self._target_y: float | None = None
        self._move_speed_fraction: float = 0.0  # 0.0-1.0 of max speed

    def snapshot(self) -> PlayerState:
        return PlayerState(
            player_id=self.player_id, team=self.team, role=self.role,
            x=self.x, y=self.y, facing_angle=self.facing_angle,
            pace=self.pace, shooting=self.shooting, passing=self.passing,
            dribbling=self.dribbling, defending=self.defending,
            physicality=self.physicality, stamina_val=self.stamina,
            awareness=self.awareness, composure=self.composure,
            health=self.health, has_ball=self.has_ball,
            cooldown_remaining=self.cooldown_remaining,
        )

    def set_target(self, x: float, y: float, speed_fraction: float = 1.0):
        """Set movement target for this tick."""
        self._target_x = x
        self._target_y = y
        self._move_speed_fraction = max(0.0, min(1.0, speed_fraction))

    def move_toward_target(self, dt: float = TICK_DURATION):
        """Move toward target position. Call once per tick."""
        if self._target_x is None or self._target_y is None:
            return

        dx = self._target_x - self.x
        dy = self._target_y - self.y
        dist = math.sqrt(dx ** 2 + dy ** 2)

        if dist < 0.1:  # Arrived
            self._target_x = None
            self._target_y = None
            return

        # Calculate speed
        max_speed = self.max_speed
        if self._move_speed_fraction < 0.3:
            actual_speed = WALK_SPEED
        elif self._move_speed_fraction < 0.6:
            actual_speed = JOG_SPEED
        else:
            actual_speed = max_speed

        move_distance = min(actual_speed * dt, dist)
        self.x += (dx / dist) * move_distance
        self.y += (dy / dist) * move_distance

        # Update facing
        self.facing_angle = math.atan2(dy, dx)

    def update_cooldown(self):
        """Decrement cooldown counter."""
        if self.cooldown_remaining > 0:
            self.cooldown_remaining -= 1

    def trigger_cooldown(self, duration: int = 3):
        """Start cooldown after a cooldown-triggering action."""
        self.cooldown_remaining = duration

    @property
    def is_on_cooldown(self) -> bool:
        return self.cooldown_remaining > 0

    @property
    def speed_multiplier(self) -> float:
        s = self.stamina
        if s > 70: return 1.0
        if s > 50: return 0.85
        return 0.70

    @property
    def max_speed(self) -> float:
        return MAX_PLAYER_SPEED * self.speed_multiplier * (self.pace / 70.0)

    @property
    def current_speed(self) -> float:
        """Estimate current speed from movement state (for stamina calc)."""
        if self._target_x is None:
            return 0.0
        if self._move_speed_fraction < 0.3:
            return WALK_SPEED
        elif self._move_speed_fraction < 0.6:
            return JOG_SPEED
        return self.max_speed

    def position(self) -> tuple[float, float]:
        return (self.x, self.y)

    def distance_to(self, px: float, py: float) -> float:
        return math.sqrt((self.x - px) ** 2 + (self.y - py) ** 2)
