"""Action Resolution Engine — stateless tick orchestrator.

Replaces Phase 4/5/6 of the MatchEngine with a single resolve_tick() call.
All actions read from one pre-tick snapshot (ADR-0009: compute-all-then-commit).

Order per AgentPitch ARE:
  1. Movement (Move / Dribble) → PMS
  2. Ball actions (Pass / Shoot / Cross) → BPS + action logic
  3. Defensive actions (Tackle / Intercept) → contest + fouls
  4. Ball physics + control contest → BPS + offside enforcement
  5. Goal detection

IFAB Laws implemented:
  - Law 11: Offside (flag at pass, enforce at ball receipt)
  - Law 12: Fouls + yellow/red cards (tackle-based, penalty area → penalty)
"""

from __future__ import annotations
import math
import random
from typing import Any

from try1000_engine.config import (
    PITCH_LENGTH, PITCH_WIDTH, GOAL_WIDTH,
    BALL_CONTROL_RADIUS, CENTER_CIRCLE_RADIUS,
    COOLDOWN_DURATION_TICKS, GOAL_RESET_TICKS,
)
from try1000_engine.actions.base import ActionType, ActionOutput
from try1000_engine.physics.ball_physics_system import advance_ball, ball_control_prob
from try1000_engine.physics.player_movement_system import (
    compute_move_result, apply_snap, detect_dribble_target,
)


def _speed_of(player: Any) -> float:
    """Return a player's current speed as a fraction of max (0-1)."""
    if hasattr(player, "current_speed"):
        return player.current_speed
    return 0.0


def _skill_attr(player: Any, attr: str) -> int:
    """Safely read a player attribute, defaulting to 50."""
    val = getattr(player, attr, 50)
    return int(val) if val else 50


def resolve_tick(
    engine,  # MatchEngine instance (for state access)
    decisions: dict[str, ActionOutput],
    rng: random.Random,
) -> dict[str, dict]:
    """Resolve one tick's worth of actions against the current game state.

    Args:
        engine: MatchEngine (provides self.players, self.ball, etc.)
        decisions: validated {player_id: ActionOutput} from AI
        rng: seeded random instance

    Returns:
        events: dict of {player_id: {"type": ..., "success": bool, "data": {...}}}
    """
    events: dict[str, dict] = {}

    # ─── Phase 1: Player Movement ───
    _resolve_movement(engine, decisions, events, rng)

    # ─── Phase 2: Ball Actions (Pass / Shoot / Cross) ───
    _resolve_ball_actions(engine, decisions, events, rng)

    # ─── Phase 3: Defensive Actions (Tackle / Intercept) ───
    _resolve_defensive(engine, decisions, events, rng)

    # ─── Phase 4: Ball Physics + Control Contest ───
    _resolve_ball_physics(engine, rng, events)

    # ─── Phase 5: Goal Detection ───
    _detect_goal(engine, events, rng)

    return events


# ═══════════════════════════════════════════════
# Phase 1: Movement
# ═══════════════════════════════════════════════

def _resolve_movement(engine, decisions, events, rng):
    """Process Move and Dribble actions. Idle players snap toward formation anchor."""
    for pid, action in decisions.items():
        player = engine._find_player(pid)
        if player is None or getattr(player, 'sent_off', False):
            continue

        at = ActionType(action.action_type)
        if at in (ActionType.MOVE, ActionType.DRIBBLE):
            new_pos = compute_move_result(
                current_pos=(player.x, player.y),
                dx=action.dx, dy=action.dy,
                speed_ratio=action.speed,
                player_attr=_skill_attr(player, "pace"),
                role=player.role,
            )
            player.x, player.y = new_pos

            # Dribble: ball follows carrier closely
            if at == ActionType.DRIBBLE and player.has_ball:
                engine.ball.x += (player.x - engine.ball.x) * 0.8
                engine.ball.y += (player.y - engine.ball.y) * 0.8

            # Dribble contest detection
            if player.has_ball:
                target = detect_dribble_target(
                    player_pos=(player.x, player.y),
                    player_team=player.team,
                    all_players=engine.players,
                    dribble_range=2.5,
                )
                if target:
                    events[pid] = {
                        "type": "dribble_contest",
                        "success": False,
                        "data": {"opponent": target},
                    }
        else:
            # Idle: snap toward formation anchor
            anchor = engine._get_anchor(player)
            new_pos = apply_snap(
                current_pos=(player.x, player.y),
                anchor_pos=anchor,
                discipline=_skill_attr(player, "awareness") / 100.0,
            )
            player.x, player.y = new_pos


