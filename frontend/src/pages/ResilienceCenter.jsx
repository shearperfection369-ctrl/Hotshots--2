import React, { useCallback, useEffect, useState } from "react";
import { ShieldCheck, Radar, Cpu, BookOpen, DatabaseBackup, Play, FileDown, Wrench, HeartPulse, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { api } from "../lib/api";

const errTxt = (e) => (typeof e?.response?.data?.detail === "string" ? e.response.data.detail : "Something went wrong");
const SEV = { critical: "#EF4444", high: "#F59E0B", medium: "#22D3EE", low: "#94A3B8" };
const BOARD_STATUS = {
  connected: ["CONNECTED", "#10B981"], healthy: ["HEALTHY", "#10B981"],
  no_credentials: ["NO KEYS", "#64748B"], connected_empty: ["EMPTY", "#F59E0B"],
};
const TABS = [
  ["sentinel", "Sentinel · Self-Repair", ShieldCheck],
  ["gateway", "Load Board Gateway", Radar],
  ["engine", "Decision Engine", Cpu],
  ["runbook", "Manual Ops Runbook", BookOpen],
  ["backups", "Backups", DatabaseBackup],
];

const dl = async (url, filename) => {
  const r = await api.get(url, { responseType: "blob" });
  const u = URL.createObjectURL(r.data);
  const a = document.createElement("a"); a.href = u; a.download = filename; a.click(); URL.revokeObjectURL(u);
};

export default function ResilienceCenter() {
  const [tab, setTab] = useState("sentinel");
  return (
    <div className="p-6 space-y-5 relative" data-testid="resilience-center">
      <div>
        <h1 className="text-2xl font-black text-white flex items-center gap-2"><ShieldCheck className="text-emerald-400" size={24} /> Resilience Center</h1>
        <p className="text-xs text-slate-500 font-mono mt-1">self-repairing load routing · board failover · standalone matching · manual-mode safety net · automated backups</p>
      </div>
      <div className="flex flex-wrap gap-1.5" data-testid="rc-tabs">
        {TABS.map(([key, label, Icon]) => (
          <button key={key} onClick={() => setTab(key)} data-testid={`rc-tab-${key}`}
                  className={`px-4 h-9 rounded-full text-xs font-bold inline-flex items-center gap-1.5 border transition ${tab === key ? "border-emerald-400 text-emerald-300 bg-emerald-500/10" : "border-white/10 text-slate-500 hover:text-slate-300"}`}>
            <Icon size={13} /> {label}
          </button>
        ))}
      </div>
      {tab === "sentinel" && <SentinelTab />}
      {tab === "gateway" && <GatewayTab />}
      {tab === "engine" && <EngineTab />}
      {tab === "runbook" && <RunbookTab />}
      {tab === "backups" && <BackupsTab />}
    </div>
  );
}

function SentinelTab() {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    try { const { data: d } = await api.get("/self-repair/status"); setData(d); } catch (_) {}
  }, []);
  useEffect(() => { load(); const t = setInterval(load, 20000); return () => clearInterval(t); }, [load]);
  const sweep = async () => {
    setBusy(true);
    try {
      const { data: r } = await api.post("/self-repair/sweep");
      toast.success(r.patched ? `Sweep done — ${r.patched} patch(es) applied` : "Sweep done — all systems nominal");
      load();
    } catch (e) { toast.error(errTxt(e)); } finally { setBusy(false); }
  };
  if (!data) return <div className="p-6 text-slate-500 font-mono text-sm">Loading sentinel…</div>;
  const st = data.state || {};
  const hb = (st.checks || []).find((c) => c.check === "loop_heartbeat");
  return (
    <div className="space-y-4" data-testid="sentinel-tab">
      <div className="flex flex-wrap items-center gap-3">
        <span className={`px-4 py-1.5 rounded-full text-xs font-black ${st.healthy ? "bg-emerald-500/15 text-emerald-300 border border-emerald-500/40" : "bg-amber-500/15 text-amber-300 border border-amber-500/40"}`} data-testid="sentinel-health-badge">
          {st.healthy === false ? "ANOMALIES OPEN" : "SELF-HEALING · NOMINAL"}
        </span>
        <span className="text-[11px] font-mono text-slate-500">last sweep {st.last_sweep_at ? st.last_sweep_at.slice(0, 16).replace("T", " ") + " UTC" : "—"} · {st.sweeps || 0} sweeps · {data.repairs_total} lifetime patches</span>
        {hb && <span className="text-[11px] font-mono inline-flex items-center gap-1" style={{ color: hb.heartbeat_age_min < 5 ? "#10B981" : "#EF4444" }}><HeartPulse size={12} /> loop heartbeat {hb.heartbeat_age_min} min ago</span>}
        <button onClick={sweep} disabled={busy} data-testid="sentinel-sweep-btn"
                className="ml-auto px-4 h-10 rounded-full border border-emerald-500/50 text-emerald-300 font-bold text-xs inline-flex items-center gap-1.5 hover:bg-emerald-500/10 disabled:opacity-50">
          {busy ? <Loader2 size={13} className="animate-spin" /> : <Play size={13} />} Run Sweep Now
        </button>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        {(st.checks || []).map((c) => (
          <div key={c.check} className="p-3 rounded-2xl border border-white/10 bg-slate-950/70" data-testid={`sentinel-check-${c.check}`}>
            <div className="text-[11px] font-bold text-white">{c.label}</div>
            <div className="text-[10px] font-mono mt-1">
              <span className={c.found ? "text-amber-300" : "text-emerald-400"}>{c.found} found</span>
              <span className="text-slate-600"> · </span>
              <span className="text-cyan-300">{c.patched} auto-patched</span>
            </div>
          </div>
        ))}
      </div>
      <div>
        <div className="text-[10px] font-mono uppercase text-slate-500 mb-2 flex items-center gap-1.5"><Wrench size={11} /> Repair log (what I detected, what I patched)</div>
        <div className="space-y-1.5 max-h-[400px] overflow-y-auto" data-testid="sentinel-repair-log">
          {(data.repair_log || []).length === 0 && <div className="text-xs text-slate-600 font-mono">No repairs yet — nothing has broken.</div>}
          {(data.repair_log || []).map((r) => (
            <div key={r.repair_id} className="p-2.5 rounded-xl border border-white/10 bg-white/[0.03] flex gap-3 items-start">
              <span className="shrink-0 mt-0.5 px-1.5 py-px rounded text-[8px] font-black tracking-wider" style={{ color: SEV[r.severity], border: `1px solid ${SEV[r.severity]}55` }}>{r.severity.toUpperCase()}</span>
              <div className="min-w-0">
                <div className="text-[12px] text-slate-200"><b className="text-white">{r.target}</b> — {r.issue}</div>
                <div className="text-[11px] text-emerald-300">↳ {r.patch}</div>
                <div className="text-[9px] font-mono text-slate-600">{r.at.slice(0, 16).replace("T", " ")} UTC · {r.check} · {r.repair_id}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function GatewayTab() {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [last, setLast] = useState(null);
  const load = useCallback(async () => {
    try { const { data: d } = await api.get("/loadboard-gateway/status"); setData(d); } catch (_) {}
  }, []);
  useEffect(() => { load(); }, [load]);
  const fetchNow = async () => {
    setBusy(true);
    try {
      const { data: r } = await api.post("/loadboard-gateway/fetch");
      setLast(r); toast.success(`${r.count} loads via ${r.source_label}`); load();
    } catch (e) { toast.error(errTxt(e)); } finally { setBusy(false); }
  };
  if (!data) return <div className="p-6 text-slate-500 font-mono text-sm">Loading gateway…</div>;
  return (
    <div className="space-y-4" data-testid="gateway-tab">
      <p className="text-xs text-slate-400 max-w-2xl">The autopilot sources loads through this failover chain — the first healthy board wins. Real DAT / Truckstop / Convoy connectors activate automatically the moment API keys are saved in Connections.</p>
      <div className="flex flex-wrap items-center gap-2" data-testid="gateway-chain">
        {data.chain.map((b, i) => {
          const [label, color] = BOARD_STATUS[b.status] || ["ERROR", "#EF4444"];
          return (
            <React.Fragment key={b.board}>
              {i > 0 && <span className="text-slate-600 font-mono text-xs">→</span>}
              <div className="p-3 rounded-2xl border border-white/10 bg-slate-950/70 min-w-[150px]" data-testid={`gateway-board-${b.board}`}>
                <div className="text-[12px] font-bold text-white">{b.label}</div>
                <div className="text-[9px] font-mono font-bold mt-1" style={{ color }}>{label}</div>
                <div className="text-[8px] font-mono text-slate-600">{b.checked_at ? "checked " + b.checked_at.slice(11, 16) + " UTC" : "not yet probed"}</div>
              </div>
            </React.Fragment>
          );
        })}
      </div>
      <div className="flex items-center gap-3">
        <button onClick={fetchNow} disabled={busy} data-testid="gateway-fetch-btn"
                className="px-4 h-10 rounded-full border border-cyan-500/50 text-cyan-300 font-bold text-xs inline-flex items-center gap-1.5 hover:bg-cyan-500/10 disabled:opacity-50">
          {busy ? <Loader2 size={13} className="animate-spin" /> : <Radar size={13} />} Test Fetch Through Chain
        </button>
        {data.state.last_fetch_at && <span className="text-[11px] font-mono text-slate-500">last fetch via <b className="text-cyan-300">{data.state.last_source}</b> · {data.state.total_fetches || 0} total fetches</span>}
      </div>
      {last && (
        <div className="p-3 rounded-2xl border border-white/10 bg-slate-950/70" data-testid="gateway-fetch-result">
          <div className="text-[10px] font-mono uppercase text-slate-500 mb-2">Fetched {last.count} loads via {last.source_label}</div>
          {last.sample.map((l) => (
            <div key={l.board_id} className="text-[11px] font-mono text-slate-300">{l.board_id} · {l.origin} → {l.dest} · {l.equipment} · ${l.shipper_rate.toLocaleString()} (${l.rpm}/mi)</div>
          ))}
        </div>
      )}
    </div>
  );
}

function EngineTab() {
  const [form, setForm] = useState({ origin: "Minneapolis, MN", dest: "Chicago, IL", equipment: "Dry Van", weight_lbs: 30000, miles: 408, shipper_rate: 1100 });
  const [res, setRes] = useState(null);
  const [busy, setBusy] = useState(false);
  const inputCls = "h-9 px-2.5 rounded-lg bg-slate-900 border border-white/15 text-xs text-white focus:border-cyan-400 outline-none";
  const run = async () => {
    setBusy(true);
    try {
      const { data: r } = await api.post("/decision-engine/match", { ...form, weight_lbs: +form.weight_lbs, miles: +form.miles || null, shipper_rate: +form.shipper_rate || null });
      setRes(r);
    } catch (e) { toast.error(errTxt(e)); } finally { setBusy(false); }
  };
  return (
    <div className="space-y-4" data-testid="engine-tab">
      <p className="text-xs text-slate-400 max-w-2xl">Standalone matching microservice — deterministic scoring over your carrier + driver registry, zero AI dependency. Callable by the autopilot, an external system, or curl. It answers whether the AI layer is online or not.</p>
      <div className="flex flex-wrap gap-2 items-end">
        {[["origin", "Origin"], ["dest", "Destination"]].map(([k, l]) => (
          <label key={k} className="text-[9px] font-mono uppercase text-slate-500">{l}
            <input value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })} data-testid={`engine-${k}`} className={`${inputCls} block w-44 mt-1`} />
          </label>
        ))}
        <label className="text-[9px] font-mono uppercase text-slate-500">Equipment
          <select value={form.equipment} onChange={(e) => setForm({ ...form, equipment: e.target.value })} data-testid="engine-equipment" className={`${inputCls} block w-32 mt-1`}>
            {["Dry Van", "Reefer", "Flatbed"].map((x) => <option key={x}>{x}</option>)}
          </select>
        </label>
        {[["weight_lbs", "Weight lbs"], ["miles", "Miles"], ["shipper_rate", "Shipper rate $"]].map(([k, l]) => (
          <label key={k} className="text-[9px] font-mono uppercase text-slate-500">{l}
            <input type="number" value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })} data-testid={`engine-${k}`} className={`${inputCls} block w-28 mt-1`} />
          </label>
        ))}
        <button onClick={run} disabled={busy} data-testid="engine-match-btn"
                className="px-5 h-9 rounded-full bg-cyan-500 text-black text-xs font-black hover:bg-cyan-400 disabled:opacity-50">
          {busy ? "Matching…" : "Match Carriers"}
        </button>
      </div>
      {res && (
        <div className="space-y-3" data-testid="engine-results">
          {res.recommended && (
            <div className="p-3 rounded-2xl border border-emerald-500/40 bg-emerald-500/5" data-testid="engine-recommended">
              <div className="text-[9px] font-mono uppercase text-emerald-400 mb-1">Recommended</div>
              <div className="text-sm font-black text-white">{res.recommended.name} <span className="text-[10px] font-mono text-slate-500">{res.recommended.mc_number}</span></div>
              <div className="text-[11px] font-mono text-slate-400">score {res.recommended.score} · {res.recommended.drivers_available} driver(s) ready{res.recommended.est_margin != null && <> · est. margin <b className="text-emerald-300">${res.recommended.est_margin.toLocaleString()}</b></>}</div>
            </div>
          )}
          <div className="space-y-1">
            {res.ranked.map((r) => (
              <div key={r.carrier_id} className="p-2 rounded-xl border border-white/10 bg-white/[0.03] flex items-center gap-3">
                <div className="w-10 text-right font-black tabular-nums text-cyan-300 text-sm">{r.score}</div>
                <div className="flex-1 h-1.5 rounded bg-white/5 max-w-[120px]"><div className="h-1.5 rounded bg-cyan-400" style={{ width: `${Math.min(100, r.score)}%` }} /></div>
                <div className="flex-[2] min-w-0">
                  <span className="text-[12px] font-bold text-white">{r.name}</span>
                  <span className="text-[9px] font-mono text-slate-500 ml-2">{r.mc_number} · {r.drivers_available} drv · OTP {r.on_time_pct}%</span>
                </div>
                {!r.qualified && <span className="text-[8px] font-mono text-red-400 border border-red-500/40 rounded px-1.5 py-px">NOT QUALIFIED</span>}
                {r.est_margin != null && <span className="text-[10px] font-mono text-emerald-300">${r.est_margin.toLocaleString()} mgn</span>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function RunbookTab() {
  const [md, setMd] = useState("");
  useEffect(() => { api.get("/ops-runbook").then((r) => setMd(r.data.markdown)).catch(() => {}); }, []);
  return (
    <div className="space-y-4" data-testid="runbook-tab">
      <p className="text-xs text-slate-400 max-w-2xl">Layer 5 — the real safety net. If every automation layer is down, this document keeps freight moving by phone and paper. The PDF appends a live snapshot of your emergency carrier contacts and driver roster. Print it weekly.</p>
      <div className="flex gap-2">
        <button onClick={() => dl("/ops-runbook/pdf", "Orisei_Manual_Ops_Runbook.pdf").catch((e) => toast.error(errTxt(e)))} data-testid="runbook-pdf-btn"
                className="px-4 h-10 rounded-full border border-amber-500/50 text-amber-300 font-bold text-xs inline-flex items-center gap-1.5 hover:bg-amber-500/10">
          <FileDown size={13} /> Runbook PDF (+ live contacts)
        </button>
        <button onClick={() => dl("/ops-runbook/load-sheets.pdf", "Orisei_Load_Sheets.pdf").catch((e) => toast.error(errTxt(e)))} data-testid="loadsheets-pdf-btn"
                className="px-4 h-10 rounded-full border border-amber-500/50 text-amber-300 font-bold text-xs inline-flex items-center gap-1.5 hover:bg-amber-500/10">
          <FileDown size={13} /> Printable Load Sheets
        </button>
      </div>
      <div className="p-4 rounded-2xl border border-white/10 bg-slate-950/70 max-h-[460px] overflow-y-auto">
        <pre className="whitespace-pre-wrap font-mono text-[11px] text-slate-300" data-testid="runbook-preview">{md || "Loading…"}</pre>
      </div>
    </div>
  );
}

function BackupsTab() {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    try { const { data: d } = await api.get("/ops-backups"); setData(d); } catch (_) {}
  }, []);
  useEffect(() => { load(); }, [load]);
  const run = async () => {
    setBusy(true);
    try { const { data: r } = await api.post("/ops-backups/run"); toast.success(`Backup ${r.backup.name} (${(r.backup.size_bytes / 1e6).toFixed(1)} MB)`); load(); }
    catch (e) { toast.error(errTxt(e)); } finally { setBusy(false); }
  };
  const prune = async () => {
    try { const { data: r } = await api.post("/ops-backups/prune"); toast.success(Object.keys(r.pruned).length ? `Pruned: ${JSON.stringify(r.pruned)}` : "Nothing over cap — no pruning needed"); load(); }
    catch (e) { toast.error(errTxt(e)); }
  };
  if (!data) return <div className="p-6 text-slate-500 font-mono text-sm">Loading backups…</div>;
  return (
    <div className="space-y-4" data-testid="backups-tab">
      <p className="text-xs text-slate-400 max-w-2xl">Full MongoDB snapshots (mongodump, gzip) run automatically every {data.cadence_days} days — the last {data.keep} are kept. Log collections are capped daily so the database never grows unbounded. Download a backup and store it off-platform; that's your disaster-recovery copy.</p>
      <div className="flex gap-2 items-center">
        <button onClick={run} disabled={busy} data-testid="backup-run-btn"
                className="px-4 h-10 rounded-full bg-emerald-500 text-black text-xs font-black hover:bg-emerald-400 disabled:opacity-50 inline-flex items-center gap-1.5">
          {busy ? <Loader2 size={13} className="animate-spin" /> : <DatabaseBackup size={13} />} Back Up Now
        </button>
        <button onClick={prune} data-testid="backup-prune-btn"
                className="px-4 h-10 rounded-full border border-white/15 text-slate-300 text-xs font-bold hover:border-cyan-400/50">Prune Log Collections</button>
        {data.state.last_backup_at && <span className="text-[11px] font-mono text-slate-500">last backup {data.state.last_backup_at.slice(0, 16).replace("T", " ")} UTC · last prune {data.state.last_prune_at ? data.state.last_prune_at.slice(0, 16).replace("T", " ") + " UTC" : "—"}</span>}
      </div>
      <div className="space-y-1.5" data-testid="backup-list">
        {data.backups.length === 0 && <div className="text-xs text-slate-600 font-mono">No backups yet — run one now.</div>}
        {data.backups.map((b) => (
          <div key={b.name} className="p-2.5 rounded-xl border border-white/10 bg-white/[0.03] flex items-center gap-3">
            <DatabaseBackup size={14} className="text-emerald-400 shrink-0" />
            <div className="flex-1 min-w-0">
              <div className="text-[12px] font-mono text-white truncate">{b.name}</div>
              <div className="text-[9px] font-mono text-slate-500">{(b.size_bytes / 1e6).toFixed(1)} MB · {b.at.slice(0, 16).replace("T", " ")} UTC</div>
            </div>
            <button onClick={() => dl(`/ops-backups/${b.name}/download`, b.name).catch((e) => toast.error(errTxt(e)))} data-testid={`backup-dl-${b.name}`}
                    className="px-3 h-8 rounded-full border border-emerald-500/50 text-emerald-300 text-[10px] font-bold inline-flex items-center gap-1 hover:bg-emerald-500/10"><FileDown size={11} /> Download</button>
          </div>
        ))}
      </div>
    </div>
  );
}
