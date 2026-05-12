import React, { useEffect, useState } from "react";
import Topbar from "../components/Topbar";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Truck, Phone, Mail, Globe, ExternalLink, Shield, Award, Star, Activity } from "lucide-react";
import { toast } from "sonner";

/**
 * SpecialtyCarriers · dedicated profile page for Tennant's priority,
 * white-glove, and capacity-assurance carriers:
 *   - Logix Transportation (pad-wrap machine specialist)
 *   - ArcBest · Panther Premium (expedite)
 *   - Fastfrate Group (cross-border CA ↔ US)
 *   - Ryan Transportation (strategic 3PL / capacity)
 *
 * Each carrier card includes contact info, direct tracking lookup,
 * specialty services, and a YTD performance strip.
 */

function Initials({ initials, color }) {
  return (
    <div
      className="w-14 h-14 rounded-xl flex items-center justify-center font-display text-xl font-bold shrink-0"
      style={{ background: color + "22", border: `1px solid ${color}66`, color }}
    >
      {initials}
    </div>
  );
}

function Stat({ label, value, accent = "text-cyan-300" }) {
  return (
    <div className="text-center px-3 py-2 rounded border border-white/5 bg-white/[0.02]">
      <div className="text-[9px] font-mono uppercase tracking-wider text-slate-500">{label}</div>
      <div className={`text-lg font-display font-bold mt-0.5 ${accent}`}>{value}</div>
    </div>
  );
}

