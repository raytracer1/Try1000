"""Engine-wide constants and configuration."""

# ─── Pitch Dimensions (meters) ───
PITCH_LENGTH = 100.0          # AgentPitch field coords
PITCH_WIDTH = 60.0            # AgentPitch field coords
GOAL_WIDTH = 7.32             # 8 yards
GOAL_DEPTH = 2.44             # 8 feet
PENALTY_AREA_LENGTH = 16.5    # 18 yards
PENALTY_AREA_WIDTH = 40.32    # 44 yards
GOAL_AREA_LENGTH = 5.5        # 6 yards
GOAL_AREA_WIDTH = 18.32       # 20 yards
CENTER_CIRCLE_RADIUS = 9.15   # 10 yards
PENALTY_SPOT_DISTANCE = 11.0  # 12 yards

# ─── Time ───
TICK_DURATION = 0.1           # seconds per tick (AgentPitch tick_rate=10)
MAX_TICKS = 3000              # 5 minutes * 60 sec * 10 tick/sec
HALF_TIME_TICK = 1500         # 2.5 minutes
EXTRA_TIME_TICKS_PER_HALF = 3000  # 5 minutes max per half
FAST_MODE_TICK_MULTIPLIER = 5 # fast mode: 0.5s per tick → still 10x faster

# ─── Player Physics ───
MAX_PLAYER_SPEED = 3.5        # m/tick (pace=100,speed=1.0 → 1.0*3.5*0.5=1.75m/tick=17.5m/s)
JOG_SPEED = 1.5               # m/tick
WALK_SPEED = 0.5              # m/tick
PLAYER_RADIUS = 0.5           # collision radius (meters)
BALL_CONTROL_RADIUS = 1.5     # AgentPitch: 1.5 field units

# ─── Ball Physics ───
BALL_MAX_SPEED = 3.5          # m/tick (power=20 → 3.5m/tick=35m/s; matches AgentPitch)
BALL_FRICTION = 0.998         # velocity decay per tick when rolling (0.1s tick)
BALL_AIR_FRICTION = 0.999     # velocity decay per tick when in air
BALL_RADIUS = 0.11            # size 5 ball radius in meters

# ─── Stamina ───
STAMINA_MAX = 100.0
STAMINA_MIN = 30.0
STAMINA_BASE_DECAY = 0.002    # per 0.1s tick (was 0.02 at 1s tick)
STAMINA_JOG_DECAY = 0.005
STAMINA_SPRINT_DECAY = 0.012
STAMINA_STAND_RECOVERY = 0.003
STAMINA_JOG_RECOVERY = 0.001
STAMINA_LOW_THRESHOLD = 50.0
STAMINA_CRITICAL_THRESHOLD = 35.0

# ─── AI ───
DECISION_TIME_BUDGET_MS = 2   # max ms per player per tick (stricter at 10 tick/s)
COOLDOWN_DURATION_TICKS = 10  # AgentPitch: action_cooldown_ticks (1s at 10tick/s)
CIRCUIT_BREAKER_LIMIT = 100   # consecutive failures → Hold
PERCEPTION_TEAMMATE_RADIUS = 30.0
PERCEPTION_OPPONENT_RADIUS = 25.0
PRESSURE_RADIUS = 5.0

# ─── Match ───
MAX_EVENTS_PER_TICK = 50
REPLAY_SAMPLE_RATE = 10       # record every 10th tick (1/s instead of 10/s)
GOAL_RESET_TICKS = 50         # pause 5s after a goal (50 ticks at 10tick/s)
HALF_TIME_PAUSE_TICKS = 50    # pause 5s at half-time

# ─── Normalized Coordinates ───
# Internal representation uses meters (0,0 at center circle)
# Replay output uses normalized 0-1 (0,0 at top-left)
def meters_to_normalized(x: float, y: float) -> tuple[float, float]:
    """Convert engine coords (center 0,0) → normalized 0-1 for frontend replay."""
    return ((x + 50.0) / 100.0, (y + 30.0) / 60.0)

def normalized_to_meters(nx: float, ny: float) -> tuple[float, float]:
    """Convert normalized 0-1 → engine coords (center 0,0)."""
    return (nx * 100.0 - 50.0, ny * 60.0 - 30.0)

def meters_to_field(x: float, y: float) -> tuple[float, float]:
    """Convert engine coords (center 0,0) → AgentPitch field coords (origin 0,0)."""
    return (x + 50.0, y + 30.0)

def field_to_meters(fx: float, fy: float) -> tuple[float, float]:
    """Convert AgentPitch field coords (origin 0,0) → engine coords (center 0,0)."""
    return (fx - 50.0, fy - 30.0)
