import React, { useCallback, useEffect, useState } from "react";
import { Card } from "../ui/card";
import { Receipt, Plus, FileDown, Mail, Link2, Check, BadgeDollarSign, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { api } from "../../lib/api";

const errTxt = (e) => (typeof e?.response?.data?.detail === "string" ? e.response.data.detail : "Something went wrong");
const STATUS_STYLE = {
  draft: "border-slate-500/50 text-slate-400",
  sent: "border-cyan-500/50 text-cyan-300",
  paid: "border-emerald-500/50 text-emerald-400",
  overdue: "border-red-500/50 text-red-400",
};

export const TcInvoices = ({ clients, jobs, reloadAll }) => {
  const [invoices, setInvoices] = useState([]);
  const [open, setOpen] = useState(false);
  const [clientId, setClientId] = useState("");
  const [sel, setSel] = useState([]);
  const [custom, setCustom] = useState({ desc: "", amount: "" });
  const [emailFor, setEmailFor] = useState(null);
  const [emailForm, setEmailForm] = useState({ to_email: "", message: "" });
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try { const { data } = await api.get("/truck-cleaning/invoices"); setInvoices(data.invoices); } catch (_) {}
  }, []);
  useEffect(() => { load(); }, [load]);

  const billableJobs = jobs.filter((j) => j.client_id === clientId && j.status !== "paid");

  const create = async () => {
    const custom_items = custom.desc && Number(custom.amount) > 0 ? [{ desc: custom.desc, amount: Number(custom.amount) }] : [];
    if (sel.length === 0 && custom_items.length === 0) { toast.error("Select at least one job or add a custom line"); return; }
    setBusy(true);
    try {
      await api.post("/truck-cleaning/invoices", { client_id: clientId, job_ids: sel, custom_items, due_days: 15 });
      toast.success("Invoice created");
      setOpen(false); setSel([]); setCustom({ desc: "", amount: "" });
      load();
    } catch (e2) { toast.error(errTxt(e2)); }
    finally { setBusy(false); }
  };

  const pdf = async (inv) => {
    try {
      const r = await api.get(`/truck-cleaning/invoices/${inv.invoice_id}/pdf`, { responseType: "blob" });
      const url = URL.createObjectURL(r.data);
      const a = document.createElement("a"); a.href = url; a.download = `Orisei_${inv.invoice_id}.pdf`; a.click(); URL.revokeObjectURL(url);
    } catch (_) { toast.error("PDF failed"); }
  };

  const copyPayLink = (inv) => {
    const url = `${window.location.origin}/tc/invoice/${inv.invoice_id}`;
    navigator.clipboard?.writeText(url).then(() => toast.success("Payment link copied")).catch(() => toast.info(url));
  };

  const markPaid = async (inv) => {
    try { await api.post(`/truck-cleaning/invoices/${inv.invoice_id}/mark-paid`); toast.success("Marked paid"); load(); reloadAll(); }
    catch (e2) { toast.error(errTxt(e2)); }
  };

  const sendEmail = async () => {
    setBusy(true);
    try {
      await api.post(`/truck-cleaning/invoices/${emailFor.invoice_id}/email`, emailForm);
      toast.success("Invoice emailed with pay link");
      setEmailFor(null); load();
    } catch (e2) { toast.error(errTxt(e2)); }
    finally { setBusy(false); }
  };

  return (
    <div className="space-y-4" data-testid="tc-invoices">
      <div className="flex justify-end">
        <button onClick={() => setOpen(!open)} data-testid="tc-invoice-new-btn"
                className="px-4 py-2 rounded-full bg-amber-500 text-black font-bold text-xs inline-flex items-center gap-1.5"><Plus size={13} /> New Invoice</button>
      </div>
      {open && (
        <Card className="p-4 bg-slate-950/70 border-amber-500/30" data-testid="tc-invoice-form">
          <div className="flex flex-wrap gap-2 items-center mb-3">
            <Receipt className="text-amber-400" size={16} />
            <select value={clientId} onChange={(e) => { setClientId(e.target.value); setSel([]); }} data-testid="tc-invoice-client-select"
                    className="h-9 rounded-lg bg-slate-950 border border-white/15 px-2 text-xs min-w-[200px]">
              <option value="">Select client…</option>
              {clients.map((c) => <option key={c.client_id} value={c.client_id}>{c.company}</option>)}
            </select>
          </div>
          {clientId && (
            <div className="space-y-1.5 mb-3">
              {billableJobs.length === 0 && <div className="text-[11px] text-slate-500 font-mono">No unbilled jobs for this client — add a custom line below.</div>}
              {billableJobs.map((j) => (
                <label key={j.job_id} className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer" data-testid={`tc-invoice-job-${j.job_id}`}>
                  <input type="checkbox" checked={sel.includes(j.job_id)}
                         onChange={() => setSel((s) => s.includes(j.job_id) ? s.filter((x) => x !== j.job_id) : [...s, j.job_id])}
                         className="accent-amber-500" />
                  <span className="font-mono text-amber-300">{j.job_id}</span> {j.date} · {j.cabs} cabs · <span className="font-bold">${j.price.toLocaleString()}</span>
                  <span className="text-[10px] text-slate-600 uppercase">({j.status})</span>
                </label>
              ))}
              <div className="flex gap-2 pt-2">
                <input value={custom.desc} onChange={(e) => setCustom({ ...custom, desc: e.target.value })} placeholder="Custom line (optional)"
                       data-testid="tc-invoice-custom-desc" className="h-9 rounded-lg bg-slate-950 border border-white/15 px-2.5 text-xs flex-1" />
                <input value={custom.amount} onChange={(e) => setCustom({ ...custom, amount: e.target.value })} placeholder="$" type="number"
                       data-testid="tc-invoice-custom-amount" className="h-9 w-24 rounded-lg bg-slate-950 border border-white/15 px-2.5 text-xs" />
              </div>
              <div className="flex justify-between items-center pt-2">
                <div className="text-xs font-mono text-slate-400">
                  Total: <span className="text-amber-300 font-bold">
                    ${(billableJobs.filter((j) => sel.includes(j.job_id)).reduce((s, j) => s + j.price, 0) + (Number(custom.amount) || 0)).toLocaleString()}
                  </span> · Net 15
                </div>
                <button onClick={create} disabled={busy} data-testid="tc-invoice-create-btn"
                        className="px-5 py-2 rounded-full bg-amber-500 text-black font-bold text-xs disabled:opacity-60">
                  {busy ? "Creating…" : "Create Invoice"}
                </button>
              </div>
            </div>
          )}
        </Card>
      )}
      <Card className="bg-slate-950/70 border-white/10 overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="text-left text-[10px] font-mono uppercase text-slate-500 border-b border-white/5">
            <th className="p-3">Invoice</th><th className="p-3">Client</th><th className="p-3">Total</th><th className="p-3">Due</th><th className="p-3">Status</th><th className="p-3">Actions</th></tr></thead>
          <tbody>
            {invoices.length === 0 && <tr><td colSpan={6} className="p-6 text-center text-slate-600 text-xs font-mono">No invoices yet — create one from completed jobs.</td></tr>}
            {invoices.map((inv) => (
              <tr key={inv.invoice_id} className="border-b border-white/5" data-testid={`tc-invoice-row-${inv.invoice_id}`}>
                <td className="p-3 font-mono text-[11px] text-amber-300">{inv.invoice_id}<div className="text-slate-600">{(inv.created_at || "").slice(0, 10)}</div></td>
                <td className="p-3 text-xs text-slate-200">{inv.company}</td>
                <td className="p-3 tabular-nums font-bold">${Number(inv.total).toLocaleString()}</td>
                <td className="p-3 text-[11px] text-slate-500">{(inv.due_date || "").slice(0, 10)}</td>
                <td className="p-3"><span className={`px-2 py-0.5 rounded-full border text-[10px] font-mono uppercase ${STATUS_STYLE[inv.status] || ""}`}>{inv.status}</span></td>
                <td className="p-3">
                  <div className="flex gap-2 items-center">
                    <button onClick={() => pdf(inv)} title="Download branded PDF" data-testid={`tc-invoice-pdf-${inv.invoice_id}`} className="text-amber-400 hover:text-amber-300"><FileDown size={14} /></button>
                    <button onClick={() => copyPayLink(inv)} title="Copy payment link" data-testid={`tc-invoice-paylink-${inv.invoice_id}`} className="text-cyan-300 hover:text-cyan-200"><Link2 size={14} /></button>
                    <button onClick={() => { setEmailFor(inv); setEmailForm({ to_email: inv.email || "", message: "" }); }} title="Email invoice"
                            data-testid={`tc-invoice-email-${inv.invoice_id}`} className="text-slate-400 hover:text-white"><Mail size={14} /></button>
                    {inv.status !== "paid" && (
                      <button onClick={() => markPaid(inv)} title="Mark paid" data-testid={`tc-invoice-markpaid-${inv.invoice_id}`}
                              className="text-emerald-500 hover:text-emerald-400"><BadgeDollarSign size={14} /></button>
                    )}
                    {inv.status === "paid" && <Check size={14} className="text-emerald-400" />}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      {emailFor && (
        <div className="fixed inset-0 z-50 bg-black/70 grid place-items-center p-4" onClick={() => setEmailFor(null)}>
          <Card className="w-full max-w-md p-5 bg-slate-950 border-amber-500/30" onClick={(e) => e.stopPropagation()} data-testid="tc-invoice-email-dialog">
            <div className="font-black text-white mb-1">Email {emailFor.invoice_id}</div>
            <p className="text-[11px] text-slate-500 mb-3">Branded invoice PDF attached + secure pay-online link. Requires Resend key in Connections.</p>
            <input value={emailForm.to_email} onChange={(e) => setEmailForm({ ...emailForm, to_email: e.target.value })} placeholder="client@fleet.com"
                   data-testid="tc-invoice-email-to" className="w-full h-10 rounded-lg bg-slate-900 border border-white/15 px-3 text-sm mb-2 outline-none focus:border-amber-400" />
            <textarea value={emailForm.message} onChange={(e) => setEmailForm({ ...emailForm, message: e.target.value })} placeholder="Personal note (optional)" rows={3}
                      data-testid="tc-invoice-email-message" className="w-full rounded-lg bg-slate-900 border border-white/15 px-3 py-2 text-sm mb-3 outline-none focus:border-amber-400" />
            <div className="flex justify-end gap-2">
              <button onClick={() => setEmailFor(null)} className="px-4 py-2 rounded-full border border-white/15 text-slate-300 text-xs font-bold">Cancel</button>
              <button onClick={sendEmail} disabled={busy || !emailForm.to_email} data-testid="tc-invoice-email-send"
                      className="px-5 py-2 rounded-full bg-amber-500 text-black font-bold text-xs inline-flex items-center gap-1.5 disabled:opacity-60">
                {busy ? <Loader2 size={13} className="animate-spin" /> : <Mail size={13} />} Send
              </button>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
};
