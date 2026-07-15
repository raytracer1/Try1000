"use client";

import { useState, useEffect } from "react";
import { useSimulationStore } from "../../stores/simulationStore";
import { api } from "../../lib/api";

export default function SimulationPage() {
  const { activeJob, isRunning, results, startSimulation, cancelPolling } = useSimulationStore();
  const [teams, setTeams] = useState<any[]>([]);
  const [tactics, setTactics] = useState<any[]>([]);
  const [homeTeamId, setHomeTeamId] = useState("");
  const [awayTeamId, setAwayTeamId] = useState("");
  const [homeTacticId, setHomeTacticId] = useState("");
  const [awayTacticId, setAwayTacticId] = useState("");
  const [matchCount, setMatchCount] = useState(10);
  const [error, setError] = useState("");

  useEffect(() => {
    api.getTeams().then(setTeams).catch(() => []);
    api.getTactics().then(setTactics).catch(() => []);
  }, []);

  const handleRun = async () => {
    if (!homeTeamId || !awayTeamId || !homeTacticId || !awayTacticId) {
      setError("Select both teams and tactics."); return;
    }
    setError("");
    try { await startSimulation({ home_team_id: Number(homeTeamId), away_team_id: Number(awayTeamId), home_tactic_id: Number(homeTacticId), away_tactic_id: Number(awayTacticId), match_count: matchCount }); }
    catch (e: any) { setError(e.message); }
  };

  const teamOpts = (Array.isArray(teams) ? teams : []).map((t: any) => <option key={t.id} value={t.id}>{t.name}</option>);
  const tacticOpts = (Array.isArray(tactics) ? tactics : []).map((t: any) => <option key={t.id} value={t.id}>{t.name} ({t.formation})</option>);

  return (
    <div className="max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold mb-6 text-stone-800">Run Simulation</h1>

      <div className="grid grid-cols-2 gap-4 mb-6">
        <div className="bg-white border border-stone-200 rounded-lg p-4">
          <label className="text-sm text-stone-500 block mb-1">Home Team</label>
          <select className="w-full bg-stone-50 border border-stone-200 rounded px-3 py-2 text-sm text-stone-700 mb-3" value={homeTeamId} onChange={(e) => setHomeTeamId(e.target.value)}>
            <option value="">Select team...</option>{teamOpts}</select>
          <label className="text-sm text-stone-500 block mb-1">Home Tactic</label>
          <select className="w-full bg-stone-50 border border-stone-200 rounded px-3 py-2 text-sm text-stone-700" value={homeTacticId} onChange={(e) => setHomeTacticId(e.target.value)}>
            <option value="">Select tactic...</option>{tacticOpts}</select>
        </div>
        <div className="bg-white border border-stone-200 rounded-lg p-4">
          <label className="text-sm text-stone-500 block mb-1">Away Team</label>
          <select className="w-full bg-stone-50 border border-stone-200 rounded px-3 py-2 text-sm text-stone-700 mb-3" value={awayTeamId} onChange={(e) => setAwayTeamId(e.target.value)}>
            <option value="">Select team...</option>{teamOpts}</select>
          <label className="text-sm text-stone-500 block mb-1">Away Tactic</label>
          <select className="w-full bg-stone-50 border border-stone-200 rounded px-3 py-2 text-sm text-stone-700" value={awayTacticId} onChange={(e) => setAwayTacticId(e.target.value)}>
            <option value="">Select tactic...</option>{tacticOpts}</select>
        </div>
      </div>

      <div className="flex gap-3 items-center mb-6">
        {[1, 10, 100, 1000].map((n) => (
          <button key={n} onClick={() => setMatchCount(n)}
            className={`px-4 py-2 text-sm font-medium transition-colors ${matchCount === n ? "bg-green-700 text-white" : "bg-white border border-stone-200 text-stone-600 hover:border-green-700"}`}>
            {n} {n === 1 ? "Match" : "Matches"}
          </button>
        ))}
        <button onClick={handleRun} disabled={isRunning}
          className="px-6 py-2 bg-green-700 text-white text-sm font-semibold hover:bg-green-800 disabled:opacity-50 ml-auto">
          {isRunning ? "Running..." : "Run"}
        </button>
        {isRunning && <button onClick={cancelPolling} className="px-4 py-2 border border-red-300 text-red-600 text-sm font-medium hover:bg-red-50">Cancel</button>}
      </div>
      {error && <p className="text-red-600 text-sm mb-4">{error}</p>}

      {activeJob && isRunning && (
        <div className="bg-white border border-stone-200 rounded-lg p-4 mb-6">
          <div className="flex justify-between text-sm mb-2">
            <span className="text-stone-500">Simulating...</span>
            <span className="text-green-700 font-bold">{activeJob.progress}%</span>
          </div>
          <div className="w-full bg-stone-200 rounded-full h-2">
            <div className="bg-green-700 h-2 rounded-full transition-all" style={{ width: `${activeJob.progress}%` }} />
          </div>
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
              { label: "Matches", value: results.length },
            ].map((s) => (
              <div key={s.label} className="bg-stone-50 rounded p-3 text-center">
                <div className="text-xs text-stone-400">{s.label}</div>
                <div className="text-xl font-bold text-stone-800">{s.value}</div>
              </div>
            ))}
          </div>
          <div className="max-h-64 overflow-y-auto text-sm">
            {(Array.isArray(results) ? results : []).slice(0, 20).map((r: any) => (
              <div key={r.matchIndex} className="flex justify-between py-1.5 border-b border-stone-100">
                <span className="text-stone-400">#{r.matchIndex + 1}</span>
                <span className="text-stone-800">{r.homeScore} - {r.awayScore}</span>
                <span className="text-stone-400">xG {Number(r.homeXg).toFixed(2)} - {Number(r.awayXg).toFixed(2)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
