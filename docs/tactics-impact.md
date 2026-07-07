# How Tactics Shape the Game

Each tactical parameter changes the **evaluation weights** inside `decide()`. This ripples through player behavior → match events → final statistics. Here's the full causal chain for each parameter.

---

## 1. Pressing Level (1–10)

Controls how aggressively the team tries to win the ball back after losing possession.

### What changes in `decide()`

```python
# Tackle weight multiplier
tackle_multiplier = 0.5 + (pressing / 10) * 1.0   # 0.55 → 1.5

# Interception radius bonus
interception_radius = 3.0 + (pressing / 10) * 5.0  # 3.5m → 8.0m

# Defensive line position (yards from own goal)
defensive_line_offset = 30 + (pressing / 10) * 25  # 33y → 55y

# Pressure willingness threshold
pressure_trigger_distance = 5 + (pressing / 10) * 15  # 6.5m → 20m
```

### Behavior changes

| Pressing | Player Behavior |
|----------|----------------|
| **1** (sit back) | Defenders stay deep in own half. Tackle attempts only inside own 30m. Interception radius 3.5m — only intercepts balls very close by. Strikers walk back after losing the ball. |
| **5** (balanced) | Midfield press. Tackle in middle third. Defensive line ~43y from goal. Moderate interception radius 5.5m. |
| **10** (gegenpress) | Full pitch press. Tackle attempts start from opponent's box. Defensive line at 55y (almost halfway). Interception radius 8m — defenders step up to cut passing lanes. Strikers immediately chase the ball after loss. |

### Match statistical impact

```
Pressing 1:
  Possession:    42%  (conservative, let opponent have it in their half)
  Ball Recovery: 12   (only recover in dangerous zones, near own box)
  Tackles:       8    (wait for opponent to come)
  Fouls:         3    (standing tackles, low risk)
  Opponent pass accuracy: 87% (no pressure → easy)

Pressing 5:
  Possession:    50%
  Ball Recovery: 22
  Tackles:       15
  Fouls:         8

Pressing 10:
  Possession:    56%  (force turnovers in opponent half)
  Ball Recovery: 35   (lots in opponent half)
  Tackles:       28   (aggressive, many attempts)
  Fouls:         14   (more desperate tackles)
  Opponent pass accuracy: 78% (constant pressure → rushed passes)
```

### Trade-off

| Gain | Lose |
|------|------|
| More possession | More fouls (set pieces against) |
| More ball recoveries high up | Defenders tired late game (stamina drain) |
| Opponent passing suffers | Space behind defense if press is bypassed |

---

## 2. Defensive Line (1–10)

Controls how high the back line positions itself. Works together with pressing.

### What changes in `decide()`

```python
# Base Y position of defenders in own half
defender_y_offset = 15 + (defensive_line / 10) * 30  # 18y → 45y from own goal

# Offside trap willingness
offside_trap_prob = (defensive_line / 10) * 0.4      # 0.04 → 0.4

# Recovery urgency after losing possession
recovery_speed_mult = 1.0 + (defensive_line / 10) * 0.5  # 1.05 → 1.5
```

### Behavior changes

| Defensive Line | Player Behavior |
|---------------|----------------|
| **1** (deep block) | CBs on the edge of their own box (18y). Defenders retreat first, engage second. Almost never step up for offside. Safe, but invites pressure. |
| **5** (mid block) | CBs around 30y. Balanced retreat vs step up. Occasional offside trap. |
| **10** (suicidal high) | CBs at 45y — near the halfway line. Aggressively step up. Frequent offside trap attempts. Recovery sprints with 1.5x speed. |

### Match statistical impact

```
Defensive Line 1:
  Offsides against:          1
  Through balls completed:   2   (opponent can't find space behind)
  Goals conceded from crosses: 8 (invites crosses, box is crowded)
  Opponent xG per shot:      0.08 (deep defense blocks most quality chances)

Defensive Line 5:
  Offsides against:          4
  Through balls completed:   7
  Goals conceded from crosses: 5
  Opponent xG per shot:      0.11

Defensive Line 10:
  Offsides against:          9   (effective trap)
  Through balls completed:   14  (one pass over the top = breakaway)
  Goals conceded from crosses: 3 (defend before cross happens)
  Opponent xG per shot:      0.22 (when beat, it's a 1v1 with keeper → high xG)
```

### Trade-off

| Gain | Lose |
|------|------|
| Compact shape → hard to play through | Step wrong once → striker 1v1 with keeper |
| More offsides | GK less protected |
| Crosses prevented early | Pace in behind is lethal |

### Interaction with Pressing

