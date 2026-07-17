"""LLM Code Generator — generates Python decide() functions for football players.

Inspired by AgentPitch. The LLM writes the code once, and the code runs
at full speed during simulation ticks. No LLM calls during a match.

Flow:
    tactic + role → prompt → LLM → Python code → compile → run 1000 matches
"""

from __future__ import annotations

import json
import os
from typing import Protocol


# ═══════════════════════════════════════════════════════════════
# LLM Client Protocol
# ═══════════════════════════════════════════════════════════════

class LLMClient(Protocol):
    """Minimal protocol for LLM API calls."""

    def generate(self, system_prompt: str, user_message: str) -> str:
        """Send a prompt and return the generated text."""
        ...


class AnthropicClient:
    """LLM client for Anthropic Claude API."""

    def __init__(self, api_key: str | None = None, model: str = "claude-sonnet-5"):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.model = model

    def generate(self, system_prompt: str, user_message: str) -> str:
        import anthropic
        client = anthropic.Anthropic(api_key=self.api_key)
        response = client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        return response.content[0].text


class DashScopeClient:
    """LLM client for Alibaba Cloud DashScope (Qwen models)."""

    def __init__(self, api_key: str | None = None, model: str = "qwen3.7-plus"):
        self.api_key = api_key or os.environ.get("DASHSCOPE_API_KEY", "")
        self.model = model

    def generate(self, system_prompt: str, user_message: str) -> str:
        import dashscope
        dashscope.base_http_api_url = "https://dashscope-intl.aliyuncs.com/api/v1"
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_message})
        response = dashscope.Generation.call(
            api_key=self.api_key,
            model=self.model,
            messages=messages,
            result_format="message",
        )
        if response.status_code != 200:
            raise RuntimeError(f"DashScope error {response.status_code}: {response.message}")
        return response.output.choices[0].message.content


class OpenAICompatibleClient:
    """LLM client for OpenAI-compatible APIs (GPT, DeepSeek, local models)."""

    def __init__(self, api_key: str | None = None, base_url: str | None = None,
                 model: str = "gpt-4o"):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.base_url = base_url
        self.model = model

    def generate(self, system_prompt: str, user_message: str) -> str:
        from openai import OpenAI
        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        response = client.chat.completions.create(
            model=self.model,
            max_tokens=4096,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        )
        return response.choices[0].message.content


# ═══════════════════════════════════════════════════════════════
# Prompt Template
# ═══════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """You are an expert football tactics programmer. You write Python code
that controls a single football player's decision-making in a simulation.

## Your Task

Write a function `decide(game_state, player_state, history)` that returns what
the player should do this tick.

## Available Actions

Return ONE of these dicts:

{"action": "Hold"}
{"action": "Move", "dx": float, "dy": float, "speed": float}
{"action": "Pass", "target_x": float, "target_y": float, "power": float}
{"action": "Shoot", "angle": float, "power": float}
{"action": "Cross", "target_x": float, "target_y": float, "power": float}
{"action": "Dribble", "dx": float, "dy": float, "speed": float}
{"action": "Tackle", "target_player_id": str}

Parameter ranges:
- dx, dy: -1.0 to 1.0 (direction vector)
- speed: 0.0 to 1.0 (fraction of max speed)
- target_x, target_y: 0.0 to 1.0 (normalized pitch coordinates, 0,0 = top-left)
- power: 1.0 to 20.0
- angle: -90 to 90 degrees (0 = straight at goal)

## Game State (dict)

```python
game_state = {
    "tick": int,               # current tick (0-5400)
    "match_time_seconds": float,
    "half": int,               # 1 or 2
    "score": {"home": int, "away": int},
    "ball": {
        "position": [float, float],  # normalized 0-1
        "possession_team": str | None,  # "home", "away", or None
        "carrier_id": str | None,
    },
    "my_team": str,            # "home" or "away"
    "my_player_id": str,
    "teammates": [             # all teammates EXCEPT self
        {"id": str, "role": str, "position": [float, float], "has_ball": bool},
        ...
    ],
    "opponents": [
        {"id": str, "role": str, "position": [float, float], "has_ball": bool},
        ...
    ],
    "field": {
        "width": 68.0, "height": 105.0,
        "my_goal_x": float, "opponent_goal_x": float,
        "goal_top": float, "goal_bottom": float,
    },
}
```

