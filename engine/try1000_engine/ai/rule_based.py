"""RuleBasedPolicy — Level 1 decision maker.

Perception → Evaluation → Max-Utility → Action.
No learning. No training. Pure heuristic weights.
"""

import math

from try1000_engine.ai.policy import Policy, Observation
from try1000_engine.ai.perception import Perception
from try1000_engine.ai.evaluator import Evaluator
from try1000_engine.actions.base import ActionOutput, ActionType
from try1000_engine.physics.player import Player
from try1000_engine.physics.ball import Ball


class RuleBasedPolicy(Policy):
    """Rule-based player decision policy.

    Each tick:
    1. Perception gathers what the player can see
    2. Evaluator scores each action
    3. Pick the action with the highest utility
    4. Convert to ActionOutput with appropriate parameters
    """

    def __init__(self, tactic: dict | None = None):
        self.tactic = tactic or {
            "pressing_level": 5,
            "defensive_line": 5,
            "attacking_width": 5,
            "passing_style": "mixed",
            "build_up_style": "balanced",
            "tempo": 5,
        }
        self.perception = Perception()
        self.evaluator = Evaluator()

    def decide(self, obs: Observation) -> ActionOutput:
        """Score all actions and pick the best one."""
        scores = self.evaluator.evaluate(obs, self.tactic)

        # For now, cooldown is handled upstream in the engine
        # (the engine filters actions before calling resolve)
        best_action = max(scores, key=scores.get)

        return self._action_from_choice(best_action, obs)

    def decide_with_context(
        self,
        player: Player,
        teammates: list[Player],
        opponents: list[Player],
        ball: Ball,
        home_score: int,
        away_score: int,
        tick: int,
        max_ticks: int,
        half: int,
        phase_id: int,
        history_actions: list[dict],
    ) -> tuple[ActionOutput, Observation]:
        """Full decision pipeline: build observation → evaluate → pick action."""

        obs = self.perception.build_observation(
            player=player,
            teammates=teammates,
            opponents=opponents,
            ball=ball,
            home_score=home_score,
            away_score=away_score,
            tick=tick,
            max_ticks=max_ticks,
            half=half,
            phase_id=phase_id,
            tactic_params=self.tactic,
            history_actions=history_actions,
        )

        action = self.decide(obs)
        return action, obs

    def name(self) -> str:
        return "RuleBased-v1"

    def _action_from_choice(self, action_type_int: int, obs: Observation) -> ActionOutput:
        """Convert a chosen action type index into a parameterized ActionOutput."""
        at = ActionType(action_type_int)

        if at == ActionType.HOLD:
            return ActionOutput.hold()

        elif at == ActionType.MOVE:
            # Key: move toward the ball when not in possession
            # Normalize ball position to get direction
            bx = obs.ball_x - 0.5  # center = 0
            by = obs.ball_y - 0.5

            # Direction toward ball (or space if ball is very close)
            if obs.ball_distance > 0.05:
                # Move toward ball
                dx = bx
                dy = by
            elif obs.space_ahead > 0.3:
                dx = 1.0 if obs.ball_possession_team >= 0 else -1.0
                dy = -obs.angle_to_opponent_goal * 0.5
            else:
                dx = 1.0 if obs.ball_possession_team >= 0 else -1.0
                dy = 0.0

            # Normalize direction
            mag = (dx**2 + dy**2) ** 0.5
            if mag > 0.01:
                dx /= mag
                dy /= mag

            # Speed: faster when ball is far or team has possession
            speed = 0.9 if obs.distance_to_opponent_goal < 0.3 and obs.ball_possession_team == 1 else 0.7
            return ActionOutput.move(dx, dy, speed)

        elif at == ActionType.PASS:
            # Pass toward nearest teammate position
            # Calculate teammate position from angle + distance
            tm_angle = obs.nearest_teammate_angle * math.pi  # back to radians
            tm_dist = obs.nearest_teammate_distance * 80.0    # back to meters
            # Convert to normalized ball-relative coordinates
            ball_x_norm = obs.ball_x
            ball_y_norm = obs.ball_y
            # Target: ~20% of the way from ball toward teammate (they'll move to meet it)
            target_x = ball_x_norm + math.cos(tm_angle) * min(tm_dist / 105.0, 0.3)
            target_y = ball_y_norm + math.sin(tm_angle) * min(tm_dist / 68.0, 0.3)
            target_x = max(0.05, min(0.95, target_x))
            target_y = max(0.05, min(0.95, target_y))
            power = 8.0 + obs.passing * 5.0
            return ActionOutput.pass_(target_x, target_y, power)

        elif at == ActionType.SHOOT:
            angle = obs.angle_to_opponent_goal * 45.0  # -45 to 45 degrees
            power = 14.0 + obs.shooting * 0.06 * 100  # 14–20
            return ActionOutput.shoot(angle, power)

        elif at == ActionType.CROSS:
            target_x = 0.85
            target_y = 0.5
            power = 12.0
            return ActionOutput.cross(target_x, target_y, power)

        elif at == ActionType.DRIBBLE:
            dx = 1.0
            dy = -obs.nearest_opponent_angle * 0.3  # away from nearest defender
            speed = 0.9
            return ActionOutput.dribble(dx, dy, speed)

        elif at == ActionType.TACKLE:
            # Target: nearest opponent (we pass 0 as placeholder, engine resolves)
            return ActionOutput.tackle(0)

        elif at == ActionType.INTERCEPT:
            # Interception is automatic — not chosen by decide()
            return ActionOutput.hold()

        return ActionOutput.hold()
