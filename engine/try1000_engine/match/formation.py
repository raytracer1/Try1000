"""Formation & Role System (FRS) — canonical player positions per formation.

References AgentPitch's FRS (`formation_and_role_system.py`) and the frontend
Pitch component's POSITIONS dict. Positions are in normalized 0-100×0-65 coords
(origin top-left), same as the SVG viewBox, and converted to engine meters.
"""

from __future__ import annotations
import math
from typing import Any

from try1000_engine.config import PITCH_LENGTH, PITCH_WIDTH

# ─── Formation Positions (normalized 0-100 x 0-65, same as Pitch.tsx) ───

# AgentPitch FRS positions (100x60 field, team attacks right)
# GK near own goal, DEF deep, MID center, FWD advanced
POSITIONS: dict[str, list[tuple[float, float]]] = {
    "4-3-3": [
        (8, 30), (25, 12), (25, 24), (25, 36), (25, 48),
        (50, 20), (50, 30), (50, 40), (70, 15), (75, 30), (70, 45),
    ],
    "4-4-2": [
        (8, 30), (25, 12), (25, 24), (25, 36), (25, 48),
        (50, 12), (50, 24), (50, 36), (50, 48), (75, 20), (75, 40),
    ],
    "3-5-2": [
        (8, 30), (25, 12), (25, 30), (25, 48),
        (50, 8), (50, 20), (50, 30), (50, 40), (50, 52),
        (75, 20), (75, 40),
    ],
    "4-2-3-1": [
        (8, 30), (25, 12), (25, 24), (25, 36), (25, 48),
        (45, 22), (45, 38), (60, 12), (60, 30), (60, 48), (80, 30),
    ],
    "3-4-3": [
        (8, 30), (25, 12), (25, 30), (25, 48),
        (50, 8), (50, 22), (50, 30), (50, 38), (50, 52),
        (75, 12), (75, 48), (80, 30),
    ],
}

# ─── Role-to-slot mapping per formation ───

# Slot roles — AgentPitch: GK, DEF, MID, FWD
SLOT_ROLES: dict[str, list[str]] = {
    "4-3-3":     ["GK", "DEF", "DEF", "DEF", "DEF", "MID", "MID", "MID", "FWD", "FWD", "FWD"],
    "4-4-2":     ["GK", "DEF", "DEF", "DEF", "DEF", "MID", "MID", "MID", "MID", "FWD", "FWD"],
    "3-5-2":     ["GK", "DEF", "DEF", "DEF", "MID", "MID", "MID", "MID", "MID", "FWD", "FWD"],
    "4-2-3-1":   ["GK", "DEF", "DEF", "DEF", "DEF", "MID", "MID", "MID", "MID", "MID", "FWD"],
    "3-4-3":     ["GK", "DEF", "DEF", "DEF", "MID", "MID", "MID", "MID", "FWD", "FWD", "FWD", "FWD"],
}

# ─── Role compatibility groups (for matching player roles to slots) ───

_COMPAT: dict[str, list[str]] = {
    "GK": ["GK"],
    "CB": ["DEF"], "LB": ["DEF"], "RB": ["DEF"], "LCB": ["DEF"], "RCB": ["DEF"],
    "CDM": ["MID"], "CM": ["MID"], "CAM": ["MID"], "LM": ["MID"], "RM": ["MID"],
    "LW": ["FWD"], "RW": ["FWD"], "ST": ["FWD"], "CF": ["FWD"],
}


def normalized_to_engine(nx: float, ny: float) -> tuple[float, float]:
    """Convert AgentPitch field coords (0-100 x 0-60) → engine meters (center 0,0)."""
    ex = (nx / 100.0) * PITCH_LENGTH - PITCH_LENGTH / 2.0
    ey = (ny / 60.0) * PITCH_WIDTH - PITCH_WIDTH / 2.0
    return (ex, ey)


def _match_role(player_role: str, slot_role: str) -> int:
    """Return 0 (exact match), 1 (compatible), or 2 (poor fit)."""
    if player_role == slot_role:
        return 0
    compat = _COMPAT.get(slot_role, [])
    return 1 if player_role in compat else 2


def compute_anchors(formation: str, players: list) -> dict[str, tuple[float, float]]:
    """Assign each player a formation position in engine meter coordinates.

    Returns {player_id: (x, y)}.

    Strategy: Greedy assignment — GK first, then assign remaining players
    to the best-fitting open slot based on role compatibility.
    """
    slots = POSITIONS.get(formation, POSITIONS["4-3-3"])
    slot_roles = SLOT_ROLES.get(formation, SLOT_ROLES["4-3-3"])
    n = len(slots)

    anchors: dict[str, tuple[float, float]] = {}
    assigned = set()

    # 1. Assign GK
    gks = [p for p in players if p.role == "GK"]
    if gks and n > 0:
        anchors[gks[0].player_id] = normalized_to_engine(*slots[0])
        assigned.add(gks[0].player_id)

    # 2. Assign remaining players to best slots
    remaining = [p for p in players if p.player_id not in assigned]
    open_slots = list(range(1, n))  # slot 0 is GK

    for player in remaining:
        best_slot, best_score = None, 99
        for si in open_slots:
            score = _match_role(player.role, slot_roles[si])
            if score < best_score:
                best_score = score
                best_slot = si
        if best_slot is not None:
            anchors[player.player_id] = normalized_to_engine(*slots[best_slot])
            open_slots.remove(best_slot)

    return anchors


