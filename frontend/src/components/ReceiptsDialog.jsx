import React, { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";
import { Button } from "./ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./ui/dialog";
import { toast } from "sonner";
import { Receipt, FileDown, Loader2, Plus } from "lucide-react";

const inputCls = "h-9 rounded bg-slate-950 border border-white/10 font-mono text-[11px] px-3 text-slate-200 placeholder:text-slate-600 w-full";

export const ReceiptsDialog = ({ open, onOpenChange }) => {
  const [data, setData] = useState(null);
  const [form, setForm] = useState({ received_from: "", amount_usd: "", method: "Cash / Direct Transfer", purpose: "Capital contribution", notes: "" });
  const [busy, setBusy] = useState(false);
  const [dl, setDl] = useState(null);

  const load = useCallback(() => {
    api.get("/receipts").then(({ data }) => setData(data)).catch(() => {});
  }, []);
  useEffect(() => { if (open) load(); }, [open, load]);

  const create = async () => {
    setBusy(true);
    try {
      const { data: r } = await api.post("/receipts", { ...form, amount_usd: parseFloat(form.amount_usd) });
      toast.success(`🧾 ${r.receipt_no} issued — $${Number(r.amount_usd).toLocaleString()} from ${r.received_from}`);
      setForm({ received_from: "", amount_usd: "", method: "Cash / Direct Transfer", purpose: "Capital contribution", notes: "" });
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Receipt failed"); }
    finally { setBusy(false); }
  };

  const pdf = async (no) => {
    setDl(no);
    try {
      const res = await api.get(`/receipts/${no}/pdf`, { responseType: "blob" });
      const url = window.URL.createObjectURL(new Blob([res.data], { type: "application/pdf" }));
      const a = document.createElement("a");
      a.href = url; a.download = `${no}.pdf`; a.click();
      window.URL.revokeObjectURL(url);
    } catch { toast.error("PDF failed"); }
    finally { setDl(null); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl bg-[#0a1220] border-white/15 text-slate-100" data-testid="receipts-dialog">
        <DialogHeader>
          <DialogTitle className="font-mono text-sm uppercase tracking-[0.2em] text-amber-300 flex items-center gap-2">
            <Receipt size={15} /> Official Receipt Register
            {data && <span className="text-slate-500 normal-case tracking-normal">· total received ${Number(data.total_received).toLocaleString()}</span>}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-1.5 max-h-56 overflow-y-auto" data-testid="receipts-list">
          {(data?.items || []).map((r) => (
            <div key={r.receipt_no} className="text-[11px] font-mono p-2 rounded bg-white/[0.03] border border-white/10 flex items-center justify-between gap-2">
              <div className="min-w-0">
                <span className="text-amber-300">{r.receipt_no}</span>
                <span className="text-slate-200 ml-2">{r.received_from}</span>
                <div className="text-slate-500 truncate">{r.purpose} · {r.received_at?.slice(0, 10)}</div>
              </div>
              <div className="flex items-center gap-3 shrink-0">
                <span className="text-emerald-300 font-bold">${Number(r.amount_usd).toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                <button onClick={() => pdf(r.receipt_no)} disabled={dl === r.receipt_no}
                  className="text-slate-400 hover:text-amber-300" title="Download branded PDF"
                  data-testid={`receipt-pdf-${r.receipt_no}`}>
                  {dl === r.receipt_no ? <Loader2 size={14} className="animate-spin" /> : <FileDown size={14} />}
                </button>
              </div>
            </div>
          ))}
        </div>

        <div className="border-t border-white/10 pt-3">
          <div className="text-[9px] font-mono uppercase tracking-[0.2em] text-slate-500 mb-2 flex items-center gap-1"><Plus size={10} /> Issue New Receipt</div>
          <div className="grid grid-cols-2 gap-2">
            <input className={inputCls} placeholder="Received from *" value={form.received_from} data-testid="receipt-from-input"
              onChange={(e) => setForm({ ...form, received_from: e.target.value })} />
            <input className={inputCls} placeholder="Amount USD *" type="number" value={form.amount_usd} data-testid="receipt-amount-input"
              onChange={(e) => setForm({ ...form, amount_usd: e.target.value })} />
            <select className={inputCls} value={form.method} onChange={(e) => setForm({ ...form, method: e.target.value })}>
              {["Cash / Direct Transfer", "Check", "ACH / Wire", "Zelle / Venmo", "Money Order"].map((m) => <option key={m}>{m}</option>)}
            </select>
            <select className={inputCls} value={form.purpose} onChange={(e) => setForm({ ...form, purpose: e.target.value })}>
              {["Capital contribution", "Additional capital contribution", "Loan to company", "Customer payment", "Reimbursement", "Other"].map((p) => <option key={p}>{p}</option>)}
            </select>
            <input className={`${inputCls} col-span-2`} placeholder="Notes (optional)" value={form.notes}
              onChange={(e) => setForm({ ...form, notes: e.target.value })} />
          </div>
          <Button onClick={create} disabled={busy || !form.received_from || !form.amount_usd} data-testid="receipt-create-btn"
            className="mt-2 bg-amber-500 hover:bg-amber-400 text-black font-black font-mono text-[10px] uppercase">
            {busy ? <Loader2 size={12} className="mr-1 animate-spin" /> : <Receipt size={12} className="mr-1" />}
            Issue Official Receipt
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};
