import React, { useCallback, useEffect, useState } from "react";
import Topbar from "../components/Topbar";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Flame, Activity, BrainCircuit, RefreshCw, Loader2, TrendingUp, ArrowDownRight } from "lucide-react";
import { AreaChart, Area, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { toast } from "sonner";

const fmt$ = (n) => `$${Number(n || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
const heatColor = (h) => h >= 65 ? "#f87171" : h >= 35 ? "#fbbf24" : "#34d399";

export default function DynamicPricing() {
  const [tab, setTab] = useState("engine");
  const TABS = [
    { key: "engine", label: "Pricing Engine", icon: Flame },
    { key: "truth", label: "Operational Truth", icon: Activity },
    { key: "playbook", label: "Match Playbook", icon: BrainCircuit },
  ];
  return (
    <>
      <Topbar title="Dynamic Pricing & Truth" subtitle="Real-time supply/demand pricing · real operational data · self-learning shipper↔carrier playbook" />
      <div className="p-4 md:p-6 space-y-4">
        <div className="flex gap-2">
          {TABS.map((t) => {
            const Icon = t.icon;
            return (
              <button key={t.key} onClick={() => setTab(t.key)} data-testid={`dp-tab-${t.key}`}
                className={`px-4 py-2 rounded border text-xs font-mono uppercase tracking-wider flex items-center gap-2 transition-colors ${
                  tab === t.key ? "bg-cyan-500 text-black border-cyan-400" : "bg-white/[0.02] text-slate-400 border-white/10 hover:text-cyan-300"}`}>
                <Icon size={13} /> {t.label}
              </button>
            );
          })}
        </div>
        {tab === "engine" && <EngineTab />}
        {tab === "truth" && <TruthTab />}
        {tab === "playbook" && <PlaybookTab />}
      </div>
    </>
  );
}

function EngineTab() {
  const [mkt, setMkt] = useState(null);
  const [trend, setTrend] = useState([]);
  const [sel, setSel] = useState(null);
  const [loading, setLoading] = useState(false);
  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [{ data: m }, { data: t }] = await Promise.all([
        api.get("/pricing/market"), api.get("/pricing/trend")]);
      setMkt(m); setTrend(t.points || []);
      setSel((s) => s || m.lanes?.[0] || null);
    } catch (e) { toast.error("Market scan failed"); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  if (!mkt) return <Card className="hud-surface p-10 text-center text-slate-500 text-sm">Reading the market…</Card>;
  const idx = mkt.market_heat_index || 0;

  return (
    <div className="space-y-4" data-testid="pricing-engine-panel">
      {/* Heat index hero */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card className="hud-surface p-5 relative overflow-hidden" data-testid="heat-index-card">
          <div className="absolute inset-0 opacity-20" style={{ background: `radial-gradient(circle at 30% 20%, ${heatColor(idx)}55, transparent 60%)` }} />
          <div className="relative">
            <div className="flex items-center justify-between">
              <div className="text-[10px] font-mono uppercase tracking-[0.25em] text-slate-500">Market Heat Index</div>
              <Button size="sm" variant="ghost" onClick={load} disabled={loading} className="h-7 px-2 text-cyan-300" data-testid="dp-refresh-btn">
                {loading ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />}
              </Button>
            </div>
            <div className="text-6xl font-black mt-2" style={{ color: heatColor(idx) }} data-testid="heat-index-value">{idx}</div>
            <div className="text-xs font-mono mt-1" style={{ color: heatColor(idx) }}>{mkt.regime}</div>
            <div className="h-2 rounded bg-white/5 overflow-hidden mt-3">
              <div className="h-full rounded transition-all duration-700" style={{ width: `${idx}%`, background: heatColor(idx) }} />
            </div>
            <div className="text-[10px] font-mono text-slate-500 mt-3">
              🔥 Hottest: {mkt.hottest}<br />🧊 Softest: {mkt.softest}
            </div>
          </div>
        </Card>
        <Card className="hud-surface p-5 lg:col-span-2" data-testid="heat-trend-card">
          <div className="text-[10px] font-mono uppercase tracking-[0.25em] text-slate-500 mb-2">Heat Index — last 48 hourly snapshots</div>
          <div className="h-40">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={trend.length ? trend : [{ hour: "now", heat_index: idx }]}>
                <defs>
                  <linearGradient id="heatG" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#22d3ee" stopOpacity={0.6} />
                    <stop offset="100%" stopColor="#22d3ee" stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="hour" tick={{ fill: "#64748b", fontSize: 9 }} axisLine={false} tickLine={false} />
                <YAxis domain={[0, 100]} tick={{ fill: "#64748b", fontSize: 9 }} axisLine={false} tickLine={false} width={26} />
                <Tooltip contentStyle={{ background: "#0B0E14", border: "1px solid rgba(255,255,255,0.1)", fontSize: 11 }} />
                <Area type="monotone" dataKey="heat_index" stroke="#22d3ee" strokeWidth={2} fill="url(#heatG)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      {/* Lane heat grid + ladder */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card className="hud-surface p-4 lg:col-span-2" data-testid="lane-heat-grid">
          <div className="text-[10px] font-mono uppercase tracking-[0.25em] text-slate-500 mb-3">Lane heat — demand vs available trucks (click a lane)</div>
          <div className="grid grid-cols-2 xl:grid-cols-3 gap-2 max-h-[430px] overflow-y-auto">
            {(mkt.lanes || []).map((l) => (
              <button key={l.lane_key} onClick={() => setSel(l)} data-testid={`lane-card-${l.lane_key}`}
                className={`text-left p-3 rounded border transition-all hover:scale-[1.015] ${sel?.lane_key === l.lane_key ? "border-cyan-400/60 bg-cyan-500/5" : "border-white/10 bg-white/[0.02]"}`}>
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-mono text-slate-500">{l.lane_key}</span>
                  <span className="text-sm font-black" style={{ color: heatColor(l.heat) }}>{l.heat}°</span>
                </div>
                <div className="text-[11px] text-slate-200 truncate mt-0.5">{l.lane_label}</div>
                <div className="h-1 rounded bg-white/5 overflow-hidden mt-1.5">
                  <div className="h-full rounded" style={{ width: `${l.heat}%`, background: heatColor(l.heat) }} />
                </div>
                <div className="text-[9px] font-mono text-slate-500 mt-1.5">
                  {l.demand_loads} loads vs {l.supply_trucks} trucks · target <span className="text-cyan-300">{l.margin_target_pct}%</span>
                </div>
              </button>
            ))}
          </div>
        </Card>

        <Card className="hud-surface p-4" data-testid="price-ladder-card">
          {sel ? (
            <>
              <div className="text-[10px] font-mono uppercase tracking-[0.25em] text-slate-500">7-day price ladder</div>
              <div className="text-sm text-slate-100 font-semibold mt-1 truncate">{sel.lane_label}</div>
              <div className="flex items-center gap-2 mt-1">
                <Badge className="bg-cyan-500/15 text-cyan-300 border-cyan-500/30 text-[9px] font-mono">TODAY {fmt$(sel.quote_today_usd)}</Badge>
                <Badge className="bg-emerald-500/15 text-emerald-300 border-emerald-500/30 text-[9px] font-mono">
                  <ArrowDownRight size={10} className="mr-0.5" />{sel.best_day.day} {fmt$(sel.best_day.quote_usd)} (−{fmt$(sel.best_day.savings_usd)})
                </Badge>
              </div>
              <div className="h-44 mt-3">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={sel.ladder}>
                    <XAxis dataKey="day" tick={{ fill: "#64748b", fontSize: 10 }} axisLine={false} tickLine={false} />
                    <YAxis hide domain={["dataMin - 100", "dataMax + 50"]} />
                    <Tooltip contentStyle={{ background: "#0B0E14", border: "1px solid rgba(255,255,255,0.1)", fontSize: 11 }} formatter={(v) => [fmt$(v), "quote"]} />
                    <Bar dataKey="quote_usd" radius={[4, 4, 0, 0]}>
                      {sel.ladder.map((d) => (
                        <Cell key={d.day} fill={d.is_today ? "#22d3ee" : d.day === sel.best_day.day ? "#34d399" : "rgba(148,163,184,0.35)"} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <div className="p-2.5 rounded border border-amber-500/25 bg-amber-500/5 text-[11px] text-amber-200/90 mt-2" data-testid="shipper-pitch-line">
                “Today this lane is {fmt$(sel.quote_today_usd)}, but {sel.best_day.day} it'll be {fmt$(sel.best_day.quote_usd)} — {fmt$(sel.best_day.savings_usd)} less, lower demand.”
              </div>
              <div className="text-[10px] font-mono text-slate-500 mt-2">Dynamic margin target: <span className="text-cyan-300 font-bold">{sel.margin_target_pct}%</span> (8% soft → 16% scorching)</div>
            </>
          ) : <div className="text-slate-500 text-sm py-10 text-center">Select a lane</div>}
        </Card>
      </div>
    </div>
  );
}

function TruthTab() {
  const [d, setD] = useState(null);
  useEffect(() => { api.get("/ops-truth/summary").then(({ data }) => setD(data)).catch(() => toast.error("Ops truth failed")); }, []);
  if (!d) return <Card className="hud-surface p-10 text-center text-slate-500 text-sm">Pulling real numbers…</Card>;
  const f = d.funnel || {};
  const steps = [
    { label: "Loads scanned", v: f.scanned, c: "#64748b" },
    { label: "Bids fired", v: f.bids, c: "#22d3ee" },
    { label: "Bids won", v: f.wins, c: "#fbbf24" },
    { label: "Auto-booked", v: f.auto_booked, c: "#34d399" },
  ];
  const maxV = Math.max(...steps.map((s) => s.v || 0), 1);
  return (
    <div className="space-y-4" data-testid="ops-truth-panel">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card className="hud-surface p-5" data-testid="truth-funnel">
          <div className="text-[10px] font-mono uppercase tracking-[0.25em] text-slate-500 mb-3">What actually books · last {d.window_days} days</div>
          <div className="space-y-2.5">
            {steps.map((s) => (
              <div key={s.label}>
                <div className="flex justify-between text-[10px] font-mono"><span className="text-slate-400">{s.label}</span><span style={{ color: s.c }}>{Number(s.v || 0).toLocaleString()}</span></div>
                <div className="h-2.5 rounded bg-white/5 overflow-hidden mt-0.5">
                  <div className="h-full rounded transition-all duration-700" style={{ width: `${Math.max((s.v || 0) / maxV * 100, 1)}%`, background: s.c }} />
                </div>
              </div>
            ))}
          </div>
          <div className="flex gap-4 mt-3 text-[10px] font-mono">
            <span className="text-cyan-300">win rate {f.win_rate_pct}%</span>
            <span className="text-emerald-300">book rate {f.book_rate_pct}%</span>
            <span className="text-slate-400">{f.booked_total} bookings total</span>
          </div>
          <div className="text-[9px] font-mono text-slate-600 mt-2">
            By source: {Object.entries(d.bookings_by_source || {}).map(([k, v]) => `${k} ${v}`).join(" · ")}
          </div>
        </Card>

        <Card className="hud-surface p-5 lg:col-span-2" data-testid="truth-margin-hold">
          <div className="text-[10px] font-mono uppercase tracking-[0.25em] text-slate-500 mb-2">Do margins hold? forecast vs settled</div>
          {d.margin_truth?.settled_loads > 0 ? (
            <>
              <div className="flex items-end gap-6">
                <div><div className="text-[9px] font-mono text-slate-500">FORECAST</div><div className="text-2xl font-black text-slate-200">{fmt$(d.margin_truth.forecast_usd)}</div></div>
                <div><div className="text-[9px] font-mono text-slate-500">SETTLED</div><div className="text-2xl font-black text-cyan-300">{fmt$(d.margin_truth.settled_usd)}</div></div>
                <div><div className="text-[9px] font-mono text-slate-500">MARGIN HELD</div>
                  <div className={`text-2xl font-black ${d.margin_truth.margin_hold_pct >= 95 ? "text-emerald-300" : "text-amber-300"}`} data-testid="margin-hold-pct">{d.margin_truth.margin_hold_pct}%</div></div>
              </div>
              <div className="text-[9px] font-mono uppercase text-slate-500 mt-4 mb-1.5">Worst drifts</div>
              <div className="space-y-1 max-h-32 overflow-y-auto">
                {(d.margin_truth.worst_drifts || []).map((w) => (
                  <div key={w.booked_id} className="flex justify-between text-[10px] font-mono">
                    <span className="text-slate-400 truncate">{w.lane} · {w.carrier}</span>
                    <span className={w.drift_usd < 0 ? "text-red-300" : "text-emerald-300"}>{w.drift_usd < 0 ? "" : "+"}{fmt$(w.drift_usd)}</span>
                  </div>
                ))}
              </div>
            </>
          ) : <div className="text-slate-500 text-sm py-6">No settled loads in the window yet — margin-hold lights up as loads settle. Forecast tracking is live on every booking.</div>}
        </Card>
      </div>

      <Card className="hud-surface p-4" data-testid="truth-carriers">
        <div className="text-[10px] font-mono uppercase tracking-[0.25em] text-slate-500 mb-2">Which carriers convert</div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead><tr className="text-left text-[9px] font-mono uppercase tracking-widest text-slate-500 border-b border-white/10">
              <th className="py-2 pr-3">Carrier</th><th className="py-2 pr-3">Assigned</th><th className="py-2 pr-3">Completed</th>
              <th className="py-2 pr-3">Conversion</th><th className="py-2 pr-3">Forecast Margin</th><th className="py-2">Margin Held</th></tr></thead>
            <tbody>
              {(d.carriers || []).map((c) => (
                <tr key={c.carrier} className="border-b border-white/5">
                  <td className="py-2 pr-3 text-slate-200">{c.carrier}</td>
                  <td className="py-2 pr-3 font-mono text-slate-400">{c.assigned}</td>
                  <td className="py-2 pr-3 font-mono text-slate-400">{c.completed}</td>
                  <td className="py-2 pr-3">
                    <div className="flex items-center gap-2">
                      <div className="h-1.5 w-20 rounded bg-white/5 overflow-hidden"><div className="h-full rounded bg-cyan-400" style={{ width: `${c.conversion_pct}%` }} /></div>
                      <span className="font-mono text-cyan-300 text-[10px]">{c.conversion_pct}%</span>
                    </div>
                  </td>
                  <td className="py-2 pr-3 font-mono text-slate-300">{fmt$(c.forecast_margin)}</td>
                  <td className="py-2 font-mono">{c.margin_hold_pct != null ? <span className={c.margin_hold_pct >= 95 ? "text-emerald-300" : "text-amber-300"}>{c.margin_hold_pct}%</span> : <span className="text-slate-600">awaiting settle</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

function PlaybookTab() {
  const [d, setD] = useState(null);
  useEffect(() => { api.get("/ops-truth/match-playbook").then(({ data }) => setD(data)).catch(() => toast.error("Playbook failed")); }, []);
  if (!d) return <Card className="hud-surface p-10 text-center text-slate-500 text-sm">Learning from your loads…</Card>;
  return (
    <div className="space-y-4" data-testid="match-playbook-panel">
      <Card className="hud-surface p-4 border-cyan-500/20">
        <div className="flex items-center gap-2 text-xs text-cyan-300">
          <BrainCircuit size={14} className="text-amber-400" />
          <span><b>{d.pairs_learned}</b> shipper↔carrier pairings learned from <b>{d.loads_observed}</b> loads — {d.learning_note}</span>
        </div>
      </Card>
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3" data-testid="playbook-recommendations">
        {(d.recommendations || []).map((r) => (
          <Card key={r.shipper} className="hud-surface p-4">
            <div className="flex items-center justify-between">
              <div className="text-xs font-bold text-slate-100 truncate">{r.shipper}</div>
              <Badge className="bg-emerald-500/15 text-emerald-300 border-emerald-500/30 text-[9px] font-mono">{r.match_score}</Badge>
            </div>
            <div className="text-[11px] text-cyan-300 mt-1 flex items-center gap-1"><TrendingUp size={11} /> {r.carrier}</div>
            <div className="text-[10px] text-slate-400 mt-1.5">{r.note}</div>
          </Card>
        ))}
        {!(d.recommendations || []).length && <div className="text-slate-500 text-sm py-8 col-span-full text-center">Book loads with named carriers and the playbook starts recommending pairings automatically.</div>}
      </div>
      <Card className="hud-surface p-4" data-testid="playbook-pairs">
        <div className="text-[10px] font-mono uppercase tracking-[0.25em] text-slate-500 mb-2">All learned pairings</div>
        <div className="overflow-x-auto max-h-80 overflow-y-auto">
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-[#0B0E14]"><tr className="text-left text-[9px] font-mono uppercase tracking-widest text-slate-500 border-b border-white/10">
              <th className="py-2 pr-3">Shipper</th><th className="py-2 pr-3">Carrier</th><th className="py-2 pr-3">Loads</th>
              <th className="py-2 pr-3">Completion</th><th className="py-2 pr-3">Margin %</th><th className="py-2">Score</th></tr></thead>
            <tbody>
              {(d.pairs || []).map((p) => (
                <tr key={p.shipper + p.carrier} className="border-b border-white/5">
                  <td className="py-1.5 pr-3 text-slate-200 truncate max-w-[180px]">{p.shipper}</td>
                  <td className="py-1.5 pr-3 text-slate-300 truncate max-w-[160px]">{p.carrier}</td>
                  <td className="py-1.5 pr-3 font-mono text-slate-400">{p.loads}</td>
                  <td className="py-1.5 pr-3 font-mono text-cyan-300">{p.completion_pct}%</td>
                  <td className="py-1.5 pr-3 font-mono text-slate-300">{p.margin_pct}%</td>
                  <td className="py-1.5 font-mono text-emerald-300">{p.match_score}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
