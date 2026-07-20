import React, { useCallback, useEffect, useState } from "react";
import { Card } from "../ui/card";
import { CalendarDays, ChevronLeft, ChevronRight, UserPlus, Users, Trash2, Wrench, Plus, Zap } from "lucide-react";
import { toast } from "sonner";
import { api } from "../../lib/api";

const errTxt = (e) => (typeof e?.response?.data?.detail === "string" ? e.response.data.detail : "Something went wrong");
const fmt = (d) => d.toISOString().slice(0, 10);
const WINDOWS = ["06:00-08:00", "08:00-10:00", "10:00-12:00", "12:00-14:00", "14:00-16:00", "16:00-18:00"];
const DOW = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

export const TcScheduler = ({ clients, reloadAll }) => {
  const [start, setStart] = useState(fmt(new Date()));
  const [board, setBoard] = useState(null);
  const [techs, setTechs] = useState([]);
  const [assignJob, setAssignJob] = useState(null);
  const [bookDay, setBookDay] = useState(null);
  const [techForm, setTechForm] = useState(null);

  const load = useCallback(async () => {
    try {
      const [s, t] = await Promise.all([
        api.get("/truck-cleaning/schedule", { params: { start, days: 7 } }),
        api.get("/truck-cleaning/techs"),
      ]);
      setBoard(s.data); setTechs(t.data.techs);
    } catch (_) {}
  }, [start]);
  useEffect(() => { load(); }, [load]);

  const shift = (n) => {
    const d = new Date(start + "T00:00:00Z"); d.setDate(d.getDate() + n); setStart(fmt(d));
  };

  const today = fmt(new Date());
  if (!board) return <div className="text-slate-500 font-mono text-sm">Loading dispatch board…</div>;
  const s = board.summary;

  return (
    <div className="space-y-4" data-testid="tc-scheduler">
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {[["Jobs this week", s.jobs, "#F59E0B"], ["Cabs", s.cabs, "#22D3EE"], ["Booked revenue", `$${s.revenue.toLocaleString()}`, "#34D399"],
          ["Crew hours needed", s.crew_hours_needed, "#A78BFA"], ["Active techs", s.techs, "#FB923C"]].map(([l, v, c]) => (
          <div key={l} className="tc-glow p-3 rounded-2xl border border-white/10 bg-slate-950/70 backdrop-blur">
            <div className="text-xl font-black tabular-nums" style={{ color: c }}>{v}</div>
            <div className="text-[9px] font-mono uppercase tracking-wider text-slate-500 mt-0.5">{l}</div>
          </div>
        ))}
      </div>

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <CalendarDays size={16} className="text-amber-400" />
          <button onClick={() => shift(-7)} data-testid="tc-sched-prev" className="h-8 w-8 grid place-items-center rounded-full border border-white/15 text-slate-300 hover:border-amber-400/60"><ChevronLeft size={14} /></button>
          <span className="font-mono text-xs text-slate-300">{board.start} → 7 days</span>
          <button onClick={() => shift(7)} data-testid="tc-sched-next" className="h-8 w-8 grid place-items-center rounded-full border border-white/15 text-slate-300 hover:border-amber-400/60"><ChevronRight size={14} /></button>
          <button onClick={() => setStart(fmt(new Date()))} className="px-3 h-8 rounded-full border border-cyan-500/40 text-cyan-300 text-[10px] font-bold">TODAY</button>
        </div>
        <button onClick={() => setTechForm({ name: "", phone: "", role: "junior", hourly_rate: 25 })} data-testid="tc-add-tech-btn"
                className="px-4 py-2 rounded-full border border-amber-500/50 text-amber-300 font-bold text-xs inline-flex items-center gap-1.5 hover:bg-amber-500/10"><UserPlus size={13} /> Add Tech</button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-7 gap-2">
        {board.days.map((d) => {
          const isToday = d.date === today;
          const dow = DOW[new Date(d.date + "T00:00:00Z").getUTCDay()];
          return (
            <div key={d.date} data-testid={`tc-sched-day-${d.date}`}
                 className={`rounded-2xl border p-2 min-h-[190px] backdrop-blur bg-slate-950/70 transition ${isToday ? "border-amber-400/70 shadow-[0_0_24px_-8px_rgba(245,158,11,0.6)]" : "border-white/10"}`}>
              <div className="flex justify-between items-center mb-1.5 px-1">
                <div>
                  <span className={`text-[10px] font-mono uppercase ${isToday ? "text-amber-300" : "text-slate-500"}`}>{dow}</span>
                  <span className="text-[10px] font-mono text-slate-600 ml-1">{d.date.slice(5)}</span>
                </div>
                {d.unassigned > 0 && <span className="text-[8px] font-mono px-1 rounded bg-red-500/20 text-red-300 border border-red-500/40">{d.unassigned} UNASSIGNED</span>}
              </div>
              {d.jobs.map((j) => (
                <button key={j.job_id} onClick={() => setAssignJob(j)} data-testid={`tc-sched-job-${j.job_id}`}
                        className={`w-full text-left mb-1.5 p-2 rounded-xl border text-[10px] transition hover:border-amber-400/60 ${j.status === "scheduled" ? "border-cyan-500/30 bg-cyan-500/5" : "border-emerald-500/30 bg-emerald-500/5 opacity-70"}`}>
                  <div className="font-bold text-white truncate">{j.company}</div>
                  <div className="font-mono text-slate-400">{j.cabs} cab{j.cabs !== 1 ? "s" : ""} · ${j.price}</div>
                  {j.window && <div className="font-mono text-amber-300">{j.window}</div>}
                  <div className="flex flex-wrap gap-1 mt-1">
                    {(j.tech_names || []).map((n) => <span key={n} className="px-1 rounded bg-white/10 text-slate-300 text-[8px]">{n.split(" ")[0]}</span>)}
                    {(j.tech_names || []).length === 0 && j.status === "scheduled" && <span className="text-[8px] text-red-400 font-mono">assign crew →</span>}
                  </div>
                </button>
              ))}
              <button onClick={() => setBookDay(d.date)} data-testid={`tc-sched-book-${d.date}`}
                      className="w-full mt-1 py-1.5 rounded-xl border border-dashed border-white/15 text-slate-500 text-[10px] font-mono hover:border-amber-400/50 hover:text-amber-300 transition inline-flex items-center justify-center gap-1">
                <Plus size={10} /> book
              </button>
              {d.cabs > 0 && <div className="text-right text-[9px] font-mono text-slate-600 mt-1">${d.revenue.toLocaleString()}</div>}
            </div>
          );
        })}
      </div>

      <Card className="p-4 bg-slate-950/70 border-white/10 backdrop-blur">
        <div className="text-xs font-mono uppercase tracking-widest text-amber-300 flex items-center gap-2 mb-3"><Users size={13} /> Tech Roster — today</div>
        <div className="grid sm:grid-cols-3 gap-3">
          {techs.map((t) => (
            <div key={t.tech_id} className="p-3 rounded-xl border border-white/10 bg-white/[0.02] relative group" data-testid={`tc-tech-${t.tech_id}`}>
              <div className="flex justify-between items-start">
                <div className="font-bold text-white text-sm">{t.name}</div>
                <span className={`text-[8px] font-mono px-1.5 py-0.5 rounded-full border uppercase ${t.status_today === "on_job" ? "border-amber-500/50 text-amber-300" : "border-emerald-500/50 text-emerald-400"}`}>
                  {t.status_today === "on_job" ? "ON JOB" : "AVAILABLE"}
                </span>
              </div>
              <div className="text-[10px] font-mono text-slate-500">{t.role === "lead" ? "SENIOR LEAD" : "TECH"} · ${t.hourly_rate}/hr</div>
              <div className="text-[10px] text-slate-400 mt-1">{t.jobs_today} job{t.jobs_today !== 1 ? "s" : ""} · {t.cabs_today} cabs today</div>
              <div className="flex flex-wrap gap-1 mt-1.5">{(t.skills || []).map((sk) => <span key={sk} className="text-[8px] font-mono px-1.5 rounded-full border border-cyan-500/30 text-cyan-300">{sk}</span>)}</div>
              <button onClick={async () => { await api.delete(`/truck-cleaning/techs/${t.tech_id}`); load(); }}
                      className="absolute top-2 right-2 hidden group-hover:block text-slate-600 hover:text-red-400 -translate-y-6"><Trash2 size={12} /></button>
            </div>
          ))}
        </div>
      </Card>

      {assignJob && <AssignDialog job={assignJob} techs={techs} onClose={() => setAssignJob(null)} onSaved={() => { setAssignJob(null); load(); }} />}
      {bookDay && <QuickBook day={bookDay} clients={clients} onClose={() => setBookDay(null)} onSaved={() => { setBookDay(null); load(); reloadAll(); }} />}
      {techForm && <TechDialog form={techForm} setForm={setTechForm} onSaved={() => { setTechForm(null); load(); }} />}
    </div>
  );
};

