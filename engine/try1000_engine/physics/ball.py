"""Ball state and physics."""

from dataclasses import dataclass, field
import math
from try1000_engine.config import (
    BALL_MAX_SPEED, BALL_FRICTION, BALL_AIR_FRICTION,
    BALL_RADIUS, PITCH_LENGTH, PITCH_WIDTH, GOAL_WIDTH,
    GOAL_DEPTH, TICK_DURATION, PLAYER_RADIUS,
)


@dataclass
class BallState:
    """Immutable snapshot of ball at a tick."""

    x: float = 0.0           # meters, center = (0, 0)
    y: float = 0.0
    z: float = 0.0           # height (0 = ground)
    vx: float = 0.0          # velocity m/s
    vy: float = 0.0
    vz: float = 0.0
    in_air: bool = False
    last_touch_team: str | None = None  # "home" | "away" | None
    last_touch_player: str | None = None

    @property
    def speed(self) -> float:
        return math.sqrt(self.vx ** 2 + self.vy ** 2)

    @property
    def normalized_pos(self) -> tuple[float, float]:
        """Position in 0-1 range for replay output."""
        from try1000_engine.config import meters_to_normalized
        return meters_to_normalized(self.x, self.y)


class Ball:
    """Manages ball physics: movement, friction, goal detection."""

    def __init__(self, x: float = 0.0, y: float = 0.0):
        self.x = x
        self.y = y
        self.z = 0.0
        self.vx = 0.0
        self.vy = 0.0
        self.vz = 0.0
        self.in_air = False
        self.last_touch_team: str | None = None
        self.last_touch_player: str | None = None
        # ARE engine attributes (AgentPitch port)
        self.carrier_id: str | None = None
        self._landing_zone: tuple[float, float] | None = None

    def snapshot(self) -> BallState:
        return BallState(
            x=self.x, y=self.y, z=self.z,
            vx=self.vx, vy=self.vy, vz=self.vz,
            in_air=self.in_air,
            last_touch_team=self.last_touch_team,
            last_touch_player=self.last_touch_player,
        )

    def apply_kick(self, vx: float, vy: float, vz: float = 0.0,
                   team: str | None = None, player_id: str | None = None):
        """Apply a kick force to the ball (pass, shoot, clearance)."""
        total_speed = math.sqrt(vx ** 2 + vy ** 2)
        if total_speed > BALL_MAX_SPEED:
            scale = BALL_MAX_SPEED / total_speed
            vx *= scale
            vy *= scale
        self.vx = vx
        self.vy = vy
        self.vz = vz
        self.in_air = vz > 0.5 or total_speed > 15.0
        self.last_touch_team = team
        self.last_touch_player = player_id

    def update(self, dt: float = TICK_DURATION):
        """Update ball position and velocity for one tick."""
        # Position update
        self.x += self.vx * dt
        self.y += self.vy * dt

        if self.in_air:
            # Simple vertical physics
            self.z += self.vz * dt
            self.vz -= 9.81 * dt  # gravity

        # Ground contact
        if self.z <= 0.0:
            self.z = 0.0
            self.vz = 0.0
            if self.in_air:
                # Ball hits ground — lose some speed
                self.vx *= 0.7
                self.vy *= 0.7
            self.in_air = False

        # Friction
        if not self.in_air:
            self.vx *= BALL_FRICTION
            self.vy *= BALL_FRICTION
            if abs(self.vx) < 0.1: self.vx = 0.0
            if abs(self.vy) < 0.1: self.vy = 0.0
        else:
            self.vx *= BALL_AIR_FRICTION
            self.vy *= BALL_AIR_FRICTION

        # Pitch boundary bounce (simplified)
        self._clamp_to_pitch()

    def _clamp_to_pitch(self):
        """Keep ball within pitch boundaries with bounce."""
        half_length = PITCH_LENGTH / 2
        half_width = PITCH_WIDTH / 2

        if abs(self.x) > half_length:
            self.x = math.copysign(half_length, self.x)
            self.vx *= -0.5  # bounce with energy loss
        if abs(self.y) > half_width:
            self.y = math.copysign(half_width, self.y)
            self.vy *= -0.5

    def is_out_of_play(self) -> str | None:
        """Check if ball is out of play. Returns 'throw_in_home', 'goal_kick', etc. or None."""
        half_length = PITCH_LENGTH / 2
        half_width = PITCH_WIDTH / 2

        # Touchlines
        if abs(self.y) > half_width:
            return "throw_in"
        # Goal lines (not between the posts)
        if abs(self.x) > half_length:
            if abs(self.y) < GOAL_WIDTH / 2:
                return None  # between posts — goal check separately
            return "goal_kick" if abs(self.x) > half_length else "corner"
        return None

    def is_goal(self) -> str | None:
        """Check if ball crossed goal line between posts. Returns 'home' or 'away' or None."""
        half_length = PITCH_LENGTH / 2
        half_goal = GOAL_WIDTH / 2

        if self.in_air and self.z > GOAL_DEPTH:
            return None  # over the bar

        if self.x > half_length and abs(self.y) < half_goal:
            return "away"  # ball in home team's goal → away scored
        if self.x < -half_length and abs(self.y) < half_goal:
            return "home"  # ball in away team's goal → home scored
        return None

    def distance_to(self, px: float, py: float) -> float:
        return math.sqrt((self.x - px) ** 2 + (self.y - py) ** 2)