def mirror_anchors(anchors: dict[str, tuple[float, float]]) -> dict[str, tuple[float, float]]:
    """Mirror anchors across center (for away team playing left-to-right)."""
    return {pid: (-x, y) for pid, (x, y) in anchors.items()}


# ─── AgentPitch FRS: Dynamic Phase-Aware Anchors ───

ROLE_TO_GROUP: dict[str, str] = {
    "GK": "GK",
    "CB": "DEF", "LCB": "DEF", "RCB": "DEF", "LB": "DEF", "RB": "DEF",
    "CDM": "MID", "CM": "MID", "CAM": "MID", "LM": "MID", "RM": "MID",
    "LW": "FWD", "RW": "FWD", "ST": "FWD", "CF": "FWD",
}

PHASE_ZONES: dict[str, dict[str, tuple[float, float, float]]] = {
    "defending": {
        "GK":  (0.03, 0.10, 0.05),
        "DEF": (0.05, 0.20, 0.15),
        "MID": (0.20, 0.40, 0.20),
        "FWD": (0.35, 0.55, 0.25),
    },
    "transitioning": {
        "GK":  (0.06, 0.12, 0.07),
        "DEF": (0.28, 0.45, 0.18),
        "MID": (0.45, 0.62, 0.22),
        "FWD": (0.65, 0.80, 0.25),
    },
    "attacking": {
        "GK":  (0.08, 0.16, 0.10),
        "DEF": (0.42, 0.62, 0.20),
        "MID": (0.58, 0.78, 0.22),
        "FWD": (0.75, 0.93, 0.20),
    },
}

Y_COMPACTION: dict[str, float] = {
    "defending": 0.55,
    "transitioning": 0.30,
    "attacking": 0.10,
}


def classify_team_phase(
    ball_x_fc: float,
    defending_goal_x: float,
    have_ball: bool,
    ball_possession: str | None = None,
) -> str:
    """AgentPitch FRS: classify team phase based on ball position and possession.

    Exactly matches AgentPitch's formation_and_role_system.classify_team_phase.
    A loose ball (ball_possession is None) is treated like "have ball" for the
    attacking threshold — the team closer to the opponent's goal pushes forward.
    """
    dist = abs(ball_x_fc - defending_goal_x) / 100.0
    loose = ball_possession is None
    if dist > 0.66:
        # Ball in opponent's third
        return "attacking" if (have_ball or loose) else "transitioning"
    if dist < 0.34:
        # Ball in own third
        return "transitioning" if have_ball else "defending"
    # Ball in middle third
    return "transitioning"


def compute_dynamic_anchor(
    player,
    all_players: list,
    ball_x_fc: float,
    ball_y_fc: float,
    own_goal_x_fc: float,
    have_ball: bool,
    ball_possession: str | None = None,
    field_width: float = 100.0,
    field_height: float = 60.0,
) -> tuple[float, float]:
    """AgentPitch FRS: compute per-tick dynamic phase-aware anchor position.

    Uses PHASE_ZONES table from AgentPitch's formation_and_role_system.py,
    with ball-side y-compaction and per-role-group lateral distribution.

    All coordinates are in AgentPitch field coords [0,100]×[0,60], matching
    AgentPitch's compute_zone_for / compute_dynamic_anchor exactly.

    Returns (x, y) in field coords.
    """
    role_group = ROLE_TO_GROUP.get(player.role, "MID")

    # Phase classification (matches AgentPitch FRS.classify_team_phase).
    phase = classify_team_phase(
        ball_x_fc, own_goal_x_fc, have_ball, ball_possession,
    )

    # Phase zone lookup
    x_min_pct, x_max_pct, y_spread_pct = PHASE_ZONES[phase][role_group]

    # Orient x based on defending direction (handles halftime swap).
    if own_goal_x_fc < field_width / 2.0:
        # Team defends low-x; attacks toward +x
        x_min = x_min_pct * field_width
        x_max = x_max_pct * field_width
    else:
        # Team defends high-x; attacks toward -x → mirror across midfield
        x_min = (1.0 - x_max_pct) * field_width
        x_max = (1.0 - x_min_pct) * field_width

    # Count players in this role group and find index (for y-distribution).
    group_players = sorted(
        [p for p in all_players if p.team == player.team
         and ROLE_TO_GROUP.get(p.role) == role_group],
        key=lambda p: p.player_id
    )
    try:
        role_idx = next(i for i, p in enumerate(group_players) if p.player_id == player.player_id)
    except StopIteration:
        role_idx = 0
    role_count = len(group_players)
    if role_count == 0:
        role_count = 1

    # Y distribution with ball-side compaction.
    # Matches AgentPitch FRS: y_base = field_height * (role_idx+1) / (role_count+1)
    y_base = field_height * (role_idx + 1) / (role_count + 1)
    ball_offset = (ball_y_fc - field_height / 2.0) * Y_COMPACTION[phase]
    y_center = max(0.0, min(field_height, y_base + ball_offset))

    # GK: anchor at own goal line + 2u (matches AgentPitch FRS).
    if role_group == "GK":
        gx = own_goal_x_fc + (2.0 if own_goal_x_fc < field_width / 2.0 else -2.0)
        return (gx, y_center)

    # Return zone center in field coords.
    cx = (x_min + x_max) / 2.0
    return (cx, y_center)
