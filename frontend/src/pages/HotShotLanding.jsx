import React, { useEffect, useState } from "react";
import {
  Zap, Bot, Radar, Workflow, MapPinned, FileText, Check, ArrowRight, Loader2, PlayCircle, Flame,
  Route, FlaskConical, ShieldCheck, Receipt, Banknote, BookOpenCheck, Camera, Gavel, Network,
  Package, BarChart3, Users, CloudLightning, Gauge, HeartHandshake, Truck, Smartphone, Activity, Timer,
} from "lucide-react";
import { BACKEND_URL } from "../lib/api";

const TIERS = [
  { name: "Starter", price: "$600", founder: "$390", tag: "Core desk", feats: ["Core TMS + live GPS tracking", "Load aggregator feed", "Instant quote engine", "Rate cons, BOLs, invoices", "Email support"] },
  { name: "Growth", price: "$1,500", founder: "$975", tag: "Full AI suite", hot: true, feats: ["Everything in Starter", "AI Load Hunter — 24/7", "AI Triage playbooks", "Workflow automation + AR", "Route optimizer + margins", "Priority support"] },
  { name: "Done-With-You", price: "$4,000", founder: "$2,600", tag: "We run it with you", feats: ["Everything in Growth", "White-glove onboarding", "Weekly ops call w/ 13-yr operator", "Custom workflows", "Data migration included"] },
];

const FEATURES = [
  { icon: Radar, t: "AI Load Hunter", d: "Hunts DAT, Truckstop and Uber Freight around the clock, scoring every load against your lanes, trucks and margin floor. It finds the money while you sleep." },
  { icon: Bot, t: "AI Triage", d: "Breakdowns, detention, claims, fall-throughs — detected in real time and resolved with operator-grade playbooks. 49 CFR 370 clocks tracked automatically." },
  { icon: Workflow, t: "Workflow Automation", d: "Check calls, status emails, invoicing, factoring, AR aging and collections — chased automatically. Your desk runs itself." },
  { icon: MapPinned, t: "Live Ops Map", d: "Every load on a live map with real road routing, ETAs and exception flags. Your shippers see what you see." },
  { icon: FileText, t: "Paperwork on Autopilot", d: "Rate cons, BOLs, PODs and branded invoices generated, e-signed and filed. 3-year record retention built in." },
  { icon: Flame, t: "Growth Copilot", d: "An AI business partner that builds your plan to $20k/week net margin, briefs you every Monday, and never lets a compliance item slip." },
];

