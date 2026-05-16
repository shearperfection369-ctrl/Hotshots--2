/* eslint-disable */
import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Truck, Snowflake, Container, Layers, Zap, Package, ShieldCheck,
  Mail, ArrowRight,
} from "lucide-react";
import { api } from "../lib/api";
import PublicNav from "../components/PublicNav";
import PublicFooter from "../components/PublicFooter";

const GOLD = "#C9A24A";
const NAVY = "#0E3A6B";

const SERVICES = [
  {
    Icon: Truck,
    title: "Truckload (TL)",
    blurb: "Dry-van, expedited, and team service across all 48 states. Named broker, signed BOL on tender, POD with photos in your inbox the moment we deliver.",
    bullets: ["48-state coverage", "Same-day cover on hot loads", "Owner-operator + asset-based fleets"],
  },
  {
    Icon: Snowflake,
    title: "Refrigerated (Reefer)",
    blurb: "FSMA-compliant cold-chain coverage for food-grade and pharma freight. Pre-cool checks, continuous temperature logging, and reefer-fuel management baked in.",
    bullets: ["FSMA Sanitary Transport Rule", "Continuous temp logging", "Pharma + food-grade trailers"],
  },
  {
    Icon: Layers,
    title: "Flatbed & Step-Deck",
    blurb: "Steel, machinery, oversize, and over-dimensional. Pre-checked tarps, chains, dunnage, and permitted oversize routing through our vetted carrier pool.",
    bullets: ["Tarps + chains + dunnage", "Permitted oversize routing", "Steel + machinery specialists"],
  },
  {
    Icon: Container,
    title: "LTL & Partial",
    blurb: "Less-than-truckload and partial-truckload programs with the major carriers — without the call-center roulette. One named human handles your account.",
    bullets: ["Daily pickups", "Liability + freight class guidance", "No surprise reclasses"],
  },
  {
    Icon: Zap,
    title: "Power-Only & Drop Trailers",
    blurb: "Your trailer pool, our drivers. Drop-and-hook programs with strict trailer-pool discipline and live trailer-status reporting.",
    bullets: ["Drop-trailer programs", "Trailer-pool discipline", "Live trailer reporting"],
  },
  {
    Icon: Package,
    title: "Specialty & Cross-Border",
    blurb: "Hot-shot, expedited, and cross-border into Canada (FAST-certified) + Mexico. Customs broker partnerships in place, no learning curve.",
    bullets: ["FAST-certified cross-border", "Hot-shot expedites", "Customs-broker partnerships"],
  },
];

const PROMISES = [
  { t: "60-minute quote", d: "Email back during business hours; after-hours by 7 a.m. CT." },
  { t: "Named broker", d: "Direct cell, direct text, direct email. No call-center routing." },
  { t: "Calafia-stamped BOL", d: "Professional paperwork on every load, every time." },
  { t: "POD in your inbox", d: "Signed Proof of Delivery + up to 3 dock photos within minutes of unload." },
  { t: "Real numbers, on time", d: "Margin-aware quoting, weekly lane reports, no fishing-for-margin nonsense." },
  { t: "Carrier vetting twice", d: "MC, DOT, CSA, insurance, and CSA scores re-checked before every booking." },
];

export default function Services() {
  const [brand, setBrand] = useState({});
  useEffect(() => { api.get("/branding").then(({ data }) => setBrand(data || {})).catch(() => {}); }, []);
  return (
    <div className="min-h-screen bg-[#0B1320] text-slate-100" data-testid="services-page">
      <PublicNav brand={brand} />

      {/* Hero */}
      <section className="max-w-7xl mx-auto px-6 pt-16 pb-10">
        <div className="text-[10px] font-mono uppercase tracking-[0.3em]" style={{ color: GOLD }}>Capabilities</div>
        <h1 className="font-display font-black text-4xl md:text-5xl mt-3 leading-tight">
          Six modes of freight,<br/>
          <span style={{ color: GOLD }}>one disciplined operation.</span>
        </h1>
        <p className="text-slate-300 max-w-3xl mt-5 leading-relaxed">
          Whether it's a one-off rescue cover at midnight or a 200-load weekly
          program, every shipment runs through the same dispatch desk, the same
          carrier-vetting workflow, and the same Calafia-stamped paperwork rhythm.
        </p>
      </section>

      {/* Service grid */}
      <section className="max-w-7xl mx-auto px-6 pb-16">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {SERVICES.map(({ Icon, title, blurb, bullets }) => (
            <div
              key={title}
              className="rounded-xl p-6 border bg-white/[0.02] hover:bg-white/[0.04] transition"
              style={{ borderColor: `${GOLD}33` }}
              data-testid={`service-${title.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`}
            >
              <Icon size={28} strokeWidth={1.5} style={{ color: GOLD }} />
              <h3 className="font-display font-bold text-xl mt-3">{title}</h3>
              <p className="text-slate-300 text-sm mt-2 leading-relaxed">{blurb}</p>
              <ul className="mt-4 space-y-1.5">
                {bullets.map((b) => (
                  <li key={b} className="text-xs text-slate-400 flex items-start gap-2">
                    <span style={{ color: GOLD }}>◆</span>
                    <span>{b}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </section>

      {/* Promises */}
      <section className="border-y border-white/5 bg-[#0E1830]/40">
        <div className="max-w-7xl mx-auto px-6 py-16">
          <div className="text-[10px] font-mono uppercase tracking-[0.3em]" style={{ color: GOLD }}>What every customer gets</div>
          <h2 className="font-display font-black text-3xl md:text-4xl mt-3">Six promises kept on every load.</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mt-8">
            {PROMISES.map((p) => (
              <div
                key={p.t}
                className="rounded p-4 border"
                style={{ borderColor: "rgba(255,255,255,0.06)" }}
              >
                <div className="flex items-center gap-2">
                  <ShieldCheck size={14} style={{ color: GOLD }} />
                  <div className="font-bold text-slate-100 text-sm">{p.t}</div>
                </div>
                <div className="text-xs text-slate-400 mt-1.5 leading-relaxed">{p.d}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="max-w-5xl mx-auto px-6 py-20 text-center">
        <h2 className="font-display font-black text-3xl md:text-4xl">Tender us your hardest load.</h2>
        <p className="text-slate-300 mt-3 max-w-2xl mx-auto">
          One named broker. One signed BOL. One POD with photos in your inbox before
          the receiver hands the keys back.
        </p>
        <div className="mt-7 flex flex-col sm:flex-row gap-3 justify-center">
          <Link
            to="/home#quote"
            data-testid="services-cta-quote"
            className="inline-flex items-center justify-center gap-2 px-7 py-3 rounded-md font-bold text-sm tracking-wider uppercase font-mono"
            style={{ background: GOLD, color: NAVY }}
          >
            Get a Quote <ArrowRight size={14} />
          </Link>
          <a
            href="mailto:oliver@oriseifreight.com"
            className="inline-flex items-center justify-center gap-2 px-7 py-3 rounded-md font-bold text-sm tracking-wider uppercase font-mono border border-white/15 text-white"
          >
            <Mail size={14} /> Email Us Direct
          </a>
        </div>
      </section>

      <PublicFooter brand={brand} />
    </div>
  );
}
