"""RuleBasedPolicy — hand-written baseline strategy.

Ported from AgentPitch's baseline.py. Used as fallback when no LLM is configured.
Implements role-aware behavior: GK, DEF, MID, FWD with carrier/off-ball logic.
"""

from __future__ import annotations
import math
from typing import Any
from try1000_engine.actions.base import ActionOutput, ActionType
from try1000_engine.ai.policy import Policy, Observation
from try1000_engine.config import meters_to_field, PITCH_LENGTH, PITCH_WIDTH


def _move(dx: float, dy: float, speed: float = 1.0) -> ActionOutput:
    return ActionOutput.move(dx, dy, speed)


def _hold() -> ActionOutput:
    return ActionOutput.hold()


def _pass(target_x: float, target_y: float, power: float = 12) -> ActionOutput:
    return ActionOutput.pass_(target_x, target_y, power)


def _shoot(angle: float = 0.0, power: float = 15) -> ActionOutput:
    return ActionOutput.shoot(angle, power)


def _tackle(target_id: int = 0) -> ActionOutput:
    return ActionOutput.tackle(target_id)


def _dribble(dx: float, dy: float, speed: float = 0.7) -> ActionOutput:
    return ActionOutput.dribble(dx, dy, speed)


def _dist(a, b):
    dx = a[0] - b[0]; dy = a[1] - b[1]
    return (dx*dx + dy*dy) ** 0.5


def _normalize(dx, dy):
    m = (dx*dx + dy*dy) ** 0.5
    if m < 1e-6: return (1.0, 0.0)
    return (dx/m, dy/m)


