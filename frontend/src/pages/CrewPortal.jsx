import React, { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";
import { toast, Toaster } from "sonner";
import { Droplets, Clock, Camera, CheckCircle2, ClipboardList, BookOpenText, Megaphone, LogOut, MapPin, Loader2, ChevronDown, ChevronUp } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api/truck-cleaning`;
const tokenStore = {
  get: () => sessionStorage.getItem("tc_crew_token") || "",
  set: (t) => sessionStorage.setItem("tc_crew_token", t),
  clear: () => sessionStorage.removeItem("tc_crew_token"),
};
const crewApi = (token) => axios.create({ baseURL: API, headers: { "X-Crew-Token": token } });

function PinLogin({ onLogin }) {
  const [pin, setPin] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setErr("");
    try {
      const { data } = await axios.post(`${API}/crew/login`, { pin });
      tokenStore.set(data.token);
      onLogin(data.crew);
    } catch (e2) {
      setErr(e2?.response?.data?.detail || "Invalid PIN");
    } finally { setBusy(false); }
  };
  return (
    <div className="min-h-screen bg-[#0D1117] flex flex-col items-center justify-center p-6" data-testid="crew-login-page">
      <Droplets size={44} className="text-amber-400 mb-3" />
      <h1 className="text-xl font-black text-white">Orisei Crew</h1>
      <p className="text-xs text-slate-500 font-mono mb-8">Truck Cleaning · Field Portal</p>
      <form onSubmit={submit} className="w-full max-w-xs space-y-4">
        <input autoFocus inputMode="numeric" pattern="[0-9]*" maxLength={6} value={pin}
          onChange={(e) => setPin(e.target.value.replace(/\D/g, ""))} placeholder="Enter your PIN"
          className="w-full h-16 rounded-2xl bg-slate-900 border border-white/15 text-center text-3xl font-black tracking-[0.4em] text-amber-300 outline-none focus:border-amber-500"
          data-testid="crew-pin-input" />
        {err && <div className="text-red-400 text-sm text-center" data-testid="crew-login-error">{err}</div>}
        <button disabled={busy || pin.length < 4} data-testid="crew-login-btn"
          className="w-full h-14 rounded-2xl bg-amber-500 text-black font-black text-lg disabled:opacity-40">
          {busy ? "Checking…" : "Sign In"}
        </button>
      </form>
      <p className="text-[10px] text-slate-600 font-mono mt-8">No PIN? Ask your dispatcher.</p>
    </div>
  );
}

function ClockCard({ me, onToggle, busy }) {
  return (
    <div className={`p-4 rounded-2xl border ${me.clocked_in ? "border-emerald-500/40 bg-emerald-500/5" : "border-white/10 bg-slate-900/70"}`} data-testid="crew-clock-card">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-sm font-bold text-white">{me.clocked_in ? "On the clock" : "Off the clock"}</div>
          {me.clocked_in && me.shift && <div className="text-[10px] font-mono text-emerald-300">since {new Date(me.shift.in_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</div>}
        </div>
        <button onClick={onToggle} disabled={busy} data-testid="crew-clock-btn"
          className={`h-12 px-6 rounded-full font-black text-sm ${me.clocked_in ? "bg-red-500/90 text-white" : "bg-emerald-500 text-black"} disabled:opacity-50`}>
          {busy ? <Loader2 size={16} className="animate-spin" /> : me.clocked_in ? "CLOCK OUT" : "CLOCK IN"}
        </button>
      </div>
    </div>
  );
}

function JobCard({ job, api, refresh }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState("");
  const fileRef = useRef(null);
  const kindRef = useRef("before");
  const toggleTask = async (t) => {
    try {
      await api.post(`/crew/jobs/${job.job_id}/task`, { task_id: t.id, done: !t.done });
      refresh();
    } catch (e) { toast.error(e?.response?.data?.detail || "Couldn't update"); }
  };
  const pickPhoto = (kind) => { kindRef.current = kind; fileRef.current?.click(); };
  const upload = async (e) => {
    const f = e.target.files?.[0];
    e.target.value = "";
    if (!f) return;
    setBusy("photo");
    const fd = new FormData();
    fd.append("file", f);
    fd.append("kind", kindRef.current);
    try {
      await api.post(`/crew/jobs/${job.job_id}/photos`, fd);
      toast.success(`${kindRef.current.toUpperCase()} photo uploaded`);
      refresh();
    } catch (e2) { toast.error(e2?.response?.data?.detail || "Upload failed"); }
    finally { setBusy(""); }
  };
  const complete = async () => {
    setBusy("complete");
    try {
      const { data } = await api.post(`/crew/jobs/${job.job_id}/complete`);
      if (data.ok) { toast.success(data.message); refresh(); }
      else data.blockers.forEach((b) => toast.error(b));
    } catch (e) { toast.error(e?.response?.data?.detail || "Couldn't complete"); }
    finally { setBusy(""); }
  };
  const done = job.status === "completed" || job.status === "paid";
  return (
    <div className={`rounded-2xl border ${done ? "border-emerald-500/30 bg-emerald-500/5" : "border-white/10 bg-slate-900/70"}`} data-testid={`crew-job-${job.job_id}`}>
      <button onClick={() => setOpen(!open)} className="w-full p-4 text-left" data-testid={`crew-job-toggle-${job.job_id}`}>
        <div className="flex items-center justify-between">
          <div>
            <div className="text-sm font-bold text-white">{job.company}</div>
            <div className="text-[10px] font-mono text-slate-500">{job.window || "anytime"} · {job.cabs} cab{job.cabs > 1 ? "s" : ""}{job.upsells.length ? ` · +${job.upsells.length} add-on${job.upsells.length > 1 ? "s" : ""}` : ""}</div>
          </div>
          <div className="flex items-center gap-2">
            {done
              ? <CheckCircle2 size={20} className="text-emerald-400" />
              : <span className="text-xs font-black text-amber-300">{job.progress_pct}%</span>}
            {open ? <ChevronUp size={16} className="text-slate-500" /> : <ChevronDown size={16} className="text-slate-500" />}
          </div>
        </div>
        {!done && <div className="mt-2 h-1.5 rounded-full bg-white/10"><div className="h-full rounded-full bg-amber-500 transition-all" style={{ width: `${job.progress_pct}%` }} /></div>}
      </button>
      {open && (
        <div className="px-4 pb-4 space-y-3">
          {job.phone && <a href={`tel:${job.phone}`} className="text-xs text-cyan-300 font-mono">{job.contact ? `${job.contact} · ` : ""}{job.phone}</a>}
          <div className="space-y-1.5">
            {job.checklist.map((t) => (
              <button key={t.id} onClick={() => !done && toggleTask(t)} data-testid={`crew-task-${job.job_id}-${t.id}`}
                className={`w-full flex items-center gap-3 p-3 rounded-xl border text-left ${t.done ? "border-emerald-500/30 bg-emerald-500/10" : "border-white/10 bg-white/[0.02]"}`}>
                <span className={`w-6 h-6 rounded-full border-2 grid place-items-center shrink-0 ${t.done ? "border-emerald-400 bg-emerald-400" : "border-slate-600"}`}>
                  {t.done && <CheckCircle2 size={14} className="text-black" />}
                </span>
                <span className={`text-xs ${t.done ? "text-emerald-200 line-through" : "text-slate-200"}`}>{t.label}</span>
                <span className="ml-auto text-[9px] font-mono text-slate-600">{t.minutes}m</span>
              </button>
            ))}
          </div>
          <div className="flex gap-2">
            <button onClick={() => pickPhoto("before")} disabled={!!busy || done} data-testid={`crew-photo-before-${job.job_id}`}
              className="flex-1 h-11 rounded-xl border border-cyan-500/40 text-cyan-300 text-xs font-bold flex items-center justify-center gap-1.5 disabled:opacity-40">
              <Camera size={14} /> BEFORE ({job.photos_before})
            </button>
            <button onClick={() => pickPhoto("after")} disabled={!!busy || done} data-testid={`crew-photo-after-${job.job_id}`}
              className="flex-1 h-11 rounded-xl border border-amber-500/40 text-amber-300 text-xs font-bold flex items-center justify-center gap-1.5 disabled:opacity-40">
              <Camera size={14} /> AFTER ({job.photos_after})
            </button>
          </div>
          <input ref={fileRef} type="file" accept="image/*" capture="environment" className="hidden" onChange={upload} data-testid={`crew-photo-input-${job.job_id}`} />
          {!done && (
            <button onClick={complete} disabled={!!busy} data-testid={`crew-complete-${job.job_id}`}
              className="w-full h-12 rounded-xl bg-emerald-500 text-black font-black text-sm disabled:opacity-50">
              {busy === "complete" ? "Checking…" : "MARK JOB COMPLETE"}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function TodayTab({ api }) {
  const [data, setData] = useState(null);
  const refresh = useCallback(() => {
    api.get("/crew/today").then(({ data: d }) => setData(d)).catch(() => {});
  }, [api]);
  useEffect(() => { refresh(); }, [refresh]);
  const claim = async (id) => {
    try { await api.post(`/crew/jobs/${id}/claim`); toast.success("Job claimed — it's yours"); refresh(); }
    catch (e) { toast.error("Couldn't claim"); }
  };
  if (!data) return <div className="text-slate-500 text-sm font-mono p-4">Loading…</div>;
  return (
    <div className="space-y-3" data-testid="crew-today-tab">
      <div className="text-[10px] font-mono uppercase tracking-widest text-slate-500">My jobs today · {data.date}</div>
      {data.my_jobs.map((j) => <JobCard key={j.job_id} job={j} api={api} refresh={refresh} />)}
      {!data.my_jobs.length && <div className="p-6 rounded-2xl border border-white/10 bg-slate-900/50 text-center text-slate-500 text-sm">No jobs assigned to you today.</div>}
      {data.open_jobs.length > 0 && (
        <>
          <div className="text-[10px] font-mono uppercase tracking-widest text-slate-500 pt-2">Up for grabs ({data.open_jobs.length})</div>
          {data.open_jobs.map((j) => (
            <div key={j.job_id} className="p-4 rounded-2xl border border-dashed border-amber-500/30 bg-amber-500/[0.03] flex items-center justify-between" data-testid={`crew-open-job-${j.job_id}`}>
              <div>
                <div className="text-sm font-bold text-white">{j.company}</div>
                <div className="text-[10px] font-mono text-slate-500">{j.cabs} cab{j.cabs > 1 ? "s" : ""} · {j.window || "anytime"}</div>
              </div>
              <button onClick={() => claim(j.job_id)} data-testid={`crew-claim-${j.job_id}`}
                className="h-9 px-4 rounded-full bg-amber-500 text-black text-xs font-black">CLAIM</button>
            </div>
          ))}
        </>
      )}
    </div>
  );
}

function GuideTab({ api }) {
  const [g, setG] = useState(null);
  const [openPhase, setOpenPhase] = useState(0);
  useEffect(() => { api.get("/crew/guide").then(({ data }) => setG(data)).catch(() => {}); }, [api]);
  if (!g) return <div className="text-slate-500 text-sm font-mono p-4">Loading…</div>;
  return (
    <div className="space-y-2" data-testid="crew-guide-tab">
      <div className="text-sm font-bold text-white">{g.title}</div>
      <p className="text-[11px] text-slate-500">{g.intro}</p>
      {g.phases.map((p, i) => (
        <div key={p.phase} className="rounded-xl border border-white/10 bg-slate-900/70">
          <button onClick={() => setOpenPhase(openPhase === i ? -1 : i)} className="w-full p-3 flex items-center justify-between text-left" data-testid={`crew-guide-phase-${i}`}>
            <span className="text-xs font-bold text-amber-300">{p.phase}</span>
            <span className="text-[9px] font-mono text-slate-500">{p.minutes} min</span>
          </button>
          {openPhase === i && (
            <ul className="px-4 pb-3 space-y-1.5">
              {p.steps.map((s, k) => <li key={k} className="text-[11px] text-slate-300 flex gap-2"><span className="text-amber-500">•</span>{s}</li>)}
            </ul>
          )}
        </div>
      ))}
    </div>
  );
}

function UpdatesTab({ api }) {
  const [rows, setRows] = useState([]);
  useEffect(() => { api.get("/crew/updates").then(({ data }) => setRows(data.updates || [])).catch(() => {}); }, [api]);
  return (
    <div className="space-y-2" data-testid="crew-updates-tab">
      {rows.map((u) => (
        <div key={u.update_id} className={`p-4 rounded-2xl border ${u.pinned ? "border-amber-500/40 bg-amber-500/5" : "border-white/10 bg-slate-900/70"}`}>
          <div className="text-sm font-bold text-white">{u.pinned && "📌 "}{u.title}</div>
          {u.body && <div className="text-xs text-slate-400 mt-1 whitespace-pre-wrap">{u.body}</div>}
          <div className="text-[9px] font-mono text-slate-600 mt-2">{new Date(u.created_at).toLocaleDateString()}</div>
        </div>
      ))}
      {!rows.length && <div className="p-6 text-center text-slate-500 text-sm">No company updates yet.</div>}
    </div>
  );
}

export default function CrewPortal() {
  const [crew, setCrew] = useState(null);
  const [me, setMe] = useState(null);
  const [tab, setTab] = useState("today");
  const [clockBusy, setClockBusy] = useState(false);
  const api = crewApi(tokenStore.get());
  const pingTimer = useRef(null);

  const loadMe = useCallback(async () => {
    if (!tokenStore.get()) return;
    try {
      const { data } = await crewApi(tokenStore.get()).get("/crew/me");
      setCrew(data.crew);
      setMe(data);
    } catch { tokenStore.clear(); setCrew(null); }
  }, []);
  useEffect(() => { loadMe(); }, [loadMe]);

  const sendPing = useCallback(() => {
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(
      (pos) => crewApi(tokenStore.get()).post("/crew/ping", { lat: pos.coords.latitude, lng: pos.coords.longitude }).catch(() => {}),
      () => {}, { enableHighAccuracy: false, maximumAge: 30000, timeout: 10000 });
  }, []);

  useEffect(() => {
    if (me?.clocked_in) {
      sendPing();
      pingTimer.current = setInterval(sendPing, 60000);
    }
    return () => pingTimer.current && clearInterval(pingTimer.current);
  }, [me?.clocked_in, sendPing]);

  const toggleClock = async () => {
    setClockBusy(true);
    const action = me.clocked_in ? "out" : "in";
    const doClock = (lat, lng) =>
      api.post("/crew/clock", { action, lat, lng })
        .then(({ data }) => { toast.success(action === "in" ? "Clocked in — have a great shift" : `Clocked out · ${data.hours}h logged`); loadMe(); })
        .catch((e) => toast.error(e?.response?.data?.detail || "Clock failed"))
        .finally(() => setClockBusy(false));
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (p) => doClock(p.coords.latitude, p.coords.longitude),
        () => doClock(null, null), { timeout: 6000 });
    } else doClock(null, null);
  };

  const logout = async () => {
    try { await api.post("/crew/logout"); } catch {}
    tokenStore.clear();
    setCrew(null); setMe(null);
  };

  if (!crew) return <><Toaster richColors position="top-center" /><PinLogin onLogin={(c) => { setCrew(c); loadMe(); }} /></>;

  const TABS = [
    { id: "today", label: "Today", icon: ClipboardList },
    { id: "guide", label: "Guide", icon: BookOpenText },
    { id: "updates", label: "Updates", icon: Megaphone },
  ];
  return (
    <div className="min-h-screen bg-[#0D1117] pb-24" data-testid="crew-portal">
      <Toaster richColors position="top-center" />
      <div className="sticky top-0 z-20 bg-[#0D1117]/95 backdrop-blur border-b border-white/10 px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Droplets size={18} className="text-amber-400" />
          <div>
            <div className="text-sm font-black text-white leading-tight">{crew.name}</div>
            <div className="text-[9px] font-mono text-slate-500 uppercase">{crew.role} · Orisei Crew</div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {me?.clocked_in && <span className="flex items-center gap-1 text-[9px] font-mono text-emerald-300"><MapPin size={10} /> LIVE</span>}
          <button onClick={logout} className="p-2 text-slate-500" data-testid="crew-logout-btn"><LogOut size={16} /></button>
        </div>
      </div>
      <div className="p-4 space-y-4 max-w-lg mx-auto">
        {me && <ClockCard me={me} onToggle={toggleClock} busy={clockBusy} />}
        {tab === "today" && <TodayTab api={api} />}
        {tab === "guide" && <GuideTab api={api} />}
        {tab === "updates" && <UpdatesTab api={api} />}
      </div>
      <div className="fixed bottom-0 inset-x-0 bg-[#0D1117]/95 backdrop-blur border-t border-white/10 flex justify-around py-2 z-20">
        {TABS.map((t) => {
          const Icon = t.icon;
          return (
            <button key={t.id} onClick={() => setTab(t.id)} data-testid={`crew-tab-${t.id}`}
              className={`flex flex-col items-center gap-0.5 px-6 py-1 ${tab === t.id ? "text-amber-400" : "text-slate-500"}`}>
              <Icon size={20} />
              <span className="text-[9px] font-mono uppercase">{t.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
