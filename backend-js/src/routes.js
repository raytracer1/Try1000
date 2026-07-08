const { OAuth2Client } = require("google-auth-library");
const jwt = require("jsonwebtoken");
const { config } = require("./config");
const schema = require("./db/schema");
const { eq, or, and } = require("drizzle-orm");

// ─── Helpers ───

function auth(ctx) {
  const token = ctx.getCookie("try1000_token");
  if (!token) { ctx.respond(401, { detail: "Not authenticated" }); return 0; }
  try { return +jwt.verify(token, config.jwtSecret).sub; }
  catch { ctx.respond(401, { detail: "Invalid token" }); return 0; }
}

const googleClient = config.googleClientId ? new OAuth2Client(config.googleClientId) : null;

// ═══════════════════════════════════════════════════
// Auth
// ═══════════════════════════════════════════════════

async function authGoogle(ctx) {
  try {
    const { credential } = ctx.parseBody();
    if (!googleClient) return ctx.respond( 400, { detail: "Google auth not configured" });
    const ticket = await googleClient.verifyIdToken({ idToken: credential, audience: config.googleClientId });
    const { email, name, sub: googleId } = ticket.getPayload();

    let [user] = await ctx.db.select().from(schema.users).where(or(eq(schema.users.googleId, googleId), eq(schema.users.email, email)));
    if (user) {
      if (!user.googleId) await ctx.db.update(schema.users).set({ googleId }).where(eq(schema.users.id, user.id));
    } else {
      [user] = await ctx.db.insert(schema.users).values({ email, username: name, googleId }).returning();
    }

    const token = jwt.sign({ sub: String(user.id) }, config.jwtSecret, { expiresIn: "24h" });
    ctx.setCookie("try1000_token", token, { maxAge: 86400 });
    ctx.respond( 200, { ok: true });
  } catch { ctx.respond( 401, { detail: "Invalid Google token" }); }
}

function authLogout(ctx) { ctx.clearCookie("try1000_token"); ctx.respond( 200, { ok: true }); }

async function authMe(ctx) {
  const uid = auth(ctx); if (!uid) return;
  const [user] = await ctx.db.select().from(schema.users).where(eq(schema.users.id, uid));
  if (!user) return ctx.respond( 404, { detail: "Not found" });
  ctx.respond( 200, { id: user.id, email: user.email, username: user.username, llm_provider: user.llmProvider, llm_model: user.llmModel, has_llm_key: !!user.llmApiKey });
}

async function authSettings(ctx) {
  const uid = auth(ctx); if (!uid) return;
  const b = ctx.parseBody();
  await ctx.db.update(schema.users).set({ llmProvider: b.llm_provider || null, llmApiKey: b.llm_api_key || null, llmModel: b.llm_model || "claude-sonnet-5" }).where(eq(schema.users.id, uid));
  ctx.respond( 200, { ok: true });
}

// ═══════════════════════════════════════════════════
// Teams
// ═══════════════════════════════════════════════════

async function teamList(ctx) {
  const uid = auth(ctx); if (!uid) return;
  const teams = await ctx.db.select().from(schema.teams).where(eq(schema.teams.userId, uid));
  for (const t of teams) { t.players = await ctx.db.select().from(schema.players).where(eq(schema.players.teamId, t.id)); }
  ctx.respond( 200, teams);
}

async function teamCreate(ctx) {
  const uid = auth(ctx); if (!uid) return;
  const [t] = await ctx.db.insert(schema.teams).values({ userId: uid, name: ctx.parseBody().name }).returning();
  ctx.respond( 200, { ...t, players: [] });
}

async function teamGet(ctx) {
  const uid = auth(ctx); if (!uid) return;
  const [t] = await ctx.db.select().from(schema.teams).where(and(eq(schema.teams.id, +ctx.params.id), eq(schema.teams.userId, uid)));
  if (!t) return ctx.respond( 404, {});
  t.players = await ctx.db.select().from(schema.players).where(eq(schema.players.teamId, t.id));
  ctx.respond( 200, t);
}

async function teamDel(ctx) {
  const uid = auth(ctx); if (!uid) return;
  await ctx.db.delete(schema.teams).where(and(eq(schema.teams.id, +ctx.params.id), eq(schema.teams.userId, uid)));
  ctx.respond( 200, { ok: true });
}

async function addPlayer(ctx) {
  const uid = auth(ctx); if (!uid) return;
  const b = ctx.parseBody();
  const [p] = await ctx.db.insert(schema.players).values({ teamId: +ctx.params.id, name: b.name, number: b.number, position: b.position, attributes: b.attributes || {} }).returning();
  ctx.respond( 200, p);
}

async function delPlayer(ctx) {
  await ctx.db.delete(schema.players).where(eq(schema.players.id, +ctx.params.id));
  ctx.respond( 200, { ok: true });
}

// ═══════════════════════════════════════════════════
// Tactics
// ═══════════════════════════════════════════════════

async function tacticList(ctx) {
  const uid = auth(ctx); if (!uid) return;
  ctx.respond( 200, await ctx.db.select().from(schema.tactics).where(eq(schema.tactics.userId, uid)));
}

async function tacticCreate(ctx) {
  const uid = auth(ctx); if (!uid) return;
  const b = ctx.parseBody();
  const [t] = await ctx.db.insert(schema.tactics).values({ userId: uid, teamId: b.team_id, name: b.name, formation: b.formation || "4-3-3", playerPositions: b.player_positions || {}, pressingLevel: b.pressing_level ?? 5, defensiveLine: b.defensive_line ?? 5, attackingWidth: b.attacking_width ?? 5, tempo: b.tempo ?? 5, passingStyle: b.passing_style || "mixed", buildUpStyle: b.build_up_style || "balanced" }).returning();
  ctx.respond( 200, t);
}

