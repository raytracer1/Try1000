"""Pass action resolution."""

import math
import random
from try1000_engine.actions.base import Action, ActionOutput
from try1000_engine.physics.ball import Ball
from try1000_engine.physics.player import Player


class PassAction(Action):
    """Resolves a pass: accuracy model, ball launch, interception chance."""

    def resolve(self, actor: Player, ball: Ball, players: list[Player],
                rng: random.Random, output: ActionOutput) -> dict:
        power = self._clamp_power(output.power)
        target_mx, target_my = self._normalized_to_meters(output.target_x, output.target_y)
        speed = self._power_to_speed(power)

        # Distance to target
        dist = math.sqrt((target_mx - ball.x) ** 2 + (target_my - ball.y) ** 2)

        # Success probability
        success_prob = self._pass_success(actor, dist)
        is_success = rng.random() < success_prob

        if is_success:
            # Ball flies toward target — speed proportional to distance
            # Ball should reach target in ~2 seconds (accounting for friction)
            pass_speed = dist / 1.5  # m/s, arrives in ~1.5s at target distance
            pass_speed = max(5.0, min(25.0, pass_speed))  # clamp
            dx = target_mx - ball.x
            dy = target_my - ball.y
            if dist > 0.01:
                ball.apply_kick(
                    (dx / dist) * pass_speed,
                    (dy / dist) * pass_speed,
                    team=actor.team,
                    player_id=actor.player_id,
                )
            else:
                ball.apply_kick(0.0, 0.0, team=actor.team, player_id=actor.player_id)

            return {
                "type": "pass",
                "actor": actor.player_id,
                "team": actor.team,
                "target_x": output.target_x,
                "target_y": output.target_y,
                "success": True,
                "power": power,
                "distance": round(dist, 1),
            }
        else:
            # Failed pass — ball goes somewhat off target (scatter)
            scatter_angle = rng.uniform(-45, 45)
            rad = math.atan2(target_my - ball.y, target_mx - ball.x) + math.radians(scatter_angle)
            reduced_speed = speed * rng.uniform(0.3, 0.7)
            ball.apply_kick(
                math.cos(rad) * reduced_speed,
                math.sin(rad) * reduced_speed,
                team=actor.team,
                player_id=actor.player_id,
            )

            return {
                "type": "pass",
                "actor": actor.player_id,
                "team": actor.team,
                "target_x": output.target_x,
                "target_y": output.target_y,
                "success": False,
                "power": power,
                "distance": round(dist, 1),
            }

    def _pass_success(self, actor: Player, distance: float) -> float:
        """Calculate pass success probability.

        Factors:
        - Passer's passing attribute (weight 40%)
        - Distance (weight 25%, inverted)
        - Composure under pressure (weight 20%)
        - Target direction precision (weight 15%)
        """
        # Passing skill: 50 → 0.70, 90 → 0.90
        skill_factor = 0.50 + (actor.passing / 100.0) * 0.50

        # Distance: 5m → 0.95, 30m → 0.65, 50m → 0.40
        dist_factor = max(0.3, 1.0 - (distance / 60.0))

        # Composure: 50 → 0.70, 90 → 0.95
        composure_factor = 0.50 + (actor.composure / 100.0) * 0.50

        # Weighted sum
        prob = (skill_factor * 0.40
                + dist_factor * 0.25
                + composure_factor * 0.20
                + 0.85 * 0.15)  # base precision

        return min(0.98, max(0.10, prob))
