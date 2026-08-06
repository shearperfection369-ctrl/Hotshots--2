import React, { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { api } from "../../lib/api";
import { Card } from "../ui/card";
import { MapPin, KeyRound, Megaphone, Trash2, RefreshCw, Clock, Zap, FileDown, BadgeDollarSign, Trophy, Star } from "lucide-react";
import { MapContainer, TileLayer, Marker, Popup } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import MapErrorBoundary from "../MapErrorBoundary";

const crewIcon = (on) => L.divIcon({
  className: "",
  html: `<div style="width:16px;height:16px;border-radius:9999px;background:${on ? "#34D399" : "#64748B"};border:3px solid #0B0E14;box-shadow:0 0 10px ${on ? "#34D399" : "#64748B"}"></div>`,
  iconSize: [16, 16], iconAnchor: [8, 8],
});

export const TcCrewLive = () => {
  const [live, setLive] = useState(null);
  const [sheets, setSheets] = useState(null);
  const [updates, setUpdates] = useState([]);
  const [uForm, setUForm] = useState({ title: "", body: "", pinned: false });
  const [pinFor, setPinFor] = useState(null);
  const [routing, setRouting] = useState(false);
  const [routeResult, setRouteResult] = useState(null);
  const [payroll, setPayroll] = useState(null);
  const [board, setBoard] = useState(null);

  const load = useCallback(() => {
    api.get("/truck-cleaning/crew-live").then(({ data }) => setLive(data)).catch(() => {});
    api.get("/truck-cleaning/timesheets").then(({ data }) => setSheets(data)).catch(() => {});
    api.get("/truck-cleaning/updates").then(({ data }) => setUpdates(data.updates || [])).catch(() => {});
    api.get("/truck-cleaning/payroll").then(({ data }) => setPayroll(data)).catch(() => {});
    api.get("/truck-cleaning/scoreboard").then(({ data }) => setBoard(data)).catch(() => {});
  }, []);
  useEffect(() => { load(); const t = setInterval(load, 30000); return () => clearInterval(t); }, [load]);

  const autoAssign = async () => {
    setRouting(true);
    try {
      const { data } = await api.post("/truck-cleaning/router/auto-assign", {});
      setRouteResult(data);
      data.assigned.length ? toast.success(data.message) : toast.info(data.message);
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Routing failed"); }
    finally { setRouting(false); }
  };

  const exportPayroll = async () => {
    try {
      const r = await api.get("/truck-cleaning/payroll.csv", { responseType: "blob" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(r.data);
      a.download = `Orisei-Payroll-${payroll?.period_start || "week"}.csv`;
      a.click();
      URL.revokeObjectURL(a.href);
      toast.success("Payroll CSV downloaded");
    } catch { toast.error("Export failed"); }
  };

  const genPin = async (tech) => {
    try {
      const { data } = await api.post(`/truck-cleaning/crew-admin/${tech.tech_id}/pin`);
      setPinFor({ name: tech.name, pin: data.pin });
      load();
    } catch (e) { toast.error("Couldn't generate PIN"); }
  };
  const postUpdate = async () => {
    if (!uForm.title) { toast.error("Update needs a title"); return; }
    try {
      await api.post("/truck-cleaning/updates", uForm);
      toast.success("Update posted to all crews");
      setUForm({ title: "", body: "", pinned: false });
      load();
    } catch { toast.error("Post failed"); }
  };
  const delUpdate = async (id) => {
    try { await api.delete(`/truck-cleaning/updates/${id}`); load(); } catch { toast.error("Delete failed"); }
  };

  if (!live) return <div className="text-slate-500 font-mono text-sm">Loading crew live board…</div>;
  const pinned = live.crews.filter((c) => c.ping);
  return (
    <div className="space-y-4" data-testid="tc-crew-live">
      {pinFor && (
        <div className="p-4 rounded-2xl border border-amber-500/50 bg-amber-500/10 flex items-center justify-between" data-testid="tc-pin-reveal">
          <div className="text-sm text-amber-200">
            New PIN for <b>{pinFor.name}</b>: <span className="font-black text-2xl tracking-[0.3em] text-amber-300 ml-2">{pinFor.pin}</span>
            <span className="block text-[10px] font-mono text-amber-400/70 mt-1">Shown once — text it to them now. Crew portal: /crew</span>
          </div>
          <button onClick={() => setPinFor(null)} className="text-xs text-slate-400" data-testid="tc-pin-dismiss">Dismiss</button>
        </div>
      )}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <button onClick={autoAssign} disabled={routing} data-testid="tc-auto-assign-btn"
          className="px-5 py-2.5 rounded-full bg-amber-500 text-black font-black text-xs inline-flex items-center gap-1.5 disabled:opacity-50">
          <Zap size={14} /> {routing ? "ROUTING…" : "AUTO-ASSIGN TODAY'S JOBS"}
        </button>
        <span className="text-[10px] font-mono text-slate-500">One tap — unassigned jobs get routed by crew workload, yard distance & clock status</span>
      </div>
      {routeResult && routeResult.assigned.length > 0 && (
        <div className="p-4 rounded-2xl border border-amber-500/30 bg-amber-500/[0.04]" data-testid="tc-route-result">
          <div className="text-xs font-bold text-amber-300 mb-2">{routeResult.message}</div>
          <div className="space-y-1">
            {routeResult.assigned.map((r) => (
              <div key={r.job_id} className="flex items-center justify-between text-[11px] font-mono">
                <span className="text-slate-300">{r.company} · {r.cabs} cab{r.cabs > 1 ? "s" : ""} <span className="text-slate-600">({r.est_minutes}m)</span></span>
                <span className="text-emerald-300">→ {r.tech_name}{r.distance_mi != null ? ` · ${r.distance_mi} mi away` : ""}</span>
              </div>
            ))}
          </div>
        </div>
      )}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[["Crews on the clock", live.clocked_in, "#34D399"], ["Total crews", live.crews.length, "#22D3EE"],
          ["Hours this week", sheets?.total_hours ?? "—", "#F59E0B"], ["Labor cost (wk)", sheets ? `$${sheets.labor_cost.toLocaleString()}` : "—", "#F87171"]].map(([l, v, c]) => (
          <div key={l} className="p-3 rounded-2xl border border-white/10 bg-slate-950/70">
            <div className="text-xl font-black tabular-nums" style={{ color: c }}>{v}</div>
            <div className="text-[9px] font-mono uppercase tracking-wider text-slate-500 mt-0.5">{l}</div>
          </div>
        ))}
      </div>

      <Card className="p-4 bg-slate-950/70 border-white/10" data-testid="tc-crew-map-card">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-bold text-white flex items-center gap-2"><MapPin size={14} className="text-emerald-400" /> Live Crew Map — geo pings while clocked in</h3>
          <button onClick={load} className="text-slate-500 hover:text-white" data-testid="tc-crew-live-refresh"><RefreshCw size={13} /></button>
        </div>
        <div className="rounded-xl overflow-hidden border border-white/10" style={{ height: 340 }} data-testid="tc-crew-map">
          <MapErrorBoundary>
            <MapContainer center={[44.9537, -93.09]} zoom={10} style={{ height: "100%", width: "100%", background: "#0B0E14" }} scrollWheelZoom>
              <TileLayer attribution='© OpenStreetMap © CARTO' url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png" />
              {pinned.map((c) => (
                <Marker key={c.tech_id} position={[c.ping.lat, c.ping.lng]} icon={crewIcon(c.clocked_in)}>
                  <Popup>
                    <div style={{ fontFamily: "monospace", fontSize: 12 }}>
                      <b>{c.name}</b> · {c.role}<br />
                      {c.clocked_in ? "ON THE CLOCK" : "off clock"}<br />
                      jobs today: {c.jobs_done_today}/{c.jobs_today}<br />
                      ping: {new Date(c.ping.at).toLocaleTimeString()}
                    </div>
                  </Popup>
                </Marker>
              ))}
            </MapContainer>
          </MapErrorBoundary>
        </div>
        {!pinned.length && <div className="text-[11px] text-slate-500 mt-2">No pings yet — crews appear here automatically once they clock in on their phones at <b>/crew</b>.</div>}
      </Card>

      <div className="grid lg:grid-cols-2 gap-4">
        <Card className="p-4 bg-slate-950/70 border-white/10" data-testid="tc-crew-roster">
          <h3 className="text-sm font-bold text-white mb-3 flex items-center gap-2"><KeyRound size={14} className="text-amber-400" /> Crew Roster & PINs</h3>
          <div className="space-y-2 max-h-[340px] overflow-y-auto">
            {live.crews.map((c) => (
              <div key={c.tech_id} className="p-3 rounded-xl border border-white/10 bg-white/[0.02] flex items-center justify-between" data-testid={`tc-crew-row-${c.tech_id}`}>
                <div>
                  <div className="text-sm text-white font-semibold flex items-center gap-2">
                    {c.name}
                    <span className={`w-2 h-2 rounded-full ${c.clocked_in ? "bg-emerald-400" : "bg-slate-600"}`} />
                  </div>
                  <div className="text-[10px] font-mono text-slate-500">{c.role} · jobs {c.jobs_done_today}/{c.jobs_today}{c.in_at ? ` · in since ${new Date(c.in_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}` : ""}</div>
                </div>
                <button onClick={() => genPin(c)} data-testid={`tc-gen-pin-${c.tech_id}`}
                  className={`px-3 py-1.5 rounded-full text-[10px] font-bold border ${c.has_pin ? "border-white/15 text-slate-400" : "border-amber-500/50 text-amber-300"}`}>
                  {c.has_pin ? "RESET PIN" : "ISSUE PIN"}
                </button>
              </div>
            ))}
          </div>
        </Card>

        <Card className="p-4 bg-slate-950/70 border-white/10" data-testid="tc-updates-panel">
          <h3 className="text-sm font-bold text-white mb-3 flex items-center gap-2"><Megaphone size={14} className="text-cyan-300" /> Company Updates (pushed to crew phones)</h3>
          <div className="space-y-2 mb-3">
            <input value={uForm.title} onChange={(e) => setUForm({ ...uForm, title: e.target.value })} placeholder="Update title — e.g. New yard: Ryder Roseville starts Monday"
              className="w-full h-10 px-3 rounded-xl bg-[#11151F] border border-white/10 text-sm text-white outline-none" data-testid="tc-update-title" />
            <textarea value={uForm.body} onChange={(e) => setUForm({ ...uForm, body: e.target.value })} placeholder="Details (optional)"
              className="w-full min-h-[60px] p-3 rounded-xl bg-[#11151F] border border-white/10 text-sm text-white outline-none" data-testid="tc-update-body" />
            <div className="flex items-center justify-between">
              <label className="flex items-center gap-2 text-xs text-slate-400">
                <input type="checkbox" checked={uForm.pinned} onChange={(e) => setUForm({ ...uForm, pinned: e.target.checked })} data-testid="tc-update-pinned" /> Pin to top
              </label>
              <button onClick={postUpdate} className="px-4 py-2 rounded-full bg-cyan-500 text-black text-xs font-black" data-testid="tc-update-post-btn">POST UPDATE</button>
            </div>
          </div>
          <div className="space-y-2 max-h-[200px] overflow-y-auto">
            {updates.map((u) => (
              <div key={u.update_id} className="p-2.5 rounded-lg border border-white/10 bg-white/[0.02] flex items-start justify-between gap-2">
                <div>
                  <div className="text-xs text-white font-semibold">{u.pinned && "📌 "}{u.title}</div>
                  {u.body && <div className="text-[10px] text-slate-500 mt-0.5">{u.body.slice(0, 120)}</div>}
                </div>
                <button onClick={() => delUpdate(u.update_id)} className="text-red-400/70 hover:text-red-300" data-testid={`tc-update-del-${u.update_id}`}><Trash2 size={12} /></button>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <Card className="p-4 bg-slate-950/70 border-white/10" data-testid="tc-scoreboard">
        <h3 className="text-sm font-bold text-white mb-3 flex items-center gap-2"><Trophy size={14} className="text-amber-400" /> Crew Scoreboard — last 30 days (crews see this on their phones)</h3>
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-2">
          {(board?.rows || []).map((r) => (
            <div key={r.tech_id} className={`p-3 rounded-xl border ${r.rank === 1 ? "border-amber-500/40 bg-amber-500/[0.06]" : "border-white/10 bg-white/[0.02]"}`} data-testid={`tc-score-${r.tech_id}`}>
              <div className="flex items-center justify-between">
                <div className="text-xs font-bold text-white">{r.rank === 1 ? "🥇 " : r.rank === 2 ? "🥈 " : r.rank === 3 ? "🥉 " : `#${r.rank} `}{r.name}</div>
                <span className="text-sm font-black text-amber-300">{r.score}</span>
              </div>
              <div className="text-[10px] font-mono text-slate-500 mt-1">{r.jobs_done} jobs · {r.cabs} cabs · {r.upsells} add-ons</div>
              <div className="flex gap-0.5 mt-1">
                {[1, 2, 3, 4, 5].map((s) => <Star key={s} size={9} className={s <= r.photo_stars ? "text-cyan-300 fill-cyan-300" : "text-slate-700"} />)}
                <span className="text-[9px] font-mono text-slate-600 ml-1">{r.avg_photos} photos/job</span>
              </div>
            </div>
          ))}
        </div>
      </Card>

      <Card className="p-4 bg-slate-950/70 border-white/10" data-testid="tc-payroll">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-bold text-white flex items-center gap-2"><BadgeDollarSign size={14} className="text-emerald-400" /> Payroll — {payroll ? `${payroll.period_start} → ${payroll.period_end}` : "last 7 days"}</h3>
          <button onClick={exportPayroll} data-testid="tc-payroll-export-btn"
            className="px-4 py-2 rounded-full bg-emerald-500 text-black text-[10px] font-black inline-flex items-center gap-1.5">
            <FileDown size={12} /> EXPORT PAYROLL CSV
          </button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead><tr className="text-left text-[10px] font-mono uppercase text-slate-500 border-b border-white/10">
              <th className="py-2 pr-3">Crew</th><th className="py-2 pr-3">Role</th><th className="py-2 pr-3">Rate</th><th className="py-2 pr-3">Shifts</th><th className="py-2 pr-3">Hours</th><th className="py-2">Gross Pay</th></tr></thead>
            <tbody>
              {(payroll?.rows || []).map((r) => (
                <tr key={r.tech_id} className="border-b border-white/5" data-testid={`tc-payroll-row-${r.tech_id}`}>
                  <td className="py-1.5 pr-3 text-slate-100">{r.name}{r.open_shift && <span className="ml-1.5 text-[8px] font-mono text-emerald-400">ON CLOCK</span>}</td>
                  <td className="py-1.5 pr-3 font-mono text-slate-500 uppercase">{r.role}</td>
                  <td className="py-1.5 pr-3 font-mono text-slate-400">${r.hourly_rate}/h</td>
                  <td className="py-1.5 pr-3 font-mono text-slate-400">{r.shifts}</td>
                  <td className="py-1.5 pr-3 font-mono text-amber-300">{r.hours}</td>
                  <td className="py-1.5 font-black text-emerald-300">${r.gross_pay.toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
            {payroll && (
              <tfoot><tr className="border-t border-white/10">
                <td colSpan={4} className="py-2 text-[10px] font-mono uppercase text-slate-500">Period totals</td>
                <td className="py-2 font-black text-amber-300">{payroll.total_hours}</td>
                <td className="py-2 font-black text-emerald-300" data-testid="tc-payroll-total">${payroll.total_gross.toLocaleString()}</td>
              </tr></tfoot>
            )}
          </table>
        </div>
      </Card>

      <Card className="p-4 bg-slate-950/70 border-white/10" data-testid="tc-timesheets">
        <h3 className="text-sm font-bold text-white mb-3 flex items-center gap-2"><Clock size={14} className="text-amber-400" /> Timesheets — last 7 days</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead><tr className="text-left text-[10px] font-mono uppercase text-slate-500 border-b border-white/10">
              <th className="py-2 pr-3">Crew</th><th className="py-2 pr-3">Date</th><th className="py-2 pr-3">In</th><th className="py-2 pr-3">Out</th><th className="py-2">Hours</th></tr></thead>
            <tbody>
              {(sheets?.entries || []).map((e) => (
                <tr key={e.entry_id} className="border-b border-white/5">
                  <td className="py-1.5 pr-3 text-slate-100">{e.tech_name}</td>
                  <td className="py-1.5 pr-3 font-mono text-slate-400">{e.date}</td>
                  <td className="py-1.5 pr-3 font-mono text-slate-400">{new Date(e.in_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</td>
                  <td className="py-1.5 pr-3 font-mono text-slate-400">{e.out_at ? new Date(e.out_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : <span className="text-emerald-400">on clock</span>}</td>
                  <td className="py-1.5 font-mono text-amber-300">{e.hours ?? "—"}</td>
                </tr>
              ))}
              {!(sheets?.entries || []).length && <tr><td colSpan={5} className="py-6 text-center text-slate-500">No clock entries yet.</td></tr>}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
};
