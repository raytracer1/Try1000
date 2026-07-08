"use client";

import { useState, useEffect } from "react";
import { useSimulationStore } from "../../stores/simulationStore";
import { api } from "../../lib/api";

export default function SimulationPage() {
  const { activeJob, isRunning, results, startSimulation, loadJob, loadReplay, replayData, cancelPolling } = useSimulationStore();
  const [teams, setTeams] = useState<any[]>([]);
  const [tactics, setTactics] = useState<any[]>([]);
  const [homeTeamId, setHomeTeamId] = useState("");
  const [awayTeamId, setAwayTeamId] = useState("");
  const [homeTacticId, setHomeTacticId] = useState("");
  const [awayTacticId, setAwayTacticId] = useState("");
  const [matchCount, setMatchCount] = useState(10);
  const [selectedJobId, setSelectedJobId] = useState("");
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
    try {
      await startSimulation({ home_team_id: homeTeamId, away_team_id: awayTeamId, home_tactic_id: homeTacticId, away_tactic_id: awayTacticId, match_count: matchCount });
      setSelectedJobId("");
    } catch (e: any) { setError(e.message); }
  };

  return (
    <div className="max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Run Simulation</h1>

      {/* Setup */}
      <div className="grid grid-cols-2 gap-4 mb-6">
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
          <label className="text-sm text-gray-400 block mb-2">Home Team</label>
          <select className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200" value={homeTeamId} onChange={(e) => setHomeTeamId(e.target.value)}>
            <option value="">Select team...</option>
            {(teams || []).map((t: any) => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
          <label className="text-sm text-gray-400 block mb-2 mt-3">Home Tactic</label>
          <select className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200" value={homeTacticId} onChange={(e) => setHomeTacticId(e.target.value)}>
            <option value="">Select tactic...</option>
            {(tactics || []).map((t: any) => <option key={t.id} value={t.id}>{t.name} ({t.formation})</option>)}
          </select>
        </div>

        <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
          <label className="text-sm text-gray-400 block mb-2">Away Team</label>
          <select className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200" value={awayTeamId} onChange={(e) => setAwayTeamId(e.target.value)}>
            <option value="">Select team...</option>
            {(teams || []).map((t: any) => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
          <label className="text-sm text-gray-400 block mb-2 mt-3">Away Tactic</label>
          <select className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200" value={awayTacticId} onChange={(e) => setAwayTacticId(e.target.value)}>
            <option value="">Select tactic...</option>
            {(tactics || []).map((t: any) => <option key={t.id} value={t.id}>{t.name} ({t.formation})</option>)}
          </select>
        </div>
      </div>

      {/* Controls */}
      <div className="flex gap-3 items-center mb-6">
        {[1, 10, 100, 1000].map((n) => (
          <button key={n}
            onClick={() => setMatchCount(n)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              matchCount === n ? "bg-emerald-600 text-white" : "bg-gray-800 text-gray-400 hover:bg-gray-700"
            }`}>
            {n} {n === 1 ? "Match" : "Matches"}
          </button>
        ))}
        <button onClick={handleRun} disabled={isRunning}
          className="px-6 py-2 bg-emerald-600 text-white rounded-lg text-sm font-medium hover:bg-emerald-500 disabled:opacity-50 ml-auto">
          {isRunning ? "Running..." : "▶ Run"}
        </button>
        {isRunning && (
          <button onClick={cancelPolling} className="px-4 py-2 bg-red-600 text-white rounded-lg text-sm hover:bg-red-500">
            Cancel
          </button>
        )}
      </div>
      {error && <p className="text-red-400 text-sm mb-4">{error}</p>}

      {/* Progress */}
      {activeJob && isRunning && (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-4 mb-6">
          <div className="flex justify-between text-sm mb-2">
            <span className="text-gray-400">Simulating...</span>
            <span className="text-emerald-400 font-bold">{activeJob.progress}%</span>
          </div>
          <div className="w-full bg-gray-800 rounded-full h-2">
            <div className="bg-emerald-500 h-2 rounded-full transition-all" style={{ width: `${activeJob.progress}%` }} />
          </div>
        </div>
      )}

      {/* Results */}
      {results.length > 0 && (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
          <h2 className="text-lg font-semibold mb-3">Results</h2>
          <div className="grid grid-cols-4 gap-3 mb-4">
            {[
              { label: "Home Wins", value: results.filter((r: any) => r.home_score > r.away_score).length },
              { label: "Draws", value: results.filter((r: any) => r.home_score === r.away_score).length },
              { label: "Away Wins", value: results.filter((r: any) => r.away_score > r.home_score).length },
              { label: "Matches", value: results.length },
            ].map((s) => (
              <div key={s.label} className="bg-gray-800 rounded-lg p-3 text-center">
                <div className="text-xs text-gray-400">{s.label}</div>
                <div className="text-xl font-bold">{s.value}</div>
              </div>
            ))}
          </div>
          <div className="max-h-64 overflow-y-auto">
            {(results || []).slice(0, 20).map((r: any) => (
              <div key={r.match_index} className="flex justify-between py-1.5 border-b border-gray-800/50 text-sm">
                <span className="text-gray-400">#{r.match_index + 1}</span>
                <span className="text-gray-200">{r.home_score} — {r.away_score}</span>
                <span className="text-gray-500">xG {r.home_xg?.toFixed(2)} — {r.away_xg?.toFixed(2)}</span>
              </div>
            ))}
            {results.length > 20 && <p className="text-xs text-gray-500 mt-2">... and {results.length - 20} more matches</p>}
          </div>
        </div>
      )}
    </div>
  );
}
