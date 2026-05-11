import React, { useEffect, useState } from "react";
import Topbar from "../components/Topbar";
import MapView from "../components/MapView";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Link } from "react-router-dom";
import {
  Truck, Plane, Ship, Package, Train, AlertTriangle,
  Cloud, CloudRain, Sun, Snowflake, Wind, TrendingUp, DollarSign,
  Activity, Clock, CheckCircle2, AlertCircle, Database, ExternalLink
} from "lucide-react";
import QuotesTicker from "../components/QuotesTicker";
import {
  ResponsiveContainer, AreaChart, Area, LineChart, Line, BarChart, Bar,
  PieChart, Pie, Cell, XAxis, YAxis, Tooltip, CartesianGrid
} from "recharts";

const MODE_ICON = { TL: Truck, LTL: Truck, Parcel: Package, Ocean: Ship, Air: Plane, Rail: Train };
const MODE_COLOR = {
  TL: "#00E5FF", LTL: "#06B6D4", Parcel: "#10B981",
  Ocean: "#3B82F6", Air: "#A78BFA", Rail: "#FFCC00"
};
const STATUS_BADGE = {
  in_transit: "bg-cyan-500/10 text-cyan-400 border-cyan-500/30",
  delayed: "bg-red-500/10 text-red-400 border-red-500/30",
  delivered: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
  pending: "bg-yellow-500/10 text-yellow-400 border-yellow-500/30",
  at_origin: "bg-yellow-500/10 text-yellow-400 border-yellow-500/30",
  at_dest: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
};

function weatherIcon(code) {
  if (code == null) return Cloud;
  if (code === 0) return Sun;
  if (code < 50) return Cloud;
  if (code < 70) return CloudRain;
  if (code < 80) return Snowflake;
  return Wind;
}

const KPI = ({ label, value, sub, accent = "cyan", testid }) => {
  const accents = {
    cyan: "text-cyan-400", green: "text-emerald-400",
    amber: "text-yellow-400", red: "text-red-400"
  };
  return (
    <Card className="hud-surface p-5 relative overflow-hidden" data-testid={testid}>
      <div className="absolute inset-0 hud-scanline pointer-events-none"></div>
      <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-slate-500">{label}</div>
      <div className={`mt-2 text-3xl font-mono font-bold tabular-nums ${accents[accent]}`}>{value}</div>
      {sub && <div className="mt-1 text-xs text-slate-400">{sub}</div>}
    </Card>
  );
};

const Row = ({ k, v, mono, green }) => (
  <div className="flex items-center justify-between gap-2">
    <span className="text-[10px] font-mono uppercase tracking-wider text-slate-500">{k}</span>
    <span className={`${mono ? "font-mono" : ""} ${green ? "text-emerald-400" : "text-slate-200"} text-right truncate max-w-[180px]`}>{v}</span>
  </div>
);

