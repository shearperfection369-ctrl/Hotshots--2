import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import Topbar from "@/components/Topbar";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  TrendingUp, DollarSign, Activity, Clock, Truck, MapPin,
  Award, BarChart3, RefreshCw, Download,
} from "lucide-react";
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip } from "recharts";

const REACT_APP_BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const WINDOW_OPTIONS = [
  { d: 7,   label: "Past 7 days" },
  { d: 30,  label: "Past 30 days" },
  { d: 90,  label: "Past 90 days" },
  { d: 365, label: "Past year" },
];

/** /brokerage/ops-kpis — The 4 KPIs every shipper + carrier asks for. */
export default function BrokerageOpsKpis() {
  const [data, setData] = useState(null);
  const [window, setWindow] = useState(30);
  const [loading, setLoading] = useState(true);

  const fetchKpis = async (w = window) => {
    setLoading(true);
    try {
      const { data: d } = await api.get(`/brokerage/ops-kpis?window_days=${w}`);
      setData(d);
    } catch (e) { toast.error("Failed to load Ops KPIs"); }
    finally { setLoading(false); }
  };
  useEffect(() => { fetchKpis(); /* eslint-disable-next-line */ }, []);

  const h = data?.headline || {};
  return (
    <>
      <Topbar title="Brokerage Ops KPIs" />
      <div className="p-6 max-w-7xl mx-auto space-y-6">

        {/* HEADER + WINDOW PICKER */}
        <Card className="hud-surface p-5" data-testid="ops-kpis-header">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div>
              <div className="text-[10px] font-mono uppercase tracking-[0.25em] text-cyan-400">
                Operations · The four shippers and carriers ask about
              </div>
              <h1 className="font-display text-3xl font-black mt-1 flex items-center gap-3">
                <BarChart3 className="text-cyan-400" size={28} /> Ops KPI Dashboard
              </h1>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              {WINDOW_OPTIONS.map((opt) => (
                <button key={opt.d}
                  onClick={() => { setWindow(opt.d); fetchKpis(opt.d); }}
                  data-testid={`window-${opt.d}`}
                  className={`px-3 py-1.5 rounded text-xs font-mono uppercase tracking-wider transition
                    ${window === opt.d
                      ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40"
                      : "text-slate-400 hover:text-cyan-300 border border-transparent hover:bg-white/5"}`}>
                  {opt.label}
                </button>
              ))}
              <Button onClick={() => fetchKpis()} size="sm" variant="ghost"
                disabled={loading} className="text-cyan-300"
                data-testid="ops-kpis-refresh">
                <RefreshCw size={13} className={`mr-1.5 ${loading ? "animate-spin" : ""}`} />
                {loading ? "Loading…" : "Refresh"}
              </Button>
            </div>
          </div>
        </Card>

        {/* HEADLINE — THE 4 KPIs */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4" data-testid="headline-kpis">
          <BigKpi v={`$${h.cost_per_mile || 0}`} k="Cost Per Mile" sub={`$${h.revenue_per_mile || 0}/mi revenue`} icon={Truck} testId="kpi-cpm" />
          <BigKpi v={`${h.gross_margin_pct || 0}%`} k="Gross Margin" sub={`$${(h.gross_margin_usd || 0).toLocaleString()} on $${(h.revenue_usd || 0).toLocaleString()}`} icon={DollarSign} testId="kpi-margin" />
          <BigKpi v={`${h.fill_rate_pct || 0}%`} k="Fill Rate" sub={`${h.delivered_loads || 0} of ${h.total_loads || 0} loads`} icon={Activity} testId="kpi-fill" />
          <BigKpi v={`${h.on_time_pct || 0}%`} k="On-Time %" sub="1-hr grace · delivered loads" icon={Clock} testId="kpi-otp" />
        </div>

        {/* MARGIN BY DAY */}
        <Card className="hud-surface p-5" data-testid="daily-margin-chart">
          <h2 className="font-display text-xl font-bold flex items-center gap-2 mb-1">
            <TrendingUp size={18} className="text-emerald-400" /> Margin By Day
          </h2>
          <p className="text-xs text-slate-400 mb-4">Daily gross margin across the selected window.</p>
          {(data?.daily || []).length === 0 ? (
            <div className="text-xs font-mono text-slate-500 py-6 text-center">No daily data in this window.</div>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={data.daily} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="marginFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#34d399" stopOpacity={0.35} />
                    <stop offset="100%" stopColor="#34d399" stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="date" tick={{ fill: "#64748b", fontSize: 9, fontFamily: "monospace" }}
                       tickFormatter={(d) => d.slice(5)} interval="preserveStartEnd" />
                <YAxis tick={{ fill: "#64748b", fontSize: 9, fontFamily: "monospace" }}
                       tickFormatter={(v) => `$${v >= 1000 ? `${(v / 1000).toFixed(1)}k` : v}`} width={52} />
                <Tooltip contentStyle={{ background: "#0b1320", border: "1px solid rgba(255,255,255,0.1)", fontSize: 11, fontFamily: "monospace" }}
                         formatter={(v, name) => [`$${Number(v).toLocaleString()}`, name === "margin_usd" ? "Margin" : "Revenue"]} />
                <Area type="monotone" dataKey="revenue_usd" stroke="#22d3ee" strokeWidth={1} fill="none" strokeDasharray="4 3" />
                <Area type="monotone" dataKey="margin_usd" stroke="#34d399" strokeWidth={2} fill="url(#marginFill)" />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </Card>

        {/* LANE BREAKDOWN */}
        <Card className="hud-surface p-5" data-testid="lane-breakdown">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="font-display text-xl font-bold flex items-center gap-2">
                <MapPin size={18} className="text-cyan-400" /> Lane Performance
              </h2>
              <p className="text-xs text-slate-400 mt-1">Cost per mile, margin %, on-time % by lane — sorted by volume.</p>
            </div>
            <div className="text-[10px] font-mono uppercase tracking-wider text-slate-400">
              {data?.lanes?.length || 0} lanes
            </div>
          </div>
          {data?.lanes?.length === 0 ? (
            <EmptyState label="No lane data in this window. Book some loads first." />
          ) : (
            <div className="overflow-x-auto" data-testid="lane-table">
              <table className="w-full text-sm">
                <thead className="text-[10px] font-mono uppercase tracking-wider text-slate-400 border-b border-white/5">
                  <tr>
                    <th className="text-left py-2">Lane</th>
                    <th className="text-right">Loads</th>
                    <th className="text-right">Miles</th>
                    <th className="text-right">Revenue</th>
                    <th className="text-right">CPM</th>
                    <th className="text-right">RPM</th>
                    <th className="text-right">Margin</th>
                    <th className="text-right">Margin %</th>
                    <th className="text-right">On-time</th>
                  </tr>
                </thead>
                <tbody>
                  {(data?.lanes || []).map((l, i) => (
                    <tr key={l.lane} className="border-b border-white/5 hover:bg-white/[0.02]" data-testid={`lane-row-${i}`}>
                      <td className="py-2 text-slate-200">{l.lane}</td>
                      <td className="text-right tabular-nums">{l.loads}</td>
                      <td className="text-right tabular-nums text-slate-400">{l.miles.toLocaleString()}</td>
                      <td className="text-right tabular-nums">${l.revenue_usd.toLocaleString()}</td>
                      <td className="text-right tabular-nums">${l.cost_per_mile}</td>
                      <td className="text-right tabular-nums">${l.revenue_per_mile}</td>
                      <td className="text-right tabular-nums">${l.margin_usd.toLocaleString()}</td>
                      <td className={`text-right tabular-nums font-bold ${l.margin_pct >= 15 ? "text-emerald-300" : l.margin_pct >= 8 ? "text-amber-300" : "text-red-300"}`}>
                        {l.margin_pct}%
                      </td>
                      <td className="text-right tabular-nums">
                        {l.on_time_pct == null ? <span className="text-slate-500">—</span>
                          : <span className={l.on_time_pct >= 95 ? "text-emerald-300" : l.on_time_pct >= 85 ? "text-amber-300" : "text-red-300"}>{l.on_time_pct}%</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        {/* CARRIER SCORECARD */}
        <Card className="hud-surface p-5" data-testid="carrier-scorecard">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="font-display text-xl font-bold flex items-center gap-2">
                <Award size={18} className="text-cyan-400" /> Carrier Performance
              </h2>
              <p className="text-xs text-slate-400 mt-1">Loads run, cost per mile, on-time % per carrier in window.</p>
            </div>
            <div className="text-[10px] font-mono uppercase tracking-wider text-slate-400">
              {data?.carriers?.length || 0} carriers
            </div>
          </div>
          {data?.carriers?.length === 0 ? (
            <EmptyState label="No carrier activity in this window yet." />
          ) : (
            <div className="overflow-x-auto" data-testid="carrier-table">
              <table className="w-full text-sm">
                <thead className="text-[10px] font-mono uppercase tracking-wider text-slate-400 border-b border-white/5">
                  <tr>
                    <th className="text-left py-2">Carrier</th>
                    <th className="text-left text-slate-500">MC</th>
                    <th className="text-right">Loads</th>
                    <th className="text-right">Miles</th>
                    <th className="text-right">Cost</th>
                    <th className="text-right">$/mi</th>
                    <th className="text-right">Margin</th>
                    <th className="text-right">On-time</th>
                  </tr>
                </thead>
                <tbody>
                  {(data?.carriers || []).map((c, i) => (
                    <tr key={c.carrier_mc} className="border-b border-white/5 hover:bg-white/[0.02]" data-testid={`carrier-row-${i}`}>
                      <td className="py-2 text-slate-200">{c.carrier_name}</td>
                      <td className="text-slate-500 font-mono text-xs">{c.carrier_mc}</td>
                      <td className="text-right tabular-nums">{c.loads}</td>
                      <td className="text-right tabular-nums text-slate-400">{c.miles.toLocaleString()}</td>
                      <td className="text-right tabular-nums">${c.carrier_cost_usd.toLocaleString()}</td>
                      <td className="text-right tabular-nums">${c.avg_cost_per_mile}</td>
                      <td className="text-right tabular-nums">${c.margin_usd.toLocaleString()}</td>
                      <td className="text-right tabular-nums">
                        {c.on_time_pct == null ? <span className="text-slate-500">—</span>
                          : <span className={c.on_time_pct >= 95 ? "text-emerald-300" : c.on_time_pct >= 85 ? "text-amber-300" : "text-red-300"}>{c.on_time_pct}%</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <div className="text-[10px] font-mono text-slate-500 text-center pt-2">
          Window: {data?.window_days || window} days · Generated {data?.generated_at ? new Date(data.generated_at).toLocaleString() : "—"}
        </div>
      </div>
    </>
  );
}

function BigKpi({ v, k, sub, icon: Icon, testId }) {
  return (
    <div className="hud-surface p-5 rounded-xl border border-cyan-500/20 bg-cyan-500/[0.04]" data-testid={testId}>
      <Icon size={16} className="text-slate-500 mb-2" />
      <div className="font-display text-4xl font-black text-cyan-300 tabular-nums">{v}</div>
      <div className="text-xs font-mono uppercase tracking-wider text-slate-300 mt-1">{k}</div>
      <div className="text-[10px] text-slate-500 mt-1">{sub}</div>
    </div>
  );
}

function EmptyState({ label }) {
  return <div className="text-slate-400 text-sm italic py-8 text-center">{label}</div>;
}
