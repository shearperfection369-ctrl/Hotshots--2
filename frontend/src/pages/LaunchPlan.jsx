import React, { useEffect, useState } from "react";
import Topbar from "@/components/Topbar";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  Rocket, Check, Clock, Circle, Phone, Mail, Linkedin, FileText, Send,
  Sparkles, Copy, Download, ChevronRight, Target, TrendingUp, ShieldCheck,
  DollarSign, Calendar, Users, BookOpenCheck
} from "lucide-react";
import { toast } from "sonner";
import { api, BACKEND_URL, getStoredToken } from "@/lib/api";

/**
 * /launch-plan — Founder cockpit for the 12-month freight brokerage launch.
 *
 * Tabs:
 *   1. Roadmap    — milestones + live KPI actuals
 *   2. Outreach   — generate branded cold-call / email / LinkedIn / PDFs
 *   3. Onboarding — one-click full shipper onboarding packet
 */

const STATUS_BADGE = {
  done:        { bg: "bg-emerald-500/20", text: "text-emerald-200", border: "border-emerald-400/50", label: "DONE", icon: Check },
  ready:       { bg: "bg-amber-500/20",   text: "text-amber-200",   border: "border-amber-400/60",   label: "READY", icon: Target },
  in_progress: { bg: "bg-cyan-500/20",    text: "text-cyan-200",    border: "border-cyan-400/40",    label: "IN PROGRESS", icon: Clock },
  todo:        { bg: "bg-slate-700/40",   text: "text-slate-300",   border: "border-white/10",       label: "TODO", icon: Circle },
  skipped:     { bg: "bg-rose-500/15",    text: "text-rose-200",    border: "border-rose-400/40",    label: "SKIPPED", icon: Circle },
};

function fmtUsd(n) {
  if (n === null || n === undefined) return "—";
  if (n >= 1_000_000) return `$${(n/1_000_000).toFixed(1)}M`;
  if (n >= 1_000)     return `$${(n/1_000).toFixed(1)}k`;
  return `$${Math.round(n)}`;
}

export default function LaunchPlan() {
  const [tab, setTab] = useState("roadmap");
  return (
    <>
      <Topbar
        title="Launch Runway"
        subtitle="12-month founder cockpit · live KPI milestones · branded outreach studio · one-click onboarding"
      />
      <div className="p-4 md:p-6 space-y-5">
        {/* Tab bar */}
        <div className="flex gap-1.5 flex-wrap" data-testid="launch-tabs">
          {[
            { id: "roadmap",    label: "12-Month Roadmap",       icon: Rocket },
            { id: "outreach",   label: "Outreach Studio",        icon: Send },
            { id: "onboarding", label: "Onboarding Packet",      icon: BookOpenCheck },
          ].map(t => {
            const Icon = t.icon;
            const active = tab === t.id;
            return (
              <button key={t.id}
                      data-testid={`tab-${t.id}`}
                      onClick={() => setTab(t.id)}
                      className={`px-4 py-2 rounded-lg text-xs font-mono uppercase tracking-widest border transition flex items-center gap-2 ${
                        active
                          ? "bg-amber-500 text-slate-950 border-amber-300"
                          : "bg-slate-900 text-slate-300 border-white/10 hover:border-amber-400/40"
                      }`}>
                <Icon size={14} /> {t.label}
              </button>
            );
          })}
        </div>

        {tab === "roadmap"    && <RoadmapTab />}
        {tab === "outreach"   && <OutreachTab />}
        {tab === "onboarding" && <OnboardingTab />}
      </div>
    </>
  );
}