const CAPABILITY_MAP = [
  {
    cat: "AI SUITE — THE MOAT", color: "text-amber-400", border: "border-amber-500/30",
    items: [
      { icon: Radar, t: "AI Load Hunter", d: "24/7 board hunting, margin-floor scoring, lane matching" },
      { icon: Bot, t: "AI Triage Engine", d: "Exception detection + operator playbooks, 49 CFR 370 clocks" },
      { icon: Zap, t: "Dispatch Autopilot", d: "ML load-matching (gradient-boosted models, AUC 0.94)" },
      { icon: ShieldCheck, t: "Auto-Match + Margin Shield", d: "Top-3 carrier scoring, one-click tender, rate snapshots" },
      { icon: Flame, t: "AI Growth Copilot", d: "Weekly plan to $20k/wk net margin, tracked automatically" },
      { icon: Activity, t: "Agent Sentinel", d: "AI health checks watch your whole system, flags issues first" },
    ],
  },
  {
    cat: "LIVE OPERATIONS", color: "text-cyan-300", border: "border-cyan-500/30",
    items: [
      { icon: MapPinned, t: "Live GPS Ops Map", d: "Every load on a real-road map with ETAs + exception flags" },
      { icon: Route, t: "Route Optimizer", d: "Real OSRM road routing, fuel + margin calc per lane" },
      { icon: Network, t: "5-Board Load Aggregator", d: "DAT, Truckstop, Convoy, Uber Freight, 123Loadboard in one feed" },
      { icon: Truck, t: "Carrier Vetting", d: "Compliance traffic-lights: MC, CSA, insurance, blocklist checks" },
      { icon: Smartphone, t: "Driver Mobile PWA", d: "Drivers update status + upload dock photos from their phone" },
      { icon: FlaskConical, t: "Operational Sandbox", d: "Simulate a full 31-day brokerage month in minutes — real diesel prices, real overhead math" },
    ],
  },
  {
    cat: "MONEY & BACK OFFICE", color: "text-emerald-300", border: "border-emerald-500/30",
    items: [
      { icon: Receipt, t: "Auto-Invoice on POD", d: "Invoice fires the second delivery is confirmed — zero touch" },
      { icon: Banknote, t: "AR Aging + Collections", d: "Every unpaid dollar chased automatically, aging dashboard" },
      { icon: HeartHandshake, t: "Factoring + Quick-Pay", d: "Factoring assignments and quick-pay flows built in" },
      { icon: BookOpenCheck, t: "QuickBooks Sync", d: "Real Intuit OAuth — invoices land in your books" },
      { icon: Gauge, t: "Cash Flow Console", d: "Live cash position, receivables, payables in one view" },
      { icon: Users, t: "Carrier Loyalty Programs", d: "Bonus programs that lock in predictable capacity" },
    ],
  },
  {
    cat: "PAPERWORK & COMPLIANCE", color: "text-purple-300", border: "border-purple-500/30",
    items: [
      { icon: FileText, t: "Doc Engine", d: "Rate cons, BOLs, PODs, invoices — branded, generated, filed" },
      { icon: Camera, t: "POD Photo Capture", d: "Dock photos from the driver's camera, embedded in the POD PDF" },
      { icon: Gavel, t: "Claims Management", d: "49 CFR 370 claim clocks, acknowledgment + resolution tracking" },
      { icon: Package, t: "EDI + Parcel Rating", d: "EDI 204/210/214/990/856 plus FedEx & UPS live rating" },
      { icon: ShieldCheck, t: "Document Vault", d: "COIs, W-9s, contracts with multi-year retention" },
      { icon: CloudLightning, t: "Live Weather Alerts", d: "Real NWS watches/warnings on every lane you run" },
    ],
  },
  {
    cat: "INTELLIGENCE & REPORTING", color: "text-orange-300", border: "border-orange-500/30",
    items: [
      { icon: BarChart3, t: "45-Metric Carrier Scorecards", d: "OTP, claims, CSA, cost-per-mile — graded A+ to F" },
      { icon: Gauge, t: "Ops KPI Dashboard", d: "Cost/mile, gross margin %, fill rate, on-time % per lane" },
      { icon: Users, t: "Shipper CRM + Reports", d: "Relationship tracking + weekly shipper digest emails" },
      { icon: Timer, t: "Margin Analytics", d: "Forecast vs settled margin per board, per lane, per carrier" },
    ],
  },
];

const WEEK_ONE = [
  { day: "Day 1", t: "You're live", d: "Import your lanes and carriers, book your first load, generate your first branded rate con — all before lunch." },
  { day: "Day 2", t: "The AI starts hunting", d: "Load Hunter is scoring freight against your margin floor overnight. You wake up to a ranked list of money." },
  { day: "Day 3", t: "First zero-touch invoice", d: "A POD lands, the invoice fires itself, AR starts the clock. Nobody typed anything." },
  { day: "Day 5", t: "Your desk runs itself", d: "Check calls, status emails and collections chased automatically. Triage catches a detention before your customer calls." },
  { day: "Day 7", t: "You see the whole business", d: "KPI dashboard shows margin per lane, carrier grades, cash position. You run your Monday from one screen." },
];

const LIVE_STATS = [
  { label: "loads scored by AI / day", target: 1284 },
  { label: "modules in the platform", target: 40 },
  { label: "docs auto-generated / week", target: 312 },
  { label: "hrs of desk work saved / week", target: 31 },
];

