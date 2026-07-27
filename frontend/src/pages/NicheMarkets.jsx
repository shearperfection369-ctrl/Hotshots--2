import React, { useCallback, useEffect, useState } from "react";
import { Crosshair, Loader2, X, Sparkles, Send, Copy, Plus, Trash2, FlaskConical, Target as TargetIcon, TrendingUp, Landmark, ShieldCheck, AlarmClock, Truck, Wrench, BellRing, Link2, RotateCcw } from "lucide-react";
import { toast } from "sonner";
import { api } from "../lib/api";

const errTxt = (e) => (typeof e?.response?.data?.detail === "string" ? e.response.data.detail : "Something went wrong");
const money = (n) => `$${Math.round(n || 0).toLocaleString()}`;
const STAGE_META = {
  target: ["PROSPECT", "#94A3B8"], researched: ["RESEARCHED", "#22D3EE"], contacted: ["PITCHING", "#A78BFA"],
  meeting: ["MEETING", "#F59E0B"], pilot_proposed: ["PILOT PROPOSED", "#F472B6"], pilot: ["PILOT LIVE", "#FB923C"], contracted: ["SIGNED", "#10B981"],
};
const OUTCOME_META = { active: ["ACTIVE", "#34D399"], maybe: ["MAYBE", "#FBBF24"], no: ["NO — DEPRI", "#F87171"] };
const LINK_STATUS_META = { in_talks: ["IN TALKS", "#94A3B8"], rate_agreed: ["RATE AGREED", "#FBBF24"], signed: ["SIGNED", "#22D3EE"], live: ["LIVE", "#10B981"] };
const warmthColor = (w) => (w >= 8 ? "#10B981" : w >= 5 ? "#FBBF24" : "#94A3B8");

const FEAT_META = { done: "#34D399", in_progress: "#FBBF24", missing: "#F87171" };
const TIER_LABEL = { 1: "TIER 1 · MANUFACTURING & INDUSTRIAL", 2: "TIER 2 · SPECIALTY LOGISTICS", 3: "TIER 3 · NICHE VERTICALS" };
const daysTo = (d) => Math.ceil((new Date(d) - new Date()) / 86400000);

