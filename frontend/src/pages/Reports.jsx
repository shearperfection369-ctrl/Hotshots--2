import React, { useEffect, useState } from "react";
import Topbar from "../components/Topbar";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid,
  LineChart, Line, Legend, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar
} from "recharts";

export default function Reports() {
  const [kpis, setKpis] = useState(null);
  useEffect(() => { api.get("/kpis").then(({ data }) => setKpis(data)); }, []);

  if (!kpis) return <><Topbar title="KPI Reports" /><div className="p-6 text-slate-400">Loading...</div></>;

  const trend = kpis.trend;
  const carrierScore = kpis.by_carrier.slice(0, 8).map((c) => ({
    ...c,
    on_time_rate: c.total ? Math.round((c.on_time / c.total) * 100) : 0,
  }));
  const radarData = carrierScore.slice(0, 6).map((c) => ({
    carrier: c.carrier.split(" ")[0],
    Score: c.on_time_rate,
    Volume: Math.min(100, c.total * 10),
  }));

  return (
    <>
      <Topbar title="KPI Reports" subtitle="Performance analytics across modes, lanes & carriers" />
      <div className="p-4 md:p-6 space-y-5">

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <KPI label="Total Shipments" value={kpis.totals.total} accent="text-cyan-400" />
          <KPI label="On-Time Rate" value={`${kpis.totals.on_time_rate}%`} accent="text-emerald-400" />
          <KPI label="Total Weight" value={`${(kpis.totals.weight_lbs / 1000).toFixed(1)}K lbs`} accent="text-cyan-400" />
          <KPI label="Total Value" value={`$${(kpis.totals.value_usd / 1000).toFixed(0)}K`} accent="text-emerald-400" />
        </div>

        <Card className="hud-surface p-5">
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-1">14-Day Cost Trend</div>
          <h3 className="font-display text-lg font-bold mb-4">Spend Analytics</h3>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={trend}>
              <CartesianGrid stroke="rgba(255,255,255,0.05)" />
              <XAxis dataKey="date" stroke="#475569" tick={{ fontSize: 10, fontFamily: "JetBrains Mono" }} />
              <YAxis stroke="#475569" tick={{ fontSize: 10, fontFamily: "JetBrains Mono" }} />
              <Tooltip contentStyle={{ background: "#0B0E14", border: "1px solid rgba(0,229,255,0.3)" }} />
              <Legend wrapperStyle={{ fontSize: 12, fontFamily: "JetBrains Mono" }} />
              <Line dataKey="cost" stroke="#00E5FF" strokeWidth={2} dot={{ r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        </Card>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <Card className="hud-surface p-5">
            <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-1">Carrier Scorecard</div>
            <h3 className="font-display text-lg font-bold mb-4">On-Time Performance by Carrier</h3>
            <ResponsiveContainer width="100%" height={320}>
              <BarChart data={carrierScore} layout="vertical">
                <CartesianGrid stroke="rgba(255,255,255,0.05)" />
                <XAxis type="number" stroke="#475569" tick={{ fontSize: 10 }} />
                <YAxis dataKey="carrier" type="category" stroke="#475569" tick={{ fontSize: 10 }} width={120} />
                <Tooltip contentStyle={{ background: "#0B0E14", border: "1px solid rgba(0,229,255,0.3)" }} />
                <Bar dataKey="on_time_rate" fill="#10B981" radius={[0, 3, 3, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Card>

          <Card className="hud-surface p-5">
            <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-1">Carrier Profile</div>
            <h3 className="font-display text-lg font-bold mb-4">Score vs Volume</h3>
            <ResponsiveContainer width="100%" height={320}>
              <RadarChart data={radarData}>
                <PolarGrid stroke="rgba(255,255,255,0.1)" />
                <PolarAngleAxis dataKey="carrier" stroke="#94A3B8" tick={{ fontSize: 10, fontFamily: "JetBrains Mono" }} />
                <PolarRadiusAxis stroke="#475569" tick={{ fontSize: 9 }} />
                <Radar dataKey="Score" stroke="#00E5FF" fill="#00E5FF" fillOpacity={0.3} />
                <Radar dataKey="Volume" stroke="#A78BFA" fill="#A78BFA" fillOpacity={0.2} />
                <Legend wrapperStyle={{ fontSize: 12, fontFamily: "JetBrains Mono" }} />
              </RadarChart>
            </ResponsiveContainer>
          </Card>
        </div>

        <Card className="hud-surface overflow-hidden">
          <div className="px-5 py-3 border-b border-white/5">
            <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400">Carrier Scorecard — Detailed</div>
            <h3 className="font-display text-lg font-bold">All Carriers</h3>
          </div>
          <table className="w-full text-sm">
            <thead className="bg-[#0B0E14] text-[10px] font-mono text-slate-500 uppercase tracking-wider">
              <tr>
                <th className="text-left py-3 px-4">Carrier</th>
                <th className="text-right py-3 px-4">Total</th>
                <th className="text-right py-3 px-4">Delivered</th>
                <th className="text-right py-3 px-4">Delayed</th>
                <th className="text-right py-3 px-4">On-Time %</th>
              </tr>
            </thead>
            <tbody className="font-mono">
              {kpis.by_carrier.sort((a, b) => b.total - a.total).map((c) => {
                const otp = c.total ? Math.round((c.on_time / c.total) * 100) : 0;
                return (
                  <tr key={c.carrier} className="border-t border-white/5 hover:bg-white/[0.02]">
                    <td className="py-2.5 px-4 text-slate-300">{c.carrier}</td>
                    <td className="py-2.5 px-4 text-right text-cyan-300">{c.total}</td>
                    <td className="py-2.5 px-4 text-right text-emerald-400">{c.on_time}</td>
                    <td className="py-2.5 px-4 text-right text-red-400">{c.delayed}</td>
                    <td className="py-2.5 px-4 text-right text-white">{otp}%</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </Card>
      </div>
    </>
  );
}

const KPI = ({ label, value, accent }) => (
  <Card className="hud-surface p-5">
    <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-slate-500">{label}</div>
    <div className={`mt-2 text-3xl font-mono font-bold tabular-nums ${accent}`}>{value}</div>
  </Card>
);
