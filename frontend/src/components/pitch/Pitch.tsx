"use client";

import { useState } from "react";

const FORMATIONS: Record<string, { x: number; y: number }[]> = {
  "4-3-3": [
    { x: 5, y: 50 }, { x: 18, y: 28 }, { x: 18, y: 72 }, { x: 22, y: 8 }, { x: 22, y: 92 },
    { x: 35, y: 50 }, { x: 48, y: 30 }, { x: 48, y: 70 }, { x: 65, y: 12 }, { x: 65, y: 88 }, { x: 78, y: 50 },
  ],
  "4-4-2": [
    { x: 5, y: 50 }, { x: 18, y: 28 }, { x: 18, y: 72 }, { x: 22, y: 8 }, { x: 22, y: 92 },
    { x: 40, y: 20 }, { x: 40, y: 80 }, { x: 55, y: 30 }, { x: 55, y: 70 }, { x: 75, y: 38 }, { x: 75, y: 62 },
  ],
  "3-5-2": [
    { x: 5, y: 50 }, { x: 18, y: 28 }, { x: 18, y: 72 }, { x: 25, y: 50 },
    { x: 40, y: 12 }, { x: 40, y: 88 }, { x: 50, y: 35 }, { x: 50, y: 65 }, { x: 30, y: 50 },
    { x: 75, y: 35 }, { x: 75, y: 65 },
  ],
  "4-2-3-1": [
    { x: 5, y: 50 }, { x: 18, y: 28 }, { x: 18, y: 72 }, { x: 22, y: 8 }, { x: 22, y: 92 },
    { x: 38, y: 30 }, { x: 38, y: 70 },
    { x: 55, y: 15 }, { x: 50, y: 50 }, { x: 55, y: 85 },
    { x: 80, y: 50 },
  ],
  "3-4-3": [
    { x: 5, y: 50 }, { x: 18, y: 28 }, { x: 18, y: 72 },
    { x: 35, y: 12 }, { x: 35, y: 88 }, { x: 45, y: 35 }, { x: 45, y: 65 },
    { x: 65, y: 18 }, { x: 65, y: 82 }, { x: 75, y: 25 }, { x: 75, y: 75 }, { x: 53, y: 50 },
  ],
};

const FORMATION_NAMES = ["4-3-3", "4-4-2", "3-5-2", "4-2-3-1", "3-4-3"];

const ROLES = ["GK", "CB", "CB", "LB", "RB", "CDM", "CM", "CM", "LW", "RW", "ST"];

function assignPositions(players: any[], formation: string, flip: boolean) {
  const positions = FORMATIONS[formation] || FORMATIONS["4-3-3"];
  const sorted = [...players].sort((a, b) => {
    const ai = ROLES.indexOf(a.position);
    const bi = ROLES.indexOf(b.position);
    return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
  });
  return sorted.slice(0, 11).map((p, i) => {
    let pos = positions[i] || { x: 50, y: 50 };
    if (flip) pos = { x: 100 - pos.x, y: 100 - pos.y };
    return { ...p, px: pos.x, py: pos.y };
  });
}

export function Pitch({ homePlayers, awayPlayers }: { homePlayers: any[]; awayPlayers: any[] }) {
  const [homeForm, setHomeForm] = useState("4-3-3");
  const [awayForm, setAwayForm] = useState("4-3-3");
  const home = assignPositions(homePlayers, homeForm, false);
  const away = assignPositions(awayPlayers, awayForm, true);

  return (
    <div>
      <div className="flex items-center justify-between mb-2 gap-4">
        <div className="flex items-center gap-2">
          <span className="text-sm text-stone-500">Home:</span>
          <select value={homeForm} onChange={(e) => setHomeForm(e.target.value)}
            className="text-sm bg-white border border-stone-300 rounded px-2 py-1.5">
            {FORMATION_NAMES.map((f) => <option key={f} value={f}>{f}</option>)}
          </select>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-stone-500">Away:</span>
          <select value={awayForm} onChange={(e) => setAwayForm(e.target.value)}
            className="text-sm bg-white border border-stone-300 rounded px-2 py-1.5">
            {FORMATION_NAMES.map((f) => <option key={f} value={f}>{f}</option>)}
          </select>
        </div>
      </div>
      <div className="relative w-full bg-stone-100 rounded-lg overflow-hidden" style={{ paddingBottom: "62%" }}>
        <svg viewBox="0 0 100 65" className="absolute inset-0 w-full h-full" style={{ background: "#2d8a3e" }}>
          <rect x="1" y="1" width="98" height="63" fill="none" stroke="white" strokeWidth="0.25" opacity="0.7" />
          <line x1="50" y1="1" x2="50" y2="64" stroke="white" strokeWidth="0.25" opacity="0.4" />
          <circle cx="50" cy="32" r="6" fill="none" stroke="white" strokeWidth="0.25" opacity="0.4" />
          <rect x="1" y="17" width="16" height="31" fill="none" stroke="white" strokeWidth="0.25" opacity="0.5" />
          <rect x="83" y="17" width="16" height="31" fill="none" stroke="white" strokeWidth="0.25" opacity="0.5" />
          <rect x="1" y="25" width="6" height="15" fill="none" stroke="white" strokeWidth="0.25" opacity="0.4" />
          <rect x="93" y="25" width="6" height="15" fill="none" stroke="white" strokeWidth="0.25" opacity="0.4" />
          <rect x="-1" y="28" width="2" height="9" fill="none" stroke="white" strokeWidth="0.5" opacity="0.7" />
          <rect x="99" y="28" width="2" height="9" fill="none" stroke="white" strokeWidth="0.5" opacity="0.7" />
          <circle cx="12" cy="32" r="0.3" fill="white" opacity="0.4" />
          <circle cx="88" cy="32" r="0.3" fill="white" opacity="0.4" />

          {home.map((p: any) => (
            <g key={"h" + p.name}>
              <circle cx={p.px} cy={p.py} r={2.5} fill="#1a73e8" stroke="white" strokeWidth="0.3" />
              <text x={p.px} y={p.py + 0.7} textAnchor="middle" fill="white" fontSize="1.8" fontWeight="bold" fontFamily="sans-serif">{p.number || ""}</text>
              <text x={p.px} y={p.py + 4.2} textAnchor="middle" fill="white" fontSize="1.6" fontFamily="sans-serif">{p.name.length > 11 ? p.name.slice(0, 10) + "." : p.name}</text>
            </g>
          ))}
          {away.map((p: any) => (
            <g key={"a" + p.name}>
              <circle cx={p.px} cy={p.py} r={2.5} fill="#dc3545" stroke="white" strokeWidth="0.3" />
              <text x={p.px} y={p.py + 0.7} textAnchor="middle" fill="white" fontSize="1.8" fontWeight="bold" fontFamily="sans-serif">{p.number || ""}</text>
              <text x={p.px} y={p.py + 4.2} textAnchor="middle" fill="white" fontSize="1.6" fontFamily="sans-serif">{p.name.length > 11 ? p.name.slice(0, 10) + "." : p.name}</text>
            </g>
          ))}
        </svg>
        <div className="absolute bottom-2 left-2 flex gap-3 text-xs text-white bg-black/40 rounded px-3 py-1">
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-full bg-[#1a73e8] inline-block" /> Home</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-full bg-[#dc3545] inline-block" /> Away</span>
        </div>
      </div>
    </div>
  );
}
