/* eslint-disable jsx-a11y/anchor-is-valid */
import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Truck, Mail, ArrowRight, ShieldCheck, Wallet, Sparkles, MapPin, Phone } from "lucide-react";
import { api } from "../lib/api";

/**
 * Orisei Freight Solutions · public marketing landing page.
 * Lives at /home — separate from the internal app shell.
 * Pulls active brand colors + logos from /api/branding so it reflects whatever
 * tenant the platform is configured for (currently orisei-freight).
 */
export default function Landing() {
  const [brand, setBrand] = useState({
    company_name: "Orisei Freight Solutions LLC",
    tagline: "Operator-built freight brokerage · Minneapolis · Saint Paul",
    primary_color: "#0E3A6B",
    accent_color: "#C9A24A",
    logo_url: "/brand/orisei_logo.png",
    wordmark_url: "/brand/orisei_wordmark.png",
  });
  useEffect(() => {
    api.get("/branding").then(({ data }) => setBrand((b) => ({ ...b, ...(data || {}) }))).catch(() => {});
  }, []);

  const azure = brand.primary_color || "#0E3A6B";
  const gold  = brand.accent_color || "#C9A24A";

  return (
    <div className="min-h-screen bg-[#0B1320] text-slate-100" data-testid="orisei-landing">
      {/* Top bar */}
      <header className="sticky top-0 z-30 backdrop-blur-xl bg-[#0B1320]/85 border-b border-white/5">
        <div className="max-w-7xl mx-auto flex items-center justify-between px-6 py-3">
          <Link to="/home" className="flex items-center gap-3" data-testid="landing-logo-link">
            <img src={brand.logo_url} alt="Orisei" className="h-9 w-9 rounded" />
            <span className="font-display font-black text-lg tracking-tight" style={{ color: gold }}>
              ORISEI
              <span className="ml-2 text-xs font-mono text-slate-400 uppercase tracking-[0.2em]">Freight Solutions</span>
            </span>
          </Link>
          <nav className="hidden md:flex items-center gap-7 text-sm font-medium text-slate-300">
            <a href="#services" className="hover:text-white">Services</a>
            <a href="#why" className="hover:text-white">Why Orisei</a>
            <a href="#network" className="hover:text-white">Network</a>
            <a href="#contact" className="hover:text-white">Contact</a>
          </nav>
          <Link
            to="/login"
            data-testid="landing-signin-cta"
            className="text-xs font-mono uppercase tracking-wider px-4 py-2 rounded-md border border-white/10 hover:border-[#C9A24A]/60 hover:text-[#C9A24A] transition-colors"
          >
            Operator Sign-In →
          </Link>
        </div>
      </header>

      {/* Hero */}
      <section className="relative overflow-hidden">
        {/* Moorish-pattern decorative backdrop */}
        <div
          aria-hidden
          className="absolute inset-0 opacity-[0.10] pointer-events-none"
          style={{
            backgroundImage: `radial-gradient(${gold} 1px, transparent 1px), radial-gradient(${gold} 1px, transparent 1px)`,
            backgroundSize: "32px 32px, 64px 64px",
            backgroundPosition: "0 0, 16px 16px",
          }}
        />
        <div className="relative max-w-7xl mx-auto px-6 pt-16 pb-24 grid grid-cols-1 lg:grid-cols-12 gap-10 items-center">
          <div className="lg:col-span-7">
            <div
              className="inline-flex items-center gap-2 px-3 py-1 rounded-full border text-[10px] font-mono uppercase tracking-[0.2em] mb-6"
              style={{ borderColor: `${gold}55`, color: gold, background: `${gold}10` }}
            >
              <span className="inline-block w-1.5 h-1.5 rounded-full" style={{ background: gold }} /> Established 2026 · Minneapolis, MN
            </div>
            <h1 className="font-display font-black text-5xl md:text-6xl lg:text-7xl leading-[1.05] tracking-tight">
              Freight, moved with
              <span style={{ color: gold }}> operator-grade </span>
              discipline.
            </h1>
            <p className="mt-6 text-lg text-slate-300 max-w-2xl leading-relaxed">
              Orisei is a Twin Cities-based property freight brokerage built by a 13-year supply-chain practitioner.
              Every load runs through our proprietary command deck — DAT, Truckstop, Convoy, Uber Freight, and 123Loadboard
              aggregated into one margin-aware queue, with a named broker answering the phone at 2 a.m.
            </p>
            <div className="mt-8 flex flex-col sm:flex-row gap-3">
              <a
                href="#contact"
                data-testid="landing-hero-cta-quote"
                className="inline-flex items-center justify-center gap-2 px-6 py-3 rounded-md font-bold text-sm tracking-wider uppercase font-mono shadow-lg transition-transform hover:-translate-y-0.5"
                style={{ background: gold, color: azure }}
              >
                Request a lane quote <ArrowRight size={14} />
              </a>
              <Link
                to="/login"
                data-testid="landing-hero-cta-portal"
                className="inline-flex items-center justify-center gap-2 px-6 py-3 rounded-md font-bold text-sm tracking-wider uppercase font-mono border border-white/15 hover:border-[#C9A24A]/60 text-slate-200 hover:text-white"
              >
                Carrier portal sign-in
              </Link>
            </div>
            <div className="mt-10 grid grid-cols-3 gap-6 max-w-lg">
              {[
                { v: "13 yrs", l: "Founder logistics tenure" },
                { v: "5 modes", l: "TL · LTL · Reefer · Flat · Intermodal" },
                { v: "24/7", l: "Named-broker dispatch" },
              ].map((m) => (
                <div key={m.l} className="border-l-2 pl-3" style={{ borderColor: gold }}>
                  <div className="font-display font-black text-xl text-white">{m.v}</div>
                  <div className="text-[10px] font-mono uppercase tracking-wider text-slate-400 leading-tight mt-1">{m.l}</div>
                </div>
              ))}
            </div>
          </div>
          <div className="lg:col-span-5 flex items-center justify-center">
            <div
              className="relative rounded-3xl p-8 backdrop-blur-md"
              style={{ background: `linear-gradient(135deg, ${azure}cc, ${azure}aa 60%, ${gold}33)`, boxShadow: `0 25px 80px -20px ${azure}` }}
            >
              <img src={brand.logo_url} alt="Orisei mark" className="w-72 h-72 object-contain drop-shadow-2xl" data-testid="landing-hero-logo" />
              <div className="text-center mt-4 font-mono text-[10px] tracking-[0.3em] uppercase" style={{ color: gold }}>
                ◇ Khatim al-Sulayman ◇
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Services */}
      <section id="services" className="relative border-y border-white/5 bg-[#0E1830]/40">
        <div className="max-w-7xl mx-auto px-6 py-20">
          <div className="text-[10px] font-mono uppercase tracking-[0.3em]" style={{ color: gold }}>Services</div>
          <h2 className="font-display font-black text-3xl md:text-4xl mt-2 mb-12">Every mode. One accountable broker.</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {[
              { icon: Truck,       title: "Truckload · Dry Van",   body: "Daily MN/WI/IA outbound capacity, anchored on the Twin Cities → Chicago/Dallas/PNW lanes." },
              { icon: ShieldCheck, title: "Reefer · Cold Chain",   body: "Continuous-trace temp logs, pharma + food grade carriers vetted to USDA standards." },
              { icon: Wallet,      title: "Flatbed · Step-Deck",   body: "Tarped or open. Equipment from 48 ft to 53 ft step decks for OEM and ag flow." },
              { icon: Sparkles,    title: "Expedited · Power-Only", body: "Medical-device and automotive critical — drop-and-hook with team service when miles demand." },
              { icon: MapPin,      title: "Intermodal",            body: "BNSF ramp Twin Cities → Long Beach / Seattle / Memphis for cost-sensitive long lanes." },
              { icon: Mail,        title: "Operator-Grade Tech",   body: "Every load tracked through the Orisei Command Deck — real-time visibility, transparent margin, signed PODs in minutes." },
            ].map((s) => (
              <div key={s.title} className="rounded-xl border border-white/10 bg-white/[0.025] p-6 hover:border-[color:var(--accent-color)]/50 transition-colors"
                   style={{ "--accent-color": gold }}>
                <s.icon size={20} style={{ color: gold }} />
                <h3 className="font-display font-bold text-lg mt-3">{s.title}</h3>
                <p className="text-sm text-slate-400 mt-2 leading-relaxed">{s.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Why */}
      <section id="why" className="max-w-7xl mx-auto px-6 py-20">
        <div className="text-[10px] font-mono uppercase tracking-[0.3em]" style={{ color: gold }}>Why Orisei</div>
        <h2 className="font-display font-black text-3xl md:text-4xl mt-2 mb-12">Built on the shipper side. Operated by the founder.</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 items-start">
          <div className="space-y-4 text-slate-300 leading-relaxed text-[15px]">
            <p>
              Most freight brokerages are run by salespeople who learned the trade from a script. Orisei is run by a 13-year supply-chain practitioner who has personally tendered, tracked, escalated, and audited freight across every mode — including ocean, air, and customs-cleared international cargo.
            </p>
            <p>
              We know exactly what shippers wish their broker would do, because we used to be the one wishing it. That's our moat: when a load goes sideways at 2 a.m., you talk to the operator who designed the system, not a level-1 rep reading a script.
            </p>
            <blockquote className="border-l-2 pl-5 italic text-slate-200" style={{ borderColor: gold }}>
              "Orisei sets a standard for what a freight broker should be — accountable, transparent, and engineered." — Founder
            </blockquote>
          </div>
          <div className="rounded-2xl border p-6" style={{ borderColor: `${gold}55`, background: `${gold}08` }}>
            <h3 className="font-display font-bold text-lg mb-4" style={{ color: gold }}>Founder fact-sheet</h3>
            <dl className="space-y-3 text-sm">
              {[
                ["Founder", "Oliver Cummins"],
                ["Tenure", "13 years in supply chain & logistics"],
                ["Modes mastered", "TL · LTL · Parcel · Ocean · Air · Rail · Intermodal"],
                ["Specialization", "International logistics · customs · FTAs"],
                ["Current role", "Transportation Analyst · Tennant Companies"],
                ["HQ", "Minneapolis · Saint Paul · Minnesota"],
              ].map(([k, v]) => (
                <div key={k} className="grid grid-cols-3 gap-3 border-b border-white/5 pb-2 last:border-b-0">
                  <dt className="col-span-1 text-[11px] font-mono uppercase tracking-wider text-slate-500">{k}</dt>
                  <dd className="col-span-2 text-slate-200">{v}</dd>
                </div>
              ))}
            </dl>
          </div>
        </div>
      </section>

      {/* Network */}
      <section id="network" className="border-y border-white/5 bg-[#0E1830]/40">
        <div className="max-w-7xl mx-auto px-6 py-20">
          <div className="text-[10px] font-mono uppercase tracking-[0.3em]" style={{ color: gold }}>Network</div>
          <h2 className="font-display font-black text-3xl md:text-4xl mt-2 mb-12">Connected to every board that moves freight.</h2>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4 max-w-5xl">
            {["DAT One", "Truckstop", "Convoy", "Uber Freight", "123Loadboard", "RMIS", "Carrier411", "QuickBooks", "Macropoint", "TriumphPay"].map((p) => (
              <div key={p} className="rounded border border-white/10 bg-white/[0.02] py-4 text-center font-mono text-xs uppercase tracking-wider text-slate-300">
                {p}
              </div>
            ))}
          </div>
          <p className="mt-8 text-sm text-slate-500 max-w-3xl">
            Multi-source matching. Real margin transparency. Carrier vetting cleared in under 30 minutes through RMIS + Carrier411 + manual operator review. Every dollar of factor fee and quick-pay shown to the shipper on quarterly business reviews — no phantom rates, ever.
          </p>
        </div>
      </section>

      {/* Contact */}
      <section id="contact" className="max-w-7xl mx-auto px-6 py-20">
        <div className="rounded-2xl border p-10 text-center" style={{ borderColor: `${gold}55`, background: `linear-gradient(135deg, ${azure}cc, ${azure}99)` }}>
          <div className="text-[10px] font-mono uppercase tracking-[0.3em]" style={{ color: gold }}>Get in touch</div>
          <h2 className="font-display font-black text-3xl md:text-4xl mt-3">Have a lane? Let's quote it in 15 minutes.</h2>
          <p className="text-slate-300 mt-3 max-w-2xl mx-auto">
            Email us the origin, destination, equipment, and weekly volume — we'll send back a fixed-rate trial on your top 3 lanes within 24 business hours, with disclosed margin.
          </p>
          <div className="mt-7 flex flex-col sm:flex-row gap-3 justify-center">
            <a
              href="mailto:oliver@oriseifreight.com?subject=Lane%20quote%20request"
              data-testid="landing-contact-email"
              className="inline-flex items-center justify-center gap-2 px-6 py-3 rounded-md font-bold text-sm tracking-wider uppercase font-mono"
              style={{ background: gold, color: azure }}
            >
              <Mail size={14} /> oliver@oriseifreight.com
            </a>
            <a
              href="tel:+16125550117"
              data-testid="landing-contact-phone"
              className="inline-flex items-center justify-center gap-2 px-6 py-3 rounded-md font-bold text-sm tracking-wider uppercase font-mono border border-white/20 text-white"
            >
              <Phone size={14} /> (612) 555-0117
            </a>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-white/5 bg-[#080F1B]">
        <div className="max-w-7xl mx-auto px-6 py-8 flex flex-col md:flex-row items-center justify-between gap-4 text-xs text-slate-500">
          <div className="flex items-center gap-3">
            <img src={brand.logo_url} alt="Orisei" className="h-6 w-6" />
            <span>{brand.company_name} · Minneapolis · Saint Paul · Minnesota</span>
          </div>
          <div className="font-mono uppercase tracking-wider">© {new Date().getFullYear()} · MC# pending · BMC-84 surety bond filed</div>
        </div>
      </footer>
    </div>
  );
}
