"use client";

import { useState, useEffect } from "react";
import { useSimulationStore } from "../../stores/simulationStore";
import { Pitch } from "../../components/pitch/Pitch";

export default function SimulationPage() {
  const { activeJob, isRunning, startSimulation, cancelPolling } = useSimulationStore();
  const [clubs, setClubs] = useState<any[]>([]);
  const [nations, setNations] = useState<any[]>([]);
  const [searchH, setSearchH] = useState("");
  const [searchA, setSearchA] = useState("");
  const [home, setHome] = useState<any>(null);
  const [away, setAway] = useState<any>(null);
  const [matchCount, setMatchCount] = useState(10);
  const [filterH, setFilterH] = useState<"club" | "nation">("club");
  const [filterA, setFilterA] = useState<"club" | "nation">("club");
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState("");
  const [homeFormation, setHomeFormation] = useState("4-3-3");
  const [awayFormation, setAwayFormation] = useState("4-3-3");
  const [homeTacticalDoc, setHomeTacticalDoc] = useState("");
  const [awayTacticalDoc, setAwayTacticalDoc] = useState("");
  const [homePositions, setHomePositions] = useState<any[]>([]);
  const [awayPositions, setAwayPositions] = useState<any[]>([]);

  const TACTIC_PRESETS: { label: string; desc: string }[] = [
    {
      label: "⚡ Gegenpress",
      desc: "High-intensity counter-pressing after losing possession.\nDefensive line: High\nPressing: All-out, hunt the ball immediately\nTransition: Instantly swarm the ball carrier\nAttacking: Fast vertical passes, exploit chaos",
    },
    {
      label: "🔄 Tiki-Taka",
      desc: "Possession-based short passing through triangles.\nDefensive line: High\nPressing: Coordinated 6-second rule\nBuild-up: Patient circulation from the back\nAttacking: Create overloads, wait for the killer pass",
    },
    {
      label: "🅿️ Park the Bus",
      desc: "Ultra-defensive low block with minimal attacking intent.\nDefensive line: Deep, 10 men behind the ball\nPressing: None — hold shape\nShape: Two banks of four, extremely narrow\nAttacking: Hope for a set-piece or lucky break",
    },
    {
      label: "🏃 Counter-Attack",
      desc: "Deep defensive block with rapid transitions.\nDefensive line: Medium-low\nPressing: Only in own half\nTransition: Release 2-3 runners on every turnover\nAttacking: Direct balls into space behind the defence",
    },
    {
      label: "🪽 Wing Play",
      desc: "Stretch the pitch and deliver crosses.\nDefensive line: Medium\nWidth: Maximum — wingers hug the touchline\nFullbacks: Overlap and deliver early crosses\nAttacking: Target striker in the box, near/far-post runs",
    },
    {
      label: "🎯 Long Ball",
      desc: "Direct play bypassing the midfield.\nDefensive line: Medium-deep\nBuild-up: Skip midfield — go route one\nTarget: Strong hold-up striker for knock-downs\nSecond balls: Press aggressively to collect",
    },
    {
      label: "🔒 Catenaccio",
      desc: "Italian defensive system with a libero.\nDefensive line: Deep with a sweeper\nMarking: Tight man-marking across the pitch\nPressing: Only engage in own third\nAttacking: One creative playmaker unlocks the game",
    },
    {
      label: "🌪️ Total Football",
      desc: "Fluid positional interchange across all lines.\nDefensive line: High\nRotation: Any outfield player fills any role\nPressing: Full-pitch coordinated press\nBuild-up: Centre-backs carry into midfield",
    },
  ];

  useEffect(() => {
    fetch("/data/teams/clubs.json").then(r => r.json()).then(d => setClubs(d.teams || [])).catch(() => {});
    fetch("/data/teams/nations.json").then(r => r.json()).then(d => setNations(d.teams || [])).catch(() => {});
  }, []);

  const loadTeam = async (t: any, side: "home" | "away") => {
    const resp = await fetch(`/data/teams/${t.file}`);
    const data = await resp.json();
    data.logo = data.logo || "";
    if (side === "home") {
      setHome(data); setSearchH(t.name);
      if (data.tactical_document) setHomeTacticalDoc(data.tactical_document);
    } else {
      setAway(data); setSearchA(t.name);
      if (data.tactical_document) setAwayTacticalDoc(data.tactical_document);
    }
  };

  const TeamOption = ({ t, side, logoUrl }: { t: any; side: "home" | "away"; logoUrl?: string }) => {
    const sel = side === "home" ? home : away;
    return (
      <button onClick={() => loadTeam(t, side)}
        className={`flex items-center gap-2 w-full text-left px-3 py-2.5 text-base border-b border-stone-100 hover:bg-green-50 ${sel?.name === t.name ? "bg-green-100" : ""}`}>
        {logoUrl ? (logoUrl.startsWith("http") ? <img src={logoUrl} alt="" referrerPolicy="no-referrer" className="w-12 h-12 object-contain" /> : <span className="text-xl">{logoUrl}</span>) : <div className="w-12 h-12" />}
        <span className="flex-1 truncate text-base">{t.name}</span>
      </button>
    );
  };

  const handleRun = async () => {
    if (!home || !away) {
      setError("Select both teams."); return;
    }
    setImporting(true);
    setError("");
    try {
      // Bundle players, formation, and tactical docs directly into the job
      // Merge custom positions from Pitch into player data
      const homePlayers = (home.players || []).map((p: any, i: number) => {
        const pos = homePositions[i];
        return {
          name: p.name, number: p.number || 0, position: p.position, attributes: p.attributes, ap: p.ap,
          px: pos?.px, py: pos?.py,
        };
      });
      const awayPlayers = (away.players || []).map((p: any, i: number) => {
        const pos = awayPositions[i];
        return {
          name: p.name, number: p.number || 0, position: p.position, attributes: p.attributes, ap: p.ap,
          px: pos?.px, py: pos?.py,
        };
      });

      await startSimulation({
        match_count: matchCount,
        home_players: homePlayers,
        away_players: awayPlayers,
        home_tactic: {
          team_name: home.name,
          formation: homeFormation,
          tactical_document: homeTacticalDoc,
        },
        away_tactic: {
          team_name: away.name,
          formation: awayFormation,
          tactical_document: awayTacticalDoc,
        },
      });
    } catch (e: any) { setError(e.message); }
    setImporting(false);
  };

  const PlayerList = ({ data }: { data: any }) => (
    <div>
      <div className="text-base text-stone-500 max-h-96 overflow-y-auto">
        {(data?.players || []).map((p: any) => (
          <div key={p.name} className="flex items-center justify-between py-1.5 border-b border-stone-100">
            <div className="flex items-center gap-2">
              {p.image ? <img src={p.image} alt="" referrerPolicy="no-referrer" className="w-16 h-16 rounded-full object-cover bg-stone-200" /> : <div className="w-16 h-16 rounded-full bg-stone-200 flex items-center justify-center text-stone-400 font-bold text-base">{p.name.charAt(0)}</div>}
              <span className="text-lg">{p.name}</span>
              <span className="text-stone-400 text-sm font-mono">#{p.number || "—"}</span>
            </div>
            <span className="text-stone-400 text-base">{p.position} · {p.overall}</span>
          </div>
        ))}
      </div>
    </div>
  );

  return (
    <div className="max-w-5xl mx-auto">
      <h1 className="text-2xl font-bold mb-6 text-stone-800">Run Simulation</h1>

      <div className="grid grid-cols-2 gap-4 mb-6">
        {/* Home Team */}
        <div className="bg-white border border-stone-200 rounded-lg p-4">
          <label className="text-base font-semibold text-stone-700 block mb-2">Home Team</label>
          {home ? (
            <div className="flex items-center gap-3 mb-2">
              {home.logo ? (
                home.logo.startsWith("http") ? <img src={home.logo} alt="" referrerPolicy="no-referrer" className="w-12 h-12 object-contain" /> : <span className="text-2xl">{home.logo}</span>
              ) : <div className="w-12 h-12 rounded-full bg-stone-200 flex items-center justify-center text-stone-400 font-bold text-lg">{home.name.charAt(0)}</div>}
              <div>
                <span className="font-semibold text-stone-800 text-base">{home.name}</span>
                <div className="text-xs text-stone-400">{home.players?.length || 0} players</div>
              </div>
              <button onClick={() => { setHome(null); setSearchH(""); }} className="text-xs text-stone-400 hover:text-red-500 ml-auto">Change</button>
            </div>
          ) : (
            <>
              <div className="flex gap-2 mb-2">
                <select className="text-sm bg-stone-50 border rounded px-2 py-1" value={filterH} onChange={(e) => { setFilterH(e.target.value as any); setHome(null); setSearchH(""); }}>
                  <option value="club">Clubs</option>
                  <option value="nation">Nations</option>
                </select>
                <input className="flex-1 bg-stone-50 border border-stone-200 rounded px-3 py-1.5 text-sm" placeholder="Search..."
                  value={searchH} onChange={(e) => { setSearchH(e.target.value); setHome(null); }} />
              </div>
              <div className="max-h-96 overflow-y-auto mb-2 border rounded">
                {(filterH === "club" ? clubs : nations).filter(t => t.name.toLowerCase().includes(searchH.toLowerCase())).map((t: any) => (
                  <TeamOption key={t.file} t={t} side="home" logoUrl={t.logo} />
                ))}
              </div>
            </>
          )}
          <PlayerList data={home} />
        </div>

        {/* Away Team */}
        <div className="bg-white border border-stone-200 rounded-lg p-4">
          <label className="text-base font-semibold text-stone-700 block mb-2">Away Team</label>
          {away ? (
            <div className="flex items-center gap-3 mb-2">
              {away.logo ? (
                away.logo.startsWith("http") ? <img src={away.logo} alt="" referrerPolicy="no-referrer" className="w-12 h-12 object-contain" /> : <span className="text-2xl">{away.logo}</span>
              ) : <div className="w-12 h-12 rounded-full bg-stone-200 flex items-center justify-center text-stone-400 font-bold text-lg">{away.name.charAt(0)}</div>}
              <div>
                <span className="font-semibold text-stone-800 text-base">{away.name}</span>
                <div className="text-xs text-stone-400">{away.players?.length || 0} players</div>
              </div>
              <button onClick={() => { setAway(null); setSearchA(""); }} className="text-xs text-stone-400 hover:text-red-500 ml-auto">Change</button>
            </div>
          ) : (
            <>
              <div className="flex gap-2 mb-2">
                <select className="text-sm bg-stone-50 border rounded px-2 py-1" value={filterA} onChange={(e) => { setFilterA(e.target.value as any); setAway(null); setSearchA(""); }}>
                  <option value="club">Clubs</option>
                  <option value="nation">Nations</option>
                </select>
                <input className="flex-1 bg-stone-50 border border-stone-200 rounded px-3 py-1.5 text-sm" placeholder="Search..."
                  value={searchA} onChange={(e) => { setSearchA(e.target.value); setAway(null); }} />
              </div>
              <div className="max-h-96 overflow-y-auto mb-2 border rounded">
                {(filterA === "club" ? clubs : nations).filter(t => t.name.toLowerCase().includes(searchA.toLowerCase())).map((t: any) => (
                  <TeamOption key={t.file} t={t} side="away" logoUrl={t.logo} />
                ))}
              </div>
            </>
          )}
          <PlayerList data={away} />
        </div>
      </div>

      {home && away && (
        <div className="mb-6">
          <div className="flex justify-between text-sm font-semibold text-stone-600 mb-2">
            <span>{home.name} ({home.players?.length}p)</span>
            <span>{away.name} ({away.players?.length}p)</span>
          </div>
          <Pitch
            homePlayers={home.players || []} awayPlayers={away.players || []}
            homeFormation={homeFormation} awayFormation={awayFormation}
            onHomeFormationChange={setHomeFormation} onAwayFormationChange={setAwayFormation}
            onPositionChange={(h, a) => { setHomePositions(h); setAwayPositions(a); }}
          />
        </div>
      )}

      {home && away && (
        <div className="mb-6 grid grid-cols-2 gap-4">
          {/* Home Tactical Document */}
          <div className="bg-white border border-stone-200 rounded-lg p-4">
            <label className="text-base font-semibold text-stone-700 block mb-2">
              📋 {home.name} — Tactical Document
            </label>
            <div className="flex flex-wrap gap-1.5 mb-3">
              {TACTIC_PRESETS.map((p) => (
                <button
                  key={p.label}
                  onClick={() => setHomeTacticalDoc(p.desc)}
                  className="px-2.5 py-1 text-xs font-medium rounded-full border border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100 hover:border-blue-300 transition-colors"
                >
                  {p.label}
                </button>
              ))}
            </div>
            <textarea
              value={homeTacticalDoc}
              onChange={(e) => setHomeTacticalDoc(e.target.value)}
              placeholder="Choose a preset above or write your own tactical instructions..."
              rows={8}
              className="w-full bg-stone-50 border border-stone-200 rounded px-4 py-3 text-sm text-stone-700 placeholder-stone-300 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 resize-y"
            />
          </div>

          {/* Away Tactical Document */}
          <div className="bg-white border border-stone-200 rounded-lg p-4">
            <label className="text-base font-semibold text-stone-700 block mb-2">
              📋 {away.name} — Tactical Document
            </label>
            <div className="flex flex-wrap gap-1.5 mb-3">
              {TACTIC_PRESETS.map((p) => (
                <button
                  key={p.label}
                  onClick={() => setAwayTacticalDoc(p.desc)}
                  className="px-2.5 py-1 text-xs font-medium rounded-full border border-red-200 bg-red-50 text-red-700 hover:bg-red-100 hover:border-red-300 transition-colors"
                >
                  {p.label}
                </button>
              ))}
            </div>
            <textarea
              value={awayTacticalDoc}
              onChange={(e) => setAwayTacticalDoc(e.target.value)}
              placeholder="Choose a preset above or write your own tactical instructions..."
              rows={8}
              className="w-full bg-stone-50 border border-stone-200 rounded px-4 py-3 text-sm text-stone-700 placeholder-stone-300 focus:outline-none focus:border-red-500 focus:ring-1 focus:ring-red-500 resize-y"
            />
          </div>
        </div>
      )}

      <div className="flex gap-3 items-center mb-6">
        {[1, 10, 100, 1000].map((n) => (
          <button key={n} onClick={() => setMatchCount(n)}
            className={`px-4 py-2 text-base font-medium ${matchCount === n ? "bg-green-700 text-white" : "bg-white border border-stone-200 text-stone-600 hover:border-green-700"}`}>
            {n} {n === 1 ? "Match" : "Matches"}
          </button>
        ))}
        <button onClick={handleRun} disabled={isRunning || importing}
          className="px-6 py-2 bg-green-700 text-white text-base font-semibold hover:bg-green-800 disabled:opacity-50 ml-auto">
          {importing ? "Starting..." : isRunning ? "Running..." : "Run"}
        </button>
        {isRunning && <button onClick={cancelPolling} className="px-4 py-2 border border-red-300 text-red-600 text-base font-medium hover:bg-red-50">Cancel</button>}
      </div>
      {error && <p className="text-red-600 text-sm mb-4">{error}</p>}

      {activeJob && isRunning && (
        <div className="bg-white border border-stone-200 rounded-lg p-4 mb-6">
          <div className="flex justify-between text-sm mb-2"><span className="text-stone-500">Simulating...</span><span className="text-green-700 font-bold">{activeJob.progress}%</span></div>
          <div className="w-full bg-stone-200 rounded-full h-2"><div className="bg-green-700 h-2 rounded-full transition-all" style={{ width: `${activeJob.progress}%` }} /></div>
        </div>
      )}

    </div>
  );
}
