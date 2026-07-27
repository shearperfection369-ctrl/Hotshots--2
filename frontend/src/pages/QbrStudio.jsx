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
  TrendingUp, TrendingDown, Minus, ClipboardList, Award, DollarSign, Package,
  ShieldCheck, Truck, MapPin, FileDown, Send, RefreshCw, Sparkles, Plus,
  Loader2, CheckCircle2, Trash2, Wand2, Calendar,
} from "lucide-react";
import { api, BACKEND_URL } from "../lib/api";
import { useBranding, useBrandRefresh } from "../lib/branding";
import { toast } from "sonner";

/**
 * QbrStudio — Quarterly Business Review Studio.
 * Auto-pulls TMS data → per-shipper QBR with comparative deltas → Orisei-branded PDF → distribute.
 */
const TABS = [
  { id: "compute", label: "Auto-Compute",  icon: Wand2 },
  { id: "drafts",  label: "Drafts",        icon: ClipboardList },
];

function currentQuarter() {
  const d = new Date();
  const q = Math.floor(d.getMonth() / 3) + 1;
  return `Q${q} ${d.getFullYear()}`;
}

export default function QbrStudio() {
  const { brand } = useBranding();
  const [tab, setTab] = useState("compute");
  const [shippers, setShippers] = useState([]);
  const [drafts, setDrafts] = useState([]);
  const [busy, setBusy] = useState(false);

  const loadAll = useCallback(async () => {
    setBusy(true);
    try {
      const [s, d] = await Promise.all([
        api.get("/qbr-studio/shippers"),
        api.get("/qbr-studio/drafts"),
      ]);
      setShippers(s.data.items || []);
      setDrafts(d.data.items || []);
    } catch (e) { toast.error("Failed to load QBR data"); }
    finally { setBusy(false); }
  }, []);
  useEffect(() => { loadAll(); }, [loadAll]);
  useBrandRefresh(() => loadAll());

  const brandShort = brand?.short_name || "Orisei";

  return (
    <>
      <Topbar
        title={`${brandShort} · QBR Studio`}
        subtitle="Auto-computed quarterly reviews · comparative deltas · distributable PDFs"
      />
      <div className="p-4 md:p-6 space-y-4">
        <div className="flex flex-wrap items-center gap-2" data-testid="qbr-studio-header">
          <TrendingUp size={22} style={{ color: brand?.primary_color || "#22D3EE" }} />
          <div className="text-slate-100 font-medium">QBR Studio</div>
          <Badge className="bg-cyan-500/15 text-cyan-200 border border-cyan-400/30">TMS-DRIVEN · COMPARATIVE</Badge>
          <div className="ml-auto">
            <Button variant="secondary" size="sm" onClick={loadAll} disabled={busy}
              data-testid="qbr-refresh">
              {busy ? <Loader2 size={13} className="animate-spin mr-1" /> : <RefreshCw size={13} className="mr-1" />}
              Refresh
            </Button>
          </div>
        </div>

        <div className="flex gap-1.5 overflow-x-auto pb-1" data-testid="qbr-tabs">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              data-testid={`qbr-tab-${id}`}
              className={`inline-flex items-center gap-2 px-4 py-2 rounded text-xs font-mono uppercase tracking-wider transition border whitespace-nowrap ${
                tab === id
                  ? "bg-cyan-500 text-black border-cyan-400 shadow-[0_0_20px_rgba(34,211,238,0.35)]"
                  : "border-white/10 text-slate-400 hover:border-cyan-400/40 hover:text-cyan-200"
              }`}
            >
              <Icon size={13} /> {label}
              {id === "drafts" && drafts.length > 0 && (
                <span className="text-[9px] px-1.5 py-0 rounded-full bg-cyan-500/20 text-cyan-200">{drafts.length}</span>
              )}
            </button>
          ))}
        </div>

        {tab === "compute" && <ComputeTab shippers={shippers} onGenerated={loadAll} />}
        {tab === "drafts"  && <DraftsTab drafts={drafts} onChange={loadAll} />}
      </div>
    </>
  );
}

