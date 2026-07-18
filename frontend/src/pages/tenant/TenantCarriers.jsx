import React, { useCallback, useEffect, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { useTenant } from "./TenantPortal";
import { errText } from "./tenantApi";

const EMPTY = { name: "", mc_number: "", contact: "", phone: "", equipment: "" };

export default function TenantCarriers() {
  const { api, me, primary } = useTenant();
  const [carriers, setCarriers] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(EMPTY);
  const canWrite = me.role !== "viewer";

  const load = useCallback(() => api.get("/carriers").then((r) => setCarriers(r.data.carriers)).catch(() => {}), [api]);
  useEffect(() => { load(); }, [load]);

  const submit = async (e) => {
    e.preventDefault();
    try { await api.post("/carriers", form); toast.success("Carrier added"); setOpen(false); setForm(EMPTY); load(); }
    catch (e2) { toast.error(errText(e2)); }
  };
  const del = async (id) => { try { await api.delete(`/carriers/${id}`); load(); } catch (e2) { toast.error(errText(e2)); } };

  return (
    <div data-testid="tenant-carriers">
      <div className="flex items-center justify-between mb-5">
        <div><h1 className="text-2xl font-black tracking-tight">Carriers</h1><p className="text-slate-500 text-sm">Your carrier pool.</p></div>
        {canWrite && <button onClick={() => setOpen(true)} data-testid="tenant-new-carrier-btn"
                             className="px-4 py-2.5 rounded-full font-bold text-black text-sm inline-flex items-center gap-2" style={{ background: primary }}><Plus size={15} /> Add Carrier</button>}
      </div>
      {open && (
        <form onSubmit={submit} className="mb-6 p-5 rounded-xl border border-white/10 bg-white/[0.03] grid sm:grid-cols-3 gap-3" data-testid="tenant-carrier-form">
          {[["name", "Carrier name *"], ["mc_number", "MC #"], ["contact", "Contact name"], ["phone", "Phone"], ["equipment", "Equipment types"]].map(([k, ph]) => (
            <input key={k} required={ph.includes("*")} value={form[k]} placeholder={ph} data-testid={`tenant-carrier-${k}-input`}
                   onChange={(e) => setForm({ ...form, [k]: e.target.value })}
                   className="h-10 rounded-lg bg-[#0D1117] border border-white/15 px-3 text-sm outline-none focus:border-white/40" />
          ))}
          <div className="sm:col-span-3 flex gap-2">
            <button type="submit" data-testid="tenant-carrier-submit" className="px-5 py-2 rounded-full font-bold text-black text-sm" style={{ background: primary }}>Save</button>
            <button type="button" onClick={() => setOpen(false)} className="px-5 py-2 rounded-full border border-white/15 text-sm">Cancel</button>
          </div>
        </form>
      )}
      <div className="rounded-xl border border-white/10 overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="text-left text-[10px] font-mono uppercase text-slate-500 border-b border-white/10 bg-white/[0.02]">
            <th className="p-3">Carrier</th><th className="p-3">MC #</th><th className="p-3">Contact</th><th className="p-3">Equipment</th>{canWrite && <th className="p-3" />}
          </tr></thead>
          <tbody>
            {carriers.length === 0 && <tr><td colSpan={5} className="p-6 text-center text-slate-500">No carriers yet.</td></tr>}
            {carriers.map((c) => (
              <tr key={c.carrier_id} className="border-b border-white/5" data-testid={`tenant-carrier-row-${c.carrier_id}`}>
                <td className="p-3 font-semibold text-slate-200">{c.name}</td>
                <td className="p-3 font-mono text-xs text-slate-400">{c.mc_number || "—"}</td>
                <td className="p-3 text-xs text-slate-400">{c.contact || "—"}<div className="text-slate-500">{c.phone}</div></td>
                <td className="p-3 text-xs text-slate-400">{c.equipment || "—"}</td>
                {canWrite && <td className="p-3"><button onClick={() => del(c.carrier_id)} data-testid={`tenant-carrier-delete-${c.carrier_id}`}
                                                          className="text-slate-500 hover:text-red-400"><Trash2 size={15} /></button></td>}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