| Pressing | + Defensive Line | Combined Effect |
|----------|-----------------|-----------------|
| High (8) | High (8) | Coherent gegenpress. Press and line move together. Compact from front to back. |
| High (8) | Low (2) | **Disaster.** Midfield presses high, defense sits deep. 30m gap between lines. Opponent plays through easily. |
| Low (2) | Low (3) | Park the bus. Everyone behind the ball. Hard to break down but offers zero counter-attack threat. |

---

## 3. Attacking Width (1–10)

Controls how wide the team spreads when in possession.

### What changes in `decide()`

```python
# Winger/base wide player X position offset
winger_width = 0.3 + (width / 10) * 0.25   # 0.33 → 0.55 (normalized pitch coords)

# Fullback overlap willingness
overlap_prob = (width / 10) * 0.5            # 0.05 → 0.5

# Cross tendency multiplier
cross_multiplier = 0.6 + (width / 10) * 0.8  # 0.68 → 1.4

# Through-ball tendency (inverse of width)
through_ball_mult = 1.4 - (width / 10) * 0.8 # 1.32 → 0.6
```

### Behavior changes

| Width | Player Behavior |
|-------|----------------|
| **1** (narrow) | Wingers tuck inside (0.33 from center). Fullbacks stay home. Through balls through the middle. Everything goes centrally. |
| **5** (balanced) | Wingers stay at 0.43. Fullbacks overlap occasionally. Mix of crosses and through balls. |
| **10** (stretch) | Wingers hug the touchline (0.55). Fullbacks constantly overlap. Cross-heavy. Stretch the opponent across the full pitch width. |

### Match statistical impact

```
Width 1 (narrow):
  Crosses:            4
  Through balls:      18
  Shots from center:  14 (most quality chances are central → high xG)
  Pass accuracy:      89% (short passes, central overloads)

Width 5:
  Crosses:            12
  Through balls:      10
  Shots from center:  8
  Pass accuracy:      84%

Width 10 (wide):
  Crosses:            28
  Through balls:      3
  Shots from center:  4
  Pass accuracy:      78% (longer passes to flanks, more turnovers)
```

### Trade-off

| Gain | Lose |
|------|------|
| Stretch opponent → gaps appear | Less compact → harder to press after losing ball |
| Crosses into the box | Crosses are low-probability chances (~5% conversion) |
| Wingers in 1v1 situations | Midfield outnumbered if wingers stay wide |

---

## 4. Passing Style (short / mixed / direct)

Controls the preferred pass distance and risk profile.

### What changes in `decide()`

```python
# Preferred pass distance (meters)
if style == "short":  preferred_distance = 5-15
if style == "mixed":  preferred_distance = 10-25
if style == "direct": preferred_distance = 20-40

# Pass safety bias
if style == "short":  safety_bias = 1.5  # strongly favors safe passes
if style == "mixed":  safety_bias = 1.0
if style == "direct": safety_bias = 0.6  # willing to attempt risky long balls

# Hold-and-wait patience
if style == "short":  hold_patience = 1.3  # wait for short options to open
if style == "direct": hold_patience = 0.5  # launch it forward quickly
```

### Behavior changes

| Style | Player Behavior |
|-------|----------------|
| **Short** | CB → CM → CAM triangles. Players wait for nearby options. If pressured, keeper distributes short to fullbacks. Never hoof it. |
| **Mixed** | Mix of short build-up and longer switches of play. CDM occasionally launches diagonal balls. |
| **Direct** | CBs bypass midfield → long balls to striker. GK kicks long. Wingers make runs behind, not to feet. |

### Match statistical impact

```
Short passing:
  Pass accuracy:         91%
  Long balls (>30m):     3
  Possession:            62% (keep ball, recycle)
  Turnovers in own half: 2  (safe = few giveaways in danger zone)
  Chance creation speed: low (patient build-up)
  Goals from set pieces: 3  (many passes in final third = more corners)

Mixed:
  Pass accuracy:         84%
  Long balls:            14
  Possession:            50%
  Turnovers in own half: 6

Direct:
  Pass accuracy:         72%
  Long balls:            42
  Possession:            41% (willing to give up ball for territory)
  Turnovers in own half: 14 (risky passes from deep)
  Chance creation speed: high (1-2 passes = shot)
  Goals from counter-attacks: high
```

### Trade-off

| Gain | Lose |
|------|------|
| Short: high possession, control | Can be sterile — lots of passes, no shots |
| Short: safe from turnovers | Vulnerable to high press |
| Direct: bypass opponent midfield | Give away possession cheaply |
| Direct: quick goals | Fewer touches for creative players |

---

## 5. Build-Up Style (slow / balanced / fast)

Controls transition speed from defense to attack after winning the ball.

### What changes in `decide()`