function AssignDialog({ job, techs, onClose, onSaved }) {
  const [sel, setSel] = useState(job.tech_ids || []);
  const [win, setWin] = useState(job.window || "");
  const save = async () => {
    try { await api.post(`/truck-cleaning/jobs/${job.job_id}/assign`, { tech_ids: sel, window: win }); toast.success("Crew dispatched"); onSaved(); }
    catch (e2) { toast.error(errTxt(e2)); }
  };
  return (
    <div className="fixed inset-0 z-50 bg-black/70 grid place-items-center p-4" onClick={onClose}>
      <Card className="w-full max-w-md p-5 bg-slate-950 border-amber-500/30" onClick={(e) => e.stopPropagation()} data-testid="tc-assign-dialog">
        <div className="font-black text-white mb-0.5 flex items-center gap-2"><Zap size={15} className="text-amber-400" /> Dispatch · {job.job_id}</div>
        <p className="text-[11px] text-slate-500 mb-4">{job.company} · {job.date} · {job.cabs} cabs (~{job.cabs * 45} crew-min)</p>
        <div className="text-[10px] font-mono uppercase text-slate-500 mb-1.5">Crew</div>
        <div className="grid grid-cols-1 gap-1.5 mb-4">
          {techs.map((t) => (
            <label key={t.tech_id} className={`flex items-center gap-2 p-2 rounded-lg border cursor-pointer text-xs ${sel.includes(t.tech_id) ? "border-amber-400/70 bg-amber-500/10" : "border-white/10"}`} data-testid={`tc-assign-tech-${t.tech_id}`}>
              <input type="checkbox" checked={sel.includes(t.tech_id)} className="accent-amber-500"
                     onChange={() => setSel((x) => x.includes(t.tech_id) ? x.filter((i) => i !== t.tech_id) : [...x, t.tech_id])} />
              <span className="font-bold text-white">{t.name}</span>
              <span className="text-slate-500 font-mono text-[10px]">{t.role} · {t.jobs_today} jobs today</span>
            </label>
          ))}
        </div>
        <div className="text-[10px] font-mono uppercase text-slate-500 mb-1.5">Time window</div>
        <div className="flex flex-wrap gap-1.5 mb-5">
          {WINDOWS.map((w) => (
            <button key={w} onClick={() => setWin(w === win ? "" : w)} data-testid={`tc-assign-window-${w}`}
                    className={`px-2.5 py-1 rounded-full border text-[10px] font-mono ${win === w ? "border-amber-400 text-amber-300 bg-amber-500/10" : "border-white/15 text-slate-400"}`}>{w}</button>
          ))}
        </div>
        <div className="flex justify-end gap-2">
          <button onClick={onClose} className="px-4 py-2 rounded-full border border-white/15 text-slate-300 text-xs font-bold">Cancel</button>
          <button onClick={save} data-testid="tc-assign-save" className="px-5 py-2 rounded-full bg-amber-500 text-black font-bold text-xs inline-flex items-center gap-1.5"><Wrench size={12} /> Dispatch</button>
        </div>
      </Card>
    </div>
  );
}

