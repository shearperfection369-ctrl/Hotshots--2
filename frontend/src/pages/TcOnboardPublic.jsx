import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import axios from "axios";
import { Sparkles, ChevronRight, ChevronLeft, Check, Loader2 } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const PLANS = [
  { id: "one_time", name: "One-Time Clean", price: "$150 / cab", desc: "Full 45-minute showroom spec, photo proof included." },
  { id: "biweekly_sub", name: "Bi-Weekly Subscription", price: "$120 / cab", desc: "We manage the schedule — you never book. Best value." },
  { id: "fleet_sub", name: "Fleet Program (10+ cabs)", price: "$125 / cab", desc: "Priority scheduling + monthly auto-billing." },
];

const Orbs = () => (
  <div className="pointer-events-none fixed inset-0 overflow-hidden">
    <div className="tcp-orb" style={{ top: "-100px", left: "10%", background: "radial-gradient(circle, rgba(245,158,11,0.3), transparent 65%)", width: 480, height: 480 }} />
    <div className="tcp-orb" style={{ bottom: "-140px", right: "-100px", background: "radial-gradient(circle, rgba(34,211,238,0.25), transparent 65%)", width: 520, height: 520, animationDelay: "3s" }} />
    <style>{`.tcp-orb{position:absolute;border-radius:9999px;filter:blur(52px);animation:tcpFloat 10s ease-in-out infinite}@keyframes tcpFloat{0%,100%{transform:translateY(0) scale(1)}50%{transform:translateY(-30px) scale(1.06)}}`}</style>
  </div>
);

