"""Interception action — automatic when ball passes near a defender."""

import math
import random
from try1000_engine.actions.base import Action
from try1000_engine.physics.ball import Ball
from try1000_engine.physics.player import Player


class InterceptAction:
    """Interception is automatic — triggered by engine when ball passes near a player.

    Not called by decide(). Instead, the engine checks in Phase 5/7 whether
    the ball's trajectory crosses a defending player's interception radius.
    """

    def try_intercept(self, player: Player, ball: Ball,
                      players: list[Player], rng: random.Random,
                      interception_radius: float = 5.0) -> dict | None:
        """Check if player can intercept the ball.

        Args:
            player: The potential intercepting player.
            ball: Current ball state.
            players: All players.
            rng: Seeded RNG.
            interception_radius: Max interception range in meters (varies by tactics).

        Returns:
            Event dict if intercepted, None otherwise.
        """
        # Only defend against opposite team's passes
        if ball.last_touch_team == player.team:
            return None

        # Don't intercept shots (too fast)
        ball_speed = math.sqrt(ball.vx ** 2 + ball.vy ** 2)
        if ball_speed > 28.0:
            return None

        # Distance from player to ball's current position
        dist_to_ball = player.distance_to(ball.x, ball.y)

        # Awareness extends effective radius
        effective_radius = interception_radius * (player.awareness / 70.0)

        if dist_to_ball > effective_radius:
            return None

        # Interception chance based on positioning and awareness
        intercept_chance = 0.15 + (player.awareness / 100.0) * 0.40 + (player.defending / 100.0) * 0.20

        # Closer player = higher chance
        proximity_bonus = max(0.0, (effective_radius - dist_to_ball) / effective_radius) * 0.25
        intercept_chance += proximity_bonus

        if rng.random() < intercept_chance:
            # Intercepted! Player gains possession
            player.has_ball = True
            ball.x = player.x
            ball.y = player.y
            ball.vx = 0
            ball.vy = 0
            ball.in_air = False
            ball.last_touch_team = player.team
            ball.last_touch_player = player.player_id

            # Clear possession from other players
            for p in players:
                if p.player_id != player.player_id:
                    p.has_ball = False

            return {
                "type": "intercept",
                "actor": player.player_id,
                "ball_x": round(ball.x, 2),
                "ball_y": round(ball.y, 2),
            }

        return None
