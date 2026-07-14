import React, { useCallback, useEffect, useRef, useState } from "react";
import { MapContainer, TileLayer, Marker, Popup, Polyline } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import Topbar from "@/components/Topbar";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { toast } from "sonner";
import ReactMarkdown from "react-markdown";
import {
  FlaskConical, Rocket, Pause, Play, RotateCcw, Loader2, Truck, DollarSign,
  ShieldAlert, FileDown, Trophy, Zap, CheckCircle2, Brain, Send,
} from "lucide-react";
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip } from "recharts";

const fmt = (n) => (n == null ? "—" : Number(n).toLocaleString(undefined, { maximumFractionDigits: 0 }));
const STATUS_COLOR = {
  posted: "text-slate-400", booked: "text-cyan-300", at_pickup: "text-yellow-300",
  in_transit: "text-emerald-300", delivered: "text-emerald-400", invoiced: "text-yellow-300",
  factored: "text-purple-300", paid: "text-emerald-300",
};

const MKT_BADGE = {
  headhaul: { label: "HH", cls: "text-red-300 border-red-500/30", title: "Headhaul — hot lane, rates priced up, margin compressed" },
  backhaul: { label: "BH", cls: "text-sky-300 border-sky-500/30", title: "Backhaul — cheap lane, rates discounted, margin widened" },
};

const truckIcon = (exc) => L.divIcon({
  className: "",
  html: `<div style="background:${exc ? "#ef4444" : "#22d3ee"};border:2px solid #0b1320;border-radius:50%;width:16px;height:16px;display:flex;align-items:center;justify-content:center;box-shadow:0 0 8px ${exc ? "#ef444488" : "#22d3ee88"}"><span style="font-size:8px">🚛</span></div>`,
  iconSize: [16, 16], iconAnchor: [8, 8],
});

function Stat({ label, value, accent = "text-cyan-300", tid }) {
  return (
    <div className="rounded border border-white/10 bg-white/[0.03] px-3 py-2 min-w-[118px]" data-testid={tid}>
      <div className={`font-mono font-bold text-base ${accent}`}>{value}</div>
      <div className="text-[9px] font-mono uppercase tracking-[0.15em] text-slate-500">{label}</div>
    </div>
  );
}

function LaunchScreen({ onStart, busy }) {
  const [cfg, setCfg] = useState({ duration_days: 7, loads_per_day: 10, sim_minutes_per_real_second: 12, autopilot: true, auto_triage: true });
  return (
    <Card className="hud-surface p-8 max-w-3xl mx-auto text-center" data-testid="sim-launch-screen">
      <FlaskConical size={42} className="mx-auto text-cyan-400 mb-3" />
      <h2 className="font-display text-3xl font-black">Operation Sandbox</h2>
      <p className="text-sm text-slate-400 mt-2 max-w-xl mx-auto">
        Run a full brokerage week against a 36-carrier nationwide sample network. Real load-board economics —
        regional lane imbalance (headhaul/backhaul pricing), monthly seasonality curves,
        current FSC (${"0.41"}/mi @ DOE $3.68) — live GPS movement, AI matching &amp; triage, BOL/POD/invoicing,
        factoring, and a running P&amp;L. Every load is marked <span className="text-yellow-300 font-mono">SAMPLE</span>.
      </p>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mt-6 text-left">
        {[["duration_days", "Week length (days)", 1, 14], ["loads_per_day", "Loads / day", 3, 25],
          ["sim_minutes_per_real_second", "Sim min per real sec", 1, 120]].map(([k, label, min, max]) => (
          <div key={k}>
            <div className="text-[9px] font-mono uppercase text-slate-500 mb-1">{label}</div>
            <input type="number" min={min} max={max} value={cfg[k]} data-testid={`sim-cfg-${k}`}
              onChange={(e) => setCfg((c) => ({ ...c, [k]: Number(e.target.value) }))}
              className="w-full h-9 rounded bg-slate-950 border border-white/10 font-mono text-sm px-3 text-slate-200" />
          </div>
        ))}
        <label className="flex items-center gap-2 text-[10px] font-mono uppercase text-slate-400 mt-4">
          <Switch checked={cfg.autopilot} onCheckedChange={(v) => setCfg((c) => ({ ...c, autopilot: v }))} data-testid="sim-cfg-autopilot" />
          AI Autopilot (books loads)
        </label>
        <label className="flex items-center gap-2 text-[10px] font-mono uppercase text-slate-400 mt-4">
          <Switch checked={cfg.auto_triage} onCheckedChange={(v) => setCfg((c) => ({ ...c, auto_triage: v }))} data-testid="sim-cfg-autotriage" />
          AI Triage (auto-resolves)
        </label>
      </div>
      <div className="text-[10px] font-mono text-slate-500 mt-4">
        At {cfg.sim_minutes_per_real_second} sim-min/sec, one sim day ≈ {Math.round(1440 / cfg.sim_minutes_per_real_second / 60 * 10) / 10} real minutes.
      </div>
      <Button onClick={() => onStart(cfg)} disabled={busy} data-testid="sim-launch-btn"
        className="mt-6 bg-cyan-500 hover:bg-cyan-400 text-black font-black font-mono text-sm uppercase tracking-widest px-8 py-6">
        {busy ? <Loader2 size={16} className="mr-2 animate-spin" /> : <Rocket size={16} className="mr-2" />}
        Launch The Week
      </Button>
    </Card>
  );
}

