import React, { useEffect, useState } from "react";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { AlarmClock, Loader2, ShieldAlert, FileText, BellRing, CheckCircle2 } from "lucide-react";
import { api } from "../lib/api";
import { toast } from "sonner";

const fmt = (n) => (n == null ? "—" : Number(n).toLocaleString(undefined, { maximumFractionDigits: 0 }));
const FLAG_STYLE = {
  credit_hold: "bg-red-500/20 text-red-300",
  escalate: "bg-orange-500/20 text-orange-300",
  watch: "bg-yellow-500/20 text-yellow-300",
  clean: "bg-emerald-500/15 text-emerald-300",
};

export const ARAgingPanel = () => {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(null);

  const load = () => api.get("/ar/aging").then(({ data: d }) => setData(d)).catch(() => {});
  useEffect(() => { load(); }, []);

  const run = async (key, url, okMsg) => {
    setBusy(key);
    try {
      const { data: d } = await api.post(url);
      toast.success(okMsg(d));
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Action failed"); }
    finally { setBusy(null); }
  };

  const remind = async (c) => {
    if (!c.oldest_invoice_id) return;
    try {
      const { data: d } = await api.post(`/ar/invoices/${c.oldest_invoice_id}/remind`);
      toast.success(`${d.level.replace(/_/g, " ")} logged for ${c.customer_name}`);
    } catch (e) { toast.error(e?.response?.data?.detail || "Reminder failed"); }
  };

  const b = data?.buckets || {};
  const BUCKETS = [["Current", b.current, "text-emerald-300"], ["1–30", b.b1_30, "text-yellow-300"],
    ["31–60", b.b31_60, "text-orange-300"], ["61–90", b.b61_90, "text-red-300"], ["90+", b.b90_plus, "text-red-400"]];

  return (
    <Card className="hud-surface p-4" data-testid="ar-engine-panel">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 mb-3">
        <div>
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-orange-300 flex items-center gap-1.5">
            <AlarmClock size={11} /> AR Engine · Collections
          </div>
          <h3 className="font-display text-lg font-bold">
            ${fmt(data?.past_due_usd)} past due <span className="text-slate-500 text-sm font-mono">({data?.past_due_pct ?? 0}% of ${fmt(data?.total_open_usd)} open)</span>
          </h3>
        </div>
        <div className="flex gap-2">
          <Button size="sm" disabled={busy === "inv"} data-testid="ar-auto-invoice-btn"
            onClick={() => run("inv", "/ar/auto-invoice/run", (d) => `Auto-generated ${d.created} invoice(s) from delivered loads`)}
            className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold font-mono text-[10px] uppercase tracking-wider">
            {busy === "inv" ? <Loader2 size={12} className="mr-1 animate-spin" /> : <FileText size={12} className="mr-1" />}
            Auto-Invoice Delivered
          </Button>
          <Button size="sm" disabled={busy === "risk"} data-testid="ar-sync-risk-btn"
            onClick={() => run("risk", "/ar/sync-risk", (d) => `${d.flagged_count} shipper(s) credit-flagged → AI Hunter will auto-reject their freight`)}
            className="bg-white/5 border border-white/10 hover:border-orange-400/40 hover:text-orange-200 text-slate-300 font-mono text-[10px] uppercase tracking-wider">
            {busy === "risk" ? <Loader2 size={12} className="mr-1 animate-spin" /> : <ShieldAlert size={12} className="mr-1" />}
            Sync Risk Flags
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-5 gap-2 mb-3" data-testid="ar-buckets">
        {BUCKETS.map(([label, v, c]) => (
          <div key={label} className="p-2 rounded bg-white/[0.02] border border-white/5 text-center">
            <div className="text-[9px] font-mono uppercase tracking-wider text-slate-500">{label}</div>
            <div className={`font-mono font-bold text-sm ${c}`}>${fmt(v)}</div>
          </div>
        ))}
      </div>

      <div className="space-y-1.5 max-h-52 overflow-y-auto" data-testid="ar-customer-rows">
        {(data?.customers || []).map((c) => (
          <div key={c.customer_name} className="flex items-center justify-between gap-2 p-2 rounded border border-white/5 bg-white/[0.02]">
            <div className="min-w-0 flex-1">
              <div className="text-xs text-slate-200 flex items-center gap-2 flex-wrap">
                {c.customer_name}
                <span className={`text-[9px] font-mono px-1.5 rounded uppercase ${FLAG_STYLE[c.flag]}`}>{c.flag.replace("_", " ")}</span>
              </div>
              <div className="text-[9px] font-mono text-slate-500">
                {c.open_invoices} open · ${fmt(c.total_open_usd)} · max {c.max_days_past_due}d past due
              </div>
            </div>
            {c.flag !== "clean" && (
              <button onClick={() => remind(c)} data-testid={`ar-remind-${c.customer_name.replace(/\s/g, "-")}`}
                className="text-[9px] font-mono uppercase text-slate-400 hover:text-orange-300 border border-white/10 hover:border-orange-400/40 rounded px-2 py-1 flex items-center gap-1 shrink-0">
                <BellRing size={10} /> Remind
              </button>
            )}
            {c.flag === "clean" && <CheckCircle2 size={13} className="text-emerald-500 shrink-0" />}
          </div>
        ))}
        {data && data.customers?.length === 0 && (
          <div className="text-[11px] font-mono text-slate-500 p-2" data-testid="ar-empty">
            No open invoices — run Auto-Invoice after loads deliver.
          </div>
        )}
      </div>
    </Card>
  );
};