# ═══════════════════════════════════════════════
# Phase 2: Ball Actions
# ═══════════════════════════════════════════════

def _resolve_ball_actions(engine, decisions, events, rng):
    """Process Pass, Shoot, Cross actions — these launch the ball into the air."""
    for pid, action in decisions.items():
        player = engine._find_player(pid)
        if player is None or not player.has_ball:
            continue

        at = ActionType(action.action_type)
        if at not in (ActionType.PASS, ActionType.SHOOT, ActionType.CROSS):
            continue

        # Use the existing action resolvers
        if at == ActionType.PASS:
            event_data = engine.pass_action.resolve(player, engine.ball, engine.players, rng, action)
        elif at == ActionType.SHOOT:
            event_data = engine.shoot_action.resolve(player, engine.ball, engine.players, rng, action)
        else:  # CROSS
            event_data = engine.cross_action.resolve(player, engine.ball, engine.players, rng, action)

        if event_data:
            events[pid] = {
                "type": at.name.lower(),
                "success": event_data.get("success", False),
                "data": event_data,
            }
            # Offside check: flag teammates in offside position at pass moment
            if at == ActionType.PASS:
                engine._offside_flagged = _check_offside(engine, player)

            # Set landing zone for BPS pass tracking
            if at == ActionType.PASS and "target_x" in event_data:
                engine._pass_landing_zone = (
                    event_data["target_x"],
                    event_data["target_y"],
                )
            # Transfer possession away from passer/shooter
            player.has_ball = False
            engine.ball.carrier_id = None
            engine.ball.last_touch_team = player.team
            # Trigger cooldown
            player.trigger_cooldown(COOLDOWN_DURATION_TICKS)


# ═══════════════════════════════════════════════
# Phase 3: Defensive Actions
# ═══════════════════════════════════════════════

def _resolve_defensive(engine, decisions, events, rng):
    """Process Tackle and auto-Intercept actions."""
    for pid, action in decisions.items():
        player = engine._find_player(pid)
        if player is None:
            continue

        at = ActionType(action.action_type)
        if at == ActionType.TACKLE:
            _resolve_tackle(engine, player, action, events, rng)

    # Auto-intercepts: any player can intercept a pass moving near them
    for p in engine.players:
        if engine.ball.carrier_id is None and engine.ball.last_touch_team and p.team != engine.ball.last_touch_team:
            event_data = engine.intercept_action.try_intercept(p, engine.ball, engine.players, rng)
            if event_data:
                events[p.player_id] = {
                    "type": "intercept",
                    "success": True,
                    "data": event_data,
                }


# ═══════════════════════════════════════════════
# Phase 4: Ball Physics + Control Contest
# ═══════════════════════════════════════════════

def _resolve_ball_physics(engine, rng, events):
    """Advance the ball and run a control contest for loose balls."""
    ball = engine.ball
    carrier_id = ball.carrier_id

    if carrier_id is None:
        # Loose ball: compute physics
        landing = getattr(engine, '_pass_landing_zone', None)
        new_pos, new_vel, oob = advance_ball(
            (ball.x, ball.y), (ball.vx, ball.vy), landing,
        )
        ball.x, ball.y = new_pos
        ball.vx, ball.vy = new_vel

        if oob:
            # Determine restart type
            oob_type = "goal_kick" if abs(ball.x) > PITCH_LENGTH * 0.45 else "throw_in"
            events["_oob"] = {"type": oob_type, "success": False, "data": {}}
        else:
            # Ball control contest
            winner = _ball_control_contest(engine, new_pos, new_vel, rng)
            if winner:
                # Offside enforcement (Law 11): flagged receiver → free kick
                offside_flagged = getattr(engine, '_offside_flagged', set())
                if winner in offside_flagged:
                    events["_offside"] = {"type": "offside", "data": {"player": winner}}
                    engine._offside_flagged = set()
                else:
                    winner_p = engine._find_player(winner)
                    if winner_p:
                        ball.carrier_id = winner
                        ball.last_touch_team = winner_p.team
                        ball.vx = 0.0
                        ball.vy = 0.0
                        if winner not in events:
                            events[winner] = {}
                        events[winner]["type"] = "ball_control"
                        events[winner]["success"] = True
                engine._offside_flagged = set()  # clear after this pass resolves
    else:
        # Ball is carried: no physics
        carrier = engine._find_ball_carrier()
        if carrier:
            ball.x = carrier.x
            ball.y = carrier.y
        ball.vx = 0.0
        ball.vy = 0.0

    # Sync has_ball flags
    for p in engine.players:
        p.has_ball = (p.player_id == ball.carrier_id)


