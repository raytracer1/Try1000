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
  const [matchCount, setMatchCount] = useState(10);
  const [filterH, setFilterH] = useState<"club" | "nation">("club");
  const [filterA, setFilterA] = useState<"club" | "nation">("club");
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch("/data/teams/clubs.json").then(r => r.json()).then(d => setClubs(d.teams || [])).catch(() => {});
    fetch("/data/teams/nations.json").then(r => r.json()).then(d => setNations(d.teams || [])).catch(() => {});
  }, []);

  const loadTeam = async (t: any, side: "home" | "away") => {
    const resp = await fetch(`/data/teams/${t.file}`);
    const data = await resp.json();
    data.logo = data.logo || "";
    if (side === "home") { setHome(data); setSearchH(t.name); }
    else { setAway(data); setSearchA(t.name); }
  };

  const TeamOption = ({ t, side, logoUrl }: { t: any; side: "home" | "away"; logoUrl?: string }) => {
    const sel = side === "home" ? home : away;
    return (
      <button onClick={() => loadTeam(t, side)}
        className={`flex items-center gap-2 w-full text-left px-3 py-2.5 text-base border-b border-stone-100 hover:bg-green-50 ${sel?.name === t.name ? "bg-green-100" : ""}`}>
        {logoUrl ? (logoUrl.startsWith("http") ? <img src={logoUrl} alt="" referrerPolicy="no-referrer" className="w-12 h-12 object-contain" /> : <span className="text-xl">{logoUrl}</span>) : <div className="w-12 h-12" />}
        <span className="flex-1 truncate text-base">{t.name}</span>
      </button>
    );
  };

  const handleRun = async () => {
    if (!home || !away) {
      setError("Select both teams."); return;
    }
    setImporting(true);
    setError("");
    try {
      // Create teams and import players
      const finalHomeId = await importTeam(home);
      const finalAwayId = await importTeam(away);
      await startSimulation({
        home_team_id: finalHomeId, away_team_id: finalAwayId,
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
    <div>
      <div className="text-base text-stone-500 max-h-96 overflow-y-auto">
        {(data?.players || []).map((p: any) => (
          <div key={p.name} className="flex items-center justify-between py-1.5 border-b border-stone-100">
            <div className="flex items-center gap-2">
              {p.image ? <img src={p.image} alt="" referrerPolicy="no-referrer" className="w-16 h-16 rounded-full object-cover bg-stone-200" /> : <div className="w-16 h-16 rounded-full bg-stone-200 flex items-center justify-center text-stone-400 font-bold text-base">{p.name.charAt(0)}</div>}
              <span className="text-lg">{p.name}</span>
            </div>
            <span className="text-stone-400 text-base">{p.position} · {p.overall}</span>
          </div>
        ))}
      </div>
    </div>
  );

  return (
    <div className="max-w-5xl mx-auto">
      <h1 className="text-2xl font-bold mb-6 text-stone-800">Run Simulation</h1>

      <div className="grid grid-cols-2 gap-4 mb-6">
        {/* Home Team */}
        <div className="bg-white border border-stone-200 rounded-lg p-4">
          <label className="text-base font-semibold text-stone-700 block mb-2">Home Team</label>
          <div className="flex gap-2 mb-2">
            <select className="text-sm bg-stone-50 border rounded px-2 py-1" value={filterH} onChange={(e) => { setFilterH(e.target.value as any); setHome(null); setSearchH(""); }}>
              <option value="club">Clubs</option>
              <option value="nation">Nations</option>
            </select>
            <input className="flex-1 bg-stone-50 border border-stone-200 rounded px-3 py-1.5 text-sm" placeholder="Search..."
              value={searchH} onChange={(e) => { setSearchH(e.target.value); setHome(null); }} />
          </div>
          <div className="max-h-96 overflow-y-auto mb-2 border rounded">
            {(filterH === "club" ? clubs : nations).filter(t => t.name.toLowerCase().includes(searchH.toLowerCase())).map((t: any) => (
              <TeamOption key={t.file} t={t} side="home" logoUrl={t.logo} />
            ))}
          </div>
          <PlayerList data={home} />
        </div>

        {/* Away Team */}
        <div className="bg-white border border-stone-200 rounded-lg p-4">
          <label className="text-base font-semibold text-stone-700 block mb-2">Away Team</label>
          <div className="flex gap-2 mb-2">
            <select className="text-sm bg-stone-50 border rounded px-2 py-1" value={filterA} onChange={(e) => { setFilterA(e.target.value as any); setAway(null); setSearchA(""); }}>
              <option value="club">Clubs</option>
              <option value="nation">Nations</option>
            </select>
            <input className="flex-1 bg-stone-50 border border-stone-200 rounded px-3 py-1.5 text-sm" placeholder="Search..."
              value={searchA} onChange={(e) => { setSearchA(e.target.value); setAway(null); }} />
          </div>
          <div className="max-h-96 overflow-y-auto mb-2 border rounded">
            {(filterA === "club" ? clubs : nations).filter(t => t.name.toLowerCase().includes(searchA.toLowerCase())).map((t: any) => (
              <TeamOption key={t.file} t={t} side="away" logoUrl={t.logo} />
            ))}
          </div>
          <PlayerList data={away} />
        </div>
      </div>

      <div className="flex gap-3 items-center mb-6">
        {[1, 10, 100, 1000].map((n) => (
          <button key={n} onClick={() => setMatchCount(n)}
            className={`px-4 py-2 text-base font-medium ${matchCount === n ? "bg-green-700 text-white" : "bg-white border border-stone-200 text-stone-600 hover:border-green-700"}`}>
            {n} {n === 1 ? "Match" : "Matches"}
          </button>
        ))}
        <button onClick={handleRun} disabled={isRunning || importing}
          className="px-6 py-2 bg-green-700 text-white text-base font-semibold hover:bg-green-800 disabled:opacity-50 ml-auto">
          {importing ? "Importing..." : isRunning ? "Running..." : "Run"}
        </button>
        {isRunning && <button onClick={cancelPolling} className="px-4 py-2 border border-red-300 text-red-600 text-base font-medium hover:bg-red-50">Cancel</button>}
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
