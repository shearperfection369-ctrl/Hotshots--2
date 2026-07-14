import React, { useCallback, useEffect, useRef, useState } from "react";
import { MapContainer, TileLayer, Marker, Popup } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import Topbar from "@/components/Topbar";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Radio, RefreshCw, Loader2, Truck, DollarSign, ShieldAlert, CheckCircle2,
} from "lucide-react";
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip } from "recharts";

const fmt = (n) => (n == null ? "—" : Number(n).toLocaleString(undefined, { maximumFractionDigits: 0 }));

const truckIcon = (delayed) => L.divIcon({
  className: "",
  html: `<div style="background:${delayed ? "#ef4444" : "#34d399"};border:2px solid #0b1320;border-radius:50%;width:16px;height:16px;display:flex;align-items:center;justify-content:center;box-shadow:0 0 8px ${delayed ? "#ef444488" : "#34d39988"}"><span style="font-size:8px">🚛</span></div>`,
  iconSize: [16, 16], iconAnchor: [8, 8],
});

function Stat({ label, value, accent = "text-emerald-300", tid }) {
  return (
    <div className="rounded border border-white/10 bg-white/[0.03] px-3 py-2 min-w-[118px]" data-testid={tid}>
      <div className={`font-mono font-bold text-base ${accent}`}>{value}</div>
      <div className="text-[9px] font-mono uppercase tracking-[0.15em] text-slate-500">{label}</div>
    </div>
  );
}

