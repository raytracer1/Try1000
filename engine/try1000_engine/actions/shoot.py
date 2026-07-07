"""Shoot action resolution with xG model."""

import math
import random
from try1000_engine.actions.base import Action, ActionOutput
from try1000_engine.physics.ball import Ball
from try1000_engine.physics.player import Player
from try1000_engine.config import PITCH_LENGTH, GOAL_WIDTH


class ShootAction(Action):
    """Resolves a shot: xG calculation, shot outcome (goal/save/miss/block)."""

    def resolve(self, actor: Player, ball: Ball, players: list[Player],
                rng: random.Random, output: ActionOutput) -> dict:
        power = self._clamp_power(output.power)
        speed = self._power_to_speed(power)

        # Angle toward opponent goal
        angle_rad = math.radians(output.angle)
        ball.apply_kick(
            math.cos(angle_rad) * speed,
            math.sin(angle_rad) * speed,
            vz=power * 0.3,  # lift based on power
            team=actor.team,
            player_id=actor.player_id,
        )

        # Calculate xG
        distance_to_goal = self._distance_to_opponent_goal(actor)
        angle = self._angle_from_goal(actor)
        xg = self._calculate_xg(distance_to_goal, angle, actor)

        # Determine outcome
        roll = rng.random()

        if roll < xg:
            outcome = "goal"
        elif roll < xg + 0.15:
            outcome = "save"
        elif roll < xg + 0.30:
            outcome = "miss"
        else:
            outcome = "block"

        return {
            "type": "shoot",
            "actor": actor.player_id,
            "team": actor.team,
            "xg": round(xg, 4),
            "outcome": outcome,
            "distance": round(distance_to_goal, 1),
            "angle": round(output.angle, 1),
            "power": power,
        }

    def _calculate_xg(self, distance: float, angle: float,
                      actor: Player) -> float:
        """Expected goals based on distance, angle, player skill, pressure.

        Base xG by distance (empirically calibrated):
            0–6m: 0.40    6–12m: 0.18
            12–18m: 0.08  18–25m: 0.03   25m+: 0.01
        """
        if distance < 6:
            base_xg = 0.40
        elif distance < 12:
            base_xg = 0.18
        elif distance < 18:
            base_xg = 0.08
        elif distance < 25:
            base_xg = 0.03
        else:
            base_xg = 0.01

        # Angle modifier: 0° (straight on) → 1.0, 45° → 0.7, 80° → 0.3
        angle_mod = max(0.2, 1.0 - (abs(angle) / 90.0) * 0.9)

        # Shooter skill: 70 → 1.0, 90 → 1.3, 50 → 0.6
        skill_mod = 0.4 + (actor.shooting / 100.0) * 1.0

        # Composure under pressure
        composure_mod = 0.6 + (actor.composure / 100.0) * 0.6

        xg = base_xg * angle_mod * skill_mod * composure_mod
        return min(0.95, max(0.001, xg))

    def _distance_to_opponent_goal(self, actor: Player) -> float:
        """Distance from actor to opponent goal line center."""
        half_length = PITCH_LENGTH / 2
        if actor.team == "home":
            goal_x = half_length  # attacking to the right
        else:
            goal_x = -half_length  # attacking to the left
        return math.sqrt((actor.x - goal_x) ** 2 + actor.y ** 2)

    def _angle_from_goal(self, actor: Player) -> float:
        """Angle from actor to the center of opponent's goal, in degrees.
        0 = straight on, 90 = from the sideline.
        """
        half_length = PITCH_LENGTH / 2
        if actor.team == "home":
            goal_x = half_length
        else:
            goal_x = -half_length

        dx = abs(goal_x - actor.x)
        dy = abs(actor.y)  # distance from center line (y=0)
        if dx < 0.01:
            return 0.0
        return math.degrees(math.atan2(dy, dx))
