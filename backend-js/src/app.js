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

  // Teams
  async teamList(ctx) {
    const uid = auth(ctx); if (!uid) return;
    const teams = await ctx.db.select().from(schema.teams).where(eq(schema.teams.userId, uid));
    for (const t of teams) {
      const ids = t.playerIds || [];
      t.players = ids.length ? await ctx.db.select().from(schema.players).where(/* IN */ (() => {
        const all = ctx.db.select().from(schema.players);
        return all; // HACK: load all and filter below
      })()) : [];
      // Actually load players by IDs properly
      if (ids.length) {
        t.players = [];
        const all = await ctx.db.select().from(schema.players).where(eq(schema.players.userId, uid));
        t.players = all.filter((p) => ids.includes(p.id));
      } else {
        t.players = [];
      }
    }
    ctx.respond(200, teams);
  },
  async teamCreate(ctx) {
    const uid = auth(ctx); if (!uid) return;
    const [t] = await ctx.db.insert(schema.teams).values({ userId: uid, name: ctx.parseBody().name, playerIds: [] }).returning();
    ctx.respond(200, { ...t, players: [] });
  },
  async teamGet(ctx) {
    const uid = auth(ctx); if (!uid) return;
    const [t] = await ctx.db.select().from(schema.teams).where(and(eq(schema.teams.id, +ctx.params.id), eq(schema.teams.userId, uid)));
    if (!t) return ctx.respond(404, {});
    const ids = t.playerIds || [];
    if (ids.length) {
      const all = await ctx.db.select().from(schema.players).where(eq(schema.players.userId, uid));
      t.players = all.filter((p) => ids.includes(p.id));
    } else { t.players = []; }
    ctx.respond(200, t);
  },
  async teamDel(ctx) {
    const uid = auth(ctx); if (!uid) return;
    await ctx.db.delete(schema.teams).where(and(eq(schema.teams.id, +ctx.params.id), eq(schema.teams.userId, uid)));
    ctx.respond(200, { ok: true });
  },
  // Add/remove player from team
  async teamAddPlayer(ctx) {
    const uid = auth(ctx); if (!uid) return;
    const [t] = await ctx.db.select().from(schema.teams).where(and(eq(schema.teams.id, +ctx.params.id), eq(schema.teams.userId, uid)));
    if (!t) return ctx.respond(404, {});
    const ids = [...(t.playerIds || [])];
    if (!ids.includes(+ctx.parseBody().player_id)) ids.push(+ctx.parseBody().player_id);
    await ctx.db.update(schema.teams).set({ playerIds: ids }).where(eq(schema.teams.id, t.id));
    ctx.respond(200, { ok: true });
  },
  async teamRemovePlayer(ctx) {
    const uid = auth(ctx); if (!uid) return;
    const [t] = await ctx.db.select().from(schema.teams).where(and(eq(schema.teams.id, +ctx.params.id), eq(schema.teams.userId, uid)));
    if (!t) return ctx.respond(404, {});
    const ids = (t.playerIds || []).filter((id) => id !== +ctx.parseBody().player_id);
    await ctx.db.update(schema.teams).set({ playerIds: ids }).where(eq(schema.teams.id, t.id));
    ctx.respond(200, { ok: true });
  },
  async playerList(ctx) {
    const uid = auth(ctx); if (!uid) return;
    ctx.respond(200, await ctx.db.select().from(schema.players).where(eq(schema.players.userId, uid)));
  },
  async addPlayer(ctx) {
    const uid = auth(ctx); if (!uid) return;
    const b = ctx.parseBody();
    const [p] = await ctx.db.insert(schema.players).values({ userId: uid, name: b.name, number: b.number, position: b.position, attributes: b.attributes || {} }).returning();
    ctx.respond(200, p);
  },
  async updatePlayer(ctx) {
    const b = ctx.parseBody();
    const set = {};
    if (b.name) set[schema.players.name] = b.name;
    if (b.number) set[schema.players.number] = b.number;
    if (b.position) set[schema.players.position] = b.position;
    if (b.attributes) set[schema.players.attributes] = b.attributes;
    const [p] = await ctx.db.update(schema.players).set(set).where(eq(schema.players.id, +ctx.params.id)).returning();
    ctx.respond(200, p);
  },

  async delPlayer(ctx) {
    await ctx.db.delete(schema.players).where(eq(schema.players.id, +ctx.params.id));
    ctx.respond(200, { ok: true });
  },

  // Tactics
  async tacticList(ctx) { const uid = auth(ctx); if (!uid) return; ctx.respond(200, await ctx.db.select().from(schema.tactics).where(eq(schema.tactics.userId, uid))); },
  async tacticCreate(ctx) {
    const uid = auth(ctx); if (!uid) return;
    const b = ctx.parseBody();
    const [t] = await ctx.db.insert(schema.tactics).values({ userId: uid, teamId: b.team_id, name: b.name, formation: b.formation || "4-3-3", playerPositions: b.player_positions || {}, pressingLevel: b.pressing_level ?? 5, defensiveLine: b.defensive_line ?? 5, attackingWidth: b.attacking_width ?? 5, tempo: b.tempo ?? 5, passingStyle: b.passing_style || "mixed", buildUpStyle: b.build_up_style || "balanced" }).returning();
    ctx.respond(200, t);
  },
  async tacticGet(ctx) {
    const uid = auth(ctx); if (!uid) return;
    const [t] = await ctx.db.select().from(schema.tactics).where(and(eq(schema.tactics.id, +ctx.params.id), eq(schema.tactics.userId, uid)));
    t ? ctx.respond(200, t) : ctx.respond(404, {});
  },
  async tacticUpdate(ctx) {
    const uid = auth(ctx); if (!uid) return;
    const b = ctx.parseBody();
    const set = {};
    const map = { playerPositions: "player_positions", pressingLevel: "pressing_level", defensiveLine: "defensive_line", attackingWidth: "attacking_width", tempo: "tempo", passingStyle: "passing_style", buildUpStyle: "build_up_style" };
    for (const [k, v] of Object.entries(b)) { if (map[k]) set[map[k]] = v; }
    const [t] = await ctx.db.update(schema.tactics).set(set).where(and(eq(schema.tactics.id, +ctx.params.id), eq(schema.tactics.userId, uid))).returning();
    ctx.respond(200, t);
  },
  async tacticDel(ctx) {
    const uid = auth(ctx); if (!uid) return;
    await ctx.db.delete(schema.tactics).where(and(eq(schema.tactics.id, +ctx.params.id), eq(schema.tactics.userId, uid)));
    ctx.respond(200, { ok: true });
  },

  // Simulation
  async simCreate(ctx) {
    const uid = auth(ctx); if (!uid) return;
    const b = ctx.parseBody();
    if (![1, 10, 100, 1000].includes(b.match_count)) return ctx.respond(400, { detail: "match_count must be 1,10,100,1000" });
    const [job] = await ctx.db.insert(schema.simulationJobs).values({ userId: uid, homeTeamId: b.home_team_id, awayTeamId: b.away_team_id, homeTacticId: b.home_tactic_id || 1, awayTacticId: b.away_tactic_id || 1, matchCount: b.match_count, status: "pending", homeTacticalDocument: b.home_tactical_document || "", awayTacticalDocument: b.away_tactical_document || "" }).returning();
    ctx.respond(200, { job_id: job.id });
  },
  async simList(ctx) {
    const uid = auth(ctx); if (!uid) return;
    ctx.respond(200, await ctx.db.select().from(schema.simulationJobs).where(eq(schema.simulationJobs.userId, uid)).orderBy(desc(schema.simulationJobs.id)).limit(20));
  },
  async simGet(ctx) {
    const uid = auth(ctx); if (!uid) return;
    const [job] = await ctx.db.select().from(schema.simulationJobs).where(eq(schema.simulationJobs.id, +ctx.params.id));
    if (!job) return ctx.respond(404, {});
    ctx.respond(200, { ...job, results: await ctx.db.select().from(schema.simulationResults).where(eq(schema.simulationResults.jobId, job.id)) });
  },
  async simReplay(ctx) {
    const [r] = await ctx.db.select().from(schema.simulationResults).where(eq(schema.simulationResults.jobId, +ctx.params.id));
    r ? ctx.respond(200, { match_index: +ctx.params.idx, replay_path: r.replayPath }) : ctx.respond(404, {});
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

  health: (ctx) => ctx.respond(200, { status: "ok" }),
};

