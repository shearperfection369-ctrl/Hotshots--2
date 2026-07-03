import React, { useEffect, useState } from "react";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";
import {
  Lightbulb, CheckCircle2, Loader2, Sparkles, TrendingUp, Shield, Zap, ArrowRight,
} from "lucide-react";
import { api, BACKEND_URL } from "../lib/api";
import { toast } from "sonner";

/**
 * Public /tour landing — no auth required. Anyone curious about the TMS
 * can read the value prop and submit the interest form. Their submission
 * lands as a CURIOUS prospect in Lighthouse Outreach.
 */
export default function PublicTour() {
  const [payload, setPayload] = useState(null);
  const [submitted, setSubmitted] = useState(false);
  const [form, setForm] = useState({
    company_name: "", contact_name: "", contact_email: "", contact_phone: "",
    contact_title: "", company_size: "", current_tms: "", monthly_loads: "",
    message: "",
  });
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    // Public endpoint — no auth needed
    fetch(`${BACKEND_URL}/api/lighthouse/public/tour`)
      .then((r) => r.json())
      .then((d) => setPayload(d))
      .catch(() => {});
  }, []);

  const submit = async () => {
    if (!form.company_name.trim() || !form.contact_name.trim() || !form.contact_email.trim()) {
      toast.error("Company, name, email are all required");
      return;
    }
    setBusy(true);
    try {
      const payload = { ...form };
      ["monthly_loads"].forEach((k) => { payload[k] = payload[k] === "" ? undefined : Number(payload[k]); });
      Object.keys(payload).forEach((k) => (payload[k] === "" || payload[k] === undefined) && delete payload[k]);
      const res = await fetch(`${BACKEND_URL}/api/lighthouse/public/interest`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setSubmitted(true);
    } catch (e) {
      toast.error("Submission failed — please email us directly.");
    } finally { setBusy(false); }
  };

  const brand = payload?.brand || {};
  const short = brand.short_name || "Orisei";
  const primary = brand.primary_color || "#22D3EE";
  const accent = brand.accent_color || "#F59E0B";
  const tagline = brand.tagline || "Freight infrastructure for modern brokerages.";

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950 text-slate-100" data-testid="public-tour-root">
      {/* Hero */}
      <div className="max-w-6xl mx-auto px-6 py-16">
        <div className="flex items-center gap-2 mb-6">
          <Lightbulb size={22} style={{ color: accent }} />
          <span className="text-[10px] font-mono uppercase tracking-widest" style={{ color: accent }}>
            {short} · TMS Platform
          </span>
        </div>
        <h1 className="text-4xl sm:text-5xl lg:text-6xl font-black tracking-tight mb-4">
          Freight infrastructure<br />
          <span style={{ color: primary }}>for modern brokerages.</span>
        </h1>
        <p className="text-slate-400 text-base sm:text-lg max-w-2xl mb-10 leading-relaxed">
          {tagline} Every module you need — aggregated load boards, live tracking, claims,
          QBRs, international, factoring — under one production-grade TMS.
        </p>

        {/* Value pillars */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-16">
          <Pillar icon={Zap} title="Aggregated load boards"
            desc="DAT, Truckstop, Convoy, Uber Freight — one scored feed. Book straight into the workflow." />
          <Pillar icon={Shield} title="Prevention-first claims"
            desc="24-hr SLA, photo evidence chain, carrier watchlist, insurance verification, branded incident reports." />
          <Pillar icon={TrendingUp} title="Auto-computed QBRs"
            desc="Pull volume/OTD/damage/spend from the TMS, compare vs prior quarter, distribute in minutes." />
        </div>

        {/* Modules list */}
        {payload?.modules && (
          <Card className="p-6 bg-slate-900/60 border-white/10 mb-10">
            <div className="text-[10px] font-mono uppercase tracking-widest mb-3" style={{ color: accent }}>
              <Sparkles size={12} className="inline mr-1" /> Module catalog
            </div>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
              {payload.modules.map((m) => (
                <div key={m} className="text-xs text-slate-300 flex items-center gap-2">
                  <CheckCircle2 size={12} style={{ color: primary }} /> {m}
                </div>
              ))}
            </div>
          </Card>
        )}

        {/* Interest form */}
        <Card className="p-6 bg-slate-900/70 border-white/10 max-w-3xl" data-testid="public-tour-form">
          {submitted ? (
            <div className="text-center py-8" data-testid="public-tour-success">
              <CheckCircle2 size={40} style={{ color: primary }} className="mx-auto mb-3" />
              <div className="text-xl font-semibold text-slate-100">Thanks — we&apos;ll be in touch within one business day.</div>
              <div className="text-sm text-slate-400 mt-2">
                Your submission landed with {short}&apos;s Lighthouse desk. Expect a personalized product tour
                and (if you shared load volume) a specific ROI snapshot for your operation.
              </div>
            </div>
          ) : (
            <>
              <div className="text-[10px] font-mono uppercase tracking-widest mb-4" style={{ color: accent }}>
                Ready to see it? Tell us about your operation.
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <FieldRow label="Company *" tid="public-tour-company">
                  <Input value={form.company_name} onChange={(e) => setForm({ ...form, company_name: e.target.value })}
                    className="bg-black/40 border-white/10 h-9 text-sm text-slate-100" />
                </FieldRow>
                <FieldRow label="Your name *" tid="public-tour-name">
                  <Input value={form.contact_name} onChange={(e) => setForm({ ...form, contact_name: e.target.value })}
                    className="bg-black/40 border-white/10 h-9 text-sm text-slate-100" />
                </FieldRow>
                <FieldRow label="Work email *" tid="public-tour-email">
                  <Input type="email" value={form.contact_email}
                    onChange={(e) => setForm({ ...form, contact_email: e.target.value })}
                    className="bg-black/40 border-white/10 h-9 text-sm text-slate-100" />
                </FieldRow>
                <FieldRow label="Phone">
                  <Input value={form.contact_phone} onChange={(e) => setForm({ ...form, contact_phone: e.target.value })}
                    className="bg-black/40 border-white/10 h-9 text-sm text-slate-100" />
                </FieldRow>
                <FieldRow label="Your title">
                  <Input value={form.contact_title} onChange={(e) => setForm({ ...form, contact_title: e.target.value })}
                    placeholder="VP Ops, Head of Logistics…"
                    className="bg-black/40 border-white/10 h-9 text-sm text-slate-100" />
                </FieldRow>
                <FieldRow label="Current TMS">
                  <Input value={form.current_tms} onChange={(e) => setForm({ ...form, current_tms: e.target.value })}
                    placeholder="McLeod, MercuryGate, spreadsheet…"
                    className="bg-black/40 border-white/10 h-9 text-sm text-slate-100" />
                </FieldRow>
                <FieldRow label="Monthly loads">
                  <Input type="number" value={form.monthly_loads}
                    onChange={(e) => setForm({ ...form, monthly_loads: e.target.value })}
                    className="bg-black/40 border-white/10 h-9 text-sm text-slate-100" />
                </FieldRow>
                <FieldRow label="Company size">
                  <Input value={form.company_size} onChange={(e) => setForm({ ...form, company_size: e.target.value })}
                    placeholder="e.g. 25 dispatchers, 400 loads/wk"
                    className="bg-black/40 border-white/10 h-9 text-sm text-slate-100" />
                </FieldRow>
                <FieldRow label="What are you hoping to solve?" className="md:col-span-2">
                  <Textarea rows={3} value={form.message}
                    onChange={(e) => setForm({ ...form, message: e.target.value })}
                    placeholder="Optional — but the more detail you share, the sharper our first response can be."
                    className="bg-black/40 border-white/10 text-sm text-slate-100"
                    data-testid="public-tour-message" />
                </FieldRow>
              </div>
              <div className="flex justify-end mt-5">
                <Button onClick={submit} disabled={busy} className="text-black font-semibold"
                  style={{ background: primary }}
                  data-testid="public-tour-submit">
                  {busy ? <Loader2 size={14} className="animate-spin mr-1" /> : <ArrowRight size={14} className="mr-1" />}
                  Request a Tour
                </Button>
              </div>
            </>
          )}
        </Card>

        <div className="text-center mt-16 text-[10px] font-mono uppercase tracking-widest text-slate-600">
          © {new Date().getFullYear()} {short} Freight Solutions LLC · confidential
        </div>
      </div>
    </div>
  );
}

function Pillar({ icon: Icon, title, desc }) {
  return (
    <Card className="p-5 bg-slate-900/60 border-white/10">
      <Icon size={22} className="text-amber-300 mb-2" />
      <div className="text-slate-100 font-medium mb-1">{title}</div>
      <div className="text-xs text-slate-400 leading-relaxed">{desc}</div>
    </Card>
  );
}

function FieldRow({ label, children, className, tid }) {
  return (
    <div className={className}>
      <div className="text-[10px] font-mono uppercase tracking-widest text-slate-500 mb-1" data-testid={tid ? `${tid}-label` : undefined}>{label}</div>
      {children}
    </div>
  );
}