function AiAnalysisPanel({ analysis }) {
  const [analyzing, setAnalyzing] = useState(false);
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [qa, setQa] = useState([]);
  const [report, setReport] = useState(analysis || null);
  const chatEndRef = useRef(null);

  useEffect(() => { if (analysis && !report) setReport(analysis); }, [analysis, report]);
  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [qa]);

  const runAnalysis = async () => {
    setAnalyzing(true);
    try {
      const { data } = await api.post("/sim/analyze");
      setReport(data.analysis);
      toast.success("🧠 Deep analysis complete");
    } catch (e) { toast.error(e?.response?.data?.detail || "Analysis failed"); }
    finally { setAnalyzing(false); }
  };

  const ask = async () => {
    const q = question.trim();
    if (!q || asking) return;
    setAsking(true);
    setQa((prev) => [...prev, { q, a: null }]);
    setQuestion("");
    try {
      const { data } = await api.post("/sim/ask", { question: q });
      setQa((prev) => prev.map((x, i) => (i === prev.length - 1 ? { ...x, a: data.answer } : x)));
    } catch (e) {
      setQa((prev) => prev.map((x, i) => (i === prev.length - 1 ? { ...x, a: `⚠ ${e?.response?.data?.detail || "Failed to answer"}` } : x)));
    } finally { setAsking(false); }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4" data-testid="sim-ai-section">
      <Card className="hud-surface p-4" data-testid="sim-ai-analysis">
        <div className="flex items-center justify-between mb-2">
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-purple-300 flex items-center gap-1.5">
            <Brain size={12} /> Deep AI Post-Mortem
          </div>
          <Button size="sm" onClick={runAnalysis} disabled={analyzing} data-testid="sim-analyze-btn"
            className="bg-purple-500/20 border border-purple-500/40 text-purple-200 font-mono text-[10px] uppercase hover:bg-purple-500/30">
            {analyzing ? <Loader2 size={12} className="mr-1 animate-spin" /> : <Brain size={12} className="mr-1" />}
            {report ? "Re-Analyze Week" : "Analyze The Week"}
          </Button>
        </div>
        {analyzing && !report && (
          <div className="text-[11px] font-mono text-slate-500 py-8 text-center">
            Claude is reviewing every load, lane, carrier, and dollar…
          </div>
        )}
        {!report && !analyzing && (
          <div className="text-[11px] font-mono text-slate-500 py-8 text-center">
            Run the analysis to get a full operations post-mortem: what worked, what leaked money, and 5 moves for next week.
          </div>
        )}
        {report && (
          <div className="prose prose-invert prose-sm max-w-none max-h-80 overflow-y-auto text-[12px] leading-relaxed [&_h2]:text-purple-300 [&_h2]:text-sm [&_h2]:font-mono [&_h2]:uppercase [&_h2]:tracking-wider [&_li]:my-0.5"
            data-testid="sim-analysis-report">
            <ReactMarkdown>{report}</ReactMarkdown>
          </div>
        )}
      </Card>

      <Card className="hud-surface p-4 flex flex-col" data-testid="sim-ai-chat">
        <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-300 flex items-center gap-1.5 mb-2">
          <Zap size={12} /> Ask The Analyst
        </div>
        <div className="flex-1 space-y-2 max-h-72 overflow-y-auto mb-3" data-testid="sim-chat-history">
          {qa.length === 0 && (
            <div className="text-[10px] font-mono text-slate-500 space-y-1.5 pt-2">
              <div>Grounded in this week's actual numbers. Try:</div>
              {["Which lane made the most margin and why?", "Where did we leak money on exceptions?",
                "Which carrier should get more freight next week?", "Why was margin low on the worst day?"].map((s) => (
                <button key={s} onClick={() => setQuestion(s)} data-testid="sim-chat-suggestion"
                  className="block text-left text-cyan-400/80 hover:text-cyan-300 border border-white/5 rounded px-2 py-1 w-full">
                  → {s}
                </button>
              ))}
            </div>
          )}
          {qa.map((item, i) => (
            <div key={i} className="space-y-1.5">
              <div className="text-[11px] font-mono text-cyan-200 bg-cyan-500/[0.06] border border-cyan-500/20 rounded p-2 ml-6">{item.q}</div>
              {item.a === null ? (
                <div className="text-[11px] font-mono text-slate-500 p-2 flex items-center gap-1.5 mr-6">
                  <Loader2 size={11} className="animate-spin" /> thinking…
                </div>
              ) : (
                <div className="text-[11px] text-slate-300 bg-white/[0.03] border border-white/10 rounded p-2 mr-6 prose prose-invert prose-sm max-w-none [&_p]:my-1">
                  <ReactMarkdown>{item.a}</ReactMarkdown>
                </div>
              )}
            </div>
          ))}
          <div ref={chatEndRef} />
        </div>
        <div className="flex gap-2">
          <input value={question} onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && ask()} data-testid="sim-chat-input"
            placeholder="Ask anything about this week's operation…"
            className="flex-1 h-9 rounded bg-slate-950 border border-white/10 font-mono text-[11px] px-3 text-slate-200 placeholder:text-slate-600" />
          <Button size="sm" onClick={ask} disabled={asking || !question.trim()} data-testid="sim-chat-send-btn"
            className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold h-9">
            {asking ? <Loader2 size={13} className="animate-spin" /> : <Send size={13} />}
          </Button>
        </div>
      </Card>
    </div>
  );
}

