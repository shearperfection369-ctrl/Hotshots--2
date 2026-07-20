import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import axios from "axios";
import { CalendarClock, Check, Loader2 } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const fmt = (d) => d.toISOString().slice(0, 10);

export default function TcReschedulePublic() {
  const { token } = useParams();
  const [job, setJob] = useState(null);
  const [state, setState] = useState("loading"); // loading | ready | done | invalid
  const [picked, setPicked] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    axios.get(`${API}/truck-cleaning/reschedule/${token}`)
      .then(({ data }) => { setJob(data); setState("ready"); })
      .catch(() => setState("invalid"));
  }, [token]);

  const quick = [1, 2, 3, 7].map((n) => {
    const d = new Date(); d.setDate(d.getDate() + n + 1);
    return { label: n === 1 ? "Day after" : n === 7 ? "Next week" : `+${n} days`, date: fmt(d) };
  });

  const submit = async (date) => {
    setBusy(true); setErr("");
    try {
      await axios.post(`${API}/truck-cleaning/reschedule/${token}`, { new_date: date });
      setPicked(date); setState("done");
    } catch (e) { setErr(typeof e?.response?.data?.detail === "string" ? e.response.data.detail : "Failed — try again"); }
    finally { setBusy(false); }
  };

  return (
    <div className="min-h-screen bg-[#0D1117] text-white relative">
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <div style={{ position: "absolute", top: -100, left: "12%", width: 440, height: 440, borderRadius: 9999, filter: "blur(52px)", background: "radial-gradient(circle, rgba(34,211,238,0.25), transparent 65%)" }} />
        <div style={{ position: "absolute", bottom: -120, right: -80, width: 480, height: 480, borderRadius: 9999, filter: "blur(52px)", background: "radial-gradient(circle, rgba(245,158,11,0.25), transparent 65%)" }} />
      </div>
      <div className="relative max-w-md mx-auto px-5 py-12">
        <div className="flex items-center gap-3 mb-8">
          <img src="/tc-logo.png" alt="Orisei Truck Cleaning" className="h-16 w-auto drop-shadow-[0_0_18px_rgba(59,130,246,0.55)]" />
          <div>
            <div className="font-black text-lg leading-tight">ORISEI <span className="text-amber-400">TRUCK CLEANING</span></div>
            <div className="text-[11px] text-slate-500 font-mono">One-tap reschedule</div>
          </div>
        </div>

        {state === "loading" && <div className="text-slate-500 font-mono text-sm flex gap-2 items-center"><Loader2 size={14} className="animate-spin" /> Loading…</div>}
        {state === "invalid" && <div className="p-6 rounded-2xl border border-red-500/30 bg-red-500/5 text-sm" data-testid="tcr-invalid">This link is invalid or expired. Call us at (612) 555-0117.</div>}

        {state === "done" && (
          <div className="p-8 rounded-2xl border border-emerald-500/40 bg-emerald-500/5 text-center" data-testid="tcr-done">
            <div className="mx-auto h-14 w-14 rounded-full bg-emerald-500/20 grid place-items-center mb-4"><Check className="text-emerald-400" size={26} /></div>
            <div className="font-black text-xl mb-1">Rescheduled!</div>
            <p className="text-sm text-slate-300">Your cleaning is now set for <b className="text-amber-300">{picked}</b>. We'll text a confirmation with the exact window 24h before.</p>
          </div>
        )}

        {state === "ready" && job && (
          <div className="rounded-2xl border border-white/10 bg-slate-950/85 backdrop-blur p-6" data-testid="tcr-card">
            <div className="flex items-center gap-2 text-sm text-slate-300 mb-1"><CalendarClock size={15} className="text-cyan-300" /> Current appointment</div>
            <div className="font-black text-2xl text-amber-300 mb-1">{job.date}</div>
            <div className="text-xs text-slate-500 mb-5">{job.company} · {job.cabs} cab{job.cabs !== 1 ? "s" : ""} · 45-min showroom spec each</div>
            <div className="text-[11px] font-mono uppercase text-slate-500 mb-2">Pick a new day — one tap</div>
            <div className="grid grid-cols-2 gap-2 mb-4">
              {quick.map((q) => (
                <button key={q.date} onClick={() => submit(q.date)} disabled={busy} data-testid={`tcr-quick-${q.date}`}
                        className="p-3 rounded-xl border border-white/15 hover:border-amber-400/70 hover:bg-amber-500/10 text-left transition disabled:opacity-50">
                  <div className="font-bold text-sm">{q.label}</div>
                  <div className="text-[11px] text-slate-500 font-mono">{q.date}</div>
                </button>
              ))}
            </div>
            <div className="flex gap-2 items-center">
              <input type="date" min={fmt(new Date(Date.now() + 86400000))} value={picked} onChange={(e) => setPicked(e.target.value)}
                     data-testid="tcr-date-input" className="flex-1 h-11 rounded-xl bg-slate-900/80 border border-white/15 px-3 text-sm outline-none focus:border-amber-400" />
              <button onClick={() => picked && submit(picked)} disabled={busy || !picked} data-testid="tcr-submit-btn"
                      className="h-11 px-5 rounded-full bg-amber-500 text-black font-bold text-xs disabled:opacity-40">
                {busy ? <Loader2 size={14} className="animate-spin" /> : "Confirm"}
              </button>
            </div>
            {err && <div className="text-red-400 text-xs mt-2" data-testid="tcr-error">{err}</div>}
          </div>
        )}
        <div className="text-center text-[10px] text-slate-600 font-mono mt-8">Orisei Truck Cleaning Solutions · Minneapolis–St. Paul, MN · (612) 555-0117</div>
      </div>
    </div>
  );
}
