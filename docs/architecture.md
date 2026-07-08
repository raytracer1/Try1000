# Try1000 Architecture

## Overview

Try1000 is an AI-powered football tactics simulation platform. Users design tactics, simulate hundreds of matches, analyze results, and continuously improve their strategies.

The system has a **split architecture**: the web application runs remotely (cloud), while the compute-heavy simulation engine and AI agents run locally on the user's machine.

```
┌─────────────────── Remote (Cloud) ───────────────────┐
│                                                       │
│  ┌──────────────┐        ┌──────────────────┐        │
│  │   Frontend   │◀──────▶│     Backend      │        │
│  │  (Next.js)   │        │    (FastAPI)     │        │
│  └──────────────┘        └────────┬─────────┘        │
│                                    │                  │
│                           ┌────────┴────────┐        │
│                           │   PostgreSQL     │        │
│                           └────────┬────────┘        │
│                                    │                  │
│                           ┌────────┴────────┐        │
│                           │      Ably        │        │
│                           │   (Pub/Sub)      │        │
│                           └────────┬────────┘        │
│                                    │                  │
└────────────────────────────────────┼──────────────────┘
                                     │
                            Internet │
                                     │
┌────────────────────────────────────┼──────────────────┐
│                       Local (User Machine)            │
│                                    │                  │
│  ┌─────────────────────────────────┴─────────────┐   │
│  │              Try1000 Local Runtime             │   │
│  │                                                 │   │
│  │  ┌──────────────────┐  ┌──────────────────┐   │   │
│  │  │     Engine        │  │      Agent        │   │   │
│  │  │  (Match Sim)      │  │   (LLM Analysis)  │   │   │
│  │  │                   │  │                   │   │   │
│  │  │  - Physics        │  │  - Tactics Agent  │   │   │
│  │  │  - Match Loop     │  │  - Analysis Agent │   │   │
│  │  │  - Rule-based AI  │  │  - Optimize Agent │   │   │
│  │  │  - Replay Output  │  │                   │   │   │
│  │  └────────┬─────────┘  └────────┬──────────┘   │   │
│  │           │                     │               │   │
│  │           └─────────┬───────────┘               │   │
│  │                     │                           │   │
│  │            ┌────────┴────────┐                  │   │
│  │            │   Ably Client   │                  │   │
│  │            │  (Subscribe)    │                  │   │
│  │            └────────┬────────┘                  │   │
│  │                     │                           │   │
│  │            ┌────────┴────────┐                  │   │
│  │            │   HTTP Client   │                  │   │
│  │            │  (Post results) │                  │   │
│  │            └─────────────────┘                  │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## Design Principles

1. **Split compute**: Heavy simulation runs locally. Web serving stays remote.
2. **Privacy**: User LLM API keys never leave the local machine.
3. **Modular**: Each component (frontend, backend, engine, agent) is independently testable and replaceable.
4. **Deterministic**: Same input + same seed = same output. Critical for trust and debugging.

---

## Components

### 1. Frontend (Remote)

| Aspect | Choice |
|--------|--------|
| Framework | Next.js 14 (App Router) |
| Language | TypeScript |
| Styling | TailwindCSS |
| State | Zustand |
| Tactics Editor | React Flow (drag-and-drop on pitch) |
| Charts | Recharts |
| Replay | HTML5 Canvas |

**Pages:**

| Route | Description |
|-------|-------------|
| `/` | Dashboard — recent simulations, key stats |
| `/tactics` | Tactics Editor — formation, player positions, tactical params |
| `/simulation` | Simulation Runner — configure & run matches, view replay |
| `/analytics/[jobId]` | Analytics — charts, heatmaps, pass network, shot map |
| `/settings` | Settings — Ably key, simulation speed |
| `/auth/login` | Login |
| `/auth/register` | Register |

### 2. Backend (Remote)

| Aspect | Choice |
|--------|--------|
| Framework | FastAPI (Python 3.13) |
| Database | PostgreSQL 14 |
| ORM | SQLAlchemy 2.0 |
| Migrations | Alembic |
| Auth | JWT (access + refresh tokens) |
| Realtime | Ably (pub/sub for task dispatch) |

**Modules:**

| Module | Responsibility |
|--------|---------------|
| `api/auth` | User registration, login, token management |
| `api/teams` | CRUD for teams and players |
| `api/tactics` | CRUD for tactics |
| `api/simulation` | Create jobs, receive results, serve replay data |
| `api/analytics` | Pre-computed statistics for completed jobs |
| `api/agent` | Create agent tasks, receive agent results |

### 3. Engine (Local)

Runs on the user's machine. A CLI program that:

1. Subscribes to Ably channel for simulation tasks
2. Downloads task config from backend
3. Runs N matches with seeded RNG
4. Uploads results + replay data to backend via HTTP
5. Reports progress during execution

**Internal modules:**

| Module | Responsibility |
|--------|---------------|
| `physics/` | Ball movement, player movement, collision, stamina |
| `actions/` | Pass, shoot, cross, dribble, tackle, intercept, move |
| `ai/` | Rule-based decision making (perception → evaluation → action) |
| `match/` | Tick loop, event recording, replay serialization |

### 4. Agent (Local)

Runs on the user's machine alongside the engine. Calls LLM APIs using the user's own API key (never sent to the server).

**Three agents:**

| Agent | Input | Output |
|-------|-------|--------|
| Tactics Agent | Tactic JSON | Strengths/weaknesses analysis |
| Analysis Agent | Simulation statistics | Tactical report |
| Optimization Agent | Tactics + simulation history | Improved tactic + change explanations |

---

## Communication Flow

### Simulation Flow

```
User                Frontend           Backend           Ably            Local Engine
 │                     │                  │                │                  │
 │  click "Run 100"    │                  │                │                  │
 │────────────────────▶│                  │                │                  │
 │                     │  POST /simulate  │                │                  │
 │                     │────────────────▶│                │                  │
 │                     │                  │  create job    │                  │
 │                     │                  │──────────────┐ │                  │
 │                     │                  │              │ │                  │
 │                     │   { job_id }     │              │ │                  │
 │                     │◀────────────────│              │ │                  │
 │                     │                  │              │ │                  │
 │                     │                  │  publish task │ │                  │
 │                     │                  │──────────────▶│                  │
 │                     │                  │              │ │  push notification│
 │                     │                  │              │ │────────────────▶│
 │                     │                  │              │ │                  │
 │                     │                  │◀─────────────┐ │                  │
 │                     │                  │  GET /tasks   │ │                  │
 │                     │                  │──────────────┐ │                  │
 │                     │                  │              │ │                  │
 │  poll GET /jobs/{id}│                  │              │ │                  │
 │────────────────────▶│                  │              │ │                  │
 │   { progress: 45% } │                  │              │ │                  │
 │◀────────────────────│                  │              │ │     run matches  │
 │                     │                  │              │ │                  │
 │                     │                  │◀─────────────┐ │                  │
 │                     │                  │  POST /jobs/{id}/results          │
 │                     │                  │              │ │                  │
 │   { status: done }  │                  │              │ │                  │
 │◀────────────────────│                  │              │ │                  │
