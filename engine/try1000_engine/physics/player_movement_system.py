"""Player Movement System (PMS) — pure functions computing player positions.

References AgentPitch's `src/core/player_movement_system.py` design:
- compute_move_result: direction × speed_ratio × player_speed → new position
- apply_snap: idle players drift back toward formation anchor (discipline pull)
- detect_dribble_target: find nearest opponent for dribble contest
"""

from __future__ import annotations
import math

from try1000_engine.config import (
    PITCH_LENGTH, PITCH_WIDTH, PLAYER_RADIUS,
    MAX_PLAYER_SPEED, JOG_SPEED, WALK_SPEED,
)

# Move unit per tick: maps speed_ratio + player attributes to meters/tick.
# At MAX_PLAYER_SPEED=10 m/s with TICK_DURATION=1s: max ≈ 10 meters/tick.
# Scaled down for realistic game distances.
MOVE_UNIT_PER_TICK = 0.5  # meters per tick at max speed_ratio × speed_attr/10

# Snap discipline: idle players drift back to formation anchor at this rate.
SNAP_MAX_FORCE = 0.15  # max fraction of distance to anchor per tick


def compute_move_result(
    current_pos: tuple[float, float],
    dx: float,
    dy: float,
    speed_ratio: float,
    player_attr: float,  # pace attribute 0-100, maps to speed capability
    role: str = "OUTFIELD",
) -> tuple[float, float]:
    """Compute post-movement position for one player.

    Formula: move_dist = clamp(speed_ratio,0,1) * player_attr/100 * MOVE_UNIT_PER_TICK
    Then: new_pos = current_pos + normalize(dx,dy) * move_dist, clamped to pitch.

    GK moves slower (shorter range, more positional).

    Args:
        current_pos: (x, y) in meters.
        dx, dy: direction vector (can be unnormalized).
        speed_ratio: 0-1 how hard the player is moving.
        player_attr: pace attribute 0-100.
        role: "GK" moves at 60% speed.

    Returns:
        (new_x, new_y) clamped to pitch boundaries.
    """
    magnitude = math.sqrt(dx * dx + dy * dy)
    if magnitude < 1e-6:
        return current_pos

    clamped_ratio = max(0.0, min(1.0, speed_ratio))
    speed = (player_attr / 100.0) * MAX_PLAYER_SPEED * MOVE_UNIT_PER_TICK
    if role == "GK":
        speed *= 0.6

    move_dist = clamped_ratio * speed
    nx = dx / magnitude
    ny = dy / magnitude

    new_x = current_pos[0] + nx * move_dist
    new_y = current_pos[1] + ny * move_dist

    # Clamp to pitch
    half_l = PITCH_LENGTH / 2
    half_w = PITCH_WIDTH / 2
    new_x = max(-half_l, min(half_l, new_x))
    new_y = max(-half_w, min(half_w, new_y))

    return (new_x, new_y)


def apply_snap(
    current_pos: tuple[float, float],
    anchor_pos: tuple[float, float],
    discipline: float = 0.5,
) -> tuple[float, float]:
    """Drift player toward formation anchor when idle.

    Formula: final = (1-force) * current + force * anchor
    where force = clamp(discipline, 0, 1) * SNAP_MAX_FORCE

    References AgentPitch PMS Formula 3.
    """
    force = max(0.0, min(1.0, discipline)) * SNAP_MAX_FORCE
    x = (1.0 - force) * current_pos[0] + force * anchor_pos[0]
    y = (1.0 - force) * current_pos[1] + force * anchor_pos[1]
    return (x, y)


def detect_dribble_target(
    player_pos: tuple[float, float],
    player_team: str,
    all_players: list,
    dribble_range: float = 3.0,
) -> str | None:
    """Find nearest opponent within dribble_range for contest.

    Returns opponent's player_id or None.

    References AgentPitch PMS Formula 4.
    """
    range_sq = dribble_range * dribble_range
    candidates = []

    for opp in all_players:
        if opp.team == player_team:
            continue
        dx = opp.x - player_pos[0]
        dy = opp.y - player_pos[1]
        dist_sq = dx * dx + dy * dy
        if dist_sq < range_sq:
            candidates.append((dist_sq, opp.player_id))

    if not candidates:
        return None

    candidates.sort(key=lambda c: (c[0], c[1]))
    return candidates[0][1]
