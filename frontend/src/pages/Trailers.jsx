import React, { useEffect, useState } from "react";
import Topbar from "../components/Topbar";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";

export default function Trailers() {
  const [trailers, setTrailers] = useState([]);
  useEffect(() => { api.get("/trailer-specs").then(({ data }) => setTrailers(data)); }, []);

  const palletData = trailers.map((t) => ({ name: t.name, pallets: t.pallets, color: t.color }));
  const weightData = trailers.map((t) => ({ name: t.name, weight: t.max_weight_lbs, color: t.color }));
  const maxLen = Math.max(...trailers.map((t) => t.length_ft), 53);

  return (
    <>
      <Topbar title="Trailer Specs" subtitle="Equipment reference · capacity & use cases" />
      <div className="p-4 md:p-6 space-y-5">

        <Card className="hud-surface p-5">
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-1">Visual Scale</div>
          <h3 className="font-display text-lg font-bold mb-5">Proportional Length Comparison</h3>
          <div className="space-y-4" data-testid="trailer-visual">
            {trailers.map((t) => {
              const pct = (t.length_ft / maxLen) * 100;
              return (
                <div key={t.id}>
                  <div className="flex items-center justify-between text-xs mb-1">
                    <span className="text-white font-medium">{t.name}</span>
                    <span className="font-mono text-slate-400">{t.length_ft}' L · {t.width_ft}' W · {t.height_ft}' H · {t.max_weight_lbs.toLocaleString()} lbs max</span>
                  </div>
                  <div className="h-8 bg-white/[0.02] rounded relative overflow-hidden border border-white/5">
                    <div
                      className="h-full flex items-center justify-end pr-3 rounded"
                      style={{ width: `${pct}%`, background: `linear-gradient(90deg, ${t.color}22, ${t.color}88)`, borderRight: `2px solid ${t.color}` }}
                    >
                      <span className="text-[10px] font-mono text-white">{t.length_ft}'</span>
                    </div>
                  </div>
                  <div className="text-[11px] text-slate-400 mt-1">
                    Best for: {t.uses.join(" · ")}
                  </div>
                </div>
              );
            })}
          </div>
        </Card>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <Card className="hud-surface p-5">
            <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-1">Pallet Capacity</div>
            <h3 className="font-display text-lg font-bold mb-4">Standard Pallet Positions (40×48")</h3>
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={palletData}>
                <CartesianGrid stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="name" stroke="#475569" tick={{ fontSize: 9, fontFamily: "JetBrains Mono" }} angle={-25} textAnchor="end" height={70} />
                <YAxis stroke="#475569" tick={{ fontSize: 10, fontFamily: "JetBrains Mono" }} />
                <Tooltip contentStyle={{ background: "#0B0E14", border: "1px solid rgba(0,229,255,0.3)" }} />
                <Bar dataKey="pallets" fill="#00E5FF" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Card>

          <Card className="hud-surface p-5">
            <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-1">Max Payload</div>
            <h3 className="font-display text-lg font-bold mb-4">Weight Capacity (lbs)</h3>
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={weightData}>
                <CartesianGrid stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="name" stroke="#475569" tick={{ fontSize: 9, fontFamily: "JetBrains Mono" }} angle={-25} textAnchor="end" height={70} />
                <YAxis stroke="#475569" tick={{ fontSize: 10, fontFamily: "JetBrains Mono" }} />
                <Tooltip contentStyle={{ background: "#0B0E14", border: "1px solid rgba(0,229,255,0.3)" }} />
                <Bar dataKey="weight" fill="#10B981" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Card>
        </div>
      </div>
    </>
  );
}
