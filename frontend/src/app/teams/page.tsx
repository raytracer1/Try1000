"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { api } from "../../lib/api";

export default function TeamsPage() {
  const [teams, setTeams] = useState<any[]>([]);
  const [name, setName] = useState("");

  const load = () => api.getTeams().then(setTeams).catch(() => []);

  useEffect(() => { load(); }, []);

  const createTeam = async () => {
    if (!name.trim()) return;
    await api.createTeam({ name });
    setName("");
    load();
  };

  const deleteTeam = async (id: number) => {
    await api.deleteTeam(id);
    load();
  };

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-6 text-stone-800">Teams</h1>

      <div className="flex gap-2 mb-8">
        <input
          className="flex-1 bg-white border border-stone-300 rounded px-4 py-2 text-sm"
          placeholder="Team name..."
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && createTeam()}
        />
        <button onClick={createTeam} className="px-4 py-2 bg-green-700 text-white text-sm font-semibold hover:bg-green-800">Create</button>
      </div>

      <div className="space-y-2">
        {(Array.isArray(teams) ? teams : []).map((team: any) => (
          <div key={team.id} className="bg-white border border-stone-200 rounded-lg p-4 flex items-center justify-between">
            <Link href={`/teams/${team.id}`} className="text-base font-semibold text-stone-800 hover:text-green-700 transition-colors">
              {team.name}
              <span className="text-xs text-stone-400 font-normal ml-2">{team.players?.length || 0} players</span>
            </Link>
            <button onClick={() => deleteTeam(team.id)} className="text-xs text-red-500 hover:underline">Delete</button>
          </div>
        ))}
      </div>
    </div>
  );
}