class RuleBasedPolicy(Policy):
    """Hand-written baseline strategy matching AgentPitch's baseline.py behavior."""

    def __init__(self, tactic: dict | None = None, team: str = "Home"):
        self.tactic = tactic or {}
        self.team = team

    def name(self) -> str:
        return "RuleBased-v1"

    def decide(self, obs: Observation) -> ActionOutput:
        return _hold()

    def decide_with_context(
        self,
        player: Any, teammates: list, opponents: list, ball: Any,
        home_score: int, away_score: int,
        tick: int, max_ticks: int, half: int, phase_id: int,
        history_actions: list[dict] | None = None,
    ) -> tuple[ActionOutput, Any]:
        """Full-context decision using AgentPitch baseline logic."""
        my_team = player.team
        my_pos_n = meters_to_field(player.x, player.y)
        ball_pos_n = meters_to_field(ball.x, ball.y)
        has_ball = player.has_ball
        on_cooldown = player.is_on_cooldown

        # Goal positions (AgentPitch field coords: 0-100 x, 0-60 y)
        my_goal_x = 0.0 if my_team == "home" else 100.0
        opp_goal_x = 100.0 if my_team == "home" else 0.0
        goal_y = 30.0  # center of goal
        half_x = 50.0

        carrier_id = getattr(ball, 'carrier_id', None)
        # Use last_touch_team as fallback when ball is in flight (pass/shot)
        last_touch = getattr(ball, 'last_touch_team', None)
        we_have_ball = (
            carrier_id is not None and any(p.player_id == carrier_id and p.team == my_team for p in teammates + [player])
        ) or (carrier_id is None and last_touch == my_team)
        they_have_ball = (
            carrier_id is not None and any(p.player_id == carrier_id and p.team != my_team for p in opponents)
        ) or (carrier_id is None and last_touch is not None and last_touch != my_team)

        def in_own_half(px):
            return (px <= half_x) if my_team == "home" else (px >= half_x)

        def closest_opponent_to(pos):
            best_id, best_d = None, 1e9
            for p in opponents:
                op = meters_to_field(p.x, p.y)
                d = _dist(pos, op)
                if d < best_d:
                    best_d = d; best_id = p.player_id
            return best_id, best_d

        def move_toward_normalized(tx, ty, speed=1.0):
            dx, dy = _normalize(tx - my_pos_n[0], ty - my_pos_n[1])
            return _move(dx, dy, speed)

        def offside_line():
            """Return the x-coordinate (engine meters) of the second-last defender.
            Forwards must stay behind this line to remain onside."""
            if len(opponents) < 2:
                return None
            if my_team == "home":
                # Home attacks right (+x): second-last = 2nd smallest x
                sorted_opp = sorted(opponents, key=lambda p: p.x)
            else:
                # Away attacks left (-x): second-last = 2nd largest x (2nd most negative)
                sorted_opp = sorted(opponents, key=lambda p: -p.x)
            return sorted_opp[1].x if len(sorted_opp) > 1 else None

        # ================================================================
        # GK
        # ================================================================
        if player.role == "GK":
            if has_ball and not on_cooldown:
                # Punt to nearest forward teammate
                best_tm, best_d = None, 1e9
                for p in teammates:
                    if p.role not in ("MID", "ST", "CF", "LW", "RW", "FWD"):
                        continue
                    tp = meters_to_field(p.x, p.y)
                    d = _dist(my_pos_n, tp)
                    if d < best_d:
                        best_d = d; best_tm = tp
                if best_tm:
                    return _pass(best_tm[0], best_tm[1], 18), self.tactic
                return _pass(0.5, goal_y, 18), self.tactic

            # Defensive positioning: hover 2u in front of own goal, mirror ball y
            keep_x = my_goal_x + 2.0 if my_team == "home" else my_goal_x - 2.0
            keep_y = max(26.34 + 1.0, min(33.66 - 1.0, ball_pos_n[1]))
            if _dist(my_pos_n, (keep_x, keep_y)) < 0.3:
                return _hold(), self.tactic
            return move_toward_normalized(keep_x, keep_y), self.tactic

        # ================================================================
        # Defensive tackle
        # ================================================================
        if they_have_ball and not on_cooldown:
            for p in opponents:
                if p.player_id == carrier_id:
                    op = meters_to_field(p.x, p.y)
                    if _dist(my_pos_n, op) < 1.9:  # AgentPitch TACKLE_RANGE
                        return _tackle(int(carrier_id.split("_")[-1])), self.tactic
                    break

        # ================================================================
        # Carrier
        # ================================================================
        if has_ball:
            d_to_goal = _dist(my_pos_n, (opp_goal_x, goal_y))
            in_opp_half = not in_own_half(my_pos_n[0])
            _, closest_opp_d = closest_opponent_to(my_pos_n)

            # Shot: within 12u of goal, in goal window
            in_y_window = (26.34 - 5) <= my_pos_n[1] <= (33.66 + 5)
            if d_to_goal < 12.0 and in_y_window and not on_cooldown:
                return _shoot(0.0, 20), self.tactic

            # Speculative long shot: 18-25u, unmarked (closest opp > 8u)
            if (in_opp_half and 18.0 <= d_to_goal < 25.0
                    and closest_opp_d > 8.0 and not on_cooldown):
                return _shoot(0.0, 18), self.tactic

            # Back-pass to GK: DEF in own box under pressure
            if player.role in ("CB", "LB", "RB") and not in_opp_half and closest_opp_d < 3.0:
                for p in teammates:
                    if p.role == "GK":
                        gp = meters_to_field(p.x, p.y)
                        return _pass(gp[0], gp[1], 14), self.tactic

            # Panic clearance: under pressure in own half
            if player.role in ("CB", "LB", "RB", "CDM", "CM") and not in_opp_half and closest_opp_d < 3.0 and not on_cooldown:
                return _pass(opp_goal_x, goal_y, 18), self.tactic

            # Pressure pass: opponent within 5u
            if closest_opp_d < 5.0 and not on_cooldown:
                best_tm, best_score = None, -1e9
                for p in teammates:
                    if p.role == "GK":
                        continue
                    tp = meters_to_field(p.x, p.y)
                    tm_to_goal = _dist(tp, (opp_goal_x, goal_y))
                    _, marked_d = closest_opponent_to(tp)
                    score = -tm_to_goal - (10.0 if marked_d < 3.0 else 0.0)
                    if score > best_score:
                        best_score = score; best_tm = tp
                if best_tm:
                    return _pass(best_tm[0], best_tm[1], 14), self.tactic

            # Patient build-up: unmarked, look for forward teammate
            if closest_opp_d > 6.0 and not on_cooldown:
                best_tm, best_prog = None, -1e9
                for p in teammates:
                    if p.role == "GK":
                        continue
                    tp = meters_to_field(p.x, p.y)
                    prog = tp[0] - my_pos_n[0] if my_team == "home" else my_pos_n[0] - tp[0]
                    if prog < 8.0:
                        continue
                    _, tm_marked = closest_opponent_to(tp)
                    if tm_marked < 3.0:
                        continue
                    if prog > best_prog:
                        best_prog = prog; best_tm = tp
                if best_tm:
                    return _pass(best_tm[0], best_tm[1], 12), self.tactic

            # Circulate: recycle to most isolated teammate
            if closest_opp_d > 6.0 and not on_cooldown:
                best_tm, best_clear = None, 4.0
                for p in teammates:
                    if p.role == "GK":
                        continue
                    _, tm_marked = closest_opponent_to(meters_to_field(p.x, p.y))
                    if tm_marked > best_clear:
                        best_clear = tm_marked; best_tm = meters_to_field(p.x, p.y)
                if best_tm:
                    return _pass(best_tm[0], best_tm[1], 10), self.tactic

            # Default: dribble toward opponent's goal
            dx, dy = _normalize(opp_goal_x - my_pos_n[0], goal_y - my_pos_n[1])
            return _dribble(dx, dy, 0.7), self.tactic

        # ================================================================
        # Off-ball: closest chases loose ball
        # ================================================================
        if carrier_id is None:
            closest_id = None
            closest_d = 1e9
            all_players = teammates + [player]
            for p in all_players:
                if p.role == "GK":
                    continue
                tp = meters_to_field(p.x, p.y)
                d = _dist(tp, ball_pos_n)
                if d < closest_d:
                    closest_d = d; closest_id = p.player_id
            if closest_id == player.player_id:
                return move_toward_normalized(ball_pos_n[0], ball_pos_n[1], 1.0), self.tactic

        # ================================================================
        # Role-aware off-ball positioning
        # ================================================================
        role = player.role
        anchor = meters_to_field(player.x, player.y)  # simplified anchor

        if role in ("CB", "LB", "RB"):
            if they_have_ball:
                # Man-mark the nearest opponent in own half
                best_id, best_d = None, 1e9
                for p in opponents:
                    if p.role == "GK":
                        continue
                    op = meters_to_field(p.x, p.y)
                    if not in_own_half(op[0]):
                        continue
                    d = _dist(anchor, op)
                    if d < best_d:
                        best_d = d; best_id = p.player_id
                if best_id:
                    for p in opponents:
                        if p.player_id == best_id:
                            op = meters_to_field(p.x, p.y)
                            ux, uy = _normalize(my_goal_x - op[0], goal_y - op[1])
                            target = (op[0] + ux * 1.0, op[1] + uy * 1.0)
                            return move_toward_normalized(target[0], target[1], 1.0), self.tactic
                target = anchor
            elif we_have_ball:
                forward = 1.0 if my_team == "home" else -1.0
                target = (anchor[0] + 15.0 * forward, anchor[1])
            else:
                target = anchor

            if _dist(my_pos_n, target) < 0.5:
                return _hold(), self.tactic
            return move_toward_normalized(target[0], target[1], 0.9), self.tactic

        if role in ("CDM", "CM", "CAM"):
            if they_have_ball:
                for p in opponents:
                    if p.player_id == carrier_id:
                        op = meters_to_field(p.x, p.y)
                        return move_toward_normalized(op[0], op[1], 1.0), self.tactic
            elif we_have_ball:
                for p in teammates + [player]:
                    if p.player_id == carrier_id:
                        cp = meters_to_field(p.x, p.y)
                        forward = 1.0 if my_team == "home" else -1.0
                        side = 8.0 if anchor[1] > goal_y else -8.0
                        target = (cp[0] + 12.0 * forward, cp[1] + side)
                        target = (max(2.0, min(98.0, target[0])), max(2.0, min(58.0, target[1])))
                        if _dist(my_pos_n, target) < 0.5:
                            return _hold(), self.tactic
                        return move_toward_normalized(target[0], target[1], 0.9), self.tactic
            target = anchor
            if _dist(my_pos_n, target) < 0.5:
                return _hold(), self.tactic
            return move_toward_normalized(target[0], target[1], 0.9), self.tactic

        if role in ("ST", "CF", "LW", "RW"):
            # Offside line: stay behind second-last defender when pushing forward
            os_line = offside_line()
            if we_have_ball:
                best_id, best_d = closest_opponent_to(my_pos_n)
                if best_id:
                    for p in opponents:
                        if p.player_id == best_id:
                            op = meters_to_field(p.x, p.y)
                            ax, ay = _normalize(my_pos_n[0] - op[0], my_pos_n[1] - op[1])
                            tx, ty = _normalize(opp_goal_x - my_pos_n[0], goal_y - my_pos_n[1])
                            bx, by = _normalize(0.5*ax + 0.5*tx, 0.5*ay + 0.5*ty)
                            target = (my_pos_n[0] + bx * 12.0, my_pos_n[1] + by * 12.0)
                            break
                else:
                    target = (opp_goal_x, goal_y)
                target = (max(2.0, min(98.0, target[0])), max(2.0, min(58.0, target[1])))
                # Stay onside: don't push past the second-last defender
                if os_line is not None:
                    os_fc = meters_to_field(os_line, 0)[0]
                    if my_team == "home":
                        target = (min(target[0], os_fc - 1.0), target[1])
                    else:
                        target = (max(target[0], os_fc + 1.0), target[1])
            elif they_have_ball:
                forward = -1.0 if my_team == "home" else 1.0
                target = (anchor[0] + 5.0 * forward, anchor[1])
            else:
                target = anchor

            if _dist(my_pos_n, target) < 0.5:
                return _hold(), self.tactic
            return move_toward_normalized(target[0], target[1], 1.0), self.tactic

        # Fallback
        if _dist(my_pos_n, anchor) < 0.5:
            return _hold(), self.tactic
        return move_toward_normalized(anchor[0], anchor[1], 0.8), self.tactic
