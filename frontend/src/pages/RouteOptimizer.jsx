import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Topbar from "../components/Topbar";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Input } from "../components/ui/input";
import { MapContainer, TileLayer, Marker, Polyline, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import {
  Route as RouteIcon, MapPin, Navigation, Fuel, DollarSign, Loader2,
  Save, Trash2, History, Gauge, Clock, TrendingUp,
} from "lucide-react";
import { toast } from "sonner";
import { api } from "../lib/api";

const pinIcon = (color) => L.divIcon({
  className: "",
  html: `<div style="width:16px;height:16px;border-radius:50%;background:${color};border:3px solid #0B0E14;box-shadow:0 0 10px ${color}"></div>`,
  iconSize: [16, 16], iconAnchor: [8, 8],
});
const ORIGIN_ICON = pinIcon("#34D399");
const DEST_ICON = pinIcon("#F87171");

const VERDICT_STYLE = {
  GO: "bg-emerald-500/15 text-emerald-300 border-emerald-500/50",
  CAUTION: "bg-amber-500/15 text-amber-300 border-amber-500/50",
  "NO-GO": "bg-red-500/15 text-red-300 border-red-500/50",
};

const money = (v) => (v == null ? "—" : `$${Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`);

function FitRoute({ geometry }) {
  const map = useMap();
  useEffect(() => {
    if (geometry?.length > 1) {
      map.fitBounds(L.latLngBounds(geometry), { padding: [40, 40] });
    }
  }, [geometry, map]);
  return null;
}

function GeocodeInput({ label, color, value, onSelect, testId }) {
  const [q, setQ] = useState("");
  const [cands, setCands] = useState([]);
  const [busy, setBusy] = useState(false);
  const boxRef = useRef(null);

  useEffect(() => {
    const close = (e) => { if (boxRef.current && !boxRef.current.contains(e.target)) setCands([]); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  const search = async () => {
    if (q.trim().length < 2) return;
    setBusy(true);
    try {
      const r = await api.get(`/route-optimizer/geocode?q=${encodeURIComponent(q)}`);
      setCands(r.data.candidates || []);
      if ((r.data.candidates || []).length === 0) toast.info("No matches — try 'City, ST'");
    } catch (_) {
      toast.error("Geocoder unavailable — try again");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div ref={boxRef} className="relative">
      <div className="text-[10px] font-mono uppercase tracking-widest text-slate-400 mb-1 flex items-center gap-1.5">
        <MapPin size={11} style={{ color }} /> {label}
      </div>
      {value ? (
        <div className="flex items-center gap-2 p-2 rounded-md border border-white/10 bg-white/[0.03]" data-testid={`${testId}-selected`}>
          <span className="flex-1 text-xs text-white truncate" title={value.label}>{value.label}</span>
          <button onClick={() => { onSelect(null); setQ(""); }} className="text-[10px] font-mono text-slate-500 hover:text-red-400" data-testid={`${testId}-clear`}>CLEAR</button>
        </div>
      ) : (
        <div className="flex gap-2">
          <Input value={q} onChange={(e) => setQ(e.target.value)}
                 onKeyDown={(e) => e.key === "Enter" && search()}
                 placeholder="City, ST or full address" data-testid={`${testId}-input`}
                 className="bg-white/[0.03] border-white/10 text-white placeholder:text-slate-600 h-9 text-sm" />
          <Button onClick={search} disabled={busy} size="sm" variant="outline" data-testid={`${testId}-search-btn`}
                  className="bg-slate-900 border-white/10 h-9 shrink-0">
            {busy ? <Loader2 size={13} className="animate-spin" /> : "Find"}
          </Button>
        </div>
      )}
      {cands.length > 0 && (
        <div className="absolute z-[1000] mt-1 w-full rounded-md border border-white/10 bg-[#0E1420] shadow-2xl max-h-52 overflow-y-auto" data-testid={`${testId}-candidates`}>
          {cands.map((c, i) => (
            <button key={i} onClick={() => { onSelect(c); setCands([]); }}
                    data-testid={`${testId}-candidate-${i}`}
                    className="block w-full text-left px-3 py-2 text-xs text-slate-300 hover:bg-cyan-500/10 hover:text-cyan-200 border-b border-white/5 last:border-0">
              {c.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default function RouteOptimizer() {
  const [origin, setOrigin] = useState(null);
  const [dest, setDest] = useState(null);
  const [routing, setRouting] = useState(false);
  const [route, setRoute] = useState(null); // {miles, drive_hours, geometry}
  const [inputs, setInputs] = useState({ rate: "", fuel_price: "3.75", mpg: "6.5", driver_pay_cpm: "0.65", tolls: "0" });
  const [history, setHistory] = useState([]);
  const [saving, setSaving] = useState(false);

  const loadHistory = useCallback(async () => {
    try { const r = await api.get("/route-optimizer/loads"); setHistory(r.data.loads || []); } catch (_) {}
  }, []);
  useEffect(() => { loadHistory(); }, [loadHistory]);

  const runRoute = async () => {
    if (!origin || !dest) { toast.error("Pick an origin and destination first"); return; }
    setRouting(true);
    setRoute(null);
    try {
      const r = await api.post("/route-optimizer/route", { origin, dest });
      setRoute(r.data);
      toast.success(`Route locked: ${r.data.miles} mi · ${r.data.drive_hours} h drive`);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Routing failed");
    } finally {
      setRouting(false);
    }
  };

  // Live margin math (mirrors backend compute_margin)
  const calc = useMemo(() => {
    const miles = route?.miles || 0;
    const rate = parseFloat(inputs.rate) || 0;
    const fuel = parseFloat(inputs.fuel_price) || 0;
    const mpg = parseFloat(inputs.mpg) || 0;
    const cpm = parseFloat(inputs.driver_pay_cpm) || 0;
    const tolls = parseFloat(inputs.tolls) || 0;
    if (!miles || !rate || !mpg) return null;
    const fuel_cost = (miles / mpg) * fuel;
    const driver_cost = miles * cpm;
    const total_cost = fuel_cost + driver_cost + tolls;
    const net = rate - total_cost;
    const rpm = rate / miles;
    const margin_pct = rate ? (net / rate) * 100 : 0;
    let verdict = "NO-GO";
    if (net > 0) verdict = rpm >= 2.0 && margin_pct >= 15 ? "GO" : "CAUTION";
    return { fuel_cost, driver_cost, tolls, total_cost, net, rpm, margin_pct, verdict };
  }, [route, inputs]);

  const saveLoad = async () => {
    if (!route || !calc) { toast.error("Run a route and enter a rate first"); return; }
    setSaving(true);
    try {
      await api.post("/route-optimizer/loads", {
        origin, dest, miles: route.miles, drive_hours: route.drive_hours,
        inputs: {
          rate: parseFloat(inputs.rate) || 0,
          fuel_price: parseFloat(inputs.fuel_price) || 0,
          mpg: parseFloat(inputs.mpg) || 1,
          driver_pay_cpm: parseFloat(inputs.driver_pay_cpm) || 0,
          tolls: parseFloat(inputs.tolls) || 0,
        },
      });
      toast.success("Load saved to history");
      loadHistory();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const deleteLoad = async (id) => {
    try { await api.delete(`/route-optimizer/loads/${id}`); loadHistory(); toast.success("Deleted"); }
    catch (err) { toast.error(err.response?.data?.detail || "Delete failed"); }
  };

  const numField = (key, label, icon, step = "0.01") => (
    <div>
      <div className="text-[10px] font-mono uppercase tracking-widest text-slate-400 mb-1 flex items-center gap-1">{icon} {label}</div>
      <Input type="number" step={step} min="0" value={inputs[key]}
             onChange={(e) => setInputs({ ...inputs, [key]: e.target.value })}
             data-testid={`ro-${key}-input`}
             className="bg-white/[0.03] border-white/10 text-white h-9 text-sm font-mono" />
    </div>
  );

  const short = (label) => (label || "").split(",").slice(0, 2).join(",");

  return (
    <>
      <Topbar title="Route Optimizer" subtitle="Real road routing (OSRM · OpenStreetMap) · live map · full margin calculator · GO/NO-GO" />
      <div className="p-4 md:p-6 grid grid-cols-1 xl:grid-cols-5 gap-5" data-testid="route-optimizer-page">
        {/* Left column — controls */}
        <div className="xl:col-span-2 space-y-4">
          <Card className="p-4 bg-slate-950/60 border-white/10 space-y-3" data-testid="ro-route-card">
            <div className="text-xs font-mono uppercase tracking-widest text-cyan-300 flex items-center gap-2">
              <RouteIcon size={13} /> Lane
            </div>
            <GeocodeInput label="Origin" color="#34D399" value={origin} onSelect={setOrigin} testId="ro-origin" />
            <GeocodeInput label="Destination" color="#F87171" value={dest} onSelect={setDest} testId="ro-dest" />
            <Button onClick={runRoute} disabled={routing || !origin || !dest} data-testid="ro-route-btn"
                    className="w-full bg-cyan-500 hover:bg-cyan-400 text-black font-bold">
              {routing ? <Loader2 size={14} className="mr-2 animate-spin" /> : <Navigation size={14} className="mr-2" />}
              Route it
            </Button>
            {route && (
              <div className="grid grid-cols-2 gap-2 pt-1" data-testid="ro-route-stats">
                <div className="p-2.5 rounded-md bg-cyan-500/10 border border-cyan-500/30">
                  <div className="text-[9px] font-mono uppercase text-cyan-400">Road miles</div>
                  <div className="text-lg font-mono font-bold text-cyan-200" data-testid="ro-miles">{route.miles.toLocaleString()}</div>
                </div>
                <div className="p-2.5 rounded-md bg-cyan-500/10 border border-cyan-500/30">
                  <div className="text-[9px] font-mono uppercase text-cyan-400 flex items-center gap-1"><Clock size={9} /> Drive time</div>
                  <div className="text-lg font-mono font-bold text-cyan-200">{route.drive_hours} h</div>
                </div>
              </div>
            )}
          </Card>

          <Card className="p-4 bg-slate-950/60 border-white/10 space-y-3" data-testid="ro-margin-card">
            <div className="text-xs font-mono uppercase tracking-widest text-amber-300 flex items-center gap-2">
              <DollarSign size={13} /> Margin calculator
            </div>
            <div className="grid grid-cols-2 gap-3">
              {numField("rate", "Line-haul rate ($)", <DollarSign size={10} />, "1")}
              {numField("fuel_price", "Fuel ($/gal)", <Fuel size={10} />)}
              {numField("mpg", "Truck MPG", <Gauge size={10} />, "0.1")}
              {numField("driver_pay_cpm", "Driver pay ($/mi)", <DollarSign size={10} />)}
              {numField("tolls", "Tolls ($)", <DollarSign size={10} />, "1")}
            </div>

            {calc ? (
              <div className="space-y-2 pt-1" data-testid="ro-results">
                <div className={`flex items-center justify-between p-3 rounded-md border-2 ${VERDICT_STYLE[calc.verdict]}`}>
                  <div>
                    <div className="text-[9px] font-mono uppercase tracking-widest opacity-80">Verdict</div>
                    <div className="text-2xl font-display font-black tracking-tight" data-testid="ro-verdict">{calc.verdict}</div>
                  </div>
                  <div className="text-right">
                    <div className="text-[9px] font-mono uppercase tracking-widest opacity-80">Net profit</div>
                    <div className="text-2xl font-mono font-bold" data-testid="ro-net-profit">{money(calc.net)}</div>
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-2 text-center">
                  <div className="p-2 rounded bg-white/[0.03] border border-white/10">
                    <div className="text-[9px] font-mono uppercase text-slate-500">Rate / mile</div>
                    <div className="text-sm font-mono font-bold text-white" data-testid="ro-rpm">${calc.rpm.toFixed(2)}</div>
                  </div>
                  <div className="p-2 rounded bg-white/[0.03] border border-white/10">
                    <div className="text-[9px] font-mono uppercase text-slate-500">Margin</div>
                    <div className="text-sm font-mono font-bold text-white">{calc.margin_pct.toFixed(1)}%</div>
                  </div>
                  <div className="p-2 rounded bg-white/[0.03] border border-white/10">
                    <div className="text-[9px] font-mono uppercase text-slate-500">Total cost</div>
                    <div className="text-sm font-mono font-bold text-white">{money(calc.total_cost)}</div>
                  </div>
                </div>
                <div className="text-[11px] font-mono text-slate-400 flex flex-wrap gap-x-4 gap-y-1">
                  <span>Fuel {money(calc.fuel_cost)}</span>
                  <span>Driver {money(calc.driver_cost)}</span>
                  <span>Tolls {money(calc.tolls)}</span>
                </div>
                <Button onClick={saveLoad} disabled={saving} data-testid="ro-save-btn"
                        className="w-full bg-amber-500 hover:bg-amber-400 text-black font-semibold">
                  {saving ? <Loader2 size={14} className="mr-2 animate-spin" /> : <Save size={14} className="mr-2" />}
                  Save load to history
                </Button>
              </div>
            ) : (
              <div className="text-[11px] text-slate-500 font-mono pt-1">
                Route the lane and enter a rate — profit, RPM and the GO/NO-GO verdict compute live.
              </div>
            )}
          </Card>
        </div>

        {/* Right column — map + history */}
        <div className="xl:col-span-3 space-y-4">
          <Card className="overflow-hidden bg-slate-950/60 border-white/10" data-testid="ro-map-card">
            <div className="h-[420px]">
              <MapContainer center={[41.5, -95.0]} zoom={4} className="h-full w-full" style={{ background: "#0B0E14" }}>
                <TileLayer
                  url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
                  attribution='&copy; OpenStreetMap &copy; CARTO'
                />
                {origin && <Marker position={[origin.lat, origin.lon]} icon={ORIGIN_ICON} />}
                {dest && <Marker position={[dest.lat, dest.lon]} icon={DEST_ICON} />}
                {route?.geometry?.length > 1 && (
                  <>
                    <Polyline positions={route.geometry} pathOptions={{ color: "#00E5FF", weight: 4, opacity: 0.9 }} />
                    <Polyline positions={route.geometry} pathOptions={{ color: "#00E5FF", weight: 10, opacity: 0.15 }} />
                    <FitRoute geometry={route.geometry} />
                  </>
                )}
              </MapContainer>
            </div>
          </Card>

          <Card className="p-4 bg-slate-950/60 border-white/10" data-testid="ro-history-card">
            <div className="text-xs font-mono uppercase tracking-widest text-cyan-300 flex items-center gap-2 mb-3">
              <History size={13} /> Saved load history
              <Badge className="bg-cyan-500/15 text-cyan-300 border-cyan-500/40 text-[10px]">{history.length}</Badge>
            </div>
            {history.length === 0 ? (
              <div className="text-sm text-slate-500 py-4 text-center">No saved loads yet — run a lane and save it.</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-[10px] font-mono uppercase tracking-wider text-slate-500 border-b border-white/5">
                      <th className="py-2 pr-3">Lane</th><th className="py-2 pr-3">Miles</th>
                      <th className="py-2 pr-3">Rate</th><th className="py-2 pr-3">Net</th>
                      <th className="py-2 pr-3">RPM</th><th className="py-2 pr-3">Verdict</th>
                      <th className="py-2 pr-3">When</th><th className="py-2" />
                    </tr>
                  </thead>
                  <tbody>
                    {history.map((l) => (
                      <tr key={l.load_id} className="border-b border-white/5" data-testid={`ro-load-${l.load_id}`}>
                        <td className="py-2 pr-3">
                          <div className="text-white text-xs">{short(l.origin.label)}</div>
                          <div className="text-slate-500 text-[10px] flex items-center gap-1"><TrendingUp size={9} /> {short(l.dest.label)}</div>
                        </td>
                        <td className="py-2 pr-3 font-mono text-slate-300">{l.miles.toLocaleString()}</td>
                        <td className="py-2 pr-3 font-mono text-slate-300">{money(l.inputs.rate)}</td>
                        <td className={`py-2 pr-3 font-mono font-bold ${l.results.net_profit > 0 ? "text-emerald-300" : "text-red-300"}`}>{money(l.results.net_profit)}</td>
                        <td className="py-2 pr-3 font-mono text-slate-300">${l.results.rpm.toFixed(2)}</td>
                        <td className="py-2 pr-3"><Badge className={`${VERDICT_STYLE[l.results.verdict]} font-mono text-[9px]`}>{l.results.verdict}</Badge></td>
                        <td className="py-2 pr-3 text-[10px] text-slate-500 font-mono">{new Date(l.created_at).toLocaleDateString([], { month: "short", day: "numeric" })}</td>
                        <td className="py-2 text-right">
                          <button onClick={() => deleteLoad(l.load_id)} data-testid={`ro-load-delete-${l.load_id}`}
                                  className="p-1.5 rounded text-slate-500 hover:text-red-400 hover:bg-red-500/10">
                            <Trash2 size={13} />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>
      </div>
    </>
  );
}