```python
if build_up == "slow":
    forward_run_prob = 0.2      # rarely sprint forward
    hold_position_weight = 1.5  # stand and wait for options
    pass_urgency = 0.6          # take time on the ball

if build_up == "balanced":
    forward_run_prob = 0.5
    hold_position_weight = 1.0
    pass_urgency = 1.0

if build_up == "fast":
    forward_run_prob = 0.9      # immediately sprint forward
    hold_position_weight = 0.3  # don't wait
    pass_urgency = 1.8          # release the ball instantly
```

### Behavior changes

| Style | Player Behavior |
|-------|----------------|
| **Slow** | After winning the ball: CB passes to GK, reset. CDM drops deep. Build from the back with patience. No rushed decisions. |
| **Balanced** | Win ball → look up → if forward option exists, go. If not, recycle. |
| **Fast** | Win ball → immediately launch forward. Wingers sprint upfield. Direct pass to striker. Counter-attack at every opportunity. |

### Match statistical impact

```
Slow build-up:
  Avg counter-attack duration: 18s (slow, methodical)
  Shots from counter:          3
  possession_after_winning:    75% (keep ball after recovery)

Balanced:
  Avg counter-attack duration: 10s
  Shots from counter:          8

Fast build-up:
  Avg counter-attack duration: 4s  (vertical, direct)
  Shots from counter:          16  (lots of transitional chances)
  possession_after_winning:    45% (quick shot or quick turnover)
```

### Trade-off

| Gain | Lose |
|------|------|
| Slow: control game rhythm | Opponent has time to recover defensive shape |
| Fast: high-quality counter chances | More turnovers (low-percentage passes) |
| Fast: punishes high-pressing opponents | Exhausts wingers and strikers |

---

## 6. Tempo (1–10)

Controls the urgency of decision-making in possession. Different from build-up style — tempo applies during sustained possession, not just transitions.

### What changes in `decide()`

```python
# Decision speed (how quickly to act)
hold_time_reduction = 0.5 + (tempo / 10) * 0.8  # 0.55 → 1.3x faster

# Risk tolerance in possession
risk_bonus = tempo / 10                          # 0.1 → 1.0

# One-touch pass probability
one_touch_prob = (tempo / 10) * 0.6              # 0.06 → 0.6

# Dribble tendency (take on defender)
dribble_mult = 0.6 + (tempo / 10) * 0.8          # 0.68 → 1.4
```

### Behavior changes

| Tempo | Player Behavior |
|-------|----------------|
| **1** (patient) | Take multiple touches. Wait for the perfect pass. Low dribble attempts. Safe, slow circulation. |
| **5** (balanced) | 2-3 touch passing. Occasional one-touch. Moderate dribbling. |
| **10** (frantic) | One-touch passing whenever possible. Quick combinations. Dribble at every 1v1. Take risks. |

### Match statistical impact

```
Tempo 1:
  Passes per minute:       8   (slow circulation)
  One-touch passes:        3%
  Dribbles:                4
  Shots:                   8  (wait for perfect chance)
  Shots on target ratio:   62% (only shoot when high probability)

Tempo 5:
  Passes per minute:       14
  One-touch passes:        18%
  Dribbles:                12
  Shots:                   14
  Shots on target ratio:   44%

Tempo 10:
  Passes per minute:       22  (rapid circulation)
  One-touch passes:        42%
  Dribbles:                28  (take on defenders constantly)
  Shots:                   22  (shoot on sight)
  Shots on target ratio:   28% (many low-percentage shots)
```

### Interaction with Passing Style

| Passing | + Tempo | Result |
|---------|---------|--------|
| Short | High (9) | Tiki-taka. Quick short passes, constant movement. Beautiful when it works. |
| Short | Low (2) | Possession for possession's sake. Safe but creates nothing. |
| Direct | High (9) | Chaos. Fast long balls + risky decisions. High variance. |
| Direct | Low (2) | Route one. Launch it to the target man, build from there. |

---

## 7. Formation

Formation sets the **spatial template** — where each player stands in each phase.

### What changes in `decide()`

```python
# Base positions (from formation template)
base_positions = {
    "4-3-3": {
        "GK":  (0.50, 0.05),   # center, near own goal
        "CB1": (0.30, 0.15),   # left center-back
        "CB2": (0.70, 0.15),   # right center-back
        "LB":  (0.15, 0.20),   # left fullback
        "RB":  (0.85, 0.20),   # right fullback
        "CDM": (0.50, 0.30),
        "CM1": (0.35, 0.40),
        "CM2": (0.65, 0.40),
        "LW":  (0.15, 0.55),
        "RW":  (0.85, 0.55),
        "ST":  (0.50, 0.65),
    },
    "4-4-2": { ... },
    "3-5-2": { ... },
    "4-2-3-1": { ... },
}

# Each player uses base_position as the anchor for their movement
# In defense: return toward base_position
# In attack: move from base_position based on role and space
```

### Formation-specific effects (examples)

| Formation | Spatial Characteristic | Match Effect |
|-----------|----------------------|--------------|
| **4-3-3** | 3 in midfield, wingers high | Wings overloaded in attack. Midfield triangle controls center. Vulnerable: space between FB and CB if wingers don't track back. |
| **4-4-2** | Two banks of 4 | Compact and organized. Two strikers press together. Vulnerable: outnumbered 2v3 in midfield vs 4-3-3. |
| **3-5-2** | 3 CBs, wingbacks provide width | Dominates central areas. Wingbacks are the only width providers → massive stamina drain. Vulnerable: 2v1 on flanks if wingback caught upfield. |
| **4-2-3-1** | Double pivot, #10 behind striker | Solid base (2 CDMs) + creative #10. Flexible in attack (3 behind striker interchange). Vulnerable: gap between double pivot and #10 if pressed. |

### Formation vs Formation (rock-paper-scissors)

```
4-3-3 vs 4-4-2  → 4-3-3 wins midfield (3v2), controls possession
4-4-2 vs 4-3-3  → 4-4-2 counters well (2 strikers vs 2 CBs)
3-5-2 vs 4-3-3  → 3-5-2 wins middle (3 CBs + 3 CMs), wingbacks push back wingers
4-2-3-1 vs 4-3-3 → 4-2-3-1's #10 finds space between 4-3-3's midfield and defense
```

---

## 8. Putting It All Together: Tactical Profiles

### Example 1: Klopp-style Gegenpress

```
Formation:        4-3-3
Pressing:         9    (full pitch, relentless)
Defensive Line:   8    (high line to compress space)
Attacking Width:  7    (winger stretch + overlapping fullbacks)
Passing:          mixed
Build-up:         8    (fast transitions, counter-pressing)
Tempo:            8    (quick decisions)
```

**Expected match stats (100-game sim):**
```
Possession:     54%
Win Rate:       62%
Goals For:      2.2/game
Goals Against:  1.1/game
xG For:         2.0/game
xG Against:     1.0/game
Shots:          16/game
Recoveries:     38/game (15 in opponent half)
Fouls:          14/game
Offsides:       6/game
```

**Strengths:** Suffocates opponent. Wins ball high. Creates from turnovers.
**Weaknesses:** Space behind fullbacks. Tired legs after 70'. Vulnerable to direct counters.

### Example 2: Mourinho-style Low Block

```
Formation:        4-4-2 (or 4-2-3-1)
Pressing:         2    (only press in own third)
Defensive Line:   2    (sit deep, protect the box)
Attacking Width:  6    (moderate width on counter)
Passing:          direct
Build-up:         9    (fast, vertical on turnover)
Tempo:            4    (patient in defense, quick on counter)
```

**Expected match stats (100-game sim):**
```
Possession:     38%
Win Rate:       48%
Goals For:      1.4/game
Goals Against:  0.8/game
xG For:         1.2/game
xG Against:     1.4/game (concede chances but defend the box well)
Shots:          8/game (few but high-quality counter shots)
Recoveries:     18/game (mostly in own third)
Fouls:          6/game (disciplined, stay on feet)
Offsides:       1/game
```

**Strengths:** Hard to break down. Clinical on the counter. Disciplined.
**Weaknesses:** Concedes possession. Few chances created. Opponent xG is high — needs a good GK.

### Example 3: Guardiola-style Possession

```
Formation:        4-3-3
Pressing:         8    (counter-press after losing ball)
Defensive Line:   7    (high line, compress space)
Attacking Width:  9    (maximum width to stretch opponent)
Passing:          short
Build-up:         3    (patient, build from the back)
Tempo:            7    (quick short passes, not slow circulation)
```

**Expected match stats (100-game sim):**
```
Possession:     65%
Win Rate:       68%
Goals For:      2.5/game
Goals Against:  0.9/game
xG For:         2.3/game
xG Against:     0.7/game
Shots:          18/game
Pass Accuracy:  91%
Passes/game:    680
```

**Strengths:** Dominates the ball. Creates constant pressure. Quality chances.
**Weaknesses:** Requires technically elite players. Vulnerable to the rare counter. One mistake at the back is fatal.

---

## 9. Design Principle: Everything Flows from Weights

The key insight is that all tactical differences emerge from **multiplying numbers**:

```
final_weight = role_base × tactic_modifier × situation_modifier × success_probability
```

There's no hardcoded "if pressing = 7 then do X". Instead:

1. Tactical parameters **shift the weights** in the evaluator
2. Different scores → different action choices
3. Different action choices → different match events
4. Aggregated events → different statistics

This means the engine can simulate tactics it was never explicitly programmed for — any combination of parameters produces emergent behavior through the weight system. The same 4-factor formula handles park-the-bus, tiki-taka, and gegenpress without special-case code.
