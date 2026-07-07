# Frontend Detailed Design

---

## 1. Tactics Editor（战术编辑）

### 1.1 Component Tree

```
TacticsEditorPage
├── TacticsToolbar                          # 顶部工具栏
│   ├── TacticNameInput                     # 战术名称 (可编辑)
│   ├── FormationSelector                   # 阵型下拉 (4-3-3, 4-4-2, ...)
│   ├── SaveButton                          # 保存 (disabled when !isDirty)
│   └── AgentAnalyzeButton                  # "AI 分析此战术"
│
├── TacticsWorkspace                        # 主体区域 (flex row)
│   ├── PitchEditor                         # 左侧: 球场 + 球员
│   │   ├── PitchSVG                        # SVG 球场 (线条、禁区、中圈)
│   │   └── PlayerNode[]                    # React Flow 节点 (可拖拽)
│   │       ├── PlayerDot                   # 圆形 + 号码 + 队徽色
│   │       └── RoleBadge                   # 悬浮标签: "CB", "ST", ...
│   │
│   └── TacticsSidebar                      # 右侧面板 (320px)
│       ├── PlayerDetailPanel               # 点击球员后显示
│       │   ├── PlayerSelector              # 下拉选球员绑定到此位置
│       │   ├── RoleSelector                # 下拉选角色
│       │   └── PlayerAttributes            # 只读属性条 (pace, shooting, ...)
│       │
│       ├── TacticalParamsSection           # 战术参数区
│       │   ├── Slider: PressingLevel       # 1-10, 实时预览压迫高度
│       │   ├── Slider: DefensiveLine       # 1-10, 实时预览防线位置
│       │   ├── Slider: AttackingWidth      # 1-10
│       │   ├── Select: PassingStyle        # short | mixed | direct
│       │   ├── Select: BuildUpStyle        # slow | balanced | fast
│       │   └── Slider: Tempo               # 1-10
│       │
│       └── FormationPresets                # 快捷预设
│           ├── PresetCard: "Gegenpress"
│           ├── PresetCard: "Tiki-Taka"
│           ├── PresetCard: "Park the Bus"
│           └── PresetCard: "Counter Attack"
│
└── AgentAnalysisModal                      # 模态框: AI 分析结果
    ├── AgentLoadingState                   # skeleton + pulsating
    ├── StrengthsList                       # 优势列表
    ├── WeaknessesList                      # 劣势列表
    └── TacticalLabel                       # "高位压迫控球型"
```

### 1.2 Data Flow

```
                    tacticsStore (Zustand)
                    ┌────────────────────────┐
                    │ currentTactic           │
                    │   formation: "4-3-3"    │
                    │   playerPositions: {...}│
                    │   pressingLevel: 7      │
                    │   defensiveLine: 6      │
                    │   ...                   │
                    │ isDirty: bool           │
                    │ isSaving: bool          │
                    └───────┬────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
  PitchEditor        TacticsSidebar       TacticsToolbar
  读: playerPositions  读: 所有参数         读: name, isDirty
  写: movePlayer()     写: setParam()       写: saveTactic()
```

### 1.3 Key Interactions

**拖拽球员:**
```
1. 用户拖拽 PlayerNode
2. React Flow onNodeDragStop → tacticsStore.movePlayer(playerId, x, y)
3. tacticsStore.isDirty = true
4. PitchEditor 重渲染 (球员位置更新)
5. 如果该球员被选中, PlayerDetailPanel 显示新坐标
```

**改变战术参数 (如 Pressing=8):**
```
1. 用户拖动 PressingLevel slider → 8
2. TacticsSidebar onChange → tacticsStore.setParam("pressingLevel", 8)
3. tacticsStore.isDirty = true
4. PitchSVG 重渲染:
   - 防守球员 Y 坐标视觉上移 (高防线)
   - 压迫触发区半透明覆盖层扩大
5. 1.5 秒后防抖生效 → 不做任何事 (不自动保存)
```

