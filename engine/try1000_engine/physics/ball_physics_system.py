"""Ball Physics System — exact formulas from AgentPitch's core/ball_physics_system.py.

Operates in engine meters. All formulas match AgentPitch exactly.
"""

from __future__ import annotations
import math
import random

from try1000_engine.config import PITCH_LENGTH, PITCH_WIDTH

# AgentPitch field constants converted to meters
_FIELD_W_M = PITCH_LENGTH       # 105.0 meters
_FIELD_H_M = PITCH_WIDTH        # 68.0 meters
_BALL_CONTROL_RANGE_M = 1.5 * (PITCH_LENGTH / 100.0)  # field units → meters
_VELOCITY_EPSILON = 1e-6


# ─── AgentPitch Story 001: advance_ball_position ───

def advance_ball(
    ball_pos: tuple[float, float],
    ball_vel: tuple[float, float],
    landing_zone: tuple[float, float] | None,
    dt: float = 1.0,
) -> tuple[tuple[float, float], tuple[float, float], bool]:
    """AgentPitch advance_ball_position — no friction, constant velocity."""
    vx, vy = ball_vel
    speed_sq = vx * vx + vy * vy
    if speed_sq < _VELOCITY_EPSILON * _VELOCITY_EPSILON:
        return (ball_pos, (0.0, 0.0), False)

    next_x = ball_pos[0] + vx
    next_y = ball_pos[1] + vy

    # OOB check
    half_w = _FIELD_W_M / 2.0
    half_h = _FIELD_H_M / 2.0
    oob = (abs(next_x) > half_w or abs(next_y) > half_h)
    if oob:
        clamped_x = max(-half_w, min(half_w, next_x))
        clamped_y = max(-half_h, min(half_h, next_y))
        return ((clamped_x, clamped_y), (0.0, 0.0), True)

    # Landing zone overshoot
    if landing_zone is not None:
        to_x = landing_zone[0] - ball_pos[0]
        to_y = landing_zone[1] - ball_pos[1]
        if vx * to_x + vy * to_y <= 0.0:
            return (landing_zone, (0.0, 0.0), False)

    # AgentPitch: no friction — constant velocity
    return ((next_x, next_y), (vx, vy), False)


# ─── AgentPitch Story 002: ball control probability ───

def ball_control_prob(player_skill: int, distance: float, ball_speed: float) -> float:
    """AgentPitch Formula 2."""
    if ball_speed == 0.0:
        return 1.0
    ratio = min(1.0, distance / _BALL_CONTROL_RANGE_M)
    return player_skill / (player_skill + ball_speed * (1.0 + ratio))


# ─── AgentPitch Story 003: ball control contest ───

def resolve_ball_control(
    players: list, ball_pos: tuple[float, float],
    ball_vel: tuple[float, float], rng: random.Random,
) -> str | None:
    """AgentPitch ball control contest — nearest in range, skill-based roll."""
    ball_speed = math.sqrt(ball_vel[0]**2 + ball_vel[1]**2)
    candidates = []
    for p in players:
        if getattr(p, 'sent_off', False): continue
        dx = p.x - ball_pos[0]; dy = p.y - ball_pos[1]
        dist_sq = dx*dx + dy*dy
        if dist_sq <= _BALL_CONTROL_RANGE_M * _BALL_CONTROL_RANGE_M:
            skill = int((getattr(p, 'passing', 70) + getattr(p, 'dribbling', 70) + getattr(p, 'awareness', 70)) / 3)
            candidates.append((dist_sq, p, skill))

    if not candidates:
        return None

    candidates.sort(key=lambda c: (c[0], c[1].player_id))
    _, player, skill = candidates[0]
    prob = ball_control_prob(skill, math.sqrt(candidates[0][0]), ball_speed)
    if rng.random() < prob:
        return player.player_id
    return None
