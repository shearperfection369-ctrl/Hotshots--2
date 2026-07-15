import React, { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";
import { Button } from "./ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./ui/dialog";
import { toast } from "sonner";
import { Landmark, Loader2, Plus } from "lucide-react";

const inputCls = "h-9 rounded bg-slate-950 border border-white/10 font-mono text-[11px] px-3 text-slate-200 placeholder:text-slate-600 w-full";
const fmt = (n) => Number(n ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2 });
const TYPE_STYLE = { contribution: "text-emerald-300", holdback: "text-purple-300", withdrawal: "text-orange-300" };

export const CapitalAccountsDialog = ({ open, onOpenChange }) => {
  const [data, setData] = useState(null);
  const [form, setForm] = useState({ member: "Oliver Cummins", entry_type: "contribution", amount_usd: "", notes: "" });
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    api.get("/capital/accounts").then(({ data }) => setData(data)).catch(() => {});
  }, []);
  useEffect(() => { if (open) load(); }, [open, load]);

  const submit = async () => {
    setBusy(true);
    try {
      const { data: e } = await api.post("/capital/entries", { ...form, amount_usd: parseFloat(form.amount_usd) });
      toast.success(e.receipt_no
        ? `💰 ${e.entry_type} recorded — official receipt ${e.receipt_no} issued`
        : `📒 ${e.entry_type} recorded for ${e.member}`);
      setForm({ ...form, amount_usd: "", notes: "" });
      load();
    } catch (err) { toast.error(err?.response?.data?.detail || "Entry failed"); }
    finally { setBusy(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl bg-[#0a1220] border-white/15 text-slate-100" data-testid="capital-accounts-dialog">
        <DialogHeader>
          <DialogTitle className="font-mono text-sm uppercase tracking-[0.2em] text-emerald-300 flex items-center gap-2">
            <Landmark size={15} /> Member Capital Accounts
            {data && <span className="text-slate-500 normal-case tracking-normal">· paid-in ${fmt(data.total_paid_in)} of ${fmt(data.total_committed)} committed</span>}
          </DialogTitle>
        </DialogHeader>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-2" data-testid="capital-member-cards">
          {(data?.members || []).map((m) => (
            <div key={m.member} className="rounded-lg border border-white/10 bg-white/[0.03] p-3" data-testid={`capital-card-${m.member.split(" ")[0].toLowerCase()}`}>
              <div className="font-mono font-bold text-[12px] text-slate-100">{m.member}</div>
              <div className="text-[9px] font-mono uppercase tracking-widest text-slate-500 mb-2">{m.role} · 33⅓%</div>
              <div className="space-y-1 text-[10px] font-mono">
                <div className="flex justify-between"><span className="text-slate-500">Commitment</span><span className="text-slate-300">${fmt(m.commitment_usd)}</span></div>
                <div className="flex justify-between"><span className="text-slate-500">Paid In</span><span className="text-emerald-300">${fmt(m.contributed_usd)}</span></div>
                <div className="flex justify-between"><span className="text-slate-500">Remaining Due</span><span className={m.remaining_commitment_usd > 0 ? "text-orange-300" : "text-emerald-300"}>${fmt(m.remaining_commitment_usd)}</span></div>
                <div className="flex justify-between"><span className="text-slate-500">Reinvest Holdbacks</span><span className="text-purple-300">${fmt(m.holdbacks_usd)}</span></div>
                <div className="flex justify-between"><span className="text-slate-500">Withdrawals</span><span className="text-orange-300">−${fmt(m.withdrawals_usd)}</span></div>
                <div className="flex justify-between border-t border-white/10 pt-1 mt-1"><span className="text-slate-300 font-bold">Balance</span><span className="text-emerald-300 font-bold" data-testid={`capital-balance-${m.member.split(" ")[0].toLowerCase()}`}>${fmt(m.balance_usd)}</span></div>
              </div>
              {m.in_kind && <div className="text-[8px] font-mono text-slate-600 mt-2">+ in-kind: {m.in_kind}</div>}
            </div>
          ))}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
          <div className="border border-white/10 rounded-lg p-3">
            <div className="text-[9px] font-mono uppercase tracking-[0.2em] text-slate-500 mb-2 flex items-center gap-1"><Plus size={10} /> Record Ledger Entry</div>
            <div className="space-y-2">
              <div className="grid grid-cols-2 gap-2">
                <select className={inputCls} value={form.member} data-testid="capital-member-select"
                  onChange={(e) => setForm({ ...form, member: e.target.value })}>
                  {(data?.members || []).map((m) => <option key={m.member}>{m.member}</option>)}
                </select>
                <select className={inputCls} value={form.entry_type} data-testid="capital-type-select"
                  onChange={(e) => setForm({ ...form, entry_type: e.target.value })}>
                  <option value="contribution">Contribution (auto-receipt)</option>
                  <option value="holdback">Reinvestment holdback credit</option>
                  <option value="withdrawal">Equity withdrawal</option>
                </select>
              </div>
              <input className={inputCls} placeholder="Amount USD *" type="number" value={form.amount_usd} data-testid="capital-amount-input"
                onChange={(e) => setForm({ ...form, amount_usd: e.target.value })} />
              <input className={inputCls} placeholder="Notes (optional)" value={form.notes}
                onChange={(e) => setForm({ ...form, notes: e.target.value })} />
              <Button onClick={submit} disabled={busy || !form.amount_usd} data-testid="capital-entry-btn"
                className="bg-emerald-500 hover:bg-emerald-400 text-black font-black font-mono text-[10px] uppercase w-full">
                {busy ? <Loader2 size={12} className="animate-spin" /> : "Record Entry"}
              </Button>
              <div className="text-[8px] font-mono text-slate-600">
                Contributions auto-issue an official Orisei receipt. Withdrawals are blocked above a member's balance (Agreement §3.4).
              </div>
            </div>
          </div>
          <div className="border border-white/10 rounded-lg p-3">
            <div className="text-[9px] font-mono uppercase tracking-[0.2em] text-slate-500 mb-2">Ledger (latest)</div>
            <div className="space-y-1 max-h-44 overflow-y-auto" data-testid="capital-ledger-list">
              {(data?.ledger || []).length === 0 && <div className="text-[10px] font-mono text-slate-500">No ledger entries yet — founding contributions live in the receipt register.</div>}
              {(data?.ledger || []).map((e) => (
                <div key={e.entry_id} className="text-[10px] font-mono p-1.5 rounded bg-white/[0.02] flex justify-between gap-2">
                  <span className="text-slate-300 truncate">
                    {e.at?.slice(0, 10)} · {e.member} · <span className={TYPE_STYLE[e.entry_type]}>{e.entry_type}</span>
                    {e.receipt_no && <span className="text-amber-300"> · {e.receipt_no}</span>}
                  </span>
                  <span className={`shrink-0 ${e.entry_type === "withdrawal" ? "text-orange-300" : "text-emerald-300"}`}>
                    {e.entry_type === "withdrawal" ? "−" : "+"}${fmt(e.amount_usd)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};
