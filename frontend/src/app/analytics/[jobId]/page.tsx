"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { api } from "../../../lib/api";

export default function AnalyticsPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const [analytics, setAnalytics] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [reporting, setReporting] = useState(false);
  const [report, setReport] = useState<any>(null);

  useEffect(() => {
    if (!jobId) return;
    api.getJobAnalytics(Number(jobId)).then((data) => { setAnalytics(data); setLoading(false); }).catch(() => setLoading(false));
  }, [jobId]);

  if (loading) return <div className="text-center py-16 text-gray-400">Loading analytics...</div>;
  if (!analytics) return <div className="text-center py-16 text-gray-400">No data available.</div>;

  return (
    <div className="max-w-5xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Analytics</h1>

      <div className="grid grid-cols-5 gap-4 mb-8">
        {[
          { label: "Home Win Rate", value: `${(analytics.home_win_rate * 100).toFixed(0)}%` },
          { label: "Draw Rate", value: `${(analytics.draw_rate * 100).toFixed(0)}%` },
          { label: "Away Win Rate", value: `${(analytics.away_win_rate * 100).toFixed(0)}%` },
          { label: "Avg Goals (H/A)", value: `${analytics.avg_home_goals} / ${analytics.avg_away_goals}` },
          { label: "Avg Possession (H)", value: `${analytics.avg_home_possession}%` },
        ].map((stat) => (
          <div key={stat.label} className="bg-gray-900 rounded-xl p-4 border border-gray-800">
            <div className="text-xs text-gray-400">{stat.label}</div>
            <div className="text-xl font-bold mt-1">{stat.value}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-6">
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
          <h2 className="text-sm font-semibold text-gray-400 mb-3">xG Analysis</h2>
          <div className="space-y-3">
            <div className="flex justify-between"><span className="text-gray-400">Home xG</span><span className="font-bold">{analytics.avg_home_xg?.toFixed(4)}</span></div>
            <div className="flex justify-between"><span className="text-gray-400">Away xG</span><span className="font-bold">{analytics.avg_away_xg?.toFixed(4)}</span></div>
            <div className="flex justify-between"><span className="text-gray-400">Home Goals</span><span className="font-bold">{analytics.avg_home_goals}</span></div>
            <div className="flex justify-between"><span className="text-gray-400">xG Diff</span><span className={`font-bold ${analytics.avg_home_xg > analytics.avg_away_xg ? "text-emerald-400" : "text-red-400"}`}>
              {(analytics.avg_home_xg - analytics.avg_away_xg).toFixed(4)}
            </span></div>
          </div>
        </div>

        <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
          <h2 className="text-sm font-semibold text-gray-400 mb-3">Summary</h2>
          <div className="space-y-3">
            <div className="flex justify-between"><span className="text-gray-400">Matches</span><span className="font-bold">{analytics.match_count}</span></div>
            <div className="flex justify-between"><span className="text-gray-400">Possession (H)</span><span className="font-bold">{analytics.avg_home_possession}%</span></div>
            <div className="w-full bg-gray-800 rounded-full h-2 mt-1">
              <div className="bg-emerald-500 h-2 rounded-full" style={{ width: `${analytics.avg_home_possession}%` }} />
            </div>
          </div>
        </div>
      </div>

      {/* AI Report */}
      <div className="mt-6 bg-gray-900 rounded-xl border border-gray-800 p-4">
        <h2 className="text-lg font-semibold mb-3">AI Tactical Report</h2>
        <div className="flex gap-3 mb-4">
          <button
            onClick={() => {
              setReporting(true);
              api.generateReport(Number(jobId)).then((r: any) => { setReport(r.result); setReporting(false); }).catch(() => setReporting(false));
            }}
            disabled={reporting}
            className="px-4 py-2 bg-emerald-600 text-white rounded-lg text-sm hover:bg-emerald-500 disabled:opacity-50"
          >
            {reporting ? "Generating..." : report ? "Re-generate" : "Generate Report"}
          </button>
        </div>
        {report && !report.error && (
          <div className="space-y-4">
            <p className="text-sm font-semibold text-gray-200">{report.headline}</p>
            <div className="grid grid-cols-3 gap-3 text-xs">
              <div className="bg-gray-800 rounded-lg p-3">
                <h4 className="text-emerald-400 font-semibold mb-1">Attack</h4>
                <p className="text-gray-400">{report.attack_analysis?.effectiveness}</p>
              </div>
              <div className="bg-gray-800 rounded-lg p-3">
                <h4 className="text-blue-400 font-semibold mb-1">Possession</h4>
                <p className="text-gray-400">{report.possession_analysis?.retention}</p>
              </div>
              <div className="bg-gray-800 rounded-lg p-3">
                <h4 className="text-red-400 font-semibold mb-1">Defense</h4>
                <p className="text-gray-400">{report.defensive_analysis?.vulnerabilities?.join(", ")}</p>
              </div>
            </div>
            <div className="bg-emerald-500/10 border border-emerald-500/30 rounded-lg p-3">
              <p className="text-sm text-emerald-400 font-semibold">Key Insight</p>
              <p className="text-xs text-gray-300 mt-1">{report.key_insight}</p>
            </div>
          </div>
        )}
        {report?.error && <p className="text-red-400 text-sm">{report.error}</p>}
      </div>
    </div>
  );
}
