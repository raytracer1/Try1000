"""Cross action resolution."""

import math
import random
from try1000_engine.actions.base import Action, ActionOutput
from try1000_engine.physics.ball import Ball
from try1000_engine.physics.player import Player
from try1000_engine.config import PLAYER_RADIUS


class CrossAction(Action):
    """Resolves a cross: ball lofted into the box, receiver contests."""

    def resolve(self, actor: Player, ball: Ball, players: list[Player],
                rng: random.Random, output: ActionOutput) -> dict:
        power = self._clamp_power(output.power)
        speed = self._power_to_speed(power) * 0.7  # crosses are floated, not driven
        target_mx, target_my = self._normalized_to_meters(output.target_x, output.target_y)

        dx = target_mx - ball.x
        dy = target_my - ball.y
        dist = math.sqrt(dx ** 2 + dy ** 2)

        # Cross quality based on player skill
        cross_quality = 0.5 + (actor.passing / 100.0) * 0.5

        if rng.random() < cross_quality:
            # Good cross — ball goes to target area
            if dist > 0.01:
                ball.apply_kick(
                    (dx / dist) * speed,
                    (dy / dist) * speed,
                    vz=8.0,  # floated cross
                    team=actor.team,
                    player_id=actor.player_id,
                )
            return {
                "type": "cross",
                "actor": actor.player_id,
                "team": actor.team,
                "target_x": output.target_x,
                "target_y": output.target_y,
                "quality": "good",
                "power": power,
            }
        else:
            # Poor cross — scatters
            scatter = rng.uniform(-30, 30)
            rad = math.atan2(dy, dx) + math.radians(scatter)
            ball.apply_kick(
                math.cos(rad) * speed * 0.5,
                math.sin(rad) * speed * 0.5,
                vz=5.0,
                team=actor.team,
                player_id=actor.player_id,
            )
            return {
                "type": "cross",
                "actor": actor.player_id,
                "team": actor.team,
                "target_x": output.target_x,
                "target_y": output.target_y,
                "quality": "poor",
                "power": power,
            }
