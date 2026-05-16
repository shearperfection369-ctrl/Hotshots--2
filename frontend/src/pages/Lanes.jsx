/* eslint-disable */
import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { MapPin, Truck, ArrowRight } from "lucide-react";
import { api } from "../lib/api";
import PublicNav from "../components/PublicNav";
import PublicFooter from "../components/PublicFooter";

const GOLD = "#C9A24A";
const NAVY = "#0E3A6B";

const FALLBACK_LANES = [
  { origin: "Twin Cities, MN", destination: "Chicago, IL",        equipment: "Reefer",  miles: 410, notes: "Daily food-grade volume" },
  { origin: "Twin Cities, MN", destination: "Dallas, TX",         equipment: "Van",     miles: 980, notes: "OEM weekly" },
  { origin: "Saint Paul, MN",  destination: "Atlanta, GA",        equipment: "Reefer",  miles: 1180, notes: "Pharma cold-chain" },
  { origin: "Minneapolis, MN", destination: "Los Angeles, CA",    equipment: "Van",     miles: 1900, notes: "Retail consolidation" },
];

export default function Lanes() {
  const [brand, setBrand] = useState({});
  const [lanes, setLanes] = useState(FALLBACK_LANES);
  useEffect(() => {
    api.get("/branding").then(({ data }) => setBrand(data || {})).catch(() => {});
    fetch(`${process.env.REACT_APP_BACKEND_URL}/api/public/lanes`)
      .then((r) => r.json())
      .then((d) => { if (d?.lanes?.length) setLanes(d.lanes); })
      .catch(() => {});
  }, []);

  return (
    <div className="min-h-screen bg-[#0B1320] text-slate-100" data-testid="lanes-page">
      <PublicNav brand={brand} />

      {/* Hero */}
      <section className="max-w-7xl mx-auto px-6 pt-16 pb-10">
        <div className="text-[10px] font-mono uppercase tracking-[0.3em]" style={{ color: GOLD }}>Network strength</div>
        <h1 className="font-display font-black text-4xl md:text-5xl mt-3 leading-tight">
          Preferred lanes,<br/>
          <span style={{ color: GOLD }}>covered without drama.</span>
        </h1>
        <p className="text-slate-300 max-w-3xl mt-5 leading-relaxed">
          These are the corridors we run hardest — repeat carriers, predictable
          transit, and dispatcher discipline that keeps shippers and receivers
          on the same page. Got a lane that's not on the list? Send it anyway —
          we'll quote it the same hour.
        </p>
      </section>

      {/* Lanes table */}
      <section className="max-w-7xl mx-auto px-6 pb-16">
        <div
          className="rounded-xl border overflow-hidden"
          style={{ borderColor: `${GOLD}44` }}
        >
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead style={{ background: `${NAVY}99` }}>
                <tr className="text-[10px] font-mono uppercase tracking-wider" style={{ color: GOLD }}>
                  <th className="text-left px-4 py-3">Origin</th>
                  <th className="text-left px-4 py-3"></th>
                  <th className="text-left px-4 py-3">Destination</th>
                  <th className="text-left px-4 py-3">Equipment</th>
                  <th className="text-right px-4 py-3">Miles</th>
                  <th className="text-left px-4 py-3">Notes</th>
                </tr>
              </thead>
              <tbody>
                {lanes.map((l, idx) => (
                  <tr key={`${l.origin}-${l.destination}-${idx}`} className="border-t border-white/5 hover:bg-white/[0.03]" data-testid={`lane-row-${idx}`}>
                    <td className="px-4 py-3 font-medium">
                      <div className="flex items-center gap-2"><MapPin size={12} style={{ color: GOLD }} /> {l.origin}</div>
                    </td>
                    <td className="px-2"><ArrowRight size={14} className="text-slate-500" /></td>
                    <td className="px-4 py-3 font-medium">
                      <div className="flex items-center gap-2"><MapPin size={12} style={{ color: GOLD }} /> {l.destination}</div>
                    </td>
                    <td className="px-4 py-3">
                      <span className="inline-flex items-center gap-1.5 text-[11px] font-mono uppercase tracking-wider px-2 py-0.5 rounded"
                            style={{ background: "rgba(201,162,74,0.12)", color: GOLD }}>
                        <Truck size={11} /> {l.equipment}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-slate-300">{l.miles?.toLocaleString?.() || l.miles}</td>
                    <td className="px-4 py-3 text-slate-400 text-xs">{l.notes}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="max-w-5xl mx-auto px-6 py-20 text-center">
        <h2 className="font-display font-black text-3xl md:text-4xl">Got a lane that's not on the list?</h2>
        <p className="text-slate-300 mt-3 max-w-2xl mx-auto">
          We cover all 48 states with vetted carriers across every major corridor.
          Tell us what you're shipping — we'll quote it within the hour.
        </p>
        <div className="mt-7 flex flex-col sm:flex-row gap-3 justify-center">
          <Link
            to="/home#quote"
            data-testid="lanes-cta-quote"
            className="inline-flex items-center justify-center gap-2 px-7 py-3 rounded-md font-bold text-sm tracking-wider uppercase font-mono"
            style={{ background: GOLD, color: NAVY }}
          >
            Quote My Lane <ArrowRight size={14} />
          </Link>
        </div>
      </section>

      <PublicFooter brand={brand} />
    </div>
  );
}
