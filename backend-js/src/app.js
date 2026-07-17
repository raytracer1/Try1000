const { parse } = require("url");
const jwt = require("jsonwebtoken");
const { getDb } = require("./database");
const { createTables } = require("./db/migrate");
const schema = require("./db/schema");
const { eq, or, and, desc } = require("drizzle-orm");
const { config } = require("./config");

// ═══════════════════════════════════════════════════
// Handlers
// ═══════════════════════════════════════════════════

function auth(ctx) {
  const token = ctx.getCookie("try1000_token");
  if (!token) { ctx.respond(401, { detail: "Not authenticated" }); return 0; }
  try { return +jwt.verify(token, config.jwtSecret).sub; }
  catch { ctx.respond(401, { detail: "Invalid token" }); return 0; }
}

const handlers = {
  async authGoogle(ctx) {
    try {
      const { code: authCode, redirect_uri } = ctx.parseBody();
      if (!authCode) return ctx.respond(400, { detail: "Missing code" });
      if (!config.googleClientId || !config.googleClientSecret) return ctx.respond(400, { detail: "Not configured" });

      // Exchange code for tokens — use WHATWG URL + Node.js https
      const params = `code=${encodeURIComponent(authCode)}&client_id=${encodeURIComponent(config.googleClientId)}&client_secret=${encodeURIComponent(config.googleClientSecret)}&redirect_uri=${encodeURIComponent(redirect_uri || "https://try1000.vercel.app")}&grant_type=authorization_code`;

      const { URL } = require("url");
      const target = new URL("https://oauth2.googleapis.com/token");

      const https = require("https");
      const tokenResult = await new Promise((resolve, reject) => {
        const req = https.request({
          hostname: target.hostname,
          path: target.pathname,
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded", "Content-Length": Buffer.byteLength(params) },
        }, (res) => { let d = ""; res.on("data", c => d += c); res.on("end", () => { try { resolve(JSON.parse(d)); } catch (e) { reject(e); } }); });
        req.on("error", reject);
        req.write(params); req.end();
      });

      if (tokenResult.error) return ctx.respond(401, { detail: tokenResult.error, description: tokenResult.error_description });

      // Decode id_token JWT to get user info
      const payload = JSON.parse(Buffer.from(tokenResult.id_token.split(".")[1], "base64").toString("utf-8"));
      const email = payload.email;
      const name = payload.name || email.split("@")[0];
      const googleId = payload.sub;

      let [user] = await ctx.db.select().from(schema.users).where(or(eq(schema.users.googleId, googleId), eq(schema.users.email, email)));
      if (user) {
        if (!user.googleId) await ctx.db.update(schema.users).set({ googleId }).where(eq(schema.users.id, user.id));
      } else {
        [user] = await ctx.db.insert(schema.users).values({ email, username: name, googleId }).returning();
      }
      const token = jwt.sign({ sub: String(user.id) }, config.jwtSecret, { expiresIn: "24h" });
      ctx.setCookie("try1000_token", token, { maxAge: 86400 });
      ctx.respond(200, { ok: true });
    } catch (e) { ctx.respond(401, { detail: "Auth failed", error: e.message }); }
  },

  logout(ctx) { ctx.clearCookie("try1000_token"); ctx.respond(200, { ok: true }); },

  async me(ctx) {
    const uid = auth(ctx); if (!uid) return;
    const [u] = await ctx.db.select().from(schema.users).where(eq(schema.users.id, uid));
    if (!u) return ctx.respond(404, { detail: "User not found" });
    ctx.respond(200, { id: u.id, email: u.email, username: u.username, has_llm_key: !!u.llmApiKey });
  },

  async settings(ctx) {
    const uid = auth(ctx); if (!uid) return;
    const b = ctx.parseBody();
    await ctx.db.update(schema.users).set({ llmProvider: b.llm_provider || null, llmApiKey: b.llm_api_key || null, llmModel: b.llm_model || "claude-sonnet-5" }).where(eq(schema.users.id, uid));
    ctx.respond(200, { ok: true });
  },

  // Simulation
  async simCreate(ctx) {
    const uid = auth(ctx); if (!uid) return;
    const b = ctx.parseBody();
    if (![1, 10, 100, 1000].includes(b.match_count)) return ctx.respond(400, { detail: "match_count must be 1,10,100,1000" });
    const [job] = await ctx.db.insert(schema.simulationJobs).values({
      userId: uid,
      homePlayers: b.home_players || [],
      awayPlayers: b.away_players || [],
      homeTactic: b.home_tactic || {},
      awayTactic: b.away_tactic || {},
      matchCount: b.match_count,
      status: "pending",
    }).returning();
    // Notify engine via Ably (non-blocking, best-effort)
    const ablyKey = config.ablyApiKey;
    if (ablyKey) {
      try {
        const Ably = require("ably");
        const ably = new Ably.Rest(ablyKey);
        const channel = ably.channels.get("try1000:tasks");
        channel.publish("new_job", { job_id: job.id });
        setTimeout(() => ably.close(), 2000);
      } catch {}
    }
    ctx.respond(200, { job_id: job.id });
  },
  async simList(ctx) {
    const uid = auth(ctx); if (!uid) return;
    const jobs = await ctx.db.select().from(schema.simulationJobs).where(eq(schema.simulationJobs.userId, uid)).orderBy(desc(schema.simulationJobs.id)).limit(20);
    ctx.respond(200, jobs.map((j) => ({ id: j.id, match_count: j.matchCount, status: j.status, progress: j.progress, created_at: j.createdAt })));
  },
  async simGet(ctx) {
    const uid = auth(ctx); if (!uid) return;
    const [job] = await ctx.db.select().from(schema.simulationJobs).where(eq(schema.simulationJobs.id, +ctx.params.id));
    if (!job) return ctx.respond(404, {});
    ctx.respond(200, {
      id: job.id, match_count: job.matchCount, status: job.status, progress: job.progress,
      created_at: job.createdAt, completed_at: job.completedAt,
      results: await ctx.db.select().from(schema.simulationResults).where(eq(schema.simulationResults.jobId, job.id)),
    });
  },
  async simReplay(ctx) {
    const uid = auth(ctx); if (!uid) return;
    const results = await ctx.db.select().from(schema.simulationResults).where(eq(schema.simulationResults.jobId, +ctx.params.id));
    const r = results.find((r) => r.matchIndex === +ctx.params.idx);
    if (!r || !r.replayPath) return ctx.respond(404, { detail: "Replay not found" });

    const storagePath = r.replayPath.replace("supabase://replays/", "");
    const supabaseUrl = config.supabaseUrl;
    const supabaseKey = config.supabaseServiceKey;

    if (!supabaseUrl || !supabaseKey || !r.replayPath.startsWith("supabase://")) {
      return ctx.respond(404, { detail: "Replay storage not configured" });
    }

    // Generate a signed URL valid for 1 hour
    try {
      const https = require("https");
      const body = JSON.stringify({ expiresIn: 3600 });
      const result = await new Promise((resolve, reject) => {
        const req = https.request(`${supabaseUrl}/storage/v1/object/sign/replays/${storagePath}`, {
          method: "POST",
          headers: {
            "Authorization": `Bearer ${supabaseKey}`,
            "Content-Type": "application/json",
            "Content-Length": Buffer.byteLength(body),
          },
        }, (res) => {
          let d = ""; res.on("data", (c) => d += c); res.on("end", () => { try { resolve(JSON.parse(d)); } catch { reject(new Error(d)); } });
          res.on("error", reject);
        });
        req.on("error", reject);
        req.write(body);
        req.end();
      });
      ctx.respond(200, { match_index: +ctx.params.idx, signed_url: result.signedURL || result.signed_url });
    } catch {
      ctx.respond(500, { detail: "Failed to generate signed URL" });
    }
  },

  // Analytics
  async analytics(ctx) {
    const uid = auth(ctx); if (!uid) return;
    const results = await ctx.db.select().from(schema.simulationResults).where(eq(schema.simulationResults.jobId, +ctx.params.jobId));
    if (!results.length) return ctx.respond(200, { match_count: 0 });
    const n = results.length, s = (fn) => results.reduce((a, r) => a + fn(r), 0);
    ctx.respond(200, { job_id: +ctx.params.jobId, match_count: n, home_win_rate: Math.round(s(r => r.homeScore > r.awayScore ? 1 : 0) / n * 1000) / 1000, avg_home_goals: Math.round(s(r => r.homeScore) / n * 100) / 100, avg_home_xg: Math.round(s(r => r.homeXg) / n * 10000) / 10000, avg_home_possession: Math.round(s(r => r.homePossession) / n * 10) / 10 });
  },

  // Agent (stubs)
  agent: (ctx) => ctx.respond(200, { status: "pending" }),
  agentResults: async (ctx) => {
    const uid = auth(ctx); if (!uid) return;
    ctx.respond(200, await ctx.db.select().from(schema.agentResults).where(eq(schema.agentResults.userId, uid)).orderBy(schema.agentResults.id.desc()).limit(20));
  },

  // Engine endpoints — called by engine runner
  async engineJobsPending(ctx) {
    const jobs = await ctx.db.select().from(schema.simulationJobs).where(eq(schema.simulationJobs.status, "pending")).orderBy(schema.simulationJobs.id).limit(5);
    // Update status so another runner doesn't pick them up
    for (const j of jobs) {
      await ctx.db.update(schema.simulationJobs).set({ status: "running" }).where(eq(schema.simulationJobs.id, j.id));
    }
    ctx.respond(200, { jobs: jobs.map((j) => ({
      id: j.id,
      home_players: j.homePlayers,
      away_players: j.awayPlayers,
      home_tactic: j.homeTactic,
      away_tactic: j.awayTactic,
      match_count: j.matchCount,
      seed_base: j.seedBase,
      status: "running",
    })) });
  },
  async engineJobResult(ctx) {
    const b = ctx.parseBody();
    await ctx.db.insert(schema.simulationResults).values({
      jobId: +ctx.params.id,
      matchIndex: b.match_index,
      homeScore: b.home_score, awayScore: b.away_score,
      homeXg: b.home_xg, awayXg: b.away_xg,
      homePossession: b.home_possession, awayPossession: b.away_possession,
      stats: b.stats || {}, replayPath: b.replay_path || null,
    });
    // Update progress
    const [job] = await ctx.db.select().from(schema.simulationJobs).where(eq(schema.simulationJobs.id, +ctx.params.id));
    if (job) {
      const done = (await ctx.db.select().from(schema.simulationResults).where(eq(schema.simulationResults.jobId, job.id))).length;
      await ctx.db.update(schema.simulationJobs).set({ progress: Math.round((done / job.matchCount) * 100) }).where(eq(schema.simulationJobs.id, job.id));
    }
    ctx.respond(200, { ok: true });
  },
  async engineJobComplete(ctx) {
    await ctx.db.update(schema.simulationJobs).set({ status: "completed", progress: 100, completedAt: new Date() }).where(eq(schema.simulationJobs.id, +ctx.params.id));
    ctx.respond(200, { ok: true });
  },

  health: (ctx) => ctx.respond(200, { status: "ok" }),
};

