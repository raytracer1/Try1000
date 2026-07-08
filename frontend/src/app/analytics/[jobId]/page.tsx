"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { api } from "../../../lib/api";

export default function AnalyticsPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const [analytics, setAnalytics] = useState<any>(null);
  const [loading, setLoading] = useState(true);

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
    </div>
  );
}
