import React, { useEffect, useState, useMemo, useCallback } from "react";
import Topbar from "@/components/Topbar";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import {
  ClipboardCheck, Truck, FileText, Send, Navigation, PackageCheck,
  CheckSquare, Receipt, Sparkles, ChevronRight, Lock, Check, RotateCcw,
  ArrowRight, DollarSign, TrendingUp, TrendingDown, Search, Loader2,
  Zap, AlertTriangle,
} from "lucide-react";
import { toast } from "sonner";

/**
 * /workflow — Orisei AI Workflow Checklist.
 *
 * Visually-stunning, high-tech HUD-style per-shipment journey tracker.
 * Eight stages from Booked → Invoiced. AI prompts the next action with a
 * one-click CTA. Margin Calculator panel surfaces live $/% margin once the
 * broker enters their carrier cost.
 */

const ICON_MAP = {
  ClipboardCheck, Truck, FileText, Send, Navigation,
  PackageCheck, CheckSquare, Receipt,
};

const HEALTH_STYLES = {
  strong:  { color: "text-emerald-300", bar: "bg-emerald-500", glow: "shadow-[0_0_30px_rgba(16,185,129,0.5)]", label: "Strong" },
  healthy: { color: "text-cyan-300",    bar: "bg-cyan-500",    glow: "shadow-[0_0_30px_rgba(6,182,212,0.45)]", label: "Healthy" },
  thin:    { color: "text-amber-300",   bar: "bg-amber-500",   glow: "shadow-[0_0_30px_rgba(245,158,11,0.5)]", label: "Thin" },
  loss:    { color: "text-red-300",     bar: "bg-red-500",     glow: "shadow-[0_0_30px_rgba(239,68,68,0.55)]", label: "Loss" },
};