**切换阵型:**
```
1. 用户 FormationSelector 选择 "4-4-2"
2. tacticsStore.setFormation("4-4-2")
3. playerPositions 重置为该阵型默认坐标
4. PitchEditor 重渲染: 全部 11 个 PlayerNode 跳到新位置
5. 警告: "切换阵型将重置球员位置" (如果是编辑中途)
```

**保存:**
```
1. 用户点击 SaveButton
2. tacticsStore.saveTactic():
   a. PATCH /api/v1/tactics/{id} (或 POST 如果是新)
   b. 请求体: TacticCreateSchema
   c. 成功 → isDirty = false, 显示 toast "Saved"
   d. 失败 → toast "Save failed: ..."
```

### 1.4 Zustand Store

```typescript
interface TacticsState {
  // Data
  currentTactic: Tactic | null;
  originalTactic: Tactic | null;  // for dirty detection
  isDirty: boolean;
  isSaving: boolean;

  // Agent
  agentAnalysis: TacticsAnalysis | null;
  isAnalyzing: boolean;

  // Actions
  loadTactic(id: string): Promise<void>;
  createNew(teamId: string): void;
  setFormation(formation: string): void;
  movePlayer(playerId: string, x: number, y: number): void;
  assignPlayerToPosition(positionIndex: number, playerId: string): void;
  setRole(positionIndex: number, role: PlayerRole): void;
  setParam(key: string, value: number | string): void;
  saveTactic(): Promise<void>;

  // Agent actions
  requestAnalysis(): Promise<void>;
}
```

---

## 2. Run Simulation（运行模拟）

### 2.1 Component Tree

```
SimulationPage
├── SimulationSetup                         # 配置区
│   ├── TeamSelector                        # 主队选择
│   │   ├── TeamDropdown                    # 选球队
│   │   ├── TacticDropdown                  # 选战术 (只显示该球队的)
│   │   └── PlayerListPreview               # 11 人预览卡片
│   ├── VsDivider                           # "VS"
│   ├── TeamSelector                        # 客队选择 (同上)
│   └── SimulationPresets                   # 快捷按钮
│       ├── PresetButton: "我的 4-3-3 vs 4-4-2"
│       └── PresetButton: "上次组合"
│
├── SimControls                             # 运行控制
│   ├── MatchCountSelector                  # 1 | 10 | 100 | 1000
│   ├── RunButton                           # "▶ Run N Matches"
│   ├── CancelButton                        # "■ Cancel" (only during running)
│   └── SpeedDisplay                        # "Estimated: ~3 min"
│
├── SimProgress                             # 进度区 (only when status=running)
│   ├── ProgressBar                         # 百分比 + 进度条
│   ├── ProgressStats                       # "12/100 matches done"
│   ├── ElapsedTime                         # "Elapsed: 00:45"
│   └── EstimatedRemaining                  # "Remaining: ~2 min"
│
├── SimResults                              # 结果区 (only when status=completed)
│   ├── ResultsSummaryCards                 # 4 张概览卡
│   │   ├── WinRateCard                     # 胜率 52% + 迷你柱状图
│   │   ├── GoalsCard                       # 场均进球 1.8
│   │   ├── XgCard                          # 场均 xG 1.9
│   │   └── PossessionCard                  # 控球率 58%
│   ├── MatchResultTable                    # 每场比赛结果
│   │   ├── MatchRow[]                      # #1 Home 2-1 Away [Replay]
│   │   └── Pagination                      # 分页 (100+ 条时)
│   └── ActionButtons
│       ├── ViewAnalyticsButton             # → /analytics/{jobId}
│       └── RerunButton                     # 重新运行 (相同配置)
│
├── ReplayDrawer                            # 右侧抽屉: 回放
│   ├── ReplayPitch                         # 2D Canvas 球场
│   │   ├── PitchLayer                      # 球场线条
│   │   ├── PlayerLayer[]                   # 22 个带号码圆圈
│   │   └── BallLayer                       # 白色小球
│   ├── ReplayControls                      # 播放控制
│   │   ├── PlayPauseButton
│   │   ├── SpeedSelector                   # 0.5x | 1x | 2x | 4x
│   │   ├── TickScrubber                    # 可拖拽时间轴
│   │   └── TickCounter                     # "T0342 / 5400"
│   ├── ScoreDisplay                        # 当前比分 (大字)
│   └── EventFeed                           # 事件流 (倒序)
│       ├── EventRow[]                      # "T342 Pass: #7 → #9 ✓"
│       └── TeamFilter                      # ALL | HOME | AWAY
│
└── ErrorState                              # (only when status=failed)
    ├── ErrorMessage                        # "Engine connection lost"
    └── RetryButton
```

