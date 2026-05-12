import React, { useEffect, useState } from "react";
import Topbar from "../components/Topbar";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../components/ui/dialog";
import { Switch } from "../components/ui/switch";
import { Plus, Trash2, IdCard, Truck, Search, Phone, Mail } from "lucide-react";
import { toast } from "sonner";

function ExpiryBadge({ dateStr }) {
  if (!dateStr) return <span className="text-[10px] font-mono text-slate-500">—</span>;
  const days = Math.floor((new Date(dateStr) - new Date()) / 86400000);
  const color = days < 0 ? "text-red-300 bg-red-500/10 border-red-500/30"
              : days < 30 ? "text-yellow-300 bg-yellow-500/10 border-yellow-500/30"
              : "text-emerald-300 bg-emerald-500/10 border-emerald-500/30";
  return (
    <span className={`px-1.5 py-0.5 rounded text-[9px] font-mono border ${color}`}>
      {dateStr} {days < 0 ? "· EXPIRED" : days < 30 ? `· ${days}d` : ""}
    </span>
  );
}

function Field({ label, value, onChange, type = "text", testId }) {
  return (
    <div>
      <Label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">{label}</Label>
      <Input type={type} value={value || ""} onChange={(e) => onChange(e.target.value)}
             data-testid={testId} className="bg-[#11151F] border-white/10 mt-1" />
    </div>
  );
}

