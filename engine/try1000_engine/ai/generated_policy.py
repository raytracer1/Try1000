"""GeneratedPolicy — runs LLM-generated decide() code as a Policy.

Compiles Python code from the LLM into an executable function, then calls it
during Phase 2 of each tick. The code is compiled once, cached, and runs
at full speed — no LLM calls during simulation.
"""

from __future__ import annotations

import math
from typing import Any

from try1000_engine.ai.policy import Policy, Observation
from try1000_engine.actions.base import ActionOutput, ActionType
from try1000_engine.ai.perception import Perception


# ═══════════════════════════════════════════════════════════════
# Action normalization — converts LLM output dict → ActionOutput
# ═══════════════════════════════════════════════════════════════

_ACTION_MAP = {
    "hold": ActionType.HOLD,
    "move": ActionType.MOVE,
    "pass": ActionType.PASS,
    "shoot": ActionType.SHOOT,
    "cross": ActionType.CROSS,
    "dribble": ActionType.DRIBBLE,
    "tackle": ActionType.TACKLE,
    "intercept": ActionType.INTERCEPT,
}


def _normalize_action(raw: dict) -> ActionOutput:
    """Convert LLM output dict to a validated ActionOutput."""
    action_name = str(raw.get("action", "Hold")).lower()
    action_type = _ACTION_MAP.get(action_name, ActionType.HOLD)

    def clamp(v, lo, hi, default):
        try:
            return max(lo, min(hi, float(v)))
        except (TypeError, ValueError):
            return float(default)

    return ActionOutput(
        action_type=int(action_type),
        dx=clamp(raw.get("dx", 0), -1.0, 1.0, 0),
        dy=clamp(raw.get("dy", 0), -1.0, 1.0, 0),
        speed=clamp(raw.get("speed", 0.5), 0.0, 1.0, 0.5),
        power=clamp(raw.get("power", 10), 1.0, 20.0, 10),
        angle=clamp(raw.get("angle", 0), -90.0, 90.0, 0),
        target_x=clamp(raw.get("target_x", 0.5), 0.0, 1.0, 0.5),
        target_y=clamp(raw.get("target_y", 0.5), 0.0, 1.0, 0.5),
        target_player_id=int(raw.get("target_player_id", 0)),
    )


# ═══════════════════════════════════════════════════════════════
# Sandbox — safe execution environment for generated code
# ═══════════════════════════════════════════════════════════════

def _safe_builtins() -> dict:
    """Return a restricted set of Python builtins safe for generated code."""
    return {
        "True": True,
        "False": False,
        "None": None,
        "abs": abs,
        "min": min,
        "max": max,
        "sum": sum,
        "len": len,
        "range": range,
        "enumerate": enumerate,
        "zip": zip,
        "sorted": sorted,
        "list": list,
        "dict": dict,
        "tuple": tuple,
        "set": set,
        "int": int,
        "float": float,
        "str": str,
        "bool": bool,
        "round": round,
        "math": math,  # allowed: sin, cos, sqrt, atan2, etc.
        "isinstance": isinstance,
        "ValueError": ValueError,
        "TypeError": TypeError,
        "Exception": Exception,
    }


class SandboxError(Exception):
    """Raised when generated code fails to compile or execute."""
    pass


# ═══════════════════════════════════════════════════════════════
# Generated Policy
# ═══════════════════════════════════════════════════════════════

