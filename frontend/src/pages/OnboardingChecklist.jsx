/**
 * /onboarding-checklist — Brokerage launch walkthrough.
 * MC filing, BOC-3, FMCSA bond, insurance, load boards, API keys.
 */
import React, { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CheckCircle2, Circle, ExternalLink, RefreshCw, Award } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";

const PRIORITY_COLOR = {
  P0: "bg-red-500/15 text-red-300 border-red-500/40",
  P1: "bg-amber-500/15 text-amber-300 border-amber-500/40",
  P2: "bg-cyan-500/15 text-cyan-300 border-cyan-500/40",
};

export default function OnboardingChecklist() {
  const [data, setData] = useState({ groups: [], total: 0, completed: 0, percent: 0 });
  const [busy, setBusy] = useState(false);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    api.get("/onboarding/checklist").then(({ data: d }) => setData(d)).catch(() => {});
  }, [tick]);

  const toggle = async (itemId) => {
    setBusy(true);
    try {
      await api.post(`/onboarding/checklist/${itemId}/toggle`);
      setTick((t) => t + 1);
    } catch { toast.error("Update failed"); }
    finally { setBusy(false); }
  };

  const reset = async () => {
    if (!confirm("Reset ALL checklist progress?")) return;
    try {
      await api.post("/onboarding/checklist/reset");
      toast.success("Reset");
      setTick((t) => t + 1);
    } catch { toast.error("Reset failed"); }
  };

  return (
    <div className="p-6 max-w-6xl mx-auto" data-testid="onboarding-page">
      <header className="mb-6 flex justify-between items-start">
        <div>
          <div className="flex items-center gap-2 text-cyan-400 font-mono text-[11px] uppercase tracking-[0.18em] mb-1.5">
            <Award size={14} /> Brokerage Launch Runway
          </div>
          <h1 className="font-display text-3xl sm:text-4xl font-black tracking-tighter">Onboarding Checklist</h1>
          <p className="text-slate-400 text-sm mt-2 max-w-2xl">
            Every step to legally operate as a freight brokerage — MC filing, BOC-3, FMCSA bond, insurance, load boards, and the API keys the TMS expects.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => setTick((t) => t + 1)} className="border-cyan-500/40" data-testid="onb-refresh">
            <RefreshCw size={13} className="mr-1" /> Refresh
          </Button>
          <Button variant="outline" size="sm" onClick={reset} className="border-red-500/30 text-red-300" data-testid="onb-reset">
            Reset all
          </Button>
        </div>
      </header>

      {/* Progress bar */}
      <Card className="bg-[#0F1421] border-white/5 mb-4">
        <CardContent className="p-4">
          <div className="flex items-center gap-4">
            <div className="flex-1">
              <div className="flex justify-between mb-1.5">
                <span className="text-xs font-mono text-slate-400 uppercase tracking-wider">Progress</span>
                <span className="text-xs font-mono text-cyan-300" data-testid="onb-progress">
                  {data.completed} / {data.total} · {data.percent}%
                </span>
              </div>
              <div className="w-full h-3 bg-black/40 rounded-full overflow-hidden">
                <div className="h-full bg-gradient-to-r from-cyan-500 to-emerald-500 transition-all"
                  style={{ width: `${data.percent}%` }} />
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="space-y-4" data-testid="onb-groups">
        {data.groups.map((g) => (
          <Card key={g.name} className="bg-[#0F1421] border-white/5" data-testid={`onb-group-${g.name.replace(/\W+/g, "-")}`}>
            <CardHeader className="pb-2">
              <CardTitle className="text-base flex items-center justify-between">
                <span>{g.name}</span>
                <span className="text-xs font-mono text-slate-500">
                  {g.items.filter((i) => i.completed).length} / {g.items.length}
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {g.items.map((i) => (
                <button key={i.id} onClick={() => !busy && toggle(i.id)}
                  data-testid={`onb-item-${i.id}`}
                  className={`w-full text-left p-3 rounded-md border transition-colors ${
                    i.completed
                      ? "border-emerald-500/40 bg-emerald-500/[0.06]"
                      : "border-white/10 bg-[#0B0E14] hover:border-cyan-500/40"
                  }`}>
                  <div className="flex items-start gap-3">
                    {i.completed ? (
                      <CheckCircle2 size={18} className="text-emerald-400 shrink-0 mt-0.5" />
                    ) : (
                      <Circle size={18} className="text-slate-600 shrink-0 mt-0.5" />
                    )}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className={`text-sm font-medium ${i.completed ? "text-emerald-200 line-through" : "text-slate-100"}`}>
                          {i.title}
                        </span>
                        <Badge className={`${PRIORITY_COLOR[i.priority] || ""} border font-mono text-[10px]`}>
                          {i.priority}
                        </Badge>
                        {i.env_var && (
                          <span className="text-[10px] font-mono text-amber-300/70 bg-amber-500/[0.05] px-1.5 py-0.5 rounded">
                            {i.env_var}
                          </span>
                        )}
                      </div>
                      <p className="text-[11px] text-slate-500 mt-1">{i.instruction}</p>
                      {i.link && (
                        <a href={i.link} target="_blank" rel="noreferrer noopener"
                          onClick={(e) => e.stopPropagation()}
                          className="text-[11px] text-cyan-400 hover:underline mt-1.5 inline-flex items-center gap-1">
                          Open resource <ExternalLink size={10} />
                        </a>
                      )}
                      {i.completed_at && (
                        <div className="text-[10px] text-emerald-400/70 mt-1 font-mono">
                          Completed {i.completed_at.slice(0, 10)}
                          {i.completed_by && ` by ${i.completed_by}`}
                        </div>
                      )}
                    </div>
                  </div>
                </button>
              ))}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