### 2.2 State Machine

```
                    ┌──────────┐
                    │  IDLE    │  ← 初始状态
                    └────┬─────┘
                         │ 用户点击 "Run"
                         ▼
                    ┌──────────┐
                    │ CREATING │  ← POST /simulate 请求中
                    └────┬─────┘
                         │ 拿到 job_id
                         ▼
                    ┌──────────┐
               ┌───▶│ PENDING  │  ← 等待 Engine 接单
               │    └────┬─────┘
               │         │ Engine 开始执行 (progress > 0)
               │         ▼
               │    ┌──────────┐
               │    │ RUNNING  │  ← 轮询 GET /jobs/{id}, 更新 progress
               │    └────┬─────┘
               │         │ status 变化:
               │         ├── "completed" ──▶ ┌────────────┐
               │         │                   │ COMPLETED  │ ← 显示结果
               │         │                   └────────────┘
               │         ├── "failed"    ──▶ ┌────────────┐
               │         │                   │  FAILED    │ ← 显示错误
               │         │                   └────────────┘
               │         └── 用户点 Cancel ──▶┌────────────┐
               │                              │ CANCELLING │
               │                              └─────┬──────┘
               │                                    │ PUT /jobs/{id}/cancel
               │                                    ▼
               │                              ┌────────────┐
               └──────────────────────────────│ CANCELLED  │
                                              └────────────┘
```

### 2.3 Polling Strategy

```typescript
// simulationStore.ts

const POLL_INTERVALS = {
  pending:  2000,  // 等 Engine 接单: 2s
  running:  1500,  // 执行中: 1.5s
  default:  5000,
};

function startPolling(jobId: string) {
  const poll = async () => {
    const job = await api.getJob(jobId);

    set({ activeJob: job });

    if (job.status === 'completed' || job.status === 'failed' || job.status === 'cancelled') {
      stopPolling();
      if (job.status === 'completed') {
        loadResults(jobId);  // 拉取完整结果
      }
      return;
    }

    // 继续轮询
    const interval = POLL_INTERVALS[job.status] ?? POLL_INTERVALS.default;
    pollTimer = setTimeout(poll, interval);
  };

  poll();
}
```

### 2.4 Simulation API Calls

```typescript
// 启动模拟
async function startSimulation(params: {
  homeTeamId: string;
  awayTeamId: string;
  homeTacticId: string;
  awayTacticId: string;
  matchCount: 1 | 10 | 100 | 1000;
}): Promise<{ jobId: string }> {
  return api.post('/simulate', params);
}

// 轮询状态
async function getJob(jobId: string): Promise<SimulationJob> {
  return api.get(`/simulation/jobs/${jobId}`);
}

// 拉取完整结果 (模拟完成后)
async function getJobResults(jobId: string): Promise<SimulationResult[]> {
  return api.get(`/simulation/jobs/${jobId}/results`);
}

// 拉取单场回放数据
async function getReplayData(jobId: string, matchIndex: number): Promise<ReplayData> {
  return api.get(`/simulation/jobs/${jobId}/replay/${matchIndex}`);
}

// 取消模拟
async function cancelJob(jobId: string): Promise<void> {
  return api.put(`/simulation/jobs/${jobId}/cancel`);
}
```

### 2.5 Replay Player

