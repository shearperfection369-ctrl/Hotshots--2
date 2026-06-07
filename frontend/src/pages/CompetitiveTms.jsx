/* eslint-disable */
import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import Topbar from "@/components/Topbar";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Plus, Trash2, Calculator, Shield, MapPinned, FileText, Calendar,
  RefreshCw, BadgeCheck, AlertCircle, Send, Trophy, Truck,
} from "lucide-react";

const TABS = [
  { id: "spot-quotes", label: "Spot Requests", icon: Send },
  { id: "accessorials", label: "Accessorials", icon: Calculator },
  { id: "fmcsa", label: "Carrier Vetting", icon: Shield },
  { id: "lanes", label: "Lane Analytics", icon: MapPinned },
  { id: "contracts", label: "Contract Rates", icon: FileText },
  { id: "dock", label: "Dock Scheduling", icon: Calendar },
  { id: "mode-shift", label: "Mode-Shift", icon: Truck },
  { id: "freight-audit", label: "Freight Audit", icon: BadgeCheck },
  { id: "rfps", label: "RFP Board", icon: Trophy },
];

export default function CompetitiveTms() {
  const [tab, setTab] = useState("spot-quotes");
  return (
    <>
      <Topbar title="Competitive TMS" />
      <div className="p-6 max-w-7xl mx-auto space-y-6">
        <Card className="hud-surface p-5" data-testid="comp-tms-header">
          <div className="text-[10px] font-mono uppercase tracking-[0.25em] text-cyan-400">
            McLeod · MercuryGate · Descartes · TMW · Parity
          </div>
          <h1 className="font-display text-3xl font-black mt-1">Competitive TMS Module</h1>
          <p className="text-sm text-slate-400 mt-2 max-w-3xl">
            Nine features that close the gap with mid-market TMS suites: shipper
            spot-quote intake · accessorial catalog · FMCSA vetting · lane
            analytics · contract rates · dock scheduling · mode-shift advisor ·
            freight audit · public RFP board.
          </p>
          <div className="flex flex-wrap gap-2 mt-5 border-t border-white/5 pt-4">
            {TABS.map((t) => (
              <button key={t.id} onClick={() => setTab(t.id)}
                data-testid={`comp-tab-${t.id}`}
                className={`px-3 py-1.5 rounded text-xs font-mono uppercase tracking-wider transition flex items-center gap-2 ${
                  tab === t.id
                    ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40"
                    : "text-slate-400 hover:text-cyan-300 border border-transparent hover:bg-white/5"
                }`}>
                <t.icon size={12} /> {t.label}
              </button>
            ))}
          </div>
        </Card>

        {tab === "spot-quotes" && <SpotQuotesTab />}
        {tab === "accessorials" && <AccessorialsTab />}
        {tab === "fmcsa" && <FmcsaTab />}
        {tab === "lanes" && <LaneAnalyticsTab />}
        {tab === "contracts" && <ContractRatesTab />}
        {tab === "dock" && <DockSchedulingTab />}
        {tab === "mode-shift" && <ModeShiftTab />}
        {tab === "freight-audit" && <FreightAuditTab />}
        {tab === "rfps" && <RfpTab />}
      </div>
    </>
  );
}

