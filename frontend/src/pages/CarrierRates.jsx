import React, { useEffect, useMemo, useState } from "react";
import Topbar from "../components/Topbar";
import { api } from "../lib/api";
import { useBrandRefresh } from "../lib/branding";
import { Card } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Fuel, TrendingUp, TrendingDown, Minus, Truck } from "lucide-react";

export default function CarrierRates() {
  const [lanes, setLanes] = useState([]);
  const [fsc, setFsc] = useState(null);
  const [mode, setMode] = useState("ALL");

  const loadRates = () => {
    Promise.all([api.get("/carrier-rates"), api.get("/carrier-rates/fsc")]).then(([l, f]) => {
      setLanes(l.data); setFsc(f.data);
    });
  };
  useEffect(() => { loadRates(); }, []);
  useBrandRefresh(() => loadRates());

  const modes = useMemo(() => ["ALL", ...Array.from(new Set(lanes.map((l) => l.mode)))], [lanes]);
  const filtered = lanes.filter((l) => mode === "ALL" || l.mode === mode);

  return (
    <>
      <Topbar title="Carrier Rates & FSC" subtitle="Side-by-side rate comparison across approved carriers · live fuel surcharge index" />
      <div className="p-4 md:p-6 space-y-5">

        {/* FSC Index */}
        {fsc && (
          <Card className="hud-surface p-5">
            <div className="flex items-start justify-between flex-wrap gap-4">
              <div>
                <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-1">Fuel Surcharge Index</div>
                <h3 className="font-display text-lg font-bold flex items-center gap-2">
                  <Fuel size={18} className="text-yellow-400" /> National DOE Diesel Avg: ${fsc.doe_diesel_avg_per_gallon}/gal
                </h3>
                <div className="text-[10px] font-mono text-slate-500 mt-1">Week ending {fsc.doe_week}</div>
              </div>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2 mt-4" data-testid="fsc-grid">
              {fsc.fsc_table.map((c) => {
                const TrendIcon = c.trend === "up" ? TrendingUp : c.trend === "down" ? TrendingDown : Minus;
                const trendColor = c.trend === "up" ? "text-red-400" : c.trend === "down" ? "text-emerald-400" : "text-slate-500";
                return (
                  <div key={c.scac} className="p-3 rounded-md border border-white/5 bg-white/[0.02]">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-mono text-slate-500">{c.scac}</span>
                      <TrendIcon size={11} className={trendColor} />
                    </div>
                    <div className="text-sm text-white mt-1 truncate" title={c.carrier}>{c.carrier}</div>
                    <div className="font-mono text-xl font-bold text-yellow-400 tabular-nums">{c.current_fsc_pct}%</div>
                    <div className={`text-[10px] font-mono ${trendColor}`}>{c.week_change_pct > 0 ? "+" : ""}{c.week_change_pct}% WoW</div>
                  </div>
                );
              })}
            </div>
          </Card>
        )}

        {/* Mode filter */}
        <div className="flex gap-2 flex-wrap" data-testid="mode-toggle">
          {modes.map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              data-testid={`rate-mode-${m}`}
              className={`px-3 py-1.5 rounded-md text-xs font-mono uppercase tracking-wider transition-all border ${
                mode === m ? "bg-cyan-500 text-black border-cyan-400 hud-glow-cyan" : "bg-white/[0.02] text-slate-300 border-white/5 hover:border-cyan-500/40"
              }`}
            >{m}</button>
          ))}
        </div>

        {/* Lane rate cards */}
        <div className="space-y-4">
          {filtered.map((l) => {
            const carriers = [...l.carriers].sort((a, b) => a.base_rate - b.base_rate);
            const cheapest = carriers[0];
            return (
              <Card key={l.lane_id} className="hud-surface overflow-hidden" data-testid={`lane-${l.lane_id}`}>
                <div className="px-5 py-3 border-b border-white/5 flex items-center justify-between flex-wrap gap-2">
                  <div className="flex items-center gap-3">
                    <Truck size={16} className="text-cyan-400" />
                    <div>
                      <div className="text-[10px] font-mono text-cyan-400 uppercase tracking-wider">{l.mode} · {l.miles ? `${l.miles} mi` : "Per Container"}</div>
                      <h3 className="font-display font-bold text-white">{l.origin} <span className="text-slate-500">→</span> {l.destination}</h3>
                    </div>
                  </div>
                  <Badge className="bg-emerald-500/10 text-emerald-300 border-emerald-500/30 font-mono text-[10px]">
                    BEST: {cheapest.carrier} · ${cheapest.base_rate.toLocaleString()}
                  </Badge>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-[#0B0E14] text-[10px] font-mono text-slate-500 uppercase tracking-wider">
                      <tr>
                        <th className="text-left py-3 px-4">Carrier</th>
                        <th className="text-left py-3 px-4">SCAC</th>
                        <th className="text-right py-3 px-4">Base Rate</th>
                        <th className="text-right py-3 px-4">{l.mode === "TL" ? "$/Mile" : l.mode === "LTL" ? "$/CWT" : l.mode === "Parcel" ? "$/Lb" : "$/Cont"}</th>
                        <th className="text-right py-3 px-4">FSC %</th>
                        <th className="text-right py-3 px-4">Min Charge</th>
                        <th className="text-right py-3 px-4">Transit</th>
                        <th className="text-left py-3 px-4">FAK / Class</th>
                        <th className="text-right py-3 px-4">All-In</th>
                      </tr>
                    </thead>
                    <tbody className="font-mono">
                      {carriers.map((c, i) => {
                        const allIn = c.base_rate * (1 + c.fsc_pct / 100);
                        const isCheapest = i === 0;
                        const perUnit = c.rate_per_mile || c.rate_per_cwt || c.rate_per_lb || c.rate_per_container;
                        return (
                          <tr key={c.scac} className={`border-t border-white/5 hover:bg-white/[0.02] ${isCheapest ? "bg-emerald-500/[0.04]" : ""}`}>
                            <td className="py-2.5 px-4 text-white">
                              {c.carrier}
                              {isCheapest && <Badge className="ml-2 bg-emerald-500/10 text-emerald-300 border-emerald-500/30 font-mono text-[9px]">CHEAPEST</Badge>}
                            </td>
                            <td className="py-2.5 px-4 text-cyan-300">{c.scac}</td>
                            <td className="py-2.5 px-4 text-right text-slate-300">${c.base_rate.toLocaleString()}</td>
                            <td className="py-2.5 px-4 text-right text-slate-400">${perUnit?.toFixed(2)}</td>
                            <td className="py-2.5 px-4 text-right text-yellow-400">{c.fsc_pct}%</td>
                            <td className="py-2.5 px-4 text-right text-slate-400">${c.min_charge}</td>
                            <td className="py-2.5 px-4 text-right text-slate-400">{c.transit_days}d</td>
                            <td className="py-2.5 px-4 text-slate-400">{c.fak}</td>
                            <td className={`py-2.5 px-4 text-right font-bold ${isCheapest ? "text-emerald-400" : "text-white"}`}>${allIn.toFixed(2)}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </Card>
            );
          })}
        </div>
      </div>
    </>
  );
}