```typescript
// useReplayAnimation.ts
//
// 核心逻辑: 逐 tick 渲染 events.jsonl 数据到 Canvas

function useReplayAnimation(canvasRef, replayData: ReplayData) {
  const [currentTick, setCurrentTick] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);  // 0.5 | 1 | 2 | 4

  useEffect(() => {
    if (!isPlaying) return;

    const tickDuration = 1000 / (speed * 10);  // 默认每秒渲染 10 ticks
    const timer = setInterval(() => {
      setCurrentTick(t => {
        const next = t + 1;
        if (next >= replayData.ticks.length) {
          setIsPlaying(false);
          return t;
        }
        return next;
      });
    }, tickDuration);

    return () => clearInterval(timer);
  }, [isPlaying, speed]);

  // 每帧绘制
  useEffect(() => {
    const ctx = canvasRef.current?.getContext('2d');
    if (!ctx) return;

    const tick = replayData.ticks[currentTick];
    drawPitch(ctx);            // 球场背景
    drawPlayers(ctx, tick);    // 球员圆圈
    drawBall(ctx, tick);       // 球
    drawEvents(ctx, tick);     // 传球线、射门线
  }, [currentTick]);

  return { currentTick, isPlaying, setIsPlaying, speed, setSpeed,
           jumpToTick: setCurrentTick, totalTicks: replayData.ticks.length };
}
```

---

## 3. Analytics Dashboard（数据分析）

### 3.1 Component Tree

```
AnalyticsPage (/analytics/[jobId])
├── AnalyticsHeader
│   ├── BackButton                          # ← Back to Simulation
│   ├── JobTitle                            # "4-3-3 Gegenpress vs 4-4-2 Low Block"
│   ├── MatchCountBadge                     # "100 matches"
│   └── MatchSelector                       # 下拉选单场 | 聚合视图
│
├── KpiRow                                  # 第一行: 关键指标
│   ├── KpiCard: Win Rate                   # 52% + △ 趋势指示
│   ├── KpiCard: Goals For / Against        # 1.8 / 1.2
│   ├── KpiCard: xG For / Against           # 1.9 / 1.1
│   ├── KpiCard: Possession                 # 58.3%
│   └── KpiCard: Pass Accuracy              # 84.2%
│
├── ChartsGrid                              # 第二行: 图表
│   ├── ChartCard: XgTimeline               # 累积 xG 折线图
│   │   └── Recharts LineChart              # 横轴: 比赛时间, 纵轴: xG
│   │                                       # home 蓝线, away 红线
│   │
│   ├── ChartCard: WinDrawLoss              # 胜平负饼图
│   │   └── Recharts PieChart               # W=52%, D=23%, L=25%
│   │
│   ├── ChartCard: GoalDistribution         # 进球分布柱状图
│   │   └── Recharts BarChart               # 0-15', 15-30', ..., 75-90'
│   │
│   └── ChartCard: PossessionOverTime       # 控球率变化折线图
│       └── Recharts LineChart              # 横轴: 比赛时间, 纵轴: %
│
├── PitchVisualizations                     # 第三行: 场地可视化
│   ├── ChartCard: Heatmap                  # 球队热力图
│   │   ├── HeatmapPitch                    # Canvas: 球场网格 + 颜色深浅
│   │   └── TeamToggle                      # Home | Away 切换
│   │
│   ├── ChartCard: ShotMap                  # 射门图
│   │   ├── ShotPitch                       # SVG 球场
│   │   │   ├── GoalMarkers[]               # 进球 ● green
│   │   │   ├── SaveMarkers[]               # 扑救 ● orange
│   │   │   ├── MissMarkers[]               # 射偏 ✕ red
│   │   │   └── BlockMarkers[]              # 被挡 ◆ gray
│   │   └── ShotLegend                      # 图例
│   │
│   └── ChartCard: PassNetwork              # 传球网络
│       ├── PassNetworkSVG                  # 节点 = 平均位置, 边 = 传球次数
│       │   ├── PlayerNode[]                # 圆圈大小 ∝ 触球次数
│       │   └── PassEdge[]                  # 线粗细 ∝ 传球次数
│       └── ThresholdSlider                 # 过滤低于 N 次的传球线
│
├── DetailedStatsTable                      # 第四行: 详细统计表
│   └── StatsTable                          # 可排序表格
│       ├── Column: Stat Name               # 统计项名称
│       ├── Column: Home                    # 主队数值
│       ├── Column: Away                    # 客队数值
│       └── Column: Diff                    # 差异 (正负色)
│
└── AgentReportSection                      # 第五行: AI 分析报告入口
    ├── GenerateReportButton                # "Generate AI Report"
    ├── ReportStatusIndicator               # (loading / ready)
    └── ReportContent                        # 展开的报告正文
```

