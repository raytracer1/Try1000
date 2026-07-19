"""Test PolicyFactory: auto-select Level 2 vs Level 1."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from try1000_engine.ai.policy_factory import PolicyFactory
from try1000_engine.ai.rule_based import RuleBasedPolicy
from try1000_engine.ai.generated_policy import GeneratedPolicy
from try1000_engine.physics.player import Player
from try1000_engine.match.match_engine import MatchEngine
from try1000_engine.actions.base import ActionType


def make_team(team_name: str) -> list[Player]:
    roles = ["GK", "CB", "CB", "LB", "RB", "CDM", "CM", "CM", "LW", "RW", "ST"]
    players = []
    for i, role in enumerate(roles):
        players.append(Player(
            f"{team_name}_{i+1}", team_name, role,
            pace=70, shooting=70, passing=70, dribbling=70,
            defending=70, physicality=70, stamina_val=100,
            awareness=70, composure=70,
        ))
    return players


def test_level1_fallback():
    """Without LLM client → uses AgentPitchBaselinePolicy (Level 1)."""
    from try1000_engine.ai.baseline_agentpitch import AgentPitchBaselinePolicy
    factory = PolicyFactory()  # No LLM client
    assert not factory.is_level2

    policies = factory.create_team(tactic={"pressing_level": 7})
    assert len(policies) >= 11  # All positions
    for role, policy in policies.items():
        assert isinstance(policy, AgentPitchBaselinePolicy), \
            f"Expected AgentPitchBaselinePolicy for {role}, got {type(policy)}"

    # Run a match with per-role policies
    home = make_team("home")
    away = make_team("away")
    engine = MatchEngine(
        home_policies=policies,
        away_policies=policies,
        seed=42, record_replay=False, fast_mode=True,
    )
    result = engine.run(home, away, 0)
    total_passes = result.home_passes + result.away_passes
    assert total_passes > 0, f"Expected passes, got {total_passes}"
    print(f"✅ Level 1 fallback: {total_passes} passes, "
          f"score {result.home_score}-{result.away_score}")


class MockLLMClient:
    """Pretends to be an LLM API. Returns hand-written code."""

    def generate(self, system_prompt: str, user_message: str) -> str:
        # Return different code for different roles
        if "ST" in user_message or "LW" in user_message or "RW" in user_message:
            return ATTACKER_CODE
        elif "CM" in user_message or "CAM" in user_message or "CDM" in user_message:
            return MIDFIELDER_CODE
        else:
            return DEFENDER_CODE


ATTACKER_CODE = '''
def decide(game_state, player_state, history):
    ball = game_state["ball"]
    my_pos = player_state["position"]
    goal_x = game_state["field"]["opponent_goal_x"]
    if player_state["has_ball"]:
        dist = ((my_pos[0]-goal_x)**2 + (my_pos[1]-0.5)**2) ** 0.5
        if dist < 0.20:
            return {"action": "Shoot", "angle": (0.5-my_pos[1])*20.0, "power": 17.0}
        for tm in game_state.get("teammates", []):
            d = ((my_pos[0]-tm["position"][0])**2 + (my_pos[1]-tm["position"][1])**2) ** 0.5
            if 0.02 < d < 0.35:
                return {"action": "Pass", "target_x": tm["position"][0], "target_y": tm["position"][1], "power": 10.0}
        return {"action": "Dribble", "dx": 0.7, "dy": 0.5-my_pos[1], "speed": 0.8}
    if ball["possession_team"] is None:
        dx, dy = ball["position"][0]-my_pos[0], ball["position"][1]-my_pos[1]
        mag = (dx**2+dy**2)**0.5
        if mag > 0.01: return {"action": "Move", "dx": dx/mag, "dy": dy/mag, "speed": 0.9}
        return {"action": "Hold"}
    if ball["possession_team"] == game_state["my_team"]:
        return {"action": "Move", "dx": goal_x-my_pos[0], "dy": 0.5-my_pos[1], "speed": 0.7}
    for opp in game_state.get("opponents", []):
        d = ((my_pos[0]-opp["position"][0])**2 + (my_pos[1]-opp["position"][1])**2) ** 0.5
        if d < 0.15: return {"action": "Tackle", "target_player_id": opp["id"]}
    return {"action": "Move", "dx": 0.2-my_pos[0], "dy": 0.5-my_pos[1], "speed": 0.5}
'''

MIDFIELDER_CODE = '''
def decide(game_state, player_state, history):
    ball = game_state["ball"]
    my_pos = player_state["position"]
    if player_state["has_ball"]:
        for tm in game_state.get("teammates", []):
            d = ((my_pos[0]-tm["position"][0])**2 + (my_pos[1]-tm["position"][1])**2) ** 0.5
            if 0.02 < d < 0.35:
                return {"action": "Pass", "target_x": tm["position"][0], "target_y": tm["position"][1], "power": 9.0}
        return {"action": "Dribble", "dx": 0.5, "dy": 0.0, "speed": 0.7}
    if ball["possession_team"] is None:
        dx, dy = ball["position"][0]-my_pos[0], ball["position"][1]-my_pos[1]
        mag = (dx**2+dy**2)**0.5
        if mag > 0.01: return {"action": "Move", "dx": dx/mag, "dy": dy/mag, "speed": 0.8}
    if ball["possession_team"] == game_state["my_team"]:
        return {"action": "Move", "dx": 0.6-my_pos[0], "dy": 0.5-my_pos[1], "speed": 0.6}
    for opp in game_state.get("opponents", []):
        d = ((my_pos[0]-opp["position"][0])**2 + (my_pos[1]-opp["position"][1])**2) ** 0.5
        if d < 0.12: return {"action": "Tackle", "target_player_id": opp["id"]}
    return {"action": "Move", "dx": 0.2-my_pos[0], "dy": 0.5-my_pos[1], "speed": 0.5}
'''

DEFENDER_CODE = '''
def decide(game_state, player_state, history):
    ball = game_state["ball"]
    my_pos = player_state["position"]
    if player_state["has_ball"]:
        for tm in game_state.get("teammates", []):
            d = ((my_pos[0]-tm["position"][0])**2 + (my_pos[1]-tm["position"][1])**2) ** 0.5
            if 0.02 < d < 0.30:
                return {"action": "Pass", "target_x": tm["position"][0], "target_y": tm["position"][1], "power": 8.0}
        return {"action": "Pass", "target_x": 0.6, "target_y": 0.5, "power": 14.0}
    for opp in game_state.get("opponents", []):
        d = ((my_pos[0]-opp["position"][0])**2 + (my_pos[1]-opp["position"][1])**2) ** 0.5
        if d < 0.12: return {"action": "Tackle", "target_player_id": opp["id"]}
    dx, dy = ball["position"][0]-my_pos[0], ball["position"][1]-my_pos[1]
    mag = (dx**2+dy**2)**0.5
    if mag > 0.01: return {"action": "Move", "dx": dx/mag, "dy": dy/mag, "speed": 0.7}
    return {"action": "Hold"}
'''


def test_level2_with_llm():
    """With LLM client → uses GeneratedPolicy (Level 2)."""
    factory = PolicyFactory(llm_client=MockLLMClient())
    assert factory.is_level2

    tactic = {"pressing_level": 8, "defensive_line": 7, "tempo": 7}
    policies = factory.create_team(tactic=tactic, team_name="Test FC")
    assert len(policies) >= 11

    # Each role should have a GeneratedPolicy
    for role in ["GK", "CB", "LB", "RB", "CDM", "CM", "CAM", "LW", "RW", "ST"]:
        policy = policies.get(role)
        assert policy is not None, f"Missing policy for {role}"
        # Should be GeneratedPolicy since we have a mock LLM
        assert isinstance(policy, GeneratedPolicy), \
            f"Expected GeneratedPolicy for {role}, got {type(policy)}"

    # Run match with per-role GeneratedPolicies
    home = make_team("home")
    away = make_team("away")

    # Away uses same policies (for simplicity)
    engine = MatchEngine(
        home_policies=policies,
        away_policies=policies,
        seed=42, record_replay=False, fast_mode=True,
    )
    result = engine.run(home, away, 0)
    total_passes = result.home_passes + result.away_passes
    total_shots = result.home_shots + result.away_shots
    print(f"✅ Level 2 LLM: {total_passes} passes, {total_shots} shots, "
          f"score {result.home_score}-{result.away_score}")
    assert total_passes > 0


def test_cache():
    """Generated policies should be cached — same (role, tactic) → same instance."""
    factory = PolicyFactory(llm_client=MockLLMClient())
    tactics = {"pressing_level": 5}
    p1 = factory.create_policy("ST", tactics)
    p2 = factory.create_policy("ST", tactics)
    assert p1 is p2, "Same (role, tactic) should return cached policy"
    print("✅ Policy cache works: same instance returned")


def test_legacy_api():
    """Old MatchEngine(home_policy=p) still works for backward compat."""
    from try1000_engine.ai.rule_based import RuleBasedPolicy
    home = make_team("home")
    away = make_team("away")
    engine = MatchEngine(
        home_policy=RuleBasedPolicy(),
        away_policy=RuleBasedPolicy(),
        seed=42, record_replay=False, fast_mode=True,
    )
    result = engine.run(home, away, 0)
    assert result.home_passes + result.away_passes > 0
    print(f"✅ Legacy API still works: {result.home_passes + result.away_passes} passes")


if __name__ == "__main__":
    test_level1_fallback()
    test_level2_with_llm()
    test_cache()
    test_legacy_api()
