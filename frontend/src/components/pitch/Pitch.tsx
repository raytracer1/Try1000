"use client";

import { useState, useCallback, useRef } from "react";

/* ── Formations ── */
// All positions in left half (0-50). flip=true mirrors to right half.
const POSITIONS: Record<string, { x: number; y: number }[]> = {
  "4-3-3": [{x:5,y:32},{x:18,y:20},{x:18,y:44},{x:22,y:6},{x:22,y:58},{x:32,y:32},{x:40,y:18},{x:40,y:46},{x:46,y:8},{x:46,y:56},{x:50,y:32}],
  "4-4-2": [{x:5,y:32},{x:18,y:20},{x:18,y:44},{x:22,y:6},{x:22,y:58},{x:32,y:10},{x:32,y:54},{x:42,y:22},{x:42,y:42},{x:48,y:22},{x:48,y:42}],
  "3-5-2": [{x:5,y:32},{x:18,y:20},{x:18,y:44},{x:24,y:32},{x:32,y:8},{x:32,y:56},{x:38,y:22},{x:38,y:42},{x:30,y:32},{x:48,y:22},{x:48,y:42}],
  "4-2-3-1":[{x:5,y:32},{x:18,y:20},{x:18,y:44},{x:22,y:6},{x:22,y:58},{x:34,y:22},{x:34,y:42},{x:42,y:10},{x:40,y:32},{x:42,y:54},{x:50,y:32}],
  "3-4-3": [{x:5,y:32},{x:18,y:20},{x:18,y:44},{x:30,y:8},{x:30,y:56},{x:36,y:22},{x:36,y:42},{x:44,y:10},{x:44,y:54},{x:42,y:22},{x:42,y:42},{x:39,y:32}],
};
const SLOT_ROLES: Record<string, string[]> = {
  "4-3-3":["GK","CB","CB","LB","RB","CDM","CM","CM","LW","RW","ST"],
  "4-4-2":["GK","CB","CB","LB","RB","RM","CM","CM","LM","ST","ST"],
  "3-5-2":["GK","CB","CB","CB","CM","CM","CM","RM","LM","ST","ST"],
  "4-2-3-1":["GK","CB","CB","LB","RB","CDM","CDM","LW","CAM","RW","ST"],
  "3-4-3":["GK","CB","CB","CB","CM","CM","LM","RM","LW","ST","RW"],
};
const FORMATION_NAMES = ["4-3-3","4-4-2","3-5-2","4-2-3-1","3-4-3"];

function matchRole(pr: string, sr: string): number {
  if (pr === sr) return 0;
  const g: Record<string, string[]> = {
    CB:["CB","LCB","RCB"],LB:["LB","LWB","RB","RWB"],RB:["RB","RWB","LB","LWB"],
    CDM:["CDM","CM"],CM:["CM","CDM","CAM"],CAM:["CAM","CM","CF"],
    LW:["LW","LM","RW","RM"],RW:["RW","RM","LW","LM"],LM:["LM","LW","CM"],RM:["RM","RW","CM"],
    ST:["ST","CF","LW","RW"],CF:["CF","ST"],
  };
  return g[sr]?.includes(pr) ? 1 : 2;
}

function assign(players: any[], form: string, flip: boolean) {
  const pos = POSITIONS[form] || POSITIONS["4-3-3"];
  const sr = SLOT_ROLES[form] || SLOT_ROLES["4-3-3"];
  const gk = players.find((p: any) => p.position === "GK");
  let rem = players.filter((p: any) => p.position !== "GK");
  const a: any[] = new Array(11);
  a[0] = gk ? { ...gk, px: flip ? (100 - pos[0].x) : pos[0].x, py: pos[0].y } : null;
  for (let s = 1; s < 11; s++) {
    if (!rem.length) break;
    let bi = 0, bs = 99;
    for (let j = 0; j < rem.length; j++) { const sc = matchRole(rem[j].position, sr[s]); if (sc < bs) { bs = sc; bi = j; } }
    a[s] = { ...rem[bi], px: flip ? (100 - pos[s].x) : pos[s].x, py: pos[s].y };
    rem.splice(bi, 1);
  }
  return { lineup: a.filter(Boolean), bench: rem };
}