### 3.2 Data Shapes (from API)

```typescript
// GET /analytics/job/{jobId} → AggregateAnalytics

interface AggregateAnalytics {
  jobId: string;
  matchCount: number;

  // KPIs
  homeWinRate: number;         // 0.52
  drawRate: number;            // 0.23
  awayWinRate: number;         // 0.25
  avgHomeGoals: number;        // 1.8
  avgAwayGoals: number;        // 1.2
  avgHomeXg: number;           // 1.9
  avgAwayXg: number;           // 1.1
  avgHomePossession: number;   // 58.3
  avgPassAccuracy: number;     // 84.2

  // Goal distribution
  goalDistribution: {
    home: [3, 5, 8, 12, 10, 7];   // per 15-min segment
    away: [1, 2, 4, 5, 6, 5];
  };

  // Cumulative xG timeline (90 data points, 1 per minute)
  xgTimeline: {
    home: number[];  // length 90
    away: number[];  // length 90
  };

  // Possession timeline
  possessionTimeline: number[];  // length 90, home possession %

  // Heatmap (grid bins, 20x14 = 280 cells)
  heatmap: {
    home: number[][];  // 20x14 matrix, values 0-1
    away: number[][];
  };

  // Shot map
  shotMap: {
    home: Shot[];  // all shots from all matches
    away: Shot[];
  };

  // Pass network
  passNetwork: {
    nodes: PassNode[];  // {playerId, avgX, avgY, touches}
    edges: PassEdge[];  // {fromId, toId, count, accuracy}
  };

  // Detailed stats table
  detailedStats: StatRow[];
}

interface Shot {
  x: number; y: number;      // position
  xg: number;                // expected goals value
  outcome: 'goal' | 'save' | 'miss' | 'block';
  playerId: string;
  minute: number;
}

interface PassNode {
  playerId: string;
  name: string;
  avgX: number; avgY: number;
  touches: number;
}

interface PassEdge {
  fromId: string; toId: string;
  count: number;
  accuracy: number;
}

interface StatRow {
  name: string;              // "Shots", "Tackles", ...
  homeValue: number;
  awayValue: number;
  unit?: string;             // "%", "per match", etc.
}
```

### 3.3 API Calls

```typescript
// 聚合分析
async function getAggregateAnalytics(jobId: string): Promise<AggregateAnalytics> {
  return api.get(`/analytics/job/${jobId}`);
}

// 单场分析
async function getMatchAnalytics(jobId: string, matchIndex: number): Promise<MatchAnalytics> {
  return api.get(`/analytics/job/${jobId}/match/${matchIndex}`);
}
```

### 3.4 Chart Rendering Details

**Heatmap:**
```
输入: 20x14 矩阵 (每个格子代表 pitch 的 1/20 × 1/14)
渲染: Canvas drawRect 逐格填充
颜色: 透明(0) → 浅蓝 → 深蓝 → 深红(1)
半透明覆盖在球场底图上
```

**ShotMap:**
```
输入: Shot[] 数组
渲染: SVG scatter plot on pitch background
尺寸: 圆圈半径 6px
颜色: goal=#22c55e, save=#f97316, miss=#ef4444, block=#6b7280
hover tooltip: 球员名, xG 值, 分钟
```

**PassNetwork:**
```
输入: {nodes: PassNode[], edges: PassEdge[]}
渲染: SVG
节点: playerNode 圆心 = (avgX, avgY), 半径 = 5 + touches/10 px
边: line 从 fromNode 到 toNode, strokeWidth = count/10 px, 透明度 = accuracy
过滤: 默认隐藏 count < 5 的边
```

---

## 4. AI Tactical Report（AI 战术报告）

### 4.1 Component Tree

