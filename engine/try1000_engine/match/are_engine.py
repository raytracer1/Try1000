"""Action Resolution Engine — exact replica of AgentPitch's ARE.

Dict-based state model, AgentPitch field coords [0,100]×[0,60],
AgentPitch Action types (Move/Pass/Shoot/Tackle/Hold).

Architecture matches AgentPitch's:
  src/foundation/action_resolution_engine/engine.py

Two calling conventions are supported:

1. Legacy (engine-native):
     ms = MatchState(snap_dict, seed)
     records = are.resolve_tick(ms, ap_actions, tick)

2. AgentPitch-compatible (new, preferred):
     ms = MatchState(snap_dict, seed)
     are = AreEngine(gsm=ms, seed=42)
     records = are.resolve_tick(tick, history, decide_callback)

The MatchState class provides the GSM-like interface for reading and
mutating state during tick resolution. When using convention (2),
MatchState acts as the "mini-GSM" — it owns the snapshot and all
mutations, just like AgentPitch's GameStateManager.
"""

from __future__ import annotations
import math
from typing import Any

from try1000_engine.match.action import Action, Move, Pass, Shoot, Tackle, Hold
from try1000_engine.physics.simulation_utils import hash_01
from try1000_engine.physics.player_movement_system import resolve_movement
from try1000_engine.physics.ball_physics_system import advance_ball

# ─── Field geometry constants (AgentPitch) ───
FIELD_W = 100.0
FIELD_H = 60.0
GOAL_TOP = 33.66
GOAL_BOTTOM = 26.34
GOAL_CENTER_Y = (GOAL_TOP + GOAL_BOTTOM) / 2.0  # 30.0
GOAL_HALF_H = (GOAL_TOP - GOAL_BOTTOM) / 2.0     # 3.66

# ─── Physics constants (AgentPitch calibrated) ───
BALL_SPEED_PER_POWER = 0.175       # power=20 → 3.5 units/tick = 35 m/s
MOVE_UNIT_PER_TICK = 0.05          # at tick_rate=10, max speed=20 → 1 unit/tick
ACTIVE_SPEED_THRESHOLD = 0.5
DRIBBLE_RANGE = 1.5
TACKLE_RANGE = 2.0
SNAP_MAX_FORCE = 0.20

# ─── Health/stamina ───
HEALTH_MAX = 100.0
HEALTH_DRAIN_FACTOR = 1.0
HEALTH_FLOOR = 30.0

# ─── Foul config ───
TACKLE_FOUL_BASE = 0.10
FOUL_YELLOW_SHARE = 0.25
FOUL_RED_SHARE = 0.05
FREE_KICK_EXCLUSION_RADIUS = 9.15
RESTART_AUTO_KICK_TICKS = 20

# ─── GK config ───
GK_SAVE_WEIGHT = 2.0
GK_CAUGHT_SHARE = 0.60
GK_BLOCK_SPEED_FACTOR = 0.4

# ─── Penalty config ───
PENALTY_GOAL_BASE = 0.60
PENALTY_GOAL_PER_POINT = 0.015
PENALTY_SAVE_PER_POINT = 0.01

# ─── Shot config ───
SHOT_MAX_ANGLE = 0.30  # ±0.30 rad (~17°) spread at skill=1

# ─── Tackle outcome shares ───
TACKLE_CLEAN_SHARE = 0.55
TACKLE_BLOCKED_FLOOR = 0.15
OFFENSIVE_TACKLE_WEIGHT = 0.15

# ─── Penalty area geometry ───
PENALTY_AREA_DEPTH = 16.5
PENALTY_MARK_DIST = 11.0

# ─── Offside config ───
OFFSIDE_ENABLED = True
FOULS_ENABLED = True

# ─── Player separation (ADR-0017) ───
MIN_PLAYER_SEPARATION = 1.0
FORMATION_SNAP_ENABLED = False


# ═══════════════════════════════════════════════════════════════
# MatchState — GSM-like mutable state container
# ═══════════════════════════════════════════════════════════════

class MatchState:
    """GSM-like mutable state that the ARE reads and writes during a tick.

    Starts as a snapshot dict built from engine objects. Gets mutated
    through the phases via the same method names as AgentPitch's GSM.
    After resolve_tick(), the caller syncs changed fields back to
    engine Player/Ball objects.
    """

    def __init__(self, snap: dict, seed: int):
        # Deep-copy the snapshot so mutations don't affect the original.
        self.players: dict[str, dict] = {
            pid: dict(p) for pid, p in snap["players"].items()
        }
        self.ball: dict[str, Any] = dict(snap["ball"])
        self.field: dict[str, Any] = dict(snap["field"])
        self.score: dict[str, int] = dict(snap.get("score", {}))
        self.tick = snap.get("tick", 0)
        self.match_phase = snap.get("match_phase", "in_play")
        self.half = snap.get("half", 1)

        # Internal state (like GSM._pass_landing_zone, etc.)
        self._pass_landing_zone: tuple | None = None
        self._last_touching_team: str | None = None
        self._last_action_ticks: dict[str, int] = {}
        self._yellow_cards: dict[str, int] = {}
        self._health_max: float = HEALTH_MAX

        # Seed for deterministic hash_01.
        self.seed = seed

    # ── Accessors (match GSM property names) ──

    def build_tick_snapshot(self) -> dict:
        """Return the current state as a snapshot dict.

        Matches AgentPitch's GameStateManager.build_tick_snapshot() exactly:
        a dict with keys "tick", "match_phase", "half", "score", "players",
        "ball", "field" — the same shape the ARE passes to decide() callbacks.
        Internal keys (_pass_landing_zone etc.) are excluded.
        """
        return {
            "tick": self.tick,
            "match_phase": self.match_phase,
            "half": self.half,
            "score": dict(self.score),
            "players": {pid: dict(p) for pid, p in self.players.items()},
            "ball": dict(self.ball),
            "field": dict(self.field),
        }

    def build_player_state(self, pid: str) -> dict:
        """Build per-player state dict (matching GSM.build_player_state)."""
        p = self.players.get(pid, {})
        # Compute cooldown_remaining from the unified per-player cooldown.
        # COOLDOWN_TICKS matches AgentPitch's SimulationConfig.action_cooldown_ticks.
        COOLDOWN_TICKS = 10
        last_tick = self._last_action_ticks.get(pid, -10**9)
        cooldown_remaining = max(0, COOLDOWN_TICKS - (self.tick - last_tick))
        return {
            "player_id": pid,
            "team": p.get("team", ""),
            "role": p.get("role", ""),
            "position": p.get("position", (0.0, 0.0)),
            "formation_position": p.get("formation_position", (0.0, 0.0)),
            "has_ball": p.get("has_ball", False),
            "speed": p.get("speed", 10),
            "skill": p.get("skill", 10),
            "strength": p.get("strength", 10),
            "save": p.get("save", 10),
            "discipline": p.get("discipline", 10),
            "dribbling": p.get("dribbling", 10),
            "passing": p.get("passing", 10),
            "shooting": p.get("shooting", 10),
            "stamina": p.get("stamina", 10),
            "offensive": p.get("offensive", 10),
            "penalty": p.get("penalty", 10),
            "current_health": p.get("current_health", HEALTH_MAX),
            "yellow_cards": self._yellow_cards.get(pid, 0),
            # Read cooldown from the player dict (propagated by engine's
            # _build_match_state from Player.cooldown_remaining). When the
            # dict doesn't carry it (legacy tests building MatchState by hand),
            # compute from _last_action_ticks as a fallback.
            "cooldown_remaining": p.get("cooldown_remaining",
                max(0, COOLDOWN_TICKS - (self.tick - last_tick))),
            "formation_zone_phase": p.get("formation_zone_phase", "transitioning"),
        }

    # ── Mutators (match GSM method names) ──

    def apply_move(self, pid: str, new_pos: tuple[float, float]):
        """Apply a single player's new position, clamped to field bounds."""
        x = max(0.0, min(FIELD_W, new_pos[0]))
        y = max(0.0, min(FIELD_H, new_pos[1]))
        if pid in self.players:
            self.players[pid]["position"] = (x, y)

    def transfer_possession(self, from_id: str | None, to_id: str | None):
        """Atomic possession transfer. Matches AgentPitch GSM exactly.

        EC-GSM-03: transfer(None, None) is a no-op.
        """
        if from_id is None and to_id is None:
            return

        # Reset all has_ball flags
        for pid in self.players:
            self.players[pid]["has_ball"] = False

        if to_id is None:
            self.ball["carrier_id"] = None
            self.ball["possession"] = None
        else:
            self.ball["carrier_id"] = to_id
            self.players[to_id]["has_ball"] = True
            self.ball["possession"] = self.players[to_id].get("team")

        if to_id is not None and to_id in self.players:
            self._last_touching_team = self.players[to_id].get("team")

    def update_ball_position(self, new_pos: tuple[float, float],
                             last_touching_team: str | None = None):
        """Set ball position. No clamping — ARE Phase 7 handles OOB.

        Matches AgentPitch GSM: field clamping is intentionally NOT done here
        because ARE Phase 7 handles OOB by detecting BPS's out_of_bounds flag
        and routing through _apply_oob_restart.
        """
        if last_touching_team is not None:
            self._last_touching_team = last_touching_team
        self.ball["position"] = new_pos

    def update_ball_velocity(self, velocity: tuple[float, float]):
        """Set ball velocity."""
        self.ball["velocity"] = velocity

    def set_pass_landing_zone(self, pos: tuple[float, float] | None):
        """Set or clear the pass landing zone."""
        self._pass_landing_zone = pos

    def get_pass_landing_zone(self) -> tuple[float, float] | None:
        """Read the current pass landing zone. BPS calls this every tick."""
        return self._pass_landing_zone

    def record_goal(self, scoring_team: str):
        """Increment score for the given team."""
        self.score[scoring_team] = self.score.get(scoring_team, 0) + 1

    def record_action_cooldown(self, pid: str, tick: int):
        """Mark that a player took a non-trivial action at this tick."""
        self._last_action_ticks[pid] = tick

    def get_last_action_tick(self, pid: str) -> int:
        """Return the tick of the player's last non-trivial action."""
        return self._last_action_ticks.get(pid, -10**9)

    def adjust_health(self, pid: str, delta: float) -> float:
        """Add delta to player's current_health. Clamped to [0, health_max].
        Returns the new value (matching AgentPitch GSM)."""
        if pid not in self.players:
            return 0.0
        ch = self.players[pid].get("current_health", HEALTH_MAX)
        ch = max(0.0, min(HEALTH_MAX, ch + delta))
        self.players[pid]["current_health"] = ch
        return ch

    def restore_all_health(self) -> None:
        """Reset every player's current_health to health_max (matching AgentPitch GSM)."""
        for p in self.players.values():
            p["current_health"] = HEALTH_MAX

    def record_card(self, pid: str, card: str) -> bool:
        """Record a yellow or red card. Returns True if player is sent off.

        Matches AgentPitch GSM: uses transfer_possession to drop the ball
        when a player is sent off, ensuring has_ball and possession are
        correctly updated.
        """
        if card == "red":
            if pid in self.players:
                self.players[pid]["sent_off"] = True
                if self.ball.get("carrier_id") == pid:
                    self.transfer_possession(pid, None)
            return True
        elif card == "yellow":
            self._yellow_cards[pid] = self._yellow_cards.get(pid, 0) + 1
            if self._yellow_cards[pid] >= 2:
                if pid in self.players:
                    self.players[pid]["sent_off"] = True
                    if self.ball.get("carrier_id") == pid:
                        self.transfer_possession(pid, None)
                return True
        return False