def _ball_control_contest(engine, ball_pos, ball_vel, rng):
    """Find the winner of the ball control contest — nearest player in range."""
    ball_speed = math.sqrt(ball_vel[0]**2 + ball_vel[1]**2)
    candidates = []
    for p in engine.players:
        if getattr(p, 'sent_off', False):
            continue
        dx = p.x - ball_pos[0]
        dy = p.y - ball_pos[1]
        dist = math.sqrt(dx*dx + dy*dy)
        if dist <= BALL_CONTROL_RADIUS:
            skill = int((_skill_attr(p, "passing") + _skill_attr(p, "dribbling") + _skill_attr(p, "awareness")) / 3)
            candidates.append((dist, p, skill))

    if not candidates:
        return None

    candidates.sort(key=lambda c: (c[0], c[1].player_id))
    dist, player, skill = candidates[0]

    prob = ball_control_prob(skill, dist, ball_speed)
    if rng.random() < prob:
        return player.player_id
    return None


# ═══════════════════════════════════════════════
# Phase 5: Goal Detection
# ═══════════════════════════════════════════════

def _detect_goal(engine, events, rng):
    """Check if the ball has crossed the goal line between the posts."""
    ball = engine.ball
    half_l = PITCH_LENGTH / 2
    half_goal = GOAL_WIDTH / 2

    # Ball must be at or beyond the goal line
    if abs(ball.x) < half_l:
        return

    # Ball must be between the goal posts
    if abs(ball.y) > half_goal:
        return

    # Goal scored
    if ball.x >= half_l:
        scorer = "home"
        engine.away_score += 1
        engine._conceding_team = "away"
    else:
        scorer = "away"
        engine.home_score += 1
        engine._conceding_team = "home"

    events["_goal"] = {
        "type": "goal",
        "success": True,
        "data": {"scorer": scorer, "xg": 0.5},
    }
    engine.phase = type(engine.phase).GOAL_SCORED
    engine._goal_pause_remaining = GOAL_RESET_TICKS


# ═══════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════

def _nearest(player, candidates):
    best, best_dist = None, float("inf")
    for p in candidates:
        d = math.sqrt((p.x - player.x)**2 + (p.y - player.y)**2)
        if d < best_dist:
            best, best_dist = p, d
    return best


# ═══════════════════════════════════════════════
# Law 11: Offside
# ═══════════════════════════════════════════════

def _check_offside(engine, passer) -> set[str]:
    """Return set of passer's teammates in an offside position.

    Offside position: player is closer to opponent's goal line than BOTH:
    - The ball
    - The second-last opponent (including GK)
    """
    flagged = set()
    own_team = passer.team
    opponents = [p for p in engine.players if p.team != own_team]
    if len(opponents) < 2:
        return flagged

    # Find second-last opponent's x position
    sorted_opp = sorted(opponents, key=lambda p: p.x if own_team == "home" else -p.x)
    # For home attacking right (+x), second-last is opponents sorted by x ascending, index 1
    # For away attacking left (-x), second-last is opponents sorted by -x ascending, index 1
    if own_team == "home":
        second_last_x = sorted_opp[1].x if len(sorted_opp) > 1 else sorted_opp[0].x
    else:
        sorted_opp_rev = sorted(opponents, key=lambda p: -p.x)
        second_last_x = sorted_opp_rev[1].x if len(sorted_opp_rev) > 1 else sorted_opp_rev[0].x

    ball_x = engine.ball.x

    for p in engine.players:
        if p.team != own_team or p.player_id == passer.player_id:
            continue
        if own_team == "home":
            # Home attacks right: offside if player_x > ball_x AND player_x > second_last_x
            if p.x > ball_x and p.x > second_last_x:
                flagged.add(p.player_id)
        else:
            # Away attacks left: offside if player_x < ball_x AND player_x < second_last_x
            if p.x < ball_x and p.x < second_last_x:
                flagged.add(p.player_id)

    return flagged