export default function Dashboard() {
  const [kpis, setKpis] = useState(null);
  const [shipments, setShipments] = useState([]);
  const [facilities, setFacilities] = useState([]);
  const [weather, setWeather] = useState([]);
  const [news, setNews] = useState([]);
  const [traffic, setTraffic] = useState([]);
  const [sapMaterials, setSapMaterials] = useState([]);

  useEffect(() => {
    (async () => {
      try {
        const [k, s, f, w, n, t, m] = await Promise.all([
          api.get("/kpis"), api.get("/shipments"), api.get("/facilities"),
          api.get("/weather"), api.get("/news"), api.get("/traffic"),
          api.get("/sap/materials"),
        ]);
        setKpis(k.data); setShipments(s.data); setFacilities(f.data);
        setWeather(w.data); setNews(n.data); setTraffic(t.data);
        setSapMaterials(m.data?.materials || []);
      } catch (e) { console.error(e); }
    })();
  }, []);

  const modeData = kpis ? Object.entries(kpis.by_mode).map(([k, v]) => ({ name: k, value: v, color: MODE_COLOR[k] })) : [];
  const recentShipments = shipments.slice(0, 8);

  return (
    <>
      <Topbar title="Command Center" subtitle="TENNANT COMPANIES · TMS HUD · LIVE OPERATIONS" />
      <div className="p-4 md:p-6 space-y-5">

        {/* Subtle inspirational quotes ticker */}
        <QuotesTicker />

        {/* SAP S/4HANA Quick Actions */}
        <Card className="hud-surface p-3" data-testid="sap-quick-actions">
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-2 px-2">
              <Database size={14} className="text-cyan-400" />
              <span className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400">SAP S/4HANA</span>
            </div>
            {[
              { to: "/sap-sync?ref=so", label: "Sales Orders" },
              { to: "/sap-sync?ref=po", label: "Purchase Orders" },
              { to: "/sap-sync?ref=imports", label: "Imports" },
              { to: "/sap-sync?ref=deliveries", label: "Open Deliveries" },
              { to: "/sap-sync?ref=materials", label: "Materials" },
              { to: "/sap-sync?ref=logs", label: "Sync Logs" },
            ].map((b) => (
              <Link key={b.to} to={b.to} data-testid={`sap-quick-${b.label.replace(/ /g, '-').toLowerCase()}`}
                className="px-3 py-1.5 rounded text-xs font-mono uppercase tracking-wider border border-cyan-500/30 text-cyan-300 hover:bg-cyan-500/10 hover:border-cyan-400 flex items-center gap-1.5">
                {b.label} <ExternalLink size={10} className="opacity-60" />
              </Link>
            ))}
          </div>
        </Card>

        {/* News Ticker */}
        <div className="hud-surface rounded-lg overflow-hidden border border-cyan-500/10" data-testid="news-ticker">
          <div className="flex items-center">
            <div className="bg-cyan-500/10 px-4 py-2.5 border-r border-cyan-500/20 flex items-center gap-2 shrink-0">
              <Activity size={14} className="text-cyan-400 blink-dot" />
              <span className="text-[10px] font-mono text-cyan-400 tracking-[0.2em] uppercase">Industry Feed</span>
            </div>
            <div className="flex-1 overflow-hidden">
              <div className="flex gap-8 py-2.5 scroll-ticker whitespace-nowrap">
                {[...news, ...news].map((n, i) => (
                  <span key={i} className="text-xs text-slate-300">
                    <span className="text-cyan-400 mono mr-2">[{n.source}]</span>{n.title}
                    <span className="ml-2 text-slate-500">· {n.time}</span>
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Customs Broker Card + News Window row */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
          {/* Customs Broker UPS_SCS */}
          <Card className="hud-surface p-4" data-testid="customs-broker-widget">
            <div className="flex items-center justify-between mb-3">
              <div>
                <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400">Customs Broker</div>
                <h3 className="font-display text-base font-bold mt-1">UPS_SCS</h3>
              </div>
              <div className="px-2 py-1 rounded bg-amber-500/10 border border-amber-500/30 text-[9px] font-mono text-amber-300">
                UPS Supply Chain Solutions
              </div>
            </div>
            <div className="space-y-1.5 text-xs">
              <Row k="Account #" v="TENNANT-CCM-04287" mono />
              <Row k="ACE Portal ID" v="UPS_SCS_001" mono />
              <Row k="POA on File" v="✓ Active" green />
              <Row k="Bond Type" v="Continuous · $250K" />
              <Row k="Primary Contact" v="Amanda Reyes" />
              <Row k="Phone (24/7)" v="+1-800-555-2227" mono />
              <Row k="Email" v="tennant@ups-scs.com" mono />
              <Row k="ISF Filings YTD" v="284" />
              <Row k="Entry Filings YTD" v="412" />
            </div>
            <a
              href="https://www.ups.com/us/en/supplychain/services/customs-brokerage.page"
              target="_blank" rel="noreferrer"
              className="mt-3 inline-flex items-center gap-1 text-xs font-mono text-cyan-400 hover:text-cyan-300"
            >Open UPS_SCS Portal <ExternalLink size={11} /></a>
          </Card>

          {/* Transportation News persistent window */}
          <Card className="hud-surface p-4 lg:col-span-2" data-testid="news-window">
            <div className="flex items-center justify-between mb-3">
              <div>
                <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400">Transportation News</div>
                <h3 className="font-display text-base font-bold mt-1">Live Feed</h3>
              </div>
              <span className="relative flex h-2 w-2"><span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span><span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span></span>
            </div>
            <div className="space-y-2 max-h-[260px] overflow-y-auto pr-1">
              {news.map((n, i) => (
                <div key={i} className="p-2.5 rounded border border-white/5 bg-white/[0.02] hover:border-cyan-500/30 transition-colors">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <div className="text-[10px] font-mono text-cyan-400 uppercase tracking-wider">{n.source} · {n.category}</div>
                      <div className="text-xs text-slate-200 mt-1 leading-relaxed">{n.title}</div>
                    </div>
                    <span className="text-[10px] font-mono text-slate-500 shrink-0">{n.time}</span>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>

        {/* SAP Materials / Part Numbers Widget */}
        <Card className="hud-surface p-4" data-testid="sap-materials-widget">
          <div className="flex items-center justify-between mb-3">
            <div>
              <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400">SAP S/4HANA · Materials</div>
              <h3 className="font-display text-base font-bold mt-1">Top Part Numbers · Open Orders</h3>
            </div>
            <Link to="/sap-sync?ref=materials" data-testid="materials-view-all"
              className="text-xs font-mono uppercase tracking-wider text-cyan-400 hover:text-cyan-300 flex items-center gap-1">
              View All in SAP <ExternalLink size={10} />
            </Link>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-[10px] font-mono text-slate-500 uppercase tracking-wider">
                <tr className="border-b border-white/5">
                  <th className="text-left py-2 px-3">Part #</th>
                  <th className="text-left py-2 px-3">Description</th>
                  <th className="text-center py-2 px-3">Plant</th>
                  <th className="text-right py-2 px-3">On Hand</th>
                  <th className="text-right py-2 px-3">Open Orders</th>
                  <th className="text-center py-2 px-3">NMFC / Class</th>
                </tr>
              </thead>
              <tbody className="font-mono">
                {sapMaterials.map((m) => (
                  <tr key={m.part_no} className="border-t border-white/5 hover:bg-white/[0.02]" data-testid={`material-${m.part_no}`}>
                    <td className="py-2 px-3">
                      <Link to={`/sap-sync?ref=material&part=${m.part_no}`} className="text-cyan-300 hover:text-cyan-200 hover:underline decoration-cyan-500/40 flex items-center gap-1">
                        {m.part_no} <ExternalLink size={9} className="opacity-50" />
                      </Link>
                    </td>
                    <td className="py-2 px-3 text-slate-300 text-xs">{m.description}</td>
                    <td className="py-2 px-3 text-center text-emerald-400 text-xs">{m.plant}</td>
                    <td className="py-2 px-3 text-right text-slate-300">{m.on_hand}</td>
                    <td className="py-2 px-3 text-right">
                      <span className={m.open_orders > 20 ? "text-yellow-400" : "text-slate-300"}>{m.open_orders}</span>
                    </td>
                    <td className="py-2 px-3 text-center text-xs"><span className="text-cyan-400">{m.nmfc}</span> <span className="text-slate-500">· {m.freight_class}</span></td>
                  </tr>
                ))}
                {sapMaterials.length === 0 && (
                  <tr><td colSpan={6} className="text-center py-6 text-slate-500">Loading from S/4HANA…</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </Card>

        {/* KPIs */}
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
          <KPI label="Active Shipments" value={kpis?.totals.in_transit ?? "—"} sub="across all modes" testid="kpi-in-transit" />
          <KPI label="Delayed" value={kpis?.totals.delayed ?? "—"} accent="red" sub="needs attention" testid="kpi-delayed" />
          <KPI label="Delivered" value={kpis?.totals.delivered ?? "—"} accent="green" sub="last 14 days" testid="kpi-delivered" />
          <KPI label="Pending" value={kpis?.totals.pending ?? "—"} accent="amber" sub="awaiting pickup" testid="kpi-pending" />
          <KPI label="On-Time Rate" value={`${kpis?.totals.on_time_rate ?? 0}%`} accent="green" sub="OTD" testid="kpi-on-time" />
          <KPI label="In Motion (lbs)" value={kpis ? Number(kpis.totals.weight_lbs).toLocaleString() : "—"} sub="tonnage" testid="kpi-weight" />
          <KPI label="Value (USD)" value={kpis ? `$${(kpis.totals.value_usd / 1000).toFixed(0)}K` : "—"} accent="green" sub="cargo value" testid="kpi-value" />
        </div>

        {/* Map + Right column */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          <div className="lg:col-span-8 space-y-4">
            <Card className="hud-surface p-4">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400">Geo-Spatial Tracker</div>
                  <h3 className="font-display text-lg font-bold mt-1">Live Shipments — All Modes</h3>
                </div>
                <div className="flex items-center gap-3 text-[10px] font-mono">
                  <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-cyan-400 hud-glow-cyan"></span>IN TRANSIT</span>
                  <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-red-500"></span>DELAYED</span>
                  <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-emerald-500"></span>DELIVERED</span>
                  <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-sm bg-cyan-500 rotate-45"></span>FACILITY</span>
                </div>
              </div>
              <MapView shipments={shipments} facilities={facilities} height={460} showRoutes />
            </Card>

            <Card className="hud-surface p-5">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400">14-Day Trend</div>
                  <h3 className="font-display text-lg font-bold mt-1">Volume & On-Time Performance</h3>
                </div>
                <TrendingUp size={18} className="text-cyan-400" />
              </div>
              <ResponsiveContainer width="100%" height={200}>
                <AreaChart data={kpis?.trend || []}>
                  <defs>
                    <linearGradient id="gradC" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#00E5FF" stopOpacity={0.4} />
                      <stop offset="100%" stopColor="#00E5FF" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="gradG" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#10B981" stopOpacity={0.3} />
                      <stop offset="100%" stopColor="#10B981" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="rgba(255,255,255,0.04)" />
                  <XAxis dataKey="date" stroke="#475569" tick={{ fontSize: 10, fontFamily: "JetBrains Mono" }} />
                  <YAxis stroke="#475569" tick={{ fontSize: 10, fontFamily: "JetBrains Mono" }} />
                  <Tooltip contentStyle={{ background: "#0B0E14", border: "1px solid rgba(0,229,255,0.3)", fontSize: 12 }} />
                  <Area type="monotone" dataKey="shipments" stroke="#00E5FF" fill="url(#gradC)" strokeWidth={2} />
                  <Area type="monotone" dataKey="on_time" stroke="#10B981" fill="url(#gradG)" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            </Card>
          </div>

          <div className="lg:col-span-4 space-y-4">
            {/* Weather */}
            <Card className="hud-surface p-4">
              <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-3">Facility Conditions</div>
              <div className="space-y-2.5" data-testid="weather-widget">
                {weather.map((w) => {
                  const Icon = weatherIcon(w.weather_code);
                  return (
                    <div key={w.facility_id} className="flex items-center justify-between p-2.5 rounded border border-white/5 bg-white/[0.02]">
                      <div className="flex items-center gap-3">
                        <Icon size={20} className="text-cyan-400" />
                        <div>
                          <div className="text-sm text-white">{w.facility_name}</div>
                          <div className="text-[10px] font-mono text-slate-500">{w.humidity}% RH · {w.wind_mph} mph</div>
                        </div>
                      </div>
                      <div className="font-mono text-xl font-bold text-cyan-400 tabular-nums">{w.temperature_f != null ? `${Math.round(w.temperature_f)}°` : "—"}</div>
                    </div>
                  );
                })}
              </div>
            </Card>

            {/* Traffic Alerts */}
            <Card className="hud-surface p-4">
              <div className="flex items-center justify-between mb-3">
                <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-yellow-400">Traffic Alerts</div>
                <AlertTriangle size={14} className="text-yellow-400" />
              </div>
              <div className="space-y-2 max-h-64 overflow-y-auto" data-testid="traffic-widget">
                {traffic.map((t, i) => (
                  <div key={i} className="p-2.5 rounded border border-white/5 bg-white/[0.02]">
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-white truncate flex-1">{t.location}</span>
                      <span className={`text-[10px] font-mono uppercase ml-2 ${t.severity === 'high' ? 'text-red-400' : t.severity === 'moderate' ? 'text-yellow-400' : 'text-slate-400'}`}>+{t.delay_min}m</span>
                    </div>
                    <div className="text-[10px] font-mono text-slate-500 mt-0.5">{t.type}</div>
                  </div>
                ))}
              </div>
            </Card>

            {/* Mode mix donut */}
            <Card className="hud-surface p-4">
              <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-3">Mode Mix</div>
              <ResponsiveContainer width="100%" height={180}>
                <PieChart>
                  <Pie data={modeData} dataKey="value" nameKey="name" innerRadius={45} outerRadius={70} stroke="none" paddingAngle={2}>
                    {modeData.map((d, i) => (<Cell key={i} fill={d.color} />))}
                  </Pie>
                  <Tooltip contentStyle={{ background: "#0B0E14", border: "1px solid rgba(0,229,255,0.3)", fontSize: 12 }} />
                </PieChart>
              </ResponsiveContainer>
              <div className="grid grid-cols-3 gap-1 mt-2">
                {modeData.map((d) => (
                  <div key={d.name} className="text-[10px] font-mono text-slate-400 flex items-center gap-1">
                    <span className="w-2 h-2 rounded-sm" style={{ background: d.color }} />{d.name} · {d.value}
                  </div>
                ))}
              </div>
            </Card>
          </div>
        </div>

        {/* Recent Shipments */}
        <Card className="hud-surface p-5">
          <div className="flex items-center justify-between mb-3">
            <div>
              <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400">Active Manifest</div>
              <h3 className="font-display text-lg font-bold mt-1">Recent Shipments</h3>
            </div>
            <Link to="/shipments" className="text-xs font-mono text-cyan-400 hover:text-cyan-300" data-testid="dashboard-view-all-shipments">VIEW ALL →</Link>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[10px] font-mono text-slate-500 uppercase tracking-wider">
                  <th className="text-left py-2 px-2">Ref</th>
                  <th className="text-left py-2 px-2">Mode</th>
                  <th className="text-left py-2 px-2">Carrier</th>
                  <th className="text-left py-2 px-2">Lane</th>
                  <th className="text-left py-2 px-2">Status</th>
                  <th className="text-right py-2 px-2">Weight</th>
                  <th className="text-right py-2 px-2">ETA</th>
                </tr>
              </thead>
              <tbody className="font-mono">
                {recentShipments.map((s) => {
                  const Icon = MODE_ICON[s.mode] || Package;
                  return (
                    <tr key={s.shipment_id} className="border-t border-white/5 hover:bg-white/[0.02]">
                      <td className="py-2 px-2 text-cyan-300">{s.reference}</td>
                      <td className="py-2 px-2"><span className="inline-flex items-center gap-1.5 text-slate-300"><Icon size={13} />{s.mode}</span></td>
                      <td className="py-2 px-2 text-slate-300">{s.carrier}</td>
                      <td className="py-2 px-2 text-slate-400 text-xs">{s.origin.city} → {s.destination.city}</td>
                      <td className="py-2 px-2"><Badge className={`${STATUS_BADGE[s.status]} font-mono text-[10px] uppercase`}>{s.status}</Badge></td>
                      <td className="py-2 px-2 text-right text-slate-300">{Number(s.weight_lbs).toLocaleString()}</td>
                      <td className="py-2 px-2 text-right text-slate-400 text-xs">{new Date(s.eta).toLocaleDateString()}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </>
  );
}
