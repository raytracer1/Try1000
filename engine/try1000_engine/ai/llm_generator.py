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

=== FEW-SHOT SKELETON ===
# Example structure — adapt for your team's style:
def decide(game_state, player_state, history):
    role = player_state["role"]
    if player_state["has_ball"]:
        # CARRIER: shoot if close, pass if teammate open, else dribble forward
        if role == "FWD" or role == "ST":
            return Shoot(angle=0.0, power=15)
        if role == "MID":
            open_teammate = find_open_forward_teammate(game_state)
            if open_teammate:
                return Pass(target_x=open_teammate["position"][0], target_y=open_teammate["position"][1], power=12)
            return Dribble(dx=0.5 if attacking_right else -0.5, dy=0.0, speed=0.7)
        if role == "DEF":
            return Pass(target_x=0.6, target_y=0.5, power=15)  # clear forward
        if role == "GK":
            return Pass(target_x=0.3, target_y=0.5, power=10)  # distribute short
        return Hold()
    else:
        # OFF-BALL: move toward ball when attacking, track back when defending
        if game_state["team_phase"] == "attacking":
            return Move(dx=ball_x - my_x, dy=ball_y - my_y, speed=0.6)
        else:
            return Move(dx=my_goal_x - my_x, dy=0.0, speed=0.5)

=== GAME STATE (dict) ===
game_state = {
    "tick": int,              # current tick (0-5400)
    "match_phase": str,       # "kick_off" | "in_play" | "goal_scored" | "half_time" | "full_time"
    "half": int,               # 1 or 2
    "score": {"home": int, "away": int},
    "ball": {
        "position": [float, float],     # normalized 0-1 (0,0=defending-left, 1,1=attacking-right for home)
        "velocity": [float, float],     # normalized units/tick — ball motion this tick, useful for predicting next position
        "possession": str | None,      # "home" | "away" | None (loose ball)
        "carrier_id": str | None,      # player_id of the ball carrier, or None
    },
    "team_phase": str,         # "attacking" | "defending" | "transitioning" — which phase YOUR team is in
    "my_team": str,            # "home" | "away"
    "my_player_id": str,       # YOUR player_id this call, e.g. "home_3"
    "teammates": [             # ALL teammates EXCEPT yourself (10 players in 11v11)
        {"id": str, "role": str, "position": [float, float], "has_ball": bool},
        ...
    ],
    "opponents": [             # ALL opponents (11 players in 11v11)
        {"id": str, "role": str, "position": [float, float], "has_ball": bool},
        ...
    ],
    "field": {
        "width": 68.0, "height": 105.0,
        "my_goal_x": float,           # x-coord of YOUR team's defending goal
        "opponent_goal_x": float,     # x-coord of the goal YOU attack
        "goal_top": 0.44,             # larger-y edge of the goal mouth (numerically GREATER, e.g. 0.56)
        "goal_bottom": 0.56,          # smaller-y edge of the goal mouth (numerically LESS, e.g. 0.44)
    },
}
Convention: goal_top > goal_bottom. Goal-mouth height = goal_top - goal_bottom (POSITIVE).
Goal centre y = (goal_top + goal_bottom) / 2.
For "home" team: my_goal_x=0.0, opponent_goal_x=1.0. For "away", reversed.
These x-values SWAP at half-time — read them every tick. Never assume a fixed direction.
Iterate teammates and opponents to find specific players by role or position.
Never assume roster size — 5v5 has 5 per team, 11v11 has 11.

=== PLAYER STATE (dict) ===
player_state = {
    "name": str,               # actual player name, e.g. "Lionel Messi"
    "number": int,             # jersey number, e.g. 10 — use for player-specific logic
    "role": str,               # GK | CB | LB | RB | CDM | CM | CAM | LM | RM | LW | RW | ST | CF
    "position": [float, float],  # YOUR current position, normalized 0-1
    # ATTRIBUTES (0-100 range):
    "pace": int,               # maximum movement per tick
    "shooting": int,           # shot accuracy
    "passing": int,            # pass landing accuracy
    "dribbling": int,          # success rate when carrying past a defender
    "defending": int,          # tackle success rate
    "physicality": int,        # strength — affects tackle outcome and foul probability
    "stamina": int,            # endurance. Each non-Hold action drains health; Hold recovers.
    "awareness": int,          # reaction speed and positioning intelligence
    "composure": int,          # decision-making under pressure
    # STATUS:
    "has_ball": bool,          # True if YOU currently possess the ball
    "health": float,           # 0.0-1.0. Below 0.5, effectiveness drops. Hold recovers it.
    "on_cooldown": bool,       # True → Pass/Shoot/Tackle BLOCKED; only Move/Hold allowed
}

