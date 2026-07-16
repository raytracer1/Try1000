"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useSimulationStore } from "../../stores/simulationStore";

export default function Dashboard() {
  const { jobs, loadJobs } = useSimulationStore();
  useEffect(() => { loadJobs(); }, []);

  return (
    <div className="max-w-5xl mx-auto">
      <h1 className="text-2xl font-bold mb-6 text-stone-800">Dashboard</h1>

      <div className="grid grid-cols-1 gap-4 mb-8">
        {[
          { href: "/simulation", label: "Run Simulation", desc: "Test tactics across 1 to 1,000 matches" },
        ].map((c) => (
          <Link key={c.href} href={c.href}
            className="bg-white border border-stone-200 rounded-lg p-5 hover:border-green-700 transition-colors">
            <h2 className="text-base font-bold mb-1 text-stone-800">{c.label}</h2>
            <p className="text-sm text-stone-500">{c.desc}</p>
          </Link>
        ))}
      </div>

      <div className="bg-white border border-stone-200 rounded-lg p-5">
        <h2 className="text-lg font-bold mb-3 text-stone-800">Recent Simulations</h2>
        {!jobs || jobs.length === 0 ? (
          <p className="text-sm text-stone-400 py-6 text-center">
            <Link href="/simulation" className="text-green-700 font-medium hover:underline">Run your first simulation →</Link>
          </p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-stone-400 border-b border-stone-100">
                <th className="text-left py-2 font-medium">ID</th>
                <th className="text-left py-2 font-medium">Matches</th>
                <th className="text-left py-2 font-medium">Status</th>
                <th className="text-left py-2 font-medium">Progress</th>
              </tr>
            </thead>
            <tbody>
              {(Array.isArray(jobs) ? jobs : []).map((job: any) => (
                <tr key={job.id} className="border-b border-stone-50">
                  <td className="py-2 text-stone-500 font-mono text-xs">{String(job.id).slice(0, 8)}</td>
                  <td className="py-2 text-stone-700">{job.matchCount}</td>
                  <td className="py-2">
                    <span className={`text-xs font-medium ${
                      job.status === "completed" ? "text-green-700" :
                      job.status === "running" ? "text-blue-600" : "text-stone-400"
                    }`}>{job.status}</span>
                  </td>
                  <td className="py-2 text-stone-700">{job.progress}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