```

### Agent Flow

```
User                Frontend           Backend           Ably            Local Agent
 │                     │                  │                │                  │
 │  click "Analyze"    │                  │                │                  │
 │────────────────────▶│                  │                │                  │
 │                     │  POST /agent/... │                │                  │
 │                     │────────────────▶│                │                  │
 │                     │                  │  publish task  │                  │
 │                     │                  │──────────────▶│                  │
 │                     │                  │              │ │  pick up task    │
 │                     │                  │              │ │────────────────▶│
 │                     │                  │              │ │                  │
 │                     │                  │              │ │   call LLM API   │
 │                     │                  │              │ │   (local key)    │
 │                     │                  │              │ │                  │
 │                     │                  │◀─────────────┐ │                  │
 │                     │                  │  POST /agent/{id}/result          │
 │                     │                  │              │ │                  │
 │  poll or return     │                  │              │ │                  │
 │◀────────────────────│                  │              │ │                  │
```

---

## Data Models

```
User
  id: UUID
  email: String (unique)
  username: String (unique)
  hashed_password: String
  created_at: DateTime

Team
  id: UUID
  user_id: UUID → User
  name: String
  created_at: DateTime

Player
  id: UUID
  team_id: UUID → Team
  name: String
  number: Int
  position: Enum (GK|CB|LB|RB|CDM|CM|CAM|LM|RM|LW|RW|ST)
  attributes: JSON {pace, shooting, passing, dribbling, defending, physicality, stamina, awareness, composure}
  created_at: DateTime

