"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useSimulationStore } from "../../stores/simulationStore";

export default function Dashboard() {
  const { jobs, loadJobs } = useSimulationStore();

  useEffect(() => { loadJobs(); }, []);

  return (
    <div className="max-w-5xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Dashboard</h1>

      <div className="grid grid-cols-3 gap-4 mb-8">
        <Link href="/tactics" className="bg-gray-900 rounded-xl border border-gray-800 p-6 hover:border-emerald-500 transition-colors">
          <div className="text-3xl mb-3">⚽</div>
          <h2 className="text-lg font-semibold mb-1">Tactics Editor</h2>
          <p className="text-sm text-gray-400">Design formations and tactics</p>
        </Link>
        <Link href="/simulation" className="bg-gray-900 rounded-xl border border-gray-800 p-6 hover:border-emerald-500 transition-colors">
          <div className="text-3xl mb-3">▶️</div>
          <h2 className="text-lg font-semibold mb-1">Run Simulation</h2>
          <p className="text-sm text-gray-400">Test tactics across matches</p>
        </Link>
        <Link href="/settings" className="bg-gray-900 rounded-xl border border-gray-800 p-6 hover:border-emerald-500 transition-colors">
          <div className="text-3xl mb-3">⚙️</div>
          <h2 className="text-lg font-semibold mb-1">Settings</h2>
          <p className="text-sm text-gray-400">Configure AI and simulation</p>
        </Link>
      </div>

      <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
        <h2 className="text-lg font-semibold mb-3">Recent Simulations</h2>
        {!jobs || jobs.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <Link href="/simulation" className="text-emerald-400 hover:underline">Run your first simulation →</Link>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-gray-400 border-b border-gray-800">
                <th className="text-left py-2">Job</th><th className="text-left py-2">Matches</th>
                <th className="text-left py-2">Status</th><th className="text-left py-2">Progress</th>
              </tr>
            </thead>
            <tbody>
              {(Array.isArray(jobs) ? jobs : []).map((job: any) => (
                <tr key={job.id} className="border-b border-gray-800/50">
                  <td className="py-2 text-gray-300 font-mono text-xs">{String(job.id).slice(0, 8)}</td>
                  <td className="py-2">{job.matchCount}</td>
                  <td className="py-2">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      job.status === "completed" ? "bg-emerald-500/20 text-emerald-400" :
                      job.status === "running" ? "bg-blue-500/20 text-blue-400" : "bg-gray-500/20 text-gray-400"
                    }`}>{job.status}</span>
                  </td>
                  <td className="py-2">{job.progress}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
