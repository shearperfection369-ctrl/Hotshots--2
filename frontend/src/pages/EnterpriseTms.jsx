/* eslint-disable */
import React, { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import Topbar from "@/components/Topbar";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Globe, Network, Boxes, ShieldAlert, Activity, Layers, Building2,
  Plus, Trash2, BadgeCheck, RefreshCw, AlertTriangle, Truck, Plane,
  Train, Package, Gauge, MapPinned, FileBarChart, Plug,
} from "lucide-react";

const TABS = [
  { id: "coverage",     label: "RFP Coverage",      icon: BadgeCheck },
  { id: "visibility",   label: "Global Visibility", icon: Globe },
  { id: "routing",      label: "Dynamic Routing",   icon: Network },
  { id: "consolidate",  label: "Consolidation",     icon: Boxes },
  { id: "hazmat",       label: "Hazmat Compliance", icon: ShieldAlert },
  { id: "mode-shop",    label: "Mode + Rate Shop",  icon: Layers },
  { id: "benchmark",    label: "Rate Benchmark",    icon: FileBarChart },
  { id: "kpis",         label: "OTIF · Cost-to-Serve", icon: Gauge },
  { id: "regional",     label: "Regional Network",  icon: Building2 },
  { id: "inbound",      label: "Inbound Shipments", icon: Truck },
  { id: "integrations", label: "Integration Registry", icon: Plug },
];

export default function EnterpriseTms() {
  const [tab, setTab] = useState("coverage");
  return (
    <>
      <Topbar title="Enterprise TMS" />
      <div className="p-6 max-w-7xl mx-auto space-y-6">
        <Card className="hud-surface p-6 border-amber-500/20" data-testid="ent-tms-header">
          <div className="flex items-start justify-between flex-wrap gap-3">
            <div>
              <div className="text-[10px] font-mono uppercase tracking-[0.3em] text-amber-300">
                $52M Enterprise RFP · Fortune-500 capability set
              </div>
              <h1 className="font-display text-4xl font-black mt-2 bg-gradient-to-r from-amber-300 via-cyan-300 to-emerald-300 bg-clip-text text-transparent">
                Enterprise TMS Capabilities
              </h1>
              <p className="text-sm text-slate-400 mt-3 max-w-3xl leading-relaxed">
                Built for global shippers across NAM, EMEA, LATAM, and APAC. Dynamic routing
                that replaces static guides, multi-stop consolidation, full DOT hazmat support,
                weight-break rate shopping, cross-mode optimization, SAP S/4HANA + EWM
                connectivity, and a single global visibility pane.
              </p>
            </div>
            <CoverageBadge />
          </div>
          <div className="flex flex-wrap gap-2 mt-6 border-t border-white/5 pt-5">
            {TABS.map((t) => (
              <button key={t.id} onClick={() => setTab(t.id)}
                data-testid={`ent-tab-${t.id}`}
                className={`px-3 py-1.5 rounded text-xs font-mono uppercase tracking-wider transition flex items-center gap-2 ${
                  tab === t.id
                    ? "bg-amber-500/20 text-amber-200 border border-amber-500/40"
                    : "text-slate-400 hover:text-amber-200 border border-transparent hover:bg-white/5"
                }`}>
                <t.icon size={12} /> {t.label}
              </button>
            ))}
          </div>
        </Card>

        {tab === "coverage" && <CoverageTab />}
        {tab === "visibility" && <VisibilityTab />}
        {tab === "routing" && <RoutingTab />}
        {tab === "consolidate" && <ConsolidationTab />}
        {tab === "hazmat" && <HazmatTab />}
        {tab === "mode-shop" && <ModeRateShopTab />}
        {tab === "benchmark" && <BenchmarkTab />}
        {tab === "kpis" && <KpisTab />}
        {tab === "regional" && <RegionalNetworkTab />}
        {tab === "inbound" && <InboundTab />}
        {tab === "integrations" && <IntegrationsTab />}
      </div>
    </>
  );
}

// ============================ Coverage badge ============================
function CoverageBadge() {
  const [pct, setPct] = useState(null);
  useEffect(() => {
    api.get("/enterprise-tms/coverage")
      .then(({ data }) => setPct(data.coverage_pct))
      .catch(() => {});
  }, []);
  return (
    <div className="text-right">
      <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-slate-400">RFP Coverage</div>
      <div className="font-display text-4xl font-black text-emerald-300 mt-1">
        {pct != null ? `${pct}%` : "—"}
      </div>
      <div className="text-[10px] text-slate-500 font-mono">live + partial weighted</div>
    </div>
  );
}

// ============================ A · COVERAGE MATRIX ============================
function CoverageTab() {
  const [data, setData] = useState(null);
  useEffect(() => {
    api.get("/enterprise-tms/coverage").then(({ data }) => setData(data)).catch(() => toast.error("Load failed"));
  }, []);
  if (!data) return <Empty msg="Loading…" />;
  const groups = { live: [], partial: [], stub: [] };
  data.items.forEach((it) => (groups[it.status] || groups.stub).push(it));
  return (
    <>
      <Card className="hud-surface p-5" data-testid="cov-summary">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Stat label="Total Requirements" value={data.total_requirements} />
          <Stat label="Live" value={data.live} color="emerald" />
          <Stat label="Partial" value={data.partial} color="amber" />
          <Stat label="Stub / Pending" value={data.stub} color="slate" />
        </div>
        <div className="mt-4 h-2 rounded-full bg-white/5 overflow-hidden">
          <div className="h-full bg-gradient-to-r from-emerald-400 via-cyan-400 to-amber-400"
               style={{ width: `${data.coverage_pct}%` }} />
        </div>
        <div className="text-xs text-slate-500 mt-2 font-mono">
          Weighted coverage: {data.coverage_pct}% (live + 0.5 × partial)
        </div>
      </Card>
      {["live", "partial", "stub"].map((status) => (
        <Card key={status} className="hud-surface p-5" data-testid={`cov-${status}`}>
          <h3 className="font-display text-lg font-bold mb-3 flex items-center gap-2">
            <StatusDot status={status} /> {status.toUpperCase()} · {groups[status].length}
          </h3>
          <div className="space-y-1.5">
            {groups[status].map((it, i) => (
              <div key={i} className="px-3 py-2 rounded border bg-white/[0.02] flex items-start justify-between gap-3"
                   style={{ borderColor: "rgba(255,255,255,0.06)" }}>
                <div className="flex-1">
                  <div className="text-sm font-medium">{it.req}</div>
                  <div className="text-[11px] text-slate-500 font-mono mt-0.5">{it.module}</div>
                </div>
                <StatusPill status={it.status} />
              </div>
            ))}
          </div>
        </Card>
      ))}
    </>
  );
}