```
AgentPanel                                 # 通用: 战术分析 / 比赛报告 / 优化建议
├── AgentTrigger                           # 触发按钮区
│   ├── TriggerButton: "Analyze Tactic"    # 战术编辑页 → TacticsAgent
│   ├── TriggerButton: "Generate Report"   # 分析页 → AnalysisAgent
│   └── TriggerButton: "Optimize Tactic"   # 分析页 → OptimizationAgent
│
├── AgentTaskStatus                        # 任务状态 (only when task active)
│   ├── StatusBadge                        # "pending" | "running" | "completed"
│   ├── ProgressSpinner                    # 加载动画
│   ├── StatusMessage                      # "Agent is analyzing your tactic..."
│   └── CancelButton
│
├── TacticsAnalysisResult                  # TacticsAgent 输出
│   ├── SummaryQuote                       # "A high-pressing 4-3-3 built for..."
│   ├── StyleLabel                         # 标签: "High-Press Possession"
│   ├── StrengthsCard
│   │   └── StrengthItem[]                 # title + description
│   ├── WeaknessesCard
│   │   └── WeaknessItem[]                 # title + description
│   ├── MatchupAdvice                      # "Ideal against: ... / Vulnerable against: ..."
│   └── CopyToClipboardButton
│
├── MatchReportResult                      # AnalysisAgent 输出
│   ├── Headline                           # 一句话摘要
│   ├── AttackSection                      # 进攻分析
│   │   ├── EffectivenessParagraph
│   │   └── PatternList                    # 关键进攻模式
│   ├── PossessionSection                  # 控球分析
│   │   ├── RetentionParagraph
│   │   └── TransitionParagraph
│   ├── DefenseSection                     # 防守分析
│   │   ├── VulnerabilityList
│   │   └── PressEffectiveness
│   ├── PlayerRatingsTable                 # 球员评分
│   │   └── PlayerRatingRow[]              # name, rating (1-10), comment
│   └── KeyInsight                         # 加粗: 最重要发现
│
└── OptimizationResult                     # OptimizationAgent 输出
    ├── ChangeList                          # 修改建议列表
    │   └── ChangeItem[]                    # param, from, to, reason
    ├── ExpectedImprovement                 # 预期改善
    ├── RiskWarning                         # 潜在新风险
    ├── ApplyButton                         # "Apply Changes → Tactic Editor"
    └── DiscardButton
```

### 4.2 Async Task Flow

```
用户点击 "Analyze Tactic" / "Generate Report" / "Optimize Tactic"
  │
  ▼
┌─────────────────────────────────────────────────────────┐
│ 1. Frontend: POST /agent/{type}                          │
│    Body: { tacticId / jobId, ... }                      │
│    → Backend 创建 agent task, 通过 Ably 发布任务         │
│    → 返回 { taskId }                                     │
│                                                          │
│ 2. Backend → Ably → Local Agent (pick up task)          │
│                                                          │
│ 3. Agent: 调 LLM API (用本地 key)                        │
│    → 生成分析报告 / 优化建议                              │
│    → POST /agent/{type}/{taskId}/result                  │
│                                                          │
│ 4. Frontend: 轮询 GET /agent/{type}/{taskId}            │
│    → status: "completed"                                 │
│    → 拿到 result                                        │
└─────────────────────────────────────────────────────────┘
  │
  ▼
渲染结果
```

### 4.3 Agent Store

```typescript
interface AgentState {
  // Tactics Agent
  tacticsAnalysisTaskId: string | null;
  tacticsAnalysisStatus: 'idle' | 'pending' | 'running' | 'completed' | 'failed';
  tacticsAnalysisResult: TacticsAnalysis | null;

  // Analysis Agent
  matchReportTaskId: string | null;
  matchReportStatus: 'idle' | 'pending' | 'running' | 'completed' | 'failed';
  matchReportResult: MatchReport | null;

  // Optimization Agent
  optimizationTaskId: string | null;
  optimizationStatus: 'idle' | 'pending' | 'running' | 'completed' | 'failed';
  optimizationResult: OptimizationResult | null;

  // Actions
  requestTacticsAnalysis(tacticId: string): Promise<void>;
  requestMatchReport(jobId: string): Promise<void>;
  requestOptimization(tacticId: string, jobId: string): Promise<void>;
  pollTaskStatus(type: string, taskId: string): void;
  applyOptimization(): void;  // 将优化结果写入 tacticsStore
}
```