export default function OperationSandbox() {
  const [state, setState] = useState(null);
  const [busy, setBusy] = useState(false);
  const timerRef = useRef(null);
  const running = state?.active && state?.sim?.status === "running";

  const refresh = useCallback(async () => {
    try { const { data } = await api.get("/sim/state"); setState(data); } catch {}
  }, []);
  useEffect(() => { refresh(); }, [refresh]);

  useEffect(() => {
    if (timerRef.current) clearInterval(timerRef.current);
    if (running) {
      timerRef.current = setInterval(async () => {
        try { const { data } = await api.post("/sim/tick"); setState(data); } catch {}
      }, 3500);
    }
    return () => timerRef.current && clearInterval(timerRef.current);
  }, [running]);

  const start = async (cfg) => {
    setBusy(true);
    try {
      await api.post("/sim/start", cfg);
      toast.success("🚀 Operation Sandbox is live — the week has begun");
      const { data } = await api.post("/sim/tick");
      setState(data);
    } catch (e) { toast.error(e?.response?.data?.detail || "Launch failed"); }
    finally { setBusy(false); }
  };
  const act = async (url, msg) => {
    try { await api.post(url); toast.success(msg); refresh(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Action failed"); }
  };
  const resolve = async (loadId) => {
    try {
      const { data } = await api.post(`/sim/triage/${loadId}/resolve`);
      toast.success(`Plan executed: ${data.plan_executed.slice(0, 90)}…`);
      refresh();
    } catch (e) { toast.error(e?.response?.data?.detail || "Resolve failed"); }
  };
  const manual = async () => {
    try {
      const res = await api.get("/brokerage/platform-manual.pdf", { responseType: "blob" });
      const url = window.URL.createObjectURL(new Blob([res.data], { type: "application/pdf" }));
      const a = document.createElement("a");
      a.href = url; a.download = "Orisei_Command_Deck_Field_Manual.pdf";
      document.body.appendChild(a); a.click(); document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch { toast.error("Manual download failed"); }
  };

  const sim = state?.sim;
  const ledger = state?.ledger || {};
  const kpis = state?.kpis || {};
  const activeLoads = (state?.loads || []).filter((l) => ["booked", "at_pickup", "in_transit"].includes(l.status));
  const clock = sim?.sim_clock ? new Date(sim.sim_clock) : null;

  return (
    <>
      <Topbar title="Operation Sandbox" />
      <div className="p-6 max-w-[1500px] mx-auto space-y-4" data-testid="sim-page">
        {!state?.active ? (
          <LaunchScreen onStart={start} busy={busy} />
        ) : (
          <>
            {/* Command bar */}
            <Card className="hud-surface p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 flex items-center gap-1.5">
                    <FlaskConical size={11} /> {sim.status === "complete" ? "Week Complete" : "Simulation Live"} · All loads marked SAMPLE
                  </div>
                  <div className="font-display text-2xl font-black flex items-center gap-3" data-testid="sim-clock">
                    Day {sim.sim_day} <span className="text-slate-600">/</span> {sim.duration_days}
                    <span className="font-mono text-cyan-300 text-lg">
                      {clock && clock.toLocaleString("en-US", { weekday: "short", hour: "2-digit", minute: "2-digit", timeZone: "UTC" })}
                    </span>
                  </div>
                  <div className="w-64 h-1.5 rounded bg-white/5 mt-1 overflow-hidden">
                    <div className="h-full bg-cyan-400" style={{ width: `${Math.min(100, ((sim.sim_day - 1) / sim.duration_days) * 100)}%` }} />
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Button size="sm" variant="ghost" onClick={manual} data-testid="sim-manual-btn"
                    className="border border-white/10 text-slate-300 font-mono text-[10px] uppercase">
                    <FileDown size={12} className="mr-1" /> Field Manual
                  </Button>
                  {sim.status === "running" && (
                    <Button size="sm" onClick={() => act("/sim/pause", "Paused")} data-testid="sim-pause-btn"
                      className="bg-white/5 border border-white/10 text-slate-300 font-mono text-[10px] uppercase">
                      <Pause size={12} className="mr-1" /> Pause
                    </Button>
                  )}
                  {sim.status === "paused" && (
                    <Button size="sm" onClick={() => act("/sim/resume", "Resumed")} data-testid="sim-resume-btn"
                      className="bg-emerald-500 text-black font-bold font-mono text-[10px] uppercase">
                      <Play size={12} className="mr-1" /> Resume
                    </Button>
                  )}
                  <Button size="sm" onClick={() => window.confirm("Purge ALL sample data?") && act("/sim/reset", "Sandbox purged — all sample data removed")}
                    data-testid="sim-reset-btn"
                    className="bg-white/5 border border-red-500/30 text-red-300 font-mono text-[10px] uppercase">
                    <RotateCcw size={12} className="mr-1" /> Reset
                  </Button>
                </div>
              </div>
              <div className="flex flex-wrap gap-2 mt-4" data-testid="sim-kpis">
                <Stat label="Revenue" value={`$${fmt(ledger.revenue)}`} accent="text-emerald-300" tid="sim-kpi-revenue" />
                <Stat label="Carrier Pay" value={`$${fmt(ledger.carrier_pay)}`} accent="text-slate-300" />
                <Stat label="Net Margin" value={`$${fmt(ledger.net_margin)}`} accent="text-yellow-300" tid="sim-kpi-margin" />
                <Stat label="Cash Collected" value={`$${fmt(ledger.cash_collected)}`} accent="text-emerald-300" />
                <Stat label="AR Outstanding" value={`$${fmt(ledger.outstanding_ar)}`} accent="text-orange-300" />
                <Stat label="Factoring Fees" value={`$${fmt(ledger.factoring_fees)}`} accent="text-purple-300" />
                <Stat label="Loads" value={`${kpis.delivered || 0}/${kpis.total_loads || 0}`} accent="text-cyan-300" tid="sim-kpi-loads" />
                <Stat label="Avg Loads/Day" value={kpis.avg_daily_loads ?? "—"} accent="text-cyan-300" tid="sim-kpi-avg-daily" />
                <Stat label="In Transit" value={kpis.active_transit || 0} accent="text-emerald-300" />
                <Stat label="On-Time" value={`${kpis.on_time_pct ?? 100}%`} accent="text-emerald-300" />
                <Stat label="FSC / DOE" value={`$${sim.fsc_per_mile}/mi`} accent="text-slate-300" />
              </div>
            </Card>

            <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
              {/* Live map */}
              <Card className="hud-surface p-0 overflow-hidden xl:col-span-2" style={{ height: 440 }} data-testid="sim-map">
                <MapContainer center={[39.5, -96.5]} zoom={4} style={{ height: "100%", width: "100%" }} scrollWheelZoom>
                  <TileLayer url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
                    attribution="&copy; OpenStreetMap &copy; CARTO" />
                  {activeLoads.map((l) => (
                    <React.Fragment key={l.load_id}>
                      <Polyline positions={[[l.origin.lat, l.origin.lng], [l.dest.lat, l.dest.lng]]}
                        pathOptions={{ color: l.exception ? "#ef4444" : "#22d3ee", weight: 1, opacity: 0.35, dashArray: "4 6" }} />
                      <Marker position={[l.position.lat, l.position.lng]} icon={truckIcon(l.exception)}>
                        <Popup>
                          <div style={{ fontFamily: "monospace", fontSize: 11 }}>
                            <b>{l.load_id}</b> · {l.status}<br />
                            {l.origin.name} → {l.dest.name}<br />
                            {l.carrier?.name} · {l.carrier?.driver}<br />
                            {Math.round(l.progress * 100)}% · ${fmt(l.sell_usd)} · margin ${fmt(l.margin_usd)}
                            {l.market && <><br />{l.market.headhaul} · lane ×{l.market.lane_mult} · season ×{l.market.seasonal_mult}</>}
                            {l.exception && <><br /><span style={{ color: "#ef4444" }}>⚠ {l.exception.title}</span></>}
                          </div>
                        </Popup>
                      </Marker>
                    </React.Fragment>
                  ))}
                </MapContainer>
              </Card>

              {/* Event feed + triage */}
              <div className="space-y-4">
                <Card className="hud-surface p-4" data-testid="sim-triage">
                  <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-red-300 flex items-center gap-1.5 mb-2">
                    <ShieldAlert size={12} /> AI Triage Queue ({(state.triage || []).length})
                  </div>
                  <div className="space-y-2 max-h-36 overflow-y-auto">
                    {(state.triage || []).length === 0 && (
                      <div className="text-[10px] font-mono text-slate-500 flex items-center gap-1.5">
                        <CheckCircle2 size={11} className="text-emerald-400" /> No open exceptions — AI is handling the board.
                      </div>
                    )}
                    {(state.triage || []).map((t) => (
                      <div key={t.load_id} className="p-2 rounded border border-red-500/20 bg-red-500/[0.04]">
                        <div className="text-[11px] text-slate-200">{t.load_id} · {t.title}</div>
                        <div className="text-[9px] font-mono text-slate-500">{t.lane} · {t.carrier}</div>
                        <div className="text-[9px] font-mono text-slate-400 mt-1">{(t.plan || "").slice(0, 110)}…</div>
                        <button onClick={() => resolve(t.load_id)} data-testid={`sim-resolve-${t.load_id}`}
                          className="mt-1.5 text-[9px] font-mono uppercase text-emerald-300 border border-emerald-500/30 rounded px-2 py-0.5 hover:bg-emerald-500/10">
                          <Zap size={9} className="inline mr-1" />Execute AI Plan
                        </button>
                      </div>
                    ))}
                  </div>
                </Card>
                <Card className="hud-surface p-4" data-testid="sim-events">
                  <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-2">Live Ops Feed</div>
                  <div className="space-y-1 max-h-56 overflow-y-auto">
                    {(state.events || []).map((e) => (
                      <div key={e.id} className={`text-[10px] font-mono p-1.5 rounded bg-white/[0.02] ${e.severity === "error" ? "text-red-300" : e.severity === "warn" ? "text-yellow-300" : "text-slate-300"}`}>
                        <span className="text-slate-600">{new Date(e.sim_time).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", timeZone: "UTC" })}</span> {e.message}
                      </div>
                    ))}
                  </div>
                </Card>
              </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              {/* Daily P&L */}
              <Card className="hud-surface p-4" data-testid="sim-daily-chart">
                <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-emerald-300 mb-2 flex items-center gap-1.5">
                  <DollarSign size={12} /> Margin By Day
                </div>
                {(sim.daily || []).length === 0 ? (
                  <div className="text-[10px] font-mono text-slate-500 py-8 text-center">Day 1 in progress…</div>
                ) : (
                  <ResponsiveContainer width="100%" height={180}>
                    <BarChart data={sim.daily}>
                      <XAxis dataKey="day" tick={{ fill: "#64748b", fontSize: 9 }} tickFormatter={(d) => `D${d}`} />
                      <YAxis tick={{ fill: "#64748b", fontSize: 9 }} tickFormatter={(v) => `$${v / 1000}k`} width={40} />
                      <Tooltip contentStyle={{ background: "#0b1320", border: "1px solid rgba(255,255,255,0.1)", fontSize: 11 }} />
                      <Bar dataKey="margin" fill="#34d399" radius={[3, 3, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </Card>
              {/* Carrier leaderboard */}
              <Card className="hud-surface p-4" data-testid="sim-leaderboard">
                <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-yellow-300 mb-2 flex items-center gap-1.5">
                  <Trophy size={12} /> Carrier Leaderboard
                </div>
                <div className="space-y-1.5 max-h-44 overflow-y-auto">
                  {(state.leaderboard || []).map((c, i) => (
                    <div key={c.carrier} className="flex items-center justify-between text-[11px] font-mono p-1.5 rounded bg-white/[0.02]">
                      <span className="text-slate-300 truncate">{i + 1}. {c.carrier}</span>
                      <span className="text-slate-500">{c.loads} · <span className="text-emerald-300">${fmt(c.margin)}</span></span>
                    </div>
                  ))}
                </div>
              </Card>
              {/* Loads table */}
              <Card className="hud-surface p-4" data-testid="sim-loads-table">
                <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-2 flex items-center gap-1.5">
                  <Truck size={12} /> Load Board ({(state.loads || []).length})
                </div>
                <div className="space-y-1.5 max-h-44 overflow-y-auto">
                  {(state.loads || []).slice(0, 40).map((l) => (
                    <div key={l.load_id} className="text-[10px] font-mono p-1.5 rounded bg-white/[0.02] flex items-center justify-between gap-2">
                      <div className="min-w-0">
                        <span className="text-slate-200">{l.load_id}</span>
                        {MKT_BADGE[l.market?.headhaul] && (
                          <span title={MKT_BADGE[l.market.headhaul].title}
                            className={`ml-1 text-[8px] border rounded px-1 ${MKT_BADGE[l.market.headhaul].cls}`}>
                            {MKT_BADGE[l.market.headhaul].label}
                          </span>
                        )}
                        <span className="text-slate-500"> {l.origin.name.split(",")[0]}→{l.dest.name.split(",")[0]}</span>
                        {l.booked_id && (l.status !== "posted") && (
                          <span className="ml-1">
                            <a className="text-cyan-400 hover:underline" href={`${process.env.REACT_APP_BACKEND_URL}/api/brokerage/bookings/${l.booked_id}/bol.pdf`} target="_blank" rel="noreferrer">BOL</a>
                            {["delivered", "invoiced", "factored", "paid"].includes(l.status) && (
                              <> · <a className="text-cyan-400 hover:underline" href={`${process.env.REACT_APP_BACKEND_URL}/api/brokerage/bookings/${l.booked_id}/pod.pdf`} target="_blank" rel="noreferrer">POD</a></>
                            )}
                          </span>
                        )}
                      </div>
                      <span className={`uppercase shrink-0 ${STATUS_COLOR[l.status] || "text-slate-400"}`}>{l.status.replace("_", " ")}</span>
                    </div>
                  ))}
                </div>
              </Card>
            </div>

            <AiAnalysisPanel analysis={state?.analysis} />
          </>
        )}
      </div>
    </>
  );
}
