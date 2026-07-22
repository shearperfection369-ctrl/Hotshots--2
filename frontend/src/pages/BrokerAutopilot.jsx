import React, { useCallback, useEffect, useState } from "react";
import { Card } from "../components/ui/card";
import { Bot, Zap, Play, FileDown, X, CircleDot, Loader2, Radar } from "lucide-react";
import { toast } from "sonner";
import { api } from "../lib/api";

const errTxt = (e) => (typeof e?.response?.data?.detail === "string" ? e.response.data.detail : "Something went wrong");
const STAGE_META = {
  sourced: ["SOURCED", "#94A3B8"], carrier_matched: ["MATCHED", "#A78BFA"], ratecon_sent: ["RATE CON SENT", "#22D3EE"],
  bol_received: ["BOL IN", "#F59E0B"], in_transit: ["IN TRANSIT", "#FB923C"], delivered: ["POD IN", "#34D399"], completed: ["CLOSED", "#10B981"],
};
const COLUMNS = ["carrier_matched", "ratecon_sent", "bol_received", "in_transit", "delivered", "completed"];

export default function BrokerAutopilot() {
  const [data, setData] = useState(null);
  const [detail, setDetail] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try { const { data: d } = await api.get("/broker-autopilot/status"); setData(d); } catch (_) {}
  }, []);
  useEffect(() => { load(); const t = setInterval(load, 15000); return () => clearInterval(t); }, [load]);

  const toggle = async () => {
    try {
      const { data: r } = await api.post("/broker-autopilot/config", { enabled: !data.config.enabled });
      toast.success(r.config.enabled ? "Autopilot engaged — AI is running the desk" : "Autopilot paused");
      load();
    } catch (e2) { toast.error(errTxt(e2)); }
  };

  const setLimit = async (n) => {
    try { await api.post("/broker-autopilot/config", { daily_limit: n }); load(); } catch (e2) { toast.error(errTxt(e2)); }
  };

  const runCycle = async () => {
    setBusy(true);
    try {
      const { data: r } = await api.post("/broker-autopilot/run-cycle", {}, { timeout: 90000 });
      toast.success(r.actions.length ? `${r.actions.length} actions: ${r.actions.slice(0, 2).join("; ")}…` : "Nothing to do this cycle");
      load();
    } catch (e2) { toast.error(errTxt(e2)); }
    finally { setBusy(false); }
  };

  if (!data) return <div className="p-8 text-slate-500 font-mono text-sm">Loading AI broker desk…</div>;
  const { config, stats, loads } = data;

  return (
    <div className="p-6 space-y-5 relative" data-testid="broker-autopilot">
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div style={{ position: "absolute", top: -140, right: "10%", width: 480, height: 480, borderRadius: 9999, filter: "blur(56px)", background: "radial-gradient(circle, rgba(34,211,238,0.14), transparent 65%)" }} />
      </div>
      <div className="relative flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-white flex items-center gap-2"><Bot className="text-cyan-300" size={24} /> AI Broker Autopilot</h1>
          <p className="text-xs text-slate-500 font-mono mt-1">sources loads → matches carriers → emails rate cons → collects BOL → runs to destination → verifies POD. Hands-free.</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] font-mono text-slate-500 uppercase">Loads/day</span>
            {[5, 10, 15].map((n) => (
              <button key={n} onClick={() => setLimit(n)} data-testid={`bap-limit-${n}`}
                      className={`h-8 w-9 rounded-full border text-xs font-black ${config.daily_limit === n ? "border-cyan-400 text-cyan-300 bg-cyan-500/10" : "border-white/15 text-slate-400"}`}>{n}</button>
            ))}
          </div>
          <button onClick={runCycle} disabled={busy} data-testid="bap-run-cycle"
                  className="px-4 h-11 rounded-full border border-amber-500/50 text-amber-300 font-bold text-xs inline-flex items-center gap-1.5 hover:bg-amber-500/10 disabled:opacity-50">
            {busy ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />} Run Cycle Now
          </button>
          <button onClick={toggle} data-testid="bap-toggle"
                  className={`px-6 h-11 rounded-full font-black text-sm inline-flex items-center gap-2 transition ${config.enabled ? "bg-emerald-500 text-black shadow-[0_0_24px_-4px_rgba(16,185,129,0.7)]" : "bg-slate-800 text-slate-300 border border-white/15"}`}>
            <Zap size={16} /> {config.enabled ? "AUTONOMOUS · ON" : "ENGAGE AUTOPILOT"}
          </button>
        </div>
      </div>

      <div className="relative grid grid-cols-2 md:grid-cols-6 gap-3">
        {[["Sourced today", `${stats.sourced_today}/${stats.daily_limit}`, "#22D3EE"], ["Active loads", stats.active, "#F59E0B"],
          ["Loads closed", stats.completed_total, "#34D399"], ["Revenue booked", `$${stats.revenue_total.toLocaleString()}`, "#A78BFA"],
          ["Margin banked", `$${stats.margin_total.toLocaleString()}`, "#10B981"], ["Margin today", `$${stats.margin_today.toLocaleString()}`, "#FB923C"]].map(([l, v, c]) => (
          <div key={l} className="p-3 rounded-2xl border border-white/10 bg-slate-950/70 backdrop-blur">
            <div className="text-xl font-black tabular-nums" style={{ color: c }}>{v}</div>
            <div className="text-[9px] font-mono uppercase tracking-wider text-slate-500 mt-0.5">{l}</div>
          </div>
        ))}
      </div>

      <div className="relative grid md:grid-cols-6 gap-2" data-testid="bap-pipeline">
        {COLUMNS.map((st) => {
          const [label, color] = STAGE_META[st];
          const col = loads.filter((l) => l.stage === st);
          return (
            <div key={st} className="rounded-2xl border border-white/10 bg-slate-950/60 backdrop-blur p-2 min-h-[200px]" data-testid={`bap-col-${st}`}>
              <div className="flex items-center gap-1.5 px-1 mb-2">
                <CircleDot size={11} style={{ color }} />
                <span className="text-[10px] font-mono font-bold" style={{ color }}>{label}</span>
                <span className="ml-auto text-[10px] font-mono text-slate-600">{col.length}</span>
              </div>
              <div className="space-y-1.5 max-h-[420px] overflow-y-auto">
                {col.map((l) => (
                  <button key={l.load_id} onClick={() => setDetail(l)} data-testid={`bap-load-${l.load_id}`}
                          className="w-full text-left p-2 rounded-xl border border-white/10 bg-white/[0.03] hover:border-cyan-400/50 transition">
                    <div className="text-[10px] font-mono text-cyan-300">{l.load_id}</div>
                    <div className="text-[11px] font-bold text-white leading-tight">{l.origin.split(",")[0]} → {l.dest.split(",")[0]}</div>
                    <div className="text-[9px] font-mono text-slate-500">{l.equipment} · {l.miles}mi · <span className="text-emerald-400">${l.margin.toLocaleString()} mgn</span></div>
                    <div className="text-[9px] font-mono text-slate-600 truncate">{l.carrier?.name}</div>
                  </button>
                ))}
              </div>
            </div>
          );
        })}
      </div>

      {!config.enabled && stats.active === 0 && (
        <div className="relative p-6 rounded-2xl border border-dashed border-cyan-500/30 text-center">
          <Radar className="mx-auto text-cyan-300 mb-2" size={26} />
          <p className="text-sm text-slate-400">Engage autopilot and the AI desk sources up to <b className="text-cyan-300">{config.daily_limit} loads a day</b>, working each one from board to POD — exactly like the sandbox, but live on your carrier pool.</p>
        </div>
      )}

      {detail && <LoadDrawer loadId={detail.load_id} onClose={() => setDetail(null)} />}
    </div>
  );
}