export default function NicheMarkets() {
  const [pb, setPb] = useState(null);
  const [dash, setDash] = useState(null);
  const [targets, setTargets] = useState([]);
  const [vertFilter, setVertFilter] = useState("");
  const [detail, setDetail] = useState(null);

  const load = useCallback(async () => {
    try {
      const [p, d, t] = await Promise.all([
        api.get("/niche-markets/playbook"), api.get("/niche-markets/dashboard"), api.get("/niche-markets/targets"),
      ]);
      setPb(p.data); setDash(d.data); setTargets(t.data.targets);
    } catch (e2) { toast.error("Failed to load niche market data — retrying may help"); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const patchTarget = async (t, patch, msg) => {
    try { await api.patch(`/niche-markets/targets/${t.id}`, patch); if (msg) toast.success(msg); load(); }
    catch (e2) { toast.error(errTxt(e2)); }
  };

  if (!pb || !dash) return <div className="p-8 text-slate-500 font-mono text-sm">Loading niche market network…</div>;
  const s = dash.stats;
  const wr = dash.win_rate || {};
  const rd = dash.readiness || {};
  const shown = vertFilter ? targets.filter((t) => t.vertical === vertFilter) : targets;

  return (
    <div className="p-6 space-y-6 relative" data-testid="niche-markets-page">
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div style={{ position: "absolute", top: -160, left: "18%", width: 520, height: 520, borderRadius: 9999, filter: "blur(60px)", background: "radial-gradient(circle, rgba(245,158,11,0.12), transparent 65%)" }} />
      </div>

      <div className="relative">
        <h1 className="text-2xl font-black text-white flex items-center gap-2"><Crosshair className="text-amber-300" size={24} /> MN Niche Market Network</h1>
        <p className="text-xs text-slate-500 font-mono mt-1">10 high-margin Minnesota verticals · {s.targets_total} named targets · AI battle cards + pitches · phase-tracked to 765 loads/mo & $4.5M Y1</p>
      </div>

      <div className="relative grid grid-cols-2 md:grid-cols-5 gap-3" data-testid="nm-stats">
        {[["Named targets", s.targets_total, "#22D3EE"], ["Loads/mo locked", `${s.contracted_loads_month}/765`, "#F59E0B"],
          ["Y1 locked", money(s.contracted_y1_revenue), "#34D399"], ["Weighted pipeline", money(s.weighted_pipeline_y1), "#A78BFA"],
          ["Pilots live", s.pilots_active, "#FB923C"],
          ["Actively pitching", wr.actively_pitching ?? 0, "#A78BFA"], ["Meetings taken", wr.meetings_taken ?? 0, "#F59E0B"],
          ["Said maybe", wr.maybe ?? 0, "#FBBF24"], ["Said no (depri)", wr.no_deprioritized ?? 0, "#F87171"],
          ["Win rate", wr.win_rate_pct == null ? "—" : `${wr.win_rate_pct}%`, "#10B981"]].map(([l, v, c]) => (
          <div key={l} className="p-3 rounded-2xl border border-white/10 bg-slate-950/70 backdrop-blur">
            <div className="text-lg font-black tabular-nums" style={{ color: c }}>{v}</div>
            <div className="text-[9px] font-mono uppercase tracking-wider text-slate-500 mt-0.5">{l}</div>
          </div>
        ))}
      </div>

      <div className="relative grid md:grid-cols-4 gap-3" data-testid="nm-readiness">
        <div className="p-3.5 rounded-2xl border border-orange-500/25 bg-orange-500/5">
          <div className="text-[10px] font-mono font-bold text-orange-300 uppercase flex items-center gap-1.5 mb-1.5"><Truck size={11} /> Carrier readiness gap</div>
          <div className="text-xl font-black text-white">{rd.carrier_gap_active_deals ?? 0} <span className="text-[11px] font-mono text-slate-500">dedicated trucks still to recruit for active deals</span></div>
        </div>
        <div className="p-3.5 rounded-2xl border border-red-500/25 bg-red-500/5">
          <div className="text-[10px] font-mono font-bold text-red-300 uppercase flex items-center gap-1.5 mb-1.5"><Wrench size={11} /> Feature blockers on live deals</div>
          {(rd.feature_blockers || []).length === 0 ? <div className="text-[11px] text-slate-500 font-mono">None — nothing blocking</div>
            : (rd.feature_blockers || []).slice(0, 3).map((b) => (
              <div key={b.feature} className="text-[11px] text-slate-300 truncate"><span style={{ color: FEAT_META[b.status] }}>●</span> {b.feature} <span className="text-slate-600 font-mono">→ {b.blocking.join(", ")}</span></div>
            ))}
        </div>
        <div className="p-3.5 rounded-2xl border border-amber-500/25 bg-amber-500/5" data-testid="nm-followups-panel">
          <div className="text-[10px] font-mono font-bold text-amber-300 uppercase flex items-center gap-1.5 mb-1.5"><BellRing size={11} /> Follow-ups due (7+ days cold)</div>
          {(rd.cold_deals || []).length === 0 ? <div className="text-[11px] text-slate-500 font-mono">No cold deals — every pitched target touched inside 7 days</div>
            : (rd.cold_deals || []).slice(0, 3).map((c) => (
              <button key={c.id} onClick={() => { const tt = targets.find((x) => x.id === c.id); if (tt) setDetail(tt); }} data-testid={`nm-cold-${c.id}`}
                      className="w-full text-[11px] text-slate-300 flex justify-between hover:text-amber-200">
                <span className="truncate">{c.name}</span>
                <span className="font-mono text-amber-300 shrink-0">{c.days_since_touch}d cold</span>
              </button>
            ))}
        </div>
        <div className="p-3.5 rounded-2xl border border-cyan-500/25 bg-cyan-500/5">
          <div className="text-[10px] font-mono font-bold text-cyan-300 uppercase flex items-center gap-1.5 mb-1.5"><AlarmClock size={11} /> Decision deadlines</div>
          {(rd.urgent_deadlines || []).length === 0 ? <div className="text-[11px] text-slate-500 font-mono">No deadlines set — add them per target</div>
            : (rd.urgent_deadlines || []).slice(0, 3).map((u) => (
              <div key={u.id} className="text-[11px] text-slate-300 flex justify-between">
                <span className="truncate">{u.name}</span>
                <span className={`font-mono ${u.overdue ? "text-red-400" : "text-cyan-300"}`}>{u.deadline}{u.overdue ? " · OVERDUE" : ""}</span>
              </div>
            ))}
        </div>
      </div>

      <div className="relative grid grid-cols-3 gap-3" data-testid="nm-velocity">
        {[["Closed last month", dash.velocity?.closed_last_month ?? 0, "pilots/contracts landed"],
          ["Closing now", dash.velocity?.closing_now ?? 0, "in pilot-proposed or pilot-live today"],
          ["Projected next", dash.velocity?.projected_next ?? 0, "in meetings now — next month's closes"]].map(([l, v, sub]) => (
          <div key={l} className="p-3 rounded-2xl border border-white/10 bg-white/[0.03]">
            <div className="text-[9px] font-mono uppercase tracking-wider text-slate-500">Velocity · {l}</div>
            <div className="text-xl font-black text-white tabular-nums">{v} <span className="text-[10px] font-mono text-slate-600 font-normal">{sub}</span></div>
          </div>
        ))}
      </div>

      <div className="relative grid md:grid-cols-3 gap-3" data-testid="nm-phases">
        {dash.phases.map((ph) => (
          <div key={ph.phase} className="p-4 rounded-2xl border border-white/10 bg-slate-950/60 backdrop-blur">
            <div className="flex items-center justify-between mb-2">
              <div className="text-[11px] font-mono font-bold text-amber-300 uppercase">{ph.label}</div>
              <div className="text-[10px] font-mono text-slate-500">{ph.loads_committed}/{ph.loads_target} loads/mo</div>
            </div>
            <div className="h-1.5 rounded-full bg-white/10 mb-3">
              <div className="h-1.5 rounded-full bg-amber-400" style={{ width: `${Math.min(100, (ph.loads_committed / ph.loads_target) * 100)}%` }} />
            </div>
            <div className="space-y-1.5">
              {ph.targets.map((t) => {
                const [lab, col] = STAGE_META[t.stage] || ["?", "#666"];
                return (
                  <div key={t.id} className="flex items-center justify-between text-[11px]">
                    <span className="text-slate-300 font-bold truncate">{t.name}</span>
                    <span className="flex items-center gap-2 shrink-0">
                      <span className="font-mono text-slate-500">{t.est_loads_month}/mo</span>
                      <span className="px-1.5 py-0.5 rounded font-mono font-bold text-[8px]" style={{ color: col, border: `1px solid ${col}55` }}>{lab}</span>
                    </span>
                  </div>
                );
              })}
            </div>
            <div className="text-[10px] font-mono text-slate-600 mt-2">Y1 plan {money(ph.y1_revenue_target)} · locked {money(ph.y1_committed)}</div>
          </div>
        ))}
      </div>

      <div className="relative space-y-3" data-testid="nm-verticals">
        {[1, 2, 3].map((tier) => (
          <div key={tier}>
            <div className="text-[10px] font-mono font-bold text-slate-500 uppercase tracking-widest mb-2">{TIER_LABEL[tier]}</div>
            <div className="grid md:grid-cols-3 lg:grid-cols-4 gap-2">
              {dash.verticals.filter((v) => v.tier === tier).map((v) => (
                <button key={v.vertical} onClick={() => setVertFilter(vertFilter === v.vertical ? "" : v.vertical)}
                        data-testid={`nm-vertical-${v.vertical}`}
                        className={`text-left p-3 rounded-2xl border transition ${vertFilter === v.vertical ? "border-amber-400 bg-amber-500/10" : "border-white/10 bg-white/[0.03] hover:border-amber-400/40"}`}>
                  <div className="text-[12px] font-bold text-white leading-tight">{v.label}</div>
                  <div className="text-[10px] font-mono text-emerald-300 mt-1">${v.margin_per_load[0]}–${v.margin_per_load[1]}/load</div>
                  <div className="text-[9px] font-mono text-slate-500">{v.targets} targets · {v.contracted} signed · wtd {money(v.weighted_y1)}</div>
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className="relative rounded-2xl border border-white/10 bg-slate-950/60 backdrop-blur overflow-hidden" data-testid="nm-target-table">
        <div className="flex items-center justify-between px-4 py-3 border-b border-white/10">
          <div className="text-sm font-black text-white">{vertFilter ? pb.verticals.find((v) => v.key === vertFilter)?.label : "All targets"} <span className="text-slate-500 font-mono text-xs">({shown.length})</span></div>
          <AddTarget verticals={pb.verticals} onAdded={load} />
        </div>
        <div className="overflow-x-auto max-h-[560px] overflow-y-auto">
          <table className="w-full text-[12px]">
            <thead className="sticky top-0 bg-slate-950 z-10">
              <tr className="text-[9px] font-mono uppercase text-slate-500 text-left">
                <th className="px-4 py-2">Company</th><th className="px-2 py-2">Phase</th>
                <th className="px-2 py-2 text-right">Loads/mo</th><th className="px-2 py-2 text-right">Y1 potential</th>
                <th className="px-2 py-2">Stage</th><th className="px-2 py-2">Outcome</th>
                <th className="px-2 py-2 text-center">Warmth</th>
                <th className="px-2 py-2">Deadline</th><th className="px-2 py-2">Contact · last touch</th>
                <th className="px-2 py-2 text-center">Carriers</th><th className="px-2 py-2 text-center">Features</th><th className="px-2 py-2" />
              </tr>
            </thead>
            <tbody>
              {shown.map((t) => {
                const [, col] = STAGE_META[t.stage] || ["?", "#666"];
                const [oLab, oCol] = OUTCOME_META[t.outcome || "active"];
                const feats = t.features_required || [];
                const featsDone = feats.filter((f) => f.status === "done").length;
                const dd = t.decision_deadline;
                const dl = dd ? daysTo(dd) : null;
                return (
                  <tr key={t.id} className={`border-t border-white/5 hover:bg-white/[0.03] ${t.outcome === "no" ? "opacity-40" : ""}`}>
                    <td className="px-4 py-2">
                      <button onClick={() => setDetail(t)} data-testid={`nm-target-${t.id}`} className="text-left">
                        <div className="font-bold text-white">{t.name}</div>
                        <div className="text-[10px] font-mono text-slate-500">{t.city} · {pb.verticals.find((v) => v.key === t.vertical)?.label}</div>
                      </button>
                    </td>
                    <td className="px-2 py-2 font-mono text-amber-300">{t.phase ? `P${t.phase}` : "bench"}</td>
                    <td className="px-2 py-2 text-right font-mono text-slate-300">{t.est_loads_month}</td>
                    <td className="px-2 py-2 text-right font-mono text-emerald-300">{money(t.y1_potential)}</td>
                    <td className="px-2 py-2">
                      <select value={t.stage} onChange={(e) => patchTarget(t, { stage: e.target.value }, `${t.name} → ${e.target.value}`)} data-testid={`nm-stage-${t.id}`}
                              className="bg-slate-900 border border-white/15 rounded-lg px-1.5 py-1 text-[10px] font-mono font-bold" style={{ color: col }}>
                        {Object.keys(STAGE_META).map((st) => <option key={st} value={st}>{STAGE_META[st][0]}</option>)}
                      </select>
                    </td>
                    <td className="px-2 py-2">
                      <select value={t.outcome || "active"} onChange={(e) => patchTarget(t, { outcome: e.target.value }, `${t.name} outcome → ${e.target.value}`)} data-testid={`nm-outcome-${t.id}`}
                              className="bg-slate-900 border border-white/15 rounded-lg px-1.5 py-1 text-[10px] font-mono font-bold" style={{ color: oCol }}>
                        {Object.keys(OUTCOME_META).map((o) => <option key={o} value={o}>{OUTCOME_META[o][0]}</option>)}
                      </select>
                    </td>
                    <td className="px-2 py-2 text-center">
                      {t.warmth_score ? <span className="px-1.5 py-0.5 rounded font-mono font-black text-[10px]" title={t.intro_source || ""} style={{ color: warmthColor(t.warmth_score), border: `1px solid ${warmthColor(t.warmth_score)}55` }}>{t.warmth_score}</span> : <span className="text-slate-700 font-mono text-[10px]">—</span>}
                    </td>
                    <td className="px-2 py-2 font-mono text-[10px]">
                      {dd ? <span className={dl < 0 ? "text-red-400" : dl <= 30 ? "text-amber-300" : "text-slate-400"}>{dd}{dl < 0 ? " ⚠" : ""}</span>
                        : <span className="text-slate-700">—</span>}
                    </td>
                    <td className="px-2 py-2 text-[10px]">
                      <div className="text-slate-300 font-bold">{t.contact_name || <span className="text-slate-700">no contact</span>}</div>
                      <div className="text-slate-600 font-mono truncate max-w-[150px]" title={t.contact_title || ""}>{t.contact_title || t.last_touchpoint || (t.last_touch_at ? t.last_touch_at.slice(0, 10) : "never touched")}</div>
                    </td>
                    <td className="px-2 py-2 text-center font-mono text-[11px]">
                      <span className={(t.carriers_secured || 0) >= (t.carriers_required || 0) ? "text-emerald-300" : "text-orange-300"}>
                        {t.carriers_secured || 0}/{t.carriers_required || 0}
                      </span>
                    </td>
                    <td className="px-2 py-2 text-center font-mono text-[11px]">
                      {feats.length ? <span className={featsDone === feats.length ? "text-emerald-300" : "text-amber-300"}>{featsDone}/{feats.length}</span> : <span className="text-slate-700">—</span>}
                    </td>
                    <td className="px-2 py-2">
                      <button onClick={() => setDetail(t)} data-testid={`nm-open-${t.id}`}
                              className="px-2.5 py-1 rounded-full border border-cyan-500/40 text-cyan-300 text-[10px] font-bold hover:bg-cyan-500/10">AI Desk</button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {detail && <TargetDrawer target={detail} vertical={pb.verticals.find((v) => v.key === detail.vertical)} onClose={() => { setDetail(null); load(); }} />}
    </div>
  );
}

function AddTarget({ verticals, onAdded }) {
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ name: "", vertical: verticals[0]?.key, city: "", est_loads_month: 10, margin_per_load_est: 400, phase: 0 });
  const save = async () => {
    try { await api.post("/niche-markets/targets", f); toast.success("Target added"); setOpen(false); onAdded(); }
    catch (e2) { toast.error(errTxt(e2)); }
  };
  if (!open) return <button onClick={() => setOpen(true)} data-testid="nm-add-btn" className="px-3 py-1.5 rounded-full border border-amber-500/50 text-amber-300 text-[11px] font-bold inline-flex items-center gap-1 hover:bg-amber-500/10"><Plus size={12} /> Add target</button>;
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <input placeholder="Company" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} data-testid="nm-add-name" className="bg-slate-900 border border-white/15 rounded-lg px-2 py-1 text-[11px] text-white w-36" />
      <select value={f.vertical} onChange={(e) => setF({ ...f, vertical: e.target.value })} data-testid="nm-add-vertical" className="bg-slate-900 border border-white/15 rounded-lg px-1.5 py-1 text-[10px] text-slate-300">
        {verticals.map((v) => <option key={v.key} value={v.key}>{v.label}</option>)}
      </select>
      <input placeholder="City" value={f.city} onChange={(e) => setF({ ...f, city: e.target.value })} className="bg-slate-900 border border-white/15 rounded-lg px-2 py-1 text-[11px] text-white w-28" />
      <input type="number" title="loads/mo" value={f.est_loads_month} onChange={(e) => setF({ ...f, est_loads_month: +e.target.value })} className="bg-slate-900 border border-white/15 rounded-lg px-2 py-1 text-[11px] text-white w-16" />
      <button onClick={save} data-testid="nm-add-save" className="px-2.5 py-1 rounded-full bg-amber-500 text-black text-[10px] font-black">SAVE</button>
      <button onClick={() => setOpen(false)} className="text-slate-500 hover:text-white"><X size={14} /></button>
    </div>
  );
}

function TargetDrawer({ target, vertical, onClose }) {
  const [t, setT] = useState(target);
  const [busy, setBusy] = useState("");
  const [contact, setContact] = useState({ contact_name: target.contact_name || "", contact_title: target.contact_title || "", contact_email: target.contact_email || "", contact_phone: target.contact_phone || "" });
  const [ops, setOps] = useState({
    decision_deadline: target.decision_deadline || "", last_touchpoint: "",
    carriers_required: target.carriers_required || 0, carriers_secured: target.carriers_secured || 0,
  });
  const [newFeat, setNewFeat] = useState("");
  const [bridge, setBridge] = useState(null);
  const [intel, setIntel] = useState({
    intro_source: target.intro_source || "", warmth_score: target.warmth_score || "",
    current_carrier: target.current_carrier || "", switch_angle: target.switch_angle || "",
    est_acquisition_cost: target.est_acquisition_cost || "",
  });
  const [sim, setSim] = useState({
    rate: target.sim_shipper_rate || Math.round((target.margin_per_load_est || 400) * 4),
    cost: target.sim_carrier_cost || Math.round((target.margin_per_load_est || 400) * 3),
  });

  const loadBridge = useCallback(async () => {
    try { const { data } = await api.get(`/niche-markets/targets/${target.id}/carrier-matches`); setBridge(data); }
    catch (_) {}
  }, [target.id]);
  useEffect(() => { loadBridge(); }, [loadBridge]);

  const linkCarrier = async (pid) => {
    try { const { data } = await api.post(`/niche-markets/targets/${t.id}/link-carrier/${pid}`); setT(data.target); toast.success(`${data.linked.name} linked to deal`); loadBridge(); }
    catch (e2) { toast.error(errTxt(e2)); }
  };
  const unlinkCarrier = async (pid) => {
    try { const { data } = await api.delete(`/niche-markets/targets/${t.id}/link-carrier/${pid}`); setT(data.target); toast.success("Carrier unlinked"); loadBridge(); }
    catch (e2) { toast.error(errTxt(e2)); }
  };
  const patchLink = async (pid, body) => {
    try { const { data } = await api.patch(`/niche-markets/targets/${t.id}/link-carrier/${pid}`, body); setT(data.target); }
    catch (e2) { toast.error(errTxt(e2)); }
  };
  const saveIntel = () => {
    const body = { intro_source: intel.intro_source, current_carrier: intel.current_carrier, switch_angle: intel.switch_angle };
    if (intel.warmth_score !== "") body.warmth_score = +intel.warmth_score;
    if (intel.est_acquisition_cost !== "") body.est_acquisition_cost = +intel.est_acquisition_cost;
    patch(body, "Intel saved");
  };
  const saveSim = () => patch({ sim_shipper_rate: +sim.rate, sim_carrier_cost: +sim.cost }, "Assumptions saved");

  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const patch = async (body, msg) => {
    try { const { data } = await api.patch(`/niche-markets/targets/${t.id}`, body); setT(data.target); if (msg) toast.success(msg); return data.target; }
    catch (e2) { toast.error(errTxt(e2)); return null; }
  };
  const saveContact = () => patch(contact, "Contact saved");
  const saveOps = () => {
    const body = { decision_deadline: ops.decision_deadline, carriers_required: +ops.carriers_required, carriers_secured: +ops.carriers_secured };
    if (ops.last_touchpoint.trim()) body.last_touchpoint = ops.last_touchpoint.trim();
    patch(body, "Readiness saved").then((r) => { if (r) setOps({ ...ops, last_touchpoint: "" }); });
  };
  const cycleFeat = (idx) => {
    const order = ["missing", "in_progress", "done"];
    const feats = [...(t.features_required || [])];
    feats[idx] = { ...feats[idx], status: order[(order.indexOf(feats[idx].status) + 1) % 3] };
    patch({ features_required: feats });
  };
  const addFeat = () => {
    if (!newFeat.trim()) return;
    patch({ features_required: [...(t.features_required || []), { name: newFeat.trim(), status: "missing" }] }, "Feature dependency added");
    setNewFeat("");
  };
  const rmFeat = (idx) => patch({ features_required: (t.features_required || []).filter((_, i) => i !== idx) });

  const genCard = async () => {
    setBusy("card");
    try { const { data } = await api.post(`/niche-markets/targets/${t.id}/battle-card`, {}, { timeout: 100000 }); setT({ ...t, battle_card: data.battle_card, stage: t.stage === "target" ? "researched" : t.stage }); toast.success("Battle card ready"); }
    catch (e2) { toast.error(errTxt(e2)); } finally { setBusy(""); }
  };
  const genPitch = async (send, followUp = false) => {
    setBusy(send ? "send" : followUp ? "followup" : "pitch");
    try {
      const { data } = await api.post(`/niche-markets/targets/${t.id}/pitch`, { send, follow_up: followUp, email: contact.contact_email || undefined }, { timeout: 100000 });
      setT({ ...t, last_pitch: data.pitch });
      toast.success(send ? (data.pitch.sent ? "Email sent via Resend" : "Email queued — add Resend key in Connections to deliver") : followUp ? "Follow-up drafted" : "Pitch drafted");
    } catch (e2) { toast.error(errTxt(e2)); } finally { setBusy(""); }
  };
  const del = async () => {
    if (!window.confirm(`Remove ${t.name} from the target board?`)) return;
    try { await api.delete(`/niche-markets/targets/${t.id}`); toast.success("Target removed"); onClose(); }
    catch (e2) { toast.error(errTxt(e2)); }
  };
  const bc = t.battle_card;

  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex justify-end" onClick={onClose}>
      <div className="w-full max-w-lg h-full bg-slate-950 border-l border-amber-500/30 p-5 overflow-y-auto" onClick={(e) => e.stopPropagation()} data-testid="nm-drawer">
        <div className="flex justify-between items-start">
          <div>
            <div className="font-black text-white text-lg">{t.name}</div>
            <div className="text-[11px] font-mono text-slate-500">{t.city} · {vertical?.label} · Tier {vertical?.tier}</div>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={del} data-testid="nm-delete" className="text-slate-600 hover:text-red-400"><Trash2 size={15} /></button>
            <button onClick={onClose} className="text-slate-500 hover:text-white"><X size={18} /></button>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-2 my-4">
          {[["Loads/mo est", t.est_loads_month, TargetIcon], ["Margin/load", `$${t.margin_per_load_est}`, TrendingUp], ["Y1 potential", money(t.est_loads_month * t.margin_per_load_est * 12), Landmark]].map(([l, v, Icon]) => (
            <div key={l} className="p-2.5 rounded-xl border border-white/10 text-center">
              <Icon size={12} className="mx-auto text-amber-300 mb-1" />
              <div className="font-black text-white text-sm tabular-nums">{v}</div>
              <div className="text-[8px] font-mono uppercase text-slate-500">{l}</div>
            </div>
          ))}
        </div>

        {t.notes && <div className="p-3 rounded-xl border border-white/10 bg-white/[0.03] text-[11.5px] text-slate-300 mb-3"><ShieldCheck size={11} className="inline mr-1.5 text-emerald-300" />{t.notes}</div>}

        <div className="p-3 rounded-xl border border-white/10 bg-white/[0.03] mb-3">
          <div className="text-[10px] font-mono uppercase text-slate-500 mb-2">Contact — {vertical?.contact_role}</div>
          <div className="grid grid-cols-2 gap-1.5">
            <input placeholder="Name" value={contact.contact_name} onChange={(e) => setContact({ ...contact, contact_name: e.target.value })} data-testid="nm-contact-name" className="bg-slate-900 border border-white/15 rounded-lg px-2 py-1.5 text-[11px] text-white" />
            <input placeholder="Title" value={contact.contact_title} onChange={(e) => setContact({ ...contact, contact_title: e.target.value })} data-testid="nm-contact-title" className="bg-slate-900 border border-white/15 rounded-lg px-2 py-1.5 text-[11px] text-white" />
            <input placeholder="Email" value={contact.contact_email} onChange={(e) => setContact({ ...contact, contact_email: e.target.value })} data-testid="nm-contact-email" className="bg-slate-900 border border-white/15 rounded-lg px-2 py-1.5 text-[11px] text-white" />
            <input placeholder="Phone" value={contact.contact_phone} onChange={(e) => setContact({ ...contact, contact_phone: e.target.value })} className="bg-slate-900 border border-white/15 rounded-lg px-2 py-1.5 text-[11px] text-white" />
          </div>
          {t.email_confidence === "pattern_guess" && (
            <div className="mt-1.5 text-[10px] font-mono text-amber-300/90" data-testid="nm-email-warning">⚠ Email is a pattern-based guess from public research — verify on LinkedIn before sending.</div>
          )}
          <button onClick={saveContact} data-testid="nm-contact-save" className="mt-2 px-3 py-1 rounded-full border border-white/20 text-slate-300 text-[10px] font-bold hover:border-amber-400">Save contact</button>
          {(t.email_pattern || t.linkedin_search || t.alt_contacts) && (
            <div className="mt-2 pt-2 border-t border-white/10 space-y-1" data-testid="nm-sourcing-intel">
              <div className="text-[9px] font-mono uppercase text-cyan-300 font-bold">Sourcing intel</div>
              {t.email_pattern && <div className="text-[10.5px] text-slate-400 font-mono">Pattern: {t.email_pattern}{t.company_domain ? ` · ${t.company_domain}` : ""}</div>}
              {t.alt_contacts && <div className="text-[10.5px] text-slate-400">Also hunt: {t.alt_contacts}</div>}
              {t.linkedin_search && (
                <a href={`https://www.linkedin.com/search/results/people/?keywords=${encodeURIComponent(t.linkedin_search)}`} target="_blank" rel="noreferrer"
                   data-testid="nm-linkedin-search" className="inline-block text-[10.5px] text-cyan-300 hover:underline">Search on LinkedIn →</a>
              )}
            </div>
          )}
          {t.last_touchpoint && <div className="mt-2 text-[10.5px] text-slate-400 font-mono">Last touch: {t.last_touchpoint} {t.last_touch_at && `· ${t.last_touch_at.slice(0, 10)}`}</div>}
        </div>

        <div className="p-3 rounded-xl border border-orange-500/20 bg-orange-500/5 mb-3" data-testid="nm-ops-panel">
          <div className="text-[10px] font-mono uppercase text-orange-300 font-bold mb-2">Deal readiness</div>
          <div className="grid grid-cols-2 gap-1.5 mb-2">
            <label className="text-[9px] font-mono text-slate-500 uppercase">Decision deadline
              <input type="date" value={ops.decision_deadline} onChange={(e) => setOps({ ...ops, decision_deadline: e.target.value })} data-testid="nm-deadline-input" className="w-full bg-slate-900 border border-white/15 rounded-lg px-2 py-1.5 text-[11px] text-white mt-0.5" />
            </label>
            <label className="text-[9px] font-mono text-slate-500 uppercase">Carriers req / secured
              <div className="flex gap-1 mt-0.5">
                <input type="number" value={ops.carriers_required} onChange={(e) => setOps({ ...ops, carriers_required: e.target.value })} data-testid="nm-carriers-required" className="w-1/2 bg-slate-900 border border-white/15 rounded-lg px-2 py-1.5 text-[11px] text-white" />
                <input type="number" value={ops.carriers_secured} onChange={(e) => setOps({ ...ops, carriers_secured: e.target.value })} data-testid="nm-carriers-secured" className="w-1/2 bg-slate-900 border border-white/15 rounded-lg px-2 py-1.5 text-[11px] text-emerald-300" />
              </div>
            </label>
          </div>
          <input placeholder="Log a touchpoint (call notes, reaction, next step…)" value={ops.last_touchpoint} onChange={(e) => setOps({ ...ops, last_touchpoint: e.target.value })} data-testid="nm-touchpoint-input" className="w-full bg-slate-900 border border-white/15 rounded-lg px-2 py-1.5 text-[11px] text-white mb-2" />
          <div className="mb-2">
            <div className="text-[9px] font-mono text-slate-500 uppercase mb-1">Orisei features required (click status to cycle)</div>
            {(t.features_required || []).map((f, i) => (
              <div key={i} className="flex items-center gap-2 text-[11px] py-0.5">
                <button onClick={() => cycleFeat(i)} className="px-1.5 py-0.5 rounded font-mono font-bold text-[8px]" style={{ color: FEAT_META[f.status], border: `1px solid ${FEAT_META[f.status]}55` }} data-testid={`nm-feat-status-${i}`}>{f.status.toUpperCase()}</button>
                <span className="text-slate-300 flex-1">{f.name}</span>
                <button onClick={() => rmFeat(i)} className="text-slate-700 hover:text-red-400"><X size={11} /></button>
              </div>
            ))}
            <div className="flex gap-1.5 mt-1">
              <input placeholder="Add feature dependency…" value={newFeat} onChange={(e) => setNewFeat(e.target.value)} data-testid="nm-feature-add-input" className="flex-1 bg-slate-900 border border-white/15 rounded-lg px-2 py-1 text-[11px] text-white" />
              <button onClick={addFeat} data-testid="nm-feature-add" className="px-2.5 rounded-lg border border-white/20 text-slate-300 text-[10px] font-bold hover:border-amber-400">Add</button>
            </div>
          </div>
          <button onClick={saveOps} data-testid="nm-ops-save" className="px-3 py-1 rounded-full bg-orange-400 text-black text-[10px] font-black">SAVE READINESS</button>
        </div>

        <div className="p-3 rounded-xl border border-emerald-500/20 bg-emerald-500/5 mb-3" data-testid="nm-margin-sim">
          <div className="text-[10px] font-mono uppercase text-emerald-300 font-bold mb-2">Margin Simulation — deal-closing oxygen</div>
          <div className="grid grid-cols-2 gap-1.5 mb-2">
            <label className="text-[9px] font-mono text-slate-500 uppercase">Avg shipper rate / load
              <input type="number" value={sim.rate} onChange={(e) => setSim({ ...sim, rate: e.target.value })} data-testid="nm-sim-rate" className="w-full bg-slate-900 border border-white/15 rounded-lg px-2 py-1.5 text-[11px] text-white mt-0.5" />
            </label>
            <label className="text-[9px] font-mono text-slate-500 uppercase">Avg carrier cost / load
              <input type="number" value={sim.cost} onChange={(e) => setSim({ ...sim, cost: e.target.value })} data-testid="nm-sim-cost" className="w-full bg-slate-900 border border-white/15 rounded-lg px-2 py-1.5 text-[11px] text-white mt-0.5" />
            </label>
          </div>
          {(() => {
            const R = +sim.rate || 0, C = +sim.cost || 0, L = t.est_loads_month || 0;
            const rows = [["Best case", R * 1.10, C * 0.95, "#34D399"], ["Expected", R, C, "#FBBF24"], ["Worst case", R * 0.88, C * 1.08, "#F87171"]];
            const dropPct = R > 0 ? Math.round(((R - C) / R) * 100) : 0;
            const expMo = (R - C) * L;
            const payback = intel.est_acquisition_cost && expMo > 0 ? (+intel.est_acquisition_cost / expMo).toFixed(1) : null;
            return (
              <>
                {rows.map(([lab, r, c, col]) => (
                  <div key={lab} className="flex items-center justify-between text-[11px] py-1 border-t border-white/5">
                    <span className="font-bold" style={{ color: col }}>{lab}</span>
                    <span className="font-mono text-slate-400">${Math.round(r).toLocaleString()} − ${Math.round(c).toLocaleString()}</span>
                    <span className="font-mono font-black" style={{ color: r - c >= 0 ? col : "#F87171" }}>{money((r - c) * L)}/mo · {money((r - c) * L * 12)}/yr</span>
                  </div>
                ))}
                <div className="mt-1.5 text-[10.5px] font-mono" data-testid="nm-sim-breakeven">
                  <span className={dropPct <= 10 ? "text-red-300" : "text-slate-400"}>Break-even at ${C.toLocaleString()} shipper rate — deal goes negative if rates soften {dropPct}%.</span>
                  {dropPct <= 10 && <span className="text-red-400 font-bold"> Thin cushion — hold the line on price.</span>}
                </div>
                {payback && <div className="text-[10.5px] font-mono text-cyan-300 mt-1" data-testid="nm-sim-payback">Acquisition payback: {payback} months at expected margin (cost {money(+intel.est_acquisition_cost)})</div>}
              </>
            );
          })()}
          <button onClick={saveSim} data-testid="nm-sim-save" className="mt-2 px-3 py-1 rounded-full border border-emerald-500/40 text-emerald-300 text-[10px] font-black hover:bg-emerald-500/10">SAVE ASSUMPTIONS</button>
        </div>

        <div className="p-3 rounded-xl border border-purple-500/20 bg-purple-500/5 mb-3" data-testid="nm-intel-panel">
          <div className="text-[10px] font-mono uppercase text-purple-300 font-bold mb-2">Intro & Competitive Intel</div>
          <div className="grid grid-cols-2 gap-1.5 mb-1.5">
            <input placeholder="Intro source (e.g. CHS referral, cold email)" value={intel.intro_source} onChange={(e) => setIntel({ ...intel, intro_source: e.target.value })} data-testid="nm-intro-source" className="bg-slate-900 border border-white/15 rounded-lg px-2 py-1.5 text-[11px] text-white" />
            <label className="flex items-center gap-2 text-[9px] font-mono text-slate-500 uppercase">Warmth 1–10
              <input type="number" min="1" max="10" value={intel.warmth_score} onChange={(e) => setIntel({ ...intel, warmth_score: e.target.value })} data-testid="nm-warmth-input" className="w-16 bg-slate-900 border border-white/15 rounded-lg px-2 py-1.5 text-[11px] font-black" style={{ color: warmthColor(+intel.warmth_score || 0) }} />
            </label>
          </div>
          <input placeholder="Current carrier(s) — who moves their freight today?" value={intel.current_carrier} onChange={(e) => setIntel({ ...intel, current_carrier: e.target.value })} data-testid="nm-current-carrier" className="w-full bg-slate-900 border border-white/15 rounded-lg px-2 py-1.5 text-[11px] text-white mb-1.5" />
          <input placeholder="Why they'd switch — what's broken about their setup?" value={intel.switch_angle} onChange={(e) => setIntel({ ...intel, switch_angle: e.target.value })} data-testid="nm-switch-angle" className="w-full bg-slate-900 border border-white/15 rounded-lg px-2 py-1.5 text-[11px] text-white mb-1.5" />
          <label className="text-[9px] font-mono text-slate-500 uppercase flex items-center gap-2">Est. acquisition cost ($)
            <input type="number" value={intel.est_acquisition_cost} onChange={(e) => setIntel({ ...intel, est_acquisition_cost: e.target.value })} data-testid="nm-acq-cost" className="w-28 bg-slate-900 border border-white/15 rounded-lg px-2 py-1.5 text-[11px] text-white" />
          </label>
          <button onClick={saveIntel} data-testid="nm-intel-save" className="mt-2 px-3 py-1 rounded-full border border-purple-500/40 text-purple-300 text-[10px] font-black hover:bg-purple-500/10">SAVE INTEL</button>
        </div>

        <div className="flex gap-2 mb-4">
          <button onClick={genCard} disabled={!!busy} data-testid="nm-battle-card-btn"
                  className="flex-1 px-3 py-2 rounded-full border border-cyan-500/50 text-cyan-300 text-[11px] font-bold inline-flex items-center justify-center gap-1.5 hover:bg-cyan-500/10 disabled:opacity-50">
            {busy === "card" ? <Loader2 size={13} className="animate-spin" /> : <FlaskConical size={13} />} AI Battle Card
          </button>
          <button onClick={() => genPitch(false)} disabled={!!busy} data-testid="nm-pitch-btn"
                  className="flex-1 px-3 py-2 rounded-full border border-amber-500/50 text-amber-300 text-[11px] font-bold inline-flex items-center justify-center gap-1.5 hover:bg-amber-500/10 disabled:opacity-50">
            {busy === "pitch" ? <Loader2 size={13} className="animate-spin" /> : <Sparkles size={13} />} AI Pitch
          </button>
          <button onClick={() => genPitch(false, true)} disabled={!!busy} data-testid="nm-followup-btn"
                  className="flex-1 px-3 py-2 rounded-full border border-emerald-500/50 text-emerald-300 text-[11px] font-bold inline-flex items-center justify-center gap-1.5 hover:bg-emerald-500/10 disabled:opacity-50">
            {busy === "followup" ? <Loader2 size={13} className="animate-spin" /> : <RotateCcw size={13} />} AI Follow-Up
          </button>
        </div>

        {bridge && (
          <div className="p-3.5 rounded-xl border border-orange-500/25 bg-orange-500/5 mb-4 space-y-2" data-testid="nm-bridge">
            <div className="flex items-center justify-between">
              <div className="text-[10px] font-mono uppercase text-orange-300 font-bold flex items-center gap-1.5"><Link2 size={11} /> Carrier Recruiting Bridge</div>
              <div className="text-[10px] font-mono" style={{ color: bridge.gap > 0 ? "#FB923C" : "#34D399" }}>{bridge.gap > 0 ? `${bridge.gap} trucks still needed` : "FULLY STAFFED"}</div>
            </div>
            <div className="flex flex-wrap gap-1">
              {bridge.needed_equipment.map((e) => <span key={e} className="px-1.5 py-0.5 rounded bg-white/5 border border-white/10 text-[9px] font-mono text-slate-300">{e}</span>)}
            </div>
            {(t.linked_carriers || []).length > 0 && (
              <div>
                <div className="text-[9px] font-mono text-slate-500 uppercase mb-1">Carrier assignments — this deal</div>
                {(t.linked_carriers || []).map((c) => {
                  const [sl, sc] = LINK_STATUS_META[c.status || "in_talks"];
                  return (
                    <div key={c.id} className="flex items-center gap-2 text-[11px] py-1 border-t border-white/5">
                      <span className="text-emerald-300 font-bold flex-1 truncate">{c.name} {c.mc_number && <span className="text-slate-600 font-mono text-[9px]">{c.mc_number}</span>}</span>
                      <input type="number" placeholder="rate $" defaultValue={c.rate_usd || ""} onBlur={(e) => e.target.value !== String(c.rate_usd || "") && patchLink(c.id, { rate_usd: +e.target.value || 0 })}
                             data-testid={`nm-link-rate-${c.id}`} className="w-20 bg-slate-900 border border-white/15 rounded-lg px-1.5 py-1 text-[10px] text-white" />
                      <select value={c.status || "in_talks"} onChange={(e) => patchLink(c.id, { status: e.target.value })} data-testid={`nm-link-status-${c.id}`}
                              className="bg-slate-900 border border-white/15 rounded-lg px-1 py-1 text-[9px] font-mono font-bold" style={{ color: sc }}>
                        {Object.keys(LINK_STATUS_META).map((s) => <option key={s} value={s}>{LINK_STATUS_META[s][0]}</option>)}
                      </select>
                      <button onClick={() => unlinkCarrier(c.id)} data-testid={`nm-unlink-${c.id}`} className="text-slate-600 hover:text-red-400"><X size={12} /></button>
                    </div>
                  );
                })}
                {(() => {
                  const links = t.linked_carriers || [];
                  const live = links.filter((c) => ["signed", "live"].includes(c.status)).length;
                  const rates = links.filter((c) => c.rate_usd);
                  const avg = rates.length ? Math.round(rates.reduce((a, c) => a + c.rate_usd, 0) / rates.length) : null;
                  return <div className="text-[9.5px] font-mono text-slate-500 mt-1" data-testid="nm-link-summary">{live}/{links.length} signed or live{avg ? ` · avg locked rate $${avg.toLocaleString()}` : ""} · {Math.max(0, (t.carriers_required || 0) - links.length)} still to source</div>;
                })()}
              </div>
            )}
            <div className="text-[9px] font-mono text-slate-500 uppercase">Best matches from Carrier Network</div>
            {bridge.matches.length === 0 ? <div className="text-[11px] text-slate-500 font-mono">No fits — recruit {bridge.needed_equipment.join("/")} carriers in the Carrier Network</div>
              : bridge.matches.slice(0, 5).map((m) => (
                <div key={m.id} className="flex items-center justify-between text-[11px] py-1 border-t border-white/5">
                  <div className="min-w-0">
                    <div className="text-slate-200 font-bold truncate">{m.name} <span className="text-slate-600 font-mono text-[9px]">score {m.match_score}</span></div>
                    <div className="text-[9px] font-mono text-slate-500 truncate">{m.stage} · {(m.equipment_fit.length ? m.equipment_fit : m.equipment).join(", ")} · {m.home_base}</div>
                  </div>
                  <button onClick={() => linkCarrier(m.id)} data-testid={`nm-link-${m.id}`}
                          className="shrink-0 px-2.5 py-1 rounded-full border border-emerald-500/50 text-emerald-300 text-[9px] font-black hover:bg-emerald-500/10">LINK</button>
                </div>
              ))}
          </div>
        )}

        {bc && (
          <div className="p-3.5 rounded-xl border border-cyan-500/25 bg-cyan-500/5 mb-4 space-y-2.5" data-testid="nm-battle-card">
            <div className="text-[10px] font-mono uppercase text-cyan-300 font-bold">Account Battle Card</div>
            <div className="text-[11.5px] text-slate-200"><b className="text-white">Ships:</b> {bc.what_they_ship}</div>
            <div className="text-[11.5px] text-slate-200"><b className="text-white">Likely lanes:</b> {(bc.likely_lanes || []).join(" · ")}</div>
            <div className="text-[11.5px] text-slate-200"><b className="text-white">Hunt on LinkedIn:</b> {(bc.decision_makers || []).join(" · ")}</div>
            {(bc.objections || []).map((o, i) => (
              <div key={i} className="text-[11px] p-2 rounded-lg bg-black/30 border border-white/10">
                <span className="text-red-300">"{o.objection}"</span>
                <div className="text-emerald-300 mt-0.5">↳ {o.counter}</div>
              </div>
            ))}
            <div className="text-[11.5px] text-amber-200 italic">Opening hook: "{bc.hook}"</div>
            <div className="text-[10.5px] text-slate-400"><b>Compliance:</b> {bc.compliance_notes}</div>
          </div>
        )}

        {t.last_pitch && (
          <div className="p-3.5 rounded-xl border border-amber-500/25 bg-amber-500/5 space-y-2" data-testid="nm-pitch-preview">
            <div className="flex items-center justify-between">
              <div className="text-[10px] font-mono uppercase text-amber-300 font-bold">{t.last_pitch.kind === "follow_up" ? "Follow-up email" : "Pitch email"} {t.last_pitch.sent && <span className="text-emerald-300">· SENT</span>}</div>
              <button onClick={() => { navigator.clipboard.writeText(`${t.last_pitch.subject}\n\n${t.last_pitch.body_text}`); toast.success("Copied"); }} data-testid="nm-pitch-copy" className="text-slate-400 hover:text-white"><Copy size={13} /></button>
            </div>
            <div className="text-[12px] font-bold text-white">{t.last_pitch.subject}</div>
            <pre className="text-[11px] text-slate-300 whitespace-pre-wrap font-sans">{t.last_pitch.body_text}</pre>
            <button onClick={() => genPitch(true)} disabled={!!busy || !contact.contact_email} data-testid="nm-pitch-send"
                    className="w-full px-3 py-2 rounded-full bg-amber-500 text-black text-[11px] font-black inline-flex items-center justify-center gap-1.5 disabled:opacity-40">
              {busy === "send" ? <Loader2 size={13} className="animate-spin" /> : <Send size={13} />} {contact.contact_email ? "SEND VIA RESEND" : "ADD CONTACT EMAIL TO SEND"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
