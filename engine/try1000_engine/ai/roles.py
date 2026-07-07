"""Role definitions and base action weights.

Each role has a weight vector over 8 action types. These are multiplied
by tactical parameters, situational context, and success probability
to produce the final utility score for each action.

Weights are on a scale where 1.0 = "standard preference for this role."
Values above 1.0 mean the role favors that action; below 1.0 means it avoids it.
"""

from try1000_engine.actions.base import ActionType

# ─── Role definitions ───

ROLE_NAMES: dict[int, str] = {
    0: "GK",   1: "CB",   2: "LB",   3: "RB",
    4: "CDM",  5: "CM",   6: "CAM",
    7: "LM",   8: "RM",   9: "LW",   10: "RW",
    11: "ST",
}

ROLE_INDEX: dict[str, int] = {v: k for k, v in ROLE_NAMES.items()}

# ─── Base action weights by role ───
# Columns: HOLD, MOVE, PASS, SHOOT, CROSS, DRIBBLE, TACKLE, INTERCEPT

ROLE_WEIGHTS: dict[int, list[float]] = {
    0:  [0.5, 0.3, 0.6, 0.0, 0.0, 0.1, 0.0, 0.1],  # GK
    1:  [0.3, 0.4, 0.8, 0.0, 0.0, 0.1, 0.7, 0.6],  # CB
    2:  [0.2, 0.6, 0.6, 0.1, 0.5, 0.3, 0.6, 0.4],  # LB
    3:  [0.2, 0.6, 0.6, 0.1, 0.5, 0.3, 0.6, 0.4],  # RB
    4:  [0.3, 0.4, 0.7, 0.2, 0.2, 0.2, 0.7, 0.6],  # CDM
    5:  [0.1, 0.5, 0.7, 0.3, 0.3, 0.3, 0.5, 0.4],  # CM
    6:  [0.1, 0.5, 0.6, 0.5, 0.3, 0.5, 0.2, 0.2],  # CAM
    7:  [0.1, 0.6, 0.4, 0.3, 0.7, 0.6, 0.3, 0.2],  # LM
    8:  [0.1, 0.6, 0.4, 0.3, 0.7, 0.6, 0.3, 0.2],  # RM
    9:  [0.1, 0.6, 0.3, 0.4, 0.6, 0.7, 0.3, 0.2],  # LW
    10: [0.1, 0.6, 0.3, 0.4, 0.6, 0.7, 0.3, 0.2],  # RW
    11: [0.1, 0.5, 0.3, 0.8, 0.05, 0.5, 0.3, 0.1],  # ST — low cross, high shoot
}


def get_role_index(role_name: str) -> int:
    """Convert role name to index. Returns 5 (CM) for unknown roles."""
    return ROLE_INDEX.get(role_name.upper(), 5)


def get_weights(role_name: str) -> list[float]:
    """Get the base action weight vector for a given role name."""
    idx = get_role_index(role_name)
    return ROLE_WEIGHTS.get(idx, ROLE_WEIGHTS[5])


def get_role_name(role_idx: int) -> str:
    return ROLE_NAMES.get(role_idx, "CM")
