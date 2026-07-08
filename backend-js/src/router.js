const { parse } = require("url");
const { getDb } = require("./database");
const { createTables } = require("./db/migrate");
const R = require("./routes");

const routes = [
  ["POST","/api/v1/auth/google",R.authGoogle],["POST","/api/v1/auth/logout",R.authLogout],
  ["GET","/api/v1/auth/me",R.authMe],["PUT","/api/v1/auth/settings",R.authSettings],
  ["GET","/api/v1/teams",R.teamList],["POST","/api/v1/teams",R.teamCreate],
  ["GET","/api/v1/teams/:id",R.teamGet],["DELETE","/api/v1/teams/:id",R.teamDel],
  ["POST","/api/v1/teams/:id/players",R.addPlayer],["DELETE","/api/v1/teams/players/:id",R.delPlayer],
  ["GET","/api/v1/tactics",R.tacticList],["POST","/api/v1/tactics",R.tacticCreate],
  ["GET","/api/v1/tactics/:id",R.tacticGet],["PUT","/api/v1/tactics/:id",R.tacticUpdate],
  ["DELETE","/api/v1/tactics/:id",R.tacticDel],
  ["POST","/api/v1/simulate",R.simCreate],["GET","/api/v1/simulation/jobs",R.simList],
  ["GET","/api/v1/simulation/jobs/:id",R.simGet],["GET","/api/v1/simulation/jobs/:id/replay/:idx",R.simReplay],
  ["GET","/api/v1/analytics/job/:jobId",R.analyticsGet],
  ["POST","/api/v1/agent/tactics/analyze",R.agentAnalyze],["POST","/api/v1/agent/match/report",R.agentReport],
  ["POST","/api/v1/agent/tactics/optimize",R.agentOptimize],["GET","/api/v1/agent/results",R.agentResults],
  ["GET","/api/v1/health",R.health],
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

function handleRequest(req, res) {
  const db = getDb();
  const pathname = parse(req.url || "/").pathname || "/";
  const method = (req.method || "GET").toUpperCase();

  // Collect cookies/headers; write all at once when res.writeHead is called
  let _cookies = [];
  const headers = {};

  const ctx = {
    db, req,
    parseBody() {
      if (!req.body) return {};
      try { return JSON.parse(req.body); } catch { return {}; }
    },
    getCookie(name) {
      const c = req.headers?.cookie || "";
      const m = c.match(new RegExp(`${name}=([^;]+)`));
      return m ? m[1] : null;
    },
    setCookie(name, value, opts = {}) {
      const p = [`${name}=${value}`, "HttpOnly", "Secure", "SameSite=Lax"];
      if (opts.maxAge) p.push(`Max-Age=${opts.maxAge}`);
      _cookies.push(p.join("; "));
    },
    clearCookie(name) {
      _cookies.push(`${name}=; Max-Age=0`);
    },
    respond(status, data) {
      res.statusCode = status;
      res.setHeader("Content-Type", "application/json; charset=utf-8");
      for (const c of _cookies) res.setHeader("Set-Cookie", c);
      res.send(typeof data === "string" ? data : JSON.stringify(data));
    },
  };

  for (const [m, path, handler] of routes) {
    if (m !== method) continue;
    const params = match(path, pathname);
    if (params) { ctx.params = params; handler(ctx); return; }
  }

  headers["Content-Type"] = "application/json; charset=utf-8";
  res.writeHead(404, headers);
  res.end(JSON.stringify({ detail: "Not found" }));
}

let _dbReady = false;
async function ensureDb() {
  if (!_dbReady) {
    _dbReady = true;
    try { await createTables(); } catch (e) { console.error("DB init failed:", e.message); }
  }
}

module.exports = { handleRequest, ensureDb };


