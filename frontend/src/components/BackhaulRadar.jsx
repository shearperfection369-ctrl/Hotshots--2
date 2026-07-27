import React, { useCallback, useEffect, useState } from "react";
import { Card } from "./ui/card";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { Repeat, RefreshCw, Loader2 } from "lucide-react";
import { api } from "../lib/api";
import { toast } from "sonner";

const Q_CLS = {
  perfect: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  reposition: "bg-cyan-500/15 text-cyan-300 border-cyan-500/30",
  standing: "bg-amber-500/15 text-amber-300 border-amber-500/30",
};
const Q_LABEL = { perfect: "PERFECT — LOADED HOME", reposition: "REPOSITION", standing: "STANDING DEADHEAD" };

export const BackhaulRadar = () => {
  const [d, setD] = useState(null);
  const [loading, setLoading] = useState(false);
  const scan = useCallback(async () => {
    setLoading(true);
    try { const { data } = await api.get("/backhaul/matches"); setD(data); }
    catch (e) { toast.error("Backhaul scan failed"); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { scan(); }, [scan]);

  return (
    <Card className="hud-surface p-4" data-testid="backhaul-radar-panel">
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          <Repeat size={15} className="text-emerald-400" />
          <h3 className="font-display text-sm font-bold text-white">Backhaul Radar</h3>
          {d && <span className="text-[9px] font-mono text-slate-500">{d.trucks_out} trucks out · {d.standing_demands} standing deadheads · {d.count} matches</span>}
        </div>
        <Button size="sm" variant="ghost" onClick={scan} disabled={loading} className="h-7 px-2 text-cyan-300" data-testid="backhaul-rescan-btn">
          {loading ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />}
        </Button>
      </div>
      <div className="text-[10px] font-mono text-slate-500 mb-3">
        Trucks delivering right now matched to paying return loads — empty miles become margin. First Strike prioritizes these lanes automatically.
      </div>
      <div className="space-y-1.5 max-h-64 overflow-y-auto">
        {(d?.matches || []).map((m, i) => (
          <div key={`${m.load_id}-${i}`} className="p-2 rounded border border-white/10 bg-white/[0.02] flex items-center justify-between gap-3 text-[10px] font-mono" data-testid={`backhaul-match-${m.load_id}`}>
            <div className="min-w-0">
              <div className="text-slate-200 truncate">{m.carrier} <span className="text-slate-500">· {m.truck_lane}</span></div>
              <div className="text-cyan-300 truncate">↩ {m.return_lane} · {m.equipment} · {m.miles} mi</div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <span className="text-emerald-300">${Number(m.rate_usd || 0).toLocaleString()} · {m.margin_pct}%</span>
              <Badge className={`${Q_CLS[m.quality]} text-[8px]`}>{Q_LABEL[m.quality]}</Badge>
            </div>
          </div>
        ))}
        {d && !d.matches?.length && (
          <div className="py-6 text-center text-slate-500 text-xs">No matches right now — radar re-checks as trucks book and boards refresh.</div>
        )}
      </div>
    </Card>
  );
};

export default BackhaulRadar;
