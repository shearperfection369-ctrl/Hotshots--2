import React, { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card } from "./ui/card";
import { Button } from "./ui/button";
import { toast } from "sonner";
import { GitCompareArrows, Loader2, BrainCog, ArrowUp, ArrowDown, History } from "lucide-react";

const FACTOR_LABEL = {
  margin_pct: "Margin %", shipper_reliability: "Shipper Reliability",
  lane_profitability: "Lane Profitability", fuel_economics: "Fuel Economics",
  detention_risk: "Detention Risk", driver_match: "Driver Match",
};

export const MisalignmentMonitor = () => {
  const [rep, setRep] = useState(null);
  const [retraining, setRetraining] = useState(false);

  const load = useCallback(() => {
    api.get("/load-hunter/misalignment").then(({ data }) => setRep(data)).catch(() => {});
  }, []);
  useEffect(() => { load(); }, [load]);

  const retrain = async () => {
    setRetraining(true);
    try {
      const { data } = await api.post("/load-hunter/misalignment/retrain");
      toast.success(`🧠 Weights retrained from ${data.decisions_used} divergent decisions — Hunter now scores like you do`);
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Retrain failed"); }
    finally { setRetraining(false); }
  };

  if (!rep) return null;
  const agree = rep.agreement_rate;
  const agreeColor = agree >= 80 ? "text-emerald-400" : agree >= 60 ? "text-yellow-300" : "text-red-400";
  const divTotal = rep.divergence.override_approve + rep.divergence.override_reject;

  return (
    <Card className="hud-surface p-4" data-testid="misalignment-monitor">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
        <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-purple-300 flex items-center gap-1.5">
          <GitCompareArrows size={12} /> Misalignment Detector · AI vs Your Decisions
        </div>
        <Button size="sm" onClick={retrain} disabled={!rep.can_retrain || retraining} data-testid="misalignment-retrain-btn"
          title={rep.can_retrain ? "Retrain weights from your divergent decisions" : `Need ${rep.min_divergent_required}+ divergent decisions (have ${divTotal})`}
          className="bg-purple-500/20 border border-purple-500/40 text-purple-200 font-mono text-[10px] uppercase hover:bg-purple-500/30 disabled:opacity-40">
          {retraining ? <Loader2 size={12} className="mr-1 animate-spin" /> : <BrainCog size={12} className="mr-1" />}
          Retrain From My Decisions
        </Button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-4">
        <div className="rounded border border-white/10 bg-white/[0.03] px-3 py-2">
          <div className={`font-mono font-black text-xl ${agreeColor}`} data-testid="misalignment-agreement-rate">{agree}%</div>
          <div className="text-[9px] font-mono uppercase tracking-widest text-slate-500">Agreement · last {rep.window_size || 0}</div>
        </div>
        <div className="rounded border border-white/10 bg-white/[0.03] px-3 py-2">
          <div className="font-mono font-black text-xl text-cyan-300">{rep.decisions_total}</div>
          <div className="text-[9px] font-mono uppercase tracking-widest text-slate-500">Decisions Logged</div>
        </div>
        <div className="rounded border border-white/10 bg-white/[0.03] px-3 py-2">
          <div className="font-mono font-black text-xl text-emerald-300">{rep.divergence.override_approve}</div>
          <div className="text-[9px] font-mono uppercase tracking-widest text-slate-500">You Booked · AI Lukewarm</div>
        </div>
        <div className="rounded border border-white/10 bg-white/[0.03] px-3 py-2">
          <div className="font-mono font-black text-xl text-red-300">{rep.divergence.override_reject}</div>
          <div className="text-[9px] font-mono uppercase tracking-widest text-slate-500">You Dismissed · AI Liked</div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div data-testid="misalignment-factor-drift">
          <div className="text-[9px] font-mono uppercase tracking-[0.2em] text-slate-500 mb-2">
            Weight Drift Proposal · current → proposed
          </div>
          <div className="space-y-1.5">
            {Object.keys(rep.current_weights).map((k) => {
              const delta = rep.deltas[k];
              return (
                <div key={k} className="flex items-center gap-2 text-[10px] font-mono">
                  <span className="w-36 text-slate-400 truncate">{FACTOR_LABEL[k] || k}</span>
                  <div className="flex-1 h-2 rounded bg-white/5 overflow-hidden relative">
                    <div className="h-full bg-slate-600" style={{ width: `${rep.current_weights[k] * 200}px`, maxWidth: "100%" }} />
                    <div className={`absolute top-0 h-full ${delta >= 0 ? "bg-emerald-400/70" : "bg-red-400/70"}`}
                      style={{ left: `${Math.min(rep.current_weights[k], rep.proposed_weights[k]) * 200}px`, width: `${Math.abs(delta) * 200}px` }} />
                  </div>
                  <span className="text-slate-300 w-10 text-right">{rep.current_weights[k]}</span>
                  <span className={`w-14 text-right flex items-center justify-end gap-0.5 ${delta > 0.002 ? "text-emerald-300" : delta < -0.002 ? "text-red-300" : "text-slate-600"}`}>
                    {delta > 0.002 ? <ArrowUp size={9} /> : delta < -0.002 ? <ArrowDown size={9} /> : null}
                    {rep.proposed_weights[k]}
                  </span>
                </div>
              );
            })}
          </div>
          <div className="text-[9px] font-mono text-slate-600 mt-2">
            Green = you value it more than the AI does · Red = it misleads the AI. Retrain applies the proposal.
          </div>
        </div>

        <div>
          <div className="text-[9px] font-mono uppercase tracking-[0.2em] text-slate-500 mb-2">Divergence Ledger</div>
          <div className="space-y-1.5 max-h-44 overflow-y-auto" data-testid="misalignment-ledger">
            {rep.recent_divergent.length === 0 && (
              <div className="text-[10px] font-mono text-slate-500 py-4">
                No divergences yet — book or dismiss surfaced loads and every override gets logged here.
              </div>
            )}
            {rep.recent_divergent.map((d) => (
              <div key={d.decision_id} className="text-[10px] font-mono p-1.5 rounded bg-white/[0.02] flex justify-between gap-2">
                <span className="text-slate-300 truncate">
                  {d.divergence === "override_approve"
                    ? <>You <span className="text-emerald-300">BOOKED</span> {d.shipper} (AI scored {d.score})</>
                    : <>You <span className="text-red-300">DISMISSED</span> {d.shipper} (AI scored {d.score})</>}
                  <span className="text-slate-600"> · {d.lane}</span>
                </span>
                <span className="text-slate-500 shrink-0">Δ{d.divergence_mag}</span>
              </div>
            ))}
          </div>
          {rep.retrain_history.length > 0 && (
            <div className="mt-3" data-testid="misalignment-retrain-history">
              <div className="text-[9px] font-mono uppercase tracking-[0.2em] text-slate-500 mb-1 flex items-center gap-1">
                <History size={10} /> Retrain History
              </div>
              {rep.retrain_history.slice(0, 3).map((r, i) => (
                <div key={i} className="text-[9px] font-mono text-slate-500 py-0.5">
                  {r.at?.slice(0, 16).replace("T", " ")} · {r.decisions_used} decisions · agreement was {r.agreement_rate}%
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </Card>
  );
};
