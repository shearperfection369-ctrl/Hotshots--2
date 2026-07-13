import React, { useCallback, useEffect, useRef, useState } from "react";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Switch } from "../components/ui/switch";
import {
  Crosshair, Zap, ShieldAlert, ShieldCheck, Truck, Loader2, CheckCircle2,
  XCircle, RefreshCw, Scale, TrendingUp, Layers, ScrollText, Sparkles,
} from "lucide-react";
import { api } from "../lib/api";
import { toast } from "sonner";

const fmt = (n) => (n == null ? "—" : Number(n).toLocaleString(undefined, { maximumFractionDigits: 0 }));

const MODES = [
  { id: "balanced", label: "Balanced", icon: Scale },
  { id: "high_margin", label: "High-Margin", icon: TrendingUp },
  { id: "high_volume", label: "High-Volume", icon: Layers },
];

const COMPONENT_LABELS = {
  margin_pct: "Margin",
  shipper_reliability: "Shipper",
  lane_profitability: "Lane",
  fuel_economics: "Fuel",
  detention_risk: "Detention",
  driver_match: "Driver",
};

function StatPill({ label, value, accent = "text-cyan-300" }) {
  return (
    <div className="rounded border border-white/10 bg-white/[0.03] px-3 py-2 text-center min-w-[110px]">
      <div className={`font-mono font-bold text-lg ${accent}`}>{value}</div>
      <div className="text-[9px] font-mono uppercase tracking-[0.15em] text-slate-500">{label}</div>
    </div>
  );
}

function ScoreBars({ components }) {
  return (
    <div className="grid grid-cols-3 gap-x-3 gap-y-1 mt-2">
      {Object.entries(COMPONENT_LABELS).map(([k, label]) => {
        const v = components?.[k] ?? 0;
        return (
          <div key={k} className="flex items-center gap-1.5">
            <span className="text-[9px] font-mono text-slate-500 w-14 uppercase">{label}</span>
            <div className="flex-1 h-1.5 rounded bg-white/5 overflow-hidden">
              <div className={`h-full ${v >= 75 ? "bg-emerald-400" : v >= 50 ? "bg-cyan-400" : "bg-yellow-500"}`}
                   style={{ width: `${Math.min(100, v)}%` }} />
            </div>
            <span className="text-[9px] font-mono text-slate-400 w-6 text-right">{Math.round(v)}</span>
          </div>
        );
      })}
    </div>
  );
}

