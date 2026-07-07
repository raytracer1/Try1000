"""Evaluator — scores each possible action for a player.

Combines role weights, tactical modifiers, situational context,
and success probability to produce a utility score per action.
"""

import math
from try1000_engine.actions.base import ActionType
from try1000_engine.ai.policy import Observation
from try1000_engine.ai.roles import get_weights, get_role_index


class Evaluator:
    """Scores each action type for a player given the current observation.

    final_score = role_weight × tactic_mod × situation_mod × success_prob
    """

    def evaluate(self, obs: Observation, tactic: dict) -> dict[int, float]:
        """Return {action_type_int: score} for all available actions."""
        role_idx = obs.role_obs
        weights = get_weights(self._role_name(role_idx))

        scores = {}
        for action_type in ActionType:
            at = int(action_type)
            if at >= len(weights):
                continue

            role_w = weights[at]
            tactic_m = self._tactic_modifier(action_type, obs, tactic)
            situ_m = self._situation_modifier(action_type, obs)
            succ_p = self._success_probability(action_type, obs)

            scores[at] = role_w * tactic_m * situ_m * succ_p

        return scores

    def pick_best(self, scores: dict[int, float], on_cooldown: bool) -> int:
        """Pick the action with the highest score, respecting cooldown."""
        if on_cooldown:
            # Filter out cooldown-triggering actions
            allowed = {at: s for at, s in scores.items()
                       if not ActionType(at).triggers_cooldown}
            if not allowed:
                return int(ActionType.HOLD)
            return max(allowed, key=allowed.get)

        return max(scores, key=scores.get)

    # ─── Tactical modifiers ───

    def _tactic_modifier(self, action_type: ActionType, obs: Observation,
                         tactic: dict) -> float:
        """How the team's tactical parameters modify this action's weight."""
        mod = 1.0

        pressing = obs.pressing_level * 10  # back to 1-10
        defensive_line = obs.defensive_line * 10
        attacking_width = obs.attacking_width * 10
        tempo = obs.tempo * 10

        if action_type == ActionType.TACKLE:
            mod *= 0.45 + pressing / 10 * 1.1      # 0.55→1.5
        elif action_type == ActionType.INTERCEPT:
            mod *= 0.50 + pressing / 10 * 1.0      # 0.60→1.5
        elif action_type == ActionType.MOVE:
            mod *= 0.70 + tempo / 10 * 0.6         # 0.76→1.3
        elif action_type == ActionType.CROSS:
            mod *= 0.50 + attacking_width / 10 * 1.0  # 0.60→1.5
        elif action_type == ActionType.DRIBBLE:
            mod *= 0.55 + tempo / 10 * 0.9         # 0.64→1.45
        elif action_type == ActionType.SHOOT:
            mod *= 0.80 + tempo / 10 * 0.4         # 0.84→1.2
        elif action_type == ActionType.PASS:
            passing_style = obs.passing_style
            if passing_style == 0:  # short
                mod *= 1.3  # prefer short passes
            elif passing_style == 2:  # direct
                mod *= 0.7  # de-prioritize short passes, favor long
        elif action_type == ActionType.HOLD:
            buildup = obs.build_up_style
            if buildup == 0:  # slow
                mod *= 1.5  # patient, hold position more
            elif buildup == 2:  # fast
                mod *= 0.4  # don't hold, go!

        return max(0.1, mod)

    # ─── Situational modifiers ───

    def _situation_modifier(self, action_type: ActionType, obs: Observation) -> float:
        """How the current match situation modifies this action's weight."""
        mod = 1.0

        # Near opponent goal → shoot more
        if action_type == ActionType.SHOOT:
            if obs.distance_to_opponent_goal < 0.25:  # ~<20m
                mod *= 3.0  # heavy boost — in shooting range
            elif obs.distance_to_opponent_goal < 0.35:  # ~<28m
                mod *= 1.8

        # Under heavy pressure → reduce hold, pass/dribble
        if obs.pressure_level > 0.6:
            if action_type == ActionType.HOLD:
                mod *= 0.3
            elif action_type == ActionType.PASS:
                mod *= 1.3
            elif action_type == ActionType.DRIBBLE:
                mod *= 1.2

        # Late game, losing → more risk
        if obs.match_time_ratio > 0.75 and obs.score_diff < 0:
            if action_type == ActionType.SHOOT:
                mod *= 1.5
            elif action_type == ActionType.TACKLE:
                mod *= 1.3

        # Late game, winning → conservative
        if obs.match_time_ratio > 0.75 and obs.score_diff > 0:
            if action_type == ActionType.HOLD:
                mod *= 1.8
            elif action_type == ActionType.PASS:
                mod *= 1.2  # keep the ball
            elif action_type == ActionType.TACKLE:
                mod *= 0.8  # avoid cards

        # Has ball → attacking actions relevant
        if obs.has_ball:
            if action_type in (ActionType.PASS, ActionType.SHOOT,
                               ActionType.CROSS, ActionType.DRIBBLE):
                mod *= 1.5
            if action_type == ActionType.HOLD:
                mod *= 0.3
            if action_type == ActionType.MOVE:
                mod *= 0.01  # can't Move without ball — use Dribble instead

        # Doesn't have ball → off-ball movement
        if not obs.has_ball:
            if action_type == ActionType.MOVE:
                mod *= 1.8
            if action_type == ActionType.TACKLE:
                mod *= 1.5

        # Cross only from wide areas in opponent's half
        if action_type == ActionType.CROSS:
            # Touchline proximity: distance_to_touchline is in [0, 0.5]
            # Cross from wide areas only (close to touchline)
            if obs.distance_to_touchline > 0.15:  # too central
                mod *= 0.1
            if obs.distance_to_opponent_goal > 0.4:  # too far from goal
                mod *= 0.2

        # Counter-attack (possession change in opponent half)
        if obs.possession_phase == 1 and obs.distance_to_opponent_goal < 0.4:
            if action_type == ActionType.MOVE:
                mod *= 1.6  # sprint forward
            if action_type == ActionType.DRIBBLE:
                mod *= 1.4

        return max(0.05, mod)

    # ─── Success probability ───

    def _success_probability(self, action_type: ActionType, obs: Observation) -> float:
        """Estimated probability of this action succeeding, based on player attributes
        and situation. Does NOT use RNG — this is the expectation, not the roll."""

        if action_type == ActionType.HOLD:
            return 1.0  # always succeeds

        elif action_type == ActionType.MOVE:
            return 1.0  # movement always succeeds (stamina is handled separately)

        elif action_type == ActionType.PASS:
            skill = obs.passing
            dist = obs.ball_distance  # rough pass distance from ball proximity
            composure = obs.composure
            prob = (skill * 0.40 + (1.0 - dist) * 0.25 + composure * 0.20 + 0.85 * 0.15)
            return max(0.10, min(0.98, prob))

        elif action_type == ActionType.SHOOT:
            # This is xG, not shot "success" (which includes saves/misses)
            dist = obs.distance_to_opponent_goal
            if dist < 0.075: xg = 0.40
            elif dist < 0.15: xg = 0.18
            elif dist < 0.22: xg = 0.08
            elif dist < 0.30: xg = 0.03
            else: xg = 0.01
            angle_mod = max(0.2, 1.0 - abs(obs.angle_to_opponent_goal) * 0.9)
            skill_mod = 0.4 + obs.shooting * 1.0
            comp_mod = 0.6 + obs.composure * 0.6
            return xg * angle_mod * skill_mod * comp_mod

        elif action_type == ActionType.CROSS:
            return 0.5 + obs.passing * 0.50  # cross accuracy ≈ passing

        elif action_type == ActionType.DRIBBLE:
            att = obs.dribbling * 0.6 + obs.pace * 0.4
            def_score = 0.7  # assume average defender
            return 0.35 + (att - def_score) * 0.65

        elif action_type == ActionType.TACKLE:
            def_score = obs.defending * 0.5 + obs.physicality * 0.3 + obs.pace * 0.2
            return max(0.05, min(0.85, 0.30 + (def_score - 0.6) * 0.70))

        elif action_type == ActionType.INTERCEPT:
            return 0.15 + obs.awareness * 0.40 + obs.defending * 0.20

        return 0.5

    def _role_name(self, role_idx: int) -> str:
        from try1000_engine.ai.roles import get_role_name
        return get_role_name(role_idx)
