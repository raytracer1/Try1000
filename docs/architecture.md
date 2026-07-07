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

## Engine Design

### Tick Loop

```
1 tick = 1 second of match time
5400 ticks = 90 minutes

Per tick:
  1. Update ball physics (position, velocity, friction)
  2. Update player positions (move toward targets, speed by stamina)
  3. For each player: AI decision (perception → evaluate → act)
  4. Resolve actions (pass, shoot, tackle, etc.)
  5. Check events (goal, foul, out of bounds)
  6. Update stamina, possession, score
  7. Record tick state (if replay mode)
```

### AI Decision Pipeline

```
For each player, every tick:
  1. PERCEPTION  — what can this player see?
     → nearby teammates, opponents, ball, goal, space

  2. EVALUATION  — score each available action
     → role weights × tactical params × situation × success probability

  3. DECISION    — pick highest-utility action

  4. EXECUTION   — roll against success probability
     → success → apply effect
     → failure → turnover, interception, out of bounds
```

### Determinism

```python
class SeededRNG:
    def __init__(self, seed: int):
        self.rng = random.Random(seed)

# seed = job.seed_base + match_index
# Same seed → same match outcome. Guaranteed.
```

### Replay Output

```json
{
  "match_id": "...",
  "ticks": [
    {
      "t": 0,
      "ball": [0.5, 0.5],
      "players": [{"id": "p1", "pos": [0.3, 0.5], "stamina": 100}],
      "events": [{"type": "pass", "actor": "p1", "target": "p3"}],
      "score": [0, 0],
      "possession": "home"
    }
  ]
}
```

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
