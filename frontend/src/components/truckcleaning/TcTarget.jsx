import React, { useCallback, useEffect, useState } from "react";
import { api } from "../../lib/api";
import { Card } from "../ui/card";
import { Target, TrendingUp, Truck, RefreshCw } from "lucide-react";

export const TcTarget = () => {
  const [d, setD] = useState(null);
  const load = useCallback(() => {
    api.get("/truck-cleaning/target").then(({ data }) => setD(data)).catch(() => {});
  }, []);
  useEffect(() => { load(); const t = setInterval(load, 60000); return () => clearInterval(t); }, [load]);
  if (!d) return <div className="text-slate-500 font-mono text-sm">Loading target tracker…</div>;
  const cabPct = Math.min(100, Math.round((d.cabs_total / d.cabs_target) * 100));
  return (
    <div className="space-y-4" data-testid="tc-target">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-bold text-white flex items-center gap-2"><Target size={15} className="text-amber-400" /> Revenue Target — {d.month}</h3>
          <div className="text-[11px] text-slate-500">The scoreboard: gap to $10K/month, live from your bookings</div>
        </div>
        <button onClick={load} className="text-slate-500 hover:text-white" data-testid="tc-target-refresh"><RefreshCw size={13} /></button>
      </div>

      <Card className="p-5 bg-slate-950/70 border-amber-500/25" data-testid="tc-target-progress">
        <div className="flex items-end justify-between mb-2 flex-wrap gap-2">
          <div>
            <span className="text-3xl font-black text-amber-300" data-testid="tc-target-projected">${d.projected.toLocaleString()}</span>
            <span className="text-slate-500 text-sm font-mono"> / ${d.target.toLocaleString()}</span>
          </div>
          <div className={`px-3 py-1 rounded-full text-[10px] font-black ${d.on_pace ? "bg-emerald-500/15 text-emerald-300 border border-emerald-500/30" : "bg-red-500/15 text-red-300 border border-red-500/30"}`}>
            {d.on_pace ? "ON PACE" : "BEHIND PACE"} · {d.month_elapsed_pct}% of month gone
          </div>
        </div>
        <div className="h-4 rounded-full bg-white/10 relative overflow-hidden">
          <div className="h-full bg-gradient-to-r from-amber-600 to-amber-400 transition-all" style={{ width: `${d.progress_pct}%` }} />
          <div className="absolute top-0 bottom-0 w-0.5 bg-white/50" style={{ left: `${d.month_elapsed_pct}%` }} title="Where the month is" />
        </div>
        <div className="flex justify-between mt-2 text-[10px] font-mono text-slate-500">
          <span>${d.revenue_done.toLocaleString()} done + ${d.revenue_booked.toLocaleString()} booked</span>
          <span className="text-red-300 font-bold" data-testid="tc-target-gap">GAP: ${d.gap.toLocaleString()}</span>
        </div>
      </Card>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[["Cabs this month", `${d.cabs_total} / ${d.cabs_target}`, "#F59E0B"],
          ["Cabs still needed", d.cabs_gap, d.cabs_gap ? "#F87171" : "#34D399"],
          ["Recurring run-rate", `$${d.recurring_run_rate.toLocaleString()}/mo`, "#34D399"],
          ["Active clients", d.clients_active, "#22D3EE"]].map(([l, v, c]) => (
          <div key={l} className="p-3 rounded-2xl border border-white/10 bg-slate-950/70">
            <div className="text-xl font-black tabular-nums" style={{ color: c }}>{v}</div>
            <div className="text-[9px] font-mono uppercase tracking-wider text-slate-500 mt-0.5">{l}</div>
          </div>
        ))}
      </div>

      <Card className="p-4 bg-slate-950/70 border-white/10" data-testid="tc-cab-meter">
        <h4 className="text-xs font-bold text-white mb-2 flex items-center gap-2"><Truck size={13} className="text-cyan-300" /> Truck volume vs crew break-even (40–50 cabs/mo pays a 2-person crew)</h4>
        <div className="h-3 rounded-full bg-white/10 overflow-hidden">
          <div className={`h-full transition-all ${cabPct >= 100 ? "bg-emerald-500" : cabPct >= 80 ? "bg-amber-500" : "bg-red-500"}`} style={{ width: `${cabPct}%` }} />
        </div>
        <div className="text-[10px] font-mono text-slate-500 mt-1.5">
          {d.cabs_done} cleaned + {d.cabs_booked} booked = <b className="text-white">{d.cabs_total}</b> of {d.cabs_target} cab target
          {d.cabs_gap > 0 ? ` — ${d.cabs_gap} more to lock in this month` : " — crew salary covered ✓"}
        </div>
      </Card>

      <Card className="p-4 bg-slate-950/70 border-white/10" data-testid="tc-gap-closers">
        <h4 className="text-xs font-bold text-white mb-3 flex items-center gap-2"><TrendingUp size={13} className="text-emerald-400" /> What closes the ${d.gap.toLocaleString()} gap</h4>
        <div className="grid sm:grid-cols-3 gap-3">
          {d.gap_closers.map((g) => (
            <div key={g.label} className={`p-4 rounded-xl border ${g.needed <= 2 && d.gap > 0 ? "border-emerald-500/40 bg-emerald-500/[0.05]" : "border-white/10 bg-white/[0.02]"}`}>
              <div className="text-2xl font-black text-white">{d.gap > 0 ? `${g.needed}×` : "✓"}</div>
              <div className="text-[11px] text-slate-300 mt-1">{g.label}</div>
              <div className="text-[10px] font-mono text-emerald-300 mt-1">${g.value_mo.toLocaleString()}/mo each</div>
            </div>
          ))}
        </div>
        <div className="text-[10px] text-slate-500 mt-3">Sign the yards on lock-in schedules (Scheduler tab) and this board updates in real time. Send the Yard Manager Package (Branded Docs) to open doors.</div>
      </Card>
    </div>
  );
};
