import React, { useCallback, useEffect, useState } from "react";
import Topbar from "../components/Topbar";
import { Card } from "../components/ui/card";
import { ShieldCheck, Play, Loader2, ChevronDown, ChevronRight, Timer, Gauge, CheckCircle2, AlertTriangle, XCircle, History, FileDown, Moon, BellRing } from "lucide-react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { toast } from "sonner";
import { api } from "../lib/api";

const VERDICT = {
  READY_TO_SELL: { label: "READY TO SELL", color: "text-emerald-400", border: "border-emerald-500/40", bg: "bg-emerald-500/10", blurb: "Every advertised capability verified. Pitch with confidence." },
  NEEDS_ATTENTION: { label: "NEEDS ATTENTION", color: "text-orange-400", border: "border-orange-500/40", bg: "bg-orange-500/10", blurb: "Core flows pass but some modules need a look before you demo them." },
  NOT_READY: { label: "NOT READY", color: "text-red-400", border: "border-red-500/40", bg: "bg-red-500/10", blurb: "A critical functional check failed — fix before selling." },
};
const STATUS_ICON = {
  pass: <CheckCircle2 size={14} className="text-emerald-400" />,
  warn: <AlertTriangle size={14} className="text-orange-400" />,
  fail: <XCircle size={14} className="text-red-400" />,
};

