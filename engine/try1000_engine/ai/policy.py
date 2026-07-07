"""Policy interface and Observation data structure.

This is the boundary between the engine and the decision-making AI.
Swap implementations without changing anything else.
"""

from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from try1000_engine.actions.base import ActionOutput, ActionType


@dataclass
class Observation:
    """Flattened feature vector for a single player at a single tick.

    Built from game_state + player_state + history at snapshot time.
    All values normalized to [0, 1] or [-1, 1] for neural network compatibility.
    Total: 49 dimensions.
    """

    # ─── Ball features (5) ───
    ball_x: float = 0.5            # normalized 0-1
    ball_y: float = 0.5
    ball_distance: float = 0.0     # normalized to [0, 1], 1 = far away
    ball_possession_team: int = 0  # -1=away, 0=none, 1=home (relative)
    has_ball: int = 0              # 0 or 1

    # ─── Goal features (4) ───
    distance_to_opponent_goal: float = 0.5  # normalized
    angle_to_opponent_goal: float = 0.0     # normalized [-1, 1], 0 = straight
    distance_to_own_goal: float = 0.5       # normalized
    angle_to_own_goal: float = 0.0          # normalized

    # ─── Nearest teammate (3) ───
    nearest_teammate_distance: float = 1.0  # 1 = far
    nearest_teammate_angle: float = 0.0     # normalized [-1, 1]
    nearest_teammate_role: int = 0          # one-hot index

    # ─── Nearest opponent (3) ───
    nearest_opponent_distance: float = 1.0  # 1 = far
    nearest_opponent_angle: float = 0.0     # normalized [-1, 1]
    pressure_level: float = 0.0             # normalized [0, 1], count within 5m / 5

    # ─── Spatial (2) ───
    space_ahead: float = 0.0               # open space in facing direction [0, 1]
    distance_to_touchline: float = 0.5     # normalized [0, 0.5]

    # ─── Self attributes (11) ───
    pace: float = 0.7
    shooting: float = 0.7
    passing: float = 0.7
    dribbling: float = 0.7
    defending: float = 0.7
    physicality: float = 0.7
    stamina_obs: float = 1.0
    awareness: float = 0.7
    composure: float = 0.7
    role_obs: int = 0               # one-hot role idx
    health: float = 1.0

    # ─── Match context (5) ───
    score_diff: int = 0             # positive = winning
    match_time_ratio: float = 0.0   # 0.0 to 1.0
    half: int = 1                   # 1 or 2
    phase_id: int = 0               # one-hot phase idx
    possession_phase: int = 0       # -1=out, 0=contested, 1=in possession

    # ─── History (10) ─── last 5 action types + success flags
    history_action_types: list[int] = field(default_factory=lambda: [0, 0, 0, 0, 0])
    history_success_flags: list[int] = field(default_factory=lambda: [0, 0, 0, 0, 0])

    # ─── Tactical context (6) ───
    pressing_level: float = 0.5
    defensive_line: float = 0.5
    attacking_width: float = 0.5
    passing_style: int = 1         # 0=short, 1=mixed, 2=direct
    build_up_style: int = 1        # 0=slow, 1=balanced, 2=fast
    tempo: float = 0.5

    def to_vector(self) -> list[float]:
        """Flatten to a 49-element vector for neural network input."""
        return [
            self.ball_x, self.ball_y, self.ball_distance,
            float(self.ball_possession_team), float(self.has_ball),
            self.distance_to_opponent_goal, self.angle_to_opponent_goal,
            self.distance_to_own_goal, self.angle_to_own_goal,
            self.nearest_teammate_distance, self.nearest_teammate_angle,
            float(self.nearest_teammate_role),
            self.nearest_opponent_distance, self.nearest_opponent_angle,
            self.pressure_level,
            self.space_ahead, self.distance_to_touchline,
            self.pace, self.shooting, self.passing, self.dribbling,
            self.defending, self.physicality, self.stamina_obs,
            self.awareness, self.composure, float(self.role_obs), self.health,
            float(self.score_diff) / 5.0, self.match_time_ratio,
            float(self.half) / 2.0, float(self.phase_id) / 7.0,
            float(self.possession_phase),
            *[float(x) for x in self.history_action_types],
            *[float(x) for x in self.history_success_flags],
            self.pressing_level, self.defensive_line, self.attacking_width,
            float(self.passing_style) / 2.0, float(self.build_up_style) / 2.0,
            self.tempo,
        ]


class Policy(ABC):
    """Abstract policy for player decision-making.

    This is the primary extension point. The engine calls Policy.decide()
    during Phase 2 — it doesn't know or care whether the policy is rule-based,
    neural, or something else entirely.
    """

    @abstractmethod
    def decide(self, obs: Observation) -> ActionOutput:
        """Given an observation, return an action.

        Called once per player per tick during Phase 2.
        Must return within the engine's time budget (currently 5ms for rule-based).
        """
        ...

    @abstractmethod
    def name(self) -> str:
        """Human-readable identifier for logging/debugging."""
        ...
