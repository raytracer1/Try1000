"""Ball Physics System (BPS) — exact replica of AgentPitch core/ball_physics_system.py.

Pure-compute module that advances the ball state by exactly one tick. Implements
a constant-velocity model (no acceleration), three-state machine (IN_FLIGHT,
AT_REST, CARRIED), dot-product overshoot detection, and a per-tick ball control
contest using deterministic SHA-256-based draws (hash_01).

BPS owns the canonical ball control formula (BPS F2 supersedes PAM F6). BPS
never mutates GameState — ARE commits the return values per ADR-0009.

All positions in AgentPitch field coords [0,100]×[0,60].
"""

from __future__ import annotations
import math

from try1000_engine.physics.simulation_utils import hash_01

# Field constants (defaults; loaded from config in production).
FIELD_WIDTH = 100.0
FIELD_HEIGHT = 60.0

# Ball control contest activation radius (default; loaded from config in production).
BALL_CONTROL_RANGE = 1.5

# Numerical safety threshold for near-zero velocity (EC-BPS-08).
_VELOCITY_EPSILON = 1e-6


# ---------------------------------------------------------------------------
# Story 001 — Ball motion
# ---------------------------------------------------------------------------


def advance_ball_position(
    ball_position: tuple[float, float],
    ball_velocity: tuple[float, float],
    pass_landing_zone: tuple[float, float] | None,
    field_width: float = FIELD_WIDTH,
    field_height: float = FIELD_HEIGHT,
) -> tuple[tuple[float, float], tuple[float, float], bool]:
    """Advance the ball one tick. Pure compute — no GameState mutation.

    Args:
        ball_position: current ball position (x, y).
        ball_velocity: current ball velocity (vx, vy).
        pass_landing_zone: optional landing zone (x, y) — None for shot path.
        field_width: pitch width (default FIELD_WIDTH=100.0).
        field_height: pitch height (default FIELD_HEIGHT=60.0).

    Returns:
        (new_position, new_velocity, out_of_bounds)

    Behavior:
        - AT_REST or near-zero velocity (‖v‖ < 1e-6): no-op.
        - IN_FLIGHT + landing_zone: advance by velocity, dot-product overshoot snap.
          OOB takes priority over overshoot (per AC-BPS-07).
        - IN_FLIGHT + no landing_zone (shot path): advance by velocity only.
    """
    vx, vy = ball_velocity
    speed_sq = vx * vx + vy * vy

    # AC-BPS-02 + AC-BPS-15: AT_REST or near-zero velocity → no-op.
    if speed_sq < _VELOCITY_EPSILON * _VELOCITY_EPSILON:
        return (ball_position, (0.0, 0.0), False)

    # AC-BPS-03: advance by velocity (constant-velocity model).
    next_x = ball_position[0] + vx
    next_y = ball_position[1] + vy
    next_pos = (next_x, next_y)

    # AC-BPS-06 + AC-BPS-07: OOB check (priority over overshoot).
    oob = (
        next_x < 0.0
        or next_x > field_width
        or next_y < 0.0
        or next_y > field_height
    )
    if oob:
        clamped_x = max(0.0, min(field_width, next_x))
        clamped_y = max(0.0, min(field_height, next_y))
        return ((clamped_x, clamped_y), (0.0, 0.0), True)

    # AC-BPS-04 + AC-BPS-05: dot-product overshoot (only if landing zone set).
    if pass_landing_zone is not None:
        to_lz_x = pass_landing_zone[0] - ball_position[0]
        to_lz_y = pass_landing_zone[1] - ball_position[1]
        dot = vx * to_lz_x + vy * to_lz_y
        if dot <= 0.0:
            # Ball has overshot (or starts at landing zone exactly) → snap.
            return (pass_landing_zone, (0.0, 0.0), False)

    # Normal IN_FLIGHT advance — no overshoot, no OOB.
    return (next_pos, (vx, vy), False)


# ---------------------------------------------------------------------------
# Story 002 — Ball control probability (Formula 2)
# ---------------------------------------------------------------------------


def compute_ball_control_prob(
    player_skill: int,
    distance_to_ball: float,
    ball_speed: float,
    ball_control_range: float = BALL_CONTROL_RANGE,
) -> float:
    """BPS Formula 2 — ball_control_prob = skill / (skill + ball_speed × (1 + distance_ratio)).

    Special case: ball_speed == 0 (AT_REST) → prob = 1.0 (deterministic pickup).

    Args:
        player_skill: PAM skill attribute in [1, 20].
        distance_to_ball: Euclidean distance from player to ball position.
        ball_speed: ‖ball.velocity‖.
        ball_control_range: contest activation radius (default BALL_CONTROL_RANGE=1.5).

    Returns:
        Probability in (0, 1]. AT_REST ball returns 1.0 exactly.
    """
    if ball_speed == 0.0:
        return 1.0

    distance_ratio = min(1.0, max(0.0, distance_to_ball / ball_control_range))
    denominator = player_skill + ball_speed * (1.0 + distance_ratio)
    return player_skill / denominator


def did_control_succeed(
    seed: int,
    tick: int,
    player_id: str,
    ball_control_prob: float,
) -> bool:
    """Deterministic ball control roll using hash_01.

    Args:
        seed: match RNG seed.
        tick: current tick counter.
        player_id: contesting player's ID.
        ball_control_prob: F2 result in (0, 1].

    Returns:
        True iff hash_01(seed, tick, player_id, "ball_control") < ball_control_prob.
    """
    draw = hash_01(seed, tick, player_id, "ball_control")
    return draw < ball_control_prob


def euclidean_distance(
    pos_a: tuple[float, float],
    pos_b: tuple[float, float],
) -> float:
    """Euclidean distance helper for distance_to_ball in F2."""
    dx = pos_a[0] - pos_b[0]
    dy = pos_a[1] - pos_b[1]
    return math.sqrt(dx * dx + dy * dy)


# ---------------------------------------------------------------------------
# Story 003 — advance_ball orchestration (full public API)
# ---------------------------------------------------------------------------


