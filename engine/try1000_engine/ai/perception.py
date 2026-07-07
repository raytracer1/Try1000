"""Perception system — what each player can "see" in a tick snapshot.

Takes the raw match snapshot and computes a rich Observation for one player.
"""

import math
from try1000_engine.config import (
    PITCH_LENGTH, PITCH_WIDTH, GOAL_WIDTH,
    PERCEPTION_TEAMMATE_RADIUS, PERCEPTION_OPPONENT_RADIUS,
    PRESSURE_RADIUS, meters_to_normalized,
)
from try1000_engine.physics.player import PlayerState, Player
from try1000_engine.physics.ball import BallState, Ball
from try1000_engine.ai.policy import Observation
from try1000_engine.ai.roles import get_role_index


class Perception:
    """Computes an Observation from a match snapshot for a single player."""

    def build_observation(
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
        tactic_params: dict,
        history_actions: list[dict],
    ) -> Observation:
        """Build a full Observation from raw match data."""

        obs = Observation()

        # ─── Ball features ───
        nx, ny = meters_to_normalized(ball.x, ball.y)
        obs.ball_x = nx
        obs.ball_y = ny
        dist_to_ball = player.distance_to(ball.x, ball.y)
        obs.ball_distance = min(1.0, dist_to_ball / 60.0)

        if ball.last_touch_team is None:
            obs.ball_possession_team = 0
        elif ball.last_touch_team == player.team:
            obs.ball_possession_team = 1
        else:
            obs.ball_possession_team = -1
        obs.has_ball = 1 if player.has_ball else 0

        # ─── Goal features ───
        half_length = PITCH_LENGTH / 2
        if player.team == "home":
            opp_goal_x, own_goal_x = half_length, -half_length
        else:
            opp_goal_x, own_goal_x = -half_length, half_length

        obs.distance_to_opponent_goal = min(1.0, math.sqrt((player.x - opp_goal_x) ** 2 + player.y ** 2) / 80.0)
        dx_opp = opp_goal_x - player.x
        if abs(dx_opp) > 0.01:
            obs.angle_to_opponent_goal = (math.atan2(player.y, dx_opp) / (math.pi / 2))
        obs.distance_to_own_goal = min(1.0, math.sqrt((player.x - own_goal_x) ** 2 + player.y ** 2) / 80.0)

        # ─── Nearest teammate ───
        nearest_tm = self._find_nearest(player, teammates)
        if nearest_tm:
            obs.nearest_teammate_distance = min(1.0, player.distance_to(nearest_tm.x, nearest_tm.y) / 40.0)
            obs.nearest_teammate_angle = self._relative_angle(player, nearest_tm.x, nearest_tm.y)
            obs.nearest_teammate_role = get_role_index(nearest_tm.role)
        else:
            obs.nearest_teammate_distance = 1.0

        # ─── Nearest opponent ───
        nearest_opp = self._find_nearest(player, opponents)
        if nearest_opp:
            obs.nearest_opponent_distance = min(1.0, player.distance_to(nearest_opp.x, nearest_opp.y) / 40.0)
            obs.nearest_opponent_angle = self._relative_angle(player, nearest_opp.x, nearest_opp.y)
            obs.pressure_level = self._calculate_pressure(player, opponents)
        else:
            obs.nearest_opponent_distance = 1.0

        # ─── Spatial ───
        obs.space_ahead = self._measure_space_ahead(player, teammates, opponents)
        obs.distance_to_touchline = abs(abs(player.y) - PITCH_WIDTH / 2) / (PITCH_WIDTH / 2)

        # ─── Self attributes ───
        obs.pace = player.pace / 100.0
        obs.shooting = player.shooting / 100.0
        obs.passing = player.passing / 100.0
        obs.dribbling = player.dribbling / 100.0
        obs.defending = player.defending / 100.0
        obs.physicality = player.physicality / 100.0
        obs.stamina_obs = player.stamina / 100.0
        obs.awareness = player.awareness / 100.0
        obs.composure = player.composure / 100.0
        obs.role_obs = get_role_index(player.role)
        obs.health = player.health

        # ─── Match context ───
        obs.score_diff = (home_score - away_score) if player.team == "home" else (away_score - home_score)
        obs.match_time_ratio = tick / max_ticks
        obs.half = half
        obs.phase_id = phase_id
        obs.possession_phase = obs.ball_possession_team  # same mapping

        # ─── History ───
        act_map = {"Hold": 0, "Move": 1, "Pass": 2, "Shoot": 3, "Cross": 4,
                   "Dribble": 5, "Tackle": 6, "Intercept": 7}
        for i, evt in enumerate(history_actions[-5:]):
            obs.history_action_types[i] = act_map.get(evt.get("type", "Hold"), 0)
            obs.history_success_flags[i] = 1 if evt.get("success", False) else 0

        # ─── Tactical context ───
        obs.pressing_level = tactic_params.get("pressing_level", 5) / 10.0
        obs.defensive_line = tactic_params.get("defensive_line", 5) / 10.0
        obs.attacking_width = tactic_params.get("attacking_width", 5) / 10.0
        style_map = {"short": 0, "mixed": 1, "direct": 2}
        obs.passing_style = style_map.get(tactic_params.get("passing_style", "mixed"), 1)
        buildup_map = {"slow": 0, "balanced": 1, "fast": 2}
        obs.build_up_style = buildup_map.get(tactic_params.get("build_up_style", "balanced"), 1)
        obs.tempo = tactic_params.get("tempo", 5) / 10.0

        return obs

    def _find_nearest(self, player: Player, candidates: list[Player]) -> Player | None:
        nearest = None
        min_dist = float("inf")
        for p in candidates:
            if p.player_id == player.player_id:
                continue
            d = player.distance_to(p.x, p.y)
            if d < min_dist:
                min_dist = d
                nearest = p
        return nearest

    def _relative_angle(self, player: Player, tx: float, ty: float) -> float:
        """Angle from player's facing direction to target, normalized [-1, 1]."""
        angle_to_target = math.atan2(ty - player.y, tx - player.x)
        rel = angle_to_target - player.facing_angle
        # Normalize to [-pi, pi]
        while rel > math.pi: rel -= 2 * math.pi
        while rel < -math.pi: rel += 2 * math.pi
        return rel / math.pi

    def _calculate_pressure(self, player: Player, opponents: list[Player]) -> float:
        """How many opponents are within pressure radius, normalized [0, 1]."""
        count = 0
        for opp in opponents:
            if player.distance_to(opp.x, opp.y) < PRESSURE_RADIUS:
                count += 1
        return min(1.0, count / 5.0)

    def _measure_space_ahead(self, player: Player,
                             teammates: list[Player],
                             opponents: list[Player]) -> float:
        """Measure open space in the direction the player is facing. [0, 1]."""
        # Look ahead up to 20m in facing direction
        look_distance = 20.0
        fx = player.x + math.cos(player.facing_angle) * look_distance
        fy = player.y + math.sin(player.facing_angle) * look_distance

        # Count players (both teams) in the cone ahead
        occupied = 0
        for p in teammates + opponents:
            if p.player_id == player.player_id:
                continue
            # Check if p is within the forward cone
            d = player.distance_to(p.x, p.y)
            if d > look_distance:
                continue
            # Angle from facing direction
            angle_to_p = math.atan2(p.y - player.y, p.x - player.x)
            rel = angle_to_p - player.facing_angle
            while rel > math.pi: rel -= 2 * math.pi
            while rel < -math.pi: rel += 2 * math.pi
            if abs(rel) < math.radians(45):
                occupied += 1

        return max(0.0, 1.0 - occupied / 5.0)
