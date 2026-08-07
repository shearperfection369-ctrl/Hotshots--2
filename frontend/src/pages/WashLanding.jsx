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

function ServicesMenu({ info }) {
  const services = info?.services || [];
  const groups = [
    { key: "car_detail_addon", title: "Full Car Detail Add-Ons", tag: "$150/car base", band: "bg-emerald-500", border: "border-emerald-500/30 hover:border-emerald-400/60", price: "bg-emerald-500/15 border-emerald-500/50 text-emerald-300", dot: "bg-emerald-400" },
    { key: "add_on", title: "Cab Add-On Services", tag: "Detail extras", band: "bg-violet-500", border: "border-violet-500/30 hover:border-violet-400/60", price: "bg-violet-500/15 border-violet-500/50 text-violet-300", dot: "bg-violet-400" },
    { key: "freshener", title: "Air Freshener Packages", tag: "Pick your scent", band: "bg-cyan-500", border: "border-cyan-500/30 hover:border-cyan-400/60", price: "bg-cyan-500/15 border-cyan-500/50 text-cyan-300", dot: "bg-cyan-400" },
    { key: "bedding", title: "Bedding & Pillow Service", tag: "Sleep like a hotel", band: "bg-rose-500", border: "border-rose-500/30 hover:border-rose-400/60", price: "bg-rose-500/15 border-rose-500/50 text-rose-300", dot: "bg-rose-400" },
  ];
  const core = ["Dashboard, console & vents detailed", "Full-cab vacuum — floor to bunk",
    "Seats deep-cleaned · stain & odor treatment", "Floor scrub — mats, pedals & undercarriage",
    "Windows & mirrors, inside and out", "Finishing scent — driver's pick"];
  const carCore = ["Full interior vacuum & wipe-down", "Exterior hand wash & dry",
    "Windows & mirrors, in and out", "Door jambs & console detailed",
    "Tire shine & wheel clean", "Finishing air freshener"];
  return (
    <section className="px-6 md:px-12 py-14 border-t border-white/10" data-testid="wash-services-menu">
      <div className="text-[10px] font-mono uppercase tracking-[0.3em] text-amber-400 mb-2">Full-color menu · everything we do</div>
      <h2 className="text-lg font-black mb-6">Services & pricing</h2>
      <div className="grid md:grid-cols-2 gap-4 max-w-5xl mb-5">
        <div className="p-5 rounded-2xl border border-emerald-500/30 bg-gradient-to-r from-emerald-500/10 to-transparent" data-testid="wash-core-spec">
          <div className="flex flex-wrap items-center gap-3 mb-3">
            <span className="px-3 py-1 rounded-full bg-emerald-500 text-black text-[10px] font-black uppercase tracking-widest">Included in every clean</span>
            <span className="text-sm font-black text-emerald-300">The 45-Minute Showroom Spec</span>
          </div>
          <div className="grid sm:grid-cols-2 gap-x-6 gap-y-2">
            {core.map((s) => (
              <div key={s} className="flex items-start gap-2 text-xs text-slate-300">
                <CheckCircle2 size={13} className="text-emerald-400 shrink-0 mt-0.5" />{s}
              </div>
            ))}
          </div>
        </div>
        <div className="p-5 rounded-2xl border border-amber-500/40 bg-gradient-to-r from-amber-500/10 to-transparent" data-testid="wash-car-detail-package">
          <div className="flex flex-wrap items-center gap-3 mb-1">
            <span className="px-3 py-1 rounded-full bg-amber-500 text-black text-[10px] font-black uppercase tracking-widest">New</span>
            <span className="text-sm font-black text-amber-300">Full Car Detail</span>
            <span className="ml-auto text-2xl font-black text-white">$150<span className="text-[11px] text-slate-500 font-mono">/car</span></span>
          </div>
          <div className="text-[11px] text-slate-400 mb-3">Not just trucks — we detail personal vehicles too. Complete inside &amp; out, base price includes:</div>
          <div className="grid sm:grid-cols-2 gap-x-6 gap-y-2">
            {carCore.map((s) => (
              <div key={s} className="flex items-start gap-2 text-xs text-slate-300">
                <CheckCircle2 size={13} className="text-amber-400 shrink-0 mt-0.5" />{s}
              </div>
            ))}
          </div>
          <a href="#book" className="inline-block mt-3 text-[11px] font-black text-amber-300 hover:text-amber-200" data-testid="wash-car-detail-book">Book a full detail →</a>
        </div>
      </div>
      <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4 max-w-5xl">
        {groups.map((g) => {
          const items = services.filter((s) => s.category === g.key);
          return (
            <div key={g.key} className={`rounded-2xl border ${g.border} bg-white/[0.03] backdrop-blur overflow-hidden transition-colors`} data-testid={`wash-services-${g.key}`}>
              <div className={`${g.band} px-4 py-2.5 flex items-center justify-between`}>
                <span className="text-xs font-black text-white uppercase tracking-wider">{g.title}</span>
                <span className="text-[9px] font-mono uppercase tracking-widest text-white/70">{g.tag}</span>
              </div>
              <div className="p-4 space-y-3">
                {items.map((s) => (
                  <div key={s.id} className="flex items-start justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-1.5 text-xs font-bold text-white"><span className={`w-1.5 h-1.5 rounded-full ${g.dot}`} />{s.label}</div>
                      <div className="text-[10px] text-slate-500 mt-0.5 leading-relaxed">{s.desc}</div>
                    </div>
                    <span className={`shrink-0 px-2.5 py-1 rounded-full border text-[11px] font-black ${g.price}`}>${s.price}</span>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
      {(info?.scents || []).length > 0 && (
        <div className="max-w-5xl mt-5" data-testid="wash-scent-menu">
          <div className="text-[10px] font-mono uppercase tracking-widest text-slate-500 mb-2">The scent menu — every driver picks</div>
          <div className="flex flex-wrap gap-2">
            {info.scents.map((s) => (
              <span key={s} className="px-3 py-1.5 rounded-full border border-cyan-500/30 bg-cyan-500/10 text-[11px] font-bold text-cyan-200">{s}</span>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

function BeforeAfterGallery() {
  const [pairs, setPairs] = useState([]);
  useEffect(() => { axios.get(`${API}/public/gallery`).then(({ data }) => setPairs((data.pairs || []).slice(0, 4))).catch(() => {}); }, []);
  if (!pairs.length) return null;
  return (
    <section className="px-6 md:px-12 py-14 border-t border-white/10" data-testid="wash-gallery">
      <div className="text-[10px] font-mono uppercase tracking-[0.3em] text-emerald-300 mb-2">Straight off our crews' phones · no staging</div>
      <h2 className="text-lg font-black mb-6">Real cabs. Real results.</h2>
      <div className="grid sm:grid-cols-2 gap-4 max-w-5xl">
        {pairs.map((p) => (
          <div key={p.job_id} className="rounded-2xl border border-white/10 bg-white/[0.03] overflow-hidden backdrop-blur hover:border-emerald-500/40 transition-colors" data-testid={`wash-gallery-pair-${p.job_id}`}>
            <div className="grid grid-cols-2">
              {[["BEFORE", p.before, "bg-rose-500"], ["AFTER", p.after, "bg-emerald-500"]].map(([label, id, chip]) => (
                <div key={label} className="relative">
                  <img src={`${API}/public/photo/${id}`} alt={`${label} — cab cleaning`} loading="lazy"
                    className="w-full h-44 object-cover" />
                  <span className={`absolute top-2 left-2 px-2 py-0.5 rounded ${chip} text-white text-[9px] font-black tracking-widest`}>{label}</span>
                </div>
              ))}
            </div>
            <div className="px-4 py-2.5 flex items-center justify-between text-[10px] font-mono text-slate-500">
              <span className="flex items-center gap-1.5"><Camera size={11} className="text-cyan-300" /> Time-stamped crew photo proof</span>
              <span>{p.date}</span>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

export default function WashLanding() {
  const [info, setInfo] = useState(null);
  const [form, setForm] = useState({ company: "", contact: "", phone: "", email: "", cabs: 1, preferred_date: "", notes: "" });
  const [plan, setPlan] = useState("one_time");
  const [scent, setScent] = useState("");
  const [sel, setSel] = useState([]);
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(null);
  useEffect(() => { axios.get(`${API}/public/site-info`).then(({ data }) => setInfo(data)).catch(() => {}); }, []);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const { data } = await axios.post(`${API}/public/booking`, { ...form, cabs: Number(form.cabs) || 1, services: sel, plan, scent });
      toast.success(data.message);
      setSent(data);
    } catch (e2) {
      toast.error(e2?.response?.data?.detail || "Something went wrong — call us at (763) 443-4459");
    } finally { setBusy(false); }
  };

  const services = info?.services || [];
  const planRates = { one_time: info?.base_price ?? 175, fleet: info?.fleet_price ?? 150, biweekly: info?.sub_price ?? 130, car_detail: info?.car_detail_price ?? 150 };
  const cabsN = Number(form.cabs) || 1;
  const isCar = plan === "car_detail";
  const unit = isCar ? "car" : "cab";
  const addonTotal = services.filter((s) => sel.includes(s.id)).reduce((a, s) => a + s.price, 0);
  const total = cabsN * planRates[plan] + addonTotal;
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
            <span className="flex items-center gap-1.5"><Truck size={13} className="text-amber-400" /> Lock-in rates from $110/cab</span>
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
            ["Single Cab", info ? `$${info.base_price}` : "$175", "One-time full 45-min showroom spec", false],
            ["Bi-Weekly Lock-In", info ? `$${info.sub_price}` : "$130", "Per cab · locked slot every 2 weeks · every 10th clean free", true],
            ["Fleet Rate", info ? `$${info.fleet_price}` : "$150", "Per cab · 10+ cabs · monthly billing", false],
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

      {/* full-color services menu */}
      <ServicesMenu info={info} />

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

      {/* before/after gallery */}
      <BeforeAfterGallery />

      {/* booking */}
      <section id="book" className="px-6 md:px-12 py-16 border-t border-white/10 bg-gradient-to-b from-white/[0.02] to-transparent">
        <div className="max-w-3xl">
          <div className="flex items-center gap-3 mb-1">
            <img src="/tc-logo.png" alt="" className="h-10 w-auto" />
            <h2 className="text-2xl font-black">Build your cleaning & book it</h2>
          </div>
          <p className="text-xs text-slate-500 mt-1 mb-6">Pick your plan, choose exactly what you want done, and our system schedules a crew instantly.</p>
          {sent ? (
            <div className="p-8 rounded-2xl border border-emerald-500/40 bg-emerald-500/5 text-center" data-testid="wash-booking-success">
              <CheckCircle2 size={36} className="text-emerald-400 mx-auto mb-3" />
              <div className="font-black text-lg">{sent.scheduled_date ? "You're on the schedule!" : "Request received!"}</div>
              <div className="text-sm text-slate-400 mt-1">{sent.message}</div>
              {sent.scheduled_date && (
                <div className="inline-flex flex-wrap justify-center gap-3 mt-4">
                  <span className="px-4 py-2 rounded-full bg-emerald-500/15 border border-emerald-500/40 text-emerald-300 text-xs font-black" data-testid="wash-booked-date">
                    {sent.scheduled_date}
                  </span>
                  {sent.tech_name && <span className="px-4 py-2 rounded-full bg-cyan-500/15 border border-cyan-500/40 text-cyan-300 text-xs font-black" data-testid="wash-booked-crew">
                    CREW: {sent.tech_name.toUpperCase()}
                  </span>}
                </div>
              )}
              <div className="text-xs text-slate-500 mt-4">Need to change anything? Call (763) 443-4459.</div>
            </div>
          ) : (
            <form onSubmit={submit} className="space-y-5 p-6 rounded-2xl border border-white/10 bg-[#0D1320]/80 backdrop-blur shadow-[0_20px_60px_rgba(0,0,0,0.4)]" data-testid="wash-booking-form">
              {/* 1 · plan */}
              <div>
                <div className="text-[10px] font-mono uppercase tracking-widest text-amber-400 mb-2">1 · Pick your plan</div>
                <div className="grid sm:grid-cols-2 gap-3" data-testid="wash-plan-picker">
                  {[["one_time", "One-Time Cab Clean", "Full 45-min spec · perfect trial", "cab"],
                    ["biweekly", "Bi-Weekly Lock-In", "Every 2 weeks · 10th clean FREE", "cab"],
                    ["fleet", "Fleet Program 10+", "Priority slots · monthly billing", "cab"],
                    ["car_detail", "Full Car Detail", "Complete interior + exterior detail", "car"]].map(([id, t, d, u]) => (
                    <button type="button" key={id} onClick={() => { setPlan(id); setSel([]); }} data-testid={`wash-plan-${id}`}
                      className={`p-4 rounded-xl border text-left transition-colors ${plan === id ? (id === "car_detail" ? "border-emerald-500 bg-emerald-500/10" : "border-amber-500 bg-amber-500/10") : "border-white/10 bg-white/[0.02] hover:border-white/30"}`}>
                      <div className="text-lg font-black">{`$${planRates[id]}`}<span className="text-[10px] text-slate-500 font-mono">/{u}</span></div>
                      <div className="text-xs font-bold mt-0.5">{t}</div>
                      <div className="text-[10px] text-slate-500 mt-0.5">{d}</div>
                    </button>
                  ))}
                </div>
              </div>
              {/* 2 · details */}
              <div>
                <div className="text-[10px] font-mono uppercase tracking-widest text-amber-400 mb-2">2 · Your yard & contact</div>
                <div className="grid sm:grid-cols-2 gap-3">
                  <input required value={form.company} onChange={(e) => setForm({ ...form, company: e.target.value })} placeholder="Company / owner-operator name *"
                    className="h-12 px-4 rounded-xl bg-[#0B0F16] border border-white/15 text-sm outline-none focus:border-amber-500 transition-colors" data-testid="wash-book-company" />
                  <input value={form.contact} onChange={(e) => setForm({ ...form, contact: e.target.value })} placeholder="Contact name"
                    className="h-12 px-4 rounded-xl bg-[#0B0F16] border border-white/15 text-sm outline-none focus:border-amber-500 transition-colors" data-testid="wash-book-contact" />
                  <input required value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} placeholder="Phone *"
                    className="h-12 px-4 rounded-xl bg-[#0B0F16] border border-white/15 text-sm outline-none focus:border-amber-500 transition-colors" data-testid="wash-book-phone" />
                  <input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="Email"
                    className="h-12 px-4 rounded-xl bg-[#0B0F16] border border-white/15 text-sm outline-none focus:border-amber-500 transition-colors" data-testid="wash-book-email" />
                  <div className="flex items-center gap-3 h-12 px-4 rounded-xl bg-[#0B0F16] border border-white/15">
                    <span className="text-xs text-slate-500 shrink-0 capitalize" data-testid="wash-unit-label">{unit}s</span>
                    <input type="number" min="1" max="200" value={form.cabs} onChange={(e) => setForm({ ...form, cabs: e.target.value })}
                      className="bg-transparent text-sm outline-none w-full" data-testid="wash-book-cabs" />
                  </div>
                  <div className="flex items-center gap-3 h-12 px-4 rounded-xl bg-[#0B0F16] border border-white/15">
                    <span className="text-xs text-slate-500 shrink-0">Preferred day</span>
                    <input type="date" value={form.preferred_date} onChange={(e) => setForm({ ...form, preferred_date: e.target.value })}
                      className="bg-transparent text-sm outline-none w-full text-slate-300" data-testid="wash-book-date" />
                  </div>
                </div>
              </div>
              {/* 3 · services */}
              <div>
                <div className="text-[10px] font-mono uppercase tracking-widest text-amber-400 mb-2">3 · Choose your extras <span className="text-slate-600">({isCar ? "the full interior + exterior detail is always included" : "the full 45-min showroom spec is always included"})</span></div>
                <div className="space-y-4" data-testid="wash-services-picker">
                  {(isCar
                    ? [["car_detail_addon", "Detail Add-Ons", "text-emerald-300 border-emerald-500/40"],
                       ["freshener", "Air Fresheners", "text-cyan-300 border-cyan-500/40"]]
                    : [["add_on", "Add-On Services", "text-violet-300 border-violet-500/40"],
                       ["freshener", "Air Fresheners", "text-cyan-300 border-cyan-500/40"],
                       ["bedding", "Bedding & Pillows", "text-rose-300 border-rose-500/40"]]
                  ).map(([cat, title, style]) => (
                    <div key={cat}>
                      <div className={`text-[10px] font-mono uppercase tracking-widest mb-1.5 ${style.split(" ")[0]}`}>{title}</div>
                      <div className="grid sm:grid-cols-2 gap-2">
                        {services.filter((s) => s.category === cat).map((s) => {
                          const on = sel.includes(s.id);
                          return (
                            <button type="button" key={s.id} data-testid={`wash-svc-${s.id}`}
                              onClick={() => setSel(on ? sel.filter((x) => x !== s.id) : [...sel, s.id])}
                              className={`flex items-start justify-between gap-2 p-3 rounded-xl border text-left transition-colors ${on ? `bg-white/[0.06] ${style.split(" ")[1]}` : "border-white/10 bg-white/[0.02] hover:border-white/25"}`}>
                              <span>
                                <span className={`text-xs font-bold ${on ? "text-white" : "text-slate-300"}`}>{on ? "✓ " : ""}{s.label}</span>
                                <span className="block text-[10px] text-slate-500 mt-0.5 leading-snug">{s.desc}</span>
                              </span>
                              <span className={`shrink-0 text-xs font-black ${on ? style.split(" ")[0] : "text-slate-500"}`}>+${s.price}</span>
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
              {/* 4 · scent */}
              <div>
                <div className="text-[10px] font-mono uppercase tracking-widest text-amber-400 mb-2">4 · Finishing scent <span className="text-slate-600">(included free)</span></div>
                <div className="flex flex-wrap gap-2" data-testid="wash-scent-picker">
                  {(info?.scents || []).map((s) => (
                    <button type="button" key={s} onClick={() => setScent(scent === s ? "" : s)} data-testid={`wash-scent-${s.replace(/[^a-z0-9]+/gi, "-").toLowerCase()}`}
                      className={`px-3 py-1.5 rounded-full border text-[11px] font-bold transition-colors ${scent === s ? "border-cyan-400 bg-cyan-500/15 text-cyan-200" : "border-white/15 text-slate-400 hover:border-white/40"}`}>
                      {scent === s ? "✓ " : ""}{s}
                    </button>
                  ))}
                </div>
              </div>
              <textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} placeholder="Yard address (helps us route the closest crew), gate codes, anything we should know…"
                className="w-full min-h-[80px] p-4 rounded-xl bg-[#0B0F16] border border-white/15 text-sm outline-none focus:border-amber-500 transition-colors" data-testid="wash-book-notes" />
              {/* total + submit */}
              <div className="flex flex-wrap items-center justify-between gap-4 p-4 rounded-xl border border-amber-500/30 bg-amber-500/[0.06]" data-testid="wash-booking-total">
                <div>
                  <div className="text-[10px] font-mono uppercase tracking-widest text-slate-500">Estimated per visit</div>
                  <div className="text-2xl font-black text-amber-400">${total.toLocaleString()}</div>
                  <div className="text-[10px] text-slate-500">{cabsN} {unit}{cabsN > 1 ? "s" : ""} × ${planRates[plan]}{addonTotal > 0 ? ` + $${addonTotal} extras` : ""} · pay after the {isCar ? "detail" : "clean"}</div>
                </div>
                <button disabled={busy} data-testid="wash-book-submit"
                  className="px-9 py-3.5 rounded-full bg-amber-500 hover:bg-amber-400 transition-colors text-black font-black text-sm disabled:opacity-50 shadow-[0_0_24px_rgba(245,158,11,0.3)]">
                  {busy ? "BOOKING…" : "BOOK IT — CREW AUTO-SCHEDULED"}
                </button>
              </div>
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