=== HISTORY (list) ===
history = [
    {"tick": int, "action": str, "success": bool},
    ...  # last 20 actions, oldest first. Empty at match start.
]

=== ATTRIBUTE REFERENCE ===
9 attributes, 0-100:
  pace:       max movement per tick. High pace = fast player.
  shooting:   shot accuracy. Blend with awareness for effective shot skill.
  passing:    pass landing accuracy. Blend with awareness.
  dribbling:  ball control + carry success. Blend with pace for effective dribble.
  defending:  tackle success + interception. Blend with physicality for effective tackle.
  physicality: strength — affects tackle outcome AND foul probability. High = stronger but more fouls.
  stamina:    endurance. Each action drains health by base_cost × (1 - stamina/100).
              stamina=100 burns no health. All success formulas multiply by health_factor.
  awareness:  reaction speed. Blended into shooting, passing, and dribbling effectiveness.
  composure:  decision quality under pressure. High = fewer panic passes.
Hold and low-speed Move recover health; half-time restores fully.

=== SHOOTING DISCIPLINE ===
Prevent the "dead zone" where a team logs ZERO shots: this happens when the pass-first
rule releases the ball as soon as the carrier reaches the final third, while the shoot
rule only fires from very close range. Make your shoot condition OVERLAP the pass-first
range — do not let the shoot gate sit strictly closer to goal than where you start passing.
Central carriers near the penalty area edge (x ≈ 0.8 for home, 0.2 for away) with
a sight of goal and no defender RIGHT on them should SHOOT, not recycle.

=== OFFSIDE (IFAB Law 11) ===
A teammate in the OPPONENTS' half AND nearer the opponent's goal line than BOTH the
ball and the second-last opponent (any role — usually GK + last defender) is OFFSIDE.
Level with the second-last opponent = onside. If a player flagged offside is the FIRST
to control the pass → play stopped, free kick to opponents. No offside from goal kicks
or throw-ins. Tactics: attackers time runs to stay level until the pass is struck, then
sprint. Passers check receiver BEFORE passing forward. Defenders hold a high line to trap.

=== FOULS AND CARDS (IFAB Law 12) ===
Every Tackle risks a foul — chance scales with your physicality rating (doubles near 100,
vanishes near 0). Foul stops play: direct free kick to fouled team. Foul inside YOUR
penalty area (within ~16.5 units of your goal line in meters, ~0.15 in normalized x)
→ PENALTY KICK. Accumulated fouls may bring a yellow card (warning) or red card
(sent off for rest of match with no replacement). NEVER tackle inside your own penalty
area unless preventing a certain goal.

=== SNAP MECHANICS ===
The engine automatically pulls players toward their formation position when idle.
You do NOT need to hardcode positional anchors like (0.25, 0.5).
Focus on WHAT the player should DO (pass/shoot/tackle/direction), not WHERE their
formation spot is. The engine handles positioning automatically.
Active intent (Move at speed>=0.5, or any carrier action) bypasses the pull entirely —
the player goes exactly where you tell them.

=== ROLE TACTICAL GUIDANCE ===
GK:  stays in penalty area; saves shots; distributes short to CBs. Sweep only for
     certain through-balls. Distribute long if pressed.
DEF (CB,LB,RB): holds shape when defending; PUSHES UP to midfield when team_phase
     is "attacking". Overlapping runs encouraged when team has sustained possession
     in opponent's half.
MID (CDM,CM,CAM,LM,RM): shuttles between thirds based on team_phase. Supports both
     attack and defense. The most position-flexible role. CDM sits deeper, CAM pushes
     higher, CM balances.
