"""Match Engine — 7-phase tick loop orchestrating the full simulation.

This is the heart of Try1000. It runs discrete ticks (1 tick = 1 second),
each going through 7 phases, from kickoff to full time.

All phases read from a single snapshot built at Phase 1. No player
can observe a sibling's action in the same tick.

Usage:
    engine = MatchEngine(home_policy, away_policy, seed=42)
    result = engine.run(home_players, away_players)
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field
from enum import IntEnum

from try1000_engine.config import (
    MAX_TICKS, TICK_DURATION, HALF_TIME_TICK,
    PITCH_LENGTH, PITCH_WIDTH, GOAL_WIDTH, GOAL_DEPTH,
    COOLDOWN_DURATION_TICKS, CIRCUIT_BREAKER_LIMIT,
    DECISION_TIME_BUDGET_MS, FAST_MODE_TICK_MULTIPLIER,
    GOAL_RESET_TICKS, HALF_TIME_PAUSE_TICKS, STAMINA_MAX,
    meters_to_field, field_to_meters,
)
from try1000_engine.physics.ball import Ball
from try1000_engine.physics.player import Player
from try1000_engine.physics.collision import CollisionSystem

from try1000_engine.actions.base import ActionType, ActionOutput

from try1000_engine.ai.policy import Policy, Observation
from try1000_engine.ai.rule_based import RuleBasedPolicy
from try1000_engine.ai.baseline_agentpitch import AgentPitchBaselinePolicy

from try1000_engine.match.event_system import Event, EventType, EventRecorder
from try1000_engine.match.replay import ReplayRecorder
from try1000_engine.match.result import MatchResult


class MatchPhase(IntEnum):
    """Real match flow phases — what state the match is in."""
    KICK_OFF = 0
    IN_PLAY = 1
    GOAL_SCORED = 2
    HALF_TIME = 3
    FULL_TIME = 4


class PlayPhase(IntEnum):
    """Tactical play phases — used by AI to adjust decision-making flavor.
    Derived from ball position and possession, not the match flow state."""
    KICK_OFF = 0
    BUILD_UP = 1
    ATTACK = 2
    DEFENSE = 3
    TRANSITION = 4
    SET_PIECE = 5


def _phase_to_str(phase: MatchPhase) -> str:
    """Convert MatchPhase enum to AgentPitch phase string."""
    mapping = {
        MatchPhase.KICK_OFF: "kick_off",
        MatchPhase.IN_PLAY: "in_play",
        MatchPhase.GOAL_SCORED: "goal_scored",
        MatchPhase.HALF_TIME: "half_time",
        MatchPhase.FULL_TIME: "full_time",
    }
    return mapping.get(phase, "in_play")


@dataclass
class Snapshot:
    """Frozen match state at the start of a tick. Phase 1 builds this."""
    tick: int
    ball: Ball
    players: list[Player]      # deep-copied positions for this tick
    phase: MatchPhase
    home_score: int
    away_score: int

    @property
    def home_players(self) -> list[Player]:
        return [p for p in self.players if p.team == "home"]

    @property
    def away_players(self) -> list[Player]:
        return [p for p in self.players if p.team == "away"]

    @property
    def all_player_ids(self) -> list[str]:
        return [p.player_id for p in self.players]


class MatchEngine:
    """Orchestrates a full football match via 7-phase tick simulation.

    Supports two policy modes:
    1. Per-team (legacy): one Policy for all 11 players
       MatchEngine(home_policy=p, away_policy=p)
    2. Per-role (default via PolicyFactory): different Policy per position
       MatchEngine(home_policies={"ST": p1, "CB": p2, ...}, ...)

    If both are provided, per-role takes precedence.
    """

    def __init__(
        self,
        home_policy: Policy | None = None,
        away_policy: Policy | None = None,
        home_policies: dict[str, Policy] | None = None,
        away_policies: dict[str, Policy] | None = None,
        seed: int | None = None,
        record_replay: bool = True,
        fast_mode: bool = False,
        replay_sample_rate: int = 1,
    ):
        self._home_default = home_policy or RuleBasedPolicy()
        self._away_default = away_policy or RuleBasedPolicy()
        self._home_roles = home_policies or {}
        self._away_roles = away_policies or {}
        # Use random seed when not specified, so each match is different.
        # Pass an explicit seed for reproducible results.
        if seed is None:
            seed = random.randint(0, 2**31 - 1)
        self.rng = random.Random(seed)
        self._seed = seed  # stored for hash_01 kickoff selection (matches AgentPitch)
        self.record_replay = record_replay
        self.fast_mode = fast_mode
        self.replay_sample_rate = replay_sample_rate  # 1=every tick, 5=every 5th
        # In fast mode, each tick represents FAST_MODE_TICK_MULTIPLIER seconds
        self._tick_multiplier = FAST_MODE_TICK_MULTIPLIER if fast_mode else 1
        self._max_ticks = MAX_TICKS // self._tick_multiplier
        self._half_time_tick = HALF_TIME_TICK // self._tick_multiplier

        # Systems
        self.collision = CollisionSystem()

        # Per-match state
        self.ball: Ball | None = None
        self.players: list[Player] = []
        self.phase: MatchPhase = MatchPhase.KICK_OFF
        self.play_phase: PlayPhase = PlayPhase.KICK_OFF
        self.home_score: int = 0
        self.away_score: int = 0
        self.tick: int = 0
        self.recorder: EventRecorder | None = None
        self.replay: ReplayRecorder | None = None
        self._history: dict[str, list[dict]] = {}  # player_id → recent events
        self._circuit_breaker: dict[str, int] = {}  # player_id → consecutive failures
        self._possession_ticks: dict[str, int] = {"home": 0, "away": 0}
        self._pass_landing_zone: tuple[float, float] | None = None
        self._offside_flagged: set[str] = set()
        self._player_fouls: dict[str, int] = {}
        self._player_cards: dict[str, str] = {}
        self._formation: str = "4-3-3"

    # ═══════════════════════════════════════════════════════════════
    # Public API
    # ═══════════════════════════════════════════════════════════════

    def run(
        self,
        home_players: list[Player],
        away_players: list[Player],
        match_index: int = 0,
        replay_path: str | None = None,
    ) -> MatchResult:
        """Run a full match from kickoff to full time.

        Args:
            home_players: 11 home team players.
            away_players: 11 away team players.
            match_index: Index within a multi-match simulation job.
            replay_path: Optional path to write events.jsonl.

        Returns:
            MatchResult with scores, stats, and replay data.
        """
        self._init_match(home_players, away_players, replay_path)
        t0 = time.perf_counter()

        while self.tick < self._max_ticks:
            self._tick()

            # Half-time: trigger pause + direction swap
            if self.tick == self._half_time_tick and self.phase == MatchPhase.IN_PLAY:
                self.phase = MatchPhase.HALF_TIME
                self._halftime_pause_remaining = HALF_TIME_PAUSE_TICKS
                self.recorder.record(self.tick, Event(
                    tick=self.tick, event_type=EventType.HALF_TIME
                ))

            if self.phase == MatchPhase.FULL_TIME:
                break

        elapsed = time.perf_counter() - t0

        # Build result
        result = MatchResult(match_index=match_index,
                             home_score=self.home_score,
                             away_score=self.away_score)
        result.compute_from_events(
            self.recorder, self.tick,
            self._possession_ticks["home"],
            self._possession_ticks["away"],
        )
        result.replay_ticks = self.replay.export() if self.replay else []

        # Final event
        self.recorder.record(self.tick, Event(
            tick=self.tick, event_type=EventType.FULL_TIME,
            data={"duration_seconds": round(elapsed, 2)}
        ))

        if self.replay:
            self.replay.close()

        return result

    # ═══════════════════════════════════════════════════════════════
    # Tick Loop
    # ═══════════════════════════════════════════════════════════════

    def _tick(self):
        """Orchestrate a single tick based on the current match phase.

        References AgentPitch's TickEngine pattern:
        - GOAL_SCORED: pause, then kickoff for conceding team
        - HALF_TIME: pause, swap directions, kickoff for other team
        - KICK_OFF / IN_PLAY: run the full 7-phase active tick
        """
        if self.phase == MatchPhase.GOAL_SCORED:
            self._goal_pause_remaining -= 1
            if self._goal_pause_remaining <= 0:
                if self.tick >= self._max_ticks:
                    self.phase = MatchPhase.FULL_TIME
                else:
                    self._setup_kickoff(self._conceding_team)
            self.tick += 1
            for p in self.players:
                p.update_cooldown()
            return

        if self.phase == MatchPhase.HALF_TIME:
            self._halftime_pause_remaining -= 1
            if self._halftime_pause_remaining <= 0:
                for p in self.players:
                    p.stamina = STAMINA_MAX
                self._setup_kickoff(self._second_half_kickoff_team)
                self._swap_directions()  # swap AFTER reset so formation positions get mirrored
            self.tick += 1
            for p in self.players:
                p.update_cooldown()
            return

        if self.phase == MatchPhase.FULL_TIME:
            return

            # Active tick: KICK_OFF or IN_PLAY — AgentPitch ARE Phases 2-7
        # ── AgentPitch ARE Phases 1-7 ──
        from try1000_engine.match.are_engine import AreEngine, MatchState
        from try1000_engine.ai.baseline_agentpitch import decide as baseline_decide
        if not hasattr(self, '_are'):
            self._are = AreEngine(seed=self.rng.randint(0, 2**31))

        # Build MatchState (mini-GSM). This is always needed — the ARE reads
        # and mutates state through it regardless of which path we use.
        ms = self._build_match_state()

        # Check if we're in pure non-AI (baseline/rule-based) mode.
        # When true, use the AgentPitch-compatible path where the ARE owns
        # Phase 1 (snapshot via ms.build_tick_snapshot()) and Phase 2
        # (decide via the callback), matching AgentPitch's ARE exactly.
        _non_ai = (
            isinstance(self._home_default, (RuleBasedPolicy, AgentPitchBaselinePolicy))
            and isinstance(self._away_default, (RuleBasedPolicy, AgentPitchBaselinePolicy))
            and all(isinstance(p, (RuleBasedPolicy, AgentPitchBaselinePolicy))
                    for p in self._home_roles.values())
            and all(isinstance(p, (RuleBasedPolicy, AgentPitchBaselinePolicy))
                    for p in self._away_roles.values())
        )
        if _non_ai:
            # ── AgentPitch-compatible path: ARE owns Phases 1-7 ──
            self._are._gsm = ms
            tick_records = self._are.resolve_tick(
                self.tick, None, baseline_decide)
        else:
            # ── Legacy path: Phase 2 handled externally (AI / per-role policies) ──
            snap = self._phase1_snapshot()
            decisions = {}
            for p in self.players:
                decisions[p.player_id] = self._phase2_decide(p, snap)
            ap_actions = self._to_ap_actions(decisions)
            tick_records = self._are.resolve_tick(ms, ap_actions, self.tick)

        # Capture score before syncing (for goal detection).
        score_before = (self.home_score, self.away_score)

        # Sync state back to engine objects
        self._sync_match_state(ms)

        # ── Goal detection (matches AgentPitch _check_phase_transitions) ──
        if (self.home_score, self.away_score) != score_before and self.phase == MatchPhase.IN_PLAY:
            self.phase = MatchPhase.GOAL_SCORED
            self._goal_pause_remaining = GOAL_RESET_TICKS // self._tick_multiplier
            # Infer conceding team from score delta
            if self.home_score > score_before[0]:
                self._conceding_team = "away"
            else:
                self._conceding_team = "home"

        # Build tick_events from records for event recording compatibility
        tick_events = self._records_to_events(tick_records)

        # Replay recording (ARE already clamps players to pitch)
        if self.record_replay and self.replay and self.tick % self.replay_sample_rate == 0:
            self.replay.record_tick(
                tick=self.tick,
                players=self.players,
                ball=self.ball,
                home_score=self.home_score,
                away_score=self.away_score,
                phase=self.phase.name,
                events=[e for e in tick_events.values() if isinstance(e, dict) and e.get("type")],
            )

        # Record events
        for pid, evt in tick_events.items():
            if pid.startswith("_") or not isinstance(evt, dict):
                continue
            atype = evt.get("type", "")
            success = evt.get("success", False)
            data = evt.get("data", {})
            if atype in ("pass", "shoot", "cross", "tackle", "intercept", "dribble_contest"):
                etype = {"pass": EventType.PASS, "shoot": EventType.SHOOT, "cross": EventType.CROSS,
                         "tackle": EventType.TACKLE, "intercept": EventType.INTERCEPT,
                         "dribble_contest": EventType.DRIBBLE}.get(atype, EventType.PASS)
                self.recorder.record(self.tick, Event(tick=self.tick, event_type=etype, actor=pid, success=success, data=data))
                self._record_history(pid, data)
            elif atype == "goal":
                self.recorder.record(self.tick, Event(tick=self.tick, event_type=EventType.GOAL, data=data))
        if "_oob" in tick_events:
            self.recorder.record(self.tick, Event(tick=self.tick,
                event_type=EventType.THROW_IN if tick_events["_oob"].get("type")=="throw_in" else EventType.GOAL_KICK))

        # Possession tracking
        carrier = self._find_ball_carrier()
        if carrier:
            self._possession_ticks[carrier.team] += 1

        self.tick += 1
        for p in self.players:
            p.update_cooldown()

        # Transition KICK_OFF → IN_PLAY after one tick
        if self.phase == MatchPhase.KICK_OFF:
            self.phase = MatchPhase.IN_PLAY

    # ═══════════════════════════════════════════════════════════════
    # State bridge: engine objects ↔ dict-based MatchState (field coords)
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def _engine_to_ap_id(engine_pid: str) -> str:
        """Convert engine player_id (e.g. 'home_9') → AP id ('team_a_9')."""
        # engine_pid format: "{home|away}_{N}" or "{home|away}_{role}_{N}"
        parts = engine_pid.split("_", 1)
        team_str = parts[0]
        suffix = parts[1] if len(parts) > 1 else "0"
        ap_team = "team_a" if team_str == "home" else "team_b"
        return f"{ap_team}_{suffix}"

    @staticmethod
    def _ap_to_engine_pid(ap_pid: str) -> str:
        """Convert AP player_id (e.g. 'team_a_9') → engine id ('home_9')."""
        # AP format: "team_a_{suffix}" or "team_b_{suffix}"
        if ap_pid.startswith("team_a_"):
            return "home_" + ap_pid[len("team_a_"):]
        elif ap_pid.startswith("team_b_"):
            return "away_" + ap_pid[len("team_b_"):]
        return ap_pid  # fallback

    def _build_match_state(self) -> 'MatchState':
        """Build AgentPitch-format MatchState from engine Player/Ball objects."""
        from try1000_engine.match.are_engine import MatchState

        # ── Players ──
        players: dict[str, dict] = {}
        for p in self.players:
            if getattr(p, 'sent_off', False):
                continue
            ap_id = self._engine_to_ap_id(p.player_id)
            fx, fy = meters_to_field(p.x, p.y)

            # Formation anchor in field coords (computed directly, no meters round-trip).
            fx_a, fy_a = self._get_anchor_field(p)

            # Attribute conversion: 0-100 → 1-20 (AgentPitch scale).
            def _to_ap(val, default=70):
                actual = getattr(p, val, default)
                return max(1, int(actual / 5))

            # Role mapping: engine-specific → AgentPitch generic (GK/DEF/MID/FWD).
            # The baseline strategy checks for these four groups, not individual roles.
            _role = p.role
            if _role == "GK":
                ap_role = "GK"
            elif _role in ("CB", "LB", "RB", "LCB", "RCB"):
                ap_role = "DEF"
            elif _role in ("CDM", "CM", "CAM", "LM", "RM"):
                ap_role = "MID"
            else:
                ap_role = "FWD"

            players[ap_id] = {
                "player_id": ap_id,
                "team": "team_a" if p.team == "home" else "team_b",
                "role": ap_role,
                "number": getattr(p, 'number', 0),
                "position": (fx, fy),
                "formation_position": (fx_a, fy_a),
                "has_ball": getattr(p, 'has_ball', False),
                "speed": _to_ap('pace', 70),
                "skill": _to_ap('composure', 70),
                "strength": _to_ap('physicality', 70),
                "save": _to_ap('save', 0),  # AgentPitch default=0, falls back to skill in GK save
                "discipline": _to_ap('awareness', 70),
                "dribbling": _to_ap('dribbling', 70),
                "passing": _to_ap('passing', 70),
                "shooting": _to_ap('shooting', 70),
                "stamina": min(10, _to_ap('stamina_val' if hasattr(p, 'stamina_val') else 'stamina', 100)),
                "offensive": _to_ap('composure', 70),
                "penalty": _to_ap('shooting', 70),
                "current_health": min(100.0, max(30.0, getattr(p, 'stamina', 100.0))),
                "sent_off": getattr(p, 'sent_off', False),
                # Per-player cooldown from engine (propagated so build_player_state
                # and the baseline strategy see the real cooldown state).
                "cooldown_remaining": max(0, getattr(p, 'cooldown_remaining', 0)),
            }

        # ── Ball ──
        ball = self.ball
        bx, by = meters_to_field(ball.x, ball.y)
        carrier_id = ball.carrier_id
        if carrier_id is not None:
            carrier_id = self._engine_to_ap_id(carrier_id)

        ap_last_touch = ball.last_touch_team
        if ap_last_touch == "home":
            ap_last_touch = "team_a"
        elif ap_last_touch == "away":
            ap_last_touch = "team_b"

        ball_dict = {
            "position": (bx, by),
            "velocity": (ball.vx, ball.vy),
            "carrier_id": carrier_id,
            "possession": carrier_id if carrier_id else None,
        }

        # ── Field ──
        half = 1 if self.tick < self._half_time_tick else 2
        field = {
            "width": 100.0,
            "height": 60.0,
            "goal_top": 33.66,
            "goal_bottom": 26.34,
        }
        if half == 1:
            field["team_a_goal_x"] = 0.0
            field["team_b_goal_x"] = 100.0
        else:
            field["team_a_goal_x"] = 100.0
            field["team_b_goal_x"] = 0.0

        # ── Score / Meta ──
        score = {"team_a": self.home_score, "team_b": self.away_score}

        snap_dict = {
            "tick": self.tick,
            "match_phase": _phase_to_str(self.phase),
            "half": half,
            "score": score,
            "players": players,
            "ball": ball_dict,
            "field": field,
        }

        ms = MatchState(snap_dict, self.rng.randint(0, 2**31))

        # Persist pass landing zone across ticks (matches AgentPitch GSM).
        # The ARE sets _pass_landing_zone in Phase 5; BPS reads it in Phase 7.
        # Without this, the overshoot detection never fires and the ball
        # keeps traveling until it hits a boundary (causing excessive OOB).
        lz = getattr(self.ball, '_landing_zone', None)
        if lz is not None:
            lz_fc = meters_to_field(lz[0], lz[1])
            ms._pass_landing_zone = lz_fc

        return ms

    def _sync_match_state(self, ms: 'MatchState'):
        """Write MatchState changes back to engine Player/Ball objects."""
        # ── Players ──
        for p in self.players:
            ap_id = self._engine_to_ap_id(p.player_id)
            ap_p = ms.players.get(ap_id)
            if ap_p is None:
                continue
            # Position: field coords → meters.
            pos = ap_p.get("position")
            if pos:
                p.x, p.y = field_to_meters(pos[0], pos[1])
            # Possession.
            p.has_ball = ap_p.get("has_ball", False)
            # Stamina (current_health in AgentPitch = stamina in engine).
            ch = ap_p.get("current_health")
            if ch is not None:
                p.stamina = ch
            # Sent off.
            p.sent_off = ap_p.get("sent_off", False)

        # ── Ball ──
        bpos = ms.ball.get("position")
        if bpos:
            self.ball.x, self.ball.y = field_to_meters(bpos[0], bpos[1])
        bvel = ms.ball.get("velocity")
        if bvel:
            self.ball.vx, self.ball.vy = bvel[0], bvel[1]
        cid = ms.ball.get("carrier_id")
        if cid is not None:
            # Map AP ID → engine ID.
            # AP format: "team_a_{suffix}", engine format: "{home|away}_{suffix}"
            for p in self.players:
                if self._engine_to_ap_id(p.player_id) == cid:
                    self.ball.carrier_id = p.player_id
                    break
        else:
            self.ball.carrier_id = None
        # Last touch team.
        lt = getattr(ms, '_last_touching_team', None)
        if lt == "team_a":
            self.ball.last_touch_team = "home"
        elif lt == "team_b":
            self.ball.last_touch_team = "away"

        # ── Score ──
        self.home_score = ms.score.get("team_a", self.home_score)
        self.away_score = ms.score.get("team_b", self.away_score)

        # ── Pass landing zone ──
        lz = getattr(ms, '_pass_landing_zone', None)
        if lz:
            self.ball._landing_zone = field_to_meters(lz[0], lz[1])
        else:
            self.ball._landing_zone = None

    def _to_ap_actions(self, decisions: dict) -> dict:
        """Convert engine ActionOutput → AgentPitch Action objects."""
        from try1000_engine.match.action import Move, Pass, Shoot, Tackle, Hold as APHold
        from try1000_engine.actions.base import ActionType

        ap_actions: dict[str, 'Action'] = {}
        for pid, a in decisions.items():
            ap_id = self._engine_to_ap_id(pid)

            at = ActionType(a.action_type)
            if at == ActionType.HOLD:
                ap_actions[ap_id] = APHold()
            elif at == ActionType.MOVE:
                ap_actions[ap_id] = Move(dx=a.dx, dy=a.dy, speed=max(0.0, min(1.0, a.speed)))
            elif at == ActionType.DRIBBLE:
                ap_actions[ap_id] = Move(dx=a.dx, dy=a.dy, speed=max(0.0, min(1.0, a.speed)))
            elif at == ActionType.PASS:
                ap_actions[ap_id] = Pass(
                    target_pos=(a.target_x, a.target_y),
                    power=max(1, min(20, int(a.power))),
                )
            elif at == ActionType.SHOOT:
                ap_actions[ap_id] = Shoot(
                    angle=a.angle,
                    power=max(1, min(20, int(a.power))),
                )
            elif at == ActionType.TACKLE:
                # Map target player ID.
                ap_tid = self._engine_to_ap_id(a.target_player_id)
                ap_actions[ap_id] = Tackle(target_player_id=ap_tid)
            elif at == ActionType.CROSS:
                ap_actions[ap_id] = Pass(
                    target_pos=(a.target_x, a.target_y),
                    power=max(1, min(20, int(a.power))),
                )
            else:
                ap_actions[ap_id] = APHold()
        return ap_actions

    def _records_to_events(self, records: dict) -> dict:
        """Convert ARE action_records → legacy tick_events format."""
        events: dict[str, dict] = {}
        for pid, rec in records.items():
            # System records (start with _) pass through as-is.
            if pid.startswith("_"):
                events[pid] = rec
                continue

            engine_pid = self._ap_to_engine_pid(pid)
            atype = rec.get("action", "").lower()
            result = rec.get("result", "ok")
            data: dict = {}

            # Use engine_pid as the key so event recording and
            # compute_from_events correctly attribute actions to teams.
            if atype == "pass":
                lp = rec.get("landing_pos")
                if lp:
                    data["landing_mx"], data["landing_my"] = field_to_meters(lp[0], lp[1])
                events[engine_pid] = {"type": "pass", "success": result == "ok", "data": data,
                               "player_id": engine_pid}
            elif atype == "shoot":
                events[engine_pid] = {"type": "shoot", "success": result == "ok", "data": data,
                               "player_id": engine_pid}
            elif atype == "tackle":
                events[engine_pid] = {"type": "tackle", "success": result in ("controlled", "blocked"),
                               "data": rec, "player_id": engine_pid}
            elif atype == "move":
                dr = rec.get("dribble_result")
                if dr:
                    events[engine_pid] = {"type": "dribble_contest", "success": dr == "success",
                                   "data": rec, "player_id": engine_pid}
            elif rec.get("ball_pickup"):
                events[engine_pid] = {"type": "ball_pickup", "success": True, "data": rec,
                               "player_id": engine_pid}
            elif rec.get("goalkeeper_save"):
                events[engine_pid] = {"type": "save", "success": True, "data": rec,
                               "player_id": engine_pid}
            elif rec.get("shot_deflection"):
                events[engine_pid] = {"type": "deflection", "success": True, "data": rec,
                               "player_id": engine_pid}
            elif rec.get("goal_scored"):
                sid = rec.get("scored_by", "")
                scorer_team = "home" if sid.startswith("team_a") else "away"
                events["_goal"] = {"type": "goal", "success": True,
                                   "data": {"scorer_team": scorer_team, "penalty": rec.get("reason") == "penalty"}}
            elif rec.get("offside"):
                events["_offside"] = rec
            elif rec.get("foul"):
                events["_foul"] = rec
            elif rec.get("out_of_bounds"):
                rst = rec.get("restart_type", "")
                events["_oob"] = {"type": rst, "success": False, "data": rec}
        return events

    # ═══════════════════════════════════════════════════════════════
    # Phase 1: Snapshot
    # ═══════════════════════════════════════════════════════════════

    def _phase1_snapshot(self) -> Snapshot:
        """Freeze the current match state. All subsequent phases read from this."""
        # Shallow copy is fine — ball and player positions are floats (immutable)
        return Snapshot(
            tick=self.tick,
            ball=self.ball,
            players=list(self.players),  # same objects, positions read-only during tick
            phase=self.phase,
            home_score=self.home_score,
            away_score=self.away_score,
        )

    # ═══════════════════════════════════════════════════════════════
    # Phase 2: AI Decision
    # ═══════════════════════════════════════════════════════════════

    def _phase2_decide(self, player: Player, snapshot: Snapshot) -> ActionOutput:
        """Call the appropriate policy for this player."""
        # Circuit breaker check
        failures = self._circuit_breaker.get(player.player_id, 0)
        if failures >= CIRCUIT_BREAKER_LIMIT:
            return ActionOutput.hold()

        # Choose policy: per-role preferred, fallback to per-team
        if player.team == "home":
            policy = self._home_roles.get(player.role, self._home_default)
        else:
            policy = self._away_roles.get(player.role, self._away_default)

        try:
            # Compute dynamic formation anchor (FRS + 3-phase shift) for AgentPitch baseline
            anchor = self._get_anchor(player)
            player._anchor_x = anchor[0]
            player._anchor_y = anchor[1]

            # Use decide_with_context for policies that support it
            from try1000_engine.ai.generated_policy import GeneratedPolicy
            from try1000_engine.ai.baseline_agentpitch import AgentPitchBaselinePolicy
            if isinstance(policy, (RuleBasedPolicy, GeneratedPolicy, AgentPitchBaselinePolicy)):
                teammates = snapshot.home_players if player.team == "home" else snapshot.away_players
                opponents = snapshot.away_players if player.team == "home" else snapshot.home_players
                history = self._history.get(player.player_id, [])

                action, _ = policy.decide_with_context(
                    player=player,
                    teammates=teammates,
                    opponents=opponents,
                    ball=snapshot.ball,
                    home_score=snapshot.home_score,
                    away_score=snapshot.away_score,
                    tick=snapshot.tick,
                    max_ticks=self._max_ticks,
                    half=1 if snapshot.tick < self._half_time_tick else 2,
                    phase_id=int(self.play_phase),
                    history_actions=history,
                )
                self._circuit_breaker[player.player_id] = 0  # reset on success
                return action
            else:
                # Generic Policy interface — build Observation manually
                obs = self._build_observation(player, snapshot)
                action = policy.decide(obs)
                self._circuit_breaker[player.player_id] = 0
                return action

        except Exception:
            # Fallback: Hold, increment circuit breaker
            self._circuit_breaker[player.player_id] = failures + 1
            return ActionOutput.hold()

    def _build_observation(self, player: Player, snapshot: Snapshot) -> Observation:
        """Build Observation for non-RuleBased policies (generic Policy interface)."""
        teammates = snapshot.home_players if player.team == "home" else snapshot.away_players
        opponents = snapshot.away_players if player.team == "home" else snapshot.home_players
        history = self._history.get(player.player_id, [])

        tactic = {}
        if player.team == "home":
            policy = self._home_roles.get(player.role, self._home_default)
        else:
            policy = self._away_roles.get(player.role, self._away_default)
        if isinstance(policy, RuleBasedPolicy):
            tactic = policy.tactic

        return self.perception.build_observation(
            player=player, teammates=teammates, opponents=opponents,
            ball=snapshot.ball, home_score=snapshot.home_score,
            away_score=snapshot.away_score, tick=snapshot.tick,
            max_ticks=self._max_ticks,
            half=1 if snapshot.tick < self._half_time_tick else 2,
            phase_id=int(self.play_phase),
            tactic_params=tactic,
            history_actions=history,
        )

    # ═══════════════════════════════════════════════════════════════
    # Match Flow — kickoff, half-time, directions
    # ═══════════════════════════════════════════════════════════════

    def _setup_kickoff(self, kickoff_team: str):
        """Reset players to formation positions and place ball at center.
        The kickoff team's nearest OUTFIELD player to center gets possession.
        Per FIFA Law 8: GKs cannot take kickoffs. Non-kicking team must be
        outside the center circle and in their own half.
        References AgentPitch's TickEngine._setup_kickoff pattern."""
        from try1000_engine.config import CENTER_CIRCLE_RADIUS
        # Reset all players to initial formation positions
        self._reset_positions()
        # Place ball at center, stationary
        self.ball.x = 0.0
        self.ball.y = 0.0
        self.ball.vx = 0.0
        self.ball.vy = 0.0
        self.ball.carrier_id = None
        # Clear has_ball on all players
        for p in self.players:
            p.has_ball = False
        # Find kickoff player: nearest to center, excluding GK (Law 8)
        center = (0.0, 0.0)
        kickoff_players = [p for p in self.players if p.team == kickoff_team and p.role != "GK"]
        if not kickoff_players:  # degenerate fallback
            kickoff_players = [p for p in self.players if p.team == kickoff_team]
        if kickoff_players:
            def dist_to_center(p):
                return math.sqrt((p.x - center[0])**2 + (p.y - center[1])**2)
            kickoff_pid = min(kickoff_players, key=dist_to_center)
            self.ball.carrier_id = kickoff_pid.player_id
            self.ball.last_touch_team = kickoff_team
            kickoff_pid.has_ball = True
        # Enforce legal kickoff positions per FIFA Law 8.
        # Matches AgentPitch's GSM._apply_kickoff_positions exactly:
        # - Kicker is placed at the center spot.
        # - Every other player is minimally clamped into their own half (0.5m
        #   margin from the halfway line), using their formation anchor as the
        #   starting point (not the current position).
        # - If the result is still inside the center circle (9.15m radius),
        #   push x further outward along own-half direction to the circle
        #   boundary at the same y.
        center_x = 0.0
        center_y = 0.0
        circle_r = CENTER_CIRCLE_RADIUS  # 9.15 metres (10 yards)
        margin = 0.5  # keep non-kickers just off the halfway line
        for p in self.players:
            if p.has_ball:
                p.x = center_x
                p.y = center_y
                continue
            own_goal_x = self.home_goal_x if p.team == "home" else self.away_goal_x
            own_half_low = own_goal_x < center_x
            # Step 1: clamp x into own half using the formation anchor.
            # _reset_positions() already placed the player at their anchor.
            if own_half_low:
                p.x = min(p.x, center_x - margin)
            else:
                p.x = max(p.x, center_x + margin)
            # Step 2: push further if still inside the centre circle.
            dy = p.y - center_y
            dist_sq = p.x * p.x + dy * dy
            if dist_sq < circle_r * circle_r:
                if own_half_low:
                    p.x = center_x - math.sqrt(max(0.0, circle_r**2 - dy**2))
                else:
                    p.x = center_x + math.sqrt(max(0.0, circle_r**2 - dy**2))
        self.phase = MatchPhase.KICK_OFF
        self.play_phase = PlayPhase.KICK_OFF

    def _swap_directions(self):
        """AgentPitch swap_attack_direction: mirror x and swap goal positions.

        Also swaps which team gets mirrored anchors — after half-time,
        home defends the other side, so their formation anchors must flip.
        """
        for p in self.players:
            p.x = -p.x
        # Swap which goal each team defends
        self.home_goal_x, self.away_goal_x = self.away_goal_x, self.home_goal_x
        if self.ball:
            self.ball.x = -self.ball.x
        # Track second half for _reset_positions anchor flip
        self._second_half = True

    # ═══════════════════════════════════════════════════════════════
    # Helpers
    # ═══════════════════════════════════════════════════════════════

    def _init_match(self, home_players: list[Player], away_players: list[Player],
                    replay_path: str | None):
        """Initialize match state."""
        self.ball = Ball(0.0, 0.0)
        self.players = home_players + away_players
        self.phase = MatchPhase.KICK_OFF
        self.home_score = 0
        self.away_score = 0
        self.tick = 0
        self.recorder = EventRecorder()
        self.replay = ReplayRecorder(replay_path) if self.record_replay else None
        self._history = {}
        self._circuit_breaker = {}
        self._second_half = False
        self._possession_ticks = {"home": 0, "away": 0}

        if self.replay:
            self.replay.open()

        # Setup kickoff — AgentPitch: hash_01(seed, 0, "kickoff") < 0.5
        from try1000_engine.physics.simulation_utils import hash_01
        kickoff_team_a = hash_01(self._seed, 0, "kickoff") < 0.5
        self._kickoff_team = "home" if kickoff_team_a else "away"
        self._second_half_kickoff_team = "away" if kickoff_team_a else "home"
        self.home_goal_x = -PITCH_LENGTH / 2  # home defends left in 1st half
        self.away_goal_x = PITCH_LENGTH / 2   # away defends right
        self._setup_kickoff(self._kickoff_team)

    def _reset_positions(self):
        """Reset players to formation anchor positions (FRS).

        Always recomputes anchors from the current formation and half.
        Matches AgentPitch's unconditional _reset_positions_to_anchors().
        """
        from try1000_engine.match.formation import compute_anchors, mirror_anchors
        formation = getattr(self, '_formation', "4-3-3")
        home_p = [p for p in self.players if p.team == "home"]
        away_p = [p for p in self.players if p.team == "away"]
        # First half: home attacks right, away attacks left.
        # After _swap_directions (second half): flip which team gets mirrored.
        if getattr(self, '_second_half', False):
            home_anchors = mirror_anchors(compute_anchors(formation, home_p))
            away_anchors = compute_anchors(formation, away_p)
        else:
            home_anchors = compute_anchors(formation, home_p)
            away_anchors = mirror_anchors(compute_anchors(formation, away_p))
        for p in self.players:
            anchor = home_anchors.get(p.player_id) or away_anchors.get(p.player_id)
            if anchor:
                p.x, p.y = anchor

    def _get_anchor(self, player: Player) -> tuple[float, float]:
        """AgentPitch FRS: dynamic phase-aware zone anchor in ENGINE METERS.

        Used by _phase2_decide for AI policy input. Converts from field coords
        to meters after computing the anchor.
        """
        from try1000_engine.config import field_to_meters
        fc_pos = self._get_anchor_field(player)
        return field_to_meters(fc_pos[0], fc_pos[1])

    def _get_anchor_field(self, player: Player) -> tuple[float, float]:
        """AgentPitch FRS: dynamic phase-aware zone anchor in FIELD COORDS.

        Used by _build_match_state for ARE MatchState. Computes directly in
        field coords (no meters round-trip), matching AgentPitch's FRS exactly.
        """
        from try1000_engine.config import meters_to_field
        from try1000_engine.match.formation import compute_dynamic_anchor

        own_goal_x_m = self.home_goal_x if player.team == "home" else self.away_goal_x

        # Determine possession: derive team string from carrier.
        cid = getattr(self.ball, 'carrier_id', None)
        if cid is not None:
            carrier = self._find_player(cid)
            if carrier:
                have_ball = (carrier.team == player.team)
                ball_possession = "team_a" if carrier.team == "home" else "team_b"
            else:
                have_ball = False
                ball_possession = None
        else:
            have_ball = False
            ball_possession = None

        # Convert engine meter coords → field coords for the computation.
        bx_fc, by_fc = meters_to_field(self.ball.x, self.ball.y)
        own_goal_x_fc, _ = meters_to_field(own_goal_x_m, 0.0)

        return compute_dynamic_anchor(
            player=player,
            all_players=self.players,
            ball_x_fc=bx_fc,
            ball_y_fc=by_fc,
            own_goal_x_fc=own_goal_x_fc,
            have_ball=have_ball,
            ball_possession=ball_possession,
        )

    def _find_player(self, player_id: str) -> Player | None:
        for p in self.players:
            if p.player_id == player_id:
                return p
        return None

    def _find_ball_carrier(self) -> Player | None:
        for p in self.players:
            if p.has_ball:
                return p
        return None

    def _record_history(self, player_id: str, event_data: dict):
        """Append to player's recent action history."""
        if player_id not in self._history:
            self._history[player_id] = []
        self._history[player_id].append({
            "tick": self.tick,
            "type": event_data.get("type", "unknown"),
            "success": event_data.get("success", False),
            "data": event_data,
        })
        # Keep last 20 actions
        if len(self._history[player_id]) > 20:
            self._history[player_id] = self._history[player_id][-20:]