def advance_ball(
    game_state: dict,
    seed: int,
    tick: int,
    field_width: float = FIELD_WIDTH,
    field_height: float = FIELD_HEIGHT,
    ball_control_range: float = BALL_CONTROL_RANGE,
    excluded_pids: set[str] | None = None,
    # ADR shot-deflection knobs.
    deflect_min_speed: float = 2.0,
    deflect_speed_factor_min: float = 0.3,
    deflect_speed_factor_max: float = 0.5,
    # Per-role pickup range.
    range_gk: float | None = None,
    range_outfield: float | None = None,
) -> dict:
    """Public BPS API. Advances ball one tick + ball control contest.

    Composes Story 001 (motion) + Story 002 (ball control probability).

    Args:
        game_state: snapshot dict containing:
            - "ball": dict with "position" (x, y), "velocity" (vx, vy),
              "carrier_id" (str | None), "possession" (str | None).
            - "players": dict[player_id, {position, team, skill, strength, role}].
            - "_pass_landing_zone": (x, y) | None — private snapshot key.
        seed: match RNG seed (for hash_01 determinism).
        tick: current tick counter (for hash_01 determinism).
        field_width / field_height / ball_control_range: tuning knobs.
        excluded_pids: optional set of player_ids to skip in the candidate scan.
        deflect_min_speed / deflect_speed_factor_min / deflect_speed_factor_max:
            shot-deflection tuning knobs.
        range_gk / range_outfield: per-role pickup range overrides.

    Returns:
        {
            "new_position": (x, y),
            "new_velocity": (vx, vy),
            "out_of_bounds": bool,
            "controlled_by": str | None,  # winner's player_id, or None
            "deflected_by": str | None,   # defender who deflected, or None
        }
    """
    ball = game_state["ball"]

    # AC-BPS-01: CARRIED skip — return carrier's position, no motion.
    if ball.get("carrier_id") is not None:
        carrier_id = ball["carrier_id"]
        carrier = game_state["players"].get(carrier_id, {})
        carrier_pos = carrier.get("position", ball["position"])
        return {
            "new_position": carrier_pos,
            "new_velocity": (0.0, 0.0),
            "out_of_bounds": False,
            "controlled_by": carrier_id,
        }

    # Story 001: advance position.
    new_pos, new_vel, oob = advance_ball_position(
        ball["position"],
        ball["velocity"],
        game_state.get("_pass_landing_zone"),
        field_width,
        field_height,
    )

    # AC-BPS-07: OOB priority — no contest this tick.
    if oob:
        return {
            "new_position": new_pos,
            "new_velocity": new_vel,
            "out_of_bounds": True,
            "controlled_by": None,
        }

    # Compute new ball speed for F2 (AT_REST → ball_speed=0 → prob=1.0).
    new_speed = math.sqrt(new_vel[0] ** 2 + new_vel[1] ** 2)

    # Find candidates within their per-role BALL_CONTROL_RANGE of the new
    # ball position. GK uses a wider range; outfield uses a tighter one.
    gk_range = range_gk if range_gk is not None else ball_control_range
    out_range = range_outfield if range_outfield is not None else ball_control_range
    gk_range_sq = gk_range * gk_range
    out_range_sq = out_range * out_range

    excluded = excluded_pids or set()
    candidates: list[tuple[float, str, int, int]] = []
    for pid, pstate in game_state["players"].items():
        if pid in excluded:
            continue
        ppos = pstate.get("position")
        if ppos is None:
            continue
        dx = ppos[0] - new_pos[0]
        dy = ppos[1] - new_pos[1]
        dist_sq = dx * dx + dy * dy
        # Per-role range gate.
        is_gk = pstate.get("role") == "GK"
        eligible_range_sq = gk_range_sq if is_gk else out_range_sq
        if dist_sq <= eligible_range_sq:
            candidates.append((
                dist_sq, pid,
                pstate.get("skill", 1),
                pstate.get("strength", 1),
            ))

    # No candidates → no contest fires.
    if not candidates:
        return {
            "new_position": new_pos,
            "new_velocity": new_vel,
            "out_of_bounds": False,
            "controlled_by": None,
        }

    # AC-BPS-13 (nearest only) + EC-BPS-04 (lexicographic tie-break on player_id).
    candidates.sort(key=lambda c: (c[0], c[1]))
    contest_dist_sq, contest_pid, contest_skill, contest_strength = candidates[0]
    contest_distance = math.sqrt(contest_dist_sq)

    # F2 + hash_01 roll.
    prob = compute_ball_control_prob(
        contest_skill, contest_distance, new_speed, ball_control_range
    )
    success = did_control_succeed(seed, tick, contest_pid, prob)

    if success:
        # Ball stops at the contesting player's position.
        controller_pos = game_state["players"][contest_pid]["position"]
        return {
            "new_position": controller_pos,
            "new_velocity": (0.0, 0.0),
            "out_of_bounds": False,
            "controlled_by": contest_pid,
        }

    # Contest failed — but on a fast ball, defender may still partially
    # deflect it. Enables corners (deflected shot wide of own end line).
    if new_speed >= deflect_min_speed:
        block_factor = (contest_skill + contest_strength) / 2.0
        deflect_prob = block_factor / (block_factor + new_speed * 4.0)
        deflect_draw = hash_01(seed, tick, contest_pid, "shot_deflect")
        if deflect_draw < deflect_prob:
            # DEFLECTED — ball squirts off the defender at reduced speed,
            # biased toward the incoming direction.
            speed_draw = hash_01(seed, tick, contest_pid, "shot_deflect_speed")
            angle_draw = hash_01(seed, tick, contest_pid, "shot_deflect_angle")
            new_ball_speed = new_speed * (
                deflect_speed_factor_min
                + speed_draw * (deflect_speed_factor_max - deflect_speed_factor_min)
            )
            incoming_angle = math.atan2(new_vel[1], new_vel[0])
            # Bias cone center toward wide of goal mouth y.
            ball_y = new_pos[1]
            goal_center_y = field_height / 2.0
            wide_sign = 1.0 if ball_y >= goal_center_y else -1.0
            WIDE_BIAS = math.pi / 6.0  # 30° toward sideline
            biased_center = incoming_angle + WIDE_BIAS * wide_sign
            # ±60° cone around biased center.
            DEFLECT_CONE_HALF = math.pi / 3.0
            deflect_angle = biased_center + (angle_draw - 0.5) * 2.0 * DEFLECT_CONE_HALF
            new_velocity = (
                math.cos(deflect_angle) * new_ball_speed,
                math.sin(deflect_angle) * new_ball_speed,
            )
            defender_pos = game_state["players"][contest_pid]["position"]
            return {
                "new_position": defender_pos,
                "new_velocity": new_velocity,
                "out_of_bounds": False,
                "controlled_by": None,
                "deflected_by": contest_pid,
            }

    # Contest failed and no deflection — ball continues at next_pos.
    return {
        "new_position": new_pos,
        "new_velocity": new_vel,
        "out_of_bounds": False,
        "controlled_by": None,
    }
