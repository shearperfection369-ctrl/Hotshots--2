import React, { useCallback, useEffect, useState } from "react";
import { UserPlus, Pencil, Check, X, UserX } from "lucide-react";
import { toast } from "sonner";
import { api } from "../../lib/api";

const errTxt = (e) => (typeof e?.response?.data?.detail === "string" ? e.response.data.detail : "Something went wrong");
const EMPTY = { carrier_id: "", name: "", phone: "", cdl_number: "", home_base: "" };
const inputCls = "h-8 px-2 rounded-lg bg-slate-900 border border-white/15 text-xs text-white placeholder:text-slate-600 focus:border-cyan-400 outline-none";

export const DriverRoster = () => {
  const [data, setData] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [editId, setEditId] = useState(null);
  const [edit, setEdit] = useState({});

  const load = useCallback(async () => {
    try { const { data: d } = await api.get("/broker-autopilot/drivers"); setData(d); } catch (_) {}
  }, []);
  useEffect(() => { load(); }, [load]);

  const add = async () => {
    if (!form.carrier_id || form.name.trim().length < 2) { toast.error("Pick a carrier and enter a driver name"); return; }
    try {
      await api.post("/broker-autopilot/drivers", form);
      toast.success("Driver added — eligible for AI load assignment");
      setForm(EMPTY); load();
    } catch (e) { toast.error(errTxt(e)); }
  };

  const save = async (id) => {
    try { await api.put(`/broker-autopilot/drivers/${id}`, edit); toast.success("Driver updated"); setEditId(null); load(); }
    catch (e) { toast.error(errTxt(e)); }
  };

  const remove = async (id) => {
    try { await api.delete(`/broker-autopilot/drivers/${id}`); toast.success("Driver deactivated"); load(); }
    catch (e) { toast.error(errTxt(e)); }
  };

  if (!data) return <div className="p-6 text-slate-500 font-mono text-sm">Loading driver roster…</div>;
  const active = data.drivers.filter((d) => d.is_active);
  const byCarrier = active.reduce((m, d) => { (m[d.carrier_name] = m[d.carrier_name] || []).push(d); return m; }, {});

  return (
    <div className="space-y-4" data-testid="driver-roster">
      <div className="p-4 rounded-2xl border border-white/10 bg-slate-950/60 backdrop-blur">
        <div className="text-[10px] font-mono uppercase text-slate-500 mb-2 flex items-center gap-1.5">
          <UserPlus size={12} className="text-cyan-300" /> Add driver
        </div>
        <div className="flex flex-wrap gap-2">
          <select value={form.carrier_id} onChange={(e) => setForm({ ...form, carrier_id: e.target.value })}
                  data-testid="driver-add-carrier" className={`${inputCls} min-w-[190px]`}>
            <option value="">Carrier…</option>
            {data.carriers.map((c) => <option key={c.carrier_id} value={c.carrier_id}>{`${c.name} (${c.mc_number})`}</option>)}
          </select>
          <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
                 placeholder="Driver name" data-testid="driver-add-name" className={`${inputCls} w-40`} />
          <input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })}
                 placeholder="Phone" data-testid="driver-add-phone" className={`${inputCls} w-32`} />
          <input value={form.cdl_number} onChange={(e) => setForm({ ...form, cdl_number: e.target.value })}
                 placeholder="CDL # (auto)" data-testid="driver-add-cdl" className={`${inputCls} w-32`} />
          <input value={form.home_base} onChange={(e) => setForm({ ...form, home_base: e.target.value })}
                 placeholder="Home base (auto)" data-testid="driver-add-home" className={`${inputCls} w-36`} />
          <button onClick={add} data-testid="driver-add-submit"
                  className="h-8 px-4 rounded-full bg-cyan-500 text-black text-xs font-black hover:bg-cyan-400">
            Add
          </button>
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-3">
        {Object.entries(byCarrier).map(([carrier, list]) => (
          <div key={carrier} className="p-4 rounded-2xl border border-white/10 bg-slate-950/60 backdrop-blur">
            <div className="text-xs font-black text-white mb-2">{carrier}
              <span className="ml-2 text-[9px] font-mono text-slate-500">{list.length} driver{list.length === 1 ? "" : "s"}</span>
            </div>
            <div className="space-y-1.5">
              {list.map((d) => (
                <div key={d.driver_id} className="p-2 rounded-xl border border-white/10 bg-white/[0.03]"
                     data-testid={`driver-row-${d.driver_id}`}>
                  {editId === d.driver_id ? (
                    <div className="flex flex-wrap gap-1.5 items-center">
                      <input value={edit.name} onChange={(e) => setEdit({ ...edit, name: e.target.value })}
                             data-testid="driver-edit-name" className={`${inputCls} w-32`} />
                      <input value={edit.phone} onChange={(e) => setEdit({ ...edit, phone: e.target.value })}
                             data-testid="driver-edit-phone" className={`${inputCls} w-28`} />
                      <input value={edit.cdl_number} onChange={(e) => setEdit({ ...edit, cdl_number: e.target.value })}
                             data-testid="driver-edit-cdl" className={`${inputCls} w-28`} />
                      <input value={edit.home_base} onChange={(e) => setEdit({ ...edit, home_base: e.target.value })}
                             data-testid="driver-edit-home" className={`${inputCls} w-32`} />
                      <button onClick={() => save(d.driver_id)} data-testid="driver-edit-save"
                              className="h-7 w-7 rounded-full bg-emerald-500 text-black grid place-items-center"><Check size={13} /></button>
                      <button onClick={() => setEditId(null)} className="h-7 w-7 rounded-full border border-white/15 text-slate-400 grid place-items-center"><X size={13} /></button>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2">
                      <div className="flex-1 min-w-0">
                        <div className="text-[12px] font-bold text-white truncate">{d.name}</div>
                        <div className="text-[9px] font-mono text-slate-500 truncate">
                          {d.cdl_number} · {d.phone} · home: {d.home_base}
                        </div>
                      </div>
                      <button onClick={() => { setEditId(d.driver_id); setEdit({ name: d.name, phone: d.phone, cdl_number: d.cdl_number, home_base: d.home_base }); }}
                              data-testid={`driver-edit-${d.driver_id}`}
                              className="h-7 w-7 rounded-full border border-white/15 text-slate-400 hover:text-cyan-300 grid place-items-center"><Pencil size={12} /></button>
                      <button onClick={() => remove(d.driver_id)} data-testid={`driver-remove-${d.driver_id}`}
                              className="h-7 w-7 rounded-full border border-white/15 text-slate-400 hover:text-red-400 grid place-items-center"><UserX size={12} /></button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
