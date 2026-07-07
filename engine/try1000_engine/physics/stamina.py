"""Stamina model for player fatigue."""

from try1000_engine.config import (
    STAMINA_MAX, STAMINA_MIN,
    STAMINA_BASE_DECAY, STAMINA_JOG_DECAY, STAMINA_SPRINT_DECAY,
    STAMINA_STAND_RECOVERY, STAMINA_JOG_RECOVERY,
)


class Stamina:
    """Tracks a player's stamina level across ticks.

    Stamina decays when running and recovers when walking/standing.
    Cannot drop below STAMINA_MIN (30%). Affects movement speed.
    """

    def __init__(self, value: float = STAMINA_MAX):
        self.value = float(value)

    def update(self, current_speed: float, dt: float = 1.0):
        """Update stamina based on current movement speed.

        Args:
            current_speed: Player's current speed in m/s.
            dt: Time delta in seconds.
        """
        if current_speed < 2.0:
            # Standing or walking — recover
            self.value += STAMINA_STAND_RECOVERY * dt
        elif current_speed < 5.0:
            # Jogging — slow decay with slight recovery
            self.value -= STAMINA_JOG_DECAY * dt
            self.value += STAMINA_JOG_RECOVERY * dt
        else:
            # Sprinting — fastest decay
            self.value -= STAMINA_SPRINT_DECAY * dt

        self.value = max(STAMINA_MIN, min(STAMINA_MAX, self.value))

    @property
    def is_fatigued(self) -> bool:
        """Player is noticeably tired."""
        return self.value < 50.0

    @property
    def is_exhausted(self) -> bool:
        """Player is extremely tired — speed is significantly reduced."""
        return self.value < 35.0

    @property
    def speed_multiplier(self) -> float:
        """How much stamina affects movement speed."""
        if self.value > 70:
            return 1.0
        if self.value > 50:
            return 0.85
        return 0.70

    @property
    def decision_penalty(self) -> float:
        """Penalty to decision quality when tired (0 = no penalty, 1 = max penalty)."""
        if self.value > 70: return 0.0
        if self.value > 50: return 0.1
        if self.value > 35: return 0.25
        return 0.40

    def reset(self):
        self.value = STAMINA_MAX
