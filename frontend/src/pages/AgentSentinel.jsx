import React, { useCallback, useEffect, useState } from "react";
import Topbar from "../components/Topbar";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Input } from "../components/ui/input";
import {
  ShieldAlert, RefreshCw, Server, Bot, Activity, Plus, Trash2,
  CheckCircle2, Loader2, Siren, Clock,
} from "lucide-react";
import { toast } from "sonner";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";

const STATUS_PILL = {
  up: "bg-emerald-500/15 text-emerald-300 border-emerald-500/40",
  ok: "bg-emerald-500/15 text-emerald-300 border-emerald-500/40",
  degraded: "bg-amber-500/15 text-amber-300 border-amber-500/40",
  slow: "bg-amber-500/15 text-amber-300 border-amber-500/40",
  error: "bg-amber-500/15 text-amber-300 border-amber-500/40",
  down: "bg-red-500/15 text-red-300 border-red-500/40",
  budget_exhausted: "bg-red-500/15 text-red-300 border-red-500/40",
  critical: "bg-red-500/15 text-red-300 border-red-500/40",
  unknown: "bg-slate-500/15 text-slate-300 border-slate-500/40",
};

const SEV_PILL = {
  critical: "bg-red-500/15 text-red-300 border-red-500/40",
  warning: "bg-amber-500/15 text-amber-300 border-amber-500/40",
};

const Pill = ({ s }) => (
  <Badge className={`${STATUS_PILL[s] || STATUS_PILL.unknown} font-mono text-[10px] uppercase`}>{String(s).replace("_", " ")}</Badge>
);

const fmtTime = (iso) => (iso ? new Date(iso).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "—");

