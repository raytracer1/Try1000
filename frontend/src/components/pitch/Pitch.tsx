"use client";

import { useState, useCallback, useRef } from "react";

const POSITIONS: Record<string, { x: number; y: number }[]> = {
  "4-3-3": [
    { x: 5, y: 32 }, { x: 20, y: 20 }, { x: 20, y: 44 }, { x: 25, y: 6 }, { x: 25, y: 58 },
    { x: 38, y: 32 }, { x: 52, y: 18 }, { x: 52, y: 46 }, { x: 70, y: 8 }, { x: 70, y: 56 }, { x: 85, y: 32 },
  ],
  "4-4-2": [
    { x: 5, y: 32 }, { x: 20, y: 20 }, { x: 20, y: 44 }, { x: 25, y: 6 }, { x: 25, y: 58 },
    { x: 45, y: 10 }, { x: 45, y: 54 }, { x: 55, y: 22 }, { x: 55, y: 42 }, { x: 78, y: 22 }, { x: 78, y: 42 },
  ],
  "3-5-2": [
    { x: 5, y: 32 }, { x: 20, y: 20 }, { x: 20, y: 44 }, { x: 28, y: 32 },
    { x: 45, y: 8 }, { x: 45, y: 56 }, { x: 52, y: 22 }, { x: 52, y: 42 }, { x: 40, y: 32 },
    { x: 80, y: 22 }, { x: 80, y: 42 },
  ],
  "4-2-3-1": [
    { x: 5, y: 32 }, { x: 20, y: 20 }, { x: 20, y: 44 }, { x: 25, y: 6 }, { x: 25, y: 58 },
    { x: 42, y: 22 }, { x: 42, y: 42 }, { x: 60, y: 10 }, { x: 55, y: 32 }, { x: 60, y: 54 }, { x: 85, y: 32 },
  ],
  "3-4-3": [
    { x: 5, y: 32 }, { x: 20, y: 20 }, { x: 20, y: 44 },
    { x: 40, y: 8 }, { x: 40, y: 56 }, { x: 48, y: 22 }, { x: 48, y: 42 },
    { x: 70, y: 10 }, { x: 70, y: 54 }, { x: 62, y: 22 }, { x: 62, y: 42 }, { x: 55, y: 32 },
  ],
};

const FORMATION_NAMES = ["4-3-3", "4-4-2", "3-5-2", "4-2-3-1", "3-4-3"];
const SLOT_ROLES: Record<string, string[]> = {
  "4-3-3": ["GK","CB","CB","LB","RB","CDM","CM","CM","LW","RW","ST"],
  "4-4-2": ["GK","CB","CB","LB","RB","RM","CM","CM","LM","ST","ST"],
  "3-5-2": ["GK","CB","CB","CB","CM","CM","CM","RM","LM","ST","ST"],
  "4-2-3-1":["GK","CB","CB","LB","RB","CDM","CDM","LW","CAM","RW","ST"],
  "3-4-3": ["GK","CB","CB","CB","CM","CM","LM","RM","LW","ST","RW"],
};

function matchRole(playerRole: string, slotRole: string): number {
  if (playerRole === slotRole) return 0;
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
  const formPos = POSITIONS[formation] || POSITIONS["4-3-3"];
  const slotRoles = SLOT_ROLES[formation] || SLOT_ROLES["4-3-3"];
  const gk = players.find((p: any) => p.position === "GK");
  let remaining = players.filter((p: any) => p.position !== "GK");
  const assigned: any[] = new Array(11);

  assigned[0] = gk ? { ...gk, px: flip ? (100 - formPos[0].x) : formPos[0].x, py: formPos[0].y } : null;

  for (let slot = 1; slot < 11; slot++) {
    if (remaining.length === 0) break;
    let bestI = 0, bestS = 99;
    for (let j = 0; j < remaining.length; j++) {
      const s = matchRole(remaining[j].position, slotRoles[slot]);
      if (s < bestS) { bestS = s; bestI = j; }
    }
    assigned[slot] = { ...remaining[bestI], px: flip ? (100 - formPos[slot].x) : formPos[slot].x, py: formPos[slot].y };
    remaining.splice(bestI, 1);
  }

  return { lineup: assigned.filter(Boolean), bench: remaining };
}

