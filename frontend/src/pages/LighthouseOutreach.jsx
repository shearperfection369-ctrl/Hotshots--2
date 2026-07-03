import React, { useCallback, useEffect, useMemo, useState } from "react";
import Topbar from "../components/Topbar";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";
import { Badge } from "../components/ui/badge";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "../components/ui/dialog";
import {
  Lightbulb, TrendingUp, Target, Sparkles, Users, MessageSquare, FileDown,
  Plus, RefreshCw, Loader2, CheckCircle2, Trash2, ExternalLink, Send,
  Presentation, Calculator, ShieldCheck, BookOpen, Map, ClipboardList,
  DollarSign, Radio,
} from "lucide-react";
import { api, BACKEND_URL, getStoredToken } from "../lib/api";
import { useBranding, useBrandRefresh } from "../lib/branding";
import { toast } from "sonner";

/**
 * LighthouseOutreach — Prospect → paying customer funnel for TMS buyers.
 * Six-stage lifecycle: curious → engaged → demo_scheduled → trial → won | lost.
 * Ships Orisei-branded collateral (product tour, ROI calc, spec sheet, case study,
 * security brief, onboarding map) — all downloads auto-log as touches.
 */
const STAGE_META = {
  curious:         { label: "CURIOUS",         color: "#94A3B8", ring: "border-slate-400/40 text-slate-300 bg-slate-500/10" },
  engaged:         { label: "ENGAGED",         color: "#22D3EE", ring: "border-cyan-400/40 text-cyan-200 bg-cyan-500/10" },
  demo_scheduled:  { label: "DEMO SCHEDULED",  color: "#A78BFA", ring: "border-violet-400/40 text-violet-200 bg-violet-500/10" },
  trial:           { label: "IN TRIAL",        color: "#F59E0B", ring: "border-amber-400/40 text-amber-200 bg-amber-500/10" },
  won:             { label: "WON",             color: "#10B981", ring: "border-emerald-400/40 text-emerald-200 bg-emerald-500/10" },
  lost:            { label: "LOST",            color: "#EF4444", ring: "border-red-400/40 text-red-200 bg-red-500/10" },
};

const ASSET_ICON = {
  product_tour:    Presentation,
  roi_calculator:  Calculator,
  spec_sheet:      ClipboardList,
  case_study:      BookOpen,
  security_brief:  ShieldCheck,
  onboarding_map:  Map,
};

const TABS = [
  { id: "deck",       label: "Command Deck", icon: Radio },
  { id: "prospects",  label: "Prospects",    icon: Users },
  { id: "assets",     label: "Collateral",   icon: Presentation },
  { id: "public",     label: "Public Landing", icon: ExternalLink },
];