FWD (ST,CF,LW,RW): presses high when attacking; drops back to support press when
     defending. Looks for through-balls behind the defense. ST stays central,
     wingers (LW,RW) stay wide.

=== RUNTIME IDENTITY ===
The same decide() runs for every player on every tick. To know which team and
which player you are this call, read:
  game_state["my_team"]       # "home" or "away"
  game_state["my_player_id"]  # your player_id this call, e.g. "home_7"
  player_state["role"]        # "GK", "DEF", "MID", or "FWD" — branch on this
NEVER hardcode specific player_ids — they vary by config and roster size.

=== SANDBOX CONSTRAINTS ===
- DO NOT use `import` statements — not even `import math`. The sandbox blocks them silently.
  A strategy with an import will return Hold() on every tick (looks frozen).
- sqrt(x) → x**0.5; pi → 3.141592653589793
- Do NOT use print(), open(), exec(), eval(), or any I/O.
- Do NOT define functions outside decide(). Helpers must be nested inside decide().
- You MAY define nested functions and use module-level variables for persistent state.
- Available builtins: abs, min, max, sum, len, range, sorted, enumerate,
  isinstance, int, float, str, list, dict, tuple, bool, round, zip, set.

=== FIELD GEOMETRY ===
Field and goal geometry vary — ALWAYS read from inputs:
  fw = game_state["field"]["width"]    # 68.0
  fh = game_state["field"]["height"]   # 105.0
  my_goal = game_state["field"]["my_goal_x"]
  opp_goal = game_state["field"]["opponent_goal_x"]
  goal_center_y = (game_state["field"]["goal_top"] + game_state["field"]["goal_bottom"]) / 2
Pick your defending goal by team. Attack the OPPOSITE goal. These swap at half-time — read them every tick.

=== BALL CARRIER LOGIC (CRITICAL) ===
EVERY player, including special ones (_9, _10, etc.), MUST handle has_ball=True.
If you get the ball, you MUST do something with it. The worst outcome is Hold() —
a carrier who Holds freezes the match. No player is exempt from this rule.
- Attacking third → Shoot if within range and central, else Pass to a forward teammate.
- Own half → Pass forward to an open teammate, or Dribble into space.
- No good option → Move TOWARD opponent's goal (general direction, not fixed spot).
- Never Hold for more than 2-3 ticks — keep the ball moving.
- AFTER your per-role special logic, ALWAYS have a fallback carrier branch:
  if has_ball: return Dribble toward opponent's goal or Pass to nearest open teammate.

=== OFF-BALL LOGIC ===
- Team attacking: Move TOWARD the ball to support, find gaps between defenders.
- Team defending: Track back GOAL-SIDE of the ball, mark nearby opponents.
- GK: Stay near goal. Distribute short to CBs. Rush out only for certain through-balls.

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

        # Build player ID → name mapping from the tactical doc's index references
        player_map = self._build_player_id_map(doc)

        return f"""Team: {team_name}
Formation: {formation}

=== PLAYER ID MAP ===
{player_map}

=== TACTICAL DOCUMENT ===
{doc}

=== TASK ===
Write the complete decide() function that implements this tactical style.
Use the PLAYER ID MAP above to reference specific players by their correct IDs.
For all other logic, branch on player_state["role"].
Return ONLY the Python code in a fenced block."""

    @staticmethod
    def _build_player_id_map(doc: str) -> str:
        """Parse tactical doc for player references with jersey numbers.
        Format: '- index N: ROLE — **Player Name** (#shirt)'
        Returns jersey number → name mapping."""
        import re
        lines = []
        for m in re.finditer(
            r'index \d+:\s*([\w/ ]+?)\s*[—–-]\s*\*{0,2}(.+?)\*{0,2}\s*\(#(\d+)\)', doc
        ):
            role, name, number = m.groups()
            role = role.strip().strip("*")
            name = name.strip().rstrip(",").strip("*")
            lines.append(f"  #{number} = {role} — {name}")
        if lines:
            return "Jersey numbers (use player_state[\"number\"] to identify):\n" + "\n".join(lines)
        return "(no jersey number mapping found — use role-based or name-based branching)"

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
