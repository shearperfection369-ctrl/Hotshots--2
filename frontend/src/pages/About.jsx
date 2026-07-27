import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { Card } from "../components/ui/card";
import {
  Truck, Sparkles, ShieldCheck, Plug, Palette, BarChart3, Globe2, Cpu, Zap,
  Building2, ChevronRight, MapPin, Briefcase, Users, ArrowRight, Award,
  CheckCircle2, ExternalLink, Mail
} from "lucide-react";

/**
 * Marketing landing page — public-facing pitch for the TMS. Reachable at /about
 * and at the root pre-login. Built around Oliver Cummins' 13-year story so
 * prospects know the platform is built by a practitioner, not a software house.
 */

const BRAND_REEL = [
  { name: "Orisei",       color: "#0E3A6B" },
  { name: "Walmart",      color: "#0071CE" },
  { name: "FedEx",        color: "#4D148C" },
  { name: "Caterpillar",  color: "#FFCD11" },
  { name: "Apple",        color: "#8E8E93" },
  { name: "Amazon",       color: "#FF9900" },
  { name: "Tesla",        color: "#CC0000" },
  { name: "Coca-Cola",    color: "#F40009" },
  { name: "Boeing",       color: "#0033A0" },
  { name: "Nike",         color: "#111111" },
];

const ERPS = [
  "SAP S/4HANA", "Oracle Fusion", "Microsoft D365 F&O", "NetSuite",
  "Infor M3", "Sage X3", "Epicor Kinetic", "IFS Cloud", "Custom REST",
];

const FEATURES = [
  { Icon: Palette,    title: "AI Company Themer",       body: "Type any company name → the entire app re-skins in seconds. Brand colors, sample data, supplier mix, fleet, lanes." },
  { Icon: Plug,       title: "9 ERP Integrations",      body: "SAP, Oracle, Dynamics, NetSuite, Infor, Sage, Epicor, IFS, or any REST API. One-click test, two-click activate." },
  { Icon: Truck,      title: "Multi-Modal Live Tracking", body: "Truckload, LTL, parcel, ocean, air, rail — all on one Leaflet map with pulsing markers, weather radar overlays, and storm alerts." },
  { Icon: BarChart3,  title: "45-Metric Carrier Scorecard", body: "OTD, on-time pickup, tender accept %, claims ratio, dwell, accessorial spend — auto-emailed to leadership weekly." },
  { Icon: ShieldCheck, title: "Trade Compliance Desk",  body: "All 11 Incoterms 2020 · Section 301/232 watch · USMCA · FTZ · drawback · broker portal · ACE filings." },
  { Icon: Cpu,        title: "AI Co-Pilot · HUDLINK",   body: "Draft carrier emails, summarize routing policies, lookup HS codes, extract BOL fields — all without leaving the workspace." },
  { Icon: Globe2,     title: "Specialty Carrier Roster", body: "White-glove, expedite, cross-border, and capacity-assurance carriers (Logix, Panther, Fastfrate, Ryan) on one page with live status." },
  { Icon: Zap,        title: "Truckload Booking Sheet", body: "The team's live shared board. Click any cell, auto-saves to the cloud. Retires the daily emailed spreadsheet for good." },
];

const STATS = [
  { v: "50+",  k: "Integrated Modules" },
  { v: "9",    k: "ERP Connectors" },
  { v: "16",   k: "Visual Themes" },
  { v: "200+", k: "API Endpoints" },
  { v: "77",   k: "Brand Directory" },
  { v: "45",   k: "Scorecard Metrics" },
];

