"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "../../../../../lib/api";

interface TickData {
  t: number;
  ball: [number, number];
  players: { id: string; name: string; number: number; pos: [number, number]; team: string; stamina: number }[];
  events: any[];
  score: [number, number];
  phase: string;
}

interface PassFx {
  passerX: number; passerY: number;
  landingX: number; landingY: number;
  team: string;
  startTick: number;
}

const FX_LIFETIME = 10; // ticks

export default function ReplayPage() {
  const { id, matchIndex } = useParams<{ id: string; matchIndex: string }>();
  const router = useRouter();

  const [ticks, setTicks] = useState<TickData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [playing, setPlaying] = useState(false);
  const [tickIndex, setTickIndex] = useState(0);
  const [speed, setSpeed] = useState(1); // 0.5, 1, 2, 4
  const [lastEvents, setLastEvents] = useState<{ tick: number; events: any[] }>({ tick: 0, events: [] });
  const [passFx, setPassFx] = useState<PassFx[]>([]);

  const animRef = useRef<number>(0);
  const lastTimeRef = useRef<number>(0);
  const tickIndexRef = useRef(0);

  // Load replay data
  useEffect(() => {
    (async () => {
      try {
        const data = await api.getReplay(id, +matchIndex);
        if (!data.signed_url) throw new Error("No signed URL");
        const res = await fetch(data.signed_url);
        const blob = await res.blob();
        const ds = new DecompressionStream("gzip");
        const text = await new Response(blob.stream().pipeThrough(ds)).text();
        const parsed = text.trim().split("\n").filter(Boolean).map((l) => JSON.parse(l) as TickData);
        setTicks(parsed);
        setLoading(false);
      } catch (e: any) {
        setError(e.message || "Failed to load replay");
        setLoading(false);
      }
    })();
  }, [id, matchIndex]);

  // Animation loop
  const animate = useCallback((time: number) => {
    if (!lastTimeRef.current) lastTimeRef.current = time;
    const elapsed = time - lastTimeRef.current;
    const msPerTick = 1000 / (10 * speed); // 10 ticks per second at 1x speed

    if (elapsed >= msPerTick) {
      lastTimeRef.current = time - (elapsed % msPerTick);
      const next = tickIndexRef.current + 1;
      if (next >= ticks.length) {
        setPlaying(false);
        return;
      }
      tickIndexRef.current = next;
      setTickIndex(next);
    }
    animRef.current = requestAnimationFrame(animate);
  }, [speed, ticks.length]);

  useEffect(() => {
    if (playing && ticks.length > 0) {
      lastTimeRef.current = 0;
      animRef.current = requestAnimationFrame(animate);
    }
    return () => { if (animRef.current) cancelAnimationFrame(animRef.current); };
  }, [playing, animate, ticks]);

  const handlePlayPause = () => {
    if (tickIndex >= ticks.length - 1) {
      tickIndexRef.current = 0;
      setTickIndex(0);
    }
    setPlaying(!playing);
  };

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const v = +e.target.value;
    tickIndexRef.current = v;
    setTickIndex(v);
  };

  // Remember last non-empty events + collect pass Fx — must stay before any conditional return
  useEffect(() => {
    const t = ticks[tickIndex];
    if (!t) return;

    // Events display
    if (t.events?.length > 0) {
      setLastEvents({ tick: t.t, events: t.events });
    }

    // Scan for pass events — events is an array of {type, success, data, player_id}
    const eventsArr: any[] = Array.isArray(t.events) ? t.events : Object.values(t.events || {});
    const newFx: PassFx[] = [];
    for (const ev of eventsArr) {
      if (ev?.type === "pass" && ev?.success && ev?.data?.landing_mx != null) {
        const passer = t.players.find((p) => p.id === ev.player_id);
        if (passer) {
          newFx.push({
            passerX: passer.pos[0],
            passerY: passer.pos[1],
            landingX: ev.data.landing_mx + 50,  // engine meters → field coords
            landingY: ev.data.landing_my + 30,
            team: passer.team,
            startTick: t.t,
          });
        }
      }
    }
    setPassFx((prev) => [...prev.filter((fx) => t.t - fx.startTick <= FX_LIFETIME), ...newFx]);
  }, [tickIndex, ticks]);

  // --- Render ---

  if (loading) {
    return (
      <div className="max-w-5xl mx-auto">
        <div className="flex flex-col items-center justify-center py-20 gap-4">
          <div className="w-8 h-8 border-2 border-stone-200 border-t-green-700 rounded-full animate-spin" />
          <div className="text-sm text-stone-400">Loading replay...</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-5xl mx-auto">
        <div className="text-sm text-stone-400 py-20 text-center">{error}</div>
      </div>
    );
  }

  const tick = ticks[tickIndex] || ticks[0];
  if (!tick) return null;

  const homePlayers = tick.players.filter((p) => p.team === "home");
  const awayPlayers = tick.players.filter((p) => p.team === "away");

  // Find ball carrier (ball within 0.5 field units of a player)
  let carrier: (typeof tick.players)[0] | null = null;
  let ballDirX = 0, ballDirY = 0;
  for (const p of tick.players) {
    const dx = tick.ball[0] - p.pos[0];
    const dy = tick.ball[1] - p.pos[1];
    if (Math.sqrt(dx*dx + dy*dy) < 0.5) { carrier = p; break; }
  }
  if (carrier) {
    const prevTick = tickIndex > 0 ? ticks[tickIndex - 1] : null;
    if (prevTick) {
      const prevP = prevTick.players.find((pp) => pp.id === carrier!.id);
      if (prevP) { ballDirX = carrier.pos[0] - prevP.pos[0]; ballDirY = carrier.pos[1] - prevP.pos[1]; }
    }
    const mag = Math.sqrt(ballDirX*ballDirX + ballDirY*ballDirY);
    if (mag < 0.01) {
      ballDirX = carrier.team === "home" ? 1 : -1;
      ballDirY = 0;
    } else { ballDirX /= mag; ballDirY /= mag; }
  }

  const CARRIER_RING_R = 1.8; // ring radius (matches AgentPitch: PLAYER_RADIUS + 4)

  return (
    <div className="max-w-5xl mx-auto overflow-hidden" style={{ overflowAnchor: "none" }}>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <button onClick={() => router.back()} className="text-sm text-stone-400 hover:text-stone-700 mb-1">← Back</button>
          <h1 className="text-xl font-bold text-stone-800">
            Replay — Match {+matchIndex + 1}
          </h1>
        </div>
        <div className="flex items-center gap-4 text-sm">
          <span className="text-stone-500">
            Tick <span className="font-mono text-stone-700">{tick.t}</span> / {ticks[ticks.length - 1]?.t}
          </span>
          <span className="font-bold text-lg text-stone-800">
            {tick.score[0]} — {tick.score[1]}
          </span>
          <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
            tick.phase === "playing" ? "bg-green-100 text-green-700" :
            tick.phase === "goal_kick" || tick.phase === "corner" ? "bg-yellow-100 text-yellow-700" :
            "bg-stone-100 text-stone-500"
          }`}>
            {tick.phase}
          </span>
        </div>
      </div>

      {/* Pitch */}
      <div className="relative w-full bg-stone-100 rounded-lg overflow-hidden mb-4" style={{ paddingBottom: "60%" }}>
        <svg viewBox="0 0 100 60" className="absolute inset-0 w-full h-full" style={{ background: "#1f3a2a" }}>
          {/* Pitch stripes — 16 equal alternating light/dark columns */}
          {Array.from({ length: 10 }, (_, i) => (
            <rect key={i} x={i * 10} y={0} width={10} height={60} fill={i % 2 === 0 ? "#2e9641" : "#2a8639"} opacity="0.6" />
          ))}
          {/* Field markings */}
          <rect x="1" y="1" width="98" height="58" fill="none" stroke="white" strokeWidth="0.25" opacity="0.7" />
          <line x1="50" y1="1" x2="50" y2="59" stroke="white" strokeWidth="0.25" opacity="0.4" />
          <circle cx="50" cy="30" r="6" fill="none" stroke="white" strokeWidth="0.25" opacity="0.4" />
          <rect x="1" y="16" width="16" height="28" fill="none" stroke="white" strokeWidth="0.25" opacity="0.5" />
          <rect x="83" y="16" width="16" height="28" fill="none" stroke="white" strokeWidth="0.25" opacity="0.5" />
          <rect x="1" y="23" width="6" height="14" fill="none" stroke="white" strokeWidth="0.25" opacity="0.4" />
          <rect x="93" y="23" width="6" height="14" fill="none" stroke="white" strokeWidth="0.25" opacity="0.4" />
          <rect x="-1" y="26" width="2" height="8" fill="none" stroke="white" strokeWidth="0.5" opacity="0.7" />
          <rect x="99" y="26" width="2" height="8" fill="none" stroke="white" strokeWidth="0.5" opacity="0.7" />
          <circle cx="12" cy="30" r="0.3" fill="white" opacity="0.4" />
          <circle cx="88" cy="30" r="0.3" fill="white" opacity="0.4" />

          {/* Pass trajectory lines */}
          {passFx.map((fx, i) => {
            const age = tick.t - fx.startTick;
            const alpha = Math.max(0, 1 - age / FX_LIFETIME);
            const color = fx.team === "home" ? "#f2a44b" : "#b08cff";
            return (
              <g key={i} opacity={alpha}>
                <line x1={fx.passerX} y1={fx.passerY} x2={fx.landingX} y2={fx.landingY}
                  stroke={color} strokeWidth={0.25} strokeDasharray="0.8 0.8" />
                <circle cx={fx.landingX} cy={fx.landingY} r={0.4} fill={color} />
              </g>
            );
          })}

          {/* Players and ball — data already in 0-100 x 0-60 field coords */}
            {/* Home players */}
            {homePlayers.map((p) => (
              <g key={p.id}>
                {carrier?.id === p.id && (
                  <circle cx={p.pos[0]} cy={p.pos[1]} r={CARRIER_RING_R} fill="none" stroke="rgba(255,255,255,0.85)" strokeWidth={0.3} />
                )}
                <circle cx={p.pos[0]} cy={p.pos[1]} r={1.2} fill="#f2a44b" stroke="white" strokeWidth="0.2" />
                <text x={p.pos[0]} y={p.pos[1] + 0.5} textAnchor="middle" fill="white" fontSize="1.1" fontWeight="bold" fontFamily="sans-serif">
                  {p.number || p.id.replace("home_", "")}
                </text>
                <text x={p.pos[0]} y={p.pos[1] + 2.8} textAnchor="middle" fill="white" fontSize="1.3" fontFamily="sans-serif">
                  {p.name ? p.name.split(" ")[0] : ""}
                </text>
              </g>
            ))}

            {/* Away players */}
            {awayPlayers.map((p) => (
              <g key={p.id}>
                {carrier?.id === p.id && (
                  <circle cx={p.pos[0]} cy={p.pos[1]} r={CARRIER_RING_R} fill="none" stroke="rgba(255,255,255,0.85)" strokeWidth={0.3} />
                )}
                <circle cx={p.pos[0]} cy={p.pos[1]} r={1.2} fill="#b08cff" stroke="white" strokeWidth="0.2" />
                <text x={p.pos[0]} y={p.pos[1] + 0.5} textAnchor="middle" fill="white" fontSize="1.1" fontWeight="bold" fontFamily="sans-serif">
                  {p.number || p.id.replace("away_", "")}
                </text>
                <text x={p.pos[0]} y={p.pos[1] + 2.8} textAnchor="middle" fill="white" fontSize="1.3" fontFamily="sans-serif">
                  {p.name ? p.name.split(" ")[0] : ""}
                </text>
              </g>
            ))}

            {/* Ball — offset to carrier ring when carried */}
            <text
              x={carrier ? carrier.pos[0] + ballDirX * CARRIER_RING_R : tick.ball[0]}
              y={carrier ? carrier.pos[1] + ballDirY * CARRIER_RING_R : tick.ball[1]}
              textAnchor="middle" dominantBaseline="central" fontSize="1.1" fontFamily="sans-serif">⚽</text>
        </svg>

        {/* Pitch legend */}
        <div className="absolute bottom-2 left-2 flex gap-3 text-xs text-white bg-black/40 rounded px-3 py-1">
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-full bg-[#1a73e8]" /> Home</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-full bg-[#dc3545]" /> Away</span>
        </div>
      </div>

      {/* Controls */}
      <div className="bg-white border border-stone-200 rounded-lg p-4">
        <div className="flex items-center gap-4">
          <button onClick={handlePlayPause}
            className="px-4 py-2 bg-green-700 text-white text-sm font-semibold rounded hover:bg-green-800 min-w-[80px]">
            {playing ? "⏸ Pause" : tickIndex >= ticks.length - 1 ? "↺ Replay" : "▶ Play"}
          </button>

          <div className="flex items-center gap-1">
            {[0.5, 1, 2, 4].map((s) => (
              <button key={s} onClick={() => setSpeed(s)}
                className={`px-2 py-1 text-xs rounded ${speed === s ? "bg-stone-700 text-white" : "bg-stone-100 text-stone-500 hover:bg-stone-200"}`}>
                {s}x
              </button>
            ))}
          </div>

          {/* Progress bar */}
          <div className="flex-1 flex items-center gap-2">
            <span className="text-xs text-stone-400 font-mono w-12 text-right">{tickIndex}</span>
            <input type="range" min={0} max={ticks.length - 1} value={tickIndex} onChange={handleSeek}
              className="flex-1 h-1 accent-green-700" />
            <span className="text-xs text-stone-400 font-mono w-12">{ticks.length - 1}</span>
          </div>
        </div>

        {/* Events log — fixed height, never causes layout shift */}
        <div className="mt-3 pt-3 border-t border-stone-100" style={{ height: "40px", overflowY: "auto" }}>
          <div className="text-xs text-stone-400 mb-1">
            {tick.events?.length > 0
              ? `Events at tick ${tick.t}:`
              : lastEvents.events.length > 0
                ? `Events at tick ${lastEvents.tick}:`
                : "No events yet"}
          </div>
          {(tick.events?.length > 0 ? tick.events : lastEvents.events).map((ev: any, i: number) => (
            <span key={i} className="inline-block text-xs bg-yellow-50 border border-yellow-200 rounded px-2 py-0.5 mr-1 mb-1">
              {ev.type || JSON.stringify(ev)}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
