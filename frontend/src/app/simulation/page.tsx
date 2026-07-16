"use client";

import { useState, useEffect } from "react";
import { useSimulationStore } from "../../stores/simulationStore";
import { api } from "../../lib/api";

export default function SimulationPage() {
  const { activeJob, isRunning, results, startSimulation, cancelPolling } = useSimulationStore();
  const [clubs, setClubs] = useState<any[]>([]);
  const [nations, setNations] = useState<any[]>([]);
  const [searchH, setSearchH] = useState("");
  const [searchA, setSearchA] = useState("");
  const [home, setHome] = useState<any>(null);
  const [away, setAway] = useState<any>(null);
  const [homeTacticId, setHomeTacticId] = useState("");
  const [awayTacticId, setAwayTacticId] = useState("");
  const [tactics, setTactics] = useState<any[]>([]);
  const [matchCount, setMatchCount] = useState(10);
  const [filterH, setFilterH] = useState<"club" | "nation">("club");
  const [filterA, setFilterA] = useState<"club" | "nation">("club");
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch("/data/teams/clubs.json").then(r => r.json()).then(d => setClubs(d.teams || [])).catch(() => {});
    fetch("/data/teams/nations.json").then(r => r.json()).then(d => setNations(d.teams || [])).catch(() => {});
    api.getTactics().then(setTactics).catch(() => []);
  }, []);

  const loadTeam = async (t: any, side: "home" | "away") => {
    const resp = await fetch(`/data/teams/${t.file}`);
    const data = await resp.json();
    if (side === "home") { setHome(data); setSearchH(t.name); }
    else { setAway(data); setSearchA(t.name); }
  };

  const handleRun = async () => {
    if (!home || !away || !homeTacticId || !awayTacticId) {
      setError("Select both teams and tactics."); return;
    }
    setImporting(true);
    setError("");
    try {
      // Create teams and import players
      const finalHomeId = await importTeam(home);
      const finalAwayId = await importTeam(away);
      await startSimulation({
        home_team_id: finalHomeId, away_team_id: finalAwayId,
        home_tactic_id: Number(homeTacticId), away_tactic_id: Number(awayTacticId),
        match_count: matchCount,
      });
    } catch (e: any) { setError(e.message); }
    setImporting(false);
  };

  const importTeam = async (data: any): Promise<number> => {
    // Check if team exists
    const existingTeams = await api.getTeams();
    const existing = existingTeams.find((t: any) => t.name === data.name);
    let teamId = existing?.id;
    if (!teamId) {
      const created = await api.createTeam({ name: data.name });
      teamId = created.id;
      // Import players
      for (const p of data.players) {
        try {
          await api.addPlayer({ team_id: teamId, name: p.name, number: p.number || 0, position: p.position, attributes: p.attributes });
        } catch {}
      }
    }
    return teamId;
  };

  const PlayerList = ({ data }: { data: any }) => (
    <div className="text-xs text-stone-500 max-h-32 overflow-y-auto">
      {(data?.players || []).slice(0, 11).map((p: any) => (
        <div key={p.name} className="flex justify-between py-0.5 border-b border-stone-100">
          <span>{p.name}</span>
          <span className="text-stone-400">{p.position} · {p.overall}</span>
        </div>
      ))}
    </div>
  );

  return (
    <div className="max-w-5xl mx-auto">
      <h1 className="text-2xl font-bold mb-6 text-stone-800">Run Simulation</h1>

      <div className="grid grid-cols-2 gap-4 mb-6">
        {/* Home Team */}
        <div className="bg-white border border-stone-200 rounded-lg p-4">
          <label className="text-sm font-semibold text-stone-700 block mb-2">Home Team</label>
          <div className="flex gap-2 mb-2">
            <select className="text-xs bg-stone-50 border rounded px-2 py-1" value={filterH} onChange={(e) => { setFilterH(e.target.value as any); setHome(null); setSearchH(""); }}>
              <option value="club">Clubs</option>
              <option value="nation">Nations</option>
            </select>
            <input className="flex-1 bg-stone-50 border border-stone-200 rounded px-2 py-1 text-xs" placeholder="Search..."
              value={searchH} onChange={(e) => { setSearchH(e.target.value); setHome(null); }} />
          </div>
          <div className="max-h-40 overflow-y-auto mb-2 border rounded">
            {(filterH === "club" ? clubs : nations).filter(t => t.name.toLowerCase().includes(searchH.toLowerCase())).map((t: any) => (
              <button key={t.file} onClick={() => loadTeam(t, "home")}
                className={`block w-full text-left px-2 py-1 text-xs border-b border-stone-100 hover:bg-green-50 ${home?.name === t.name ? "bg-green-100" : ""}`}>
                {t.name} ({t.players}p)
              </button>
            ))}
          </div>
          <PlayerList data={home} />
          <label className="text-sm text-stone-600 block mt-3 mb-1">Tactic</label>
          <select className="w-full bg-stone-50 border border-stone-200 rounded px-3 py-2 text-sm" value={homeTacticId} onChange={(e) => setHomeTacticId(e.target.value)}>
            <option value="">Select...</option>
            {tactics.map((t: any) => <option key={t.id} value={t.id}>{t.name} ({t.formation})</option>)}
          </select>
        </div>

        {/* Away Team */}
        <div className="bg-white border border-stone-200 rounded-lg p-4">
          <label className="text-sm font-semibold text-stone-700 block mb-2">Away Team</label>
          <div className="flex gap-2 mb-2">
            <select className="text-xs bg-stone-50 border rounded px-2 py-1" value={filterA} onChange={(e) => { setFilterA(e.target.value as any); setAway(null); setSearchA(""); }}>
              <option value="club">Clubs</option>
              <option value="nation">Nations</option>
            </select>
            <input className="flex-1 bg-stone-50 border border-stone-200 rounded px-2 py-1 text-xs" placeholder="Search..."
              value={searchA} onChange={(e) => { setSearchA(e.target.value); setAway(null); }} />
          </div>
          <div className="max-h-40 overflow-y-auto mb-2 border rounded">
            {(filterA === "club" ? clubs : nations).filter(t => t.name.toLowerCase().includes(searchA.toLowerCase())).map((t: any) => (
              <button key={t.file} onClick={() => loadTeam(t, "away")}
                className={`block w-full text-left px-2 py-1 text-xs border-b border-stone-100 hover:bg-green-50 ${away?.name === t.name ? "bg-green-100" : ""}`}>
                {t.name} ({t.players}p)
              </button>
            ))}
          </div>
          <PlayerList data={away} />
          <label className="text-sm text-stone-600 block mt-3 mb-1">Tactic</label>
          <select className="w-full bg-stone-50 border border-stone-200 rounded px-3 py-2 text-sm" value={awayTacticId} onChange={(e) => setAwayTacticId(e.target.value)}>
            <option value="">Select...</option>
            {tactics.map((t: any) => <option key={t.id} value={t.id}>{t.name} ({t.formation})</option>)}
          </select>
        </div>
      </div>

      <div className="flex gap-3 items-center mb-6">
        {[1, 10, 100, 1000].map((n) => (
          <button key={n} onClick={() => setMatchCount(n)}
            className={`px-4 py-2 text-sm font-medium ${matchCount === n ? "bg-green-700 text-white" : "bg-white border border-stone-200 text-stone-600 hover:border-green-700"}`}>
            {n} {n === 1 ? "Match" : "Matches"}
          </button>
        ))}
        <button onClick={handleRun} disabled={isRunning || importing}
          className="px-6 py-2 bg-green-700 text-white text-sm font-semibold hover:bg-green-800 disabled:opacity-50 ml-auto">
          {importing ? "Importing..." : isRunning ? "Running..." : "Run"}
        </button>
        {isRunning && <button onClick={cancelPolling} className="px-4 py-2 border border-red-300 text-red-600 text-sm font-medium hover:bg-red-50">Cancel</button>}
      </div>
      {error && <p className="text-red-600 text-sm mb-4">{error}</p>}

      {activeJob && isRunning && (
        <div className="bg-white border border-stone-200 rounded-lg p-4 mb-6">
          <div className="flex justify-between text-sm mb-2"><span className="text-stone-500">Simulating...</span><span className="text-green-700 font-bold">{activeJob.progress}%</span></div>
          <div className="w-full bg-stone-200 rounded-full h-2"><div className="bg-green-700 h-2 rounded-full transition-all" style={{ width: `${activeJob.progress}%` }} /></div>
        </div>
      )}

      {results.length > 0 && (
        <div className="bg-white border border-stone-200 rounded-lg p-4">
          <h2 className="text-lg font-bold mb-3 text-stone-800">Results</h2>
          <div className="grid grid-cols-4 gap-3 mb-4">
            {[
              { label: "Home Wins", value: results.filter((r: any) => r.homeScore > r.awayScore).length },
              { label: "Draws", value: results.filter((r: any) => r.homeScore === r.awayScore).length },
              { label: "Away Wins", value: results.filter((r: any) => r.awayScore > r.homeScore).length },
              { label: "Total", value: results.length },
            ].map((s) => (
              <div key={s.label} className="bg-stone-50 rounded p-3 text-center">
                <div className="text-xs text-stone-400">{s.label}</div>
                <div className="text-xl font-bold text-stone-800">{s.value}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