/* ── Component ── */
export function Pitch({ homePlayers, awayPlayers, homeFormation, awayFormation, onHomeFormationChange, onAwayFormationChange }: {
  homePlayers: any[]; awayPlayers: any[];
  homeFormation?: string; awayFormation?: string;
  onHomeFormationChange?: (f: string) => void; onAwayFormationChange?: (f: string) => void;
}) {
  const [homeForm, setHomeForm] = useState(homeFormation || "4-3-3");
  const [awayForm, setAwayForm] = useState(awayFormation || "4-3-3");

  const hi = assign(homePlayers, homeForm, false);
  const ai = assign(awayPlayers, awayForm, true);
  const [homeL, setHomeL] = useState(hi.lineup);
  const [homeB, setHomeB] = useState(hi.bench);
  const [awayL, setAwayL] = useState(ai.lineup);
  const [awayB, setAwayB] = useState(ai.bench);

  // Drag state
  const [drag, setDrag] = useState<{ t: "h" | "a"; i: number } | null>(null);
  // Sub picker state
  const [sub, setSub] = useState<{ t: "h" | "a"; i: number; clientX: number; clientY: number } | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const pitchRef = useRef<HTMLDivElement>(null);

  const reapplyFormation = (lineup: any[], form: string, flip: boolean) => {
    const pos = POSITIONS[form] || POSITIONS["4-3-3"];
    return lineup.map((p, i) => {
      const pt = pos[i] || { x: 50, y: 32 };
      return { ...p, px: flip ? (100 - pt.x) : pt.x, py: pt.y };
    });
  };

  // ── Mouse events ──
  const onDown = (t: "h" | "a", i: number) => (e: React.MouseEvent) => {
    e.preventDefault();
    setDrag({ t, i });
  };

  const onMove = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!drag || !svgRef.current) return;
    const r = svgRef.current.getBoundingClientRect();
    const x = ((e.clientX - r.left) / r.width) * 100;
    const y = ((e.clientY - r.top) / r.height) * 65;
    const L = drag.t === "h" ? [...homeL] : [...awayL];
    L[drag.i] = { ...L[drag.i], px: x, py: y };
    drag.t === "h" ? setHomeL(L) : setAwayL(L);
  };

  const onUp = () => setDrag(null);

  const onDblClick = (t: "h" | "a", i: number) => (e: React.MouseEvent) => {
    e.preventDefault();
    if (!svgRef.current) return;
    const svgRect = svgRef.current.getBoundingClientRect();
    const lineup = t === "h" ? homeL : awayL;
    const p = lineup[i];
    if (!p) return;
    const cx = svgRect.left + (p.px / 100) * svgRect.width;
    const cy = svgRect.top + (p.py / 65) * svgRect.height;
    // Position popup to the side with more space
    const toRight = svgRect.right - cx > 180;
    const toBottom = svgRect.bottom - cy > 200;
    setSub({ t, i, clientX: toRight ? cx : cx - 180, clientY: toBottom ? cy : cy - 200 });
  };

  const doSwap = (benchIdx: number) => {
    if (!sub) return;
    const { t, i } = sub;
    if (t === "h") {
      const L = [...homeL], B = [...homeB];
      const oldPx = L[i].px, oldPy = L[i].py;
      B[benchIdx] = { ...B[benchIdx], px: oldPx, py: oldPy };
      [L[i], B[benchIdx]] = [B[benchIdx], L[i]];
      setHomeL(L); setHomeB(B);
    } else {
      const L = [...awayL], B = [...awayB];
      const oldPx = L[i].px, oldPy = L[i].py;
      B[benchIdx] = { ...B[benchIdx], px: oldPx, py: oldPy };
      [L[i], B[benchIdx]] = [B[benchIdx], L[i]];
      setAwayL(L); setAwayB(B);
    }
    setSub(null);
  };

  // ── Render ──
  const players = (L: any[], color: string, t: "h" | "a") =>
    L.map((p: any, i: number) => (
      <g key={i} cursor="pointer" onMouseDown={onDown(t, i)} onDoubleClick={onDblClick(t, i)}>
        <circle cx={p.px} cy={p.py} r={2.8} fill={color} stroke="white" strokeWidth="0.3" />
        <text x={p.px} y={p.py + 0.7} textAnchor="middle" fill="white" fontSize="1.8" fontWeight="bold" fontFamily="sans-serif">{p.number || i + 1}</text>
        <text x={p.px} y={p.py + 4.5} textAnchor="middle" fill="white" fontSize="1.6" fontFamily="sans-serif">{p.name.length > 11 ? p.name.slice(0, 10) + "." : p.name}</text>
        {sub && sub.t === t && sub.i === i && (
          <circle cx={p.px} cy={p.py} r={3.5} fill="none" stroke="yellow" strokeWidth="0.5" strokeDasharray="2,1" />
        )}
      </g>
    ));

  const bench = sub ? (sub.t === "h" ? homeB : awayB) : [];

  return (
    <div>
      {/* Formation selectors */}
      <div className="flex items-center justify-between mb-2 gap-4">
        <div className="flex items-center gap-2">
          <span className="text-sm text-stone-500">Home:</span>
          <select value={homeForm} onChange={(e) => { const f = e.target.value; setHomeForm(f); onHomeFormationChange?.(f); setTimeout(() => setHomeL(prev => reapplyFormation(prev, f, false)), 0); }}
            className="text-sm bg-white border border-stone-300 rounded px-2 py-1.5">
            {FORMATION_NAMES.map((f) => <option key={f} value={f}>{f}</option>)}
          </select>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-stone-500">Away:</span>
          <select value={awayForm} onChange={(e) => { const f = e.target.value; setAwayForm(f); onAwayFormationChange?.(f); setTimeout(() => setAwayL(prev => reapplyFormation(prev, f, true)), 0); }}
            className="text-sm bg-white border border-stone-300 rounded px-2 py-1.5">
            {FORMATION_NAMES.map((f) => <option key={f} value={f}>{f}</option>)}
          </select>
        </div>
      </div>

      {/* Pitch */}
      <div ref={pitchRef} className="relative w-full bg-stone-100 rounded-lg overflow-hidden" style={{ paddingBottom: "62%" }}>
        <svg ref={svgRef} viewBox="0 0 100 65" className="absolute inset-0 w-full h-full" style={{ background: "#2d8a3e" }}
          onMouseMove={onMove} onMouseUp={onUp} onMouseLeave={onUp}>
          {/* Pitch stripes — 16 equal alternating light/dark columns */}
          {Array.from({ length: 10 }, (_, i) => (
            <rect key={i} x={i * 10} y={0} width={10} height={65} fill={i % 2 === 0 ? "#2e9641" : "#2a8639"} opacity="0.6" />
          ))}
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
          {players(homeL, "#1a73e8", "h")}
          {players(awayL, "#dc3545", "a")}
        </svg>

        {/* Sub picker popup — fixed position to avoid clipping */}
        {sub && bench.length > 0 && (
          <div className="fixed bg-white border border-stone-300 rounded-lg shadow-lg z-50 p-1" style={{ left: sub.clientX || 0, top: sub.clientY || 0, maxHeight: "250px", overflowY: "auto" }}>
            {bench.map((p: any, bi: number) => (
              <button key={bi} onClick={() => doSwap(bi)}
                className="block w-full text-left px-3 py-1.5 text-sm hover:bg-green-50 whitespace-nowrap">
                <span className="font-medium">{p.name}</span>
                <span className="text-stone-400 ml-2">{p.position} · {p.overall}</span>
              </button>
            ))}
            <button onClick={() => setSub(null)} className="block w-full text-center px-3 py-1 text-xs text-stone-400 hover:bg-stone-50">Cancel</button>
          </div>
        )}

        <div className="absolute bottom-2 left-2 flex gap-3 text-xs text-white bg-black/40 rounded px-3 py-1">
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-full bg-[#1a73e8]" /> Home</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-full bg-[#dc3545]" /> Away</span>
        </div>
      </div>
    </div>
  );
}
