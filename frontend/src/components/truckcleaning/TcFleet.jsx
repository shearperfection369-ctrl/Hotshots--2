import React, { useCallback, useEffect, useState } from "react";
import { Card } from "../ui/card";
import { Truck, Plus, Trash2, Sparkles, Loader2, CheckCircle2, History, Gauge } from "lucide-react";
import { toast } from "sonner";
import { api } from "../../lib/api";

const errTxt = (e) => (typeof e?.response?.data?.detail === "string" ? e.response.data.detail : "Something went wrong");
const STATUS = {
  overdue: { label: "OVERDUE", cls: "border-red-500/60 text-red-400", bar: "#F87171" },
  never_cleaned: { label: "NEVER CLEANED", cls: "border-red-500/60 text-red-400", bar: "#F87171" },
  due_soon: { label: "DUE SOON", cls: "border-amber-500/60 text-amber-300", bar: "#F59E0B" },
  fresh: { label: "FRESH", cls: "border-emerald-500/60 text-emerald-400", bar: "#34D399" },
};

export const TcFleet = ({ clients }) => {
  const [units, setUnits] = useState([]);
  const [fleets, setFleets] = useState([]);
  const [sel, setSel] = useState("");
  const [addOpen, setAddOpen] = useState(false);
  const [form, setForm] = useState({ client_id: "", unit_number: "", make: "", model: "", year: "" });
  const [detail, setDetail] = useState(null);
  const [sched, setSched] = useState(null);
  const [schedBusy, setSchedBusy] = useState(false);

  const load = useCallback(async () => {
    try { const { data } = await api.get("/truck-cleaning/units"); setUnits(data.units); setFleets(data.fleets); } catch (_) {}
  }, []);
  useEffect(() => { load(); }, [load]);

  const add = async (e) => {
    e.preventDefault();
    try { await api.post("/truck-cleaning/units", { ...form, cadence_days: 0, notes: "" }); toast.success("Unit added to registry"); setAddOpen(false); setForm({ client_id: form.client_id, unit_number: "", make: "", model: "", year: "" }); load(); }
    catch (e2) { toast.error(errTxt(e2)); }
  };

  const genSchedule = async () => {
    setSchedBusy(true);
    try { const { data } = await api.get("/truck-cleaning/ai-schedule", { params: { days: 7 }, timeout: 90000 }); setSched(data); }
    catch (e2) { toast.error(errTxt(e2)); }
    finally { setSchedBusy(false); }
  };

  const shown = sel ? units.filter((u) => u.client_id === sel) : units;

  return (
    <div className="space-y-4" data-testid="tc-fleet">
      <div className="flex flex-wrap items-center gap-2">
        <button onClick={() => setSel("")} className={`px-3 py-1.5 rounded-full border text-[11px] font-bold ${!sel ? "border-amber-400 text-amber-300 bg-amber-500/10" : "border-white/15 text-slate-400"}`} data-testid="tc-fleet-all">
          ALL FLEETS ({units.length})
        </button>
        {fleets.map((f) => (
          <button key={f.client_id} onClick={() => setSel(f.client_id)} data-testid={`tc-fleet-pill-${f.client_id}`}
                  className={`px-3 py-1.5 rounded-full border text-[11px] font-bold inline-flex items-center gap-1.5 ${sel === f.client_id ? "border-amber-400 text-amber-300 bg-amber-500/10" : "border-white/15 text-slate-400"}`}>
            <Truck size={11} /> {f.company} · {f.units}
            {f.overdue > 0 && <span className="px-1 rounded bg-red-500/20 text-red-300 text-[9px]">{f.overdue}!</span>}
          </button>
        ))}
        <div className="flex-1" />
        <button onClick={() => { setAddOpen(!addOpen); setForm((x) => ({ ...x, client_id: sel || "" })); }} data-testid="tc-unit-add-btn"
                className="px-4 py-2 rounded-full bg-amber-500 text-black font-bold text-xs inline-flex items-center gap-1.5"><Plus size={13} /> Add Unit</button>
      </div>

      {sel && (() => {
        const f = fleets.find((x) => x.client_id === sel);
        const cl = clients.find((c) => c.client_id === sel);
        if (!f) return null;
        const fresh = f.units - f.overdue - f.due_soon;
        return (
          <div className="grid grid-cols-2 md:grid-cols-6 gap-3" data-testid="tc-fleet-client-metrics">
            {[["Units in fleet", f.units, "#F59E0B"], ["Overdue", f.overdue, "#F87171"], ["Due soon", f.due_soon, "#FBBF24"],
              ["Fresh", fresh, "#34D399"], ["Lifetime cleans", f.total_cleans, "#22D3EE"],
              ["Full-fleet clean", cl ? `$${(f.units * cl.rate).toLocaleString()}` : "—", "#A78BFA"]].map(([l, v, c]) => (
              <div key={l} className="p-3 rounded-2xl border border-white/10 bg-slate-950/70 backdrop-blur">
                <div className="text-lg font-black tabular-nums" style={{ color: c }}>{v}</div>
                <div className="text-[8px] font-mono uppercase tracking-wider text-slate-500 mt-0.5">{l}</div>
              </div>
            ))}
          </div>
        );
      })()}

      {addOpen && (
        <form onSubmit={add} className="p-4 rounded-xl border border-white/10 bg-slate-950/70 flex flex-wrap gap-2 items-center" data-testid="tc-unit-form">
          <select required value={form.client_id} onChange={(e) => setForm({ ...form, client_id: e.target.value })} data-testid="tc-unit-client"
                  className="h-9 rounded-lg bg-slate-950 border border-white/15 px-2 text-xs min-w-[170px]">
            <option value="">Client fleet…</option>
            {clients.map((c) => <option key={c.client_id} value={c.client_id}>{c.company}</option>)}
          </select>
          {[["unit_number", "Unit # *"], ["make", "Make"], ["model", "Model"], ["year", "Year"]].map(([k, ph]) => (
            <input key={k} required={ph.includes("*")} value={form[k]} placeholder={ph} onChange={(e) => setForm({ ...form, [k]: e.target.value })}
                   data-testid={`tc-unit-${k}`} className="h-9 rounded-lg bg-slate-950 border border-white/15 px-2.5 text-xs w-28 outline-none focus:border-amber-400" />
          ))}
          <button type="submit" data-testid="tc-unit-save" className="h-9 px-5 rounded-full bg-amber-500 text-black font-bold text-xs">Save</button>
        </form>
      )}

      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {shown.map((u) => {
          const m = u.metrics; const st = STATUS[m.status] || STATUS.fresh;
          const pct = m.days_since == null ? 100 : Math.min(100, Math.round((m.days_since / m.cadence_days) * 100));
          return (
            <button key={u.unit_id} onClick={() => setDetail(u)} data-testid={`tc-unit-card-${u.unit_id}`}
                    className="text-left p-4 rounded-2xl border border-white/10 bg-slate-950/70 backdrop-blur hover:border-amber-400/50 transition group">
              <div className="flex justify-between items-start mb-1">
                <div className="font-black text-white">{u.unit_number}</div>
                <span className={`px-2 py-0.5 rounded-full border text-[9px] font-mono ${st.cls}`}>{st.label}</span>
              </div>
              <div className="text-[11px] text-slate-500 font-mono mb-2">{[u.year, u.make, u.model].filter(Boolean).join(" ")} · {u.company}</div>
              <div className="h-1.5 rounded-full bg-white/10 overflow-hidden mb-2">
                <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, background: st.bar }} />
              </div>
              <div className="flex justify-between text-[10px] font-mono text-slate-500">
                <span>{m.days_since == null ? "no history" : `${m.days_since}d since clean`}</span>
                <span>{m.total_cleans} cleans · every {m.cadence_days}d</span>
              </div>
            </button>
          );
        })}
        {shown.length === 0 && <div className="col-span-full p-8 text-center text-slate-600 text-xs font-mono border border-dashed border-white/10 rounded-2xl">No units yet — add each truck in the fleet to start tracking cleans.</div>}
      </div>

      <Card className="p-5 bg-slate-950/70 border-cyan-500/30 backdrop-blur" data-testid="tc-ai-schedule">
        <div className="flex items-center justify-between mb-3">
          <div className="text-xs font-mono uppercase tracking-widest text-cyan-300 flex items-center gap-2"><Sparkles size={13} /> AI Efficiency Schedule</div>
          <button onClick={genSchedule} disabled={schedBusy} data-testid="tc-ai-schedule-btn"
                  className="px-4 py-2 rounded-full bg-cyan-500 text-black font-bold text-xs inline-flex items-center gap-1.5 disabled:opacity-60">
            {schedBusy ? <Loader2 size={13} className="animate-spin" /> : <Gauge size={13} />} Generate Week Plan
          </button>
        </div>
        {!sched && <p className="text-[12px] text-slate-500">Scores every unit against its cleaning cadence, groups fleets into single yard trips, and packs days to crew capacity — then the AI adds efficiency + revenue notes.</p>}
        {sched && (
          <div className="space-y-3">
            <div className="flex flex-wrap gap-2 text-[10px] font-mono">
              <span className="px-2 py-1 rounded-full border border-red-500/40 text-red-300">{sched.overdue} overdue</span>
              <span className="px-2 py-1 rounded-full border border-amber-500/40 text-amber-300">{sched.units_due} due now</span>
              <span className="px-2 py-1 rounded-full border border-white/15 text-slate-400">capacity {sched.capacity_per_day} cabs/day · {sched.techs} techs</span>
            </div>
            <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-2">
              {sched.plan.filter((d) => d.stops.length > 0).map((d) => (
                <div key={d.date} className="p-3 rounded-xl border border-white/10 bg-white/[0.02]" data-testid={`tc-ai-day-${d.date}`}>
                  <div className="text-[10px] font-mono text-cyan-300 mb-1.5">{d.date} · {d.cabs} cabs</div>
                  {d.stops.map((s) => (
                    <div key={s.client_id} className="mb-1.5">
                      <div className="text-[11px] font-bold text-white">{s.company}</div>
                      <div className="text-[9px] font-mono text-slate-500">{s.units.map((x) => x.unit_number).join(" · ")}</div>
                    </div>
                  ))}
                </div>
              ))}
            </div>
            {sched.ai_notes && (
              <div className="p-3 rounded-xl border border-cyan-500/25 bg-cyan-500/5 text-[12px] text-slate-300 whitespace-pre-wrap" data-testid="tc-ai-notes">{sched.ai_notes}</div>
            )}
          </div>
        )}
      </Card>

      {detail && <UnitDetail unit={detail} onClose={() => setDetail(null)} onChanged={() => { setDetail(null); load(); }} />}
    </div>
  );
};

