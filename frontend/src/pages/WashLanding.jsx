import React, { useEffect, useState } from "react";
import axios from "axios";
import { toast, Toaster } from "sonner";
import { Droplets, Sparkles, ShieldCheck, Clock, Camera, Truck, Phone, Mail, MapPin, ChevronRight, CheckCircle2 } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api/truck-cleaning`;

const STEPS = [
  { icon: Clock, t: "Book a slot", d: "Pick a date — we come to your yard, your dock, or your driveway." },
  { icon: Sparkles, t: "45-min showroom spec", d: "One cab, one crew, 45 minutes flat. Standardized 9-phase deep clean, every time." },
  { icon: Camera, t: "Before & after proof", d: "Time-stamped photos on every job. You see exactly what you paid for." },
];

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
    <div className="min-h-screen bg-[#0D1117] text-white" data-testid="wash-landing">
      <Toaster richColors position="top-center" />
      {/* nav */}
      <nav className="flex items-center justify-between px-6 md:px-12 py-4 border-b border-white/5">
        <div className="flex items-center gap-2">
          <Droplets size={22} className="text-amber-400" />
          <span className="font-black tracking-tight">ORISEI <span className="text-amber-400">TRUCK CLEANING</span></span>
        </div>
        <div className="flex items-center gap-4">
          <a href="tel:7634434459" className="hidden sm:flex items-center gap-1.5 text-xs font-mono text-slate-400"><Phone size={12} /> (763) 443-4459</a>
          <a href="#book" data-testid="wash-nav-book-btn" className="px-4 py-2 rounded-full bg-amber-500 text-black text-xs font-black">BOOK NOW</a>
        </div>
      </nav>

      {/* hero */}
      <section className="px-6 md:px-12 pt-16 pb-12 max-w-5xl">
        <div className="text-[10px] font-mono uppercase tracking-[0.3em] text-cyan-300 mb-4">Twin Cities · Mobile · At your yard</div>
        <h1 className="text-4xl sm:text-5xl lg:text-6xl font-black leading-[1.05]">
          Your cab.<br /><span className="text-amber-400">Showroom clean.</span><br />Every time.
        </h1>
        <p className="mt-5 text-slate-400 max-w-xl text-sm md:text-base">
          Professional semi-truck cab deep cleaning — we roll up to your yard with battery-powered gear,
          run our 45-minute 9-phase spec, and leave you time-stamped before/after proof. Flat rates, fleet discounts, zero downtime games.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <a href="#book" data-testid="wash-hero-book-btn" className="px-6 py-3 rounded-full bg-amber-500 text-black font-black text-sm inline-flex items-center gap-1.5">Book a cleaning <ChevronRight size={15} /></a>
          <a href="tel:7634434459" className="px-6 py-3 rounded-full border border-white/15 text-slate-200 font-bold text-sm">Call (763) 443-4459</a>
        </div>
        <div className="mt-10 flex flex-wrap gap-6 text-xs font-mono text-slate-500">
          <span className="flex items-center gap-1.5"><ShieldCheck size={13} className="text-emerald-400" /> Insured crews</span>
          <span className="flex items-center gap-1.5"><Camera size={13} className="text-cyan-300" /> Photo proof on every job</span>
          <span className="flex items-center gap-1.5"><Truck size={13} className="text-amber-400" /> Fleet rates from $125/cab</span>
        </div>
      </section>

      {/* pricing */}
      <section className="px-6 md:px-12 py-12 border-t border-white/5">
        <h2 className="text-lg font-black mb-6">Simple, flat pricing</h2>
        <div className="grid sm:grid-cols-3 gap-4 max-w-4xl" data-testid="wash-pricing">
          {[
            ["Single Cab", info ? `$${info.base_price}` : "$150", "One-time full 45-min showroom spec", false],
            ["Bi-Weekly Plan", info ? `$${info.sub_price}` : "$120", "Per cab · locked slot every 2 weeks", true],
            ["Fleet Rate", info ? `$${info.fleet_price}` : "$125", "Per cab · 10+ cabs · monthly billing", false],
          ].map(([t, p, d, hot]) => (
            <div key={t} className={`p-6 rounded-2xl border ${hot ? "border-amber-500/50 bg-amber-500/5" : "border-white/10 bg-slate-900/60"}`}>
              {hot && <div className="text-[9px] font-mono text-amber-400 uppercase tracking-widest mb-2">Most popular</div>}
              <div className="text-3xl font-black text-white">{p}<span className="text-xs text-slate-500 font-mono">/cab</span></div>
              <div className="text-sm font-bold mt-1">{t}</div>
              <div className="text-xs text-slate-500 mt-1">{d}</div>
            </div>
          ))}
        </div>
      </section>

      {/* how it works */}
      <section className="px-6 md:px-12 py-12 border-t border-white/5">
        <h2 className="text-lg font-black mb-6">How it works</h2>
        <div className="grid sm:grid-cols-3 gap-4 max-w-4xl">
          {STEPS.map((s) => {
            const Icon = s.icon;
            return (
              <div key={s.t} className="p-5 rounded-2xl border border-white/10 bg-slate-900/60">
                <Icon size={20} className="text-cyan-300 mb-3" />
                <div className="text-sm font-bold">{s.t}</div>
                <div className="text-xs text-slate-500 mt-1">{s.d}</div>
              </div>
            );
          })}
        </div>
      </section>

      {/* booking */}
      <section id="book" className="px-6 md:px-12 py-14 border-t border-white/5">
        <div className="max-w-2xl">
          <h2 className="text-2xl font-black">Book your cleaning</h2>
          <p className="text-xs text-slate-500 mt-1 mb-6">Tell us about your trucks — we confirm your slot within one business day.</p>
          {sent ? (
            <div className="p-8 rounded-2xl border border-emerald-500/40 bg-emerald-500/5 text-center" data-testid="wash-booking-success">
              <CheckCircle2 size={36} className="text-emerald-400 mx-auto mb-3" />
              <div className="font-black text-lg">Request received!</div>
              <div className="text-sm text-slate-400 mt-1">We'll confirm your slot within one business day. Need it faster? Call (763) 443-4459.</div>
            </div>
          ) : (
            <form onSubmit={submit} className="space-y-3" data-testid="wash-booking-form">
              <div className="grid sm:grid-cols-2 gap-3">
                <input required value={form.company} onChange={(e) => setForm({ ...form, company: e.target.value })} placeholder="Company / owner-operator name *"
                  className="h-12 px-4 rounded-xl bg-slate-900 border border-white/15 text-sm outline-none focus:border-amber-500" data-testid="wash-book-company" />
                <input value={form.contact} onChange={(e) => setForm({ ...form, contact: e.target.value })} placeholder="Contact name"
                  className="h-12 px-4 rounded-xl bg-slate-900 border border-white/15 text-sm outline-none focus:border-amber-500" data-testid="wash-book-contact" />
                <input required value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} placeholder="Phone *"
                  className="h-12 px-4 rounded-xl bg-slate-900 border border-white/15 text-sm outline-none focus:border-amber-500" data-testid="wash-book-phone" />
                <input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="Email"
                  className="h-12 px-4 rounded-xl bg-slate-900 border border-white/15 text-sm outline-none focus:border-amber-500" data-testid="wash-book-email" />
                <input type="number" min="1" max="200" value={form.cabs} onChange={(e) => setForm({ ...form, cabs: e.target.value })} placeholder="Number of cabs"
                  className="h-12 px-4 rounded-xl bg-slate-900 border border-white/15 text-sm outline-none focus:border-amber-500" data-testid="wash-book-cabs" />
                <input type="date" value={form.preferred_date} onChange={(e) => setForm({ ...form, preferred_date: e.target.value })}
                  className="h-12 px-4 rounded-xl bg-slate-900 border border-white/15 text-sm outline-none focus:border-amber-500 text-slate-400" data-testid="wash-book-date" />
              </div>
              {addons.length > 0 && (
                <div>
                  <div className="text-[10px] font-mono uppercase tracking-widest text-slate-500 mb-2">Popular add-ons (optional)</div>
                  <div className="flex flex-wrap gap-2">
                    {addons.map((s) => (
                      <button type="button" key={s.id} onClick={() => setSel(sel.includes(s.id) ? sel.filter((x) => x !== s.id) : [...sel, s.id])}
                        data-testid={`wash-addon-${s.id}`}
                        className={`px-3 py-2 rounded-full border text-xs font-bold ${sel.includes(s.id) ? "border-amber-500 bg-amber-500/15 text-amber-300" : "border-white/15 text-slate-400"}`}>
                        {s.label} +${s.price}
                      </button>
                    ))}
                  </div>
                </div>
              )}
              <textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} placeholder="Yard address, gate codes, anything we should know…"
                className="w-full min-h-[80px] p-4 rounded-xl bg-slate-900 border border-white/15 text-sm outline-none focus:border-amber-500" data-testid="wash-book-notes" />
              <button disabled={busy} data-testid="wash-book-submit"
                className="w-full sm:w-auto px-8 h-13 py-3.5 rounded-full bg-amber-500 text-black font-black text-sm disabled:opacity-50">
                {busy ? "Sending…" : "REQUEST MY SLOT"}
              </button>
            </form>
          )}
        </div>
      </section>

      <footer className="px-6 md:px-12 py-8 border-t border-white/5 flex flex-wrap items-center justify-between gap-3 text-xs font-mono text-slate-600">
        <span className="flex items-center gap-1.5"><Droplets size={12} className="text-amber-500" /> Orisei Truck Cleaning · a division of Orisei Freight Solutions LLC</span>
        <span className="flex items-center gap-4">
          <span className="flex items-center gap-1"><MapPin size={11} /> {info?.area || "Twin Cities metro"}</span>
          <a href="mailto:oliver@oriseifreightsolutions.com" className="flex items-center gap-1"><Mail size={11} /> Email us</a>
          <a href="/crew" className="text-slate-700 hover:text-slate-500" data-testid="wash-crew-link">Crew login</a>
        </span>
      </footer>
    </div>
  );
}