// ═══════════════════════════════════════════════════
// Router
// ═══════════════════════════════════════════════════

const routes = [
  ["POST","/api/v1/auth/google",handlers.authGoogle],["GET","/api/v1/auth/google/callback",handlers.health],
  ["POST","/api/v1/auth/logout",handlers.logout],
  ["GET","/api/v1/auth/me",handlers.me],["PUT","/api/v1/auth/settings",handlers.settings],
  ["POST","/api/v1/simulate",handlers.simCreate],["GET","/api/v1/simulation/jobs",handlers.simList],
  ["GET","/api/v1/simulation/jobs/:id",handlers.simGet],["GET","/api/v1/simulation/jobs/:id/replay/:idx",handlers.simReplay],
  ["GET","/api/v1/analytics/job/:jobId",handlers.analytics],
  ["GET","/api/v1/engine/jobs/pending",handlers.engineJobsPending],
  ["POST","/api/v1/engine/jobs/:id/result",handlers.engineJobResult],
  ["PUT","/api/v1/engine/jobs/:id/complete",handlers.engineJobComplete],
  ["POST","/api/v1/agent/tactics/analyze",handlers.agent],["POST","/api/v1/agent/match/report",handlers.agent],
  ["POST","/api/v1/agent/tactics/optimize",handlers.agent],["GET","/api/v1/agent/results",handlers.agentResults],
  ["GET","/api/v1/health",handlers.health],
];

