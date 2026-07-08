"""Test LLM-generated policy: compile and run generated code."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from try1000_engine.ai.generated_policy import GeneratedPolicy, SandboxError
from try1000_engine.ai.policy import Observation


# ═══════════════════════════════════════════════════════════
# A "mock" LLM response — the kind of code a real LLM would generate
# ═══════════════════════════════════════════════════════════

STRIKER_CODE = '''
def decide(game_state, player_state, history):
    """Striker in a high-press 4-3-3. Attacks space, shoots in the box."""

    ball = game_state["ball"]
    my_pos = player_state["position"]
    ball_pos = ball["position"]

    # --- If I have the ball ---
    if player_state["has_ball"]:
        # Calculate distance to opponent goal
        goal_x = game_state["field"]["opponent_goal_x"]
        dist_to_goal = (
            (my_pos[0] - goal_x) ** 2 + (my_pos[1] - 0.5) ** 2
        ) ** 0.5

        # In shooting range (< 0.22 normalized ≈ 18m)
        if dist_to_goal < 0.20:
            return {
                "action": "Shoot",
                "angle": (0.5 - my_pos[1]) * 30.0,
                "power": 16.0 + player_state["shooting"] * 0.04,
            }

        # Close to goal, but tight angle → dribble toward center
        if dist_to_goal < 0.30 and abs(my_pos[1] - 0.5) > 0.2:
            return {
                "action": "Dribble",
                "dx": 0.7,
                "dy": 0.5 - my_pos[1],
                "speed": 0.9,
            }

        # Has teammates ahead → pass
        for tm in game_state["teammates"]:
            tm_dist = (
                (my_pos[0] - tm["position"][0]) ** 2 +
                (my_pos[1] - tm["position"][1]) ** 2
            ) ** 0.5
            if tm_dist < 0.35:
                return {
                    "action": "Pass",
                    "target_x": tm["position"][0],
                    "target_y": tm["position"][1],
                    "power": 8.0 + tm_dist * 30.0,
                }

        # No good option → dribble forward
        return {"action": "Dribble", "dx": 0.8, "dy": 0.0, "speed": 0.8}

    # --- I don't have the ball ---
    # Move toward the ball if it's loose
    if ball["possession_team"] is None:
        dx = ball_pos[0] - my_pos[0]
        dy = ball_pos[1] - my_pos[1]
        mag = (dx**2 + dy**2) ** 0.5
        if mag > 0.01:
            return {"action": "Move", "dx": dx/mag, "dy": dy/mag, "speed": 0.9}
        return {"action": "Hold"}

    # My team has the ball → move into space ahead
    if ball["possession_team"] == game_state["my_team"]:
        goal_x = game_state["field"]["opponent_goal_x"]
        return {
            "action": "Move",
            "dx": goal_x - my_pos[0],
            "dy": 0.5 - my_pos[1],
            "speed": 0.7,
        }

    # Opponent has the ball → press if close enough
    nearest_opp = None
    nearest_dist = 999.0
    for opp in game_state["opponents"]:
        d = ((my_pos[0] - opp["position"][0])**2 +
             (my_pos[1] - opp["position"][1])**2) ** 0.5
        if d < nearest_dist:
            nearest_dist = d
            nearest_opp = opp

    if nearest_opp and nearest_dist < 0.15:
        return {"action": "Tackle", "target_player_id": nearest_opp["id"]}

    # Track back toward own goal
    return {
        "action": "Move",
        "dx": game_state["field"]["my_goal_x"] - my_pos[0],
        "dy": 0.5 - my_pos[1],
        "speed": 0.5,
    }
'''


def make_st_obs(has_ball=True, near_goal=False) -> Observation:
    """Build an Observation for a striker."""
    obs = Observation()
    obs.role_obs = 11  # ST
    obs.has_ball = 1 if has_ball else 0
    obs.ball_x = 0.7 if near_goal else 0.5
    obs.ball_y = 0.5
    obs.ball_distance = 0.0 if has_ball else 0.3
    obs.ball_possession_team = 1 if has_ball else 0
    obs.distance_to_opponent_goal = 0.19 if near_goal else 0.45
    obs.angle_to_opponent_goal = -0.1
    obs.distance_to_own_goal = 0.8
    obs.nearest_teammate_distance = 0.18
    obs.nearest_teammate_angle = 0.2
    obs.nearest_opponent_distance = 0.15
    obs.nearest_opponent_angle = -0.3
    obs.pressure_level = 0.3
    obs.space_ahead = 0.6
    obs.distance_to_touchline = 0.3
    obs.pace = 0.80
    obs.shooting = 0.85
    obs.passing = 0.65
    obs.dribbling = 0.75
    obs.defending = 0.25
    obs.physicality = 0.70
    obs.stamina_obs = 0.90
    obs.awareness = 0.75
    obs.composure = 0.80
    obs.health = 1.0
    obs.score_diff = 0
    obs.match_time_ratio = 0.3
    obs.half = 1
    obs.possession_phase = 1
    obs.pressing_level = 0.7
    obs.tempo = 0.7
    obs.history_action_types = [0, 0, 0, 0, 0]
    obs.history_success_flags = [0, 0, 0, 0, 0]
    return obs


def test_compile_and_run():
    """Compile LLM-generated code and verify it produces valid actions."""
    policy = GeneratedPolicy(code=STRIKER_CODE, role="ST")

    print(f"Policy: {policy.name()}")

    # Striker with ball near goal → should shoot
    obs = make_st_obs(has_ball=True, near_goal=True)
    action = policy.decide(obs)
    from try1000_engine.actions.base import ActionType
    action_name = ActionType(action.action_type).label
    print(f"  ST w/ ball near goal → {action_name} (power={action.power:.0f})")

    # Striker with ball far from goal → should pass or dribble
    obs2 = make_st_obs(has_ball=True, near_goal=False)
    action2 = policy.decide(obs2)
    print(f"  ST w/ ball far → {ActionType(action2.action_type).label}")

    # Striker without ball, ball loose → should move toward ball
    obs3 = make_st_obs(has_ball=False, near_goal=False)
    obs3.ball_possession_team = 0  # contested
    action3 = policy.decide(obs3)
    print(f"  ST off-ball loose → {ActionType(action3.action_type).label}")

    # All outputs should be valid ActionOutput
    assert action.power > 0
    assert action2.action_type >= 0
    assert action3.action_type >= 0

    print("\n✅ LLM-generated policy compiles and runs correctly!")


def test_invalid_code():
    """Test that broken code raises SandboxError."""
    try:
        GeneratedPolicy(code="def wrong_name(): pass", role="ST")
        assert False, "Should have raised SandboxError"
    except SandboxError:
        print("✅ Invalid code correctly rejected (missing 'decide' function)")

    try:
        GeneratedPolicy(code="def decide(: # syntax error", role="ST")
        assert False, "Should have raised SandboxError"
    except SandboxError:
        print("✅ Syntax error correctly rejected")


def test_fallback_on_error():
    """Test that runtime errors in generated code fall back to Hold."""
    buggy_code = '''
def decide(game_state, player_state, history):
    # Bug: divide by zero
    x = 1 / 0
    return {"action": "Hold"}
'''
    policy = GeneratedPolicy(code=buggy_code, role="ST")
    obs = make_st_obs()
    action = policy.decide(obs)
    from try1000_engine.actions.base import ActionType
    assert ActionType(action.action_type) == ActionType.HOLD
    print("✅ Runtime error gracefully falls back to Hold()")


if __name__ == "__main__":
    test_compile_and_run()
    test_invalid_code()
    test_fallback_on_error()
