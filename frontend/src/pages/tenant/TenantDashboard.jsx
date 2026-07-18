import React, { useEffect, useState } from "react";
import { useTenant } from "./TenantPortal";

const STATUS_COLOR = { booked: "#22D3EE", in_transit: "#F59E0B", delivered: "#34D399", invoiced: "#A78BFA", quoted: "#94A3B8", cancelled: "#EF4444" };

export default function TenantDashboard() {
  const { api, brand, primary, accent } = useTenant();
  const [data, setData] = useState(null);

  useEffect(() => { api.get("/dashboard").then((r) => setData(r.data)).catch(() => {}); }, [api]);

  if (!data) return <div className="text-slate-500 font-mono text-sm">Loading…</div>;
  const k = data.kpis;
  const tiles = [
    ["Total loads", k.total_loads, primary], ["Active loads", k.active_loads, accent],
    ["Gross revenue", `$${k.gross_revenue.toLocaleString()}`, primary],
    ["Gross margin", `$${k.gross_margin.toLocaleString()}`, "#34D399"],
    ["Open A/R", `$${k.open_ar.toLocaleString()}`, "#FB923C"],
    ["Carriers", k.carriers, accent], ["Team", k.team, "#A78BFA"],
  ];
  return (
    <div data-testid="tenant-dashboard">
      <h1 className="text-2xl font-black tracking-tight mb-1">{brand.company_name} — Command Deck</h1>
      <p className="text-slate-500 text-sm mb-6">Your desk at a glance. Isolated workspace — your data never leaves your database.</p>
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3 mb-8">
        {tiles.map(([label, val, color]) => (
          <div key={label} className="p-4 rounded-xl border border-white/10 bg-white/[0.02]">
            <div className="text-2xl font-black tabular-nums" style={{ color }}>{val}</div>
            <div className="text-[10px] font-mono uppercase tracking-wider text-slate-500 mt-1">{label}</div>
          </div>
        ))}
      </div>
      <div className="grid md:grid-cols-2 gap-5">
        <div className="p-5 rounded-xl border border-white/10 bg-white/[0.02]">
          <div className="text-xs font-mono uppercase tracking-widest text-slate-400 mb-3">Loads by status</div>
          {Object.keys(data.by_status).length === 0 ? (
            <div className="text-sm text-slate-500 py-4">No loads yet — book your first one in the Loads tab.</div>
          ) : Object.entries(data.by_status).map(([s, n]) => (
            <div key={s} className="flex items-center gap-3 py-1.5">
              <span className="w-2 h-2 rounded-full" style={{ background: STATUS_COLOR[s] || "#64748B" }} />
              <span className="flex-1 text-sm text-slate-300 capitalize">{s.replace("_", " ")}</span>
              <span className="font-bold tabular-nums">{n}</span>
            </div>
          ))}
        </div>
        <div className="p-5 rounded-xl border border-white/10 bg-white/[0.02]">
          <div className="text-xs font-mono uppercase tracking-widest text-slate-400 mb-3">Recent loads</div>
          {data.recent_loads.length === 0 ? (
            <div className="text-sm text-slate-500 py-4">Nothing yet.</div>
          ) : data.recent_loads.map((l) => (
            <div key={l.load_id} className="flex items-center gap-3 py-2 border-b border-white/5 last:border-0 text-sm">
              <span className="font-mono text-[11px]" style={{ color: accent }}>{l.load_id}</span>
              <span className="flex-1 truncate text-slate-300">{l.origin} → {l.destination}</span>
              <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded-full border border-white/10" style={{ color: STATUS_COLOR[l.status] }}>{l.status}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
