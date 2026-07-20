import React, { useEffect, useState } from "react";
import { Card } from "../ui/card";
import { SprayCan, Clock, ShieldCheck, Star, Wrench, CheckCircle2 } from "lucide-react";
import { api } from "../../lib/api";

export const TcGuide = () => {
  const [g, setG] = useState(null);
  useEffect(() => { api.get("/truck-cleaning/guide").then((r) => setG(r.data)).catch(() => {}); }, []);
  if (!g) return <div className="text-slate-500 font-mono text-sm">Loading guide…</div>;
  const totalMin = g.phases.reduce((s, p) => s + p.minutes, 0);

  return (
    <div className="space-y-5" data-testid="tc-guide">
      <Card className="p-5 bg-slate-950/70 border-amber-500/30 backdrop-blur">
        <div className="font-black text-lg text-white flex items-center gap-2"><SprayCan size={18} className="text-amber-400" /> {g.title}</div>
        <p className="text-sm text-slate-300 mt-2">{g.intro}</p>
        <div className="mt-3 inline-flex items-center gap-1.5 px-3 py-1 rounded-full border border-cyan-500/40 text-cyan-300 text-[11px] font-mono">
          <Clock size={12} /> {totalMin} minutes total · {g.phases.length} phases
        </div>
      </Card>

      <Card className="p-5 bg-slate-950/70 border-white/10 backdrop-blur" data-testid="tc-guide-kit">
        <div className="text-xs font-mono uppercase tracking-widest text-cyan-300 mb-3 flex items-center gap-2"><Wrench size={13} /> Supply kit — every van, every day</div>
        <div className="grid sm:grid-cols-2 gap-x-6 gap-y-1.5">
          {g.supply_kit.map((s) => (
            <div key={s} className="flex gap-2 text-[13px] text-slate-300"><span className="text-amber-400">▸</span>{s}</div>
          ))}
        </div>
      </Card>

      <div className="space-y-3">
        {g.phases.map((p, i) => (
          <Card key={p.phase} className="p-5 bg-slate-950/70 border-white/10 backdrop-blur hover:border-amber-500/30 transition" data-testid={`tc-guide-phase-${i}`}>
            <div className="flex items-center justify-between mb-3">
              <div className="font-black text-amber-300">{p.phase}</div>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full border border-white/15 text-slate-400 inline-flex items-center gap-1"><Clock size={10} /> {p.minutes} min</span>
            </div>
            <ol className="space-y-2">
              {p.steps.map((st, j) => (
                <li key={j} className="flex gap-3 text-[13px] text-slate-300">
                  <span className="shrink-0 h-5 w-5 rounded-full bg-amber-500/15 border border-amber-500/40 text-amber-300 grid place-items-center text-[10px] font-black">{j + 1}</span>
                  <span className={st.startsWith("Pro tip") ? "text-cyan-300" : ""}>{st}</span>
                </li>
              ))}
            </ol>
          </Card>
        ))}
      </div>

      <Card className="p-5 bg-slate-950/70 border-emerald-500/30 backdrop-blur" data-testid="tc-guide-upsells">
        <div className="text-xs font-mono uppercase tracking-widest text-emerald-400 mb-3 flex items-center gap-2"><Star size={13} /> Upsell procedures</div>
        <div className="grid md:grid-cols-3 gap-4">
          {g.upsells.map((u) => (
            <div key={u.name} className="p-3 rounded-xl border border-white/10 bg-white/[0.02]">
              <div className="font-bold text-white text-sm mb-2">{u.name}</div>
              <ol className="space-y-1.5">
                {u.steps.map((st, j) => (
                  <li key={j} className="flex gap-2 text-[12px] text-slate-400"><span className="text-emerald-400 font-mono">{j + 1}.</span>{st}</li>
                ))}
              </ol>
            </div>
          ))}
        </div>
      </Card>

      <div className="grid md:grid-cols-2 gap-4">
        <Card className="p-5 bg-slate-950/70 border-red-500/30 backdrop-blur" data-testid="tc-guide-safety">
          <div className="text-xs font-mono uppercase tracking-widest text-red-400 mb-3 flex items-center gap-2"><ShieldCheck size={13} /> Safety — non-negotiable</div>
          <ul className="space-y-2">{g.safety.map((s) => <li key={s} className="flex gap-2 text-[13px] text-slate-300"><span className="text-red-400">■</span>{s}</li>)}</ul>
        </Card>
        <Card className="p-5 bg-slate-950/70 border-amber-500/30 backdrop-blur" data-testid="tc-guide-quality">
          <div className="text-xs font-mono uppercase tracking-widest text-amber-300 mb-3 flex items-center gap-2"><CheckCircle2 size={13} /> Quality bar — before you leave</div>
          <ul className="space-y-2">{g.quality_bar.map((s) => <li key={s} className="flex gap-2 text-[13px] text-slate-300"><CheckCircle2 size={14} className="text-amber-400 shrink-0 mt-0.5" />{s}</li>)}</ul>
        </Card>
      </div>
    </div>
  );
};
