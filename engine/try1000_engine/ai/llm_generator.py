"""LLM Code Generator — generates Python decide() functions for football players.

Inspired by AgentPitch. The LLM writes the code once, and the code runs
at full speed during simulation ticks. No LLM calls during a match.

Flow:
    tactic + role → prompt → LLM → Python code → compile → run 1000 matches
"""

from __future__ import annotations

import json
import logging
import os
from typing import Protocol

logger = logging.getLogger(__name__)


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
            max_tokens=16384,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        return response.content[0].text


class DashScopeClient:
    """LLM client for Alibaba Cloud DashScope (Qwen models).

    Uses dashscope.Generation.call() for text generation (faster than MultiModal).
    Default model: qwen-plus. For qwen3.7-plus, set LLM_MODEL=qwen3.7-plus in env
    (will fall back to MultiModalConversation since qwen3.7-plus is multimodal-only).
    """

    def __init__(self, api_key: str | None = None, model: str = "qwen-plus"):
        self.api_key = api_key or os.environ.get("DASHSCOPE_API_KEY", "")
        self.model = model
        self.base_url = os.environ.get(
            "DASHSCOPE_BASE_URL",
            "https://dashscope-intl.aliyuncs.com/api/v1",
        )

    def generate(self, system_prompt: str, user_message: str) -> str:
        import dashscope
        dashscope.base_http_api_url = self.base_url

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_message})

        # qwen3.7-plus requires MultiModalConversation; others use Generation
        if "3.7" in self.model or "multimodal" in self.model.lower():
            # Convert to multimodal format
            mm_messages = []
            if system_prompt:
                mm_messages.append({"role": "system", "content": [{"text": system_prompt}]})
            mm_messages.append({"role": "user", "content": [{"text": user_message}]})
            response = dashscope.MultiModalConversation.call(
                api_key=self.api_key, model=self.model, messages=mm_messages,
            )
            if response.status_code != 200:
                raise RuntimeError(f"DashScope error {response.status_code}: {response.code} — {response.message}")
            return response.output.choices[0].message.content[0]["text"]

        response = dashscope.Generation.call(
            api_key=self.api_key,
            model=self.model,
            messages=messages,
            result_format="message",
        )
        if response.status_code != 200:
            raise RuntimeError(
                f"DashScope error {response.status_code}: {response.code} — {response.message}"
            )
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
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        )
        return response.choices[0].message.content


# ═══════════════════════════════════════════════════════════════
# Prompt Template
# ═══════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """\
You are designing a football strategy. Write ONE Python function `decide(game_state, player_state, history)` that controls ALL 11 players by branching on `player_state["role"]`. Called once per tick per player.

=== ACTION SPACE ===
Return ONE dict per call:
  {"action":"Hold"}
  {"action":"Move","dx":float,"dy":float,"speed":float}          # dx,dy ∈ [-1,1], speed ∈ [0,1]
  {"action":"Pass","target_x":float,"target_y":float,"power":float}  # target in [0,1] normalized, power ∈ [1,20]
  {"action":"Shoot","angle":float,"power":float}                 # angle ∈ [-90,90], 0=straight at goal
  {"action":"Dribble","dx":float,"dy":float,"speed":float}
  {"action":"Tackle","target_player_id":str}
Validation: non-carrier Pass/Shoot → Hold(); out-of-range Tackle → Hold(); speed clamped to [0,1].

=== GAME STATE (dict) ===
game_state = {
    "tick": int, "half": int,  # 1 or 2
    "score": {"home": int, "away": int},
    "ball": {
        "position": [float, float],     # normalized 0-1 (0,0=top-left, 1,1=bottom-right)
        "possession_team": str | None,  # "home", "away", or None
        "carrier_id": str | None,
    },
    "my_team": str, "my_player_id": str,
    "teammates": [{"id":str,"role":str,"position":[float,float],"has_ball":bool}, ...],
    "opponents": [{"id":str,"role":str,"position":[float,float],"has_ball":bool}, ...],
    "field": {
        "width": 68.0, "height": 105.0,
        "my_goal_x": float, "opponent_goal_x": float,  # x-coord of each goal line (0 or 1)
        "goal_top": 0.44, "goal_bottom": 0.56,           # y-edges of goal mouth
    },
}
Convention: for "home" team, my_goal_x=0.0, opponent_goal_x=1.0. For "away", reversed.
Goal mouth spans y ∈ [goal_top, goal_bottom]. my_goal_x is your team's defending goal.

=== PLAYER STATE (dict) ===
player_state = {
    "role": str,  # GK, CB, LB, RB, CDM, CM, CAM, LM, RM, LW, RW, ST, CF
    "position": [float, float],  # normalized 0-1
    "pace": int, "shooting": int, "passing": int, "dribbling": int,
    "defending": int, "physicality": int, "stamina": int,
    "awareness": int, "composure": int,  # all 0-100
    "has_ball": bool, "health": float,  # 0.0-1.0
    "on_cooldown": bool,  # True → Pass/Shoot/Tackle blocked, only Move/Hold allowed
}

