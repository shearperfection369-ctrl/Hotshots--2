import React, { useEffect, useState } from "react";
import Topbar from "../components/Topbar";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Switch } from "../components/ui/switch";
import {
  Activity, Database, Users, MessageSquare, Truck, Cpu, Server, Clock, Sparkles,
  Bell, CloudRain, RefreshCw, Plug, ShieldCheck, TrendingUp, ChevronRight,
  Zap, Palette
} from "lucide-react";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useBranding } from "../lib/branding";
import { Navigate, Link } from "react-router-dom";
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, BarChart, Bar, CartesianGrid } from "recharts";
import { toast } from "sonner";
import CompanyTheme from "../components/CompanyTheme";
import ERPManager from "../components/ERPManager";
import LegalCompliance from "../components/LegalCompliance";

/**
 * AdminDashboard — system-of-systems control deck for the admin.
 * Surfaces health, throughput, user activity, LLM usage, the active brand,
 * the active ERP connection, recent activity, and one-tap quick toggles for
 * the highest-traffic settings.
 */
export default function AdminDashboard() {
  const { user } = useAuth();
  const { brand } = useBranding();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshAt, setRefreshAt] = useState(Date.now());

  const load = async () => {
    try {
      const { data } = await api.get("/admin/dashboard");
      setData(data);
      setRefreshAt(Date.now());
    } catch (e) {
      toast.error("Failed to load admin dashboard");
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); const t = setInterval(load, 30000); return () => clearInterval(t); }, []);

  if (user && user.role !== "admin") return <Navigate to="/dashboard" replace />;

  const toggle = async (key, value) => {
    try {
      await api.post("/admin/dashboard/quick-toggle", { key, value });
      setData((d) => ({ ...d, settings: { ...(d?.settings || {}), [key]: value } }));
      toast.success(`${key.replace(/_/g, " ")} ${value ? "enabled" : "disabled"}`);
    } catch { toast.error("Toggle failed"); }
  };

  const sys = data?.system || {};
  const counts = data?.counts || {};
  const users = data?.users || {};
  const llm = data?.llm || {};
  const ships = data?.shipments || {};
  const settings = data?.settings || {};
  const audit = data?.recent_audit || [];

  return (
    <>
      <Topbar title="Admin Control Deck" subtitle="System health · user activity · LLM usage · feature toggles · active brand · ERP integrations" />
      <div className="p-4 md:p-6 space-y-6">

        {/* === HERO STATUS BAR === */}
        <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-8 gap-3" data-testid="admin-status-bar">
          <StatusPill ok={sys.db_ok} label="Database" value={sys.db_ok ? `${sys.db_ping_ms}ms` : "OFFLINE"} Icon={Database} />
          <StatusPill ok={true} label="Uptime" value={sys.uptime_human || "—"} Icon={Clock} />
          <StatusPill ok={(users.active_24h ?? 0) > 0} label="Active · 24h" value={users.active_24h ?? 0} Icon={Users} />
          <StatusPill ok={true} label="Active · 7d" value={users.active_7d ?? 0} Icon={TrendingUp} />
          <StatusPill ok={true} label="Shipments" value={ships.total ?? 0} Icon={Truck} />
          <StatusPill ok={true} label="LLM · 24h" value={llm.messages_24h ?? 0} Icon={MessageSquare} />
          <StatusPill ok={true} label="Brand" value={data?.brand?.active?.short_name || "—"} Icon={Palette} accent={data?.brand?.active?.primary_color} />
          <StatusPill ok={!!data?.erp?.active} label="ERP" value={data?.erp?.active?.erp_name || "Not Linked"} Icon={Plug} />
        </div>

        {/* === MAIN GRID === */}
        <div className="grid grid-cols-1 xl:grid-cols-12 gap-5">

          {/* Shipment volume trend */}
          <Card className="hud-surface p-5 xl:col-span-8" data-testid="admin-shipment-trend">
            <div className="flex items-center justify-between mb-3">
              <div>
                <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400">Shipment Volume · 14d</div>
                <h3 className="text-base font-display font-bold text-white">Daily Throughput</h3>
              </div>
              <button onClick={load} disabled={loading} className="text-[10px] font-mono uppercase text-slate-400 hover:text-cyan-300 flex items-center gap-1.5" data-testid="admin-refresh">
                <RefreshCw size={11} className={loading ? "animate-spin" : ""} /> Refresh
              </button>
            </div>
            <div style={{ height: 220 }}>
              <ResponsiveContainer>
                <AreaChart data={ships.trend_14d || []}>
                  <defs>
                    <linearGradient id="cyanFade" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#22D3EE" stopOpacity={0.55} />
                      <stop offset="100%" stopColor="#22D3EE" stopOpacity={0.04} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="#1F2937" strokeDasharray="2 4" />
                  <XAxis dataKey="date" stroke="#64748B" fontSize={10} fontFamily="monospace" />
                  <YAxis stroke="#64748B" fontSize={10} fontFamily="monospace" allowDecimals={false} />
                  <Tooltip contentStyle={{ background: "#0B0E14", border: "1px solid rgba(34,211,238,0.3)", borderRadius: 6, fontFamily: "monospace", fontSize: 11 }} />
                  <Area dataKey="count" stroke="#22D3EE" fill="url(#cyanFade)" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </Card>

          {/* Quick toggles */}
          <Card className="hud-surface p-5 xl:col-span-4" data-testid="admin-quick-toggles">
            <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-1">Feature Switches</div>
            <h3 className="text-base font-display font-bold text-white mb-4 flex items-center gap-2"><Zap size={14} className="text-cyan-400" /> Quick Toggles</h3>
            <div className="space-y-3">
              <ToggleRow Icon={Bell} label="Wellness Nudges" hint="In-app stretch / hydrate reminders" value={!!settings.wellness_nudges_enabled} onChange={(v) => toggle("wellness_nudges_enabled", v)} />
              <ToggleRow Icon={CloudRain} label="Weather Alerts Banner" hint="NWS storm advisories on dashboard" value={settings.weather_alerts_enabled !== false} onChange={(v) => toggle("weather_alerts_enabled", v)} />
              <ToggleRow Icon={Sparkles} label="HUDLINK AI" hint="Show the AI Co-Pilot in the sidebar" value={settings.hudlink_enabled !== false} onChange={(v) => toggle("hudlink_enabled", v)} />
              <ToggleRow Icon={ShieldCheck} label="Audit Logging" hint="Record every admin action" value={settings.audit_enabled !== false} onChange={(v) => toggle("audit_enabled", v)} />
              <ToggleRow Icon={Activity} label="Auto-Refresh Tracking" hint="Live map polls every 30 s" value={settings.auto_refresh_tracking !== false} onChange={(v) => toggle("auto_refresh_tracking", v)} />
            </div>
            <div className="mt-4 pt-3 border-t border-white/5 text-[10px] font-mono text-slate-500">
              Last refresh {new Date(refreshAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })} · auto every 30s
            </div>
          </Card>

          {/* Collections heat-bar */}
          <Card className="hud-surface p-5 xl:col-span-8" data-testid="admin-collections">
            <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-1">Data Volume</div>
            <h3 className="text-base font-display font-bold text-white mb-4 flex items-center gap-2"><Database size={14} className="text-cyan-400" /> Collection Totals</h3>
            <div style={{ height: 220 }}>
              <ResponsiveContainer>
                <BarChart data={Object.entries(counts).map(([k, v]) => ({ name: k, count: v })).filter(d => d.count > 0).sort((a, b) => b.count - a.count).slice(0, 12)}>
                  <CartesianGrid stroke="#1F2937" strokeDasharray="2 4" />
                  <XAxis dataKey="name" stroke="#64748B" fontSize={9} fontFamily="monospace" angle={-25} dy={6} height={50} />
                  <YAxis stroke="#64748B" fontSize={10} fontFamily="monospace" />
                  <Tooltip contentStyle={{ background: "#0B0E14", border: "1px solid rgba(34,211,238,0.3)", borderRadius: 6, fontFamily: "monospace", fontSize: 11 }} />
                  <Bar dataKey="count" fill="#22D3EE" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>

          {/* Recent audit */}
          <Card className="hud-surface p-5 xl:col-span-4" data-testid="admin-recent-audit">
            <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-1">Audit Trail</div>
            <h3 className="text-base font-display font-bold text-white mb-3 flex items-center gap-2"><ShieldCheck size={14} className="text-cyan-400" /> Recent Activity</h3>
            <div className="space-y-2 max-h-[400px] overflow-y-auto pr-1">
              {audit.length === 0 && <div className="text-xs text-slate-500 italic py-4">No audit events yet.</div>}
              {audit.map((a, i) => (
                <div key={i} className="text-[11px] border-l-2 border-cyan-500/30 pl-2 py-1">
                  <div className="font-mono text-cyan-300">{a.action || "event"}</div>
                  <div className="text-slate-400 truncate">{a.actor_name || a.actor || "system"}</div>
                  <div className="text-[9px] text-slate-500 font-mono">{a.at ? new Date(a.at).toLocaleString() : ""}</div>
                </div>
              ))}
            </div>
          </Card>

          {/* User roles */}
          <Card className="hud-surface p-5 xl:col-span-4" data-testid="admin-roles">
            <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-1">User Mix</div>
            <h3 className="text-base font-display font-bold text-white mb-3 flex items-center gap-2"><Users size={14} className="text-cyan-400" /> Role Breakdown</h3>
            <div className="space-y-2.5">
              {Object.entries(users.role_breakdown || {}).map(([role, n]) => {
                const max = Math.max(...Object.values(users.role_breakdown || { x: 1 }));
                return (
                  <div key={role}>
                    <div className="flex justify-between text-[11px] font-mono mb-0.5">
                      <span className="text-slate-300 uppercase">{role}</span>
                      <span className="text-cyan-300 tabular-nums">{n}</span>
                    </div>
                    <div className="h-1.5 bg-white/5 rounded overflow-hidden">
                      <div className="h-full bg-gradient-to-r from-cyan-500 to-emerald-500" style={{ width: `${(n / max) * 100}%` }} />
                    </div>
                  </div>
                );
              })}
              {Object.keys(users.role_breakdown || {}).length === 0 && <div className="text-xs text-slate-500 italic">No users yet.</div>}
            </div>
          </Card>

          {/* LLM usage card */}
          <Card className="hud-surface p-5 xl:col-span-4" data-testid="admin-llm">
            <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-1">AI Co-Pilot</div>
            <h3 className="text-base font-display font-bold text-white mb-3 flex items-center gap-2"><Cpu size={14} className="text-cyan-400" /> LLM Usage</h3>
            <div className="grid grid-cols-2 gap-3">
              <Metric label="Messages · all-time" value={llm.total_messages ?? 0} />
              <Metric label="Messages · 24h" value={llm.messages_24h ?? 0} accent="text-emerald-300" />
            </div>
            <Link to="/hudlink" data-testid="admin-llm-open" className="mt-4 inline-flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider text-cyan-300 hover:text-cyan-200">
              Open HUDLINK · <ChevronRight size={11} />
            </Link>
          </Card>

          {/* Backend tile */}
          <Card className="hud-surface p-5 xl:col-span-4" data-testid="admin-backend">
            <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-1">Backend</div>
            <h3 className="text-base font-display font-bold text-white mb-3 flex items-center gap-2"><Server size={14} className="text-cyan-400" /> API Status</h3>
            <div className="space-y-2 font-mono text-xs">
              <Row k="DB Ping" v={sys.db_ok ? `${sys.db_ping_ms} ms` : "DOWN"} ok={sys.db_ok} />
              <Row k="Uptime" v={sys.uptime_human} />
              <Row k="Boot At" v={sys.boot_at ? new Date(sys.boot_at).toLocaleString() : "—"} small />
              <Row k="Active Brand" v={brand?.company_name || "—"} small />
              <Row k="Custom Brands" v={data?.brand?.custom_count ?? 0} />
            </div>
          </Card>

        </div>

        {/* === COMPANY THEME === */}
        <div className="grid grid-cols-1 gap-5">
          <CompanyTheme />
          <ERPManager active={data?.erp?.active} onChange={load} />
          <LegalCompliance />
        </div>

      </div>
    </>
  );
}