export default function PlatformReadiness() {
  const [run, setRun] = useState(null);
  const [runs, setRuns] = useState([]);
  const [busy, setBusy] = useState(false);
  const [openCats, setOpenCats] = useState({});
  const [nightly, setNightly] = useState(null);

  const loadNightly = useCallback(() => api.get("/hotshot/readiness/nightly").then((r) => setNightly(r.data)).catch(() => {}), []);
  useEffect(() => { loadNightly(); }, [loadNightly]);

  const load = useCallback(async () => {
    try {
      const [l, h] = await Promise.all([api.get("/hotshot/readiness/latest"), api.get("/hotshot/readiness/runs")]);
      if (l.data.run) setRun(l.data.run);
      setRuns(h.data.runs.slice().reverse());
    } catch (_) {}
  }, []);
  useEffect(() => { load(); }, [load]);

  const execute = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/hotshot/readiness/run", {}, { timeout: 120000 });
      setRun(data);
      setOpenCats({ [data.categories[0].name]: true });
      toast.success(`Self-test complete — ${data.metrics.passed}/${data.metrics.total_checks} checks passed`);
      load();
    } catch (e) { toast.error("Self-test failed to complete — check backend logs"); }
    finally { setBusy(false); }
  };

  const downloadReport = async () => {
    try {
      const r = await api.get("/hotshot/readiness/report.pdf", { responseType: "blob" });
      const url = URL.createObjectURL(r.data);
      const a = document.createElement("a");
      a.href = url; a.download = "HotShot_TMS_Verification_Report.pdf"; a.click();
      URL.revokeObjectURL(url);
    } catch (_) { toast.error("Run the self-test first"); }
  };

  const ackAlert = async (id) => {
    try { await api.post(`/hotshot/readiness/alerts/${id}/ack`); loadNightly(); } catch (_) {}
  };

  const v = run ? VERDICT[run.verdict] || VERDICT.NEEDS_ATTENTION : null;
  const chart = runs.map((r) => ({ name: r.run_id.slice(-4), pass: r.metrics.pass_rate, p95: r.metrics.p95_latency_ms }));

  return (
    <>
      <Topbar title="Platform Readiness" subtitle="Sell-ready self-test — every feature advertised on the Hot Shot TMS landing page, verified live with full reliability & efficiency metrics" />
      <div className="p-4 md:p-6 space-y-5" data-testid="platform-readiness-page">
        {/* Verdict + run */}
        <Card className={`p-5 bg-slate-950/60 ${v ? v.border : "border-white/10"}`} data-testid="pr-verdict-card">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className={`w-14 h-14 rounded-2xl grid place-items-center ${v ? v.bg : "bg-white/5"}`}>
                <ShieldCheck size={26} className={v ? v.color : "text-slate-500"} />
              </div>
              <div>
                <div className={`text-2xl font-black tracking-tight ${v ? v.color : "text-slate-400"}`} data-testid="pr-verdict">
                  {v ? v.label : "NO RUNS YET"}
                </div>
                <div className="text-xs text-slate-400 max-w-md">{v ? v.blurb : "Run the self-test to verify every advertised capability against the live platform."}</div>
                {run && <div className="text-[10px] font-mono text-slate-500 mt-1">{run.run_id} · {new Date(run.started_at).toLocaleString()} · full suite in {(run.duration_ms / 1000).toFixed(1)}s</div>}
              </div>
            </div>
            <div className="flex items-center gap-3">
              <button onClick={downloadReport} disabled={!run} data-testid="pr-download-pdf-btn"
                      className="px-5 py-3 rounded-full border border-white/15 hover:border-amber-400/50 text-slate-200 font-bold text-sm inline-flex items-center gap-2 disabled:opacity-40">
                <FileDown size={15} /> PDF Report
              </button>
              <button onClick={execute} disabled={busy} data-testid="pr-run-btn"
                      className="px-6 py-3 rounded-full bg-amber-500 text-black font-black text-sm inline-flex items-center gap-2 hover:bg-amber-400 disabled:opacity-60">
                {busy ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
                {busy ? "Testing every module…" : "Run Full Self-Test"}
              </button>
            </div>
          </div>
        </Card>

        {/* Open alerts */}
        {nightly?.open_alerts?.length > 0 && (
          <Card className="p-4 bg-red-500/10 border-red-500/40" data-testid="pr-alerts-card">
            <div className="text-xs font-mono uppercase tracking-widest text-red-400 flex items-center gap-2 mb-2"><BellRing size={13} /> Sell-ready alerts</div>
            {nightly.open_alerts.map((a) => (
              <div key={a.alert_id} className="flex flex-wrap items-center gap-3 py-2 border-b border-red-500/20 last:border-0 text-sm">
                <span className="font-mono text-[10px] text-slate-500">{new Date(a.at).toLocaleString()}</span>
                <span className="text-red-300 font-bold">{a.verdict.replace(/_/g, " ")} · score {a.score}</span>
                <span className="text-slate-400 text-xs flex-1 truncate">{(a.failed_checks || []).slice(0, 3).join(" · ")}</span>
                <button onClick={() => ackAlert(a.alert_id)} data-testid={`pr-ack-${a.alert_id}`}
                        className="px-3 py-1 rounded-full border border-red-500/40 text-red-300 text-xs font-bold hover:bg-red-500/10">Acknowledge</button>
              </div>
            ))}
          </Card>
        )}

        {/* Nightly watchdog */}
        <Card className="p-4 bg-slate-950/60 border-white/10" data-testid="pr-nightly-card">
          <div className="flex flex-wrap items-center gap-4">
            <div className="w-10 h-10 rounded-xl bg-indigo-500/15 grid place-items-center"><Moon size={18} className="text-indigo-300" /></div>
            <div className="flex-1 min-w-[220px]">
              <div className="font-black text-sm text-white">Nightly self-test watchdog <span className="ml-2 text-[9px] font-mono uppercase px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-300 border border-emerald-500/40">armed</span></div>
              <div className="text-xs text-slate-400">Runs the full suite every night at {nightly ? `${nightly.hour_utc}:00 UTC` : "…"} and raises an alert (plus email, once your Resend key is in) if the platform drops below sell-ready.</div>
            </div>
            <div className="text-right">
              <div className="text-[10px] font-mono uppercase text-slate-500">Next run</div>
              <div className="text-sm font-bold text-indigo-300" data-testid="pr-nightly-next">{nightly ? new Date(nightly.next_run_at).toLocaleString() : "—"}</div>
              {nightly?.last_nightly && (
                <div className="text-[10px] text-slate-500 font-mono mt-0.5">last: {nightly.last_nightly.verdict.replace(/_/g, " ")} · {nightly.last_nightly.score}</div>
              )}
            </div>
          </div>
        </Card>

        {run && (
          <>
            {/* Metrics */}
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3" data-testid="pr-metrics">
              {[
                ["Readiness score", `${run.score}`, "text-amber-400"],
                ["Checks passed", `${run.metrics.passed}/${run.metrics.total_checks}`, "text-emerald-400"],
                ["Pass rate", `${run.metrics.pass_rate}%`, "text-emerald-400"],
                ["Deep functional", run.metrics.functional_pass, "text-cyan-300"],
                ["Avg latency", `${run.metrics.avg_latency_ms}ms`, "text-purple-300"],
                ["P95 latency", `${run.metrics.p95_latency_ms}ms`, "text-orange-300"],
              ].map(([label, val, color]) => (
                <Card key={label} className="p-4 bg-slate-950/60 border-white/10">
                  <div className={`text-xl font-black tabular-nums ${color}`}>{val}</div>
                  <div className="text-[10px] font-mono uppercase tracking-wider text-slate-500 mt-1">{label}</div>
                </Card>
              ))}
            </div>

            {/* Category results */}
            <div className="space-y-3" data-testid="pr-categories">
              {run.categories.map((cat) => {
                const open = !!openCats[cat.name];
                const fails = cat.checks.filter((c) => c.status === "fail").length;
                const warns = cat.checks.filter((c) => c.status === "warn").length;
                return (
                  <Card key={cat.name} className="bg-slate-950/60 border-white/10 overflow-hidden">
                    <button onClick={() => setOpenCats({ ...openCats, [cat.name]: !open })}
                            data-testid={`pr-cat-${cat.name.split(" ")[0].toLowerCase().replace(/[^a-z]/g, "")}`}
                            className="w-full flex items-center gap-3 p-4 text-left hover:bg-white/[0.02]">
                      {open ? <ChevronDown size={15} className="text-slate-500" /> : <ChevronRight size={15} className="text-slate-500" />}
                      <span className="font-black text-sm text-white flex-1">{cat.name}</span>
                      {warns > 0 && <span className="text-[10px] font-mono text-orange-400">{warns} warn</span>}
                      {fails > 0 && <span className="text-[10px] font-mono text-red-400">{fails} fail</span>}
                      <span className={`text-sm font-black tabular-nums ${cat.pass_rate === 100 ? "text-emerald-400" : cat.pass_rate >= 80 ? "text-orange-300" : "text-red-400"}`}>
                        {cat.pass_rate}%
                      </span>
                    </button>
                    {open && (
                      <div className="border-t border-white/5">
                        {cat.checks.map((c, i) => (
                          <div key={i} className="flex items-center gap-3 px-5 py-2 border-b border-white/5 last:border-0 text-sm">
                            {STATUS_ICON[c.status]}
                            <span className="flex-1 text-slate-200">{c.name}</span>
                            <span className="text-[10px] font-mono uppercase text-slate-600">{c.kind}</span>
                            <span className="text-[11px] font-mono text-slate-400 w-16 text-right">{c.ms > 0 ? `${c.ms}ms` : "—"}</span>
                            <span className="text-[11px] text-slate-500 w-64 truncate text-right hidden lg:block">{c.evidence}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </Card>
                );
              })}
            </div>
          </>
        )}

        {/* Reliability over time */}
        {chart.length > 1 && (
          <Card className="p-4 bg-slate-950/60 border-white/10" data-testid="pr-history-chart">
            <div className="text-xs font-mono uppercase tracking-widest text-cyan-300 flex items-center gap-2 mb-3"><History size={13} /> Reliability trend · pass rate % and P95 latency per run</div>
            <div className="h-48">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chart}>
                  <XAxis dataKey="name" stroke="#475569" fontSize={10} />
                  <YAxis yAxisId="l" domain={[0, 100]} stroke="#34D399" fontSize={10} />
                  <YAxis yAxisId="r" orientation="right" stroke="#FB923C" fontSize={10} />
                  <Tooltip contentStyle={{ background: "#0D1117", border: "1px solid rgba(255,255,255,0.1)", fontSize: 12 }} />
                  <Line yAxisId="l" type="monotone" dataKey="pass" name="Pass rate %" stroke="#34D399" strokeWidth={2} dot={{ r: 3 }} />
                  <Line yAxisId="r" type="monotone" dataKey="p95" name="P95 ms" stroke="#FB923C" strokeWidth={2} dot={{ r: 3 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </Card>
        )}

        {run?.metrics?.slowest_check && (
          <div className="flex items-center gap-2 text-xs text-slate-500 font-mono">
            <Timer size={12} /> Slowest check: {run.metrics.slowest_check.name} ({run.metrics.slowest_check.ms}ms)
            <Gauge size={12} className="ml-3" /> The deep functional flow provisions a real throwaway tenant, books a load, invoices it, generates PDFs, creates a Stripe session, then tears everything down.
          </div>
        )}
      </div>
    </>
  );
}
