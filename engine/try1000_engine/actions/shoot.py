"""Shoot action resolver — AgentPitch formula.

Port of AgentPitch's ARE Phase 5 (lines 1045-1069).
Shoot speed: power * 0.175 units/tick, skill-based angular spread.
"""

from __future__ import annotations
import math, random
from try1000_engine.actions.base import Action, ActionOutput
from try1000_engine.config import COOLDOWN_DURATION_TICKS, meters_to_field


class ShootAction(Action):
    BALL_SPEED_PER_POWER = 0.175
    SHOT_MAX_ANGLE = 0.30
    cooldown_ticks = COOLDOWN_DURATION_TICKS

    def resolve(self, player, ball, all_players, rng, output):
        if not player.has_ball:
            return {"success": False, "reason": "not_carrier"}

        power = max(1.0, min(20.0, output.power))

        shooter_skill = (player.shooting or 70) / 5.0
        shot_eff_skill = (2.0 * shooter_skill + (player.composure or 70) / 5.0) / 3.0
        shot_spread = max(0.0, 1.0 - shot_eff_skill / 20.0) ** 0.7

        pfx, pfy = meters_to_field(player.x, player.y)
        opp_goal_x = 100.0 if player.team == "home" else 0.0
        goal_center_y = 30.0

        base_angle = math.atan2(goal_center_y - pfy, opp_goal_x - pfx)
        strategy_intent = math.radians(output.angle)
        angular_spread = shot_spread * self.SHOT_MAX_ANGLE
        skill_deviation = (rng.random() - 0.5) * 2.0 * angular_spread
        final_angle = base_angle + strategy_intent + skill_deviation

        ball_speed = power * self.BALL_SPEED_PER_POWER
        ball.vx = math.cos(final_angle) * ball_speed
        ball.vy = math.sin(final_angle) * ball_speed

        ball.carrier_id = None
        player.has_ball = False
        ball.last_touch_team = player.team
        player.trigger_cooldown(self.cooldown_ticks)

        dist = math.sqrt((opp_goal_x - pfx)**2 + (goal_center_y - pfy)**2)
        xg = max(0.01, 1.0 / (1.0 + dist * 0.05))

        return {
            "success": True,
            "angle": output.angle, "power": power,
            "final_angle_rad": final_angle, "xg": round(xg, 4),
        }

    def _clamp_power(self, power: float) -> float:
        return max(1.0, min(20.0, power))
