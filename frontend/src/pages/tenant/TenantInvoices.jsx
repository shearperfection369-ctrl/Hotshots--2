import React, { useCallback, useEffect, useState } from "react";
import { CheckCircle2, FileDown } from "lucide-react";
import { toast } from "sonner";
import { useTenant } from "./TenantPortal";
import { errText } from "./tenantApi";

export default function TenantInvoices() {
  const { api, me, primary } = useTenant();
  const [invoices, setInvoices] = useState([]);
  const canWrite = me.role !== "viewer";

  const load = useCallback(() => api.get("/invoices").then((r) => setInvoices(r.data.invoices)).catch(() => {}), [api]);
  useEffect(() => { load(); }, [load]);

  const markPaid = async (id) => {
    try { await api.post(`/invoices/${id}/paid`); toast.success("Marked paid"); load(); }
    catch (e2) { toast.error(errText(e2)); }
  };
  const downloadPdf = async (id) => {
    try {
      const r = await api.get(`/invoices/${id}/pdf`, { responseType: "blob" });
      const url = URL.createObjectURL(r.data);
      const a = document.createElement("a");
      a.href = url; a.download = `Invoice_${id}.pdf`; a.click();
      URL.revokeObjectURL(url);
    } catch (e2) { toast.error("Failed to generate invoice PDF"); }
  };

  const open = invoices.filter((i) => i.status === "open");
  const openTotal = open.reduce((a, i) => a + (i.amount || 0), 0);

  return (
    <div data-testid="tenant-invoices">
      <div className="flex items-center justify-between mb-5">
        <div><h1 className="text-2xl font-black tracking-tight">Invoices</h1><p className="text-slate-500 text-sm">Created from delivered loads with one click.</p></div>
        <div className="text-right">
          <div className="text-2xl font-black tabular-nums" style={{ color: primary }} data-testid="tenant-open-ar">${openTotal.toLocaleString()}</div>
          <div className="text-[10px] font-mono uppercase text-slate-500">open A/R · {open.length} invoices</div>
        </div>
      </div>
      <div className="rounded-xl border border-white/10 overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="text-left text-[10px] font-mono uppercase text-slate-500 border-b border-white/10 bg-white/[0.02]">
            <th className="p-3">Invoice</th><th className="p-3">Load</th><th className="p-3">Customer</th><th className="p-3">Amount</th><th className="p-3">Status</th>{canWrite && <th className="p-3" />}
          </tr></thead>
          <tbody>
            {invoices.length === 0 && <tr><td colSpan={6} className="p-6 text-center text-slate-500">No invoices yet — invoice a load from the Loads tab.</td></tr>}
            {invoices.map((i) => (
              <tr key={i.invoice_id} className="border-b border-white/5" data-testid={`tenant-invoice-row-${i.invoice_id}`}>
                <td className="p-3 font-mono text-[11px]" style={{ color: primary }}>{i.invoice_id}</td>
                <td className="p-3 font-mono text-[11px] text-slate-400">{i.load_id}</td>
                <td className="p-3 text-slate-300 text-xs">{i.customer || "—"}</td>
                <td className="p-3 font-bold tabular-nums">${(i.amount || 0).toLocaleString()}</td>
                <td className="p-3">
                  <span className={`text-[10px] font-mono uppercase px-2 py-0.5 rounded-full border ${i.status === "paid" ? "text-emerald-300 border-emerald-500/40 bg-emerald-500/10" : "text-orange-300 border-orange-500/40 bg-orange-500/10"}`}>{i.status}</span>
                </td>
                {canWrite && (
                  <td className="p-3">
                    <div className="flex gap-2.5 items-center">
                      <button onClick={() => downloadPdf(i.invoice_id)} title="Download invoice PDF" data-testid={`tenant-invoice-pdf-${i.invoice_id}`}
                              className="text-slate-400 hover:text-cyan-300"><FileDown size={15} /></button>
                      {i.status === "open" && (
                        <button onClick={() => markPaid(i.invoice_id)} data-testid={`tenant-invoice-paid-${i.invoice_id}`}
                                className="flex items-center gap-1 text-xs text-emerald-400 hover:text-emerald-300"><CheckCircle2 size={14} /> Mark paid</button>
                      )}
                    </div>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