## Player State (dict)

```python
player_state = {
    "role": str,               # "GK", "CB", "ST", etc.
    "position": [float, float],  # normalized 0-1
    "pace": 0-100,
    "shooting": 0-100,
    "passing": 0-100,
    "dribbling": 0-100,
    "defending": 0-100,
    "physicality": 0-100,
    "stamina": 0-100,
    "awareness": 0-100,
    "composure": 0-100,
    "has_ball": bool,
    "health": float,           # 0.0-1.0
    "on_cooldown": bool,       # True if Pass/Shoot/Tackle are disabled
}
```

## History (list)

```python
history = [
    {"tick": int, "action": str, "success": bool},
    ...  # last 20 actions, oldest first
]
```

## Code Rules

1. Function MUST be pure: same inputs → same outputs. No random().
2. No file I/O, no network, no imports except `math`.
3. Must return a dict (one of the 7 action types above).
4. Must handle ALL game states gracefully (no crashes).
5. Comment your logic briefly.

## Tactical Context Provided by User

The user will provide the team's tactical parameters in their message.
Write code that implements the described playing style."""


# ═══════════════════════════════════════════════════════════════
# Code Generator
# ═══════════════════════════════════════════════════════════════

class CodeGenerator:
    """Uses an LLM to generate Python decide() functions.

    Usage:
        gen = CodeGenerator(client)
        code = gen.generate(role="ST", tactic={...}, team_name="Home FC")
        # code is a Python function string ready to compile
    """

    def __init__(self, client: LLMClient):
        self.client = client

    def generate(self, role: str, tactic: dict, team_name: str = "Team") -> str:
        """Generate a decide() function for a specific role and tactic."""
        user_message = self._build_user_message(role, tactic, team_name)
        response = self.client.generate(SYSTEM_PROMPT, user_message)
        return self._extract_code(response)

    def generate_team(self, tactic: dict, team_name: str = "Team") -> dict[str, str]:
        """Generate decide() functions for all 11 roles in a team.

        Returns {role: code_string} for all 11 positions.
        """
        results = {}
        roles = ["GK", "CB", "LB", "RB", "CDM", "CM", "CAM", "LW", "RW", "ST"]
        # The two CBs share code, LBs share with RBs, etc.
        unique_roles = ["GK", "CB", "LB", "CDM", "CM", "CAM", "LW", "ST"]
        for role in unique_roles:
            results[role] = self.generate(role, tactic, team_name)
        return results

    def evolve(self, current_code: str, role: str, tactic: dict,
               match_summary: dict) -> str:
        """Rewrite a decide() function based on match results.

        The LLM sees what worked and what didn't, and improves the code.
        """
        user_message = f"""## Current decide() function for {role}

```python
{current_code}
```

## Match Performance Summary

{json.dumps(match_summary, indent=2)}

## Task

Analyze the match data above. Rewrite the decide() function to fix
identified problems while maintaining the team's tactical style.

Tactical parameters: {json.dumps(tactic)}

Return ONLY the improved Python code, with brief comments explaining changes."""

        response = self.client.generate(SYSTEM_PROMPT, user_message)
        return self._extract_code(response)

    def _build_user_message(self, role: str, tactic: dict, team_name: str) -> str:
        """Build the user prompt for initial code generation."""
        return f"""## Team: {team_name}
## Role: {role}
## Tactical Parameters

```json
{json.dumps(tactic, indent=2)}
```

## Task

Write a `decide()` function for a {role} playing in this tactical system.

The function should implement:
- Role-appropriate behavior ({role} fundamentals)
- The team's tactical style (pressing, build-up, width, etc.)
- Smart off-ball movement
- Appropriate pass/shoot/dribble decision-making

Return ONLY the Python code (no explanation outside the code comments)."""

    def _extract_code(self, llm_response: str) -> str:
        """Extract Python code from LLM response (may contain markdown fences)."""
        code = llm_response.strip()

        # Strip markdown code fences if present
        if "```python" in code:
            code = code.split("```python", 1)[1]
        elif "```" in code:
            code = code.split("```", 1)[1]
        if code.endswith("```"):
            code = code[:-3]

        code = code.strip()

        # Ensure it has a function definition
        if "def decide" not in code:
            raise ValueError(
                "LLM did not generate a valid decide() function. "
                f"Response was: {llm_response[:200]}..."
            )

        return code
