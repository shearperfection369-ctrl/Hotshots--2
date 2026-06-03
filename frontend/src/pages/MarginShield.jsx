import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import Topbar from "@/components/Topbar";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Shield, Zap, DollarSign, AlertTriangle, CheckCircle2, XCircle,
  TrendingUp, Award, Trophy, Star, FileText, Plus, Trash2,
  Activity, Sparkles, Gauge, ChevronRight,
} from "lucide-react";

/**
 * /margin-shield — Brokerage Margin Shield admin page.
 * 5 sections in one screen:
 *   1. KPI dashboard (top)
 *   2. Auto-Match top-3 carriers for an open load
 *   3. Real-time rate snapshot (DAT + Truckstop + historical)
 *   4. Compliance traffic-light lookup
 *   5. Carrier Loyalty Programs CRUD
 */
export default function MarginShield() {
  const [dash, setDash] = useState(null);
  const [activeTab, setActiveTab] = useState("auto-match");
  const [loadId, setLoadId] = useState("");
  const [matchResult, setMatchResult] = useState(null);
  const [rateResult, setRateResult] = useState(null);
  const [mcLookup, setMcLookup] = useState("");
  const [compResult, setCompResult] = useState(null);
  const [programs, setPrograms] = useState([]);
  const [newProgram, setNewProgram] = useState({
    name: "", bonus_type: "percent", bonus_value: 1.5, tier: "platinum",
    first_look_minutes: 30, active: true, notes: "",
  });

  const fetchDash = async () => {
    try {
      const { data } = await api.get("/margin-shield/dashboard");
      setDash(data);
    } catch (e) { /* graceful */ }
  };
  const fetchPrograms = async () => {
    try {
      const { data } = await api.get("/margin-shield/loyalty/programs");
      setPrograms(data.items || []);
    } catch (e) { /* graceful */ }
  };

  useEffect(() => { fetchDash(); fetchPrograms(); }, []);

  const runAutoMatch = async () => {
    if (!loadId.trim()) return toast.error("Enter a load ID");
    try {
      const { data } = await api.get(`/margin-shield/auto-match/${loadId.trim()}`);
      setMatchResult(data);
      toast.success(`Ranked ${data.total_candidates} carriers · top 3 shown`);
    } catch (e) { toast.error(e?.response?.data?.detail || "Match failed"); }
  };

  const runRateSnapshot = async () => {
    if (!loadId.trim()) return toast.error("Enter a load ID");
    try {
      const { data } = await api.get(`/margin-shield/rates/${loadId.trim()}`);
      setRateResult(data);
    } catch (e) { toast.error(e?.response?.data?.detail || "Rate snapshot failed"); }
  };

  const runCompliance = async () => {
    if (!mcLookup.trim()) return toast.error("Enter an MC or DOT #");
    try {
      const { data } = await api.get(`/margin-shield/compliance/${mcLookup.trim()}`);
      setCompResult(data);
    } catch (e) {
      setCompResult(null);
      toast.error(e?.response?.data?.detail || "Compliance check failed");
    }
  };

  const tenderLoad = async (carrier) => {
    if (!window.confirm(`Tender load ${matchResult.load_id} to ${carrier.carrier_name}?`)) return;
    try {
      const { data } = await api.post(
        `/margin-shield/auto-match/${matchResult.load_id}/tender`,
        { carrier_mc: carrier.carrier_mc, compliance_flag: carrier.compliance?.flag });
      toast.success(`Tendered · ${data.tender_id}`);
      runAutoMatch();
    } catch (e) { toast.error(e?.response?.data?.detail || "Tender failed"); }
  };

  const createProgram = async () => {
    if (!newProgram.name.trim()) return toast.error("Program name required");
    try {
      await api.post("/margin-shield/loyalty/programs", newProgram);
      toast.success(`Created · ${newProgram.name}`);
      setNewProgram({ name: "", bonus_type: "percent", bonus_value: 1.5,
        tier: "platinum", first_look_minutes: 30, active: true, notes: "" });
      fetchPrograms();
    } catch (e) { toast.error(e?.response?.data?.detail || "Create failed"); }
  };

  const deleteProgram = async (pid) => {
    if (!window.confirm("Delete this loyalty program?")) return;
    try {
      await api.delete(`/margin-shield/loyalty/programs/${pid}`);
      toast.success("Deleted");
      fetchPrograms();
    } catch (e) { toast.error("Delete failed"); }
  };

  const TABS = [
    { id: "auto-match",  label: "Auto-Match",  icon: Zap },
    { id: "rates",       label: "Rate Snapshot", icon: TrendingUp },
    { id: "compliance",  label: "Compliance",  icon: Shield },
    { id: "invoice",     label: "Auto-Invoice", icon: FileText },
    { id: "loyalty",     label: "Loyalty",     icon: Trophy },
  ];

  return (
    <>
      <Topbar title="Margin Shield" />
      <div className="p-6 max-w-7xl mx-auto space-y-6">
        {/* HEADER + KPI ROW */}
        <Card className="hud-surface p-6" data-testid="margin-shield-header">
          <div className="flex items-start justify-between flex-wrap gap-4">
            <div>
              <div className="text-[10px] font-mono uppercase tracking-[0.25em] text-cyan-400">
                Brokerage Operations · Margin Protection
              </div>
              <h1 className="font-display text-3xl font-black mt-1 flex items-center gap-3">
                <Shield className="text-cyan-400" size={30} /> Margin Shield
              </h1>
              <p className="text-sm text-slate-400 mt-2 max-w-2xl leading-relaxed">
                Automated load matching, real-time rate visibility, compliance
                pre-checks, auto-invoicing on POD, and a loyalty program that
                locks in your carrier base. Stable cost = stable margin.
              </p>
            </div>
            {dash && (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="kpi-row">
                <Kpi v={dash.loads_open} k="Open loads" icon={Activity} />
                <Kpi v={`$${(dash.margin_total_usd || 0).toLocaleString()}`} k="YTD margin" icon={DollarSign} />
                <Kpi v={dash.carrier_pool?.platinum || 0} k="Platinum carriers" icon={Trophy} />
                <Kpi v={`${dash.compliance?.green || 0}/${dash.carrier_pool?.total || 0}`} k="Tender-ready" icon={CheckCircle2} />
              </div>
            )}
          </div>
          {/* Tab bar */}
          <div className="flex flex-wrap gap-2 mt-6 border-t border-white/5 pt-4" data-testid="margin-shield-tabs">
            {TABS.map((t) => (
              <button key={t.id} onClick={() => setActiveTab(t.id)}
                      data-testid={`tab-${t.id}`}
                      className={`px-4 py-2 rounded font-mono text-xs uppercase tracking-wider transition flex items-center gap-2
                        ${activeTab === t.id
                          ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40"
                          : "text-slate-400 hover:text-cyan-300 border border-transparent hover:bg-white/5"}`}>
                <t.icon size={13} /> {t.label}
              </button>
            ))}
          </div>
        </Card>

        {/* ================ AUTO-MATCH ================ */}
        {activeTab === "auto-match" && (
          <Card className="hud-surface p-6" data-testid="tab-content-auto-match">
            <h2 className="font-display text-xl font-bold mb-1">Auto-Match Engine</h2>
            <p className="text-xs text-slate-400 mb-4">
              Enter an open load ID. Scoring blends scorecard, lane history,
              equipment fit, loyalty tier, and freshness.
            </p>
            <div className="flex gap-2 mb-5">
              <Input value={loadId} onChange={(e) => setLoadId(e.target.value)}
                placeholder="e.g. LD-2026-0042"
                className="bg-[#0B1320] border-white/10 text-white max-w-xs"
                data-testid="auto-match-load-id" />
              <Button onClick={runAutoMatch} className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold"
                data-testid="auto-match-run">
                <Zap size={14} className="mr-2" /> Match
              </Button>
            </div>

            {matchResult && (
              <div className="space-y-3" data-testid="auto-match-results">
                <div className="text-[10px] font-mono uppercase tracking-wider text-cyan-400">
                  Top 3 of {matchResult.total_candidates} candidates · Load {matchResult.load_id}
                </div>
                {matchResult.matches.map((m, idx) => (
                  <div key={m.carrier_mc} className="p-4 rounded-lg border bg-white/[0.02]"
                       style={{ borderColor: idx === 0 ? "rgba(34,211,238,0.4)" : "rgba(255,255,255,0.08)" }}
                       data-testid={`match-card-${idx}`}>
                    <div className="flex items-start justify-between flex-wrap gap-3">
                      <div className="flex-1 min-w-[250px]">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-display text-lg font-bold">#{idx + 1} · {m.carrier_name}</span>
                          <TierPill tier={m.tier} />
                          <CompliancePill flag={m.compliance?.flag} />
                        </div>
                        <div className="text-xs text-slate-500 font-mono mt-1">MC {m.carrier_mc}</div>
                        <div className="grid grid-cols-3 md:grid-cols-5 gap-2 mt-3 text-[10px] font-mono">
                          {Object.entries(m.components).map(([k, v]) => (
                            <ComponentBar key={k} label={k} val={v} />
                          ))}
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="font-display text-4xl font-black text-cyan-300 tabular-nums">{m.score}</div>
                        <div className="text-[9px] font-mono uppercase tracking-wider text-slate-400">match score</div>
                        <Button size="sm" onClick={() => tenderLoad(m)}
                          disabled={m.compliance?.flag === "red"}
                          className="mt-2 bg-cyan-500 hover:bg-cyan-400 text-black font-bold text-xs disabled:bg-slate-600 disabled:text-slate-400"
                          data-testid={`tender-${idx}`}>
                          {m.compliance?.flag === "red" ? "Compliance BLOCKER" : "One-click tender"} <ChevronRight size={12} className="ml-1" />
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        )}

        {/* ================ RATE SNAPSHOT ================ */}
        {activeTab === "rates" && (
          <Card className="hud-surface p-6" data-testid="tab-content-rates">
            <h2 className="font-display text-xl font-bold mb-1">Real-Time Rate Snapshot</h2>
            <p className="text-xs text-slate-400 mb-4">
              Pulls DAT + Truckstop + your historical lane average into one view.
              Connect DAT and Truckstop in Connections Vault for live rates.
            </p>
            <div className="flex gap-2 mb-5">
              <Input value={loadId} onChange={(e) => setLoadId(e.target.value)}
                placeholder="Load ID"
                className="bg-[#0B1320] border-white/10 text-white max-w-xs"
                data-testid="rates-load-id" />
              <Button onClick={runRateSnapshot} className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold"
                data-testid="rates-run">
                <TrendingUp size={14} className="mr-2" /> Pull Rates
              </Button>
            </div>

            {rateResult && (
              <div data-testid="rates-results">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-5">
                  <Kpi v={`$${rateResult.recommended_rate.toLocaleString()}`}
                       k={`Recommended · $${rateResult.recommended_rpm}/mi`} icon={Sparkles} accent="cyan" />
                  <Kpi v={`${rateResult.confidence_pct}%`}
                       k={`Confidence · ${rateResult.live_source_count}/3 live`} icon={Gauge}
                       accent={rateResult.confidence_pct > 75 ? "cyan" : "amber"} />
                  <Kpi v={`${rateResult.sources?.length || 0}`}
                       k="Data sources" icon={Activity} />
                </div>
                {rateResult.synthetic_warning && (
                  <div className="mb-4 p-3 rounded border border-amber-500/30 bg-amber-500/10 text-xs text-amber-300 flex items-center gap-2">
                    <AlertTriangle size={14} /> Live rate sources unavailable. Connect DAT One and Truckstop in Connections Vault for real-time data.
                  </div>
                )}
                <div className="space-y-2">
                  {rateResult.sources.map((s) => (
                    <div key={s.name} className="p-3 rounded border bg-white/[0.02] grid grid-cols-12 gap-2 items-center"
                         style={{ borderColor: "rgba(255,255,255,0.06)" }}
                         data-testid={`rate-row-${s.name.replace(/\s+/g, "-").toLowerCase()}`}>
                      <div className="col-span-12 md:col-span-3">
                        <div className="font-bold text-sm">{s.name}</div>
                        <div className="text-[10px] font-mono text-slate-500 flex items-center gap-1">
                          <span className={`w-1.5 h-1.5 rounded-full ${s.live ? "bg-emerald-400" : "bg-amber-400"}`}></span>
                          {s.live ? "LIVE" : "SYNTHETIC"}
                        </div>
                      </div>
                      <div className="col-span-4 md:col-span-2 text-right">
                        <div className="text-slate-500 text-[10px] font-mono uppercase">Low</div>
                        <div className="font-mono text-sm">${s.rate_low.toLocaleString()}</div>
                      </div>
                      <div className="col-span-4 md:col-span-2 text-right">
                        <div className="text-cyan-400 text-[10px] font-mono uppercase">Avg</div>
                        <div className="font-display font-bold text-cyan-300">${s.rate_avg.toLocaleString()}</div>
                      </div>
                      <div className="col-span-4 md:col-span-2 text-right">
                        <div className="text-slate-500 text-[10px] font-mono uppercase">High</div>
                        <div className="font-mono text-sm">${s.rate_high.toLocaleString()}</div>
                      </div>
                      <div className="col-span-12 md:col-span-3 text-right">
                        <div className="text-slate-500 text-[10px] font-mono">${s.rpm}/mi · {s.note}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </Card>
        )}

        {/* ================ COMPLIANCE ================ */}
        {activeTab === "compliance" && (
          <Card className="hud-surface p-6" data-testid="tab-content-compliance">
            <h2 className="font-display text-xl font-bold mb-1">Compliance Traffic-Lights</h2>
            <p className="text-xs text-slate-400 mb-4">
              5-check carrier vetting · MC active · CSA · Insurance · Blocklist · Clearinghouse.
            </p>
            <div className="flex gap-2 mb-5">
              <Input value={mcLookup} onChange={(e) => setMcLookup(e.target.value)}
                placeholder="MC or DOT number"
                className="bg-[#0B1320] border-white/10 text-white max-w-xs"
                data-testid="compliance-mc" />
              <Button onClick={runCompliance} className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold"
                data-testid="compliance-run">
                <Shield size={14} className="mr-2" /> Run Check
              </Button>
            </div>

            {compResult && (
              <div className="p-5 rounded-lg border bg-white/[0.02]"
                   style={{ borderColor: compResult.flag === "green" ? "rgba(16,185,129,0.4)"
                            : compResult.flag === "amber" ? "rgba(251,146,60,0.4)" : "rgba(239,68,68,0.4)" }}
                   data-testid="compliance-result">
                <div className="flex items-center justify-between flex-wrap gap-3 mb-4">
                  <div>
                    <div className="font-display text-xl font-bold">{compResult.carrier_name || "Unknown carrier"}</div>
                    <div className="text-xs font-mono text-slate-500">MC {compResult.mc_number}</div>
                  </div>
                  <CompliancePill flag={compResult.flag} large summary={compResult.summary} />
                </div>
                <div className="space-y-2">
                  {compResult.checks.map((c, i) => (
                    <div key={i} className="flex items-center justify-between p-2 rounded bg-black/20" data-testid={`check-${i}`}>
                      <div className="flex items-center gap-2 text-sm">
                        {c.status === "pass" ? <CheckCircle2 size={14} className="text-emerald-400" />
                          : c.status === "warn" ? <AlertTriangle size={14} className="text-amber-400" />
                          : <XCircle size={14} className="text-red-400" />}
                        <span>{c.name}</span>
                      </div>
                      <div className="text-xs text-slate-400">{c.detail}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </Card>
        )}

        {/* ================ AUTO-INVOICE ================ */}
        {activeTab === "invoice" && (
          <Card className="hud-surface p-6" data-testid="tab-content-invoice">
            <h2 className="font-display text-xl font-bold mb-1">Auto-Invoice on POD</h2>
            <p className="text-xs text-slate-400 mb-4">
              When a POD lands on any booking, this endpoint fires atomically:
              generates the invoice PDF, queues a QuickBooks AR entry, and
              drafts the customer email. Call from your POD upload handler or
              hit manually below.
            </p>
            <AutoInvoiceForm />
            <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-3 text-xs text-slate-400">
              <div className="p-3 rounded border border-white/5 bg-white/[0.02]">
                <FileText size={14} className="text-cyan-400 mb-1" />
                <div className="font-bold text-white">PDF generated</div>
                <div>Brand-aware invoice, BOL/POD bundled.</div>
              </div>
              <div className="p-3 rounded border border-white/5 bg-white/[0.02]">
                <DollarSign size={14} className="text-cyan-400 mb-1" />
                <div className="font-bold text-white">QuickBooks queued</div>
                <div>AR entry waits for QBO connector poll.</div>
              </div>
              <div className="p-3 rounded border border-white/5 bg-white/[0.02]">
                <Sparkles size={14} className="text-cyan-400 mb-1" />
                <div className="font-bold text-white">Customer email drafted</div>
                <div>Net-30 reminder ready for Resend.</div>
              </div>
            </div>
          </Card>
        )}

        {/* ================ LOYALTY ================ */}
        {activeTab === "loyalty" && (
          <>
            <Card className="hud-surface p-6" data-testid="tab-content-loyalty">
              <h2 className="font-display text-xl font-bold mb-1">Carrier Loyalty Programs</h2>
              <p className="text-xs text-slate-400 mb-4">
                Define a per-load bonus (flat $ or % of line haul) and a first-look
                window. Platinum carriers see new loads 30 min before the public
                board. Cost: 1–2%. Value: locked-in capacity.
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
                <FormField label="Program name *" value={newProgram.name}
                  onChange={(v) => setNewProgram({ ...newProgram, name: v })}
                  testId="prog-name" placeholder="e.g. Platinum 1.5% Lane-Lock" />
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <Label className="text-[10px] font-mono uppercase tracking-[0.15em] text-slate-400 mb-1.5 block">Bonus type</Label>
                    <select value={newProgram.bonus_type}
                      onChange={(e) => setNewProgram({ ...newProgram, bonus_type: e.target.value })}
                      data-testid="prog-bonus-type"
                      className="w-full px-3 py-2 rounded border bg-[#0B1320] text-white text-sm border-white/10">
                      <option value="percent">% of line haul</option>
                      <option value="flat">$ flat</option>
                    </select>
                  </div>
                  <FormField label={newProgram.bonus_type === "flat" ? "Bonus $" : "Bonus %"}
                    type="number" value={newProgram.bonus_value}
                    onChange={(v) => setNewProgram({ ...newProgram, bonus_value: parseFloat(v) || 0 })}
                    testId="prog-bonus-value" />
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <Label className="text-[10px] font-mono uppercase tracking-[0.15em] text-slate-400 mb-1.5 block">Tier</Label>
                    <select value={newProgram.tier}
                      onChange={(e) => setNewProgram({ ...newProgram, tier: e.target.value })}
                      data-testid="prog-tier"
                      className="w-full px-3 py-2 rounded border bg-[#0B1320] text-white text-sm border-white/10">
                      <option value="platinum">Platinum</option>
                      <option value="gold">Gold</option>
                      <option value="silver">Silver</option>
                    </select>
                  </div>
                  <FormField label="First-look min" type="number" value={newProgram.first_look_minutes}
                    onChange={(v) => setNewProgram({ ...newProgram, first_look_minutes: parseInt(v) || 0 })}
                    testId="prog-first-look" />
                </div>
                <FormField label="Notes (optional)" value={newProgram.notes}
                  onChange={(v) => setNewProgram({ ...newProgram, notes: v })}
                  testId="prog-notes" placeholder="who, when, why" />
              </div>
              <Button onClick={createProgram} className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold"
                data-testid="prog-create">
                <Plus size={14} className="mr-2" /> Create Program
              </Button>
            </Card>

            <Card className="hud-surface p-6" data-testid="loyalty-programs-list">
              <h3 className="font-display text-lg font-bold mb-3">Active Programs · {programs.length}</h3>
              {programs.length === 0 ? (
                <div className="text-slate-400 text-sm italic py-8 text-center">
                  No loyalty programs yet. Create your first one above.
                </div>
              ) : (
                <div className="space-y-2">
                  {programs.map((p) => (
                    <div key={p.program_id} className="p-3 rounded border bg-white/[0.02] flex items-center justify-between flex-wrap gap-2"
                         style={{ borderColor: "rgba(255,255,255,0.06)" }}
                         data-testid={`prog-card-${p.program_id}`}>
                      <div className="flex items-center gap-3 flex-wrap">
                        <TierPill tier={p.tier} large />
                        <div>
                          <div className="font-bold">{p.name}</div>
                          <div className="text-xs text-slate-500 font-mono">
                            {p.bonus_type === "flat" ? `$${p.bonus_value} flat` : `${p.bonus_value}% of line haul`} ·
                            {p.first_look_minutes}-min first-look · {p.active ? "ACTIVE" : "PAUSED"}
                          </div>
                          {p.notes && <div className="text-[10px] text-slate-400 italic mt-1">{p.notes}</div>}
                        </div>
                      </div>
                      <Button size="sm" variant="ghost" onClick={() => deleteProgram(p.program_id)}
                        className="text-red-400 hover:bg-red-500/10"
                        data-testid={`prog-delete-${p.program_id}`}>
                        <Trash2 size={12} />
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </>
        )}
      </div>
    </>
  );
}

function AutoInvoiceForm() {
  const [bookingId, setBookingId] = useState("");
  const [loading, setLoading] = useState(false);
  const run = async () => {
    if (!bookingId.trim()) return toast.error("Booking ID required");
    setLoading(true);
    try {
      const { data } = await api.post(`/margin-shield/invoice/auto/${bookingId.trim()}`);
      if (data.already_invoiced) toast.info(`Already invoiced as ${data.invoice_id}`);
      else toast.success(`Invoice ${data.invoice_id} · $${data.amount_usd.toLocaleString()} · QBO queued · Email drafted`);
    } catch (e) { toast.error(e?.response?.data?.detail || "Auto-invoice failed"); }
    finally { setLoading(false); }
  };
  return (
    <div className="flex gap-2">
      <Input value={bookingId} onChange={(e) => setBookingId(e.target.value)}
        placeholder="Booking ID (must have POD uploaded)"
        className="bg-[#0B1320] border-white/10 text-white max-w-md"
        data-testid="invoice-booking-id" />
      <Button onClick={run} disabled={loading} className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold"
        data-testid="invoice-run">
        <FileText size={14} className="mr-2" /> {loading ? "Generating…" : "Auto-Invoice"}
      </Button>
    </div>
  );
}

function Kpi({ v, k, icon: Icon, accent }) {
  const color = accent === "amber" ? "text-amber-300" : "text-cyan-300";
  return (
    <div className="p-3 rounded-lg border border-cyan-500/20 bg-cyan-500/5 min-w-[100px]">
      <Icon size={14} className="text-slate-500 mb-1" />
      <div className={`font-display text-2xl font-black tabular-nums ${color}`}>{v}</div>
      <div className="text-[9px] font-mono uppercase tracking-wider text-slate-400 mt-0.5">{k}</div>
    </div>
  );
}

function TierPill({ tier, large }) {
  if (!tier || tier === "none") return null;
  const styles = {
    platinum: { bg: "bg-cyan-500/20", text: "text-cyan-300", border: "border-cyan-500/40", icon: Trophy },
    gold:     { bg: "bg-amber-500/20", text: "text-amber-300", border: "border-amber-500/40", icon: Award },
    silver:   { bg: "bg-slate-500/20", text: "text-slate-300", border: "border-slate-500/40", icon: Star },
  };
  const s = styles[tier] || styles.silver;
  const Icon = s.icon;
  return (
    <span className={`inline-flex items-center gap-1 ${large ? "px-2.5 py-1 text-xs" : "px-2 py-0.5 text-[10px]"} rounded-full font-mono uppercase tracking-wider border ${s.bg} ${s.text} ${s.border}`}>
      <Icon size={large ? 12 : 10} /> {tier}
    </span>
  );
}

function CompliancePill({ flag, large, summary }) {
  const styles = {
    green:  { bg: "bg-emerald-500/20", text: "text-emerald-300", border: "border-emerald-500/40", label: "GREEN" },
    amber:  { bg: "bg-amber-500/20", text: "text-amber-300", border: "border-amber-500/40", label: "AMBER" },
    red:    { bg: "bg-red-500/20", text: "text-red-300", border: "border-red-500/40", label: "RED" },
  };
  const s = styles[flag] || styles.amber;
  return (
    <span className={`inline-flex items-center gap-1.5 ${large ? "px-3 py-1.5 text-sm" : "px-2 py-0.5 text-[10px]"} rounded-full font-mono uppercase tracking-wider font-bold border ${s.bg} ${s.text} ${s.border}`}>
      <span className={`w-2 h-2 rounded-full ${s.text.replace("text-", "bg-").replace("-300", "-400")}`}></span>
      {s.label}{summary && large ? ` · ${summary}` : ""}
    </span>
  );
}

function ComponentBar({ label, val }) {
  return (
    <div>
      <div className="flex justify-between text-[9px] uppercase">
        <span className="text-slate-500">{label}</span>
        <span className="text-cyan-300 tabular-nums">{val}</span>
      </div>
      <div className="h-1 bg-white/5 rounded overflow-hidden mt-0.5">
        <div className="h-full bg-cyan-400" style={{ width: `${Math.min(100, (val / 35) * 100)}%` }} />
      </div>
    </div>
  );
}

function FormField({ label, value, onChange, type = "text", placeholder, testId }) {
  return (
    <div>
      <Label className="text-[10px] font-mono uppercase tracking-[0.15em] text-slate-400 mb-1.5 block">{label}</Label>
      <Input type={type} value={value} onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder} data-testid={testId}
        className="bg-[#0B1320] border-white/10 text-white" />
    </div>
  );
}