function match(routePath, requestPath) {
  const rp = routePath.split("/"), qp = requestPath.split("/");
  if (rp.length !== qp.length) return null;
  const params = {};
  for (let i = 0; i < rp.length; i++) {
    if (rp[i].startsWith(":")) params[rp[i].slice(1)] = qp[i];
    else if (rp[i] !== qp[i]) return null;
  }
  return params;
}

async function handleRequest(req, res) {
  const db = getDb();
  const pathname = parse(req.url || "/").pathname || "/";
  const method = (req.method || "GET").toUpperCase();
  let _cookies = [];

  const ctx = {
    db,
    req,
    parseBody() { if (!req.body) return {}; try { return JSON.parse(req.body); } catch { return {}; } },
    getCookie(n) { const raw = req.headers?.cookie || req.headers?.Cookie || ""; const m = raw.match(new RegExp(`${n}=([^;]+)`)); return m ? m[1] : null; },
    setCookie(n, v, o = {}) { _cookies.push([`${n}=${v}`, "HttpOnly", "Secure", "SameSite=Lax", "Path=/", `Max-Age=${o.maxAge || 86400}`].join("; ")); },
    clearCookie(n) { _cookies.push(`${n}=; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=0`); },
    respond(status, data, contentType) {
      const h = { "Content-Type": contentType || "application/json; charset=utf-8" };
      if (_cookies.length) h["Set-Cookie"] = _cookies;
      res.writeHead(status, h);
      if (Buffer.isBuffer(data)) { res.send(data); }
      else { res.send(typeof data === "string" ? data : JSON.stringify(data)); }
    },
  };

  for (const [m, path, handler] of routes) {
    if (m !== method) continue;
    const params = match(path, pathname);
    if (params) { ctx.params = params; await handler(ctx); return; }
  }

  res.writeHead(404, { "Content-Type": "application/json; charset=utf-8" });
  res.send(JSON.stringify({ detail: "Not found" }));
}

let _ready = false;
async function ensure() { if (!_ready) { _ready = true; await createTables(); } }

module.exports = { handleRequest, ensure };
