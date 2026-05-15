import React, { useEffect, useState } from "react";
import Topbar from "../components/Topbar";
import MapView from "../components/MapView";
import { api } from "../lib/api";
import { toast } from "sonner";
import { Card } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Link } from "react-router-dom";
import {
  Truck, Plane, Ship, Package, Train, AlertTriangle,
  Cloud, CloudRain, Sun, Snowflake, Wind, TrendingUp, DollarSign,
  Activity, Clock, CheckCircle2, AlertCircle, Database, ExternalLink, Youtube,
  GripVertical, RotateCcw
} from "lucide-react";
import QuotesTicker from "../components/QuotesTicker";
import MiniCalendar from "../components/MiniCalendar";
import WeatherAlertsBanner from "../components/WeatherAlertsBanner";
import WeatherRadar from "../components/WeatherRadar";
import { useUserLayout } from "../components/DraggableTiles";
import { useBranding, useBrandRefresh } from "../lib/branding";
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
  const { brand } = useBranding();
  const [kpis, setKpis] = useState(null);
  const [shipments, setShipments] = useState([]);
  const [facilities, setFacilities] = useState([]);
  const [weather, setWeather] = useState([]);
  const [news, setNews] = useState([]);
  const [traffic, setTraffic] = useState([]);
  const [sapMaterials, setSapMaterials] = useState([]);

  useEffect(() => {
    loadAll();
  }, []);
  useBrandRefresh(() => loadAll());

  async function loadAll() {
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
  }

  const modeData = kpis ? Object.entries(kpis.by_mode).map(([k, v]) => ({ name: k, value: v, color: MODE_COLOR[k] })) : [];
  const recentShipments = shipments.slice(0, 8);

  // Drag-and-drop ordering for Command Center sections. Default puts the
  // Geo-Spatial Tracker + Facility Conditions (`main-grid`) AT THE TOP per
  // the user's request, then KPIs, then secondary widgets. The order is
  // persisted server-side per user via /api/user/layouts/dashboard.
  const DEFAULT_SECTIONS = [
    "main-grid", "kpis", "sap-quick", "news-ticker", "video-row", "sap-materials", "recent-shipments",
  ];
  const { order: sectionOrder, setOrder: setSectionOrder, reset: resetSectionOrder } =
    useUserLayout("dashboard", DEFAULT_SECTIONS);
  const [dragSec, setDragSec] = useState(null);
  const [overSec, setOverSec] = useState(null);
  const handleDrop = (target) => (e) => {
    e.preventDefault();
    const src = e.dataTransfer.getData("text/plain");
    setDragSec(null); setOverSec(null);
    if (!src || src === target) return;
    setSectionOrder((arr) => {
      const next = [...arr];
      const from = next.indexOf(src);
      const to = next.indexOf(target);
      if (from === -1 || to === -1) return arr;
      const [moved] = next.splice(from, 1);
      next.splice(to, 0, moved);
      return next;
    });
  };
  const sectionProps = (id) => ({
    "data-testid": `dash-section-${id}`,
    "data-section-id": id,
    style: { order: sectionOrder.indexOf(id) },
    onDragOver: (e) => { if (!dragSec) return; e.preventDefault(); e.dataTransfer.dropEffect = "move"; if (overSec !== id) setOverSec(id); },
    onDragLeave: () => { if (overSec === id) setOverSec(null); },
    onDrop: handleDrop(id),
    className: `relative group ${overSec === id && dragSec && dragSec !== id ? "ring-2 ring-cyan-400 rounded-lg" : ""} ${dragSec === id ? "opacity-50" : ""}`,
  });
  const dragHandle = (id, label) => (
    <button
      type="button"
      draggable
      onDragStart={(e) => { e.dataTransfer.setData("text/plain", id); e.dataTransfer.effectAllowed = "move"; setDragSec(id); }}
      onDragEnd={() => { setDragSec(null); setOverSec(null); }}
      aria-label={`Drag ${label}`}
      data-testid={`drag-${id}`}
      className="absolute top-1.5 right-1.5 z-20 p-1.5 rounded bg-black/50 backdrop-blur border border-white/10 text-slate-400 hover:text-cyan-300 hover:border-cyan-500/40 cursor-grab active:cursor-grabbing opacity-30 group-hover:opacity-100 transition"
    >
      <GripVertical size={12} />
    </button>
  );

  return (
    <>
      <Topbar title="Command Center" subtitle={`${(brand?.company_name || "TENNANT COMPANIES").toUpperCase()} · TMS HUD · LIVE OPERATIONS`} />
      <div className="p-4 md:p-6 flex flex-col gap-5">

        {/* Auto NWS-style weather alert banner — polls every 60s, dismissible per alert_id */}
        <WeatherAlertsBanner />

        {/* Thin full-width quotes ticker — no longer flex-stretched against the
            taller MiniCalendar (that was leaving a big empty box). */}
        <QuotesTicker />

        {/* Weather radar + mini calendar share a row so the calendar's height
            is balanced by the radar instead of an empty gap. Stacks below md. */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-3 items-start">
          <div className="lg:col-span-9">
            <WeatherRadar height={360} />
          </div>
          <div className="lg:col-span-3 flex justify-center lg:justify-end">
            <MiniCalendar />
          </div>
        </div>

        {/* Drag-to-reorder hint + Reset */}
        <div className="flex items-center justify-end gap-2 -mb-3" data-testid="dash-reorder-toolbar">
          <span className="text-[10px] font-mono uppercase tracking-[0.2em] text-slate-500">
            Drag any tile by its grip · layout saves automatically
          </span>
          <button
            onClick={() => resetSectionOrder()}
            data-testid="dash-reset-layout"
            className="inline-flex items-center gap-1 px-2.5 py-1 rounded border border-cyan-500/30 text-[10px] font-mono uppercase tracking-wider text-cyan-300 hover:bg-cyan-500/10"
          >
            <RotateCcw size={11} /> Reset Layout
          </button>
        </div>

        {/* SAP S/4HANA Quick Actions */}
        <div {...sectionProps("sap-quick")}>
          {dragHandle("sap-quick", "SAP Quick Actions")}
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
        </div>

        {/* News Ticker */}
        <div {...sectionProps("news-ticker")}>
          {dragHandle("news-ticker", "Industry Feed")}
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
        </div>

        {/* Compact YouTube Video Tile + News Window row */}
        <div {...sectionProps("video-row")}>
          {dragHandle("video-row", "Video & News")}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
          {/* Compact YouTube video screen — slot replaces former Customs Broker.
              Intentionally smaller than the broker card was, so the rest of the
              Command tab stays above the fold. */}
          <CompactVideoTile />

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
        </div>

        {/* SAP Materials / Part Numbers Widget */}
        <div {...sectionProps("sap-materials")}>
          {dragHandle("sap-materials", "SAP Materials")}
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
        </div>

        {/* KPIs */}
        <div {...sectionProps("kpis")}>
          {dragHandle("kpis", "KPI Strip")}
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
          <KPI label="Active Shipments" value={kpis?.totals.in_transit ?? "—"} sub="across all modes" testid="kpi-in-transit" />
          <KPI label="Delayed" value={kpis?.totals.delayed ?? "—"} accent="red" sub="needs attention" testid="kpi-delayed" />
          <KPI label="Delivered" value={kpis?.totals.delivered ?? "—"} accent="green" sub="last 14 days" testid="kpi-delivered" />
          <KPI label="Pending" value={kpis?.totals.pending ?? "—"} accent="amber" sub="awaiting pickup" testid="kpi-pending" />
          <KPI label="On-Time Rate" value={`${kpis?.totals.on_time_rate ?? 0}%`} accent="green" sub="OTD" testid="kpi-on-time" />
          <KPI label="In Motion (lbs)" value={kpis ? Number(kpis.totals.weight_lbs).toLocaleString() : "—"} sub="tonnage" testid="kpi-weight" />
          <KPI label="Value (USD)" value={kpis ? `$${(kpis.totals.value_usd / 1000).toFixed(0)}K` : "—"} accent="green" sub="cargo value" testid="kpi-value" />
        </div>
        </div>

        {/* Map + Right column */}
        <div {...sectionProps("main-grid")}>
          {dragHandle("main-grid", "Map & Side Panels")}
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
            <FacilityConditions weather={weather} />

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
        </div>

        {/* Recent Shipments */}
        <div {...sectionProps("recent-shipments")}>
          {dragHandle("recent-shipments", "Recent Shipments")}
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
      </div>
    </>
  );
}

