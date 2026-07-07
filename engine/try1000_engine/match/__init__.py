"""Match module — tick loop, event recording, replay output, and result computation."""

from try1000_engine.match.match_engine import MatchEngine, Snapshot, Phase
from try1000_engine.match.event_system import Event, EventType, EventRecorder
from try1000_engine.match.replay import ReplayRecorder
from try1000_engine.match.result import MatchResult

__all__ = [
    "MatchEngine", "Snapshot", "Phase",
    "Event", "EventType", "EventRecorder",
    "ReplayRecorder", "MatchResult",
]