export default function AgentSentinel() {
  const { user } = useAuth();
  const [status, setStatus] = useState(null);
  const [feed, setFeed] = useState([]);
  const [scanning, setScanning] = useState(false);
  const [newDep, setNewDep] = useState({ name: "", url: "" });
  const [deps, setDeps] = useState([]);

  const load = useCallback(async () => {
    try {
      const [s, a, d] = await Promise.all([
        api.get("/sentinel/status"),
        api.get("/sentinel/alerts?limit=100"),
        api.get("/sentinel/deployments"),
      ]);
      setStatus(s.data);
      setFeed(a.data.alerts || []);
      setDeps(d.data.deployments || []);
    } catch (_) {
      toast.error("Failed to load sentinel status");
    }
  }, []);

  useEffect(() => { load(); const t = setInterval(load, 60000); return () => clearInterval(t); }, [load]);

  const runScan = async () => {
    setScanning(true);
    try {
      await api.post("/sentinel/scan");
      await load();
      toast.success("Health sweep complete");
    } catch (_) {
      toast.error("Scan failed");
    } finally {
      setScanning(false);
    }
  };

  const ack = async (id) => {
    try { await api.post(`/sentinel/alerts/${id}/ack`); await load(); toast.success("Alert acknowledged"); }
    catch (_) { toast.error("Failed to acknowledge"); }
  };

  const addDep = async (e) => {
    e.preventDefault();
    try {
      await api.post("/sentinel/deployments", { name: newDep.name, url: newDep.url });
      setNewDep({ name: "", url: "" });
      await load();
      toast.success("Deployment added to watch list");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to add deployment");
    }
  };

  const removeDep = async (id) => {
    try { await api.delete(`/sentinel/deployments/${id}`); await load(); toast.success("Removed"); }
    catch (err) { toast.error(err.response?.data?.detail || "Cannot remove"); }
  };

  const snap = status?.snapshot;
  const llm = snap?.llm;
  const er = snap?.error_rate;
  const activeAlerts = status?.active_alerts || [];
  const upCount = (snap?.deployments || []).filter((d) => d.status === "up").length;
  const canManage = user?.role === "admin" || user?.role === "owner";

  return (
    <>
      <Topbar title="Agent Sentinel" subtitle="Automated health checks · every 30 min · deployments, agents, LLM budget, error rates" />
      <div className="p-4 md:p-6 space-y-5" data-testid="agent-sentinel-page">
        {/* Overall + controls */}
        <Card className={`p-5 border-2 ${snap?.overall === "ok" ? "border-emerald-500/30 bg-emerald-950/10" : snap?.overall === "critical" ? "border-red-500/40 bg-red-950/20" : "border-amber-500/30 bg-amber-950/10"}`}>
          <div className="flex flex-wrap items-center gap-4 justify-between">
            <div className="flex items-center gap-3">
              <div className={`w-11 h-11 rounded-lg grid place-items-center ${snap?.overall === "ok" ? "bg-emerald-500/15" : "bg-red-500/15"}`}>
                {snap?.overall === "ok" ? <CheckCircle2 className="text-emerald-400" size={22} /> : <Siren className="text-red-400 animate-pulse" size={22} />}
              </div>
              <div>
                <div className="font-display text-xl font-bold" data-testid="sentinel-overall">
                  {snap ? (snap.overall === "ok" ? "All systems nominal" : snap.overall === "critical" ? "RED ALERT — degradation detected" : "Degraded performance") : "Awaiting first sweep…"}
                </div>
                <div className="text-xs text-slate-400 font-mono flex items-center gap-2 mt-0.5">
                  <Clock size={11} /> Last sweep {fmtTime(snap?.at)} · every {status?.interval_min || 30} min
                </div>
              </div>
            </div>
            <Button onClick={runScan} disabled={scanning} data-testid="sentinel-scan-btn"
                    className="bg-cyan-500 hover:bg-cyan-400 text-black font-semibold">
              {scanning ? <Loader2 size={14} className="mr-2 animate-spin" /> : <RefreshCw size={14} className="mr-2" />}
              Run checks now
            </Button>
          </div>
        </Card>

        {/* KPI cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card className="p-4 bg-slate-950/60 border-white/10" data-testid="sentinel-deployments-card">
            <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-widest text-slate-400"><Server size={13} /> Deployments</div>
            <div className="mt-2 text-2xl font-mono font-bold text-cyan-300">{upCount}/{snap?.deployments?.length ?? 0} up</div>
            <div className="text-[11px] text-slate-500 mt-1">HTTP reachability + latency on every watched app</div>
          </Card>
          <Card className="p-4 bg-slate-950/60 border-white/10" data-testid="sentinel-llm-card">
            <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-widest text-slate-400"><Bot size={13} /> Agent · LLM key</div>
            <div className="mt-2 flex items-center gap-2">
              <Pill s={llm?.status || "unknown"} />
              <span className="text-sm font-mono text-slate-300">{llm?.latency_ms != null ? `${llm.latency_ms} ms` : ""}</span>
            </div>
            <div className="text-[11px] text-slate-500 mt-1 truncate" title={llm?.detail}>{llm?.detail || "Live ping probes agent responsiveness + budget errors"}</div>
          </Card>
          <Card className="p-4 bg-slate-950/60 border-white/10" data-testid="sentinel-errors-card">
            <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-widest text-slate-400"><Activity size={13} /> API error rate · 60 min</div>
            <div className="mt-2 flex items-center gap-2">
              <span className={`text-2xl font-mono font-bold ${er?.status === "ok" ? "text-emerald-300" : "text-red-300"}`}>{er?.rate_pct ?? 0}%</span>
              <Pill s={er?.status || "unknown"} />
            </div>
            <div className="text-[11px] text-slate-500 mt-1">{er ? `${er.errors_5xx} of ${er.total_requests} requests returned 5xx` : "Rolling in-process window"}</div>
          </Card>
        </div>

        {/* Deployments table */}
        <Card className="p-5 bg-slate-950/60 border-white/10">
          <div className="flex items-center justify-between mb-3">
            <div className="text-xs font-mono uppercase tracking-widest text-cyan-300 flex items-center gap-2"><Server size={13} /> Watched deployments</div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[10px] font-mono uppercase tracking-wider text-slate-500 border-b border-white/5">
                  <th className="py-2 pr-4">Deployment</th><th className="py-2 pr-4">Status</th>
                  <th className="py-2 pr-4">Latency</th><th className="py-2 pr-4">HTTP</th>
                  <th className="py-2 pr-4">Last check</th><th className="py-2" />
                </tr>
              </thead>
              <tbody>
                {deps.map((d) => {
                  const chk = (snap?.deployments || []).find((x) => x.deployment_id === d.deployment_id);
                  return (
                    <tr key={d.deployment_id} className="border-b border-white/5" data-testid={`sentinel-dep-${d.deployment_id}`}>
                      <td className="py-2.5 pr-4">
                        <div className="text-white font-medium">{d.name}</div>
                        <div className="text-[11px] text-slate-500 font-mono">{d.url}</div>
                      </td>
                      <td className="py-2.5 pr-4"><Pill s={chk?.status || "unknown"} /></td>
                      <td className="py-2.5 pr-4 font-mono text-slate-300">{chk?.latency_ms != null ? `${chk.latency_ms} ms` : "—"}</td>
                      <td className="py-2.5 pr-4 font-mono text-slate-400">{chk?.http_code ?? "—"}</td>
                      <td className="py-2.5 pr-4 text-slate-400 text-xs">{fmtTime(chk?.checked_at)}</td>
                      <td className="py-2.5 text-right">
                        {canManage && !d.builtin && (
                          <button onClick={() => removeDep(d.deployment_id)} data-testid={`sentinel-dep-remove-${d.deployment_id}`}
                                  className="p-1.5 rounded text-slate-500 hover:text-red-400 hover:bg-red-500/10" title="Remove">
                            <Trash2 size={14} />
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {canManage && (
            <form onSubmit={addDep} className="mt-4 flex flex-col sm:flex-row gap-2" data-testid="sentinel-add-dep-form">
              <Input required value={newDep.name} onChange={(e) => setNewDep({ ...newDep, name: e.target.value })}
                     placeholder="Deployment name (e.g. Barbershop Booking App)" data-testid="sentinel-dep-name-input"
                     className="bg-white/[0.03] border-white/10 text-white placeholder:text-slate-600" />
              <Input required value={newDep.url} onChange={(e) => setNewDep({ ...newDep, url: e.target.value })}
                     placeholder="https://your-app.emergent.host" data-testid="sentinel-dep-url-input"
                     className="bg-white/[0.03] border-white/10 text-white placeholder:text-slate-600" />
              <Button type="submit" data-testid="sentinel-dep-add-btn" variant="outline"
                      className="bg-cyan-500/10 border-cyan-500/40 text-cyan-300 hover:bg-cyan-500/20 shrink-0">
                <Plus size={14} className="mr-1" /> Watch
              </Button>
            </form>
          )}
        </Card>

        {/* Alerts feed */}
        <Card className="p-5 bg-slate-950/60 border-white/10" data-testid="sentinel-alerts-feed">
          <div className="text-xs font-mono uppercase tracking-widest text-cyan-300 flex items-center gap-2 mb-3">
            <ShieldAlert size={13} /> Alerts feed
            {activeAlerts.length > 0 && (
              <Badge className="bg-red-500/15 text-red-300 border-red-500/40 text-[10px]">{activeAlerts.length} active</Badge>
            )}
          </div>
          {feed.length === 0 ? (
            <div className="text-sm text-slate-500 py-6 text-center">No alerts yet — the sentinel has a clean sheet.</div>
          ) : (
            <div className="space-y-2 max-h-[420px] overflow-y-auto pr-1">
              {feed.map((a) => (
                <div key={a.alert_id} data-testid={`sentinel-alert-${a.alert_id}`}
                     className={`flex items-start gap-3 p-3 rounded-md border ${a.status === "resolved" ? "border-white/5 bg-white/[0.01] opacity-50" : a.severity === "critical" ? "border-red-500/30 bg-red-950/20" : "border-amber-500/25 bg-amber-950/10"}`}>
                  <Badge className={`${SEV_PILL[a.severity] || SEV_PILL.warning} font-mono text-[9px] uppercase mt-0.5 shrink-0`}>{a.severity}</Badge>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm text-white font-medium">{a.title}</div>
                    <div className="text-xs text-slate-400 mt-0.5">{a.detail}</div>
                    <div className="text-[10px] text-slate-500 font-mono mt-1">
                      {fmtTime(a.detected_at)} · {a.source}
                      {a.status === "resolved" && ` · resolved ${fmtTime(a.resolved_at)}`}
                      {a.status === "acked" && ` · acked by ${a.acked_by || ""}`}
                    </div>
                  </div>
                  {a.status === "active" && (
                    <Button size="sm" variant="outline" onClick={() => ack(a.alert_id)}
                            data-testid={`sentinel-ack-${a.alert_id}`}
                            className="bg-slate-900 border-white/10 h-7 text-xs shrink-0">Ack</Button>
                  )}
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </>
  );
}