=== HISTORY (list) ===
history = [{"tick":int,"action":str,"success":bool}, ...]  # last 20 actions, oldest first

=== SHOOTING DISCIPLINE ===
Prevent the "dead zone": when you are the ball carrier in the attacking third and have a sight of goal, SHOOT instead of always passing. Make the shoot gate OVERLAP the pass-first range — do not let the shoot condition sit strictly closer to goal than where you start passing. Central carriers near the penalty area edge should shoot.

=== OFFSIDE (Law 11) ===
A teammate in the opponents' half AND nearer the opponent's goal line than both the ball and the second-last opponent is OFFSIDE. Pass to an offside player → play stopped, free kick to opponents. No offside from goal kicks or throw-ins. Attackers: time runs to stay level. Passers: check receiver BEFORE passing forward.

=== FOULS AND CARDS (Law 12) ===
Every Tackle risks a foul — chance scales with physicality. Foul in own penalty area → PENALTY KICK. A red card (or two yellows) → player sent off for rest of match. Never tackle inside your own penalty area unless preventing a certain goal.

=== SNAP MECHANICS ===
When idle (Hold, or Move at speed<0.5), a soft formation pull drifts the player toward their anchor position. Active intent (Move at speed>=0.5, or any carrier action) bypasses this. The discipline is at most 20% of motion.

=== RUNTIME IDENTITY ===
The same decide() runs for every player. Branch on `player_state["role"]` to differentiate. NEVER hardcode specific player_ids — roles vary by config.

=== SANDBOX CONSTRAINTS ===
- DO NOT use `import` statements — not even `import math`. The sandbox blocks them.
- sqrt(x) → x**0.5; pi → 3.141592653589793
- Do NOT use print(), open(), exec(), eval(), or any I/O.
- You MAY define nested functions inside decide().
- Use module-level variables for cross-tick persistent state if needed.
- Available builtins: abs, min, max, sum, len, range, sorted, enumerate, isinstance, int, float, str, list, dict, tuple, bool.

=== FIELD GEOMETRY ===
Field and goal geometry vary — ALWAYS read from inputs:
  fw = game_state["field"]["width"]    # 68.0
  fh = game_state["field"]["height"]   # 105.0
  my_goal = game_state["field"]["my_goal_x"]
  opp_goal = game_state["field"]["opponent_goal_x"]
  goal_center_y = (game_state["field"]["goal_top"] + game_state["field"]["goal_bottom"]) / 2
Pick your defending goal by team. Attack the OPPOSITE goal. These swap at half-time — read them every tick.

=== BALL CARRIER LOGIC ===
- If has_ball and in attacking third → Shoot or Pass (never hold too long).
- If has_ball and in own half → Pass forward to an open teammate, or Dribble into space.
- If has_ball and no good option → Move toward opponent's goal at moderate speed.

=== OFF-BALL LOGIC ===
- If team has ball (attacking): Move into space, support the carrier, stay between defenders.
- If opponents have ball (defending): Track back, mark opponents, stay goal-side.
- GK: Stay in/near penalty area. When ball is in own box, rush to claim.

=== USER INTENT ===
The user message below contains the team's tactical document. Bias your strategy TOWARD it while respecting all rules above. The tactical document may contain specific per-role instructions — encode those as if/elif branches.

=== OUTPUT FORMAT ===
Return ONLY the decide() function inside a Python fenced code block. No explanation, no other text.
```python
def decide(game_state, player_state, history):
    ...
```"""


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

    def generate_team(self, tactic: dict, team_name: str = "Team") -> str:
        """Generate ONE decide() function for the entire team.

        The LLM writes a single function that branches on player.role
        to handle all 11 positions — same as AgentPitch's CGP.

        Returns the full Python code string.
        """
        logger.info(f"Generating strategy for {team_name} (1 LLM call)...")
        user_message = self._build_team_message(tactic, team_name)
        return self._extract_code(self.client.generate(SYSTEM_PROMPT, user_message))

    def _build_team_message(self, tactic: dict, team_name: str) -> str:
        """Build the user message — tactical doc is the user intent (AgentPitch SECTION 13 pattern)."""
        formation = tactic.get("formation", "4-3-3")
        doc = tactic.get("tactical_document", "").strip()
        if not doc:
            doc = "(no specific user intent — apply general best practices for a balanced, competitive strategy)"

        return f"""Team: {team_name}
Formation: {formation}

=== TACTICAL DOCUMENT (YOUR USER INTENT) ===
{doc}

=== TASK ===
Write the complete decide() function that implements this tactical style.
Branch on player_state["role"] to give each position (GK, CB, LB, RB, CDM, CM, CAM, LM, RM, LW, RW, ST, CF) appropriate behavior.
Include ball-carrier logic, off-ball positioning, pressing triggers, and defensive shape.
Return ONLY the Python code in a fenced block."""

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
