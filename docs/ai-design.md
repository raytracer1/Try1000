# Try1000 AI Design

Try1000 has two AI layers:

1. **Engine AI** — Rule-based football intelligence that controls 22 players during simulation
2. **Agent AI** — LLM-powered analysis agents that help users understand and improve tactics

---

# Part 1: Engine AI (Rule-Based)

## Overview

The Engine AI controls every player on the pitch during simulation. It is:
- **Rule-based**: hand-written weights + modifiers, no training data, no GPU
- **Deterministic**: given the same seed, produces the same decisions
- **Tactics-aware**: player behavior is shaped by formation, roles, and team tactics
- **Replaceable**: the `Policy` interface can be swapped for LLM-generated code later (see [Level 2 upgrade](#level-2-llm-generated-policy-future))

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Engine AI Pipeline                  │
│                                                       │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐       │
│  │Perception│───▶│Evaluation│───▶│ Decision │       │
│  └──────────┘    └──────────┘    └──────────┘       │
│       │               │               │              │
│       ▼               ▼               ▼              │
│  What can I       Which action     Execute the       │
│  see around       has highest      chosen action     │
│  me right now?    utility score?   (roll dice)       │
│                                                       │
│  Inputs:           Weights from:    Output:           │
│  - Ball position   - Player role    - Pass/Shoot/     │
│  - Teammates       - Team tactics     Dribble/...     │
│  - Opponents       - Match state   - Target position │
│  - My position     - Success prob   - Success/fail    │
└─────────────────────────────────────────────────────┘
```

## Perception System

Each player has a **limited view** of the pitch. They do NOT see everything — this creates realistic decision-making.

```python
class Perception:
    def gather(self, player, state) -> PerceptionData:
        return PerceptionData(
            ball_position=state.ball.position,
            ball_distance=distance(player, state.ball),
            has_possession=(state.possession.player_id == player.id),
            nearby_teammates=self.find_teammates(player, state, radius=30.0),
            nearby_opponents=self.find_opponents(player, state, radius=25.0),
            nearest_opponent=self.find_nearest(player, state.opponents),
            distance_to_goal=self.distance_to_opponent_goal(player),
            distance_to_own_goal=self.distance_to_own_goal(player),
            pressure_level=self.calculate_pressure(player, state),
            space_ahead=self.find_space(player, state),
        )
```

**Key parameters:**
- Vision radius varies by awareness attribute (60–100 → 20m–40m radius)
- Players under pressure have reduced awareness
- Ball carrier sees less (head down, focused on ball)

## Evaluation System

Each possible action gets a **utility score**. The action with the highest score wins.

```python
class Evaluator:
    def evaluate(self, perception, player, tactics, state) -> dict[Action, float]:
        scores = {}
        for action in ActionType:
            base = self.base_weight(action, player.role)
            tactic_mod = self.tactic_modifier(action, tactics)
            situation_mod = self.situation_modifier(action, perception, state)
            success_prob = self.success_probability(action, perception, player)
            scores[action] = base * tactic_mod * situation_mod * success_prob
        return scores
```

### Base Weights by Role

| Role | Pass | Shoot | Cross | Dribble | Hold | Move |
|------|------|-------|-------|---------|------|------|
| GK | 0.3 | 0.0 | 0.0 | 0.1 | 0.5 | 0.1 |
| CB | 0.6 | 0.0 | 0.0 | 0.2 | 0.4 | 0.2 |
| FB | 0.5 | 0.1 | 0.4 | 0.3 | 0.2 | 0.4 |
| CDM | 0.5 | 0.2 | 0.1 | 0.2 | 0.3 | 0.2 |
| CM | 0.5 | 0.3 | 0.2 | 0.3 | 0.1 | 0.3 |
| CAM | 0.4 | 0.4 | 0.2 | 0.4 | 0.0 | 0.3 |
| Winger | 0.3 | 0.3 | 0.5 | 0.5 | 0.0 | 0.4 |
| ST | 0.2 | 0.6 | 0.1 | 0.3 | 0.1 | 0.3 |

### Tactical Modifiers

Each tactical parameter adjusts action preferences:

| Tactic Param | Effect |
|-------------|--------|
| **Pressing (1-10)** | ↑ = more tackles, higher defensive line, more interceptions |
| **Defensive Line (1-10)** | ↑ = defenders push higher, more offside traps |
| **Attacking Width (1-10)** | ↑ = wingers stay wider, more crosses; ↓ = narrow attacks, more through balls |
| **Passing Style** | Short → safe short passes; Direct → long balls forward; Mixed → balanced |
| **Build-up Style** | Slow → hold position, short passes; Fast → direct runs, quick transitions |
| **Tempo (1-10)** | ↑ = faster decisions, less hold, more risk |

### Situational Modifiers

| Situation | Effect |
|-----------|--------|
| Near opponent goal (< 25m) | Increase shoot weight |
| Under heavy pressure | Reduce hold, increase pass urgency |
| Counter-attack (transition phase) | Increase move/dribble, long passes |
| Leading by 2+ goals, late game | Reduce tempo, increase hold |
| Losing, late game | Increase risk, direct play |

## Action Resolution

Every action has a success probability. A random roll determines outcome.

### Pass Success Model

```
pass_success = f(
    passer.passing,        # attribute: 0-100
    distance_to_target,    # longer = harder
    pressure_on_passer,    # more pressure = harder
    receiver_awareness,    # better positioning = easier
    passing_style,         # short = easier, direct = harder
)
```

| Factor | Weight |
|--------|--------|
| Passer passing skill | 40% |
| Pass distance | 25% |
| Pressure | 20% |
| Receiver awareness | 15% |

### Shot xG Model

```
xG = f(
    distance_to_goal,      # inverted: closer = higher
    angle_from_goal,       # centered = higher
    pressure_on_shooter,
    shooter.shooting,
    goalkeeper.awareness,  # better keeper = lower xG
    shot_type,             # volley, header, driven, placed
)
```

| Distance (m) | Base xG |
|-------------|---------|
| 0-6 (box) | 0.40 |
| 6-12 | 0.18 |
| 12-18 | 0.08 |
| 18-25 | 0.03 |
| 25+ | 0.01 |

Modified by angle, pressure, shooter skill, keeper skill.

### Dribble Success Model

```
dribble_success = f(
    attacker.dribbling,
    defender.tackling,
    defender_count,        # multiple defenders = harder
    space_available,
)
```

### Tackle Success Model

```
tackle_success = f(
    defender.tackling,
    attacker.dribbling,
    tackle_type,           # standing vs sliding
    approach_angle,
)
foul_probability rises with poor tackling and desperation.
```

## Match Phases

The match engine tracks which phase the game is in. AI behavior changes per phase.

```
KICKOFF → BUILD_UP → ATTACK ⇄ DEFENSE → TRANSITION → SET_PIECE
                                                         │
                                                    ┌────┘
                                                    ▼
                                               BUILD_UP / ATTACK / DEFENSE
```

| Phase | Description | AI Behavior |
|-------|-------------|-------------|
| **KICKOFF** | Start of match/half or after goal | Predefined positions, short pass |
| **BUILD_UP** | Team has possession in own half | Patient passing, movement into space |
| **ATTACK** | Team has possession in opponent half | Creative runs, through balls, crosses |
| **DEFENSE** | Opponent has possession | Track back, maintain shape, press triggers |
| **TRANSITION** | Possession just changed | Quick decisions: counter-attack or recover shape |
| **SET_PIECE** | Free kick, corner, throw-in, goal kick | Set piece routines |

## Stamina Model

```python
class Stamina:
    MAX = 100.0
    BASE_DECAY = 0.02    # per tick at walking speed
    SPRINT_DECAY = 0.12  # per tick at sprint speed
    BASE_RECOVERY = 0.01 # per tick when walking/standing

    def update(self, current_speed: float, dt: float):
        if current_speed > SPRINT_THRESHOLD:
            self.value -= SPRINT_DECAY * self.stamina_factor * dt
        else:
            self.value -= BASE_DECAY * dt
            self.value += BASE_RECOVERY * dt

        self.value = clamp(self.value, 30.0, 100.0)  # can't go below 30%

    @property
    def speed_multiplier(self) -> float:
        # below 50% stamina → movement speed decreases
        if self.value > 70: return 1.0
        if self.value > 50: return 0.85
        return 0.70
```

Stamina affects: movement speed, decision quality (urgency), pass/shoot accuracy (slight penalty when exhausted).

---

## Level 2: Custom Policy (Future)

Level 1 uses hand-written weights. Level 2 allows advanced users to write their own `decide()` function in Python, implementing the `Policy` interface.

```
class CustomPolicy(Policy):
    def __init__(self, decide_fn):
        self._decide_fn = decide_fn

    def decide(self, obs: Observation) -> ActionOutput:
        return self._decide_fn(obs)
```

**Key constraint**: the decision logic is **fixed for a batch of matches**. A 1000-match test uses the exact same code for all 1000 matches. This is necessary because:
- Changing logic between matches makes results incomparable
- The only variable in a test batch should be the tactical parameters (1-10 sliders)
- "Improving tactics" means changing parameters, not changing code

Level 2 exists for flexibility, not as part of the optimization loop.

---

# Part 2: Agent AI (LLM-Powered)

## Overview

Three AI agents run locally on the user's machine. They use LLMs (Claude, GPT, etc.) to analyze tactics and simulation results, then provide actionable insights.

**Key design decisions:**
- User's LLM API key stays local — never sent to the backend
- Agents are stateless: input → LLM → output
- Prompt templates are in separate `.txt` files, easy to modify
- Outputs are structured (JSON + Markdown) for frontend rendering

## Base Agent

```python
class BaseAgent:
    """Common LLM client shared by all agents."""

    def __init__(self, api_key: str, model: str, provider: str):
        self.client = self._build_client(api_key, model, provider)

    def run(self, system_prompt: str, user_input: str) -> str:
        response = self.client.messages.create(
            model=self.model,
            system=system_prompt,
            messages=[{"role": "user", "content": user_input}],
            max_tokens=4096,
        )
        return response.content[0].text
```

## Agent 1: Tactics Agent

**Purpose**: Analyze a tactic and explain its strengths and weaknesses before any simulation is run.

**Input:**
```json
{
  "formation": "4-3-3",
  "player_positions": {
    "p1": {"x": 0.5, "y": 0.1, "role": "GK"},
    "p2": {"x": 0.3, "y": 0.3, "role": "CB"},
    "...": "..."
  },
  "pressing_level": 7,
  "defensive_line": 6,
  "attacking_width": 8,
  "passing_style": "short",
  "build_up_style": "slow",
  "tempo": 5
}
```

**LLM System Prompt (abbreviated):**
```
You are an expert football tactics analyst. Given a tactic configuration,
analyze it and respond in JSON format:

{
  "summary": "One-sentence tactical profile",
  "strengths": [
    {"title": "...", "description": "..."},
    ...
  ],
  "weaknesses": [
    {"title": "...", "description": "..."},
    ...
  ],
  "ideal_against": "What kind of opponent this tactic counters",
  "vulnerable_against": "What kind of opponent counters this tactic",
  "style_label": "e.g. High-Press Possession, Counter-Attacking, etc."
}
```

**Output Example:**
```json
{
  "summary": "A high-pressing 4-3-3 built for possession dominance with wide attacks.",
  "strengths": [
    {"title": "Wide overloads", "description": "Fullbacks push high while wingers stay wide, creating 2v1 on flanks."},
    {"title": "High press triggers", "description": "Pressing level 7 forces turnovers in opponent's half."}
  ],
  "weaknesses": [
    {"title": "Space behind fullbacks", "description": "Attacking width 8 + high defensive line leaves gaps for counter-attacks."},
    {"title": "Slow build-up vulnerability", "description": "Short passing from the back is vulnerable to high pressing opponents."}
  ],
  "ideal_against": "Teams that sit deep and defend narrow",
  "vulnerable_against": "Fast counter-attacking 4-4-2 with pace on wings",
  "style_label": "High-Press Possession"
}
```

## Agent 2: Analysis Agent

**Purpose**: Generate a comprehensive tactical report from simulation results.

**Input:** Aggregated statistics from N simulated matches:
```json
{
  "match_count": 100,
  "home_wins": 52, "draws": 23, "away_wins": 25,
  "avg_home_goals": 1.8, "avg_away_goals": 1.2,
  "avg_home_xg": 1.9, "avg_away_xg": 1.1,
  "avg_home_possession": 58.3,
  "pass_accuracy": 84.2,
  "shots_per_match": 14.3,
  "shots_on_target_per_match": 5.8,
  "pass_network": {
    "edges": [{"from": "p4", "to": "p7", "count": 34}, ...]
  },
  "heatmap_zones": {
    "zone_D3": 0.15, "zone_E4": 0.22, ...
  },
  "xg_timeline": [0.0, 0.1, 0.1, 0.2, ...],
  "goals_conceded_zones": [
    {"zone": "left_flank", "count": 12},
    {"zone": "center_box", "count": 8}
  ],
  "top_passers": [
    {"player_id": "p4", "name": "CM", "passes": 87, "accuracy": 91.2}
  ]
}
```

**LLM System Prompt (abbreviated):**
```
You are an expert football performance analyst. Given match simulation
statistics, generate a detailed tactical report in JSON format:

{
  "headline": "One-line summary of the simulation results",
  "attack_analysis": {
    "effectiveness": "Why attacks succeeded",
    "patterns": ["Key attacking patterns observed"],
    "xg_analysis": "xG vs actual goals analysis"
  },
  "possession_analysis": {
    "retention": "Where possession is kept/lost",
    "transitions": "Counter-attack effectiveness"
  },
  "defensive_analysis": {
    "vulnerabilities": ["Weak defensive areas"],
    "pressing_effectiveness": "How well the press worked"
  },
  "player_performance": [
    {"player": "name", "rating": 7.5, "note": "..."},
    ...
  ],
  "key_insight": "The single most important finding"
}
```

## Agent 3: Optimization Agent

**Purpose**: Suggest tactic improvements based on simulation results.

**Input:** Current tactic + simulation results:
```json
{
  "current_tactic": { /* full tactic JSON */ },
  "simulation_summary": {
    "win_rate": 0.52,
    "avg_goals_scored": 1.8,
    "avg_goals_conceded": 1.2,
    "xg_diff": 0.8,
    "possession": 58.3,
    "top_weakness": "vulnerable to counter-attacks down the flanks"
  }
}
```

**LLM System Prompt (abbreviated):**
```
You are an expert football tactics coach. Given a tactic and its simulation
results, suggest specific, justified improvements. Respond in JSON:

{
  "changes": [
    {
      "param": "defensive_line",
      "from": 6,
      "to": 5,
      "reason": "Lowering the defensive line by 1 reduces space behind fullbacks,
                  which was the main source of conceded goals (12 from left flank alone)."
    },
    ...
  ],
  "expected_improvement": "What should change after applying these modifications",
  "risk": "Any new weakness these changes might introduce"
}
```

**Constraints for the LLM:**
- Change at most 3 parameters at a time (too many changes make it hard to attribute improvement)
- Each change must reference specific data from the simulation results
- Changes must be within valid ranges (1-10 for sliders)
- Must explain the tactical reasoning, not just say "increase this"
- **Agent only outputs suggestions. It never writes to the tactic.**
- **Only the user, via the frontend "Apply Changes" button, can modify tactics.**

---

## Agent Task Flow (Local)

```
┌─────────────────────────────────────────────┐
│              Local Runtime Loop              │
│                                               │
│  1. Ably Client receives task notification   │
│     │                                         │
│     ▼                                         │
│  2. HTTP GET /tasks/{id} from backend        │
│     │  → task type, input data               │
│     ▼                                         │
│  3. Route to correct agent:                  │
│     ├── "tactics_analysis" → TacticsAgent    │
│     ├── "match_report"    → AnalysisAgent    │
│     └── "optimization"    → OptimizationAgent│
│     │                                         │
│     ▼                                         │
│  4. Agent builds prompt + calls LLM          │
│     (using user's local API key)             │
│     │                                         │
│     ▼                                         │
│  5. HTTP POST result back to backend         │
│     │  → POST /agent/{type}/{id}/result      │
│     ▼                                         │
│  6. Backend stores result, notifies frontend │
│                                               │
└─────────────────────────────────────────────┘
```

---

## Prompt Engineering Principles

1. **Structured output**: All agents return JSON with a defined schema (enforced via `response_format` or system prompt)
2. **Specific over generic**: Prompts ask for data-backed claims, not football clichés
3. **Constrained scope**: Each agent does one thing well; no crossover
4. **Grounded in data**: Prompts require citing specific numbers from the input
5. **Actionable**: Outputs must contain concrete suggestions, not just observations

---

## Future Extensions

- **Streaming responses**: LLM responses streamed token-by-token for faster perceived feedback
- **Multi-model**: Support Claude, GPT, Gemini, local models (Ollama)
- **Agent memory**: Remember previous analyses to track improvement over time
- **Adversarial agent**: An agent that tries to "beat" your tactic before simulation
- **Training data**: Collect user corrections to fine-tune prompts over time