# ═══════════════════════════════════════════════════════════════
# Action Resolution Engine
# ═══════════════════════════════════════════════════════════════

class AreEngine:
    """Exact replica of AgentPitch's ActionResolutionEngine.

    Two calling conventions:

    1. Legacy (Phases 1-2 handled externally):
         are = AreEngine(seed=42)
         records = are.resolve_tick(state, actions, tick)

    2. AgentPitch-compatible (Phases 1-7 internal, preferred):
         are = AreEngine(gsm=ms, seed=42)
         records = are.resolve_tick(tick, history, decide_callback)

    When using convention (2), the ARE owns Phase 1 (snapshot via
    self._gsm.build_tick_snapshot()) and Phase 2 (decide via the
    callback), matching AgentPitch's ActionResolutionEngine exactly.
    """

    def __init__(self, seed: int = 42, gsm: MatchState | None = None):
        self.seed = seed
        self._gsm = gsm  # AgentPitch-compatible: gsm injected at construction

        # Tick-local state (per AgentPitch ARE.__init__).
        self._ball_just_passed = False
        self._last_touching_team: str | None = None
        self._last_ball_action_pid: str | None = None
        self._cooldown_blocked: dict[str, str] = {}
        self._offside_pids_at_pass: set[str] = set()
        self._restart_kick_pid: str | None = None
        self._pending_kick: tuple[str, int] | None = None  # (pid, tick)
        self._dribble_records: dict[str, dict] = {}
        self._foul_counts: dict[str, int] = {}
        self._tick_records: dict[str, dict] = {}
        self._stuck_ticks = 0
        self._stuck_anchor: tuple | None = None

    # ═══════════════════════════════
    # Public entry points
    # ═══════════════════════════════

    def resolve_tick(
        self,
        *args,
        **kwargs,
    ) -> dict[str, dict]:
        """Resolve one tick through Phases 1-7 (AgentPitch-compatible) or 3-7 (legacy).

        Two overloads, detected by first positional argument:

        1. Legacy: resolve_tick(state: MatchState, actions: dict, tick: int, history=None)
           Phases 1-2 handled externally (MatchEngine builds state + actions).

        2. AgentPitch-compatible (preferred):
           resolve_tick(tick: int, history: list, decide_callback: Callable)
           Phases 1-2 handled internally via self._gsm and the callback.
        """
        if len(args) >= 1 and isinstance(args[0], MatchState):
            # Legacy path: (state, actions, tick, history)
            state = args[0]
            actions = args[1] if len(args) > 1 else {}
            tick = args[2] if len(args) > 2 else 0
            history = args[3] if len(args) > 3 else None
            return self._resolve_tick_legacy(state, actions, tick, history)
        else:
            # AgentPitch-compatible path: (tick, history, decide_callback)
            tick = args[0] if len(args) > 0 else 0
            history = args[1] if len(args) > 1 else None
            decide_callback = args[2] if len(args) > 2 else None
            return self._resolve_tick_new(tick, history, decide_callback)

    def _resolve_tick_new(
        self,
        tick: int,
        history: list | None,
        decide_callback,
    ) -> dict[str, dict]:
        """AgentPitch-compatible resolve_tick: Phases 1-7 internal.

        Phase 1: build snapshot from self._gsm.
        Phase 2: invoke decide_callback for each player.
        Phases 3-7: validate, move, ball action, tackle, physics.
        """
        gsm = self._gsm
        if gsm is None:
            raise ValueError(
                "AreEngine._resolve_tick_new requires gsm to be set. "
                "Construct as AreEngine(gsm=MatchState(...)) or use "
                "the legacy resolve_tick(state, actions, tick) path."
            )

        # Phase 1: build snapshot (AgentPitch: gsm.build_tick_snapshot()).
        snap = gsm.build_tick_snapshot()

        # Kickoff restart arm (matches AgentPitch ARE._arm_kickoff_restart).
        if snap.get("match_phase") == "kick_off":
            ball = snap.get("ball", {})
            carrier = ball.get("carrier_id")
            if isinstance(carrier, str) and (
                    self._pending_kick is None or self._pending_kick[0] != carrier):
                self._pending_kick = (carrier, tick)

        # Phase 2: callback invocation (AgentPitch: sandbox.execute loop).
        actions: dict[str, Action] = {}
        pending_kicker = self._pending_kick[0] if self._pending_kick else None
        for player in snap["players"].values():
            pid = player["player_id"]
            team = player["team"]
            game_state = {
                **snap,
                "my_player_id": pid,
                "my_team": team,
                "restart_kicker": pending_kicker,
            }
            player_state = gsm.build_player_state(pid)
            actions[pid] = decide_callback(game_state, player_state, history)

        # Phases 3-7: same as legacy path, but using self._gsm as state.
        return self._resolve_phases(gsm, actions, tick)

    def _resolve_tick_legacy(
        self,
        state: MatchState,
        actions: dict[str, Action],
        tick: int,
        history: list[dict] | None = None,
    ) -> dict[str, dict]:
        """Legacy resolve_tick: Phases 3-7 only (Phases 1-2 handled externally).

        Kept for backward compatibility with existing callers and tests.
        """
        return self._resolve_phases(state, actions, tick)

    def _resolve_phases(
        self,
        state: MatchState,
        actions: dict[str, Action],
        tick: int,
    ) -> dict[str, dict]:
        """Core Phases 3-7: validate → move → ball action → tackle → physics.

        Extracted so both legacy and new resolve_tick paths share the same
        Phase 3-7 implementation. Uses `state` (a MatchState) for all
        reads and mutations — when called from the new path, state is
        self._gsm; when called from the legacy path, state is the caller's
        MatchState.
        """
        # Tick-local state reset (per AgentPitch).
        self._tick_state = state  # store for _is_on_cooldown access
        self._ball_just_passed = False
        self._cooldown_blocked = {}
        self._dribble_records = {}
        self._tick_records = {}

        # Validate pending_kick — void if carrier changed.
        if self._pending_kick is not None:
            live_cid = state.ball.get("carrier_id")
            if live_cid != self._pending_kick[0]:
                self._pending_kick = None

        # Phase 3: Action Validation.
        validated, reasons = self._validate_actions(actions, state, tick)

        # Phase 4: Movement + Dribble Contest.
        dribble_consumed = self._resolve_phase4(validated, state, tick)

        # Find current carrier after Phase 4.
        current_carrier = state.ball.get("carrier_id")

        # Phase 5: Ball Actions (Pass / Shoot).
        ball_action_records = self._resolve_phase5(validated, state, tick, current_carrier)

        # Phase 6: Tackle Resolution.
        tackle_records = self._resolve_phase6(validated, state, tick)

        # Phase 7: Ball Physics + OOB + Goal + Offside.
        bp_records, goal_records = self._resolve_phase7(state, tick)

        # Build action records (matching AgentPitch merge order).
        action_records: dict[str, dict] = {}
        for pid, action in validated.items():
            record: dict[str, Any] = {
                "action": type(action).__name__,
                "result": reasons.get(pid, "ok"),
                "tick": tick,
            }
            if hasattr(action, 'power') and reasons.get(pid) == "power_capped":
                record["effective_power"] = action.power
            if reasons.get(pid) == "restart_auto_kick":
                record["restart_auto_kick"] = True
            if pid in self._cooldown_blocked:
                record["intended_action"] = self._cooldown_blocked[pid]
            action_records[pid] = record

        # Merge dribble records.
        for pid, dr in self._dribble_records.items():
            if pid in action_records:
                action_records[pid].update(dr)

        # Merge ball action records.
        for pid, br in ball_action_records.items():
            if pid not in action_records:
                action_records[pid] = {"action": "Hold", "result": "ok", "tick": tick}
            action_records[pid].update(br)

        # Merge tackle records.
        for pid, tr in tackle_records.items():
            if pid not in action_records:
                action_records[pid] = {"action": "Hold", "result": "ok", "tick": tick}
            action_records[pid].update(tr)

        # Merge ball physics records.
        for pid, bpr in bp_records.items():
            if pid not in action_records:
                action_records[pid] = {"action": "Hold", "result": "ok", "tick": tick}
            action_records[pid].update(bpr)

        # Merge goal records.
        for pid, gr in goal_records.items():
            if pid not in action_records:
                action_records[pid] = {"action": "Hold", "result": "ok", "tick": tick}
            action_records[pid].update(gr)

        # Stamina drain.
        self._apply_health_drain(validated, state)

        # Stalemate check.
        self._check_stalemate(state, tick)

        return action_records

    # ═══════════════════════════════
    # Phase 3: Action Validation
    # ═══════════════════════════════

    def _validate_actions(
        self, actions: dict[str, Action], state: MatchState, tick: int = 0,
    ) -> tuple[dict[str, Action], dict[str, str]]:
        """AgentPitch Phase 3: per-action-type validation/normalization.

        Checks: cooldown, range clamp, power cap, non-finite guard,
        zero-move substitution, tackle target validation, free-kick
        taker enforcement.
        """
        validated: dict[str, Action] = {}
        reasons: dict[str, str] = {}
        carrier_id = state.ball.get("carrier_id")

        to_record_cooldowns: list[str] = []

        for pid, action in actions.items():
            player = state.players.get(pid)
            if player is None or player.get("sent_off", False):
                continue

            # ── Free-kick taker enforcement ──
            pending = self._pending_kick
            is_pending_kicker = pending is not None and pid == pending[0]
            if is_pending_kicker and not isinstance(action, (Pass, Shoot)):
                if tick - pending[1] >= RESTART_AUTO_KICK_TICKS:
                    # Auto-kick: pass to nearest teammate.
                    target = self._nearest_teammate_pos(pid, state)
                    if target:
                        action = Pass(target_pos=target, power=12)
                        reasons[pid] = "restart_auto_kick"
                    else:
                        validated[pid] = Hold()
                        reasons[pid] = "restart_must_kick"
                        continue
                else:
                    if not isinstance(action, Hold):
                        validated[pid] = Hold()
                        reasons[pid] = "restart_must_kick"
                        continue

            # ── Unified cooldown check ──
            if isinstance(action, (Pass, Shoot, Tackle)):
                if self._is_on_cooldown(pid, tick) and not is_pending_kicker:
                    validated[pid] = Hold()
                    reasons[pid] = "cooldown_blocked"
                    self._cooldown_blocked[pid] = type(action).__name__
                    continue

            # ── Move: non-finite guard + zero-move substitution ──
            if isinstance(action, Move):
                if not (_is_finite_number(action.dx)
                        and _is_finite_number(action.dy)
                        and _is_finite_number(action.speed)):
                    validated[pid] = Hold()
                    reasons[pid] = "non_finite_move"
                    continue
                speed = max(0.0, min(1.0, action.speed))
                if speed == 0.0 or (action.dx == 0.0 and action.dy == 0.0):
                    validated[pid] = Hold()
                    reasons[pid] = "zero_move_substituted"
                else:
                    validated[pid] = Move(dx=action.dx, dy=action.dy, speed=speed)
                continue

            # ── Pass: power cap by strength + range clamp ──
            if isinstance(action, Pass):
                if pid != carrier_id:
                    validated[pid] = Hold()
                    reasons[pid] = "not_carrier"
                    continue
                if not (isinstance(action.target_pos, (tuple, list))
                        and len(action.target_pos) == 2
                        and _is_finite_number(action.target_pos[0])
                        and _is_finite_number(action.target_pos[1])):
                    validated[pid] = Hold()
                    reasons[pid] = "invalid_target_pos"
                    continue
                p_strength = player.get("strength", 10)
                floored = max(1, action.power)
                effective = min(floored, p_strength)
                tx = max(1.0, min(FIELD_W - 1.0, action.target_pos[0]))
                ty = max(1.0, min(FIELD_H - 1.0, action.target_pos[1]))
                validated[pid] = Pass(target_pos=(tx, ty), power=effective)
                if effective < action.power:
                    reasons[pid] = "power_capped"
                to_record_cooldowns.append(pid)
                continue

            # ── Shoot: power cap by strength ──
            if isinstance(action, Shoot):
                if pid != carrier_id:
                    validated[pid] = Hold()
                    reasons[pid] = "not_carrier"
                    continue
                if not _is_finite_number(action.angle):
                    validated[pid] = Hold()
                    reasons[pid] = "invalid_angle"
                    continue
                p_strength = player.get("strength", 10)
                floored = max(1, action.power)
                effective = min(floored, p_strength)
                validated[pid] = Shoot(angle=action.angle, power=effective)
                if effective < action.power:
                    reasons[pid] = "power_capped"
                to_record_cooldowns.append(pid)
                continue

            # ── Tackle: target validation ──
            if isinstance(action, Tackle):
                tid = action.target_player_id
                target_player = state.players.get(tid)
                if target_player is None:
                    validated[pid] = Hold()
                    reasons[pid] = "unknown_target"
                    continue
                if target_player.get("team") == player.get("team"):
                    validated[pid] = Hold()
                    reasons[pid] = "same_team_tackle"
                    continue
                validated[pid] = action
                to_record_cooldowns.append(pid)
                continue

            # Hold or other → pass through.
            validated[pid] = action

        # Apply cooldown recordings.
        for pid in to_record_cooldowns:
            state.record_action_cooldown(pid, tick)

        return validated, reasons

    def _is_on_cooldown(self, pid: str, current_tick: int) -> bool:
        """True if player's cooldown hasn't expired."""
        COOLDOWN_TICKS = 10
        last = self._last_action_tick_val(pid)
        return current_tick - last < COOLDOWN_TICKS

    def _last_action_tick_val(self, pid: str) -> int:
        """Get last action tick for a player from MatchState's cooldown tracking.

        Reads from the MatchState's _last_action_ticks (set by record_action_cooldown).
        Falls back to ARE's internal _last_touch_tick for backward compatibility
        with tests that don't set up MatchState correctly.
        """
        state = getattr(self, '_tick_state', None)
        if state is not None and hasattr(state, '_last_action_ticks'):
            return state._last_action_ticks.get(pid, -10**9)
        return getattr(self, '_last_touch_tick', {}).get(pid, -10**9)

    # ─── Player separation (ADR-0017) ───

    def _min_player_separation(self) -> float:
        """Per ADR-0017: read min separation. Returns module-level constant
        (disabled by default = 0.0, matching AgentPitch config default)."""
        return MIN_PLAYER_SEPARATION

    def _enforce_player_separation(
        self,
        positions: dict,
        min_sep: float,
        field_w: float,
        field_h: float,
    ) -> dict:
        """Per ADR-0017: single-pass pairwise separation. Players within
        min_sep of each other are pushed apart equally along the
        center-to-center vector. Field-boundary clamp applied per push.

        Deterministic: iterates pairs in sorted player_id order. For 10
        players in a sparse 100x60 field, single pass converges; rare
        cascade edges self-correct on the next tick.
        """
        out = {pid: pos for pid, pos in positions.items()}
        pids = sorted(out.keys())

        for i in range(len(pids)):
            pid_i = pids[i]
            for j in range(i + 1, len(pids)):
                pid_j = pids[j]
                xi, yi = out[pid_i]
                xj, yj = out[pid_j]
                dx = xj - xi
                dy = yj - yi
                d = (dx * dx + dy * dy) ** 0.5
                if d >= min_sep:
                    continue
                # Compute push direction; handle exact-overlap edge case.
                if d < 1e-6:
                    ux, uy = 1.0, 0.0
                    d = 1e-6
                else:
                    ux = dx / d
                    uy = dy / d
                overlap = min_sep - d
                push = overlap / 2.0
                # Push apart, clamp to field.
                out[pid_i] = (
                    max(0.0, min(field_w, xi - ux * push)),
                    max(0.0, min(field_h, yi - uy * push)),
                )
                out[pid_j] = (
                    max(0.0, min(field_w, xj + ux * push)),
                    max(0.0, min(field_h, yj + uy * push)),
                )
        return out

    # ═══════════════════════════════
    # Phase 4: Movement
    # ═══════════════════════════════

    def _resolve_phase4(
        self, validated: dict[str, Action], state: MatchState, tick: int,
    ) -> set[str]:
        """Phase 4: Movement compute-all-then-commit + dribble contest.

        Returns dribble_consumed — defender ids consumed by dribble.

        Matches AgentPitch's structure:
        - Separate loops for Move and Hold actions
        - Hold actions only recorded if position actually changed
        - Player separation (ADR-0017) before commit
        - snap_enabled toggle for formation snap
        """
        snap = {"players": state.players, "ball": state.ball,
                "field": state.field, "match_phase": state.match_phase}
        snap_enabled = FORMATION_SNAP_ENABLED

        move_results: dict[str, tuple[tuple[float, float], str | None]] = {}

        # ── Move actions (ADR-0022 amendment d) ──
        for pid, action in validated.items():
            if isinstance(action, Move):
                action_dict = {
                    "type": "move",
                    "dx": action.dx,
                    "dy": action.dy,
                    "speed": action.speed,
                }
                player_state = state.build_player_state(pid)
                final_pos, dribble_target = resolve_movement(
                    pid, action_dict, player_state, snap,
                    snap_enabled=snap_enabled,
                )
                move_results[pid] = (final_pos, dribble_target)

        # ── Hold actions (ADR-0022 amendment d, option B) ──
        # Feed Hold through PMS so soft snap can drift idle players toward
        # their dynamic anchor. Only record if position actually changed.
        for pid, action in validated.items():
            if isinstance(action, Hold):
                action_dict = {"type": "hold"}
                player_state = state.build_player_state(pid)
                final_pos, dribble_target = resolve_movement(
                    pid, action_dict, player_state, snap,
                    snap_enabled=snap_enabled,
                )
                # Only record if position actually changed (avoid no-op apply_move).
                current_pos = player_state["position"]
                if final_pos != current_pos:
                    move_results[pid] = (final_pos, dribble_target)

        # ── Player separation pass (ADR-0017) ──
        # When enabled: build full set of 10 players' final positions,
        # apply pairwise separation, then commit ALL 10 (non-movers may
        # have shifted from incoming pushes). When disabled: commit only movers.
        min_sep = self._min_player_separation()
        if min_sep > 0:
            all_pos: dict[str, tuple[float, float]] = {}
            for pid_key, pdata in state.players.items():
                if pid_key in move_results:
                    all_pos[pid_key] = move_results[pid_key][0]
                else:
                    all_pos[pid_key] = pdata.get("position", (0.0, 0.0))

            all_pos = self._enforce_player_separation(
                all_pos, min_sep, FIELD_W, FIELD_H)
            # Update move_results so dribble contest uses post-separation positions.
            for pid_key in list(move_results.keys()):
                _, dt = move_results[pid_key]
                move_results[pid_key] = (all_pos[pid_key], dt)

            # Commit ALL 10 — non-movers may have shifted.
            for pid_key, pos in all_pos.items():
                state.apply_move(pid_key, pos)
        else:
            # Separation disabled: commit only movers.
            for pid_key, (final_pos, _) in move_results.items():
                state.apply_move(pid_key, final_pos)

        # ── Dribble contests (after all moves committed) ──
        dribble_consumed: set[str] = set()
        for pid, (_, dribble_target) in move_results.items():
            if dribble_target is None:
                continue
            carrier = state.players.get(pid, {})
            defender = state.players.get(dribble_target, {})
            attacker_power = (carrier.get("dribbling", 10) + carrier.get("speed", 10)) / 2
            prob = attacker_power / (attacker_power + defender.get("strength", 10))
            draw = hash_01(state.seed, tick, pid, dribble_target)
            if draw >= prob:  # FAIL → defender steals.
                state.transfer_possession(pid, dribble_target)
                self._dribble_records[pid] = {
                    "dribble_result": "failed",
                    "dribble_target": dribble_target,
                }
            else:  # SUCCESS.
                self._dribble_records[pid] = {
                    "dribble_result": "success",
                    "dribble_target": dribble_target,
                }
            dribble_consumed.add(dribble_target)

        self.dribble_consumed = dribble_consumed
        self.move_results = move_results
        return dribble_consumed

    # ═══════════════════════════════
    # Phase 5: Ball Actions (Pass / Shoot)
    # ═══════════════════════════════

    def _resolve_phase5(
        self, validated: dict[str, Action], state: MatchState,
        tick: int, current_carrier: str | None,
    ) -> dict[str, dict]:
        """Phase 5: Pass and Shoot resolution with skill-based deviation."""
        if current_carrier is None:
            return {}

        action = validated.get(current_carrier)
        if not isinstance(action, (Pass, Shoot)):
            return {}

        passer = state.players.get(current_carrier, {})
        skill = passer.get("skill", 10)
        passing_attr = passer.get("passing", skill)
        shooting_attr = passer.get("shooting", skill)
        h_factor = self._health_factor(state, current_carrier)

        # Effective skill (ADR-0018).
        pass_eff = (2.0 * passing_attr + skill) / 3.0 * h_factor
        shot_eff = (2.0 * shooting_attr + skill) / 3.0 * h_factor

        if isinstance(action, Pass):
            return self._resolve_pass(state, passer, action, pass_eff, tick)
        else:
            return self._resolve_shoot(state, passer, action, shot_eff, tick)

    def _resolve_pass(
        self, state: MatchState, passer: dict, action: Pass,
        eff_skill: float, tick: int,
    ) -> dict[str, dict]:
        """ADR-0018 F1: continuous pass deviation."""
        pid = passer["player_id"]
        spread = max(0.0, 1.0 - eff_skill / 20.0) ** 0.7

        # Deviation.
        dev_mag = spread * 8.0 * hash_01(state.seed, tick, pid, "pass_dev_mag")
        dev_ang = hash_01(state.seed, tick, pid, "pass_dev_angle") * 2 * math.pi
        landing = (
            action.target_pos[0] + math.cos(dev_ang) * dev_mag,
            action.target_pos[1] + math.sin(dev_ang) * dev_mag,
        )

        # Ball velocity toward landing.
        passer_pos = passer["position"]
        dx = landing[0] - passer_pos[0]
        dy = landing[1] - passer_pos[1]
        dist = math.sqrt(dx * dx + dy * dy)

        if dist < 1e-6:
            # Default toward opponent goal.
            opp_goal_x = state.field.get("team_b_goal_x" if passer.get("team") == "team_a" else "team_a_goal_x", 100.0)
            dx = opp_goal_x - passer_pos[0]
            dy = 0.0
            dist = abs(dx) or 1.0

        ball_speed = action.power * BALL_SPEED_PER_POWER
        unit = (dx / dist, dy / dist)
        state.update_ball_velocity((unit[0] * ball_speed, unit[1] * ball_speed))
        state.set_pass_landing_zone(landing)
        state.transfer_possession(pid, None)
        self._ball_just_passed = True
        self._last_touching_team = passer.get("team")
        self._last_ball_action_pid = pid
        self._last_ball_action_tick: dict[str, int] = getattr(self, '_last_ball_action_tick', {})
        if not hasattr(self, '_last_ball_action_tick'):
            # For BPS deflection tracking: record tick of ball action.
            pass

        # Pending kick consumed.
        if self._pending_kick is not None and pid == self._pending_kick[0]:
            self._pending_kick = None

        # Offside capture (Law 11: exempt for goal kick/throw-in/corner).
        if OFFSIDE_ENABLED:
            if pid == self._restart_kick_pid:
                self._offside_pids_at_pass.clear()
            else:
                self._capture_offside_at_pass(state, passer)
        self._restart_kick_pid = None

        return {pid: {"action": "Pass", "result": "ok", "landing_pos": landing}}

    def _resolve_shoot(
        self, state: MatchState, passer: dict, action: Shoot,
        eff_skill: float, tick: int,
    ) -> dict[str, dict]:
        """ADR-0018: shoot toward goal mouth center + skill spread."""
        pid = passer["player_id"]
        team = passer.get("team", "")
        spread = max(0.0, 1.0 - eff_skill / 20.0) ** 0.7

        # Goal center (AgentPitch: goal mouth center).
        opp_goal_x = state.field.get(
            "team_b_goal_x" if team == "team_a" else "team_a_goal_x", 100.0)
        goal_center = (opp_goal_x, GOAL_CENTER_Y)
        passer_pos = passer["position"]

        base_angle = math.atan2(goal_center[1] - passer_pos[1],
                                goal_center[0] - passer_pos[0])
        strategy_intent = math.radians(action.angle)

        # Skill-based angular spread.
        angular_spread = spread * SHOT_MAX_ANGLE
        skill_dev = (hash_01(state.seed, tick, pid, "shot_dev_angle") - 0.5) * 2.0 * angular_spread

        final_angle = base_angle + strategy_intent + skill_dev
        ball_speed = action.power * BALL_SPEED_PER_POWER

        state.update_ball_velocity(
            (math.cos(final_angle) * ball_speed, math.sin(final_angle) * ball_speed))
        state.set_pass_landing_zone(None)
        state.transfer_possession(pid, None)
        self._ball_just_passed = True
        self._last_touching_team = team
        self._last_ball_action_pid = pid

        # Pending kick consumed.
        if self._pending_kick is not None and pid == self._pending_kick[0]:
            self._pending_kick = None

        self._offside_pids_at_pass.clear()
        self._restart_kick_pid = None

        return {pid: {"action": "Shoot", "result": "ok"}}

    # ═══════════════════════════════
    # Phase 6: Tackle Resolution
    # ═══════════════════════════════

    def _resolve_phase6(
        self, validated: dict[str, Action], state: MatchState, tick: int,
    ) -> dict[str, dict]:
        """Phase 6: Tackle resolution — strength-based 3-outcome contest."""
        tackle_records: dict[str, dict] = {}

        tacklers = [
            (pid, action) for pid, action in validated.items()
            if isinstance(action, Tackle) and pid not in self.dribble_consumed
        ]
        tacklers.sort(key=lambda x: x[0])

        for tackler_id, action in tacklers:
            target_id = action.target_player_id
            tackler = state.players.get(tackler_id, {})
            target = state.players.get(target_id, {})

            if not tackler or not target:
                continue

            # Range check — use POST-COMMIT positions from Phase 4 (ADR-0017).
            if hasattr(self, 'move_results') and tackler_id in self.move_results:
                tp = self.move_results[tackler_id][0]
            else:
                tp = tackler.get("position", (0.0, 0.0))

            if hasattr(self, 'move_results') and target_id in self.move_results:
                op = self.move_results[target_id][0]
            else:
                op = target.get("position", (0.0, 0.0))

            dist = math.sqrt((tp[0] - op[0])**2 + (tp[1] - op[1])**2)
            if dist > TACKLE_RANGE:
                tackle_records[tackler_id] = {"action": "Tackle", "result": "out_of_range"}
                continue

            # Ball must be with target.
            if state.ball.get("carrier_id") != target_id:
                tackle_records[tackler_id] = {"action": "Tackle", "result": "no_ball"}
                continue

            # Settled-possession grace.
            grace = 3
            last_touch_tick = state.get_last_action_tick(target_id)
            if tick - last_touch_tick < grace:
                tackle_records[tackler_id] = {"action": "Tackle", "result": "no_op_settled"}
                continue

            # Pending free kick taker is untacklable.
            if self._pending_kick is not None and target_id == self._pending_kick[0]:
                tackle_records[tackler_id] = {"action": "Tackle", "result": "no_op_restart_pending"}
                continue

            # Foul check (preempts tackle outcome).
            if FOULS_ENABLED:
                t_off = tackler.get("offensive", 10)
                foul_prob = TACKLE_FOUL_BASE * (t_off / 10.0)
                foul_draw = hash_01(state.seed, tick, tackler_id, "foul")
                if foul_draw < foul_prob:
                    self._resolve_foul(state, tackler_id, target_id, tick, tackle_records)
                    continue

            # PAM F4: tackle contest.
            t_str = tackler.get("strength", 10)
            t_off = tackler.get("offensive", 10)
            t_str *= 1.0 + OFFENSIVE_TACKLE_WEIGHT * (t_off - 10) / 10.0
            t_str *= self._health_factor(state, tackler_id)

            o_str = target.get("strength", 10)
            o_str *= self._health_factor(state, target_id)

            prob = t_str / (t_str + o_str) if (t_str + o_str) > 0 else 0.5
            controlled_prob = prob * TACKLE_CLEAN_SHARE
            blocked_prob = prob * (1.0 - TACKLE_CLEAN_SHARE) + TACKLE_BLOCKED_FLOOR
            if controlled_prob + blocked_prob > 1.0:
                blocked_prob = max(0.0, 1.0 - controlled_prob)

            draw = hash_01(state.seed, tick, tackler_id, target_id, "tackle")

            if draw < controlled_prob:
                # Controlled: clean take.
                if state.ball.get("carrier_id") == target_id:
                    state.transfer_possession(target_id, tackler_id)
                    tackle_records[tackler_id] = {"action": "Tackle", "result": "controlled"}
                else:
                    tackle_records[tackler_id] = {"action": "Tackle", "result": "no_op_carrier_changed"}
            elif draw < controlled_prob + blocked_prob:
                # Blocked: ball squirts loose.
                if state.ball.get("carrier_id") == target_id:
                    state.transfer_possession(target_id, None)
                    ang = hash_01(state.seed, tick, tackler_id, "tackle_block_angle") * 2 * math.pi
                    spd = 1.0 + hash_01(state.seed, tick, tackler_id, "tackle_block_speed") * 2.0
                    state.update_ball_velocity((math.cos(ang) * spd, math.sin(ang) * spd))
                    state.set_pass_landing_zone(None)
                    state._last_touching_team = tackler.get("team")
                    tackle_records[tackler_id] = {"action": "Tackle", "result": "blocked"}
                else:
                    tackle_records[tackler_id] = {"action": "Tackle", "result": "no_op_carrier_changed"}
            else:
                tackle_records[tackler_id] = {"action": "Tackle", "result": "failed"}

        return tackle_records

    def _resolve_foul(
        self, state: MatchState, tackler_id: str, target_id: str,
        tick: int, tackle_records: dict,
    ):
        """Issue #38 — IFAB Law 12: foul severity + restart."""
        tackler = state.players.get(tackler_id, {})
        target = state.players.get(target_id, {})
        fouling_team = tackler.get("team", "")
        fouled_team = target.get("team", "")

        # Foul spot = carrier position.
        foul_spot = target.get("position", (0.0, 0.0))

        # Severity roll.
        sev_draw = hash_01(state.seed, tick, tackler_id, "foul_severity")
        if sev_draw < FOUL_RED_SHARE:
            severity, card = "excessive_force", "red"
        elif sev_draw < FOUL_RED_SHARE + FOUL_YELLOW_SHARE:
            severity, card = "reckless", "yellow"
        else:
            severity, card = "careless", None

        sent_off = False
        if card is not None:
            sent_off = state.record_card(tackler_id, card)

        # Reverse tackle — give ball to fouled team.
        state.transfer_possession(None, target_id)
        state.update_ball_velocity((0.0, 0.0))
        state.set_pass_landing_zone(None)
        self._offside_pids_at_pass.clear()

        # Restart: penalty vs free kick.
        if self._is_in_penalty_area(foul_spot, fouling_team, state):
            self._resolve_penalty_kick(state, fouling_team, fouled_team,
                                       foul_spot, tackler_id, tick,
                                       tackle_records, card=card, sent_off=sent_off)
        else:
            self._apply_foul_free_kick(state, fouling_team, fouled_team,
                                       foul_spot, tackler_id, tick,
                                       tackle_records, card=card, sent_off=sent_off)

        tackle_records[tackler_id] = {
            "action": "Tackle", "result": "foul",
            "foul_severity": severity, "fouled_player": target_id,
        }
        if card is not None:
            tackle_records[tackler_id]["card"] = card
        if sent_off:
            tackle_records[tackler_id]["sent_off"] = True

    # ═══════════════════════════════
    # Phase 7: Ball Physics + OOB + Goal + Offside
    # ═══════════════════════════════

    def _resolve_phase7(
        self, state: MatchState, tick: int,
    ) -> tuple[dict[str, dict], dict[str, dict]]:
        """Phase 7: BPS advance_ball, OOB, offside, goal, GK saves."""
        ball = state.ball
        bp_records: dict[str, dict] = {}
        goal_records: dict[str, dict] = {}

        carrier_id = ball.get("carrier_id")

        # Carried ball: snap position, check goal.
        if carrier_id is not None:
            self._offside_pids_at_pass.clear()
            carrier = state.players.get(carrier_id, {})
            carrier_pos = carrier.get("position")
            if carrier_pos:
                state.update_ball_position(carrier_pos)
                # Carrier at goal line within goal mouth → goal or GK save.
                if self._is_goal_line_crossed(carrier_pos, state):
                    defending = self._get_defending_team(carrier_pos, state)
                    carrier_team = carrier.get("team")
                    if carrier_team is not None and carrier_team != defending:
                        gk_id = self._find_goalkeeper(defending, state)
                        if gk_id is not None:
                            outcome, reason = self._attempt_goalkeeper_save(
                                gk_id, carrier_pos, (0.0, 0.0), state, tick)
                            if outcome in ("caught", "blocked"):
                                state.update_ball_velocity((0.0, 0.0))
                                state.transfer_possession(carrier_id, gk_id)
                                self._snap_ball_to_carrier(state, gk_id)
                                self._last_ball_action_pid = None
                                state._last_touching_team = defending
                                return bp_records, {gk_id: {
                                    "goalkeeper_save": outcome,
                                    "reason": reason,
                                    "saved_from": carrier_id,
                                }}
                        # No keeper or save missed → goal.
                        state.update_ball_velocity((0.0, 0.0))
                        state.transfer_possession(carrier_id, None)
                        self._record_goal(state, defending)
                        self._last_ball_action_pid = None
                        return bp_records, {"system": {
                            "goal_scored": self._get_attacking_team(defending),
                            "scored_by": carrier_id,
                            "reason": "dribbled_in",
                        }}
            return bp_records, goal_records

        # No carrier: run BPS (unless ball was just passed).
        if self._ball_just_passed:
            return bp_records, goal_records

        # Build BPS-compatible game_state from MatchState.
        bps_gs = {
            "ball": state.ball,
            "players": state.players,
            "field": state.field,
            "_pass_landing_zone": state._pass_landing_zone,
        }

        # Cooldown exclusion.
        excluded: set[str] = set()
        for pid in state.players:
            if self._is_on_cooldown(pid, tick):
                excluded.add(pid)

        result = advance_ball(
            bps_gs, state.seed, tick,
            range_gk=1.5, range_outfield=1.0,
            excluded_pids=excluded,
        )

        # Commit BPS results.
        state.update_ball_position(result["new_position"])
        state.update_ball_velocity(result["new_velocity"])

        # Deflection tracking.
        deflector = result.get("deflected_by")
        if deflector is not None:
            deflector_team = state.players.get(deflector, {}).get("team")
            if deflector_team:
                state._last_touching_team = deflector_team
            state.record_action_cooldown(deflector, tick)
            self._offside_pids_at_pass.clear()
            bp_records[deflector] = {
                "shot_deflection": True,
                "deflected_from": self._last_ball_action_pid,
            }

        # Goal check (precedes OOB).
        if self._is_goal_line_crossed(result["new_position"], state):
            self._offside_pids_at_pass.clear()
            shooter_id = self._last_ball_action_pid
            defending = self._get_defending_team(result["new_position"], state)
            gk_id = self._find_goalkeeper(defending, state)

            if gk_id is not None:
                save_outcome, reason = self._attempt_goalkeeper_save(
                    gk_id, result["new_position"], result["new_velocity"], state, tick)

                if save_outcome == "caught":
                    state.update_ball_velocity((0.0, 0.0))
                    state.transfer_possession(None, gk_id)
                    self._snap_ball_to_carrier(state, gk_id)
                    self._last_ball_action_pid = None
                    state._last_touching_team = defending
                    goal_records[gk_id] = {
                        "goalkeeper_save": "success", "reason": reason,
                        "saved_from": shooter_id,
                    }
                elif save_outcome == "blocked":
                    # Push-wide (corner) vs rebound.
                    ball_y = result["new_position"][1]
                    post_proximity = min(1.0, abs(ball_y - GOAL_CENTER_Y) / max(1e-6, GOAL_HALF_H))
                    push_wide_prob = 0.45 + 0.45 * post_proximity
                    oob_draw = hash_01(state.seed, tick, gk_id, "save_block_oob")

                    team_goal_x = state.field.get(
                        f"{defending}_goal_x", 0.0 if defending == "team_a" else 100.0)
                    away_x_sign = 1.0 if team_goal_x < FIELD_W / 2.0 else -1.0

                    if oob_draw < push_wide_prob:
                        # Push-wide → corner.
                        side_sign = 1.0 if ball_y >= GOAL_CENTER_Y else -1.0
                        post_y = GOAL_CENTER_Y + side_sign * GOAL_HALF_H
                        oob_y = post_y + side_sign * 0.5
                        oob_y = max(0.0, min(FIELD_H, oob_y))
                        oob_x = 0.0 if team_goal_x <= 0.001 else FIELD_W
                        state.update_ball_position((oob_x, oob_y))
                        state.update_ball_velocity((0.0, 0.0))
                        state.set_pass_landing_zone(None)
                        state._last_touching_team = defending
                        self._last_ball_action_pid = None
                        self._apply_oob_restart(state, (oob_x, oob_y), bp_records, tick)
                        goal_records[gk_id] = {
                            "goalkeeper_save": "blocked", "reason": reason,
                            "saved_from": shooter_id, "push_wide": True,
                        }
                    else:
                        # Rebound into box.
                        pre_vel = result.get("_pre_vel", result["new_velocity"])
                        incoming_speed = math.sqrt(pre_vel[0]**2 + pre_vel[1]**2)
                        new_speed = max(2.0, incoming_speed * GK_BLOCK_SPEED_FACTOR)
                        incoming_angle = math.atan2(pre_vel[1], pre_vel[0])
                        reverse_angle = incoming_angle + math.pi
                        cone_draw = hash_01(state.seed, tick, gk_id, "save_block_angle")
                        REBOUND_CONE_HALF = math.pi / 3.0
                        angle = reverse_angle + (cone_draw - 0.5) * 2.0 * REBOUND_CONE_HALF
                        state.update_ball_velocity(
                            (math.cos(angle) * new_speed, math.sin(angle) * new_speed))
                        # Nudge away from goal line (AgentPitch).
                        deflected = (result["new_position"][0] + away_x_sign * 3.0,
                                     result["new_position"][1])
                        deflected = (max(0.0, min(FIELD_W, deflected[0])), deflected[1])
                        state.update_ball_position(deflected)
                        state.set_pass_landing_zone(None)
                        state._last_touching_team = defending
                        goal_records[gk_id] = {
                            "goalkeeper_save": "blocked", "reason": reason,
                            "saved_from": shooter_id, "push_wide": False,
                        }
                else:  # missed
                    state.update_ball_velocity((0.0, 0.0))
                    state.set_pass_landing_zone(None)
                    self._record_goal(state, defending)
                    self._last_ball_action_pid = None
                    goal_records[gk_id] = {
                        "goalkeeper_save": "failed", "reason": reason,
                        "goal_scored": self._get_attacking_team(defending),
                        "scored_by": shooter_id,
                    }
            else:
                # No goalkeeper — automatic goal.
                state.update_ball_velocity((0.0, 0.0))
                state.set_pass_landing_zone(None)
                self._record_goal(state, defending)
                self._last_ball_action_pid = None
                goal_records["system"] = {
                    "goal_scored": self._get_attacking_team(defending),
                    "scored_by": shooter_id,
                    "reason": "no_goalkeeper",
                }
            return bp_records, goal_records

        # OOB handling (only if not a goal).
        if result["out_of_bounds"]:
            state.set_pass_landing_zone(None)
            self._apply_oob_restart(state, result["new_position"], bp_records, tick)
            return bp_records, goal_records

        # Ball pickup + offside enforcement.
        pickup_id = result.get("controlled_by")
        if pickup_id is not None and pickup_id in self._offside_pids_at_pass:
            self._offside_pids_at_pass.clear()
            self._apply_offside_free_kick(state, pickup_id, bp_records, tick)
            return bp_records, goal_records
        if pickup_id is not None:
            self._offside_pids_at_pass.clear()
            state.transfer_possession(None, pickup_id)
            state.record_action_cooldown(pickup_id, tick)
            self._snap_ball_to_carrier(state, pickup_id)
            self._last_ball_action_pid = None
            picker_team = state.players.get(pickup_id, {}).get("team")
            if picker_team:
                state._last_touching_team = picker_team
            bp_records[pickup_id] = {"ball_pickup": "success", "reason": "ok"}

        return bp_records, goal_records

    # ─── OOB Handling ───

    def _apply_oob_restart(
        self, state: MatchState, oob_pos: tuple[float, float],
        records: dict, tick: int = 0,
    ):
        """FIFA Laws 15-17: classify OOB and award restart."""
        bx, by = oob_pos
        self._offside_pids_at_pass.clear()

        end_oob = (bx <= 0.001 or bx >= FIELD_W - 0.001)
        side_oob = (by <= 0.001 or by >= FIELD_H - 0.001)

        last_team = state._last_touching_team or "team_a"
        other = "team_b" if last_team == "team_a" else "team_a"

        if end_oob:
            # Determine defending team from goal positions.
            team_a_goal_x = state.field.get("team_a_goal_x", 0.0)
            if (bx <= 0.001 and team_a_goal_x <= 0.001) or \
               (bx >= FIELD_W - 0.001 and team_a_goal_x >= FIELD_W - 0.001):
                defending = "team_a"
            else:
                defending = "team_b"
            attacking = "team_b" if defending == "team_a" else "team_a"

            if state._last_touching_team == attacking:
                # Goal kick → defending GK.
                receiving = defending
                sign = 1.0 if bx <= 0.001 else -1.0
                restart_spot = (bx + sign * 5.5, FIELD_H / 2.0)
                restart_type = "goal_kick"
                kicker_id = self._select_restarter(state, receiving, restart_spot, prefer_role="GK")
            else:
                # Corner kick → attacking team.
                receiving = attacking
                corner_x = 0.0 if bx <= 0.001 else FIELD_W
                corner_y = 0.0 if by < FIELD_H / 2.0 else FIELD_H
                restart_spot = (corner_x, corner_y)
                restart_type = "corner_kick"
                kicker_id = self._select_restarter(state, receiving, restart_spot, exclude_role="GK")
        elif side_oob:
            # Throw-in → opposing team.
            receiving = other
            restart_y = 0.5 if by <= 0.001 else FIELD_H - 0.5
            restart_x = max(2.0, min(FIELD_W - 2.0, bx))
            restart_spot = (restart_x, restart_y)
            restart_type = "throw_in"
            kicker_id = self._select_restarter(state, receiving, restart_spot, exclude_role="GK")
        else:
            return

        # Apply restart.
        state.update_ball_position(restart_spot)
        state.update_ball_velocity((0.0, 0.0))
        if kicker_id is not None:
            state.apply_move(kicker_id, restart_spot)
            state.transfer_possession(None, kicker_id)
            state._last_touching_team = receiving
            self._restart_kick_pid = kicker_id
            self._pending_kick = (kicker_id, tick)

        records["system"] = {
            "out_of_bounds": True,
            "position": (bx, by),
            "restart_spot": restart_spot,
            "restart_type": restart_type,
            "restart_team": receiving,
            "kicker_id": kicker_id,
        }

    # ─── Goalkeeper Save ───

    def _attempt_goalkeeper_save(
        self, gk_id: str, ball_pos: tuple[float, float],
        ball_vel: tuple[float, float], state: MatchState, tick: int,
    ) -> tuple[str, str]:
        """ARE GDD Rule 14a + ADR-0018: 3-state GK save (caught/blocked/missed)."""
        gk = state.players.get(gk_id, {})
        gk_pos = gk.get("position", (0.0, 0.0))

        # Effective save = (2*save + skill) / 3 * health.
        # Matches AgentPitch: save defaults to gk_skill when not set.
        gk_skill = gk.get("skill", 1)
        gk_save = gk.get("save", gk_skill)
        eff_save = (2.0 * gk_save + gk_skill) / 3.0
        eff_save *= self._health_factor(state, gk_id)

        dist = math.sqrt((gk_pos[0] - ball_pos[0])**2 + (gk_pos[1] - ball_pos[1])**2)
        ball_speed = math.sqrt(ball_vel[0]**2 + ball_vel[1]**2)

        save_prob = (GK_SAVE_WEIGHT * eff_save) / (GK_SAVE_WEIGHT * eff_save + ball_speed + dist)
        caught_threshold = save_prob * GK_CAUGHT_SHARE

        draw = hash_01(state.seed, tick, gk_id, "goalkeeper_save")
        if draw < caught_threshold:
            return "caught", "skill_sufficient"
        if draw < save_prob:
            return "blocked", "parried"
        return "missed", "skill_insufficient"

    # ─── Goal Detection ───

    def _is_goal_line_crossed(
        self, ball_pos: tuple[float, float], state: MatchState,
    ) -> bool:
        """Check if ball crossed a goal line between the posts."""
        x, y = ball_pos
        if not (GOAL_BOTTOM <= y <= GOAL_TOP):
            return False
        return x <= 0.0 or x >= FIELD_W

    def _get_defending_team(
        self, ball_pos: tuple[float, float], state: MatchState,
    ) -> str:
        """Determine which team defends the crossed goal line."""
        x, _ = ball_pos
        crossed_x = 0.0 if x <= 0.0 else FIELD_W
        if abs(state.field.get("team_a_goal_x", 0.0) - crossed_x) < 1e-6:
            return "team_a"
        return "team_b"

    def _get_attacking_team(self, defending: str) -> str:
        return "team_b" if defending == "team_a" else "team_a"

    def _find_goalkeeper(self, team: str, state: MatchState) -> str | None:
        for pid, p in state.players.items():
            if p.get("team") == team and p.get("role") == "GK":
                return pid
        return None

    def _record_goal(self, state: MatchState, defending: str):
        attacking = self._get_attacking_team(defending)
        state.record_goal(attacking)

    def _snap_ball_to_carrier(self, state: MatchState, carrier_id: str):
        carrier = state.players.get(carrier_id, {})
        pos = carrier.get("position")
        if pos:
            state.update_ball_position(pos)

    # ─── Offside ───

    def _capture_offside_at_pass(self, state: MatchState, passer: dict):
        """IFAB Law 11: snapshot offside positions at pass moment."""
        self._offside_pids_at_pass.clear()
        if not OFFSIDE_ENABLED:
            return

        team = passer.get("team", "")
        opp_goal_x = state.field.get(
            "team_b_goal_x" if team == "team_a" else "team_a_goal_x")

        passer_pos = passer.get("position", (0.0, 0.0))
        ball_dist = abs(passer_pos[0] - opp_goal_x)

        opp_dists = sorted(
            abs(p.get("position", (0.0, 0.0))[0] - opp_goal_x)
            for p in state.players.values() if p.get("team") != team
        )
        second_last = opp_dists[1] if len(opp_dists) >= 2 else float("inf")
        half_width = FIELD_W / 2.0

        for pid, p in state.players.items():
            if p.get("team") != team or pid == passer.get("player_id"):
                continue
            d = abs(p.get("position", (0.0, 0.0))[0] - opp_goal_x)
            if d < half_width and d < ball_dist and d < second_last:
                self._offside_pids_at_pass.add(pid)

    def _apply_offside_free_kick(
        self, state: MatchState, offender_id: str,
        records: dict, tick: int = 0,
    ):
        """IFAB Law 11 sanction: free kick to defending team."""
        offender = state.players.get(offender_id, {})
        offender_team = offender.get("team", "")
        offender_pos = offender.get("position", (0.0, 0.0))

        if offender_team not in ("team_a", "team_b"):
            return
        receiving = "team_b" if offender_team == "team_a" else "team_a"

        restart_spot = (
            max(2.0, min(FIELD_W - 2.0, float(offender_pos[0]))),
            max(0.5, min(FIELD_H - 0.5, float(offender_pos[1]))),
        )

        state.update_ball_position(restart_spot)
        state.update_ball_velocity((0.0, 0.0))
        state.set_pass_landing_zone(None)
        self._last_ball_action_pid = None

        kicker_id = self._select_restarter(state, receiving, restart_spot, exclude_role="GK")
        if kicker_id is not None:
            state.apply_move(kicker_id, restart_spot)
            state.transfer_possession(None, kicker_id)
            state._last_touching_team = receiving
            self._pending_kick = (kicker_id, tick)

        records["system"] = {
            "offside": True,
            "offender_id": offender_id,
            "position": (float(offender_pos[0]), float(offender_pos[1])),
            "restart_spot": restart_spot,
            "restart_type": "free_kick_offside",
            "restart_team": receiving,
            "kicker_id": kicker_id,
        }

    # ─── Foul Free Kick + Penalty ───

    def _is_in_penalty_area(
        self, pos: tuple[float, float], defending: str, state: MatchState,
    ) -> bool:
        """True if pos is inside defending team's own penalty area."""
        x, y = pos
        goal_x = state.field.get(f"{defending}_goal_x")
        if goal_x is None:
            return False
        return (abs(x - goal_x) <= PENALTY_AREA_DEPTH
                and GOAL_BOTTOM - PENALTY_AREA_DEPTH <= y <= GOAL_TOP + PENALTY_AREA_DEPTH)

    def _apply_foul_free_kick(
        self, state: MatchState, fouling: str, fouled: str,
        foul_spot: tuple[float, float], offender_id: str,
        tick: int, records: dict, *, card=None, sent_off=False,
    ):
        """IFAB Law 13: direct free kick at foul spot with wall exclusion."""
        self._offside_pids_at_pass.clear()

        restart_spot = (
            max(2.0, min(FIELD_W - 2.0, float(foul_spot[0]))),
            max(0.5, min(FIELD_H - 0.5, float(foul_spot[1]))),
        )

        state.update_ball_position(restart_spot)
        state.update_ball_velocity((0.0, 0.0))
        state.set_pass_landing_zone(None)
        self._last_ball_action_pid = None

        kicker_id = self._select_restarter(state, fouled, restart_spot, exclude_role="GK")
        if kicker_id is not None:
            state.apply_move(kicker_id, restart_spot)
            state.transfer_possession(None, kicker_id)
            state._last_touching_team = fouled
            self._pending_kick = (kicker_id, tick)

        # Wall exclusion: push fouling team players out.
        for pid, p in state.players.items():
            if p.get("team") != fouling or p.get("sent_off", False):
                continue
            if pid == kicker_id:
                continue
            ppos = p.get("position")
            if ppos is None:
                continue
            dx = ppos[0] - restart_spot[0]
            dy = ppos[1] - restart_spot[1]
            d = math.sqrt(dx*dx + dy*dy)
            if d < FREE_KICK_EXCLUSION_RADIUS and d > 1e-6:
                ux, uy = dx / d, dy / d
                state.apply_move(pid, (
                    restart_spot[0] + ux * FREE_KICK_EXCLUSION_RADIUS,
                    restart_spot[1] + uy * FREE_KICK_EXCLUSION_RADIUS,
                ))

        records["system"] = {
            "foul": True, "offender_id": offender_id,
            "fouling_team": fouling,
            "position": (float(foul_spot[0]), float(foul_spot[1])),
            "restart_spot": restart_spot,
            "restart_type": "free_kick_foul",
            "restart_team": fouled,
            "kicker_id": kicker_id,
            "card": card, "sent_off": sent_off,
        }

    def _resolve_penalty_kick(
        self, state: MatchState, fouling: str, fouled: str,
        foul_spot: tuple[float, float], offender_id: str,
        tick: int, records: dict, *, card=None, sent_off=False,
    ):
        """IFAB Law 14: penalty kick, resolved instantly."""
        self._offside_pids_at_pass.clear()

        goal_x = state.field.get(f"{fouling}_goal_x", 0.0)
        mark_x = goal_x + PENALTY_MARK_DIST if goal_x < FIELD_W / 2.0 \
            else goal_x - PENALTY_MARK_DIST
        mark = (mark_x, GOAL_CENTER_Y)

        # Taker: highest penalty rating.
        candidates = []
        for pid, p in state.players.items():
            if p.get("team") != fouled or p.get("sent_off", False):
                continue
            rating = p.get("penalty", p.get("shooting", p.get("skill", 10)))
            if not isinstance(rating, (int, float)):
                rating = 10
            candidates.append((-rating, pid))
        if not candidates:
            return
        candidates.sort()
        taker_id = candidates[0][1]
        taker_penalty = -candidates[0][0]

        # Stage kick.
        state.apply_move(taker_id, mark)
        state.update_ball_position(mark)
        state.update_ball_velocity((0.0, 0.0))
        state.set_pass_landing_zone(None)
        self._last_ball_action_pid = None

        # GK contest.
        gk_id = self._find_goalkeeper(fouling, state)
        gk_save = 10
        if gk_id:
            gk = state.players.get(gk_id, {})
            rating = gk.get("save", 10)
            if isinstance(rating, (int, float)):
                gk_save = rating

        p_goal = max(0.0, min(1.0,
            PENALTY_GOAL_BASE + PENALTY_GOAL_PER_POINT * taker_penalty
            - PENALTY_SAVE_PER_POINT * (gk_save - 10)))
        if gk_id is None:
            p_goal = 1.0
        draw = hash_01(state.seed, tick, taker_id, "penalty_kick")

        if draw < p_goal:
            # Goal!
            live_carrier = state.ball.get("carrier_id")
            if live_carrier is not None:
                state.transfer_possession(live_carrier, None)
            state.record_goal(fouled)
            records["system"] = {
                "penalty_outcome": "goal", "goal_scored": fouled,
                "scored_by": taker_id,
            }
        else:
            # Saved → GK collects.
            state.transfer_possession(None, gk_id)
            self._snap_ball_to_carrier(state, gk_id)
            state._last_touching_team = fouling
            records["system"] = {"penalty_outcome": "saved"}

        records["system"].update({
            "foul": True, "offender_id": offender_id,
            "fouling_team": fouling,
            "position": (float(foul_spot[0]), float(foul_spot[1])),
            "restart_spot": mark, "restart_type": "penalty_kick",
            "restart_team": fouled, "kicker_id": taker_id,
            "card": card, "sent_off": sent_off,
        })

    # ─── Restart Helpers ───

    def _select_restarter(
        self, state: MatchState, team: str, spot: tuple[float, float],
        exclude_role: str | None = None, prefer_role: str | None = None,
    ) -> str | None:
        """Pick the team player nearest to spot to take a restart."""
        candidates = []
        for pid, p in state.players.items():
            if p.get("team") != team or p.get("sent_off", False):
                continue
            role = p.get("role")
            if exclude_role is not None and role == exclude_role:
                continue
            ppos = p.get("position", (0.0, 0.0))
            d = math.sqrt((ppos[0] - spot[0])**2 + (ppos[1] - spot[1])**2)
            preferred = (prefer_role is not None and role == prefer_role)
            candidates.append(((0 if preferred else 1), d, pid))
        if not candidates:
            return None
        candidates.sort()
        return candidates[0][2]

    # ─── Stamina / Health ───

    _BASE_DRAIN = {"Move": 0.3, "Pass": 2.0, "Shoot": 4.0, "Tackle": 4.0}
    _RECOVER_HOLD = 1.5
    _RECOVER_MOVE_LOW = 0.5
    _MOVE_LOW_SPEED = 0.5

    def _health_factor(self, state: MatchState, pid: str) -> float:
        """AgentPitch health multiplier: floor + (1-floor) × health/max."""
        p = state.players.get(pid, {})
        ch = p.get("current_health", HEALTH_MAX)
        floor = 0.6
        return floor + (1.0 - floor) * (max(0.0, ch) / HEALTH_MAX)

    def _apply_health_drain(
        self, validated: dict[str, Action], state: MatchState,
    ):
        """AgentPitch _apply_health_drain — stamina per action type."""
        for pid, action in validated.items():
            p = state.players.get(pid, {})
            stamina = p.get("stamina", 10)
            drain_mod = max(0.0, 1.0 - stamina / 20.0)
            name = type(action).__name__

            if name == "Hold":
                delta = self._RECOVER_HOLD
            elif name == "Move":
                speed = float(getattr(action, "speed", 1.0))
                if speed <= self._MOVE_LOW_SPEED:
                    delta = self._RECOVER_MOVE_LOW
                else:
                    delta = -self._BASE_DRAIN["Move"] * drain_mod * HEALTH_DRAIN_FACTOR
            elif name in ("Pass", "Shoot", "Tackle"):
                delta = -self._BASE_DRAIN[name] * drain_mod * HEALTH_DRAIN_FACTOR
            else:
                delta = 0.0

            if delta != 0.0:
                state.adjust_health(pid, delta)

    # ─── Stalemate Detection ───

    _STUCK_RADIUS = 2.0
    _STUCK_MAX_TICKS = 50

    def _check_stalemate(self, state: MatchState, tick: int):
        """Detect frozen ball and force turnover."""
        carrier_id = state.ball.get("carrier_id")
        if carrier_id is None:
            self._stuck_ticks = 0
            self._stuck_anchor = None
            return

        pos = state.ball.get("position")
        if pos is None:
            return

        if (self._stuck_anchor is not None
                and (pos[0] - self._stuck_anchor[0])**2 + (pos[1] - self._stuck_anchor[1])**2 <= self._STUCK_RADIUS**2):
            self._stuck_ticks += 1
        else:
            self._stuck_anchor = (float(pos[0]), float(pos[1]))
            self._stuck_ticks = 1

        if self._stuck_ticks >= self._STUCK_MAX_TICKS:
            carrier = state.players.get(carrier_id, {})
            carrier_team = carrier.get("team")
            opponents = [
                (pid, p) for pid, p in state.players.items()
                if p.get("team") != carrier_team
            ]
            if opponents:
                nearest = min(opponents, key=lambda x: (
                    (x[1].get("position", (0, 0))[0] - pos[0])**2
                    + (x[1].get("position", (0, 0))[1] - pos[1])**2
                ))
                state.transfer_possession(carrier_id, nearest[0])
                self._snap_ball_to_carrier(state, nearest[0])
                state.update_ball_velocity((0.0, 0.0))
            self._stuck_ticks = 0
            self._stuck_anchor = None

    # ─── Helpers ───

    def _nearest_teammate_pos(
        self, pid: str, state: MatchState,
    ) -> tuple[float, float] | None:
        """Position of pid's nearest teammate."""
        me = state.players.get(pid, {})
        team = me.get("team")
        my_pos = me.get("position", (0.0, 0.0))
        best_pos = None
        best_d = None
        for opid, p in state.players.items():
            if opid == pid or p.get("team") != team:
                continue
            ppos = p.get("position")
            if ppos is None:
                continue
            d = (ppos[0] - my_pos[0])**2 + (ppos[1] - my_pos[1])**2
            if best_d is None or d < best_d:
                best_d = d
                best_pos = (float(ppos[0]), float(ppos[1]))
        return best_pos


def _is_finite_number(value) -> bool:
    """True only for a real, finite int/float (not bool, NaN, Inf)."""
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )
