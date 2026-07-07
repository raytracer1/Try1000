"""Engine-wide constants and configuration."""

# ─── Pitch Dimensions (meters) ───
PITCH_LENGTH = 105.0          # touchline to touchline
PITCH_WIDTH = 68.0            # goal line to goal line
GOAL_WIDTH = 7.32             # 8 yards
GOAL_DEPTH = 2.44             # 8 feet
PENALTY_AREA_LENGTH = 16.5    # 18 yards
PENALTY_AREA_WIDTH = 40.32    # 44 yards
GOAL_AREA_LENGTH = 5.5        # 6 yards
GOAL_AREA_WIDTH = 18.32       # 20 yards
CENTER_CIRCLE_RADIUS = 9.15   # 10 yards
PENALTY_SPOT_DISTANCE = 11.0  # 12 yards

# ─── Time ───
TICK_DURATION = 1.0           # seconds per tick
MAX_TICKS = 5400              # 90 minutes * 60 seconds
HALF_TIME_TICK = 2700         # 45 minutes
EXTRA_TIME_TICKS_PER_HALF = 300  # 5 minutes max per half
FAST_MODE_TICK_MULTIPLIER = 5 # fast mode: 5s per tick → 1080 ticks per match

# ─── Player Physics ───
MAX_PLAYER_SPEED = 10.0       # m/s (~36 km/h, elite sprint)
JOG_SPEED = 4.0               # m/s
WALK_SPEED = 1.5              # m/s
PLAYER_RADIUS = 0.5           # collision radius (meters)
BALL_CONTROL_RADIUS = 5.0     # max distance to control ball (generous for tactical sim)

# ─── Ball Physics ───
BALL_MAX_SPEED = 35.0         # m/s (~126 km/h, powerful shot)
BALL_FRICTION = 0.98          # velocity decay per tick when rolling
BALL_AIR_FRICTION = 0.995     # velocity decay per tick when in air
BALL_RADIUS = 0.11            # size 5 ball radius in meters

# ─── Stamina ───
STAMINA_MAX = 100.0
STAMINA_MIN = 30.0            # can't drop below 30% (walking pace)
STAMINA_BASE_DECAY = 0.02     # per tick at walking speed
STAMINA_JOG_DECAY = 0.05      # per tick at jogging speed
STAMINA_SPRINT_DECAY = 0.12   # per tick at sprint speed
STAMINA_STAND_RECOVERY = 0.03 # per tick when standing/walking
STAMINA_JOG_RECOVERY = 0.01   # per tick when jogging
STAMINA_LOW_THRESHOLD = 50.0  # below this, speed starts dropping
STAMINA_CRITICAL_THRESHOLD = 35.0

# ─── AI ───
DECISION_TIME_BUDGET_MS = 5   # max ms per player per tick
COOLDOWN_DURATION_TICKS = 3   # ticks before Pass/Shoot/Tackle allowed again
CIRCUIT_BREAKER_LIMIT = 10    # consecutive failures → Hold for rest of match
PERCEPTION_TEAMMATE_RADIUS = 30.0   # meters
PERCEPTION_OPPONENT_RADIUS = 25.0   # meters
PRESSURE_RADIUS = 5.0         # meters — "under pressure" threshold

# ─── Match ───
MAX_EVENTS_PER_TICK = 50      # safety cap
REPLAY_SAMPLE_RATE = 1        # record every tick (1 = all, 2 = every other)

# ─── Normalized Coordinates ───
# Internal representation uses meters (0,0 at center circle)
# Replay output uses normalized 0-1 (0,0 at top-left)
def meters_to_normalized(x_m: float, y_m: float) -> tuple[float, float]:
    """Convert meter coordinates to normalized 0-1 for replay."""
    nx = (x_m + PITCH_LENGTH / 2) / PITCH_LENGTH
    ny = (y_m + PITCH_WIDTH / 2) / PITCH_WIDTH
    return (nx, ny)

def normalized_to_meters(nx: float, ny: float) -> tuple[float, float]:
    """Convert normalized 0-1 coordinates to meters."""
    x_m = nx * PITCH_LENGTH - PITCH_LENGTH / 2
    y_m = ny * PITCH_WIDTH - PITCH_WIDTH / 2
    return (x_m, y_m)
