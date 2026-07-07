"""Move action — player moves without the ball."""

import math
import random
from try1000_engine.actions.base import Action, ActionOutput
from try1000_engine.physics.ball import Ball
from try1000_engine.physics.player import Player


class MoveAction(Action):
    """Resolves a Move: player moves toward a direction at a given speed.

    Movement is applied in Phase 4 of the tick pipeline.
    """

    def resolve(self, actor: Player, ball: Ball, players: list[Player],
                rng: random.Random, output: ActionOutput) -> dict | None:
        dx, dy = output.dx, output.dy
        mag = math.sqrt(dx ** 2 + dy ** 2)

        if mag < 0.01:
            # No movement — equivalent to standing
            actor.set_target(actor.x, actor.y, 0.0)
            return None

        # Normalize direction
        dx /= mag
        dy /= mag

        step_size = 3.0 * output.speed  # ~3m per tick at full speed (walk: ~1m, sprint: ~3m)
        target_x = actor.x + dx * step_size
        target_y = actor.y + dy * step_size

        actor.set_target(target_x, target_y, output.speed)
        actor.move_toward_target()

        # Move doesn't generate events unless it's significant
        return None