/**
 * Compact YouTube video tile for the Command Center.
 *
 * Replaces the former Customs Broker card slot. Intentionally smaller than
 * the broker card so the Command tab fits above the fold:
 *  - Iframe locked to a 16:9 box no taller than the broker card was (~h-44)
 *  - Pasteable URL/ID input collapsed behind a "Change" toggle to save space
 *  - Default video: Tennant Company official trailer (mTxE3g7o4aY)
 *  - Persists the chosen video to localStorage so it survives page reloads
 */
function CompactVideoTile() {
  const DEFAULT_ID = "mTxE3g7o4aY";
  const KEY = "tms-dashboard-video";
  const PLAYLIST_KEY = "tms-dashboard-playlist";
  const DEFAULT_PLAYLIST = [
    { id: "mTxE3g7o4aY", title: "Tennant · Is Everywhere Trailer" },
    { id: "5qap5aO4i9A", title: "Lofi · Study Stream" },
    { id: "jfKfPfyJRdk", title: "Lofi · Beats to Relax" },
    { id: "rQ7yA5jb5_M", title: "FedEx · Inside Look" },
  ];
  const [videoId, setVideoId] = useState(() => {
    try {
      const saved = localStorage.getItem(KEY);
      if (saved && /^[A-Za-z0-9_-]{11}$/.test(saved)) return saved;
    } catch (e) { /* ignore */ }
    return DEFAULT_ID;
  });
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(videoId);
  const [err, setErr] = useState("");
  const [playlist, setPlaylist] = useState(() => {
    try {
      const saved = localStorage.getItem(PLAYLIST_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length > 0) return parsed;
      }
    } catch (e) { /* ignore */ }
    return DEFAULT_PLAYLIST;
  });

  useEffect(() => {
    try { localStorage.setItem(KEY, videoId); } catch (e) { /* ignore */ }
  }, [videoId]);
  useEffect(() => {
    try { localStorage.setItem(PLAYLIST_KEY, JSON.stringify(playlist)); } catch (e) { /* ignore */ }
  }, [playlist]);

  const parseId = (s) => {
    const t = String(s || "").trim();
    if (!t) return null;
    if (/^[A-Za-z0-9_-]{11}$/.test(t)) return t;
    try {
      const u = new URL(t);
      if (u.searchParams.get("v")) return u.searchParams.get("v");
      const parts = u.pathname.split("/").filter(Boolean);
      const i = parts.findIndex((p) => ["embed", "shorts", "v", "live"].includes(p));
      if (i >= 0 && /^[A-Za-z0-9_-]{11}$/.test(parts[i + 1] || "")) return parts[i + 1];
      if (u.hostname.includes("youtu.be") && /^[A-Za-z0-9_-]{11}$/.test(parts[0] || "")) return parts[0];
    } catch (e) { /* not a URL */ }
    return null;
  };

  const apply = () => {
    const id = parseId(draft);
    if (!id) { setErr("Couldn't read that link — paste a youtube.com / youtu.be URL or 11-char ID."); return; }
    setErr(""); setVideoId(id); setDraft(id); setEditing(false);
  };

  const pin = () => {
    if (playlist.some((p) => p.id === videoId)) return;
    // Use a sensible default title (user can rename later if we add UI).
    const title = window.prompt("Title for this pinned video?", `Video · ${videoId.slice(0, 6)}`);
    if (!title) return;
    setPlaylist([{ id: videoId, title }, ...playlist].slice(0, 12));
  };

  const playPin = (id) => { setVideoId(id); setDraft(id); setErr(""); };
  const removePin = (id) => setPlaylist(playlist.filter((p) => p.id !== id));

  return (
    <Card className="hud-surface p-3" data-testid="video-player-tile">
      <div className="flex items-center justify-between mb-2 gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <Youtube size={14} className="text-red-500 shrink-0" />
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 truncate">Video Screen</div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            onClick={pin}
            disabled={playlist.some((p) => p.id === videoId)}
            data-testid="video-pin-btn"
            title={playlist.some((p) => p.id === videoId) ? "Already pinned" : "Pin to playlist"}
            className="text-[9px] font-mono uppercase tracking-wider text-emerald-300 hover:text-emerald-200 disabled:opacity-40 disabled:cursor-not-allowed inline-flex items-center gap-0.5"
          >＋Pin</button>
          <button
            type="button"
            onClick={() => { setEditing((v) => !v); setErr(""); setDraft(videoId); }}
            data-testid="video-edit-toggle"
            className="text-[9px] font-mono uppercase tracking-wider text-slate-400 hover:text-cyan-300"
          >{editing ? "Cancel" : "Change"}</button>
          <a
            href={`https://www.youtube.com/watch?v=${videoId}`}
            target="_blank" rel="noreferrer"
            data-testid="video-open-youtube"
            className="text-[9px] font-mono uppercase tracking-wider text-cyan-300 hover:text-cyan-200 inline-flex items-center gap-1"
          >Open <ExternalLink size={9} /></a>
        </div>
      </div>
      {/* Pinned playlist — quick-switch with one click. */}
      {playlist.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-2" data-testid="video-playlist">
          {playlist.map((p) => (
            <div
              key={p.id}
              className={`group flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-mono uppercase tracking-wider border transition ${
                p.id === videoId
                  ? "bg-cyan-500 text-black border-cyan-400"
                  : "border-white/10 text-slate-300 hover:border-cyan-400/40 hover:text-cyan-200"
              }`}
            >
              <button
                onClick={() => playPin(p.id)}
                data-testid={`video-play-${p.id}`}
                title={p.title}
                className="max-w-[140px] truncate text-left"
              >{p.title}</button>
              <button
                onClick={() => removePin(p.id)}
                data-testid={`video-unpin-${p.id}`}
                title="Remove pin"
                className={`opacity-0 group-hover:opacity-100 ${p.id === videoId ? "hover:text-red-700" : "hover:text-red-400"}`}
              >×</button>
            </div>
          ))}
        </div>
      )}
      <div className="relative w-full aspect-video bg-black rounded overflow-hidden border border-white/5 max-h-44">
        <iframe
          key={videoId}
          src={`https://www.youtube.com/embed/${videoId}?rel=0&modestbranding=1&playsinline=1`}
          title="YouTube player"
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
          allowFullScreen
          data-testid="video-iframe"
          className="absolute inset-0 w-full h-full"
        />
      </div>
      {editing && (
        <div className="mt-2 flex gap-1.5">
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") apply(); }}
            placeholder="Paste YouTube URL or ID…"
            data-testid="video-url-input"
            className="flex-1 px-2 py-1 bg-[#0B0E14] border border-white/10 rounded text-xs font-mono text-slate-200"
          />
          <button
            onClick={apply}
            data-testid="video-load-btn"
            className="px-2 py-1 rounded border border-cyan-500/30 text-cyan-300 hover:bg-cyan-500/10 text-[10px] font-mono uppercase tracking-wider"
          >Load</button>
        </div>
      )}
      {err && <div className="mt-1.5 text-[10px] font-mono text-red-400" data-testid="video-error">{err}</div>}
    </Card>
  );
}