export function Pitch({ homePlayers, awayPlayers }: { homePlayers: any[]; awayPlayers: any[] }) {
  const [homeForm, setHomeForm] = useState("4-3-3");
  const [awayForm, setAwayForm] = useState("4-3-3");

  const homeInit = assignPositions(homePlayers, homeForm, false);
  const awayInit = assignPositions(awayPlayers, awayForm, true);

  const [homeLineup, setHomeLineup] = useState(homeInit.lineup);
  const [homeBench, setHomeBench] = useState(homeInit.bench);
  const [awayLineup, setAwayLineup] = useState(awayInit.lineup);
  const [awayBench, setAwayBench] = useState(awayInit.bench);

  const [dragging, setDragging] = useState<{ team: "home" | "away"; index: number } | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  // Reset when formation or players change
  const reset = useCallback(() => {
    const h = assignPositions(homePlayers, homeForm, false);
    setHomeLineup(h.lineup); setHomeBench(h.bench);
    const a = assignPositions(awayPlayers, awayForm, true);
    setAwayLineup(a.lineup); setAwayBench(a.bench);
  }, [homePlayers, awayPlayers, homeForm, awayForm]);

  const handleFormationChange = (team: "home" | "away", form: string) => {
    if (team === "home") setHomeForm(form); else setAwayForm(form);
    setTimeout(reset, 0);
  };

  // Drag handlers
  const handleMouseDown = (team: "home" | "away", index: number) => (e: React.MouseEvent) => {
    e.preventDefault();
    setDragging({ team, index });
  };

  const handleMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!dragging || !svgRef.current) return;
    const rect = svgRef.current.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * 100;
    const y = ((e.clientY - rect.top) / rect.height) * 65;
    const lineup = dragging.team === "home" ? [...homeLineup] : [...awayLineup];
    if (lineup[dragging.index]) {
      lineup[dragging.index] = { ...lineup[dragging.index], px: x, py: y };
      if (dragging.team === "home") setHomeLineup(lineup); else setAwayLineup(lineup);
    }
  };

  const handleMouseUp = () => setDragging(null);

  // Swap player between lineup and bench
  const swapPlayer = (team: "home" | "away", lineupIdx: number, benchIdx: number) => {
    if (team === "home") {
      const lineup = [...homeLineup], bench = [...homeBench];
      const temp = lineup[lineupIdx];
      lineup[lineupIdx] = bench[benchIdx];
      bench[benchIdx] = temp;
      setHomeLineup(lineup); setHomeBench(bench);
    } else {
      const lineup = [...awayLineup], bench = [...awayBench];
      const temp = lineup[lineupIdx];
      lineup[lineupIdx] = bench[benchIdx];
      bench[benchIdx] = temp;
      setAwayLineup(lineup); setAwayBench(bench);
    }
  };

  const renderPitch = (lineup: any[], color: string, team: "home" | "away") =>
    lineup.map((p: any, i: number) => (
      <g key={i} cursor="pointer" onMouseDown={handleMouseDown(team, i)}>
        <circle cx={p.px} cy={p.py} r={2.5} fill={color} stroke="white" strokeWidth="0.3" />
        <text x={p.px} y={p.py + 0.7} textAnchor="middle" fill="white" fontSize="1.8" fontWeight="bold" fontFamily="sans-serif">{p.number || i + 1}</text>
        <text x={p.px} y={p.py + 4.2} textAnchor="middle" fill="white" fontSize="1.6" fontFamily="sans-serif">{p.name.length > 11 ? p.name.slice(0, 10) + "." : p.name}</text>
      </g>
    ));

  const BenchPanel = ({ lineup, bench, team }: { lineup: any[]; bench: any[]; team: "home" | "away" }) => (
    <div className="text-xs mt-2">
      <div className="text-stone-500 font-medium mb-1">Starting XI: {lineup.length} | Bench: {bench.length}</div>
      <div className="flex flex-wrap gap-1">
        {bench.map((p: any, bi: number) => (
          <span key={bi} className="bg-stone-100 px-1.5 py-0.5 rounded cursor-pointer hover:bg-green-100 text-xs"
            onClick={() => { /* Select bench player to swap */ }}>
            {p.name} ({p.position})
          </span>
        ))}
      </div>
    </div>
  );

  return (
    <div>
      {/* Formation selectors */}
      <div className="flex items-center justify-between mb-2 gap-4">
        <div className="flex items-center gap-2">
          <span className="text-sm text-stone-500">Home:</span>
          <select value={homeForm} onChange={(e) => handleFormationChange("home", e.target.value)}
            className="text-sm bg-white border border-stone-300 rounded px-2 py-1.5">
            {FORMATION_NAMES.map((f) => <option key={f} value={f}>{f}</option>)}
          </select>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-stone-500">Away:</span>
          <select value={awayForm} onChange={(e) => handleFormationChange("away", e.target.value)}
            className="text-sm bg-white border border-stone-300 rounded px-2 py-1.5">
            {FORMATION_NAMES.map((f) => <option key={f} value={f}>{f}</option>)}
          </select>
        </div>
      </div>

      {/* Pitch */}
      <div className="relative w-full bg-stone-100 rounded-lg overflow-hidden" style={{ paddingBottom: "62%" }}>
        <svg ref={svgRef} viewBox="0 0 100 65" className="absolute inset-0 w-full h-full" style={{ background: "#2d8a3e" }}
          onMouseMove={handleMouseMove} onMouseUp={handleMouseUp} onMouseLeave={handleMouseUp}>
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
          {renderPitch(homeLineup, "#1a73e8", "home")}
          {renderPitch(awayLineup, "#dc3545", "away")}
        </svg>
        <div className="absolute bottom-2 left-2 flex gap-3 text-xs text-white bg-black/40 rounded px-3 py-1">
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-full bg-[#1a73e8] inline-block" /> Home</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-full bg-[#dc3545] inline-block" /> Away</span>
        </div>
      </div>

      {/* Bench panels */}
      <div className="grid grid-cols-2 gap-4 mt-2 text-xs text-stone-500">
        <BenchPanel lineup={homeLineup} bench={homeBench} team="home" />
        <BenchPanel lineup={awayLineup} bench={awayBench} team="away" />
      </div>
    </div>
  );
}
