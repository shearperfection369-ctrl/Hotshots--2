import React, { useCallback, useEffect, useMemo, useState } from "react";
import Topbar from "../components/Topbar";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Badge } from "../components/ui/badge";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "../components/ui/dialog";
import {
  ShieldAlert, ShieldCheck, FileWarning, Camera, Clock, DollarSign, TrendingDown,
  AlertTriangle, CheckCircle2, XCircle, Zap, Users, PiggyBank, ClipboardList,
  MessageSquare, FileDown, Plus, RefreshCw, Loader2, Trash2, Sparkles,
  Radio, Ban, Award, Truck, ExternalLink,
} from "lucide-react";
import { api, BACKEND_URL } from "../lib/api";
import { useBranding, useBrandRefresh } from "../lib/branding";
import { CarrierCombobox } from "../components/CarrierCombobox";
import { toast } from "sonner";

/**
 * ClaimsMaster — Orisei-branded claim tracking + resolution workflow.
 * Prevention-first (checklist + COI verification), swift-resolution
 * (24-hr SLA, fast-pay decisions, Orisei-branded incident reports).
 */
const STATUS_META = {
  new:           { label: "NEW",           color: "#EF4444", ring: "border-red-400/40 text-red-200 bg-red-500/10" },
  acknowledged:  { label: "ACK",           color: "#F59E0B", ring: "border-amber-400/40 text-amber-200 bg-amber-500/10" },
  investigating: { label: "INVESTIGATING", color: "#22D3EE", ring: "border-cyan-400/40 text-cyan-200 bg-cyan-500/10" },
  decision:      { label: "DECISION",      color: "#A78BFA", ring: "border-violet-400/40 text-violet-200 bg-violet-500/10" },
  paid:          { label: "PAID",          color: "#10B981", ring: "border-emerald-400/40 text-emerald-200 bg-emerald-500/10" },
  denied:        { label: "DENIED",        color: "#64748B", ring: "border-slate-400/40 text-slate-200 bg-slate-500/10" },
  closed:        { label: "CLOSED",        color: "#94A3B8", ring: "border-slate-400/40 text-slate-300 bg-slate-500/10" },
};

const KIND_META = {
  damage:        { label: "Damage",        icon: FileWarning },
  shortage:      { label: "Shortage",      icon: AlertTriangle },
  loss:          { label: "Loss",          icon: XCircle },
  delay:         { label: "Delay",         icon: Clock },
  refused:       { label: "Refused",       icon: Ban },
  contamination: { label: "Contamination", icon: ShieldAlert },
  other:         { label: "Other",         icon: FileWarning },
};

const TABS = [
  { id: "deck",       label: "Command Deck",  icon: Radio },
  { id: "claims",     label: "Active Claims", icon: FileWarning },
  { id: "prevention", label: "Prevention",    icon: ShieldCheck },
  { id: "watchlist",  label: "Carrier Watchlist", icon: Ban },
  { id: "coi",        label: "Insurance COI", icon: Award },
  { id: "reserve",    label: "Claims Reserve", icon: PiggyBank },
];

export default function ClaimsMaster() {
  const { brand } = useBranding();
  const [tab, setTab] = useState("deck");
  const [dashboard, setDashboard] = useState(null);
  const [claims, setClaims] = useState([]);
  const [busy, setBusy] = useState(false);

  const loadAll = useCallback(async () => {
    setBusy(true);
    try {
      const [d, c] = await Promise.all([
        api.get("/claims/dashboard"),
        api.get("/claims/claims"),
      ]);
      setDashboard(d.data);
      setClaims(c.data.items || []);
    } catch (e) {
      toast.error("Failed to load claims");
    } finally { setBusy(false); }
  }, []);
  useEffect(() => { loadAll(); }, [loadAll]);
  useBrandRefresh(() => loadAll());

  const brandShort = brand?.short_name || "Orisei";
  const primary = brand?.primary_color || "#22D3EE";

  return (
    <>
      <Topbar
        title={`${brandShort} · Claims Master`}
        subtitle="Prevention-first · 24-hr SLA · Orisei-branded incident reports"
      />
      <div className="p-4 md:p-6 space-y-4">
        <div className="flex flex-wrap items-center gap-2" data-testid="claims-master-header">
          <ShieldAlert size={22} style={{ color: primary }} />
          <div className="text-slate-100 font-medium">Claims Master · {brandShort}</div>
          <Badge className="bg-red-500/15 text-red-200 border border-red-400/30">24-HR SLA · FAST-PAY</Badge>
          <div className="ml-auto">
            <Button variant="secondary" size="sm" onClick={loadAll} disabled={busy}
              data-testid="claims-refresh">
              {busy ? <Loader2 size={13} className="animate-spin mr-1" /> : <RefreshCw size={13} className="mr-1" />}
              Refresh
            </Button>
          </div>
        </div>

        <div className="flex gap-1.5 overflow-x-auto pb-1" data-testid="claims-tabs">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              data-testid={`claims-tab-${id}`}
              className={`inline-flex items-center gap-2 px-4 py-2 rounded text-xs font-mono uppercase tracking-wider transition border whitespace-nowrap ${
                tab === id
                  ? "bg-cyan-500 text-black border-cyan-400 shadow-[0_0_20px_rgba(34,211,238,0.35)]"
                  : "border-white/10 text-slate-400 hover:border-cyan-400/40 hover:text-cyan-200"
              }`}
            >
              <Icon size={13} /> {label}
            </button>
          ))}
        </div>

        {tab === "deck"       && <CommandDeck dashboard={dashboard} claims={claims} onRefresh={loadAll} />}
        {tab === "claims"     && <ClaimsTab claims={claims} onRefresh={loadAll} />}
        {tab === "prevention" && <PreventionTab onRefresh={loadAll} />}
        {tab === "watchlist"  && <WatchlistTab />}
        {tab === "coi"        && <CoiTab />}
        {tab === "reserve"    && <ReserveTab dashboard={dashboard} />}
      </div>
    </>
  );
}

