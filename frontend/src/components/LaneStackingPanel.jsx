import React, { useCallback, useEffect, useState } from "react";
import { Card } from "./ui/card";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { Layers, RefreshCw, Loader2, Link2 } from "lucide-react";
import { api } from "../lib/api";
import { toast } from "sonner";

const fmt$ = (n) => `$${Number(n || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

export const LaneStackingPanel = () => {
  const [opps, setOpps] = useState(null);
  const [stacks, setStacks] = useState(null);
  const [loading, setLoading] = useState(false);
  const [booking, setBooking] = useState(null);

  const scan = useCallback(async () => {
    setLoading(true);
    try {
      const [{ data: o }, { data: s }] = await Promise.all([
        api.get("/lane-stacking/opportunities"),
        api.get("/lane-stacking/stacks"),
      ]);
      setOpps(o); setStacks(s);
    } catch (e) { toast.error("Lane stack scan failed"); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { scan(); }, [scan]);

  const book = async (opp) => {
    setBooking(opp.lane_key + opp.equipment);
    try {
      const { data } = await api.post("/lane-stacking/book", {
        lane_key: opp.lane_key, equipment: opp.equipment, load_ids: opp.load_ids,
      });
      toast.success(`Stack booked — ${data.stack.stack_id} · kept ${fmt$(data.stack.discount_kept_usd)} carrier discount as margin`);
      scan();
    } catch (e) { toast.error(e.response?.data?.detail || "Stack booking failed"); }
    finally { setBooking(null); }
  };

  return (
    <Card className="hud-surface p-4" data-testid="lane-stacking-panel">
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          <Layers size={15} className="text-amber-400" />
          <h3 className="font-display text-sm font-bold text-white">Lane Stacking</h3>
          {opps && <span className="text-[9px] font-mono text-slate-500">{opps.count} stackable lanes · {stacks?.stacks?.length || 0} stacks booked · {fmt$(stacks?.total_discount_kept_usd)} discount kept</span>}
        </div>
        <Button size="sm" variant="ghost" onClick={scan} disabled={loading} className="h-7 px-2 text-cyan-300" data-testid="stack-rescan-btn">
          {loading ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />}
        </Button>
      </div>
      <div className="text-[10px] font-mono text-slate-500 mb-3">
        3 consecutive loads on one route = predictability the carrier pays 2–3% for. That discount stays in YOUR margin.
      </div>
      <div className="space-y-1.5 max-h-56 overflow-y-auto">
        {(opps?.opportunities || []).map((o) => (
          <div key={o.lane_key + o.equipment} className="p-2.5 rounded border border-white/10 bg-white/[0.02] flex items-center justify-between gap-3 text-[10px] font-mono" data-testid={`stack-opp-${o.lane_key}`}>
            <div className="min-w-0">
              <div className="text-slate-200 truncate flex items-center gap-1.5">
                <Link2 size={11} className="text-amber-400 shrink-0" />
                {o.lane_label} <span className="text-slate-500">· {o.equipment} · 3 loads</span>
                {o.contract_carrier && <Badge className="bg-cyan-500/15 text-cyan-300 border-cyan-500/30 text-[8px]">CONTRACT: {o.contract_carrier}</Badge>}
              </div>
              <div className="text-slate-500">rev {fmt$(o.revenue_usd)} · margin {fmt$(o.stacked_margin_usd)} ({o.stacked_margin_pct}%) · <span className="text-emerald-300">+{fmt$(o.discount_usd)} from {o.stack_discount_pct}% carrier discount</span></div>
            </div>
            <Button size="sm" onClick={() => book(o)} disabled={booking === o.lane_key + o.equipment}
              className="bg-amber-500 hover:bg-amber-400 text-black font-bold h-7 px-2.5 text-[10px] shrink-0" data-testid={`stack-book-${o.lane_key}`}>
              {booking === o.lane_key + o.equipment ? <Loader2 size={12} className="animate-spin" /> : "Book Stack"}
            </Button>
          </div>
        ))}
        {opps && !opps.opportunities?.length && (
          <div className="py-6 text-center text-slate-500 text-xs">No lanes with 3+ open loads right now — the radar re-checks as boards refresh.</div>
        )}
      </div>
      {(stacks?.stacks || []).length > 0 && (
        <div className="mt-3 pt-2 border-t border-white/5">
          <div className="text-[9px] font-mono uppercase tracking-widest text-slate-500 mb-1.5">Booked stacks</div>
          <div className="space-y-1 max-h-24 overflow-y-auto">
            {stacks.stacks.slice(0, 5).map((s) => (
              <div key={s.stack_id} className="flex items-center justify-between text-[10px] font-mono" data-testid={`stack-row-${s.stack_id}`}>
                <span className="text-slate-300 truncate">{s.stack_id} · {s.lane_label} · {s.carrier_name}</span>
                <span className="text-emerald-300 shrink-0">margin {fmt$(s.margin_usd)} (+{fmt$(s.discount_kept_usd)} kept)</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
};

export default LaneStackingPanel;
