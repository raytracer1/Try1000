"""Pass action resolver — AgentPitch formula.

Port of AgentPitch's ARE Phase 5 (lines 991-1064).
Pass speed: power * 0.175 units/tick, skill-based deviation.
"""

from __future__ import annotations
import math, random
from try1000_engine.actions.base import Action, ActionOutput
from try1000_engine.config import COOLDOWN_DURATION_TICKS, field_to_meters


class PassAction(Action):
    BALL_SPEED_PER_POWER = 0.175  # AgentPitch: power=20 → 3.5 units/tick
    cooldown_ticks = COOLDOWN_DURATION_TICKS

    def _pass_max_deviation(self) -> float:
        return 8.0  # AgentPitch: pass_max_deviation

    def resolve(self, player, ball, all_players, rng, output):
        if not player.has_ball:
            return {"success": False, "reason": "not_carrier"}

        # Convert target from field coords → meters
        target_mx, target_my = self._normalized_to_meters(output.target_x, output.target_y)
        power = max(1.0, min(20.0, output.power))

        # AgentPitch: skill-based deviation
        passer_skill = (player.passing or 70) / 5.0  # → 1-20 scale
        pass_eff_skill = (2.0 * passer_skill + (player.composure or 70) / 5.0) / 3.0
        pass_spread = max(0.0, 1.0 - pass_eff_skill / 20.0) ** 0.7
        deviation_m = pass_spread * self._pass_max_deviation() * rng.random()
        dev_angle = rng.uniform(0, 2 * math.pi)
        landing_mx = target_mx + math.cos(dev_angle) * deviation_m
        landing_my = target_my + math.sin(dev_angle) * deviation_m

        # Ball velocity
        px, py = player.x, player.y
        dx = landing_mx - px
        dy = landing_my - py
        dist = math.sqrt(dx*dx + dy*dy)
        if dist < 1e-6:
            dx = 50.0 if player.team == "home" else -50.0
            dy = 0.0
            dist = abs(dx)

        ball_speed = power * self.BALL_SPEED_PER_POWER  # units/tick
        unit_x, unit_y = dx/dist, dy/dist
        ball.vx = unit_x * ball_speed
        ball.vy = unit_y * ball_speed

        # Store landing zone for BPS tracking
        ball._landing_zone = (landing_mx, landing_my)

        ball.carrier_id = None
        player.has_ball = False
        ball.last_touch_team = player.team
        player.trigger_cooldown(self.cooldown_ticks)

        return {
            "success": True,
            "target_x": output.target_x, "target_y": output.target_y,
            "power": power,
            "landing_mx": landing_mx, "landing_my": landing_my,
        }

    def _clamp_power(self, power: float) -> float:
        return max(1.0, min(20.0, power))