// ============================================================
//  ROADMAP
// ============================================================
function RoadmapTab() {
  const [plan, setPlan] = useState(null);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [savingId, setSavingId] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const [p, s] = await Promise.all([
        api.get("/launch-runway"),
        api.get("/launch-runway/summary"),
      ]);
      setPlan(p.data);
      setSummary(s.data);
    } catch (e) {
      toast.error("Failed to load roadmap");
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); }, []);

  const toggle = async (m) => {
    const next = m.status === "done" ? "todo" : "done";
    setSavingId(m.id);
    try {
      await api.post(`/launch-runway/${m.id}/toggle`, { status: next });
      toast.success(next === "done" ? `Marked complete · ${m.label}` : "Re-opened");
      load();
    } catch (e) {
      toast.error("Could not save");
    } finally { setSavingId(null); }
  };

  const annotate = async (m) => {
    const note = window.prompt(`Add a note to "${m.label}":`, m.note || "");
    if (note === null) return;
    try {
      await api.post(`/launch-runway/${m.id}/notes`, { note });
      toast.success("Saved");
      load();
    } catch (e) {
      toast.error("Could not save note");
    }
  };

  if (loading || !plan || !summary) {
    return <Card className="p-8 bg-slate-950/60 border-white/10 text-center text-slate-500 text-sm">Loading roadmap…</Card>;
  }

  const phases = plan.phases;
  const phaseOrder = Object.keys(phases);

  return (
    <>
      {/* HEADER METRIC ROW */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricCard label="Plan Progress" value={`${summary.pct_complete}%`} sub={`${summary.completed} / ${summary.total_milestones} milestones`} icon={Rocket} accent="amber" testid="metric-progress" />
        <MetricCard label="Shippers Closed" value={summary.actuals.shippers_closed} sub="A/B credit targets" icon={Users} accent="emerald" testid="metric-shippers" />
        <MetricCard label="Invoices Generated" value={summary.actuals.invoices_generated} sub={fmtUsd(summary.actuals.invoiced_usd) + " billed"} icon={FileText} accent="cyan" testid="metric-invoices" />
        <MetricCard label="Margin To Date" value={fmtUsd(summary.actuals.total_margin)} sub={`Year-1 target ${fmtUsd(summary.target_y1_margin)}`} icon={DollarSign} accent="violet" testid="metric-margin" />
      </div>

      {/* CURRENT FOCUS */}
      {summary.current && (
        <Card className="p-5 bg-gradient-to-br from-amber-950/30 via-slate-950 to-slate-950 border-amber-400/40 mt-4">
          <div className="flex items-start gap-3">
            <Target className="text-amber-300 shrink-0 mt-1" size={28} />
            <div className="flex-1">
              <div className="text-[10px] font-mono uppercase tracking-widest text-amber-200">CURRENT FOCUS · {summary.current.phase}</div>
              <div className="text-lg font-semibold text-white mt-0.5">{summary.current.label}</div>
              <div className="text-xs text-slate-400 mt-1">{summary.current.narrative}</div>
              <div className="mt-3 flex items-center gap-3">
                <div className="text-xs font-mono text-amber-300">
                  {summary.current.actual} / {summary.current.kpi_target} {summary.current.kpi_label}
                </div>
                <div className="flex-1 h-1.5 bg-slate-800 rounded-full overflow-hidden max-w-md">
                  <div className="h-full bg-amber-400 transition-all"
                       style={{ width: `${Math.min(100, summary.current.actual / Math.max(1, summary.current.kpi_target) * 100)}%` }} />
                </div>
                {summary.current.status === "ready" && (
                  <Badge className="bg-amber-500/30 text-amber-100 border-amber-400/50">TARGET HIT</Badge>
                )}
              </div>
            </div>
          </div>
        </Card>
      )}

      {/* TIMELINE */}
      <div className="mt-4 space-y-5" data-testid="roadmap-timeline">
        {phaseOrder.map(phase => (
          <div key={phase}>
            <div className="text-[10px] font-mono uppercase tracking-[0.25em] text-amber-300 mb-2">
              {phase}
            </div>
            <div className="space-y-2">
              {phases[phase].map(mid => {
                const m = plan.milestones.find(x => x.id === mid);
                const sty = STATUS_BADGE[m.status] || STATUS_BADGE.todo;
                const Icon = sty.icon;
                return (
                  <Card key={m.id}
                        data-testid={`milestone-${m.id}`}
                        className={`p-4 bg-slate-950/60 border-2 ${sty.border} transition`}>
                    <div className="flex items-start gap-3">
                      <button
                        type="button"
                        data-testid={`toggle-${m.id}`}
                        onClick={() => toggle(m)}
                        disabled={savingId === m.id}
                        title="Toggle complete"
                        className={`shrink-0 w-9 h-9 rounded-lg grid place-items-center border-2 ${sty.border} ${sty.bg} ${sty.text} hover:scale-105 transition`}>
                        <Icon size={16} />
                      </button>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-baseline justify-between gap-3">
                          <div className="text-sm font-semibold text-white">{m.label}</div>
                          <Badge className={`${sty.bg} ${sty.text} border ${sty.border} text-[9px] font-mono shrink-0`}>{sty.label}</Badge>
                        </div>
                        <div className="text-xs text-slate-400 mt-1">{m.narrative}</div>

                        {/* progress bar */}
                        <div className="mt-2 flex items-center gap-3">
                          <div className="flex-1 h-1 bg-slate-800/80 rounded-full overflow-hidden">
                            <div className={`h-full transition-all ${
                              m.status === "done" ? "bg-emerald-400" :
                              m.status === "ready" ? "bg-amber-400" :
                              m.status === "in_progress" ? "bg-cyan-400" :
                              "bg-slate-600"
                            }`} style={{ width: `${m.actual_pct}%` }} />
                          </div>
                          <div className="text-[10px] font-mono text-slate-400 tabular-nums shrink-0">
                            {m.actual.toLocaleString()} / {m.kpi_target.toLocaleString()} {m.kpi_label}
                          </div>
                          <button onClick={() => annotate(m)}
                                  data-testid={`note-${m.id}`}
                                  className="text-[10px] text-slate-500 hover:text-amber-300 underline shrink-0">
                            {m.note ? "edit note" : "+ note"}
                          </button>
                        </div>
                        {m.note && (
                          <div className="mt-2 text-[11px] text-amber-200/80 italic px-2 py-1 bg-amber-500/5 border-l-2 border-amber-400/30 rounded-r">
                            {m.note}
                          </div>
                        )}
                      </div>
                    </div>
                  </Card>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </>
  );
}

// ============================================================
//  OUTREACH STUDIO
// ============================================================
const TEXT_CHANNELS = [
  { id: "email",       label: "Cold Email",       icon: Mail },
  { id: "call_script", label: "Cold Call Script", icon: Phone },
  { id: "linkedin_dm", label: "LinkedIn DM",      icon: Linkedin },
];
const PDF_CHANNELS = [
  { id: "capability_pdf",  label: "Capability Statement PDF", icon: FileText },
  { id: "founder_bio_pdf", label: "Founder Bio · Stone Arch credentials", icon: FileText },
  { id: "agreement_pdf",   label: "Service Agreement PDF",    icon: FileText },
  { id: "welcome_pdf",     label: "Welcome Letter PDF",       icon: FileText },
  { id: "credit_ref_pdf",  label: "Credit / Setup Form PDF",  icon: FileText },
];

function OutreachTab() {
  const [shipper, setShipper] = useState("SUPERVALU");
  const [contact, setContact] = useState("Mike Johnson");
  const [lane, setLane] = useState("Eden Prairie, MN → Des Moines, IA");
  const [mode, setMode] = useState("TL refrigerated · 5–10 loads / week");
  const [aiPersonalize, setAiPersonalize] = useState(true);
  const [channel, setChannel] = useState("email");
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [netTerms, setNetTerms] = useState(14);

  const generate = async () => {
    if (!shipper.trim()) { toast.error("Shipper name is required"); return; }
    setBusy(true); setResult(null);
    const body = {
      shipper_name: shipper, contact_name: contact, lane_focus: lane,
      mode_mix: mode, net_terms: parseInt(netTerms, 10),
      personalize_with_ai: aiPersonalize,
    };
    try {
      if (TEXT_CHANNELS.find(c => c.id === channel)) {
        const r = await api.post(`/shipper-outreach/generate?channel=${channel}`, body);
        setResult({ kind: "text", channel, ...r.data });
        toast.success("Generated");
      } else {
        // PDF download
        const token = getStoredToken();
        const res = await fetch(`${BACKEND_URL}/api/shipper-outreach/pdf?channel=${channel}`, {
          method: "POST",
          headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
          body: JSON.stringify(body),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        setResult({ kind: "pdf", channel, url, filename: res.headers.get("content-disposition")?.match(/filename="([^"]+)"/)?.[1] || `${channel}.pdf` });
        toast.success("PDF rendered + auto-archived to legal vault");
      }
    } catch (e) {
      toast.error("Generation failed: " + e.message);
    } finally { setBusy(false); }
  };

  const copyText = (txt) => {
    navigator.clipboard.writeText(txt);
    toast.success("Copied to clipboard");
  };

  const openMailto = () => {
    if (!result || result.kind !== "text" || channel !== "email") return;
    const url = `mailto:?subject=${encodeURIComponent(result.subject)}&body=${encodeURIComponent(result.plain)}`;
    window.location.href = url;
  };

  return (
    <div className="grid grid-cols-12 gap-4">
      {/* LEFT — input form */}
      <Card className="col-span-12 lg:col-span-4 p-5 bg-slate-950/60 border-white/10 space-y-3" data-testid="outreach-form">
        <div className="text-xs font-mono uppercase tracking-widest text-amber-300 mb-2">Target shipper</div>

        <div>
          <Label className="text-[10px] uppercase tracking-widest text-slate-400">Shipper company</Label>
          <Input data-testid="shipper-input" value={shipper} onChange={e => setShipper(e.target.value)} placeholder="SUPERVALU"
                 className="bg-slate-900 border-white/10 mt-1" />
        </div>
        <div>
          <Label className="text-[10px] uppercase tracking-widest text-slate-400">Primary contact</Label>
          <Input data-testid="contact-input" value={contact} onChange={e => setContact(e.target.value)} placeholder="Mike Johnson, VP Logistics"
                 className="bg-slate-900 border-white/10 mt-1" />
        </div>
        <div>
          <Label className="text-[10px] uppercase tracking-widest text-slate-400">Lane focus</Label>
          <Input data-testid="lane-input" value={lane} onChange={e => setLane(e.target.value)} placeholder="Eden Prairie, MN → Des Moines, IA"
                 className="bg-slate-900 border-white/10 mt-1" />
        </div>
        <div>
          <Label className="text-[10px] uppercase tracking-widest text-slate-400">Mode / volume</Label>
          <Input data-testid="mode-input" value={mode} onChange={e => setMode(e.target.value)} placeholder="TL reefer · 5-10 loads / week"
                 className="bg-slate-900 border-white/10 mt-1" />
        </div>
        {channel === "agreement_pdf" && (
          <div>
            <Label className="text-[10px] uppercase tracking-widest text-slate-400">Payment terms</Label>
            <Select value={String(netTerms)} onValueChange={(v) => setNetTerms(parseInt(v,10))}>
              <SelectTrigger data-testid="net-terms" className="bg-slate-900 border-white/10 mt-1"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="7">Net 7</SelectItem>
                <SelectItem value="10">Net 10</SelectItem>
                <SelectItem value="14">Net 14</SelectItem>
                <SelectItem value="30">Net 30</SelectItem>
              </SelectContent>
            </Select>
          </div>
        )}

        <div className="pt-2 border-t border-white/5">
          <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer" data-testid="ai-toggle">
            <input type="checkbox" checked={aiPersonalize} onChange={e => setAiPersonalize(e.target.checked)} className="accent-amber-400" />
            <Sparkles size={12} className="text-amber-300" />
            AI-personalize intro (Claude Sonnet)
          </label>
        </div>

        <div className="pt-3 border-t border-white/5">
          <div className="text-[10px] font-mono uppercase tracking-widest text-slate-400 mb-2">Channel · text</div>
          <div className="flex flex-wrap gap-1.5">
            {TEXT_CHANNELS.map(c => {
              const Icon = c.icon;
              return (
                <button key={c.id} data-testid={`channel-${c.id}`}
                        onClick={() => setChannel(c.id)}
                        className={`px-2.5 py-1.5 rounded-md text-[11px] border transition inline-flex items-center gap-1 ${
                          channel === c.id ? "bg-amber-500 text-slate-950 border-amber-300" : "bg-slate-900 text-slate-300 border-white/10 hover:border-amber-400/40"
                        }`}>
                  <Icon size={11} /> {c.label}
                </button>
              );
            })}
          </div>
          <div className="text-[10px] font-mono uppercase tracking-widest text-slate-400 mt-3 mb-2">Channel · PDF</div>
          <div className="flex flex-wrap gap-1.5">
            {PDF_CHANNELS.map(c => {
              const Icon = c.icon;
              return (
                <button key={c.id} data-testid={`channel-${c.id}`}
                        onClick={() => setChannel(c.id)}
                        className={`px-2.5 py-1.5 rounded-md text-[11px] border transition inline-flex items-center gap-1 ${
                          channel === c.id ? "bg-amber-500 text-slate-950 border-amber-300" : "bg-slate-900 text-slate-300 border-white/10 hover:border-amber-400/40"
                        }`}>
                  <Icon size={11} /> {c.label}
                </button>
              );
            })}
          </div>
        </div>

        <Button data-testid="generate-btn" onClick={generate} disabled={busy}
                className="w-full bg-amber-500 hover:bg-amber-400 text-slate-950 font-semibold mt-4">
          {busy ? <><Clock className="animate-spin mr-1" size={14} /> Generating…</> : <><Sparkles size={14} className="mr-1" /> Generate</>}
        </Button>
      </Card>

      {/* RIGHT — result */}
      <Card className="col-span-12 lg:col-span-8 p-5 bg-slate-950/60 border-white/10 min-h-[60vh]" data-testid="outreach-result">
        {!result && (
          <div className="text-center text-slate-500 py-20">
            <Send size={42} className="mx-auto mb-3 opacity-30" />
            <div className="text-sm">Pick a channel and click Generate.</div>
            <div className="text-xs text-slate-600 mt-1">Every PDF you render here is auto-archived to the immutable Document Vault (7-year retention).</div>
          </div>
        )}

        {result?.kind === "text" && result.channel === "email" && (
          <div className="space-y-3" data-testid="result-email">
            <div className="flex items-center justify-between">
              <div className="text-[10px] font-mono uppercase tracking-widest text-amber-300">EMAIL</div>
              <div className="flex gap-1.5">
                <Button size="sm" variant="outline" data-testid="copy-subject" onClick={() => copyText(result.subject)} className="h-7 bg-slate-900 border-white/10 text-[11px]"><Copy size={11} className="mr-1" /> Subject</Button>
                <Button size="sm" variant="outline" data-testid="copy-body" onClick={() => copyText(result.plain)} className="h-7 bg-slate-900 border-white/10 text-[11px]"><Copy size={11} className="mr-1" /> Body</Button>
                <Button size="sm" data-testid="open-mail" onClick={openMailto} className="h-7 bg-amber-500 hover:bg-amber-400 text-slate-950 text-[11px]"><Mail size={11} className="mr-1" /> Open Mail</Button>
              </div>
            </div>
            <div className="bg-slate-900 border border-white/10 rounded p-3 text-xs text-slate-300 font-mono">
              <div className="text-amber-300">Subject:</div>
              <div>{result.subject}</div>
            </div>
            <div className="bg-white text-slate-800 rounded p-5 border border-white/10 prose-sm max-h-[58vh] overflow-y-auto"
                 dangerouslySetInnerHTML={{ __html: result.html }} />
          </div>
        )}

        {result?.kind === "text" && result.channel === "linkedin_dm" && (
          <div className="space-y-3" data-testid="result-dm">
            <div className="flex items-center justify-between">
              <div className="text-[10px] font-mono uppercase tracking-widest text-amber-300">LINKEDIN DM</div>
              <Button size="sm" data-testid="copy-dm" onClick={() => copyText(result.text)} className="h-7 bg-amber-500 hover:bg-amber-400 text-slate-950 text-[11px]"><Copy size={11} className="mr-1" /> Copy</Button>
            </div>
            <pre className="bg-slate-900 border border-white/10 rounded p-4 text-xs text-slate-200 whitespace-pre-wrap font-mono">{result.text}</pre>
          </div>
        )}

        {result?.kind === "text" && result.channel === "call_script" && (
          <div className="space-y-3" data-testid="result-call">
            <div className="flex items-center justify-between">
              <div className="text-[10px] font-mono uppercase tracking-widest text-amber-300">COLD CALL SCRIPT</div>
              <Button size="sm" data-testid="copy-script" onClick={() => copyText(result.markdown)} className="h-7 bg-amber-500 hover:bg-amber-400 text-slate-950 text-[11px]"><Copy size={11} className="mr-1" /> Copy Markdown</Button>
            </div>
            <pre className="bg-slate-900 border border-white/10 rounded p-4 text-[11px] text-slate-200 whitespace-pre-wrap font-mono max-h-[58vh] overflow-y-auto">{result.markdown}</pre>
          </div>
        )}

        {result?.kind === "pdf" && (
          <div className="space-y-3" data-testid="result-pdf">
            <div className="flex items-center justify-between">
              <div className="text-[10px] font-mono uppercase tracking-widest text-amber-300">{result.channel.replace(/_/g, " ").toUpperCase()}</div>
              <a href={result.url} download={result.filename} data-testid="download-pdf"
                 className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md text-xs font-semibold bg-amber-500 text-slate-950 hover:bg-amber-400 transition">
                <Download size={12} /> {result.filename}
              </a>
            </div>
            <iframe src={result.url} className="w-full h-[70vh] bg-white rounded border border-white/10" title="generated pdf" />
          </div>
        )}
      </Card>
    </div>
  );
}

// ============================================================
//  ONBOARDING — one-click full packet
// ============================================================
function OnboardingTab() {
  const [shipper, setShipper] = useState("");
  const [contact, setContact] = useState("");
  const [lane, setLane] = useState("");
  const [mode, setMode] = useState("");
  const [netTerms, setNetTerms] = useState(14);
  const [busy, setBusy] = useState(false);
  const [packetUrl, setPacketUrl] = useState(null);
  const [packetName, setPacketName] = useState("");

  const generate = async () => {
    if (!shipper.trim()) { toast.error("Shipper name is required"); return; }
    setBusy(true); setPacketUrl(null);
    try {
      const token = getStoredToken();
      const res = await fetch(`${BACKEND_URL}/api/shipper-outreach/pdf?channel=onboarding_packet`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          shipper_name: shipper, contact_name: contact, lane_focus: lane,
          mode_mix: mode, net_terms: parseInt(netTerms, 10),
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      setPacketUrl(URL.createObjectURL(blob));
      setPacketName(res.headers.get("content-disposition")?.match(/filename="([^"]+)"/)?.[1] || `Orisei_Onboarding_${shipper.replace(/\s+/g,"_")}.pdf`);
      toast.success("Packet generated · auto-archived to immutable vault");
    } catch (e) {
      toast.error("Generate failed: " + e.message);
    } finally { setBusy(false); }
  };

  const PACKET_CONTENTS = [
    { title: "Welcome Letter",     desc: "Day 1–14 onboarding cadence + escalation path" },
    { title: "Capability Statement", desc: "Modes, tech stack, authority & coverage" },
    { title: "Founder Bio",        desc: "Stone Arch · SBA · JOC Top 100 · CP Transload Award" },
    { title: "Service Agreement",  desc: `Broker · Shipper master agreement · Net ${netTerms}` },
    { title: "Customer Setup & Credit Reference", desc: "Trade refs + W-9/COI checklist" },
  ];

  return (
    <div className="grid grid-cols-12 gap-4" data-testid="onboarding-form">
      <Card className="col-span-12 lg:col-span-5 p-5 bg-slate-950/60 border-amber-400/30 space-y-3">
        <div className="text-xs font-mono uppercase tracking-widest text-amber-300 mb-1">One-click shipper onboarding packet</div>
        <div className="text-xs text-slate-400 mb-3">
          Generates a single, branded, signature-ready PDF combining all four onboarding documents — ready to email immediately after a closed call.
        </div>

        <div>
          <Label className="text-[10px] uppercase tracking-widest text-slate-400">Shipper company</Label>
          <Input data-testid="onb-shipper" value={shipper} onChange={e => setShipper(e.target.value)} placeholder="SUPERVALU"
                 className="bg-slate-900 border-white/10 mt-1" />
        </div>
        <div>
          <Label className="text-[10px] uppercase tracking-widest text-slate-400">Primary contact</Label>
          <Input data-testid="onb-contact" value={contact} onChange={e => setContact(e.target.value)} placeholder="Mike Johnson, VP Logistics"
                 className="bg-slate-900 border-white/10 mt-1" />
        </div>
        <div>
          <Label className="text-[10px] uppercase tracking-widest text-slate-400">Anchor lane(s)</Label>
          <Input data-testid="onb-lane" value={lane} onChange={e => setLane(e.target.value)} placeholder="Eden Prairie, MN → Des Moines, IA"
                 className="bg-slate-900 border-white/10 mt-1" />
        </div>
        <div>
          <Label className="text-[10px] uppercase tracking-widest text-slate-400">Modes / volume</Label>
          <Input data-testid="onb-mode" value={mode} onChange={e => setMode(e.target.value)} placeholder="TL · LTL · ~10 loads/wk"
                 className="bg-slate-900 border-white/10 mt-1" />
        </div>
        <div>
          <Label className="text-[10px] uppercase tracking-widest text-slate-400">Payment terms</Label>
          <Select value={String(netTerms)} onValueChange={(v) => setNetTerms(parseInt(v,10))}>
            <SelectTrigger data-testid="onb-net" className="bg-slate-900 border-white/10 mt-1"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="7">Net 7</SelectItem>
              <SelectItem value="10">Net 10</SelectItem>
              <SelectItem value="14">Net 14</SelectItem>
              <SelectItem value="30">Net 30</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <Button data-testid="onb-generate" onClick={generate} disabled={busy}
                className="w-full bg-amber-500 hover:bg-amber-400 text-slate-950 font-semibold mt-3">
          {busy ? <><Clock className="animate-spin mr-1" size={14} /> Generating…</> : <><BookOpenCheck size={14} className="mr-1" /> Generate Onboarding Packet</>}
        </Button>

        <div className="pt-3 border-t border-white/5">
          <div className="text-[10px] font-mono uppercase tracking-widest text-slate-400 mb-2">Packet includes</div>
          <div className="space-y-2">
            {PACKET_CONTENTS.map((c, i) => (
              <div key={i} className="flex items-start gap-2">
                <Check size={14} className="text-emerald-300 shrink-0 mt-0.5" />
                <div>
                  <div className="text-xs font-semibold text-white">{c.title}</div>
                  <div className="text-[10px] text-slate-400">{c.desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </Card>

      <Card className="col-span-12 lg:col-span-7 p-5 bg-slate-950/60 border-white/10 min-h-[60vh]">
        {!packetUrl && (
          <div className="text-center text-slate-500 py-24">
            <BookOpenCheck size={56} className="mx-auto mb-4 opacity-20" />
            <div className="text-sm">Fill in the shipper details and generate the packet.</div>
            <div className="text-xs text-slate-600 mt-1">
              All four documents render in one PDF — branded with the Orisei wordmark and the Queen Califia heraldic border.
            </div>
          </div>
        )}
        {packetUrl && (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="text-[10px] font-mono uppercase tracking-widest text-amber-300">ONBOARDING PACKET · {shipper.toUpperCase()}</div>
              <a href={packetUrl} download={packetName} data-testid="download-packet"
                 className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md text-xs font-semibold bg-amber-500 text-slate-950 hover:bg-amber-400 transition">
                <Download size={12} /> Download
              </a>
            </div>
            <iframe src={packetUrl} className="w-full h-[72vh] bg-white rounded border border-white/10" title="onboarding packet" />
          </div>
        )}
      </Card>
    </div>
  );
}

// ============================================================
//  Reusable metric card
// ============================================================
const ACCENT = {
  amber:   { border: "border-amber-400/40",   text: "text-amber-300",   sub: "text-amber-200/70" },
  emerald: { border: "border-emerald-400/40", text: "text-emerald-300", sub: "text-emerald-200/70" },
  cyan:    { border: "border-cyan-400/40",    text: "text-cyan-300",    sub: "text-cyan-200/70" },
  violet:  { border: "border-violet-400/40",  text: "text-violet-300",  sub: "text-violet-200/70" },
};

function MetricCard({ label, value, sub, icon: Icon, accent="amber", testid }) {
  const a = ACCENT[accent];
  return (
    <Card className={`p-4 bg-slate-950/60 border-2 ${a.border}`} data-testid={testid}>
      <div className="flex items-center justify-between mb-1">
        <div className="text-[10px] font-mono uppercase tracking-widest text-slate-400">{label}</div>
        <Icon className={a.text} size={16} />
      </div>
      <div className={`text-2xl font-semibold ${a.text} font-mono`}>{value}</div>
      <div className={`text-[10px] font-mono uppercase tracking-widest ${a.sub} mt-0.5`}>{sub}</div>
    </Card>
  );
}