// ============================================================
//                     COMPUTE TAB
// ============================================================
function ComputeTab({ shippers, onGenerated }) {
  const [shipper, setShipper] = useState("");
  const [period, setPeriod] = useState(currentQuarter());
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [narrative, setNarrative] = useState({
    executive_summary: "", strengths: "", gaps: "", action_items: "", next_review_date: "",
  });

  useEffect(() => {
    if (!shipper && shippers.length) setShipper(shippers[0].name);
  }, [shippers, shipper]);

  const compute = async () => {
    if (!shipper) { toast.error("Pick a shipper first"); return; }
    setLoading(true);
    try {
      const { data } = await api.get(`/qbr-studio/period/${encodeURIComponent(period)}/${encodeURIComponent(shipper)}`);
      setData(data);
      toast.success("Metrics computed");
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    finally { setLoading(false); }
  };

  const save = async () => {
    if (!data) { toast.error("Compute first"); return; }
    setSaving(true);
    try {
      const payload = {
        shipper_name: shipper,
        period,
        executive_summary: narrative.executive_summary || undefined,
        strengths: narrative.strengths || undefined,
        gaps: narrative.gaps || undefined,
        next_review_date: narrative.next_review_date || undefined,
        action_items: narrative.action_items
          ? narrative.action_items.split("\n").map((s) => s.trim()).filter(Boolean)
          : undefined,
      };
      Object.keys(payload).forEach((k) => payload[k] === undefined && delete payload[k]);
      const { data: draft } = await api.post("/qbr-studio/generate", payload);
      toast.success(`Draft saved: ${draft.draft_id}`);
      onGenerated?.();
      setNarrative({ executive_summary: "", strengths: "", gaps: "", action_items: "", next_review_date: "" });
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    finally { setSaving(false); }
  };

  return (
    <div className="space-y-4">
      {/* Controls */}
      <Card className="p-4 bg-slate-900/60 border-white/10">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3 items-end">
          <div>
            <div className="text-[9px] font-mono uppercase tracking-widest text-slate-500 mb-1">Shipper</div>
            <select value={shipper} onChange={(e) => setShipper(e.target.value)}
              className="w-full bg-black/40 border border-white/10 rounded px-2 py-1.5 text-xs text-slate-100"
              data-testid="qbr-shipper-select">
              <option value="">— Select —</option>
              {shippers.map((s) => (
                <option key={s.name} value={s.name}>{s.name} · {s.source}</option>
              ))}
            </select>
          </div>
          <div>
            <div className="text-[9px] font-mono uppercase tracking-widest text-slate-500 mb-1">Period</div>
            <Input value={period} onChange={(e) => setPeriod(e.target.value)}
              placeholder="Q1 2026 or YTD 2026"
              className="bg-black/40 border-white/10 h-8 text-xs"
              data-testid="qbr-period-input" />
          </div>
          <div className="md:col-span-2 flex gap-2 justify-end">
            <Button variant="outline" disabled={!shipper}
              onClick={() => {
                const token = localStorage.getItem("tms_session_token");
                toast.info("Generating AI executive summary PDF…");
                fetch(`${BACKEND_URL}/api/qbr-studio/exec-summary/${encodeURIComponent(shipper)}/pdf?period=${encodeURIComponent(period)}`, {
                  headers: { Authorization: `Bearer ${token}` },
                }).then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.blob(); })
                  .then((b) => window.open(URL.createObjectURL(b), "_blank"))
                  .catch(() => toast.error("Exec summary failed — check period format (Q1 2026)"));
              }}
              className="border-amber-500/40 text-amber-300 hover:bg-amber-500/10"
              data-testid="qbr-exec-summary-btn">
              <Sparkles size={14} className="mr-1" /> Exec Summary PDF
            </Button>
            <Button onClick={compute} disabled={loading} className="bg-cyan-500 hover:bg-cyan-400 text-black"
              data-testid="qbr-compute-btn">
              {loading ? <Loader2 size={14} className="animate-spin mr-1" /> : <Wand2 size={14} className="mr-1" />}
              Compute From TMS
            </Button>
          </div>
        </div>
      </Card>

      {!data ? (
        <Card className="p-12 text-center bg-slate-900/60 border-white/10">
          <Sparkles size={28} className="mx-auto text-slate-600 mb-3" />
          <div className="text-sm text-slate-400 mb-2">Pick a shipper and click <b>Compute From TMS</b></div>
          <div className="text-xs text-slate-500 max-w-lg mx-auto">
            The studio pulls bookings, shipments, and claims for the period, compares against the prior quarter, and lets you layer executive narrative on top.
          </div>
        </Card>
      ) : (
        <>
          {/* Headline delta grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <DeltaKpi label="Loads" cur={data.metrics.loads.total} delta={data.deltas.loads_total} />
            <DeltaKpi label="Revenue" cur={data.metrics.loads.revenue_usd} delta={data.deltas.revenue_usd} money />
            <DeltaKpi label="Margin" cur={data.metrics.loads.margin_usd} delta={data.deltas.margin_usd} money />
            <DeltaKpi label="Margin %" cur={data.metrics.loads.margin_pct} delta={data.deltas.margin_pct} pct />
            <DeltaKpi label="Avg RPM" cur={data.metrics.loads.avg_rpm} delta={data.deltas.avg_rpm} rpm />
            <DeltaKpi label="OTD %" cur={data.metrics.shipments.otd_pct} delta={data.deltas.otd_pct} pct />
            <DeltaKpi label="Damage-Free %" cur={data.metrics.claims.damage_free_pct} delta={data.deltas.damage_free_pct} pct />
            <DeltaKpi label="Claims $" cur={data.metrics.claims.amount_usd} delta={data.deltas.claims_amount_usd} money />
          </div>

          {/* Body */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {/* Left column: read-out */}
            <div className="md:col-span-2 space-y-3">
              <ReadoutCard title="Volume & Revenue" icon={DollarSign}>
                <MetricRow label="Total loads" value={data.metrics.loads.total} />
                <MetricRow label="Total miles" value={fmtInt(data.metrics.loads.total_miles)} />
                <MetricRow label="Revenue" value={fmtUSD(data.metrics.loads.revenue_usd)} />
                <MetricRow label="Carrier cost" value={fmtUSD(data.metrics.loads.carrier_cost_usd)} />
                <MetricRow label="Margin" value={fmtUSD(data.metrics.loads.margin_usd)} />
                <MetricRow label="Avg RPM" value={fmtUSD(data.metrics.loads.avg_rpm)} />
              </ReadoutCard>

              <ReadoutCard title="On-Time Performance" icon={ShieldCheck}>
                <MetricRow label="Shipments tracked" value={data.metrics.shipments.total} />
                <MetricRow label="OTD %" value={data.metrics.shipments.otd_pct != null ? `${data.metrics.shipments.otd_pct}%` : "—"} />
                <MetricRow label="Delivered" value={data.metrics.shipments.delivered} />
                <MetricRow label="Delayed" value={data.metrics.shipments.delayed} />
                <MetricRow label="In-transit" value={data.metrics.shipments.in_transit} />
              </ReadoutCard>

              <ReadoutCard title="Damage & Claims" icon={Package}>
                <MetricRow label="Claims filed" value={data.metrics.claims.total} />
                <MetricRow label="Claim exposure" value={fmtUSD(data.metrics.claims.amount_usd)} />
                <MetricRow label="Claims paid" value={fmtUSD(data.metrics.claims.paid_usd)} />
                <MetricRow label="Damage-free %" value={data.metrics.claims.damage_free_pct != null ? `${data.metrics.claims.damage_free_pct}%` : "—"} />
                <MetricRow label="24-hr SLA adherence" value={`${data.metrics.claims.sla_adherence_pct}%`} />
                {Object.keys(data.metrics.claims.by_kind || {}).length > 0 && (
                  <div className="text-[10px] text-slate-500 mt-2">
                    By type: {Object.entries(data.metrics.claims.by_kind).map(([k, v]) => `${k} (${v})`).join(" · ")}
                  </div>
                )}
              </ReadoutCard>

              {data.metrics.lanes.top.length > 0 && (
                <ReadoutCard title="Top Lanes" icon={MapPin}>
                  {data.metrics.lanes.top.map((l, i) => (
                    <MetricRow key={i} label={l.lane} value={`${l.count} loads`} />
                  ))}
                </ReadoutCard>
              )}

              {data.metrics.equipment.length > 0 && (
                <ReadoutCard title="Equipment Mix" icon={Truck}>
                  {data.metrics.equipment.map((e, i) => (
                    <MetricRow key={i} label={e.kind} value={`${e.count} loads`} />
                  ))}
                </ReadoutCard>
              )}

              {data.metrics.account?.lifecycle && (
                <ReadoutCard title="Account Snapshot" icon={Award}>
                  <MetricRow label="Lifecycle" value={data.metrics.account.lifecycle.toUpperCase()} />
                  {data.metrics.account.payment_terms && (
                    <MetricRow label="Payment terms" value={data.metrics.account.payment_terms.toUpperCase().replace("_", "-")} />
                  )}
                  {data.metrics.account.dedicated_am && (
                    <MetricRow label="Dedicated AM" value={data.metrics.account.dedicated_am} />
                  )}
                  {data.metrics.account.annual_volume_loads != null && (
                    <MetricRow label="Annual commitment" value={`${fmtInt(data.metrics.account.annual_volume_loads)} loads`} />
                  )}
                  {data.metrics.account.annual_revenue_usd != null && (
                    <MetricRow label="Annual revenue commitment" value={fmtUSD(data.metrics.account.annual_revenue_usd)} />
                  )}
                  {(data.metrics.account.assigned_incentives || []).length > 0 && (
                    <div className="text-[10px] text-slate-500 mt-2">
                      Incentives: {data.metrics.account.assigned_incentives.join(" · ")}
                    </div>
                  )}
                </ReadoutCard>
              )}
            </div>

            {/* Right column: narrative + save */}
            <div className="space-y-3">
              <Card className="p-4 bg-slate-900/60 border-white/10 space-y-3">
                <div className="text-[10px] font-mono uppercase tracking-widest text-cyan-300">
                  <ClipboardList size={12} className="inline mr-1" /> Narrative
                </div>
                <NarrativeField label="Executive summary" testid="qbr-narrative-exec"
                  value={narrative.executive_summary}
                  onChange={(v) => setNarrative({ ...narrative, executive_summary: v })}
                  placeholder="High-level narrative for the shipper's C-suite. What was the story this quarter?" />
                <NarrativeField label="Strengths" testid="qbr-narrative-strengths"
                  value={narrative.strengths}
                  onChange={(v) => setNarrative({ ...narrative, strengths: v })}
                  placeholder="Where we performed well." />
                <NarrativeField label="Gaps & opportunities" testid="qbr-narrative-gaps"
                  value={narrative.gaps}
                  onChange={(v) => setNarrative({ ...narrative, gaps: v })}
                  placeholder="Where to improve next quarter." />
                <NarrativeField label="Action items (one per line)" testid="qbr-narrative-actions"
                  value={narrative.action_items}
                  onChange={(v) => setNarrative({ ...narrative, action_items: v })}
                  placeholder={"Deploy EDI 214 pings by Mar 15\nSchedule reefer temp SOP review"} />
                <div>
                  <div className="text-[9px] font-mono uppercase tracking-widest text-slate-500 mb-1">Next review</div>
                  <Input type="date" value={narrative.next_review_date}
                    onChange={(e) => setNarrative({ ...narrative, next_review_date: e.target.value })}
                    className="bg-black/40 border-white/10 h-8 text-xs" data-testid="qbr-narrative-next" />
                </div>
              </Card>
              <Button onClick={save} disabled={saving} className="w-full bg-cyan-500 hover:bg-cyan-400 text-black"
                data-testid="qbr-save-btn">
                {saving ? <Loader2 size={13} className="animate-spin mr-1" /> : <CheckCircle2 size={13} className="mr-1" />}
                Save Draft
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function ReadoutCard({ title, icon: Icon, children }) {
  return (
    <Card className="p-4 bg-slate-900/60 border-white/10 space-y-1">
      <div className="text-[10px] font-mono uppercase tracking-widest text-cyan-300 mb-2 flex items-center gap-1">
        {Icon && <Icon size={12} />} {title}
      </div>
      {children}
    </Card>
  );
}
function MetricRow({ label, value }) {
  return (
    <div className="flex items-center justify-between text-xs border-b border-white/5 pb-1 last:border-0">
      <span className="text-slate-400">{label}</span>
      <span className="text-slate-100 font-mono">{value}</span>
    </div>
  );
}
function NarrativeField({ label, testid, value, onChange, placeholder }) {
  return (
    <div>
      <div className="text-[9px] font-mono uppercase tracking-widest text-slate-500 mb-1">{label}</div>
      <Textarea rows={3} value={value} onChange={(e) => onChange?.(e.target.value)}
        placeholder={placeholder}
        className="bg-black/40 border-white/10 text-xs" data-testid={testid} />
    </div>
  );
}
function DeltaKpi({ label, cur, delta, money, pct, rpm }) {
  const fmt = (v) => v == null ? "—" : money ? fmtUSD(v) : pct ? `${v}%` : rpm ? `$${Number(v).toFixed(2)}` : fmtInt(v);
  const dir = delta?.direction || "n/a";
  const Icon = dir === "up" ? TrendingUp : dir === "down" ? TrendingDown : Minus;
  // For claims/gaps, "up" is bad — but we don't try to invert here; just show the number and let the operator interpret.
  const color = dir === "up" ? "#10B981" : dir === "down" ? "#EF4444" : "#94A3B8";
  const dPct = delta?.pct;
  return (
    <Card className="p-3 bg-slate-900/60 border-white/10">
      <div className="text-[10px] font-mono uppercase tracking-widest text-slate-500">{label}</div>
      <div className="text-2xl font-mono text-slate-100 mt-1">{fmt(cur)}</div>
      <div className="flex items-center gap-1 mt-1 text-[10px] font-mono" style={{ color }}>
        <Icon size={10} />
        {delta ? (dPct != null ? `${dPct >= 0 ? "+" : ""}${dPct}% vs prior` : "no prior data") : "—"}
      </div>
    </Card>
  );
}

// ============================================================
//                     DRAFTS TAB
// ============================================================
function DraftsTab({ drafts, onChange }) {
  const [detailOpen, setDetailOpen] = useState(null);
  const [distributeOpen, setDistributeOpen] = useState(null);

  const del = async (draft_id) => {
    if (!window.confirm("Delete this QBR draft?")) return;
    try { await api.delete(`/qbr-studio/drafts/${draft_id}`); toast.success("Deleted"); onChange?.(); }
    catch (e) { toast.error("Failed"); }
  };

  const downloadPdf = (draft_id) => {
    const token = localStorage.getItem("tms_session_token");
    fetch(`${BACKEND_URL}/api/qbr-studio/drafts/${draft_id}/report.pdf`, {
      headers: { Authorization: `Bearer ${token}` },
    }).then((r) => r.blob()).then((b) => window.open(URL.createObjectURL(b), "_blank"));
  };

  if (!drafts.length) {
    return (
      <Card className="p-12 text-center bg-slate-900/60 border-white/10">
        <ClipboardList size={28} className="mx-auto text-slate-600 mb-3" />
        <div className="text-sm text-slate-400">No drafts yet. Compute + save one from the <b>Auto-Compute</b> tab.</div>
      </Card>
    );
  }

  return (
    <>
      <Card className="p-0 bg-slate-900/60 border-white/10 overflow-hidden">
        <table className="w-full text-xs" data-testid="qbr-drafts-table">
          <thead className="bg-black/40 text-slate-400 font-mono uppercase tracking-wider">
            <tr>
              <th className="px-3 py-2 text-left">Draft</th>
              <th className="px-3 py-2 text-left">Shipper</th>
              <th className="px-3 py-2 text-left">Period</th>
              <th className="px-3 py-2 text-right">Loads</th>
              <th className="px-3 py-2 text-right">Revenue</th>
              <th className="px-3 py-2 text-left">Status</th>
              <th className="px-3 py-2 text-left">Created</th>
              <th className="px-3 py-2 text-right"></th>
            </tr>
          </thead>
          <tbody>
            {drafts.map((d) => (
              <tr key={d.draft_id} className="border-t border-white/5 hover:bg-white/[0.02]"
                data-testid={`qbr-draft-row-${d.draft_id}`}>
                <td className="px-3 py-2 text-cyan-300 font-mono">{d.draft_id}</td>
                <td className="px-3 py-2 text-slate-100">{d.shipper_name}</td>
                <td className="px-3 py-2 text-slate-300 font-mono">{d.period}</td>
                <td className="px-3 py-2 text-right text-slate-200 font-mono">{fmtInt(d.metrics?.loads?.total || 0)}</td>
                <td className="px-3 py-2 text-right text-emerald-300 font-mono">{fmtUSD(d.metrics?.loads?.revenue_usd || 0)}</td>
                <td className="px-3 py-2">
                  <span className={`px-2 py-0.5 rounded-full text-[9px] font-mono uppercase border ${
                    d.status === "distributed" ? "border-emerald-400/40 text-emerald-200 bg-emerald-500/10" :
                    "border-slate-400/40 text-slate-300 bg-slate-500/10"
                  }`}>{d.status}</span>
                </td>
                <td className="px-3 py-2 text-slate-500 text-[10px] font-mono">{d.created_at?.slice(0, 10)}</td>
                <td className="px-3 py-2 text-right">
                  <div className="flex gap-1 justify-end">
                    <Button size="sm" variant="ghost" onClick={() => setDetailOpen(d)}
                      className="h-7 px-2 text-cyan-300 hover:text-cyan-100"
                      data-testid={`qbr-draft-view-${d.draft_id}`}>View</Button>
                    <Button size="sm" variant="ghost" onClick={() => downloadPdf(d.draft_id)}
                      className="h-7 px-2 text-cyan-300 hover:text-cyan-100"
                      data-testid={`qbr-draft-pdf-${d.draft_id}`}>
                      <FileDown size={11} />
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => setDistributeOpen(d)}
                      className="h-7 px-2 text-emerald-300 hover:text-emerald-100"
                      data-testid={`qbr-draft-send-${d.draft_id}`}>
                      <Send size={11} />
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => del(d.draft_id)}
                      className="h-7 px-2 text-red-400 hover:text-red-200"
                      data-testid={`qbr-draft-del-${d.draft_id}`}>
                      <Trash2 size={11} />
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <DraftDetailDialog draft={detailOpen} onClose={() => setDetailOpen(null)} onSaved={onChange} />
      <DistributeDialog draft={distributeOpen} onClose={() => setDistributeOpen(null)} onSent={onChange} />
    </>
  );
}

function DraftDetailDialog({ draft, onClose, onSaved }) {
  const [form, setForm] = useState({});
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (draft) {
      setForm({
        executive_summary: draft.executive_summary || "",
        strengths: draft.strengths || "",
        gaps: draft.gaps || "",
        action_items: (draft.action_items || []).join("\n"),
        next_review_date: draft.next_review_date || "",
      });
    }
  }, [draft]);
  if (!draft) return null;

  const save = async () => {
    setBusy(true);
    try {
      const payload = {
        executive_summary: form.executive_summary || undefined,
        strengths: form.strengths || undefined,
        gaps: form.gaps || undefined,
        next_review_date: form.next_review_date || undefined,
        action_items: form.action_items
          ? form.action_items.split("\n").map((s) => s.trim()).filter(Boolean)
          : undefined,
      };
      Object.keys(payload).forEach((k) => payload[k] === undefined && delete payload[k]);
      await api.patch(`/qbr-studio/drafts/${draft.draft_id}`, payload);
      toast.success("Saved");
      onSaved?.(); onClose?.();
    } catch (e) { toast.error("Failed"); } finally { setBusy(false); }
  };

  return (
    <Dialog open={!!draft} onOpenChange={(o) => !o && onClose?.()}>
      <DialogContent className="max-w-3xl bg-slate-950 border-white/10 max-h-[92vh] overflow-y-auto"
        data-testid="qbr-draft-detail-modal">
        <DialogHeader>
          <DialogTitle className="text-cyan-100">
            {draft.shipper_name} · {draft.period}
          </DialogTitle>
          <DialogDescription className="text-slate-400 text-xs">
            {fmtInt(draft.metrics?.loads?.total || 0)} loads · {fmtUSD(draft.metrics?.loads?.revenue_usd || 0)} revenue · OTD {draft.metrics?.shipments?.otd_pct ?? "—"}%
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <NarrativeField label="Executive summary" testid="qbr-detail-exec"
            value={form.executive_summary || ""} onChange={(v) => setForm({ ...form, executive_summary: v })} />
          <NarrativeField label="Strengths" testid="qbr-detail-strengths"
            value={form.strengths || ""} onChange={(v) => setForm({ ...form, strengths: v })} />
          <NarrativeField label="Gaps" testid="qbr-detail-gaps"
            value={form.gaps || ""} onChange={(v) => setForm({ ...form, gaps: v })} />
          <NarrativeField label="Action items" testid="qbr-detail-actions"
            value={form.action_items || ""} onChange={(v) => setForm({ ...form, action_items: v })} />
          <div>
            <div className="text-[9px] font-mono uppercase tracking-widest text-slate-500 mb-1">Next review</div>
            <Input type="date" value={form.next_review_date || ""}
              onChange={(e) => setForm({ ...form, next_review_date: e.target.value })}
              className="bg-black/40 border-white/10 h-8 text-xs" />
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={save} disabled={busy} className="bg-cyan-500 hover:bg-cyan-400 text-black"
            data-testid="qbr-detail-save">
            {busy ? <Loader2 size={13} className="animate-spin mr-1" /> : <CheckCircle2 size={13} className="mr-1" />}
            Save Changes
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function DistributeDialog({ draft, onClose, onSent }) {
  const [form, setForm] = useState({ to_email: "", cc: "", subject: "", message: "" });
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (draft) setForm({ to_email: "", cc: "", subject: "", message: "" }); }, [draft]);
  if (!draft) return null;
  const send = async () => {
    if (!form.to_email.trim()) { toast.error("Recipient email required"); return; }
    setBusy(true);
    try {
      const payload = {
        to_email: form.to_email.trim(),
        cc: form.cc ? form.cc.split(",").map((s) => s.trim()).filter(Boolean) : undefined,
        subject: form.subject || undefined,
        message: form.message || undefined,
      };
      Object.keys(payload).forEach((k) => payload[k] === undefined && delete payload[k]);
      await api.post(`/qbr-studio/drafts/${draft.draft_id}/distribute`, payload);
      toast.success(`Queued to ${payload.to_email}`);
      onSent?.(); onClose?.();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); } finally { setBusy(false); }
  };
  return (
    <Dialog open={!!draft} onOpenChange={(o) => !o && onClose?.()}>
      <DialogContent className="max-w-lg bg-slate-950 border-white/10" data-testid="qbr-distribute-modal">
        <DialogHeader>
          <DialogTitle className="text-cyan-100 flex items-center gap-2">
            <Send size={15} /> Distribute QBR
          </DialogTitle>
          <DialogDescription className="text-slate-400 text-xs">
            Queues an email with the branded PDF attached. Actual send happens once Resend key is wired.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div>
            <div className="text-[9px] font-mono uppercase tracking-widest text-slate-500 mb-1">To *</div>
            <Input type="email" value={form.to_email} onChange={(e) => setForm({ ...form, to_email: e.target.value })}
              placeholder="ops@acmeretail.com"
              className="bg-black/40 border-white/10 h-8 text-xs" data-testid="qbr-distribute-to" />
          </div>
          <div>
            <div className="text-[9px] font-mono uppercase tracking-widest text-slate-500 mb-1">CC (comma-separated)</div>
            <Input value={form.cc} onChange={(e) => setForm({ ...form, cc: e.target.value })}
              className="bg-black/40 border-white/10 h-8 text-xs" />
          </div>
          <div>
            <div className="text-[9px] font-mono uppercase tracking-widest text-slate-500 mb-1">Subject</div>
            <Input value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })}
              placeholder="Auto-filled if empty"
              className="bg-black/40 border-white/10 h-8 text-xs" />
          </div>
          <div>
            <div className="text-[9px] font-mono uppercase tracking-widest text-slate-500 mb-1">Message</div>
            <Textarea rows={4} value={form.message} onChange={(e) => setForm({ ...form, message: e.target.value })}
              placeholder="Auto-filled with summary if empty."
              className="bg-black/40 border-white/10 text-xs" />
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={send} disabled={busy} className="bg-emerald-500 hover:bg-emerald-400 text-black"
            data-testid="qbr-distribute-send">
            {busy ? <Loader2 size={13} className="animate-spin mr-1" /> : <Send size={13} className="mr-1" />}
            Queue Send
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ============================================================
//                     UTILS
// ============================================================
function fmtInt(n) {
  return Number(n || 0).toLocaleString("en-US", { maximumFractionDigits: 0 });
}
function fmtUSD(n) {
  const v = Number(n) || 0;
  return `$${v.toLocaleString("en-US", { maximumFractionDigits: 2 })}`;
}
