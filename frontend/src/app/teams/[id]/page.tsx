"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { api } from "../../../lib/api";

const POSITIONS = ["GK", "CB", "LB", "RB", "CDM", "CM", "CAM", "LW", "RW", "ST"];
const ATTRS = ["pace", "shooting", "passing", "dribbling", "defending", "physicality", "stamina", "awareness", "composure"];

const POSITION_DEFAULTS: Record<string, Record<string,number>> = {
  GK:  { pace: 50, shooting: 20, passing: 60, dribbling: 30, defending: 80, physicality: 70, stamina: 95, awareness: 80, composure: 75 },
  CB:  { pace: 70, shooting: 30, passing: 65, dribbling: 40, defending: 82, physicality: 78, stamina: 85, awareness: 75, composure: 70 },
  LB:  { pace: 80, shooting: 40, passing: 70, dribbling: 55, defending: 75, physicality: 65, stamina: 85, awareness: 70, composure: 70 },
  RB:  { pace: 80, shooting: 40, passing: 70, dribbling: 55, defending: 75, physicality: 65, stamina: 85, awareness: 70, composure: 70 },
  CDM: { pace: 65, shooting: 55, passing: 78, dribbling: 60, defending: 78, physicality: 75, stamina: 85, awareness: 78, composure: 75 },
  CM:  { pace: 70, shooting: 65, passing: 82, dribbling: 70, defending: 60, physicality: 65, stamina: 82, awareness: 78, composure: 78 },
  CAM: { pace: 75, shooting: 75, passing: 85, dribbling: 82, defending: 35, physicality: 55, stamina: 78, awareness: 82, composure: 82 },
  LW:  { pace: 90, shooting: 72, passing: 72, dribbling: 88, defending: 30, physicality: 52, stamina: 78, awareness: 72, composure: 70 },
  RW:  { pace: 90, shooting: 72, passing: 72, dribbling: 88, defending: 30, physicality: 52, stamina: 78, awareness: 72, composure: 70 },
  ST:  { pace: 82, shooting: 85, passing: 65, dribbling: 78, defending: 25, physicality: 68, stamina: 80, awareness: 75, composure: 82 },
};

export default function TeamDetail() {
  const { id } = useParams<{ id: string }>();
  const [team, setTeam] = useState<any>(null);
  const [showForm, setShowForm] = useState(false);
  const [editPlayer, setEditPlayer] = useState<any>(null);
  const [form, setForm] = useState({ name: "", number: "", position: "CM", attrs: {} as Record<string,number> });

  const load = () => api.getTeam(Number(id)).then(setTeam).catch(() => {});

  useEffect(() => { load(); }, [id]);

  const resetForm = () => {
    setShowForm(false);
    setEditPlayer(null);
    setForm({ name: "", number: "", position: "CM", attrs: {} });
  };

  const openAdd = () => {
    resetForm();
    setForm({ ...form, attrs: { ...POSITION_DEFAULTS["CM"] } });
    setShowForm(true);
  };

  const openEdit = (p: any) => {
    setEditPlayer(p);
    setForm({ name: p.name, number: String(p.number), position: p.position, attrs: p.attributes || { ...POSITION_DEFAULTS[p.position] || {} } });
    setShowForm(true);
  };

  const save = async () => {
    if (!form.name || !form.number) return;
    await api.addPlayer({
      team_id: Number(id),
      name: form.name,
      number: parseInt(form.number),
      position: form.position,
      attributes: form.attrs,
    });
    resetForm();
    load();
  };

  const del = async (playerId: number) => {
    await api.deletePlayer(playerId);
    load();
  };

  const updateAttr = (attr: string, value: number) => {
    setForm({ ...form, attrs: { ...form.attrs, [attr]: value } });
  };

  const setPosition = (pos: string) => {
    setForm({ ...form, position: pos, attrs: { ...POSITION_DEFAULTS[pos] } });
  };

  if (!team) return <div className="text-center py-12 text-stone-400">Loading...</div>;

  return (
    <div className="max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold mb-6 text-stone-800">{team.name}</h1>

      <div className="flex items-center justify-between mb-6">
        <span className="text-sm text-stone-400">{team.players?.length || 0} players</span>
        <button onClick={openAdd} className="px-4 py-2 bg-green-700 text-white text-sm font-semibold hover:bg-green-800">Add Player</button>
      </div>

      {showForm && (
        <div className="bg-white border border-stone-200 rounded-lg p-5 mb-6">
          <h3 className="text-base font-bold text-stone-800 mb-4">{editPlayer ? `Edit ${editPlayer.name}` : "New Player"}</h3>
          <div className="flex gap-3 mb-4">
            <input className="w-40 bg-stone-50 border border-stone-200 rounded px-3 py-2 text-sm" placeholder="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            <input className="w-16 bg-stone-50 border border-stone-200 rounded px-3 py-2 text-sm" placeholder="#" value={form.number} onChange={(e) => setForm({ ...form, number: e.target.value })} />
            <select className="w-24 bg-stone-50 border border-stone-200 rounded px-3 py-2 text-sm" value={form.position} onChange={(e) => setPosition(e.target.value)}>
              {POSITIONS.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
            <button onClick={save} className="px-5 py-2 bg-green-700 text-white text-sm font-semibold hover:bg-green-800">Save</button>
            <button onClick={resetForm} className="px-4 py-2 border border-stone-200 text-sm text-stone-500 rounded hover:bg-stone-50">Cancel</button>
          </div>
          <div className="grid grid-cols-3 gap-x-6 gap-y-2">
            {ATTRS.map((a) => (
              <div key={a} className="flex items-center gap-2">
                <span className="text-xs text-stone-500 w-24 capitalize text-right">{a}</span>
                <input type="range" min={1} max={99} value={form.attrs[a] ?? 70}
                  onChange={(e) => updateAttr(a, +e.target.value)} className="flex-1 accent-green-700 h-1" />
                <span className="text-xs text-stone-700 w-6">{form.attrs[a] ?? 70}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-3 gap-3">
        {(Array.isArray(team.players) ? team.players : []).map((p: any) => (
          <div key={p.id} className="bg-white border border-stone-200 rounded-lg p-3">
            <div className="flex items-center justify-between mb-2">
              <div>
                <div className="font-semibold text-stone-800 text-sm">{p.name}</div>
                <div className="text-xs text-stone-400">#{p.number} · {p.position}</div>
              </div>
              <div className="flex gap-2">
                <button onClick={() => openEdit(p)} className="text-xs text-stone-400 hover:text-green-700">Edit</button>
                <button onClick={() => del(p.id)} className="text-xs text-red-400 hover:underline">×</button>
              </div>
            </div>
            <div className="grid grid-cols-3 gap-x-2 gap-y-0.5 text-xs">
              {ATTRS.map((a) => (
                <div key={a} className="flex justify-between text-stone-400">
                  <span>{a.charAt(0).toUpperCase()}</span>
                  <span className="text-stone-600 font-mono">{p.attributes?.[a] ?? 70}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
