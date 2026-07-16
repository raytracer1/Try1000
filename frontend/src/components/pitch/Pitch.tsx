"use client";

import { useState } from "react";

// Horizontal pitch: 100 wide, 65 tall. Home attacks right (→), Away attacks left (←).
// x = horizontal position (0=left goal, 100=right goal)
// y = vertical position (0=top, 65=bottom)
const FORMATIONS: Record<string, { x: number; y: number }[]> = {
  "4-3-3": [
    { x: 5, y: 32 },  // GK
    { x: 20, y: 20 }, { x: 20, y: 44 },  // CB
    { x: 25, y: 6 }, { x: 25, y: 58 },   // LB/RB
    { x: 38, y: 32 },  // CDM
    { x: 52, y: 18 }, { x: 52, y: 46 },  // CM
    { x: 70, y: 8 }, { x: 70, y: 56 },   // LW/RW
    { x: 85, y: 32 },  // ST
  ],
  "4-4-2": [
    { x: 5, y: 32 }, { x: 20, y: 20 }, { x: 20, y: 44 }, { x: 25, y: 6 }, { x: 25, y: 58 },
    { x: 45, y: 10 }, { x: 45, y: 54 }, { x: 55, y: 22 }, { x: 55, y: 42 },
    { x: 78, y: 22 }, { x: 78, y: 42 },
  ],
  "3-5-2": [
    { x: 5, y: 32 }, { x: 20, y: 20 }, { x: 20, y: 44 }, { x: 28, y: 32 },
    { x: 45, y: 8 }, { x: 45, y: 56 }, { x: 52, y: 22 }, { x: 52, y: 42 }, { x: 40, y: 32 },
    { x: 80, y: 22 }, { x: 80, y: 42 },
  ],
  "4-2-3-1": [
    { x: 5, y: 32 }, { x: 20, y: 20 }, { x: 20, y: 44 }, { x: 25, y: 6 }, { x: 25, y: 58 },
    { x: 42, y: 22 }, { x: 42, y: 42 },
    { x: 60, y: 10 }, { x: 55, y: 32 }, { x: 60, y: 54 },
    { x: 85, y: 32 },
  ],
  "3-4-3": [
    { x: 5, y: 32 }, { x: 20, y: 20 }, { x: 20, y: 44 },
    { x: 40, y: 8 }, { x: 40, y: 56 }, { x: 48, y: 22 }, { x: 48, y: 42 },
    { x: 70, y: 10 }, { x: 70, y: 54 }, { x: 62, y: 22 }, { x: 62, y: 42 }, { x: 55, y: 32 },
  ],
};

const FORMATION_NAMES = ["4-3-3", "4-4-2", "3-5-2", "4-2-3-1", "3-4-3"];

const ROLES = ["GK", "CB", "CB", "LB", "RB", "CDM", "CM", "CM", "CAM", "LM", "RM", "LW", "RW", "CF", "ST", "LF", "RF", "LWB", "RWB"];

// Expected roles for each formation slot (index 0 = GK, then field players)
const SLOT_ROLES: Record<string, string[]> = {
  "4-3-3": ["GK", "CB", "CB", "LB", "RB", "CDM", "CM", "CM", "LW", "RW", "ST"],
  "4-4-2": ["GK", "CB", "CB", "LB", "RB", "RM", "CM", "CM", "LM", "ST", "ST"],
  "3-5-2": ["GK", "CB", "CB", "CB", "CM", "CM", "CM", "RM", "LM", "ST", "ST"],
  "4-2-3-1":["GK", "CB", "CB", "LB", "RB", "CDM","CDM","LW","CAM","RW","ST"],
  "3-4-3": ["GK", "CB", "CB", "CB", "CM","CM","LM","RM","LW","ST","RW"],
};

function matchRole(playerRole: string, slotRole: string): number {
  // Score how well a player fits a slot (lower = better)
  if (playerRole === slotRole) return 0;
  // Position groups
  const groups: Record<string, string[]> = {
    CB: ["CB","LCB","RCB"], LB: ["LB","LWB","RB","RWB"], RB: ["RB","RWB","LB","LWB"],
    CDM: ["CDM","CM"], CM: ["CM","CDM","CAM"], CAM: ["CAM","CM","CF"],
    LW: ["LW","LM","RW","RM"], RW: ["RW","RM","LW","LM"],
    LM: ["LM","LW","CM"], RM: ["RM","RW","CM"],
    ST: ["ST","CF","LW","RW"], CF: ["CF","ST"],
  };
  if (groups[slotRole]?.includes(playerRole)) return 1;
  return 2;
}

function assignPositions(players: any[], formation: string, flip: boolean) {
  const positions = FORMATIONS[formation] || FORMATIONS["4-3-3"];
  const slotRoles = SLOT_ROLES[formation] || SLOT_ROLES["4-3-3"];

  // Find GK
  const gk = players.find((p) => p.position === "GK");
  let remaining = players.filter((p) => p.position !== "GK");

  // Assign each slot (except GK)
  const assigned: any[] = new Array(11).fill(null);
  assigned[0] = gk;

  for (let slot = 1; slot < 11; slot++) {
    if (remaining.length === 0) break;
    // Find the best matching player for this slot
    let bestIdx = 0;
    let bestScore = Infinity;
    for (let j = 0; j < remaining.length; j++) {
      const score = matchRole(remaining[j].position, slotRoles[slot]);
      if (score < bestScore) { bestScore = score; bestIdx = j; }
    }
    assigned[slot] = remaining[bestIdx];
    remaining.splice(bestIdx, 1);
  }

  return assigned.filter(Boolean).map((p, i) => {
    let pos = positions[i] || { x: 50, y: 50 };
    if (flip) pos = { x: 100 - pos.x, y: pos.y };
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
