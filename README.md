# Try1000

> AI-powered football tactics simulation — 1,000 matches to master the beautiful game.

## Inspiration

The 2026 World Cup has come and gone. Cristiano Ronaldo, Luka Modrić, Neymar, Harry Kane — some of the greatest players of our generation — walked off the pitch without the trophy they deserved. For many of them, this was almost certainly their last World Cup.

Part of the blame falls on tactics. Talented squads underperformed because their coaches couldn't find the right system, the right formation, the right approach against specific opponents. Tactical decisions that take seconds on the sideline echo for four years. And for these legends, there won't be another four years.

I built Try1000 so this story doesn't keep repeating itself. By simulating football matches as realistically as possible — real physics, full FIFA rules, AI-driven player decisions — coaches can test thousands of tactical variations before stepping onto the pitch. What formation works best against a high press? Should the fullbacks overlap or stay deep? Which player pairing produces the most goals per 90 minutes? Run 1,000 matches and the data gives you answers, not guesses.

The name "Try1000" is both the method and the mission: try 1,000 times in simulation, so you only need to get it right once in real life.

## What it does

Try1000 is a full-stack football simulation platform with three layers:

**🎮 Simulation Engine (Python)**
- Tick-based match simulation at 10 ticks/second, 7-phase resolution per tick
- Real physics: ball trajectory, player movement, dribble contests, tackle resolution
- Full FIFA Laws: offside, fouls, yellow/red cards, penalties, throw-ins, corners, goal kicks
- Stamina system with health drain and half-time recovery
- 11v11 matches with customizable formations (4-3-3, 4-4-2, 3-5-2, etc.)
- Deterministic random seed for reproducible results

**🧠 AI Strategy Layer**
- Each player runs their own `decide()` callback — Python, JavaScript, or Rust
- LLM-generated strategies via Claude, GPT, or Gemini
- Strategies evolve between matches through post-match analysis
- Sandboxed execution with circuit breakers and fallback handlers
- Baseline hand-written strategies for validation and benchmarking

**🖥️ Web Interface (Next.js + React)**
- Real-time 2D match visualization with player numbers and ball tracking
- Pass lines, shot trajectories, and event highlights
- Strategy editor and match replay viewer
- Tournament and league management

## How we built it

The simulation core is a custom-built Action Resolution Engine designed for performance and hackability:

- **7-phase tick loop**: Snapshot → Decide → Validate → Move → Ball Action → Tackle → Physics
- **Ball Physics System (BPS)**: constant-velocity model with landing-zone overshoot detection, ball control contests, and shot deflection
- **Player Movement System (PMS)**: movement formula with formation snap (soft drift toward tactical anchor)
- **Formation & Role System (FRS)**: dynamic phase-aware anchors that shift between attacking/transitioning/defending phases
- **MatchEngine**: orchestrates kickoff, half-time, goal restarts, and full match lifecycle
- **Coordinate bridge**: engine uses real-world meters internally, converts to field coords [0,100]×[0,60] at the simulation boundary

The frontend is a Next.js app with a Zustand state store, rendering matches on an SVG pitch with real-time event streaming.

## Challenges we ran into

**Getting the physics exactly right**: Building a realistic football simulation from scratch is hard. The most elusive bug was a missing pass landing zone persistence — the ball's destination was lost between simulation ticks, causing it to fly straight to the boundary instead of stopping at the target. One line of code was causing 10× more out-of-bounds events. Weeks of debugging to find it, one line to fix it.

**Cooldown system disconnect**: The action cooldown system read from a dictionary that was never populated, while cooldown recordings went to a completely different object. The ARE's safety net was silently broken, and the baseline strategy was unknowingly enforcing cooldown at the application layer instead.

**AI strategy reliability**: LLM-generated strategies can produce invalid code, infinite loops, or nonsensical actions. We built a multi-layer safety system — sandbox timeouts, circuit breakers, action validation, and fallback handlers — to ensure matches always complete regardless of strategy quality.

**Deterministic randomness**: We needed every match to be reproducible (same seed = same result) for fair strategy comparison, while still feeling random and organic. The solution was a SHA-256-based hash function (`hash_01`) with seed/tick/player/context inputs.

**Real-time visualization performance**: Rendering 22 players, ball physics, event highlights, and pass lines at 60fps required careful SVG optimization and efficient state management.

## Accomplishments that we're proud of

- **Realistic match simulation**: The non-AI simulation produces authentic match statistics — realistic out-of-bounds rates, pass counts, shot frequencies, and goal totals across 5-minute matches

- **Zero-downtime strategy evolution**: AI strategies improve across matches without human intervention, running entirely in sandboxed environments

- **Full FIFA Law implementation**: Offside detection, foul severity rolls, card accumulation, penalty shootouts, and all restart types (throw-in, corner, goal kick, free kick)

- **Multi-language sandbox**: Strategies can be written in Python, JavaScript, or Rust (compiled to WASM), all executing safely in per-match sandboxes

- **Clean architecture**: Clear separation between physics (stateless pure functions), state management (MatchState/GSM), and orchestration (MatchEngine), making the codebase easy to extend

## What we learned

- **Football is surprisingly deep to simulate**: Getting even basic things right — when should a player shoot vs pass? How does formation shape affect passing lanes? — requires hundreds of tuning iterations

- **AI agents need guardrails**: LLMs are creative but unpredictable. The combination of sandbox execution, action validation, and fallback handlers is essential for production reliability

- **Deterministic testing is gold**: Being able to replay any match bit-for-bit made debugging physics bugs infinitely faster than trying to reproduce random events

- **Coordinate systems are a trap**: Maintaining two coordinate systems (engine meters and simulation field coords) created subtle bugs that only surfaced under specific conditions. In hindsight, using a single coordinate system would have been simpler

- **The gap between "looks right" and "is right"**: The simulation passed smoke tests for weeks before we discovered the pass landing zone bug. Visual inspection isn't enough — you need statistical comparison against a reference implementation

## What's next for Try1000

- **2D → 3D, more realistic simulation**: Upgrade from the current 2D pitch model to a full 3D physics engine. Add player height, body orientation, first-touch control, aerial duels, and ball spin. The closer the simulation gets to real football physics, the more trustworthy the tactical insights become.

- **Per-player behavioral models**: Train a small model for each real-world player using match video data. Every footballer has unique instincts — De Bruyne sees passing lanes others don't, Mbappé times his runs differently from anyone else. Capturing these individual decision patterns means the simulation doesn't just model "a striker", it models *your* striker.

- **Real-time in-match intelligence**: Currently Try1000 runs pre-match simulations to test tactics beforehand. The next step is live — stream match data during a game, run thousands of parallel simulations against the current scoreline and opponent behavior, and surface real-time recommendations to the coaching staff: when to substitute, which tactical adjustment to make, what the opponent is likely to do next. Turn the sideline into a data-driven command center.
