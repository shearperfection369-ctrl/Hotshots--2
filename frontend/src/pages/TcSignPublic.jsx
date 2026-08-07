import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import axios from "axios";
import { toast, Toaster } from "sonner";
import { ShieldCheck, CheckCircle2, PenLine, Phone } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api/truck-cleaning`;

const TERMS = [
  ["Services", "Orisei performs the standardized 45-minute showroom-spec cab cleaning on scheduled vehicles, with time-stamped before/after photo proof on every unit."],
  ["Your lock-in slot", "Same crew, same day, on the frequency below. Add or skip a unit with one text — 12 hours notice."],
  ["Billing", "One monthly invoice for the whole yard. Card, ACH or check · Net 15. Every 10th clean per cab is FREE."],
  ["Quality", "Re-clean free if reported within 24 hours. Crews are insured, background-checked and uniformed."],
  ["Term", "Month-to-month. Either party may cancel with 30 days written notice. Founding rate locked for 12 months."],
];

export default function TcSignPublic() {
  const { token } = useParams();
  const [a, setA] = useState(null);
  const [err, setErr] = useState("");
  const [name, setName] = useState("");
  const [title, setTitle] = useState("");
  const [agree, setAgree] = useState(false);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState("");

  useEffect(() => {
    axios.get(`${API}/public/agreement/${token}`)
      .then(({ data }) => { setA(data); if (data.status === "signed") setDone(`Already signed by ${data.signature?.name || "your team"}.`); })
      .catch(() => setErr("This agreement link is invalid or has expired. Call us at (763) 443-4459."));
  }, [token]);

  const sign = async () => {
    if (name.trim().length < 3) { toast.error("Type your full legal name to sign"); return; }
    if (!agree) { toast.error("Please tick the agreement box"); return; }
    setBusy(true);
    try {
      const { data } = await axios.post(`${API}/public/agreement/${token}/sign`, { name: name.trim(), title: title.trim() });
      setDone(data.message);
    } catch (e) { toast.error(e?.response?.data?.detail || "Signing failed — call (763) 443-4459"); }
    finally { setBusy(false); }
  };

  return (
    <div className="min-h-screen bg-[#0B0F16] text-white px-4 py-8" data-testid="tc-sign-page"
         style={{ backgroundImage: "radial-gradient(ellipse 80% 50% at 50% -10%, rgba(37,99,235,0.18), transparent)" }}>
      <Toaster richColors position="top-center" />
      <div className="max-w-lg mx-auto">
        <div className="flex items-center gap-3 mb-6">
          <img src="/tc-logo.png" alt="Orisei" className="h-14 w-auto drop-shadow-[0_0_14px_rgba(59,130,246,0.6)]" />
          <div className="leading-tight">
            <div className="font-black text-sm">ORISEI <span className="text-amber-400">TRUCK CLEANING</span></div>
            <div className="text-[9px] font-mono uppercase tracking-[0.25em] text-slate-500">Yard Lock-In Agreement</div>
          </div>
        </div>

        {err && <div className="p-6 rounded-2xl border border-red-500/40 bg-red-500/5 text-sm text-red-300" data-testid="tc-sign-error">{err}</div>}

        {a && !done && (
          <>
            <div className="p-5 rounded-2xl border border-amber-500/30 bg-gradient-to-b from-amber-500/10 to-transparent mb-4" data-testid="tc-sign-summary">
              <div className="text-lg font-black">{a.company}</div>
              <div className="grid grid-cols-2 gap-3 mt-3 text-center">
                {[["Frequency", a.frequency === "weekly" ? "Weekly" : "Bi-Weekly"],
                  ["Cabs on the slot", a.cabs],
                  ["Rate per cab", `$${Math.round(a.rate)}`],
                  ["Est. monthly", `$${Math.round(a.monthly_value).toLocaleString()}`]].map(([l, v]) => (
                  <div key={l} className="p-3 rounded-xl bg-white/[0.04] border border-white/10">
                    <div className="text-xl font-black text-amber-400">{v}</div>
                    <div className="text-[9px] font-mono uppercase tracking-widest text-slate-500 mt-0.5">{l}</div>
                  </div>
                ))}
              </div>
            </div>

            <div className="p-5 rounded-2xl border border-white/10 bg-white/[0.03] mb-4 space-y-3" data-testid="tc-sign-terms">
              {TERMS.map(([h, t]) => (
                <div key={h} className="flex items-start gap-2.5">
                  <ShieldCheck size={15} className="text-cyan-300 shrink-0 mt-0.5" />
                  <div><span className="text-xs font-bold text-white">{h} — </span><span className="text-xs text-slate-400">{t}</span></div>
                </div>
              ))}
            </div>

            <div className="p-5 rounded-2xl border border-emerald-500/30 bg-[#0D1320]/90 space-y-3" data-testid="tc-sign-form">
              <div className="text-sm font-black flex items-center gap-2"><PenLine size={15} className="text-emerald-300" /> Sign from your phone</div>
              <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Full legal name (this is your signature) *"
                className="w-full h-12 px-4 rounded-xl bg-[#0B0F16] border border-white/15 text-sm outline-none focus:border-emerald-400"
                style={{ fontFamily: "cursive", fontSize: name ? 18 : 14 }} data-testid="tc-sign-name" />
              <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Your title (e.g. Yard Manager)"
                className="w-full h-12 px-4 rounded-xl bg-[#0B0F16] border border-white/15 text-sm outline-none focus:border-emerald-400" data-testid="tc-sign-title" />
              <label className="flex items-start gap-2.5 text-xs text-slate-400 cursor-pointer">
                <input type="checkbox" checked={agree} onChange={(e) => setAgree(e.target.checked)} className="mt-0.5 accent-emerald-500" data-testid="tc-sign-agree" />
                I have authority to sign for {a.company} and agree to the terms above. Typing my name constitutes my electronic signature.
              </label>
              <button onClick={sign} disabled={busy} data-testid="tc-sign-submit"
                className="w-full py-3.5 rounded-full bg-emerald-500 hover:bg-emerald-400 transition-colors text-black font-black text-sm disabled:opacity-50 shadow-[0_0_24px_rgba(16,185,129,0.3)]">
                {busy ? "SIGNING…" : "SIGN & LOCK MY SLOT"}
              </button>
            </div>
          </>
        )}

        {done && (
          <div className="p-8 rounded-2xl border border-emerald-500/40 bg-emerald-500/5 text-center" data-testid="tc-sign-success">
            <CheckCircle2 size={40} className="text-emerald-400 mx-auto mb-3" />
            <div className="font-black text-lg">Locked in!</div>
            <div className="text-sm text-slate-400 mt-2">{done}</div>
            <a href="tel:7634434459" className="inline-flex items-center gap-1.5 mt-5 px-6 py-3 rounded-full bg-amber-500 text-black font-black text-xs">
              <Phone size={13} /> (763) 443-4459
            </a>
          </div>
        )}

        <div className="text-center text-[10px] font-mono text-slate-600 mt-8">
          Orisei Truck Cleaning Solutions · a division of Orisei Freight Solutions LLC · Twin Cities, MN
        </div>
      </div>
    </div>
  );
}
