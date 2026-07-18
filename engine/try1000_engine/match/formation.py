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
