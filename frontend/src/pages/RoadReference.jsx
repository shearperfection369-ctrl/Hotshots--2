import React, { useEffect, useMemo, useState } from "react";
import Topbar from "../components/Topbar";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import { Textarea } from "../components/ui/textarea";
import { Scale, StickyNote, BookOpen, Trash2, Search, MapPin } from "lucide-react";
import { toast } from "sonner";

const TABS = [
  { key: "weigh", label: "Weigh Stations", icon: Scale },
  { key: "notes", label: "Lane Notes", icon: StickyNote },
  { key: "nmfc", label: "NMFC Database", icon: BookOpen },
];

export default function RoadReference() {
  const [tab, setTab] = useState("weigh");
  return (
    <>
      <Topbar title="Road Reference" subtitle="Weigh stations · lane-specific shipping notes · NMFC commodity classes" />
      <div className="p-4 md:p-6 space-y-4">
        <div className="flex gap-2">
          {TABS.map((t) => {
            const Icon = t.icon;
            return (
              <button key={t.key} onClick={() => setTab(t.key)} data-testid={`roadref-tab-${t.key}`}
                className={`px-4 py-2 rounded border text-xs font-mono uppercase tracking-wider flex items-center gap-2 transition-colors ${
                  tab === t.key ? "bg-cyan-500 text-black border-cyan-400" : "bg-white/[0.02] text-slate-400 border-white/10 hover:text-cyan-300"}`}>
                <Icon size={13} /> {t.label}
              </button>
            );
          })}
        </div>
        {tab === "weigh" && <WeighStationsTab />}
        {tab === "notes" && <LaneNotesTab />}
        {tab === "nmfc" && <NmfcTab />}
      </div>
    </>
  );
}

function WeighStationsTab() {
  const [stations, setStations] = useState([]);
  const [hourCt, setHourCt] = useState(null);
  const [state, setState] = useState("");
  const load = (st) => {
    api.get(`/reference/weigh-stations${st ? `?state=${st}` : ""}`)
      .then(({ data }) => { setStations(data.stations || []); setHourCt(data.hour_ct); })
      .catch(() => toast.error("Failed to load weigh stations"));
  };
  useEffect(() => { load(state); }, [state]);
  const states = useMemo(() => [...new Set(stations.map((s) => s.state))].sort(), [stations]);
  return (
    <Card className="hud-surface p-5" data-testid="weigh-stations-panel">
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <div>
          <h3 className="font-display text-base font-bold text-white">Fixed Weigh & Inspection Stations</h3>
          <div className="text-[11px] text-slate-500">Open/closed advice is estimated for the current hour ({hourCt !== null ? `${String(hourCt).padStart(2, "0")}:00 CT` : "…"}) — ramp signage always rules.</div>
        </div>
        <Input value={state} onChange={(e) => setState(e.target.value.toUpperCase().slice(0, 2))}
          placeholder="Filter by state (e.g. MN)" className="w-48 bg-[#11151F] border-white/10 font-mono uppercase" data-testid="weigh-state-filter" />
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-left text-[10px] font-mono uppercase tracking-widest text-slate-500 border-b border-white/10">
              <th className="py-2 pr-3">State</th><th className="py-2 pr-3">Station</th><th className="py-2 pr-3">Highway</th>
              <th className="py-2 pr-3">Status Now</th><th className="py-2">Advice</th>
            </tr>
          </thead>
          <tbody>
            {stations.map((s) => (
              <tr key={`${s.state}-${s.name}`} className="border-b border-white/5 hover:bg-white/[0.02]">
                <td className="py-2 pr-3 font-mono text-cyan-300">{s.state}</td>
                <td className="py-2 pr-3 text-slate-100 whitespace-nowrap"><MapPin size={11} className="inline mr-1 text-slate-500" />{s.name}</td>
                <td className="py-2 pr-3 font-mono text-slate-400">{s.hwy}</td>
                <td className="py-2 pr-3">
                  <Badge className={s.likely_open ? "bg-amber-500/15 text-amber-300 border-amber-500/30" : "bg-emerald-500/15 text-emerald-300 border-emerald-500/30"}>
                    {s.likely_open ? "LIKELY OPEN" : "LIKELY CLOSED"}
                  </Badge>
                </td>
                <td className="py-2 text-slate-400 max-w-md">{s.advice}</td>
              </tr>
            ))}
            {!stations.length && <tr><td colSpan={5} className="py-8 text-center text-slate-500">No stations for that state filter.</td></tr>}
          </tbody>
        </table>
      </div>
      {states.length > 1 && <div className="mt-3 text-[10px] font-mono text-slate-600">{stations.length} stations · {states.length} states covered</div>}
    </Card>
  );
}