export default function WorkflowChecklist() {
  const [bookings, setBookings] = useState([]);
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState(null);
  const [checklist, setChecklist] = useState(null);
  const [loading, setLoading] = useState(false);
  const [notesOpen, setNotesOpen] = useState(false);
  const [notesText, setNotesText] = useState("");
  const [pendingStage, setPendingStage] = useState(null);
  const [margin, setMargin] = useState(null);
  const [carrierCost, setCarrierCost] = useState("");
  const [extraCost, setExtraCost] = useState("");
  const [exceptions, setExceptions] = useState([]);
  const [archivedDocs, setArchivedDocs] = useState([]);
  const [detailsOpen, setDetailsOpen] = useState(true);
  const [expandedId, setExpandedId] = useState(null);  // inline-expand in sidebar

  const selectedBooking = useMemo(
    () => bookings.find(b => b.booked_id === selectedId) || null,
    [bookings, selectedId]
  );

  const loadBookings = useCallback(async () => {
    try {
      const { data } = await api.get("/brokerage/margins");
      const list = (data?.bookings || []).filter(b => b?.booked_id);
      setBookings(list);
      if (!selectedId && list.length) setSelectedId(list[0].booked_id);
    } catch (e) {
      console.error(e);
    }
  }, [selectedId]);

  const loadChecklist = useCallback(async (bookedId) => {
    if (!bookedId) return;
    setLoading(true);
    try {
      const [cl, mg, ex] = await Promise.all([
        api.get(`/orisei/workflow/checklist/${bookedId}`),
        api.get(`/orisei/workflow/margin/${bookedId}`),
        api.get(`/shipment-triage/exceptions?booked_id=${bookedId}`).catch(() => ({ data: { items: [] } })),
      ]);
      setChecklist(cl.data);
      setMargin(mg.data);
      setExceptions(
        (ex.data?.items || []).filter(
          e => e.status === "open" || e.status === "acknowledged" || e.status === "in_progress"
        )
      );
      if (mg.data?.has_manual_cost) {
        setCarrierCost(String(mg.data.carrier_cost_usd ?? ""));
        setExtraCost(String(mg.data.extra_costs_usd ?? ""));
      } else {
        setCarrierCost("");
        setExtraCost("");
      }
    } catch (e) {
      console.error(e);
      toast.error("Could not load workflow checklist");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadBookings(); }, [loadBookings]);
  useEffect(() => { if (selectedId) loadChecklist(selectedId); }, [selectedId, loadChecklist]);

  // Load archived documents tied to the current booking
  useEffect(() => {
    if (!selectedId) { setArchivedDocs([]); return; }
    api.get(`/doc-vault?ref_id=${selectedId}&limit=20`)
       .then(r => setArchivedDocs(r.data?.items || []))
       .catch(() => setArchivedDocs([]));
  }, [selectedId, checklist]);

  const filtered = useMemo(() => {
    const s = search.trim().toLowerCase();
    if (!s) return bookings;
    return bookings.filter(b =>
      (b.booked_id || "").toLowerCase().includes(s) ||
      (b.load_id || "").toLowerCase().includes(s) ||
      (b.origin || "").toLowerCase().includes(s) ||
      (b.destination || "").toLowerCase().includes(s) ||
      (b.carrier_name || "").toLowerCase().includes(s) ||
      (b.customer_name || "").toLowerCase().includes(s)
    );
  }, [bookings, search]);

  const markStage = async (stageId, notes) => {
    try {
      const { data } = await api.post(
        `/orisei/workflow/checklist/${selectedId}/mark`,
        { stage_id: stageId, notes: notes || undefined }
      );
      setChecklist(data);
      toast.success(`Marked "${data.stages.find(s => s.id === stageId)?.label}" complete`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not mark stage");
    }
  };

  const unmarkStage = async (stageId) => {
    try {
      const { data } = await api.post(
        `/orisei/workflow/checklist/${selectedId}/unmark`,
        { stage_id: stageId }
      );
      setChecklist(data);
      toast.success("Stage reset");
    } catch (e) {
      toast.error("Could not reset stage");
    }
  };

  const handleStageClick = (stage) => {
    if (stage.completed) {
      if (window.confirm(`Reset "${stage.label}" to incomplete?`)) unmarkStage(stage.id);
      return;
    }
    setPendingStage(stage);
    setNotesText("");
    setNotesOpen(true);
  };

  const confirmMark = async () => {
    if (!pendingStage) return;
    await markStage(pendingStage.id, notesText);
    setNotesOpen(false);
    setPendingStage(null);
  };

  const submitMargin = async () => {
    const cc = parseFloat(carrierCost);
    if (!Number.isFinite(cc) || cc < 0) {
      toast.error("Enter a valid carrier cost");
      return;
    }
    try {
      const { data } = await api.post("/orisei/workflow/margin/quick", {
        booked_id: selectedId,
        carrier_cost_usd: cc,
        extra_costs_usd: parseFloat(extraCost) || 0,
      });
      setMargin({ ...data, has_manual_cost: true });
      toast.success(`Margin: $${data.margin_usd.toLocaleString()} (${data.margin_pct}%)`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not calc margin");
    }
  };

  return (
    <>
      <Topbar
        title="Workflow · Run-the-Load HUD"
        subtitle="AI-coached shipment journey from booking to invoiced"
      />
      <div className="p-4 md:p-6 grid grid-cols-12 gap-4">

        {/* LEFT — booking selector */}
        <Card className="col-span-12 lg:col-span-3 p-4 bg-slate-950/60 border-cyan-500/20" data-testid="workflow-booking-list">
          <div className="flex items-center gap-2 mb-3">
            <Search size={14} className="text-cyan-300" />
            <Input
              data-testid="workflow-search"
              placeholder="Search loads / carrier / city"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="h-8 text-xs bg-slate-900/70 border-white/10"
            />
          </div>
          <div className="text-[10px] uppercase tracking-widest text-slate-500 mb-2 font-mono">
            Active Bookings · {filtered.length}
          </div>
          <div className="space-y-1.5 max-h-[70vh] overflow-y-auto pr-1">
            {filtered.map(b => {
              const isSelected = selectedId === b.booked_id;
              const isExpanded = expandedId === b.booked_id;
              const fmt$ = (n) => n ? `$${Number(n).toLocaleString()}` : "—";
              return (
                <div key={b.booked_id}
                     data-testid={`workflow-card-${b.booked_id}`}
                     className={`rounded-lg border transition-all ${
                       isSelected
                         ? "bg-cyan-500/10 border-cyan-400/50 shadow-[0_0_15px_rgba(34,211,238,0.25)]"
                         : "bg-slate-900/40 border-white/5 hover:border-cyan-400/30"
                     }`}>
                  {/* Header row — click body selects + expands */}
                  <button
                    type="button"
                    data-testid={`workflow-pick-${b.booked_id}`}
                    onClick={() => {
                      setSelectedId(b.booked_id);
                      setExpandedId(prev => prev === b.booked_id ? null : b.booked_id);
                    }}
                    className="w-full text-left p-2.5"
                  >
                    <div className="flex items-center justify-between">
                      <div className="font-mono text-[11px] text-cyan-200">{b.booked_id}</div>
                      <div className="flex items-center gap-1.5">
                        <StatusPill status={b.status} />
                        <ChevronRight
                          size={12}
                          className={`text-slate-400 transition-transform ${isExpanded ? "rotate-90" : ""}`}
                        />
                      </div>
                    </div>
                    <div className="text-xs text-white mt-1 truncate">{b.origin} → {b.destination}</div>
                    <div className="text-[10px] text-slate-400 mt-0.5 truncate flex items-center gap-1">
                      {b.carrier_name || "Unassigned"} · {b.miles ? `${b.miles}mi` : ""}
                      {b.source === "book_load" && (
                        <span className="text-amber-300 ml-1">· REAL</span>
                      )}
                      {b.is_sample && (
                        <span className="text-slate-500 ml-1">· sample</span>
                      )}
                    </div>
                  </button>

                  {/* Inline expandable detail */}
                  {isExpanded && (
                    <div data-testid={`workflow-expand-${b.booked_id}`}
                         className="px-2.5 pb-2.5 pt-1 border-t border-cyan-400/15 space-y-1 text-[10px]">
                      <Row k="Equipment" v={b.equipment || b.mode || "—"} />
                      <Row k="Rate" v={fmt$(b.forecast_rate_usd || b.rate_usd)} tone="amber" />
                      <Row k="Carrier pay" v={fmt$(b.forecast_carrier_pay_usd || b.carrier_pay_usd)} />
                      <Row k="Margin" v={fmt$(b.forecast_margin_usd)} tone="emerald" />
                      <Row k="Pickup" v={b.pickup_date || "—"} />
                      <Row k="Delivery" v={b.delivery_date || "—"} />
                      <Row k="MC #" v={b.carrier_mc || "—"} />
                      <Row k="Commodity" v={b.commodity || "—"} />
                      <Row k="Weight" v={b.weight_lbs ? `${Number(b.weight_lbs).toLocaleString()} lbs` : "—"} />
                      <Row k="Pieces" v={b.pieces || "—"} />
                      <Row k="Booked" v={b.booked_at ? new Date(b.booked_at).toLocaleString() : "—"} />
                      <Row k="Source" v={b.source || "load_board"} />
                      <Row k="Reference" v={b.reference || b.load_id || "—"} />

                      <div className="flex gap-1 pt-1.5 border-t border-white/5 mt-1.5">
                        <button
                          type="button"
                          data-testid={`scroll-detail-${b.booked_id}`}
                          onClick={(e) => {
                            e.stopPropagation();
                            const el = document.querySelector('[data-testid="workflow-drilldown"]');
                            if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
                          }}
                          className="flex-1 px-2 py-1 rounded text-[9px] font-mono uppercase tracking-widest border border-cyan-400/30 text-cyan-200 hover:bg-cyan-500/20 transition"
                        >
                          Jump to drill-down ↓
                        </button>
                        {b.shipment_id && (
                          <a href={`/shipments?id=${b.shipment_id}`}
                             onClick={(e) => e.stopPropagation()}
                             data-testid={`sidebar-shipment-${b.booked_id}`}
                             className="px-2 py-1 rounded text-[9px] font-mono uppercase tracking-widest border border-amber-400/30 text-amber-200 hover:bg-amber-500/20 transition">
                            Shipments →
                          </a>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
            {!filtered.length && (
              <div className="text-xs text-slate-500 py-8 text-center">
                No bookings match.
              </div>
            )}
          </div>
        </Card>

        {/* CENTER — checklist HUD */}
        <Card className="col-span-12 lg:col-span-6 p-5 bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 border-cyan-500/30 relative overflow-hidden" data-testid="workflow-hud">
          {/* Background grid */}
          <div className="pointer-events-none absolute inset-0 opacity-[0.06]"
               style={{ backgroundImage: "linear-gradient(rgba(34,211,238,0.5) 1px, transparent 1px), linear-gradient(90deg, rgba(34,211,238,0.5) 1px, transparent 1px)", backgroundSize: "40px 40px" }} />
          <div className="pointer-events-none absolute -top-32 -right-32 w-96 h-96 rounded-full bg-cyan-500/10 blur-3xl" />
          <div className="pointer-events-none absolute -bottom-32 -left-32 w-96 h-96 rounded-full bg-amber-500/10 blur-3xl" />

          {loading && (
            <div className="absolute inset-0 grid place-items-center bg-slate-950/70 z-20">
              <Loader2 className="animate-spin text-cyan-300" />
            </div>
          )}

          {!checklist && !loading && (
            <div className="text-center text-slate-400 py-16">
              <ClipboardCheck size={42} className="mx-auto mb-3 opacity-40" />
              Pick a booking on the left to load its journey.
            </div>
          )}

          {checklist && (
            <div className="relative z-10">
              {/* Header band */}
              <div className="flex items-center justify-between mb-4">
                <div>
                  <div className="text-[10px] uppercase tracking-[0.3em] text-cyan-300 font-mono">
                    Mission · {checklist.booked_id}
                    <a
                      href={`/document-archive?ref_id=${checklist.booked_id}`}
                      data-testid="workflow-doc-archive-link"
                      title="Open immutable document archive for this load"
                      className="ml-2 inline-flex items-center gap-1 text-[10px] text-amber-300 hover:underline normal-case tracking-normal"
                    >
                      ↳ archive
                    </a>
                  </div>
                  <div className="text-xl font-light text-white mt-1">
                    {checklist.origin} <span className="text-amber-300">→</span> {checklist.destination}
                  </div>
                  <div className="text-xs text-slate-400 mt-0.5">
                    Customer: {checklist.customer_name || "—"} · Carrier: {checklist.carrier_name || "Unassigned"}
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-3xl font-mono text-cyan-300 tabular-nums" data-testid="workflow-pct">
                    {checklist.pct_complete}<span className="text-base text-slate-500">%</span>
                  </div>
                  <div className="text-[10px] text-slate-400 uppercase tracking-widest mt-0.5">
                    {checklist.completed_count} / {checklist.total_count} stages
                  </div>
                </div>
              </div>

              {/* Progress bar */}
              <div className="relative h-2 bg-slate-800/80 rounded-full overflow-hidden mb-6 border border-white/5">
                <div
                  className="absolute inset-y-0 left-0 bg-gradient-to-r from-cyan-400 via-cyan-300 to-emerald-400 transition-all duration-700 shadow-[0_0_18px_rgba(34,211,238,0.7)]"
                  style={{ width: `${checklist.pct_complete}%` }}
                />
              </div>

              {/* Stage rail */}
              <div className="space-y-2.5" data-testid="workflow-stage-list">
                {checklist.stages.map((stage, idx) => {
                  const Icon = ICON_MAP[stage.icon] || ClipboardCheck;
                  const isCurrent = stage.id === checklist.current_stage_id;
                  return (
                    <button
                      key={stage.id}
                      data-testid={`workflow-stage-${stage.id}`}
                      onClick={() => handleStageClick(stage)}
                      className={`group w-full flex items-stretch gap-3 p-3 rounded-lg border text-left transition-all ${
                        stage.completed
                          ? "bg-emerald-500/5 border-emerald-400/40"
                          : isCurrent
                            ? "bg-cyan-500/10 border-cyan-400/60 shadow-[0_0_20px_rgba(34,211,238,0.25)]"
                            : "bg-slate-900/40 border-white/5 hover:border-cyan-400/30"
                      }`}
                    >
                      {/* Step indicator */}
                      <div className={`relative flex-none w-11 h-11 rounded-lg grid place-items-center border ${
                        stage.completed
                          ? "bg-emerald-500/20 border-emerald-400/60 text-emerald-300"
                          : isCurrent
                            ? "bg-cyan-500/20 border-cyan-400/70 text-cyan-200"
                            : "bg-slate-900 border-white/10 text-slate-500"
                      }`}>
                        {stage.completed ? <Check size={20} /> : <Icon size={18} />}
                        <div className="absolute -top-1.5 -left-1.5 w-5 h-5 rounded-full bg-slate-950 border border-white/20 text-[10px] font-mono grid place-items-center text-slate-400">
                          {String(idx + 1).padStart(2, "0")}
                        </div>
                      </div>

                      {/* Body */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <div className={`text-sm font-semibold ${
                            stage.completed ? "text-emerald-200" : isCurrent ? "text-white" : "text-slate-300"
                          }`}>
                            {stage.label}
                          </div>
                          {stage.manual && (
                            <Badge variant="outline" className="border-amber-400/40 text-amber-300 text-[9px] px-1.5 py-0">
                              MANUAL
                            </Badge>
                          )}
                          {isCurrent && !stage.completed && (
                            <Badge className="bg-cyan-500/20 border-cyan-400/40 text-cyan-200 text-[9px]">
                              NEXT
                            </Badge>
                          )}
                        </div>
                        <div className="text-[11px] text-slate-400 mt-0.5 truncate">
                          {stage.description}
                        </div>
                        {stage.completed_at && (
                          <div className="text-[10px] text-emerald-400/70 mt-1 font-mono">
                            ✓ {new Date(stage.completed_at).toLocaleString()}
                          </div>
                        )}
                        {stage.notes && (
                          <div className="text-[11px] text-slate-300 mt-1 italic line-clamp-1">
                            &ldquo;{stage.notes}&rdquo;
                          </div>
                        )}
                      </div>

                      {/* CTA chevron */}
                      <div className="flex-none self-center text-slate-500 group-hover:text-cyan-300 transition">
                        {stage.completed
                          ? <RotateCcw size={14} className="opacity-60" />
                          : <ChevronRight size={16} />}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </Card>

        {/* RIGHT — AI coach + margin */}
        <div className="col-span-12 lg:col-span-3 space-y-4">

          {/* Exception alerts */}
          {exceptions.length > 0 && (
            <Card className="p-4 bg-red-950/40 border-red-400/50 shadow-[0_0_25px_rgba(239,68,68,0.35)] relative overflow-hidden" data-testid="workflow-exceptions">
              <div className="flex items-center gap-2 text-red-300 text-[10px] uppercase tracking-[0.3em] font-mono mb-2">
                <AlertTriangle size={12} className="animate-pulse" /> Active Exceptions
              </div>
              <div className="space-y-2">
                {exceptions.map(ex => (
                  <a key={ex.exception_id} href="/triage"
                     data-testid={`hud-ex-${ex.exception_id}`}
                     className="block p-2 rounded bg-slate-900/60 border border-red-400/30 hover:border-red-400/60 transition">
                    <div className="flex justify-between items-center">
                      <div className="text-xs font-semibold text-white">{ex.advice?.title || ex.exception_type}</div>
                      <span className="text-[9px] font-mono px-1.5 py-0.5 rounded uppercase bg-red-500/20 text-red-200">{ex.severity}</span>
                    </div>
                    <div className="text-[10px] text-slate-300 italic mt-0.5 truncate">{ex.signal}</div>
                  </a>
                ))}
              </div>
              <a href="/triage" className="block text-center text-[11px] text-red-300 mt-2 hover:underline">
                Open AI Triage Console →
              </a>
            </Card>
          )}

          {/* AI coach card */}
          {checklist?.next_action ? (
            <Card className="p-4 bg-gradient-to-br from-cyan-950/60 via-slate-950 to-amber-950/30 border-amber-400/30 relative overflow-hidden" data-testid="workflow-ai-coach">
              <div className="pointer-events-none absolute -top-8 -right-8 w-32 h-32 rounded-full bg-amber-400/15 blur-2xl" />
              <div className="flex items-center gap-2 text-amber-300 text-[10px] uppercase tracking-[0.3em] font-mono">
                <Sparkles size={12} /> AI Co-Pilot
              </div>
              <div className="text-sm font-semibold text-white mt-2">
                {checklist.next_action.title}
              </div>
              <p className="text-xs text-slate-300 mt-2 leading-relaxed">
                {checklist.next_action.advice}
              </p>
              <Button
                data-testid="workflow-cta"
                onClick={() => handleStageClick(
                  checklist.stages.find(s => s.id === checklist.next_action.stage_id))}
                className="mt-3 w-full bg-gradient-to-r from-amber-400 to-amber-500 text-slate-950 font-semibold hover:from-amber-300 hover:to-amber-400"
              >
                {checklist.next_action.cta_label}
                <ArrowRight size={14} className="ml-1.5" />
              </Button>
            </Card>
          ) : checklist ? (
            <Card className="p-4 bg-gradient-to-br from-emerald-950/60 to-slate-950 border-emerald-400/40 text-center" data-testid="workflow-complete">
              <PackageCheck className="mx-auto text-emerald-300 mb-2" size={32} />
              <div className="text-emerald-200 font-semibold">Load Complete</div>
              <div className="text-xs text-slate-300 mt-1">All 8 stages confirmed. Margin recognized.</div>
            </Card>
          ) : null}

          {/* Margin calculator */}
          <Card className="p-4 bg-slate-950/70 border-amber-400/20" data-testid="workflow-margin-card">
            <div className="flex items-center gap-2 text-amber-300 text-[10px] uppercase tracking-[0.3em] font-mono mb-2">
              <DollarSign size={12} /> Quick Margin
            </div>
            <div className="text-xs text-slate-400 mb-3">
              Enter carrier cost to see live margin without waiting for settlement.
            </div>

            <div className="space-y-2">
              <div>
                <Label className="text-[10px] uppercase tracking-widest text-slate-400">
                  Customer rate (locked)
                </Label>
                <div className="text-lg font-mono text-white mt-0.5" data-testid="margin-customer-rate">
                  ${(margin?.customer_rate_usd ?? 0).toLocaleString()}
                </div>
              </div>
              <div>
                <Label className="text-[10px] uppercase tracking-widest text-slate-400">
                  Carrier cost
                </Label>
                <Input
                  data-testid="margin-carrier-cost"
                  type="number" min="0" step="0.01"
                  value={carrierCost}
                  onChange={(e) => setCarrierCost(e.target.value)}
                  placeholder="0.00"
                  className="bg-slate-900/70 border-white/10 text-white"
                />
              </div>
              <div>
                <Label className="text-[10px] uppercase tracking-widest text-slate-400">
                  Other costs (lumper, detention, etc.)
                </Label>
                <Input
                  data-testid="margin-extra-cost"
                  type="number" min="0" step="0.01"
                  value={extraCost}
                  onChange={(e) => setExtraCost(e.target.value)}
                  placeholder="0.00"
                  className="bg-slate-900/70 border-white/10 text-white"
                />
              </div>
              <Button
                data-testid="margin-calc-btn"
                onClick={submitMargin}
                disabled={!selectedId}
                className="w-full bg-amber-500 text-slate-950 hover:bg-amber-400 font-semibold"
              >
                <Zap size={14} className="mr-1.5" /> Calculate
              </Button>
            </div>

            {margin?.has_manual_cost && (
              <div className={`mt-4 p-3 rounded-lg bg-slate-900/70 border border-white/5 ${HEALTH_STYLES[margin.health]?.glow || ""}`}>
                <div className="flex items-baseline justify-between">
                  <div className="text-[10px] uppercase tracking-widest text-slate-400">Margin</div>
                  <div className={`text-[10px] font-mono uppercase ${HEALTH_STYLES[margin.health]?.color}`}>
                    {HEALTH_STYLES[margin.health]?.label}
                  </div>
                </div>
                <div className="text-2xl font-mono mt-1 text-white tabular-nums" data-testid="margin-result-usd">
                  ${margin.margin_usd?.toLocaleString()}
                </div>
                <div className="flex items-center gap-1 text-sm">
                  {margin.margin_pct >= 0
                    ? <TrendingUp size={14} className="text-emerald-400" />
                    : <TrendingDown size={14} className="text-red-400" />}
                  <span className={`font-mono ${margin.margin_pct >= 12 ? "text-emerald-300" : margin.margin_pct >= 6 ? "text-amber-300" : "text-red-300"}`} data-testid="margin-result-pct">
                    {margin.margin_pct?.toFixed(2)}%
                  </span>
                </div>
                <div className="mt-2 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                  <div
                    className={`h-full ${HEALTH_STYLES[margin.health]?.bar || "bg-slate-500"} transition-all`}
                    style={{ width: `${Math.max(0, Math.min(100, (margin.margin_pct || 0) * 4))}%` }}
                  />
                </div>
              </div>
            )}
          </Card>

        </div>
      </div>

      {/* DRILL-DOWN — full load details */}
      {selectedBooking && (
        <div className="px-4 md:px-6 pb-6">
          <Card className="bg-slate-950/70 border-cyan-500/20" data-testid="workflow-drilldown">
            <button
              type="button"
              data-testid="drilldown-toggle"
              onClick={() => setDetailsOpen(v => !v)}
              className="w-full flex items-center justify-between px-4 py-3 hover:bg-slate-900/40 transition"
            >
              <div className="flex items-center gap-2">
                <Search size={14} className="text-cyan-300" />
                <span className="text-xs font-mono uppercase tracking-[0.25em] text-cyan-200">
                  Load Details · drill-down
                </span>
                <Badge className="bg-slate-900 border border-white/10 text-slate-300 text-[10px] font-mono">
                  {selectedBooking.booked_id}
                </Badge>
                {selectedBooking.source === "book_load" && (
                  <Badge className="bg-amber-500/20 text-amber-200 border border-amber-400/40 text-[10px] font-mono">
                    ↳ FROM BOOK LOAD
                  </Badge>
                )}
                {selectedBooking.is_sample && (
                  <Badge className="bg-slate-700/40 text-slate-300 border border-white/10 text-[10px] font-mono">
                    SAMPLE DATA
                  </Badge>
                )}
              </div>
              <ChevronRight
                size={16}
                className={`text-slate-400 transition-transform ${detailsOpen ? "rotate-90" : ""}`}
              />
            </button>

            {detailsOpen && (
              <div className="border-t border-white/5 grid grid-cols-12 gap-4 p-4">
                {/* Trip */}
                <div className="col-span-12 md:col-span-4 space-y-2">
                  <div className="text-[10px] font-mono uppercase tracking-widest text-amber-300 mb-1">Trip</div>
                  <DetailRow label="Origin" value={selectedBooking.origin} />
                  <DetailRow label="Destination" value={selectedBooking.destination} />
                  <DetailRow label="Equipment" value={selectedBooking.equipment} />
                  <DetailRow label="Miles" value={selectedBooking.miles?.toLocaleString() || "—"} />
                  <DetailRow label="Pickup" value={selectedBooking.pickup_date || "—"} />
                  <DetailRow label="Delivery" value={selectedBooking.delivery_date || "—"} />
                </div>

                {/* Carrier + financials */}
                <div className="col-span-12 md:col-span-4 space-y-2">
                  <div className="text-[10px] font-mono uppercase tracking-widest text-amber-300 mb-1">Carrier · Financials</div>
                  <DetailRow label="Carrier" value={selectedBooking.carrier_name} />
                  <DetailRow label="MC #" value={selectedBooking.carrier_mc || "—"} />
                  <DetailRow label="Rate" value={selectedBooking.forecast_rate_usd ? `$${Number(selectedBooking.forecast_rate_usd).toLocaleString()}` : "—"} />
                  <DetailRow label="Carrier pay" value={selectedBooking.forecast_carrier_pay_usd ? `$${Number(selectedBooking.forecast_carrier_pay_usd).toLocaleString()}` : "—"} />
                  <DetailRow label="Forecast margin" value={selectedBooking.forecast_margin_usd ? `$${Number(selectedBooking.forecast_margin_usd).toLocaleString()}` : "—"} accent="emerald" />
                  <DetailRow label="Status" value={selectedBooking.status} />
                </div>

                {/* Freight */}
                <div className="col-span-12 md:col-span-4 space-y-2">
                  <div className="text-[10px] font-mono uppercase tracking-widest text-amber-300 mb-1">Freight</div>
                  <DetailRow label="Commodity" value={selectedBooking.commodity || "—"} />
                  <DetailRow label="Pieces" value={selectedBooking.pieces || "—"} />
                  <DetailRow label="Weight" value={selectedBooking.weight_lbs ? `${Number(selectedBooking.weight_lbs).toLocaleString()} lbs` : "—"} />
                  <DetailRow label="Booked at" value={selectedBooking.booked_at ? new Date(selectedBooking.booked_at).toLocaleString() : "—"} />
                  <DetailRow label="Source" value={selectedBooking.source || "load_board"} />
                  <DetailRow label="Reference" value={selectedBooking.reference || selectedBooking.load_id || "—"} />
                </div>

                {/* Linked archived documents */}
                <div className="col-span-12 mt-2 border-t border-white/5 pt-3">
                  <div className="flex items-center justify-between mb-2">
                    <div className="text-[10px] font-mono uppercase tracking-widest text-amber-300">
                      Linked archived documents · {archivedDocs.length}
                    </div>
                    <a href={`/document-archive?ref_id=${selectedId}`}
                       data-testid="open-archive-link"
                       className="text-[10px] font-mono text-cyan-300 hover:underline">
                      Open Document Archive →
                    </a>
                  </div>
                  {archivedDocs.length === 0 ? (
                    <div className="text-[11px] text-slate-500 italic">
                      No documents archived for this load yet — generating a BOL, rate-con, or invoice will auto-archive it here.
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                      {archivedDocs.map(d => (
                        <a key={d.archive_id}
                           href={`/document-archive?doc_id=${d.doc_id}`}
                           data-testid={`linked-doc-${d.archive_id}`}
                           className="block p-2 rounded bg-slate-900/60 border border-white/5 hover:border-amber-400/40 transition">
                          <div className="flex items-center justify-between">
                            <div className="text-[10px] font-mono uppercase tracking-widest text-amber-200">{d.doc_type}</div>
                            <div className="text-[10px] font-mono text-slate-500">v{d.version}</div>
                          </div>
                          <div className="text-xs text-white mt-0.5 font-mono truncate">{d.doc_id}</div>
                          <div className="text-[10px] text-slate-500 mt-0.5">{new Date(d.created_at).toLocaleString()}</div>
                        </a>
                      ))}
                    </div>
                  )}
                </div>

                {/* Quick links */}
                <div className="col-span-12 flex flex-wrap gap-2 mt-2 pt-3 border-t border-white/5">
                  {selectedBooking.shipment_id && (
                    <a href={`/shipments?id=${selectedBooking.shipment_id}`}
                       data-testid="open-shipment-link"
                       className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md text-xs text-cyan-200 bg-slate-900 border border-cyan-400/30 hover:border-cyan-400/60">
                      <Truck size={11} /> View in Shipments
                    </a>
                  )}
                  <a href={`/triage?booked_id=${selectedId}`}
                     data-testid="open-triage-link"
                     className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md text-xs text-rose-200 bg-slate-900 border border-rose-400/30 hover:border-rose-400/60">
                    <AlertTriangle size={11} /> AI Triage
                  </a>
                  <a href={`/factoring?booked_id=${selectedId}`}
                     data-testid="open-factoring-link"
                     className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md text-xs text-emerald-200 bg-slate-900 border border-emerald-400/30 hover:border-emerald-400/60">
                    <DollarSign size={11} /> Factoring
                  </a>
                </div>
              </div>
            )}
          </Card>
        </div>
      )}
      <Dialog open={notesOpen} onOpenChange={setNotesOpen}>
        <DialogContent className="bg-slate-950 border-cyan-500/30 text-white">
          <DialogHeader>
            <DialogTitle className="text-cyan-200">
              Confirm &ldquo;{pendingStage?.label}&rdquo;
            </DialogTitle>
            <DialogDescription className="text-slate-400 text-xs">
              {pendingStage?.description}
            </DialogDescription>
          </DialogHeader>
          <div>
            <Label className="text-[11px] uppercase tracking-widest text-slate-400">
              Notes (optional)
            </Label>
            <Textarea
              data-testid="workflow-notes-input"
              value={notesText}
              onChange={(e) => setNotesText(e.target.value)}
              placeholder="e.g. Driver picked up 13:42 CST, seal #87431"
              className="bg-slate-900 border-white/10 mt-1 min-h-[90px]"
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setNotesOpen(false)} className="bg-slate-900 border-white/10">
              Cancel
            </Button>
            <Button
              data-testid="workflow-confirm-mark"
              onClick={confirmMark}
              className="bg-gradient-to-r from-cyan-400 to-cyan-500 text-slate-950 font-semibold"
            >
              <Check size={14} className="mr-1.5" /> Mark Complete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function StatusPill({ status }) {
  const cls = {
    booked:   "bg-cyan-500/20 text-cyan-200 border-cyan-400/40",
    settled:  "bg-emerald-500/20 text-emerald-200 border-emerald-400/40",
    cancelled:"bg-red-500/20 text-red-200 border-red-400/40",
  }[status] || "bg-slate-800 text-slate-300 border-white/10";
  return (
    <span className={`px-1.5 py-0.5 rounded text-[9px] uppercase tracking-widest border ${cls}`}>
      {status || "?"}
    </span>
  );
}

function DetailRow({ label, value, accent }) {
  const valCls = accent === "emerald" ? "text-emerald-200" : "text-white";
  return (
    <div className="flex items-baseline justify-between gap-2 text-xs">
      <div className="text-[10px] font-mono uppercase tracking-widest text-slate-500 shrink-0">{label}</div>
      <div className={`${valCls} font-mono text-right truncate`} title={String(value ?? "")}>{value ?? "—"}</div>
    </div>
  );
}

// Sidebar inline-expand row: tighter, mono, tone-aware
function Row({ k, v, tone }) {
  const valCls =
    tone === "emerald" ? "text-emerald-200" :
    tone === "amber"   ? "text-amber-200"   :
                         "text-slate-200";
  return (
    <div className="flex items-baseline justify-between gap-2">
      <div className="text-[9px] font-mono uppercase tracking-widest text-slate-500 shrink-0">{k}</div>
      <div className={`${valCls} font-mono text-[10px] text-right truncate`}
           title={String(v ?? "")}>{v ?? "—"}</div>
    </div>
  );
}