Tactic
  id: UUID
  user_id: UUID → User
  team_id: UUID → Team
  name: String
  formation: String (e.g. "4-3-3")
  player_positions: JSON {player_id: {x, y, role}}
  pressing_level: Int (1-10)
  defensive_line: Int (1-10)
  attacking_width: Int (1-10)
  passing_style: Enum (short|mixed|direct)
  build_up_style: Enum (slow|balanced|fast)
  tempo: Int (1-10)
  created_at: DateTime
  updated_at: DateTime

SimulationJob
  id: UUID
  user_id: UUID → User
  home_team_id: UUID → Team
  away_team_id: UUID → Team
  home_tactic_id: UUID → Tactic
  away_tactic_id: UUID → Tactic
  match_count: Int (1|10|100|1000)
  status: Enum (pending|running|completed|failed)
  progress: Int (0-100)
  seed_base: Int
  created_at: DateTime
  completed_at: DateTime?

SimulationResult
  id: UUID
  job_id: UUID → SimulationJob
  match_index: Int
  home_score: Int
  away_score: Int
  home_xg: Float
  away_xg: Float
  home_possession: Float
  away_possession: Float
  stats: JSON
  events: JSON (replay ticks)
  created_at: DateTime
```

---

## API Endpoints

Base: `/api/v1`

### Auth
| Method | Path | Auth |
|--------|------|------|
| POST | `/auth/register` | No |
| POST | `/auth/login` | No |
| GET | `/auth/me` | Yes |

### Teams
| Method | Path | Auth |
|--------|------|------|
| GET | `/teams` | Yes |
| POST | `/teams` | Yes |
| GET | `/teams/{id}` | Yes |
| PUT | `/teams/{id}` | Yes |
| DELETE | `/teams/{id}` | Yes |
| POST | `/teams/{id}/players` | Yes |
| PUT | `/players/{id}` | Yes |
| DELETE | `/players/{id}` | Yes |

### Tactics
| Method | Path | Auth |
|--------|------|------|
| GET | `/tactics` | Yes |
| POST | `/tactics` | Yes |
| GET | `/tactics/{id}` | Yes |
| PUT | `/tactics/{id}` | Yes |
| DELETE | `/tactics/{id}` | Yes |

### Simulation
| Method | Path | Auth |
|--------|------|------|
| POST | `/simulate` | Yes |
| GET | `/simulation/jobs` | Yes |
| GET | `/simulation/jobs/{id}` | Yes |
| GET | `/simulation/jobs/{id}/replay/{matchIndex}` | Yes |
| POST | `/simulation/jobs/{id}/results` | Engine* |
| PUT | `/simulation/jobs/{id}/progress` | Engine* |

*Engine authenticates with a per-user API token, not JWT.

### Analytics
| Method | Path | Auth |
|--------|------|------|
| GET | `/analytics/job/{jobId}` | Yes |
| GET | `/analytics/job/{jobId}/match/{matchIndex}` | Yes |

### Agent
| Method | Path | Auth |
|--------|------|------|
| POST | `/agent/tactics/analyze` | Yes |
| POST | `/agent/tactics/analyze/{id}/result` | Engine* |
| POST | `/agent/match/report` | Yes |
| POST | `/agent/match/report/{id}/result` | Engine* |
| POST | `/agent/tactics/optimize` | Yes |
| POST | `/agent/tactics/optimize/{id}/result` | Engine* |

---

## Simulation Constraints (Invariants)

These constraints are enforced by design. No component may violate them.

### 1. Fixed Decision Logic

During a simulation batch (1–1000 matches), every player's `decide()` function is **immutable**. The same observation always maps to the same action distribution. This guarantees:

- Match 1 and Match 1000 use identical player intelligence
- Any difference in results comes from RNG + tactics, not from evolving AI
- Results are comparable across a batch

### 2. Tactical Parameters Are Read-Only for Engine and Agent

```
┌──────────────────────────────────────────────────────────────┐
│              Only the User Changes Tactics                   │
│                                                              │
│  User                    Engine              Agent           │
│  ────                    ──────              ─────           │
│  writes tactic           reads tactic        reads tactic    │
│  edits params            never writes        never writes    │
│  saves to DB             params              params          │
│  clicks "Apply"          only consumes       only suggests   │
│                                                              │
│  Tactic params are immutable during a simulation batch.      │
│  Agent outputs advice text — never mutates tactic objects.   │
└──────────────────────────────────────────────────────────────┘
```

Rule:
- Engine: reads `tactic` dict, uses it to compute `tactic_modifier` → **never modifies**
- Agent: reads `tactic` + `match_results`, outputs `{changes: [{param, from, to, reason}]}` → **user decides**
- Only the `PATCH /api/v1/tactics/{id}` endpoint (called by user action in frontend) mutates tactic data

### 3. No Automatic Optimization Loop

There is no closed loop where the system runs simulations and auto-applies parameter changes. The full cycle is always:

```
User designs tactic → User runs simulation → User views results
→ User requests AI analysis (optional) → User applies changes (optional)
→ Loop
```

The human is always the decision-maker. This is a coaching tool, not an auto-tuner.

---

## Engine Design

### Core Concepts

| Concept | Description |
|---------|-------------|
| **Tick** | 1 tick = 1 second of match time. 5400 ticks = 90 minutes |
| **Snapshot** | All 7 phases in a tick read from one snapshot built at Phase 1 — no player can observe a sibling's action in the same tick |
| **Cooldown** | Pass, Shoot, Tackle, and Pickup trigger a per-player cooldown. Move and Hold never trigger cooldown. While on cooldown, player can only Move or Hold |
| **Seeded RNG** | seed = job.seed_base + match_index. Same seed → identical match. Guaranteed |
| **Fallback** | Any AI failure (exception, invalid return) → `Hold()`. Circuit breaker: 10 consecutive failures → Hold() for rest of match |

### Action Types

```
Returned by decide(). All actions are immutable frozen dataclasses.
```

| Action | Parameters | Triggers Cooldown | Description |
|--------|-----------|-------------------|-------------|
| `Hold()` | none | No | Stand in place. Universal fallback |
| `Move(dx, dy, speed)` | direction vector, speed 0.0–1.0 | No | Move in a given direction |
| `Pass(target_pos, power)` | (x, y) coordinate, power 1–20 | Yes | Kick ball toward a field position |
| `Shoot(angle, power)` | angle in degrees, power 1–20 | Yes | Shoot at goal |
| `Cross(target_pos, power)` | (x, y) coordinate, power 1–20 | Yes | Cross ball into the box |
| `Dribble(dx, dy)` | direction vector | Yes | Carry ball while moving |
| `Tackle(target_player_id)` | opponent player ID | Yes | Win ball from nearby opponent |
| `Intercept()` | none (automatic) | No | Triggered when ball passes near defender |

### AI Decision Function

```
decide(game_state, player_state, history) → Action

