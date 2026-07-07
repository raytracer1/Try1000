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
)
from try1000_engine.physics.ball import Ball
from try1000_engine.physics.player import Player
from try1000_engine.physics.collision import CollisionSystem
from try1000_engine.physics.stamina import Stamina

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


class Phase(IntEnum):
    """Match phases — determines AI behavior flavor."""
    KICKOFF = 0
    BUILD_UP = 1
    ATTACK = 2
    DEFENSE = 3
    TRANSITION = 4
    SET_PIECE = 5
    FINISHED = 6


@dataclass
class Snapshot:
    """Frozen match state at the start of a tick. Phase 1 builds this."""
    tick: int
    ball: Ball
    players: list[Player]      # deep-copied positions for this tick
    phase: Phase
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

    Attributes:
        home_policy: Decision policy for home team players.
        away_policy: Decision policy for away team players.
        rng: Seeded random number generator for deterministic output.
        record_replay: Whether to record per-tick position snapshots.
    """

    def __init__(
        self,
        home_policy: Policy | None = None,
        away_policy: Policy | None = None,
        seed: int = 42,
        record_replay: bool = True,
        fast_mode: bool = False,
    ):
        self.home_policy = home_policy or RuleBasedPolicy()
        self.away_policy = away_policy or RuleBasedPolicy()
        self.rng = random.Random(seed)
        self.record_replay = record_replay
        self.fast_mode = fast_mode
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
        self.phase: Phase = Phase.KICKOFF
        self.home_score: int = 0
        self.away_score: int = 0
        self.tick: int = 0
        self.recorder: EventRecorder | None = None
        self.replay: ReplayRecorder | None = None
        self._history: dict[str, list[dict]] = {}  # player_id → recent events
        self._circuit_breaker: dict[str, int] = {}  # player_id → consecutive failures
        self._possession_ticks: dict[str, int] = {"home": 0, "away": 0}

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

            # Half-time check
            if self.tick == self._half_time_tick:
                self.recorder.record(self.tick, Event(
                    tick=self.tick, event_type=EventType.HALF_TIME
                ))

            if self.phase == Phase.FINISHED:
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
        """Execute one tick (1 second) through all 7 phases."""
        # Phase 1: Build snapshot
        snapshot = self._phase1_snapshot()

        # Phase 2: AI decisions for each player
        decisions: dict[str, ActionOutput] = {}
        for player in self.players:
            decisions[player.player_id] = self._phase2_decide(player, snapshot)

        # Phase 3: Validate actions
        decisions = self._phase3_validate(decisions, snapshot)

        # Phase 4: Apply player movement
        self._phase4_movement(decisions, snapshot)

        # Phase 5: Resolve ball actions (Pass, Shoot, Cross)
        self._phase5_ball_actions(decisions, snapshot)

        # Phase 6: Resolve tackles
        self._phase6_tackles(decisions, snapshot)

        # Phase 7: Ball physics, goal detection, stamina, record
        self._phase7_finalize(snapshot)

        # Increment tick
        self.tick += 1
        for p in self.players:
            p.update_cooldown()

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

        # Choose policy
        policy = self.home_policy if player.team == "home" else self.away_policy

        try:
            # Use rule_based decide_with_context for full perception pipeline
            if isinstance(policy, RuleBasedPolicy):
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
                    phase_id=int(self.phase),
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
        policy = self.home_policy if player.team == "home" else self.away_policy
        if isinstance(policy, RuleBasedPolicy):
            tactic = policy.tactic

        return self.perception.build_observation(
            player=player, teammates=teammates, opponents=opponents,
            ball=snapshot.ball, home_score=snapshot.home_score,
            away_score=snapshot.away_score, tick=snapshot.tick,
            max_ticks=self._max_ticks,
            half=1 if snapshot.tick < self._half_time_tick else 2,
            phase_id=int(self.phase),
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
        """Apply Move and Dribble actions to update player positions."""
        for pid, action in decisions.items():
            player = self._find_player(pid)
            if player is None:
                continue

            at = ActionType(action.action_type)
            if at == ActionType.MOVE:
                self.move_action.resolve(player, snapshot.ball, self.players, self.rng, action)
            elif at == ActionType.DRIBBLE:
                self.dribble_action.resolve(player, snapshot.ball, self.players, self.rng, action)

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

        # 7a. Update ball physics
        self.ball.update(TICK_DURATION)

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
                    self.phase = Phase.KICKOFF
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
            self.phase = Phase.KICKOFF
            self._reset_positions()
        elif goal_team == "away":
            self.away_score += 1
            self.recorder.record(self.tick, Event(
                tick=self.tick, event_type=EventType.GOAL,
                data={"scorer": "away"}
            ))
            self.phase = Phase.KICKOFF
            self._reset_positions()

        # 7d. Out of play check
        out = self.ball.is_out_of_play()
        if out:
            self.phase = Phase.SET_PIECE
            self.recorder.record(self.tick, Event(
                tick=self.tick,
                event_type=EventType.THROW_IN if out == "throw_in" else EventType.GOAL_KICK,
            ))

        # 7e. Ball possession (nearest player picks up loose ball)
        self.collision.resolve_ball_possession(self.ball, self.players)

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
        if self.phase not in (Phase.KICKOFF, Phase.SET_PIECE, Phase.FINISHED):
            carrier = self._find_ball_carrier()
            if carrier:
                if carrier.team == "home":
                    if carrier.x > PITCH_LENGTH * 0.2:  # in opponent half
                        self.phase = Phase.ATTACK
                    else:
                        self.phase = Phase.BUILD_UP
                else:
                    if carrier.x < -PITCH_LENGTH * 0.2:
                        self.phase = Phase.ATTACK
                    else:
                        self.phase = Phase.BUILD_UP
            else:
                self.phase = Phase.TRANSITION

        # 7i. Clamp players to pitch
        for p in self.players:
            self.collision.clamp_to_pitch(p)

        # 7j. Record replay
        if self.record_replay and self.replay:
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
    # Helpers
    # ═══════════════════════════════════════════════════════════════

    def _init_match(self, home_players: list[Player], away_players: list[Player],
                    replay_path: str | None):
        """Initialize match state."""
        self.ball = Ball(0.0, 0.0)
        self.players = home_players + away_players
        self.phase = Phase.KICKOFF
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

        # Set initial kickoff positions
        self._reset_positions()

        # Give ball to the nearest home player (not GK) at kickoff
        home_outfield = [p for p in home_players if p.role != "GK"]
        if home_outfield:
            nearest = min(home_outfield, key=lambda p: p.distance_to(self.ball.x, self.ball.y))
            nearest.has_ball = True
            self.ball.last_touch_team = nearest.team
            self.ball.last_touch_player = nearest.player_id

    def _reset_positions(self):
        """Reset players to base formation positions after a goal or at kickoff."""
        for p in self.players:
            if p.role == "GK":
                p.x = -PITCH_LENGTH * 0.45 if p.team == "home" else PITCH_LENGTH * 0.45
                p.y = 0.0
            elif "CB" in p.role:
                p.x = -PITCH_LENGTH * 0.35 if p.team == "home" else PITCH_LENGTH * 0.35
                p.y = -15.0 if "1" in p.player_id else 15.0
            else:
                # Simplified: circle around center
                angle = hash(p.player_id) % 360
                rad = math.radians(angle)
                dist = 15.0
                p.x = math.cos(rad) * dist
                p.y = math.sin(rad) * dist
                if p.team == "away":
                    p.x = -p.x

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