function LaneNotesTab() {
  const [notes, setNotes] = useState([]);
  const [form, setForm] = useState({ origin: "", destination: "", instructions: "", flags: "", shipper: "" });
  const load = () => api.get("/reference/lane-notes").then(({ data }) => setNotes(data.notes || []));
  useEffect(() => { load(); }, []);
  const save = async () => {
    if (!form.origin || !form.destination || !form.instructions) { toast.error("Origin, destination and instructions are required"); return; }
    try {
      await api.post("/reference/lane-notes", {
        ...form,
        flags: form.flags.split(",").map((f) => f.trim()).filter(Boolean),
      });
      toast.success("Lane note saved");
      setForm({ origin: "", destination: "", instructions: "", flags: "", shipper: "" });
      load();
    } catch (e) { toast.error("Save failed"); }
  };
  const remove = async (id) => {
    try { await api.delete(`/reference/lane-notes/${id}`); toast.success("Deleted"); load(); }
    catch (e) { toast.error("Delete failed"); }
  };
  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <Card className="hud-surface p-5 lg:col-span-1" data-testid="lane-note-form">
        <h3 className="font-display text-base font-bold text-white mb-3">Add Lane Note</h3>
        <div className="space-y-3">
          <Input value={form.origin} onChange={(e) => setForm({ ...form, origin: e.target.value })} placeholder="Origin (Minneapolis, MN)" className="bg-[#11151F] border-white/10" data-testid="lane-note-origin" />
          <Input value={form.destination} onChange={(e) => setForm({ ...form, destination: e.target.value })} placeholder="Destination (Chicago, IL)" className="bg-[#11151F] border-white/10" data-testid="lane-note-destination" />
          <Input value={form.shipper} onChange={(e) => setForm({ ...form, shipper: e.target.value })} placeholder="Shipper (optional)" className="bg-[#11151F] border-white/10" data-testid="lane-note-shipper" />
          <Textarea value={form.instructions} onChange={(e) => setForm({ ...form, instructions: e.target.value })} placeholder="Special instructions — e.g. liftgate required at delivery, no dock, appointment only 8-11 AM…" className="bg-[#11151F] border-white/10 min-h-[90px]" data-testid="lane-note-instructions" />
          <Input value={form.flags} onChange={(e) => setForm({ ...form, flags: e.target.value })} placeholder="Flags CSV: liftgate-required, no-dock" className="bg-[#11151F] border-white/10 font-mono" data-testid="lane-note-flags" />
          <Button onClick={save} className="w-full bg-cyan-500 hover:bg-cyan-400 text-black font-bold" data-testid="lane-note-save-btn">Save Lane Note</Button>
        </div>
      </Card>
      <Card className="hud-surface p-5 lg:col-span-2" data-testid="lane-notes-list">
        <h3 className="font-display text-base font-bold text-white mb-3">Saved Lane Notes ({notes.length})</h3>
        <div className="space-y-2 max-h-[560px] overflow-y-auto">
          {notes.map((n) => (
            <div key={n.id || n.lane_key} className="p-3 rounded border border-white/10 bg-white/[0.02]" data-testid={`lane-note-${n.id}`}>
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="text-sm text-slate-100 font-semibold">{n.origin} → {n.destination}</div>
                  {n.shipper && <div className="text-[10px] font-mono text-slate-500 uppercase">Shipper: {n.shipper}</div>}
                </div>
                <Button size="sm" variant="ghost" onClick={() => remove(n.id)} className="text-red-400 hover:text-red-300 h-7 px-2" data-testid={`lane-note-delete-${n.id}`}><Trash2 size={13} /></Button>
              </div>
              <div className="text-xs text-slate-400 mt-1">{n.instructions}</div>
              {(n.flags || []).length > 0 && (
                <div className="flex gap-1.5 mt-2 flex-wrap">
                  {n.flags.map((f) => <Badge key={f} className="bg-cyan-500/10 text-cyan-300 border-cyan-500/30 text-[9px] font-mono uppercase">{f}</Badge>)}
                </div>
              )}
            </div>
          ))}
          {!notes.length && <div className="py-10 text-center text-slate-500 text-sm">No lane notes yet — capture liftgate, dock and appointment quirks per lane so every re-book runs clean.</div>}
        </div>
      </Card>
    </div>
  );
}

function NmfcTab() {
  const [codes, setCodes] = useState([]);
  const [q, setQ] = useState("");
  useEffect(() => { api.get("/nmfc/codes").then(({ data }) => setCodes(data.codes || [])); }, []);
  const filtered = useMemo(() => {
    const s = q.toLowerCase();
    return codes.filter((c) => !s || (c.description || "").toLowerCase().includes(s)
      || (c.nmfc || "").includes(s) || (c.category || "").toLowerCase().includes(s));
  }, [codes, q]);
  return (
    <Card className="hud-surface p-5" data-testid="nmfc-panel">
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <div>
          <h3 className="font-display text-base font-bold text-white">NMFC Commodity Database ({codes.length} codes)</h3>
          <div className="text-[11px] text-slate-500">Broker reference of the most-used NMFC codes & freight classes. Licensed ClassIT lookups stay authoritative for disputes.</div>
        </div>
        <div className="relative">
          <Search size={13} className="absolute left-2.5 top-2.5 text-slate-500" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search commodity, NMFC #, category…" className="w-72 pl-8 bg-[#11151F] border-white/10" data-testid="nmfc-search-input" />
        </div>
      </div>
      <div className="overflow-x-auto max-h-[620px] overflow-y-auto">
        <table className="w-full text-xs">
          <thead className="sticky top-0 bg-[#0B0E14]">
            <tr className="text-left text-[10px] font-mono uppercase tracking-widest text-slate-500 border-b border-white/10">
              <th className="py-2 pr-3">NMFC</th><th className="py-2 pr-3">Description</th><th className="py-2 pr-3">Class</th><th className="py-2">Category</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((c) => (
              <tr key={c.nmfc + c.description} className="border-b border-white/5 hover:bg-white/[0.02]">
                <td className="py-1.5 pr-3 font-mono text-cyan-300">{c.nmfc}</td>
                <td className="py-1.5 pr-3 text-slate-200">{c.description}</td>
                <td className="py-1.5 pr-3"><Badge className="bg-amber-500/10 text-amber-300 border-amber-500/30 font-mono">{c.freight_class}</Badge></td>
                <td className="py-1.5 text-slate-400">{c.category}</td>
              </tr>
            ))}
            {!filtered.length && <tr><td colSpan={4} className="py-8 text-center text-slate-500">No matches.</td></tr>}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