// ============================ A · SPOT QUOTE REQUESTS ============================
function SpotQuotesTab() {
  const [items, setItems] = useState([]);
  const fetchAll = async () => {
    try { const { data } = await api.get("/tms-competitive/spot-quote-requests"); setItems(data.items || []); }
    catch { toast.error("Failed to load"); }
  };
  useEffect(() => { fetchAll(); }, []);
  const markQuoted = async (id) => {
    await api.post(`/tms-competitive/spot-quote-requests/${id}/quote`);
    toast.success("Marked quoted"); fetchAll();
  };
  return (
    <Card className="hud-surface p-5" data-testid="spot-quotes-card">
      <h3 className="font-display text-lg font-bold mb-3">Shipper-submitted spot quotes · {items.length}</h3>
      {items.length === 0 ? <Empty msg="No requests yet — share customer portal links to invite shippers."/> : (
        <div className="space-y-2">
          {items.map((r) => (
            <div key={r.request_id} className="p-3 rounded border bg-white/[0.02] flex items-start justify-between flex-wrap gap-2"
                 style={{borderColor:"rgba(255,255,255,0.06)"}} data-testid={`sqr-${r.request_id}`}>
              <div>
                <div className="font-bold">{r.customer_name} · {r.origin} → {r.destination}</div>
                <div className="text-xs text-slate-500 font-mono mt-0.5">
                  {r.request_id} · pickup {r.pickup_date || "—"} · {r.equipment} · {r.weight_lbs || "—"} lbs
                </div>
                {r.notes && <div className="text-xs text-slate-400 mt-1 italic">"{r.notes}"</div>}
              </div>
              <div className="flex items-center gap-2">
                <Pill status={r.status} />
                {r.status === "open" && (
                  <Button size="sm" onClick={() => markQuoted(r.request_id)}
                    className="bg-cyan-500 hover:bg-cyan-400 text-black text-xs h-7"
                    data-testid={`sqr-quote-${r.request_id}`}>Mark quoted</Button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

// ============================ B · ACCESSORIALS ============================
function AccessorialsTab() {
  const [items, setItems] = useState([]);
  const [form, setForm] = useState({ code: "", label: "", description: "", rate_usd: "", rate_type: "flat", chargeable_to: "customer" });
  const fetchAll = async () => {
    const { data } = await api.get("/tms-competitive/accessorials?active_only=false");
    setItems((data.items || []).filter((a) => a.active !== false));
  };
  useEffect(() => { fetchAll(); }, []);
  const create = async () => {
    if (!form.code || !form.label) return toast.error("Code + label required");
    try {
      await api.post("/tms-competitive/accessorials", { ...form, rate_usd: parseFloat(form.rate_usd || 0) });
      toast.success("Added"); setForm({ code: "", label: "", description: "", rate_usd: "", rate_type: "flat", chargeable_to: "customer" }); fetchAll();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };
  const remove = async (id) => {
    if (!window.confirm("Deactivate?")) return;
    await api.delete(`/tms-competitive/accessorials/${id}`); fetchAll();
  };
  return (
    <>
      <Card className="hud-surface p-5" data-testid="acc-form-card">
        <h3 className="font-display text-lg font-bold mb-3 flex items-center gap-2"><Plus size={16} className="text-cyan-400"/> Add accessorial</h3>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          <F label="Code *" value={form.code} onChange={(v)=>setForm({...form,code:v.toUpperCase()})} testId="acc-code"/>
          <F label="Label *" value={form.label} onChange={(v)=>setForm({...form,label:v})} testId="acc-label"/>
          <F label="Rate ($)" type="number" value={form.rate_usd} onChange={(v)=>setForm({...form,rate_usd:v})} testId="acc-rate"/>
          <Select label="Rate type" value={form.rate_type} onChange={(v)=>setForm({...form,rate_type:v})}
            opts={["flat","per_hour","per_mile","per_pallet"]} testId="acc-type"/>
          <Select label="Chargeable to" value={form.chargeable_to} onChange={(v)=>setForm({...form,chargeable_to:v})}
            opts={["customer","carrier","both"]} testId="acc-charge"/>
          <F label="Description" value={form.description} onChange={(v)=>setForm({...form,description:v})} testId="acc-desc"/>
        </div>
        <Button onClick={create} className="bg-cyan-500 hover:bg-cyan-400 text-black mt-3" data-testid="acc-create">
          <Plus size={14} className="mr-2"/> Add
        </Button>
      </Card>
      <Card className="hud-surface p-5" data-testid="acc-list-card">
        <h3 className="font-display text-lg font-bold mb-3">Active accessorials · {items.length}</h3>
        <div className="space-y-1.5">
          {items.map((a) => (
            <div key={a.accessorial_id} className="px-3 py-2 rounded border bg-white/[0.02] flex items-center justify-between gap-2"
                 style={{borderColor:"rgba(255,255,255,0.06)"}}>
              <div className="flex-1">
                <span className="font-mono text-cyan-300 text-xs mr-3">{a.code}</span>
                <span className="font-bold text-sm">{a.label}</span>
                <span className="text-xs text-slate-500 ml-3">${a.rate_usd} {a.rate_type.replace("_", " ")}</span>
                <span className="text-[10px] text-slate-500 ml-3 font-mono uppercase">→ {a.chargeable_to}</span>
              </div>
              {!a.is_default && (
                <Button size="sm" variant="ghost" onClick={() => remove(a.accessorial_id)}
                  className="text-red-400 hover:bg-red-500/10 h-7 w-7 p-0">
                  <Trash2 size={12}/>
                </Button>
              )}
            </div>
          ))}
        </div>
      </Card>
    </>
  );
}

// ============================ C · FMCSA SAFER LOOKUP ============================
function FmcsaTab() {
  const [mc, setMc] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const lookup = async () => {
    if (!mc) return toast.error("Enter MC #");
    setLoading(true);
    try { const { data } = await api.get(`/tms-competitive/fmcsa/${mc.replace(/\D/g, "")}`); setResult(data); }
    catch (e) { toast.error(e?.response?.data?.detail || "Lookup failed"); }
    finally { setLoading(false); }
  };
  return (
    <Card className="hud-surface p-5" data-testid="fmcsa-card">
      <h3 className="font-display text-lg font-bold mb-3">FMCSA Carrier Safety Lookup</h3>
      <div className="flex gap-2 items-end">
        <div className="flex-1 max-w-xs">
          <Label className="text-[10px] font-mono uppercase tracking-[0.15em] text-slate-400 mb-1.5 block">MC #</Label>
          <Input value={mc} onChange={(e)=>setMc(e.target.value)} placeholder="e.g. 111180" data-testid="fmcsa-mc"
                 className="bg-[#0B1320] border-white/10 text-white"/>
        </div>
        <Button onClick={lookup} disabled={loading} className="bg-cyan-500 hover:bg-cyan-400 text-black" data-testid="fmcsa-lookup">
          <Shield size={14} className="mr-2"/>{loading ? "Looking up…" : "Vet carrier"}
        </Button>
      </div>
      {result && (
        <div className="mt-5 p-4 rounded border" style={{borderColor:"rgba(255,255,255,0.06)",background:"rgba(255,255,255,0.02)"}}>
          {result.error ? (
            <div className="text-red-300 text-sm flex items-start gap-2">
              <AlertCircle size={16} className="mt-0.5"/>
              <div>
                <div className="font-bold">{result.error}</div>
                <div className="text-xs text-slate-400 mt-1">
                  FMCSA SAFER may require registration for a webKey at{" "}
                  <a href="https://mobile.fmcsa.dot.gov" target="_blank" rel="noreferrer" className="text-cyan-300 underline">mobile.fmcsa.dot.gov</a>{" "}
                  for production-grade lookups. For now, manually verify at the link.
                </div>
              </div>
            </div>
          ) : (
            <>
              <div className="flex items-center justify-between flex-wrap gap-2">
                <div>
                  <div className="font-bold text-lg">{result.legal_name || "Unknown carrier"}</div>
                  <div className="text-xs text-slate-500 font-mono">MC {result.mc} · {result.city_state}</div>
                </div>
                <VerdictPill v={result.verdict} />
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-4">
                <Stat label="Status" value={result.operating_status}/>
                <Stat label="Safety Rating" value={result.safety_rating}/>
                <Stat label="Power Units" value={result.power_units || "—"}/>
                <Stat label="Drivers" value={result.drivers || "—"}/>
              </div>
              {result.flags?.length > 0 && (
                <div className="mt-4 space-y-1.5">
                  {result.flags.map((f, i) => (
                    <div key={i} className={`text-xs px-2 py-1.5 rounded ${
                      f.level === "red" ? "bg-red-500/15 text-red-300" : "bg-amber-500/15 text-amber-300"
                    }`}>⚠ {f.code}: {f.msg}</div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      )}
    </Card>
  );
}

// ============================ D · LANE ANALYTICS ============================
function LaneAnalyticsTab() {
  const [d, setD] = useState(null);
  const [w, setW] = useState(90);
  const fetch = async () => {
    const { data } = await api.get(`/tms-competitive/lane-analytics?window_days=${w}`); setD(data);
  };
  useEffect(() => { fetch(); }, [w]);  // eslint-disable-line
  if (!d) return <Card className="hud-surface p-5"><div className="text-slate-400 text-sm">Loading…</div></Card>;
  return (
    <Card className="hud-surface p-5" data-testid="lane-analytics-card">
      <div className="flex items-center justify-between flex-wrap gap-2 mb-4">
        <h3 className="font-display text-lg font-bold">Lane Analytics · {d.lane_count} lanes · {d.total_loads} loads</h3>
        <div className="flex gap-1">
          {[30, 90, 180, 365].map((days) => (
            <Button key={days} size="sm" variant="ghost"
              onClick={() => setW(days)}
              className={`text-xs h-7 ${w === days ? "bg-cyan-500/20 text-cyan-300" : "text-slate-400"}`}>
              {days}d
            </Button>
          ))}
        </div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mb-5">
        <Stat label="Lanes" value={d.lane_count}/>
        <Stat label="Total loads" value={d.total_loads}/>
        <Stat label="Network avg RPM" value={`$${d.network_avg_rpm}`}/>
        <Stat label="Window" value={`${w} days`}/>
      </div>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-[10px] font-mono uppercase tracking-wider text-slate-400 border-b border-white/5">
            <th className="text-left py-2">Lane</th>
            <th className="text-right">Loads</th>
            <th className="text-right">Avg $</th>
            <th className="text-right">RPM</th>
            <th className="text-right">OTP</th>
            <th className="text-right">Cap</th>
          </tr>
        </thead>
        <tbody>
          {d.lanes.map((L, i) => (
            <tr key={i} className="border-b border-white/5" data-testid={`lane-${L.origin}-${L.destination}`}>
              <td className="py-2">{L.origin} → {L.destination}</td>
              <td className="text-right">{L.loads}</td>
              <td className="text-right">{L.avg_rate_usd ? `$${L.avg_rate_usd.toLocaleString()}` : "—"}</td>
              <td className="text-right">{L.rpm ? `$${L.rpm}` : "—"}</td>
              <td className="text-right">{L.on_time_pct !== null ? `${L.on_time_pct}%` : "—"}</td>
              <td className="text-right">
                <span className={`px-1.5 py-0.5 rounded text-[10px] font-mono uppercase ${
                  L.capacity_tightness === "high" ? "bg-red-500/15 text-red-300" :
                  L.capacity_tightness === "low" ? "bg-emerald-500/15 text-emerald-300" :
                  "bg-amber-500/15 text-amber-300"
                }`}>{L.capacity_tightness}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

// ============================ E · CONTRACT RATES ============================
function ContractRatesTab() {
  const [items, setItems] = useState([]);
  const [form, setForm] = useState({ customer_id: "", origin_state: "", destination_state: "", equipment: "Dry Van", line_haul_usd: "", fuel_surcharge_usd: "0", effective_from: "", effective_to: "", min_commit_loads: "" });
  const fetchAll = async () => { const { data } = await api.get("/tms-competitive/contract-rates"); setItems(data.items || []); };
  useEffect(() => { fetchAll(); }, []);
  const create = async () => {
    try {
      await api.post("/tms-competitive/contract-rates", { ...form,
        line_haul_usd: parseFloat(form.line_haul_usd),
        fuel_surcharge_usd: parseFloat(form.fuel_surcharge_usd || 0),
        min_commit_loads: form.min_commit_loads ? parseInt(form.min_commit_loads, 10) : null,
        origin_state: form.origin_state.toUpperCase(), destination_state: form.destination_state.toUpperCase() });
      toast.success("Contract added"); fetchAll();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };
  return (
    <>
      <Card className="hud-surface p-5" data-testid="contract-form-card">
        <h3 className="font-display text-lg font-bold mb-3">New contract rate</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <F label="Customer ID *" value={form.customer_id} onChange={(v)=>setForm({...form,customer_id:v})} testId="ctr-cust"/>
          <F label="Origin state *" value={form.origin_state} onChange={(v)=>setForm({...form,origin_state:v})} testId="ctr-os"/>
          <F label="Dest state *" value={form.destination_state} onChange={(v)=>setForm({...form,destination_state:v})} testId="ctr-ds"/>
          <F label="Equipment" value={form.equipment} onChange={(v)=>setForm({...form,equipment:v})} testId="ctr-eq"/>
          <F label="Line haul $ *" type="number" value={form.line_haul_usd} onChange={(v)=>setForm({...form,line_haul_usd:v})} testId="ctr-lh"/>
          <F label="FSC $" type="number" value={form.fuel_surcharge_usd} onChange={(v)=>setForm({...form,fuel_surcharge_usd:v})} testId="ctr-fsc"/>
          <F label="From *" type="date" value={form.effective_from} onChange={(v)=>setForm({...form,effective_from:v})} testId="ctr-from"/>
          <F label="To *" type="date" value={form.effective_to} onChange={(v)=>setForm({...form,effective_to:v})} testId="ctr-to"/>
          <F label="Min commit (loads)" type="number" value={form.min_commit_loads} onChange={(v)=>setForm({...form,min_commit_loads:v})} testId="ctr-min"/>
        </div>
        <Button onClick={create} className="bg-cyan-500 hover:bg-cyan-400 text-black mt-3" data-testid="ctr-create">
          <Plus size={14} className="mr-2"/> Add contract
        </Button>
      </Card>
      <Card className="hud-surface p-5">
        <h3 className="font-display text-lg font-bold mb-3">Active contracts · {items.length}</h3>
        {items.length === 0 ? <Empty msg="No contracts on file."/> : (
          <div className="space-y-2">
            {items.map((c) => (
              <div key={c.contract_rate_id} className="p-3 rounded border bg-white/[0.02] flex items-center justify-between flex-wrap gap-2"
                   style={{borderColor:"rgba(255,255,255,0.06)"}}>
                <div>
                  <div className="font-bold">{c.origin_state} → {c.destination_state} · {c.equipment}</div>
                  <div className="text-xs text-slate-500 font-mono mt-0.5">
                    {c.contract_rate_id} · ${c.line_haul_usd} line haul + ${c.fuel_surcharge_usd} FSC · {c.effective_from} → {c.effective_to}
                    {c.min_commit_loads && <> · min {c.min_commit_loads} loads</>}
                  </div>
                </div>
                <span className="text-xs font-mono text-slate-500">Customer · {c.customer_id}</span>
              </div>
            ))}
          </div>
        )}
      </Card>
    </>
  );
}

// ============================ F · DOCK SCHEDULING ============================
function DockSchedulingTab() {
  const [items, setItems] = useState([]);
  const [form, setForm] = useState({ facility_name: "", facility_address: "", appointment_type: "pickup", scheduled_at: "", duration_minutes: "60", carrier_name: "", carrier_mc: "", notes: "" });
  const fetchAll = async () => { const { data } = await api.get("/tms-competitive/dock-appointments"); setItems(data.items || []); };
  useEffect(() => { fetchAll(); }, []);
  const create = async () => {
    if (!form.facility_name || !form.scheduled_at) return toast.error("Facility + scheduled time required");
    try {
      await api.post("/tms-competitive/dock-appointments", { ...form, duration_minutes: parseInt(form.duration_minutes, 10) });
      toast.success("Scheduled"); fetchAll();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };
  const cancel = async (id) => {
    if (!window.confirm("Cancel appointment?")) return;
    await api.delete(`/tms-competitive/dock-appointments/${id}`); fetchAll();
  };
  return (
    <>
      <Card className="hud-surface p-5">
        <h3 className="font-display text-lg font-bold mb-3">Schedule dock appointment</h3>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          <F label="Facility *" value={form.facility_name} onChange={(v)=>setForm({...form,facility_name:v})} testId="dock-fac"/>
          <F label="Facility address" value={form.facility_address} onChange={(v)=>setForm({...form,facility_address:v})} testId="dock-addr"/>
          <Select label="Type" value={form.appointment_type} onChange={(v)=>setForm({...form,appointment_type:v})} opts={["pickup","delivery"]} testId="dock-type"/>
          <F label="Scheduled at *" type="datetime-local" value={form.scheduled_at} onChange={(v)=>setForm({...form,scheduled_at:v})} testId="dock-when"/>
          <F label="Duration (min)" type="number" value={form.duration_minutes} onChange={(v)=>setForm({...form,duration_minutes:v})} testId="dock-dur"/>
          <F label="Carrier name" value={form.carrier_name} onChange={(v)=>setForm({...form,carrier_name:v})} testId="dock-carrier"/>
          <F label="Carrier MC" value={form.carrier_mc} onChange={(v)=>setForm({...form,carrier_mc:v})} testId="dock-mc"/>
          <F label="Notes" value={form.notes} onChange={(v)=>setForm({...form,notes:v})} testId="dock-notes"/>
        </div>
        <Button onClick={create} className="bg-cyan-500 hover:bg-cyan-400 text-black mt-3" data-testid="dock-create">
          <Plus size={14} className="mr-2"/> Schedule
        </Button>
      </Card>
      <Card className="hud-surface p-5">
        <h3 className="font-display text-lg font-bold mb-3">Upcoming · {items.length}</h3>
        <div className="space-y-2">
          {items.map((a) => (
            <div key={a.appt_id} className="p-3 rounded border bg-white/[0.02] flex items-center justify-between flex-wrap gap-2"
                 style={{borderColor:"rgba(255,255,255,0.06)"}}>
              <div>
                <div className="font-bold">{a.facility_name} · {a.appointment_type}</div>
                <div className="text-xs text-slate-500 font-mono mt-0.5">
                  {a.appt_id} · {a.scheduled_at?.replace("T", " ").slice(0, 16)} · {a.duration_minutes} min
                  {a.carrier_name && <> · {a.carrier_name}</>}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Pill status={a.status}/>
                {a.status === "scheduled" && (
                  <Button size="sm" variant="ghost" onClick={()=>cancel(a.appt_id)} className="text-red-400 hover:bg-red-500/10 h-7 w-7 p-0">
                    <Trash2 size={12}/>
                  </Button>
                )}
              </div>
            </div>
          ))}
        </div>
      </Card>
    </>
  );
}

// ============================ G · MODE-SHIFT ============================
function ModeShiftTab() {
  const [form, setForm] = useState({ origin: "", destination: "", miles: "", weight_lbs: "", equipment: "Dry Van", current_rate_usd: "" });
  const [result, setResult] = useState(null);
  const calc = async () => {
    try {
      const { data } = await api.post("/tms-competitive/mode-shift", { ...form, miles: parseFloat(form.miles), weight_lbs: parseFloat(form.weight_lbs), current_rate_usd: parseFloat(form.current_rate_usd) });
      setResult(data);
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };
  return (
    <>
      <Card className="hud-surface p-5">
        <h3 className="font-display text-lg font-bold mb-3">Mode-shift recommender</h3>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          <F label="Origin *" value={form.origin} onChange={(v)=>setForm({...form,origin:v})} testId="ms-o"/>
          <F label="Destination *" value={form.destination} onChange={(v)=>setForm({...form,destination:v})} testId="ms-d"/>
          <F label="Miles *" type="number" value={form.miles} onChange={(v)=>setForm({...form,miles:v})} testId="ms-mi"/>
          <F label="Weight (lbs) *" type="number" value={form.weight_lbs} onChange={(v)=>setForm({...form,weight_lbs:v})} testId="ms-w"/>
          <F label="Equipment" value={form.equipment} onChange={(v)=>setForm({...form,equipment:v})} testId="ms-eq"/>
          <F label="Current rate $ *" type="number" value={form.current_rate_usd} onChange={(v)=>setForm({...form,current_rate_usd:v})} testId="ms-r"/>
        </div>
        <Button onClick={calc} className="bg-cyan-500 hover:bg-cyan-400 text-black mt-3" data-testid="ms-calc">
          <RefreshCw size={14} className="mr-2"/> Analyze
        </Button>
      </Card>
      {result && (
        <Card className="hud-surface p-5">
          <h3 className="font-display text-lg font-bold mb-3">{result.lane} · {result.miles} mi</h3>
          <div className="space-y-3">
            {result.options.map((o, i) => (
              <div key={i} className="p-3 rounded border bg-white/[0.02]" style={{borderColor:"rgba(255,255,255,0.06)"}}>
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <div>
                    <div className="font-bold">{o.mode}</div>
                    <div className="text-xs text-slate-500 font-mono mt-0.5">
                      ${o.estimated_rate_usd?.toLocaleString()} · saves ${o.savings_usd?.toLocaleString()} ({o.savings_pct}%) · +{o.added_days}d
                    </div>
                  </div>
                  {o.savings_usd > 0 && (
                    <span className="px-2 py-0.5 rounded text-[10px] font-mono uppercase bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
                      Recommended
                    </span>
                  )}
                </div>
                {o.notes && <div className="text-xs text-slate-400 italic mt-2">{o.notes}</div>}
                {o.carriers && (
                  <div className="text-xs text-slate-500 mt-2">Carriers: {o.carriers.join(" · ")}</div>
                )}
              </div>
            ))}
          </div>
        </Card>
      )}
    </>
  );
}

// ============================ I · FREIGHT AUDIT ============================
function FreightAuditTab() {
  const [form, setForm] = useState({ booking_id: "", carrier_invoice_usd: "", invoice_number: "" });
  const [audits, setAudits] = useState([]);
  const fetchAll = async () => { const { data } = await api.get("/tms-competitive/freight-audits"); setAudits(data.items || []); };
  useEffect(() => { fetchAll(); }, []);
  const audit = async () => {
    try {
      const { data } = await api.post("/tms-competitive/freight-audit", { ...form, carrier_invoice_usd: parseFloat(form.carrier_invoice_usd) });
      toast.success(`Verdict ${data.verdict}`); fetchAll();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };
  return (
    <>
      <Card className="hud-surface p-5">
        <h3 className="font-display text-lg font-bold mb-3">Audit carrier invoice</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <F label="Booking ID *" value={form.booking_id} onChange={(v)=>setForm({...form,booking_id:v})} testId="fa-bid"/>
          <F label="Carrier invoice $ *" type="number" value={form.carrier_invoice_usd} onChange={(v)=>setForm({...form,carrier_invoice_usd:v})} testId="fa-inv"/>
          <F label="Invoice number" value={form.invoice_number} onChange={(v)=>setForm({...form,invoice_number:v})} testId="fa-num"/>
        </div>
        <Button onClick={audit} className="bg-cyan-500 hover:bg-cyan-400 text-black mt-3" data-testid="fa-audit">
          <BadgeCheck size={14} className="mr-2"/> Audit
        </Button>
      </Card>
      <Card className="hud-surface p-5">
        <h3 className="font-display text-lg font-bold mb-3">Recent audits · {audits.length}</h3>
        <div className="space-y-2">
          {audits.map((a) => (
            <div key={a.audit_id} className="p-3 rounded border bg-white/[0.02]" style={{borderColor:"rgba(255,255,255,0.06)"}}>
              <div className="flex items-center justify-between flex-wrap gap-2">
                <div>
                  <div className="font-bold">{a.booking_id} · expected ${a.expected_total_usd?.toFixed(2)} · invoice ${a.carrier_invoice_usd?.toFixed(2)}</div>
                  <div className="text-xs text-slate-500 font-mono mt-0.5">
                    {a.audit_id} · diff ${a.diff_usd?.toFixed(2)} · {a.audited_at?.slice(0,10)}
                  </div>
                </div>
                <VerdictPill v={a.verdict}/>
              </div>
              {a.flags?.length > 0 && (
                <div className="mt-2 space-y-1">
                  {a.flags.map((f, i) => (
                    <div key={i} className={`text-xs ${f.level === "red" ? "text-red-300" : "text-amber-300"}`}>⚠ {f.msg}</div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </Card>
    </>
  );
}

// ============================ J · RFP ============================
function RfpTab() {
  const [items, setItems] = useState([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const fetchAll = async () => { const { data } = await api.get("/tms-competitive/rfps"); setItems(data.items || []); };
  useEffect(() => { fetchAll(); }, []);
  return (
    <Card className="hud-surface p-5">
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <h3 className="font-display text-lg font-bold">Active RFPs · {items.length}</h3>
        <div className="flex items-center gap-2">
          <Button size="sm" onClick={() => setDialogOpen(true)}
            className="bg-cyan-500 hover:bg-cyan-400 text-black text-xs h-7"
            data-testid="rfp-create-open">
            <Plus size={12} className="mr-1"/> New RFP
          </Button>
          <a href="/rfp-board" target="_blank" rel="noreferrer"
             className="text-xs text-cyan-300 hover:underline">Public board ↗</a>
        </div>
      </div>
      {items.length === 0 ? <Empty msg="No RFPs published yet."/> : (
        <div className="space-y-2">
          {items.map((r) => (
            <div key={r.rfp_id} className="p-3 rounded border bg-white/[0.02]" style={{borderColor:"rgba(255,255,255,0.06)"}}>
              <div className="flex items-center justify-between flex-wrap gap-2">
                <div>
                  <div className="font-bold">{r.title}</div>
                  <div className="text-xs text-slate-500 font-mono mt-0.5">
                    {r.rfp_id} · {r.shipper_name} · deadline {r.submission_deadline} · {r.lanes?.length} lanes
                  </div>
                </div>
                <span className="text-xs font-mono text-cyan-300">{r.bid_count} bids</span>
              </div>
            </div>
          ))}
        </div>
      )}
      {dialogOpen && <RfpCreateDialog onClose={() => { setDialogOpen(false); fetchAll(); }}/>}
    </Card>
  );
}

function RfpCreateDialog({ onClose }) {
  const [form, setForm] = useState({
    shipper_name: "", title: "", description: "", submission_deadline: "",
    contact_email: "", is_public: true,
  });
  const [lanes, setLanes] = useState([{ origin: "", destination: "", equipment: "Dry Van", est_volume_per_week: 1 }]);
  const [submitting, setSubmitting] = useState(false);

  const addLane = () => setLanes([...lanes, { origin: "", destination: "", equipment: "Dry Van", est_volume_per_week: 1 }]);
  const removeLane = (i) => setLanes(lanes.filter((_, idx) => idx !== i));
  const setLane = (i, k, v) => { const u = [...lanes]; u[i] = { ...u[i], [k]: v }; setLanes(u); };

  const submit = async () => {
    if (!form.shipper_name || !form.title || !form.submission_deadline) return toast.error("Shipper, title, deadline required");
    if (lanes.some((L) => !L.origin || !L.destination)) return toast.error("Every lane needs origin + destination");
    setSubmitting(true);
    try {
      await api.post("/tms-competitive/rfps", {
        ...form, lanes: lanes.map((L) => ({ ...L, est_volume_per_week: parseInt(L.est_volume_per_week, 10) || 1 })),
      });
      toast.success("RFP published");
      onClose();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    finally { setSubmitting(false); }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4"
         onClick={onClose} data-testid="rfp-create-dialog">
      <Card className="hud-surface p-6 max-w-2xl w-full max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <div className="font-bold text-lg mb-4">Publish RFP</div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
          <F label="Shipper name *" value={form.shipper_name} onChange={(v)=>setForm({...form,shipper_name:v})} testId="rfp-shipper"/>
          <F label="Title *" value={form.title} onChange={(v)=>setForm({...form,title:v})} testId="rfp-title"/>
          <F label="Submission deadline *" type="date" value={form.submission_deadline} onChange={(v)=>setForm({...form,submission_deadline:v})} testId="rfp-deadline"/>
          <F label="Contact email" type="email" value={form.contact_email} onChange={(v)=>setForm({...form,contact_email:v})} testId="rfp-contact"/>
          <div className="col-span-2">
            <F label="Description" value={form.description} onChange={(v)=>setForm({...form,description:v})} testId="rfp-desc"/>
          </div>
        </div>
        <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-slate-400 mb-2">Lanes</div>
        <div className="space-y-2 mb-4">
          {lanes.map((L, i) => (
            <div key={i} className="grid grid-cols-12 gap-2 items-end p-2 rounded bg-white/[0.02]">
              <div className="col-span-4"><F label="Origin" value={L.origin} onChange={(v)=>setLane(i,"origin",v)} testId={`rfp-lane-o-${i}`}/></div>
              <div className="col-span-4"><F label="Destination" value={L.destination} onChange={(v)=>setLane(i,"destination",v)} testId={`rfp-lane-d-${i}`}/></div>
              <div className="col-span-2"><F label="Equip" value={L.equipment} onChange={(v)=>setLane(i,"equipment",v)} testId={`rfp-lane-e-${i}`}/></div>
              <div className="col-span-1"><F label="Vol/wk" type="number" value={L.est_volume_per_week} onChange={(v)=>setLane(i,"est_volume_per_week",v)} testId={`rfp-lane-v-${i}`}/></div>
              <div className="col-span-1 flex justify-end">
                {lanes.length > 1 && (
                  <Button size="sm" variant="ghost" onClick={() => removeLane(i)} className="text-red-400 h-7 w-7 p-0">
                    <Trash2 size={12}/>
                  </Button>
                )}
              </div>
            </div>
          ))}
        </div>
        <Button size="sm" variant="ghost" onClick={addLane} className="text-cyan-300 mb-4 text-xs" data-testid="rfp-add-lane">
          <Plus size={12} className="mr-1"/> Add lane
        </Button>
        <div className="flex gap-2 mt-3">
          <Button onClick={submit} disabled={submitting} className="bg-cyan-500 hover:bg-cyan-400 text-black flex-1"
                  data-testid="rfp-create-submit">
            {submitting ? "Publishing…" : "Publish RFP"}
          </Button>
          <Button onClick={onClose} variant="outline" className="border-white/10">Cancel</Button>
        </div>
      </Card>
    </div>
  );
}

// ============================ shared bits ============================
function F({ label, value, onChange, type="text", testId }) {
  return (
    <div>
      <Label className="text-[10px] font-mono uppercase tracking-[0.15em] text-slate-400 mb-1.5 block">{label}</Label>
      <Input type={type} value={value} onChange={(e) => onChange(e.target.value)}
             data-testid={testId} className="bg-[#0B1320] border-white/10 text-white"/>
    </div>
  );
}
function Select({ label, value, onChange, opts, testId }) {
  return (
    <div>
      <Label className="text-[10px] font-mono uppercase tracking-[0.15em] text-slate-400 mb-1.5 block">{label}</Label>
      <select value={value} onChange={(e)=>onChange(e.target.value)}
              className="w-full px-3 py-2 rounded border bg-[#0B1320] text-white text-sm border-white/10"
              data-testid={testId}>
        {opts.map((o)=><option key={o} value={o}>{o}</option>)}
      </select>
    </div>
  );
}
function Pill({ status }) {
  const s = (status || "").toLowerCase();
  const cls = s === "open" || s === "scheduled" ? "bg-cyan-500/15 text-cyan-300 border-cyan-500/30" :
              s === "quoted" || s === "completed" ? "bg-emerald-500/15 text-emerald-300 border-emerald-500/30" :
              s === "cancelled" ? "bg-red-500/15 text-red-300 border-red-500/30" :
              "bg-slate-500/15 text-slate-300 border-slate-500/30";
  return <span className={`px-2 py-0.5 rounded text-[10px] font-mono uppercase tracking-wider border ${cls}`}>{status || "—"}</span>;
}
function VerdictPill({ v }) {
  const cls = v === "GREEN" ? "bg-emerald-500/15 text-emerald-300 border-emerald-500/30" :
              v === "AMBER" ? "bg-amber-500/15 text-amber-300 border-amber-500/30" :
              v === "RED" ? "bg-red-500/15 text-red-300 border-red-500/30" :
              "bg-slate-500/15 text-slate-300 border-slate-500/30";
  return <span className={`px-2 py-0.5 rounded text-[10px] font-mono uppercase tracking-wider border ${cls}`}>{v || "—"}</span>;
}
function Stat({ label, value }) {
  return (
    <div className="p-3 rounded border bg-white/[0.02]" style={{borderColor:"rgba(255,255,255,0.06)"}}>
      <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-slate-400">{label}</div>
      <div className="font-display text-xl font-bold mt-1 text-cyan-300">{value}</div>
    </div>
  );
}
function Empty({ msg }) { return <div className="text-slate-500 text-sm italic py-4 text-center">{msg}</div>; }
