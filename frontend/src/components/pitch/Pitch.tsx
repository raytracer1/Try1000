"use client";

const POSITIONS: Record<string, { x: number; y: number }[]> = {
  "4-3-3": [
    { x: 5, y: 50 },  // GK
    { x: 18, y: 28 }, { x: 18, y: 72 },  // CB
    { x: 22, y: 8 }, { x: 22, y: 92 },   // LB/RB
    { x: 35, y: 50 },  // CDM
    { x: 48, y: 30 }, { x: 48, y: 70 },  // CM
    { x: 65, y: 12 }, { x: 65, y: 88 },  // LW/RW
    { x: 78, y: 50 },  // ST
  ],
};

const ROLES = ["GK", "CB", "CB", "LB", "RB", "CDM", "CM", "CM", "LW", "RW", "ST"];

function assignPositions(players: any[], flip: boolean) {
  // Sort players by role priority
  const sorted = [...players].sort((a, b) => {
    const ai = ROLES.indexOf(a.position);
    const bi = ROLES.indexOf(b.position);
    return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
  });

  return sorted.slice(0, 11).map((p, i) => {
    let pos = POSITIONS["4-3-3"][i] || { x: 50, y: 50 };
    if (flip) { pos = { x: 100 - pos.x, y: 100 - pos.y }; }
    return { ...p, px: pos.x, py: pos.y };
  });
}

export function Pitch({ homePlayers, awayPlayers }: { homePlayers: any[]; awayPlayers: any[] }) {
  const home = assignPositions(homePlayers, false);
  const away = assignPositions(awayPlayers, true);

  return (
    <div className="relative w-full bg-stone-100 rounded-lg overflow-hidden" style={{ paddingBottom: "62%" }}>
      <svg viewBox="0 0 100 65" className="absolute inset-0 w-full h-full" style={{ background: "#2d8a3e" }}>
        {/* Pitch outline */}
        <rect x="1" y="1" width="98" height="63" fill="none" stroke="white" strokeWidth="0.25" opacity="0.7" />
        {/* Center line */}
        <line x1="50" y1="1" x2="50" y2="64" stroke="white" strokeWidth="0.25" opacity="0.4" />
        <circle cx="50" cy="32" r="6" fill="none" stroke="white" strokeWidth="0.25" opacity="0.4" />

        {/* Penalty areas */}
        <rect x="1" y="17" width="16" height="31" fill="none" stroke="white" strokeWidth="0.25" opacity="0.5" />
        <rect x="83" y="17" width="16" height="31" fill="none" stroke="white" strokeWidth="0.25" opacity="0.5" />
        <rect x="1" y="25" width="6" height="15" fill="none" stroke="white" strokeWidth="0.25" opacity="0.4" />
        <rect x="93" y="25" width="6" height="15" fill="none" stroke="white" strokeWidth="0.25" opacity="0.4" />

        {/* Goals */}
        <rect x="-1" y="28" width="2" height="9" fill="none" stroke="white" strokeWidth="0.5" opacity="0.7" />
        <rect x="99" y="28" width="2" height="9" fill="none" stroke="white" strokeWidth="0.5" opacity="0.7" />

        {/* Penalty spots */}
        <circle cx="12" cy="32" r="0.3" fill="white" opacity="0.4" />
        <circle cx="88" cy="32" r="0.3" fill="white" opacity="0.4" />

        {/* Home players (blue) */}
        {home.map((p: any) => (
          <g key={"h" + p.name}>
            <circle cx={p.px} cy={p.py} r={2.5} fill="#1a73e8" stroke="white" strokeWidth="0.3" />
            <text x={p.px} y={p.py + 0.7} textAnchor="middle" fill="white" fontSize="1.8" fontWeight="bold" fontFamily="sans-serif">
              {p.number || ""}
            </text>
            <text x={p.px} y={p.py + 4.2} textAnchor="middle" fill="white" fontSize="1.6" fontFamily="sans-serif">
              {p.name.length > 11 ? p.name.slice(0, 10) + "." : p.name}
            </text>
          </g>
        ))}

        {/* Away players (red) */}
        {away.map((p: any) => (
          <g key={"a" + p.name}>
            <circle cx={p.px} cy={p.py} r={2.5} fill="#dc3545" stroke="white" strokeWidth="0.3" />
            <text x={p.px} y={p.py + 0.7} textAnchor="middle" fill="white" fontSize="1.8" fontWeight="bold" fontFamily="sans-serif">
              {p.number || ""}
            </text>
            <text x={p.px} y={p.py + 4.2} textAnchor="middle" fill="white" fontSize="1.6" fontFamily="sans-serif">
              {p.name.length > 11 ? p.name.slice(0, 10) + "." : p.name}
            </text>
          </g>
        ))}
      </svg>

      {/* Legend */}
      <div className="absolute bottom-2 left-2 flex gap-3 text-xs text-white bg-black/40 rounded px-3 py-1">
        <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-full bg-[#1a73e8] inline-block" /> Home</span>
        <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-full bg-[#dc3545] inline-block" /> Away</span>
      </div>
    </div>
  );
}
