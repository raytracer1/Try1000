"""Smoke test: run a full match and verify basic behavior."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from try1000_engine.physics.player import Player
from try1000_engine.ai.rule_based import RuleBasedPolicy
from try1000_engine.match.match_engine import MatchEngine


def make_team(team: str, formation: str = "4-3-3") -> list[Player]:
    """Create 11 players for a team."""
    roles = ["GK", "CB", "CB", "LB", "RB", "CDM", "CM", "CM", "LW", "RW", "ST"]
    players = []
    for i, role in enumerate(roles):
        # Vary attributes by role
        if role == "GK":
            attrs = {"pace": 50, "shooting": 20, "passing": 60, "dribbling": 30,
                     "defending": 80, "physicality": 70, "stamina_val": 95,
                     "awareness": 80, "composure": 75}
        elif role in ("CB", "LB", "RB"):
            attrs = {"pace": 70, "shooting": 30, "passing": 65, "dribbling": 40,
                     "defending": 80, "physicality": 75, "stamina_val": 85,
                     "awareness": 75, "composure": 70}
        elif role in ("CDM", "CM"):
            attrs = {"pace": 70, "shooting": 60, "passing": 80, "dribbling": 65,
                     "defending": 65, "physicality": 70, "stamina_val": 80,
                     "awareness": 75, "composure": 75}
        elif role in ("LW", "RW"):
            attrs = {"pace": 90, "shooting": 70, "passing": 70, "dribbling": 85,
                     "defending": 35, "physicality": 55, "stamina_val": 75,
                     "awareness": 70, "composure": 65}
        else:  # ST
            attrs = {"pace": 80, "shooting": 85, "passing": 65, "dribbling": 75,
                     "defending": 25, "physicality": 70, "stamina_val": 80,
                     "awareness": 75, "composure": 80}

        p = Player(
            player_id=f"{team}_{i+1}",
            team=team,
            role=role,
            **attrs,
        )
        players.append(p)
    return players


def test_smoke():
    """Run one match with two 4-3-3 teams. Verify it completes."""
    home = make_team("home")
    away = make_team("away")

    # Home plays high-press, away plays low block
    home_policy = RuleBasedPolicy(tactic={
        "pressing_level": 8, "defensive_line": 7, "attacking_width": 7,
        "passing_style": "mixed", "build_up_style": "fast", "tempo": 7,
    })
    away_policy = RuleBasedPolicy(tactic={
        "pressing_level": 3, "defensive_line": 3, "attacking_width": 5,
        "passing_style": "direct", "build_up_style": "fast", "tempo": 4,
    })

    engine = MatchEngine(
        home_policy=home_policy,
        away_policy=away_policy,
        seed=42,
        record_replay=True,
    )

    result = engine.run(home, away, match_index=0)

    print(f"Match result: Home {result.home_score} - {result.away_score} Away")
    print(f"xG: Home {result.home_xg:.3f} - {result.away_xg:.3f} Away")
    print(f"Possession: Home {result.home_possession:.1f}% - {result.away_possession:.1f}% Away")
    print(f"Shots: Home {result.home_shots} - {result.away_shots} Away")
    print(f"Passes: Home {result.home_passes} - {result.away_passes} Away")
    print(f"Tackles: Home {result.home_tackles} - {result.away_tackles} Away")
    print(f"Fouls: Home {result.home_fouls} - {result.away_fouls} Away")
    print(f"Replay ticks: {len(result.replay_ticks)}")
    print(f"Full time events: {len(result.replay_ticks)} ticks recorded")

    # Basic assertions
    assert result.home_score >= 0
    assert result.away_score >= 0
    assert len(result.replay_ticks) > 0, "Should have recorded replay ticks"
    total_passes = result.home_passes + result.away_passes
    assert total_passes > 0, f"Should have passes, got {total_passes}"

    print("\n✅ Smoke test passed!")
    print(f"   {total_passes} passes, {result.home_shots + result.away_shots} shots, "
          f"{result.home_score + result.away_score} goals")


def test_determinism():
    """Verify same seed produces identical results."""
    home = make_team("home")
    away = make_team("away")

    results = []
    for i in range(3):
        engine = MatchEngine(
            home_policy=RuleBasedPolicy(),
            away_policy=RuleBasedPolicy(),
            seed=42,  # Same seed
            record_replay=False,
        )
        # Need fresh players each time (state gets mutated)
        h = make_team("home")
        a = make_team("away")
        r = engine.run(h, a, match_index=i)
        results.append((r.home_score, r.away_score))

    # All 3 runs should produce identical scores
    assert results[0] == results[1] == results[2], \
        f"Determinism failed! Results: {results}"

    print("✅ Determinism test passed! All 3 runs produced identical results.")


if __name__ == "__main__":
    test_smoke()
    test_determinism()
