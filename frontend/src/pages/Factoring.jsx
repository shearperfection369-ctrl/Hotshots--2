import React, { useEffect, useState, useCallback, useMemo } from "react";
import Topbar from "@/components/Topbar";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription,
} from "@/components/ui/dialog";
import {
  Banknote, TrendingUp, Building2, Map, FileText, Plus, Send, Copy, Sparkles,
  Calculator, Route, Network, Clock, PiggyBank, PieChart, ExternalLink, Mail,
  CheckCircle2, AlertTriangle, ArrowRight, ArrowDown, DollarSign, Shield,
  Loader2, Trash2,
} from "lucide-react";
import { toast } from "sonner";

/**
 * /factoring — Orisei Freight Factoring & ABL Transition Hub.
 *
 * Six tabs sourced from the user's playbook:
 *   1. Dashboard           — live stats + current stage + per-factor mix
 *   2. Factor Marketplace  — 8 freight factors + AI-polished outreach
 *   3. Submissions         — submit invoices, track advance/reserve
 *   4. Calculator          — Spot vs Recourse vs Non-Recourse vs ABL
 *   5. Maturity Roadmap    — 5-stage day-1 → ABL transition plan
 *   6. Strategies          — 4 critical strategies from the playbook
 */

const TABS = [
  { id: "dash",        label: "Dashboard",          icon: TrendingUp },
  { id: "factors",     label: "Factor Marketplace", icon: Building2 },
  { id: "submissions", label: "Submissions",        icon: FileText },
  { id: "calc",        label: "Cost Calculator",    icon: Calculator },
  { id: "roadmap",     label: "Maturity Roadmap",   icon: Route },
  { id: "strategies",  label: "Strategies",         icon: Sparkles },
];

const STRATEGY_ICONS = { Network, Clock, PiggyBank, PieChart };

