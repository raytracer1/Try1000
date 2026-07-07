"""Tackle action resolution."""

import math
import random
from try1000_engine.actions.base import Action, ActionOutput
from try1000_engine.physics.ball import Ball
from try1000_engine.physics.player import Player
from try1000_engine.config import PLAYER_RADIUS


class TackleAction(Action):
    """Resolves a tackle attempt: win ball, foul, or miss."""

    def resolve(self, actor: Player, ball: Ball, players: list[Player],
                rng: random.Random, output: ActionOutput) -> dict:
        # Find target player
        target = self._find_player_by_id(players, output.target_player_id)
        if target is None:
            return {"type": "tackle", "actor": actor.player_id, "team": actor.team, "success": False, "reason": "no_target"}

        # Check distance — must be within tackle range
        dist = actor.distance_to(target.x, target.y)
        if dist > PLAYER_RADIUS * 4:
            return {"type": "tackle", "actor": actor.player_id, "team": actor.team, "success": False, "reason": "too_far"}

        success_prob = self._tackle_success(actor, target)
        foul_prob = self._foul_probability(actor, dist)

        roll = rng.random()
        if roll < foul_prob:
            # Foul — free kick for opponent
            return {
                "type": "tackle",
                "actor": actor.player_id,
                "team": actor.team,
                "target": target.player_id,
                "success": False,
                "foul": True,
            }
        elif roll < foul_prob + success_prob:
            # Clean tackle — win the ball
            target.has_ball = False
            actor.has_ball = True
            ball.last_touch_team = actor.team
            ball.last_touch_player = actor.player_id
            return {
                "type": "tackle",
                "actor": actor.player_id,
                "team": actor.team,
                "target": target.player_id,
                "success": True,
                "foul": False,
            }
        else:
            # Missed tackle
            return {
                "type": "tackle",
                "actor": actor.player_id,
                "team": actor.team,
                "target": target.player_id,
                "success": False,
                "foul": False,
            }

    def _tackle_success(self, defender: Player, attacker: Player) -> float:
        """Probability of a clean tackle."""
        def_score = (defender.defending / 100.0) * 0.5 + (defender.physicality / 100.0) * 0.3 + (defender.pace / 100.0) * 0.2
        att_score = (attacker.dribbling / 100.0) * 0.5 + (attacker.physicality / 100.0) * 0.25 + (attacker.composure / 100.0) * 0.25

        prob = 0.30 + (def_score - att_score) * 0.70
        return min(0.85, max(0.05, prob))

    def _foul_probability(self, defender: Player, distance: float) -> float:
        """Probability of committing a foul.

        Higher when: poor defending attribute, lunging (far distance), desperate.
        """
        base_foul = 0.08
        skill_penalty = (1.0 - defender.defending / 100.0) * 0.10
        distance_penalty = (distance / (PLAYER_RADIUS * 4)) * 0.07
        return base_foul + skill_penalty + distance_penalty

    def _find_player_by_id(self, players: list[Player], player_id: int | str) -> Player | None:
        for p in players:
            if str(p.player_id) == str(player_id):
                return p
        return None
