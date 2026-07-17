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
)
from try1000_engine.physics.ball import Ball
from try1000_engine.physics.player import Player
from try1000_engine.physics.collision import CollisionSystem
from try1000_engine.physics.stamina import Stamina
from try1000_engine.physics.ball_physics_system import advance_ball, resolve_ball_control
from try1000_engine.physics.player_movement_system import (
    compute_move_result, apply_snap, detect_dribble_target,
)

from try1000_engine.actions.base import ActionType, ActionOutput
from try1000_engine.actions.pass_action import PassAction
from try1000_engine.actions.shoot import ShootAction
from try1000_engine.actions.cross import CrossAction
from try1000_engine.actions.dribble import DribbleAction
from try1000_engine.actions.tackle import TackleAction
from try1000_engine.actions.intercept import InterceptAction
from try1000_engine.actions.move import MoveAction

from try1000_engine.ai.policy import Policy, Observation
from try1000_engine.ai.rule_based import RuleBasedPolicy
from try1000_engine.ai.perception import Perception

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


# Map ActionType → EventType (they have different enum values)
_ACTION_TO_EVENT = {
    ActionType.PASS: EventType.PASS,
    ActionType.SHOOT: EventType.SHOOT,
    ActionType.CROSS: EventType.CROSS,
    ActionType.DRIBBLE: EventType.DRIBBLE,
    ActionType.TACKLE: EventType.TACKLE,
    ActionType.INTERCEPT: EventType.INTERCEPT,
}


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
        seed: int = 42,
        record_replay: bool = True,
        fast_mode: bool = False,
        replay_sample_rate: int = 1,
    ):
        self._home_default = home_policy or RuleBasedPolicy()
        self._away_default = away_policy or RuleBasedPolicy()
        self._home_roles = home_policies or {}
        self._away_roles = away_policies or {}
        self.rng = random.Random(seed)
        self.record_replay = record_replay
        self.fast_mode = fast_mode
        self.replay_sample_rate = replay_sample_rate  # 1=every tick, 5=every 5th
        # In fast mode, each tick represents FAST_MODE_TICK_MULTIPLIER seconds
        self._tick_multiplier = FAST_MODE_TICK_MULTIPLIER if fast_mode else 1
        self._max_ticks = MAX_TICKS // self._tick_multiplier
        self._half_time_tick = HALF_TIME_TICK // self._tick_multiplier

        # Action resolvers
        self.pass_action = PassAction()
        self.shoot_action = ShootAction()
        self.cross_action = CrossAction()
        self.dribble_action = DribbleAction()
        self.tackle_action = TackleAction()
        self.intercept_action = InterceptAction()
        self.move_action = MoveAction()

        # Systems
        self.collision = CollisionSystem()
        self.perception = Perception()

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
                # Restore all players' stamina (simulates 15-min half-time break)
                for p in self.players:
                    p.stamina = STAMINA_MAX
                self._swap_directions()
                self._setup_kickoff(self._second_half_kickoff_team)
            self.tick += 1
            for p in self.players:
                p.update_cooldown()
            return

        if self.phase == MatchPhase.FULL_TIME:
            return

            # Active tick: KICK_OFF or IN_PLAY — use unified ARE
        snapshot = self._phase1_snapshot()

        decisions: dict[str, ActionOutput] = {}
        for player in self.players:
            decisions[player.player_id] = self._phase2_decide(player, snapshot)

        decisions = self._phase3_validate(decisions, snapshot)

        # ARE: unified action resolution (replaces old phases 4-7)
        from try1000_engine.match.action_resolver import resolve_tick
        tick_events = resolve_tick(self, decisions, self.rng)

        # Stamina update
        for p in self.players:
            speed = p.current_speed
            stamina = Stamina(p.stamina)
            stamina.update(speed, TICK_DURATION)
            p.stamina = stamina.value

        # Clamp players to pitch
        for p in self.players:
            self.collision.clamp_to_pitch(p)

        # Play phase transition
        if self.phase in (MatchPhase.KICK_OFF, MatchPhase.IN_PLAY):
            carrier = self._find_ball_carrier()
            if carrier:
                if carrier.team == "home":
                    self.play_phase = PlayPhase.ATTACK if carrier.x > PITCH_LENGTH * 0.2 else PlayPhase.BUILD_UP
                else:
                    self.play_phase = PlayPhase.ATTACK if carrier.x < -PITCH_LENGTH * 0.2 else PlayPhase.BUILD_UP
            else:
                self.play_phase = PlayPhase.TRANSITION

        # Replay recording
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

        # Record events to the event recorder
        for pid, evt in tick_events.items():
            if pid.startswith("_") or not isinstance(evt, dict):
                continue
            atype = evt.get("type", "")
            success = evt.get("success", False)
            data = evt.get("data", {})
            if atype in ("pass", "shoot", "cross", "tackle", "intercept", "dribble_contest"):
                etype = {
                    "pass": EventType.PASS, "shoot": EventType.SHOOT,
                    "cross": EventType.CROSS, "tackle": EventType.TACKLE,
                    "intercept": EventType.INTERCEPT,
                    "dribble_contest": EventType.DRIBBLE,
                }.get(atype, EventType.PASS)
                self.recorder.record(self.tick, Event(
                    tick=self.tick, event_type=etype, actor=pid,
                    success=success, data=data,
                ))
                self._record_history(pid, data)
            elif atype == "goal":
                self.recorder.record(self.tick, Event(
                    tick=self.tick, event_type=EventType.GOAL,
                    data=data,
                ))

        # OOB / Offside / Penalty events
        if "_oob" in tick_events:
            oob_type = tick_events["_oob"].get("type", "throw_in")
            self.recorder.record(self.tick, Event(
                tick=self.tick,
                event_type=EventType.THROW_IN if oob_type == "throw_in" else EventType.GOAL_KICK,
            ))
        if "_offside" in tick_events:
            self.recorder.record(self.tick, Event(
                tick=self.tick, event_type=EventType.GOAL_KICK,
                data={"offside_player": tick_events["_offside"]["data"].get("player")},
            ))
        if "_penalty" in tick_events:
            self.recorder.record(self.tick, Event(
                tick=self.tick, event_type=EventType.GOAL,
                data={"penalty_awarded": tick_events["_penalty"]["team"]},
            ))

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
            # Use decide_with_context for policies that support it
            from try1000_engine.ai.generated_policy import GeneratedPolicy
            if isinstance(policy, (RuleBasedPolicy, GeneratedPolicy)):
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
    # Phase 3: Validate
    # ═══════════════════════════════════════════════════════════════

    def _phase3_validate(self, decisions: dict[str, ActionOutput],
                         snapshot: Snapshot) -> dict[str, ActionOutput]:
        """Validate decisions: cooldown enforcement, range checks."""
        validated = {}
        for pid, action in decisions.items():
            player = self._find_player(pid)

            # Cooldown check
            if player and player.is_on_cooldown:
                at = ActionType(action.action_type)
                if at.triggers_cooldown:
                    validated[pid] = ActionOutput.hold()
                    continue

            # Range checks
            action = self._clamp_action(action)
            validated[pid] = action

        return validated

    def _clamp_action(self, action: ActionOutput) -> ActionOutput:
        """Ensure action parameters are within valid ranges."""
        action.dx = max(-1.0, min(1.0, action.dx))
        action.dy = max(-1.0, min(1.0, action.dy))
        action.speed = max(0.0, min(1.0, action.speed))
        action.power = max(1.0, min(20.0, action.power))
        action.target_x = max(0.0, min(1.0, action.target_x))
        action.target_y = max(0.0, min(1.0, action.target_y))
        return action

    # ═══════════════════════════════════════════════════════════════
    # Phase 4: Player Movement
    # ═══════════════════════════════════════════════════════════════

    def _phase4_movement(self, decisions: dict[str, ActionOutput],
                         snapshot: Snapshot):
        """Apply Move and Dribble using PMS compute_move_result.
        Idle players (Hold) drift toward formation anchor via apply_snap."""
        for pid, action in decisions.items():
            player = self._find_player(pid)
            if player is None:
                continue

            at = ActionType(action.action_type)
            if at in (ActionType.MOVE, ActionType.DRIBBLE):
                # Use PMS for movement: direction, speed, player attributes
                new_pos = compute_move_result(
                    current_pos=(player.x, player.y),
                    dx=action.dx, dy=action.dy,
                    speed_ratio=action.speed,
                    player_attr=player.pace,
                    role=player.role,
                )
                player.x, player.y = new_pos
                # Blur ball slightly toward carrier when dribbling
                if at == ActionType.DRIBBLE and player.has_ball:
                    self.ball.x += (player.x - self.ball.x) * 0.8
                    self.ball.y += (player.y - self.ball.y) * 0.8
            else:
                # Idle: snap toward formation anchor (discipline drift)
                anchor = self._get_anchor(player)
                new_pos = apply_snap(
                    current_pos=(player.x, player.y),
                    anchor_pos=anchor,
                    discipline=player.awareness / 100.0,
                )
                player.x, player.y = new_pos

    # ═══════════════════════════════════════════════════════════════
    # Phase 5: Ball Actions
    # ═══════════════════════════════════════════════════════════════

    def _phase5_ball_actions(self, decisions: dict[str, ActionOutput],
                             snapshot: Snapshot):
        """Resolve Pass, Shoot, and Cross actions."""
        for pid, action in decisions.items():
            player = self._find_player(pid)
            if player is None:
                continue

            at = ActionType(action.action_type)
            event_data = None

            if at == ActionType.PASS:
                event_data = self.pass_action.resolve(
                    player, self.ball, self.players, self.rng, action)
            elif at == ActionType.SHOOT:
                event_data = self.shoot_action.resolve(
                    player, self.ball, self.players, self.rng, action)
                # Track xG
                if event_data:
                    xg = event_data.get("xg", 0)
                    if player.team == "home":
                        pass  # xG accumulated in result
            elif at == ActionType.CROSS:
                event_data = self.cross_action.resolve(
                    player, self.ball, self.players, self.rng, action)

            if event_data:
                self.recorder.record(self.tick, Event(
                    tick=self.tick,
                    event_type=_ACTION_TO_EVENT[at],
                    actor=pid,
                    success=event_data.get("success", False),
                    data=event_data,
                ))
                self._record_history(pid, event_data)

                # Trigger cooldown
                player.trigger_cooldown(COOLDOWN_DURATION_TICKS)

    # ═══════════════════════════════════════════════════════════════
    # Phase 6: Tackles
    # ═══════════════════════════════════════════════════════════════

    def _phase6_tackles(self, decisions: dict[str, ActionOutput],
                        snapshot: Snapshot):
        """Resolve Tackle actions."""
        for pid, action in decisions.items():
            player = self._find_player(pid)
            if player is None:
                continue

            at = ActionType(action.action_type)
            if at != ActionType.TACKLE:
                continue

            # Find target - the nearest opponent
            opponents = snapshot.away_players if player.team == "home" else snapshot.home_players
            nearest = self._nearest_opponent(player, opponents)
            if nearest:
                action.target_player_id = nearest.player_id

            event_data = self.tackle_action.resolve(
                player, self.ball, self.players, self.rng, action)

            if event_data:
                self.recorder.record(self.tick, Event(
                    tick=self.tick,
                    event_type=EventType.TACKLE,
                    actor=pid,
                    success=event_data.get("success", False),
                    data=event_data,
                ))
                self._record_history(pid, event_data)
                player.trigger_cooldown(COOLDOWN_DURATION_TICKS)

    # ═══════════════════════════════════════════════════════════════
    # Phase 7: Finalize
    # ═══════════════════════════════════════════════════════════════

    def _phase7_finalize(self, snapshot: Snapshot):
        """Ball physics, goal detection, stamina, possession, replay recording."""

        # 7a. Update ball physics via BPS
        carrier = self._find_ball_carrier()
        if carrier and self.ball.carrier_id == carrier.player_id:
            # Ball carried: stays at carrier's position
            self.ball.x = carrier.x
            self.ball.y = carrier.y
            self.ball.vx = 0.0
            self.ball.vy = 0.0
        else:
            # Loose ball: use BPS advance
            new_pos, new_vel, oob = advance_ball(
                ball_pos=(self.ball.x, self.ball.y),
                ball_vel=(self.ball.vx, self.ball.vy),
                landing_zone=getattr(self, '_pass_landing_zone', None),
            )
            self.ball.x, self.ball.y = new_pos
            self.ball.vx, self.ball.vy = new_vel
            if oob:
                self.recorder.record(self.tick, Event(
                    tick=self.tick,
                    event_type=EventType.THROW_IN if abs(self.ball.y) < PITCH_WIDTH * 0.4 else EventType.GOAL_KICK if abs(self.ball.x) > PITCH_LENGTH * 0.48 else EventType.THROW_IN,
                ))
            # BPS ball control contest for loose balls
            winner = resolve_ball_control(self.players, new_pos, new_vel, self.rng)
            if winner and not oob:
                carrier_p = self._find_player(winner)
                if carrier_p:
                    self.ball.carrier_id = winner
                    self.ball.last_touch_team = carrier_p.team
                    self.ball.vx = 0.0
                    self.ball.vy = 0.0

        # 7b. Automatic interceptions
        for p in self.players:
            if p.team != self.ball.last_touch_team:  # only intercept opponent passes
                event_data = self.intercept_action.try_intercept(
                    p, self.ball, self.players, self.rng)
                if event_data:
                    self.recorder.record(self.tick, Event(
                        tick=self.tick,
                        event_type=EventType.INTERCEPT,
                        actor=p.player_id,
                        success=True,
                        data=event_data,
                    ))

        # 7c. Cross resolution: ball in box + teammate nearby → header/shot
        if self.ball.in_air and self._ball_in_penalty_area():
            receiver = self._find_attacker_in_box(self.ball.last_touch_team)
            if receiver:
                # Auto-resolve as a shot from the cross
                shot_xg = self._cross_header_xg(receiver)
                goal = self.rng.random() < shot_xg
                if goal:
                    if receiver.team == "home":
                        self.home_score += 1
                    else:
                        self.away_score += 1
                    self.recorder.record(self.tick, Event(
                        tick=self.tick, event_type=EventType.GOAL,
                        actor=receiver.player_id,
                        data={"scorer": receiver.team, "xg": round(shot_xg, 4),
                              "type": "header", "assist": self.ball.last_touch_player}
                    ))
                    self.phase = MatchPhase.GOAL_SCORED
                    self._goal_pause_remaining = GOAL_RESET_TICKS
                    self._conceding_team = "away" if receiver.team == "home" else "home"
                    self._reset_positions()
                else:
                    self.recorder.record(self.tick, Event(
                        tick=self.tick, event_type=EventType.SHOOT,
                        actor=receiver.player_id,
                        data={"type": "header", "xg": round(shot_xg, 4),
                              "outcome": "save" if self.rng.random() < 0.3 else "miss",
                              "team": receiver.team}
                    ))
                # Ball goes out or is claimed by keeper after header attempt
                self.ball.vx = 0
                self.ball.vy = 0
                self.ball.in_air = False

        # 7d. Goal detection (direct shots)
        goal_team = self.ball.is_goal()
        if goal_team == "home":
            self.home_score += 1
            self.recorder.record(self.tick, Event(
                tick=self.tick, event_type=EventType.GOAL,
                data={"scorer": "home"}
            ))
            self.phase = MatchPhase.GOAL_SCORED
            self._goal_pause_remaining = GOAL_RESET_TICKS
            self._conceding_team = "home"
            self._reset_positions()
        elif goal_team == "away":
            self.away_score += 1
            self.recorder.record(self.tick, Event(
                tick=self.tick, event_type=EventType.GOAL,
                data={"scorer": "away"}
            ))
            self.phase = MatchPhase.GOAL_SCORED
            self._goal_pause_remaining = GOAL_RESET_TICKS
            self._conceding_team = "away"
            self._reset_positions()

        # 7d. Out of play check
        out = self.ball.is_out_of_play()
        if out:
            self.phase = PlayPhase.SET_PIECE
            self.recorder.record(self.tick, Event(
                tick=self.tick,
                event_type=EventType.THROW_IN if out == "throw_in" else EventType.GOAL_KICK,
            ))

        # 7e. Ball possession handled by BPS resolve_ball_control above

        # Sync has_ball flag with ball.carrier_id
        for p in self.players:
            p.has_ball = (p.player_id == self.ball.carrier_id)

        # 7f. Track possession ticks
        current_possessor = self._find_ball_carrier()
        if current_possessor:
            self._possession_ticks[current_possessor.team] += 1

        # 7g. Stamina update
        for p in self.players:
            speed = p.current_speed
            stamina = Stamina(p.stamina)
            stamina.update(speed, TICK_DURATION)
            p.stamina = stamina.value

        # 7h. Phase transitions
        if self.phase in (MatchPhase.KICK_OFF, MatchPhase.IN_PLAY):
            carrier = self._find_ball_carrier()
            if carrier:
                if carrier.team == "home":
                    if carrier.x > PITCH_LENGTH * 0.2:  # in opponent half
                        self.play_phase = PlayPhase.ATTACK
                    else:
                        self.play_phase = PlayPhase.BUILD_UP
                else:
                    if carrier.x < -PITCH_LENGTH * 0.2:
                        self.play_phase = PlayPhase.ATTACK
                    else:
                        self.play_phase = PlayPhase.BUILD_UP
            else:
                self.play_phase = PlayPhase.TRANSITION

        # 7i. Clamp players to pitch
        for p in self.players:
            self.collision.clamp_to_pitch(p)

        # 7j. Record replay (with sampling for large batches)
        if self.record_replay and self.replay and self.tick % self.replay_sample_rate == 0:
            self.replay.record_tick(
                tick=self.tick,
                players=self.players,
                ball=self.ball,
                home_score=self.home_score,
                away_score=self.away_score,
                phase=self.phase.name,
                events=self.recorder.get_tick_events(self.tick),
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
        # Enforce legal kickoff positions: non-kickoff players in own half, outside center circle
        circle_r_sq = CENTER_CIRCLE_RADIUS * CENTER_CIRCLE_RADIUS
        for p in self.players:
            if p.has_ball:
                p.x = 0.0
                p.y = 0.0
                continue
            # Determine correct half for this player
            in_own_half = (p.x <= 0) if p.team == kickoff_team else (p.x >= 0)
            dist_sq = p.x * p.x + p.y * p.y
            if not in_own_half or dist_sq < circle_r_sq:
                # Push player to correct half, outside circle
                sign = -1.0 if p.team == kickoff_team else 1.0
                push_dist = CENTER_CIRCLE_RADIUS + 2.0
                if abs(p.y) < 0.1:
                    p.y = 3.0  # avoid exact center
                angle = math.atan2(p.y, sign * abs(p.x) if p.x != 0 else 1.0)
                p.x = sign * push_dist * abs(math.cos(angle)) + (sign * 2.0)
                # Clamp to pitch bounds
                half_l = PITCH_LENGTH / 2
                p.x = max(-half_l, min(half_l, p.x))
        self.phase = MatchPhase.KICK_OFF
        self.play_phase = PlayPhase.KICK_OFF

    def _swap_directions(self):
        """Swap all players' coordinates around the center line (mirror x).
        References AgentPitch's half-time direction swap."""
        for p in self.players:
            p.x = -p.x
        # Swap ball too
        if self.ball:
            self.ball.x = -self.ball.x

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
        self._possession_ticks = {"home": 0, "away": 0}

        if self.replay:
            self.replay.open()

        # Setup kickoff — home team starts
        self._kickoff_team = "home"
        self._second_half_kickoff_team = "away"
        self._setup_kickoff(self._kickoff_team)

    def _reset_positions(self):
        """Reset players to formation anchor positions (FRS)."""
        from try1000_engine.match.formation import compute_anchors, mirror_anchors
        formation = getattr(self, '_formation', "4-3-3")
        home_p = [p for p in self.players if p.team == "home"]
        away_p = [p for p in self.players if p.team == "away"]
        home_anchors = compute_anchors(formation, home_p)
        away_anchors = mirror_anchors(compute_anchors(formation, away_p))
        for p in self.players:
            anchor = home_anchors.get(p.player_id) or away_anchors.get(p.player_id)
            if anchor:
                p.x, p.y = anchor

    def _get_anchor(self, player: Player) -> tuple[float, float]:
        """Return the formation anchor position for a player (FRS)."""
        from try1000_engine.match.formation import compute_anchors, mirror_anchors
        formation = getattr(self, '_formation', "4-3-3")
        team_players = [p for p in self.players if p.team == player.team]
        anchors = compute_anchors(formation, team_players)
        if player.team == "away":
            anchors = mirror_anchors(anchors)
        return anchors.get(player.player_id, (player.x, player.y))

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

    def _nearest_opponent(self, player: Player, opponents: list[Player]) -> Player | None:
        nearest = None
        min_dist = float("inf")
        for opp in opponents:
            d = player.distance_to(opp.x, opp.y)
            if d < min_dist:
                min_dist = d
                nearest = opp
        return nearest

    def _ball_in_penalty_area(self) -> bool:
        """Check if ball is inside either penalty area."""
        half_length = PITCH_LENGTH / 2
        from try1000_engine.config import PENALTY_AREA_LENGTH, PENALTY_AREA_WIDTH
        pa_len = PENALTY_AREA_LENGTH
        pa_width = PENALTY_AREA_WIDTH / 2
        bx, by = self.ball.x, self.ball.y
        # Home penalty area (away team's attacking end): x > half_length - pa_len
        if bx > half_length - pa_len and abs(by) < pa_width:
            return True
        # Away penalty area (home team's attacking end): x < -half_length + pa_len
        if bx < -half_length + pa_len and abs(by) < pa_width:
            return True
        return False

    def _find_attacker_in_box(self, team: str | None) -> Player | None:
        """Find an attacking player in the penalty area near the ball."""
        if team is None:
            return None
        attackers = [p for p in self.players if p.team == team]
        if not attackers:
            return None
        # Find nearest attacker to ball within 10m
        nearest = None
        min_dist = float("inf")
        for p in attackers:
            d = p.distance_to(self.ball.x, self.ball.y)
            if d < min_dist:
                min_dist = d
                nearest = p
        if nearest and min_dist < 10.0:
            return nearest
        return None

    def _cross_header_xg(self, attacker: Player) -> float:
        """xG for a header/volley from a cross. Depends on attacker attributes + position."""
        # Distance from goal center
        half_length = PITCH_LENGTH / 2
        goal_x = half_length if attacker.team == "home" else -half_length
        dist = ((attacker.x - goal_x) ** 2 + attacker.y ** 2) ** 0.5
        # Base xG: close range header
        if dist < 6: base = 0.25
        elif dist < 10: base = 0.12
        elif dist < 14: base = 0.05
        else: base = 0.02
        skill_mod = 0.5 + (attacker.shooting / 100.0) * 0.5
        comp_mod = 0.6 + (attacker.composure / 100.0) * 0.6
        return base * skill_mod * comp_mod

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