function DriversTab() {
  const [drivers, setDrivers] = useState([]);
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({});
  const load = () => api.get("/drivers").then(({ data }) => setDrivers(data.drivers || []));
  useEffect(() => { load(); }, []);
  const filtered = drivers.filter((d) => !q || [d.name, d.cdl_number, d.carrier, d.phone].some((v) => (v || "").toLowerCase().includes(q.toLowerCase())));
  const create = async () => {
    if (!form.name) { toast.error("Name required"); return; }
    await api.post("/drivers", form); setOpen(false); setForm({}); toast.success("Driver added"); load();
  };
  const remove = async (id) => {
    if (!window.confirm("Delete this driver?")) return;
    await api.delete(`/drivers/${id}`); toast.success("Driver removed"); load();
  };
  return (
    <Card className="hud-surface" data-testid="drivers-tab">
      <div className="px-5 py-3 border-b border-white/5 flex items-center justify-between flex-wrap gap-2">
        <div>
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400">Drivers · {drivers.length}</div>
          <h3 className="font-display text-lg font-bold">CDL · endorsements · medical compliance</h3>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search size={11} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-500" />
            <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search…" className="pl-7 w-56 bg-[#11151F] border-white/10 text-xs" />
          </div>
          <Button onClick={() => setOpen(true)} data-testid="driver-add" className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold">
            <Plus size={13} className="mr-1" /> Add Driver
          </Button>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="bg-[#0B0E14] text-[9px] font-mono text-slate-500 uppercase tracking-wider">
            <tr>
              <th className="text-left py-2 px-3">Driver</th>
              <th className="text-left py-2 px-3">CDL</th>
              <th className="text-left py-2 px-3">CDL Expiry</th>
              <th className="text-left py-2 px-3">Med Card</th>
              <th className="text-left py-2 px-3">Carrier</th>
              <th className="text-left py-2 px-3">Contact</th>
              <th className="text-center py-2 px-3">Endorsements</th>
              <th className="text-center py-2 px-3"></th>
            </tr>
          </thead>
          <tbody className="font-mono">
            {filtered.map((d) => (
              <tr key={d.id} className="border-t border-white/5 hover:bg-cyan-500/[0.04]" data-testid={`driver-row-${d.id}`}>
                <td className="py-2.5 px-3"><div className="text-cyan-100">{d.name}</div><div className="text-[10px] text-slate-500">{d.id}</div></td>
                <td className="py-2.5 px-3">{d.cdl_class} · {d.cdl_state}<div className="text-[10px] text-slate-500">{d.cdl_number}</div></td>
                <td className="py-2.5 px-3"><ExpiryBadge dateStr={d.cdl_expiry} /></td>
                <td className="py-2.5 px-3"><ExpiryBadge dateStr={d.medical_card_expiry} /></td>
                <td className="py-2.5 px-3 text-slate-200">{d.carrier || "—"}</td>
                <td className="py-2.5 px-3">
                  <div className="flex items-center gap-1 text-slate-300"><Phone size={9} /> {d.phone || "—"}</div>
                  <div className="flex items-center gap-1 text-slate-400 text-[10px]"><Mail size={9} /> {d.email || "—"}</div>
                </td>
                <td className="py-2.5 px-3 text-center">
                  <div className="flex items-center justify-center gap-1">
                    {d.hazmat_endorsement && <span className="px-1 py-0.5 rounded bg-red-500/10 text-red-300 border border-red-500/30 text-[9px]">HAZMAT</span>}
                    {d.tanker_endorsement && <span className="px-1 py-0.5 rounded bg-yellow-500/10 text-yellow-300 border border-yellow-500/30 text-[9px]">TANKER</span>}
                    {d.twic_card && <span className="px-1 py-0.5 rounded bg-cyan-500/10 text-cyan-300 border border-cyan-500/30 text-[9px]">TWIC</span>}
                  </div>
                </td>
                <td className="py-2.5 px-3 text-center">
                  <button onClick={() => remove(d.id)} className="text-red-400 hover:text-red-300"><Trash2 size={12} /></button>
                </td>
              </tr>
            ))}
            {filtered.length === 0 && <tr><td colSpan={8} className="text-center text-slate-500 py-8">No drivers — add one to start the registry.</td></tr>}
          </tbody>
        </table>
      </div>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="bg-[#0B0E14] border-cyan-500/20 max-w-xl">
          <DialogHeader><DialogTitle className="text-white">Add Driver</DialogTitle></DialogHeader>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Name *" value={form.name} onChange={(v) => setForm({ ...form, name: v })} testId="d-name" />
            <Field label="Carrier" value={form.carrier} onChange={(v) => setForm({ ...form, carrier: v })} testId="d-carrier" />
            <Field label="CDL #" value={form.cdl_number} onChange={(v) => setForm({ ...form, cdl_number: v })} testId="d-cdl" />
            <Field label="CDL State" value={form.cdl_state} onChange={(v) => setForm({ ...form, cdl_state: v })} testId="d-cdl-state" />
            <Field label="CDL Expiry" type="date" value={form.cdl_expiry} onChange={(v) => setForm({ ...form, cdl_expiry: v })} testId="d-cdl-exp" />
            <Field label="Med Card Expiry" type="date" value={form.medical_card_expiry} onChange={(v) => setForm({ ...form, medical_card_expiry: v })} testId="d-med-exp" />
            <Field label="Phone" value={form.phone} onChange={(v) => setForm({ ...form, phone: v })} testId="d-phone" />
            <Field label="Email" type="email" value={form.email} onChange={(v) => setForm({ ...form, email: v })} testId="d-email" />
            <div className="col-span-2 flex items-center gap-4 mt-1">
              <label className="flex items-center gap-1.5 text-xs text-slate-300">
                <Switch checked={!!form.hazmat_endorsement} onCheckedChange={(v) => setForm({ ...form, hazmat_endorsement: v })} /> HAZMAT
              </label>
              <label className="flex items-center gap-1.5 text-xs text-slate-300">
                <Switch checked={!!form.tanker_endorsement} onCheckedChange={(v) => setForm({ ...form, tanker_endorsement: v })} /> TANKER
              </label>
              <label className="flex items-center gap-1.5 text-xs text-slate-300">
                <Switch checked={!!form.twic_card} onCheckedChange={(v) => setForm({ ...form, twic_card: v })} /> TWIC
              </label>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)} className="border-white/10 text-slate-300">Cancel</Button>
            <Button onClick={create} data-testid="driver-save" className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold">Save Driver</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}

function TrailersTab() {
  const [trailers, setTrailers] = useState([]);
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ type: "Dry Van 53'" });
  const load = () => api.get("/trailers").then(({ data }) => setTrailers(data.trailers || []));
  useEffect(() => { load(); }, []);
  const filtered = trailers.filter((t) => !q || [t.trailer_no, t.type, t.carrier, t.license_plate, t.vin].some((v) => (v || "").toLowerCase().includes(q.toLowerCase())));
  const create = async () => {
    if (!form.trailer_no) { toast.error("Trailer # required"); return; }
    await api.post("/trailers", form); setOpen(false); setForm({ type: "Dry Van 53'" }); toast.success("Trailer added"); load();
  };
  const remove = async (id) => {
    if (!window.confirm("Delete this trailer?")) return;
    await api.delete(`/trailers/${id}`); toast.success("Trailer removed"); load();
  };
  return (
    <Card className="hud-surface" data-testid="trailers-tab">
      <div className="px-5 py-3 border-b border-white/5 flex items-center justify-between flex-wrap gap-2">
        <div>
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400">Trailers & Equipment · {trailers.length}</div>
          <h3 className="font-display text-lg font-bold">Plate · VIN · capacity · DOT inspection</h3>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search size={11} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-500" />
            <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search…" className="pl-7 w-56 bg-[#11151F] border-white/10 text-xs" />
          </div>
          <Button onClick={() => setOpen(true)} data-testid="trailer-add" className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold">
            <Plus size={13} className="mr-1" /> Add Trailer
          </Button>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="bg-[#0B0E14] text-[9px] font-mono text-slate-500 uppercase tracking-wider">
            <tr>
              <th className="text-left py-2 px-3">Trailer</th>
              <th className="text-left py-2 px-3">Type</th>
              <th className="text-left py-2 px-3">Plate / VIN</th>
              <th className="text-left py-2 px-3">Carrier</th>
              <th className="text-right py-2 px-3">Capacity</th>
              <th className="text-left py-2 px-3">Last Insp.</th>
              <th className="text-left py-2 px-3">Next Insp.</th>
              <th className="text-left py-2 px-3">Notes</th>
              <th className="text-center py-2 px-3"></th>
            </tr>
          </thead>
          <tbody className="font-mono">
            {filtered.map((t) => (
              <tr key={t.id} className="border-t border-white/5 hover:bg-cyan-500/[0.04]" data-testid={`trailer-row-${t.id}`}>
                <td className="py-2.5 px-3 text-cyan-200">{t.trailer_no}</td>
                <td className="py-2.5 px-3 text-slate-200">{t.type}</td>
                <td className="py-2.5 px-3">
                  <div className="text-slate-200">{t.license_plate || "—"} <span className="text-slate-500">{t.license_state}</span></div>
                  <div className="text-[10px] text-slate-500">{t.vin || "—"}</div>
                </td>
                <td className="py-2.5 px-3 text-slate-200">{t.carrier || "—"}</td>
                <td className="py-2.5 px-3 text-right text-slate-200">{(t.capacity_lbs || 0).toLocaleString()} lbs</td>
                <td className="py-2.5 px-3"><span className="text-[10px] text-slate-400">{t.last_inspection || "—"}</span></td>
                <td className="py-2.5 px-3"><ExpiryBadge dateStr={t.next_inspection} /></td>
                <td className="py-2.5 px-3 text-slate-400 text-[10px] max-w-[200px] truncate">{t.notes || "—"}</td>
                <td className="py-2.5 px-3 text-center">
                  <button onClick={() => remove(t.id)} className="text-red-400 hover:text-red-300"><Trash2 size={12} /></button>
                </td>
              </tr>
            ))}
            {filtered.length === 0 && <tr><td colSpan={9} className="text-center text-slate-500 py-8">No trailers yet.</td></tr>}
          </tbody>
        </table>
      </div>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="bg-[#0B0E14] border-cyan-500/20 max-w-xl">
          <DialogHeader><DialogTitle className="text-white">Add Trailer</DialogTitle></DialogHeader>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Trailer # *" value={form.trailer_no} onChange={(v) => setForm({ ...form, trailer_no: v })} testId="t-no" />
            <div>
              <Label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Type</Label>
              <select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })} className="w-full mt-1 bg-[#11151F] border border-white/10 rounded px-2 py-1.5 text-sm text-white">
                {["Dry Van 53'", "Dry Van 48'", "Reefer", "Flatbed", "Step Deck", "Drop Deck", "Pup 28'", "Box Truck", "Sprinter", "40' HC Container", "40' Container", "20' Container", "Air-Ride Lowboy"].map((o) => <option key={o}>{o}</option>)}
              </select>
            </div>
            <Field label="Carrier" value={form.carrier} onChange={(v) => setForm({ ...form, carrier: v })} testId="t-carrier" />
            <Field label="License Plate" value={form.license_plate} onChange={(v) => setForm({ ...form, license_plate: v })} testId="t-plate" />
            <Field label="License State" value={form.license_state} onChange={(v) => setForm({ ...form, license_state: v })} testId="t-state" />
            <Field label="VIN" value={form.vin} onChange={(v) => setForm({ ...form, vin: v })} testId="t-vin" />
            <Field label="Capacity (lbs)" type="number" value={form.capacity_lbs} onChange={(v) => setForm({ ...form, capacity_lbs: Number(v) })} testId="t-cap" />
            <Field label="Last Inspection" type="date" value={form.last_inspection} onChange={(v) => setForm({ ...form, last_inspection: v })} testId="t-last" />
            <Field label="Next Inspection" type="date" value={form.next_inspection} onChange={(v) => setForm({ ...form, next_inspection: v })} testId="t-next" />
            <div className="col-span-2">
              <Label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Notes</Label>
              <Input value={form.notes || ""} onChange={(e) => setForm({ ...form, notes: e.target.value })} className="bg-[#11151F] border-white/10 mt-1" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)} className="border-white/10 text-slate-300">Cancel</Button>
            <Button onClick={create} data-testid="trailer-save" className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold">Save Trailer</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}

