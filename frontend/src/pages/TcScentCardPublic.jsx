import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import axios from "axios";
import { Check, Loader2, Sparkles, BedDouble, Wind } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function TcScentCardPublic() {
  const { token } = useParams();
  const [data, setData] = useState(null);
  const [state, setState] = useState("loading"); // loading | ready | done | invalid
  const [scent, setScent] = useState("");
  const [picks, setPicks] = useState([]);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    axios.get(`${API}/truck-cleaning/scent/${token}`)
      .then(({ data: d }) => {
        setData(d); setScent(d.current.scent || ""); setPicks(d.current.upsell_ids || []);
        setState("ready");
      })
      .catch(() => setState("invalid"));
  }, [token]);

  const toggle = (id) => setPicks((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]));
  const total = data ? data.upgrades.filter((u) => picks.includes(u.id)).reduce((s, u) => s + u.price, 0) : 0;

  const submit = async () => {
    setBusy(true); setErr("");
    try {
      const { data: r } = await axios.post(`${API}/truck-cleaning/scent/${token}`, { scent, upsell_ids: picks });
      setResult(r); setState("done");
    } catch (e) { setErr(typeof e?.response?.data?.detail === "string" ? e.response.data.detail : "Failed — try again"); }
    finally { setBusy(false); }
  };

  const Section = ({ title, icon: Icon, items, accent }) => (
    <div className="mb-5">
      <div className="text-[11px] font-mono uppercase tracking-[0.25em] mb-2 flex items-center gap-1.5" style={{ color: accent }}><Icon size={13} /> {title}</div>
      <div className="grid grid-cols-1 gap-2">
        {items.map((u) => (
          <button key={u.id} onClick={() => toggle(u.id)} data-testid={`tcs-upgrade-${u.id}`}
                  className={`text-left p-3 rounded-xl border transition ${picks.includes(u.id) ? "border-amber-400 bg-amber-500/10" : "border-white/10 hover:border-white/25"}`}>
            <div className="flex justify-between items-center">
              <span className="font-bold text-sm">{u.label}</span>
              <span className="font-mono text-amber-300 text-sm">+${u.price}</span>
            </div>
            <div className="text-[11px] text-slate-400 mt-0.5">{u.desc}</div>
          </button>
        ))}
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-[#0D1117] text-white relative">
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <div style={{ position: "absolute", top: -100, left: "10%", width: 460, height: 460, borderRadius: 9999, filter: "blur(52px)", background: "radial-gradient(circle, rgba(245,158,11,0.28), transparent 65%)" }} />
        <div style={{ position: "absolute", bottom: -140, right: -90, width: 500, height: 500, borderRadius: 9999, filter: "blur(52px)", background: "radial-gradient(circle, rgba(34,211,238,0.22), transparent 65%)" }} />
      </div>
      <div className="relative max-w-lg mx-auto px-5 py-12">
        <div className="flex items-center gap-3 mb-8">
          <img src="/tc-logo.png" alt="Orisei Truck Cleaning" className="h-16 w-auto drop-shadow-[0_0_18px_rgba(59,130,246,0.55)]" />
          <div>
            <div className="font-black text-lg leading-tight">ORISEI <span className="text-amber-400">TRUCK CLEANING</span></div>
            <div className="text-[11px] text-slate-500 font-mono">Driver scent card · make it yours</div>
          </div>
        </div>

        {state === "loading" && <div className="text-slate-500 font-mono text-sm flex gap-2 items-center"><Loader2 size={14} className="animate-spin" /> Loading…</div>}
        {state === "invalid" && <div className="p-6 rounded-2xl border border-red-500/30 bg-red-500/5 text-sm" data-testid="tcs-invalid">This scent card link is invalid. Call (612) 555-0117.</div>}

        {state === "done" && result && (
          <div className="p-8 rounded-2xl border border-emerald-500/40 bg-emerald-500/5 text-center" data-testid="tcs-done">
            <div className="mx-auto h-14 w-14 rounded-full bg-emerald-500/20 grid place-items-center mb-4"><Check className="text-emerald-400" size={26} /></div>
            <div className="font-black text-xl mb-1">Locked in!</div>
            <p className="text-sm text-slate-300">{result.scent && <>Scent: <b className="text-amber-300">{result.scent}</b>. </>}
              {result.added_total > 0 ? <>Upgrades added: <b className="text-amber-300">${result.added_total}</b> — billed with the job.</> : "No paid upgrades selected."}</p>
            <p className="text-[11px] text-slate-500 mt-2">The crew will have everything on the truck when they arrive.</p>
          </div>
        )}

        {state === "ready" && data && (
          <div className="rounded-2xl border border-white/10 bg-slate-950/85 backdrop-blur p-6" data-testid="tcs-card">
            <div className="text-sm text-slate-300 mb-1">Cleaning for <b className="text-white">{data.company}</b> on <b className="text-amber-300">{data.date}</b></div>
            <p className="text-[11px] text-slate-500 mb-5">Pick your scent (free with every clean) and any bunk upgrades — the crew brings it all.</p>
            {data.locked && <div className="p-3 rounded-xl border border-amber-500/40 bg-amber-500/5 text-xs text-amber-200 mb-4">This job is already finished — picks apply to your next visit. Call us to book!</div>}
            <div className="text-[11px] font-mono uppercase tracking-[0.25em] mb-2 text-cyan-300 flex items-center gap-1.5"><Sparkles size={13} /> Your scent — included free</div>
            <div className="flex flex-wrap gap-2 mb-6">
              {data.scents.map((s) => (
                <button key={s} onClick={() => setScent(s === scent ? "" : s)} data-testid={`tcs-scent-${s.replace(/[^a-z]/gi, "")}`}
                        className={`px-3.5 py-2 rounded-full border text-sm font-bold transition ${scent === s ? "border-cyan-400 text-cyan-300 bg-cyan-500/10" : "border-white/15 text-slate-400 hover:border-white/30"}`}>{s}</button>
              ))}
            </div>
            <Section title="Freshener upgrades" icon={Wind} accent="#22D3EE" items={data.upgrades.filter((u) => u.category === "freshener")} />
            <Section title="Bedding & pillows — installed for you" icon={BedDouble} accent="#FB7185" items={data.upgrades.filter((u) => u.category === "bedding")} />
            {err && <div className="text-red-400 text-xs mb-2" data-testid="tcs-error">{err}</div>}
            <button onClick={submit} disabled={busy || data.locked} data-testid="tcs-submit"
                    className="w-full h-12 rounded-full bg-amber-500 text-black font-black text-sm inline-flex items-center justify-center gap-2 disabled:opacity-40">
              {busy ? <Loader2 size={16} className="animate-spin" /> : <Check size={16} />}
              LOCK IT IN {total > 0 ? `— +$${total} ON THE JOB` : "— SCENT IS FREE"}
            </button>
          </div>
        )}
        <div className="text-center text-[10px] text-slate-600 font-mono mt-8">Orisei Truck Cleaning Solutions · Minneapolis–St. Paul, MN · (612) 555-0117</div>
      </div>
    </div>
  );
}