### 4.4 API Calls

```typescript
// 发起 Agent 任务
async function requestAgentTask(type: string, params: object): Promise<{ taskId: string }> {
  return api.post(`/agent/${type}`, params);
}

// 轮询任务状态
async function getAgentTaskStatus(type: string, taskId: string): Promise<AgentTask> {
  return api.get(`/agent/${type}/${taskId}`);
}

// Agent 回传结果 (本地 Engine 调用)
async function submitAgentResult(type: string, taskId: string, result: object): Promise<void> {
  return api.post(`/agent/${type}/${taskId}/result`, result);
}
```

### 4.5 Agent Output Data Shapes

```typescript
interface TacticsAnalysis {
  summary: string;
  strengths: Array<{ title: string; description: string }>;
  weaknesses: Array<{ title: string; description: string }>;
  idealAgainst: string;
  vulnerableAgainst: string;
  styleLabel: string;
}

interface MatchReport {
  headline: string;
  attackAnalysis: {
    effectiveness: string;
    patterns: string[];
    xgAnalysis: string;
  };
  possessionAnalysis: {
    retention: string;
    transitions: string;
  };
  defensiveAnalysis: {
    vulnerabilities: string[];
    pressingEffectiveness: string;
  };
  playerPerformance: Array<{
    playerName: string;
    rating: number;    // 1-10
    note: string;
  }>;
  keyInsight: string;
}

interface OptimizationResult {
  changes: Array<{
    param: string;     // "defensiveLine", "pressingLevel", ...
    from: number;
    to: number;
    reason: string;
  }>;
  expectedImprovement: string;
  risk: string;
}

interface AgentTask {
  taskId: string;
  type: 'tactics_analysis' | 'match_report' | 'optimization';
  status: 'pending' | 'running' | 'completed' | 'failed';
  result?: TacticsAnalysis | MatchReport | OptimizationResult;
  error?: string;
}
```

### 4.6 Integration Points

Agent 功能不独立成页，而是嵌入在对应页面中：

| Agent | 嵌入位置 | 触发方式 |
|-------|---------|---------|
| **Tactics Agent** | TacticsEditor 右侧面板底部 | 编辑战术时随时触发，分析当前战术 |
| **Analysis Agent** | AnalyticsPage 底部 Section | 查看分析数据后触发，生成文字报告 |
| **Optimization Agent** | AnalyticsPage 底部 Section | 看完报告后触发，生成改进建议 |

三个 agent 共享同一个 `agentStore`，但 UI 渲染在不同页面中。

---

## 5. Shared UI Components

```
components/ui/
├── Button.tsx              # variant: primary | secondary | danger | ghost
├── Card.tsx                # 通用卡片 (padding, shadow, title slot)
├── Slider.tsx              # 1-10 整数滑块 (带标签 + 实时数值)
├── Select.tsx              # 下拉选择器
├── Modal.tsx               # 模态框 (header, body, footer slots)
├── Toast.tsx               # 通知提示
├── Badge.tsx               # 小标签 (状态、角色)
├── Tabs.tsx                # 标签页切换
├── Skeleton.tsx            # 加载骨架屏
├── ProgressBar.tsx         # 进度条
├── EmptyState.tsx          # 空状态占位图
└── ErrorBoundary.tsx       # 错误边界
```

---

## 6. Route Design Summary

```
/                          Dashboard
/tactics                   Tactics Editor (新建/编辑)
/tactics/[id]              Tactics Editor (编辑已有)
/simulation                Simulation Runner (新建)
/simulation/[jobId]        Simulation Results + Replay
/analytics/[jobId]         Analytics Dashboard
/settings                  Settings (Ably key, LLM config)
/auth/login                Login
/auth/register             Register
```