// ============================ B · GLOBAL VISIBILITY ============================
function VisibilityTab() {
  const [data, setData] = useState(null);
  const load = () => api.get("/enterprise-tms/global-visibility").then(({ data }) => setData(data)).catch(() => toast.error("Load failed"));
  useEffect(() => { load(); }, []);
  if (!data) return <Empty msg="Loading…" />;
  return (
    <>
      <Card className="hud-surface p-5" data-testid="vis-summary">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-display text-lg font-bold flex items-center gap-2"><Globe size={16} className="text-cyan-300" /> Single global pane</h3>
          <Button size="sm" onClick={load} variant="ghost" className="text-cyan-300"><RefreshCw size={12} className="mr-1" /> Refresh</Button>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
          <Stat label="Active Shipments" value={data.total_active_shipments} color="cyan" />
          <Stat label="Outbound" value={data.outbound_count} color="emerald" />
          <Stat label="Inbound" value={data.inbound_count} color="amber" />
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {Object.entries(data.by_region).map(([region, stats]) => (
            <div key={region} className="p-4 rounded border bg-gradient-to-br from-white/[0.03] to-transparent"
                 style={{ borderColor: "rgba(255,255,255,0.08)" }} data-testid={`vis-region-${region}`}>
              <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-2">{region}</div>
              <div className="space-y-1 text-xs">
                <Row label="Outbound" v={stats.outbound} />
                <Row label="Inbound" v={stats.inbound} />
                <Row label="In transit" v={stats.in_transit} accent="cyan" />
                <Row label="At risk" v={stats.at_risk} accent={stats.at_risk ? "red" : "slate"} />
              </div>
            </div>
          ))}
        </div>
      </Card>
      <Card className="hud-surface p-5">
        <h3 className="font-display text-sm font-bold mb-3 text-slate-300">Recent Outbound</h3>
        {data.recent_outbound.length === 0 ? <Empty msg="No active outbound" /> : (
          <div className="space-y-1">
            {data.recent_outbound.slice(0, 10).map((b, i) => (
              <div key={i} className="px-3 py-1.5 rounded border bg-white/[0.02] flex justify-between text-xs"
                   style={{ borderColor: "rgba(255,255,255,0.06)" }}>
                <span><span className="font-mono text-cyan-300 mr-2">{b.booked_id || b.booking_id}</span>{b.origin} → {b.destination}</span>
                <span className="text-slate-500">{b.carrier_name || "—"} · <StatusPill status={b.status} /></span>
              </div>
            ))}
          </div>
        )}
      </Card>
    </>
  );
}