export default function DriverRegistry() {
  const [tab, setTab] = useState("drivers");
  return (
    <>
      <Topbar title="Driver & Trailer Registry" subtitle="CDL · medical · trailer · DOT inspection" />
      <div className="p-4 md:p-6 space-y-4">
        <div className="flex items-center gap-1 p-1 hud-surface rounded-lg w-fit" data-testid="registry-tabs">
          <button onClick={() => setTab("drivers")} data-testid="tab-drivers"
            className={`px-4 py-1.5 rounded text-xs font-mono uppercase tracking-wider flex items-center gap-1.5 ${tab === "drivers" ? "bg-cyan-500 text-black font-bold" : "text-slate-400 hover:text-cyan-300"}`}>
            <IdCard size={12} /> Drivers
          </button>
          <button onClick={() => setTab("trailers")} data-testid="tab-trailers"
            className={`px-4 py-1.5 rounded text-xs font-mono uppercase tracking-wider flex items-center gap-1.5 ${tab === "trailers" ? "bg-cyan-500 text-black font-bold" : "text-slate-400 hover:text-cyan-300"}`}>
            <Truck size={12} /> Trailers
          </button>
        </div>
        {tab === "drivers" ? <DriversTab /> : <TrailersTab />}
      </div>
    </>
  );
}
