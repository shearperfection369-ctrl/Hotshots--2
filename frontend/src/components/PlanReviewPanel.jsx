import React, { useCallback, useEffect, useState } from "react";
import { ClipboardCheck, Check, MessageSquareWarning, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { api } from "../lib/api";

const usd = (n) => `$${Number(n).toLocaleString()}`;
const PARTNERS = ["Oliver Cummins", "Daniel W. Karsor", "Doug Graham"];

export const PlanReviewPanel = () => {
  const [data, setData] = useState(null);
  const [partner, setPartner] = useState(PARTNERS[0]);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState("");

  const load = useCallback(async () => {
    try { const { data: d } = await api.get("/brokerage/plan-review"); setData(d); } catch (_) {}
  }, []);
  useEffect(() => { load(); }, [load]);

  const ack = async (decision) => {
    setBusy(decision);
    try {
      await api.post("/brokerage/plan-review/ack", { partner, decision, note });
      toast.success(decision === "approved" ? `${partner} approved the revised plan` : `${partner} requested changes`);
      setNote(""); load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed to record"); } finally { setBusy(""); }
  };

  if (!data) return null;
  const ackFor = (name) => (data.acks || []).find((a) => a.partner === name);

  return (
    <div className="mx-auto max-w-3xl mb-8 p-5 rounded-2xl border border-amber-500/30 bg-amber-500/[0.04]" data-testid="plan-review-panel">
      <div className="flex items-center gap-2 mb-1">
        <ClipboardCheck size={16} className="text-amber-300" />
        <h3 className="text-sm font-black text-white uppercase tracking-wider">Financial Recalc — Partner Review</h3>
      </div>
      <p className="text-[11px] text-slate-400 mb-4" data-testid="plan-review-note">{data.revision_note}</p>

      <div className="grid md:grid-cols-3 gap-2 mb-4" data-testid="plan-review-ownership">
        {data.ownership.map((o) => (
          <div key={o.name} className="p-3 rounded-xl border border-white/10 bg-slate-950/60">
            <div className="text-[12px] font-bold text-white">{o.name} <span className="text-amber-300 font-black">{o.stake}</span></div>
            <div className="text-[9px] text-slate-500 mt-0.5">{o.role}</div>
            <div className="text-[9px] font-mono text-slate-400 mt-1">{o.contribution}</div>
          </div>
        ))}
      </div>

      <div className="p-3 rounded-xl border border-emerald-500/25 bg-emerald-500/5 mb-4" data-testid="plan-review-salary">
        <div className="text-[10px] font-mono uppercase text-emerald-400 mb-0.5">Operator salary ({data.salary.reference})</div>
        <div className="text-sm text-white"><b>{usd(data.salary.amount_monthly)}/month</b> to {data.salary.recipient} — only salaried member</div>
        <div className="text-[10px] text-slate-500">{data.salary.trigger}</div>
      </div>

      <div className="overflow-x-auto mb-4">
        <table className="w-full text-[11px]" data-testid="plan-review-pnl">
          <thead>
            <tr className="text-slate-500 font-mono text-[9px] uppercase">
              <th className="text-left py-1.5">3-Year P&L (revised)</th>
              <th className="text-right">Year 1</th><th className="text-right">Year 2</th><th className="text-right">Year 3</th>
            </tr>
          </thead>
          <tbody>
            {data.pnl.map((r) => (
              <tr key={r.metric} className={`border-t border-white/5 ${r.bold ? "text-white font-bold" : "text-slate-300"}`}>
                <td className="py-1.5">{r.metric}</td>
                <td className="text-right tabular-nums">{usd(r.y1)}</td>
                <td className="text-right tabular-nums">{usd(r.y2)}</td>
                <td className={`text-right tabular-nums ${r.bold ? "text-emerald-300" : ""}`}>{usd(r.y3)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {data.scenario_b && (
        <div className="mb-4 p-3 rounded-xl border border-cyan-500/25 bg-cyan-500/[0.04]" data-testid="plan-review-scenario-b">
          <div className="text-[10px] font-mono uppercase text-cyan-300 mb-1">Scenario B — Automation Case (§15A)</div>
          <p className="text-[10px] text-slate-500 mb-2">{data.scenario_b.note}</p>
          <div className="overflow-x-auto">
            <table className="w-full text-[11px]">
              <thead>
                <tr className="text-slate-500 font-mono text-[9px] uppercase">
                  <th className="text-left py-1">Weekly</th>
                  {data.scenario_b.columns.map((c) => <th key={c} className="text-right px-1">{c}</th>)}
                </tr>
              </thead>
              <tbody>
                {data.scenario_b.rows.map((r) => (
                  <tr key={r.metric} className={`border-t border-white/5 ${r.bold ? "text-white font-bold" : "text-slate-300"}`}>
                    <td className="py-1">{r.metric}</td>
                    <td className="text-right tabular-nums px-1">{r.a}</td>
                    <td className={`text-right tabular-nums px-1 ${r.bold ? "text-cyan-300" : ""}`}>{r.b}</td>
                    <td className="text-right tabular-nums px-1 text-slate-400">{r.c}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {data.working_capital && (
        <div className="mb-4 p-3 rounded-xl border border-purple-500/25 bg-purple-500/[0.04]" data-testid="plan-review-working-capital">
          <div className="text-[10px] font-mono uppercase text-purple-300 mb-1">Working Capital Plan</div>
          <p className="text-[10px] font-mono text-slate-500 mb-2">{data.working_capital.formula}</p>
          <div className="space-y-1.5 mb-2">
            {data.working_capital.phases.map((p) => (
              <div key={p.phase} className="p-2 rounded-lg border border-white/10 bg-slate-950/60">
                <div className="text-[11px] font-bold text-white">{p.phase} <span className="text-slate-500 font-normal">· {p.volume} · {p.revenue}</span></div>
                <div className="text-[10px] font-mono text-slate-400">AR {p.ar} → cash float <b className="text-purple-300">{p.cash_needed}</b></div>
                <div className="text-[10px] text-slate-500">{p.funding}</div>
              </div>
            ))}
          </div>
          <div className="flex flex-wrap gap-1 mb-2">
            {data.working_capital.guardrails.map((g) => (
              <span key={g} className="px-2 py-0.5 rounded-full border border-white/10 text-[9px] font-mono text-slate-400">{g}</span>
            ))}
          </div>
          <p className="text-[11px] text-purple-200" data-testid="plan-review-wc-bottomline">{data.working_capital.bottom_line}</p>
        </div>
      )}

      <div className="flex flex-wrap gap-2 mb-3" data-testid="plan-review-acks">
        {PARTNERS.map((p) => {
          const a = ackFor(p);
          return (
            <span key={p} className={`px-2.5 py-1 rounded-full text-[10px] font-mono border ${a ? (a.decision === "approved" ? "border-emerald-500/50 text-emerald-300" : "border-amber-500/50 text-amber-300") : "border-white/15 text-slate-500"}`}
                  data-testid={`plan-ack-${p.split(" ")[0].toLowerCase()}`}>
              {p.split(" ")[0]}: {a ? (a.decision === "approved" ? "APPROVED" : "CHANGES REQUESTED") : "PENDING"}
            </span>
          );
        })}
      </div>

      <div className="flex flex-wrap gap-2 items-center">
        <select value={partner} onChange={(e) => setPartner(e.target.value)} data-testid="plan-review-partner"
                className="h-9 px-2.5 rounded-lg bg-slate-950 border border-white/15 text-xs text-white outline-none">
          {PARTNERS.map((p) => <option key={p}>{p}</option>)}
        </select>
        <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Optional note…" data-testid="plan-review-note-input"
               className="h-9 px-2.5 rounded-lg bg-slate-950 border border-white/15 text-xs text-white flex-1 min-w-[160px] outline-none placeholder:text-slate-600" />
        <Button onClick={() => ack("approved")} disabled={!!busy} data-testid="plan-review-approve-btn"
                className="bg-emerald-500 hover:bg-emerald-400 text-black font-bold font-mono text-[11px] uppercase h-9">
          {busy === "approved" ? <Loader2 size={12} className="mr-1 animate-spin" /> : <Check size={12} className="mr-1" />} Approve
        </Button>
        <Button onClick={() => ack("changes_requested")} disabled={!!busy} data-testid="plan-review-changes-btn"
                className="bg-white/5 border border-amber-500/40 text-amber-300 font-mono text-[11px] uppercase h-9 hover:bg-amber-500/10">
          <MessageSquareWarning size={12} className="mr-1" /> Request Changes
        </Button>
      </div>
    </div>
  );
};
