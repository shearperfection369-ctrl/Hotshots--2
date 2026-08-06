import React, { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { api } from "../../lib/api";
import { Card } from "../ui/card";
import { Truck, Plus, Trash2, MapPin } from "lucide-react";

const STATUS_STYLE = {
  active: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  maintenance: "bg-red-500/15 text-red-300 border-red-500/30",
  idle: "bg-slate-500/15 text-slate-300 border-slate-500/30",
};

export const TcVehicles = () => {
  const [rows, setRows] = useState([]);
  const [techs, setTechs] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", plate: "", vtype: "van", status: "active", assigned_tech_id: "", notes: "" });

  const load = useCallback(() => {
    api.get("/truck-cleaning/vehicles").then(({ data }) => setRows(data.vehicles || [])).catch(() => {});
    api.get("/truck-cleaning/techs").then(({ data }) => setTechs(data.techs || data.rows || [])).catch(() => {});
  }, []);
  useEffect(() => { load(); }, [load]);

  const add = async (e) => {
    e.preventDefault();
    try {
      await api.post("/truck-cleaning/vehicles", form);
      toast.success("Vehicle added to the fleet");
      setForm({ name: "", plate: "", vtype: "van", status: "active", assigned_tech_id: "", notes: "" });
      setOpen(false);
      load();
    } catch (e2) { toast.error(e2?.response?.data?.detail || "Save failed"); }
  };
  const setStatus = async (v, status) => {
    try { await api.put(`/truck-cleaning/vehicles/${v.vehicle_id}`, { ...v, status }); load(); }
    catch { toast.error("Update failed"); }
  };
  const del = async (id) => {
    try { await api.delete(`/truck-cleaning/vehicles/${id}`); load(); } catch { toast.error("Delete failed"); }
  };

  return (
    <div className="space-y-4" data-testid="tc-vehicles">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-bold text-white flex items-center gap-2"><Truck size={15} className="text-amber-400" /> Company Fleet — vans & service trucks</h3>
        <button onClick={() => setOpen(!open)} className="px-4 py-2 rounded-full bg-amber-500 text-black font-bold text-xs inline-flex items-center gap-1.5" data-testid="tc-add-vehicle-btn">
          <Plus size={13} /> Add Vehicle
        </button>
      </div>
      {open && (
        <form onSubmit={add} className="p-4 rounded-xl border border-white/10 bg-slate-950/70 grid sm:grid-cols-3 gap-2" data-testid="tc-vehicle-form">
          <input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Name — e.g. Van 1 · Transit 250"
            className="h-10 px-3 rounded-xl bg-[#11151F] border border-white/10 text-sm text-white" data-testid="tc-veh-name" />
          <input value={form.plate} onChange={(e) => setForm({ ...form, plate: e.target.value })} placeholder="Plate"
            className="h-10 px-3 rounded-xl bg-[#11151F] border border-white/10 text-sm text-white" data-testid="tc-veh-plate" />
          <select value={form.vtype} onChange={(e) => setForm({ ...form, vtype: e.target.value })}
            className="h-10 px-3 rounded-xl bg-[#11151F] border border-white/10 text-sm text-slate-300" data-testid="tc-veh-type">
            <option value="van">Van</option><option value="truck">Truck</option><option value="trailer">Trailer</option>
          </select>
          <select value={form.assigned_tech_id} onChange={(e) => setForm({ ...form, assigned_tech_id: e.target.value })}
            className="h-10 px-3 rounded-xl bg-[#11151F] border border-white/10 text-sm text-slate-300" data-testid="tc-veh-tech">
            <option value="">— Assign crew lead (tracks location) —</option>
            {techs.map((t) => <option key={t.tech_id} value={t.tech_id}>{t.name}</option>)}
          </select>
          <input value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} placeholder="Notes — oil due, gear loadout…"
            className="h-10 px-3 rounded-xl bg-[#11151F] border border-white/10 text-sm text-white" data-testid="tc-veh-notes" />
          <button className="h-10 rounded-full bg-amber-500 text-black text-xs font-black" data-testid="tc-veh-submit">SAVE VEHICLE</button>
        </form>
      )}
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {rows.map((v) => (
          <Card key={v.vehicle_id} className="p-4 bg-slate-950/70 border-white/10" data-testid={`tc-vehicle-${v.vehicle_id}`}>
            <div className="flex items-start justify-between">
              <div>
                <div className="text-sm font-bold text-white">{v.name}</div>
                <div className="text-[10px] font-mono text-slate-500 uppercase">{v.vtype}{v.plate ? ` · ${v.plate}` : ""}</div>
              </div>
              <button onClick={() => del(v.vehicle_id)} className="text-red-400/60 hover:text-red-300" data-testid={`tc-veh-del-${v.vehicle_id}`}><Trash2 size={13} /></button>
            </div>
            <div className="flex gap-1.5 mt-3">
              {["active", "maintenance", "idle"].map((s) => (
                <button key={s} onClick={() => setStatus(v, s)} data-testid={`tc-veh-status-${v.vehicle_id}-${s}`}
                  className={`px-2 py-1 rounded-full border text-[9px] font-mono uppercase ${v.status === s ? STATUS_STYLE[s] : "border-white/10 text-slate-600"}`}>{s}</button>
              ))}
            </div>
            <div className="mt-3 text-[11px] text-slate-400">
              {v.assigned_tech_name ? (
                <span className="flex items-center gap-1.5">
                  <MapPin size={11} className={v.location ? "text-emerald-400" : "text-slate-600"} />
                  {v.assigned_tech_name}
                  {v.location
                    ? <span className="text-emerald-300 font-mono text-[9px]">live · {new Date(v.location.at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
                    : <span className="text-slate-600 font-mono text-[9px]">no ping yet</span>}
                </span>
              ) : <span className="text-slate-600">Unassigned — assign a crew lead to track it live</span>}
            </div>
            {v.notes && <div className="mt-2 text-[10px] text-slate-500">{v.notes}</div>}
          </Card>
        ))}
        {!rows.length && <div className="col-span-full py-10 text-center text-slate-500 text-sm">No company vehicles yet — add your first van. Assigned crew-lead GPS pings track it live on the Crew Live map.</div>}
      </div>
    </div>
  );
};
