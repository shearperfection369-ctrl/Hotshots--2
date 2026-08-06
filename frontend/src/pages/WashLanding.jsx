import React, { useEffect, useState } from "react";
import axios from "axios";
import { toast, Toaster } from "sonner";
import { Sparkles, ShieldCheck, Clock, Camera, Truck, Phone, Mail, MapPin, ChevronRight, CheckCircle2, Star } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api/truck-cleaning`;

const STEPS = [
  { icon: Clock, t: "Book a slot", d: "Pick a date — we come to your yard, your dock, or your driveway." },
  { icon: Sparkles, t: "45-min showroom spec", d: "One cab, one crew, 45 minutes flat. Standardized 9-phase deep clean, every time." },
  { icon: Camera, t: "Before & after proof", d: "Time-stamped photos on every job. You see exactly what you paid for." },
];

const STATS = [
  ["9", "phase showroom spec"],
  ["45", "minutes per cab"],
  ["2×", "photo proof, every unit"],
  ["50mi", "Twin Cities coverage"],
];

function TechBackdrop() {
  return (
    <div className="fixed inset-0 z-0 pointer-events-none overflow-hidden" aria-hidden="true" data-testid="wash-tech-backdrop">
      <style>{`
        @keyframes washGridScroll { from { background-position: 0 0; } to { background-position: 0 56px; } }
        @keyframes washScan { 0% { top: -12%; opacity: 0; } 8% { opacity: 1; } 92% { opacity: 1; } 100% { top: 112%; opacity: 0; } }
        @keyframes washDrift1 { 0%,100% { transform: translate(0,0) scale(1); } 50% { transform: translate(70px,-50px) scale(1.15); } }
        @keyframes washDrift2 { 0%,100% { transform: translate(0,0) scale(1); } 50% { transform: translate(-60px,40px) scale(0.9); } }
        @keyframes washBlink { 0%,100% { opacity: .08; } 50% { opacity: .45; } }
        @keyframes washDash { to { stroke-dashoffset: -400; } }
      `}</style>
      {/* slow-scrolling tech grid */}
      <div className="absolute inset-0" style={{
        backgroundImage: "linear-gradient(rgba(56,189,248,0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(56,189,248,0.05) 1px, transparent 1px)",
        backgroundSize: "56px 56px",
        animation: "washGridScroll 14s linear infinite",
        maskImage: "radial-gradient(ellipse 90% 70% at 50% 30%, black 30%, transparent 75%)",
        WebkitMaskImage: "radial-gradient(ellipse 90% 70% at 50% 30%, black 30%, transparent 75%)",
      }} />
      {/* drifting glow orbs */}
      <div className="absolute rounded-full" style={{ width: 420, height: 420, top: "8%", right: "6%", background: "radial-gradient(circle, rgba(37,99,235,0.14), transparent 65%)", filter: "blur(10px)", animation: "washDrift1 22s ease-in-out infinite" }} />
      <div className="absolute rounded-full" style={{ width: 340, height: 340, bottom: "12%", left: "4%", background: "radial-gradient(circle, rgba(245,158,11,0.09), transparent 65%)", filter: "blur(10px)", animation: "washDrift2 28s ease-in-out infinite" }} />
      {/* vertical scan beam */}
      <div className="absolute left-0 right-0" style={{ height: 130, top: "-12%", background: "linear-gradient(180deg, transparent, rgba(56,189,248,0.045), transparent)", animation: "washScan 11s linear infinite" }} />
      {/* circuit trace lines */}
      <svg className="absolute inset-0 w-full h-full" style={{ opacity: 0.35 }}>
        <path d="M -20 180 H 300 L 360 240 H 720 L 780 180 H 1200" fill="none" stroke="rgba(56,189,248,0.12)" strokeWidth="1"
              strokeDasharray="8 14" style={{ animation: "washDash 20s linear infinite" }} />
        <path d="M 1940 560 H 1500 L 1440 620 H 1000 L 940 560 H 500" fill="none" stroke="rgba(245,158,11,0.10)" strokeWidth="1"
              strokeDasharray="6 16" style={{ animation: "washDash 26s linear infinite" }} />
      </svg>
      {/* blinking nodes */}
      {[["12%", "22%", "0s"], ["78%", "14%", "1.2s"], ["64%", "58%", "2.4s"], ["22%", "72%", "0.8s"], ["88%", "78%", "1.8s"], ["42%", "36%", "2.9s"]].map(([l, t, d], i) => (
        <span key={i} className="absolute w-1.5 h-1.5 rounded-full bg-cyan-300" style={{ left: l, top: t, animation: `washBlink 4s ease-in-out ${d} infinite`, boxShadow: "0 0 8px rgba(56,189,248,0.8)" }} />
      ))}
    </div>
  );
}

export default function WashLanding() {
  const [info, setInfo] = useState(null);
  const [form, setForm] = useState({ company: "", contact: "", phone: "", email: "", cabs: 1, preferred_date: "", notes: "" });
  const [sel, setSel] = useState([]);
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  useEffect(() => { axios.get(`${API}/public/site-info`).then(({ data }) => setInfo(data)).catch(() => {}); }, []);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const { data } = await axios.post(`${API}/public/booking`, { ...form, cabs: Number(form.cabs) || 1, services: sel });
      toast.success(data.message);
      setSent(true);
    } catch (e2) {
      toast.error(e2?.response?.data?.detail || "Something went wrong — call us at (763) 443-4459");
    } finally { setBusy(false); }
  };

  const addons = (info?.services || []).filter((s) => s.category === "add_on").slice(0, 6);
  return (
    <div className="min-h-screen bg-[#0B0F16] text-white overflow-x-hidden" data-testid="wash-landing"
         style={{ backgroundImage: "radial-gradient(ellipse 80% 50% at 70% -10%, rgba(37,99,235,0.18), transparent), radial-gradient(ellipse 60% 40% at 10% 110%, rgba(245,158,11,0.08), transparent)" }}>
      <Toaster richColors position="top-center" />
      <TechBackdrop />
      <div className="relative z-10">
      {/* nav */}
      <nav className="flex items-center justify-between px-6 md:px-12 py-3 border-b border-white/10 bg-[#0B0F16]/80 backdrop-blur sticky top-0 z-30">
        <div className="flex items-center gap-3">
          <img src="/tc-logo.png" alt="Orisei Truck Cleaning Solutions" className="h-12 w-auto drop-shadow-[0_0_14px_rgba(59,130,246,0.6)]" data-testid="wash-logo" />
          <div className="hidden sm:block leading-tight">
            <div className="font-black tracking-tight text-sm">ORISEI <span className="text-amber-400">TRUCK CLEANING</span></div>
            <div className="text-[9px] font-mono uppercase tracking-[0.25em] text-slate-500">Solutions · Est. 2023</div>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <a href="tel:7634434459" className="hidden sm:flex items-center gap-1.5 text-xs font-mono text-slate-400 hover:text-white transition-colors"><Phone size={12} /> (763) 443-4459</a>
          <a href="#book" data-testid="wash-nav-book-btn" className="px-5 py-2.5 rounded-full bg-amber-500 hover:bg-amber-400 transition-colors text-black text-xs font-black shadow-[0_0_20px_rgba(245,158,11,0.35)]">BOOK NOW</a>
        </div>
      </nav>

      {/* hero */}
      <section className="px-6 md:px-12 pt-14 pb-10 grid lg:grid-cols-[1.2fr_0.8fr] gap-10 items-center max-w-6xl">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-cyan-500/30 bg-cyan-500/10 text-[10px] font-mono uppercase tracking-[0.25em] text-cyan-300 mb-6">
            <MapPin size={11} /> Twin Cities · Mobile · At your yard
          </div>
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-black leading-[1.02]">
            Your cab.<br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-amber-300 via-amber-400 to-amber-500">Showroom clean.</span><br />
            Every time.
          </h1>
          <p className="mt-6 text-slate-400 max-w-xl text-sm md:text-base leading-relaxed">
            Professional semi-truck cab deep cleaning — we roll up to your yard with battery-powered gear,
            run our 45-minute 9-phase spec, and leave you time-stamped before/after proof. Flat rates, fleet discounts, zero downtime games.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <a href="#book" data-testid="wash-hero-book-btn" className="px-7 py-3.5 rounded-full bg-amber-500 hover:bg-amber-400 transition-colors text-black font-black text-sm inline-flex items-center gap-1.5 shadow-[0_0_28px_rgba(245,158,11,0.35)]">Book a cleaning <ChevronRight size={15} /></a>
            <a href="tel:7634434459" className="px-7 py-3.5 rounded-full border border-white/15 hover:border-white/40 transition-colors text-slate-200 font-bold text-sm">Call (763) 443-4459</a>
          </div>
          <div className="mt-10 flex flex-wrap gap-6 text-xs font-mono text-slate-500">
            <span className="flex items-center gap-1.5"><ShieldCheck size={13} className="text-emerald-400" /> Insured crews</span>
            <span className="flex items-center gap-1.5"><Camera size={13} className="text-cyan-300" /> Photo proof on every job</span>
            <span className="flex items-center gap-1.5"><Truck size={13} className="text-amber-400" /> Fleet rates from $110/cab</span>
          </div>
        </div>
        <div className="hidden lg:flex justify-center">
          <div className="relative">
            <div className="absolute inset-0 blur-3xl bg-blue-600/25 rounded-full scale-90" />
            <img src="/tc-logo.png" alt="Orisei shield" className="relative h-80 w-auto drop-shadow-[0_10px_40px_rgba(37,99,235,0.5)]" data-testid="wash-hero-shield" />
          </div>
        </div>
      </section>

      {/* stats band */}
      <section className="px-6 md:px-12 py-6 border-y border-white/10 bg-white/[0.02] backdrop-blur">
        <div className="max-w-5xl grid grid-cols-2 sm:grid-cols-4 gap-6" data-testid="wash-stats">
          {STATS.map(([v, l]) => (
            <div key={l} className="text-center sm:text-left">
              <div className="text-3xl font-black text-amber-400">{v}</div>
              <div className="text-[10px] font-mono uppercase tracking-widest text-slate-500 mt-1">{l}</div>
            </div>
          ))}
        </div>
      </section>

      {/* pricing */}
      <section className="px-6 md:px-12 py-14">
        <div className="text-[10px] font-mono uppercase tracking-[0.3em] text-cyan-300 mb-2">Flat rates · no surprises</div>
        <h2 className="text-lg font-black mb-6">Simple, flat pricing</h2>
        <div className="grid sm:grid-cols-3 gap-4 max-w-4xl" data-testid="wash-pricing">
          {[
            ["Single Cab", info ? `$${info.base_price}` : "$150", "One-time full 45-min showroom spec", false],
            ["Bi-Weekly Lock-In", info ? `$${info.sub_price}` : "$120", "Per cab · locked slot every 2 weeks · every 10th clean free", true],
            ["Fleet Rate", info ? `$${info.fleet_price}` : "$125", "Per cab · 10+ cabs · monthly billing", false],
          ].map(([t, p, d, hot]) => (
            <div key={t} className={`relative p-6 rounded-2xl border backdrop-blur transition-transform hover:-translate-y-1 ${hot ? "border-amber-500/60 bg-gradient-to-b from-amber-500/10 to-transparent shadow-[0_0_30px_rgba(245,158,11,0.15)]" : "border-white/10 bg-white/[0.03]"}`}>
              {hot && <div className="absolute -top-3 left-5 px-3 py-1 rounded-full bg-amber-500 text-black text-[9px] font-black uppercase tracking-widest">Most popular</div>}
              <div className="text-3xl font-black text-white">{p}<span className="text-xs text-slate-500 font-mono">/cab</span></div>
              <div className="text-sm font-bold mt-1">{t}</div>
              <div className="text-xs text-slate-500 mt-1">{d}</div>
            </div>
          ))}
        </div>
      </section>

      {/* how it works */}
      <section className="px-6 md:px-12 py-12 border-t border-white/10">
        <h2 className="text-lg font-black mb-6">How it works</h2>
        <div className="grid sm:grid-cols-3 gap-4 max-w-4xl">
          {STEPS.map((s, i) => {
            const Icon = s.icon;
            return (
              <div key={s.t} className="p-5 rounded-2xl border border-white/10 bg-white/[0.03] backdrop-blur hover:border-cyan-500/40 transition-colors">
                <div className="flex items-center gap-2 mb-3">
                  <span className="w-7 h-7 rounded-full bg-cyan-500/15 border border-cyan-500/40 grid place-items-center text-cyan-300 text-xs font-black">{i + 1}</span>
                  <Icon size={18} className="text-cyan-300" />
                </div>
                <div className="text-sm font-bold">{s.t}</div>
                <div className="text-xs text-slate-500 mt-1">{s.d}</div>
              </div>
            );
          })}
        </div>
        <div className="mt-8 max-w-4xl p-5 rounded-2xl border border-emerald-500/25 bg-emerald-500/[0.04] flex items-start gap-3" data-testid="wash-founding-offer">
          <Star size={18} className="text-emerald-300 shrink-0 mt-0.5" />
          <div>
            <div className="text-sm font-black text-emerald-300">FOUNDING YARD OFFER</div>
            <div className="text-xs text-slate-400 mt-1">First 3 yards to lock in a weekly or bi-weekly slot get their <b className="text-white">first 2 cabs cleaned FREE</b> on the pilot visit — and the founding rate locked for 12 months.</div>
          </div>
        </div>
      </section>

      {/* booking */}
      <section id="book" className="px-6 md:px-12 py-16 border-t border-white/10 bg-gradient-to-b from-white/[0.02] to-transparent">
        <div className="max-w-2xl">
          <div className="flex items-center gap-3 mb-1">
            <img src="/tc-logo.png" alt="" className="h-10 w-auto" />
            <h2 className="text-2xl font-black">Book your cleaning</h2>
          </div>
          <p className="text-xs text-slate-500 mt-1 mb-6">Tell us about your trucks — we confirm your slot within one business day.</p>
          {sent ? (
            <div className="p-8 rounded-2xl border border-emerald-500/40 bg-emerald-500/5 text-center" data-testid="wash-booking-success">
              <CheckCircle2 size={36} className="text-emerald-400 mx-auto mb-3" />
              <div className="font-black text-lg">Request received!</div>
              <div className="text-sm text-slate-400 mt-1">We'll confirm your slot within one business day. Need it faster? Call (763) 443-4459.</div>
            </div>
          ) : (
            <form onSubmit={submit} className="space-y-3 p-6 rounded-2xl border border-white/10 bg-[#0D1320]/80 backdrop-blur shadow-[0_20px_60px_rgba(0,0,0,0.4)]" data-testid="wash-booking-form">
              <div className="grid sm:grid-cols-2 gap-3">
                <input required value={form.company} onChange={(e) => setForm({ ...form, company: e.target.value })} placeholder="Company / owner-operator name *"
                  className="h-12 px-4 rounded-xl bg-[#0B0F16] border border-white/15 text-sm outline-none focus:border-amber-500 transition-colors" data-testid="wash-book-company" />
                <input value={form.contact} onChange={(e) => setForm({ ...form, contact: e.target.value })} placeholder="Contact name"
                  className="h-12 px-4 rounded-xl bg-[#0B0F16] border border-white/15 text-sm outline-none focus:border-amber-500 transition-colors" data-testid="wash-book-contact" />
                <input required value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} placeholder="Phone *"
                  className="h-12 px-4 rounded-xl bg-[#0B0F16] border border-white/15 text-sm outline-none focus:border-amber-500 transition-colors" data-testid="wash-book-phone" />
                <input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="Email"
                  className="h-12 px-4 rounded-xl bg-[#0B0F16] border border-white/15 text-sm outline-none focus:border-amber-500 transition-colors" data-testid="wash-book-email" />
                <input type="number" min="1" max="200" value={form.cabs} onChange={(e) => setForm({ ...form, cabs: e.target.value })} placeholder="Number of cabs"
                  className="h-12 px-4 rounded-xl bg-[#0B0F16] border border-white/15 text-sm outline-none focus:border-amber-500 transition-colors" data-testid="wash-book-cabs" />
                <input type="date" value={form.preferred_date} onChange={(e) => setForm({ ...form, preferred_date: e.target.value })}
                  className="h-12 px-4 rounded-xl bg-[#0B0F16] border border-white/15 text-sm outline-none focus:border-amber-500 transition-colors text-slate-400" data-testid="wash-book-date" />
              </div>
              {addons.length > 0 && (
                <div>
                  <div className="text-[10px] font-mono uppercase tracking-widest text-slate-500 mb-2">Popular add-ons (optional)</div>
                  <div className="flex flex-wrap gap-2">
                    {addons.map((s) => (
                      <button type="button" key={s.id} onClick={() => setSel(sel.includes(s.id) ? sel.filter((x) => x !== s.id) : [...sel, s.id])}
                        data-testid={`wash-addon-${s.id}`}
                        className={`px-3 py-2 rounded-full border text-xs font-bold transition-colors ${sel.includes(s.id) ? "border-amber-500 bg-amber-500/15 text-amber-300" : "border-white/15 text-slate-400 hover:border-white/40"}`}>
                        {s.label} +${s.price}
                      </button>
                    ))}
                  </div>
                </div>
              )}
              <textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} placeholder="Yard address, gate codes, anything we should know…"
                className="w-full min-h-[80px] p-4 rounded-xl bg-[#0B0F16] border border-white/15 text-sm outline-none focus:border-amber-500 transition-colors" data-testid="wash-book-notes" />
              <button disabled={busy} data-testid="wash-book-submit"
                className="w-full sm:w-auto px-9 py-3.5 rounded-full bg-amber-500 hover:bg-amber-400 transition-colors text-black font-black text-sm disabled:opacity-50 shadow-[0_0_24px_rgba(245,158,11,0.3)]">
                {busy ? "Sending…" : "REQUEST MY SLOT"}
              </button>
            </form>
          )}
        </div>
      </section>

      <footer className="px-6 md:px-12 py-8 border-t border-white/10 flex flex-wrap items-center justify-between gap-4 text-xs font-mono text-slate-600">
        <span className="flex items-center gap-2.5">
          <img src="/tc-logo.png" alt="" className="h-9 w-auto opacity-80" />
          Orisei Truck Cleaning Solutions · a division of Orisei Freight Solutions LLC · Est. 2023
        </span>
        <span className="flex items-center gap-4">
          <span className="flex items-center gap-1"><MapPin size={11} /> {info?.area || "Twin Cities metro"}</span>
          <a href="mailto:oliver@oriseifreightsolutions.com" className="flex items-center gap-1 hover:text-slate-400 transition-colors"><Mail size={11} /> Email us</a>
          <a href="/crew" className="text-slate-700 hover:text-slate-500 transition-colors" data-testid="wash-crew-link">Crew login</a>
        </span>
      </footer>
      </div>
    </div>
  );
}
