import React, { useCallback, useEffect, useState } from "react";
import { Card } from "../ui/card";
import { Truck, Boxes, Hammer, Trophy, ArrowLeft, Crown } from "lucide-react";
import { api } from "../../lib/api";
import { toast } from "sonner";
import FreightRunner from "./FreightRunner";
import LoadStacker from "./LoadStacker";
import DockBreaker from "./DockBreaker";

const GAMES = [
  { id: "freight-runner", name: "Freight Runner", icon: Truck, accent: "text-cyan-300", border: "border-cyan-500/40", desc: "Neon snake, trucker edition. Haul crates, grow your rig, don't jackknife.", comp: FreightRunner },
  { id: "load-stacker", name: "Load Stacker 2048", icon: Boxes, accent: "text-amber-300", border: "border-amber-500/40", desc: "Consolidate pallets into the legendary 2048 mega-load.", comp: LoadStacker },
  { id: "dock-breaker", name: "Dock Breaker", icon: Hammer, accent: "text-orange-300", border: "border-orange-500/40", desc: "Classic brick-breaker at the loading dock. Clear every crate row.", comp: DockBreaker },
];

export default function SoloArcade() {
  const [active, setActive] = useState(null);
  const [scores, setScores] = useState({ top: [], my_best: 0 });

  const loadScores = useCallback(async (gameId) => {
    try { const { data } = await api.get(`/arcade/solo/highscores?game=${gameId}`); setScores(data); } catch (_) {}
  }, []);

  useEffect(() => { if (active) loadScores(active.id); }, [active, loadScores]);

  const handleScore = async (score) => {
    if (!active || score <= 0) return;
    try {
      const { data } = await api.post("/arcade/solo/score", { game: active.id, score });
      if (data.is_new_best) toast.success(`New personal best: ${score.toLocaleString()}!`);
      loadScores(active.id);
    } catch (_) {}
  };

  if (!active) {
    return (
      <div className="grid sm:grid-cols-3 gap-4" data-testid="solo-arcade-picker">
        {GAMES.map((g) => (
          <Card key={g.id} onClick={() => setActive(g)} data-testid={`solo-game-${g.id}`}
                className={`hud-surface p-6 cursor-pointer hover:scale-[1.02] transition-transform border ${g.border} group`}>
            <g.icon className={`${g.accent} mb-3 group-hover:scale-110 transition-transform`} size={30} />
            <div className="font-black text-white text-lg">{g.name}</div>
            <p className="text-[13px] text-slate-400 mt-1.5 leading-relaxed">{g.desc}</p>
            <div className={`mt-4 text-xs font-mono uppercase tracking-widest ${g.accent}`}>Play solo →</div>
          </Card>
        ))}
      </div>
    );
  }

  const GameComp = active.comp;
  return (
    <div className="grid lg:grid-cols-[1fr_260px] gap-4" data-testid="solo-arcade-game">
      <Card className="hud-surface p-5">
        <div className="flex items-center justify-between mb-4">
          <button onClick={() => setActive(null)} data-testid="solo-back-btn"
                  className="flex items-center gap-1.5 text-xs font-mono uppercase text-slate-400 hover:text-white">
            <ArrowLeft size={13} /> All games
          </button>
          <div className={`font-black ${active.accent}`}>{active.name}</div>
        </div>
        <GameComp onScore={handleScore} />
      </Card>
      <Card className="hud-surface p-4 h-fit" data-testid="solo-leaderboard">
        <div className="text-xs font-mono uppercase tracking-widest text-slate-400 flex items-center gap-2 mb-3">
          <Trophy size={13} className="text-yellow-400" /> High scores
        </div>
        <div className="mb-3 p-2.5 rounded-lg bg-white/5 border border-white/10 flex justify-between items-center">
          <span className="text-xs text-slate-400">Your best</span>
          <span className={`font-black tabular-nums ${active.accent}`} data-testid="solo-my-best">{scores.my_best.toLocaleString()}</span>
        </div>
        {scores.top.length === 0 ? (
          <div className="text-xs text-slate-500 text-center py-4">No scores yet — set the first record.</div>
        ) : (
          <div className="space-y-1.5">
            {scores.top.map((row, i) => (
              <div key={row.user_id} className={`flex items-center gap-2 text-sm px-2 py-1.5 rounded ${i === 0 ? "bg-yellow-500/10 border border-yellow-500/30" : ""}`}>
                <span className="w-5 text-[11px] font-mono text-slate-500">{i === 0 ? <Crown size={13} className="text-yellow-400" /> : `#${i + 1}`}</span>
                <span className="flex-1 truncate text-slate-300 text-xs">{row.name}</span>
                <span className="font-bold tabular-nums text-white text-xs">{row.score.toLocaleString()}</span>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
