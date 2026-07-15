"use client";

import { useState, useEffect } from "react";
import { useTacticsStore } from "../../stores/tacticsStore";
import { api } from "../../lib/api";
import { FORMATIONS, PASSING_STYLES, BUILD_UP_STYLES, TACTIC_PRESETS } from "../../lib/constants";

export default function TacticsEditor() {
  const { currentTactic, isDirty, isSaving, newTactic, loadTactic, setFormation, setParam, applyPreset, saveTactic } = useTacticsStore();
  const [teams, setTeams] = useState<any[]>([]);
  const [tactics, setTactics] = useState<any[]>([]);
  const [selectedTeamId, setSelectedTeamId] = useState("");
  const [message, setMessage] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [analysis, setAnalysis] = useState<any>(null);

  useEffect(() => {
    api.getTeams().then(setTeams).catch(() => []);
    api.getTactics().then(setTactics).catch(() => []);
  }, []);

  const handleSave = async () => {
    try {
      if (!selectedTeamId) { setMessage("Select a team first."); return; }
      await saveTactic(Number(selectedTeamId));
      setMessage("Saved");
      setTimeout(() => setMessage(""), 2000);
    } catch (e: any) { setMessage("Error: " + e.message); }
  };

  if (!currentTactic) {
    return (
      <div className="max-w-2xl mx-auto py-12">
        <h1 className="text-2xl font-bold mb-6 text-stone-800">Tactics Editor</h1>
        <div className="space-y-3">
          <select className="w-full bg-white border border-stone-300 rounded-lg px-4 py-2.5 text-stone-700"
            onChange={(e) => { setSelectedTeamId(e.target.value); newTactic(Number(e.target.value)); }}
            value={selectedTeamId}>
            <option value="">Create new tactic (select team)...</option>
            {(Array.isArray(teams) ? teams : []).map((t: any) => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
          <p className="text-sm text-stone-400">or load existing:</p>
          {(Array.isArray(tactics) ? tactics : []).map((t: any) => (
            <button key={t.id} onClick={() => loadTactic(t.id)}
              className="block w-full text-left bg-white border border-stone-200 rounded-lg px-4 py-3 hover:border-green-700 transition-colors">
              <div className="font-medium text-stone-800">{t.name}</div>
              <div className="text-sm text-stone-400">{t.formation} · Pressing {t.pressingLevel}</div>
            </button>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-stone-800">{currentTactic.name || "New Tactic"}</h1>
        <div className="flex gap-3 items-center">
          {message && <span className={`text-sm ${message.startsWith("Error") ? "text-red-600" : "text-green-700"}`}>{message}</span>}
          {isDirty && <span className="text-xs text-amber-600 font-medium">Unsaved</span>}
          <button onClick={handleSave} disabled={isSaving}
            className="px-5 py-2 bg-green-700 text-white text-sm font-semibold hover:bg-green-800 disabled:opacity-50">
            {isSaving ? "Saving..." : "Save"}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        {[
          { label: "Formation", type: "select", key: "formation", options: FORMATIONS },
          { label: "Pressing Level", type: "range", key: "pressingLevel", min: 1, max: 10, left: "Sit back", right: "Gegenpress" },
          { label: "Defensive Line", type: "range", key: "defensiveLine", min: 1, max: 10, left: "Deep", right: "High" },
          { label: "Attacking Width", type: "range", key: "attackingWidth", min: 1, max: 10, left: "Narrow", right: "Wide" },
          { label: "Tempo", type: "range", key: "tempo", min: 1, max: 10, left: "Slow", right: "Fast" },
          { label: "Passing Style", type: "select", key: "passingStyle", options: PASSING_STYLES },
          { label: "Build-up Style", type: "select", key: "buildUpStyle", options: BUILD_UP_STYLES },
        ].map((f) => (
          <div key={f.key} className="bg-white border border-stone-200 rounded-lg p-4">
            <label className="text-sm text-stone-500 block mb-2">{f.label}
              {f.type === "range" && <span className="text-stone-800 font-bold ml-1">{(currentTactic as any)[f.key]}</span>}
            </label>
            {f.type === "select" ? (
              <select value={(currentTactic as any)[f.key]} onChange={(e) => setParam(f.key, e.target.value)}
                className="w-full bg-stone-50 border border-stone-200 rounded px-3 py-1.5 text-sm text-stone-700">
                {f.options?.map((o: string) => <option key={o} value={o}>{o}</option>)}
              </select>
            ) : (
              <>
                <input type="range" min={f.min} max={f.max} value={(currentTactic as any)[f.key]}
                  onChange={(e) => setParam(f.key, Number(e.target.value))}
                  className="w-full accent-green-700" />
                <div className="flex justify-between text-xs text-stone-400 mt-1"><span>{f.left}</span><span>{f.right}</span></div>
              </>
            )}
          </div>
        ))}
      </div>

      <div className="mt-4">
        <span className="text-sm text-stone-400 mr-2">Presets:</span>
        {Object.entries(TACTIC_PRESETS).map(([name, preset]) => (
          <button key={name} onClick={() => applyPreset(preset)}
            className="px-3 py-1 bg-white border border-stone-200 rounded text-xs text-stone-600 hover:border-green-700 mr-2 mb-2 transition-colors">
            {name}
          </button>
        ))}
      </div>

      {currentTactic?.id && (
        <div className="mt-6 bg-white border border-stone-200 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-base font-bold text-stone-800">AI Analysis</h3>
            <button onClick={() => {
              setAnalyzing(true);
              api.analyzeTactic(currentTactic.id).then((r: any) => { setAnalysis(r.result); setAnalyzing(false); }).catch(() => setAnalyzing(false));
            }} disabled={analyzing}
              className="px-4 py-1.5 bg-green-700 text-white text-sm font-medium hover:bg-green-800 disabled:opacity-50">
              {analyzing ? "Analyzing..." : analysis ? "Re-analyze" : "Analyze"}
            </button>
          </div>
          {analysis && !analysis.error && (
            <div>
              <p className="text-sm text-stone-700 italic mb-2">"{analysis.summary}"</p>
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div>
                  <h4 className="font-semibold text-green-700 mb-1">Strengths</h4>
                  {analysis.strengths?.map((s: any, i: number) => <p key={i} className="text-stone-500 text-xs mb-0.5"><b>{s.title}</b>: {s.description}</p>)}
                </div>
                <div>
                  <h4 className="font-semibold text-red-600 mb-1">Weaknesses</h4>
                  {analysis.weaknesses?.map((w: any, i: number) => <p key={i} className="text-stone-500 text-xs mb-0.5"><b>{w.title}</b>: {w.description}</p>)}
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
