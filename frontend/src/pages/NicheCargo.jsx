import React, { useEffect, useState } from "react";
import Topbar from "../components/Topbar";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Target, Sparkles, Loader2, TrendingUp } from "lucide-react";
import { toast } from "sonner";

export default function NicheCargo() {
  const [data, setData] = useState(null);
  const [advice, setAdvice] = useState(null);
  const [advising, setAdvising] = useState(false);

  useEffect(() => {
    api.get("/niche-cargo/analysis").then(({ data }) => setData(data))
      .catch(() => toast.error("Failed to load niche analysis"));
  }, []);

  const runAdvise = async () => {
    setAdvising(true);
    try {
      const { data } = await api.post("/niche-cargo/ai-advise");
      setAdvice(data);
      toast.success(data.cached ? "Loaded cached advisory (refreshes every 6h)" : "Fresh AI advisory generated");
    } catch (e) {
      toast.error(e.response?.data?.detail || "AI advisory failed");
    } finally { setAdvising(false); }
  };

  const verdictColor = (v) =>
    v?.startsWith("PURSUE") ? "bg-emerald-500/15 text-emerald-300 border-emerald-500/30"
      : v?.startsWith("watch") ? "bg-amber-500/15 text-amber-300 border-amber-500/30"
      : "bg-red-500/10 text-red-300 border-red-500/30";

  return (
    <>
      <Topbar title="Niche Cargo Master" subtitle="AI mines your desk data for consistent profitable lanes & niche specializations worth capitalizing on" />
      <div className="p-4 md:p-6 space-y-4">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <Card className="hud-surface p-5 lg:col-span-2" data-testid="niche-lanes-panel">
            <div className="flex items-center gap-2 mb-3">
              <TrendingUp size={15} className="text-cyan-400" />
              <h3 className="font-display text-base font-bold text-white">Lane Performance Mining</h3>
            </div>
            <div className="overflow-x-auto max-h-[480px] overflow-y-auto">
              <table className="w-full text-xs">
                <thead className="sticky top-0 bg-[#0B0E14]">
                  <tr className="text-left text-[10px] font-mono uppercase tracking-widest text-slate-500 border-b border-white/10">
                    <th className="py-2 pr-3">Lane</th><th className="py-2 pr-3">Loads</th><th className="py-2 pr-3">Revenue</th>
                    <th className="py-2 pr-3">Margin</th><th className="py-2">Verdict</th>
                  </tr>
                </thead>
                <tbody>
                  {(data?.lanes || []).map((r) => (
                    <tr key={r.lane} className="border-b border-white/5 hover:bg-white/[0.02]">
                      <td className="py-2 pr-3 text-slate-200 whitespace-nowrap">{r.lane}</td>
                      <td className="py-2 pr-3 font-mono text-slate-300">{r.loads}</td>
                      <td className="py-2 pr-3 font-mono text-slate-300">${(r.revenue_usd || 0).toLocaleString()}</td>
                      <td className="py-2 pr-3 font-mono text-cyan-300">${(r.margin_usd || 0).toLocaleString()} · {r.margin_pct}%</td>
                      <td className="py-2"><Badge className={`${verdictColor(r.verdict)} text-[9px] font-mono uppercase`}>{r.verdict}</Badge></td>
                    </tr>
                  ))}
                  {!data?.lanes?.length && <tr><td colSpan={5} className="py-8 text-center text-slate-500">No booked lane data yet — book loads and the miner lights up.</td></tr>}
                </tbody>
              </table>
            </div>
          </Card>

          <Card className="hud-surface p-5" data-testid="niche-ai-panel">
            <div className="flex items-center gap-2 mb-3">
              <Sparkles size={15} className="text-amber-400" />
              <h3 className="font-display text-base font-bold text-white">AI Capitalization Advisory</h3>
            </div>
            <Button onClick={runAdvise} disabled={advising} className="w-full bg-amber-500 hover:bg-amber-400 text-black font-bold mb-3" data-testid="niche-ai-advise-btn">
              {advising ? <Loader2 size={14} className="animate-spin mr-1.5" /> : <Target size={14} className="mr-1.5" />}
              {advising ? "Analyzing your desk…" : "Generate AI Advisory"}
            </Button>
            {advice ? (
              <div className="text-xs text-slate-300 whitespace-pre-wrap max-h-[400px] overflow-y-auto leading-relaxed" data-testid="niche-ai-advice-text">{advice.advice}</div>
            ) : (
              <div className="text-xs text-slate-500">Claude reviews your consistent profitable lanes and tells you exactly which niches to double down on, which shipper archetypes to cold-call, and one contrarian play.</div>
            )}
          </Card>
        </div>

        <Card className="hud-surface p-5" data-testid="niche-library-panel">
          <h3 className="font-display text-base font-bold text-white mb-3">Niche Playbook Library</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
            {(data?.niche_library || []).map((n) => (
              <div key={n.niche} className="p-3 rounded border border-white/10 bg-white/[0.02]">
                <div className="text-sm font-semibold text-cyan-300">{n.niche}</div>
                <div className="text-[11px] text-slate-400 mt-1"><span className="text-slate-500 font-mono uppercase text-[9px]">Who ships it · </span>{n.who}</div>
                <div className="text-[11px] text-slate-400 mt-1"><span className="text-slate-500 font-mono uppercase text-[9px]">Why it pays · </span>{n.why}</div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </>
  );
}