async function tacticGet(ctx) {
  const uid = auth(ctx); if (!uid) return;
  const [t] = await ctx.db.select().from(schema.tactics).where(and(eq(schema.tactics.id, +ctx.params.id), eq(schema.tactics.userId, uid)));
  t ? ctx.respond( 200, t) : ctx.respond( 404, {});
}

async function tacticUpdate(ctx) {
  const uid = auth(ctx); if (!uid) return;
  const b = ctx.parseBody();
  const cols = { playerPositions: "player_positions", pressingLevel: "pressing_level", defensiveLine: "defensive_line", attackingWidth: "attacking_width", tempo: "tempo", passingStyle: "passing_style", buildUpStyle: "build_up_style" };
  const set = {};
  for (const [k, v] of Object.entries(b)) { if (cols[k]) set[cols[k]] = v; else if (schema.tactics[k]) set[k] = v; }
  const [t] = await ctx.db.update(schema.tactics).set(set).where(and(eq(schema.tactics.id, +ctx.params.id), eq(schema.tactics.userId, uid))).returning();
  ctx.respond( 200, t);
}

async function tacticDel(ctx) {
  const uid = auth(ctx); if (!uid) return;
  await ctx.db.delete(schema.tactics).where(and(eq(schema.tactics.id, +ctx.params.id), eq(schema.tactics.userId, uid)));
  ctx.respond( 200, { ok: true });
}

// ═══════════════════════════════════════════════════
// Simulation
// ═══════════════════════════════════════════════════

async function simCreate(ctx) {
  const uid = auth(ctx); if (!uid) return;
  const b = ctx.parseBody();
  if (![1, 10, 100, 1000].includes(b.match_count)) return ctx.respond( 400, { detail: "match_count must be 1,10,100,1000" });
  const [job] = await ctx.db.insert(schema.simulationJobs).values({ userId: uid, homeTeamId: b.home_team_id, awayTeamId: b.away_team_id, homeTacticId: b.home_tactic_id, awayTacticId: b.away_tactic_id, matchCount: b.match_count, status: "pending" }).returning();
  ctx.respond( 200, { job_id: job.id });
}

async function simList(ctx) {
  const uid = auth(ctx); if (!uid) return;
  const jobs = await ctx.db.select().from(schema.simulationJobs).where(eq(schema.simulationJobs.userId, uid)).orderBy(schema.simulationJobs.id.desc()).limit(20);
  ctx.respond( 200, jobs);
}

async function simGet(ctx) {
  const uid = auth(ctx); if (!uid) return;
  const [job] = await ctx.db.select().from(schema.simulationJobs).where(eq(schema.simulationJobs.id, +ctx.params.id));
  if (!job) return ctx.respond( 404, {});
  const results = await ctx.db.select().from(schema.simulationResults).where(eq(schema.simulationResults.jobId, job.id));
  ctx.respond( 200, { ...job, results });
}

async function simReplay(ctx) {
  const [r] = await ctx.db.select().from(schema.simulationResults).where(eq(schema.simulationResults.jobId, +ctx.params.id));
  r ? ctx.respond( 200, { match_index: +ctx.params.idx, replay_path: r.replayPath }) : ctx.respond( 404, {});
}

// ═══════════════════════════════════════════════════
// Analytics
// ═══════════════════════════════════════════════════

async function analyticsGet(ctx) {
  const uid = auth(ctx); if (!uid) return;
  const results = await ctx.db.select().from(schema.simulationResults).where(eq(schema.simulationResults.jobId, +ctx.params.jobId));
  if (!results.length) return ctx.respond( 200, { match_count: 0 });
  const n = results.length, s = (fn) => results.reduce((a, r) => a + fn(r), 0);
  ctx.respond( 200, { job_id: +ctx.params.jobId, match_count: n, home_win_rate: Math.round(s(r => r.homeScore > r.awayScore ? 1 : 0) / n * 1000) / 1000, draw_rate: Math.round(s(r => r.homeScore === r.awayScore ? 1 : 0) / n * 1000) / 1000, avg_home_goals: Math.round(s(r => r.homeScore) / n * 100) / 100, avg_home_xg: Math.round(s(r => r.homeXg) / n * 10000) / 10000, avg_home_possession: Math.round(s(r => r.homePossession) / n * 10) / 10 });
}

// ═══════════════════════════════════════════════════
// Agent
// ═══════════════════════════════════════════════════

function agentAnalyze(ctx) { ctx.respond( 200, { status: "pending", message: "Task dispatched" }); }
function agentReport(ctx) { ctx.respond( 200, { status: "pending", message: "Task dispatched" }); }
function agentOptimize(ctx) { ctx.respond( 200, { status: "pending", message: "Task dispatched" }); }

async function agentResults(ctx) {
  const uid = auth(ctx); if (!uid) return;
  const results = await ctx.db.select().from(schema.agentResults).where(eq(schema.agentResults.userId, uid)).orderBy(schema.agentResults.id.desc()).limit(20);
  ctx.respond( 200, results);
}

// ═══════════════════════════════════════════════════
// Health
// ═══════════════════════════════════════════════════

function health(ctx) {
  ctx.respond( 200, { status: "ok" });
}

module.exports = {
  authGoogle, authLogout, authMe, authSettings,
  teamList, teamCreate, teamGet, teamDel, addPlayer, delPlayer,
  tacticList, tacticCreate, tacticGet, tacticUpdate, tacticDel,
  simCreate, simList, simGet, simReplay,
  analyticsGet,
  agentAnalyze, agentReport, agentOptimize, agentResults,
  health,
};