function QuickBook({ day, clients, onClose, onSaved }) {
  const [form, setForm] = useState({ client_id: "", cabs: 1 });
  const save = async () => {
    try { await api.post("/truck-cleaning/jobs", { client_id: form.client_id, cabs: Number(form.cabs), date: day, upsells: [] }); toast.success("Job booked"); onSaved(); }
    catch (e2) { toast.error(errTxt(e2)); }
  };
  return (
    <div className="fixed inset-0 z-50 bg-black/70 grid place-items-center p-4" onClick={onClose}>
      <Card className="w-full max-w-sm p-5 bg-slate-950 border-amber-500/30" onClick={(e) => e.stopPropagation()} data-testid="tc-quickbook-dialog">
        <div className="font-black text-white mb-3">Book job · {day}</div>
        <select value={form.client_id} onChange={(e) => setForm({ ...form, client_id: e.target.value })} data-testid="tc-quickbook-client"
                className="w-full h-10 rounded-lg bg-slate-900 border border-white/15 px-2 text-xs mb-2">
          <option value="">Select client…</option>
          {clients.map((c) => <option key={c.client_id} value={c.client_id}>{c.company}</option>)}
        </select>
        <input type="number" min="1" value={form.cabs} onChange={(e) => setForm({ ...form, cabs: e.target.value })} data-testid="tc-quickbook-cabs"
               className="w-full h-10 rounded-lg bg-slate-900 border border-white/15 px-3 text-xs mb-4" placeholder="Cabs" />
        <div className="flex justify-end gap-2">
          <button onClick={onClose} className="px-4 py-2 rounded-full border border-white/15 text-slate-300 text-xs font-bold">Cancel</button>
          <button onClick={save} disabled={!form.client_id} data-testid="tc-quickbook-save" className="px-5 py-2 rounded-full bg-amber-500 text-black font-bold text-xs disabled:opacity-40">Book</button>
        </div>
      </Card>
    </div>
  );
}