Analogous to AgentPitch's decide(), but logic is computed by
rule-based evaluation instead of LLM-generated code. No sandbox needed.
```

**`game_state`** — Shared match snapshot (what everyone can see):
```
{
  tick: int, match_time_seconds: float, half: 1|2,
  score: {home: int, away: int},
  ball: {position: (float, float), possession: "home"|"away"|null, carrier_id: str|null},
  players: {player_id: {team, role, position, has_ball}},
  field: {width, height, goal_center_y, goal_top, goal_bottom, home_goal_x, away_goal_x},
  my_team: "home"|"away",
  my_player_id: str
}
```

**`player_state`** — Per-player attributes (what this player knows about themselves):
```
{
  player_id: str, role: str, position: (float, float),
  pace: 0-100, shooting: 0-100, passing: 0-100,
  dribbling: 0-100, defending: 0-100, physicality: 0-100,
  stamina: 0-100, awareness: 0-100, composure: 0-100,
  has_ball: bool, health: float (0.0–1.0)
}
```

**`history`** — Recent action log (ordered oldest-first):
```
[
  {tick: 120, action: "Pass", success: true, target: (0.6, 0.4)},
  {tick: 115, action: "Move", success: true},
  ...
]
```

### Policy Interface (Swappable AI Backend)

The decision-making layer is abstracted behind a `Policy` interface. The engine's Phase 2 calls `policy.decide()` — it does not know or care whether the policy is rule-based or neural. This is the **primary extension point** for upgrading from Level 1 (rule-based) to Level 2 (neural network).

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Protocol

# ─── Observation: what the policy receives ───

@dataclass
class Observation:
    """Flattened feature vector for a single player at a single tick.
    Built from game_state + player_state + history at Phase 1 snapshot time."""

    # Ball features (5)
    ball_x: float
    ball_y: float
    ball_distance: float           # normalized to [0, 1]
    ball_possession_team: int      # -1=away, 0=none, 1=home (relative to this player)
    has_ball: int                  # 0 or 1

    # Goal features (4)
    distance_to_opponent_goal: float
    angle_to_opponent_goal: float  # radians, 0 = straight on
    distance_to_own_goal: float
    angle_to_own_goal: float

    # Nearest teammate features (3)
    nearest_teammate_distance: float
    nearest_teammate_angle: float
    nearest_teammate_role: int     # one-hot encoded role

    # Nearest opponent features (3)
    nearest_opponent_distance: float
    nearest_opponent_angle: float
    pressure_level: float          # count of opponents within 5m, normalized

    # Spatial features (2)
    space_ahead: float             # open space in facing direction, normalized
    distance_to_touchline: float   # min distance to either sideline

    # Self features (11)
    pace: float                    # all attributes normalized to [0, 1]
    shooting: float
    passing: float
    dribbling: float
    defending: float
    physicality: float
    stamina: float
    awareness: float
    composure: float
    role: int                      # one-hot encoded
    health: float

    # Match context (5)
    score_diff: int                # positive = winning, negative = losing
    match_time_ratio: float        # 0.0 to 1.0
    half: int                      # 1 or 2
    phase: int                     # one-hot: KICKOFF, BUILD_UP, ATTACK, etc.
    possession_phase: int          # -1=out of possession, 0=contested, 1=in possession

    # History features (N recent actions, encoded)
    history_action_types: list[int]    # last 5 action type IDs
    history_success_flags: list[int]   # last 5 success/fail flags

    # Tactical context (6) — the team's tactical parameters
    pressing_level: float          # normalized [0, 1]
    defensive_line: float
    attacking_width: float
    passing_style: int             # one-hot: short, mixed, direct
    build_up_style: int            # one-hot: slow, balanced, fast
    tempo: float                   # normalized [0, 1]

    def to_vector(self) -> list[float]:
        """Flatten to a fixed-length vector for neural network input."""
        ...


# ─── Action: what the policy returns ───

@dataclass
class ActionOutput:
    """Discrete action selection. Same shape regardless of policy implementation."""
    action_type: int           # 0=Hold, 1=Move, 2=Pass, 3=Shoot, 4=Cross,
                               # 5=Dribble, 6=Tackle, 7=Intercept
    dx: float                  # 0.0–1.0, only used by Move/Dribble
    dy: float                  # 0.0–1.0
    speed: float               # 0.0–1.0, only used by Move
    power: float               # 1.0–20.0, only used by Pass/Shoot/Cross
    angle: float               # degrees, only used by Shoot
    target_x: float            # 0.0–1.0, only used by Pass/Cross
    target_y: float            # 0.0–1.0
    target_player_id: int      # only used by Tackle


# ─── The Policy Interface ───

class Policy(ABC):
    """Abstract policy for player decision-making.

    This is the boundary between the engine (which orchestrates ticks)
    and the AI (which decides what each player does).
    """

    @abstractmethod
    def decide(self, obs: Observation) -> ActionOutput:
        """Given an observation, return an action.

        Called once per player per tick during Phase 2.
        Must return within TIME_BUDGET_MS (currently 5ms for rule-based,
        may be relaxed for neural inference with batching).
        """
        ...

    @abstractmethod
    def name(self) -> str:
        """Human-readable identifier for logging/debugging."""
        ...


# ─── Level 1: Rule-Based Policy (current MVP) ───

class RuleBasedPolicy(Policy):
    """Decision via perception → evaluation → max-utility.

    No learning. No training. Pure heuristic weights.
    """

    def __init__(self, team_tactic: dict):
        self.tactic = team_tactic
        self.perception = Perception()
        self.evaluator = Evaluator()

    def decide(self, obs: Observation) -> ActionOutput:
        # 1. Perception: enrich observation with computed features
        percept = self.perception.process(obs)

        # 2. Evaluation: score each possible action
        scores = {}
        for action_type in [0, 1, 2, 3, 4, 5, 6]:  # Hold..Tackle
            base   = ROLE_WEIGHTS[obs.role][action_type]
            tactic = self.evaluator.tactic_modifier(action_type, self.tactic)
            situ   = self.evaluator.situation_modifier(action_type, percept, obs)
            prob   = self.evaluator.success_probability(action_type, percept, obs)
            scores[action_type] = base * tactic * situ * prob

        # 3. Pick best, convert to ActionOutput
        best = argmax(scores)
        return self._build_action(best, percept, obs)

    def name(self) -> str:
        return "RuleBased-v1"


# ─── Level 2: Custom Policy (future, user-written code) ───

class CustomPolicy(Policy):
    """Decision via user-provided Python decide() function.

    For advanced users who want to write their own decision logic.
    Same interface, different implementation. Runs at full speed.
    """

    def __init__(self, decide_fn: callable, name_str: str = "Custom"):
        self._decide_fn = decide_fn
        self._name = name_str

    def decide(self, obs: Observation) -> ActionOutput:
        return self._decide_fn(obs)

    def name(self) -> str:
        return self._name


# ─── How the engine uses Policy ───

class MatchEngine:
    def __init__(self, home_policy: Policy, away_policy: Policy):
        self.home_policy = home_policy
        self.away_policy = away_policy

    def _phase2_decide(self, snapshot: Snapshot):
        """Phase 2: call decide() for each player."""
        for player in snapshot.all_players:
            obs = Observation.from_snapshot(snapshot, player.id)
            policy = self.home_policy if player.team == "home" else self.away_policy

            try:
                with time_budget_ms(5):
                    action = policy.decide(obs)
            except TimeoutError:
                action = ActionOutput(action_type=0)  # Hold

            player.queued_action = action
```

