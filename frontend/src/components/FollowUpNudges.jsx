import React, { useCallback, useEffect, useState } from "react";
import { Card } from "./ui/card";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { BellRing, Loader2, Send } from "lucide-react";
import { api } from "../lib/api";
import { toast } from "sonner";

export const FollowUpNudges = ({ onChanged }) => {
  const [d, setD] = useState(null);
  const [sending, setSending] = useState(null);
  const load = useCallback(() => {
    api.get("/carrier-network/follow-ups").then(({ data }) => setD(data)).catch(() => {});
  }, []);
  useEffect(() => { load(); }, [load]);

  const send = async (f) => {
    if (!f.contact_email) { toast.error(`${f.name} has no email on file — open the prospect and add one`); return; }
    setSending(f.id);
    try {
      const { data } = await api.post(`/carrier-network/outreach/${f.id}`, { email: f.contact_email, follow_up: true });
      if (data.sent) toast.success(`Follow-up sent to ${f.name}`);
      else toast.warning("Follow-up recorded but NOT sent — add your Resend key in Connections");
      load(); onChanged?.();
    } catch (e) { toast.error(e.response?.data?.detail || "Send failed"); }
    finally { setSending(null); }
  };

  if (!d || d.count === 0) return null;
  return (
    <Card className="hud-surface p-4 border-amber-500/25" data-testid="followup-nudges-panel">
      <div className="flex items-center gap-2 mb-1">
        <BellRing size={15} className="text-amber-400" />
        <h3 className="font-display text-sm font-bold text-white">Follow-Up Nudges</h3>
        <Badge className="bg-amber-500/15 text-amber-300 border-amber-500/30 text-[9px] font-mono" data-testid="followup-count">{d.count} overdue</Badge>
      </div>
      <div className="text-[10px] font-mono text-slate-500 mb-3">Contacted 5+ days ago with no movement — a ready-to-send nudge is loaded for each.</div>
      <div className="space-y-1.5 max-h-52 overflow-y-auto">
        {d.follow_ups.map((f) => (
          <div key={f.id} className="p-2.5 rounded border border-white/10 bg-white/[0.02]" data-testid={`followup-${f.id}`}>
            <div className="flex items-center justify-between gap-3">
              <div className="min-w-0">
                <div className="text-[11px] text-slate-100 font-semibold truncate">{f.name}
                  <span className="ml-2 text-[9px] font-mono text-amber-300">{f.days_since}d silent · {f.outreach_count} touch{f.outreach_count === 1 ? "" : "es"}</span>
                </div>
                <div className="text-[10px] text-slate-500 truncate italic">“{f.follow_up_preview}”</div>
              </div>
              <Button size="sm" onClick={() => send(f)} disabled={sending === f.id}
                className="bg-amber-500 hover:bg-amber-400 text-black font-bold h-7 px-2.5 text-[10px] shrink-0" data-testid={`followup-send-${f.id}`}>
                {sending === f.id ? <Loader2 size={12} className="animate-spin" /> : <><Send size={11} className="mr-1" /> Send Follow-Up</>}
              </Button>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
};

export default FollowUpNudges;
