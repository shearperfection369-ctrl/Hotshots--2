import React, { useCallback, useEffect, useState } from "react";
import { Card } from "../ui/card";
import { CalendarDays, ChevronLeft, ChevronRight, UserPlus, Users, Trash2, Plus, Zap, Repeat } from "lucide-react";
import { toast } from "sonner";
import { api } from "../../lib/api";

const errTxt = (e) => (typeof e?.response?.data?.detail === "string" ? e.response.data.detail : "Something went wrong");
const fmt = (d) => d.toISOString().slice(0, 10);
const WINDOWS = ["06:00-08:00", "08:00-10:00", "10:00-12:00", "12:00-14:00", "14:00-16:00", "16:00-18:00"];
const DOW = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"];
const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const WEEKDAYS = [["0", "Monday"], ["1", "Tuesday"], ["2", "Wednesday"], ["3", "Thursday"], ["4", "Friday"], ["5", "Saturday"], ["6", "Sunday"]];

function LockInCard({ clients, onGenerated }) {
  const [rules, setRules] = useState([]);
  const [runRate, setRunRate] = useState(0);
  const [form, setForm] = useState({ client_id: "", frequency: "biweekly", weekday: 1, window: "08:00-10:00", cabs: 4 });
  const [busy, setBusy] = useState("");
  const load = useCallback(() => {
    api.get("/truck-cleaning/recurring").then(({ data }) => { setRules(data.rules || []); setRunRate(data.monthly_run_rate || 0); }).catch(() => {});
  }, []);
  useEffect(() => { load(); }, [load]);
  const save = async () => {
    if (!form.client_id) { toast.error("Pick a client / yard"); return; }
    setBusy("save");
    try {
      await api.post("/truck-cleaning/recurring", { ...form, weekday: Number(form.weekday), cabs: Number(form.cabs) });
      toast.success("Lock-in slot saved");
      load();
    } catch (e) { toast.error(errTxt(e)); }
    finally { setBusy(""); }
  };
  const gen = async () => {
    setBusy("gen");
    try {
      const { data } = await api.post("/truck-cleaning/recurring/generate", { weeks: 4 });
      toast.success(data.message);
      load();
      onGenerated && onGenerated();
    } catch (e) { toast.error(errTxt(e)); }
    finally { setBusy(""); }
  };
  const del = async (id) => {
    try { await api.delete(`/truck-cleaning/recurring/${id}`); load(); } catch (e) { toast.error(errTxt(e)); }
  };
  return (
    <Card className="p-4 bg-slate-950/70 border-emerald-500/25" data-testid="tc-lockin-card">
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <div>
          <h3 className="text-sm font-bold text-white flex items-center gap-2"><Repeat size={14} className="text-emerald-400" /> Lock-In Schedule — weekly & bi-weekly yard slots</h3>
          <div className="text-[10px] text-slate-500">Sign a yard once, we fill the calendar automatically. Weekly $110/cab · Bi-weekly $130/cab.</div>
        </div>
        <div className="px-3 py-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/5 text-[11px] font-mono text-emerald-300" data-testid="tc-lockin-runrate">
          run-rate ${runRate.toLocaleString()}/mo
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-2 mb-3" data-testid="tc-lockin-form">
        <select value={form.client_id} onChange={(e) => setForm({ ...form, client_id: e.target.value })}
          className="h-9 px-2 rounded-lg bg-[#11151F] border border-white/10 text-xs text-slate-200 min-w-[190px]" data-testid="tc-lockin-client">
          <option value="">— Client / yard —</option>
          {clients.map((c) => <option key={c.client_id} value={c.client_id}>{c.company}</option>)}
        </select>
        <select value={form.frequency} onChange={(e) => setForm({ ...form, frequency: e.target.value })}
          className="h-9 px-2 rounded-lg bg-[#11151F] border border-white/10 text-xs text-slate-200" data-testid="tc-lockin-freq">
          <option value="biweekly">Bi-weekly</option><option value="weekly">Weekly</option>
        </select>
        <select value={form.weekday} onChange={(e) => setForm({ ...form, weekday: e.target.value })}
          className="h-9 px-2 rounded-lg bg-[#11151F] border border-white/10 text-xs text-slate-200" data-testid="tc-lockin-weekday">
          {WEEKDAYS.map(([v, l]) => <option key={v} value={v}>{`${l}s`}</option>)}
        </select>
        <select value={form.window} onChange={(e) => setForm({ ...form, window: e.target.value })}
          className="h-9 px-2 rounded-lg bg-[#11151F] border border-white/10 text-xs text-slate-200" data-testid="tc-lockin-window">
          {WINDOWS.map((w) => <option key={w} value={w}>{w}</option>)}
        </select>
        <input type="number" min="1" max="200" value={form.cabs} onChange={(e) => setForm({ ...form, cabs: e.target.value })}
          className="h-9 w-20 px-2 rounded-lg bg-[#11151F] border border-white/10 text-xs text-white" title="cabs per visit" data-testid="tc-lockin-cabs" />
        <button onClick={save} disabled={!!busy} data-testid="tc-lockin-save"
          className="h-9 px-4 rounded-full bg-emerald-500 text-black text-xs font-black disabled:opacity-50">SAVE SLOT</button>
        <button onClick={gen} disabled={!!busy || !rules.length} data-testid="tc-lockin-generate"
          className="h-9 px-4 rounded-full border border-amber-500/50 text-amber-300 text-xs font-bold disabled:opacity-40">
          {busy === "gen" ? "PLACING…" : "FILL NEXT 4 WEEKS"}
        </button>
      </div>
      {rules.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {rules.map((r) => (
            <span key={r.rule_id} className="flex items-center gap-2 px-3 py-1.5 rounded-full border border-white/10 bg-white/[0.02] text-[10px] font-mono text-slate-300" data-testid={`tc-lockin-rule-${r.rule_id}`}>
              <b className="text-white">{r.company}</b> · {r.frequency} {WEEKDAYS[r.weekday][1]}s · {r.cabs} cabs · <span className="text-emerald-300">${r.monthly_value.toLocaleString()}/mo</span>
              <button onClick={() => del(r.rule_id)} className="text-red-400/70 hover:text-red-300" data-testid={`tc-lockin-del-${r.rule_id}`}><Trash2 size={11} /></button>
            </span>
          ))}
        </div>
      )}
    </Card>
  );
}