// ============================ C · DYNAMIC ROUTING ============================
function RoutingTab() {
  const [rules, setRules] = useState([]);
  const [decision, setDecision] = useState(null);
  const [decideForm, setDecideForm] = useState({
    origin: "Chicago, IL", destination: "Dallas, TX", equipment: "Dry Van",
    weight_lbs: 22000, pickup_date: new Date().toISOString().slice(0, 10),
    hazmat_un: "",
  });
  const [ruleForm, setRuleForm] = useState({
    name: "", priority: 100, action: "prefer_carrier",
    preferred_carrier_name: "", match_equipment: "",
    match_hazmat: false, match_origin_region: "",
    match_destination_region: "", forced_mode: "",
  });
  const loadRules = () => api.get("/enterprise-tms/routing-rules?active_only=true")
    .then(({ data }) => setRules(data.items || []));
  useEffect(() => { loadRules(); }, []);

  const decide = async () => {
    try {
      const { data } = await api.post("/enterprise-tms/dynamic-route", {
        ...decideForm, weight_lbs: parseFloat(decideForm.weight_lbs) || 0,
        hazmat_un: decideForm.hazmat_un || null,
      });
      setDecision(data);
    } catch (e) { toast.error(e?.response?.data?.detail || "Decision failed"); }
  };
  const createRule = async () => {
    if (!ruleForm.name) return toast.error("Name required");
    try {
      await api.post("/enterprise-tms/routing-rules", {
        ...ruleForm, priority: parseInt(ruleForm.priority) || 100,
        match_hazmat: ruleForm.match_hazmat || null,
      });
      toast.success("Rule added"); setRuleForm({ ...ruleForm, name: "" }); loadRules();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };
  const deleteRule = async (id) => {
    if (!window.confirm("Deactivate rule?")) return;
    await api.delete(`/enterprise-tms/routing-rules/${id}`); loadRules();
  };

  return (
    <>
      <Card className="hud-surface p-5" data-testid="dyn-route-card">
        <h3 className="font-display text-lg font-bold mb-1 flex items-center gap-2">
          <Network size={16} className="text-cyan-300" /> Dynamic Routing Decision
        </h3>
        <p className="text-xs text-slate-500 mb-4">
          Replaces static routing tables. Evaluates contract carriers, spot market,
          mode shifts, hazmat constraints in real time.
        </p>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          <F label="Origin" value={decideForm.origin} onChange={(v) => setDecideForm({ ...decideForm, origin: v })} testId="dyn-origin" />
          <F label="Destination" value={decideForm.destination} onChange={(v) => setDecideForm({ ...decideForm, destination: v })} testId="dyn-dest" />
          <F label="Equipment" value={decideForm.equipment} onChange={(v) => setDecideForm({ ...decideForm, equipment: v })} testId="dyn-eq" />
          <F label="Weight (lbs)" type="number" value={decideForm.weight_lbs} onChange={(v) => setDecideForm({ ...decideForm, weight_lbs: v })} testId="dyn-wt" />
          <F label="Pickup date" type="date" value={decideForm.pickup_date} onChange={(v) => setDecideForm({ ...decideForm, pickup_date: v })} testId="dyn-date" />
          <F label="Hazmat UN# (optional)" value={decideForm.hazmat_un} onChange={(v) => setDecideForm({ ...decideForm, hazmat_un: v })} testId="dyn-un" />
        </div>
        <Button onClick={decide} className="bg-cyan-500 hover:bg-cyan-400 text-black mt-3" data-testid="dyn-decide">
          <Network size={14} className="mr-2" /> Decide Route
        </Button>
        {decision && (
          <div className="mt-5 space-y-2">
            <div className="text-xs text-slate-400 font-mono">{decision.lane} · {decision.weight_lbs} lbs</div>
            {decision.hazmat_constraint && (
              <div className="p-3 rounded border border-amber-500/30 bg-amber-500/5 text-xs text-amber-200 flex items-start gap-2">
                <AlertTriangle size={14} className="mt-0.5" />
                <div>
                  <b>{decision.hazmat_constraint.un}</b> · Class {decision.hazmat_constraint.class}
                  {decision.hazmat_constraint.placard_required ? " · Placard required" : ""}
                  <div className="text-[11px] mt-1 text-slate-400">{decision.hazmat_constraint.constraint}</div>
                </div>
              </div>
            )}
            {decision.options.map((o, i) => {
              const isRec = o === decision.recommendation;
              return (
                <div key={i} className={`p-3 rounded border ${isRec ? "border-emerald-500/40 bg-emerald-500/5" : "border-white/5 bg-white/[0.02]"}`}
                     data-testid={`dyn-opt-${i}`}>
                  <div className="flex items-center justify-between flex-wrap gap-2">
                    <div>
                      <span className="font-bold">{o.mode}</span>
                      {isRec && <span className="ml-2 text-[10px] font-mono uppercase tracking-wider text-emerald-300 border border-emerald-500/30 px-2 py-0.5 rounded">RECOMMENDED</span>}
                      <span className="text-xs text-slate-500 ml-3 font-mono">{o.source}</span>
                    </div>
                    <div className="font-display text-2xl font-bold text-cyan-300">${o.rate_usd}</div>
                  </div>
                  <div className="text-xs text-slate-400 mt-1">{o.rationale}</div>
                  <div className="text-[11px] text-slate-500 font-mono mt-1">Transit: {o.transit_days_est} d</div>
                </div>
              );
            })}
          </div>
        )}
      </Card>

      <Card className="hud-surface p-5" data-testid="rule-form">
        <h3 className="font-display text-lg font-bold mb-3 flex items-center gap-2">
          <Plus size={14} className="text-cyan-400" /> Persist a routing rule
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          <F label="Name *" value={ruleForm.name} onChange={(v) => setRuleForm({ ...ruleForm, name: v })} testId="rule-name" />
          <F label="Priority (1 highest)" type="number" value={ruleForm.priority} onChange={(v) => setRuleForm({ ...ruleForm, priority: v })} testId="rule-priority" />
          <Select label="Action" value={ruleForm.action} onChange={(v) => setRuleForm({ ...ruleForm, action: v })}
                  opts={["prefer_carrier", "force_mode", "block", "escalate"]} testId="rule-action" />
          <F label="Equipment match" value={ruleForm.match_equipment} onChange={(v) => setRuleForm({ ...ruleForm, match_equipment: v })} testId="rule-eq" />
          <F label="Origin region" value={ruleForm.match_origin_region} onChange={(v) => setRuleForm({ ...ruleForm, match_origin_region: v })} testId="rule-orig" />
          <F label="Destination region" value={ruleForm.match_destination_region} onChange={(v) => setRuleForm({ ...ruleForm, match_destination_region: v })} testId="rule-dest" />
          <F label="Preferred carrier" value={ruleForm.preferred_carrier_name} onChange={(v) => setRuleForm({ ...ruleForm, preferred_carrier_name: v })} testId="rule-carrier" />
          <F label="Forced mode (if action=force_mode)" value={ruleForm.forced_mode} onChange={(v) => setRuleForm({ ...ruleForm, forced_mode: v })} testId="rule-mode" />
          <label className="flex items-center gap-2 text-xs text-slate-300 mt-6">
            <input type="checkbox" checked={ruleForm.match_hazmat} onChange={(e) => setRuleForm({ ...ruleForm, match_hazmat: e.target.checked })} />
            Match hazmat-only
          </label>
        </div>
        <Button onClick={createRule} className="bg-cyan-500 hover:bg-cyan-400 text-black mt-3" data-testid="rule-create">
          <Plus size={14} className="mr-2" /> Save rule
        </Button>
      </Card>

      <Card className="hud-surface p-5" data-testid="rule-list">
        <h3 className="font-display text-sm font-bold mb-3">Active routing rules · {rules.length}</h3>
        {rules.length === 0 ? <Empty msg="No active rules — use defaults from the decision engine." /> : (
          <div className="space-y-1.5">
            {rules.map((r) => (
              <div key={r.rule_id} className="px-3 py-2 rounded border bg-white/[0.02] flex justify-between items-center"
                   style={{ borderColor: "rgba(255,255,255,0.06)" }}>
                <div>
                  <div className="text-sm"><span className="font-mono text-cyan-300 text-[11px] mr-2">P{r.priority}</span>{r.name}</div>
                  <div className="text-[11px] text-slate-500 font-mono">
                    {r.action}{r.preferred_carrier_name ? ` → ${r.preferred_carrier_name}` : ""}{r.forced_mode ? ` → ${r.forced_mode}` : ""}
                  </div>
                </div>
                <Button size="sm" variant="ghost" onClick={() => deleteRule(r.rule_id)} className="text-red-400 hover:bg-red-500/10 h-7 w-7 p-0">
                  <Trash2 size={12} />
                </Button>
              </div>
            ))}
          </div>
        )}
      </Card>
    </>
  );
}

// ============================ D · CONSOLIDATION ============================
function ConsolidationTab() {
  const [groups, setGroups] = useState([]);
  const [result, setResult] = useState(null);
  const [groupForm, setGroupForm] = useState({
    name: "", lane_origin: "", lane_destination: "",
    pickup_window_days: "Mon,Wed,Fri", max_weight_lbs: 44000,
    max_cube_ft: 3500, target_savings_pct: 15,
  });
  const [candidates, setCandidates] = useState([
    { origin: "Chicago, IL", destination: "Atlanta, GA", weight_lbs: 8000, cube_ft: 600 },
    { origin: "Chicago, IL", destination: "Atlanta, GA", weight_lbs: 12000, cube_ft: 900 },
    { origin: "Chicago, IL", destination: "Atlanta, GA", weight_lbs: 14000, cube_ft: 1100 },
  ]);
  const load = () => api.get("/enterprise-tms/consolidation-groups").then(({ data }) => setGroups(data.items || []));
  useEffect(() => { load(); }, []);

  const runConsolidate = async () => {
    try {
      const { data } = await api.post("/enterprise-tms/consolidate", {
        candidates, max_weight_lbs: 44000, max_cube_ft: 3500, max_pickup_window_hours: 48,
      });
      setResult(data);
    } catch (e) { toast.error("Consolidate failed"); }
  };
  const addCandidate = () => setCandidates([...candidates, { origin: "", destination: "", weight_lbs: 0, cube_ft: 0 }]);
  const updateCandidate = (i, k, v) => {
    const next = [...candidates]; next[i] = { ...next[i], [k]: v }; setCandidates(next);
  };
  const removeCandidate = (i) => setCandidates(candidates.filter((_, x) => x !== i));

  const createGroup = async () => {
    if (!groupForm.name || !groupForm.lane_origin) return toast.error("Name + origin required");
    try {
      await api.post("/enterprise-tms/consolidation-groups", {
        ...groupForm,
        pickup_window_days: groupForm.pickup_window_days.split(",").map((s) => s.trim()).filter(Boolean),
        max_weight_lbs: parseFloat(groupForm.max_weight_lbs) || 44000,
        max_cube_ft: parseFloat(groupForm.max_cube_ft) || 3500,
        target_savings_pct: parseFloat(groupForm.target_savings_pct) || 15,
      });
      toast.success("Group saved"); setGroupForm({ ...groupForm, name: "" }); load();
    } catch (e) { toast.error("Failed"); }
  };
  const deleteGroup = async (id) => {
    if (!window.confirm("Deactivate?")) return;
    await api.delete(`/enterprise-tms/consolidation-groups/${id}`); load();
  };

  return (
    <>
      <Card className="hud-surface p-5" data-testid="consol-opt">
        <h3 className="font-display text-lg font-bold mb-1 flex items-center gap-2">
          <Boxes size={16} className="text-cyan-300" /> Multi-stop Consolidation Optimizer
        </h3>
        <p className="text-xs text-slate-500 mb-4">
          Greedy grouping by lane + window. Splits over-capacity loads automatically.
        </p>
        <div className="space-y-2 mb-3">
          {candidates.map((c, i) => (
            <div key={i} className="grid grid-cols-2 md:grid-cols-5 gap-2 items-end">
              <F label="Origin" value={c.origin} onChange={(v) => updateCandidate(i, "origin", v)} />
              <F label="Destination" value={c.destination} onChange={(v) => updateCandidate(i, "destination", v)} />
              <F label="Weight" type="number" value={c.weight_lbs} onChange={(v) => updateCandidate(i, "weight_lbs", parseFloat(v) || 0)} />
              <F label="Cube ft" type="number" value={c.cube_ft} onChange={(v) => updateCandidate(i, "cube_ft", parseFloat(v) || 0)} />
              <Button size="sm" variant="ghost" onClick={() => removeCandidate(i)} className="text-red-400 h-9"><Trash2 size={12} /></Button>
            </div>
          ))}
        </div>
        <div className="flex gap-2">
          <Button size="sm" variant="ghost" onClick={addCandidate} className="text-cyan-300"><Plus size={12} className="mr-1" /> Add shipment</Button>
          <Button onClick={runConsolidate} className="bg-cyan-500 hover:bg-cyan-400 text-black" data-testid="consol-run">
            <Boxes size={14} className="mr-2" /> Optimize
          </Button>
        </div>
        {result && (
          <div className="mt-5 p-4 rounded border border-emerald-500/30 bg-emerald-500/5">
            <div className="grid grid-cols-3 gap-3 mb-3">
              <Stat label="Input shipments" value={result.input_shipments} />
              <Stat label="Consolidated loads" value={result.consolidated_loads} color="cyan" />
              <Stat label="Truck reduction" value={`${result.savings_pct}%`} color="emerald" />
            </div>
            <div className="text-xs text-slate-300 space-y-1">
              {result.loads.map((l, i) => (
                <div key={i} className="px-2 py-1 rounded bg-white/[0.03]">
                  <span className="font-mono text-cyan-300 mr-2">Load {i + 1}{l.split ? ` (${l.split})` : ""}</span>
                  {l.origin} → {l.destination} · {l.total_weight_lbs.toFixed(0)} lbs · {l.total_cube_ft.toFixed(0)} ft³ · {l.shipments.length} shipments
                </div>
              ))}
            </div>
          </div>
        )}
      </Card>

      <Card className="hud-surface p-5" data-testid="consol-group-form">
        <h3 className="font-display text-lg font-bold mb-3 flex items-center gap-2">
          <Plus size={14} className="text-cyan-400" /> Save a recurring consolidation group
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          <F label="Name *" value={groupForm.name} onChange={(v) => setGroupForm({ ...groupForm, name: v })} testId="cg-name" />
          <F label="Lane origin" value={groupForm.lane_origin} onChange={(v) => setGroupForm({ ...groupForm, lane_origin: v })} testId="cg-orig" />
          <F label="Lane destination" value={groupForm.lane_destination} onChange={(v) => setGroupForm({ ...groupForm, lane_destination: v })} testId="cg-dest" />
          <F label="Pickup days (CSV)" value={groupForm.pickup_window_days} onChange={(v) => setGroupForm({ ...groupForm, pickup_window_days: v })} />
          <F label="Max weight (lbs)" type="number" value={groupForm.max_weight_lbs} onChange={(v) => setGroupForm({ ...groupForm, max_weight_lbs: v })} />
          <F label="Target savings %" type="number" value={groupForm.target_savings_pct} onChange={(v) => setGroupForm({ ...groupForm, target_savings_pct: v })} />
        </div>
        <Button onClick={createGroup} className="bg-cyan-500 hover:bg-cyan-400 text-black mt-3" data-testid="cg-create">
          <Plus size={14} className="mr-2" /> Save group
        </Button>
      </Card>

      <Card className="hud-surface p-5">
        <h3 className="font-display text-sm font-bold mb-3">Saved groups · {groups.length}</h3>
        {groups.length === 0 ? <Empty msg="No saved consolidation patterns yet." /> : (
          <div className="space-y-1.5">
            {groups.filter((g) => g.active !== false).map((g) => (
              <div key={g.group_id} className="px-3 py-2 rounded border bg-white/[0.02] flex justify-between items-center"
                   style={{ borderColor: "rgba(255,255,255,0.06)" }}>
                <div>
                  <div className="text-sm font-medium">{g.name}</div>
                  <div className="text-[11px] text-slate-500 font-mono">
                    {g.lane_origin} → {g.lane_destination} · {(g.pickup_window_days || []).join(", ")} · target {g.target_savings_pct}%
                  </div>
                </div>
                <Button size="sm" variant="ghost" onClick={() => deleteGroup(g.group_id)} className="text-red-400 h-7 w-7 p-0">
                  <Trash2 size={12} />
                </Button>
              </div>
            ))}
          </div>
        )}
      </Card>
    </>
  );
}

// ============================ E · HAZMAT ============================
function HazmatTab() {
  const [un, setUn] = useState("UN1203");
  const [result, setResult] = useState(null);
  const [profiles, setProfiles] = useState([]);
  const [catalog, setCatalog] = useState([]);
  const [pForm, setPForm] = useState({
    customer_id: "", customer_name: "", un_numbers: "",
    emergency_contact_name: "", emergency_contact_phone: "",
    emergency_response_provider: "CHEMTREC", chemtrec_contract: "",
  });
  const load = () => Promise.all([
    api.get("/enterprise-tms/hazmat-profiles").then(({ data }) => setProfiles(data.items || [])),
    api.get("/enterprise-tms/hazmat-catalog").then(({ data }) => setCatalog(data.items || [])),
  ]);
  useEffect(() => { load(); }, []);

  const lookup = async () => {
    try { const { data } = await api.get(`/enterprise-tms/hazmat/${un}`); setResult(data); }
    catch { toast.error("Lookup failed"); }
  };
  const createProfile = async () => {
    if (!pForm.customer_id || !pForm.emergency_contact_name) return toast.error("Customer ID + emergency contact required");
    try {
      await api.post("/enterprise-tms/hazmat-profiles", {
        ...pForm,
        un_numbers: pForm.un_numbers.split(",").map((s) => s.trim()).filter(Boolean),
      });
      toast.success("Profile saved"); setPForm({ ...pForm, customer_id: "", un_numbers: "" }); load();
    } catch (e) { toast.error("Failed"); }
  };

  return (
    <>
      <Card className="hud-surface p-5" data-testid="hz-lookup">
        <h3 className="font-display text-lg font-bold mb-3 flex items-center gap-2">
          <ShieldAlert size={16} className="text-amber-300" /> Hazmat UN# Validator
        </h3>
        <div className="flex gap-2 items-end">
          <div className="flex-1 max-w-xs">
            <Label className="text-[10px] font-mono uppercase tracking-[0.15em] text-slate-400 mb-1.5 block">UN Number</Label>
            <Input value={un} onChange={(e) => setUn(e.target.value)} placeholder="e.g. UN1203"
                   className="bg-[#0B1320] border-white/10 text-white" data-testid="hz-un" />
          </div>
          <Button onClick={lookup} className="bg-amber-500 hover:bg-amber-400 text-black" data-testid="hz-lookup-btn">
            <ShieldAlert size={14} className="mr-2" /> Validate
          </Button>
        </div>
        {result && (
          <div className="mt-4 p-4 rounded border border-amber-500/20 bg-amber-500/5">
            {result.known ? (
              <>
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <div>
                    <div className="font-display text-xl font-bold">{result.proper_shipping_name}</div>
                    <div className="text-xs text-slate-400 font-mono">{result.un_number} · Class {result.hazard_class} · PG {result.packing_group}</div>
                  </div>
                  <div className="text-right">
                    <div className="text-[10px] font-mono uppercase tracking-wider text-amber-300">{result.label}</div>
                    {result.placard_required && <div className="text-[10px] font-mono text-red-300 mt-1">PLACARD REQUIRED</div>}
                  </div>
                </div>
                <ul className="mt-3 text-xs text-slate-300 list-disc list-inside space-y-1">
                  {(result.compliance_notes || []).map((n, i) => <li key={i}>{n}</li>)}
                </ul>
              </>
            ) : (
              <div className="text-amber-200 text-sm flex items-start gap-2">
                <AlertTriangle size={14} className="mt-0.5" /> {result.message}
              </div>
            )}
          </div>
        )}
        <div className="text-xs text-slate-500 mt-3 font-mono">Built-in catalog: {catalog.length} commodities · 49 CFR aligned</div>
      </Card>

      <Card className="hud-surface p-5" data-testid="hz-profile-form">
        <h3 className="font-display text-lg font-bold mb-3 flex items-center gap-2">
          <Plus size={14} className="text-cyan-400" /> Customer Hazmat Profile
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          <F label="Customer ID *" value={pForm.customer_id} onChange={(v) => setPForm({ ...pForm, customer_id: v })} testId="hz-cust" />
          <F label="Customer Name" value={pForm.customer_name} onChange={(v) => setPForm({ ...pForm, customer_name: v })} />
          <F label="UN#s shipped (CSV)" value={pForm.un_numbers} onChange={(v) => setPForm({ ...pForm, un_numbers: v })} />
          <F label="Emergency contact *" value={pForm.emergency_contact_name} onChange={(v) => setPForm({ ...pForm, emergency_contact_name: v })} testId="hz-emerg" />
          <F label="Emergency phone *" value={pForm.emergency_contact_phone} onChange={(v) => setPForm({ ...pForm, emergency_contact_phone: v })} />
          <F label="Provider (CHEMTREC etc)" value={pForm.emergency_response_provider} onChange={(v) => setPForm({ ...pForm, emergency_response_provider: v })} />
          <F label="CHEMTREC contract #" value={pForm.chemtrec_contract} onChange={(v) => setPForm({ ...pForm, chemtrec_contract: v })} />
        </div>
        <Button onClick={createProfile} className="bg-cyan-500 hover:bg-cyan-400 text-black mt-3" data-testid="hz-create-profile">
          <Plus size={14} className="mr-2" /> Save profile
        </Button>
      </Card>

      <Card className="hud-surface p-5">
        <h3 className="font-display text-sm font-bold mb-3">Hazmat profiles · {profiles.length}</h3>
        {profiles.length === 0 ? <Empty msg="No customer hazmat profiles yet." /> : (
          <div className="space-y-1.5">
            {profiles.filter((p) => p.active !== false).map((p) => (
              <div key={p.profile_id} className="px-3 py-2 rounded border bg-white/[0.02]"
                   style={{ borderColor: "rgba(255,255,255,0.06)" }}>
                <div className="flex items-center justify-between">
                  <div className="text-sm"><span className="font-mono text-cyan-300 mr-2">{p.customer_id}</span>{p.customer_name || "—"}</div>
                  <div className="text-[11px] text-emerald-300 font-mono">{p.compliance_score}% compliant</div>
                </div>
                <div className="text-[11px] text-slate-500 mt-1">
                  {(p.un_numbers || []).join(", ") || "no UN#s"} · {p.emergency_response_provider} · {p.emergency_contact_phone}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </>
  );
}

// ============================ F · MODE + RATE SHOP ============================
function ModeRateShopTab() {
  const [form, setForm] = useState({
    origin: "Los Angeles, CA", destination: "Newark, NJ",
    weight_lbs: 4500, pieces: 8, equipment: "Dry Van", hazmat_un: "",
  });
  const [data, setData] = useState(null);
  const run = async () => {
    try {
      const { data } = await api.post("/enterprise-tms/mode-rate-shop", {
        ...form, weight_lbs: parseFloat(form.weight_lbs) || 0,
        pieces: parseInt(form.pieces) || 1, hazmat_un: form.hazmat_un || null,
      });
      setData(data);
    } catch { toast.error("Quote failed"); }
  };
  const icon = (mode) => mode.includes("Parcel") ? Package : mode.includes("LTL") ? Truck :
                          mode.includes("Truckload") ? Truck : mode.includes("Intermodal") ? Train : Plane;
  return (
    <Card className="hud-surface p-5" data-testid="mode-shop-card">
      <h3 className="font-display text-lg font-bold mb-1 flex items-center gap-2">
        <Layers size={16} className="text-cyan-300" /> Cross-mode + Weight-break Rate Shop
      </h3>
      <p className="text-xs text-slate-500 mb-4">
        Quotes parcel · LTL · TL · intermodal · air for the same lane. Recommends the cheapest viable mode.
      </p>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <F label="Origin" value={form.origin} onChange={(v) => setForm({ ...form, origin: v })} testId="ms-orig" />
        <F label="Destination" value={form.destination} onChange={(v) => setForm({ ...form, destination: v })} testId="ms-dest" />
        <F label="Weight (lbs)" type="number" value={form.weight_lbs} onChange={(v) => setForm({ ...form, weight_lbs: v })} testId="ms-wt" />
        <F label="Pieces" type="number" value={form.pieces} onChange={(v) => setForm({ ...form, pieces: v })} />
        <F label="Equipment" value={form.equipment} onChange={(v) => setForm({ ...form, equipment: v })} />
        <F label="Hazmat UN# (opt)" value={form.hazmat_un} onChange={(v) => setForm({ ...form, hazmat_un: v })} />
      </div>
      <Button onClick={run} className="bg-cyan-500 hover:bg-cyan-400 text-black mt-3" data-testid="ms-run">
        <Layers size={14} className="mr-2" /> Shop modes
      </Button>
      {data && (
        <div className="mt-5">
          <div className="text-xs text-slate-400 font-mono mb-3">{data.lane} · {data.miles} mi · {data.weight_lbs} lbs</div>
          {data.hazmat && (
            <div className="p-2 rounded border border-amber-500/30 bg-amber-500/5 text-[11px] text-amber-200 mb-3">
              Hazmat {data.hazmat.un} · Class {data.hazmat.class} · +${data.hazmat.surcharge_usd} surcharge added to each option
            </div>
          )}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {data.options.map((o, i) => {
              const Icon = icon(o.mode);
              return (
                <div key={i} className="p-4 rounded border bg-white/[0.02]"
                     style={{ borderColor: "rgba(255,255,255,0.08)" }} data-testid={`ms-opt-${i}`}>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Icon size={16} className="text-cyan-300" />
                      <span className="font-bold">{o.mode}</span>
                    </div>
                    <div className="flex gap-1">
                      {(o.badges || []).map((b) => (
                        <span key={b} className={`text-[9px] font-mono px-1.5 py-0.5 rounded border ${b === "CHEAPEST" ? "border-emerald-500/40 text-emerald-300" : "border-cyan-500/40 text-cyan-300"}`}>{b}</span>
                      ))}
                    </div>
                  </div>
                  <div className="font-display text-3xl font-black text-cyan-300 mt-2">${o.rate_usd.toLocaleString()}</div>
                  <div className="text-xs text-slate-400 mt-1">{o.rate_basis}</div>
                  <div className="text-[11px] text-slate-500 font-mono mt-2">Transit: {o.transit_days} d · {o.carriers.slice(0, 2).join(" / ")}</div>
                  <div className="text-[11px] text-slate-500 mt-1 italic">{o.notes}</div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </Card>
  );
}

// ============================ G · RATE BENCHMARK ============================
function BenchmarkTab() {
  const [form, setForm] = useState({ origin_state: "IL", destination_state: "TX", equipment: "Dry Van" });
  const [data, setData] = useState(null);
  const run = async () => {
    try {
      const { data } = await api.get("/enterprise-tms/rate-benchmark", { params: form });
      setData(data);
    } catch { toast.error("Failed"); }
  };
  return (
    <Card className="hud-surface p-5" data-testid="bench-card">
      <h3 className="font-display text-lg font-bold mb-1 flex items-center gap-2">
        <FileBarChart size={16} className="text-cyan-300" /> Automated Rate Benchmark
      </h3>
      <p className="text-xs text-slate-500 mb-4">
        Compare your historical lane rates vs network average vs DAT spot proxy. Surfaces over-/under-pay bookings.
      </p>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <F label="Origin state" value={form.origin_state} onChange={(v) => setForm({ ...form, origin_state: v.toUpperCase() })} testId="bm-orig" />
        <F label="Destination state" value={form.destination_state} onChange={(v) => setForm({ ...form, destination_state: v.toUpperCase() })} testId="bm-dest" />
        <F label="Equipment" value={form.equipment} onChange={(v) => setForm({ ...form, equipment: v })} />
      </div>
      <Button onClick={run} className="bg-cyan-500 hover:bg-cyan-400 text-black mt-3" data-testid="bm-run">
        <FileBarChart size={14} className="mr-2" /> Benchmark
      </Button>
      {data && (
        <div className="mt-5">
          {data.samples === 0 ? (
            <div className="text-slate-400 text-sm">{data.note}</div>
          ) : (
            <>
              <div className="flex items-center justify-between mb-3">
                <div className="text-sm font-mono text-slate-300">{data.lane} · {data.samples} bookings · {data.window_days} d</div>
                <span className={`text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded border ${
                  data.verdict === "ALIGNED" ? "border-emerald-500/40 text-emerald-300" :
                  data.verdict === "OVER" ? "border-red-500/40 text-red-300" :
                  "border-amber-500/40 text-amber-300"
                }`}>{data.verdict}</span>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <Stat label="P25" value={`$${data.p25_usd}`} />
                <Stat label="Median" value={`$${data.median_usd}`} color="cyan" />
                <Stat label="P75" value={`$${data.p75_usd}`} />
                <Stat label="DAT spot proxy" value={`$${data.dat_spot_proxy_usd}`} color="amber" />
              </div>
              <div className="text-xs text-slate-400 mt-3 font-mono">vs spot: {data.vs_spot_pct > 0 ? "+" : ""}{data.vs_spot_pct}%</div>
            </>
          )}
        </div>
      )}
    </Card>
  );
}

// ============================ H · KPIs ============================
function KpisTab() {
  const [data, setData] = useState(null);
  useEffect(() => {
    api.get("/enterprise-tms/kpis/global").then(({ data }) => setData(data)).catch(() => {});
  }, []);
  if (!data) return <Empty msg="Loading…" />;
  return (
    <Card className="hud-surface p-5" data-testid="kpis-card">
      <h3 className="font-display text-lg font-bold mb-1 flex items-center gap-2">
        <Gauge size={16} className="text-cyan-300" /> OTIF + Cost-to-Serve (Global, {data.window_days}d)
      </h3>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-4">
        <Stat label="Shipments" value={data.shipments_total} />
        <Stat label="Delivered" value={data.shipments_delivered} color="cyan" />
        <Stat label="OTIF %" value={`${data.otif_pct}%`} color="emerald" />
        <Stat label="On-time %" value={`${data.on_time_pct}%`} color="emerald" />
        <Stat label="In-full %" value={`${data.in_full_pct}%`} color="cyan" />
        <Stat label="Cost-to-serve" value={`${data.cost_to_serve_pct}%`} color="amber" />
        <Stat label="Carrier spend" value={`$${(data.total_carrier_spend_usd || 0).toLocaleString()}`} />
        <Stat label="Premium freight %" value={`${data.premium_freight_pct}%`} color="amber" />
      </div>
      <div className="text-[11px] text-slate-500 mt-4 font-mono">
        Active regions: {data.regions.join(" · ")}
      </div>
    </Card>
  );
}

// ============================ I · REGIONAL NETWORK ============================
function RegionalNetworkTab() {
  const [data, setData] = useState(null);
  useEffect(() => {
    api.get("/enterprise-tms/regional-network").then(({ data }) => setData(data));
  }, []);
  if (!data) return <Empty msg="Loading…" />;
  return (
    <>
      {data.regions.map((r) => (
        <Card key={r.region} className="hud-surface p-5" data-testid={`region-${r.region}`}>
          <h3 className="font-display text-lg font-bold mb-3 flex items-center gap-2">
            <Building2 size={16} className="text-cyan-300" /> {r.region} · {r.carrier_count} carriers
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {r.carriers.map((c, i) => (
              <div key={i} className="px-3 py-2 rounded border bg-white/[0.02]"
                   style={{ borderColor: "rgba(255,255,255,0.06)" }}>
                <div className="text-sm font-medium">{c.name}</div>
                <div className="text-[11px] text-slate-500 font-mono mt-0.5">{c.modes} · {c.coverage}</div>
              </div>
            ))}
          </div>
        </Card>
      ))}
    </>
  );
}

// ============================ J · INBOUND ============================
function InboundTab() {
  const [items, setItems] = useState([]);
  const [form, setForm] = useState({
    supplier_name: "", supplier_country: "USA", po_number: "",
    destination_dc: "", expected_arrival: new Date().toISOString().slice(0, 10),
    mode: "TL", weight_lbs: "", commodity: "", carrier_name: "", tracking_number: "",
  });
  const load = () => api.get("/enterprise-tms/inbound").then(({ data }) => setItems(data.items || []));
  useEffect(() => { load(); }, []);
  const create = async () => {
    if (!form.supplier_name || !form.destination_dc) return toast.error("Supplier + DC required");
    try {
      await api.post("/enterprise-tms/inbound", {
        ...form, weight_lbs: parseFloat(form.weight_lbs) || null,
      });
      toast.success("Inbound created"); setForm({ ...form, supplier_name: "", po_number: "", tracking_number: "" }); load();
    } catch { toast.error("Failed"); }
  };
  const updateStatus = async (id, status) => {
    await api.post(`/enterprise-tms/inbound/${id}/status`, { status });
    load();
  };
  return (
    <>
      <Card className="hud-surface p-5" data-testid="inbound-form">
        <h3 className="font-display text-lg font-bold mb-3 flex items-center gap-2">
          <Plus size={14} className="text-cyan-400" /> Schedule inbound shipment
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          <F label="Supplier *" value={form.supplier_name} onChange={(v) => setForm({ ...form, supplier_name: v })} testId="ib-supplier" />
          <F label="Country" value={form.supplier_country} onChange={(v) => setForm({ ...form, supplier_country: v })} />
          <F label="PO #" value={form.po_number} onChange={(v) => setForm({ ...form, po_number: v })} />
          <F label="Destination DC *" value={form.destination_dc} onChange={(v) => setForm({ ...form, destination_dc: v })} testId="ib-dc" />
          <F label="Expected arrival" type="date" value={form.expected_arrival} onChange={(v) => setForm({ ...form, expected_arrival: v })} />
          <Select label="Mode" value={form.mode} onChange={(v) => setForm({ ...form, mode: v })} opts={["TL", "LTL", "Ocean", "Air", "Parcel", "Intermodal"]} />
          <F label="Weight (lbs)" type="number" value={form.weight_lbs} onChange={(v) => setForm({ ...form, weight_lbs: v })} />
          <F label="Commodity" value={form.commodity} onChange={(v) => setForm({ ...form, commodity: v })} />
          <F label="Carrier" value={form.carrier_name} onChange={(v) => setForm({ ...form, carrier_name: v })} />
        </div>
        <Button onClick={create} className="bg-cyan-500 hover:bg-cyan-400 text-black mt-3" data-testid="ib-create">
          <Plus size={14} className="mr-2" /> Schedule
        </Button>
      </Card>
      <Card className="hud-surface p-5">
        <h3 className="font-display text-sm font-bold mb-3">Active inbound · {items.length}</h3>
        {items.length === 0 ? <Empty msg="No inbound shipments scheduled." /> : (
          <div className="space-y-1.5">
            {items.map((s) => (
              <div key={s.inbound_id} className="px-3 py-2 rounded border bg-white/[0.02] flex justify-between items-center flex-wrap gap-2"
                   style={{ borderColor: "rgba(255,255,255,0.06)" }}>
                <div>
                  <div className="text-sm"><span className="font-mono text-cyan-300 text-[11px] mr-2">{s.inbound_id}</span>{s.supplier_name} → {s.destination_dc}</div>
                  <div className="text-[11px] text-slate-500 font-mono">{s.mode} · ETA {s.expected_arrival} · {s.commodity || "—"}</div>
                </div>
                <div className="flex items-center gap-2">
                  <StatusPill status={s.status} />
                  <select value={s.status} onChange={(e) => updateStatus(s.inbound_id, e.target.value)}
                          className="text-xs px-2 py-1 rounded border bg-[#0B1320] text-white border-white/10">
                    {["booked", "departed", "in_transit", "customs", "arrived", "received"].map((o) => (
                      <option key={o} value={o}>{o}</option>
                    ))}
                  </select>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </>
  );
}

// ============================ K · INTEGRATIONS ============================
function IntegrationsTab() {
  const [data, setData] = useState(null);
  useEffect(() => {
    api.get("/enterprise-tms/integration-registry").then(({ data }) => setData(data));
  }, []);
  if (!data) return <Empty msg="Loading…" />;
  return (
    <Card className="hud-surface p-5" data-testid="int-reg-card">
      <h3 className="font-display text-lg font-bold mb-3 flex items-center gap-2">
        <Plug size={16} className="text-cyan-300" /> Integration Registry · {data.total} connectors
      </h3>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-4">
        <Stat label="Live" value={data.live} color="emerald" />
        <Stat label="Stubs" value={data.stub} color="amber" />
      </div>
      <div className="space-y-2">
        {data.items.map((i) => (
          <div key={i.slug} className="px-3 py-3 rounded border bg-white/[0.02]"
               style={{ borderColor: "rgba(255,255,255,0.06)" }} data-testid={`int-${i.slug}`}>
            <div className="flex items-center justify-between flex-wrap gap-2">
              <div>
                <div className="text-sm font-bold">{i.name}</div>
                <div className="text-[11px] text-slate-500 font-mono">{i.category}</div>
              </div>
              <StatusPill status={i.status.replace("live_partial", "partial")} />
            </div>
            <div className="text-xs text-slate-400 mt-2">{i.value}</div>
            <div className="text-[11px] text-slate-500 mt-1 font-mono">Needs: {i.needs.join(" · ")}</div>
          </div>
        ))}
      </div>
    </Card>
  );
}

// ============================ shared bits ============================
function F({ label, value, onChange, type = "text", testId }) {
  return (
    <div>
      <Label className="text-[10px] font-mono uppercase tracking-[0.15em] text-slate-400 mb-1.5 block">{label}</Label>
      <Input type={type} value={value} onChange={(e) => onChange(e.target.value)}
             data-testid={testId} className="bg-[#0B1320] border-white/10 text-white" />
    </div>
  );
}
function Select({ label, value, onChange, opts, testId }) {
  return (
    <div>
      <Label className="text-[10px] font-mono uppercase tracking-[0.15em] text-slate-400 mb-1.5 block">{label}</Label>
      <select value={value} onChange={(e) => onChange(e.target.value)}
              className="w-full px-3 py-2 rounded border bg-[#0B1320] text-white text-sm border-white/10"
              data-testid={testId}>
        {opts.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    </div>
  );
}
function Stat({ label, value, color = "cyan" }) {
  const cls = color === "emerald" ? "text-emerald-300" : color === "amber" ? "text-amber-300" :
              color === "red" ? "text-red-300" : color === "slate" ? "text-slate-300" : "text-cyan-300";
  return (
    <div className="p-3 rounded border bg-white/[0.02]" style={{ borderColor: "rgba(255,255,255,0.06)" }}>
      <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-slate-400">{label}</div>
      <div className={`font-display text-xl font-bold mt-1 ${cls}`}>{value}</div>
    </div>
  );
}
function Row({ label, v, accent = "slate" }) {
  const cls = accent === "cyan" ? "text-cyan-300" : accent === "red" ? "text-red-300" :
              accent === "emerald" ? "text-emerald-300" : "text-slate-300";
  return (
    <div className="flex justify-between">
      <span className="text-slate-500">{label}</span>
      <span className={`font-mono font-bold ${cls}`}>{v}</span>
    </div>
  );
}
function StatusDot({ status }) {
  const cls = status === "live" ? "bg-emerald-400" : status === "partial" ? "bg-amber-400" : "bg-slate-500";
  return <span className={`inline-block w-2 h-2 rounded-full ${cls}`} />;
}
function StatusPill({ status }) {
  const s = (status || "").toLowerCase();
  const cls = s === "live" || s === "delivered" || s === "received" ? "bg-emerald-500/15 text-emerald-300 border-emerald-500/30" :
              s === "partial" || s === "in_transit" || s === "departed" || s === "booked" ? "bg-cyan-500/15 text-cyan-300 border-cyan-500/30" :
              s === "stub" || s === "queued" ? "bg-amber-500/15 text-amber-300 border-amber-500/30" :
              s === "cancelled" || s === "blocked" ? "bg-red-500/15 text-red-300 border-red-500/30" :
              "bg-slate-500/15 text-slate-300 border-slate-500/30";
  return <span className={`px-2 py-0.5 rounded text-[10px] font-mono uppercase tracking-wider border ${cls}`}>{status || "—"}</span>;
}
function Empty({ msg }) { return <Card className="hud-surface p-8 text-center text-slate-500 text-sm italic">{msg}</Card>; }
