"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useSimulationStore } from "../../../stores/simulationStore";

export default function HistoryDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { activeJob, results, loadJob } = useSimulationStore();
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (id) {
      loadJob(+id).finally(() => setLoading(false));
    }
  }, [id]);

  if (loading) {
    return (
      <div className="max-w-5xl mx-auto">
        <div className="text-sm text-stone-400 py-20 text-center">Loading...</div>
      </div>
    );
  }

  if (!activeJob) {
    return (
      <div className="max-w-5xl mx-auto">
        <div className="text-sm text-stone-400 py-20 text-center">
          Job not found.{" "}
          <Link href="/history" className="text-green-700 font-medium hover:underline">Back to History →</Link>
        </div>
      </div>
    );
  }

  const matchResults = Array.isArray(results) ? results : [];

  return (
    <div className="max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <button onClick={() => router.back()}
            className="text-sm text-stone-400 hover:text-stone-700 mb-1">← Back</button>
          <h1 className="text-2xl font-bold text-stone-800">Simulation #{id}</h1>
        </div>
        <span className={`text-xs font-medium px-3 py-1 rounded-full ${
          activeJob.status === "completed" ? "bg-green-100 text-green-700" :
          activeJob.status === "running" ? "bg-blue-100 text-blue-700" :
          "bg-stone-100 text-stone-500"
        }`}>
          {activeJob.status}
        </span>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-4 gap-3 mb-6">
        <div className="bg-white border border-stone-200 rounded-lg p-4 text-center">
          <div className="text-xs text-stone-400 mb-1">Matches</div>
          <div className="text-2xl font-bold text-stone-800">{activeJob.match_count}</div>
        </div>
        <div className="bg-white border border-stone-200 rounded-lg p-4 text-center">
          <div className="text-xs text-stone-400 mb-1">Home Wins</div>
          <div className="text-2xl font-bold text-green-700">
            {matchResults.filter((r: any) => r.homeScore > r.awayScore).length}
          </div>
        </div>
        <div className="bg-white border border-stone-200 rounded-lg p-4 text-center">
          <div className="text-xs text-stone-400 mb-1">Draws</div>
          <div className="text-2xl font-bold text-stone-500">
            {matchResults.filter((r: any) => r.homeScore === r.awayScore).length}
          </div>
        </div>
        <div className="bg-white border border-stone-200 rounded-lg p-4 text-center">
          <div className="text-xs text-stone-400 mb-1">Away Wins</div>
          <div className="text-2xl font-bold text-red-600">
            {matchResults.filter((r: any) => r.awayScore > r.homeScore).length}
          </div>
        </div>
      </div>

      {/* Aggregate stats */}
      {matchResults.length > 0 && (
        <div className="grid grid-cols-3 gap-3 mb-6">
          {[
            { label: "Avg Home Goals", value: (matchResults.reduce((a: number, r: any) => a + r.homeScore, 0) / matchResults.length).toFixed(1) },
            { label: "Avg Away Goals", value: (matchResults.reduce((a: number, r: any) => a + r.awayScore, 0) / matchResults.length).toFixed(1) },
            { label: "Avg Home Possession", value: (matchResults.reduce((a: number, r: any) => a + (r.homePossession || 50), 0) / matchResults.length).toFixed(0) + "%" },
          ].map((s) => (
            <div key={s.label} className="bg-white border border-stone-200 rounded-lg p-3 text-center">
              <div className="text-xs text-stone-400">{s.label}</div>
              <div className="text-lg font-bold text-stone-800">{s.value}</div>
            </div>
          ))}
        </div>
      )}

      {/* Match-by-match table */}
      <div className="bg-white border border-stone-200 rounded-lg">
        <h2 className="text-lg font-bold p-5 pb-3 text-stone-800">
          Match Results
          {matchResults.length > 0 && (
            <span className="text-sm font-normal text-stone-400 ml-2">({matchResults.length} matches)</span>
          )}
        </h2>
        {matchResults.length === 0 ? (
          <p className="text-sm text-stone-400 py-10 text-center">
            {activeJob.status === "running" ? "Simulation in progress..." : "No results yet."}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-stone-400 border-b border-stone-100">
                  <th className="text-left py-2 px-5 font-medium w-10">#</th>
                  <th className="text-center py-2 font-medium">Home</th>
                  <th className="text-center py-2 font-medium w-16">Score</th>
                  <th className="text-center py-2 font-medium">Away</th>
                  <th className="text-center py-2 font-medium">xG</th>
                  <th className="text-center py-2 font-medium">Possession</th>
                  <th className="text-right py-2 px-5 font-medium"></th>
                </tr>
              </thead>
              <tbody>
                {matchResults.map((r: any, i: number) => {
                  const isHomeWin = r.homeScore > r.awayScore;
                  const isAwayWin = r.awayScore > r.homeScore;
                  return (
                    <tr key={i} className="border-b border-stone-50 hover:bg-stone-50">
                      <td className="py-2 px-5 text-stone-400 font-mono text-xs">{i + 1}</td>
                      <td className={`py-2 text-center font-semibold ${isHomeWin ? "text-green-700" : "text-stone-700"}`}>
                        {r.homeScore}
                      </td>
                      <td className="py-2 text-center text-stone-300">—</td>
                      <td className={`py-2 text-center font-semibold ${isAwayWin ? "text-red-600" : "text-stone-700"}`}>
                        {r.awayScore}
                      </td>
                      <td className="py-2 text-center text-stone-400 text-xs">
                        {r.homeXg?.toFixed(2)} / {r.awayXg?.toFixed(2)}
                      </td>
                      <td className="py-2 text-center text-stone-400 text-xs">
                        {r.homePossession?.toFixed(0)}% — {(100 - r.homePossession)?.toFixed(0)}%
                      </td>
                      <td className="py-2 px-5 text-right">
                        {r.replayPath && (
                          <button
                            onClick={async () => {
                              const api = (await import("../../../lib/api")).api;
                              try {
                                const data = await api.getReplay(+id, i);
                                alert(`Replay path: ${data.replay_path || data.signed_url}`);
                              } catch { alert("Failed to load replay"); }
                            }}
                            className="text-xs text-green-700 font-medium hover:underline"
                          >
                            Replay
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