function CountUp({ target }) {
  const [n, setN] = useState(0);
  useEffect(() => {
    let raf; const start = performance.now();
    const tick = (now) => {
      const p = Math.min((now - start) / 1400, 1);
      setN(Math.round(target * (1 - Math.pow(1 - p, 3))));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target]);
  return <>{n.toLocaleString()}</>;
}

export default function HotShotLanding() {
  const [form, setForm] = useState({ name: "", email: "", company: "", fleet_or_volume: "", tier_interest: "Growth", message: "" });
  const [sending, setSending] = useState(false);
  const [done, setDone] = useState(false);
  const [err, setErr] = useState("");
  const [roi, setRoi] = useState({ loads: 60, margin: 300, hours: 25 });
  const [demo, setDemo] = useState({ exists: false });

  useEffect(() => {
    fetch(`${BACKEND_URL}/api/hotshot/demo-video/status`).then((r) => r.json()).then(setDemo).catch(() => {});
  }, []);

  const deskSavings = Math.round(roi.hours * 0.65 * 25 * 4.33);
  const extraMargin = Math.round(roi.loads * 0.06 * roi.margin);
  const totalValue = deskSavings + extraMargin;
  const roiMultiple = (totalValue / 975).toFixed(1);

  const submit = async (e) => {
    e.preventDefault();
    setSending(true); setErr("");
    try {
      const r = await fetch(`${BACKEND_URL}/api/hotshot/leads`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(form),
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(typeof d?.detail === "string" ? d.detail : "Something went wrong");
      setDone(true);
    } catch (e2) { setErr(e2.message); } finally { setSending(false); }
  };

  const scrollTo = (id) => document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });

  return (
    <div className="min-h-screen bg-[#0D1117] text-slate-100" data-testid="hotshot-landing">
      {/* Nav */}
      <nav className="sticky top-0 z-40 backdrop-blur-md bg-[#0D1117]/90 border-b border-amber-500/20 px-5 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2 font-black tracking-tight text-lg">
          <Zap className="text-amber-400" size={20} /> HOT SHOT <span className="text-amber-400">TMS</span>
        </div>
        <div className="flex items-center gap-4 text-xs font-semibold">
          <button onClick={() => scrollTo("capabilities")} className="text-slate-300 hover:text-amber-300 hidden sm:block">Capabilities</button>
          <button onClick={() => scrollTo("pricing")} className="text-slate-300 hover:text-amber-300">Pricing</button>
          <a href={`${BACKEND_URL}/api/hotshot/one-pager.pdf`} className="text-slate-300 hover:text-amber-300">One-Pager</a>
          <button onClick={() => scrollTo("demo")} data-testid="hs-nav-demo-btn"
                  className="px-4 py-2 rounded-full bg-amber-500 text-black font-bold hover:bg-amber-400">Book a demo</button>
        </div>
      </nav>

      {/* Hero */}
      <section className="px-5 pt-16 pb-12 max-w-6xl mx-auto grid md:grid-cols-2 gap-10 items-center">
        <div>
          <div className="inline-flex items-center gap-2 text-[11px] font-mono uppercase tracking-[0.2em] text-amber-400 border border-amber-500/40 rounded-full px-3 py-1 mb-5">
            <Flame size={12} /> Founder rate · 35% off · first 5 clients
          </div>
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-black leading-[1.05] tracking-tight">
            The AI-driven TMS<br />built by a <span className="text-amber-400">working brokerage</span>.
          </h1>
          <p className="mt-5 text-slate-400 text-base leading-relaxed max-w-lg">
            Not a software company's idea of freight. Hot Shot TMS runs our own brokerage every single day —
            AI hunting loads, triaging exceptions, and chasing invoices while the operator sleeps.
            Now we're licensing it to a handful of small brokerages and owner-operators.
          </p>
          <div className="mt-7 flex flex-wrap gap-3">
            <button onClick={() => scrollTo("demo")} data-testid="hs-hero-demo-btn"
                    className="px-6 py-3 rounded-full bg-amber-500 text-black font-bold hover:bg-amber-400 inline-flex items-center gap-2">
              Watch it hunt loads <ArrowRight size={16} />
            </button>
            <button onClick={() => scrollTo("capabilities")} className="px-6 py-3 rounded-full border border-white/15 text-slate-200 hover:border-amber-400/50 font-semibold">
              See everything it does
            </button>
          </div>
          <div className="mt-8 flex gap-8 text-center">
            {[["24/7", "AI load hunting"], ["< 1 day", "to go live"], ["13 yrs", "operator DNA"]].map(([a, b]) => (
              <div key={b}><div className="text-2xl font-black text-amber-400">{a}</div><div className="text-[11px] text-slate-500 font-mono uppercase">{b}</div></div>
            ))}
          </div>
        </div>
        <img src="/hotshot/logo_wide.png" alt="Hot Shot TMS" className="rounded-2xl border border-amber-500/20 shadow-2xl shadow-amber-500/10" />
      </section>

      {/* Live stats strip */}
      <section className="px-5 py-6 border-y border-amber-500/20 bg-amber-500/[0.04]" data-testid="hs-live-stats">
        <div className="max-w-6xl mx-auto grid grid-cols-2 md:grid-cols-4 gap-4">
          {LIVE_STATS.map(({ label, target }) => (
            <div key={label} className="text-center">
              <div className="text-3xl font-black text-amber-400 tabular-nums"><CountUp target={target} />{label.includes("modules") ? "+" : ""}</div>
              <div className="text-[10px] text-slate-500 font-mono uppercase tracking-wider mt-1">{label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Who it's for */}
      <section className="px-5 py-10 border-b border-white/5 bg-white/[0.02]">
        <div className="max-w-6xl mx-auto grid sm:grid-cols-3 gap-4 text-sm">
          {[["Small brokerages · $500K–$5M/yr", "Replace spreadsheets and 2005-era TMS tools in one afternoon."],
            ["Owner-operators · 3–10 trucks", "Dispatch, margins and paperwork handled — compete with the big fleets."],
            ["New MC holders", "Your entire back office live on day one of your authority."]].map(([t, d]) => (
            <div key={t} className="p-4 rounded-xl border border-white/10">
              <div className="font-bold text-amber-300">{t}</div>
              <div className="text-slate-400 mt-1 text-[13px]">{d}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Headline features */}
      <section className="px-5 py-16 max-w-6xl mx-auto">
        <h2 className="text-lg font-black tracking-tight mb-8">THE AI DOES THE WORK. <span className="text-amber-400">YOU KEEP THE MARGIN.</span></h2>
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {FEATURES.map(({ icon: I, t, d }) => (
            <div key={t} className="p-5 rounded-xl border border-white/10 bg-white/[0.02] hover:border-amber-500/40 transition group">
              <I className="text-amber-400 mb-3 group-hover:scale-110 transition-transform" size={22} />
              <div className="font-bold text-white">{t}</div>
              <p className="text-[13px] text-slate-400 mt-1.5 leading-relaxed">{d}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Value in the first 7 days */}
      <section className="px-5 py-16 bg-white/[0.02] border-y border-white/5" data-testid="hs-week-one">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-lg font-black tracking-tight mb-2">VALUE YOU FEEL <span className="text-amber-400">IN THE FIRST 7 DAYS.</span></h2>
          <p className="text-slate-400 text-sm mb-8 max-w-2xl">No 6-month implementation. No consultants. Here's what your first week actually looks like.</p>
          <div className="grid md:grid-cols-5 gap-4">
            {WEEK_ONE.map(({ day, t, d }, i) => (
              <div key={day} className="relative p-4 rounded-xl border border-white/10 bg-[#0D1117] hover:border-amber-500/40 transition">
                <div className="text-[10px] font-mono uppercase tracking-widest text-amber-400 mb-1">{day}</div>
                <div className="font-bold text-white text-sm">{t}</div>
                <p className="text-[12px] text-slate-400 mt-1.5 leading-relaxed">{d}</p>
                {i < WEEK_ONE.length - 1 && <ArrowRight size={14} className="hidden md:block absolute -right-[13px] top-1/2 -translate-y-1/2 text-amber-500/60 z-10" />}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Full capability map */}
      <section id="capabilities" className="px-5 py-16 max-w-6xl mx-auto" data-testid="hs-capability-map">
        <h2 className="text-lg font-black tracking-tight mb-2">THE FULL PLATFORM. <span className="text-amber-400">40+ MODULES, ONE LOGIN.</span></h2>
        <p className="text-slate-400 text-sm mb-8 max-w-2xl">Everything below is live in production today — running real loads at our own brokerage. Nothing on this list is a roadmap slide.</p>
        <div className="space-y-8">
          {CAPABILITY_MAP.map(({ cat, color, border, items }) => (
            <div key={cat}>
              <div className={`text-[11px] font-mono uppercase tracking-[0.2em] ${color} mb-3`}>{cat}</div>
              <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {items.map(({ icon: I, t, d }) => (
                  <div key={t} className={`p-4 rounded-xl border ${border} bg-white/[0.02] hover:bg-white/[0.05] transition flex gap-3`}>
                    <I className={`${color} shrink-0 mt-0.5`} size={18} />
                    <div>
                      <div className="font-bold text-white text-sm">{t}</div>
                      <p className="text-[12px] text-slate-400 mt-0.5 leading-relaxed">{d}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Sandbox spotlight */}
      <section className="px-5 py-14 bg-amber-500/[0.04] border-y border-amber-500/20" data-testid="hs-sandbox-spotlight">
        <div className="max-w-6xl mx-auto grid md:grid-cols-2 gap-8 items-center">
          <div>
            <div className="inline-flex items-center gap-2 text-[11px] font-mono uppercase tracking-[0.2em] text-amber-400 mb-3">
              <FlaskConical size={13} /> Nobody else has this
            </div>
            <h2 className="text-2xl sm:text-3xl font-black tracking-tight">Test-drive a whole month of your brokerage <span className="text-amber-400">in five minutes.</span></h2>
            <p className="mt-4 text-slate-400 text-sm leading-relaxed">
              The Operational Sandbox simulates 31 days of your business with real industry math — live diesel prices,
              actual fixed overhead, real load-board dynamics, even your own trucks running under your authority.
              See what a hire, a new lane, or a rate drop does to your margin <em>before</em> you bet real money on it.
            </p>
            <ul className="mt-4 space-y-2 text-[13px] text-slate-300">
              {["Full 31-day month simulations with day-by-day P&L", "Real-time diesel prices + industry-accurate overhead", "Run your own company trucks alongside brokered freight", "AI builds and follows a plan to $20k/week net margin"].map((f) => (
                <li key={f} className="flex gap-2"><Check size={14} className="text-amber-400 mt-0.5 shrink-0" />{f}</li>
              ))}
            </ul>
          </div>
          <div className="p-6 rounded-2xl border border-amber-500/30 bg-[#0D1117]">
            <div className="text-[10px] font-mono uppercase tracking-widest text-slate-500 mb-3">Simulated month · sample output</div>
            {[["Loads moved", "127"], ["Gross revenue", "$286,400"], ["Net margin", "$41,200"], ["Margin per load", "$324"], ["AI plan status", "ON TRACK → $20k/wk"]].map(([k, v], i) => (
              <div key={k} className={`flex justify-between py-2.5 ${i < 4 ? "border-b border-white/5" : ""}`}>
                <span className="text-[13px] text-slate-400">{k}</span>
                <span className={`text-sm font-black ${i === 4 ? "text-emerald-400" : "text-amber-300"}`}>{v}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ROI calculator */}
      <section className="px-5 py-16 max-w-6xl mx-auto" data-testid="hs-roi-calculator">
        <h2 className="text-lg font-black tracking-tight mb-2">WHAT'S IT WORTH <span className="text-amber-400">TO YOUR DESK?</span></h2>
        <p className="text-slate-400 text-sm mb-8 max-w-2xl">Slide to your numbers. The math is conservative — 65% of admin time automated, 6% more booked loads from 24/7 AI hunting.</p>
        <div className="grid md:grid-cols-2 gap-8 items-center">
          <div className="space-y-6">
            {[
              { key: "loads", label: "Loads you move per month", min: 10, max: 500, step: 5, fmt: (v) => v },
              { key: "margin", label: "Average gross margin per load", min: 100, max: 800, step: 25, fmt: (v) => `$${v}` },
              { key: "hours", label: "Hours/week on paperwork, check calls & collections", min: 5, max: 60, step: 1, fmt: (v) => `${v} hrs` },
            ].map(({ key, label, min, max, step, fmt }) => (
              <div key={key}>
                <div className="flex justify-between text-sm mb-2">
                  <span className="text-slate-300">{label}</span>
                  <span className="font-black text-amber-400 tabular-nums">{fmt(roi[key])}</span>
                </div>
                <input type="range" min={min} max={max} step={step} value={roi[key]}
                       onChange={(e) => setRoi({ ...roi, [key]: Number(e.target.value) })}
                       data-testid={`hs-roi-${key}-slider`}
                       className="w-full h-2 rounded-full appearance-none bg-white/10 accent-amber-500 cursor-pointer" />
              </div>
            ))}
          </div>
          <div className="p-6 rounded-2xl border border-amber-500/40 bg-amber-500/[0.05]">
            <div className="text-[10px] font-mono uppercase tracking-widest text-slate-400 mb-4">Estimated monthly value</div>
            <div className="text-5xl font-black text-amber-400 tabular-nums" data-testid="hs-roi-total">${totalValue.toLocaleString()}<span className="text-lg text-slate-500 font-bold">/mo</span></div>
            <div className="mt-5 space-y-2.5">
              <div className="flex justify-between text-sm border-b border-white/5 pb-2.5">
                <span className="text-slate-400">Desk hours automated (65% × $25/hr)</span>
                <span className="font-bold text-white tabular-nums" data-testid="hs-roi-desk">${deskSavings.toLocaleString()}</span>
              </div>
              <div className="flex justify-between text-sm border-b border-white/5 pb-2.5">
                <span className="text-slate-400">Extra margin from 24/7 AI load hunting (+6%)</span>
                <span className="font-bold text-white tabular-nums" data-testid="hs-roi-extra">${extraMargin.toLocaleString()}</span>
              </div>
              <div className="flex justify-between text-sm pt-1">
                <span className="text-slate-300 font-semibold">Return on the Growth founder rate ($975/mo)</span>
                <span className="font-black text-emerald-400 tabular-nums" data-testid="hs-roi-multiple">{roiMultiple}×</span>
              </div>
            </div>
            <button onClick={() => scrollTo("demo")} data-testid="hs-roi-demo-btn"
                    className="mt-6 w-full py-3 rounded-full bg-amber-500 text-black font-black hover:bg-amber-400 inline-flex items-center justify-center gap-2">
              Lock in the founder rate <ArrowRight size={15} />
            </button>
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="px-5 py-16 bg-white/[0.02] border-b border-white/5">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-lg font-black tracking-tight mb-2">SIMPLE PRICING. <span className="text-amber-400">NO PER-SEAT GAMES.</span></h2>
          <p className="text-slate-400 text-sm mb-8">First 5 clients get the founder rate — 35% off for life, in exchange for a testimonial.</p>
          <div className="grid md:grid-cols-3 gap-5">
            {TIERS.map((t) => (
              <div key={t.name} data-testid={`hs-tier-${t.name.toLowerCase().replace(/[^a-z]/g, "")}`}
                   className={`p-6 rounded-2xl border ${t.hot ? "border-amber-500 bg-amber-500/5 shadow-xl shadow-amber-500/10" : "border-white/10"}`}>
                {t.hot && <div className="text-[10px] font-mono uppercase tracking-widest text-amber-400 mb-2">⚡ Most popular</div>}
                <div className="font-black text-xl">{t.name}</div>
                <div className="text-[11px] text-slate-500 font-mono uppercase">{t.tag}</div>
                <div className="mt-3 flex items-baseline gap-2">
                  <span className="text-3xl font-black text-amber-400">{t.founder}</span>
                  <span className="text-slate-500 line-through text-sm">{t.price}</span>
                  <span className="text-slate-500 text-xs">/mo founder</span>
                </div>
                <ul className="mt-4 space-y-2 text-[13px] text-slate-300">
                  {t.feats.map((f) => <li key={f} className="flex gap-2"><Check size={14} className="text-amber-400 mt-0.5 shrink-0" />{f}</li>)}
                </ul>
                <button onClick={() => { setForm((x) => ({ ...x, tier_interest: t.name })); scrollTo("demo"); }}
                        className={`mt-5 w-full py-2.5 rounded-full font-bold text-sm ${t.hot ? "bg-amber-500 text-black hover:bg-amber-400" : "border border-white/15 hover:border-amber-400/50"}`}>
                  Start with {t.name}
                </button>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Demo + lead capture */}
      <section id="demo" className="px-5 py-16 max-w-6xl mx-auto grid md:grid-cols-2 gap-10">
        <div>
          <h2 className="text-lg font-black tracking-tight mb-3">SEE THE AI <span className="text-amber-400">HUNT LOADS LIVE.</span></h2>
          <p className="text-slate-400 text-sm leading-relaxed mb-5">
            We don't do slide decks. On the demo you'll watch the Load Hunter score real freight,
            the Triage engine work an exception, and a full simulated brokerage month run in minutes.
            15 minutes, screen share, no fluff.
          </p>
          <div className="rounded-xl border border-white/10 bg-white/[0.02] aspect-video grid place-items-center overflow-hidden">
            {demo.exists ? (
              <video controls preload="metadata" className="w-full h-full bg-black" data-testid="hs-demo-video"
                     src={`${BACKEND_URL}/api/hotshot/demo-video`} />
            ) : (
              <div className="text-center">
                <PlayCircle className="text-amber-400 mx-auto mb-2" size={44} />
                <div className="text-sm text-slate-300 font-semibold">Demo video drops here soon</div>
                <div className="text-[11px] text-slate-500">Until then — book the live one. It's better anyway.</div>
              </div>
            )}
          </div>
          <a href={`${BACKEND_URL}/api/hotshot/one-pager.pdf`} data-testid="hs-onepager-link"
             className="mt-4 inline-flex items-center gap-2 text-sm text-amber-300 hover:text-amber-200 font-semibold">
            <FileText size={15} /> Download the one-pager (PDF)
          </a>
        </div>
        <div className="p-6 rounded-2xl border border-amber-500/30 bg-white/[0.02]">
          {done ? (
            <div className="text-center py-14" data-testid="hs-lead-success">
              <Check className="text-amber-400 mx-auto mb-3" size={40} />
              <div className="font-black text-xl">You're in.</div>
              <p className="text-slate-400 text-sm mt-2">We'll reach out within one business day to book your demo. Founder-rate seats are first come, first served.</p>
            </div>
          ) : (
            <form onSubmit={submit} className="space-y-3" data-testid="hs-lead-form">
              <div className="font-black">Book a demo</div>
              {[["name", "Your name *"], ["email", "Email *"], ["company", "Brokerage / company"], ["fleet_or_volume", "Trucks or loads per month"]].map(([k, ph]) => (
                <input key={k} required={ph.includes("*")} type={k === "email" ? "email" : "text"}
                       value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })}
                       placeholder={ph} data-testid={`hs-lead-${k}-input`}
                       className="w-full h-11 rounded-lg bg-[#0D1117] border border-white/15 px-3 text-sm placeholder:text-slate-600 focus:border-amber-400 outline-none" />
              ))}
              <select value={form.tier_interest} onChange={(e) => setForm({ ...form, tier_interest: e.target.value })}
                      data-testid="hs-lead-tier-select"
                      className="w-full h-11 rounded-lg bg-[#0D1117] border border-white/15 px-3 text-sm text-slate-300">
                {TIERS.map((t) => <option key={t.name}>{t.name}</option>)}
              </select>
              <textarea value={form.message} onChange={(e) => setForm({ ...form, message: e.target.value })}
                        placeholder="Anything we should know?" rows={2} data-testid="hs-lead-message-input"
                        className="w-full rounded-lg bg-[#0D1117] border border-white/15 px-3 py-2 text-sm placeholder:text-slate-600 focus:border-amber-400 outline-none" />
              {err && <div className="text-xs text-red-400" data-testid="hs-lead-error">{err}</div>}
              <button type="submit" disabled={sending} data-testid="hs-lead-submit-btn"
                      className="w-full py-3 rounded-full bg-amber-500 text-black font-black hover:bg-amber-400 inline-flex items-center justify-center gap-2 disabled:opacity-60">
                {sending ? <Loader2 size={16} className="animate-spin" /> : <Zap size={16} />} Claim a founder-rate demo
              </button>
            </form>
          )}
        </div>
      </section>

      <footer className="px-5 py-8 border-t border-white/5 text-center text-[11px] text-slate-500 font-mono">
        HOT SHOT TMS · built &amp; battle-tested by Orisei Freight Solutions LLC · Minnesota · oliver@oriseifreight.com
      </footer>
    </div>
  );
}
