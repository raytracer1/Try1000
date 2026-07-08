"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useSimulationStore } from "../stores/simulationStore";

export default function Dashboard() {
  const { jobs, loadJobs } = useSimulationStore();

  useEffect(() => { loadJobs(); }, []);

  return (
    <div className="max-w-5xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Dashboard</h1>

      <div className="grid grid-cols-4 gap-4 mb-8">
        {[
          { label: "Win Rate", value: "—", sub: "from simulations" },
          { label: "Avg xG", value: "—", sub: "per match" },
          { label: "Possession", value: "—", sub: "avg %" },
          { label: "Simulations", value: String(jobs.length), sub: "total jobs" },
        ].map((stat) => (
          <div key={stat.label} className="bg-gray-900 rounded-xl p-4 border border-gray-800">
            <div className="text-sm text-gray-400">{stat.label}</div>
            <div className="text-2xl font-bold mt-1">{stat.value}</div>
            <div className="text-xs text-gray-500 mt-1">{stat.sub}</div>
          </div>
        ))}
      </div>

      <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
        <h2 className="text-lg font-semibold mb-3">Recent Simulations</h2>
        {jobs.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <p className="text-4xl mb-2">⚽</p>
            <p>No simulations yet.</p>
            <Link href="/simulation" className="text-emerald-400 hover:underline mt-2 inline-block">
              Run your first simulation →
            </Link>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-gray-400 border-b border-gray-800">
                <th className="text-left py-2">Job</th>
                <th className="text-left py-2">Matches</th>
                <th className="text-left py-2">Status</th>
                <th className="text-left py-2">Progress</th>
                <th className="text-left py-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {(Array.isArray(jobs) ? jobs : []).map((job: any) => (
                <tr key={job.id} className="border-b border-gray-800/50">
                  <td className="py-2 text-gray-300 font-mono text-xs">{job.id?.slice(0, 8)}...</td>
                  <td className="py-2">{job.match_count}</td>
                  <td className="py-2">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      job.status === "completed" ? "bg-emerald-500/20 text-emerald-400" :
                      job.status === "running" ? "bg-blue-500/20 text-blue-400" :
                      job.status === "failed" ? "bg-red-500/20 text-red-400" :
                      "bg-gray-500/20 text-gray-400"
                    }`}>{job.status}</span>
                  </td>
                  <td className="py-2">{job.progress}%</td>
                  <td className="py-2">
                    {job.status === "completed" && (
                      <Link href={`/analytics/${job.id}`} className="text-emerald-400 hover:underline text-xs">
                        View
                      </Link>
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