### Policy Architecture

```
┌───────────────────────────────────────────────────────────┐
│           Policy = Fixed Logic + Tunable Params           │
│                                                           │
│  decide(obs) = role_weight × tactic_param × situ × prob   │
│                      ↑                   ↑                │
│                  固定的权重表        用户可调 (1-10)       │
│                                                           │
│  - 决策逻辑在 1000 场测试中完全不变                        │
│  - 战术参数是唯一变量 → 对比结果才有意义                    │
│  - 改进战术 = 改参数，不改代码                              │
└───────────────────────────────────────────────────────────┘
```

```
Level 1 (MVP)                    Level 2 (Future)
┌─────────────────┐           ┌─────────────────┐
│ RuleBasedPolicy  │           │  CustomPolicy    │
│                  │           │                  │
│ fixed weights    │  user     │ user-defined     │
│ + tunable        │───writes─▶│ decide() logic   │
│ tactic params    │  code?    │ in Python        │
│                  │           │                  │
│ 开箱即用          │           │ 高级用户自定义规则 │
└─────────────────┘           └─────────────────┘

Same interface: Policy.decide(Observation) → ActionOutput
Engine never changes.
```

### Observation Space Size

| Feature Group | Dims | Count |
|--------------|------|-------|
| Ball | 5 | 5 |
| Goal | 4 | 4 |
| Nearest teammate | 3 | 3 |
| Nearest opponent | 3 | 3 |
| Spatial | 2 | 2 |
| Self attributes | 11 | 11 |
| Match context | 5 | 5 |
| History | 10 | 10 |
| Tactical context | 6 | 6 |
| **Total** | | **49** |

