"""Replay data recording and events.jsonl output."""

import json
from typing import TextIO
from try1000_engine.config import meters_to_normalized
from try1000_engine.physics.player import Player
from try1000_engine.physics.ball import Ball


class ReplayRecorder:
    """Records per-tick snapshot data and writes to events.jsonl format.

    Output is JSON Lines: one JSON object per line, one line per tick.
    This is streamable (no need to load entire file) and appendable.
    """

    def __init__(self, file_path: str | None = None):
        self.file_path = file_path
        self._file: TextIO | None = None
        self.ticks: list[dict] = []
        self._tick_count = 0

    def open(self):
        """Open the output file for writing."""
        if self.file_path:
            self._file = open(self.file_path, "w")

    def close(self):
        """Close the output file."""
        if self._file:
            self._file.close()
            self._file = None

    def record_tick(
        self,
        tick: int,
        players: list[Player],
        ball: Ball,
        home_score: int,
        away_score: int,
        phase: str,
        events: list[dict],
    ):
        """Record one tick of match state."""
        tick_data = {
            "t": tick,
            "ball": list(meters_to_normalized(ball.x, ball.y)),
            "players": [
                {
                    "id": p.player_id,
                    "pos": list(meters_to_normalized(p.x, p.y)),
                    "team": p.team,
                    "stamina": round(p.stamina, 1),
                }
                for p in players
            ],
            "events": events,
            "score": [home_score, away_score],
            "phase": phase,
        }

        self.ticks.append(tick_data)
        self._tick_count += 1

        # Stream write if using file
        if self._file:
            self._file.write(json.dumps(tick_data) + "\n")

    def export(self) -> list[dict]:
        """Return all recorded ticks as a list of dicts."""
        return self.ticks

    def export_jsonl(self) -> str:
        """Return all ticks as JSON Lines string."""
        return "\n".join(json.dumps(t) for t in self.ticks)

    @property
    def tick_count(self) -> int:
        return self._tick_count
