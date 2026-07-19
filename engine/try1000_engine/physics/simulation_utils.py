"""Simulation utilities — exact replica of AgentPitch foundation/simulation_utils.py.

Provides deterministic hash_01 for all probabilistic systems.
"""

import hashlib
import struct
from typing import Any


def hash_01(seed: int, tick: int, *args: Any) -> float:
    """Returns a deterministic float in [0.0, 1.0) for the given inputs.

    Used by all probabilistic systems (pass accuracy, shot resolution, tackle,
    dribble, ball control) as the single source of randomness. Same inputs
    always return the same value on any machine — this is the foundation of
    simulation determinism.

    Args:
        seed: Match RNG seed.
        tick: Current tick counter — passed second for per-tick uniqueness.
        *args: Additional discriminators (player_ids, context strings).

    Returns:
        Float in [0.0, 1.0).
    """
    data = f"{seed}:{tick}:{':'.join(str(a) for a in args)}"
    digest = hashlib.sha256(data.encode("utf-8")).digest()
    # Take first 4 bytes → unsigned 32-bit int → divide by max.
    return struct.unpack(">I", digest[:4])[0] / 0x100000000
