"""Ball Physics System (BPS) — pure functions advancing ball state one tick.

References AgentPitch's `src/core/ball_physics_system.py` design:
- Constant-velocity motion with optional landing-zone overshoot detection
- OOB detection (side/touch lines, goal lines)
- Ball control contest: skill-based probability, nearest-candidate wins
- Carrier skip: carrier's position IS ball position, no motion
"""

from __future__ import annotations
import math
import random

from try1000_engine.config import (
    PITCH_LENGTH, PITCH_WIDTH, BALL_FRICTION, BALL_AIR_FRICTION,
    BALL_CONTROL_RADIUS,
)


def advance_ball(
    ball_pos: tuple[float, float],
    ball_vel: tuple[float, float],
    landing_zone: tuple[float, float] | None,
    dt: float = 1.0,
) -> tuple[tuple[float, float], tuple[float, float], bool]:
    """Advance ball one tick. Returns (new_pos, new_vel, out_of_bounds).

    If landing_zone is set (pass target), overshoot snaps ball to target.
    Otherwise (shot/dribble), ball moves in straight line with friction.

    Args:
        ball_pos: current (x, y) in meters, center at (0,0).
        ball_vel: current (vx, vy) in m/s.
        landing_zone: optional pass target position.
        dt: tick duration in seconds.

    Returns:
        (new_position, new_velocity, out_of_bounds)
    """
    vx, vy = ball_vel
    speed_sq = vx * vx + vy * vy

    # AT_REST or near-zero → no motion
    if speed_sq < 1e-6:
        return (ball_pos, (0.0, 0.0), False)

    # Advance by velocity
    bx, by = ball_pos
    next_x = bx + vx * dt
    next_y = by + vy * dt

    # Check OOB
    half_l = PITCH_LENGTH / 2
    half_w = PITCH_WIDTH / 2
    oob = (abs(next_x) > half_l or abs(next_y) > half_w)
    if oob:
        clamped_x = max(-half_l, min(half_l, next_x))
        clamped_y = max(-half_w, min(half_w, next_y))
        return ((clamped_x, clamped_y), (0.0, 0.0), True)

    # Landing zone overshoot detection (pass only)
    if landing_zone is not None:
        lx, ly = landing_zone
        # Vector from start to landing zone
        to_lz_x = lx - bx
        to_lz_y = ly - by
        # Dot product: if <= 0, ball has passed the landing zone
        dot = vx * to_lz_x + vy * to_lz_y
        if dot <= 0.0:
            return (landing_zone, (0.0, 0.0), False)

    # Apply friction
    new_vx = vx * (BALL_AIR_FRICTION if abs(vx) > 5.0 else BALL_FRICTION)
    new_vy = vy * (BALL_AIR_FRICTION if abs(vy) > 5.0 else BALL_FRICTION)
    if abs(new_vx) < 0.1: new_vx = 0.0
    if abs(new_vy) < 0.1: new_vy = 0.0

    return ((next_x, next_y), (new_vx, new_vy), False)


def ball_control_prob(player_skill: int, distance: float, ball_speed: float) -> float:
    """Probability a player controls the ball. Based on AgentPitch BPS Formula 2.

    AT_REST ball (speed==0) → deterministic pickup (1.0).
    Otherwise: skill / (skill + ball_speed * (1 + distance/range)).
    """
    if ball_speed == 0.0:
        return 1.0
    ratio = min(1.0, distance / BALL_CONTROL_RADIUS)
    return player_skill / (player_skill + ball_speed * (1.0 + ratio))


def resolve_ball_control(
    players: list,
    ball_pos: tuple[float, float],
    ball_vel: tuple[float, float],
    rng: random.Random,
) -> str | None:
    """Find the player who controls a loose ball, or None.

    Nearest player within BALL_CONTROL_RADIUS gets a skill-based roll.
    References AgentPitch BPS Story 003.
    """
    ball_speed = math.sqrt(ball_vel[0]**2 + ball_vel[1]**2)
    candidates = []

    for p in players:
        dx = p.x - ball_pos[0]
        dy = p.y - ball_pos[1]
        dist = math.sqrt(dx*dx + dy*dy)
        if dist <= BALL_CONTROL_RADIUS:
            # Skill proxy: average of relevant attributes
            skill = int((p.passing + p.dribbling + p.awareness) / 3)
            candidates.append((dist, p, skill))

    if not candidates:
        return None

    # Sort by distance (nearest first), then by player_id (tie-break)
    candidates.sort(key=lambda c: (c[0], c[1].player_id))
    dist, player, skill = candidates[0]

    prob = ball_control_prob(skill, dist, ball_speed)
    if rng.random() < prob:
        return player.player_id

    return None