export default function About() {
  const [brandIdx, setBrandIdx] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setBrandIdx((i) => (i + 1) % BRAND_REEL.length), 1800);
    return () => clearInterval(t);
  }, []);
  const active = BRAND_REEL[brandIdx];

  return (
    <div className="min-h-screen bg-[#0B0E14] text-white overflow-x-hidden">
      {/* Background grid */}
      <div
        className="fixed inset-0 opacity-[0.04] pointer-events-none"
        style={{
          backgroundImage: "linear-gradient(rgba(0,229,255,0.4) 1px,transparent 1px), linear-gradient(90deg,rgba(0,229,255,0.4) 1px,transparent 1px)",
          backgroundSize: "60px 60px",
        }}
      />
      {/* HEADER */}
      <header className="relative z-10 border-b border-white/5 bg-[#0B0E14]/80 backdrop-blur">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-400 to-cyan-600 flex items-center justify-center font-black text-black">H</div>
            <span className="font-display text-lg font-bold tracking-tight">Hot Shot TMS</span>
          </div>
          <nav className="flex items-center gap-6 text-sm font-mono uppercase tracking-wider text-slate-400">
            <a href="#features" className="hover:text-cyan-300">Features</a>
            <a href="#integrations" className="hover:text-cyan-300">Integrations</a>
            <a href="#founder" className="hover:text-cyan-300">Founder</a>
            <a href="#plan" className="hover:text-cyan-300">Plan</a>
            <Link to="/tms-investors" data-testid="about-cta-investors" className="px-3 py-1.5 border border-cyan-500/40 text-cyan-300 hover:bg-cyan-500/10 font-bold rounded text-xs">
              Investor Pitch
            </Link>
            <Link to="/login" data-testid="about-cta-login" className="px-3 py-1.5 bg-cyan-500 hover:bg-cyan-400 text-black font-bold rounded text-xs">
              Open the App →
            </Link>
          </nav>
        </div>
      </header>

      {/* HERO */}
      <section className="relative z-10 max-w-7xl mx-auto px-6 pt-20 pb-28">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-10 items-center">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-cyan-500/30 bg-cyan-500/10 text-cyan-300 text-[10px] font-mono uppercase tracking-[0.2em] mb-6">
              <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" /> Built by a Logistics Practitioner
            </div>
            <h1 className="font-display text-5xl md:text-7xl font-black leading-[1.05] tracking-tighter">
              One TMS.
              <br />
              <span className="inline-block transition-all" style={{ color: active.color }}>{active.name}.</span>
              <br />
              <span className="text-slate-500">Any Company.</span>
            </h1>
            <p className="mt-6 text-lg text-slate-300 leading-relaxed max-w-xl">
              The first Transportation Management System that <strong>re-themes itself for any
              company in minutes</strong>. Type the company name. Watch the entire app — colors,
              sample data, ERP context, suppliers, lanes — reshape around them.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link to="/tms-investors" data-testid="about-cta-primary" className="px-5 py-3 bg-cyan-500 hover:bg-cyan-400 text-black font-bold rounded inline-flex items-center gap-2">
                Watch the Live Demo <ArrowRight size={14} />
              </Link>
              <a href="#features" className="px-5 py-3 bg-white/5 hover:bg-white/10 text-white border border-white/10 rounded inline-flex items-center gap-2">
                See What's Inside <ChevronRight size={14} />
              </a>
            </div>
            <div className="mt-6 text-[10px] font-mono uppercase tracking-[0.2em] text-slate-500">
              v2.1 · Production · 250 active operators · Apr 2026
            </div>
          </div>

          {/* Theme reel mockup */}
          <div className="relative">
            <div className="absolute -inset-4 rounded-2xl blur-3xl opacity-30 transition-colors duration-700" style={{ background: active.color }} />
            <Card className="relative hud-surface p-8 border-2" style={{ borderColor: active.color + "66" }}>
              <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-slate-400 mb-1">Active Brand · Re-theming live</div>
              <div className="flex items-center gap-4">
                <div className="w-16 h-16 rounded-2xl flex items-center justify-center text-3xl font-black text-black transition-colors duration-700" style={{ background: active.color }}>
                  {active.name[0]}
                </div>
                <div>
                  <div className="font-display text-3xl font-bold">{active.name}</div>
                  <div className="text-xs font-mono text-slate-400">Themed automatically · {brandIdx + 1} / {BRAND_REEL.length}</div>
                </div>
              </div>
              <div className="mt-6 grid grid-cols-3 gap-3">
                {BRAND_REEL.slice(0, 9).map((b, i) => (
                  <div key={b.name} onClick={() => setBrandIdx(i)}
                       className={`p-3 rounded border cursor-pointer transition ${i === brandIdx ? "border-cyan-400 bg-cyan-500/10" : "border-white/10 hover:border-cyan-500/30"}`}>
                    <div className="w-6 h-6 rounded mb-2" style={{ background: b.color }} />
                    <div className="text-xs font-mono truncate">{b.name}</div>
                  </div>
                ))}
              </div>
              <div className="mt-6 text-[11px] text-slate-400 leading-relaxed">
                <Sparkles size={11} className="inline text-cyan-400 mr-1" />
                Type any company name → Claude Sonnet writes the brand profile → app re-skins instantly.
              </div>
            </Card>
          </div>
        </div>
      </section>

      {/* STATS BAR */}
      <section className="relative z-10 border-y border-cyan-500/20 bg-cyan-500/[0.03]">
        <div className="max-w-7xl mx-auto px-6 py-10 grid grid-cols-2 md:grid-cols-6 gap-6">
          {STATS.map((s) => (
            <div key={s.k}>
              <div className="font-display text-4xl font-black text-cyan-300 tabular-nums">{s.v}</div>
              <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-slate-400 mt-1">{s.k}</div>
            </div>
          ))}
        </div>
      </section>

      {/* FEATURES */}
      <section id="features" className="relative z-10 max-w-7xl mx-auto px-6 py-24">
        <div className="max-w-3xl">
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-2">FEATURES</div>
          <h2 className="font-display text-4xl md:text-5xl font-black tracking-tighter">
            Everything you'd need to run a control tower.
            <span className="text-cyan-400"> All on one screen.</span>
          </h2>
        </div>
        <div className="mt-12 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {FEATURES.map((f) => (
            <Card key={f.title} className="hud-surface p-5 hover:border-cyan-500/40 transition">
              <div className="p-2 rounded-lg inline-block bg-cyan-500/10 border border-cyan-500/20 mb-3">
                <f.Icon size={16} className="text-cyan-400" />
              </div>
              <h3 className="font-display text-lg font-bold mb-1">{f.title}</h3>
              <p className="text-sm text-slate-400 leading-relaxed">{f.body}</p>
            </Card>
          ))}
        </div>
      </section>

      {/* INTEGRATIONS */}
      <section id="integrations" className="relative z-10 max-w-7xl mx-auto px-6 py-24 border-t border-white/5">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 items-center">
          <div className="lg:col-span-5">
            <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-2">INTEGRATIONS</div>
            <h2 className="font-display text-4xl font-black tracking-tighter mb-6">Connect to <span className="text-cyan-400">your ERP</span> in two clicks.</h2>
            <p className="text-slate-300 leading-relaxed">
              Whatever your company runs on, the TMS speaks it. Drop your endpoint URL,
              paste in your service-user credentials, hit <strong>Test Connection</strong> — done.
              Live orders, shipments, customers and materials flow into the app immediately.
            </p>
            <ul className="mt-6 space-y-2">
              {["One-click test against live ERP", "Encrypted credentials at rest", "Multiple environments (PROD, QAS, DEV) side-by-side", "Auto-stub on brand activate"].map((line) => (
                <li key={line} className="flex items-start gap-2 text-sm text-slate-300">
                  <CheckCircle2 size={14} className="text-emerald-400 mt-0.5 shrink-0" />
                  {line}
                </li>
              ))}
            </ul>
          </div>
          <div className="lg:col-span-7 grid grid-cols-3 gap-3">
            {ERPS.map((e) => (
              <Card key={e} className="hud-surface p-4 hover:border-cyan-500/40 transition">
                <Plug size={14} className="text-cyan-400 mb-2" />
                <div className="text-sm font-bold">{e}</div>
                <div className="text-[10px] font-mono text-slate-500 mt-1">Native connector</div>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* FOUNDER */}
      <section id="founder" className="relative z-10 max-w-7xl mx-auto px-6 py-24 border-t border-white/5">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 items-start">
          <div className="lg:col-span-4">
            <div className="aspect-square rounded-2xl bg-gradient-to-br from-cyan-500/20 to-slate-900 border-2 border-cyan-500/30 flex items-center justify-center">
              <div className="text-center">
                <div className="w-32 h-32 mx-auto rounded-full bg-cyan-500 text-black flex items-center justify-center text-6xl font-black">OC</div>
                <div className="mt-4 font-display text-2xl font-bold">Oliver Cummins</div>
                <div className="text-xs font-mono text-cyan-300 mt-1">FOUNDER · BUILDER · OPERATOR</div>
              </div>
            </div>
          </div>
          <div className="lg:col-span-8">
            <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-2">THE FOUNDER</div>
            <h2 className="font-display text-4xl font-black tracking-tighter mb-4">
              Built by someone who's actually run the desk.
            </h2>
            <p className="text-slate-300 text-lg leading-relaxed">
              Most TMS platforms are designed by engineers who&rsquo;ve never tendered a load, never chased a
              short-shipped pallet at midnight, never fought a customs broker over an HS code. <strong className="text-cyan-300">Hot Shot TMS is different.</strong>
            </p>
            <p className="text-slate-300 mt-4 leading-relaxed">
              <strong>Oliver Cummins</strong> has spent <strong>13 years</strong> in supply chain &amp; logistics across all modes —
              truckload, LTL, parcel, ocean, air, and rail. He specializes in <strong>international logistics</strong>,
              with deep experience navigating ocean booking lanes, customs clearance, FTAs, and cross-border compliance.
              He&rsquo;s worked at several major Minnesota corporations and currently serves as a
              <strong className="text-cyan-300"> Transportation Analyst at Orisei Freight Solutions</strong>.
            </p>
            <p className="text-slate-300 mt-4 leading-relaxed">
              Who better to design a Transportation Management System than a tenured logistics professional
              who has personally lived every workflow it surfaces? Every screen in Hot Shot TMS was prototyped
              on real loads, real BOLs, real customer escalations.
            </p>

            <div className="mt-6 grid grid-cols-2 md:grid-cols-4 gap-3">
              <FounderStat v="13" k="Years in Logistics" />
              <FounderStat v="6" k="Modes Mastered" />
              <FounderStat v="MN" k="HQ State" />
              <FounderStat v="∞" k="Pallets Chased" />
            </div>

            <div className="mt-6 flex flex-wrap gap-2">
              <Pill Icon={MapPin}    label="Plymouth · MN" />
              <Pill Icon={Briefcase} label="Orisei Freight Solutions" />
              <Pill Icon={Globe2}    label="International Specialist" />
              <Pill Icon={Award}     label="13+ Years Operator" />
            </div>
          </div>
        </div>
      </section>

      {/* BUSINESS PLAN PREVIEW */}
      <section id="plan" className="relative z-10 max-w-7xl mx-auto px-6 py-24 border-t border-white/5">
        <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-2">THE BUSINESS</div>
        <h2 className="font-display text-4xl font-black tracking-tighter mb-10">
          The business case for an <span className="text-cyan-400">infinitely-themable</span> TMS.
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          <PlanCard title="Market" body="$15.3B global TMS market by 2030 (Gartner). Mid-market shippers ($100M–$2B revenue) are systematically underserved by SAP TM, Oracle OTM, and Manhattan." />
          <PlanCard title="The Wedge" body="60-second brand activation. Most TMS implementations take 6-18 months. Hot Shot TMS skins itself for the prospect's company DURING the sales call." />
          <PlanCard title="ARR Model" body="$24K/year base + $2K/integration + $0.10/shipment. 70% gross margin at scale, sub-$5K CAC via founder-led sales." />
          <PlanCard title="The Moat" body="Operator-built. Every feature shipped solves a real headache Oliver has lived. Software houses can't fake 13 years of muscle memory." />
          <PlanCard title="GTM" body="Founder-led for the first 25 logos. Convert 5 MN-based industrials by EOY 2026. Productize playbook in 2027." />
          <PlanCard title="Vision" body="A TMS that ships pre-skinned for every Fortune 1000 logistics team. One product, 1,000 themes, zero implementation lead time." />
        </div>
        <div className="mt-10 p-6 rounded-xl border border-cyan-500/30 bg-cyan-500/[0.05] text-center">
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-300 mb-2">CONTACT THE FOUNDER</div>
          <div className="font-display text-2xl font-bold mb-3">Want a demo skinned for your company?</div>
          <a href="mailto:oliver@oriseifreightsolutions.com" data-testid="about-contact-email" className="inline-flex items-center gap-2 px-5 py-3 bg-cyan-500 hover:bg-cyan-400 text-black font-bold rounded">
            <Mail size={14} /> oliver@oriseifreightsolutions.com
          </a>
        </div>
      </section>

      <footer className="relative z-10 border-t border-white/5 max-w-7xl mx-auto px-6 py-10 text-xs font-mono text-slate-500">
        <div className="flex justify-between flex-wrap gap-3">
          <div>© 2026 Hot Shot TMS · Built by Oliver Cummins · Plymouth, MN</div>
          <div className="flex items-center gap-4">
            <Link to="/tms-investors" className="hover:text-cyan-300">Investor Pitch</Link>
            <Link to="/login" className="hover:text-cyan-300">Sign In</Link>
            <a href="mailto:oliver@oriseifreightsolutions.com" className="hover:text-cyan-300">Contact</a>
          </div>
        </div>
      </footer>
    </div>
  );
}

function FounderStat({ v, k }) {
  return (
    <div className="p-3 rounded border border-white/10 bg-white/[0.02]">
      <div className="font-display text-3xl font-black text-cyan-300 tabular-nums">{v}</div>
      <div className="text-[10px] font-mono uppercase tracking-wider text-slate-400 mt-1">{k}</div>
    </div>
  );
}
function Pill({ Icon, label }) {
  return (
    <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded border border-white/10 bg-white/[0.02] text-xs text-slate-300">
      <Icon size={11} className="text-cyan-400" /> {label}
    </div>
  );
}
function PlanCard({ title, body }) {
  return (
    <Card className="hud-surface p-5">
      <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-1">{title}</div>
      <p className="text-sm text-slate-300 leading-relaxed">{body}</p>
    </Card>
  );
}
