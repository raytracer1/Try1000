"""Event types and recording during match simulation."""

from dataclasses import dataclass, field
from enum import IntEnum


class EventType(IntEnum):
    """Types of match events."""
    PASS = 0
    SHOOT = 1
    CROSS = 2
    DRIBBLE = 3
    TACKLE = 4
    INTERCEPT = 5
    GOAL = 6
    SAVE = 7
    MISS = 8
    BLOCK = 9
    FOUL = 10
    OFFSIDE = 11
    CORNER = 12
    THROW_IN = 13
    GOAL_KICK = 14
    HALF_TIME = 15
    FULL_TIME = 16
    KICKOFF = 17
    POSSESSION_CHANGE = 18
    PLAYER_PICKUP = 19


@dataclass
class Event:
    """A single event within a tick."""
    tick: int
    event_type: EventType
    actor: str | None = None       # player_id
    target: str | None = None      # player_id or zone
    success: bool = True
    data: dict = field(default_factory=dict)  # type-specific payload

    def to_dict(self) -> dict:
        return {
            "type": self.event_type.name.lower(),
            "actor": self.actor,
            "target": self.target,
            "success": self.success,
            **self.data,
        }


class EventRecorder:
    """Records events for a single match. Events are flushed to replay per tick."""

    def __init__(self):
        self.tick_events: dict[int, list[Event]] = {}  # tick → events

    def record(self, tick: int, event: Event):
        """Record an event at the current tick."""
        if tick not in self.tick_events:
            self.tick_events[tick] = []
        self.tick_events[tick].append(event)

    def get_tick_events(self, tick: int) -> list[dict]:
        """Get events for a tick as dicts (for replay output)."""
        events = self.tick_events.get(tick, [])
        return [e.to_dict() for e in events]

    def all_events(self) -> list[Event]:
        """All events sorted by tick."""
        result = []
        for tick in sorted(self.tick_events.keys()):
            result.extend(self.tick_events[tick])
        return result

    def count_by_type(self, event_type: EventType) -> int:
        """Count events of a specific type."""
        count = 0
        for events in self.tick_events.values():
            count += sum(1 for e in events if e.event_type == event_type)
        return count