export default function LighthouseOutreach() {
  const { brand } = useBranding();
  const [tab, setTab] = useState("deck");
  const [dashboard, setDashboard] = useState(null);
  const [prospects, setProspects] = useState([]);
  const [assets, setAssets] = useState([]);
  const [busy, setBusy] = useState(false);

  const loadAll = useCallback(async () => {
    setBusy(true);
    try {
      const [d, p, a] = await Promise.all([
        api.get("/lighthouse/dashboard"),
        api.get("/lighthouse/prospects"),
        api.get("/lighthouse/assets/catalog"),
      ]);
      setDashboard(d.data);
      setProspects(p.data.items || []);
      setAssets(a.data.items || []);
    } catch (e) { toast.error("Failed to load Lighthouse data"); }
    finally { setBusy(false); }
  }, []);
  useEffect(() => { loadAll(); }, [loadAll]);
  useBrandRefresh(() => loadAll());

  const brandShort = brand?.short_name || "Orisei";

  return (
    <>
      <Topbar
        title={`${brandShort} · Lighthouse Outreach`}
        subtitle="Curious → paying customer · branded collateral · funnel tracking"
      />
      <div className="p-4 md:p-6 space-y-4">
        <div className="flex flex-wrap items-center gap-2" data-testid="lighthouse-header">
          <Lightbulb size={22} style={{ color: brand?.accent_color || "#F59E0B" }} />
          <div className="text-slate-100 font-medium">Lighthouse Outreach</div>
          <Badge className="bg-amber-500/15 text-amber-200 border border-amber-400/30">TMS BUYER FUNNEL</Badge>
          <div className="ml-auto">
            <Button variant="secondary" size="sm" onClick={loadAll} disabled={busy}
              data-testid="lighthouse-refresh">
              {busy ? <Loader2 size={13} className="animate-spin mr-1" /> : <RefreshCw size={13} className="mr-1" />}
              Refresh
            </Button>
          </div>
        </div>

        <div className="flex gap-1.5 overflow-x-auto pb-1" data-testid="lighthouse-tabs">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              data-testid={`lighthouse-tab-${id}`}
              className={`inline-flex items-center gap-2 px-4 py-2 rounded text-xs font-mono uppercase tracking-wider transition border whitespace-nowrap ${
                tab === id
                  ? "bg-amber-500 text-black border-amber-400 shadow-[0_0_20px_rgba(245,158,11,0.35)]"
                  : "border-white/10 text-slate-400 hover:border-amber-400/40 hover:text-amber-200"
              }`}
            >
              <Icon size={13} /> {label}
            </button>
          ))}
        </div>

        {tab === "deck"      && <CommandDeck dashboard={dashboard} />}
        {tab === "prospects" && <ProspectsTab prospects={prospects} assets={assets} onChange={loadAll} />}
        {tab === "assets"    && <AssetsTab assets={assets} />}
        {tab === "public"    && <PublicTab />}
      </div>
    </>
  );
}