# ═══════════════════════════════════════════════
# Law 12: Fouls and cards
# ═══════════════════════════════════════════════

FOUL_BASE_PROB = 0.25       # base probability a tackle is a foul
YELLOW_THRESHOLD = 3        # fouls before a yellow card
SENT_OFF_THRESHOLD = 6      # fouls before a straight red card

_PENALTY_AREA_DEPTH = 16.5   # meters from goal line
_PENALTY_MARK_X = PITCH_LENGTH / 2 - 11.0  # penalty spot x in meters


def _check_tackle_foul(engine, tackler, target, event_data, events, rng):
    """Check if a tackle is a foul, and handle cards/penalties.

    Called after a tackle resolves (whether successful or not).
    Returns True if play should stop (penalty / red card).
    """
    if not event_data:
        return False

    # Foul probability increases with lower defending skill
    defending = _skill_attr(tackler, "defending")
    foul_prob = FOUL_BASE_PROB * (1.0 - defending / 200.0)  # 0.125 at 100 def, 0.25 at 50 def
    if rng.random() > foul_prob:
        return False  # clean tackle

    # Register foul
    fouls = getattr(engine, '_player_fouls', {})
    if not hasattr(engine, '_player_fouls'):
        engine._player_fouls = {}
    engine._player_fouls[tackler.player_id] = engine._player_fouls.get(tackler.player_id, 0) + 1
    foul_count = engine._player_fouls[tackler.player_id]

    event_data["foul"] = True
    events[tackler.player_id] = {"type": "foul", "success": False, "data": event_data}

    # Card check
    if not hasattr(engine, '_player_cards'):
        engine._player_cards = {}
    existing = engine._player_cards.get(tackler.player_id, None)

    if foul_count >= SENT_OFF_THRESHOLD:
        engine._player_cards[tackler.player_id] = "red"
        events[tackler.player_id]["data"]["card"] = "red"
        tackler.sent_off = True
        return True  # stop play
    elif foul_count >= YELLOW_THRESHOLD and existing != "yellow":
        engine._player_cards[tackler.player_id] = "yellow"
        events[tackler.player_id]["data"]["card"] = "yellow"

    # Penalty area foul → penalty kick
    target_x = target.x
    if target.team == "home":
        in_box = target_x > (PITCH_LENGTH / 2 - _PENALTY_AREA_DEPTH)
    else:
        in_box = target_x < (-PITCH_LENGTH / 2 + _PENALTY_AREA_DEPTH)

    if in_box:
        events[tackler.player_id]["data"]["restart_type"] = "penalty_kick"
        events["_penalty"] = {"type": "penalty_kick", "team": target.team}
        return True  # stop play

    return False


def _resolve_tackle(engine, tackler, action, events, rng):
    """Resolve a single tackle action with foul/card checking."""
    # Find target
    opponents = [p for p in engine.players if p.team != tackler.team]
    target = _nearest(tackler, opponents)
    if not target:
        return
    action.target_player_id = target.player_id

    event_data = engine.tackle_action.resolve(
        tackler, engine.ball, engine.players, rng, action)

    if event_data:
        # Check for foul/card
        stop_play = _check_tackle_foul(engine, tackler, target, event_data, events, rng)
        if not stop_play:
            events[tackler.player_id] = {
                "type": "tackle",
                "success": event_data.get("success", False),
                "data": event_data,
            }
        tackler.trigger_cooldown(COOLDOWN_DURATION_TICKS)
