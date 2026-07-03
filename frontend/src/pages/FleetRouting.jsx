import React, { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import {
  Truck, MapPin, Route as RouteIcon, ShieldAlert, Radar, Loader2,
  Satellite, Clock, Gauge, AlertTriangle, Navigation, CheckCircle2, PlugZap,
} from "lucide-react";
import { toast } from "sonner";

/**
 * FleetRouting — combined Live Fleet Telematics (Samsara) + On-Demand Route
 * Compute (Mapbox / OSRM). Both surfaces work in "sample" mode when the
 * upstream API key is not configured, and light up automatically when it is.
 */
export default function FleetRouting() {
  const [tab, setTab] = useState("fleet");

  return (
    <div className="p-4 space-y-4 min-h-screen bg-slate-950" data-testid="fleet-routing-root">
      <header className="flex items-end justify-between border-b border-white/10 pb-3">
        <div>
          <h1 className="text-2xl font-mono tracking-widest text-cyan-100 uppercase flex items-center gap-2">
            <Satellite size={20} className="text-cyan-400" /> Fleet · Routing Console
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Samsara telematics · Mapbox/OSRM driving directions · degrades gracefully when keys aren&apos;t wired.
          </p>
        </div>
        <div className="flex gap-2">
          {[
            { id: "fleet",    label: "Live Fleet",    icon: Truck },
            { id: "routing",  label: "Route Compute", icon: RouteIcon },
            { id: "safety",   label: "Safety Events", icon: ShieldAlert },
            { id: "hos",      label: "HOS Logs",      icon: Clock },
          ].map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              data-testid={`fleet-routing-tab-${id}`}
              className={`inline-flex items-center gap-2 px-3 py-2 rounded text-[11px] font-mono uppercase tracking-widest border transition ${
                tab === id
                  ? "bg-cyan-500/15 border-cyan-400 text-cyan-100 shadow-[0_0_18px_rgba(34,211,238,0.25)]"
                  : "border-white/10 text-slate-400 hover:border-cyan-400/40 hover:text-cyan-100"
              }`}
            >
              <Icon size={13} /> {label}
            </button>
          ))}
        </div>
      </header>

      {tab === "fleet"   && <FleetView />}
      {tab === "routing" && <RoutingView />}
      {tab === "safety"  && <SafetyView />}
      {tab === "hos"     && <HosView />}
    </div>
  );
}

