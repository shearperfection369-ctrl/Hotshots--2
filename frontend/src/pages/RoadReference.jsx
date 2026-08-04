import React, { useEffect, useMemo, useState } from "react";
import Topbar from "../components/Topbar";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import { Textarea } from "../components/ui/textarea";
import { Scale, StickyNote, BookOpen, Trash2, Search, MapPin, Route, X } from "lucide-react";
import { toast } from "sonner";
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import MapErrorBoundary from "../components/MapErrorBoundary";

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

function FitToStations({ stations, route }) {
  const map = useMap();
  useEffect(() => {
    if (route?.geometry?.length > 1) { map.fitBounds(L.latLngBounds(route.geometry).pad(0.15)); return; }
    const pts = stations.filter((s) => Number.isFinite(s.lat) && Number.isFinite(s.lng));
    if (pts.length > 1) map.fitBounds(L.latLngBounds(pts.map((s) => [s.lat, s.lng])).pad(0.25));
    else if (pts.length === 1) map.setView([pts[0].lat, pts[0].lng], 7);
    else map.setView([39.5, -98.35], 4);
  }, [stations, route, map]);
  return null;
}

function endpointIcon(color, label) {
  try {
    return L.divIcon({
      className: "",
      html: `<div style="display:flex;flex-direction:column;align-items:center;">
        <div style="width:16px;height:16px;border-radius:9999px;background:${color};border:3px solid #0B0E14;box-shadow:0 0 10px ${color}"></div>
        <div style="font-family:monospace;font-size:9px;font-weight:800;color:${color};text-shadow:0 0 4px #000;white-space:nowrap;">${label}</div>
      </div>`,
      iconSize: [16, 28], iconAnchor: [8, 8],
    });
  } catch { return undefined; }
}

function stationIcon(open) {
  const c = open ? "#F59E0B" : "#34D399";
  try {
    return L.divIcon({
      className: "",
      html: `<div style="width:14px;height:14px;border-radius:9999px;background:${c};border:2px solid #0B0E14;box-shadow:0 0 8px ${c}AA"></div>`,
      iconSize: [14, 14], iconAnchor: [7, 7],
    });
  } catch { return undefined; }
}

function WeighStationMap({ stations, route }) {
  const pts = stations.filter((s) => Number.isFinite(s.lat) && Number.isFinite(s.lng));
  return (
    <div className="rounded-xl overflow-hidden border border-white/10 mb-4" style={{ height: 420 }} data-testid="weigh-stations-map">
      <MapErrorBoundary>
        <MapContainer center={[39.5, -98.35]} zoom={4} style={{ height: "100%", width: "100%", background: "#0B0E14" }} scrollWheelZoom>
          <TileLayer
            attribution='© OpenStreetMap contributors © CARTO'
            url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          />
          <FitToStations stations={pts} route={route} />
          {route?.geometry?.length > 1 && (
            <>
              <Polyline positions={route.geometry} pathOptions={{ color: "#22D3EE", weight: 3, opacity: 0.85 }} />
              <Marker position={[route.origin.lat, route.origin.lng]} icon={endpointIcon("#22D3EE", "PICKUP")}>
                <Popup><div style={{ fontFamily: "monospace", fontSize: 12 }}>{route.origin.label}</div></Popup>
              </Marker>
              <Marker position={[route.destination.lat, route.destination.lng]} icon={endpointIcon("#F472B6", "DROP")}>
                <Popup><div style={{ fontFamily: "monospace", fontSize: 12 }}>{route.destination.label}</div></Popup>
              </Marker>
            </>
          )}
          {pts.map((s) => (
            <Marker key={`${s.state}-${s.name}`} position={[s.lat, s.lng]} icon={stationIcon(s.likely_open)}>
              <Popup>
                <div style={{ fontFamily: "monospace", fontSize: 12, minWidth: 190 }}>
                  <div style={{ fontWeight: 800 }}>{s.name} · {s.state}</div>
                  <div style={{ color: "#475569" }}>{s.hwy}</div>
                  <div style={{ color: s.likely_open ? "#B45309" : "#047857", fontWeight: 700, margin: "4px 0" }}>
                    {s.likely_open ? "LIKELY OPEN" : "LIKELY CLOSED"}{Number.isFinite(s.off_route_mi) ? ` · ${s.off_route_mi} mi off-route` : ""}
                  </div>
                  <div style={{ fontFamily: "inherit" }}>{s.advice}</div>
                </div>
              </Popup>
            </Marker>
          ))}
        </MapContainer>
      </MapErrorBoundary>
    </div>
  );
}