// ============================================================
//                    COMMAND DECK
// ============================================================
function CommandDeck({ dashboard }) {
  if (!dashboard) return <Loader />;
  const { totals, by_stage, by_source, recent_touches } = dashboard;
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3" data-testid="lighthouse-kpi-strip">
        <BigKpi label="Prospects" value={totals.prospects} accent="#F59E0B" icon={Users} sub="in the funnel" />
        <BigKpi label="30-day touches" value={totals.touches_30d} accent="#22D3EE" icon={MessageSquare} sub="interactions" />
        <BigKpi label="Pipeline value" value={`$${fmtM(totals.pipeline_value_usd)}`} accent="#A78BFA" icon={DollarSign} sub="engaged/demo/trial" />
        <BigKpi label="Won value" value={`$${fmtM(totals.won_value_usd)}`} accent="#10B981" icon={CheckCircle2} sub="closed / annual" />
        <BigKpi label="Win rate" value={totals.win_rate_pct != null ? `${totals.win_rate_pct}%` : "—"} accent="#EF4444" icon={Target} sub="won / (won+lost)" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
        <Card className="md:col-span-3 p-4 bg-slate-900/60 border-white/10">
          <div className="text-[10px] font-mono uppercase tracking-widest text-amber-300 mb-3">Funnel stages</div>
          <FunnelBars byStage={by_stage} />
        </Card>
        <Card className="md:col-span-2 p-4 bg-slate-900/60 border-white/10">
          <div className="text-[10px] font-mono uppercase tracking-widest text-amber-300 mb-3">Sources</div>
          {Object.entries(by_source).length === 0 ? (
            <div className="text-xs text-slate-500">No prospects yet.</div>
          ) : (
            <div className="space-y-1.5">
              {Object.entries(by_source).sort((a, b) => b[1] - a[1]).map(([src, n]) => (
                <div key={src} className="flex items-center justify-between text-xs">
                  <span className="text-slate-300">{src}</span>
                  <span className="text-amber-300 font-mono">{n}</span>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      <Card className="p-0 bg-slate-900/60 border-white/10 overflow-hidden">
        <div className="px-3 py-2 border-b border-white/10 text-[10px] font-mono uppercase tracking-widest text-amber-300">
          <Sparkles size={12} className="inline mr-1" /> Recent touches
        </div>
        {(!recent_touches || recent_touches.length === 0) ? (
          <div className="p-6 text-center text-xs text-slate-500">No touches yet.</div>
        ) : (
          <table className="w-full text-xs">
            <thead className="bg-black/40 text-slate-400 font-mono uppercase tracking-wider">
              <tr>
                <th className="px-3 py-2 text-left">When</th>
                <th className="px-3 py-2 text-left">Kind</th>
                <th className="px-3 py-2 text-left">Prospect</th>
                <th className="px-3 py-2 text-left">Summary</th>
              </tr>
            </thead>
            <tbody>
              {recent_touches.map((t) => (
                <tr key={t.touch_id} className="border-t border-white/5">
                  <td className="px-3 py-2 text-slate-500 font-mono text-[10px]">{t.created_at?.slice(0, 16).replace("T", " ")}</td>
                  <td className="px-3 py-2 text-amber-300 font-mono uppercase text-[10px]">{t.kind}</td>
                  <td className="px-3 py-2 text-slate-300 font-mono text-[10px]">{t.prospect_id}</td>
                  <td className="px-3 py-2 text-slate-200">{t.summary}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}

function FunnelBars({ byStage }) {
  const total = Math.max(1, Object.values(byStage || {}).reduce((s, v) => s + v, 0));
  const order = ["curious", "engaged", "demo_scheduled", "trial", "won", "lost"];
  return (
    <div className="space-y-2">
      {order.map((k) => {
        const v = byStage?.[k] || 0;
        const pct = (v / total) * 100;
        const meta = STAGE_META[k];
        return (
          <div key={k} className="flex items-center gap-3" data-testid={`funnel-${k}`}>
            <div className="w-40 text-[10px] font-mono uppercase tracking-widest" style={{ color: meta.color }}>
              {meta.label}
            </div>
            <div className="flex-1 h-5 bg-black/40 rounded overflow-hidden border border-white/5">
              <div className="h-full flex items-center px-2 text-[10px] font-mono text-black"
                style={{ width: `${Math.max(pct, 3)}%`, background: meta.color }}>
                {v}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ============================================================
//                    PROSPECTS
// ============================================================
function ProspectsTab({ prospects, assets, onChange }) {
  const [addOpen, setAddOpen] = useState(false);
  const [selected, setSelected] = useState(null);
  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <div className="text-[10px] font-mono uppercase tracking-widest text-amber-300">
          <Users size={12} className="inline mr-1" /> {prospects.length} prospects
        </div>
        <Button size="sm" onClick={() => setAddOpen(true)} className="bg-amber-500 hover:bg-amber-400 text-black"
          data-testid="lighthouse-add-prospect-btn">
          <Plus size={13} className="mr-1" /> Add Prospect
        </Button>
      </div>

      {prospects.length === 0 ? (
        <Card className="p-8 text-center bg-slate-900/60 border-white/10">
          <Lightbulb size={22} className="mx-auto text-slate-600 mb-2" />
          <div className="text-xs text-slate-500">
            No prospects yet. Add one manually or share your <b>public interest form</b> to capture inbound leads.
          </div>
        </Card>
      ) : (
        <Card className="p-0 bg-slate-900/60 border-white/10 overflow-hidden">
          <table className="w-full text-xs" data-testid="lighthouse-prospects-table">
            <thead className="bg-black/40 text-slate-400 font-mono uppercase tracking-wider">
              <tr>
                <th className="px-3 py-2 text-left">Company</th>
                <th className="px-3 py-2 text-left">Contact</th>
                <th className="px-3 py-2 text-left">Current TMS</th>
                <th className="px-3 py-2 text-right">Loads/mo</th>
                <th className="px-3 py-2 text-left">Source</th>
                <th className="px-3 py-2 text-left">Stage</th>
                <th className="px-3 py-2 text-left">Created</th>
              </tr>
            </thead>
            <tbody>
              {prospects.map((p) => (
                <tr key={p.prospect_id}
                  onClick={() => setSelected(p)}
                  className="border-t border-white/5 hover:bg-white/[0.02] cursor-pointer"
                  data-testid={`lighthouse-prospect-row-${p.prospect_id}`}>
                  <td className="px-3 py-2 text-slate-100 font-medium">{p.company_name}</td>
                  <td className="px-3 py-2 text-slate-400">{p.contact_name || "—"}</td>
                  <td className="px-3 py-2 text-slate-400">{p.current_tms || "—"}</td>
                  <td className="px-3 py-2 text-right text-slate-200 font-mono">{fmt(p.monthly_loads || 0)}</td>
                  <td className="px-3 py-2 text-slate-400">{p.source || "—"}</td>
                  <td className="px-3 py-2">
                    <span className={`px-2 py-0.5 rounded-full text-[9px] font-mono uppercase border ${STAGE_META[p.stage]?.ring || ""}`}>
                      {STAGE_META[p.stage]?.label || p.stage}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-slate-500 font-mono text-[10px]">{p.created_at?.slice(0, 10)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      <AddProspectDialog open={addOpen} onClose={() => setAddOpen(false)} onSaved={onChange} />
      <ProspectDetailDialog prospect={selected} assets={assets} onClose={() => setSelected(null)} onChange={onChange} />
    </div>
  );
}

function AddProspectDialog({ open, onClose, onSaved }) {
  const [form, setForm] = useState({
    company_name: "", contact_name: "", contact_email: "", contact_phone: "",
    contact_title: "", company_size: "", current_tms: "", monthly_loads: "",
    fleet_size: "", source: "referral", stage: "curious", notes: "",
  });
  const [busy, setBusy] = useState(false);
  const save = async () => {
    if (!form.company_name.trim()) { toast.error("Company required"); return; }
    setBusy(true);
    try {
      const payload = { ...form };
      ["monthly_loads", "fleet_size"].forEach((k) => {
        payload[k] = payload[k] === "" ? undefined : Number(payload[k]);
      });
      Object.keys(payload).forEach((k) => (payload[k] === "" || payload[k] === undefined) && delete payload[k]);
      await api.post("/lighthouse/prospects", payload);
      toast.success(`Added ${form.company_name}`);
      onSaved?.(); onClose?.();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    finally { setBusy(false); }
  };
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose?.()}>
      <DialogContent className="max-w-2xl bg-slate-950 border-white/10 max-h-[90vh] overflow-y-auto"
        data-testid="lighthouse-add-modal">
        <DialogHeader>
          <DialogTitle className="text-amber-100">
            <Lightbulb size={16} className="inline mr-2" /> Add TMS Prospect
          </DialogTitle>
          <DialogDescription className="text-slate-400 text-xs">
            Manual add. Public inbound leads land automatically via the public interest form.
          </DialogDescription>
        </DialogHeader>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <FF label="Company Name *">
            <Input value={form.company_name} onChange={(e) => setForm({ ...form, company_name: e.target.value })}
              className="bg-black/40 border-white/10 h-8 text-xs" data-testid="lighthouse-form-company" />
          </FF>
          <FF label="Current TMS">
            <Input value={form.current_tms} onChange={(e) => setForm({ ...form, current_tms: e.target.value })}
              className="bg-black/40 border-white/10 h-8 text-xs" placeholder="McLeod, MercuryGate, spreadsheet…" />
          </FF>
          <FF label="Contact Name">
            <Input value={form.contact_name} onChange={(e) => setForm({ ...form, contact_name: e.target.value })}
              className="bg-black/40 border-white/10 h-8 text-xs" />
          </FF>
          <FF label="Contact Title">
            <Input value={form.contact_title} onChange={(e) => setForm({ ...form, contact_title: e.target.value })}
              placeholder="VP Ops, Head of Logistics…"
              className="bg-black/40 border-white/10 h-8 text-xs" />
          </FF>
          <FF label="Contact Email">
            <Input type="email" value={form.contact_email} onChange={(e) => setForm({ ...form, contact_email: e.target.value })}
              className="bg-black/40 border-white/10 h-8 text-xs" />
          </FF>
          <FF label="Contact Phone">
            <Input value={form.contact_phone} onChange={(e) => setForm({ ...form, contact_phone: e.target.value })}
              className="bg-black/40 border-white/10 h-8 text-xs" />
          </FF>
          <FF label="Monthly loads">
            <Input type="number" value={form.monthly_loads}
              onChange={(e) => setForm({ ...form, monthly_loads: e.target.value })}
              className="bg-black/40 border-white/10 h-8 text-xs" />
          </FF>
          <FF label="Fleet size">
            <Input type="number" value={form.fleet_size}
              onChange={(e) => setForm({ ...form, fleet_size: e.target.value })}
              className="bg-black/40 border-white/10 h-8 text-xs" />
          </FF>
          <FF label="Source">
            <select value={form.source} onChange={(e) => setForm({ ...form, source: e.target.value })}
              className="w-full bg-black/40 border border-white/10 rounded px-2 py-1.5 text-xs text-slate-100">
              <option>website</option>
              <option>referral</option>
              <option>linkedin</option>
              <option>outbound</option>
              <option>event</option>
              <option>partner</option>
            </select>
          </FF>
          <FF label="Stage">
            <select value={form.stage} onChange={(e) => setForm({ ...form, stage: e.target.value })}
              className="w-full bg-black/40 border border-white/10 rounded px-2 py-1.5 text-xs text-slate-100">
              {Object.entries(STAGE_META).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
            </select>
          </FF>
          <FF label="Notes" className="md:col-span-2">
            <Textarea rows={3} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })}
              className="bg-black/40 border-white/10 text-xs" />
          </FF>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={save} disabled={busy} className="bg-amber-500 hover:bg-amber-400 text-black"
            data-testid="lighthouse-form-save">
            {busy ? <Loader2 size={13} className="animate-spin mr-1" /> : <CheckCircle2 size={13} className="mr-1" />}
            Save Prospect
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function ProspectDetailDialog({ prospect, assets, onClose, onChange }) {
  const [detail, setDetail] = useState(null);
  const [touchForm, setTouchForm] = useState({ kind: "call", summary: "" });
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (!prospect) return;
    try {
      const { data } = await api.get(`/lighthouse/prospects/${prospect.prospect_id}`);
      setDetail(data);
    } catch (e) { /* no-op */ }
  }, [prospect]);
  useEffect(() => { load(); }, [load]);

  if (!prospect) return null;

  const move = async (stage) => {
    try {
      await api.post(`/lighthouse/prospects/${prospect.prospect_id}/stage`, { stage });
      toast.success(`Moved to ${STAGE_META[stage].label}`);
      onChange?.(); load();
    } catch (e) { toast.error("Failed"); }
  };

  const logTouch = async () => {
    if (!touchForm.summary.trim()) { toast.error("Summary required"); return; }
    setBusy(true);
    try {
      await api.post(`/lighthouse/prospects/${prospect.prospect_id}/touch`, touchForm);
      toast.success("Logged");
      setTouchForm({ ...touchForm, summary: "" });
      load();
    } catch (e) { toast.error("Failed"); }
    finally { setBusy(false); }
  };

  const del = async () => {
    if (!window.confirm(`Delete ${prospect.company_name}?`)) return;
    try {
      await api.delete(`/lighthouse/prospects/${prospect.prospect_id}`);
      toast.success("Deleted");
      onChange?.(); onClose?.();
    } catch (e) { toast.error("Failed"); }
  };

  const downloadAsset = async (kind) => {
    const token = getStoredToken();
    try {
      const res = await fetch(
        `${BACKEND_URL}/api/lighthouse/assets/${kind}.pdf?prospect_id=${prospect.prospect_id}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      window.open(URL.createObjectURL(blob), "_blank");
      toast.success("Delivered · touch logged");
      load();
    } catch (e) { toast.error("Download failed"); }
  };

  return (
    <Dialog open={!!prospect} onOpenChange={(o) => !o && onClose?.()}>
      <DialogContent className="max-w-4xl bg-slate-950 border-white/10 max-h-[92vh] overflow-y-auto"
        data-testid="lighthouse-detail-modal">
        <DialogHeader>
          <DialogTitle className="text-amber-100 flex items-center gap-2">
            {prospect.company_name}
            <span className={`px-2 py-0.5 rounded-full text-[9px] font-mono uppercase border ${STAGE_META[prospect.stage]?.ring}`}>
              {STAGE_META[prospect.stage]?.label}
            </span>
          </DialogTitle>
          <DialogDescription className="text-slate-400 text-xs">
            {prospect.contact_name || "—"} · {prospect.contact_title || "—"} · {prospect.current_tms ? `on ${prospect.current_tms}` : "no current TMS"}
          </DialogDescription>
        </DialogHeader>

        {/* Stage mover */}
        <div className="flex flex-wrap gap-2">
          {Object.keys(STAGE_META).map((k) => (
            <button key={k} onClick={() => move(k)}
              data-testid={`lighthouse-move-${k}`}
              className={`px-3 py-1 rounded-full text-[10px] font-mono uppercase tracking-wider border transition ${
                prospect.stage === k ? STAGE_META[k].ring : "border-white/10 text-slate-500 hover:border-white/30"
              }`}>
              {STAGE_META[k].label}
            </button>
          ))}
          <Button size="sm" variant="ghost" onClick={del}
            className="ml-auto h-7 px-2 text-red-400 hover:text-red-200"
            data-testid="lighthouse-detail-delete">
            <Trash2 size={12} className="mr-1" /> Delete
          </Button>
        </div>

        {/* Send collateral */}
        <Card className="p-3 bg-slate-900/60 border-white/10">
          <div className="text-[10px] font-mono uppercase tracking-widest text-amber-300 mb-2">
            <Presentation size={11} className="inline mr-1" /> Send Orisei-branded collateral
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
            {assets.map((a) => {
              const Icon = ASSET_ICON[a.kind] || FileDown;
              return (
                <button key={a.kind} onClick={() => downloadAsset(a.kind)}
                  data-testid={`lighthouse-send-asset-${a.kind}`}
                  className="p-2.5 rounded border border-white/10 bg-black/30 hover:border-amber-400/40 hover:bg-amber-500/5 transition text-left">
                  <div className="flex items-center gap-2">
                    <Icon size={14} className="text-amber-300" />
                    <div className="text-xs text-slate-100 font-medium">{a.title}</div>
                  </div>
                  <div className="text-[10px] text-slate-500 mt-1">{a.desc}</div>
                </button>
              );
            })}
          </div>
        </Card>

        {/* Touch log */}
        <Card className="p-3 bg-slate-900/60 border-white/10">
          <div className="text-[10px] font-mono uppercase tracking-widest text-amber-300 mb-2">
            <MessageSquare size={11} className="inline mr-1" /> Touch log · {(detail?.touches || []).length}
          </div>
          <div className="grid grid-cols-1 md:grid-cols-5 gap-2 mb-2">
            <select value={touchForm.kind} onChange={(e) => setTouchForm({ ...touchForm, kind: e.target.value })}
              className="bg-black/40 border border-white/10 rounded px-2 py-1.5 text-xs text-slate-100"
              data-testid="lighthouse-touch-kind">
              <option value="call">Call</option>
              <option value="email">Email</option>
              <option value="meeting">Meeting</option>
              <option value="demo">Demo</option>
              <option value="trial_ping">Trial ping</option>
              <option value="note">Note</option>
            </select>
            <Input value={touchForm.summary} onChange={(e) => setTouchForm({ ...touchForm, summary: e.target.value })}
              placeholder="Summary" className="md:col-span-3 bg-black/40 border-white/10 h-8 text-xs"
              data-testid="lighthouse-touch-summary" />
            <Button size="sm" onClick={logTouch} disabled={busy}
              className="bg-amber-500 hover:bg-amber-400 text-black"
              data-testid="lighthouse-touch-save">
              {busy ? <Loader2 size={13} className="animate-spin" /> : <Plus size={13} />} Log
            </Button>
          </div>
          <div className="space-y-1 max-h-64 overflow-y-auto">
            {(detail?.touches || []).length === 0 && (
              <div className="text-[11px] text-slate-500 text-center py-4">No touches logged yet.</div>
            )}
            {(detail?.touches || []).map((t) => (
              <div key={t.touch_id} className="text-[11px] text-slate-300 border-l-2 border-amber-500/30 pl-2 py-1">
                <span className="text-amber-300 font-mono uppercase text-[9px] tracking-widest mr-2">{t.kind}</span>
                <span className="text-slate-500">{t.created_at?.slice(0, 16).replace("T", " ")}</span>
                <div>{t.summary}</div>
                {t.detail && <div className="text-[10px] text-slate-500 mt-0.5">{t.detail}</div>}
              </div>
            ))}
          </div>
        </Card>

        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Close</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ============================================================
//                    ASSETS TAB
// ============================================================
function AssetsTab({ assets }) {
  const download = async (kind) => {
    const token = getStoredToken();
    try {
      const res = await fetch(`${BACKEND_URL}/api/lighthouse/assets/${kind}.pdf`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      window.open(URL.createObjectURL(blob), "_blank");
    } catch (e) { toast.error("Failed"); }
  };
  return (
    <div className="space-y-4">
      <Card className="p-4 bg-slate-900/60 border-white/10">
        <div className="text-[10px] font-mono uppercase tracking-widest text-amber-300">
          <Presentation size={12} className="inline mr-1" /> Orisei-branded prospect collateral
        </div>
        <div className="text-[11px] text-slate-500 mt-1">
          Every asset is auto-branded with your active brand kit (logo, colors, letterhead).
          When you send from a prospect card, the download auto-logs as a touch.
        </div>
      </Card>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3" data-testid="lighthouse-assets-grid">
        {assets.map((a) => {
          const Icon = ASSET_ICON[a.kind] || FileDown;
          return (
            <Card key={a.kind} className="p-4 bg-slate-900/60 border-white/10 space-y-3"
              data-testid={`lighthouse-asset-${a.kind}`}>
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-amber-500/15 border border-amber-400/40 flex items-center justify-center">
                  <Icon size={18} className="text-amber-300" />
                </div>
                <div>
                  <div className="text-sm text-slate-100 font-medium">{a.title}</div>
                  <div className="text-[10px] text-slate-500 font-mono uppercase tracking-widest">{a.audience}</div>
                </div>
              </div>
              <div className="text-[11px] text-slate-400 leading-relaxed">{a.desc}</div>
              <Button size="sm" onClick={() => download(a.kind)} className="w-full bg-amber-500 hover:bg-amber-400 text-black"
                data-testid={`lighthouse-asset-dl-${a.kind}`}>
                <FileDown size={12} className="mr-1" /> Preview PDF
              </Button>
            </Card>
          );
        })}
      </div>
    </div>
  );
}

// ============================================================
//                    PUBLIC LANDING SHARE
// ============================================================
function PublicTab() {
  const [copied, setCopied] = useState(false);
  const publicUrl = `${window.location.origin}/tour`;
  const copyLink = () => {
    navigator.clipboard.writeText(publicUrl);
    setCopied(true);
    toast.success("Link copied");
    setTimeout(() => setCopied(false), 3000);
  };
  return (
    <div className="space-y-4">
      <Card className="p-6 bg-slate-900/60 border-white/10 space-y-4">
        <div className="flex items-center gap-3">
          <ExternalLink size={20} className="text-amber-300" />
          <div>
            <div className="text-sm text-slate-100 font-medium">Public tour landing page</div>
            <div className="text-[11px] text-slate-500">Share this link anywhere — LinkedIn, cold emails, event follow-ups. Any submission becomes a CURIOUS prospect.</div>
          </div>
        </div>
        <div className="p-3 bg-black/40 border border-amber-400/30 rounded flex items-center justify-between">
          <span className="text-xs font-mono text-amber-100 truncate mr-2">{publicUrl}</span>
          <div className="flex gap-1">
            <Button size="sm" onClick={copyLink} variant="secondary" data-testid="lighthouse-copy-tour-link">
              {copied ? <CheckCircle2 size={12} className="mr-1" /> : <Send size={12} className="mr-1" />}
              {copied ? "Copied" : "Copy"}
            </Button>
            <a href={publicUrl} target="_blank" rel="noreferrer"
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md text-xs font-semibold bg-amber-500 text-black hover:bg-amber-400 transition"
              data-testid="lighthouse-open-tour-link">
              <ExternalLink size={12} /> Open
            </a>
          </div>
        </div>
      </Card>
      <Card className="p-4 bg-slate-900/60 border-white/10">
        <div className="text-[10px] font-mono uppercase tracking-widest text-amber-300 mb-2">How the funnel works</div>
        <ol className="text-xs text-slate-300 space-y-1.5 list-decimal list-inside">
          <li>Prospect visits <span className="text-amber-300 font-mono">/tour</span> and submits the interest form.</li>
          <li>A CURIOUS prospect lands in your funnel automatically, with UTM tracking.</li>
          <li>Send Orisei-branded collateral from the prospect card (each send = tracked touch).</li>
          <li>Move stages: <span className="text-cyan-300">ENGAGED</span> → <span className="text-violet-300">DEMO SCHEDULED</span> → <span className="text-amber-300">TRIAL</span> → <span className="text-emerald-300">WON</span>.</li>
          <li>When they convert, promote to a full <b>Shipper Relations</b> account.</li>
        </ol>
      </Card>
    </div>
  );
}

// ============================================================
//                    SHARED UI
// ============================================================
function BigKpi({ label, value, accent, icon: Icon, sub }) {
  return (
    <Card className="p-4 bg-slate-900/60 border-white/10">
      <div className="flex items-center justify-between">
        <div className="text-[10px] font-mono uppercase tracking-widest text-slate-500">{label}</div>
        {Icon && <Icon size={13} style={{ color: accent }} />}
      </div>
      <div className="text-2xl md:text-3xl font-mono mt-1" style={{ color: accent }}>{value}</div>
      {sub && <div className="text-[10px] text-slate-500 mt-0.5">{sub}</div>}
    </Card>
  );
}
function FF({ label, children, className }) {
  return (
    <div className={className}>
      <div className="text-[9px] font-mono uppercase tracking-widest text-slate-500 mb-1">{label}</div>
      {children}
    </div>
  );
}
function Loader() {
  return (
    <div className="p-8 text-center text-xs text-slate-500">
      <Loader2 size={16} className="animate-spin inline mr-2" /> Loading…
    </div>
  );
}
function fmt(n) {
  return Number(n || 0).toLocaleString("en-US", { maximumFractionDigits: 0 });
}
function fmtM(n) {
  const v = Number(n) || 0;
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `${(v / 1_000).toFixed(0)}K`;
  return v.toLocaleString("en-US", { maximumFractionDigits: 0 });
}
