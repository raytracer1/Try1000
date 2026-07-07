"""Match result computation and statistics."""

from dataclasses import dataclass, field
from try1000_engine.match.event_system import EventType


@dataclass
class MatchResult:
    """Final result of a simulated match with all statistics."""

    match_index: int
    home_score: int
    away_score: int
    home_xg: float = 0.0
    away_xg: float = 0.0
    home_possession: float = 50.0
    away_possession: float = 50.0

    # Detailed stats
    home_shots: int = 0
    away_shots: int = 0
    home_shots_on_target: int = 0
    away_shots_on_target: int = 0
    home_passes: int = 0
    away_passes: int = 0
    home_pass_accuracy: float = 0.0
    away_pass_accuracy: float = 0.0
    home_tackles: int = 0
    away_tackles: int = 0
    home_fouls: int = 0
    away_fouls: int = 0
    home_interceptions: int = 0
    away_interceptions: int = 0
    home_crosses: int = 0
    away_crosses: int = 0
    home_dribbles: int = 0
    away_dribbles: int = 0

    # Replay data
    replay_ticks: list[dict] = field(default_factory=list)

    def compute_from_events(self, recorder, tick_count: int,
                            home_possession_ticks: int, away_possession_ticks: int):
        """Populate stats from event recorder and possession tracking."""
        total_ticks = max(tick_count, 1)

        self.home_possession = round(home_possession_ticks / total_ticks * 100, 1)
        self.away_possession = round(away_possession_ticks / total_ticks * 100, 1)

        # Count events by team via event data
        for evt in recorder.all_events():
            data = evt.data
            event_type = evt.event_type
            actor_team = data.get("team") or (
                "home" if (evt.actor or "").startswith("home") else
                "away" if (evt.actor or "").startswith("away") else None
            )

            if event_type == EventType.PASS:
                if actor_team == "home":
                    self.home_passes += 1
                    if data.get("success"):
                        self.home_pass_accuracy = (self.home_pass_accuracy * (self.home_passes - 1) + 100) / self.home_passes
                else:
                    self.away_passes += 1
                    if data.get("success"):
                        self.away_pass_accuracy = (self.away_pass_accuracy * (self.away_passes - 1) + 100) / self.away_passes
            elif event_type == EventType.SHOOT:
                if actor_team == "home":
                    self.home_shots += 1
                else:
                    self.away_shots += 1
                outcome = data.get("outcome", "")
                if outcome in ("goal", "save"):
                    if actor_team == "home":
                        self.home_shots_on_target += 1
                    else:
                        self.away_shots_on_target += 1
                if outcome == "goal":
                    if actor_team == "home":
                        self.home_xg += data.get("xg", 0)
                    else:
                        self.away_xg += data.get("xg", 0)
            elif event_type == EventType.TACKLE:
                if actor_team == "home":
                    self.home_tackles += 1
                    if data.get("foul"):
                        self.home_fouls += 1
                else:
                    self.away_tackles += 1
                    if data.get("foul"):
                        self.away_fouls += 1
            elif event_type == EventType.INTERCEPT:
                if actor_team == "home":
                    self.home_interceptions += 1
                else:
                    self.away_interceptions += 1
            elif event_type == EventType.CROSS:
                if actor_team == "home":
                    self.home_crosses += 1
                else:
                    self.away_crosses += 1
            elif event_type == EventType.DRIBBLE:
                if actor_team == "home":
                    self.home_dribbles += 1
                else:
                    self.away_dribbles += 1

    def to_dict(self) -> dict:
        """Serialize for API response."""
        return {
            "match_index": self.match_index,
            "home_score": self.home_score,
            "away_score": self.away_score,
            "home_xg": round(self.home_xg, 4),
            "away_xg": round(self.away_xg, 4),
            "home_possession": self.home_possession,
            "away_possession": self.away_possession,
            "home_shots": self.home_shots,
            "away_shots": self.away_shots,
            "home_shots_on_target": self.home_shots_on_target,
            "away_shots_on_target": self.away_shots_on_target,
            "home_passes": self.home_passes,
            "away_passes": self.away_passes,
            "home_pass_accuracy": self.home_pass_accuracy,
            "away_pass_accuracy": self.away_pass_accuracy,
            "home_tackles": self.home_tackles,
            "away_tackles": self.away_tackles,
            "home_fouls": self.home_fouls,
            "away_fouls": self.away_fouls,
            "home_interceptions": self.home_interceptions,
            "away_interceptions": self.away_interceptions,
            "replay_tick_count": len(self.replay_ticks),
        }
