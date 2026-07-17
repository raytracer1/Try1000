"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useSimulationStore } from "../../stores/simulationStore";

function formatDate(ts: string) {
  if (!ts) return "";
  const d = new Date(ts);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })
    + " " + d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" });
}

export default function HistoryPage() {
  const { jobs, loadJobs } = useSimulationStore();

  useEffect(() => { loadJobs(); }, []);

  return (
    <div className="max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-stone-800">History</h1>
        <Link href="/simulation"
          className="px-4 py-2 bg-green-700 text-white text-sm font-semibold rounded hover:bg-green-800">
          + New Simulation
        </Link>
      </div>

      {/* Stats overview */}
      {jobs && jobs.length > 0 && (
        <div className="grid grid-cols-4 gap-3 mb-6">
          {[
            { label: "Total Jobs", value: jobs.length },
            { label: "Completed", value: jobs.filter((j: any) => j.status === "completed").length },
            { label: "Running", value: jobs.filter((j: any) => j.status === "running").length },
            { label: "Total Matches", value: jobs.reduce((a: number, j: any) => a + (j.match_count || 0), 0) },
          ].map((s) => (
            <div key={s.label} className="bg-white border border-stone-200 rounded-lg p-3 text-center">
              <div className="text-xs text-stone-400">{s.label}</div>
              <div className="text-lg font-bold text-stone-800">{s.value}</div>
            </div>
          ))}
        </div>
      )}

      {/* History table */}
      <div className="bg-white border border-stone-200 rounded-lg">
        <h2 className="text-lg font-bold p-5 pb-3 text-stone-800">Simulation History</h2>
        {!jobs || jobs.length === 0 ? (
          <p className="text-sm text-stone-400 py-10 text-center">
            No simulations yet.{" "}
            <Link href="/simulation" className="text-green-700 font-medium hover:underline">Run your first →</Link>
          </p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-stone-400 border-b border-stone-100">
                <th className="text-left py-2 px-5 font-medium">Date</th>
                <th className="text-left py-2 font-medium">Matches</th>
                <th className="text-left py-2 font-medium">Status</th>
                <th className="text-left py-2 font-medium">Result</th>
                <th className="text-right py-2 px-5 font-medium"></th>
              </tr>
            </thead>
            <tbody>
              {(Array.isArray(jobs) ? jobs : []).map((job: any) => (
                <tr key={job.id} className="border-b border-stone-50 hover:bg-stone-50">
                  <td className="py-2.5 px-5 text-stone-500 text-xs whitespace-nowrap">{formatDate(job.created_at)}</td>
                  <td className="py-2.5 text-stone-700 font-medium">{job.match_count}</td>
                  <td className="py-2.5">
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                      job.status === "completed" ? "bg-green-100 text-green-700" :
                      job.status === "running" ? "bg-blue-100 text-blue-700" :
                      job.status === "failed" ? "bg-red-100 text-red-700" :
                      "bg-stone-100 text-stone-500"
                    }`}>
                      {job.status}
                    </span>
                  </td>
                  <td className="py-2.5">
                    {job.status === "completed" && job.home_wins !== undefined ? (
                      <span className="text-xs">
                        <span className="text-green-700 font-medium">{job.home_wins}</span>
                        <span className="text-stone-300 mx-1">/</span>
                        <span className="text-stone-500">{job.draws}</span>
                        <span className="text-stone-300 mx-1">/</span>
                        <span className="text-red-600 font-medium">{job.away_wins}</span>
                        <span className="text-stone-400 ml-1">W/D/L</span>
                      </span>
                    ) : (
                      <span className="text-stone-300 text-xs">—</span>
                    )}
                  </td>
                  <td className="py-2.5 px-5 text-right">
                    {job.status === "completed" ? (
                      <Link href={`/history/${job.id}`}
                        className="text-xs text-green-700 font-medium hover:underline">
                        Details →
                      </Link>
                    ) : (
                      <span className="text-xs text-stone-300">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