/**
 * FacilityConditions — brand-aware weather widget.
 *   - auto-lists the active brand's facilities (re-fetched on theme switch)
 *   - admin/dispatcher can ADD ad-hoc cities to track + REMOVE any extra
 *   - extra cities persist in localStorage so they survive page reloads
 */
function FacilityConditions({ weather }) {
  const STORAGE_KEY = "tms.extra_weather_cities.v1";
  const [extras, setExtras] = React.useState([]);
  const [adding, setAdding] = React.useState(false);
  const [city, setCity] = React.useState("");
  const [busy, setBusy] = React.useState(false);

  React.useEffect(() => {
    try { setExtras(JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]")); } catch { /* noop */ }
  }, []);

  // Re-load every 5 minutes
  React.useEffect(() => {
    if (extras.length === 0) return;
    refreshExtras();
    const t = setInterval(refreshExtras, 300_000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [extras.map((e) => e.id).join(",")]);

  const refreshExtras = async () => {
    const next = await Promise.all(extras.map(async (e) => {
      try {
        const url = `https://api.open-meteo.com/v1/forecast?latitude=${e.lat}&longitude=${e.lng}&current=temperature_2m,wind_speed_10m,weather_code,relative_humidity_2m&temperature_unit=fahrenheit&wind_speed_unit=mph`;
        const r = await fetch(url).then((x) => x.json());
        const d = r.current || {};
        return { ...e, temperature_f: d.temperature_2m, humidity: d.relative_humidity_2m, wind_mph: d.wind_speed_10m, weather_code: d.weather_code };
      } catch { return e; }
    }));
    setExtras(next);
  };

  const geocode = async (q) => {
    const url = `https://geocoding-api.open-meteo.com/v1/search?name=${encodeURIComponent(q)}&count=1&language=en&format=json`;
    const r = await fetch(url).then((x) => x.json());
    const hit = (r.results || [])[0];
    if (!hit) return null;
    return { lat: hit.latitude, lng: hit.longitude, label: `${hit.name}${hit.admin1 ? ", " + hit.admin1 : ""}` };
  };

  const submitAdd = async () => {
    if (!city.trim()) return;
    setBusy(true);
    try {
      const geo = await geocode(city.trim());
      if (!geo) { toast.error("Couldn't find that location"); return; }
      const id = `extra-${Date.now()}`;
      const entry = { id, facility_id: id, facility_name: geo.label, lat: geo.lat, lng: geo.lng };
      const next = [...extras, entry];
      setExtras(next);
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      setCity("");
      setAdding(false);
      toast.success(`Added ${geo.label}`);
    } catch { toast.error("Lookup failed"); } finally { setBusy(false); }
  };

  const removeExtra = (id) => {
    const next = extras.filter((e) => e.id !== id);
    setExtras(next);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  };

  const allRows = [...weather, ...extras];

  return (
    <Card className="hud-surface p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400">Facility Conditions</div>
        <button
          onClick={() => setAdding((v) => !v)}
          data-testid="weather-add-toggle"
          className="text-[10px] font-mono uppercase tracking-wider text-cyan-300 hover:text-cyan-200 flex items-center gap-1"
        >
          {adding ? "Cancel" : "+ Add Location"}
        </button>
      </div>

      {adding && (
        <div className="mb-3 flex gap-2" data-testid="weather-add-form">
          <input
            value={city}
            onChange={(e) => setCity(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") submitAdd(); }}
            placeholder="Type any city — Tokyo, Berlin…"
            data-testid="weather-add-input"
            className="flex-1 bg-[#11151F] border border-white/10 rounded px-2 py-1 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500/50"
            disabled={busy}
          />
          <button
            onClick={submitAdd}
            disabled={busy || !city.trim()}
            data-testid="weather-add-submit"
            className="text-[10px] font-mono uppercase tracking-wider px-3 py-1 bg-cyan-500 text-black font-bold rounded hover:bg-cyan-400 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {busy ? "…" : "Add"}
          </button>
        </div>
      )}

      <div className="space-y-2.5" data-testid="weather-widget">
        {allRows.map((w) => {
          const Icon = weatherIcon(w.weather_code);
          const isExtra = w.id?.startsWith?.("extra-");
          return (
            <div key={w.facility_id || w.id} className="group flex items-center justify-between p-2.5 rounded border border-white/5 bg-white/[0.02] hover:border-cyan-500/30 transition-colors">
              <div className="flex items-center gap-3 min-w-0">
                <Icon size={20} className="text-cyan-400 shrink-0" />
                <div className="min-w-0">
                  <div className="text-sm text-white truncate">{w.facility_name}</div>
                  <div className="text-[10px] font-mono text-slate-500">{w.humidity != null ? `${w.humidity}% RH · ` : ""}{w.wind_mph != null ? `${w.wind_mph} mph` : "—"}</div>
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <div className="font-mono text-xl font-bold text-cyan-400 tabular-nums">{w.temperature_f != null ? `${Math.round(w.temperature_f)}°` : "—"}</div>
                {isExtra && (
                  <button
                    onClick={() => removeExtra(w.id)}
                    data-testid={`weather-remove-${w.id}`}
                    className="opacity-0 group-hover:opacity-100 text-slate-500 hover:text-red-400 transition"
                    title="Remove"
                  >
                    ×
                  </button>
                )}
              </div>
            </div>
          );
        })}
        {allRows.length === 0 && <div className="text-xs text-slate-500 italic py-3 text-center">No facilities configured.</div>}
      </div>
    </Card>
  );
}