function StatusPill({ ok, label, value, Icon, accent }) {
  return (
    <Card className="hud-surface p-3 relative overflow-hidden" data-testid={`admin-pill-${label.toLowerCase().replace(/\W/g, "-")}`}>
      <div className={`absolute left-0 top-0 bottom-0 w-0.5 ${ok ? "bg-cyan-400" : "bg-red-400"}`} />
      <div className="flex items-center gap-2 mb-1">
        <Icon size={11} className={ok ? "text-cyan-400" : "text-red-400"} />
        <div className="text-[9px] font-mono uppercase tracking-[0.18em] text-slate-400">{label}</div>
      </div>
      <div className="text-base font-display font-bold text-white truncate tabular-nums flex items-center gap-1.5">
        {accent && <span className="inline-block w-2 h-2 rounded-full" style={{ background: accent }} />}
        {value}
      </div>
    </Card>
  );
}

function ToggleRow({ Icon, label, hint, value, onChange }) {
  return (
    <div className="flex items-start gap-3" data-testid={`toggle-${label.toLowerCase().replace(/\s+/g, "-")}`}>
      <div className="p-1.5 rounded bg-cyan-500/10 border border-cyan-500/20 mt-0.5"><Icon size={11} className="text-cyan-400" /></div>
      <div className="flex-1 min-w-0">
        <div className="text-xs font-bold text-white">{label}</div>
        <div className="text-[10px] text-slate-500">{hint}</div>
      </div>
      <Switch checked={value} onCheckedChange={onChange} />
    </div>
  );
}

function Metric({ label, value, accent = "text-cyan-300" }) {
  return (
    <div className="p-2.5 rounded bg-white/[0.02] border border-white/5">
      <div className="text-[9px] font-mono uppercase tracking-[0.18em] text-slate-500">{label}</div>
      <div className={`text-xl font-display font-bold tabular-nums ${accent} mt-0.5`}>{value}</div>
    </div>
  );
}

function Row({ k, v, ok = null, small = false }) {
  return (
    <div className="flex justify-between gap-2">
      <span className="text-slate-400">{k}</span>
      <span className={`${ok === false ? "text-red-300" : ok === true ? "text-emerald-300" : "text-cyan-300"} truncate ${small ? "text-[10px]" : ""}`}>{v}</span>
    </div>
  );
}