function CarrierCard({ c }) {
  const [tracking, setTracking] = useState("");

  const openTracking = () => {
    const t = tracking.trim();
    if (!t) { toast.error("Enter a tracking / reference number first"); return; }
    const url = c.tracking_url.replace("{tracking}", encodeURIComponent(t));
    window.open(url, "_blank", "noopener,noreferrer");
  };

  return (
    <Card
      className="hud-surface p-5 overflow-hidden relative"
      data-testid={`specialty-carrier-${c.id}`}
    >
      <div
        className="absolute inset-x-0 top-0 h-0.5"
        style={{ background: `linear-gradient(90deg, ${c.color}00, ${c.color}, ${c.color}00)` }}
      />
      <div className="flex items-start gap-4 flex-wrap">
        <Initials initials={c.logo_initials} color={c.color} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="font-display text-xl font-bold text-white">{c.name}</h3>
            <span
              className="px-2 py-0.5 rounded text-[9px] font-mono uppercase tracking-wider border"
              style={{ background: c.color + "1A", color: c.color, borderColor: c.color + "55" }}
            >
              {c.priority}
            </span>
          </div>
          <div className="text-[11px] font-mono mt-0.5" style={{ color: c.color }}>{c.tagline}</div>
          <p className="text-sm text-slate-300 mt-2 leading-relaxed">{c.summary}</p>
        </div>
      </div>

      {/* Specialty chips */}
      <div className="mt-4">
        <div className="text-[9px] font-mono uppercase tracking-wider text-slate-500 mb-1.5">Specialty Services</div>
        <div className="flex flex-wrap gap-1.5">
          {c.specialty.map((s) => (
            <span key={s} className="px-2 py-0.5 rounded text-[10px] font-mono bg-white/[0.04] text-slate-200 border border-white/10">
              {s}
            </span>
          ))}
        </div>
      </div>

      {/* Performance strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-4">
        <Stat label="YTD Loads" value={c.ytd_loads.toLocaleString()} accent="text-cyan-300" />
        <Stat label="On-Time %" value={`${c.on_time_pct}%`} accent="text-emerald-300" />
        <Stat label="Claim Rate" value={`${c.claim_rate_pct}%`} accent="text-yellow-300" />
        <Stat label="Partner Since" value={c.since} accent="text-slate-300" />
      </div>

      {/* Contact + tracking */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-4">
        <div className="p-3 rounded border border-white/5 bg-white/[0.02]">
          <div className="text-[9px] font-mono uppercase tracking-wider text-slate-500 mb-1.5 flex items-center gap-1">
            <Phone size={9} /> Contact
          </div>
          <div className="text-xs font-mono text-cyan-200">{c.contact.name}</div>
          <div className="text-xs font-mono text-slate-300 flex items-center gap-1 mt-0.5">
            <Phone size={10} /> <a href={`tel:${c.contact.phone}`} className="hover:text-cyan-300">{c.contact.phone}</a>
          </div>
          <div className="text-xs font-mono text-slate-300 flex items-center gap-1 mt-0.5">
            <Mail size={10} /> <a href={`mailto:${c.contact.email}`} className="hover:text-cyan-300 truncate">{c.contact.email}</a>
          </div>
          <div className="text-[10px] font-mono text-slate-500 mt-1">After hours: {c.contact.after_hours}</div>
          <a
            href={c.website}
            target="_blank" rel="noreferrer"
            data-testid={`specialty-website-${c.id}`}
            className="mt-2 inline-flex items-center gap-1 text-[10px] font-mono uppercase tracking-wider text-cyan-300 hover:text-cyan-200"
          >
            Open carrier portal <ExternalLink size={9} />
          </a>
        </div>

        <div className="p-3 rounded border border-white/5 bg-white/[0.02]">
          <div className="text-[9px] font-mono uppercase tracking-wider text-slate-500 mb-1.5 flex items-center gap-1">
            <Activity size={9} /> Direct Tracking
          </div>
          <div className="flex items-center gap-1.5">
            <Input
              value={tracking}
              onChange={(e) => setTracking(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && openTracking()}
              placeholder="Tracking / PRO / Probill / Ref #"
              data-testid={`specialty-tracking-input-${c.id}`}
              className="flex-1 bg-[#11151F] border-white/10 text-xs font-mono"
            />
            <Button
              onClick={openTracking}
              data-testid={`specialty-tracking-go-${c.id}`}
              className="text-black font-bold"
              style={{ background: c.color }}
            >
              Track →
            </Button>
          </div>
          <div className="text-[10px] font-mono text-slate-500 mt-1.5">
            Opens {c.name} tracking page in a new tab.
          </div>
        </div>
      </div>

      <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-3 text-[10px] font-mono">
        <div>
          <span className="uppercase tracking-wider text-slate-500">Modes · </span>
          <span className="text-slate-300">{c.modes.join(" · ")}</span>
        </div>
        <div>
          <span className="uppercase tracking-wider text-slate-500">Rate basis · </span>
          <span className="text-slate-300">{c.rate_basis}</span>
        </div>
      </div>
      <div className="mt-1 text-[10px] font-mono">
        <span className="uppercase tracking-wider text-slate-500">Priority lanes · </span>
        <span className="text-slate-300">{c.lanes.join(" · ")}</span>
      </div>
    </Card>
  );
}

export default function SpecialtyCarriers() {
  const [carriers, setCarriers] = useState([]);
  useEffect(() => {
    api.get("/specialty-carriers").then((r) => setCarriers(r.data.carriers || [])).catch(() => {});
  }, []);

  return (
    <>
      <Topbar
        title="Specialty Carriers"
        subtitle="White-glove · Expedite · Cross-border · Capacity Assurance"
      />
      <div className="p-4 md:p-6 space-y-5" data-testid="specialty-carriers-page">
        <Card className="hud-surface p-4 flex items-center gap-3 flex-wrap">
          <Award size={20} className="text-cyan-400" />
          <div className="flex-1 min-w-[260px]">
            <h2 className="font-display text-lg font-bold text-white">Tennant's priority-use & special-handling roster</h2>
            <p className="text-xs text-slate-400 mt-1 leading-relaxed">
              These four carriers operate outside the standard rate-shop flow. Use them when freight requires
              white-glove pad-wrap protection, expedited time-critical pickup, cross-border CA ↔ US specialty,
              or surge capacity beyond the contracted fleet. Direct contact and per-carrier tracking below.
            </p>
          </div>
          <div className="flex items-center gap-2 text-[10px] font-mono">
            <Shield size={11} className="text-cyan-400" /> <span className="text-cyan-300">All approved & insured</span>
          </div>
        </Card>

        <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
          {carriers.map((c) => <CarrierCard key={c.id} c={c} />)}
        </div>
      </div>
    </>
  );
}