function WeighStationsTab() {
  const [stations, setStations] = useState([]);
  const [hourCt, setHourCt] = useState(null);
  const [state, setState] = useState("");
  const [loads, setLoads] = useState([]);
  const [loadId, setLoadId] = useState("");
  const [manual, setManual] = useState({ origin: "", destination: "" });
  const [route, setRoute] = useState(null);
  const [scanning, setScanning] = useState(false);
  const load = (st) => {
    api.get(`/reference/weigh-stations${st ? `?state=${st}` : ""}`)
      .then(({ data }) => { setStations(data.stations || []); setHourCt(data.hour_ct); })
      .catch(() => toast.error("Failed to load weigh stations"));
  };
  useEffect(() => { load(state); }, [state]);
  useEffect(() => { api.get("/reference/active-loads").then(({ data }) => setLoads(data.loads || [])).catch(() => {}); }, []);
  const scan = async () => {
    if (!loadId && (!manual.origin || !manual.destination)) {
      toast.error("Pick an active load or enter origin & destination"); return;
    }
    setScanning(true);
    try {
      const { data } = await api.post("/reference/weigh-stations/load-route",
        loadId ? { load_id: loadId } : { origin: manual.origin, destination: manual.destination });
      setRoute(data);
      setHourCt(data.hour_ct);
      toast.success(`${data.stations.length} station(s) on this route · ${data.likely_open_count} likely open`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Route scan failed");
    } finally { setScanning(false); }
  };
  const clearRoute = () => { setRoute(null); setLoadId(""); setManual({ origin: "", destination: "" }); };
  const shown = route ? route.stations : stations;
  const states = useMemo(() => [...new Set(shown.map((s) => s.state))].sort(), [shown]);
  return (
    <Card className="hud-surface p-5" data-testid="weigh-stations-panel">
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <div>
          <h3 className="font-display text-base font-bold text-white">Fixed Weigh & Inspection Stations</h3>
          <div className="text-[11px] text-slate-500">Open/closed advice is estimated for the current hour ({hourCt !== null ? `${String(hourCt).padStart(2, "0")}:00 CT` : "…"}) — ramp signage always rules.</div>
        </div>
        {!route && (
          <Input value={state} onChange={(e) => setState(e.target.value.toUpperCase().slice(0, 2))}
            placeholder="Filter by state (e.g. MN)" className="w-48 bg-[#11151F] border-white/10 font-mono uppercase" data-testid="weigh-state-filter" />
        )}
      </div>

      <div className="p-3 rounded-lg border border-cyan-500/20 bg-cyan-500/[0.04] mb-4" data-testid="route-scan-panel">
        <div className="flex items-center gap-2 mb-2">
          <Route size={14} className="text-cyan-300" />
          <span className="text-xs font-mono uppercase tracking-widest text-cyan-300">Scan Weigh Stations Along A Load Route</span>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select value={loadId} onChange={(e) => { setLoadId(e.target.value); if (e.target.value) setManual({ origin: "", destination: "" }); }}
            className="h-9 px-2 rounded-md bg-[#11151F] border border-white/10 text-xs text-slate-200 font-mono min-w-[260px]" data-testid="route-scan-load-select">
            <option value="">— Pick an active load ({loads.length} booked) —</option>
            {loads.map((l) => (
              <option key={l.booked_id} value={l.booked_id}>
                {l.reference || l.booked_id} · {l.origin} → {l.destination}{l.carrier_name ? ` · ${l.carrier_name}` : ""}
              </option>
            ))}
          </select>
          <span className="text-[10px] font-mono text-slate-600">OR</span>
          <Input value={manual.origin} onChange={(e) => { setManual({ ...manual, origin: e.target.value }); if (e.target.value) setLoadId(""); }}
            placeholder="Origin (Minneapolis, MN)" className="w-52 h-9 bg-[#11151F] border-white/10 text-xs" data-testid="route-scan-origin" />
          <Input value={manual.destination} onChange={(e) => { setManual({ ...manual, destination: e.target.value }); if (e.target.value) setLoadId(""); }}
            placeholder="Destination (Dallas, TX)" className="w-52 h-9 bg-[#11151F] border-white/10 text-xs" data-testid="route-scan-destination" />
          <Button onClick={scan} disabled={scanning} className="h-9 bg-cyan-500 hover:bg-cyan-400 text-black font-bold text-xs" data-testid="route-scan-btn">
            {scanning ? "Scanning…" : "Scan Route"}
          </Button>
          {route && (
            <Button onClick={clearRoute} variant="ghost" className="h-9 text-slate-400 hover:text-white text-xs" data-testid="route-scan-clear-btn">
              <X size={13} className="mr-1" /> Clear
            </Button>
          )}
        </div>
        {route && (
          <div className="mt-3 p-3 rounded border border-amber-500/25 bg-amber-500/[0.05] text-xs text-amber-200/90 leading-relaxed" data-testid="route-scan-summary">
            {route.ai_summary}
            <span className="block mt-1 text-[10px] font-mono text-slate-500 uppercase">
              route via {route.route_provider}{route.distance_mi ? ` · ${route.distance_mi.toLocaleString()} mi` : ""} · corridor ±20 mi
            </span>
          </div>
        )}
      </div>

      <WeighStationMap stations={shown} route={route} />
      <div className="flex items-center gap-4 mb-3 text-[10px] font-mono text-slate-500">
        <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full inline-block" style={{ background: "#F59E0B" }} /> LIKELY OPEN NOW</span>
        <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full inline-block" style={{ background: "#34D399" }} /> LIKELY CLOSED NOW</span>
        <span className="text-slate-600">click a pin for advice</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-left text-[10px] font-mono uppercase tracking-widest text-slate-500 border-b border-white/10">
              <th className="py-2 pr-3">State</th><th className="py-2 pr-3">Station</th><th className="py-2 pr-3">Highway</th>
              {route && <th className="py-2 pr-3">Off-Route</th>}
              <th className="py-2 pr-3">Status Now</th><th className="py-2">Advice</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((s) => (
              <tr key={`${s.state}-${s.name}`} className="border-b border-white/5 hover:bg-white/[0.02]">
                <td className="py-2 pr-3 font-mono text-cyan-300">{s.state}</td>
                <td className="py-2 pr-3 text-slate-100 whitespace-nowrap"><MapPin size={11} className="inline mr-1 text-slate-500" />{s.name}</td>
                <td className="py-2 pr-3 font-mono text-slate-400">{s.hwy}</td>
                {route && <td className="py-2 pr-3 font-mono text-slate-400">{Number.isFinite(s.off_route_mi) ? `${s.off_route_mi} mi` : "—"}</td>}
                <td className="py-2 pr-3">
                  <Badge className={s.likely_open ? "bg-amber-500/15 text-amber-300 border-amber-500/30" : "bg-emerald-500/15 text-emerald-300 border-emerald-500/30"}>
                    {s.likely_open ? "LIKELY OPEN" : "LIKELY CLOSED"}
                  </Badge>
                </td>
                <td className="py-2 text-slate-400 max-w-md">{s.advice}</td>
              </tr>
            ))}
            {!shown.length && <tr><td colSpan={6} className="py-8 text-center text-slate-500">{route ? "No fixed weigh stations within 20 miles of this route." : "No stations for that state filter."}</td></tr>}
          </tbody>
        </table>
      </div>
      {states.length > 1 && <div className="mt-3 text-[10px] font-mono text-slate-600">{shown.length} stations · {states.length} states covered</div>}
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