export default function Factoring() {
  const [tab, setTab] = useState("dash");
  return (
    <>
      <Topbar
        title="Factoring · Run the Float"
        subtitle="Float shipper payments · pay carriers in 48h · graduate to ABL"
      />
      <div className="p-4 md:p-6">
        <div className="flex gap-2 flex-wrap mb-4" data-testid="factoring-tabs">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              data-testid={`tab-${id}`}
              onClick={() => setTab(id)}
              className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-mono uppercase tracking-wider transition border ${
                tab === id
                  ? "bg-amber-500 text-slate-950 border-amber-400 shadow-[0_0_18px_rgba(245,158,11,0.4)]"
                  : "border-white/10 text-slate-400 hover:border-amber-400/40 hover:text-amber-200"
              }`}
            >
              <Icon size={13} /> {label}
            </button>
          ))}
        </div>

        {tab === "dash"        && <DashTab />}
        {tab === "factors"     && <FactorsTab />}
        {tab === "submissions" && <SubmissionsTab />}
        {tab === "calc"        && <CalcTab />}
        {tab === "roadmap"     && <RoadmapTab />}
        {tab === "strategies"  && <StrategiesTab />}
      </div>
    </>
  );
}

// =====================================================================
// DASHBOARD
// =====================================================================
function DashTab() {
  const [dash, setDash] = useState(null);
  const load = useCallback(async () => {
    try {
      const { data } = await api.get("/factoring/dashboard");
      setDash(data);
    } catch (e) { toast.error("Could not load dashboard"); }
  }, []);
  useEffect(() => { load(); }, [load]);

  if (!dash) return <div className="text-slate-500 text-sm">Loading…</div>;

  return (
    <div className="grid grid-cols-12 gap-4">
      {/* KPIs */}
      <Card className="col-span-12 md:col-span-3 p-4 bg-slate-950/60 border-amber-400/20">
        <div className="text-[10px] uppercase tracking-widest text-amber-300 font-mono">Live Factors</div>
        <div className="text-3xl font-mono text-white mt-1 tabular-nums" data-testid="kpi-live-factors">
          {dash.live_factor_count}
        </div>
        <div className="text-[11px] text-slate-400 mt-1">
          {dash.application_count} total applications
        </div>
      </Card>
      <Card className="col-span-12 md:col-span-3 p-4 bg-slate-950/60 border-cyan-400/20">
        <div className="text-[10px] uppercase tracking-widest text-cyan-300 font-mono">90d Invoiced</div>
        <div className="text-3xl font-mono text-white mt-1 tabular-nums" data-testid="kpi-invoices">
          ${(dash.totals_90d.invoices_usd / 1000).toFixed(1)}<span className="text-sm text-slate-500">k</span>
        </div>
        <div className="text-[11px] text-slate-400 mt-1">{dash.totals_90d.submissions} submissions</div>
      </Card>
      <Card className="col-span-12 md:col-span-3 p-4 bg-slate-950/60 border-red-400/20">
        <div className="text-[10px] uppercase tracking-widest text-red-300 font-mono">90d Factor Fee</div>
        <div className="text-3xl font-mono text-white mt-1 tabular-nums" data-testid="kpi-fee">
          ${(dash.totals_90d.fee_usd / 1000).toFixed(1)}<span className="text-sm text-slate-500">k</span>
        </div>
        <div className="text-[11px] text-slate-400 mt-1">eff. {dash.totals_90d.effective_fee_pct}%</div>
      </Card>
      <Card className="col-span-12 md:col-span-3 p-4 bg-slate-950/60 border-emerald-400/20">
        <div className="text-[10px] uppercase tracking-widest text-emerald-300 font-mono">Current Stage</div>
        <div className="text-lg font-semibold text-white mt-1">{dash.stage.label}</div>
        <div className="text-[11px] text-slate-400 mt-1">
          {dash.monthly_loads_est} loads/mo · {dash.stage.type_label}
        </div>
      </Card>

      {/* Per-factor mix */}
      <Card className="col-span-12 lg:col-span-7 p-5 bg-slate-950/60 border-white/10">
        <div className="text-xs font-mono uppercase tracking-widest text-amber-300 mb-3">
          Per-Factor Volume Mix (90 days)
        </div>
        {!dash.by_factor.length && (
          <div className="text-slate-500 text-sm py-8 text-center">
            No submissions yet. Submit your first invoice on the Submissions tab.
          </div>
        )}
        <div className="space-y-2">
          {dash.by_factor.map(f => {
            const pct = dash.totals_90d.invoices_usd > 0
              ? (f.invoices_usd / dash.totals_90d.invoices_usd * 100) : 0;
            return (
              <div key={f.factor_id} className="p-3 rounded-lg bg-slate-900/60 border border-white/5">
                <div className="flex justify-between items-baseline">
                  <div className="text-sm text-white font-semibold">{f.name}</div>
                  <div className="text-xs text-slate-400 font-mono">{pct.toFixed(1)}%</div>
                </div>
                <div className="flex gap-4 mt-1 text-[11px] text-slate-400">
                  <span>${f.invoices_usd.toLocaleString()} invoiced</span>
                  <span>${f.fee_usd.toLocaleString()} fee</span>
                  <span>{f.count} subs</span>
                  <span className="text-amber-300">eff {f.effective_fee_pct}%</span>
                </div>
                <div className="mt-1.5 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                  <div className="h-full bg-gradient-to-r from-amber-400 to-amber-600" style={{ width: `${pct}%` }} />
                </div>
              </div>
            );
          })}
        </div>
      </Card>

      {/* Applications funnel */}
      <Card className="col-span-12 lg:col-span-5 p-5 bg-slate-950/60 border-white/10">
        <div className="text-xs font-mono uppercase tracking-widest text-cyan-300 mb-3">
          Application Pipeline
        </div>
        <div className="space-y-2">
          {Object.entries(dash.applications_summary).map(([k, v]) => (
            <div key={k} className="flex justify-between items-center py-2 px-3 rounded-lg bg-slate-900/60 border border-white/5">
              <span className="text-xs text-slate-300 capitalize">{k.replace("_", " ")}</span>
              <span className="font-mono text-white">{v}</span>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

// =====================================================================
// FACTOR MARKETPLACE + AI OUTREACH
// =====================================================================
function FactorsTab() {
  const [factors, setFactors] = useState([]);
  const [apps, setApps] = useState([]);
  const [selected, setSelected] = useState(null);
  const [outreach, setOutreach] = useState(null);
  const [polishing, setPolishing] = useState(false);
  const [appOpen, setAppOpen] = useState(false);
  const [appDraft, setAppDraft] = useState({ status: "preparing", notes: "" });
  const [outreachForm, setOutreachForm] = useState({
    broker_name: "Orisei Freight Solutions LLC",
    contact_name: "Oliver Cummins",
    contact_email: "",
    contact_phone: "",
    current_loads_per_month: 25,
    projected_3mo_loads: 80,
    projected_6mo_loads: 250,
    top_shippers: ["SUPERVALU", "Target", "3M"],
    lanes: ["MPLS → Chicago", "MPLS → Milwaukee"],
    state: "Minnesota",
    custom_note: "",
  });

  const load = useCallback(async () => {
    try {
      const [f, a] = await Promise.all([
        api.get("/factoring/factors"),
        api.get("/factoring/applications"),
      ]);
      setFactors(f.data.items || []);
      setApps(a.data.items || []);
    } catch (e) { toast.error("Could not load factors"); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const generateOutreach = async (factor, polish = false) => {
    setSelected(factor);
    setOutreach(null);
    if (polish) setPolishing(true);
    try {
      const endpoint = polish ? "/factoring/outreach/ai-polish" : "/factoring/outreach/generate";
      const { data } = await api.post(endpoint, {
        factor_id: factor.factor_id,
        ...outreachForm,
        contact_email: outreachForm.contact_email || undefined,
      });
      setOutreach(data);
      if (polish && data.ai_polished) toast.success("AI polish complete");
      if (polish && !data.ai_polished) toast.info("AI unavailable, returned deterministic template");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not generate");
    } finally {
      setPolishing(false);
    }
  };

  const copyBody = () => {
    if (!outreach) return;
    navigator.clipboard.writeText(outreach.body);
    toast.success("Outreach copied to clipboard");
  };

  const startApplication = (factor) => {
    setSelected(factor);
    setAppDraft({
      factor_id: factor.factor_id,
      status: "preparing", notes: "",
      monthly_volume_target_usd: outreachForm.current_loads_per_month * 1320,
    });
    setAppOpen(true);
  };

  const saveApplication = async () => {
    try {
      await api.post("/factoring/applications", {
        ...appDraft, factor_id: selected.factor_id,
      });
      toast.success(`Application logged: ${selected.name}`);
      setAppOpen(false);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not save");
    }
  };

  const appsByFactor = useMemo(() => {
    const map = {};
    for (const a of apps) (map[a.factor_id] = map[a.factor_id] || []).push(a);
    return map;
  }, [apps]);

  return (
    <div className="grid grid-cols-12 gap-4">
      {/* Outreach form */}
      <Card className="col-span-12 lg:col-span-4 p-5 bg-slate-950/60 border-amber-400/20" data-testid="outreach-form">
        <div className="flex items-center gap-2 mb-3">
          <Sparkles className="text-amber-300" size={16} />
          <div className="text-sm font-semibold text-white">Outreach Parameters</div>
        </div>
        <div className="space-y-2">
          <Field label="Broker name" value={outreachForm.broker_name}
                 onChange={(v) => setOutreachForm({ ...outreachForm, broker_name: v })} />
          <Field label="Contact name" value={outreachForm.contact_name}
                 onChange={(v) => setOutreachForm({ ...outreachForm, contact_name: v })} />
          <Field label="Contact email" value={outreachForm.contact_email} type="email"
                 onChange={(v) => setOutreachForm({ ...outreachForm, contact_email: v })} />
          <Field label="Contact phone" value={outreachForm.contact_phone}
                 onChange={(v) => setOutreachForm({ ...outreachForm, contact_phone: v })} />
          <div className="grid grid-cols-3 gap-2">
            <Field label="Today / mo" type="number" value={outreachForm.current_loads_per_month}
                   onChange={(v) => setOutreachForm({ ...outreachForm, current_loads_per_month: parseInt(v) || 0 })} />
            <Field label="3mo / mo" type="number" value={outreachForm.projected_3mo_loads}
                   onChange={(v) => setOutreachForm({ ...outreachForm, projected_3mo_loads: parseInt(v) || 0 })} />
            <Field label="6mo / mo" type="number" value={outreachForm.projected_6mo_loads}
                   onChange={(v) => setOutreachForm({ ...outreachForm, projected_6mo_loads: parseInt(v) || 0 })} />
          </div>
          <Field label="Top shippers (comma)"
                 value={outreachForm.top_shippers.join(", ")}
                 onChange={(v) => setOutreachForm({ ...outreachForm, top_shippers: v.split(",").map(s => s.trim()).filter(Boolean) })} />
          <Field label="Lanes (semicolon)"
                 value={outreachForm.lanes.join("; ")}
                 onChange={(v) => setOutreachForm({ ...outreachForm, lanes: v.split(";").map(s => s.trim()).filter(Boolean) })} />
          <div>
            <Label className="text-[10px] uppercase tracking-widest text-slate-400">Custom note</Label>
            <Textarea data-testid="outreach-custom-note" value={outreachForm.custom_note}
                      onChange={(e) => setOutreachForm({ ...outreachForm, custom_note: e.target.value })}
                      className="bg-slate-900 border-white/10 text-xs min-h-[60px]"
                      placeholder="e.g. Referred by John at Bell Bank" />
          </div>
        </div>
      </Card>

      {/* Factor cards */}
      <div className="col-span-12 lg:col-span-8 space-y-3">
        <div className="text-xs font-mono uppercase tracking-widest text-amber-300">
          Freight Factor Marketplace · {factors.length} options
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {factors.map(f => (
            <Card key={f.factor_id} data-testid={`factor-${f.factor_id}`}
                  className={`p-4 bg-slate-950/60 border ${f.midwest ? "border-amber-400/30" : "border-white/10"} hover:border-amber-400/50 transition`}>
              <div className="flex justify-between items-start gap-2 mb-2">
                <div className="min-w-0">
                  <div className="text-sm font-semibold text-white">{f.name}</div>
                  <div className="text-[11px] text-slate-400 mt-0.5">{f.headquarters}</div>
                </div>
                <div className="text-right">
                  {f.midwest && <Badge className="bg-amber-500/20 text-amber-200 border-amber-400/40 text-[9px]">MIDWEST</Badge>}
                  <Badge variant="outline" className="bg-slate-900 border-white/10 text-[9px] ml-1">{f.kind.toUpperCase()}</Badge>
                </div>
              </div>
              <div className="grid grid-cols-3 gap-2 my-3 text-center">
                <div>
                  <div className="text-[9px] uppercase tracking-widest text-slate-400">Fee</div>
                  <div className="text-sm font-mono text-amber-300">{f.fee_pct_min}–{f.fee_pct_max}%</div>
                </div>
                <div>
                  <div className="text-[9px] uppercase tracking-widest text-slate-400">Advance</div>
                  <div className="text-sm font-mono text-cyan-300">{f.advance_pct}%</div>
                </div>
                <div>
                  <div className="text-[9px] uppercase tracking-widest text-slate-400">Setup</div>
                  <div className="text-sm font-mono text-white">{Math.round(f.setup_time_hours / 24)}d</div>
                </div>
              </div>
              <div className="text-[11px] text-slate-300 mb-2 line-clamp-2">{f.best_for}</div>
              <div className="text-[10px] text-slate-500 italic mb-3">{f.notes}</div>
              {appsByFactor[f.factor_id]?.length > 0 && (
                <div className="mb-2 flex flex-wrap gap-1">
                  {appsByFactor[f.factor_id].map(a => (
                    <Badge key={a.application_id}
                           className="bg-emerald-500/15 text-emerald-200 border-emerald-400/30 text-[9px]">
                      {a.status}
                    </Badge>
                  ))}
                </div>
              )}
              <div className="flex flex-wrap gap-2">
                <Button size="sm" onClick={() => generateOutreach(f, false)}
                        data-testid={`outreach-${f.factor_id}`}
                        className="bg-cyan-500 text-black hover:bg-cyan-400 h-8 text-xs">
                  <Mail size={11} className="mr-1" /> Outreach
                </Button>
                <Button size="sm" onClick={() => generateOutreach(f, true)}
                        data-testid={`ai-polish-${f.factor_id}`}
                        className="bg-gradient-to-r from-amber-400 to-amber-500 text-slate-950 hover:from-amber-300 h-8 text-xs">
                  <Sparkles size={11} className="mr-1" /> AI Polish
                </Button>
                <Button size="sm" variant="outline" onClick={() => startApplication(f)}
                        data-testid={`apply-${f.factor_id}`}
                        className="bg-slate-900 border-white/10 h-8 text-xs">
                  <Plus size={11} className="mr-1" /> Log App
                </Button>
                <a href={f.website} target="_blank" rel="noreferrer"
                   className="inline-flex items-center gap-1 px-2 py-1 text-[11px] text-slate-400 hover:text-cyan-300">
                  <ExternalLink size={10} /> Site
                </a>
              </div>
            </Card>
          ))}
        </div>
      </div>

      {/* Outreach preview modal */}
      <Dialog open={!!outreach} onOpenChange={() => { setOutreach(null); setSelected(null); }}>
        <DialogContent className="bg-slate-950 border-amber-400/30 text-white max-w-3xl">
          <DialogHeader>
            <DialogTitle className="text-amber-200 flex items-center gap-2">
              {polishing && <Loader2 className="animate-spin" size={16} />}
              Outreach · {outreach?.factor_name || selected?.name}
              {outreach?.ai_polished && <Badge className="bg-amber-500/20 text-amber-200 border-amber-400/40 text-[9px]">AI POLISHED</Badge>}
            </DialogTitle>
            <DialogDescription className="text-slate-400 text-xs">
              First-touch email · {outreach?.factor_name}
            </DialogDescription>
          </DialogHeader>
          {outreach && (
            <div className="space-y-3">
              <div>
                <Label className="text-[10px] uppercase tracking-widest text-slate-400">Subject</Label>
                <Input value={outreach.subject} readOnly
                       data-testid="outreach-subject"
                       className="bg-slate-900 border-white/10 text-amber-200" />
              </div>
              <div>
                <Label className="text-[10px] uppercase tracking-widest text-slate-400">Body</Label>
                <Textarea value={outreach.body} readOnly
                          data-testid="outreach-body"
                          className="bg-slate-900 border-white/10 font-mono text-xs min-h-[340px]" />
              </div>
              <div className="text-[11px] text-slate-400">
                Contact methods: {(outreach.factor?.contact_methods || []).join(" · ")}
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => { setOutreach(null); setSelected(null); }} className="bg-slate-900 border-white/10">Close</Button>
            {outreach && (
              <>
                <Button onClick={copyBody} className="bg-slate-700 hover:bg-slate-600" data-testid="outreach-copy">
                  <Copy size={14} className="mr-1.5" /> Copy
                </Button>
                <a href={outreach.mailto} className="inline-flex">
                  <Button className="bg-amber-500 text-slate-950 hover:bg-amber-400 font-semibold" data-testid="outreach-mailto">
                    <Send size={14} className="mr-1.5" /> Open in mail client
                  </Button>
                </a>
              </>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Application dialog */}
      <Dialog open={appOpen} onOpenChange={setAppOpen}>
        <DialogContent className="bg-slate-950 border-white/10 text-white max-w-md">
          <DialogHeader>
            <DialogTitle>Log application · {selected?.name}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <Label className="text-[10px] uppercase tracking-widest text-slate-400">Status</Label>
              <select value={appDraft.status}
                      onChange={(e) => setAppDraft({ ...appDraft, status: e.target.value })}
                      data-testid="app-status"
                      className="w-full bg-slate-900 border border-white/10 rounded px-3 py-2 text-sm">
                <option value="preparing">Preparing</option>
                <option value="sent">Sent</option>
                <option value="underwriting">Underwriting</option>
                <option value="approved">Approved</option>
                <option value="live">Live</option>
                <option value="declined">Declined</option>
              </select>
            </div>
            <Field label="Contact name (factor side)" value={appDraft.contact_name || ""}
                   onChange={(v) => setAppDraft({ ...appDraft, contact_name: v })} />
            <Field label="Contact email" value={appDraft.contact_email || ""}
                   onChange={(v) => setAppDraft({ ...appDraft, contact_email: v })} type="email" />
            <Field label="Monthly volume target $" type="number" value={appDraft.monthly_volume_target_usd || 0}
                   onChange={(v) => setAppDraft({ ...appDraft, monthly_volume_target_usd: parseFloat(v) || 0 })} />
            <div>
              <Label className="text-[10px] uppercase tracking-widest text-slate-400">Notes</Label>
              <Textarea value={appDraft.notes || ""}
                        onChange={(e) => setAppDraft({ ...appDraft, notes: e.target.value })}
                        className="bg-slate-900 border-white/10 text-xs" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAppOpen(false)} className="bg-slate-900 border-white/10">Cancel</Button>
            <Button onClick={saveApplication} data-testid="app-save" className="bg-amber-500 text-slate-950 hover:bg-amber-400">
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// =====================================================================
// SUBMISSIONS
// =====================================================================
function SubmissionsTab() {
  const [items, setItems] = useState([]);
  const [totals, setTotals] = useState({});
  const [factors, setFactors] = useState([]);
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState({
    factor_id: "", invoice_id: "", customer_name: "",
    invoice_usd: 0, carrier_cost_usd: 0, payment_terms_days: 14,
  });

  const load = useCallback(async () => {
    try {
      const [s, f] = await Promise.all([
        api.get("/factoring/submissions"),
        api.get("/factoring/factors"),
      ]);
      setItems(s.data.items || []);
      setTotals(s.data.totals || {});
      setFactors(f.data.items || []);
      if (!draft.factor_id && f.data.items?.length)
        setDraft(d => ({ ...d, factor_id: f.data.items[0].factor_id }));
    } catch (e) { toast.error("Could not load submissions"); }
  }, [draft.factor_id]);
  useEffect(() => { load(); }, [load]);

  const submit = async () => {
    if (!draft.factor_id || !draft.invoice_id || !draft.invoice_usd) {
      toast.error("Factor, invoice ID and amount are required"); return;
    }
    try {
      await api.post("/factoring/submissions", draft);
      toast.success(`Submitted to ${factors.find(f => f.factor_id === draft.factor_id)?.name}`);
      setOpen(false);
      setDraft({ ...draft, invoice_id: "", customer_name: "", invoice_usd: 0, carrier_cost_usd: 0 });
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not submit");
    }
  };

  const setStatus = async (id, status) => {
    try {
      await api.post(`/factoring/submissions/${id}/status`, { status });
      toast.success(`Marked ${status}`);
      load();
    } catch (e) { toast.error("Could not update"); }
  };

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <Stat label="Invoices" value={`$${(totals.invoices_usd || 0).toLocaleString()}`} />
        <Stat label="Advances paid" value={`$${(totals.advance_usd || 0).toLocaleString()}`} />
        <Stat label="Fees paid"    value={`$${(totals.fee_usd || 0).toLocaleString()}`} color="text-red-300" />
        <Stat label="Reserves held" value={`$${(totals.reserve_usd || 0).toLocaleString()}`} color="text-amber-300" />
        <Stat label="Effective %"  value={`${totals.effective_fee_pct || 0}%`} color="text-cyan-300" />
      </div>

      <div className="flex justify-between items-center">
        <div className="text-xs font-mono uppercase tracking-widest text-amber-300">
          Submissions · {items.length}
        </div>
        <Button onClick={() => setOpen(true)} data-testid="new-submission-btn"
                className="bg-amber-500 text-slate-950 hover:bg-amber-400">
          <Plus size={14} className="mr-1" /> Submit Invoice
        </Button>
      </div>

      <Card className="p-0 bg-slate-950/60 border-white/10 overflow-hidden">
        <table className="w-full text-xs">
          <thead className="bg-slate-900/80 text-[10px] uppercase tracking-widest text-slate-400 font-mono">
            <tr>
              <th className="text-left p-3">ID</th>
              <th className="text-left p-3">Factor</th>
              <th className="text-left p-3">Invoice</th>
              <th className="text-right p-3">Amount</th>
              <th className="text-right p-3">Advance</th>
              <th className="text-right p-3">Fee</th>
              <th className="text-right p-3">Take-home</th>
              <th className="text-center p-3">Status</th>
            </tr>
          </thead>
          <tbody>
            {items.map(s => (
              <tr key={s.submission_id} data-testid={`sub-${s.submission_id}`}
                  className="border-t border-white/5 hover:bg-slate-900/40">
                <td className="p-3 font-mono text-cyan-200 text-[11px]">{s.submission_id}</td>
                <td className="p-3 text-white">{s.factor_name}</td>
                <td className="p-3">
                  <div className="font-mono text-amber-200">{s.invoice_id}</div>
                  <div className="text-[10px] text-slate-500">{s.customer_name || "—"}</div>
                </td>
                <td className="p-3 text-right font-mono">${(s.invoice_usd || 0).toLocaleString()}</td>
                <td className="p-3 text-right font-mono text-cyan-300">${(s.advance_usd || 0).toLocaleString()}</td>
                <td className="p-3 text-right font-mono text-red-300">${(s.fee_usd || 0).toLocaleString()}</td>
                <td className={`p-3 text-right font-mono ${s.broker_take_home_usd >= 0 ? "text-emerald-300" : "text-red-300"}`}>
                  ${(s.broker_take_home_usd || 0).toLocaleString()}
                </td>
                <td className="p-3 text-center">
                  <select value={s.status} onChange={(e) => setStatus(s.submission_id, e.target.value)}
                          data-testid={`status-${s.submission_id}`}
                          className="bg-slate-900 border border-white/10 rounded px-2 py-1 text-[11px]">
                    <option value="submitted">submitted</option>
                    <option value="approved">approved</option>
                    <option value="funded">funded</option>
                    <option value="settled">settled</option>
                    <option value="declined">declined</option>
                  </select>
                </td>
              </tr>
            ))}
            {!items.length && (
              <tr><td colSpan="8" className="p-8 text-center text-slate-500">
                No factoring submissions yet. Click <b>Submit Invoice</b> to log your first one.
              </td></tr>
            )}
          </tbody>
        </table>
      </Card>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="bg-slate-950 border-white/10 text-white max-w-lg">
          <DialogHeader>
            <DialogTitle>Submit invoice for factoring</DialogTitle>
            <DialogDescription className="text-slate-400 text-xs">
              Calculates advance, fee, reserve and broker take-home automatically.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <Label className="text-[10px] uppercase tracking-widest text-slate-400">Factor</Label>
              <select value={draft.factor_id}
                      onChange={(e) => setDraft({ ...draft, factor_id: e.target.value })}
                      data-testid="sub-factor"
                      className="w-full bg-slate-900 border border-white/10 rounded px-3 py-2 text-sm">
                {factors.map(f => (
                  <option key={f.factor_id} value={f.factor_id}>{f.name}</option>
                ))}
              </select>
            </div>
            <Field label="Invoice ID" value={draft.invoice_id}
                   onChange={(v) => setDraft({ ...draft, invoice_id: v })} testid="sub-invoice-id" />
            <Field label="Customer name (optional)" value={draft.customer_name}
                   onChange={(v) => setDraft({ ...draft, customer_name: v })} />
            <div className="grid grid-cols-2 gap-3">
              <Field label="Invoice $ (customer rate)" type="number" value={draft.invoice_usd}
                     onChange={(v) => setDraft({ ...draft, invoice_usd: parseFloat(v) || 0 })} testid="sub-amount" />
              <Field label="Carrier cost $" type="number" value={draft.carrier_cost_usd}
                     onChange={(v) => setDraft({ ...draft, carrier_cost_usd: parseFloat(v) || 0 })} testid="sub-carrier-cost" />
            </div>
            <Field label="Payment terms (days)" type="number" value={draft.payment_terms_days}
                   onChange={(v) => setDraft({ ...draft, payment_terms_days: parseInt(v) || 14 })} />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)} className="bg-slate-900 border-white/10">Cancel</Button>
            <Button onClick={submit} data-testid="sub-save" className="bg-amber-500 text-slate-950 hover:bg-amber-400">
              <Banknote size={14} className="mr-1.5" /> Submit
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// =====================================================================
// COST CALCULATOR
// =====================================================================
function CalcTab() {
  const [params, setParams] = useState({
    monthly_loads: 80, avg_invoice_usd: 1320,
    avg_margin_usd_per_load: 220, payment_terms_days: 14,
  });
  const [result, setResult] = useState(null);

  const calc = useCallback(async () => {
    try {
      const { data } = await api.post("/factoring/compare-cost", params);
      setResult(data);
    } catch (e) { toast.error("Could not calculate"); }
  }, [params]);
  useEffect(() => { calc(); }, [calc]);

  return (
    <div className="grid grid-cols-12 gap-4">
      <Card className="col-span-12 lg:col-span-4 p-5 bg-slate-950/60 border-amber-400/20">
        <div className="text-xs font-mono uppercase tracking-widest text-amber-300 mb-3">
          Your Volume Profile
        </div>
        <div className="space-y-3">
          <Field label="Monthly loads" type="number" value={params.monthly_loads}
                 onChange={(v) => setParams({ ...params, monthly_loads: parseInt(v) || 0 })} testid="calc-loads" />
          <Field label="Avg invoice $" type="number" value={params.avg_invoice_usd}
                 onChange={(v) => setParams({ ...params, avg_invoice_usd: parseFloat(v) || 0 })} testid="calc-invoice" />
          <Field label="Avg margin $/load" type="number" value={params.avg_margin_usd_per_load}
                 onChange={(v) => setParams({ ...params, avg_margin_usd_per_load: parseFloat(v) || 0 })} testid="calc-margin" />
          <Field label="Shipper payment terms (days)" type="number" value={params.payment_terms_days}
                 onChange={(v) => setParams({ ...params, payment_terms_days: parseInt(v) || 14 })} testid="calc-terms" />
          {result && (
            <div className="pt-3 border-t border-white/10 space-y-1 text-xs">
              <Row k="Total invoices/mo" v={`$${result.total_invoices_usd.toLocaleString()}`} />
              <Row k="Total margin/mo"   v={`$${result.total_margin_usd.toLocaleString()}`} color="text-emerald-300" />
              <Row k="Outstanding AR"    v={`$${result.outstanding_ar_usd.toLocaleString()}`} color="text-cyan-300" />
            </div>
          )}
        </div>
      </Card>

      <div className="col-span-12 lg:col-span-8 space-y-3">
        <div className="text-xs font-mono uppercase tracking-widest text-amber-300">
          Funding Method Comparison
        </div>
        {result?.rows.map(r => (
          <Card key={r.kind} data-testid={`calc-row-${r.kind}`}
                className={`p-4 bg-slate-950/60 border ${r.is_best ? "border-emerald-400/60 shadow-[0_0_20px_rgba(16,185,129,0.25)]" : "border-white/10"}`}>
            <div className="flex justify-between items-start">
              <div>
                <div className="flex items-center gap-2">
                  <div className="text-sm font-semibold text-white">{r.label}</div>
                  {r.is_best && (
                    <Badge className="bg-emerald-500/20 text-emerald-200 border-emerald-400/40 text-[9px]">
                      LOWEST COST
                    </Badge>
                  )}
                  {r.is_interest && (
                    <Badge variant="outline" className="bg-slate-900 border-cyan-400/30 text-cyan-200 text-[9px]">
                      MONTHLY INTEREST
                    </Badge>
                  )}
                </div>
                <div className="text-[11px] text-slate-400 mt-0.5">
                  {r.fee_or_apr_pct}% {r.is_interest ? "on outstanding AR" : "of every invoice"} · {r.advance_pct}% advance
                </div>
              </div>
              <div className="text-right">
                <div className="text-[10px] uppercase tracking-widest text-slate-500">Cost / mo</div>
                <div className="text-xl font-mono text-red-300">${r.cost_usd.toLocaleString()}</div>
              </div>
            </div>
            <div className="grid grid-cols-3 gap-2 mt-3 text-center">
              <Mini label="Cash unlocked" v={`$${r.advance_usd.toLocaleString()}`} c="text-cyan-300" />
              <Mini label="Net margin"    v={`$${r.net_margin_usd.toLocaleString()}`} c="text-emerald-300" />
              <Mini label="% of margin"   v={`${r.margin_cost_pct}%`} c={r.margin_cost_pct > 18 ? "text-red-300" : r.margin_cost_pct > 10 ? "text-amber-300" : "text-emerald-300"} />
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}

// =====================================================================
// MATURITY ROADMAP
// =====================================================================
function RoadmapTab() {
  const [stages, setStages] = useState([]);
  const [open, setOpen] = useState(null);

  useEffect(() => {
    api.get("/factoring/stages").then(({ data }) => setStages(data.stages || [])).catch(() => {});
  }, []);

  return (
    <div className="space-y-4" data-testid="roadmap">
      <Card className="p-5 bg-gradient-to-r from-amber-950/40 to-slate-950/60 border-amber-400/30">
        <div className="flex items-center gap-2 text-amber-300 text-xs font-mono uppercase tracking-widest mb-2">
          <Route size={14} /> Your 12-month transition · Day 1 → ABL
        </div>
        <div className="text-sm text-slate-200">
          Five stages calibrated to your weekly load volume + monthly margin. Click each card
          for the exact next-action checklist and success metrics.
        </div>
      </Card>

      <div className="space-y-3">
        {stages.map((s, idx) => (
          <Card key={s.stage_id} data-testid={`stage-${s.stage_id}`}
                className="p-4 bg-slate-950/60 border-white/10 hover:border-amber-400/40 cursor-pointer transition"
                onClick={() => setOpen(s)}>
            <div className="flex items-center gap-4">
              <div className="flex-none w-12 h-12 rounded-xl grid place-items-center bg-gradient-to-br from-amber-400 to-amber-700 text-slate-950 font-bold text-lg">
                {idx + 1}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <div className="text-base font-semibold text-white">{s.label}</div>
                  <Badge className="bg-cyan-500/15 text-cyan-200 border-cyan-400/30 text-[9px]">
                    {s.type_label}
                  </Badge>
                </div>
                <div className="text-[11px] text-slate-400 mt-0.5">
                  {s.month_range} · {s.loads_per_week_min}–{s.loads_per_week_max} loads/wk ·
                  ${(s.monthly_margin_usd_min/1000).toFixed(1)}k–${(s.monthly_margin_usd_max/1000).toFixed(0)}k margin
                </div>
                <div className="text-xs text-slate-300 mt-1 line-clamp-1">{s.rationale}</div>
              </div>
              <div className="flex-none text-right">
                <div className="text-[10px] uppercase tracking-widest text-amber-300">Fee</div>
                <div className="text-lg font-mono text-amber-200">{s.fee_pct}%</div>
              </div>
              <ArrowRight className="text-slate-500" size={18} />
            </div>
          </Card>
        ))}
      </div>

      <Dialog open={!!open} onOpenChange={() => setOpen(null)}>
        <DialogContent className="bg-slate-950 border-amber-400/30 text-white max-w-2xl">
          <DialogHeader>
            <DialogTitle className="text-amber-200">{open?.label}</DialogTitle>
            <DialogDescription className="text-slate-400 text-xs">
              {open?.month_range} · {open?.type_label} · {open?.fee_pct}% fee · {open?.advance_pct}% advance
            </DialogDescription>
          </DialogHeader>
          {open && (
            <div className="space-y-3">
              <div className="text-sm text-slate-200 italic">{open.rationale}</div>
              <div>
                <div className="text-[10px] uppercase tracking-widest text-amber-300 mb-2">Action Items</div>
                <ul className="space-y-1.5">
                  {open.actions.map((a, i) => (
                    <li key={i} className="flex gap-2 text-xs text-slate-300">
                      <CheckCircle2 size={14} className="flex-none text-emerald-400 mt-0.5" />
                      <span>{a}</span>
                    </li>
                  ))}
                </ul>
              </div>
              <Card className="p-3 bg-emerald-950/30 border-emerald-400/30">
                <div className="text-[10px] uppercase tracking-widest text-emerald-300">Success Metric</div>
                <div className="text-sm text-white mt-1">{open.success_metric}</div>
              </Card>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

// =====================================================================
// STRATEGIES
// =====================================================================
function StrategiesTab() {
  const [items, setItems] = useState([]);
  useEffect(() => {
    api.get("/factoring/strategies").then(({ data }) => setItems(data.strategies || [])).catch(() => {});
  }, []);

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4" data-testid="strategies">
      {items.map(s => {
        const Icon = STRATEGY_ICONS[s.icon] || Sparkles;
        return (
          <Card key={s.id} data-testid={`strategy-${s.id}`}
                className="p-5 bg-slate-950/60 border-amber-400/20">
            <div className="flex items-start gap-3 mb-3">
              <div className="flex-none w-11 h-11 rounded-lg bg-amber-500/20 grid place-items-center text-amber-300 border border-amber-400/40">
                <Icon size={18} />
              </div>
              <div>
                <div className="text-sm font-semibold text-white">{s.title}</div>
                <div className="text-[11px] text-slate-400 mt-0.5">{s.summary}</div>
              </div>
            </div>
            <ul className="space-y-1.5 mt-2">
              {s.implementation.map((step, i) => (
                <li key={i} className="flex gap-2 text-xs text-slate-300">
                  <ArrowRight size={12} className="flex-none text-cyan-300 mt-0.5" />
                  <span>{step}</span>
                </li>
              ))}
            </ul>
          </Card>
        );
      })}
    </div>
  );
}

// =====================================================================
// Helpers
// =====================================================================
function Field({ label, value, onChange, type = "text", testid }) {
  return (
    <div>
      <Label className="text-[10px] uppercase tracking-widest text-slate-400">{label}</Label>
      <Input
        data-testid={testid}
        type={type}
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value)}
        className="bg-slate-900 border-white/10 text-white"
      />
    </div>
  );
}

function Stat({ label, value, color = "text-white" }) {
  return (
    <Card className="p-3 bg-slate-950/60 border-white/10">
      <div className="text-[10px] uppercase tracking-widest text-slate-400 font-mono">{label}</div>
      <div className={`text-xl font-mono mt-1 tabular-nums ${color}`}>{value}</div>
    </Card>
  );
}

function Row({ k, v, color = "text-white" }) {
  return (
    <div className="flex justify-between">
      <span className="text-slate-400">{k}</span>
      <span className={`font-mono ${color}`}>{v}</span>
    </div>
  );
}

function Mini({ label, v, c = "text-white" }) {
  return (
    <div>
      <div className="text-[9px] uppercase tracking-widest text-slate-500">{label}</div>
      <div className={`text-sm font-mono ${c}`}>{v}</div>
    </div>
  );
}