function UnitDetail({ unit, onClose, onChanged }) {
  const m = unit.metrics; const st = STATUS[m.status] || STATUS.fresh;
  const [cadence, setCadence] = useState(m.cadence_days);
  const [busy, setBusy] = useState(false);
  const markClean = async () => {
    setBusy(true);
    try { await api.post(`/truck-cleaning/units/${unit.unit_id}/clean`, { date: "", job_id: "", upsells: [] }); toast.success("Clean logged"); onChanged(); }
    catch (e2) { toast.error(errTxt(e2)); } finally { setBusy(false); }
  };
  const saveCadence = async () => {
    try { await api.post(`/truck-cleaning/units/${unit.unit_id}/cadence`, { cadence_days: Number(cadence) }); toast.success("Cadence updated"); onChanged(); }
    catch (e2) { toast.error(errTxt(e2)); }
  };
  const del = async () => {
    try { await api.delete(`/truck-cleaning/units/${unit.unit_id}`); toast.success("Unit removed"); onChanged(); }
    catch (e2) { toast.error(errTxt(e2)); }
  };
  return (
    <div className="fixed inset-0 z-50 bg-black/70 grid place-items-center p-4" onClick={onClose}>
      <Card className="w-full max-w-md p-5 bg-slate-950 border-amber-500/30 max-h-[85vh] overflow-y-auto" onClick={(e) => e.stopPropagation()} data-testid="tc-unit-detail">
        <div className="flex justify-between items-start mb-1">
          <div className="font-black text-white text-lg">{unit.unit_number}</div>
          <span className={`px-2 py-0.5 rounded-full border text-[9px] font-mono ${st.cls}`}>{st.label}</span>
        </div>
        <div className="text-[11px] text-slate-500 font-mono mb-4">{[unit.year, unit.make, unit.model].filter(Boolean).join(" ")} · {unit.company}</div>
        <div className="grid grid-cols-3 gap-2 mb-4">
          {[["Days since", m.days_since ?? "—"], ["Total cleans", m.total_cleans], ["Avg interval", m.avg_interval_days ? `${m.avg_interval_days}d` : "—"]].map(([l, v]) => (
            <div key={l} className="p-2.5 rounded-xl border border-white/10 bg-white/[0.02] text-center">
              <div className="font-black text-amber-300 tabular-nums">{v}</div>
              <div className="text-[8px] font-mono uppercase text-slate-500">{l}</div>
            </div>
          ))}
        </div>
        <div className="flex gap-2 items-center mb-4">
          <span className="text-[10px] font-mono uppercase text-slate-500">Clean every</span>
          <input type="number" min="3" max="120" value={cadence} onChange={(e) => setCadence(e.target.value)} data-testid="tc-unit-cadence-input"
                 className="h-8 w-16 rounded-lg bg-slate-900 border border-white/15 px-2 text-xs" />
          <span className="text-[10px] font-mono text-slate-500">days</span>
          <button onClick={saveCadence} data-testid="tc-unit-cadence-save" className="px-3 h-8 rounded-full border border-cyan-500/50 text-cyan-300 text-[10px] font-bold">Save</button>
        </div>
        <div className="text-[10px] font-mono uppercase text-slate-500 mb-1.5 flex items-center gap-1.5"><History size={11} /> Clean history</div>
        <div className="space-y-1 mb-4 max-h-36 overflow-y-auto">
          {(unit.history || []).slice().reverse().map((h, i) => (
            <div key={i} className="flex justify-between text-[11px] p-2 rounded-lg bg-white/[0.03] border border-white/5">
              <span className="font-mono text-slate-300">{h.date}</span>
              <span className="text-slate-500">{(h.upsells || []).length ? h.upsells.join(", ").replace(/_/g, " ") : "standard spec"}</span>
            </div>
          ))}
          {(unit.history || []).length === 0 && <div className="text-[11px] text-slate-600 font-mono">no cleans logged yet</div>}
        </div>
        <div className="flex justify-between">
          <button onClick={del} className="px-3 py-2 rounded-full border border-red-500/40 text-red-400 text-[10px] font-bold inline-flex items-center gap-1"><Trash2 size={11} /> Remove</button>
          <button onClick={markClean} disabled={busy} data-testid="tc-unit-mark-clean"
                  className="px-5 py-2 rounded-full bg-emerald-500 text-black font-bold text-xs inline-flex items-center gap-1.5 disabled:opacity-60">
            {busy ? <Loader2 size={13} className="animate-spin" /> : <CheckCircle2 size={13} />} Mark Cleaned Today
          </button>
        </div>
      </Card>
    </div>
  );
}