// ============================================================
//                     COMMAND DECK
// ============================================================
function CommandDeck({ dashboard, claims, onRefresh }) {
  const [fileOpen, setFileOpen] = useState(false);
  if (!dashboard) return <Loader />;
  const { totals, by_status, by_kind, top_shippers, carrier_watchlist, reserve } = dashboard;
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="claims-kpi-strip">
        <BigKpi label="Total Claims" value={totals.claims_total} accent="#22D3EE" icon={FileWarning}
          sub={`${Object.keys(by_kind).length} kinds`} />
        <BigKpi label="Open Exposure" value={`$${fmt(totals.open_claims_usd)}`} accent="#F59E0B" icon={TrendingDown} sub="unresolved" />
        <BigKpi label="Paid YTD" value={`$${fmt(totals.paid_claims_usd)}`} accent="#10B981" icon={CheckCircle2} sub="fast-pay wins" />
        <BigKpi label="SLA Breached" value={totals.sla_breached} accent="#EF4444" icon={AlertTriangle} sub="> 24h no ack" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <Card className="md:col-span-2 p-4 bg-slate-900/60 border-white/10">
          <div className="flex items-center justify-between mb-3">
            <div className="text-[10px] font-mono uppercase tracking-widest text-cyan-300">
              Claims by status
            </div>
            <Button size="sm" onClick={() => setFileOpen(true)} className="bg-red-500 hover:bg-red-400 text-white"
              data-testid="claims-file-btn">
              <Plus size={13} className="mr-1" /> File New Claim
            </Button>
          </div>
          <StatusBars byStatus={by_status} />
        </Card>
        <Card className="p-4 bg-slate-900/60 border-white/10">
          <div className="text-[10px] font-mono uppercase tracking-widest text-cyan-300 mb-3">Reserve suggestion</div>
          <div className="text-3xl font-mono text-amber-300">
            ${fmt(reserve.recommended_reserve_usd_low)}<span className="text-slate-500 text-lg"> – </span>${fmt(reserve.recommended_reserve_usd_high)}
          </div>
          <div className="text-[10px] text-slate-500 mt-1">
            2–3% of ${fmt(reserve.monthly_avg_revenue_usd)} avg monthly rev
          </div>
          <div className="text-[10px] text-slate-400 mt-2 leading-relaxed">
            {reserve.reasoning}
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <Card className="p-0 bg-slate-900/60 border-white/10 overflow-hidden">
          <div className="px-3 py-2 border-b border-white/10 text-[10px] font-mono uppercase tracking-widest text-cyan-300">
            <Users size={12} className="inline mr-1" /> Top shippers by claim count
          </div>
          {top_shippers.length === 0 ? (
            <div className="p-6 text-center text-xs text-slate-500">No claims filed yet.</div>
          ) : (
            <table className="w-full text-xs">
              <thead className="bg-black/40 text-slate-400 font-mono uppercase tracking-wider">
                <tr>
                  <th className="px-3 py-2 text-left">Shipper</th>
                  <th className="px-3 py-2 text-right">Count</th>
                  <th className="px-3 py-2 text-right">Total $</th>
                </tr>
              </thead>
              <tbody>
                {top_shippers.map((s, i) => (
                  <tr key={i} className="border-t border-white/5">
                    <td className="px-3 py-2 text-slate-100">{s.shipper_name}</td>
                    <td className="px-3 py-2 text-right text-slate-200 font-mono">{s.claims_count}</td>
                    <td className="px-3 py-2 text-right text-red-300 font-mono">${fmt(s.total_claim_usd)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>

        <Card className="p-0 bg-slate-900/60 border-white/10 overflow-hidden">
          <div className="px-3 py-2 border-b border-white/10 text-[10px] font-mono uppercase tracking-widest text-cyan-300">
            <Ban size={12} className="inline mr-1" /> Carrier watchlist (2+ claims = cut)
          </div>
          {carrier_watchlist.length === 0 ? (
            <div className="p-6 text-center text-xs text-slate-500">Clean roster — no repeat offenders.</div>
          ) : (
            <table className="w-full text-xs">
              <thead className="bg-black/40 text-slate-400 font-mono uppercase tracking-wider">
                <tr>
                  <th className="px-3 py-2 text-left">Carrier</th>
                  <th className="px-3 py-2 text-right">Claims</th>
                  <th className="px-3 py-2 text-right">$ exposure</th>
                </tr>
              </thead>
              <tbody>
                {carrier_watchlist.map((c, i) => (
                  <tr key={i} className="border-t border-white/5 text-red-200">
                    <td className="px-3 py-2 font-medium">{c.carrier_name} <span className="text-slate-500 text-[10px]">MC {c.carrier_mc}</span></td>
                    <td className="px-3 py-2 text-right font-mono">{c.claims_count}</td>
                    <td className="px-3 py-2 text-right font-mono">${fmt(c.total_claim_usd)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      </div>

      <FileClaimDialog open={fileOpen} onClose={() => setFileOpen(false)} onSaved={onRefresh} />
    </div>
  );
}

function StatusBars({ byStatus }) {
  const total = Math.max(1, Object.values(byStatus || {}).reduce((s, v) => s + v, 0));
  const order = ["new", "acknowledged", "investigating", "decision", "paid", "denied", "closed"];
  return (
    <div className="space-y-2">
      {order.map((k) => {
        const v = byStatus?.[k] || 0;
        const pct = (v / total) * 100;
        const meta = STATUS_META[k];
        return (
          <div key={k} className="flex items-center gap-3">
            <div className="w-32 text-[10px] font-mono uppercase tracking-widest" style={{ color: meta.color }}>
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
//                     CLAIMS TAB
// ============================================================
function ClaimsTab({ claims, onRefresh }) {
  const [selected, setSelected] = useState(null);
  const [fileOpen, setFileOpen] = useState(false);
  const [filter, setFilter] = useState("all");

  const filtered = useMemo(() => {
    if (filter === "all") return claims;
    if (filter === "sla_breached") return claims.filter((c) => c.sla_breached);
    return claims.filter((c) => c.status === filter);
  }, [claims, filter]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2 items-center">
        {["all", "sla_breached", "new", "acknowledged", "investigating", "paid"].map((f) => (
          <button key={f} onClick={() => setFilter(f)}
            data-testid={`claims-filter-${f}`}
            className={`px-3 py-1 rounded-full text-[10px] font-mono uppercase tracking-widest border transition ${
              filter === f ? "bg-cyan-500/15 border-cyan-400 text-cyan-100" : "border-white/10 text-slate-400 hover:border-cyan-400/40"
            }`}>
            {f.replace("_", " ")}
          </button>
        ))}
        <Button size="sm" onClick={() => setFileOpen(true)} className="bg-red-500 hover:bg-red-400 text-white ml-auto"
          data-testid="claims-file-btn-tab">
          <Plus size={13} className="mr-1" /> File Claim
        </Button>
      </div>

      {filtered.length === 0 ? (
        <Card className="p-8 text-center bg-slate-900/60 border-white/10">
          <FileWarning size={22} className="mx-auto text-slate-600 mb-2" />
          <div className="text-xs text-slate-500">No claims match this filter.</div>
        </Card>
      ) : (
        <Card className="p-0 bg-slate-900/60 border-white/10 overflow-hidden">
          <table className="w-full text-xs" data-testid="claims-table">
            <thead className="bg-black/40 text-slate-400 font-mono uppercase tracking-wider">
              <tr>
                <th className="px-3 py-2 text-left">Claim</th>
                <th className="px-3 py-2 text-left">Shipper</th>
                <th className="px-3 py-2 text-left">Carrier</th>
                <th className="px-3 py-2 text-left">Kind</th>
                <th className="px-3 py-2 text-right">Amount</th>
                <th className="px-3 py-2 text-left">Status</th>
                <th className="px-3 py-2 text-left">SLA</th>
                <th className="px-3 py-2 text-left">Filed</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((c) => {
                const KindIcon = KIND_META[c.kind]?.icon || FileWarning;
                const statusMeta = STATUS_META[c.status] || STATUS_META.new;
                return (
                  <tr key={c.claim_id}
                    onClick={() => setSelected(c)}
                    className="border-t border-white/5 hover:bg-white/[0.03] cursor-pointer"
                    data-testid={`claims-row-${c.claim_id}`}>
                    <td className="px-3 py-2 text-slate-100 font-mono">{c.claim_id}</td>
                    <td className="px-3 py-2 text-slate-200">{c.shipper_name}</td>
                    <td className="px-3 py-2 text-slate-400">{c.carrier_name || "—"}</td>
                    <td className="px-3 py-2 text-slate-300"><KindIcon size={11} className="inline mr-1" />{KIND_META[c.kind]?.label || c.kind}</td>
                    <td className="px-3 py-2 text-right text-red-300 font-mono">${fmt(c.claim_amount_usd)}</td>
                    <td className="px-3 py-2">
                      <span className={`px-2 py-0.5 rounded-full text-[9px] font-mono uppercase border ${statusMeta.ring}`}>
                        {statusMeta.label}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-[10px] font-mono">
                      {c.sla_hours_remaining == null ? (
                        <span className="text-slate-500">ACK</span>
                      ) : c.sla_breached ? (
                        <span className="text-red-400">BREACHED · {Math.abs(c.sla_hours_remaining).toFixed(1)}h</span>
                      ) : (
                        <span className="text-amber-300">{c.sla_hours_remaining.toFixed(1)}h left</span>
                      )}
                    </td>
                    <td className="px-3 py-2 text-slate-500 font-mono text-[10px]">{c.filed_at?.slice(0, 10)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </Card>
      )}

      <FileClaimDialog open={fileOpen} onClose={() => setFileOpen(false)} onSaved={onRefresh} />
      <ClaimDetailDialog claim={selected} onClose={() => setSelected(null)} onChange={() => { onRefresh(); }} />
    </div>
  );
}

// ============================================================
//                     FILE CLAIM DIALOG
// ============================================================
function FileClaimDialog({ open, onClose, onSaved }) {
  const [form, setForm] = useState({
    shipper_name: "", carrier_mc: "", carrier_name: "", load_reference: "",
    origin: "", destination: "", kind: "damage",
    claim_amount_usd: "", incident_at: new Date().toISOString().slice(0, 10),
    discovered_at: new Date().toISOString().slice(0, 10),
    description: "", shipper_contact_email: "", reported_by: "",
  });
  const [busy, setBusy] = useState(false);
  const save = async () => {
    if (!form.shipper_name.trim() || !form.description.trim() || !form.claim_amount_usd) {
      toast.error("Shipper, amount, description all required");
      return;
    }
    setBusy(true);
    try {
      const payload = { ...form, claim_amount_usd: Number(form.claim_amount_usd) };
      Object.keys(payload).forEach((k) => payload[k] === "" && delete payload[k]);
      const { data } = await api.post("/claims/claims", payload);
      toast.success(`Filed claim ${data.claim_id} · 24-hr SLA started`);
      setForm({ ...form, shipper_name: "", carrier_mc: "", carrier_name: "", claim_amount_usd: "", description: "" });
      onSaved?.(); onClose?.();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    finally { setBusy(false); }
  };
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose?.()}>
      <DialogContent className="max-w-2xl bg-slate-950 border-white/10 max-h-[90vh] overflow-y-auto"
        data-testid="claims-file-modal">
        <DialogHeader>
          <DialogTitle className="text-red-200">
            <FileWarning size={16} className="inline mr-2" /> File New Claim
          </DialogTitle>
          <DialogDescription className="text-slate-400 text-xs">
            The 24-hour acknowledgment SLA starts immediately. Silence = shipper churn.
          </DialogDescription>
        </DialogHeader>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <FF label="Shipper Name *">
            <Input value={form.shipper_name} onChange={(e) => setForm({ ...form, shipper_name: e.target.value })}
              className="bg-black/40 border-white/10 h-8 text-xs" data-testid="claims-form-shipper" />
          </FF>
          <FF label="Load / Booking ref">
            <Input value={form.load_reference} onChange={(e) => setForm({ ...form, load_reference: e.target.value })}
              className="bg-black/40 border-white/10 h-8 text-xs" placeholder="ORI-88231" />
          </FF>
          <FF label="Carrier Name">
            <CarrierCombobox value={form.carrier_name} onChange={(v) => setForm({ ...form, carrier_name: v })}
              onSelect={(rec) => setForm((f) => ({ ...f, carrier_name: rec.name, carrier_mc: rec.mc || f.carrier_mc }))}
              testid="claims-carrier-combobox" className="bg-black/40 border-white/10 h-8 text-xs" />
          </FF>
          <FF label="Carrier MC #">
            <Input value={form.carrier_mc} onChange={(e) => setForm({ ...form, carrier_mc: e.target.value })}
              className="bg-black/40 border-white/10 h-8 text-xs" />
          </FF>
          <FF label="Origin">
            <Input value={form.origin} onChange={(e) => setForm({ ...form, origin: e.target.value })}
              className="bg-black/40 border-white/10 h-8 text-xs" />
          </FF>
          <FF label="Destination">
            <Input value={form.destination} onChange={(e) => setForm({ ...form, destination: e.target.value })}
              className="bg-black/40 border-white/10 h-8 text-xs" />
          </FF>
          <FF label="Kind">
            <select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}
              className="w-full bg-black/40 border border-white/10 rounded px-2 py-1.5 text-xs text-slate-100"
              data-testid="claims-form-kind">
              {Object.entries(KIND_META).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
            </select>
          </FF>
          <FF label="Claim Amount (USD) *">
            <Input type="number" step="0.01" value={form.claim_amount_usd}
              onChange={(e) => setForm({ ...form, claim_amount_usd: e.target.value })}
              className="bg-black/40 border-white/10 h-8 text-xs" data-testid="claims-form-amount" />
          </FF>
          <FF label="Incident date">
            <Input type="date" value={form.incident_at} onChange={(e) => setForm({ ...form, incident_at: e.target.value })}
              className="bg-black/40 border-white/10 h-8 text-xs" />
          </FF>
          <FF label="Discovered date">
            <Input type="date" value={form.discovered_at} onChange={(e) => setForm({ ...form, discovered_at: e.target.value })}
              className="bg-black/40 border-white/10 h-8 text-xs" />
          </FF>
          <FF label="Shipper contact email">
            <Input type="email" value={form.shipper_contact_email}
              onChange={(e) => setForm({ ...form, shipper_contact_email: e.target.value })}
              className="bg-black/40 border-white/10 h-8 text-xs" />
          </FF>
          <FF label="Reported by">
            <Input value={form.reported_by} onChange={(e) => setForm({ ...form, reported_by: e.target.value })}
              className="bg-black/40 border-white/10 h-8 text-xs" />
          </FF>
          <FF label="Description *" className="md:col-span-2">
            <Textarea rows={4} value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              className="bg-black/40 border-white/10 text-xs"
              placeholder="What was damaged? When was it discovered? Photos, repair estimates, carrier's side."
              data-testid="claims-form-desc" />
          </FF>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={save} disabled={busy} className="bg-red-500 hover:bg-red-400 text-white"
            data-testid="claims-form-save">
            {busy ? <Loader2 size={13} className="animate-spin mr-1" /> : <FileWarning size={13} className="mr-1" />}
            File Claim (start 24-hr SLA)
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ============================================================
//                     CLAIM DETAIL DIALOG
// ============================================================
function ClaimDetailDialog({ claim, onClose, onChange }) {
  const [detail, setDetail] = useState(null);
  const [commForm, setCommForm] = useState({ channel: "email", direction: "outbound", with_party: "shipper", summary: "" });
  const [decisionForm, setDecisionForm] = useState({ outcome: "fast_pay", payout_usd: "", reasoning: "", evidence_summary: "" });
  const [decisionOpen, setDecisionOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [photoBusy, setPhotoBusy] = useState(false);

  const load = useCallback(async () => {
    if (!claim) return;
    try {
      const { data } = await api.get(`/claims/claims/${claim.claim_id}`);
      setDetail(data);
    } catch (e) { /* no-op */ }
  }, [claim]);
  useEffect(() => { load(); }, [load]);

  if (!claim) return null;
  const c = detail?.claim || claim;
  const status = STATUS_META[c.status] || STATUS_META.new;

  const acknowledge = async () => {
    try {
      await api.post(`/claims/claims/${claim.claim_id}/acknowledge`, { ack_note: "" });
      toast.success("Acknowledged · SLA timer stopped");
      onChange?.(); load();
    } catch (e) { toast.error("Failed"); }
  };

  const logComm = async () => {
    if (!commForm.summary.trim()) { toast.error("Summary required"); return; }
    setBusy(true);
    try {
      await api.post(`/claims/claims/${claim.claim_id}/comms`, commForm);
      toast.success("Logged");
      setCommForm({ ...commForm, summary: "" });
      load();
    } catch (e) { toast.error("Failed"); } finally { setBusy(false); }
  };

  const submitDecision = async () => {
    if (!decisionForm.reasoning.trim()) { toast.error("Reasoning required"); return; }
    setBusy(true);
    try {
      const payload = { ...decisionForm, payout_usd: Number(decisionForm.payout_usd || 0) };
      await api.post(`/claims/claims/${claim.claim_id}/decision`, payload);
      toast.success(`Decision recorded: ${payload.outcome.toUpperCase()}`);
      setDecisionOpen(false);
      onChange?.(); load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    finally { setBusy(false); }
  };

  const uploadPhoto = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const kind = window.prompt("Photo type: damage · pickup · delivery · seal · other", "damage") || "damage";
    const caption = window.prompt("Caption (optional)", "") || "";
    setPhotoBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("kind", kind);
      fd.append("caption", caption);
      const token = localStorage.getItem("tms_session_token");
      const res = await fetch(`${BACKEND_URL}/api/claims/claims/${claim.claim_id}/photos`, {
        method: "POST", headers: { Authorization: `Bearer ${token}` }, body: fd,
      });
      if (!res.ok) throw new Error(await res.text());
      toast.success("Photo uploaded");
      load();
    } catch (err) { toast.error("Upload failed"); }
    finally { setPhotoBusy(false); e.target.value = ""; }
  };

  const deletePhoto = async (photo_id) => {
    if (!window.confirm("Delete this photo?")) return;
    try {
      await api.delete(`/claims/claims/${claim.claim_id}/photos/${photo_id}`);
      toast.success("Deleted");
      load();
    } catch (e) { toast.error("Failed"); }
  };

  const downloadReport = () => {
    const token = localStorage.getItem("tms_session_token");
    // Cannot pass Authorization on window.open; do a fetch → blob → object URL
    fetch(`${BACKEND_URL}/api/claims/claims/${claim.claim_id}/report.pdf`, {
      headers: { Authorization: `Bearer ${token}` },
    }).then((r) => r.blob()).then((b) => {
      const url = URL.createObjectURL(b);
      window.open(url, "_blank");
    });
  };

  return (
    <Dialog open={!!claim} onOpenChange={(o) => !o && onClose?.()}>
      <DialogContent className="max-w-5xl bg-slate-950 border-white/10 max-h-[92vh] overflow-y-auto"
        data-testid="claims-detail-modal">
        <DialogHeader>
          <DialogTitle className="text-slate-100 flex items-center gap-3">
            <span className="font-mono text-cyan-300">{c.claim_id}</span>
            <span className={`px-2 py-0.5 rounded-full text-[10px] font-mono uppercase border ${status.ring}`}>{status.label}</span>
            <span className="text-red-300 font-mono">${fmt(c.claim_amount_usd)}</span>
          </DialogTitle>
          <DialogDescription className="text-slate-400 text-xs">
            {c.shipper_name} · Carrier {c.carrier_name || "—"} · {c.origin || "—"} → {c.destination || "—"}
          </DialogDescription>
        </DialogHeader>

        {/* SLA banner */}
        {c.sla_breached ? (
          <div className="p-2 rounded bg-red-500/15 border border-red-400/40 text-red-200 text-xs flex items-center gap-2">
            <AlertTriangle size={13} /> SLA BREACHED by {Math.abs(c.sla_hours_remaining || 0).toFixed(1)}h — acknowledge NOW.
          </div>
        ) : c.sla_hours_remaining != null ? (
          <div className="p-2 rounded bg-amber-500/15 border border-amber-400/40 text-amber-200 text-xs flex items-center gap-2">
            <Clock size={13} /> {c.sla_hours_remaining.toFixed(1)}h remaining to acknowledge (24-hr SLA).
          </div>
        ) : null}

        {/* Action bar */}
        <div className="flex flex-wrap gap-2">
          {!c.acknowledged_at && (
            <Button size="sm" onClick={acknowledge} className="bg-amber-500 hover:bg-amber-400 text-black"
              data-testid="claims-ack-btn">
              <CheckCircle2 size={13} className="mr-1" /> Acknowledge
            </Button>
          )}
          {!["paid", "denied", "closed"].includes(c.status) && (
            <Button size="sm" onClick={() => setDecisionOpen(true)} className="bg-violet-500 hover:bg-violet-400 text-white"
              data-testid="claims-decision-btn">
              <Zap size={13} className="mr-1" /> Record Decision
            </Button>
          )}
          <Button size="sm" variant="secondary" onClick={downloadReport} data-testid="claims-report-btn">
            <FileDown size={13} className="mr-1" /> Orisei Incident Report (PDF)
          </Button>
          <label className="inline-flex items-center gap-1 px-3 py-1.5 rounded bg-cyan-500/15 border border-cyan-400/40 text-cyan-100 text-[11px] cursor-pointer hover:bg-cyan-500/25"
            data-testid="claims-photo-upload-label">
            {photoBusy ? <Loader2 size={13} className="animate-spin" /> : <Camera size={13} />}
            Upload Photo
            <input type="file" accept="image/*" hidden onChange={uploadPhoto} disabled={photoBusy} />
          </label>
        </div>

        {/* Details */}
        <Card className="p-3 bg-slate-900/60 border-white/10 space-y-2">
          <div className="text-[10px] font-mono uppercase tracking-widest text-cyan-300">Description</div>
          <div className="text-xs text-slate-300 leading-relaxed">{c.description}</div>
          {c.decision && (
            <div className="mt-2 p-2 border-l-2 border-violet-500/40 bg-violet-500/5">
              <div className="text-[10px] font-mono uppercase tracking-widest text-violet-300">
                Decision · {(c.decision.outcome || "").toUpperCase()} · ${fmt(c.decision.payout_usd)}
              </div>
              <div className="text-[11px] text-slate-300 mt-1">{c.decision.reasoning}</div>
              {c.decision.evidence_summary && (
                <div className="text-[10px] text-slate-500 mt-1"><b>Evidence:</b> {c.decision.evidence_summary}</div>
              )}
            </div>
          )}
        </Card>

        {/* Photos */}
        <Card className="p-3 bg-slate-900/60 border-white/10">
          <div className="text-[10px] font-mono uppercase tracking-widest text-cyan-300 mb-2">
            <Camera size={11} className="inline mr-1" /> Photos · {(detail?.photos || []).length}
          </div>
          {(detail?.photos || []).length === 0 ? (
            <div className="text-[11px] text-slate-500">No photos yet. Upload pickup, damage, and delivery shots.</div>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              {detail.photos.map((p) => (
                <div key={p.photo_id} className="relative group" data-testid={`claim-photo-${p.photo_id}`}>
                  <img
                    src={`${BACKEND_URL}/api/claims/claims/${claim.claim_id}/photos/${p.photo_id}?t=${localStorage.getItem("tms_session_token")}`}
                    alt={p.caption || p.filename}
                    className="w-full aspect-square object-cover rounded border border-white/10 cursor-pointer"
                    onClick={() => {
                      const token = localStorage.getItem("tms_session_token");
                      fetch(`${BACKEND_URL}/api/claims/claims/${claim.claim_id}/photos/${p.photo_id}`, {
                        headers: { Authorization: `Bearer ${token}` },
                      }).then((r) => r.blob()).then((b) => window.open(URL.createObjectURL(b), "_blank"));
                    }}
                  />
                  <div className="absolute top-1 left-1 text-[9px] font-mono uppercase bg-black/70 px-1.5 py-0.5 rounded text-cyan-300">
                    {p.kind}
                  </div>
                  <button onClick={() => deletePhoto(p.photo_id)}
                    data-testid={`claim-photo-del-${p.photo_id}`}
                    className="absolute top-1 right-1 opacity-0 group-hover:opacity-100 bg-red-500/80 text-white rounded p-1 transition">
                    <Trash2 size={10} />
                  </button>
                  {p.caption && (
                    <div className="text-[9px] text-slate-500 mt-1 truncate">{p.caption}</div>
                  )}
                </div>
              ))}
            </div>
          )}
        </Card>

        {/* Communications */}
        <Card className="p-3 bg-slate-900/60 border-white/10">
          <div className="text-[10px] font-mono uppercase tracking-widest text-cyan-300 mb-2">
            <MessageSquare size={11} className="inline mr-1" /> Communications
          </div>
          <div className="grid grid-cols-1 md:grid-cols-5 gap-2 mb-2">
            <select value={commForm.channel} onChange={(e) => setCommForm({ ...commForm, channel: e.target.value })}
              className="bg-black/40 border border-white/10 rounded px-2 py-1.5 text-xs text-slate-100">
              <option value="call">Call</option><option value="email">Email</option>
              <option value="sms">SMS</option><option value="meeting">Meeting</option>
              <option value="note">Note</option>
            </select>
            <select value={commForm.direction} onChange={(e) => setCommForm({ ...commForm, direction: e.target.value })}
              className="bg-black/40 border border-white/10 rounded px-2 py-1.5 text-xs text-slate-100">
              <option value="outbound">Outbound</option><option value="inbound">Inbound</option>
              <option value="internal">Internal</option>
            </select>
            <select value={commForm.with_party} onChange={(e) => setCommForm({ ...commForm, with_party: e.target.value })}
              className="bg-black/40 border border-white/10 rounded px-2 py-1.5 text-xs text-slate-100">
              <option value="shipper">Shipper</option><option value="carrier">Carrier</option>
              <option value="insurer">Insurer</option><option value="internal">Internal</option>
            </select>
            <Input value={commForm.summary} onChange={(e) => setCommForm({ ...commForm, summary: e.target.value })}
              placeholder="Summary" className="bg-black/40 border-white/10 h-8 text-xs md:col-span-1"
              data-testid="claims-comm-summary" />
            <Button size="sm" onClick={logComm} disabled={busy} className="bg-cyan-500 hover:bg-cyan-400 text-black"
              data-testid="claims-comm-save">
              {busy ? <Loader2 size={13} className="animate-spin" /> : <Plus size={13} />} Log
            </Button>
          </div>
          <div className="space-y-1 max-h-64 overflow-y-auto">
            {(detail?.communications || []).length === 0 && (
              <div className="text-[11px] text-slate-500 text-center py-4">No communications logged yet.</div>
            )}
            {(detail?.communications || []).map((cc) => (
              <div key={cc.comm_id} className="text-[11px] text-slate-300 border-l-2 border-cyan-500/30 pl-2 py-1">
                <span className="text-cyan-300 font-mono uppercase text-[9px] tracking-widest mr-2">
                  {cc.channel} · {cc.direction} · {cc.with_party}
                </span>
                <span className="text-slate-500">{cc.created_at?.slice(0, 16).replace("T", " ")}</span>
                <div>{cc.summary}</div>
              </div>
            ))}
          </div>
        </Card>

        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Close</Button>
        </DialogFooter>

        {/* Decision sub-dialog */}
        <Dialog open={decisionOpen} onOpenChange={setDecisionOpen}>
          <DialogContent className="max-w-lg bg-slate-950 border-white/10" data-testid="claims-decision-modal">
            <DialogHeader>
              <DialogTitle className="text-cyan-100">Record Decision</DialogTitle>
              <DialogDescription className="text-slate-400 text-xs">
                Fast-pay preserves relationships. Dispute only with airtight evidence.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-3">
              <FF label="Outcome">
                <select value={decisionForm.outcome} onChange={(e) => setDecisionForm({ ...decisionForm, outcome: e.target.value })}
                  className="w-full bg-black/40 border border-white/10 rounded px-2 py-1.5 text-xs text-slate-100"
                  data-testid="claims-decision-outcome">
                  <option value="fast_pay">Fast-Pay (carrier liable · pay in 48h)</option>
                  <option value="dispute">Dispute (need more investigation)</option>
                  <option value="shipper_fault">Shipper fault (deny with evidence)</option>
                  <option value="force_majeure">Force majeure (weather/act of God)</option>
                </select>
              </FF>
              <FF label="Payout (USD)">
                <Input type="number" step="0.01" value={decisionForm.payout_usd}
                  onChange={(e) => setDecisionForm({ ...decisionForm, payout_usd: e.target.value })}
                  className="bg-black/40 border-white/10 h-8 text-xs"
                  data-testid="claims-decision-payout" />
              </FF>
              <FF label="Reasoning *">
                <Textarea rows={4} value={decisionForm.reasoning}
                  onChange={(e) => setDecisionForm({ ...decisionForm, reasoning: e.target.value })}
                  placeholder="Why this outcome? Docs, photos, timestamps supporting the decision."
                  className="bg-black/40 border-white/10 text-xs"
                  data-testid="claims-decision-reasoning" />
              </FF>
              <FF label="Evidence summary">
                <Textarea rows={2} value={decisionForm.evidence_summary}
                  onChange={(e) => setDecisionForm({ ...decisionForm, evidence_summary: e.target.value })}
                  placeholder="BOL, weight ticket, weather report, carrier email…"
                  className="bg-black/40 border-white/10 text-xs" />
              </FF>
            </div>
            <DialogFooter>
              <Button variant="ghost" onClick={() => setDecisionOpen(false)}>Cancel</Button>
              <Button onClick={submitDecision} disabled={busy} className="bg-violet-500 hover:bg-violet-400 text-white"
                data-testid="claims-decision-save">
                {busy ? <Loader2 size={13} className="animate-spin mr-1" /> : <Zap size={13} className="mr-1" />}
                Record Decision
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </DialogContent>
    </Dialog>
  );
}

// ============================================================
//                     PREVENTION TAB
// ============================================================
function PreventionTab({ onRefresh }) {
  const [checklist, setChecklist] = useState([]);
  const [audits, setAudits] = useState([]);
  const [auditForm, setAuditForm] = useState({});
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [c, a] = await Promise.all([
        api.get("/claims/prevention/checklist"),
        api.get("/claims/prevention/audits"),
      ]);
      setChecklist(c.data.checklist || []);
      setAudits(a.data.items || []);
    } catch (e) { /* no-op */ }
  }, []);
  useEffect(() => { load(); }, [load]);

  const submitAudit = async () => {
    if (!auditForm.load_id?.trim()) { toast.error("Load ID required"); return; }
    setBusy(true);
    try {
      const payload = { ...auditForm };
      checklist.forEach((c) => { payload[c.key] = !!payload[c.key]; });
      await api.post("/claims/prevention/audits", payload);
      toast.success("Prevention audit recorded");
      setAuditForm({});
      load(); onRefresh?.();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    finally { setBusy(false); }
  };

  return (
    <div className="space-y-4">
      <Card className="p-4 bg-slate-900/60 border-white/10">
        <div className="text-[10px] font-mono uppercase tracking-widest text-cyan-300 mb-3">
          <Sparkles size={12} className="inline mr-1" /> Prevention is 90% of the battle — every load runs this checklist
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mb-4">
          <div className="md:col-span-2">
            <FF label="Load ID *">
              <Input value={auditForm.load_id || ""} onChange={(e) => setAuditForm({ ...auditForm, load_id: e.target.value })}
                className="bg-black/40 border-white/10 h-8 text-xs" placeholder="ORI-88231"
                data-testid="prev-audit-load-id" />
            </FF>
          </div>
          {checklist.map((c) => (
            <label key={c.key} className="flex items-start gap-2 p-2 bg-black/30 border border-white/5 rounded cursor-pointer hover:border-cyan-400/30"
              data-testid={`prev-check-${c.key}`}>
              <input type="checkbox" checked={!!auditForm[c.key]}
                onChange={(e) => setAuditForm({ ...auditForm, [c.key]: e.target.checked })}
                className="mt-0.5" />
              <div className="flex-1">
                <div className="text-xs text-slate-100">{c.label}</div>
                <div className="text-[10px] text-slate-500 leading-relaxed">{c.explain}</div>
              </div>
            </label>
          ))}
        </div>
        <FF label="Notes"><Textarea rows={2} value={auditForm.notes || ""}
          onChange={(e) => setAuditForm({ ...auditForm, notes: e.target.value })}
          className="bg-black/40 border-white/10 text-xs" /></FF>
        <div className="flex justify-end mt-3">
          <Button size="sm" onClick={submitAudit} disabled={busy} className="bg-cyan-500 hover:bg-cyan-400 text-black"
            data-testid="prev-audit-save">
            {busy ? <Loader2 size={13} className="animate-spin mr-1" /> : <ClipboardList size={13} className="mr-1" />}
            Record Audit
          </Button>
        </div>
      </Card>

      <Card className="p-0 bg-slate-900/60 border-white/10 overflow-hidden">
        <div className="px-3 py-2 border-b border-white/10 text-[10px] font-mono uppercase tracking-widest text-cyan-300">
          Recent audits · {audits.length}
        </div>
        {audits.length === 0 ? (
          <div className="p-6 text-center text-xs text-slate-500">No audits recorded yet.</div>
        ) : (
          <table className="w-full text-xs">
            <thead className="bg-black/40 text-slate-400 font-mono uppercase tracking-wider">
              <tr>
                <th className="px-3 py-2 text-left">Load ID</th>
                <th className="px-3 py-2 text-right">Score</th>
                <th className="px-3 py-2 text-right">Passed</th>
                <th className="px-3 py-2 text-left">Attested</th>
                <th className="px-3 py-2 text-left">By</th>
              </tr>
            </thead>
            <tbody>
              {audits.map((a) => (
                <tr key={a.audit_id} className="border-t border-white/5" data-testid={`prev-audit-row-${a.audit_id}`}>
                  <td className="px-3 py-2 text-slate-100 font-mono">{a.load_id}</td>
                  <td className={`px-3 py-2 text-right font-mono ${a.score_pct >= 90 ? "text-emerald-300" : a.score_pct >= 70 ? "text-amber-300" : "text-red-300"}`}>
                    {a.score_pct}%
                  </td>
                  <td className="px-3 py-2 text-right text-slate-300 font-mono">{a.passed_count}/{a.total_checks}</td>
                  <td className="px-3 py-2 text-slate-500 font-mono text-[10px]">{a.attested_at?.slice(0, 16).replace("T", " ")}</td>
                  <td className="px-3 py-2 text-slate-400">{a.attested_by}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}

// ============================================================
//                     WATCHLIST TAB
// ============================================================
function WatchlistTab() {
  const [rows, setRows] = useState([]);
  useEffect(() => {
    api.get("/claims/carriers/watchlist").then(({ data }) => setRows(data.items || [])).catch(() => {});
  }, []);
  return (
    <div className="space-y-4">
      <Card className="p-4 bg-slate-900/60 border-white/10">
        <div className="text-[10px] font-mono uppercase tracking-widest text-cyan-300">
          <Ban size={12} className="inline mr-1" /> Systemic protection: carriers with 2+ claims are auto-flagged
        </div>
      </Card>
      {rows.length === 0 ? (
        <Card className="p-8 text-center bg-slate-900/60 border-white/10">
          <ShieldCheck size={22} className="mx-auto text-emerald-500 mb-2" />
          <div className="text-xs text-slate-500">Clean carrier roster. Well done.</div>
        </Card>
      ) : (
        <Card className="p-0 bg-slate-900/60 border-white/10 overflow-hidden">
          <table className="w-full text-xs" data-testid="watchlist-table">
            <thead className="bg-black/40 text-slate-400 font-mono uppercase tracking-wider">
              <tr>
                <th className="px-3 py-2 text-left">Carrier</th>
                <th className="px-3 py-2 text-left">MC</th>
                <th className="px-3 py-2 text-right">Claims</th>
                <th className="px-3 py-2 text-right">$ exposure</th>
                <th className="px-3 py-2 text-right">$ paid</th>
                <th className="px-3 py-2 text-left">Last claim</th>
                <th className="px-3 py-2 text-left">Rec.</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.carrier_mc} className={`border-t border-white/5 ${r.cut_recommended ? "bg-red-500/[0.03]" : ""}`}
                  data-testid={`watchlist-row-${r.carrier_mc}`}>
                  <td className="px-3 py-2 text-slate-100">{r.carrier_name}</td>
                  <td className="px-3 py-2 text-slate-500 font-mono">{r.carrier_mc}</td>
                  <td className="px-3 py-2 text-right text-slate-200 font-mono">{r.claims_count}</td>
                  <td className="px-3 py-2 text-right text-red-300 font-mono">${fmt(r.total_claim_usd)}</td>
                  <td className="px-3 py-2 text-right text-emerald-300 font-mono">${fmt(r.total_paid_usd)}</td>
                  <td className="px-3 py-2 text-slate-500 font-mono text-[10px]">{r.last_claim_at?.slice(0, 10)}</td>
                  <td className="px-3 py-2">
                    {r.cut_recommended ? (
                      <span className="px-2 py-0.5 rounded-full text-[9px] font-mono uppercase border border-red-400/40 text-red-200 bg-red-500/10">CUT</span>
                    ) : (
                      <span className="text-slate-500 text-[10px]">Monitor</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}

// ============================================================
//                     COI TAB
// ============================================================
function CoiTab() {
  const [rows, setRows] = useState([]);
  const [addOpen, setAddOpen] = useState(false);
  const [form, setForm] = useState({
    carrier_mc: "", carrier_name: "", policy_number: "", insurer: "",
    coverage_usd: "", effective_date: "", expiration_date: "", verified_by: "",
  });
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    try { const { data } = await api.get("/claims/insurance/verifications"); setRows(data.items || []); }
    catch (e) { /* no-op */ }
  }, []);
  useEffect(() => { load(); }, [load]);

  const save = async () => {
    if (!form.carrier_mc.trim() || !form.effective_date || !form.expiration_date) {
      toast.error("MC, effective, expiration required"); return;
    }
    setBusy(true);
    try {
      const payload = { ...form, coverage_usd: Number(form.coverage_usd || 0) };
      Object.keys(payload).forEach((k) => payload[k] === "" && delete payload[k]);
      await api.post("/claims/insurance/verifications", payload);
      toast.success("COI verified");
      setForm({ ...form, carrier_mc: "", carrier_name: "", policy_number: "", coverage_usd: "" });
      setAddOpen(false); load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    finally { setBusy(false); }
  };

  const statusColor = (s) => ({
    expired: "border-red-400/40 text-red-200 bg-red-500/10",
    expiring_soon: "border-amber-400/40 text-amber-200 bg-amber-500/10",
    current: "border-emerald-400/40 text-emerald-200 bg-emerald-500/10",
    unknown: "border-slate-400/40 text-slate-200",
  }[s] || "border-slate-400/40 text-slate-200");

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <div className="text-[10px] font-mono uppercase tracking-widest text-cyan-300">
          <Award size={12} className="inline mr-1" /> {rows.length} carriers on file
        </div>
        <Button size="sm" onClick={() => setAddOpen(true)} className="bg-cyan-500 hover:bg-cyan-400 text-black"
          data-testid="coi-add-btn">
          <Plus size={13} className="mr-1" /> Verify Carrier COI
        </Button>
      </div>
      {rows.length === 0 ? (
        <Card className="p-8 text-center bg-slate-900/60 border-white/10">
          <Award size={22} className="mx-auto text-slate-600 mb-2" />
          <div className="text-xs text-slate-500">No COIs verified yet — verify every carrier before dispatching.</div>
        </Card>
      ) : (
        <Card className="p-0 bg-slate-900/60 border-white/10 overflow-hidden">
          <table className="w-full text-xs" data-testid="coi-table">
            <thead className="bg-black/40 text-slate-400 font-mono uppercase tracking-wider">
              <tr>
                <th className="px-3 py-2 text-left">Carrier</th>
                <th className="px-3 py-2 text-left">MC</th>
                <th className="px-3 py-2 text-left">Insurer</th>
                <th className="px-3 py-2 text-left">Policy #</th>
                <th className="px-3 py-2 text-right">Coverage</th>
                <th className="px-3 py-2 text-left">Effective</th>
                <th className="px-3 py-2 text-left">Expires</th>
                <th className="px-3 py-2 text-left">Status</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.verification_id} className="border-t border-white/5"
                  data-testid={`coi-row-${r.verification_id}`}>
                  <td className="px-3 py-2 text-slate-100">{r.carrier_name || "—"}</td>
                  <td className="px-3 py-2 text-slate-500 font-mono">{r.carrier_mc}</td>
                  <td className="px-3 py-2 text-slate-300">{r.insurer || "—"}</td>
                  <td className="px-3 py-2 text-slate-400 font-mono text-[10px]">{r.policy_number || "—"}</td>
                  <td className="px-3 py-2 text-right text-slate-200 font-mono">${fmt(r.coverage_usd)}</td>
                  <td className="px-3 py-2 text-slate-400 text-[10px]">{r.effective_date?.slice(0, 10)}</td>
                  <td className="px-3 py-2 text-slate-400 text-[10px]">{r.expiration_date?.slice(0, 10)}</td>
                  <td className="px-3 py-2">
                    <span className={`px-2 py-0.5 rounded-full text-[9px] font-mono uppercase border ${statusColor(r.status)}`}>
                      {r.status.replace("_", " ")}
                    </span>
                    {r.days_until_expiration != null && (
                      <div className="text-[9px] text-slate-500 mt-0.5">
                        {r.days_until_expiration >= 0 ? `${r.days_until_expiration}d left` : `expired ${Math.abs(r.days_until_expiration)}d ago`}
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent className="max-w-2xl bg-slate-950 border-white/10 max-h-[90vh] overflow-y-auto" data-testid="coi-modal">
          <DialogHeader>
            <DialogTitle className="text-cyan-100">Verify Carrier COI</DialogTitle>
            <DialogDescription className="text-slate-400 text-xs">
              A claim denied because coverage lapsed is worse than no claim. Verify every 30 days.
            </DialogDescription>
          </DialogHeader>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <FF label="Carrier MC *"><Input value={form.carrier_mc} onChange={(e) => setForm({ ...form, carrier_mc: e.target.value })}
              className="bg-black/40 border-white/10 h-8 text-xs" data-testid="coi-form-mc" /></FF>
            <FF label="Carrier Name"><CarrierCombobox value={form.carrier_name} onChange={(v) => setForm({ ...form, carrier_name: v })}
              onSelect={(rec) => setForm((f) => ({ ...f, carrier_name: rec.name, carrier_mc: rec.mc || f.carrier_mc }))}
              testid="coi-carrier-combobox" className="bg-black/40 border-white/10 h-8 text-xs" /></FF>
            <FF label="Insurer"><Input value={form.insurer} onChange={(e) => setForm({ ...form, insurer: e.target.value })}
              className="bg-black/40 border-white/10 h-8 text-xs" placeholder="Progressive Commercial, Great West…" /></FF>
            <FF label="Policy Number"><Input value={form.policy_number} onChange={(e) => setForm({ ...form, policy_number: e.target.value })}
              className="bg-black/40 border-white/10 h-8 text-xs" /></FF>
            <FF label="Coverage (USD)"><Input type="number" value={form.coverage_usd}
              onChange={(e) => setForm({ ...form, coverage_usd: e.target.value })}
              className="bg-black/40 border-white/10 h-8 text-xs" placeholder="1000000" /></FF>
            <FF label="Verified By"><Input value={form.verified_by} onChange={(e) => setForm({ ...form, verified_by: e.target.value })}
              className="bg-black/40 border-white/10 h-8 text-xs" /></FF>
            <FF label="Effective Date *"><Input type="date" value={form.effective_date}
              onChange={(e) => setForm({ ...form, effective_date: e.target.value })}
              className="bg-black/40 border-white/10 h-8 text-xs" /></FF>
            <FF label="Expiration Date *"><Input type="date" value={form.expiration_date}
              onChange={(e) => setForm({ ...form, expiration_date: e.target.value })}
              className="bg-black/40 border-white/10 h-8 text-xs" /></FF>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setAddOpen(false)}>Cancel</Button>
            <Button onClick={save} disabled={busy} className="bg-cyan-500 hover:bg-cyan-400 text-black" data-testid="coi-form-save">
              {busy ? <Loader2 size={13} className="animate-spin mr-1" /> : <CheckCircle2 size={13} className="mr-1" />}
              Save COI
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ============================================================
//                     RESERVE TAB
// ============================================================
function ReserveTab({ dashboard }) {
  if (!dashboard) return <Loader />;
  const r = dashboard.reserve;
  return (
    <div className="space-y-4">
      <Card className="p-6 bg-slate-900/60 border-white/10 text-center">
        <PiggyBank size={40} className="mx-auto text-amber-300 mb-2" />
        <div className="text-[10px] font-mono uppercase tracking-widest text-cyan-300 mb-2">Recommended claims reserve</div>
        <div className="text-4xl font-mono text-amber-300">
          ${fmt(r.recommended_reserve_usd_low)}<span className="text-slate-500 text-2xl mx-2">–</span>${fmt(r.recommended_reserve_usd_high)}
        </div>
        <div className="text-xs text-slate-400 mt-2">2–3% of ${fmt(r.monthly_avg_revenue_usd)} avg monthly revenue</div>
        <div className="text-[11px] text-slate-500 mt-4 max-w-2xl mx-auto leading-relaxed">{r.reasoning}</div>
      </Card>
      <Card className="p-4 bg-slate-900/60 border-white/10">
        <div className="text-[10px] font-mono uppercase tracking-widest text-cyan-300 mb-3">
          Revenue basis (trailing 90 days)
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <MiniTile label="90d Revenue" value={`$${fmt(r.trailing_90d_revenue_usd)}`} accent="#10B981" />
          <MiniTile label="Monthly Avg" value={`$${fmt(r.monthly_avg_revenue_usd)}`} accent="#22D3EE" />
          <MiniTile label="Reserve Range" value={`$${fmt(r.recommended_reserve_usd_low)} – $${fmt(r.recommended_reserve_usd_high)}`} accent="#F59E0B" />
        </div>
      </Card>
    </div>
  );
}

// ============================================================
//                     SHARED UI PRIMS
// ============================================================
function BigKpi({ label, value, accent, icon: Icon, sub }) {
  return (
    <Card className="p-4 bg-slate-900/60 border-white/10">
      <div className="flex items-center justify-between">
        <div className="text-[10px] font-mono uppercase tracking-widest text-slate-500">{label}</div>
        {Icon && <Icon size={14} style={{ color: accent }} />}
      </div>
      <div className="text-2xl md:text-3xl font-mono mt-1" style={{ color: accent }}>{value}</div>
      {sub && <div className="text-[10px] text-slate-500 mt-0.5">{sub}</div>}
    </Card>
  );
}
function MiniTile({ label, value, accent }) {
  return (
    <div className="p-3 bg-black/30 border border-white/10 rounded">
      <div className="text-[10px] font-mono uppercase tracking-widest text-slate-500">{label}</div>
      <div className="text-lg font-mono mt-1" style={{ color: accent }}>{value}</div>
    </div>
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
  const v = Number(n) || 0;
  return v.toLocaleString("en-US", { maximumFractionDigits: 2 });
}