function TechDialog({ form, setForm, onSaved }) {
  const save = async () => {
    try { await api.post("/truck-cleaning/techs", { ...form, hourly_rate: Number(form.hourly_rate), skills: [] }); toast.success("Tech added"); onSaved(); }
    catch (e2) { toast.error(errTxt(e2)); }
  };
  return (
    <div className="fixed inset-0 z-50 bg-black/70 grid place-items-center p-4" onClick={() => setForm(null)}>
      <Card className="w-full max-w-sm p-5 bg-slate-950 border-amber-500/30" onClick={(e) => e.stopPropagation()} data-testid="tc-tech-dialog">
        <div className="font-black text-white mb-3">Add Tech</div>
        <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Full name" data-testid="tc-tech-name"
               className="w-full h-10 rounded-lg bg-slate-900 border border-white/15 px-3 text-xs mb-2" />
        <input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} placeholder="Phone" data-testid="tc-tech-phone"
               className="w-full h-10 rounded-lg bg-slate-900 border border-white/15 px-3 text-xs mb-2" />
        <div className="flex gap-2 mb-4">
          <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })} data-testid="tc-tech-role"
                  className="flex-1 h-10 rounded-lg bg-slate-900 border border-white/15 px-2 text-xs">
            <option value="junior">Junior tech · $25/hr</option><option value="lead">Senior lead · $32/hr</option>
          </select>
          <input type="number" value={form.hourly_rate} onChange={(e) => setForm({ ...form, hourly_rate: e.target.value })} data-testid="tc-tech-rate"
                 className="w-24 h-10 rounded-lg bg-slate-900 border border-white/15 px-3 text-xs" />
        </div>
        <div className="flex justify-end gap-2">
          <button onClick={() => setForm(null)} className="px-4 py-2 rounded-full border border-white/15 text-slate-300 text-xs font-bold">Cancel</button>
          <button onClick={save} disabled={(form.name || "").length < 2} data-testid="tc-tech-save" className="px-5 py-2 rounded-full bg-amber-500 text-black font-bold text-xs disabled:opacity-40">Save</button>
        </div>
      </Card>
    </div>
  );
}
