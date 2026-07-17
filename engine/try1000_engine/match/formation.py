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

POSITIONS: dict[str, list[tuple[float, float]]] = {
    "4-3-3": [
        (5, 32), (18, 20), (18, 44), (22, 6), (22, 58),
        (32, 32), (40, 18), (40, 46), (46, 8), (46, 56), (50, 32),
    ],
    "4-4-2": [
        (5, 32), (18, 20), (18, 44), (22, 6), (22, 58),
        (32, 10), (32, 54), (42, 22), (42, 42), (48, 22), (48, 42),
    ],
    "3-5-2": [
        (5, 32), (18, 20), (18, 44), (24, 32),
        (32, 8), (32, 56), (38, 22), (38, 42), (30, 32),
        (48, 22), (48, 42),
    ],
    "4-2-3-1": [
        (5, 32), (18, 20), (18, 44), (22, 6), (22, 58),
        (34, 22), (34, 42), (42, 10), (40, 32), (42, 54), (50, 32),
    ],
    "3-4-3": [
        (5, 32), (18, 20), (18, 44),
        (30, 8), (30, 56), (36, 22), (36, 42),
        (44, 10), (44, 54), (42, 22), (42, 42), (39, 32),
    ],
}

# ─── Role-to-slot mapping per formation ───

SLOT_ROLES: dict[str, list[str]] = {
    "4-3-3":     ["GK", "CB", "CB", "LB", "RB", "CDM", "CM", "CM", "LW", "RW", "ST"],
    "4-4-2":     ["GK", "CB", "CB", "LB", "RB", "RM", "CM", "CM", "LM", "ST", "ST"],
    "3-5-2":     ["GK", "CB", "CB", "CB", "CM", "CM", "CM", "RM", "LM", "ST", "ST"],
    "4-2-3-1":   ["GK", "CB", "CB", "LB", "RB", "CDM", "CDM", "LW", "CAM", "RW", "ST"],
    "3-4-3":     ["GK", "CB", "CB", "CB", "CM", "CM", "LM", "RM", "LW", "ST", "RW"],
}

# ─── Role compatibility groups (for matching player roles to slots) ───

_COMPAT: dict[str, list[str]] = {
    "GK": ["GK"],
    "CB": ["CB", "LCB", "RCB"],
    "LB": ["LB", "LWB", "RB", "RWB"],
    "RB": ["RB", "RWB", "LB", "LWB"],
    "CDM": ["CDM", "CM"],
    "CM": ["CM", "CDM", "CAM"],
    "CAM": ["CAM", "CM", "CF"],
    "LW": ["LW", "LM", "RW", "RM"],
    "RW": ["RW", "RM", "LW", "LM"],
    "LM": ["LM", "LW", "CM"],
    "RM": ["RM", "RW", "CM"],
    "ST": ["ST", "CF", "LW", "RW"],
    "CF": ["CF", "ST"],
}


def normalized_to_engine(nx: float, ny: float) -> tuple[float, float]:
    """Convert normalized coords (0-100 x 0-65, SVG viewBox) → engine meters (center 0,0)."""
    ex = (nx / 100.0) * PITCH_LENGTH - PITCH_LENGTH / 2.0
    ey = (ny / 65.0) * PITCH_WIDTH - PITCH_WIDTH / 2.0
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