// ============================================================
//                     FLEET (Samsara vehicles + locations)
// ============================================================
function FleetView() {
  const [provider, setProvider] = useState(null);
  const [locs, setLocs] = useState([]);
  const [busy, setBusy] = useState(false);
  const [token, setToken] = useState("");
  const [connecting, setConnecting] = useState(false);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      const [p, l] = await Promise.all([
        api.get("/telematics/provider"),
        api.get("/telematics/vehicles/locations"),
      ]);
      setProvider(p.data);
      setLocs(l.data.items || []);
    } catch (e) {
      toast.error("Failed to load fleet");
    } finally { setBusy(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const connect = async () => {
    if (token.trim().length < 10) { toast.error("Samsara token looks too short"); return; }
    setConnecting(true);
    try {
      await api.post("/telematics/connect", { api_token: token.trim() });
      toast.success("Samsara connected · switching to LIVE data");
      setToken("");
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to connect Samsara");
    } finally { setConnecting(false); }
  };

  return (
    <div className="space-y-3">
      <ProviderBanner provider={provider} />

      {provider && !provider.connected && (
        <Card className="p-3 bg-amber-500/5 border-amber-500/30" data-testid="fleet-connect-card">
          <div className="flex items-center gap-3">
            <PlugZap size={16} className="text-amber-400" />
            <div className="flex-1 text-xs text-amber-100">
              <b className="text-amber-300 font-mono uppercase text-[10px] tracking-widest">Sample mode</b>
              <span className="text-slate-400 ml-2">Paste your Samsara API token to switch to live vehicle telemetry.</span>
            </div>
            <Input
              type="password"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="samsara_api_token…"
              className="max-w-[260px] bg-black/40 border-white/10 h-8 text-xs"
              data-testid="fleet-samsara-token-input"
            />
            <Button size="sm" onClick={connect} disabled={connecting}
              className="bg-amber-500 hover:bg-amber-400 text-black"
              data-testid="fleet-samsara-connect-btn">
              {connecting ? <Loader2 size={12} className="animate-spin mr-1" /> : <PlugZap size={12} className="mr-1" />}
              Connect
            </Button>
          </div>
        </Card>
      )}

      <Card className="p-0 bg-slate-900/60 border-white/10 overflow-hidden">
        <div className="px-3 py-2 border-b border-white/10 flex items-center justify-between">
          <span className="text-[10px] font-mono uppercase tracking-widest text-cyan-300">
            <Radar size={12} className="inline mr-1" />
            {locs.length} vehicles · {provider?.mode === "live" ? "LIVE Samsara feed" : "SAMPLE data"}
          </span>
          <Button size="sm" variant="ghost" onClick={load} disabled={busy}
            className="text-cyan-300 hover:text-cyan-100 h-7 px-2" data-testid="fleet-refresh">
            {busy ? <Loader2 size={12} className="animate-spin" /> : "Refresh"}
          </Button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs" data-testid="fleet-vehicles-table">
            <thead className="bg-black/40 text-slate-400 font-mono uppercase tracking-wider">
              <tr>
                <th className="px-3 py-2 text-left">Vehicle</th>
                <th className="px-3 py-2 text-left">Near</th>
                <th className="px-3 py-2 text-right">Lat / Lng</th>
                <th className="px-3 py-2 text-right">Speed</th>
                <th className="px-3 py-2 text-right">Heading</th>
                <th className="px-3 py-2 text-left">Last Ping</th>
              </tr>
            </thead>
            <tbody>
              {locs.map((v) => (
                <tr key={v.vehicle_id} className="border-t border-white/5 hover:bg-white/[0.02]"
                  data-testid={`fleet-row-${v.vehicle_id}`}>
                  <td className="px-3 py-2 text-slate-100 font-mono">{v.name || v.vehicle_id}</td>
                  <td className="px-3 py-2 text-slate-300">{v.near_city || "—"}</td>
                  <td className="px-3 py-2 text-right text-slate-400 font-mono">
                    {v.lat?.toFixed?.(3)}, {v.lng?.toFixed?.(3)}
                  </td>
                  <td className="px-3 py-2 text-right font-mono">
                    <Badge variant={v.speed_mph > 0 ? "default" : "outline"}
                      className={v.speed_mph > 0 ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/40" : "text-slate-500"}>
                      {v.speed_mph || 0} mph
                    </Badge>
                  </td>
                  <td className="px-3 py-2 text-right text-slate-400 font-mono">{v.heading_deg}°</td>
                  <td className="px-3 py-2 text-slate-500 font-mono text-[10px]">
                    {v.ts?.slice(11, 19) || "—"}
                  </td>
                </tr>
              ))}
              {!locs.length && !busy && (
                <tr><td colSpan={6} className="p-8 text-center text-slate-500 text-xs">No vehicles reporting.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

// ============================================================
//                    ROUTING (Mapbox / OSRM)
// ============================================================
function RoutingView() {
  const [provider, setProvider] = useState(null);
  const [form, setForm] = useState({ origin: "", destination: "" });
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [recent, setRecent] = useState([]);

  const loadProvider = useCallback(async () => {
    try {
      const { data } = await api.get("/routing/provider");
      setProvider(data);
    } catch (e) { /* no-op */ }
  }, []);
  const loadRecent = useCallback(async () => {
    try {
      const { data } = await api.get("/routing/recent");
      setRecent(data.items || []);
    } catch (e) { /* no-op */ }
  }, []);
  useEffect(() => { loadProvider(); loadRecent(); }, [loadProvider, loadRecent]);

  const compute = async () => {
    if (!form.origin.trim() || !form.destination.trim()) {
      toast.error("Enter both origin and destination"); return;
    }
    setBusy(true); setResult(null);
    try {
      const { data } = await api.post("/routing/route", {
        origin_address: form.origin.trim(),
        destination_address: form.destination.trim(),
      });
      setResult(data);
      loadRecent();
      toast.success(`Route via ${data.provider} · ${data.distance_mi} mi`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Route compute failed");
    } finally { setBusy(false); }
  };

  return (
    <div className="space-y-3">
      <ProviderBanner provider={
        provider ? {
          mode: provider.mapbox_enabled ? "live" : "sample",
          connected: provider.mapbox_enabled,
          provider: provider.primary,
          hint: provider.mapbox_enabled
            ? null
            : "Using free OSRM public instance. Set MAPBOX_TOKEN for traffic-aware directions.",
        } : null
      } label="Router" />

      <Card className="p-4 bg-slate-900/60 border-white/10">
        <div className="grid md:grid-cols-3 gap-3 items-end">
          <div>
            <div className="text-[10px] font-mono uppercase tracking-widest text-cyan-300 mb-1">Origin</div>
            <Input value={form.origin} onChange={(e) => setForm({ ...form, origin: e.target.value })}
              placeholder="Los Angeles, CA · or 34.05,-118.24"
              className="bg-black/40 border-white/10 text-xs h-9"
              data-testid="routing-origin-input" />
          </div>
          <div>
            <div className="text-[10px] font-mono uppercase tracking-widest text-cyan-300 mb-1">Destination</div>
            <Input value={form.destination} onChange={(e) => setForm({ ...form, destination: e.target.value })}
              placeholder="Phoenix, AZ · or 33.45,-112.07"
              className="bg-black/40 border-white/10 text-xs h-9"
              data-testid="routing-destination-input" />
          </div>
          <Button onClick={compute} disabled={busy} className="bg-cyan-500 hover:bg-cyan-400 text-black h-9"
            data-testid="routing-compute-btn">
            {busy ? <Loader2 size={13} className="animate-spin mr-1" /> : <Navigation size={13} className="mr-1" />}
            Compute Route
          </Button>
        </div>

        {result && (
          <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-2" data-testid="routing-result-card">
            <ResultTile label="Provider"   value={result.provider} color="#22D3EE" icon={Satellite} />
            <ResultTile label="Distance"   value={`${result.distance_mi} mi`} color="#10B981" icon={RouteIcon} />
            <ResultTile label="Drive Time" value={`${result.duration_hr} hr`} color="#F59E0B" icon={Clock} />
            <ResultTile label="Avg Speed" value={`${result.duration_hr > 0 ? (result.distance_mi / result.duration_hr).toFixed(0) : 0} mph`} color="#A78BFA" icon={Gauge} />
          </div>
        )}
      </Card>

      {recent.length > 0 && (
        <Card className="p-0 bg-slate-900/60 border-white/10 overflow-hidden">
          <div className="px-3 py-2 border-b border-white/10 text-[10px] font-mono uppercase tracking-widest text-cyan-300">
            <Clock size={12} className="inline mr-1" /> Recent lookups
          </div>
          <table className="w-full text-xs" data-testid="routing-recent-table">
            <thead className="bg-black/40 text-slate-500 font-mono uppercase tracking-wider">
              <tr>
                <th className="px-3 py-2 text-left">When</th>
                <th className="px-3 py-2 text-left">Origin → Dest</th>
                <th className="px-3 py-2 text-right">Distance</th>
                <th className="px-3 py-2 text-right">Duration</th>
                <th className="px-3 py-2 text-left">Provider</th>
              </tr>
            </thead>
            <tbody>
              {recent.slice(0, 12).map((r) => (
                <tr key={r.route_id} className="border-t border-white/5">
                  <td className="px-3 py-2 text-slate-500 font-mono">{r.computed_at?.slice(11, 19)}</td>
                  <td className="px-3 py-2 text-slate-300">
                    {r.origin_address || `${r.origin?.lat?.toFixed?.(2)},${r.origin?.lng?.toFixed?.(2)}`}
                    <span className="text-slate-600 mx-1">→</span>
                    {r.destination_address || `${r.destination?.lat?.toFixed?.(2)},${r.destination?.lng?.toFixed?.(2)}`}
                  </td>
                  <td className="px-3 py-2 text-right text-emerald-300 font-mono">{r.distance_mi} mi</td>
                  <td className="px-3 py-2 text-right text-amber-300 font-mono">{r.duration_hr} hr</td>
                  <td className="px-3 py-2 text-cyan-300 font-mono uppercase text-[10px]">{r.provider}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}

// ============================================================
//                    SAFETY EVENTS
// ============================================================
function SafetyView() {
  const [events, setEvents] = useState([]);
  const [mode, setMode] = useState("sample");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    (async () => {
      setBusy(true);
      try {
        const { data } = await api.get("/telematics/safety/events");
        setEvents(data.items || []);
        setMode(data.mode || "sample");
      } catch (e) { toast.error("Failed to load safety events"); }
      finally { setBusy(false); }
    })();
  }, []);
  const sevColor = (s) => s >= 3 ? "text-red-400 border-red-500/40 bg-red-500/10"
    : s === 2 ? "text-amber-400 border-amber-500/40 bg-amber-500/10"
    : "text-emerald-400 border-emerald-500/40 bg-emerald-500/10";

  return (
    <Card className="p-0 bg-slate-900/60 border-white/10 overflow-hidden">
      <div className="px-3 py-2 border-b border-white/10 text-[10px] font-mono uppercase tracking-widest text-cyan-300 flex justify-between">
        <span><AlertTriangle size={12} className="inline mr-1" />
          {events.length} safety events · {mode.toUpperCase()} data</span>
        {busy && <Loader2 size={12} className="animate-spin" />}
      </div>
      <table className="w-full text-xs" data-testid="safety-events-table">
        <thead className="bg-black/40 text-slate-500 font-mono uppercase tracking-wider">
          <tr>
            <th className="px-3 py-2 text-left">Time</th>
            <th className="px-3 py-2 text-left">Driver / Vehicle</th>
            <th className="px-3 py-2 text-left">Event</th>
            <th className="px-3 py-2 text-left">Severity</th>
            <th className="px-3 py-2 text-left">Location</th>
            <th className="px-3 py-2 text-left">Coaching</th>
          </tr>
        </thead>
        <tbody>
          {events.map((e) => (
            <tr key={e.event_id} className="border-t border-white/5" data-testid={`safety-row-${e.event_id}`}>
              <td className="px-3 py-2 text-slate-400 font-mono text-[10px]">{e.ts?.slice(11, 19)}</td>
              <td className="px-3 py-2 text-slate-200">
                <div>{e.driver_name}</div>
                <div className="text-[10px] text-slate-500 font-mono">{e.vehicle_id}</div>
              </td>
              <td className="px-3 py-2 text-slate-300 font-mono">{e.event_type?.replace(/_/g, " ")}</td>
              <td className="px-3 py-2">
                <span className={`px-2 py-0.5 rounded-full text-[10px] font-mono uppercase border ${sevColor(e.severity)}`}>
                  Sev {e.severity}
                </span>
              </td>
              <td className="px-3 py-2 text-slate-500 font-mono text-[10px]">
                <MapPin size={9} className="inline" /> {e.location_lat?.toFixed?.(2)}, {e.location_lng?.toFixed?.(2)}
              </td>
              <td className="px-3 py-2 text-slate-300 uppercase text-[10px] font-mono">{e.coaching_status}</td>
            </tr>
          ))}
          {!events.length && !busy && (
            <tr><td colSpan={6} className="p-8 text-center text-slate-500">No safety events on record.</td></tr>
          )}
        </tbody>
      </table>
    </Card>
  );
}

// ============================================================
//                    HOS LOGS
// ============================================================
function HosView() {
  const [items, setItems] = useState([]);
  const [atRisk, setAtRisk] = useState(0);
  const [mode, setMode] = useState("sample");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    (async () => {
      setBusy(true);
      try {
        const { data } = await api.get("/telematics/drivers/hos");
        setItems(data.items || []); setAtRisk(data.at_risk || 0); setMode(data.mode || "sample");
      } catch (e) { toast.error("Failed to load HOS"); }
      finally { setBusy(false); }
    })();
  }, []);
  const riskColor = (r) => r === "high" ? "text-red-400" : r === "medium" ? "text-amber-400" : "text-emerald-400";
  return (
    <Card className="p-0 bg-slate-900/60 border-white/10 overflow-hidden">
      <div className="px-3 py-2 border-b border-white/10 text-[10px] font-mono uppercase tracking-widest text-cyan-300 flex justify-between">
        <span><Clock size={12} className="inline mr-1" />
          {items.length} drivers · <span className="text-red-400">{atRisk} at-risk</span> · {mode.toUpperCase()}</span>
        {busy && <Loader2 size={12} className="animate-spin" />}
      </div>
      <table className="w-full text-xs" data-testid="hos-table">
        <thead className="bg-black/40 text-slate-500 font-mono uppercase tracking-wider">
          <tr>
            <th className="px-3 py-2 text-left">Driver</th>
            <th className="px-3 py-2 text-left">Vehicle</th>
            <th className="px-3 py-2 text-left">Status</th>
            <th className="px-3 py-2 text-right">Drove Today</th>
            <th className="px-3 py-2 text-right">Remaining</th>
            <th className="px-3 py-2 text-right">70-Hr Cycle</th>
            <th className="px-3 py-2 text-left">Risk</th>
          </tr>
        </thead>
        <tbody>
          {items.map((d) => (
            <tr key={d.driver_id} className="border-t border-white/5" data-testid={`hos-row-${d.driver_id}`}>
              <td className="px-3 py-2 text-slate-200">
                {d.driver_name}
                <div className="text-[10px] text-slate-500 font-mono">{d.driver_id}</div>
              </td>
              <td className="px-3 py-2 text-slate-400 font-mono">{d.vehicle_id}</td>
              <td className="px-3 py-2 text-slate-300 uppercase text-[10px] font-mono">{d.current_status}</td>
              <td className="px-3 py-2 text-right text-slate-300 font-mono">{(d.driving_minutes_today / 60).toFixed(1)}h</td>
              <td className="px-3 py-2 text-right text-emerald-300 font-mono">{(d.driving_minutes_remaining / 60).toFixed(1)}h</td>
              <td className="px-3 py-2 text-right text-cyan-300 font-mono">{(d.duty_cycle_minutes_remaining / 60).toFixed(1)}h</td>
              <td className={`px-3 py-2 uppercase font-mono text-[10px] ${riskColor(d.violation_risk)}`}>
                {d.violation_risk === "high" && <AlertTriangle size={10} className="inline mr-1" />}
                {d.violation_risk}
              </td>
            </tr>
          ))}
          {!items.length && !busy && (
            <tr><td colSpan={7} className="p-8 text-center text-slate-500">No HOS logs available.</td></tr>
          )}
        </tbody>
      </table>
    </Card>
  );
}

// ============================================================
//                    SHARED UI
// ============================================================
function ProviderBanner({ provider, label = "Samsara" }) {
  if (!provider) return null;
  const live = provider.mode === "live" || provider.connected;
  return (
    <div className={`px-3 py-2 rounded border flex items-center gap-2 text-xs ${
      live ? "border-emerald-500/40 bg-emerald-500/5 text-emerald-100"
           : "border-slate-500/30 bg-slate-500/5 text-slate-300"
    }`} data-testid={`fleet-provider-banner-${label.toLowerCase()}`}>
      {live ? <CheckCircle2 size={13} className="text-emerald-400" /> : <PlugZap size={13} className="text-slate-400" />}
      <span className="font-mono uppercase text-[10px] tracking-widest">{label}</span>
      <Badge variant="outline" className={live ? "border-emerald-500/40 text-emerald-300" : "border-slate-500/40 text-slate-400"}>
        {live ? "LIVE" : "SAMPLE"}
      </Badge>
      {provider.hint && <span className="text-slate-400 ml-2">{provider.hint}</span>}
    </div>
  );
}

function ResultTile({ label, value, color, icon: Icon }) {
  return (
    <div className="p-3 rounded bg-black/40 border border-white/10">
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-mono uppercase tracking-widest text-slate-500">{label}</span>
        {Icon && <Icon size={12} style={{ color }} />}
      </div>
      <div className="text-lg font-mono mt-1" style={{ color }}>{value}</div>
    </div>
  );
}