49-dimensional observation vector → compact enough for fast inference (batch all 22 players through the network in one forward pass).

### 7-Phase Tick Pipeline

All 7 phases read from the snapshot built at Phase 1. No phase observes side effects of later phases within the same tick.

```
┌──────────────────────────────────────────────────────────────┐
│                      Tick N (1 second)                        │
│                                                               │
│  Phase 1  BUILD SNAPSHOT                                      │
│           Freeze game_state + all player_states + histories   │
│           │                                                   │
│  Phase 2  AI DECISION (perception → evaluate → decide)       │
│           For each player, call decide(snapshot) → Action    │
│           5ms budget per decision (rule-based, rarely fails) │
│           Failure → FallbackHandler → Hold()                  │
│           │                                                   │
│  Phase 3  VALIDATE ACTIONS                                    │
│           Range checks (dx,dy in bounds, power 1-20)         │
│           Cooldown enforcement (reject Pass/Shoot/...        │
│             if player on cooldown → downgrade to Hold)       │
│           Invalid → Hold()                                    │
│           │                                                   │
│  Phase 4  PLAYER MOVEMENT                                     │
│           Apply Move/Dribble to player positions              │
│           Speed modified by stamina, physicality              │
│           Max speed ≈10 m/s (calibrated to field scale)      │
│           │                                                   │
│  Phase 5  BALL ACTIONS (Pass, Shoot, Cross)                  │
│           Resolve pass/shoot/cross via BallPhysicsSystem     │
│           Success probability → roll SeededRNG                │
│           On success: ball in flight toward target            │
│           On failure: interception chance, out of bounds      │
│           │                                                   │
│  Phase 6  TACKLE RESOLUTION                                   │
│           For each Tackle: check distance to target           │
│           Success = f(defender.tackling, attacker.dribbling,  │
│                        approach_angle, stamina)               │
│           Foul chance = f(defender.defending, desperation)    │
│           │                                                   │
│  Phase 7  BALL PHYSICS + GOAL DETECTION                       │
│           Update ball position (in-flight or loose)           │
│           Resolve nearest-player ball pickup (50/50 contests) │
│           Check ball vs goal boundaries → GOAL event          │
│           Check ball vs pitch boundaries → out of play        │
│           Deplete stamina for sprinting players               │
│           │                                                   │
│           └──▶ Generate tick events → write to events.jsonl  │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

### Action Resolution Details

**Pass Success:**
```
pass_success = f(
    passer.passing,          # attribute 0-100, weight 40%
    distance_to_target,      # inverted: longer = harder, weight 25%
    pressure_on_passer,      # nearby opponents, weight 20%
    receiver.awareness,      # positioning, weight 15%
)
```

**Shot xG:**
```
base_xg by distance:
  0-6m   → 0.40    6-12m  → 0.18
  12-18m → 0.08    18-25m → 0.03    25m+ → 0.01