class GeneratedPolicy(Policy):
    """A Policy backed by LLM-generated Python code.

    The code is compiled once at construction time. Each call to decide()
    executes the compiled function — no LLM calls, sandboxing, or code
    generation during the match.

    Usage:
        code = generator.generate(role="ST", tactic={...})
        policy = GeneratedPolicy(code=code, role="ST")
        # Use policy in MatchEngine — runs at full speed
    """

    def __init__(self, code: str, role: str = "unknown",
                 tactic: dict | None = None):
        self.code = code
        self.role = role
        self.tactic = tactic or {}
        self._decide_fn = self._compile(code)
        self._code_hash = hex(abs(hash(code)) % (10 ** 8))[2:]

    # ─── Policy interface ───

    def decide_with_context(
        self,
        player: Any,
        teammates: list,
        opponents: list,
        ball: Any,
        home_score: int, away_score: int,
        tick: int, max_ticks: int,
        half: int, phase_id: int,
        history_actions: list[dict] | None = None,
    ) -> tuple[ActionOutput, dict]:
        """Full-context decision — preferred by MatchEngine over generic decide()."""
        gs = self._build_gamestate_full(
            player, teammates, opponents, ball,
            home_score, away_score, tick, half,
        )
        ps = self._build_playerstate_full(player)
        hist = self._build_history_full(history_actions)

        try:
            result = self._decide_fn(gs, ps, hist)
            if not isinstance(result, dict):
                return ActionOutput.hold(), {}
            return _normalize_action(result), {}
        except Exception:
            return ActionOutput.hold(), {}

    def decide(self, obs: Observation) -> ActionOutput:
        """Execute the generated code on this observation.

        Converts Observation → game_state + player_state dicts,
        calls the generated function, and normalizes the result.
        """
        gs = self._obs_to_gamestate(obs)
        ps = self._obs_to_playerstate(obs)
        hist = self._obs_to_history(obs)

        try:
            result = self._decide_fn(gs, ps, hist)
            if not isinstance(result, dict):
                return ActionOutput.hold()
            return _normalize_action(result)
        except Exception:
            # Fallback: Hold on any error
            return ActionOutput.hold()

    def name(self) -> str:
        return f"Gen-{self.role}-{self._code_hash}"

    # ─── Compilation ───

    def _compile(self, code: str):
        """Compile the LLM-generated code into an executable function.

        Uses Python's built-in compile() with a restricted namespace.
        No RestrictedPython dependency — safe enough for code we trust
        (LLM-generated but validated).
        """
        try:
            bytecode = compile(code, "<generated_policy>", "exec")
        except SyntaxError as e:
            raise SandboxError(f"Generated code has syntax error: {e}") from e

        namespace = _safe_builtins()
        try:
            exec(bytecode, namespace)
        except Exception as e:
            raise SandboxError(f"Generated code failed to execute: {e}") from e

        decide_fn = namespace.get("decide")
        if not callable(decide_fn):
            raise SandboxError(
                "Generated code must define a 'decide' function. "
                f"Found: {list(namespace.keys())[-10:]}"
            )

        return decide_fn

    # ─── Full-context builders (matches LLM system prompt format) ───

    def _build_gamestate_full(self, player, teammates, opponents, ball,
                              home_score, away_score, tick, half):
        my_team = player.team
        opp_goal_x = 1.0 if my_team == "home" else 0.0
        my_goal_x = 0.0 if my_team == "home" else 1.0

        def to_norm(x, y):
            from try1000_engine.config import meters_to_normalized
            nx, ny = meters_to_normalized(x, y)
            return [nx, ny]

        def player_info(p):
            return {
                "id": str(p.player_id),
                "role": p.role,
                "position": to_norm(p.x, p.y),
                "has_ball": bool(p.has_ball),
            }

        return {
            "tick": tick,
            "match_time_seconds": tick,
            "half": half,
            "score": {"home": home_score, "away": away_score},
            "ball": {
                "position": to_norm(ball.x, ball.y),
                "possession_team": ball.last_touch_team or (player.team if ball.carrier_id else None),
                "carrier_id": str(ball.carrier_id) if ball.carrier_id else None,
            },
            "my_team": my_team,
            "my_player_id": str(player.player_id),
            "teammates": [player_info(p) for p in teammates],
            "opponents": [player_info(p) for p in opponents],
            "field": {
                "width": 68.0, "height": 105.0,
                "my_goal_x": my_goal_x, "opponent_goal_x": opp_goal_x,
                "goal_top": 0.44, "goal_bottom": 0.56,
            },
        }

    def _build_playerstate_full(self, player):
        return {
            "role": player.role,
            "position": [0.5, 0.5],  # will be overridden by game_state
            "pace": int(player.pace or 70), "shooting": int(player.shooting or 70),
            "passing": int(player.passing or 70), "dribbling": int(player.dribbling or 70),
            "defending": int(player.defending or 70), "physicality": int(player.physicality or 70),
            "stamina": int(player.stamina or 100), "awareness": int(player.awareness or 70),
            "composure": int(player.composure or 70),
            "has_ball": bool(player.has_ball),
            "health": 1.0,
            "on_cooldown": bool(player.is_on_cooldown),
        }

    def _build_history_full(self, history_actions):
        if not history_actions:
            return []
        return [{"tick": -i, "action": h.get("action", "Hold"), "success": h.get("success", False)}
                for i, h in enumerate(history_actions[:20])]

    # ─── Observation → dict conversion (for legacy generic Policy interface) ───

    def _obs_to_gamestate(self, obs: Observation) -> dict:
        """Convert Observation to the game_state dict the generated code expects."""
        # Determine goal positions based on team context
        # We assume: ball_possession_team > 0 means "home" perspective
        my_team = "home"  # Default; overridden per-player during actual match
        opponent_goal_x = 0.95  # normalized, attacking right
        my_goal_x = 0.05

        return {
            "tick": 0,
            "match_time_seconds": obs.match_time_ratio * 5400,
            "half": obs.half,
            "score": {
                "home": obs.score_diff if obs.score_diff > 0 else 0,
                "away": abs(obs.score_diff) if obs.score_diff < 0 else 0,
            },
            "ball": {
                "position": [obs.ball_x, obs.ball_y],
                "possession_team": (
                    "home" if obs.ball_possession_team == 1 else
                    "away" if obs.ball_possession_team == -1 else None
                ),
                "carrier_id": None,
            },
            "my_team": my_team,
            "my_player_id": "player_0",
            "teammates": self._build_teammates(obs),
            "opponents": self._build_opponents(obs),
            "field": {
                "width": 68.0,
                "height": 105.0,
                "my_goal_x": my_goal_x,
                "opponent_goal_x": opponent_goal_x,
                "goal_top": 0.44,
                "goal_bottom": 0.56,
            },
        }

    def _obs_to_playerstate(self, obs: Observation) -> dict:
        """Convert Observation to the player_state dict."""
        return {
            "role": self.role,
            "position": [obs.ball_x if obs.has_ball else 0.5, obs.ball_y if obs.has_ball else 0.5],
            "pace": round(obs.pace * 100),
            "shooting": round(obs.shooting * 100),
            "passing": round(obs.passing * 100),
            "dribbling": round(obs.dribbling * 100),
            "defending": round(obs.defending * 100),
            "physicality": round(obs.physicality * 100),
            "stamina": round(obs.stamina_obs * 100),
            "awareness": round(obs.awareness * 100),
            "composure": round(obs.composure * 100),
            "has_ball": bool(obs.has_ball),
            "health": obs.health,
            "on_cooldown": False,
        }

    def _obs_to_history(self, obs: Observation) -> list[dict]:
        """Convert Observation history to the format expected by generated code."""
        action_names = ["Hold", "Move", "Pass", "Shoot", "Cross", "Dribble", "Tackle", "Intercept"]
        return [
            {
                "tick": -i,
                "action": action_names[min(a, 7)],
                "success": bool(s),
            }
            for i, (a, s) in enumerate(zip(
                obs.history_action_types,
                obs.history_success_flags,
            ))
        ]

    def _build_teammates(self, obs: Observation) -> list[dict]:
        """Build teammates list with nearest teammate info."""
        if obs.nearest_teammate_distance >= 1.0:
            return []
        angle = obs.nearest_teammate_angle * math.pi
        dist = obs.nearest_teammate_distance * 80.0
        tx = obs.ball_x + math.cos(angle) * dist / 105.0
        ty = obs.ball_y + math.sin(angle) * dist / 68.0
        return [{
            "id": "teammate_0",
            "role": "CM",
            "position": [max(0.0, min(1.0, tx)), max(0.0, min(1.0, ty))],
            "has_ball": False,
        }]

    def _build_opponents(self, obs: Observation) -> list[dict]:
        """Build opponents list with nearest opponent info."""
        if obs.nearest_opponent_distance >= 1.0:
            return []
        angle = obs.nearest_opponent_angle * math.pi
        dist = obs.nearest_opponent_distance * 80.0
        ox = obs.ball_x + math.cos(angle) * dist / 105.0
        oy = obs.ball_y + math.sin(angle) * dist / 68.0
        return [{
            "id": "opponent_0",
            "role": "CB",
            "position": [max(0.0, min(1.0, ox)), max(0.0, min(1.0, oy))],
            "has_ball": False,
        }]
