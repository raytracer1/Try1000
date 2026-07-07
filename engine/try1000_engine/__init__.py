"""Try1000 Engine — Football tactics simulation engine."""

from try1000_engine.config import (
    PITCH_LENGTH,
    PITCH_WIDTH,
    MAX_TICKS,
    TICK_DURATION,
    GOAL_WIDTH,
    GOAL_DEPTH,
    PENALTY_AREA_LENGTH,
    PENALTY_AREA_WIDTH,
)
from try1000_engine.match.match_engine import MatchEngine
from try1000_engine.match.result import MatchResult
from try1000_engine.ai.policy import Policy
from try1000_engine.ai.rule_based import RuleBasedPolicy
from try1000_engine.actions.base import ActionOutput, ActionType

__all__ = [
    # Config
    "PITCH_LENGTH", "PITCH_WIDTH", "MAX_TICKS", "TICK_DURATION",
    "GOAL_WIDTH", "GOAL_DEPTH", "PENALTY_AREA_LENGTH", "PENALTY_AREA_WIDTH",
    # Match
    "MatchEngine", "MatchResult",
    # AI
    "Policy", "RuleBasedPolicy",
    # Actions
    "ActionOutput", "ActionType",
]