modified by: angle from goal, pressure, shooter.shooting,
             goalkeeper.awareness, shot_type (volley/header/driven/placed)
```

**Tackle Success:**
```
tackle_success = f(
    defender.defending,
    attacker.dribbling,
    defender_count,       # multiple defenders = easier tackle
    approach_angle,        # front-on = better
)
foul_probability: rises with poor defending attribute and late-game desperation
```

### Cooldown System

```python
@dataclass
class Cooldown:
    duration_ticks: int = 3   # ticks before action allowed again
    remaining: int = 0

    @property
    def is_active(self) -> bool:
        return self.remaining > 0

    def tick(self):
        if self.remaining > 0:
            self.remaining -= 1

# Pass/Shoot/Cross/Dribble/Tackle → remaining = duration_ticks
# Move/Hold → never trigger, always available
```

### Determinism

```python
class SeededRNG:
    """Wraps random.Random with a fixed seed for deterministic replay."""

    def __init__(self, seed: int):
        self.rng = random.Random(seed)

    def roll(self, threshold: float) -> bool:
        return self.rng.random() < threshold

    def uniform(self, lo: float, hi: float) -> float:
        return self.rng.uniform(lo, hi)

# seed = job.seed_base + match_index
# Same seed → identical match outcome. Guaranteed.
```

### Replay Output: events.jsonl

Replay data is stored as **JSON Lines** — one JSON record per tick, one line per tick. This is streamable (no need to load the entire file) and appendable (engine writes line-by-line).

```
{"t":0,"ball":[0.50,0.50],"players":[{"id":"h1","pos":[0.50,0.50],"team":"home","stamina":100}],"events":[],"score":[0,0],"phase":"KICKOFF"}
{"t":1,"ball":[0.50,0.52],"players":[{"id":"h1","pos":[0.50,0.51],"team":"home","stamina":100},{"id":"h3","pos":[0.48,0.54],"team":"home","stamina":99}],"events":[],"score":[0,0],"phase":"BUILD_UP"}
...
{"t":342,"ball":[0.85,0.35],"players":[...],"events":[{"type":"pass","actor":"h7","target":"h9","success":true,"from":[0.70,0.40],"to":[0.82,0.35]}],"score":[0,0],"phase":"ATTACK"}
...
{"t":1207,"ball":[0.92,0.48],"players":[...],"events":[{"type":"goal","actor":"h9","xg":0.34,"assist":"h7"}],"score":[1,0],"phase":"KICKOFF"}
```

**Field reference:**

| Field | Type | Description |
|-------|------|-------------|
| `t` | int | Tick number (0–5400) |
| `ball` | [float, float] | Ball position, normalized 0.0–1.0 |
| `players` | array | All 22 players: id, position, team, stamina |
| `events` | array | Actions resolved this tick (empty array if idle) |
| `score` | [int, int] | Current score [home, away] |
| `phase` | string | Match phase (KICKOFF, BUILD_UP, ATTACK, DEFENSE, TRANSITION, SET_PIECE, FINISHED) |

**Event types:**
`pass`, `shoot`, `cross`, `dribble`, `tackle`, `intercept`, `goal`, `save`, `foul`, `offside`, `corner`, `throw_in`, `goal_kick`, `half_time`, `full_time`

---

## Agent Design

All three agents run locally. They share a common LLM client.

```
class BaseAgent:
    def __init__(self, api_key: str, model: str, provider: str)
    def run(self, prompt_template: str, input_data: dict) -> str
```

| Agent | LLM Input | LLM Output |
|-------|-----------|------------|
| **Tactics Agent** | Tactic JSON (formation, positions, params) | Strengths + weaknesses + tactical profile |
| **Analysis Agent** | Aggregated match stats from N simulations | Report: attack, defense, possession, players |
| **Optimization Agent** | Current tactic + simulation history | Modified tactic JSON + per-change explanations |

---

## Technology Stack Summary

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14, React, TypeScript, TailwindCSS, React Flow, Zustand, Recharts |
| Backend | FastAPI, Python 3.13, SQLAlchemy 2.0, Alembic, PostgreSQL 14 |
| Realtime | Ably (pub/sub) |
| Engine | Python 3.13, rule-based AI, multiprocessing |
| Agent | Python 3.13, LLM SDK (Anthropic / OpenAI) |
| Auth | JWT (backend), API token (engine→backend) |