export default function TcOnboardPublic() {
  const { token } = useParams();
  const [state, setState] = useState("loading"); // loading | form | done | invalid | finalized
  const [step, setStep] = useState(0);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [form, setForm] = useState({ company: "", contact: "", phone: "", email: "", cabs: 1, plan: "biweekly_sub", fleet_notes: "", yard_address: "", agreement_accepted: false });

  useEffect(() => {
    axios.get(`${API}/truck-cleaning/onboard/${token}`)
      .then(({ data }) => {
        if (["approved", "rejected"].includes(data.status)) setState("finalized");
        else { setForm((f) => ({ ...f, ...Object.fromEntries(Object.entries(data.prefill).filter(([, v]) => v)) })); setState("form"); }
      })
      .catch(() => setState("invalid"));
  }, [token]);

  const submit = async () => {
    setBusy(true); setErr("");
    try {
      await axios.post(`${API}/truck-cleaning/onboard/${token}/submit`, { ...form, cabs: Number(form.cabs) });
      setState("done");
    } catch (e) { setErr(typeof e?.response?.data?.detail === "string" ? e.response.data.detail : "Submission failed — try again"); }
    finally { setBusy(false); }
  };

  const input = (k, ph, type = "text") => (
    <input value={form[k]} type={type} placeholder={ph} onChange={(e) => setForm({ ...form, [k]: e.target.value })}
           data-testid={`tcp-${k}-input`}
           className="w-full h-11 rounded-xl bg-slate-900/80 border border-white/15 px-4 text-sm text-white outline-none focus:border-amber-400" />
  );

  const canNext = step === 0 ? form.company.length > 1 && form.contact.length > 1 && form.email.length > 4
    : step === 1 ? Number(form.cabs) >= 1 : form.agreement_accepted;

  return (
    <div className="min-h-screen bg-[#0D1117] text-white relative">
      <Orbs />
      <div className="relative max-w-xl mx-auto px-5 py-12">
        <div className="flex items-center gap-3 mb-8">
          <img src="/tc-logo.png" alt="Orisei Truck Cleaning" data-testid="tcp-logo" className="h-16 w-auto drop-shadow-[0_0_18px_rgba(59,130,246,0.55)]" />
          <div>
            <div className="font-black text-lg leading-tight">ORISEI <span className="text-amber-400">TRUCK CLEANING</span></div>
            <div className="text-[11px] text-slate-500 font-mono">Your cab. Showroom clean. Every time.</div>
          </div>
        </div>

        {state === "loading" && <div className="text-slate-500 font-mono text-sm flex gap-2 items-center"><Loader2 size={14} className="animate-spin" /> Loading…</div>}
        {state === "invalid" && <div className="p-6 rounded-2xl border border-red-500/30 bg-red-500/5 text-sm" data-testid="tcp-invalid">This onboarding link is invalid or expired. Contact oliver@oriseifreightsolutions.com for a fresh one.</div>}
        {state === "finalized" && <div className="p-6 rounded-2xl border border-white/10 bg-white/5 text-sm" data-testid="tcp-finalized">This onboarding has already been completed. Questions? oliver@oriseifreightsolutions.com</div>}

        {state === "done" && (
          <div className="p-8 rounded-2xl border border-emerald-500/40 bg-emerald-500/5 text-center" data-testid="tcp-done">
            <div className="mx-auto h-14 w-14 rounded-full bg-emerald-500/20 grid place-items-center mb-4"><Check className="text-emerald-400" size={26} /></div>
            <div className="font-black text-xl mb-2">You're in the queue!</div>
            <p className="text-sm text-slate-300">Application received. Our crew lead will call within <b>1 business day</b> to lock your first service window and walk you through the 45-minute showroom spec.</p>
          </div>
        )}

        {state === "form" && (
          <div className="rounded-2xl border border-white/10 bg-slate-950/80 backdrop-blur p-6" data-testid="tcp-wizard">
            <div className="flex items-center gap-2 mb-6">
              {["Company", "Fleet & Plan", "Agreement"].map((s, i) => (
                <React.Fragment key={s}>
                  <div className={`flex items-center gap-1.5 text-[11px] font-bold ${i === step ? "text-amber-300" : i < step ? "text-emerald-400" : "text-slate-600"}`}>
                    <span className={`h-5 w-5 rounded-full grid place-items-center text-[10px] border ${i === step ? "border-amber-400" : i < step ? "border-emerald-500 bg-emerald-500/10" : "border-slate-700"}`}>{i < step ? "✓" : i + 1}</span>{s}
                  </div>
                  {i < 2 && <div className="flex-1 h-px bg-white/10" />}
                </React.Fragment>
              ))}
            </div>

            {step === 0 && (
              <div className="space-y-3">
                <div className="text-sm text-slate-300 mb-1 flex items-center gap-2"><Sparkles size={14} className="text-amber-400" /> Tell us about your operation</div>
                {input("company", "Company / fleet name *")}
                {input("contact", "Your name *")}
                {input("email", "Email *", "email")}
                {input("phone", "Phone")}
              </div>
            )}
            {step === 1 && (
              <div className="space-y-3">
                <div className="text-sm text-slate-300">How many cabs, and which program fits?</div>
                <div className="flex items-center gap-3">
                  <span className="text-xs text-slate-500 font-mono">CABS</span>
                  <input type="number" min="1" max="500" value={form.cabs} onChange={(e) => setForm({ ...form, cabs: e.target.value })}
                         data-testid="tcp-cabs-input" className="h-11 w-28 rounded-xl bg-slate-900/80 border border-white/15 px-4 text-sm outline-none focus:border-amber-400" />
                </div>
                {PLANS.map((p) => (
                  <button key={p.id} onClick={() => setForm({ ...form, plan: p.id })} data-testid={`tcp-plan-${p.id}`}
                          className={`w-full text-left p-3.5 rounded-xl border transition ${form.plan === p.id ? "border-amber-400 bg-amber-500/10" : "border-white/10 hover:border-white/25"}`}>
                    <div className="flex justify-between"><span className="font-bold text-sm">{p.name}</span><span className="text-amber-300 font-mono text-xs">{p.price}</span></div>
                    <div className="text-[11px] text-slate-400 mt-0.5">{p.desc}</div>
                  </button>
                ))}
                {input("yard_address", "Yard / lot address (where we come to you)")}
                <textarea value={form.fleet_notes} onChange={(e) => setForm({ ...form, fleet_notes: e.target.value })} rows={2}
                          placeholder="Anything we should know — truck makes, access windows, problem cabs…"
                          data-testid="tcp-fleet-notes" className="w-full rounded-xl bg-slate-900/80 border border-white/15 px-4 py-2.5 text-sm outline-none focus:border-amber-400" />
              </div>
            )}
            {step === 2 && (
              <div className="space-y-3">
                <div className="text-sm text-slate-300">Service agreement — the short version</div>
                <div className="p-4 rounded-xl border border-white/10 bg-white/[0.03] text-[12px] text-slate-400 space-y-1.5 max-h-48 overflow-y-auto">
                  <p><b className="text-slate-200">Services.</b> Orisei performs the standardized 45-minute cab cleaning spec on scheduled vehicles. Upsells only on written approval.</p>
                  <p><b className="text-slate-200">Billing.</b> Invoices auto-generate on completion; Net 15. Card, ACH, or check.</p>
                  <p><b className="text-slate-200">Scheduling.</b> You provide yard access windows; we confirm via SMS 24h ahead. Missed access without 12h notice billed at 50%.</p>
                  <p><b className="text-slate-200">Quality.</b> Before/after photos on every unit. Free re-clean if reported within 24 hours.</p>
                  <p><b className="text-slate-200">Term.</b> Month-to-month; either party may cancel with 30 days written notice. Crews insured & background-checked.</p>
                </div>
                <label className="flex items-start gap-2.5 cursor-pointer" data-testid="tcp-agreement-label">
                  <input type="checkbox" checked={form.agreement_accepted} onChange={(e) => setForm({ ...form, agreement_accepted: e.target.checked })}
                         data-testid="tcp-agreement-checkbox" className="mt-0.5 accent-amber-500 h-4 w-4" />
                  <span className="text-[12px] text-slate-300">I, <b>{form.contact || "the undersigned"}</b>, accept the Orisei Truck Cleaning service agreement on behalf of <b>{form.company || "my company"}</b>.</span>
                </label>
                {err && <div className="text-red-400 text-xs" data-testid="tcp-error">{err}</div>}
              </div>
            )}

            <div className="flex justify-between mt-6">
              <button onClick={() => setStep((s) => Math.max(0, s - 1))} disabled={step === 0}
                      className="px-4 py-2 rounded-full border border-white/15 text-slate-300 text-xs font-bold inline-flex items-center gap-1 disabled:opacity-30">
                <ChevronLeft size={13} /> Back
              </button>
              {step < 2 ? (
                <button onClick={() => setStep((s) => s + 1)} disabled={!canNext} data-testid="tcp-next-btn"
                        className="px-5 py-2 rounded-full bg-amber-500 text-black font-bold text-xs inline-flex items-center gap-1 disabled:opacity-40">
                  Continue <ChevronRight size={13} />
                </button>
              ) : (
                <button onClick={submit} disabled={!canNext || busy} data-testid="tcp-submit-btn"
                        className="px-6 py-2 rounded-full bg-amber-500 text-black font-bold text-xs inline-flex items-center gap-1.5 disabled:opacity-40">
                  {busy ? <Loader2 size={13} className="animate-spin" /> : <Check size={13} />} Submit Application
                </button>
              )}
            </div>
          </div>
        )}
        <div className="text-center text-[10px] text-slate-600 font-mono mt-8">Orisei Truck Cleaning Solutions · a division of Orisei Freight Solutions LLC · Minneapolis–St. Paul, MN</div>
      </div>
    </div>
  );
}