// ═══════════════════════════════════════════════════
// Router
// ═══════════════════════════════════════════════════

const routes = [
  ["POST","/api/v1/auth/google",handlers.authGoogle],["GET","/api/v1/auth/google/callback",handlers.health],
  ["POST","/api/v1/auth/logout",handlers.logout],
  ["GET","/api/v1/auth/me",handlers.me],["PUT","/api/v1/auth/settings",handlers.settings],
  ["GET","/api/v1/teams",handlers.teamList],["POST","/api/v1/teams",handlers.teamCreate],
  ["GET","/api/v1/teams/:id",handlers.teamGet],["DELETE","/api/v1/teams/:id",handlers.teamDel],
  ["POST","/api/v1/teams/:id/players",handlers.teamAddPlayer],["DELETE","/api/v1/teams/:id/players",handlers.teamRemovePlayer],
  ["GET","/api/v1/players",handlers.playerList],["POST","/api/v1/players",handlers.addPlayer],
  ["PUT","/api/v1/players/:id",handlers.updatePlayer],["DELETE","/api/v1/players/:id",handlers.delPlayer],
  ["GET","/api/v1/tactics",handlers.tacticList],["POST","/api/v1/tactics",handlers.tacticCreate],
  ["GET","/api/v1/tactics/:id",handlers.tacticGet],["PUT","/api/v1/tactics/:id",handlers.tacticUpdate],
  ["DELETE","/api/v1/tactics/:id",handlers.tacticDel],
  ["POST","/api/v1/simulate",handlers.simCreate],["GET","/api/v1/simulation/jobs",handlers.simList],
  ["GET","/api/v1/simulation/jobs/:id",handlers.simGet],["GET","/api/v1/simulation/jobs/:id/replay/:idx",handlers.simReplay],
  ["GET","/api/v1/analytics/job/:jobId",handlers.analytics],
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
    respond(status, data) {
      const h = { "Content-Type": "application/json; charset=utf-8" };
      if (_cookies.length) h["Set-Cookie"] = _cookies;
      res.writeHead(status, h);
      res.send(typeof data === "string" ? data : JSON.stringify(data));
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
