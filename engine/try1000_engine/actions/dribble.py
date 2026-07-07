"""Dribble action resolution."""

import math
import random
from try1000_engine.actions.base import Action, ActionOutput
from try1000_engine.physics.ball import Ball
from try1000_engine.physics.player import Player
from try1000_engine.config import PLAYER_RADIUS


class DribbleAction(Action):
    """Resolves a dribble: player carries ball while moving."""

    def resolve(self, actor: Player, ball: Ball, players: list[Player],
                rng: random.Random, output: ActionOutput) -> dict:
        # Clamp direction to unit length
        dx, dy = output.dx, output.dy
        mag = math.sqrt(dx ** 2 + dy ** 2)
        if mag > 1.0:
            dx /= mag
            dy /= mag
        if mag < 0.01:
            dx, dy = 0.0, 0.0

        speed_frac = max(0.1, min(1.0, output.speed))

        # Check if there's a nearby opponent trying to tackle
        nearest_opp = self._nearest_opponent(actor, players)
        if nearest_opp:
            opp_dist = actor.distance_to(nearest_opp.x, nearest_opp.y)
            if opp_dist < PLAYER_RADIUS * 3:
                # Contested dribble
                success_prob = self._dribble_success_prob(actor, nearest_opp)
                if rng.random() > success_prob:
                    # Dribble failed — opponent wins ball
                    nearest_opp.has_ball = True
                    actor.has_ball = False
                    return {
                        "type": "dribble",
                        "actor": actor.player_id,
                        "team": actor.team,
                        "success": False,
                        "tackled_by": nearest_opp.player_id,
                    }

        # Successful dribble — move actor and ball together
        step_size = 2.0 * speed_frac  # ~2m per tick at full speed dribbling
        actor.set_target(actor.x + dx * step_size, actor.y + dy * step_size, speed_frac)
        actor.move_toward_target()

        # Ball follows
        if actor.has_ball:
            ball.x = actor.x
            ball.y = actor.y
            ball.last_touch_team = actor.team
            ball.last_touch_player = actor.player_id

        return {
            "type": "dribble",
            "actor": actor.player_id,
            "team": actor.team,
            "success": True,
        }

    def _dribble_success_prob(self, attacker: Player, defender: Player) -> float:
        """Probability of successfully dribbling past a defender."""
        att_score = (attacker.dribbling / 100.0) * 0.6 + (attacker.pace / 100.0) * 0.4
        def_score = (defender.defending / 100.0) * 0.6 + (defender.physicality / 100.0) * 0.4

        # Attacker advantage: attacker has initiative
        prob = 0.35 + (att_score - def_score) * 0.65
        return min(0.90, max(0.10, prob))

    def _nearest_opponent(self, actor: Player, players: list[Player]) -> Player | None:
        nearest = None
        min_dist = float("inf")
        for p in players:
            if p.team == actor.team or p.player_id == actor.player_id:
                continue
            dist = actor.distance_to(p.x, p.y)
            if dist < min_dist:
                min_dist = dist
                nearest = p
        return nearest
