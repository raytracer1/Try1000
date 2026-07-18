"""Player Movement System — exact port of AgentPitch's core/player_movement_system.py.

Operates in AgentPitch field coords (100×60). Conversion from meters
happens in the engine-facing wrapper.
"""

from __future__ import annotations
import math

# AgentPitch constants (field coords)
FIELD_WIDTH = 100.0
FIELD_HEIGHT = 60.0
_DIRECTION_EPSILON = 1e-6
ACTIVE_SPEED_THRESHOLD = 0.5
MOVE_UNIT_PER_TICK = 0.05          # AgentPitch: power=20 → 1.0 units/tick
DRIBBLE_RANGE = 1.5
SNAP_MAX_FORCE = 0.20              # at most 20% pull

# Conversion: engine coords (center 0,0, range [-50,50]×[-30,30]) ↔ field (origin 0,0)
def _m_to_fx(x): return x + 50.0
def _m_to_fy(y): return y + 30.0
def _f_to_mx(fx): return fx - 50.0
def _f_to_my(fy): return fy - 30.0

def _discipline_to_force(discipline_0_100: int) -> float:
    """Convert our 0-100 discipline to AgentPitch snap force (0-0.20)."""
    return min(discipline_0_100 / 100.0, SNAP_MAX_FORCE)


def compute_move_result(
    player,          # engine Player
    dx: float, dy: float, speed_ratio: float,
) -> tuple[float, float]:
    """AgentPitch Formula 1 — compute movement distance in field coords,
    then convert back to engine meters.

    AgentPitch: move_dist = clamped_ratio * player_speed * MOVE_UNIT_PER_TICK
    player_speed is in AgentPitch 1-20 scale (mapped from pace 0-100).
    """
    clamped_ratio = max(0.0, min(1.0, speed_ratio))

    # Convert pace (0-100) to AgentPitch speed (1-20)
    agentpitch_speed = max(1, int(getattr(player, 'pace', 70) / 5))

    # AgentPitch Formula 1 in field coords
    move_dist = clamped_ratio * agentpitch_speed * MOVE_UNIT_PER_TICK  # field units = engine units

    magnitude = math.sqrt(dx * dx + dy * dy)
    if magnitude < _DIRECTION_EPSILON:
        return (player.x, player.y)

    nx = dx / magnitude
    ny = dy / magnitude
    new_x = player.x + nx * move_dist
    new_y = player.y + ny * move_dist

    # Clamp to pitch (field coords, center 0,0)
    half_l = 50.0; half_w = 30.0
    new_x = max(-half_l, min(half_l, new_x))
    new_y = max(-half_w, min(half_w, new_y))
    return (new_x, new_y)


def apply_snap(
    player,            # engine Player
    anchor_x_m: float, anchor_y_m: float,
    force: float = 0.10,
) -> tuple[float, float]:
    """AgentPitch Formula 3 — drift toward formation anchor when idle."""
    force = min(force, SNAP_MAX_FORCE)
    x = (1.0 - force) * player.x + force * anchor_x_m
    y = (1.0 - force) * player.y + force * anchor_y_m
    return (x, y)


def detect_dribble_target(
    player,            # engine Player
    all_players: list,
    dribble_range_m: float = 1.5 * 1.05,  # field units → meters
) -> str | None:
    """AgentPitch Formula 4 — find nearest opponent for dribble contest."""
    range_sq = dribble_range_m * dribble_range_m
    candidates = []
    for opp in all_players:
        if opp.team == player.team:
            continue
        dx = opp.x - player.x
        dy = opp.y - player.y
        dist_sq = dx * dx + dy * dy
        if dist_sq < range_sq:
            candidates.append((dist_sq, opp.player_id))
    if not candidates:
        return None
    candidates.sort(key=lambda c: (c[0], c[1]))
    return candidates[0][1]
