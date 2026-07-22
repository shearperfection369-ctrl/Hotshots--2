import React, { useCallback, useEffect, useState } from "react";
import { Crosshair, Home, CircleDot, Radar } from "lucide-react";
import { api } from "../../lib/api";

const HUNT_META = {
  hunting: ["HUNTING", "#F59E0B"],
  booked: ["BOOKED", "#22D3EE"],
  completed: ["DRIVER HOME", "#10B981"],
  expired: ["EXPIRED", "#64748B"],
};

export const BackhaulHunter = () => {
  const [data, setData] = useState(null);

  const load = useCallback(async () => {
    try { const { data: d } = await api.get("/broker-autopilot/backhaul"); setData(d); } catch (_) {}
  }, []);
  useEffect(() => { load(); const t = setInterval(load, 15000); return () => clearInterval(t); }, [load]);

  if (!data) return <div className="p-6 text-slate-500 font-mono text-sm">Loading backhaul hunter…</div>;
  const { hunts, stats } = data;

  return (
    <div className="space-y-4" data-testid="backhaul-hunter">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[["Hunting now", stats.hunting, "#F59E0B"], ["Backhauls booked", stats.booked, "#22D3EE"],
          ["Round trips closed", stats.round_trips, "#10B981"],
          ["Backhaul margin", `$${stats.backhaul_margin.toLocaleString()}`, "#A78BFA"]].map(([l, v, c]) => (
          <div key={l} className="p-3 rounded-2xl border border-white/10 bg-slate-950/70 backdrop-blur">
            <div className="text-xl font-black tabular-nums" style={{ color: c }}>{v}</div>
            <div className="text-[9px] font-mono uppercase tracking-wider text-slate-500 mt-0.5">{l}</div>
          </div>
        ))}
      </div>

      {hunts.length === 0 && (
        <div className="p-6 rounded-2xl border border-dashed border-amber-500/30 text-center" data-testid="bh-empty">
          <Radar className="mx-auto text-amber-300 mb-2" size={26} />
          <p className="text-sm text-slate-400">No hunts yet. The moment a driver delivers away from home base,
            the Hunter opens a hunt, scans the boards each cycle, and books the optimal return load —
            then runs it rate con → BOL → transit → POD until the driver is home.</p>
        </div>
      )}

      <div className="grid md:grid-cols-2 gap-3">
        {hunts.map((h) => {
          const [label, color] = HUNT_META[h.status] || HUNT_META.expired;
          const b = h.best_candidate;
          return (
            <div key={h.hunt_id} className="p-4 rounded-2xl border border-white/10 bg-slate-950/60 backdrop-blur"
                 data-testid={`bh-hunt-${h.hunt_id}`}>
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-1.5 text-[10px] font-mono">
                  <Crosshair size={12} className="text-amber-300" />
                  <span className="text-slate-500">{h.hunt_id}</span>
                </div>
                <span className="px-2 py-0.5 rounded-full border text-[9px] font-mono font-bold"
                      style={{ borderColor: color, color }}
                      data-testid={`bh-status-${h.hunt_id}`}>
                  {h.status === "hunting" && <CircleDot size={9} className="inline mr-1 animate-pulse" />}{label}
                </span>
              </div>
              <div className="text-sm font-bold text-white flex items-center gap-1.5">
                {h.stranded_at} <span className="text-slate-500">→</span> <Home size={13} className="text-emerald-400" /> {h.home_base}
              </div>
              <div className="text-[10px] font-mono text-slate-500 mb-2">
                {h.driver?.name} · CDL {h.driver?.cdl_number} · {h.carrier?.name} · after {h.outbound_load_id}
              </div>
              <div className="flex flex-wrap gap-2 text-[10px] font-mono">
                <span className="px-2 py-1 rounded-lg bg-white/[0.04] border border-white/10 text-slate-400">
                  {h.scans} board scan{h.scans === 1 ? "" : "s"}
                </span>
                {b && (
                  <>
                    <span className="px-2 py-1 rounded-lg bg-cyan-500/10 border border-cyan-500/25 text-cyan-300">
                      best score {b.score}
                    </span>
                    <span className="px-2 py-1 rounded-lg bg-emerald-500/10 border border-emerald-500/25 text-emerald-300">
                      ${b.margin?.toLocaleString()} mgn · ${b.rpm}/mi
                    </span>
                    <span className="px-2 py-1 rounded-lg bg-white/[0.04] border border-white/10 text-slate-400">
                      {b.deadhead_miles} mi deadhead
                    </span>
                  </>
                )}
                {h.booked_load_id && (
                  <span className="px-2 py-1 rounded-lg bg-purple-500/10 border border-purple-500/30 text-purple-300 font-bold"
                        data-testid={`bh-booked-${h.hunt_id}`}>
                    {h.booked_load_id}
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