function WinnerCard({ w, onBook, onDismiss, busy }) {
  const l = w.load || {};
  const auto = w.status === "auto_booked";
  return (
    <Card className={`hud-surface p-4 ${auto ? "border-emerald-500/40" : w.risk_override ? "border-yellow-500/40" : ""}`}
          data-testid={`hunter-winner-${w.winner_id}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-mono font-black text-lg text-white">{l.origin} → {l.destination}</span>
            {w.is_new && <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-cyan-500/20 text-cyan-300 uppercase tracking-wider" data-testid="hunter-new-badge">New</span>}
            {auto && <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 uppercase tracking-wider">Auto-Booked</span>}
            {w.risk_override && <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-yellow-500/20 text-yellow-300 uppercase tracking-wider">Risk Override</span>}
          </div>
          <div className="text-[10px] font-mono text-slate-500 mt-0.5">
            {l.shipper} · {l.equipment} · {fmt(l.miles)} mi · {String(w.board_id || "").toUpperCase()} · ${l.rate_per_mile?.toFixed?.(2) || "—"}/mi
          </div>
          <ScoreBars components={w.components} />
          <div className="flex items-center gap-2 mt-2 text-[10px] font-mono">
            <Truck size={11} className={w.best_carrier?.qualified ? "text-emerald-400" : "text-slate-600"} />
            <span className={w.best_carrier?.qualified ? "text-slate-300" : "text-slate-600"}>
              {w.best_carrier?.qualified
                ? `${w.best_carrier.carrier_name} · match ${w.best_carrier.score}`
                : "No qualified carrier on roster"}
            </span>
          </div>
        </div>
        <div className="text-right shrink-0">
          <div className={`font-mono font-black text-2xl ${w.score >= 85 ? "text-emerald-400" : "text-cyan-300"}`}>{w.score}</div>
          <div className="text-[9px] font-mono text-slate-500 uppercase">AI Score</div>
          <div className="font-mono text-emerald-300 text-sm mt-1">${fmt(l.margin_usd)}</div>
          <div className="text-[9px] font-mono text-slate-500">{l.margin_pct?.toFixed?.(1)}% margin</div>
        </div>
      </div>
      {!auto && w.status === "surfaced" && (
        <div className="flex gap-2 mt-3">
          <Button size="sm" disabled={busy} onClick={() => onBook(w)}
            data-testid={`hunter-book-${w.winner_id}`}
            className="bg-emerald-500 hover:bg-emerald-400 text-black font-bold font-mono text-[10px] uppercase tracking-wider flex-1">
            <CheckCircle2 size={12} className="mr-1" /> Book · {w.best_carrier?.carrier_name || "assign later"}
          </Button>
          <Button size="sm" variant="ghost" disabled={busy} onClick={() => onDismiss(w)}
            data-testid={`hunter-dismiss-${w.winner_id}`}
            className="border border-white/10 text-slate-400 font-mono text-[10px] uppercase">
            <XCircle size={12} className="mr-1" /> Dismiss
          </Button>
        </div>
      )}
    </Card>
  );
}

export default function LoadHunterTab() {
  const [cfg, setCfg] = useState(null);
  const [winners, setWinners] = useState([]);
  const [stats, setStats] = useState(null);
  const [lastScan, setLastScan] = useState(null);
  const [scanning, setScanning] = useState(false);
  const [autoScan, setAutoScan] = useState(false);
  const [busy, setBusy] = useState(false);
  const [risk, setRisk] = useState([]);
  const [audit, setAudit] = useState([]);
  const [showAudit, setShowAudit] = useState(false);
  const timerRef = useRef(null);

  const loadAll = useCallback(async () => {
    try {
      const [c, w, s, r] = await Promise.all([
        api.get("/load-hunter/config"), api.get("/load-hunter/winners"),
        api.get("/load-hunter/stats"), api.get("/load-hunter/risk"),
      ]);
      setCfg(c.data); setWinners(w.data.items || []); setStats(s.data); setRisk(r.data.items || []);
    } catch (e) { console.error(e); }
  }, []);
  useEffect(() => { loadAll(); }, [loadAll]);

  const runScan = useCallback(async (silent = false) => {
    setScanning(true);
    try {
      const { data } = await api.post("/load-hunter/scan");
      setLastScan(data);
      setWinners(data.winners_list || []);
      api.get("/load-hunter/stats").then(({ data: s }) => setStats(s)).catch(() => {});
      if (!silent) toast.success(`Scan complete — ${data.winners} winners from ${data.scanned} loads in ${data.elapsed_ms}ms`);
      if (data.auto_booked > 0) toast.success(`🤖 Auto-booked ${data.auto_booked} load(s)`, { duration: 6000 });
    } catch (e) {
      if (!silent) toast.error(e?.response?.data?.detail || "Scan failed");
    } finally { setScanning(false); }
  }, []);

  // Real-time sync loop — rescans every scan_interval_sec (default 45s)
  useEffect(() => {
    if (timerRef.current) clearInterval(timerRef.current);
    if (autoScan) {
      const iv = (cfg?.scan_interval_sec || 45) * 1000;
      timerRef.current = setInterval(() => runScan(true), iv);
    }
    return () => timerRef.current && clearInterval(timerRef.current);
  }, [autoScan, cfg?.scan_interval_sec, runScan]);

  const saveCfg = async (patch) => {
    try {
      const { data } = await api.post("/load-hunter/config", patch);
      setCfg((c) => ({ ...c, ...data }));
      toast.success("Hunter config updated");
    } catch (e) { toast.error(e?.response?.data?.detail || "Config update failed"); }
  };

  const book = async (w) => {
    setBusy(true);
    try {
      const { data } = await api.post(`/load-hunter/winners/${w.winner_id}/book`);
      toast.success(`Booked ${data.booked_id} → tracking as ${data.shipment_id}`);
      setWinners((ws) => ws.map((x) => x.winner_id === w.winner_id ? { ...x, status: "booked" } : x));
    } catch (e) { toast.error(e?.response?.data?.detail || "Book failed"); }
    finally { setBusy(false); }
  };
  const dismiss = async (w) => {
    try {
      await api.post(`/load-hunter/winners/${w.winner_id}/dismiss`);
      setWinners((ws) => ws.filter((x) => x.winner_id !== w.winner_id));
    } catch { toast.error("Dismiss failed"); }
  };

  const loadAudit = async () => {
    if (!showAudit) {
      const { data } = await api.get("/load-hunter/audit?limit=40").catch(() => ({ data: { items: [] } }));
      setAudit(data.items || []);
    }
    setShowAudit((s) => !s);
  };

  const ab = cfg?.auto_book || {};
  const active = winners.filter((w) => ["surfaced", "auto_booked"].includes(w.status));

  return (
    <div className="space-y-4" data-testid="load-hunter-tab">
      {/* Header + stats */}
      <Card className="hud-surface p-5">
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
          <div>
            <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 flex items-center gap-1.5">
              <Sparkles size={11} /> Autonomous Load Selection
            </div>
            <h3 className="font-display text-xl font-black flex items-center gap-2">
              <Crosshair size={18} className="text-cyan-400" /> AI Load Hunter
            </h3>
            <div className="text-[10px] font-mono text-slate-500 mt-1">
              Scans every board in one pass · scores on your weighted profile · auto-rejects risk · pre-matches carriers
            </div>
          </div>
          <div className="flex items-center gap-2 flex-wrap" data-testid="hunter-stats">
            <StatPill label="Last scan" value={lastScan ? `${lastScan.elapsed_ms}ms` : stats?.last_scan ? `${stats.last_scan.elapsed_ms}ms` : "—"} accent="text-emerald-300" />
            <StatPill label="Scanned" value={fmt(lastScan?.scanned ?? stats?.last_scan?.scanned)} />
            <StatPill label="Winners" value={fmt(active.length)} />
            <StatPill label="Auto-booked" value={fmt(stats?.auto_booked_total)} accent="text-emerald-300" />
            <StatPill label="Pipeline $" value={`$${fmt(stats?.pipeline_margin_usd)}`} accent="text-yellow-300" />
          </div>
        </div>

        {/* Controls */}
        <div className="flex flex-wrap items-center gap-3 mt-4 pt-4 border-t border-white/5">
          <div className="flex items-center gap-1" data-testid="hunter-mode-pills">
            {MODES.map((m) => (
              <button key={m.id} onClick={() => saveCfg({ mode: m.id })}
                data-testid={`hunter-mode-${m.id}`}
                className={`px-3 py-1.5 rounded font-mono text-[10px] uppercase tracking-wider border flex items-center gap-1.5 ${
                  cfg?.mode === m.id ? "bg-cyan-500/15 border-cyan-400/50 text-cyan-200"
                                     : "border-white/10 text-slate-400 hover:border-cyan-500/30"}`}>
                <m.icon size={11} /> {m.label}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-2 ml-auto">
            <label className="flex items-center gap-2 text-[10px] font-mono uppercase text-slate-400">
              <Switch checked={autoScan} onCheckedChange={setAutoScan} data-testid="hunter-autoscan-toggle" />
              Auto-scan {cfg?.scan_interval_sec || 45}s
            </label>
            <label className="flex items-center gap-2 text-[10px] font-mono uppercase text-slate-400">
              <Switch checked={!!ab.enabled}
                onCheckedChange={(v) => saveCfg({ auto_book_enabled: v })}
                data-testid="hunter-autobook-toggle" />
              Auto-book
            </label>
            <div className="flex items-center gap-1 text-[10px] font-mono text-slate-500">
              cap $
              <Input type="number" defaultValue={ab.max_rate_usd} key={ab.max_rate_usd}
                onBlur={(e) => saveCfg({ auto_book_max_rate_usd: Number(e.target.value) || 0 })}
                data-testid="hunter-autobook-cap"
                className="w-20 h-7 bg-slate-950 border-white/10 text-xs font-mono" />
            </div>
            <Button onClick={() => runScan(false)} disabled={scanning}
              data-testid="hunter-scan-btn"
              className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold font-mono text-[11px] uppercase tracking-wider">
              {scanning ? <Loader2 size={13} className="mr-1.5 animate-spin" /> : <Zap size={13} className="mr-1.5" />}
              Hunt Now
            </Button>
          </div>
        </div>
        {cfg && (
          <div className="text-[10px] font-mono text-slate-500 mt-2">
            {cfg.preset_descriptions?.[cfg.mode]} · min score {cfg.min_score} · auto-book needs score ≥{ab.min_score}, rate ≤${fmt(ab.max_rate_usd)}, max {ab.max_per_day}/day, clean risk
          </div>
        )}
      </Card>

      {/* Winners queue */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3" data-testid="hunter-winners-grid">
        {active.length === 0 && (
          <Card className="hud-surface p-8 lg:col-span-2 text-center text-slate-500 font-mono text-sm" data-testid="hunter-empty">
            <Crosshair size={24} className="mx-auto mb-2 text-slate-600" />
            No winners in queue — hit <span className="text-cyan-300">Hunt Now</span> to scan all boards.
          </Card>
        )}
        {active.map((w) => (
          <WinnerCard key={w.winner_id} w={w} onBook={book} onDismiss={dismiss} busy={busy} />
        ))}
      </div>

      {/* Risk registry + audit */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <Card className="hud-surface p-4" data-testid="hunter-risk-panel">
          <div className="flex items-center justify-between mb-3">
            <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-yellow-400 flex items-center gap-1.5">
              <ShieldAlert size={12} /> Shipper Risk Registry
            </div>
          </div>
          <div className="space-y-1.5 max-h-56 overflow-y-auto">
            {risk.map((r) => (
              <div key={r.shipper} className="flex items-center justify-between p-2 rounded border border-white/5 bg-white/[0.02]">
                <div className="min-w-0">
                  <div className="text-xs text-slate-200 flex items-center gap-2">
                    {r.shipper}
                    {r.blacklisted && <span className="text-[9px] font-mono px-1 rounded bg-red-500/20 text-red-300 uppercase">Blacklist</span>}
                    {r.credit_flag && <span className="text-[9px] font-mono px-1 rounded bg-yellow-500/20 text-yellow-300 uppercase">Credit Flag</span>}
                  </div>
                  <div className="text-[9px] font-mono text-slate-500">{r.avg_days_to_pay}d to pay · {r.dispute_count} disputes · {r.detention_incidents_90d} detention/90d</div>
                </div>
                <span className={`font-mono font-bold text-sm ${r.payment_score >= 80 ? "text-emerald-400" : r.payment_score >= 60 ? "text-yellow-300" : "text-red-400"}`}>
                  {r.payment_score}
                </span>
              </div>
            ))}
          </div>
        </Card>

        <Card className="hud-surface p-4" data-testid="hunter-audit-panel">
          <div className="flex items-center justify-between mb-3">
            <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 flex items-center gap-1.5">
              <ScrollText size={12} /> Decision Audit Trail
            </div>
            <button onClick={loadAudit} data-testid="hunter-audit-toggle"
              className="text-[10px] font-mono uppercase text-slate-400 hover:text-cyan-300 border border-white/10 rounded px-2 py-0.5 flex items-center gap-1">
              <RefreshCw size={10} /> {showAudit ? "Hide" : "Load"}
            </button>
          </div>
          {showAudit ? (
            <div className="space-y-1 max-h-48 overflow-y-auto">
              {audit.map((a) => (
                <div key={a.id} className="text-[10px] font-mono flex items-center gap-2 p-1.5 rounded bg-white/[0.02]">
                  <span className={`uppercase shrink-0 ${a.action === "auto_book" ? "text-emerald-400" : a.action === "risk_reject" ? "text-red-400" : a.action === "manual_book" ? "text-cyan-300" : "text-slate-400"}`}>
                    {a.action.replace("_", " ")}
                  </span>
                  <span className="text-slate-400 truncate">{a.lane} · {a.shipper}{a.score != null ? ` · score ${a.score}` : ""}</span>
                </div>
              ))}
              {audit.length === 0 && <div className="text-[10px] font-mono text-slate-600">No decisions yet — run a scan.</div>}
            </div>
          ) : (
            <div className="text-[10px] font-mono text-slate-500 leading-relaxed flex items-start gap-2">
              <ShieldCheck size={13} className="text-emerald-400 shrink-0 mt-0.5" />
              Compliance guardrail: scoring uses business metrics only — payment history, service performance,
              lane economics, equipment &amp; insurance fit. No protected characteristics are ingested or scored.
              Every surface / reject / auto-book decision is logged here.
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