export default function LiveOps() {
  const [state, setState] = useState(null);
  const [loading, setLoading] = useState(true);
  const timerRef = useRef(null);

  const refresh = useCallback(async () => {
    try { const { data } = await api.get("/live-ops/state"); setState(data); }
    catch {}
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    refresh();
    timerRef.current = setInterval(refresh, 15000);
    return () => clearInterval(timerRef.current);
  }, [refresh]);

  const k = state?.kpis || {};
  const transits = state?.transits || [];

  return (
    <>
      <Topbar title="Live Ops Command" />
      <div className="p-6 max-w-[1500px] mx-auto space-y-4" data-testid="live-ops-page">
        <Card className="hud-surface p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-emerald-400 flex items-center gap-1.5">
                <Radio size={11} className="animate-pulse" /> Live Production Operations · Real bookings only (samples excluded)
              </div>
              <div className="font-display text-2xl font-black" data-testid="live-ops-title">
                Today &amp; Trailing 7 Days
              </div>
              <div className="text-[10px] font-mono text-slate-500 mt-0.5">
                As of {state?.as_of ? new Date(state.as_of).toLocaleString() : "—"} · auto-refreshes every 15s
              </div>
            </div>
            <Button size="sm" variant="ghost" onClick={refresh} data-testid="live-ops-refresh-btn"
              className="border border-white/10 text-slate-300 font-mono text-[10px] uppercase">
              {loading ? <Loader2 size={12} className="mr-1 animate-spin" /> : <RefreshCw size={12} className="mr-1" />} Refresh
            </Button>
          </div>
          <div className="flex flex-wrap gap-2 mt-4" data-testid="live-ops-kpis">
            <Stat label="Loads Today" value={fmt(k.today_loads)} accent="text-cyan-300" tid="live-kpi-today-loads" />
            <Stat label="Revenue Today" value={`$${fmt(k.today_revenue)}`} tid="live-kpi-today-revenue" />
            <Stat label="Margin Today" value={`$${fmt(k.today_margin)}`} accent="text-yellow-300" tid="live-kpi-today-margin" />
            <Stat label="Avg Loads / Day" value={k.avg_daily_loads ?? "—"} accent="text-cyan-300" tid="live-kpi-avg-daily" />
            <Stat label="Loads · 7D" value={fmt(k.week_loads)} accent="text-slate-300" />
            <Stat label="Revenue · 7D" value={`$${fmt(k.week_revenue)}`} />
            <Stat label="Margin · 7D" value={`$${fmt(k.week_margin)}`} accent="text-yellow-300" tid="live-kpi-week-margin" />
            <Stat label="In Transit" value={fmt(k.in_transit)} accent="text-emerald-300" />
            <Stat label="AR Outstanding" value={`$${fmt(k.ar_outstanding)}`} accent="text-orange-300" tid="live-kpi-ar" />
            <Stat label="AR Past Due" value={`$${fmt(k.ar_past_due)}`} accent="text-red-300" />
            <Stat label="Cash Collected · 7D" value={`$${fmt(k.cash_collected_week)}`} />
          </div>
        </Card>

        <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
          <Card className="hud-surface p-0 overflow-hidden xl:col-span-2" style={{ height: 440 }} data-testid="live-ops-map">
            <MapContainer center={[39.5, -96.5]} zoom={4} style={{ height: "100%", width: "100%" }} scrollWheelZoom>
              <TileLayer url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
                attribution="&copy; OpenStreetMap &copy; CARTO" />
              {transits.map((t) => {
                const loc = t.current_location || {};
                if (loc.lat == null || loc.lng == null) return null;
                return (
                  <Marker key={t.shipment_id || t.reference} position={[loc.lat, loc.lng]} icon={truckIcon(t.status === "delayed")}>
                    <Popup>
                      <div style={{ fontFamily: "monospace", fontSize: 11 }}>
                        <b>{t.reference || t.shipment_id}</b> · {t.status}<br />
                        {typeof t.origin === "string" ? t.origin : t.origin?.city} → {typeof t.destination === "string" ? t.destination : t.destination?.city}<br />
                        {t.carrier} {t.progress != null && <>· {Math.round((t.progress || 0) * 100)}%</>}
                        {t.eta && <><br />ETA {t.eta}</>}
                      </div>
                    </Popup>
                  </Marker>
                );
              })}
            </MapContainer>
          </Card>

          <div className="space-y-4">
            <Card className="hud-surface p-4" data-testid="live-ops-triage">
              <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-red-300 flex items-center gap-1.5 mb-2">
                <ShieldAlert size={12} /> Triage ({(state?.triage || []).length})
              </div>
              <div className="space-y-2 max-h-36 overflow-y-auto">
                {(state?.triage || []).length === 0 && (
                  <div className="text-[10px] font-mono text-slate-500 flex items-center gap-1.5">
                    <CheckCircle2 size={11} className="text-emerald-400" /> Nothing needs your attention.
                  </div>
                )}
                {(state?.triage || []).map((t, i) => (
                  <div key={i} className="p-2 rounded border border-red-500/20 bg-red-500/[0.04]">
                    <div className="text-[11px] text-slate-200">{t.title}</div>
                    <div className="text-[9px] font-mono text-slate-400 mt-1">{t.action}</div>
                  </div>
                ))}
              </div>
            </Card>
            <Card className="hud-surface p-4" data-testid="live-ops-feed">
              <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-emerald-400 mb-2">Live Activity Feed</div>
              <div className="space-y-1 max-h-56 overflow-y-auto">
                {(state?.feed || []).length === 0 && (
                  <div className="text-[10px] font-mono text-slate-500">No production activity in the last 7 days. Book a load and it shows up here instantly.</div>
                )}
                {(state?.feed || []).map((e, i) => (
                  <div key={i} className="text-[10px] font-mono p-1.5 rounded bg-white/[0.02] text-slate-300">
                    <span className="text-slate-600">{e.at ? new Date(e.at).toLocaleString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : ""}</span> {e.message}
                  </div>
                ))}
              </div>
            </Card>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <Card className="hud-surface p-4" data-testid="live-ops-daily-margin">
            <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-emerald-300 mb-2 flex items-center gap-1.5">
              <DollarSign size={12} /> Margin By Day (Real)
            </div>
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={state?.daily || []}>
                <XAxis dataKey="date" tick={{ fill: "#64748b", fontSize: 9 }} tickFormatter={(d) => d?.slice(5)} />
                <YAxis tick={{ fill: "#64748b", fontSize: 9 }} tickFormatter={(v) => `$${v / 1000}k`} width={40} />
                <Tooltip contentStyle={{ background: "#0b1320", border: "1px solid rgba(255,255,255,0.1)", fontSize: 11 }} />
                <Bar dataKey="margin" fill="#34d399" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Card>
          <Card className="hud-surface p-4" data-testid="live-ops-daily-loads">
            <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-300 mb-2 flex items-center gap-1.5">
              <Truck size={12} /> Loads By Day (Real)
            </div>
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={state?.daily || []}>
                <XAxis dataKey="date" tick={{ fill: "#64748b", fontSize: 9 }} tickFormatter={(d) => d?.slice(5)} />
                <YAxis tick={{ fill: "#64748b", fontSize: 9 }} allowDecimals={false} width={30} />
                <Tooltip contentStyle={{ background: "#0b1320", border: "1px solid rgba(255,255,255,0.1)", fontSize: 11 }} />
                <Bar dataKey="loads" fill="#22d3ee" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Card>
        </div>
      </div>
    </>
  );
}
