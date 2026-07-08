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

  useEffect(() => {
    api.getTeams().then(setTeams).catch(() => {});
    api.getTactics().then(setTactics).catch(() => {});
  }, []);

  const handleSave = async () => {
    try {
      if (!selectedTeamId) { setMessage("Select a team first."); return; }
      await saveTactic(Number(selectedTeamId));
      setMessage("Saved!");
      setTimeout(() => setMessage(""), 2000);
    } catch (e: any) { setMessage("Error: " + e.message); }
  };

  if (!currentTactic) {
    return (
      <div className="max-w-2xl mx-auto text-center py-16">
        <p className="text-4xl mb-4">⚽</p>
        <h1 className="text-xl font-bold mb-4">Tactics Editor</h1>
        <div className="space-y-3">
          <select
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-gray-200"
            onChange={(e) => { setSelectedTeamId(e.target.value); newTactic(Number(e.target.value)); }}
            value={selectedTeamId}
          >
            <option value="">Create new tactic (select team)...</option>
            {teams.map((t: any) => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
          <p className="text-sm text-gray-500">or</p>
          {tactics.map((t: any) => (
            <button
              key={t.id}
              className="block w-full text-left bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 hover:border-emerald-500 transition-colors"
              onClick={() => loadTactic(t.id)}
            >
              <div className="font-medium">{t.name}</div>
              <div className="text-xs text-gray-400">{t.formation} · Pressing {t.pressing_level} · {t.passing_style}</div>
            </button>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">{currentTactic.name || "New Tactic"}</h1>
        <div className="flex gap-2 items-center">
          {message && <span className={`text-xs ${message.startsWith("Error") ? "text-red-400" : "text-emerald-400"}`}>{message}</span>}
          {isDirty && <span className="text-xs text-yellow-400">Unsaved</span>}
          <button onClick={handleSave} disabled={isSaving}
            className="px-4 py-1.5 bg-emerald-600 text-white rounded-lg text-sm hover:bg-emerald-500 disabled:opacity-50">
            {isSaving ? "Saving..." : "Save"}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Formation */}
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
          <label className="text-sm text-gray-400 block mb-2">Formation</label>
          <select value={currentTactic.formation} onChange={(e) => setFormation(e.target.value)}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-gray-200 text-sm">
            {FORMATIONS.map((f) => <option key={f} value={f}>{f}</option>)}
          </select>
        </div>

        {/* Pressing */}
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
          <label className="text-sm text-gray-400 block mb-2">Pressing Level: <span className="text-white font-bold">{currentTactic.pressing_level}</span></label>
          <input type="range" min={1} max={10} value={currentTactic.pressing_level}
            onChange={(e) => setParam("pressing_level", Number(e.target.value))}
            className="w-full accent-emerald-500" />
          <div className="flex justify-between text-xs text-gray-500"><span>1 (sit back)</span><span>10 (gegenpress)</span></div>
        </div>

        {/* Defensive Line */}
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
          <label className="text-sm text-gray-400 block mb-2">Defensive Line: <span className="text-white font-bold">{currentTactic.defensive_line}</span></label>
          <input type="range" min={1} max={10} value={currentTactic.defensive_line}
            onChange={(e) => setParam("defensive_line", Number(e.target.value))}
            className="w-full accent-emerald-500" />
          <div className="flex justify-between text-xs text-gray-500"><span>1 (deep)</span><span>10 (high)</span></div>
        </div>

        {/* Attacking Width */}
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
          <label className="text-sm text-gray-400 block mb-2">Attacking Width: <span className="text-white font-bold">{currentTactic.attacking_width}</span></label>
          <input type="range" min={1} max={10} value={currentTactic.attacking_width}
            onChange={(e) => setParam("attacking_width", Number(e.target.value))}
            className="w-full accent-emerald-500" />
          <div className="flex justify-between text-xs text-gray-500"><span>1 (narrow)</span><span>10 (wide)</span></div>
        </div>

        {/* Tempo */}
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
          <label className="text-sm text-gray-400 block mb-2">Tempo: <span className="text-white font-bold">{currentTactic.tempo}</span></label>
          <input type="range" min={1} max={10} value={currentTactic.tempo}
            onChange={(e) => setParam("tempo", Number(e.target.value))}
            className="w-full accent-emerald-500" />
          <div className="flex justify-between text-xs text-gray-500"><span>1 (slow)</span><span>10 (frantic)</span></div>
        </div>

        {/* Passing Style */}
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
          <label className="text-sm text-gray-400 block mb-2">Passing Style</label>
          <select value={currentTactic.passing_style} onChange={(e) => setParam("passing_style", e.target.value)}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-gray-200 text-sm">
            {PASSING_STYLES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>

        {/* Build-up Style */}
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
          <label className="text-sm text-gray-400 block mb-2">Build-up Style</label>
          <select value={currentTactic.build_up_style} onChange={(e) => setParam("build_up_style", e.target.value)}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-gray-200 text-sm">
            {BUILD_UP_STYLES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
      </div>

      {/* Presets */}
      <div className="mt-6">
        <h3 className="text-sm text-gray-400 mb-2">Quick Presets</h3>
        <div className="flex gap-2 flex-wrap">
          {Object.entries(TACTIC_PRESETS).map(([name, preset]) => (
            <button key={name}
              onClick={() => applyPreset(preset)}
              className="px-3 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-xs text-gray-300 hover:border-emerald-500 transition-colors">
              {name}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
