import React, { useCallback, useEffect, useState } from "react";
import { Plus, Trash2, Receipt, FileDown } from "lucide-react";
import { toast } from "sonner";
import { useTenant } from "./TenantPortal";
import { errText } from "./tenantApi";

const STATUSES = ["quoted", "booked", "in_transit", "delivered", "invoiced", "cancelled"];
const EMPTY = { origin: "", destination: "", pickup_date: "", equipment: "Dry Van", customer: "", carrier: "", customer_rate: "", carrier_rate: "", notes: "" };

export default function TenantLoads() {
  const { api, me, primary } = useTenant();
  const [loads, setLoads] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(EMPTY);
  const canWrite = me.role !== "viewer";

  const load = useCallback(() => api.get("/loads").then((r) => setLoads(r.data.loads)).catch(() => {}), [api]);
  useEffect(() => { load(); }, [load]);

  const submit = async (e) => {
    e.preventDefault();
    try {
      await api.post("/loads", { ...form, customer_rate: Number(form.customer_rate) || 0, carrier_rate: Number(form.carrier_rate) || 0 });
      toast.success("Load booked");
      setOpen(false); setForm(EMPTY); load();
    } catch (e2) { toast.error(errText(e2)); }
  };

  const setStatus = async (id, status) => {
    try { await api.patch(`/loads/${id}`, { status }); load(); } catch (e2) { toast.error(errText(e2)); }
  };
  const invoice = async (id) => {
    try { const { data } = await api.post(`/loads/${id}/invoice`); toast.success(data.already_invoiced ? "Already invoiced" : `Invoice ${data.invoice.invoice_id} created`); load(); }
    catch (e2) { toast.error(errText(e2)); }
  };
  const downloadRatecon = async (id) => {
    try {
      const r = await api.get(`/loads/${id}/ratecon.pdf`, { responseType: "blob" });
      const url = URL.createObjectURL(r.data);
      const a = document.createElement("a");
      a.href = url; a.download = `RateCon_${id}.pdf`; a.click();
      URL.revokeObjectURL(url);
    } catch (e2) { toast.error("Failed to generate rate con"); }
  };
  const del = async (id) => {
    try { await api.delete(`/loads/${id}`); load(); } catch (e2) { toast.error(errText(e2)); }
  };

  return (
    <div data-testid="tenant-loads">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h1 className="text-2xl font-black tracking-tight">Loads</h1>
          <p className="text-slate-500 text-sm">Book, track and invoice your freight.</p>
        </div>
        {canWrite && (
          <button onClick={() => setOpen(true)} data-testid="tenant-new-load-btn"
                  className="px-4 py-2.5 rounded-full font-bold text-black text-sm inline-flex items-center gap-2" style={{ background: primary }}>
            <Plus size={15} /> New Load
          </button>
        )}
      </div>

      {open && (
        <form onSubmit={submit} className="mb-6 p-5 rounded-xl border border-white/10 bg-white/[0.03] grid sm:grid-cols-3 gap-3" data-testid="tenant-load-form">
          {[["origin", "Origin city, ST *"], ["destination", "Destination city, ST *"], ["pickup_date", "Pickup date"],
            ["equipment", "Equipment"], ["customer", "Customer"], ["carrier", "Carrier"],
            ["customer_rate", "Customer rate $"], ["carrier_rate", "Carrier rate $"], ["notes", "Notes"]].map(([k, ph]) => (
            <input key={k} required={ph.includes("*")} value={form[k]} placeholder={ph}
                   type={k.includes("rate") ? "number" : "text"} data-testid={`tenant-load-${k}-input`}
                   onChange={(e) => setForm({ ...form, [k]: e.target.value })}
                   className="h-10 rounded-lg bg-[#0D1117] border border-white/15 px-3 text-sm outline-none focus:border-white/40" />
          ))}
          <div className="sm:col-span-3 flex gap-2">
            <button type="submit" data-testid="tenant-load-submit" className="px-5 py-2 rounded-full font-bold text-black text-sm" style={{ background: primary }}>Book it</button>
            <button type="button" onClick={() => setOpen(false)} className="px-5 py-2 rounded-full border border-white/15 text-sm">Cancel</button>
          </div>
        </form>
      )}

      <div className="rounded-xl border border-white/10 overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="text-left text-[10px] font-mono uppercase text-slate-500 border-b border-white/10 bg-white/[0.02]">
            <th className="p-3">Load</th><th className="p-3">Lane</th><th className="p-3">Customer / Carrier</th>
            <th className="p-3">Rate / Cost</th><th className="p-3">Margin</th><th className="p-3">Status</th>{canWrite && <th className="p-3" />}
          </tr></thead>
          <tbody>
            {loads.length === 0 && <tr><td colSpan={7} className="p-6 text-center text-slate-500">No loads yet.</td></tr>}
            {loads.map((l) => (
              <tr key={l.load_id} className="border-b border-white/5" data-testid={`tenant-load-row-${l.load_id}`}>
                <td className="p-3 font-mono text-[11px]" style={{ color: primary }}>{l.load_id}</td>
                <td className="p-3 text-slate-200">{l.origin} → {l.destination}<div className="text-[10px] text-slate-500">{l.equipment} {l.pickup_date && `· ${l.pickup_date}`}</div></td>
                <td className="p-3 text-slate-400 text-xs">{l.customer || "—"}<div className="text-slate-500">{l.carrier || "no carrier"}</div></td>
                <td className="p-3 tabular-nums text-slate-300">${(l.customer_rate || 0).toLocaleString()}<div className="text-[10px] text-slate-500">${(l.carrier_rate || 0).toLocaleString()} cost</div></td>
                <td className="p-3 font-bold tabular-nums" style={{ color: l.margin >= 0 ? "#34D399" : "#EF4444" }}>${(l.margin || 0).toLocaleString()}</td>
                <td className="p-3">
                  {canWrite ? (
                    <select value={l.status} onChange={(e) => setStatus(l.load_id, e.target.value)} data-testid={`tenant-load-status-${l.load_id}`}
                            className="h-8 rounded bg-[#0D1117] border border-white/10 text-[11px] font-mono px-1">
                      {STATUSES.map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}
                    </select>
                  ) : <span className="text-[11px] font-mono uppercase">{l.status}</span>}
                </td>
                {canWrite && (
                  <td className="p-3">
                    <div className="flex gap-2">
                      <button onClick={() => downloadRatecon(l.load_id)} title="Download rate confirmation PDF" data-testid={`tenant-load-ratecon-${l.load_id}`}
                              className="text-slate-400 hover:text-cyan-300"><FileDown size={15} /></button>
                      <button onClick={() => invoice(l.load_id)} title="Create invoice" data-testid={`tenant-load-invoice-${l.load_id}`}
                              className="text-slate-400 hover:text-emerald-400"><Receipt size={15} /></button>
                      <button onClick={() => del(l.load_id)} title="Delete" data-testid={`tenant-load-delete-${l.load_id}`}
                              className="text-slate-500 hover:text-red-400"><Trash2 size={15} /></button>
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
