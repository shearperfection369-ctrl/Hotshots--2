import React, { useEffect, useState, useMemo } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import PublicNav from "../components/PublicNav";
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid,
} from "recharts";
import {
  Download, ArrowRight, Target, TrendingUp, Shield, Briefcase, Sparkles,
  CheckCircle2, Linkedin, Mail, Send,
} from "lucide-react";

const REACT_APP_BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

/**
 * Public-facing executive summary at /investors — no auth required.
 * Polished one-pager designed for direct sharing from LinkedIn / Twitter / email.
 * Open Graph + Twitter Card meta tags injected for rich social previews.
 */
export default function PublicInvestors() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [form, setForm] = useState({
    name: "", email: "", firm: "", check_size_usd: "", linkedin: "", message: "", website: "",
  });

  useEffect(() => {
    const titleText = "Orisei Freight · Investor Executive Summary";
    document.title = titleText;
    setMetaTags();
    // Re-assert title after branding provider's async fetch completes (~500ms)
    const t1 = setTimeout(() => { document.title = titleText; }, 600);
    const t2 = setTimeout(() => { document.title = titleText; }, 1500);
    (async () => {
      try {
        const { data: d } = await axios.get(`${REACT_APP_BACKEND_URL}/api/public/investor-summary`);
        setData(d);
        const branded = `${d.brand.short_name} · Investor Executive Summary`;
        document.title = branded;
        setTimeout(() => { document.title = branded; }, 800);
        setMetaTags(d);
      } catch (e) { /* leave fallback rendering */ }
      finally { setLoading(false); }
    })();
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, []);

  const submit = async (e) => {
    e.preventDefault();
    if (!form.name || !form.email) return;
    setSubmitting(true);
    try {
      await axios.post(`${REACT_APP_BACKEND_URL}/api/public/investor-intro`, form);
      setSubmitted(true);
    } catch (err) { /* show inline state */ }
    finally { setSubmitting(false); }
  };

  const brand = data?.brand;
  const primary = brand?.primary_color || "#0E3A6B";
  const accent = brand?.accent_color || "#C9A24A";
  const company = brand?.company_name || "Orisei Freight Solutions LLC";
  const short = brand?.short_name || "Orisei";
  const founder = brand?.owner_name || "Oliver Cummins";
  const tagline = brand?.tagline || "Operator-built freight brokerage · Minneapolis · Saint Paul";

  const monthlyChartData = useMemo(() => (data?.monthly_revenue || []).map((m) => ({
    month: m.month, Revenue: m.revenue_usd,
  })), [data]);

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0B1320] text-white">
        <PublicNav brand={brand} />
        <div className="p-16 text-slate-400 text-center">Loading executive summary…</div>
      </div>
    );
  }
  if (!data) return null;

  const deckUrl = `${REACT_APP_BACKEND_URL}/api/public/deck.pdf`;
  const onePagerUrl = `${REACT_APP_BACKEND_URL}/api/public/one-pager.pdf`;

  return (
    <div className="min-h-screen bg-[#0B1320] text-white">
      <PublicNav brand={brand} />

      {/* HERO */}
      <section className="relative overflow-hidden border-b border-white/5"
               style={{ background: `radial-gradient(ellipse at 20% 0%, ${primary}55 0%, transparent 60%), #0B1320` }}
               data-testid="public-investors-hero">
        <div className="max-w-6xl mx-auto px-6 py-20 md:py-28 grid grid-cols-1 md:grid-cols-12 gap-10">
          <div className="md:col-span-7">
            <div className="text-[10px] font-mono uppercase tracking-[0.25em]" style={{ color: accent }}>
              Series Seed · Open SAFE round · Confidential investor summary
            </div>
            <h1 className="font-display text-5xl md:text-6xl font-black leading-[1.05] mt-3 tracking-tight"
                style={{ color: "#fff" }} data-testid="public-investors-headline">
              We're rebuilding the <span style={{ color: accent }}>freight brokerage</span> for operators
              who actually <span style={{ color: accent }}>answer the phone</span>.
            </h1>
            <p className="mt-5 text-lg text-slate-300 leading-relaxed max-w-xl">
              {short} pairs a 13-year founder with an operator-grade TMS — margin-aware
              load queue, auto-stamped BOLs, dock-photo PODs, and same-day quick-pay —
              built to take share from the mega-3PLs that have forgotten what shippers want.
            </p>
            <div className="mt-7 flex flex-wrap gap-3">
              <a href={deckUrl} target="_blank" rel="noopener noreferrer"
                 data-testid="public-investors-download-deck"
                 className="inline-flex items-center gap-2 px-5 py-3 rounded-md font-bold text-black"
                 style={{ background: accent }}>
                <Download size={16} /> Download Pitch Deck
              </a>
              <a href={onePagerUrl} target="_blank" rel="noopener noreferrer"
                 data-testid="public-investors-download-one-pager"
                 className="inline-flex items-center gap-2 px-5 py-3 rounded-md font-bold border-2 transition-colors"
                 style={{ borderColor: accent, color: accent }}>
                <Download size={16} /> One-Pager (PDF)
              </a>
              <a href="#intro" data-testid="public-investors-talk-cta"
                 className="inline-flex items-center gap-2 px-5 py-3 rounded-md text-sm text-slate-300 hover:text-white transition">
                Let's talk <ArrowRight size={14} />
              </a>
            </div>
            <div className="mt-7 flex flex-wrap items-center gap-4 text-xs font-mono text-slate-500">
              <span className="flex items-center gap-1.5"><CheckCircle2 size={12} style={{ color: accent }} /> {founder} · Founder</span>
              <span>•</span>
              <span className="flex items-center gap-1.5">{brand.headquarters}</span>
              <span>•</span>
              <span className="flex items-center gap-1.5"><Mail size={12} style={{ color: accent }} /> {brand.contact_email}</span>
            </div>
          </div>

          {/* Probability badge */}
          <div className="md:col-span-5 flex md:justify-end">
            <div className="rounded-2xl p-8 border-2 text-center w-full max-w-sm"
                 style={{ borderColor: accent, background: `${primary}88` }}
                 data-testid="public-probability-badge">
              <div className="text-[10px] font-mono uppercase tracking-[0.2em]" style={{ color: accent }}>
                Year-1 success probability
              </div>
              <div className="font-display text-7xl md:text-8xl font-black tabular-nums mt-2"
                   style={{ color: accent }}>
                {data.probability.score_pct.toFixed(0)}%
              </div>
              <div className="font-mono text-sm uppercase tracking-wider font-bold mt-1"
                   style={{ color: accent }}>
                {data.probability.band}
              </div>
              <div className="text-xs text-slate-300 mt-3 leading-relaxed">
                {data.probability.band_note}
              </div>
              <div className="text-[10px] text-slate-500 mt-3 italic">
                Methodology + sources in the full deck.
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* AT A GLANCE */}
      <section className="border-b border-white/5" data-testid="public-at-a-glance">
        <div className="max-w-6xl mx-auto px-6 py-14">
          <div className="text-[10px] font-mono uppercase tracking-[0.25em] mb-2" style={{ color: accent }}>
            The opportunity at a glance
          </div>
          <h2 className="font-display text-3xl md:text-4xl font-black mb-8" data-testid="at-a-glance-heading">
            A <span style={{ color: accent }}>$210B</span> industry where <span style={{ color: accent }}>32%</span> of new entrants fail
            because of solvable problems.
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <GlanceCard big={`$${data.market_sizing.tam.value_usd_billion}B`} label="TAM" sub="US freight brokerage · TIA 2024" accent={accent} />
            <GlanceCard big={`$${data.market_sizing.sam.value_usd_billion}B`} label="SAM" sub="Midwest TL/LTL property freight" accent={accent} />
            <GlanceCard big={`$${data.market_sizing.som_year3.value_usd_million}M`} label="Year-3 SOM" sub="Twin Cities + upper Midwest" accent={accent} />
            <GlanceCard big={`${data.headline_benchmarks.broker_failure_year1_pct}%`} label="Y1 broker failure" sub="SBA + TIA 2023 baseline" />
          </div>
        </div>
      </section>

      {/* WHY THIS WINS */}
      <section className="border-b border-white/5">
        <div className="max-w-6xl mx-auto px-6 py-14">
          <div className="text-[10px] font-mono uppercase tracking-[0.25em] mb-2" style={{ color: accent }}>Why this wins</div>
          <h2 className="font-display text-3xl md:text-4xl font-black mb-8">
            What we're solving — and why <span style={{ color: accent }}>operator-grade tooling</span> changes the math.
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <ReasonCard title="One named broker on every load" body="No call-center roulette. No pod-based shipper accounts. A direct cell phone answered in person — the way freight ran before brokerage scaled into anonymity." accent={accent} icon={Shield} />
            <ReasonCard title="Auto-stamped paperwork, every load" body="BOLs render in your shipper's inbox within seconds of booking. Photo PODs hit within seconds of delivery. Compliance hardened into the workflow — not bolted on after." accent={accent} icon={Sparkles} />
            <ReasonCard title="Same-day quick-pay → best carriers" body="2% quick-pay on every clean POD attracts the A-team owner-operators in our region. That carrier quality cascades straight back to shipper service." accent={accent} icon={TrendingUp} />
          </div>
        </div>
      </section>

      {/* FINANCIAL TRAJECTORY */}
      <section className="border-b border-white/5">
        <div className="max-w-6xl mx-auto px-6 py-14">
          <div className="text-[10px] font-mono uppercase tracking-[0.25em] mb-2" style={{ color: accent }}>3-year trajectory</div>
          <h2 className="font-display text-3xl md:text-4xl font-black mb-8">
            From bootstrap to <span style={{ color: accent }}>${(data.trajectory[2].revenue_usd / 1_000_000).toFixed(1)}M</span> revenue and <span style={{ color: accent }}>{data.trajectory[2].ebitda_margin_pct}%</span> EBITDA by Year 3.
          </h2>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
            {data.trajectory.map((y) => (
              <div key={y.year} className="rounded-xl p-5 border bg-white/[0.02]"
                   style={{ borderColor: `${accent}33` }} data-testid={`trajectory-y${y.year}`}>
                <div className="text-[10px] font-mono uppercase tracking-[0.2em]" style={{ color: accent }}>Year {y.year}</div>
                <div className="font-display text-3xl font-black mt-2 tabular-nums">${(y.revenue_usd / 1000).toFixed(0)}K</div>
                <div className="text-xs text-slate-400 mt-1">Revenue</div>
                <div className="grid grid-cols-2 gap-3 mt-4">
                  <div>
                    <div className="text-[9px] font-mono uppercase text-slate-500">Loads</div>
                    <div className="font-mono font-bold mt-0.5">{y.loads.toLocaleString()}</div>
                  </div>
                  <div>
                    <div className="text-[9px] font-mono uppercase text-slate-500">EBITDA</div>
                    <div className="font-mono font-bold mt-0.5" style={{ color: y.ebitda_usd >= 0 ? "#10B981" : "#EF4444" }}>
                      ${(y.ebitda_usd / 1000).toFixed(0)}K
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
          <div className="h-72 rounded-xl border p-4 bg-white/[0.02]" style={{ borderColor: `${accent}22` }}>
            <ResponsiveContainer>
              <AreaChart data={monthlyChartData} margin={{ left: 10, right: 10, top: 10, bottom: 0 }}>
                <defs>
                  <linearGradient id="pubRev" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={accent} stopOpacity={0.65} />
                    <stop offset="100%" stopColor={accent} stopOpacity={0.05} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="#1F2937" strokeDasharray="3 3" />
                <XAxis dataKey="month" tick={{ fill: "#94A3B8", fontSize: 10 }} interval={3} />
                <YAxis tick={{ fill: "#94A3B8", fontSize: 10 }} tickFormatter={(v) => `$${(v / 1000).toFixed(0)}K`} />
                <Tooltip contentStyle={{ background: "#0B0E14", border: `1px solid ${accent}55`, color: "#fff" }}
                  formatter={(v) => `$${Number(v).toLocaleString()}`} />
                <Area type="monotone" dataKey="Revenue" stroke={accent} strokeWidth={2} fill="url(#pubRev)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          <div className="text-xs text-slate-500 mt-3">Sources: {data.headline_benchmarks.sources.join(" · ")}</div>
        </div>
      </section>

      {/* THE ASK */}
      <section className="border-b border-white/5" style={{ background: `${primary}33` }} data-testid="public-the-ask">
        <div className="max-w-6xl mx-auto px-6 py-14 grid grid-cols-1 md:grid-cols-12 gap-10">
          <div className="md:col-span-5">
            <div className="text-[10px] font-mono uppercase tracking-[0.25em] mb-2" style={{ color: accent }}>The ask</div>
            <h2 className="font-display text-4xl md:text-5xl font-black leading-tight">
              <span style={{ color: accent }}>${(data.ask.amount_usd / 1000).toFixed(0)}K</span> SAFE at a <span style={{ color: accent }}>${(data.ask.valuation_cap_usd / 1_000_000).toFixed(1)}M cap</span> with a {data.ask.discount_pct}% discount.
            </h2>
            <p className="mt-5 text-slate-300 leading-relaxed max-w-md">
              First paying shipper within 30 days of close. Carrier network of 300+ by Day 90.
              Break-even by Month 9. Operating control retained.
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <a href={deckUrl} target="_blank" rel="noopener noreferrer"
                 className="inline-flex items-center gap-2 px-5 py-3 rounded-md font-bold text-black"
                 style={{ background: accent }}>
                Full deck (PDF) <ArrowRight size={14} />
              </a>
              <a href="#intro" className="inline-flex items-center gap-2 px-5 py-3 rounded-md border-2 transition-colors"
                 style={{ borderColor: accent, color: accent }}>
                Request the data room
              </a>
            </div>
          </div>
          <div className="md:col-span-7">
            <div className="text-[10px] font-mono uppercase tracking-[0.2em] mb-3" style={{ color: accent }}>Use of funds</div>
            <div className="space-y-2">
              {data.ask.use_of_funds.map((u, idx) => (
                <div key={idx} className="flex items-center justify-between px-4 py-3 rounded-md border"
                     style={{ borderColor: "rgba(255,255,255,0.06)", background: "rgba(255,255,255,0.02)" }}>
                  <div className="text-sm text-slate-200">{u.label}</div>
                  <div className="font-mono font-bold tabular-nums" style={{ color: accent }}>
                    ${u.amount_usd.toLocaleString()}
                  </div>
                </div>
              ))}
              <div className="flex items-center justify-between px-4 py-3 rounded-md font-bold mt-2"
                   style={{ background: accent, color: primary }}>
                <div>TOTAL</div>
                <div className="font-mono tabular-nums">${data.ask.amount_usd.toLocaleString()}</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* PROOF / TRACTION */}
      <section className="border-b border-white/5">
        <div className="max-w-6xl mx-auto px-6 py-14">
          <div className="text-[10px] font-mono uppercase tracking-[0.25em] mb-2" style={{ color: accent }}>Built, not theorized</div>
          <h2 className="font-display text-3xl md:text-4xl font-black mb-8">
            Things that already exist in production today.
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {data.proof_points.map((p, i) => (
              <div key={i} className="flex items-start gap-3 px-4 py-4 rounded-md border bg-white/[0.02]"
                   style={{ borderColor: `${accent}22` }}>
                <CheckCircle2 size={18} style={{ color: accent, flexShrink: 0, marginTop: 2 }} />
                <div className="text-sm text-slate-200 leading-relaxed">{p}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* INVESTOR INTRO FORM */}
      <section id="intro" className="border-b border-white/5" data-testid="public-intro-form-section">
        <div className="max-w-3xl mx-auto px-6 py-16">
          <div className="text-[10px] font-mono uppercase tracking-[0.25em] mb-2 text-center" style={{ color: accent }}>
            30-minute deep-dive
          </div>
          <h2 className="font-display text-3xl md:text-4xl font-black mb-3 text-center">
            Let's talk.
          </h2>
          <p className="text-center text-slate-400 mb-8 max-w-xl mx-auto">
            Drop your details below and we'll send the full data room within 24 hours plus
            three time slots for a 30-minute call.
          </p>

          {submitted ? (
            <div className="rounded-xl p-8 border-2 text-center"
                 style={{ borderColor: accent, background: `${accent}11` }}
                 data-testid="intro-thank-you">
              <CheckCircle2 size={42} style={{ color: accent }} className="mx-auto mb-3" />
              <h3 className="font-display text-2xl font-bold mb-2">Got it — thank you.</h3>
              <p className="text-slate-300 max-w-md mx-auto">
                {founder} will email you within 24 hours with the full data room and three
                time slots for a 30-minute deep-dive. Watch your inbox.
              </p>
            </div>
          ) : (
            <form onSubmit={submit} className="space-y-3" data-testid="intro-form">
              <input type="text" name="website" value={form.website} onChange={(e) => setForm({ ...form, website: e.target.value })}
                     style={{ position: "absolute", left: "-9999px" }} tabIndex={-1} autoComplete="off" />
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <FormField label="Your name" required value={form.name} testId="intro-name"
                  onChange={(v) => setForm({ ...form, name: v })} accent={accent} />
                <FormField label="Email" type="email" required value={form.email} testId="intro-email"
                  onChange={(v) => setForm({ ...form, email: v })} accent={accent} />
                <FormField label="Firm (optional)" value={form.firm} testId="intro-firm"
                  onChange={(v) => setForm({ ...form, firm: v })} accent={accent} />
                <FormField label="Typical check size (optional)" value={form.check_size_usd}
                  testId="intro-check" placeholder="e.g. $50K–$250K"
                  onChange={(v) => setForm({ ...form, check_size_usd: v })} accent={accent} />
              </div>
              <FormField label="LinkedIn (optional)" value={form.linkedin}
                placeholder="https://linkedin.com/in/…" testId="intro-linkedin"
                onChange={(v) => setForm({ ...form, linkedin: v })} accent={accent} />
              <div>
                <label className="text-[10px] font-mono uppercase tracking-[0.15em] text-slate-400 block mb-1.5">
                  Message (optional)
                </label>
                <textarea rows={4} value={form.message} data-testid="intro-message"
                  onChange={(e) => setForm({ ...form, message: e.target.value })}
                  className="w-full px-3 py-2 rounded border bg-[#0B0E14] text-white text-sm"
                  style={{ borderColor: "rgba(255,255,255,0.1)" }}
                  placeholder="What grabbed your attention? Anything specific you'd like to see in the deep-dive?" />
              </div>
              <button type="submit" disabled={submitting}
                      data-testid="intro-submit"
                      className="w-full mt-2 px-5 py-3 rounded-md font-bold text-black flex items-center justify-center gap-2 disabled:opacity-60"
                      style={{ background: accent }}>
                <Send size={14} /> {submitting ? "Sending…" : "Request the data room"}
              </button>
              <p className="text-[10px] text-slate-500 text-center mt-2">
                We'll only ever use your details to send the data room and schedule a single
                introductory call. No mailing list, no third-party sharing.
              </p>
            </form>
          )}
        </div>
      </section>

      {/* FOOTER */}
      <footer className="py-10 text-center text-xs text-slate-500" data-testid="public-investors-footer">
        <div className="max-w-6xl mx-auto px-6 flex flex-col md:flex-row gap-3 items-center justify-between">
          <div>{company} · {brand.headquarters}</div>
          <div className="flex items-center gap-4">
            <Link to="/home" className="hover:text-slate-200">Home</Link>
            <Link to="/services" className="hover:text-slate-200">Services</Link>
            <Link to="/lanes" className="hover:text-slate-200">Lanes</Link>
            <Link to="/contact" className="hover:text-slate-200">Contact</Link>
            <a href={`mailto:${brand.contact_email}`} className="hover:text-slate-200 inline-flex items-center gap-1"><Mail size={11} /> Email founder</a>
          </div>
        </div>
      </footer>
    </div>
  );
}

/* ---- subcomponents ---- */
function GlanceCard({ big, label, sub, accent }) {
  return (
    <div className="p-5 rounded-xl border bg-white/[0.02]"
         style={{ borderColor: accent ? `${accent}33` : "rgba(255,255,255,0.06)" }}
         data-testid={`glance-${label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`}>
      <div className="font-display text-3xl md:text-4xl font-black tabular-nums"
           style={accent ? { color: accent } : { color: "#fff" }}>
        {big}
      </div>
      <div className="text-sm font-medium mt-2 text-slate-200">{label}</div>
      <div className="text-[10px] text-slate-500 mt-1">{sub}</div>
    </div>
  );
}

function ReasonCard({ title, body, accent, icon: Icon }) {
  return (
    <div className="p-6 rounded-xl border bg-white/[0.02]" style={{ borderColor: `${accent}33` }}>
      <Icon size={20} style={{ color: accent }} />
      <h3 className="font-display text-lg font-bold mt-3 mb-2 text-white">{title}</h3>
      <p className="text-sm text-slate-300 leading-relaxed">{body}</p>
    </div>
  );
}

function FormField({ label, value, onChange, type = "text", required = false, placeholder, accent, testId }) {
  return (
    <div>
      <label className="text-[10px] font-mono uppercase tracking-[0.15em] text-slate-400 block mb-1.5">
        {label} {required && <span style={{ color: accent }}>*</span>}
      </label>
      <input
        type={type} value={value} required={required}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        data-testid={testId}
        className="w-full px-3 py-2 rounded border bg-[#0B0E14] text-white text-sm"
        style={{ borderColor: "rgba(255,255,255,0.1)" }}
      />
    </div>
  );
}

/* ---- Open Graph / Twitter Card meta ---- */
function setMetaTags(d) {
  const title = d
    ? `${d.brand.company_name} · Investor Executive Summary`
    : "Orisei Freight · Investor Executive Summary";
  const description = d
    ? `Series Seed · $${(d.ask.amount_usd / 1000).toFixed(0)}K SAFE @ $${(d.ask.valuation_cap_usd / 1_000_000).toFixed(1)}M cap. ${d.brand.short_name} — operator-built freight brokerage. Year-3 trajectory: $${(d.trajectory[2].revenue_usd / 1_000_000).toFixed(1)}M revenue at ${d.trajectory[2].ebitda_margin_pct}% EBITDA.`
    : "Operator-built freight brokerage. Series Seed round open.";
  const setMeta = (selector, attrs) => {
    let el = document.head.querySelector(selector);
    if (!el) {
      el = document.createElement("meta");
      Object.entries(attrs).forEach(([k, v]) => k !== "content" && el.setAttribute(k, v));
      document.head.appendChild(el);
    }
    el.setAttribute("content", attrs.content);
  };
  setMeta('meta[property="og:title"]',       { property: "og:title", content: title });
  setMeta('meta[property="og:description"]', { property: "og:description", content: description });
  setMeta('meta[property="og:type"]',        { property: "og:type", content: "website" });
  setMeta('meta[property="og:image"]',       { property: "og:image", content: `${window.location.origin}/brand/orisei_wordmark.png` });
  setMeta('meta[name="twitter:card"]',       { name: "twitter:card", content: "summary_large_image" });
  setMeta('meta[name="twitter:title"]',      { name: "twitter:title", content: title });
  setMeta('meta[name="twitter:description"]', { name: "twitter:description", content: description });
  setMeta('meta[name="description"]',        { name: "description", content: description });
}