function LoadDrawer({ loadId, onClose }) {
  const [ld, setLd] = useState(null);
  useEffect(() => { api.get(`/broker-autopilot/loads/${loadId}`).then((r) => setLd(r.data)).catch(() => {}); }, [loadId]);
  const doc = async (d) => {
    try {
      const r = await api.get(`/broker-autopilot/loads/${loadId}/docs/${d}.pdf`, { responseType: "blob" });
      const url = URL.createObjectURL(r.data);
      const a = document.createElement("a"); a.href = url; a.download = `${d}_${loadId}.pdf`; a.click(); URL.revokeObjectURL(url);
    } catch (e2) { toast.error(errTxt(e2)); }
  };
  if (!ld) return null;
  const [label, color] = STAGE_META[ld.stage];
  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex justify-end" onClick={onClose}>
      <div className="w-full max-w-md h-full bg-slate-950 border-l border-cyan-500/30 p-5 overflow-y-auto" onClick={(e) => e.stopPropagation()} data-testid="bap-drawer">
        <div className="flex justify-between items-start mb-1">
          <div className="font-black text-white text-lg">{ld.load_id}</div>
          <button onClick={onClose} className="text-slate-500 hover:text-white"><X size={18} /></button>
        </div>
        <div className="text-sm text-slate-300">{ld.origin} → {ld.dest}</div>
        <div className="text-[11px] font-mono text-slate-500 mb-3">{ld.equipment} · {ld.commodity} · {ld.weight_lbs?.toLocaleString()} lbs · PU {ld.pickup_date}</div>
        <span className="px-2.5 py-1 rounded-full border text-[10px] font-mono font-bold" style={{ borderColor: color, color }}>{label}</span>
        <div className="grid grid-cols-3 gap-2 my-4">
          {[["Shipper pays", `$${ld.shipper_rate.toLocaleString()}`], ["Carrier gets", `$${ld.carrier_rate.toLocaleString()}`], ["AI margin", `$${ld.margin.toLocaleString()}`]].map(([l, v]) => (
            <div key={l} className="p-2.5 rounded-xl border border-white/10 text-center">
              <div className="font-black text-amber-300 text-sm tabular-nums">{v}</div>
              <div className="text-[8px] font-mono uppercase text-slate-500">{l}</div>
            </div>
          ))}
        </div>
        <div className="p-3 rounded-xl border border-white/10 bg-white/[0.03] mb-4">
          <div className="text-[10px] font-mono uppercase text-slate-500 mb-1">Carrier</div>
          <div className="font-bold text-white text-sm">{ld.carrier?.name}</div>
          <div className="text-[11px] text-slate-400">MC {ld.carrier?.mc_number} · match score {ld.carrier?.match_score}</div>
        </div>
        {ld.ai_reasoning && <div className="p-3 rounded-xl border border-cyan-500/25 bg-cyan-500/5 text-[12px] text-cyan-100 mb-4" data-testid="bap-ai-reasoning"><Bot size={12} className="inline mr-1.5 text-cyan-300" />{ld.ai_reasoning}</div>}
        <div className="flex gap-2 mb-5">
          {[["ratecon", "Rate Con"], ["bol", "BOL"], ["pod", "POD"]].map(([d, l]) => (
            <button key={d} onClick={() => doc(d)} data-testid={`bap-doc-${d}`}
                    className="px-3.5 py-2 rounded-full border border-amber-500/50 text-amber-300 text-[11px] font-bold inline-flex items-center gap-1.5 hover:bg-amber-500/10"><FileDown size={12} /> {l}</button>
          ))}
        </div>
        <div className="text-[10px] font-mono uppercase text-slate-500 mb-2">AI activity timeline</div>
        <div className="space-y-2" data-testid="bap-timeline">
          {(ld.timeline || []).slice().reverse().map((t, i) => (
            <div key={i} className="flex gap-2.5">
              <div className="shrink-0 mt-1 h-2 w-2 rounded-full" style={{ background: (STAGE_META[t.stage] || ["", "#64748B"])[1] }} />
              <div>
                <div className="text-[12px] text-slate-200">{t.note}</div>
                <div className="text-[9px] font-mono text-slate-600">{t.at.slice(0, 16).replace("T", " ")} UTC · {t.stage}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