export const TcScheduler = ({ clients, reloadAll }) => {
  const [month, setMonth] = useState(() => { const d = new Date(); return new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), 1)); });
  const [jobsByDate, setJobsByDate] = useState({});
  const [summary, setSummary] = useState(null);
  const [techs, setTechs] = useState([]);
  const [editJob, setEditJob] = useState(null);
  const [bookDay, setBookDay] = useState(null);
  const [techForm, setTechForm] = useState(null);

  const gridStart = new Date(month); gridStart.setUTCDate(1 - gridStart.getUTCDay());
  const cells = Array.from({ length: 42 }, (_, i) => { const d = new Date(gridStart); d.setUTCDate(d.getUTCDate() + i); return d; });

  const load = useCallback(async () => {
    try {
      const [s, t] = await Promise.all([
        api.get("/truck-cleaning/schedule", { params: { start: fmt(gridStart), days: 42 } }),
        api.get("/truck-cleaning/techs"),
      ]);
      const map = {};
      s.data.days.forEach((d) => { map[d.date] = d; });
      setJobsByDate(map); setSummary(s.data.summary); setTechs(t.data.techs);
    } catch (_) {}
  }, [month]); // eslint-disable-line
  useEffect(() => { load(); }, [load]);

  const shiftMonth = (n) => setMonth((m) => new Date(Date.UTC(m.getUTCFullYear(), m.getUTCMonth() + n, 1)));
  const today = fmt(new Date());

  return (
    <div className="space-y-4" data-testid="tc-scheduler">
      <LockInCard clients={clients} onGenerated={load} />
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          {[["Jobs on calendar", summary.jobs, "#F59E0B"], ["Cabs", summary.cabs, "#22D3EE"], ["Booked revenue", `$${summary.revenue.toLocaleString()}`, "#34D399"],
            ["Crew hours needed", summary.crew_hours_needed, "#A78BFA"], ["Active techs", summary.techs, "#FB923C"]].map(([l, v, c]) => (
            <div key={l} className="p-3 rounded-2xl border border-white/10 bg-slate-950/70 backdrop-blur">
              <div className="text-xl font-black tabular-nums" style={{ color: c }}>{v}</div>
              <div className="text-[9px] font-mono uppercase tracking-wider text-slate-500 mt-0.5">{l}</div>
            </div>
          ))}
        </div>
      )}

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <CalendarDays size={18} className="text-amber-400" />
          <button onClick={() => shiftMonth(-1)} data-testid="tc-sched-prev" className="h-9 w-9 grid place-items-center rounded-full border border-white/15 text-slate-300 hover:border-amber-400/60"><ChevronLeft size={16} /></button>
          <span className="font-black text-white text-lg min-w-[190px] text-center" data-testid="tc-sched-month-label">{MONTHS[month.getUTCMonth()]} {month.getUTCFullYear()}</span>
          <button onClick={() => shiftMonth(1)} data-testid="tc-sched-next" className="h-9 w-9 grid place-items-center rounded-full border border-white/15 text-slate-300 hover:border-amber-400/60"><ChevronRight size={16} /></button>
          <button onClick={() => { const d = new Date(); setMonth(new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), 1))); }}
                  className="px-3 h-9 rounded-full border border-cyan-500/40 text-cyan-300 text-xs font-bold">TODAY</button>
        </div>
        <button onClick={() => setTechForm({ name: "", phone: "", role: "junior", hourly_rate: 25 })} data-testid="tc-add-tech-btn"
                className="px-4 py-2 rounded-full border border-amber-500/50 text-amber-300 font-bold text-xs inline-flex items-center gap-1.5 hover:bg-amber-500/10"><UserPlus size={13} /> Add Tech</button>
      </div>

      <div className="rounded-2xl border border-white/10 bg-slate-950/60 backdrop-blur overflow-hidden">
        <div className="grid grid-cols-7 border-b border-white/10">
          {DOW.map((d) => <div key={d} className="py-2 text-center text-[11px] font-mono text-slate-500">{d}</div>)}
        </div>
        <div className="grid grid-cols-7">
          {cells.map((d) => {
            const ds = fmt(d);
            const inMonth = d.getUTCMonth() === month.getUTCMonth();
            const isToday = ds === today;
            const day = jobsByDate[ds];
            return (
              <div key={ds} data-testid={isToday ? "tc-cal-today" : `tc-cal-day-${ds}`}
                   className={`min-h-[110px] border-b border-r border-white/5 p-1.5 relative group ${inMonth ? "" : "opacity-35"} ${isToday ? "bg-amber-500/[0.07] ring-1 ring-inset ring-amber-400/50" : ""}`}>
                <div className="flex justify-between items-center mb-1">
                  <span className={`text-xs font-mono ${isToday ? "text-amber-300 font-black" : "text-slate-500"}`}>{d.getUTCDate()}</span>
                  <button onClick={() => setBookDay(ds)} data-testid={`tc-sched-book-${ds}`}
                          className="opacity-0 group-hover:opacity-100 h-5 w-5 grid place-items-center rounded-full border border-white/20 text-slate-400 hover:border-amber-400 hover:text-amber-300 transition"><Plus size={11} /></button>
                </div>
                <div className="space-y-1 max-h-[92px] overflow-y-auto">
                  {(day?.jobs || []).map((j) => (
                    <button key={j.job_id} onClick={() => setEditJob(j)} data-testid={`tc-cal-job-${j.job_id}`}
                            className={`w-full text-left px-1.5 py-1 rounded-md border text-[10px] leading-tight transition hover:border-amber-400/70 ${
                              j.status === "scheduled" ? (j.tech_ids?.length ? "border-cyan-500/40 bg-cyan-500/10" : "border-red-500/40 bg-red-500/10") : "border-emerald-500/30 bg-emerald-500/10 opacity-75"}`}>
                      <div className="font-bold text-white truncate">{j.company}</div>
                      <div className="font-mono text-slate-400 truncate">{j.cabs}cab · {j.window || "no window"}{j.tech_names?.length ? ` · ${j.tech_names.map((n) => n.split(" ")[0]).join(",")}` : ""}</div>
                    </button>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
        <div className="flex gap-4 px-3 py-2 border-t border-white/10 text-[10px] font-mono text-slate-500" data-testid="tc-sched-legend">
          <span><span className="inline-block h-2 w-2 rounded-sm bg-cyan-500/50 mr-1" />crewed</span>
          <span><span className="inline-block h-2 w-2 rounded-sm bg-red-500/50 mr-1" />needs crew</span>
          <span><span className="inline-block h-2 w-2 rounded-sm bg-emerald-500/50 mr-1" />done/paid</span>
          <span className="ml-auto">click any entry to edit · hover a day to book</span>
        </div>
      </div>

      <Card className="p-4 bg-slate-950/70 border-white/10 backdrop-blur">
        <div className="text-xs font-mono uppercase tracking-widest text-amber-300 flex items-center gap-2 mb-3"><Users size={13} /> Tech Roster — click to edit</div>
        <div className="grid sm:grid-cols-3 gap-3">
          {techs.map((t) => (
            <button key={t.tech_id} onClick={() => setTechForm({ ...t, edit: true })} data-testid={`tc-tech-${t.tech_id}`}
                    className="text-left p-3 rounded-xl border border-white/10 bg-white/[0.02] hover:border-amber-400/50 transition">
              <div className="flex justify-between items-start">
                <div className="font-bold text-white text-base">{t.name}</div>
                <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded-full border uppercase ${t.status_today === "on_job" ? "border-amber-500/50 text-amber-300" : "border-emerald-500/50 text-emerald-400"}`}>
                  {t.status_today === "on_job" ? "ON JOB" : "AVAILABLE"}
                </span>
              </div>
              <div className="text-[11px] font-mono text-slate-500">{t.role === "lead" ? "SENIOR LEAD" : "TECH"} · ${t.hourly_rate}/hr {t.phone && `· ${t.phone}`}</div>
              <div className="text-[11px] text-slate-400 mt-1">{t.jobs_today} job{t.jobs_today !== 1 ? "s" : ""} · {t.cabs_today} cabs today</div>
            </button>
          ))}
        </div>
      </Card>

      {editJob && <EditJobDialog job={editJob} techs={techs} onClose={() => setEditJob(null)} onSaved={() => { setEditJob(null); load(); reloadAll(); }} />}
      {bookDay && <QuickBook day={bookDay} clients={clients} onClose={() => setBookDay(null)} onSaved={() => { setBookDay(null); load(); reloadAll(); }} />}
      {techForm && <TechDialog form={techForm} setForm={setTechForm} onSaved={() => { setTechForm(null); load(); }} />}
    </div>
  );
};

function EditJobDialog({ job, techs, onClose, onSaved }) {
  const [form, setForm] = useState({ date: job.date, cabs: job.cabs, window: job.window || "", tech_ids: job.tech_ids || [], status: job.status });
  const [busy, setBusy] = useState(false);
  const toggleTech = (id) => setForm((f) => ({ ...f, tech_ids: f.tech_ids.includes(id) ? f.tech_ids.filter((x) => x !== id) : [...f.tech_ids, id] }));
  const save = async () => {
    setBusy(true);
    try {
      await api.post(`/truck-cleaning/jobs/${job.job_id}/update`,
        { date: form.date, cabs: Number(form.cabs), window: form.window, tech_ids: form.tech_ids, status: form.status });
      toast.success("Job updated"); onSaved();
    } catch (e2) { toast.error(errTxt(e2)); } finally { setBusy(false); }
  };
  const del = async () => {
    try { await api.delete(`/truck-cleaning/jobs/${job.job_id}`); toast.success("Job deleted"); onSaved(); }
    catch (e2) { toast.error(errTxt(e2)); }
  };
  return (
    <div className="fixed inset-0 z-50 bg-black/70 grid place-items-center p-4" onClick={onClose}>
      <Card className="w-full max-w-lg p-6 bg-slate-950 border-amber-500/30 max-h-[88vh] overflow-y-auto" onClick={(e) => e.stopPropagation()} data-testid="tc-edit-job-dialog">
        <div className="font-black text-white text-xl mb-1 flex items-center gap-2"><Zap size={18} className="text-amber-400" /> {job.company}</div>
        <p className="text-sm text-slate-500 mb-5 font-mono">{job.job_id} · ${job.price?.toLocaleString()} · ~{job.cabs * 45} crew-min</p>
        <div className="grid grid-cols-2 gap-3 mb-4">
          <div>
            <div className="text-xs font-mono uppercase text-slate-500 mb-1.5">Date</div>
            <input type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} data-testid="tc-edit-date"
                   className="w-full h-12 rounded-xl bg-slate-900 border border-white/15 px-3 text-base outline-none focus:border-amber-400" />
          </div>
          <div>
            <div className="text-xs font-mono uppercase text-slate-500 mb-1.5">Cabs</div>
            <input type="number" min="1" value={form.cabs} onChange={(e) => setForm({ ...form, cabs: e.target.value })} data-testid="tc-edit-cabs"
                   className="w-full h-12 rounded-xl bg-slate-900 border border-white/15 px-3 text-base outline-none focus:border-amber-400" />
          </div>
        </div>
        <div className="text-xs font-mono uppercase text-slate-500 mb-1.5">Time window</div>
        <div className="flex flex-wrap gap-2 mb-4">
          {WINDOWS.map((w) => (
            <button key={w} onClick={() => setForm({ ...form, window: form.window === w ? "" : w })} data-testid={`tc-edit-window-${w}`}
                    className={`px-4 py-2 rounded-full border text-sm font-mono font-bold ${form.window === w ? "border-amber-400 text-amber-300 bg-amber-500/10" : "border-white/15 text-slate-400"}`}>{w}</button>
          ))}
        </div>
        <div className="text-xs font-mono uppercase text-slate-500 mb-1.5">Crew</div>
        <div className="grid grid-cols-1 gap-2 mb-4">
          {techs.map((t) => (
            <label key={t.tech_id} className={`flex items-center gap-3 p-3 rounded-xl border cursor-pointer ${form.tech_ids.includes(t.tech_id) ? "border-amber-400/70 bg-amber-500/10" : "border-white/10"}`} data-testid={`tc-edit-tech-${t.tech_id}`}>
              <input type="checkbox" checked={form.tech_ids.includes(t.tech_id)} onChange={() => toggleTech(t.tech_id)} className="accent-amber-500 h-5 w-5" />
              <span className="font-bold text-white text-base">{t.name}</span>
              <span className="text-slate-500 font-mono text-sm ml-auto">{t.role} · {t.jobs_today} today</span>
            </label>
          ))}
        </div>
        <div className="text-xs font-mono uppercase text-slate-500 mb-1.5">Status</div>
        <select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })} data-testid="tc-edit-status"
                className="w-full h-12 rounded-xl bg-slate-900 border border-white/15 px-3 text-base mb-6">
          <option value="scheduled">scheduled</option><option value="completed">completed</option><option value="paid">paid</option>
        </select>
        <div className="flex justify-between">
          <button onClick={del} data-testid="tc-edit-delete" className="px-4 py-2.5 rounded-full border border-red-500/40 text-red-400 text-sm font-bold inline-flex items-center gap-1.5"><Trash2 size={14} /> Delete</button>
          <div className="flex gap-2">
            <button onClick={onClose} className="px-5 py-2.5 rounded-full border border-white/15 text-slate-300 text-sm font-bold">Cancel</button>
            <button onClick={save} disabled={busy} data-testid="tc-edit-save" className="px-6 py-2.5 rounded-full bg-amber-500 text-black font-bold text-sm disabled:opacity-60">{busy ? "Saving…" : "Save"}</button>
          </div>
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
      <Card className="w-full max-w-sm p-6 bg-slate-950 border-amber-500/30" onClick={(e) => e.stopPropagation()} data-testid="tc-quickbook-dialog">
        <div className="font-black text-white text-lg mb-4">Book job · {day}</div>
        <select value={form.client_id} onChange={(e) => setForm({ ...form, client_id: e.target.value })} data-testid="tc-quickbook-client"
                className="w-full h-12 rounded-xl bg-slate-900 border border-white/15 px-3 text-base mb-3">
          <option value="">Select client…</option>
          {clients.map((c) => <option key={c.client_id} value={c.client_id}>{c.company}</option>)}
        </select>
        <input type="number" min="1" value={form.cabs} onChange={(e) => setForm({ ...form, cabs: e.target.value })} data-testid="tc-quickbook-cabs"
               className="w-full h-12 rounded-xl bg-slate-900 border border-white/15 px-3 text-base mb-5" placeholder="Cabs" />
        <div className="flex justify-end gap-2">
          <button onClick={onClose} className="px-5 py-2.5 rounded-full border border-white/15 text-slate-300 text-sm font-bold">Cancel</button>
          <button onClick={save} disabled={!form.client_id} data-testid="tc-quickbook-save" className="px-6 py-2.5 rounded-full bg-amber-500 text-black font-bold text-sm disabled:opacity-40">Book</button>
        </div>
      </Card>
    </div>
  );
}

function TechDialog({ form, setForm, onSaved }) {
  const [busy, setBusy] = useState(false);
  const save = async () => {
    setBusy(true);
    try {
      if (form.edit) await api.post(`/truck-cleaning/techs/${form.tech_id}/update`, { name: form.name, phone: form.phone, role: form.role, hourly_rate: Number(form.hourly_rate) });
      else await api.post("/truck-cleaning/techs", { name: form.name, phone: form.phone, role: form.role, hourly_rate: Number(form.hourly_rate), skills: [] });
      toast.success(form.edit ? "Tech updated" : "Tech added"); onSaved();
    } catch (e2) { toast.error(errTxt(e2)); } finally { setBusy(false); }
  };
  const remove = async () => {
    try { await api.delete(`/truck-cleaning/techs/${form.tech_id}`); toast.success("Tech removed"); onSaved(); }
    catch (e2) { toast.error(errTxt(e2)); }
  };
  return (
    <div className="fixed inset-0 z-50 bg-black/70 grid place-items-center p-4" onClick={() => setForm(null)}>
      <Card className="w-full max-w-sm p-6 bg-slate-950 border-amber-500/30" onClick={(e) => e.stopPropagation()} data-testid="tc-tech-dialog">
        <div className="font-black text-white text-lg mb-4">{form.edit ? "Edit Tech" : "Add Tech"}</div>
        <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Full name" data-testid="tc-tech-name"
               className="w-full h-12 rounded-xl bg-slate-900 border border-white/15 px-3 text-base mb-3" />
        <input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} placeholder="Phone" data-testid="tc-tech-phone"
               className="w-full h-12 rounded-xl bg-slate-900 border border-white/15 px-3 text-base mb-3" />
        <div className="flex gap-2 mb-5">
          <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })} data-testid="tc-tech-role"
                  className="flex-1 h-12 rounded-xl bg-slate-900 border border-white/15 px-3 text-base">
            <option value="junior">Junior tech</option><option value="lead">Senior lead</option>
          </select>
          <input type="number" value={form.hourly_rate} onChange={(e) => setForm({ ...form, hourly_rate: e.target.value })} data-testid="tc-tech-rate"
                 className="w-28 h-12 rounded-xl bg-slate-900 border border-white/15 px-3 text-base" />
        </div>
        <div className="flex justify-between">
          {form.edit ? <button onClick={remove} className="px-4 py-2.5 rounded-full border border-red-500/40 text-red-400 text-sm font-bold inline-flex items-center gap-1.5"><Trash2 size={14} /> Remove</button> : <span />}
          <div className="flex gap-2">
            <button onClick={() => setForm(null)} className="px-5 py-2.5 rounded-full border border-white/15 text-slate-300 text-sm font-bold">Cancel</button>
            <button onClick={save} disabled={busy || (form.name || "").length < 2} data-testid="tc-tech-save" className="px-6 py-2.5 rounded-full bg-amber-500 text-black font-bold text-sm disabled:opacity-40">Save</button>
          </div>
        </div>
      </Card>
    </div>
  );
}
