"""Benchmark: run multiple matches and measure performance."""

import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from try1000_engine.physics.player import Player
from try1000_engine.ai.rule_based import RuleBasedPolicy
from try1000_engine.match.match_engine import MatchEngine


def make_team(team: str) -> list[Player]:
    roles = ["GK", "CB", "CB", "LB", "RB", "CDM", "CM", "CM", "LW", "RW", "ST"]
    players = []
    for i, role in enumerate(roles):
        attrs = {"pace": 70, "shooting": 70, "passing": 70, "dribbling": 70,
                 "defending": 70, "physicality": 70, "stamina_val": 100,
                 "awareness": 70, "composure": 70}
        players.append(Player(f"{team}_{i+1}", team, role, **attrs))
    return players


def benchmark(n_matches: int = 10):
    """Run N matches and report timing."""
    home = make_team("home")
    away = make_team("away")

    hp = RuleBasedPolicy(tactic={"pressing_level": 7, "defensive_line": 6,
                                  "attacking_width": 7, "passing_style": "mixed",
                                  "build_up_style": "fast", "tempo": 7})
    ap = RuleBasedPolicy(tactic={"pressing_level": 3, "defensive_line": 3,
                                  "attacking_width": 5, "passing_style": "direct",
                                  "build_up_style": "fast", "tempo": 4})

    t0 = time.perf_counter()
    results = []
    for i in range(n_matches):
        engine = MatchEngine(hp, ap, seed=42 + i, record_replay=False, fast_mode=True)
        h = make_team("home")
        a = make_team("away")
        r = engine.run(h, a, match_index=i)
        results.append(r)

    elapsed = time.perf_counter() - t0
    total_passes = sum(r.home_passes + r.away_passes for r in results)
    total_shots = sum(r.home_shots + r.away_shots for r in results)
    total_goals = sum(r.home_score + r.away_score for r in results)

    print(f"Ran {n_matches} matches in {elapsed:.1f}s")
    print(f"  Avg per match: {elapsed/n_matches:.2f}s")
    print(f"  Total passes: {total_passes}, shots: {total_shots}, goals: {total_goals}")
    print(f"  Projected: 100 matches in ~{elapsed/n_matches*100:.0f}s, "
          f"1000 matches in ~{elapsed/n_matches*1000:.0f}s")

    assert elapsed > 0
    print("\n✅ Benchmark passed!")


if __name__ == "__main__":
    benchmark(10)
